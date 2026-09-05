"""Index downloaded meeting documents: extract text, verify dates, scan for corridor topics.

Reads a body's ``download-manifest.yaml``, opens each downloaded file from the
evidence tree, pulls its text (PDF text layer / DOCX / HTML — **no OCR**, see below;
the DOCX and HTML readers are :mod:`watermark.documents.office`'s, shared with the corpus
retrieval path rather than duplicated here, #1757), and writes
``data/extracted/<slug>/meetings/meeting-index.yaml`` with, per file:

* ``date_verified`` — the listing date **only when it appears in the file's own
  text** (content verification), with ``date_evidence`` naming how (``pdf_text`` /
  ``docx`` / ``html``); otherwise ``null`` and ``date_evidence: listing`` (the date
  is still the listing's, just unconfirmed).
* ``hits`` — corridor topic/subject slugs found in the text (``watermark.civic.keywords``),
  which is what lets a meeting surface on the corridor timeline.

**OCR boundary (honest):** there is no tesseract dependency, so an image-only
scanned PDF (no embedded text layer) yields ``text_method: none`` — its date stays
unverified and its text is unscanned. Those files need an OCR pass that isn't wired
here; the manifest/index ``counts`` make the gap visible rather than silent.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.civic.keywords import scan_text
from watermark.civic.layout import meetings_dir
from watermark.civic.models import Subdivision
from watermark.config import Settings, get_settings
from watermark.documents import office
from watermark.documents.pdf import PdfDocument
from watermark.logging import get_logger
from watermark.text_sidecars import sidecar_for_source

log = get_logger(__name__)

_MAX_PAGES = 12  # minutes/agendas are short; bound text extraction cost
_OCR_DPI = 200  # matches the commissioners-corpus OCR convention
_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class IndexedDoc(BaseModel):
    """One meeting document's index entry (manifest provenance + verified content)."""

    model_config = ConfigDict(extra="forbid")

    filename: str
    kind: str
    body: str | None
    date_listing: str | None  # from the records-page listing (provisional)
    date_verified: str | None  # listing date confirmed in the file's own text, else null
    date_evidence: str  # pdf_text | docx | html | listing (unconfirmed) | none
    text_method: str  # pdf_text | docx | html | sidecar | ocr | none
    char_count: int
    hits: list[str]  # corridor topic/subject slugs found in the text
    title: str | None
    source_url: str
    sha256: str | None

    @property
    def date(self) -> str | None:
        """Best date: content-verified if available, else the listing date."""
        return self.date_verified or self.date_listing


class IndexReport(BaseModel):
    """Outcome of indexing one subdivision's downloaded meetings."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    docs: list[IndexedDoc]

    @property
    def text_extracted(self) -> int:
        return sum(1 for d in self.docs if d.text_method != "none")

    @property
    def date_verified(self) -> int:
        return sum(1 for d in self.docs if d.date_verified)

    @property
    def with_hits(self) -> int:
        return sum(1 for d in self.docs if d.hits)


class OcrUnavailableError(RuntimeError):
    """OCR was requested but pytesseract / the tesseract binary isn't available."""


def _pdf_text(path: Path) -> str:
    pdf = PdfDocument(path)
    try:
        return "\n".join(pdf.page_text(i) for i in range(min(pdf.page_count, _MAX_PAGES)))
    except Exception as exc:  # a malformed PDF is a "no text" finding, not a crash
        log.warning("civic.index.pdf_error", path=str(path), error=str(exc).splitlines()[0])
        return ""
    finally:
        pdf.close()


def ocr_pdf(path: Path, *, dpi: int = _OCR_DPI, max_pages: int = _MAX_PAGES) -> str:
    """OCR an image-only PDF by rendering pages and running tesseract.

    Optional path: raises :class:`OcrUnavailableError` if pytesseract or the
    tesseract binary is missing, so callers can degrade rather than crash.
    """
    import io

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise OcrUnavailableError("pytesseract is not installed") from exc

    pdf = PdfDocument(path, dpi=dpi)
    pages: list[str] = []
    try:
        for i in range(min(pdf.page_count, max_pages)):
            png = pdf.render_page_png(i, dpi=dpi)
            pages.append(pytesseract.image_to_string(Image.open(io.BytesIO(png))))
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailableError("the tesseract binary is not on PATH") from exc
    finally:
        pdf.close()
    return "\n".join(pages)


def _sidecar_text(path: Path, documents_dir: Path | None) -> str:
    """The committed ``-text`` sidecar's transcription of *path*, or ``""``.

    A legacy Office binary (``.doc``/``.dot``/``.xls``/``.rtf``) has no in-process reader, so
    without this it indexes as ``text_method: none`` — indistinguishable from an image-only
    scan, and silently unsearchable. The bytes ARE readable; the text just lives in a committed
    sidecar (:mod:`watermark.text_sidecars`, #1757) that this indexer never consulted.
    """
    if documents_dir is None:
        return ""
    try:
        rel = path.resolve().relative_to(documents_dir.resolve())
    except ValueError:
        return ""  # not under data/documents — a test fixture or an ad-hoc path
    sidecar = sidecar_for_source(PurePosixPath(rel), documents_dir)
    if sidecar is None:
        return ""
    try:
        return (documents_dir / sidecar).read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("civic.index.sidecar_error", path=str(sidecar), error=str(exc))
        return ""


def extract_text(
    path: Path, *, ocr: bool = False, documents_dir: Path | None = None
) -> tuple[str, str]:
    """``(text, method)`` for a downloaded file. ``method`` is ``none`` when empty.

    For a PDF with no embedded text layer (an image-only scan), ``ocr=True`` renders
    + OCRs it (``method='ocr'``); otherwise such a file returns ``("", "none")``.

    ``documents_dir`` lets a legacy Office binary be read from its committed ``-text`` sidecar
    (``method='sidecar'``). Omit it and such a file is ``none`` — which is what this function did
    for every ``.doc`` in the corpus, conflating "needs a converter we already ran" with "needs
    OCR nobody has wired". The distinction matters: only one of the two is already answerable.
    """
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx", ".htm", ".html"}:
        # Extensionless downloads (CivicPlus ViewFile) are real PDFs — sniff the magic.
        try:
            if path.read_bytes()[:5].startswith(b"%PDF"):
                suffix = ".pdf"
        except OSError:
            pass
    if suffix == ".pdf":
        text, method = _pdf_text(path), "pdf_text"
        if not text.strip() and ocr:
            text, method = ocr_pdf(path), "ocr"
    elif suffix == ".docx":
        text, method = office.docx_text(path), "docx"
    elif suffix in {".htm", ".html"}:
        text, method = office.html_text(path), "html"
    elif suffix in office.SIDECAR_SOURCE_SUFFIXES:
        text, method = _sidecar_text(path, documents_dir), "sidecar"
    else:
        text, method = "", "none"
    # Normalize whitespace: PDF/DOCX/OCR runs split words and inject newlines, which
    # would otherwise break "January 6, 2026"-style date matching and topic scans.
    text = re.sub(r"\s+", " ", text).strip()
    return (text, method if text else "none")


def _date_appears(text: str, iso: str) -> bool:
    """Whether an ISO ``yyyy-mm-dd`` appears in ``text`` in any common written form.

    Whitespace-tolerant (Word splits a date like ``February 9, 2026`` across runs,
    leaving ``9 , 2026``) and accepts day ordinals (``9th``).
    """
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso or "")
    if not m:
        return False
    year, month, day = int(m[1]), int(m[2]), int(m[3])
    name = _MONTHS[month - 1]
    yy = str(year)[2:]
    ordinal = r"(?:st|nd|rd|th)?"
    patterns = [
        rf"{name}\s+{day}{ordinal}\s*,?\s*{year}",  # February 9, 2026 / 9th 2026
        rf"{name[:3]}\.?\s+{day}{ordinal}\s*,?\s*{year}",  # Feb 9, 2026
        rf"\b0?{month}\s*/\s*0?{day}\s*/\s*{year}\b",  # 2/9/2026, 02/09/2026
        rf"\b0?{month}\s*-\s*0?{day}\s*-\s*(?:{year}|{yy})\b",  # 2-9-2026, 2-9-26
        rf"\b{year}\s*-\s*{month:02d}\s*-\s*{day:02d}\b",  # 2026-02-09
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _verify_date(text: str, listing: str | None, method: str) -> tuple[str | None, str]:
    """Confirm the listing date against the file's text. Returns (verified, evidence)."""
    if listing and method != "none" and _date_appears(text, listing):
        return listing, method
    return None, "listing" if listing else "none"


def _dedup_entries(entries: list[Any]) -> list[dict[str, Any]]:
    """One index row per on-disk document.

    The same bytes can be served at two provenance URLs — CivicPlus serves a meeting
    id at both ``/Agenda/`` and ``/Minutes/`` — so the manifest records two entries. They
    may share a filename (one written file, the duplicate ``skipped_existing``) or differ
    only in name (Content-Disposition vs URL basename) while sharing a ``sha256``. Collapse
    both. When a byte-identical pair is split across kinds, keep the ``minutes`` row — an
    agenda that is byte-identical to the minutes is just the minutes served at the agenda URL.
    """
    valid = [
        e
        for e in entries
        if isinstance(e, dict) and e.get("status") != "error" and e.get("filename")
    ]
    # Representative per sha256: prefer a "minutes" kind over any other.
    rep_by_sha: dict[str, dict[str, Any]] = {}
    for e in valid:
        sha = e.get("sha256")
        if not sha:
            continue
        cur = rep_by_sha.get(sha)
        if cur is None or (cur.get("kind") != "minutes" and e.get("kind") == "minutes"):
            rep_by_sha[sha] = e
    # Emit at most one row per sha256 and per filename, in first-seen order.
    out: list[dict[str, Any]] = []
    seen_sha: set[str] = set()
    seen_file: set[str] = set()
    for e in valid:
        sha = e.get("sha256")
        if sha:
            if sha in seen_sha:
                continue
            seen_sha.add(sha)
            chosen = rep_by_sha[sha]
            seen_file.add(str(chosen["filename"]))
            out.append(chosen)
        else:
            fn = str(e["filename"])
            if fn in seen_file:
                continue
            seen_file.add(fn)
            out.append(e)
    return out


def index_meetings(
    subdivision: Subdivision,
    *,
    settings: Settings | None = None,
    docs_dir: Path | None = None,
    manifest_path: Path | None = None,
    ocr: bool = False,
) -> IndexReport:
    """Index a body's downloaded meetings from its download manifest.

    ``ocr=True`` OCRs image-only scanned PDFs (needs the tesseract binary); the
    default leaves them ``text_method: none``.
    """
    settings = settings or get_settings()
    base = meetings_dir(settings.extracted_dir, subdivision.slug, settings)
    manifest_path = manifest_path or (base / "download-manifest.yaml")
    docs_dir = docs_dir or meetings_dir(settings.documents_dir, subdivision.slug, settings)
    manifest = (
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    entries = manifest.get("documents", []) if isinstance(manifest, dict) else []

    indexed: list[IndexedDoc] = []
    for entry in _dedup_entries(entries):
        filename = str(entry["filename"])
        path = docs_dir / filename
        text, method = (
            extract_text(path, ocr=ocr, documents_dir=settings.documents_dir)
            if path.exists()
            else ("", "none")
        )
        listing = entry.get("date")
        verified, evidence = _verify_date(text, listing, method)
        indexed.append(
            IndexedDoc(
                filename=filename,
                kind=str(entry.get("kind", "other")),
                body=entry.get("body"),
                date_listing=listing,
                date_verified=verified,
                date_evidence=evidence,
                text_method=method,
                char_count=len(text),
                hits=scan_text(text),
                title=entry.get("title"),
                source_url=str(entry.get("source_url", "")),
                sha256=entry.get("sha256"),
            )
        )
    log.info(
        "civic.index",
        slug=subdivision.slug,
        total=len(indexed),
        text_extracted=sum(1 for d in indexed if d.text_method != "none"),
        verified=sum(1 for d in indexed if d.date_verified),
        with_hits=sum(1 for d in indexed if d.hits),
    )
    return IndexReport(slug=subdivision.slug, docs=indexed)


def _text_extraction_note(report: IndexReport) -> str:
    """How this index's text was actually read, from the documents' own ``text_method``."""
    ocr = sum(1 for d in report.docs if d.text_method == "ocr")
    unread = sum(1 for d in report.docs if d.text_method == "none")
    note = "PDF text layer (pypdf) / DOCX / HTML"
    note += (
        f", plus OCR (tesseract) on {ocr} image-only scan(s)"
        if ocr
        else " — NO OCR was run on this index"
    )
    note += (
        f". {unread} file(s) yielded no text (text_method: none — date unverified, text "
        "unscanned); an image-only scan needs `index --ocr`."
        if unread
        else ". Every file yielded text."
    )
    return note


def write_index(report: IndexReport, out_path: Path) -> Path:
    """Write the meeting index YAML (a timeline source; corridor hits drive events)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"{report.slug} meeting index (text-verified dates + corridor hits)",
            "slug": report.slug,
            "generated_at": datetime.now(UTC).date().isoformat(),
            # State what this run actually did, per file. The fixed "NO OCR" string predated
            # `index --ocr` and outlived it: the Hancock County commissioners' index was written
            # claiming no OCR over 53 files it had just OCR'd (#1839). Each document's own
            # `text_method` is the record; this summarises it.
            "text_extraction": _text_extraction_note(report),
            "date_evidence": "date_verified is the listing date CONFIRMED in the file's "
            "own text; null means unconfirmed (date_listing still stands).",
            "counts": {
                "total": len(report.docs),
                "text_extracted": report.text_extracted,
                "date_verified": report.date_verified,
                "with_corridor_hits": report.with_hits,
            },
        },
        "documents": [d.model_dump() for d in report.docs],
    }
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_path
