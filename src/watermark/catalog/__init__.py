"""The BOSC data catalog — one typed entry per dataset under ``data/``.

A unified, git-backed, Pydantic-validated registry (epic #631) that finally answers, in
one place: *what datasets do we have, where did each come from, when was it last refreshed,
what's its license/access tier, what command regenerates it, is it stale?* Today three
siloed catalog-shaped things each cover a slice — the bundle ``manifest.json`` (published
feeds), the documents feed (raw corpus), and ~40 hand-written ``data/reference/*/README.md``
(prose; only a few state a license) — plus a scattered regeneration registry (~28 ``watermark``
commands). Provenance is strong per-file (:class:`watermark.hydrology.model.ProvenancedValue` /
``SourceKind``) but nothing rolls up. This module is the rollup.

One :class:`CatalogEntry` is committed per dataset at ``data/catalog/<scope>/<id>.yaml``,
where ``scope`` mirrors the ``data/`` tree and ``id`` is a stable kebab slug unique across
the catalog. The entry is the **declared** half; the **observed** half (stat + sha256 +
freshness) is computed by ``watermark catalog reconcile`` into ``_observed.yaml`` (issue #625),
and ``watermark catalog check`` (issue #626) gates the two against each other.

This module mirrors :mod:`watermark.hypotheses` / :mod:`watermark.sites` conventions: typed frozen
models, a ``data/`` loader, and a structural validator surfaced by the ``watermark catalog`` CLI.
It imports only :mod:`watermark.config`, reusing that package's ``SourceKind`` vocabulary so the
whole tree speaks one provenance language. The heavier observe/gate logic (reconcile, check,
backfill, render) lands in the sibling issues — this is the schema everything builds on.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

import yaml
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from watermark.config import Settings, get_settings

# The first-level ``data/`` collection an entry catalogs — the catalog dir mirrors the tree.
Scope = Literal[
    "documents",  # raw, immutable source corpus (Git-LFS for large binaries)
    "extracted",  # reviewed structured artifacts mirroring documents/ by collection
    "reference",  # authoritative data from outside sources (EPA ECHO, USGS/NOAA, parcels)
    "derived",  # model outputs computed from the above (hydrology/grid/economics)
    "bundle",  # the published frontend content bundle (feeds + manifest)
    "people",  # curated per-individual profiles
    "hypotheses",  # the (site x hypothesis) evidence cells
    "poi",  # curated point-of-interest profiles
]
# A dataset's review state. ``backfill`` (issue #624) writes new stubs as ``needs-review``;
# a human pass flips them to ``reviewed`` after filling license/access_tier.
EntryStatus = Literal["needs-review", "reviewed", "deprecated"]
# How a dataset comes into being — distinct from ``provenance`` (where its *facts* come from).
ProducerKind = Literal[
    "connector",  # a live public-data connector (ECHO/NWIS/NOAA/EIA via cached_get)
    "derived",  # computed from other catalogued datasets (a model output)
    "vendored",  # downloaded once from an outside source and committed as-is
    "manual",  # hand-authored / hand-transcribed
    "extracted",  # produced by the ingest→extract pipeline from a source document
]
# Who can fetch the dataset's upstream — captures facts (WATERMARK_EIA_API_KEY required, the ECHO
# 300-req/hr throttle) that today live in only a few of the 40 READMEs.
AccessTier = Literal["public", "keyed", "throttled"]
# The per-site axis (see ``watermark.sites``) — the *owner* of a dataset (#778). The three legacy
# kinds plus an explicit-owner grammar so a dataset that belongs to one specific site, basin, or
# state is expressible (not just "Lima vs everyone"):
#   - ``lima-legacy``     — Lima's un-slugged reference-layout files (the reference build's own)
#   - ``slug-scoped``     — a genuine ``{site}`` per-site template; every site has its own copy
#   - ``basin-shared``    — a basin/national output shared across every site
#   - ``site:<slug>``     — owned by one specific site (e.g. Fort Wayne's IDEM permits)
#   - ``basin:<name>``    — owned by one basin (e.g. the Great Miami ECHO inventory)
#   - ``state:<XX>``      — owned by one state (e.g. the Ohio Revised Code)
# A site's bundle/readiness includes a row iff its owner matches the site — see
# ``watermark.catalog.sites.owner_matches``. The reference build still hosts the whole catalog.
_FIXED_SITE_SCOPES = ("lima-legacy", "slug-scoped", "basin-shared")
_OWNER_SITE_SCOPE_RE = re.compile(r"^(?:site|basin):[a-z0-9-]+$|^state:[A-Z]{2}$")


def _validate_site_scope(value: str) -> str:
    """Enforce the ``site_scope`` grammar (#778); semantic checks (real slug/basin/state) live
    in ``watermark catalog check``."""
    if value in _FIXED_SITE_SCOPES or _OWNER_SITE_SCOPE_RE.match(value):
        return value
    raise ValueError(
        f"invalid site_scope {value!r}: expected one of {_FIXED_SITE_SCOPES} or "
        "'site:<slug>' / 'basin:<name>' / 'state:<XX>'"
    )


SiteScope = Annotated[str, AfterValidator(_validate_site_scope)]
# How often the upstream is expected to move — drives staleness with ``Refresh.ttl_days``.
Cadence = Literal["daily", "weekly", "monthly", "quarterly", "annual", "on-demand", "static"]
# Where a dataset's *facts* come from — reused verbatim from the provenance vocabulary so
# the catalog speaks the same language as ProvenancedValue / feeds.Citation.
SourceKind = Literal["document", "connector", "reference", "assumption", "derived"]


class Producer(BaseModel):
    """How a dataset is (re)generated and where it ultimately comes from.

    The de-scattering of the ~28 ``watermark`` regeneration commands: :attr:`command` is the
    invocation that rewrites the dataset (e.g. ``npdes --basin maumee``), :attr:`connector_ref`
    the module that does the pull, :attr:`source` a human upstream label, and
    :attr:`external_url` the canonical upstream page when one exists.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ProducerKind
    command: str | None = None  # the `watermark <cmd>` regenerator, e.g. "npdes --basin maumee"
    connector_ref: str | None = (
        None  # dotted module path, e.g. "watermark.hydrology.connectors.echo"
    )
    source: str  # human upstream label, e.g. "EPA ECHO — cwa_rest_services v2017-10-13"
    external_url: str | None = None


class StorageItem(BaseModel):
    """One committed file belonging to a dataset, addressed relative to ``settings.data_dir``.

    :attr:`sha256` is optional and **pinned** only when integrity matters (e.g. a SWMM deck);
    the live, observed checksum is computed by ``watermark catalog reconcile`` (#625), not here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    relpath: str  # relative to settings.data_dir (e.g. "reference/echo/maumee-wwtp.all-npdes.yaml")
    media_type: str  # MIME, e.g. application/x-yaml, text/csv, application/pdf
    lfs: bool = False  # tracked via Git-LFS (may be an unmaterialized pointer locally)
    sha256: str | None = None  # pinned content hash, when integrity is enforced


class Refresh(BaseModel):
    """A dataset's refresh expectation — the basis for the staleness gate.

    :attr:`cadence` says how often the upstream moves; :attr:`ttl_days` is the staleness
    threshold ``check`` measures the observed file age against (``None`` = never stale, e.g.
    a ``static`` vendored snapshot); :attr:`last_refreshed` is the declared last pull date
    (ISO ``YYYY-MM-DD``), distinct from the observed mtime reconcile records.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    cadence: Cadence
    ttl_days: int | None = None
    last_refreshed: str | None = None  # ISO date, e.g. "2026-06-24"


class CatalogEntry(BaseModel):
    """One dataset in the catalog — the declared, reviewable record of a ``data/`` collection.

    Committed at ``data/catalog/<scope>/<id>.yaml``; :attr:`scope` and :attr:`id` must match
    that path (the loader cross-checks). Reuses the ``SourceKind`` provenance vocabulary
    (:attr:`provenance`) and points :attr:`schema_ref` at the validating Pydantic model
    rather than carrying a column sidecar. Free :attr:`notes` prose is preserved verbatim by
    the generators (``backfill`` / ``render``), so a reviewer's words survive a re-scaffold.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable kebab slug, unique across the catalog
    title: str
    # A per-site title template for `slug-scoped` datasets whose data is the active site's own
    # (#1250): a `str.format` string over the active `SiteProfile` — `{county_state}` ("Allen
    # County, OH"), `{county}` ("Allen County"), `{state}`, `{place}`, `{fips}`. Resolved at
    # bundle-export time by `watermark.catalog.sites.site_title` so a sibling site's catalog names
    # its own county instead of Lima's; `title` stays the resolved reference-build (Lima) string
    # for every non-per-site surface (README render, COMPLETENESS audit). `None` = a fixed title.
    title_template: str | None = None
    scope: Scope
    status: EntryStatus = "needs-review"
    producer: Producer
    # The entries that must be produced before this one can be regenerated (#1020) — each a
    # catalog entry ``id``. This is *process* ordering (the executable-runbook DAG that
    # ``watermark catalog run`` walks), not necessarily byte-level data lineage. Referential
    # integrity + acyclicity are gated by ``watermark catalog check`` (watermark.catalog.dag).
    depends_on: list[str] = Field(default_factory=list)
    license: str | None = None  # e.g. "U.S. Government work (public domain)"
    access_tier: AccessTier = "public"
    site_scope: SiteScope = "basin-shared"
    storage: list[StorageItem] = Field(default_factory=list)
    refresh: Refresh
    provenance: SourceKind = "reference"
    schema_ref: str | None = None  # dotted path to the validating Pydantic model
    tags: list[str] = Field(default_factory=list)
    notes: str = ""  # free prose, preserved verbatim by generators

    @model_validator(mode="after")
    def _check_id(self) -> CatalogEntry:
        """The id must be a non-empty kebab slug (lowercase, digits, hyphens)."""
        if not self.id or not all(c.islower() or c.isdigit() or c == "-" for c in self.id):
            raise ValueError(f"catalog id {self.id!r} must be a kebab slug (a-z0-9-)")
        return self


# --- the committed catalog store (data/catalog/<scope>/<id>.yaml) ---------------------------
def entry_path(entry: CatalogEntry, *, settings: Settings | None = None) -> Path:
    """Where a single dataset entry is committed."""
    settings = settings or get_settings()
    return settings.catalog_dir / entry.scope / f"{entry.id}.yaml"


def load_entries(*, settings: Settings | None = None) -> list[CatalogEntry]:
    """Load every committed catalog entry under ``data/catalog/`` (sorted, stable).

    Each entry is validated against :class:`CatalogEntry` and cross-checked: its ``scope``
    must equal the parent directory and its ``id`` the filename stem, so a misfiled entry is
    a hard error here rather than a silent orphan. ``_observed.yaml`` (the reconcile snapshot,
    issue #625) lives at the catalog root and is skipped.
    """
    settings = settings or get_settings()
    root = settings.catalog_dir
    if not root.exists():
        return []
    entries: list[CatalogEntry] = []
    for path in sorted(root.rglob("*.yaml")):
        if path.parent == root:  # root-level files (e.g. _observed.yaml) are not entries
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entry = CatalogEntry.model_validate(data)
        scope_dir = path.parent.name
        if entry.scope != scope_dir:
            raise ValueError(f"{path}: entry scope {entry.scope!r} != directory {scope_dir!r}")
        if entry.id != path.stem:
            raise ValueError(f"{path}: entry id {entry.id!r} != filename {path.stem!r}")
        entries.append(entry)
    return entries


def get_entry(entry_id: str, *, settings: Settings | None = None) -> CatalogEntry | None:
    """The catalog entry with ``id == entry_id``, or ``None`` if not catalogued."""
    for entry in load_entries(settings=settings):
        if entry.id == entry_id:
            return entry
    return None


def entries_for_scope(scope: Scope, *, settings: Settings | None = None) -> list[CatalogEntry]:
    """The catalogued datasets under one ``scope``."""
    return [e for e in load_entries(settings=settings) if e.scope == scope]


def output_dir_for_command(command: str, *, settings: Settings | None = None) -> Path | None:
    """The single reference output directory the catalog assigns to ``watermark <command>``.

    Resolves the collection dir from the ``storage`` relpaths of every entry whose
    ``producer.command`` verb matches ``command`` — a ``{site}`` segment is dropped, since the
    per-site template shares its collection dir. Returns ``None`` when no entry names the command
    or the entries span more than one collection (ambiguous), so a caller keeps its own default.
    This is what lets the regeneration commands derive their ``--out`` from the catalog (#630)
    instead of hardcoding the path in a third place.

    **Applies only to basin-shared, single-collection commands** (the wired set: ``npdes``,
    ``rsei``, ``gleif``, ``usaspending``, ``interchange``). It is deliberately **not** used to
    drive the output of *per-site* commands (#658): the slug-scoped writers (``eia``, ``grid``,
    ``economics``) persist through the active ``SiteProfile`` relpath, and the per-jurisdiction
    GIS writers (``parcels``, ``zoning``, ``floodzone``) persist through the per-site GIS
    ``schema.reference_dir`` / URLs. Those paths carry the site/jurisdiction the collection dir
    alone can't, so the ``SiteProfile`` stays their single source of truth — collapsing them to
    one catalog dir would pin Lima's path for every site. (``zoning``/``floodzone`` already
    resolve to ``None`` here, since their entries span multiple jurisdiction dirs.)
    """
    settings = settings or get_settings()
    dirs: set[str] = set()
    for entry in load_entries(settings=settings):
        cmd = entry.producer.command
        if not cmd or cmd.split()[0] != command:
            continue
        for item in entry.storage:
            parts = [p for p in PurePosixPath(item.relpath).parent.parts if p != "{site}"]
            dirs.add("/".join(parts))
    if len(dirs) != 1:
        return None
    return settings.data_dir / dirs.pop()


# --- structural validation (the model-layer half of `watermark catalog check`, #626) ------------
class CatalogFinding(BaseModel):
    """One structural problem with the committed catalog (surfaced by ``watermark catalog validate``).

    This is the model-layer lint: invalid/misfiled entries (caught at load) plus duplicate
    ids. The fuller gate — missing declared files, orphaned uncatalogued data, staleness,
    checksum drift — lands in issue #626 once reconcile (#625) supplies the observed snapshot.
    """

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    kind: Literal["duplicate-id", "load-error", "unknown-owner"]
    detail: str


def validate_entries(*, settings: Settings | None = None) -> list[CatalogFinding]:
    """Structurally validate the committed catalog (schema + uniqueness).

    A YAML that fails :class:`CatalogEntry` validation or the scope/id path cross-check
    raises in :func:`load_entries`, so this wraps that as a ``load-error`` finding rather
    than crashing; it then reports any ``id`` committed under more than one path.
    """
    findings: list[CatalogFinding] = []
    try:
        entries = load_entries(settings=settings)
    except Exception as exc:  # surface the load failure as a finding, not a crash
        findings.append(CatalogFinding(entry_id="—", kind="load-error", detail=str(exc)))
        return findings
    seen: dict[str, int] = {}
    for entry in entries:
        seen[entry.id] = seen.get(entry.id, 0) + 1
    for entry_id, n in sorted(seen.items()):
        if n > 1:
            findings.append(
                CatalogFinding(
                    entry_id=entry_id,
                    kind="duplicate-id",
                    detail=f"id committed {n} times (must be unique across the catalog)",
                )
            )

    # An explicit-owner site_scope (#778) must reference a real site / basin / state — the
    # grammar shape is validated by the model; this catches a typo'd or stale owner value.
    from watermark.sites import SITES

    pools: dict[str, set[str]] = {
        "site": set(SITES),
        "basin": {p.basin for p in SITES.values()},
        "state": {p.eia_state for p in SITES.values()},
    }
    for entry in entries:
        kind, _, value = str(entry.site_scope).partition(":")
        pool = pools.get(kind)
        if pool is not None and value not in pool:
            findings.append(
                CatalogFinding(
                    entry_id=entry.id,
                    kind="unknown-owner",
                    detail=f"site_scope {entry.site_scope!r} names an unknown {kind} "
                    f"(not in the watermark.sites registry)",
                )
            )
    return findings
