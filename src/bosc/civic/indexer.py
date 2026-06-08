"""Index downloaded meeting documents: extract text, verify dates, scan for corridor topics.

Reads a body's ``download-manifest.yaml``, opens each downloaded file from the
evidence tree, pulls its text (PDF text layer / DOCX / HTML — **no OCR**, see below),
and writes ``data/extracted/<slug>/meetings/meeting-index.yaml`` with, per file:

* ``date_verified`` — the listing date **only when it appears in the file's own
  text** (content verification), with ``date_evidence`` naming how (``pdf_text`` /
  ``docx`` / ``html``); otherwise ``null`` and ``date_evidence: listing`` (the date
  is still the listing's, just unconfirmed).
* ``hits`` — corridor topic/subject slugs found in the text (``bosc.civic.keywords``),
  which is what lets a meeting surface on the corridor timeline.

**OCR boundary (honest):** there is no tesseract dependency, so an image-only
scanned PDF (no embedded text layer) yields ``text_method: none`` — its date stays
unverified and its text is unscanned. Those files need an OCR pass that isn't wired
here; the manifest/index ``counts`` make the gap visible rather than silent.
"""

from __future__ import annotations

import html as _html
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.civic.keywords import scan_text
from bosc.civic.models import Subdivision
from bosc.config import Settings, get_settings
from bosc.documents.pdf import PdfDocument
from bosc.logging import get_logger

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
    text_method: str  # pdf_text | docx | html | none
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


def _docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    # <w:t> runs hold the visible text; join with spaces, decode entities.
    runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.DOTALL)
    return _html.unescape(" ".join(runs))


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


def extract_text(path: Path, *, ocr: bool = False) -> tuple[str, str]:
    """``(text, method)`` for a downloaded file. ``method`` is ``none`` when empty.

    For a PDF with no embedded text layer (an image-only scan), ``ocr=True`` renders
    + OCRs it (``method='ocr'``); otherwise such a file returns ``("", "none")``.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text, method = _pdf_text(path), "pdf_text"
        if not text.strip() and ocr:
            text, method = ocr_pdf(path), "ocr"
    elif suffix == ".docx":
        text, method = _docx_text(path), "docx"
    elif suffix in {".htm", ".html"}:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        text, method = _html.unescape(re.sub(r"<[^>]+>", " ", raw)), "html"
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
    base = settings.extracted_dir / subdivision.slug / "meetings"
    manifest_path = manifest_path or (base / "download-manifest.yaml")
    docs_dir = docs_dir or (settings.documents_dir / subdivision.slug / "meetings")
    manifest = (
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    )
    entries = manifest.get("documents", []) if isinstance(manifest, dict) else []

    indexed: list[IndexedDoc] = []
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or entry.get("status") == "error"
            or not entry.get("filename")
        ):
            continue
        path = docs_dir / str(entry["filename"])
        text, method = extract_text(path, ocr=ocr) if path.exists() else ("", "none")
        listing = entry.get("date")
        verified, evidence = _verify_date(text, listing, method)
        indexed.append(
            IndexedDoc(
                filename=str(entry["filename"]),
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


def write_index(report: IndexReport, out_path: Path) -> Path:
    """Write the meeting index YAML (a timeline source; corridor hits drive events)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"{report.slug} meeting index (text-verified dates + corridor hits)",
            "slug": report.slug,
            "generated_at": datetime.now(UTC).date().isoformat(),
            "text_extraction": "PDF text layer (pypdf) / DOCX / HTML — NO OCR. An "
            "image-only scanned PDF has text_method: none (date unverified, text "
            "unscanned); those need an OCR pass not wired here.",
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
