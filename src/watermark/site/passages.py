"""Build the ``passages`` feed (#1589) — a page-level excerpt index over the published PDFs.

The passages feed turns a "which page says X" question into a page-cited excerpt instead of a
whole-record pull: one :class:`~watermark.site.feeds.PassageItem` per text-bearing page of every
*published* source PDF. It powers the web ``search_passages`` MCP tool (epic #1579 Phase 3).

Two invariants shape the scope:

* **Publish policy (#280).** Passages come only from documents the ``documents`` feed marks
  ``published`` — the same policy (cleared scope minus the ``withhold`` denylist) that governs
  which source *bytes* are served publicly, so a withheld page's text never ships either. A
  non-published document's text never enters the bundle (chain of custody), which also keeps the
  feed small (the cleared scope is a curated handful of collections, not the whole corpus).
* **Text layer first, OCR where the text layer is unusable.** Page text is normally the pypdf
  text-layer extraction, the same source the agent-side
  :func:`watermark.retrieval.ingestion.iter_document_chunks` reads — but here scoped to the published
  set and joined to the ``documents`` feed. For a scanned document the text layer is garbled OCR
  (per the root CLAUDE.md, never trust its digits); the excerpt is a **locator** for the cited page,
  not a transcription. Image-only pages (no text layer) carry no excerpt and are skipped. A page
  whose text layer is *broken* rather than merely noisy falls back to OCR — see below — and each
  passage records which read produced it (:attr:`~watermark.site.feeds.PassageItem.method`).

**The broken-``ToUnicode`` fallback (#1966).** Some source PDFs embed a subset font whose
``ToUnicode`` CMap maps character codes to raw *glyph indices* instead of Unicode. pypdf decodes
those runs faithfully and the result is unusable: in ``oepa/van-wert/2PD00006.f8aaad0a.pdf`` the
effluent-limit start date ``July 1, 2026`` extracts as ``-XO\\\\\\x03\\x14\\x0f\\x03\\x15\\x13\\x15\\x19\\x0f``
— every code shifted down by ``0x1D``. **The C0 control bytes are only the detectable half of the
damage.** Codes that land on a printable character shift silently into *other printable
characters* (``July`` → ``-XO\\``), so a page that trips :func:`has_broken_text_layer` cannot be
repaired by scrubbing its control bytes: the rest of that font's run is already confidently wrong.
The whole page is therefore re-read by OCR, which is an independent read of what the page actually
renders. That trades a table's digital digits for OCR noise on the affected pages, which is the
right trade here — the feed's contract is a *locator*, its text is already garbled OCR for every
scanned document, and a locator that says ``-XO\\`` where the record says ``July`` cannot be found
by anyone searching for it.

**LFS independence (the reason for the committed artifact).** The source PDFs are Git-LFS-tracked,
and the frontend build (CI + Cloudflare Pages) checks out *without* LFS, so re-extracting at export
time would yield nothing in production. Extraction (:func:`extract_published_passages`, needs
``git lfs pull``) is therefore run out-of-band by ``watermark passages`` and its output committed to
:data:`data/site/passages.ndjson`; :func:`watermark.site.export._passages_feed` reads that committed
artifact (:func:`load_committed_passages`) and filters it to the site's published docs, so the build
is LFS-independent. Regenerate the artifact whenever the publish allowlist or the source PDFs change.

:func:`watermark.site.embeddings.build_passage_embeddings` then vectorises the emitted feed (the same
split as ``ask-embeddings``: text here, vectors there).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watermark.logging import get_logger
from watermark.site.feeds import PassageItem, PassageMethod

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

# Match the agent-side chunk cap (watermark.retrieval.ingestion._MAX_CHUNK_CHARS) so a page's
# excerpt is bounded identically on both retrieval paths.
_MAX_PASSAGE_CHARS = 4_000

# The committed, LFS-independent passage artifact (relative to settings.data_dir). Global (documents
# are corpus-global): each per-site export filters it to that site's published docs.
_ARTIFACT_RELPATH = ("site", "passages.ndjson")

# The reference extractions read scans at 300 DPI (watermark.documents.pdf.DEFAULT_DPI); match it so
# a fallback OCR read is the same quality as the extract pipeline's.
_OCR_DPI = 300

# A C0 control byte in decoded page text is the signature of a broken ``ToUnicode`` CMap (#1966): no
# legitimate text layer emits one. \t \n \r are excluded — pypdf lays pages out with them.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# One page's OCR read: ``(pdf_path, 0-based page index) -> text``. An injection seam so the fallback
# is testable without the tesseract binary; :func:`ocr_page_text` is the real one.
OcrPage = Callable[[Path, int], str]


def has_broken_text_layer(text: str) -> bool:
    """Whether ``text`` shows the signature of a broken ``ToUnicode`` CMap (#1966).

    A C0 control byte (excluding ``\\t``/``\\n``/``\\r``, which pypdf lays pages out with) is never
    legitimate decoded page text — it is a glyph index that reached the output because the font's
    ``ToUnicode`` maps codes to glyph ids rather than Unicode. It is a *detector*, not a measure of
    the damage: the same shift moves other codes onto plausible-looking printable characters, so a
    page that trips this predicate is wrong well beyond the bytes matched here. On the committed
    corpus it fires on exactly the 50 known-broken pages of two OEPA permits and nothing else.
    """
    return bool(_CONTROL_RE.search(text))


def _strip_control_bytes(text: str) -> str:
    """Drop C0 control bytes from an OCR read.

    Applied by :func:`build_passages` to every passage it emits, whichever read produced it, so the
    invariant ("no emitted passage trips :func:`has_broken_text_layer`") holds for *any*
    implementation of the :data:`OcrPage` seam and for an unrepairable page too. It is not cosmetic:
    tesseract ends every page with a form feed (``\\x0c``), which would otherwise make its own clean
    read look like the damage it was called in to repair.
    """
    return _CONTROL_RE.sub("", text)


def ocr_page_text(pdf_path: Path, page_idx: int, *, dpi: int = _OCR_DPI) -> str:
    """OCR a single page of ``pdf_path`` (0-based) — the real :data:`OcrPage`.

    Renders with pypdfium2 and reads with tesseract, the same pair as
    :func:`watermark.civic.indexer.ocr_pdf`, but one page at a time (the fallback is per-page, and
    these documents run to 128 pages). Raises
    :class:`~watermark.civic.indexer.OcrUnavailableError` when pytesseract or the tesseract binary
    is missing, so the caller can degrade rather than crash.
    """
    import io

    from watermark.civic.indexer import OcrUnavailableError
    from watermark.documents.pdf import PdfDocument

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - exercised only without the dep
        raise OcrUnavailableError("pytesseract is not installed") from exc

    doc = PdfDocument(pdf_path, dpi=dpi)
    try:
        png = doc.render_page_png(page_idx, dpi=dpi)
        text = str(pytesseract.image_to_string(Image.open(io.BytesIO(png))))
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailableError("the tesseract binary is not on PATH") from exc
    finally:
        doc.close()
    return text.strip()


def _published_pdf_entries(
    documents_feed: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str]]:
    """The ``(rel, title)`` of every published PDF in the assembled ``documents`` feed.

    Reads the just-built feed rows (``DocumentCollectionItem`` dicts) rather than re-deriving the
    allowlist, so passages and the public document catalog can never disagree on what's published.
    """
    out: list[tuple[str, str]] = []
    for collection in documents_feed:
        for entry in collection.get("entries", []):
            if not entry.get("published") or entry.get("render_class") != "pdf":
                continue
            rel = entry.get("rel")
            if not rel:
                continue
            out.append((str(rel), str(entry.get("name") or rel)))
    return out


def build_passages(
    documents_feed: Sequence[Mapping[str, Any]],
    documents_dir: Path,
    *,
    ocr_page: OcrPage | None = ocr_page_text,
) -> list[PassageItem]:
    """Extract one :class:`PassageItem` per text-bearing page of each published PDF.

    ``documents_feed`` is the assembled ``documents`` feed (a list of ``DocumentCollectionItem``
    dicts); ``documents_dir`` is ``settings.documents_dir`` (the join base for ``document_id``). A
    PDF that can't be opened (an unresolved Git-LFS pointer, a corrupt file) yields no passages and
    is skipped — the feed degrades to what's readable, never raising, exactly like
    :func:`~watermark.retrieval.ingestion.iter_document_chunks`.

    A page whose text layer trips :func:`has_broken_text_layer` is re-read through ``ocr_page``
    (``method="ocr"``); pass ``None`` to disable the fallback. When that re-read yields nothing —
    no tesseract binary, or a page pdfium renders blank — the page keeps the *readable remainder*
    of its text layer and is marked ``method="pdf_text_damaged"`` rather than dropped: it is still
    a locator, and naming it is how a better copy of that source gets requested. Emitted ``text``
    never carries a C0 control byte under any method.

    ``watermark passages`` reports both counts, because a regen on a machine without tesseract
    would otherwise quietly turn 49 repaired pages back into damaged ones.
    """
    import pypdf  # a core dep (also used by the extract pipeline + retrieval ingestion)

    from watermark.civic.indexer import OcrUnavailableError

    passages: list[PassageItem] = []
    skipped_docs = 0
    damaged_pages = 0
    ocr_pages = 0
    ocr_available = True
    for rel, title in _published_pdf_entries(documents_feed):
        pdf_path = documents_dir / rel
        try:
            reader = pypdf.PdfReader(str(pdf_path), strict=False)
        except Exception:
            skipped_docs += 1
            continue
        collection = rel.split("/", 1)[0] if "/" in rel else ""
        # Iterating reader.pages lazily parses each page, and a malformed PDF can raise mid-traversal
        # (not just in extract_text) — wrap the loop so a broken document contributes what it could
        # and is skipped, never aborting the whole export.
        try:
            for page_idx, page in enumerate(reader.pages):
                try:
                    text = (page.extract_text() or "").strip()
                except Exception:
                    text = ""
                if not text:
                    continue  # image-only / empty page — no excerpt to index
                method: PassageMethod = "pdf_text"
                if has_broken_text_layer(text):
                    damaged_pages += 1
                    method = "pdf_text_damaged"
                    ocr_text = ""
                    if ocr_page is not None and ocr_available:
                        try:
                            ocr_text = ocr_page(pdf_path, page_idx).strip()
                        except OcrUnavailableError as exc:
                            # One report per run: the binary won't appear mid-loop.
                            ocr_available = False
                            log.warning("passages.ocr_unavailable", error=str(exc))
                        except Exception as exc:  # a page that won't render is not fatal
                            log.warning(
                                "passages.ocr_failed",
                                document=rel,
                                page=page_idx + 1,
                                error=str(exc).splitlines()[0],
                            )
                    if ocr_text:
                        text, method = ocr_text, "ocr"
                        ocr_pages += 1
                    else:
                        # Nothing renders (a page pdfium draws blank) — keep the readable remainder
                        # as a locator, scrubbed below, and say the read is damaged.
                        log.warning("passages.unrepaired", document=rel, page=page_idx + 1)
                # Emit invariant: no C0 control byte ever ships, whichever read produced the text.
                # It also keeps an OCR read (tesseract ends every page with \x0c) from looking like
                # the damage it was called in to clear.
                text = _strip_control_bytes(text).strip()
                if not text:
                    continue
                page_1 = page_idx + 1
                passages.append(
                    PassageItem(
                        id=f"{rel}#p{page_1}",
                        document_id=rel,
                        collection=collection,
                        title=title,
                        page=page_1,
                        section=None,
                        text=text[:_MAX_PASSAGE_CHARS],
                        method=method,
                    )
                )
        except Exception:
            skipped_docs += 1
    log.info(
        "passages.built",
        passages=len(passages),
        published_pdfs=len(_published_pdf_entries(documents_feed)),
        skipped_docs=skipped_docs,
        damaged_pages=damaged_pages,
        ocr_pages=ocr_pages,
    )
    return passages


# --- the committed, LFS-independent artifact ----------------------------------------------------
def artifact_path(settings: Settings) -> Path:
    """Path to the committed passages artifact (``data/site/passages.ndjson``)."""
    return settings.data_dir.joinpath(*_ARTIFACT_RELPATH)


def load_committed_passages(settings: Settings) -> list[PassageItem]:
    """Read the committed passages artifact, or ``[]`` when it's absent.

    This is what the export reads (not the raw PDFs), so the LFS-free build serves real page text.
    """
    path = artifact_path(settings)
    if not path.exists():
        return []
    return [
        PassageItem.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def extract_published_passages(settings: Settings) -> list[PassageItem]:
    """Extract page passages for **every** published PDF across the whole corpus (the regen source).

    Reads the raw LFS PDFs, so it must run with ``git lfs pull`` (via ``watermark passages``), never
    at export time. The publish policy (cleared scope minus the ``withhold`` denylist, exhibits
    auto-included) is resolved exactly as the export does, so a passage ships only where the
    ``documents`` feed marks the doc ``published`` — but over the **whole tree** (``scope=None``) so
    the one global artifact covers every site's published docs; each per-site ``_passages_feed``
    filters it back down to its own set.
    """
    from watermark.site import documents as documents_mod
    from watermark.site import exhibits as exhibits_mod

    site_dir = settings.data_dir / "site"
    exhibit_items = exhibits_mod.export_exhibits(site_dir / "exhibits.yaml", settings.documents_dir)
    allowlist = documents_mod.load_publish_allowlist(
        site_dir / "published-documents.yaml",
        exhibit_sources=exhibits_mod.publishable_exhibit_sources(exhibit_items),
    )
    documents_feed = documents_mod.export_documents(
        settings.documents_dir, allowlist=allowlist, scope=None
    )
    feed_rows = [c.model_dump(mode="json", by_alias=True) for c in documents_feed]
    return build_passages(feed_rows, settings.documents_dir)


def write_committed_passages(passages: Sequence[PassageItem], settings: Settings) -> Path:
    """Write the passages artifact as NDJSON (one :class:`PassageItem` per line). Returns the path."""
    path = artifact_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(p.model_dump_json(by_alias=True) + "\n" for p in passages)
    path.write_text(payload, encoding="utf-8")
    return path
