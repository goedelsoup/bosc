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

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
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

# The index's provenance sidecar (#2025): the published-PDF set the artifact beside it was built
# from, so a later publish-policy change is detectable without re-reading a single PDF.
_META_RELPATH = ("site", "passages.meta.json")

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


# The C1 range a PDF emits when its text layer carries CP1252 bytes that reach the output
# un-mapped. Every one of these is a *printable* character in CP1252 — the smart quotes and
# dashes a word processor produces — so unlike the C0 damage above they must be REPAIRED, never
# dropped. Five C1 codes are unassigned in CP1252 (0x81, 0x8d, 0x8f, 0x90, 0x9d); they map to
# nothing and are removed.
_CP1252_C1 = {
    code: repaired
    for code in range(0x80, 0xA0)
    for repaired in [bytes([code]).decode("cp1252", errors="ignore")]
}


_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
# A well-formed UTF-16 pair: a high surrogate followed by a low one. Matched explicitly so a
# pair is recombined and an ORPHAN is removed, rather than round-tripping the whole string
# through ``errors="replace"`` — which would swap the orphan for U+FFFD, a visible edit to
# quoted public-record text and exactly what the CP1252 repair above refuses to do.
_SURROGATE_PAIR_RE = re.compile(r"[\ud800-\udbff][\udc00-\udfff]")


def _repair_surrogate_pairs(text: str) -> str:
    """Recombine UTF-16 surrogate pairs pypdf hands back as separate code points.

    A third damage mode, distinct from the two above and from #1966's broken CMap. Some
    ``ToUnicode`` CMaps encode astral characters as UTF-16 **surrogate pairs**, and pypdf
    yields the two halves as individual code points rather than the character they jointly
    denote: Lima's WWTP capacity report writes its removal-efficiency formula in a
    mathematical-italic font, so ``U+D835 U+DC45`` reaches the output where the document
    prints ``U+1D445`` (MATHEMATICAL ITALIC CAPITAL R).

    That is not cosmetic. A lone surrogate is representable in a Python ``str`` and **not**
    encodable to UTF-8, so it survives every check that operates on text and then kills the
    write — ``watermark passages`` died on one page of one document out of 261 with a
    ``PydanticSerializationError``, having already done the work.

    Paired halves are recombined into the character the document actually prints (the same
    repair-don't-drop rule as :func:`_repair_cp1252_punctuation` — this is quoted
    public-record text). A surrogate with no partner denotes nothing and cannot be encoded,
    so it is dropped; it is the only outcome available, and it is rare enough to be worth a
    warning at the call site rather than a silent pass.
    """
    if not _SURROGATE_RE.search(text):
        return text
    paired = _SURROGATE_PAIR_RE.sub(
        lambda m: m.group(0).encode("utf-16", "surrogatepass").decode("utf-16"), text
    )
    return _SURROGATE_RE.sub("", paired)


def _repair_cp1252_punctuation(text: str) -> str:
    """Map stray C1 bytes onto the CP1252 characters they actually encode.

    Distinct from the C0 damage :func:`has_broken_text_layer` detects, and distinct in the
    consequence. A broken ``ToUnicode`` CMap (#1966) makes the whole page untrustworthy, so that
    path re-reads by OCR. This is narrower: the text layer is *correct*, and pypdf simply passed
    a CP1252 byte through as the same-numbered codepoint — ``U+0092`` where the document says
    ``U+2019``. Van Wert's council PDFs do it (``today\\x92s``, ``project\\x92s``, en/em dashes at
    ``\\x96``/``\\x97``).

    Repaired rather than stripped **because these are evidence**. Dropping ``\\x92`` turns
    "today's" into "todays" — a silent edit to quoted public-record text, which the corpus's
    chain-of-custody rule forbids; and dropping ``\\x97`` welds two clauses together. The bytes
    are unambiguous (CP1252 assigns all but five of them), so the mapping recovers what the
    document prints rather than guessing at it.

    Deliberately NOT folded into :func:`has_broken_text_layer`: a page needing this repair does
    not need OCR, and routing it to a 300-DPI re-read would replace a correct text layer with a
    worse one.
    """
    return text.translate(_CP1252_C1)


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
                # the damage it was called in to clear. The CP1252 repair runs alongside it and in
                # the other direction — those bytes are real punctuation and are restored, not cut.
                # The surrogate repair runs last and guards the WRITE: a lone surrogate passes
                # every text-level check and then fails to encode to UTF-8 at serialization.
                text = _repair_surrogate_pairs(
                    _repair_cp1252_punctuation(_strip_control_bytes(text))
                ).strip()
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


def _published_documents_feed(settings: Settings) -> list[dict[str, Any]]:
    """The assembled whole-tree ``documents`` feed rows, with the publish policy applied.

    Shared by the extractor and the freshness check so they can never disagree about what is
    published — the same reason :func:`_published_pdf_entries` reads the feed rather than
    re-deriving the allowlist.
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
    return [c.model_dump(mode="json", by_alias=True) for c in documents_feed]


def published_pdf_rels(settings: Settings) -> list[str]:
    """Every published PDF rel the index is expected to cover, sorted (#2025).

    Cheap — it resolves the publish policy and reads the document catalog, opening no PDF. That
    is what makes the freshness check affordable: the expensive half (extraction) only has to run
    once the check says the set has moved.
    """
    return sorted(rel for rel, _ in _published_pdf_entries(_published_documents_feed(settings)))


def meta_path(settings: Settings) -> Path:
    """Path to the index's provenance sidecar (``data/site/passages.meta.json``)."""
    return settings.data_dir.joinpath(*_META_RELPATH)


def load_index_meta(settings: Settings) -> dict[str, Any] | None:
    """The committed sidecar, or ``None`` when the index predates it."""
    path = meta_path(settings)
    if not path.exists():
        return None
    parsed: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return parsed


@dataclass(frozen=True)
class PassageIndexFinding:
    """One way the committed passage index no longer describes the published corpus."""

    kind: str  # no-meta | newly-published | no-longer-published
    subject: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.subject} — {self.detail}"


def check_index_freshness(settings: Settings) -> list[PassageIndexFinding]:
    """Report whether ``data/site/passages.ndjson`` still covers the published corpus (#2025).

    The shared index has no per-site regeneration and no freshness check, so it is the worst case
    of the committed-artifact lag: #2023 cleared eight ``oepa/`` documents that were already inside
    a cleared boundary, and they sat unindexed until somebody rebuilt for an unrelated site.

    The predicate is the **published set**, not coverage. "Published but carrying no passage" is
    useless as a signal — 63 of the 261 published PDFs carry none, and not one of them is an
    unresolved LFS pointer: they are image-only scans whose text layer is zero-length, so a
    coverage check would be 63 standing findings forever. What is exact is whether the set the
    index was built from still matches the set the publish policy clears today: a document added to
    that set has provably never been offered to the extractor, and one removed from it is being
    retained past its clearance.

    Opens no PDF, so it is cheap enough to run in CI; the extraction it recommends is not.
    """
    meta = load_index_meta(settings)
    if meta is None:
        return [
            PassageIndexFinding(
                "no-meta",
                "data/site/passages.meta.json",
                "the index carries no record of what it was built from — run `watermark passages`",
            )
        ]
    built_from = set(meta.get("published_pdfs") or ())
    current = set(published_pdf_rels(settings))
    findings = [
        PassageIndexFinding(
            "newly-published", rel, "cleared for publication since the index was built"
        )
        for rel in sorted(current - built_from)
    ]
    findings += [
        PassageIndexFinding(
            "no-longer-published", rel, "indexed but no longer cleared — passages retained past it"
        )
        for rel in sorted(built_from - current)
    ]
    return findings


@dataclass(frozen=True)
class PassageExtraction:
    """A regen's two outputs: the passages, and the published set they were extracted over.

    They travel together because the sidecar's whole value is that it describes *this* run — a
    set re-derived at write time could differ from the one the extractor actually saw.
    """

    items: list[PassageItem]
    published_pdfs: list[str]


def extract_published_passages(settings: Settings) -> PassageExtraction:
    """Extract page passages for **every** published PDF across the whole corpus (the regen source).

    Reads the raw LFS PDFs, so it must run with ``git lfs pull`` (via ``watermark passages``), never
    at export time. The publish policy (cleared scope minus the ``withhold`` denylist, exhibits
    auto-included) is resolved exactly as the export does, so a passage ships only where the
    ``documents`` feed marks the doc ``published`` — but over the **whole tree** (``scope=None``) so
    the one global artifact covers every site's published docs; each per-site ``_passages_feed``
    filters it back down to its own set.
    """
    feed = _published_documents_feed(settings)
    return PassageExtraction(
        items=build_passages(feed, settings.documents_dir),
        published_pdfs=sorted(rel for rel, _ in _published_pdf_entries(feed)),
    )


def write_committed_passages(extraction: PassageExtraction, settings: Settings) -> Path:
    """Write the passages artifact as NDJSON, plus the sidecar recording what it covers.

    The sidecar (``passages.meta.json``) is what makes staleness detectable at all: without it,
    "published but unindexed" cannot be told apart from "published and legitimately text-free",
    and the index can silently fall behind a publish-policy change — which is how #2023's eight
    newly-cleared documents went unindexed. See :func:`check_index_freshness`.

    The covered set travels in :class:`PassageExtraction` rather than being re-derived here, so
    the sidecar can only ever record the set the extraction actually ran over.
    """
    path = artifact_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(p.model_dump_json(by_alias=True) + "\n" for p in extraction.items)
    path.write_text(payload, encoding="utf-8")

    meta = {
        "published_pdfs": list(extraction.published_pdfs),
        "documents_with_passages": len({p.document_id for p in extraction.items}),
        "passage_count": len(extraction.items),
    }
    meta_path(settings).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
