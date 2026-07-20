"""Catalog the full source-document corpus as typed library feeds.

Mission goal (1): *present a downloadable form of each document.* The raw corpus
under ``data/documents`` is ~5 GB across ~1,500 files — far too large to
republish onto a static host — so this exports a complete **catalog** instead
(:func:`export_documents` → :class:`~watermark.site.feeds.DocumentCollectionItem`),
listing every source file with its size and type. Direct downloads are wired only
for the curated :mod:`watermark.site.exhibits`; the rest are catalogued with their
repo-relative path so the record is transparent even when the bytes aren't
republished. (The legacy markdown ``render_documents`` peer was removed at the
SSG-cutover cleanup, #603.)

Set ``settings.documents_mirror_base_url`` to an external mirror (Archive.org /
S3 / Drive) to turn every catalogued file into a direct download link.

Chain of custody: this only *reads* and *links* source files — it never copies,
renames, or alters a byte under ``data/documents``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from urllib.parse import quote

import yaml

from watermark.logging import get_logger
from watermark.pipeline.corpus import relpath_in_scope
from watermark.site import exhibits as exhibits_mod
from watermark.site.feeds import DocumentCollectionItem, DocumentItem, RenderClass
from watermark.sites import CorpusScopeArg

log = get_logger(__name__)

# Extension -> (MIME, render_class). The fallback when a content sniff can't positively
# identify the file. `render_class` is what the frontend viewer dispatches on (#274/#275):
# image/text/html inline, pdf native+PDF.js, office (doc/docx/odg) download-only.
_EXT_MEDIA: dict[str, tuple[str, RenderClass]] = {
    "pdf": ("application/pdf", "pdf"),
    "png": ("image/png", "image"),
    "jpg": ("image/jpeg", "image"),
    "jpeg": ("image/jpeg", "image"),
    "gif": ("image/gif", "image"),
    "webp": ("image/webp", "image"),
    "bmp": ("image/bmp", "image"),
    "tif": ("image/tiff", "image"),
    "tiff": ("image/tiff", "image"),
    "svg": ("image/svg+xml", "image"),
    "html": ("text/html", "html"),
    "htm": ("text/html", "html"),
    "txt": ("text/plain", "text"),
    "csv": ("text/csv", "text"),
    "json": ("application/json", "text"),
    "md": ("text/markdown", "text"),
    "doc": ("application/msword", "office"),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "office",
    ),
    "odg": ("application/vnd.oasis.opendocument.graphics", "office"),
    "odt": ("application/vnd.oasis.opendocument.text", "office"),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", "office"),
    "odp": ("application/vnd.oasis.opendocument.presentation", "office"),
    "xls": ("application/vnd.ms-excel", "office"),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "office",
    ),
    "ppt": ("application/vnd.ms-powerpoint", "office"),
    "pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "office",
    ),
}
_FALLBACK_MEDIA: tuple[str, RenderClass] = ("application/octet-stream", "other")


def _sniff_media(head: bytes) -> tuple[str, RenderClass] | None:
    """Identify a file from its leading magic bytes, or ``None`` if unrecognized.

    Only the signatures we can positively identify — degraded scans and mislabeled
    extensions are common in this corpus, so a confident sniff is trusted over the name.
    """
    if head.startswith(b"%PDF"):
        return ("application/pdf", "pdf")
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ("image/png", "image")
    if head.startswith(b"\xff\xd8\xff"):
        return ("image/jpeg", "image")
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ("image/gif", "image")
    return None


def _media_type_and_render_class(
    path: Path, suffix: str, *, sniffable: bool
) -> tuple[str, RenderClass]:
    """Resolve ``(media_type, render_class)`` for a source file (epic #274 / #275).

    Sniffs the leading bytes and trusts a confident sniff over the extension; falls back
    to the extension table otherwise. A Git-LFS pointer has no real local bytes (its content
    is pointer text), so when the file isn't sniffable we trust the extension instead.
    """
    by_ext = _EXT_MEDIA.get(suffix, _FALLBACK_MEDIA)
    if not sniffable:
        return by_ext
    try:
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError:
        return by_ext
    return _sniff_media(head) or by_ext


# Companion / metadata files that describe a collection rather than being source
# documents in their own right — kept out of the catalog (READMEs are surfaced
# separately as collection descriptions).
_SKIP_NAMES = frozenset({".DS_Store", "README.md", "MANIFEST.yaml"})
_SKIP_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".sh"})

# Human labels for collection slugs where title-casing the slug reads wrong.
_COLLECTION_LABELS: dict[str, str] = {
    "aedg": "AEDG (Allen Economic Development Group)",
    "oepa": "Ohio EPA",
    "lacrpc": "LACRPC (regional planning)",
    "maumee-tmdl": "Maumee Watershed Nutrient TMDL",
    "lima": "City of Lima",
    "prr-mandamus": "PRR & mandamus (legal history)",
    "recorder": "County Recorder (deeds)",
    "commissioners": "County Commissioners",
}


@dataclass
class DocumentEntry:
    """One catalogued source file under ``data/documents``."""

    rel: str  # path relative to data/documents (the as-received name, never altered)
    name: str
    size_bytes: int
    suffix: str
    media_type: str  # MIME, from the real file (extension + content sniff)
    render_class: RenderClass  # what the viewer dispatches on (#274/#275)
    published: bool  # cleared for public serving: in cleared scope and not withheld (#280)
    available: bool  # the bytes are servable (real file or LFS pointer → R2), not missing
    download_url: str | None  # exhibit link or external mirror URL, when present
    # Version / duplicate-cluster metadata (#1590) is NOT carried here: it's stamped by
    # watermark.site.docversions onto the Pydantic DocumentItems after the catalog is built
    # (apply_document_versions), so DocumentItem's own defaults apply for an unclustered file.


@dataclass
class DocumentCollection:
    """A top-level collection (``data/documents/<slug>/``) and its files."""

    slug: str
    title: str
    description: str
    entries: list[DocumentEntry] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(e.size_bytes for e in self.entries)

    @property
    def n_downloadable(self) -> int:
        return sum(1 for e in self.entries if e.download_url)


@dataclass
class DocumentsResult:
    collections: list[DocumentCollection]

    @property
    def n_documents(self) -> int:
        return sum(len(c.entries) for c in self.collections)

    @property
    def n_downloadable(self) -> int:
        return sum(c.n_downloadable for c in self.collections)


_LFS_POINTER_MAGIC = b"version https://git-lfs.github.com/spec/v1"


def _lfs_pointer_size(head: bytes) -> int | None:
    """The real byte size recorded in a Git-LFS pointer, or ``None`` if not a pointer.

    A pointer is short YAML-ish text (``version`` / ``oid`` / ``size`` lines); the ``size``
    line carries the true size of the bytes that live in LFS/R2 storage, so we can report
    it without pulling the object.
    """
    if not head.startswith(_LFS_POINTER_MAGIC):
        return None
    for line in head.split(b"\n"):
        if line.startswith(b"size "):
            try:
                return int(line[len(b"size ") :].strip())
            except ValueError:
                return None
    return None


def _document_stat(path: Path) -> tuple[int, bool, bool]:
    """Resolve ``(size_bytes, available, is_pointer)`` for a source file (#1347).

    An unpulled Git-LFS pointer is **not** absent: its bytes live in LFS/R2 and are served
    from the object store (``/api/doc``), not the build tree — so it counts as available,
    with the true size read from the pointer text. Only an unreadable/missing file is absent.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(256)
        ptr_size = _lfs_pointer_size(head)
        if ptr_size is not None:
            return ptr_size, True, True
        return path.stat().st_size, True, False
    except OSError:
        return 0, False, False


def _collection_title(slug: str) -> str:
    return _COLLECTION_LABELS.get(slug, slug.replace("-", " ").title())


def _collection_description(collection_dir: Path) -> str:
    """First non-heading paragraph of the collection's README, if any."""
    readme = collection_dir / "README.md"
    if not readme.is_file():
        return ""
    para: list[str] = []
    for line in readme.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("<!--"):
            if para:
                break
            continue
        if not stripped:
            if para:
                break
            continue
        para.append(stripped)
    return " ".join(para).strip()


def _download_url(rel: str, *, exhibit_links: dict[str, str], mirror_base_url: str) -> str | None:
    """Resolve a download link for a source file: exhibit first, then mirror."""
    if rel in exhibit_links:
        # From documents/<collection>.md up to exhibits/<name>.
        return f"../exhibits/{exhibit_links[rel]}"
    if mirror_base_url:
        base = mirror_base_url.rstrip("/")
        return f"{base}/{quote(rel)}"
    return None


def build_documents(
    documents_dir: Path,
    *,
    exhibits: list[exhibits_mod.Exhibit] | None = None,
    mirror_base_url: str = "",
    allowlist: PublishAllowlist | None = None,
) -> DocumentsResult:
    """Walk ``data/documents`` and assemble the per-collection catalog.

    ``allowlist`` (#280) sets each entry's ``published`` flag; ``None`` means default-deny
    (nothing public), which is correct for a catalog built without the publish gate.
    """
    # Source path -> published exhibit filename, for direct-download cross-links.
    exhibit_links: dict[str, str] = {
        ex.source: ex.out_name
        for ex in (exhibits or [])
        if ex.available and ex.out_name is not None
    }

    collections: dict[str, DocumentCollection] = {}
    if not documents_dir.is_dir():
        log.warning("site.documents.no_dir", path=str(documents_dir))
        return DocumentsResult(collections=[])

    for path in sorted(documents_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in _SKIP_NAMES or path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        rel_path = path.relative_to(documents_dir)
        # A collection is a first-level subdirectory; a file dropped directly under
        # documents_dir has no collection and would otherwise become a single-file
        # "collection" named after the file (#617). Skip it, surfaced for review.
        if len(rel_path.parts) < 2:
            log.warning("site.documents.uncollected_file", path=str(rel_path))
            continue
        slug = rel_path.parts[0]
        rel = str(rel_path)
        coll = collections.get(slug)
        if coll is None:
            coll = DocumentCollection(
                slug=slug,
                title=_collection_title(slug),
                description=_collection_description(documents_dir / slug),
            )
            collections[slug] = coll
        size, available, is_pointer = _document_stat(path)
        suffix = path.suffix.lower().lstrip(".")
        media_type, render_class = _media_type_and_render_class(
            path, suffix, sniffable=not is_pointer
        )
        coll.entries.append(
            DocumentEntry(
                rel=rel,
                name=path.name,
                size_bytes=size,
                suffix=suffix,
                media_type=media_type,
                render_class=render_class,
                published=allowlist.is_published(rel) if allowlist is not None else False,
                available=available,
                download_url=(
                    _download_url(rel, exhibit_links=exhibit_links, mirror_base_url=mirror_base_url)
                    if available
                    else None
                ),
            )
        )

    ordered = [collections[s] for s in sorted(collections)]
    result = DocumentsResult(collections=ordered)
    log.info(
        "site.documents.cataloged",
        collections=len(ordered),
        documents=result.n_documents,
        downloadable=result.n_downloadable,
    )
    return result


def export_documents(
    documents_dir: Path,
    *,
    exhibits: list[exhibits_mod.Exhibit] | None = None,
    mirror_base_url: str = "",
    allowlist: PublishAllowlist | None = None,
    scope: CorpusScopeArg = None,
) -> list[DocumentCollectionItem]:
    """Export the source-document catalog as :class:`DocumentCollectionItem` items.

    Reuses :func:`build_documents` (the same enumeration the renderer uses) without
    writing any markdown — each file keeps its as-received corpus path (chain of custody).
    ``allowlist`` (#280) sets each item's ``published`` flag; ``None`` is default-deny.

    ``scope`` is the active site's corpus prefixes (#762): when set, only documents whose rel
    is in scope are exported (so a non-Lima site's catalog carries its own source docs, e.g.
    ``idem/<slug>/…``), and a collection left with no in-scope entries is dropped. ``None``
    exports the whole tree (Lima, the reference build).
    """
    result = build_documents(
        documents_dir, exhibits=exhibits, mirror_base_url=mirror_base_url, allowlist=allowlist
    )
    items: list[DocumentCollectionItem] = []
    for c in result.collections:
        entries = [
            DocumentItem(
                rel=e.rel,
                name=e.name,
                size_bytes=e.size_bytes,
                suffix=e.suffix,
                media_type=e.media_type,
                render_class=e.render_class,
                published=e.published,
                available=e.available,
                download_url=e.download_url,
                # duplicate_cluster / canonical_document_id / version / supersedes default here;
                # apply_document_versions stamps them onto the clustered items afterward (#1590).
            )
            for e in c.entries
            if relpath_in_scope(e.rel, scope)
        ]
        if not entries:
            continue
        items.append(
            DocumentCollectionItem(
                slug=c.slug, title=c.title, description=c.description, entries=entries
            )
        )
    return items


@dataclass(frozen=True)
class PublishScope:
    """A set of ``data/documents`` rels named by three optional rule kinds.

    A rel is *in scope* when it's an exact ``documents`` rel, its first path segment is a
    whole ``collections`` entry, or it matches any ``globs`` (``fnmatch``) pattern. Used for
    both sides of the publish policy: the cleared scope and the withhold denylist.
    """

    collections: frozenset[str] = frozenset()
    globs: tuple[str, ...] = ()
    documents: frozenset[str] = frozenset()

    def matches(self, rel: str) -> bool:
        if rel in self.documents:
            return True
        if rel.split("/", 1)[0] in self.collections:
            return True
        return any(fnmatch(rel, g) for g in self.globs)


@dataclass(frozen=True)
class PublishAllowlist:
    """The public publish policy: publishable-by-default within reviewed scope, withhold
    declaratively (epic #274 / C1 #280).

    A rel is **public** iff it falls inside a **cleared** boundary *and* is not on the
    **withhold** denylist:

    * **Cleared scope** — the fail-safe eligibility gate. The three flat fields name it with
      the same three rule kinds as :class:`PublishScope`: exact ``documents`` rels (incl. the
      curated exhibits, which are always auto-included so their existing download links keep
      working), whole ``collections`` (first path segment), and ``globs``. A rel in **no**
      cleared boundary is never public, so an unreviewed file stays private by default — a
      boundary is cleared only after the C2 redaction/PII pass.
    * **Publishable-by-default within scope** — inside a cleared boundary every file publishes;
      you no longer have to restate each one.
    * **Withhold** — the declarative opt-out. A withhold rule carves a rel (or subtree, or
      glob) back out of a cleared boundary. Withhold **wins over everything**, including the
      auto-included exhibits, so it is the authoritative way to keep a specific file off the
      public surface.
    """

    collections: frozenset[str] = frozenset()
    globs: tuple[str, ...] = ()
    documents: frozenset[str] = frozenset()  # cleared exact rels, incl. auto-included exhibits
    withhold: PublishScope = PublishScope()  # declarative opt-out; wins over the cleared scope

    def is_published(self, rel: str) -> bool:
        cleared = (
            rel in self.documents
            or rel.split("/", 1)[0] in self.collections
            or any(fnmatch(rel, g) for g in self.globs)
        )
        return cleared and not self.withhold.matches(rel)


def _parse_scope(data: Any) -> tuple[list[str], list[str], list[str]]:
    """Parse one scope block into ``(collections, globs, documents)``.

    Accepts either a mapping carrying optional ``collections`` / ``globs`` / ``documents``
    lists, or a bare list — shorthand for ``documents`` (exact rels), the common withhold form.
    """
    if isinstance(data, Mapping):
        return (
            [str(s).strip() for s in (data.get("collections") or []) if str(s).strip()],
            [str(g).strip() for g in (data.get("globs") or []) if str(g).strip()],
            [str(r).strip() for r in (data.get("documents") or []) if str(r).strip()],
        )
    if isinstance(data, list):
        return ([], [], [str(r).strip() for r in data if str(r).strip()])
    return ([], [], [])


def load_publish_allowlist(path: Path, *, exhibit_sources: Iterable[str] = ()) -> PublishAllowlist:
    """Load the publish-policy YAML, auto-including the curated exhibits in the cleared scope.

    The file (``data/site/published-documents.yaml``, C1 / #280) carries the cleared scope as
    top-level ``collections`` / ``globs`` / ``documents`` lists, plus an optional ``withhold``
    block (a mapping of the same three kinds, or a bare list of exact rels). A missing or empty
    file means nothing is cleared **except** the exhibits — which are always allowed because
    they're already published downloads. A boundary is cleared by hand only after the C2
    redaction pass; a withhold rule then carves individual files back out.
    """
    collections: list[str] = []
    globs: list[str] = []
    documents: list[str] = list(exhibit_sources)
    withhold = PublishScope()
    if path.is_file():
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            log.warning(
                "site.documents.bad_allowlist", path=str(path), error=str(exc).splitlines()[0]
            )
            data = {}
        if isinstance(data, Mapping):
            cleared_c, cleared_g, cleared_d = _parse_scope(data)
            collections, globs = cleared_c, cleared_g
            documents += cleared_d
            wc, wg, wd = _parse_scope(data.get("withhold"))
            withhold = PublishScope(frozenset(wc), tuple(wg), frozenset(wd))
    return PublishAllowlist(
        collections=frozenset(collections),
        globs=tuple(globs),
        documents=frozenset(documents),
        withhold=withhold,
    )


def build_doc_index(
    collections: list[DocumentCollectionItem],
) -> dict[str, tuple[RenderClass, bool]]:
    """``rel -> (render_class, published)`` for every catalogued source file.

    The join target for records (#274 / #276): a record resolves its real source
    document only when that file is actually in the catalog, so a stale or removed
    ``source_path`` yields no link rather than a broken one. ``published`` is read
    straight off each :class:`DocumentItem` (set by the allowlist in ``export_documents``).
    """
    return {e.rel: (e.render_class, e.published) for coll in collections for e in coll.entries}
