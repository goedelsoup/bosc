"""Corpus ingestion: chunk source documents, reference data, and extracted YAMLs (#809).

Yields :class:`~watermark.retrieval.store.Chunk` objects for each indexed fragment.
The full source document tree is indexed (not just extracted artifacts) so the agent
can surface genuinely unextracted context and report it as a lead rather than silently
missing it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from watermark.retrieval.store import Chunk

if TYPE_CHECKING:
    from watermark.sites import CorpusScope

_MAX_CHUNK_CHARS = 4_000
_CORPUS_HOME = "lima"


def _chunk_id(*parts: str) -> str:
    return "::".join(parts)


def _split_text(text: str, *, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split *text* on paragraph boundaries into chunks of at most *max_chars*."""
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0
        current.append(para)
        current_len += len(para) + 2  # account for \n\n
    if current:
        chunks.append("\n\n".join(current))
    return chunks or [text[:max_chars]]


def _prov(**kw: Any) -> dict[str, Any]:
    return {k: v for k, v in kw.items() if v is not None}


def _pdf_chunks(path: Path, source_rel: str, collection: str) -> Iterator[Chunk]:
    """One chunk per page of a PDF, from its pypdf text layer."""
    import pypdf  # already a core dep

    try:
        reader = pypdf.PdfReader(str(path), strict=False)
    except Exception:
        return

    # Iterating reader.pages lazily parses each page, and a malformed PDF can raise mid-traversal
    # (not just in extract_text) — wrap the loop so a broken document contributes the pages it
    # could and is then dropped, never aborting the whole index build. Same guard as the export
    # side's watermark.site.passages.build_passages.
    try:
        for page_idx, page in enumerate(reader.pages):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""

            if not text:
                text = f"[image-only page; no text layer — source: {path.name} p.{page_idx + 1}]"

            yield Chunk(
                chunk_id=_chunk_id("document", source_rel, str(page_idx)),
                text=text[:_MAX_CHUNK_CHARS],
                site="",
                collection=collection,
                doc_kind="document",
                source_path=source_rel,
                page=page_idx,
                provenance=_prov(
                    filename=path.name,
                    page_1indexed=page_idx + 1,
                    collection=collection or None,
                ),
            )
    except Exception:
        return


def _text_chunks(
    text: str,
    *,
    source_rel: str,
    filename: str,
    collection: str,
    text_source: str,
    sidecar: str | None = None,
) -> Iterator[Chunk]:
    """Paragraph-split chunks for a document with no page structure.

    ``page`` is ``-1`` (the same "not paginated" convention the reference iterator uses); the
    provenance names the reader that produced the text, and — for a converted legacy format — the
    committed sidecar it was read from, so a result can always be traced back to how it was made.
    """
    for chunk_idx, chunk_text in enumerate(_split_text(text)):
        yield Chunk(
            chunk_id=_chunk_id("document", source_rel, str(chunk_idx)),
            text=chunk_text[:_MAX_CHUNK_CHARS],
            site="",
            collection=collection,
            doc_kind="document",
            source_path=source_rel,
            page=-1,
            provenance=_prov(
                filename=filename,
                chunk=chunk_idx if chunk_idx else None,
                collection=collection or None,
                text_source=text_source,
                sidecar=sidecar,
            ),
        )


def iter_document_chunks(documents_dir: Path) -> Iterator[Chunk]:
    """Yield retrieval chunks for every readable source document under *documents_dir*.

    Documents are corpus-global (not site-scoped); the agent retrieves them with
    no site filter when looking for any site's source context.

    Three routes, by what the bytes are (#1757 — before it, only the first existed, which left
    the whole native Office/browser tranche of the batch-3 sanitary production unsearchable):

    * **PDF** → one chunk per page, from the pypdf text layer. An image-only page still yields a
      chunk, marked as having no text layer, so the gap is retrievable rather than absent.
    * **Natively readable** (``.txt``/``.htm``/``.html``/``.docx``/``.xlsx``, via
      :mod:`watermark.documents.office`) → paragraph-split chunks, ``page=-1``.
    * **Legacy binary** (``.doc``/``.dot``/``.xls``/``.rtf``) → read from its committed
      ``-text`` sidecar (:mod:`watermark.text_sidecars`), and attributed to the **source**
      document: ``source_path`` is the ``.DOC``, never the derived ``.txt``, so a citation names
      the record. The sidecar's own path is carried in the provenance.

    Files with no extension are routed by their magic bytes (three arrived that way and are never
    renamed). Anything else — images, media, the sidecar trees' own manifests — is skipped.
    """
    from watermark.documents.office import (
        NATIVE_TEXT_SUFFIXES,
        detect_suffix,
        plain_text,
        read_native_text,
    )
    from watermark.text_sidecars import in_sidecar_tree, sidecar_source_rel

    for path in sorted(documents_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(documents_dir)
        rel_posix = rel.as_posix()

        if in_sidecar_tree(rel_posix, documents_dir):
            source = sidecar_source_rel(rel_posix, documents_dir)
            if source is None:
                continue  # the tree's own manifest/README, or a sidecar whose source is gone
            text = plain_text(path).strip()
            if not text:
                continue
            source_rel = str(source)
            yield from _text_chunks(
                text,
                source_rel=source_rel,
                filename=PurePosixPath(source_rel).name,
                collection=source.parts[0] if len(source.parts) > 1 else "",
                text_source="sidecar",
                sidecar=rel_posix,
            )
            continue

        suffix = detect_suffix(path)
        if suffix not in {".pdf", *NATIVE_TEXT_SUFFIXES}:
            continue

        source_rel = str(rel)
        collection = rel.parts[0] if len(rel.parts) > 1 else ""
        if suffix == ".pdf":
            yield from _pdf_chunks(path, source_rel, collection)
            continue

        text, method = read_native_text(path, suffix=suffix)
        if not text:
            continue
        yield from _text_chunks(
            text,
            source_rel=source_rel,
            filename=path.name,
            collection=collection,
            text_source=method,
        )


def iter_reference_chunks(reference_dir: Path) -> Iterator[Chunk]:
    """Yield chunks from data/reference/ (README summaries, CSVs, YAMLs)."""
    if not reference_dir.exists():
        return

    for path in sorted(reference_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(reference_dir)
        collection = rel.parts[0] if len(rel.parts) > 1 else str(rel.parent)
        source_rel = str(rel)
        suffix = path.suffix.lower()

        if suffix not in {".csv", ".md", ".yaml", ".yml", ".txt", ".json"}:
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        if suffix == ".csv":
            lines = text.splitlines()
            if not lines:
                continue
            header = lines[0]
            for row_idx, row in enumerate(lines[1:], start=1):
                if not row.strip():
                    continue
                yield Chunk(
                    chunk_id=_chunk_id("reference", source_rel, str(row_idx)),
                    text=f"{header}\n{row}",
                    site="",
                    collection=collection,
                    doc_kind="reference",
                    source_path=source_rel,
                    page=-1,
                    provenance=_prov(file=path.name, row=row_idx),
                )
        else:
            for chunk_idx, chunk_text in enumerate(_split_text(text)):
                yield Chunk(
                    chunk_id=_chunk_id("reference", source_rel, str(chunk_idx)),
                    text=chunk_text,
                    site="",
                    collection=collection,
                    doc_kind="reference",
                    source_path=source_rel,
                    page=-1,
                    provenance=_prov(file=path.name, chunk=chunk_idx if chunk_idx else None),
                )


def _corpus_scope(site: str) -> CorpusScope:
    """The extracted-tree region that belongs to *site* — the same scope the export /
    timeline / entities path reads (#1504).

    Resolved from the site's registered :class:`~watermark.sites.SiteProfile` via
    :func:`~watermark.sites.effective_corpus_scope`, so ``retrieve_corpus(site=…)`` and the
    site bundle agree on the corpus. Lima (the reference build) reads the whole tree minus every
    peer's subtree (#1505); a registered peer reads only the prefixes its profile names (its own
    ``<slug>/`` plus any jurisdiction prefix like ``idem/fort-wayne``). An unregistered slug
    falls back to that same default (``(slug,)``, or whole-tree for the corpus home) so the
    iterator never raises on an ad-hoc ``watermark index --site`` value.
    """
    from watermark.sites import SITES, CorpusScope, effective_corpus_scope

    profile = SITES.get(site)
    if profile is not None:
        return effective_corpus_scope(profile)
    return CorpusScope(include=None) if site == _CORPUS_HOME else CorpusScope(include=(site,))


def iter_extracted_chunks(extracted_dir: Path, *, site: str) -> Iterator[Chunk]:
    """Yield chunks from the *site*'s extracted YAML artifacts under *extracted_dir*.

    Membership is decided by the site's corpus scope (:func:`_corpus_scope`) through the same
    ``relpath_in_scope`` predicate the export/timeline/entities path uses (#1504) — so a site
    whose records live under a collection prefix (Fort Wayne's ``idem/fort-wayne``, Urbana's
    ``oepa/urbana``) is reachable by ``retrieve_corpus(site=…)``, not just its bare ``<slug>/``
    subdir. Lima (scope ``None``) indexes the whole tree.

    A file that lives under both Lima's whole tree and a peer's scope is indexed once per site
    (same ``chunk_id``, different ``site`` column) — the pre-existing behavior for every peer's
    ``<slug>/`` subtree, kept consistent here. Narrowing Lima's pass to exclude registered peer
    prefixes is the separate Lima-bundle concern (#1505).
    """
    from watermark.pipeline.corpus import relpath_in_scope

    if not extracted_dir.exists():
        return

    scope = _corpus_scope(site)

    for path in sorted(extracted_dir.rglob("*.yaml")):
        rel = path.relative_to(extracted_dir)
        source_rel = str(rel)
        if not relpath_in_scope(source_rel, scope):
            continue
        collection = rel.parts[0] if len(rel.parts) > 1 else ""

        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for chunk_idx, chunk_text in enumerate(_split_text(text)):
            yield Chunk(
                chunk_id=_chunk_id("extracted", source_rel, str(chunk_idx)),
                text=chunk_text,
                site=site,
                collection=collection,
                doc_kind="extracted",
                source_path=source_rel,
                page=-1,
                provenance=_prov(
                    file=path.name,
                    chunk=chunk_idx if chunk_idx else None,
                    collection=collection or None,
                ),
            )
