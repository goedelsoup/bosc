"""Download OEPA/DAM permit PDFs and write a filename-map manifest.

Implements the ``watermark oepa fetch`` backend: given a list of URLs (from a discovery
manifest or constructed from bare permit IDs), stream each PDF into
``data/documents/oepa/<site-slug>/`` and record provenance in
``data/documents/oepa/<site-slug>/filename-map.yaml``.

Chain-of-custody rules (mirrors :mod:`watermark.civic.downloader`):

* Names are as-received (Content-Disposition, else URL basename).
* An identical existing file is skipped (hash match → ``skipped_existing``).
* A differing file under the same name is kept alongside the original
  (``<name>.<sha8>.ext``, status ``conflict``).

Three eDocument-portal behaviours break those rules and are handled explicitly, because each
corrupts a bulk fetch while every individual response looks fine:

* **A portal document has no ``Content-Disposition`` and no filename in its URL path.** The
  document is addressed by query string (``ViewDocument.aspx?docid=4192703``), so the
  as-received basename is ``ViewDocument.aspx`` for *every* document the portal serves —
  a 261-document fetch would land one file plus 260 ``conflict`` rows, each reported as
  "same name, different bytes" when nothing actually collided. :func:`_basename` names these
  ``edoc-<docid>.pdf`` instead, matching the convention the corpus already uses for the
  hand-curated west-union and urbana trees.
* **At least one docid is served truncated at exactly 2 MiB**, with the server's own
  ``Content-Length`` agreeing, so neither a short read nor a length mismatch reveals it.
  :func:`_pdf_is_complete` checks for the trailing ``%%EOF`` marker and the fetch is recorded
  ``truncated`` rather than written — a silently half-copied PDF is the one outcome this
  corpus cannot tolerate, since ``data/documents/**`` is litigation evidence.
* **A docid the portal cannot serve is answered with an EMPTY 200, not a 404** — verified
  2026-08-23 against ``docid=4116210``: ``HTTP 200``, ``Content-Type: text/html``,
  ``Content-Length: 0``, no body at all. Written naively that is a 0-byte ``.pdf`` in the
  corpus, hashed to the empty-string digest and recorded ``downloaded`` — a file that exists,
  is empty, and reads as a successful acquisition, which is worse than the truncation case
  because nothing about the row looks wrong (#2091). :func:`_refusal` classifies the body
  BEFORE anything is hashed or written: a zero-length body is ``empty`` and an HTML body is
  ``not_a_document``.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.civic._http import _browser_request
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

# DAM URL prefix for constructing permit URLs from bare IDs.
_DAM_PERMIT_BASE = (
    "https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/{id}.pdf"
)

FetchStatus = Literal[
    "downloaded",
    "skipped_existing",
    "conflict",
    "error",
    "truncated",
    "empty",
    "not_a_document",
]

# The portal addresses a document by query string, not by path, so its URL carries no
# filename at all. The docid IS the as-served identity.
_PORTAL_DOC_RE = re.compile(r"ViewDocument\.aspx\?docid=(\d+)", re.I)

# A PDF ends with a %%EOF marker, optionally followed by whitespace. The portal has served
# a response truncated at exactly 2 MiB whose Content-Length agreed with the short body, so
# the marker is the only signal that the bytes are incomplete.
#
# The marker must be the LAST thing in the file, not merely present near the end: a body cut
# mid-object after an incremental-update section still carries an earlier `%%EOF` well inside
# any trailing window, and a substring test would pass it. Verified against all 261 documents
# of the Lima WWTP pull — every one ends with the marker under `rstrip()`, so the strict rule
# costs nothing on real agency PDFs.
_PDF_MAGIC = b"%PDF-"
_PDF_EOF = b"%%EOF"

# An HTML body under a ``.pdf`` name is the same defect class as a truncated one: a file that
# exists and is not the document. The declared type is the primary signal (the portal answers
# ``text/html`` for a docid it will not serve), and the body is sniffed as well because a
# missing or mislabelled ``Content-Type`` must not be the thing that lets an error page in.
# Both are checked only AFTER the PDF magic, so a real PDF served under a wrong content type
# is still committed — the bytes decide what a document is, not the header.
_HTML_TYPES = frozenset({"text/html", "application/xhtml+xml"})
_HTML_SNIFF = (b"<!doctype html", b"<html", b"<!--")
# A UTF-8 BOM ahead of the markup is invisible to ``bytes.lstrip()``, which strips ASCII
# whitespace only — so a BOM'd error page mislabelled ``application/pdf`` would sniff clean and
# be written under a .pdf name. ASP.NET emits one whenever the response encoding says to.
_UTF8_BOM = b"\xef\xbb\xbf"


class FetchedPermit(BaseModel):
    """Outcome of one permit download."""

    model_config = ConfigDict(extra="forbid")

    filename: str
    permit_id: str | None
    source_url: str
    sha256: str | None
    bytes: int | None
    content_type: str | None
    fetched_at: str | None
    status: FetchStatus
    note: str | None = None


def dam_url(permit_id: str) -> str:
    """Construct the standard DAM permit URL for a bare permit ID."""
    return _DAM_PERMIT_BASE.format(id=permit_id)


def _pdf_is_complete(content: bytes) -> bool:
    """Whether a PDF response carries its terminating ``%%EOF`` marker.

    Judges ONLY bodies that announce themselves as PDFs; anything else is waved through here
    and classified by :func:`_refusal` instead. That division used to read "left to the callers
    that already handle it", and no caller did: ``b"".startswith(b"%PDF-")`` is ``False``, so an
    *empty* body took the non-PDF branch and was written to the corpus as a 0-byte ``.pdf``
    marked ``downloaded`` (#2091). :func:`_refusal` is now the single gate — never call this
    one on its own to decide whether a response may be committed.
    """
    if not content.startswith(_PDF_MAGIC):
        return True
    return content.rstrip().endswith(_PDF_EOF)


def _looks_like_html(content: bytes, content_type: str | None) -> bool:
    """Whether a non-PDF body is an HTML page — by declared type, else by sniffing it."""
    if content_type and content_type.split(";", 1)[0].strip().lower() in _HTML_TYPES:
        return True
    head = content[:512].lstrip().removeprefix(_UTF8_BOM).lstrip().lower()
    return head.startswith(_HTML_SNIFF)


def _refusal(content: bytes, content_type: str | None) -> tuple[FetchStatus, str] | None:
    """Classify a response body that must not enter the corpus; ``None`` means write it.

    The single gate in front of the write path, and the order is the point — emptiness is
    tested first because a zero-length body answers no other question correctly, and the PDF
    magic is tested before the content type because the bytes decide what a document is.

    Three distinct outcomes, not one, because the manifest note has to say the right thing:

    * ``empty`` — nothing was served at all. For the eDocument portal this is a *negative
      result* about a docid, not a transport failure to retry: the portal answers a docid it
      cannot serve with ``HTTP 200`` / ``Content-Type: text/html`` / ``Content-Length: 0``
      rather than a 404 (verified against ``docid=4116210``, 2026-08-23).
    * ``truncated`` — a real PDF, cut short. Re-fetch and compare; the bytes we hold are a
      prefix of a document that exists.
    * ``not_a_document`` — an HTML page under a URL fetched for a PDF, i.e. an error, session
      or landing page. Read it in a browser before re-fetching; the URL is likely wrong.
    """
    if not content:
        return (
            "empty",
            "refused: the server answered 200 with a ZERO-LENGTH body — nothing was served, so "
            "there is no document to commit. The Ohio EPA eDocument portal answers a docid it "
            "cannot serve this way (200, Content-Type: text/html, Content-Length: 0) instead of "
            "404ing, so an empty body is a negative result about the docid, not a short read to "
            "retry blindly. Confirm the docid before re-fetching.",
        )
    if content.startswith(_PDF_MAGIC):
        if not _pdf_is_complete(content):
            return (
                "truncated",
                f"refused: PDF body of {len(content)} bytes has no trailing %%EOF — the portal "
                "serves some documents truncated with a Content-Length that agrees, so this is "
                "not a short read to retry blindly. Re-fetch and compare before committing.",
            )
        return None
    if _looks_like_html(content, content_type):
        return (
            "not_a_document",
            f"refused: the response is an HTML page ({content_type or 'no Content-Type'}, "
            f"{len(content)} bytes), not the PDF this URL was fetched for — an error, session "
            "or landing page. Written under the derived .pdf name it would read as a committed "
            "document. Open the URL in a browser and confirm it before re-fetching.",
        )
    return None


def _basename(url: str, content_disposition: str | None) -> str:
    portal = _PORTAL_DOC_RE.search(url)
    if portal:
        return f"edoc-{portal.group(1)}.pdf"
    if content_disposition:
        for part in content_disposition.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                name = part[9:].strip().strip('"')
                if name:
                    return name
    return urlparse(url).path.rsplit("/", 1)[-1] or "document.pdf"


def fetch_one(
    url: str,
    dest_dir: Path,
    *,
    permit_id: str | None = None,
    settings: Settings | None = None,
) -> FetchedPermit:
    """Stream one URL to ``dest_dir``; return the outcome record."""
    settings = settings or get_settings()
    base = FetchedPermit(
        filename="",
        permit_id=permit_id,
        source_url=url,
        sha256=None,
        bytes=None,
        content_type=None,
        fetched_at=None,
        status="error",
    )
    try:
        with _browser_request("GET", url, settings, stream=True) as resp:
            content = resp.read()
            ctype = resp.headers.get("content-type")
            disposition = resp.headers.get("content-disposition")
    except httpx.HTTPError as exc:
        base.note = f"fetch failed: {type(exc).__name__}: {exc}"
        log.warning("oepa.fetch.error", url=url, error=str(exc))
        return base

    refusal = _refusal(content, ctype)
    if refusal is not None:
        status_refused, base.note = refusal[0], refusal[1]
        # WARNING, never DEBUG: two errors buried in seventy-eight debug lines are
        # indistinguishable from zero errors (#1994).
        log.warning(f"oepa.fetch.{status_refused}", url=url, bytes=len(content), content_type=ctype)
        return base.model_copy(
            update={"status": status_refused, "bytes": len(content), "content_type": ctype}
        )

    digest = hashlib.sha256(content).hexdigest()
    filename = _basename(url, disposition)
    target = dest_dir / filename
    status: FetchStatus = "downloaded"

    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            status = "skipped_existing"
        else:
            filename = f"{target.stem}.{digest[:8]}{target.suffix}"
            target = dest_dir / filename
            status = "conflict"

    if status != "skipped_existing":
        dest_dir.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    log.info("oepa.fetch.done", filename=filename, status=status, bytes=len(content))
    return base.model_copy(
        update={
            "filename": filename,
            "sha256": digest,
            "bytes": len(content),
            "content_type": ctype,
            "fetched_at": datetime.now(UTC).isoformat(),
            "status": status,
            "note": "same name, different bytes — kept alongside original"
            if status == "conflict"
            else None,
        }
    )


#: Reviewed keys a human adds to a ``filename-map`` entry that no fetch can reproduce — the
#: canonical name of the sub-document, the date verified from its own text layer, the
#: as-received DAM basename behind a collision-suffixed filename, and any review note. A
#: re-fetch of the *same bytes* must not erase them.
_REVIEWED_KEYS = ("canonical_name", "content_verified_date", "as_received_name")

_DEFAULT_META = {
    "subject": "OEPA/DAM permit download manifest",
    "policy": "non-destructive — originals keep as-received names",
}


def update_filename_map(records: list[FetchedPermit], map_path: Path) -> None:
    """Merge new fetch records into ``filename-map.yaml`` — keyed by ``(source_url, sha256)``.

    Chain of custody, two ways (#1406):

    * **A slot that later serves different bytes does not overwrite the earlier capture.**
      Ohio EPA re-serves ``permits/doc/<id>.pdf`` in place when a permit is modified, so the
      same URL yields the ``*VD`` renewal one month and the ``*WD`` modification the next.
      Both files are on disk under the fetcher's collision rule; keying the manifest on the URL
      alone silently dropped the older one's provenance — a document we hold with no record of
      where it came from. The key is the URL *and* the content hash.
    * **Reviewed fields survive a re-fetch.** ``canonical_name`` / ``content_verified_date`` /
      ``as_received_name`` and a hand-written ``note`` are the human half of the manifest and
      are not derivable from an HTTP response; they are carried forward onto the matching entry.
      A hand-authored ``meta`` is likewise preserved (only ``generated_at`` is refreshed).

    A fetch that produced no file — an HTTP **error**, or a body :func:`_refusal` rejected as
    ``empty`` / ``not_a_document`` / ``truncated`` — has no hash, so it cannot be keyed the same
    way and would otherwise be unreachable forever: the retry that succeeds carries a digest, lands under a different key,
    and leaves the failure behind as a permanent row with an empty ``filename`` describing no
    document. The Lima WWTP pull hit that immediately — the portal 500'd on 22 of 261 documents
    and served every one of them on retry, leaving a manifest of 283 rows against 261 files.
    So a record that *succeeds* first retires any unsuccessful row for the same URL. Two
    successful captures of one URL still coexist; that is the ``*VD``/``*WD`` case above, and
    it is the whole reason the hash is in the key.
    """
    from typing import Any

    def key(url: str, sha: str | None) -> tuple[str, str | None]:
        return (url, sha)

    # Entry order is preserved, and an entry is addressable only if the fetcher could have
    # written it. A map may also hold WHOLLY hand-authored entries — the urbana and
    # west-union maps predate this fetcher and key their documents by ``edoc_id`` with no
    # ``source_url`` at all. Those carry no fetch identity, so they are never merged
    # against and are written back verbatim; reading them as fetch records raised KeyError
    # and blocked `watermark oepa fetch` outright on any site holding a curated map.
    ordered: list[dict[str, Any]] = []
    existing: dict[tuple[str, str | None], int] = {}
    meta: dict[str, Any] = dict(_DEFAULT_META)
    if map_path.exists():
        data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
        meta = {**meta, **(data.get("meta") or {})}
        for entry in data.get("documents", []):
            ordered.append(entry)
            url = entry.get("source_url")
            if url is not None:
                existing[key(url, entry.get("sha256"))] = len(ordered) - 1

    # A URL that succeeds ANYWHERE in this batch retires its hashless rows, computed up front
    # rather than as each record is walked. Order-dependent retirement missed the batch that
    # succeeds and then errors on the same URL — the failure is appended after the success has
    # already run, so nothing retires it and the phantom row survives.
    succeeded_urls = {r.source_url for r in records if r.sha256 is not None}

    def _retire_failures_for(url: str) -> None:
        """Drop rows for ``url`` that never produced a file (no hash, so no identity)."""
        if existing.pop(key(url, None), None) is None:
            return
        ordered[:] = [
            e for e in ordered if not (e.get("source_url") == url and e.get("sha256") is None)
        ]
        # Indices shifted; rebuild the address book rather than patch it.
        existing.clear()
        for i, entry in enumerate(ordered):
            u = entry.get("source_url")
            if u is not None:
                existing[key(u, entry.get("sha256"))] = i

    for r in records:
        if r.source_url in succeeded_urls:
            _retire_failures_for(r.source_url)
            if r.sha256 is None:
                # A failed attempt on a URL this batch also captured. It describes an HTTP
                # event, not a document, and the capture is the record that survives.
                continue
        k = key(r.source_url, r.sha256)
        index = existing.get(k)
        prior = ordered[index] if index is not None else {}
        merged = r.model_dump()
        for field in _REVIEWED_KEYS:
            if field in prior:
                merged[field] = prior[field]
        # A reviewed note outranks the fetcher's boilerplate; a fetch error still speaks.
        if prior.get("note") and r.status != "error":
            merged["note"] = prior["note"]
        if index is None:
            ordered.append(merged)
            existing[k] = len(ordered) - 1
        else:
            ordered[index] = merged

    meta["generated_at"] = datetime.now(UTC).date().isoformat()
    doc = {"meta": meta, "documents": ordered}
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
