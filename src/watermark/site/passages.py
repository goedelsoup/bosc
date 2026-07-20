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
* **Text layer only.** Page text is the pypdf text-layer extraction, the same source the agent-side
  :func:`watermark.retrieval.ingestion.iter_document_chunks` reads — but here scoped to the published
  set and joined to the ``documents`` feed. For a scanned document the text layer is garbled OCR
  (per the root CLAUDE.md, never trust its digits); the excerpt is a **locator** for the cited page,
  not a transcription. Image-only pages (no text layer) carry no excerpt and are skipped.

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

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from watermark.logging import get_logger
from watermark.site.feeds import PassageItem

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

# Match the agent-side chunk cap (watermark.retrieval.ingestion._MAX_CHUNK_CHARS) so a page's
# excerpt is bounded identically on both retrieval paths.
_MAX_PASSAGE_CHARS = 4_000

# The committed, LFS-independent passage artifact (relative to settings.data_dir). Global (documents
# are corpus-global): each per-site export filters it to that site's published docs.
_ARTIFACT_RELPATH = ("site", "passages.ndjson")


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
) -> list[PassageItem]:
    """Extract one :class:`PassageItem` per text-bearing page of each published PDF.

    ``documents_feed`` is the assembled ``documents`` feed (a list of ``DocumentCollectionItem``
    dicts); ``documents_dir`` is ``settings.documents_dir`` (the join base for ``document_id``). A
    PDF that can't be opened (an unresolved Git-LFS pointer, a corrupt file) yields no passages and
    is skipped — the feed degrades to what's readable, never raising, exactly like
    :func:`~watermark.retrieval.ingestion.iter_document_chunks`.
    """
    import pypdf  # a core dep (also used by the extract pipeline + retrieval ingestion)

    passages: list[PassageItem] = []
    skipped_docs = 0
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
                    )
                )
        except Exception:
            skipped_docs += 1
    log.info(
        "passages.built",
        passages=len(passages),
        published_pdfs=len(_published_pdf_entries(documents_feed)),
        skipped_docs=skipped_docs,
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
    at export time. The publish allowlist + exhibit auto-includes are resolved exactly as the export
    does, but over the **whole tree** (``scope=None``) so the one global artifact covers every site's
    published docs; each per-site ``_passages_feed`` filters it back down to its own set.
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
