"""Build the ``passages`` feed (#1589) — a page-level excerpt index over the published PDFs.

The passages feed turns a "which page says X" question into a page-cited excerpt instead of a
whole-record pull: one :class:`~watermark.site.feeds.PassageItem` per text-bearing page of every
*published* source PDF. It powers the web ``search_passages`` MCP tool (epic #1579 Phase 3).

Two invariants shape the scope:

* **Publish allowlist (#280).** Passages come only from documents the ``documents`` feed marks
  ``published`` — the same default-deny allowlist that governs which source *bytes* are served
  publicly. A non-published document's text never enters the bundle (chain of custody), which also
  keeps the feed small (the allowlist is a curated handful of collections, not the whole corpus).
* **Text layer only.** Page text is the pypdf text-layer extraction, the same source the agent-side
  :func:`watermark.retrieval.ingestion.iter_document_chunks` reads — but here scoped to the published
  set and joined to the ``documents`` feed. For a scanned document the text layer is garbled OCR
  (per the root CLAUDE.md, never trust its digits); the excerpt is a **locator** for the cited page,
  not a transcription. Image-only pages (no text layer) carry no excerpt and are skipped.

This module does the text extraction; :func:`watermark.site.embeddings.build_passage_embeddings`
vectorises the emitted feed (the same split as ``ask-embeddings``: text here, vectors there).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from watermark.logging import get_logger
from watermark.site.feeds import PassageItem

log = get_logger(__name__)

# Match the agent-side chunk cap (watermark.retrieval.ingestion._MAX_CHUNK_CHARS) so a page's
# excerpt is bounded identically on both retrieval paths.
_MAX_PASSAGE_CHARS = 4_000


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
    log.info(
        "passages.built",
        passages=len(passages),
        published_pdfs=len(_published_pdf_entries(documents_feed)),
        skipped_docs=skipped_docs,
    )
    return passages
