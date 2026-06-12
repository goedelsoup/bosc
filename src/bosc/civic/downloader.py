"""Download a body's meeting documents into the corpus, under chain of custody.

Takes the ``MeetingDoc`` inventory a fetcher produced and pulls each binary into
``data/documents/<slug>/meetings/`` — the raw, immutable, LFS-tracked evidence tree
— then writes a non-destructive **download manifest** under
``data/extracted/<slug>/meetings/`` recording, per file: the as-received filename,
source URL, sha256, byte count, content-type, fetch time, and the
listing-derived date/kind.

Chain-of-custody rules this enforces:

* **As-received names are preserved.** The on-disk name is what the server
  delivered (Content-Disposition → URL basename); a human/indexer-friendly
  ``canonical`` name is recorded in the manifest, never imposed on the file.
* **Never overwrite a differing byte.** Re-downloading an unchanged file is a
  no-op (hash match); a *different* file claiming the same name is written beside
  it (``name.<sha8>.ext``) and flagged ``conflict`` — originals are immutable.
* **Dates are provisional.** A date parsed from a records-page listing is recorded
  with ``evidence: listing`` — it is **not** content-verified. Content
  verification (text layer / OCR of the file itself) is the downstream OCR step,
  mirroring ``commissioners/minutes/filename-map.yaml``.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from bosc.civic._http import BROWSER_HEADERS
from bosc.civic.models import MeetingDoc, Subdivision
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

# (content, content_type, content_disposition) for a URL — injectable for tests.
BytesFetcher = Callable[[str, Settings], "tuple[bytes, str | None, str | None]"]

_CD_FILENAME = re.compile(r"""filename\*?=(?:UTF-8''|)["']?([^"';]+)""", re.IGNORECASE)
_SAFE = re.compile(r"[^A-Za-z0-9._ -]+")


class DownloadedDoc(BaseModel):
    """One meeting document's download outcome + provenance."""

    model_config = ConfigDict(extra="forbid")

    filename: str  # as-received name on disk (relative to the meetings dir)
    canonical: str | None  # indexer-friendly <date>-<kind>.<ext>, manifest-only
    source_url: str
    body: str | None
    kind: str
    date: str | None  # listing-derived (NOT content-verified)
    title: str | None
    sha256: str | None
    bytes: int | None
    content_type: str | None
    fetched_at: str | None
    status: str  # downloaded | skipped_existing | conflict | error
    note: str | None = None


class DownloadReport(BaseModel):
    """Outcome of a download run for one subdivision."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    dest_dir: str
    source_page: str | None
    docs: list[DownloadedDoc]

    @property
    def downloaded(self) -> int:
        return sum(1 for d in self.docs if d.status == "downloaded")

    @property
    def skipped(self) -> int:
        return sum(1 for d in self.docs if d.status == "skipped_existing")

    @property
    def conflicts(self) -> int:
        return sum(1 for d in self.docs if d.status == "conflict")

    @property
    def errors(self) -> int:
        return sum(1 for d in self.docs if d.status == "error")


# Fallback extensions when the name carries none (CivicPlus ViewFile URLs like
# /AgendaCenter/ViewFile/Minutes/_05062024-853 have no extension but serve a PDF).
_CONTENT_EXT = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/html": ".html",
}


def derive_filename(
    url: str, *, content_disposition: str | None = None, content_type: str | None = None
) -> str:
    """As-received filename: Content-Disposition, else the URL path basename.

    Percent-decoded and path-stripped; spaces/odd chars collapsed but the stem is
    preserved verbatim. If the result has no extension, one is appended from
    ``content_type`` so extensionless CivicPlus downloads index as the PDFs they are.
    Never returns an empty or path-bearing name.
    """
    name = ""
    if content_disposition and (m := _CD_FILENAME.search(content_disposition)):
        name = unquote(m.group(1).strip())  # RFC5987 filename*=…%20… and Wix %20 names
    if not name:
        name = unquote(urlparse(url).path).rsplit("/", 1)[-1]
    name = _SAFE.sub("_", name.replace("/", "_")).strip(" .") or "document"
    if "." not in name and content_type:
        ct = content_type.split(";", 1)[0].strip().lower()
        name += _CONTENT_EXT.get(ct, "")
    return name


def _canonical_name(doc: MeetingDoc, filename: str) -> str | None:
    """An indexer-friendly ``<YYYY-MM-DD>-<kind>.<ext>`` (manifest-only), if dated."""
    if not doc.date:
        return None
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{doc.date}-{doc.kind}.{ext}"


def _get_bytes(url: str, settings: Settings) -> tuple[bytes, str | None, str | None]:
    """Default network fetch: stream a URL to bytes + content-type + disposition."""
    with httpx.stream(
        "GET",
        url,
        follow_redirects=True,
        timeout=settings.hydro_request_timeout_s,
        headers=BROWSER_HEADERS,
    ) as resp:
        resp.raise_for_status()
        content = resp.read()
        return content, resp.headers.get("content-type"), resp.headers.get("content-disposition")


def download_meetings(
    subdivision: Subdivision,
    docs: list[MeetingDoc],
    *,
    settings: Settings | None = None,
    dest_root: Path | None = None,
    limit: int | None = None,
    fetcher: BytesFetcher = _get_bytes,
    source_page: str | None = None,
) -> DownloadReport:
    """Download ``docs`` into ``data/documents/<slug>/meetings/`` (chain of custody).

    Idempotent: an identical existing file is skipped; a differing file under the
    same name is written beside it and flagged ``conflict`` (never overwritten).
    ``limit`` caps how many are pulled this run (the rest are simply not fetched —
    a later run resumes). ``fetcher`` is injectable for tests. ``source_page`` is the
    listing actually scraped (the ``--url`` override for bodies whose minutes/agenda
    pages differ); it falls back to the registry ``records_url`` for the manifest.
    """
    settings = settings or get_settings()
    dest = dest_root or (settings.documents_dir / subdivision.slug / "meetings")
    dest.mkdir(parents=True, exist_ok=True)
    selected = docs[:limit] if limit is not None else docs
    results: list[DownloadedDoc] = []
    for doc in selected:
        results.append(_download_one(doc, dest, settings, fetcher))
    log.info(
        "civic.download",
        slug=subdivision.slug,
        downloaded=sum(1 for d in results if d.status == "downloaded"),
        skipped=sum(1 for d in results if d.status == "skipped_existing"),
        conflicts=sum(1 for d in results if d.status == "conflict"),
        errors=sum(1 for d in results if d.status == "error"),
    )
    return DownloadReport(
        slug=subdivision.slug,
        dest_dir=str(dest),
        source_page=source_page or subdivision.publishing.records_url,
        docs=results,
    )


def _download_one(
    doc: MeetingDoc, dest: Path, settings: Settings, fetcher: BytesFetcher
) -> DownloadedDoc:
    base = DownloadedDoc(
        filename="",
        canonical=None,
        source_url=doc.url,
        body=doc.body,
        kind=doc.kind,
        date=doc.date,
        title=doc.title,
        sha256=None,
        bytes=None,
        content_type=None,
        fetched_at=None,
        status="error",
    )
    try:
        content, ctype, disposition = fetcher(doc.url, settings)
    except httpx.HTTPError as exc:
        base.note = f"fetch failed: {type(exc).__name__}"
        return base

    digest = hashlib.sha256(content).hexdigest()
    filename = derive_filename(doc.url, content_disposition=disposition, content_type=ctype)
    target = dest / filename
    status = "downloaded"
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            status = "skipped_existing"
        else:
            # Same name, different bytes — keep both; never overwrite evidence.
            filename = f"{target.stem}.{digest[:8]}{target.suffix}"
            target = dest / filename
            status = "conflict"
    if status != "skipped_existing":
        target.write_bytes(content)

    return base.model_copy(
        update={
            "filename": filename,
            "canonical": _canonical_name(doc, filename),
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


def write_manifest(report: DownloadReport, out_path: Path) -> Path:
    """Write the non-destructive download manifest (mirrors filename-map.yaml).

    Merges with an existing manifest at ``out_path``, keyed by ``source_url`` (this
    run wins for a re-downloaded URL). A body that posts minutes and agendas on
    *separate* pages downloads in two runs (the second with ``--url``); both must
    accumulate into the one manifest the indexer reads, so ``source_pages`` is a list
    and ``counts`` are recomputed across the merged set.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    by_url: dict[str | None, dict[str, Any]] = {}
    source_pages: list[str] = []
    if out_path.exists():
        existing = yaml.safe_load(out_path.read_text(encoding="utf-8")) or {}
        if isinstance(existing, dict):
            for prior in existing.get("documents", []):
                by_url[prior.get("source_url")] = prior
            prior_meta = existing.get("meta", {}) or {}
            prior_pages = prior_meta.get("source_pages")
            if isinstance(prior_pages, list):
                source_pages.extend(p for p in prior_pages if isinstance(p, str))
            elif isinstance(prior_meta.get("source_page"), str):  # migrate the old key
                source_pages.append(prior_meta["source_page"])
    for d in report.docs:
        by_url[d.source_url] = d.model_dump()
    if report.source_page and report.source_page not in source_pages:
        source_pages.append(report.source_page)
    merged = list(by_url.values())

    def _count(status: str) -> int:
        return sum(1 for d in merged if d.get("status") == status)

    doc = {
        "meta": {
            "subject": f"{report.slug} meeting-document download manifest",
            "slug": report.slug,
            "source_pages": source_pages,
            "dest_dir": report.dest_dir,
            "generated_at": datetime.now(UTC).date().isoformat(),
            "policy": "non-destructive — originals keep as-received names; this is an "
            "alias/provenance layer only.",
            "date_evidence": "listing — dates are parsed from the records-page link "
            "text/filename, NOT content-verified. OCR of each file is the verification step.",
            "counts": {
                "total": len(merged),
                "downloaded": _count("downloaded"),
                "skipped_existing": _count("skipped_existing"),
                "conflicts": _count("conflict"),
                "errors": _count("error"),
            },
        },
        "documents": merged,
    }
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_path
