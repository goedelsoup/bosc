"""``watermark catalog backfill`` — idempotently scaffold catalog entries from committed data.

Phase 1 of the data-catalog epic (#631, issue #624). Bootstraps the ~40 ``data/reference/*``
collections and the ``data/extracted/**`` collections into typed :class:`watermark.catalog.CatalogEntry`
stubs without hand-writing them, then keeps them in sync — so the catalog tracks the data BOSC
already produces instead of drifting from it.

**Discovery.** The data tree is the spine. Files under ``reference/`` and ``extracted/`` are
grouped into *logical datasets* by ``(collection directory, dotted-stem prefix)``, with the
**per-site axis collapsed**: a path segment that names a registered site (``watermark.sites.SITES``)
is templated to ``{site}``, so the eighteen ``eia/<slug>/consumer-energy.yaml`` files and Lima's
un-slugged ``eia/consumer-energy.yaml`` peer fold into one ``eia-consumer-energy`` entry whose
``site_scope`` is ``slug-scoped`` and whose ``storage`` carries the ``{site}`` template (the model
documents this: *for slug-scoped, the relpath is a template*). Each stub is then enriched from two
more sources — an embedded ``meta.source`` block where the producing connector wrote one, and a
curated ``command → collection`` hint map for the ``watermark`` regenerator and connector module.

**Idempotent + prose-preserving** (mirrors the periplus backfill): a discovered dataset is matched
to an existing entry by id *or* storage overlap (so a human-renamed reviewed entry is never
duplicated). ``reviewed`` entries are left untouched; ``needs-review`` entries have their
*mechanical* fields (storage, producer, scope) rewritten while the reviewer's curation
(``title``, ``license``, ``access_tier``, ``notes``, ``tags``, ``refresh``, and the editorial
``site_scope`` owner #778) is preserved verbatim; an unmatched dataset becomes a fresh
``needs-review`` stub with a mechanically-defaulted ``site_scope``. The human pass that flips
``needs-review → reviewed`` (filling license/access_tier) is tracked separately, not here.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.catalog import (
    CatalogEntry,
    Producer,
    ProducerKind,
    Refresh,
    Scope,
    SiteScope,
    SourceKind,
    StorageItem,
    load_entries,
)
from watermark.config import Settings, get_settings
from watermark.sites import SITES

# The scopes backfill scaffolds — the committed, reviewable artifact tree (issue #624). The
# raw LFS-heavy ``documents`` tree and the derived/bundle/people/poi scopes are out of scope.
BACKFILL_SCOPES: tuple[Scope, ...] = ("reference", "extracted")

# Files that are not datasets: prose, generator scripts, and OS/VCS noise.
_SKIP_NAMES = {"README.md", "ONBOARDING.md", ".gitignore", ".gitattributes", ".DS_Store"}
_SKIP_SUFFIXES = {".py"}

_MEDIA_TYPES: dict[str, str] = {
    ".yaml": "application/x-yaml",
    ".yml": "application/x-yaml",
    ".json": "application/json",
    ".geojson": "application/geo+json",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".zip": "application/zip",
}


class _ProducerHint(BaseModel):
    """A curated producer enrichment for a reference/extracted collection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ProducerKind
    command: str | None = None
    connector_ref: str | None = None


# The connector-backed reference collections (first path segment under ``reference/``) and the
# extracted pipeline — the de-scattering of the regeneration registry. A partial, *correct* map:
# collections without a hint scaffold as ``manual`` for a reviewer to fill, never guessed wrong.
_PRODUCER_HINTS: dict[str, _ProducerHint] = {
    "reference/echo": _ProducerHint(
        kind="connector", command="npdes", connector_ref="watermark.hydrology.connectors.echo"
    ),
    "reference/rsei": _ProducerHint(
        kind="connector", command="rsei", connector_ref="watermark.rsei"
    ),
    "reference/eia": _ProducerHint(
        kind="connector", command="eia", connector_ref="watermark.economics.energy"
    ),
    "reference/gleif": _ProducerHint(
        kind="connector", command="gleif", connector_ref="watermark.gleif"
    ),
    "reference/usaspending": _ProducerHint(
        kind="connector", command="usaspending", connector_ref="watermark.usaspending"
    ),
    "reference/lsc": _ProducerHint(kind="connector", command="lsc"),
    "reference/orc": _ProducerHint(kind="connector", command="orc"),
    "reference/hydrology": _ProducerHint(kind="connector", connector_ref="watermark.hydrology"),
}


def _is_data_file(path: Path) -> bool:
    return path.is_file() and path.name not in _SKIP_NAMES and path.suffix not in _SKIP_SUFFIXES


def _media_type(suffix: str) -> str:
    return _MEDIA_TYPES.get(suffix.lower(), "application/octet-stream")


def _slug(text: str) -> str:
    out = "".join(c if (c.islower() or c.isdigit()) else "-" for c in text.lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def _lfs_globs(repo_root: Path) -> list[tuple[str, str]]:
    """Parse ``.gitattributes`` into (prefix, ext) pairs for the ``filter=lfs`` patterns.

    Every LFS pattern in this repo has the shape ``<prefix>/**/*.<ext>`` (or ``…/**/<name>``),
    so a match is ``path.startswith(prefix) and path.endswith(ext)`` — enough to flag the
    reference PDFs and imagery GeoTIFFs without a full gitignore-style engine.
    """
    gitattributes = repo_root / ".gitattributes"
    if not gitattributes.exists():
        return []
    pairs: list[tuple[str, str]] = []
    for line in gitattributes.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "filter=lfs" not in line:
            continue
        pattern = line.split()[0]
        if "**" not in pattern:
            continue
        prefix, _, tail = pattern.partition("**")
        ext = tail.rsplit("*", 1)[-1]  # "/*.pdf" -> ".pdf"; "/name" -> "/name"
        pairs.append((prefix, ext))
    return pairs


def _site_segment(parts: tuple[str, ...]) -> int | None:
    """Index of the first path segment that names a registered site, or ``None``."""
    for i, part in enumerate(parts):
        if part in SITES:
            return i
    return None


class DiscoveredDataset(BaseModel):
    """A logical dataset found on disk — the scaffold for one :class:`CatalogEntry` (internal)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    scope: Scope
    site_scope: SiteScope
    storage: list[StorageItem]
    producer_kind: ProducerKind
    command: str | None = None
    connector_ref: str | None = None
    source: str | None = None  # from an embedded meta.source block, when present

    def _relpaths(self) -> set[str]:
        return {s.relpath for s in self.storage}


def _read_meta_source(path: Path) -> str | None:
    """The ``meta.source`` label from a YAML dataset member, if it carries one."""
    if path.suffix.lower() not in (".yaml", ".yml"):
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # a malformed/huge member is not worth crashing discovery over
        return None
    if isinstance(data, dict):
        meta = data.get("meta")
        if isinstance(meta, dict):
            source = meta.get("source")
            if isinstance(source, str):
                return source
    return None


def _provenance_for(kind: ProducerKind) -> SourceKind:
    mapping: dict[ProducerKind, SourceKind] = {
        "connector": "connector",
        "extracted": "document",
        "derived": "derived",
        "vendored": "reference",
        "manual": "reference",
    }
    return mapping[kind]


class _Member(BaseModel):
    """One discovered file before grouping (internal)."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    coll: str  # site-templated collection dir (e.g. "eia/{site}" or "echo")
    stem: str  # filename up to the first "."
    store_rel: str  # storage relpath, with the site segment templated to {site}
    abspath: Path
    lfs: bool
    site_scoped: bool


def discover_datasets(scope: Scope, *, settings: Settings | None = None) -> list[DiscoveredDataset]:
    """Discover the logical datasets committed under one ``scope`` (``reference``/``extracted``).

    Files are grouped by ``(site-templated collection dir, dotted-stem prefix)`` — but a real
    multi-file fileset (a stem shared by ≥2 files, e.g. ``maumee-wwtp.*``) becomes its own
    dataset, while the singleton files of a directory collapse into one directory-level bundle
    (so a dump of uniquely-named PDFs is one entry, not twenty). Per-site files collapse onto a
    ``{site}`` template and Lima's un-slugged peer folds in. Each dataset is enriched with a
    producer hint and an embedded ``meta.source``.
    """
    settings = settings or get_settings()
    root = settings.data_dir / scope
    lfs = _lfs_globs(settings.data_dir.parent)

    members: list[_Member] = []
    for path in sorted(root.rglob("*")):
        if not _is_data_file(path):
            continue
        rel = path.relative_to(settings.data_dir)  # e.g. reference/eia/bryan/consumer-energy.yaml
        coll_parts = rel.parts[1:-1]  # collection dirs between scope/ and the file
        site_idx = _site_segment(coll_parts)
        if site_idx is not None:
            templated = tuple("{site}" if i == site_idx else p for i, p in enumerate(coll_parts))
            store_rel = str(Path(scope, *templated, path.name))
            coll = "/".join(templated)
        else:
            store_rel = str(rel)
            coll = "/".join(coll_parts)
        is_lfs = any(
            str(rel).startswith(p.removeprefix("data/")) and str(rel).endswith(e) for p, e in lfs
        )
        members.append(
            _Member(
                coll=coll,
                stem=path.name.split(".", 1)[0],
                store_rel=store_rel,
                abspath=path,
                lfs=is_lfs,
                site_scoped=site_idx is not None,
            )
        )

    return _assemble(scope, members)


def _assemble(scope: Scope, members: list[_Member]) -> list[DiscoveredDataset]:
    """Group members into datasets: shared-stem filesets split out, singletons collapse to a bundle."""
    by_stem: dict[tuple[str, str], list[_Member]] = {}
    for m in members:
        by_stem.setdefault((m.coll, m.stem), []).append(m)

    # Fold Lima's un-slugged peer (collection without {site}) into the matching slug-scoped fileset.
    slug_parents: dict[tuple[str, str], tuple[str, str]] = {}
    for (coll, stem), ms in by_stem.items():
        if any(m.site_scoped for m in ms):
            parent = "/".join(p for p in coll.split("/") if p != "{site}")
            slug_parents[(parent, stem)] = (coll, stem)
    for key in list(by_stem):
        ms = by_stem[key]
        if any(m.site_scoped for m in ms):
            continue
        target = slug_parents.get(key)
        if target is not None and target != key:
            by_stem[target].extend(ms)
            del by_stem[key]

    # Per directory: a stem with ≥2 files is its own dataset; the rest fold into a dir bundle.
    bundle: dict[str, list[_Member]] = {}
    datasets: list[DiscoveredDataset] = []
    for (coll, stem), ms in sorted(by_stem.items()):
        if len(ms) >= 2:
            datasets.append(_dataset(scope, coll, stem, ms))
        else:
            bundle.setdefault(coll, []).extend(ms)
    for coll, ms in sorted(bundle.items()):
        datasets.append(_dataset(scope, coll, None, ms))
    return sorted(datasets, key=lambda d: d.id)


def _dataset(
    scope: Scope, coll: str, stem: str | None, members: list[_Member]
) -> DiscoveredDataset:
    """Build one :class:`DiscoveredDataset` from a group of members (a fileset or a dir bundle)."""
    coll_segs = [p for p in coll.split("/") if p and p != "{site}"]
    entry_id = "-".join(_slug(s) for s in [*coll_segs, *([stem] if stem else [])] if s)
    if not entry_id:  # collection was purely {site}: name a bundle by its member stems
        entry_id = "-".join(sorted({_slug(m.stem) for m in members}))

    seen: dict[str, StorageItem] = {}
    meta_source: str | None = None
    for m in sorted(members, key=lambda x: x.store_rel):
        if m.store_rel not in seen:
            seen[m.store_rel] = StorageItem(
                relpath=m.store_rel, media_type=_media_type(m.abspath.suffix), lfs=m.lfs
            )
        if meta_source is None:
            meta_source = _read_meta_source(m.abspath)

    if any(m.site_scoped for m in members):
        site_scope: SiteScope = "slug-scoped"
    elif all(m.stem.startswith("bosc-") for m in members):
        site_scope = "lima-legacy"  # bosc-prefixed reference/extracted files are Lima's
    else:
        site_scope = "basin-shared"

    hint = _producer_hint(scope, coll)
    kind: ProducerKind = hint.kind if hint else ("extracted" if scope == "extracted" else "manual")
    return DiscoveredDataset(
        id=entry_id,
        scope=scope,
        site_scope=site_scope,
        storage=sorted(seen.values(), key=lambda s: s.relpath),
        producer_kind=kind,
        command=hint.command if hint else None,
        connector_ref=hint.connector_ref if hint else None,
        source=meta_source,
    )


def _producer_hint(scope: Scope, coll: str) -> _ProducerHint | None:
    """The curated hint for a collection — keyed by the first segment under the scope root."""
    first = coll.split("/")[0] if coll else ""
    return _PRODUCER_HINTS.get(f"{scope}/{first}")


# --- the scaffold/refresh writer -----------------------------------------------------------
class BackfillAction(BaseModel):
    """One backfill outcome for a discovered dataset (surfaced by the CLI)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    scope: Scope
    action: Literal["create", "refresh", "skip-reviewed", "skip-unchanged"]
    relpath: str  # the catalog entry yaml, relative to settings.data_dir
    detail: str = ""


# CatalogEntry fields a reviewer owns — preserved verbatim when refreshing a needs-review stub.
_PRESERVED_FIELDS = (
    "title",
    "license",
    "access_tier",
    "refresh",
    "provenance",
    "schema_ref",
    "tags",
    "notes",
    # ``depends_on`` is editorial too (#1020): the process DAG is mapped by hand, so a
    # refreshed stub must never drop a reviewer's declared prerequisites.
    "depends_on",
    # ``site_scope`` is editorial (#778): a path can't tell that Fort Wayne's IDEM permits are
    # `site:fort-wayne` rather than a generic `slug-scoped` template, so the reviewer's owner tag
    # is preserved on refresh. The mechanical default below is only for a brand-new stub.
    "site_scope",
)


def _title_from_id(entry_id: str) -> str:
    return entry_id.replace("-", " ").title()


def _build_entry(ds: DiscoveredDataset, existing: CatalogEntry | None) -> CatalogEntry:
    """The scaffolded/refreshed entry: mechanical fields from ``ds``, prose from ``existing``."""
    producer = Producer(
        kind=ds.producer_kind,
        command=ds.command,
        connector_ref=ds.connector_ref,
        source=(
            ds.source or (existing.producer.source if existing else None) or "(unknown — fill in)"
        ),
        external_url=existing.producer.external_url if existing else None,
    )
    base: dict[str, object] = {
        "id": ds.id,
        "title": _title_from_id(ds.id),
        "scope": ds.scope,
        "status": "needs-review",
        "producer": producer,
        "site_scope": ds.site_scope,
        "storage": ds.storage,
        "refresh": Refresh(cadence="on-demand"),
        "provenance": _provenance_for(ds.producer_kind),
    }
    if existing is not None:
        for field in _PRESERVED_FIELDS:
            base[field] = getattr(existing, field)
    return CatalogEntry.model_validate(base)


def _strip_empty(value: object) -> object:
    """Recursively drop ``None`` and empty list/str values for clean, stable YAML."""
    if isinstance(value, dict):
        out: dict[str, object] = {}
        for key, val in value.items():  # model_dump preserves field-declaration order
            cleaned = _strip_empty(val)
            if cleaned is None or cleaned == [] or cleaned == "":
                continue
            out[key] = cleaned
        return out
    if isinstance(value, list):
        return [_strip_empty(v) for v in value]
    return value


def _dump_entry(entry: CatalogEntry) -> str:
    """Deterministic YAML for an entry: model field order, no nulls/empties, stable diffs."""
    clean = _strip_empty(entry.model_dump(mode="python"))
    return yaml.safe_dump(clean, sort_keys=False, allow_unicode=True, width=100)


def _match(
    ds: DiscoveredDataset, by_id: dict[str, CatalogEntry], by_relpath: dict[str, CatalogEntry]
) -> CatalogEntry | None:
    """Match a discovered dataset to an existing entry by id, else by storage overlap.

    A discovered slug-scoped dataset carries a ``{site}`` template in its relpaths; an existing
    entry may instead pin a single site *literally* (a reviewer-owned ``site:<slug>`` scope, #778).
    So after the exact checks, match the template against those literal paths — otherwise a lone
    per-site file (e.g. Wilmington's ``watch-items.geojson``) is re-proposed as a fresh generic
    entry the moment a sibling site's file promotes the shared stem to a real ``≥2`` fileset (which
    is exactly what a second ``parcel-assemblage`` site does to the ``{site}`` singleton bundle).
    """
    if ds.id in by_id:
        return by_id[ds.id]
    for rel in ds._relpaths():
        if rel in by_relpath:
            return by_relpath[rel]
    for rel in ds._relpaths():
        if "{site}" not in rel:
            continue
        pattern = re.compile("^" + re.escape(rel).replace(r"\{site\}", "[^/]+") + "$")
        for committed_rel, entry in by_relpath.items():
            if pattern.match(committed_rel):
                return entry
    return None


def backfill(
    *,
    scopes: tuple[Scope, ...] = BACKFILL_SCOPES,
    only: str | None = None,
    apply: bool = False,
    settings: Settings | None = None,
) -> list[BackfillAction]:
    """Scaffold/refresh catalog entries from committed data; write only when ``apply``.

    Returns one :class:`BackfillAction` per discovered dataset. ``only`` filters to ids with
    that prefix. Existing ``reviewed`` entries are never touched; ``needs-review`` entries are
    refreshed in place (prose preserved) and skipped when the render is byte-identical.
    """
    settings = settings or get_settings()
    existing = load_entries(settings=settings)
    by_id = {e.id: e for e in existing}
    by_relpath = {s.relpath: e for e in existing for s in e.storage}

    actions: list[BackfillAction] = []
    for scope in scopes:
        for ds in discover_datasets(scope, settings=settings):
            if only and not ds.id.startswith(only):
                continue
            match = _match(ds, by_id, by_relpath)
            target = settings.catalog_dir / scope / f"{ds.id}.yaml"
            relpath = str(target.relative_to(settings.data_dir))
            if match is not None and match.status == "reviewed":
                actions.append(
                    BackfillAction(
                        id=ds.id,
                        scope=scope,
                        action="skip-reviewed",
                        relpath=relpath,
                        detail=f"covered by reviewed entry {match.id!r}",
                    )
                )
                continue
            entry = _build_entry(ds, match)
            rendered = _dump_entry(entry)
            entry_path = settings.catalog_dir / scope / f"{entry.id}.yaml"
            entry_rel = str(entry_path.relative_to(settings.data_dir))
            if match is not None:
                current = entry_path.read_text(encoding="utf-8") if entry_path.exists() else ""
                if current == rendered:
                    actions.append(
                        BackfillAction(
                            id=entry.id,
                            scope=scope,
                            action="skip-unchanged",
                            relpath=entry_rel,
                        )
                    )
                    continue
                action: Literal["create", "refresh"] = "refresh"
            else:
                action = "create"
            if apply:
                entry_path.parent.mkdir(parents=True, exist_ok=True)
                entry_path.write_text(rendered, encoding="utf-8")
            actions.append(
                BackfillAction(
                    id=entry.id,
                    scope=scope,
                    action=action,
                    relpath=entry_rel,
                    detail=f"{len(entry.storage)} file(s) · {entry.site_scope}",
                )
            )
    return actions
