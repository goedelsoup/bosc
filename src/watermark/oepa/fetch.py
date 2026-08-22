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

Two eDocument-portal behaviours break those rules and are handled explicitly, because both
corrupt a bulk fetch while every individual response looks fine:

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

FetchStatus = Literal["downloaded", "skipped_existing", "conflict", "error", "truncated"]

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

    Only applied to bodies that actually announce themselves as PDFs — a non-PDF response
    (an HTML error page, say) is not judged by this rule and is left to the callers that
    already handle it.
    """
    if not content.startswith(_PDF_MAGIC):
        return True
    return content.rstrip().endswith(_PDF_EOF)


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

    if not _pdf_is_complete(content):
        base.note = (
            f"refused: PDF body of {len(content)} bytes has no trailing %%EOF — the portal "
            "serves some documents truncated with a Content-Length that agrees, so this is "
            "not a short read to retry blindly. Re-fetch and compare before committing."
        )
        log.warning("oepa.fetch.truncated", url=url, bytes=len(content))
        return base.model_copy(update={"status": "truncated", "bytes": len(content)})

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

    A **failed** fetch has no hash, so it cannot be keyed the same way and would otherwise be
    unreachable forever: the retry that succeeds carries a digest, lands under a different key,
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
