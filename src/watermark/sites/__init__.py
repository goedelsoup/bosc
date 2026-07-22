"""The BOSC network — the Python registry of watershed-point site profiles.

The data-tier peer of ``web/packages/core/src/sites.ts`` (Epic #308 / #323, Track 1): one
:class:`SiteProfile` per watershed point, holding every value that is specific to *that*
site. Lima is the live reference build; basin sites (Fort Wayne, Defiance, …) come online
incrementally and are populated by their onboarding issues (#235-#238), not here.

The active site is selected by ``WATERMARK_SITE`` (``watermark.config.Settings.site``, default
``"lima"``). :class:`~watermark.config.Settings` resolves the profile's *config knobs*
(the fields in :data:`PROFILE_SETTINGS_FIELDS`) into itself, so the existing ``settings.X``
consumers are unchanged; the deeper hydrology/grid/rsei constants are read by their modules
via :func:`active_profile`.

Per-**basin** data (the Maumee HUC-8 set, the curated mainstem gages) is shared across all
Maumee sites and stays in its modules; a profile only names its ``basin``.

This module imports nothing from :mod:`watermark.config` — ``active_profile`` duck-types the
``.site`` accessor — so the dependency runs one way (``config → sites``). The GIS field-map
*models* come from :mod:`watermark.connectors.gis_schema` (a pure-pydantic leaf under the neutral
connectors package, deliberately *not* ``watermark.hydrology.connectors``, which would close a
``config → sites → connectors → config`` loop); the schema *instances* live here with the
profiles, where site-specific values belong.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict

from watermark.sites._gis_schemas import (
    ALLEN_IN_PARCEL_SCHEMA as ALLEN_IN_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    FINDLAY_ZONING_SCHEMA as FINDLAY_ZONING_SCHEMA,
)
from watermark.sites._gis_schemas import (
    FORT_WAYNE_ZONING_SCHEMA as FORT_WAYNE_ZONING_SCHEMA,
)
from watermark.sites._gis_schemas import (
    LIMA_FLOOD_SCHEMA as LIMA_FLOOD_SCHEMA,
)
from watermark.sites._gis_schemas import (
    LIMA_PARCEL_SCHEMA as LIMA_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    LIMA_ZONING_SCHEMA as LIMA_ZONING_SCHEMA,
)
from watermark.sites._gis_schemas import (
    LUCAS_AREIS_PARCEL_SCHEMA as LUCAS_AREIS_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    LUCAS_ZONING_SCHEMA as LUCAS_ZONING_SCHEMA,
)
from watermark.sites._gis_schemas import (
    MIAMI_PARCEL_SCHEMA as MIAMI_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    NATIONAL_NFHL_FLOOD_SCHEMA as NATIONAL_NFHL_FLOOD_SCHEMA,
)
from watermark.sites._gis_schemas import (
    OHIO_STATEWIDE_PARCEL_SCHEMA as OHIO_STATEWIDE_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    PUTNAM_PARCEL_SCHEMA as PUTNAM_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    RICHLAND_PARCEL_SCHEMA as RICHLAND_PARCEL_SCHEMA,
)
from watermark.sites._gis_schemas import (
    VAN_WERT_PARCEL_SCHEMA as VAN_WERT_PARCEL_SCHEMA,
)
from watermark.sites._model import (
    PROFILE_SETTINGS_FIELDS as PROFILE_SETTINGS_FIELDS,
)
from watermark.sites._model import (
    YAML_BACKED_PROFILE_FIELDS as YAML_BACKED_PROFILE_FIELDS,
)
from watermark.sites._model import (
    CoolingModelType as CoolingModelType,
)
from watermark.sites._model import (
    DcEndUse as DcEndUse,
)
from watermark.sites._model import (
    FacilityLifecycle as FacilityLifecycle,
)
from watermark.sites._model import (
    ItLoadGrounding as ItLoadGrounding,
)
from watermark.sites._model import (
    SiteEntry as SiteEntry,
)
from watermark.sites._model import (
    SiteFacility as SiteFacility,
)
from watermark.sites._model import (
    SiteProfile as SiteProfile,
)
from watermark.sites._model import (
    _get_identity as _get_identity,
)
from watermark.sites._profiles import (
    PER_SITE_OUTPUT_FIELDS as PER_SITE_OUTPUT_FIELDS,
)
from watermark.sites._profiles import (
    SITES as SITES,
)
from watermark.sites._scope import (
    WHOLE_TREE as WHOLE_TREE,
)
from watermark.sites._scope import (
    CorpusScope as CorpusScope,
)
from watermark.sites._scope import (
    CorpusScopeArg as CorpusScopeArg,
)

if TYPE_CHECKING:
    from watermark.config import Settings


def get_profile(slug: str) -> SiteProfile:
    """The :class:`SiteProfile` for ``slug``; raises ``KeyError`` if unknown."""
    return SITES[slug]


def active_profile(settings: Settings) -> SiteProfile:
    """The active site's profile, keyed by ``settings.site``."""
    return SITES[settings.site]


# The reference build (Lima) keeps the flat / un-slugged committed layout for its curated stores;
# every other site's copy lives under a ``<slug>/`` subdir — the same convention the catalog's
# ``site_scope`` axis encodes (:data:`watermark.catalog.sites._LEGACY_SITE`).
_REFERENCE_LAYOUT_SITE = "lima"


def is_reference_site(slug: str) -> bool:
    """Whether ``slug`` is the reference build (Lima).

    The reference build keeps the flat committed layout *and* hosts the network-global feeds
    (the cross-site hypothesis matrix, the whole-data-tier catalog) that the root pages read —
    a sibling site's bundle carries only its own slice (#762). Use this to keep the reference
    bundle byte-identical while narrowing siblings.
    """
    return slug == _REFERENCE_LAYOUT_SITE


def _peer_scope_prefixes(slug: str) -> tuple[str, ...]:
    """Every *other* registered site's own inclusion prefixes — the subtrees the reference build
    subtracts so it stops swallowing a peer's slug-scoped records (#1505).

    A peer's prefixes are its explicit ``corpus_relpaths`` or, when unset, its own ``<slug>``.
    Another whole-tree/reference site (``corpus_relpaths`` ``None``) contributes nothing — you
    cannot subtract "everything" — but only Lima is the reference build today.
    """
    prefixes: set[str] = set()
    for other, prof in SITES.items():
        if other == slug:
            continue
        if prof.corpus_relpaths is not None:
            prefixes.update(prof.corpus_relpaths)
        elif not is_reference_site(other):
            prefixes.add(other)
    return tuple(sorted(prefixes))


def effective_corpus_scope(profile: SiteProfile) -> CorpusScope:
    """The corpus scope to actually read for a site (#762/#780/#1505) — the extracted-tree region
    its bundle/derivations are bounded to.

    An explicit ``corpus_relpaths`` always wins (inclusion-only). Otherwise the default is
    **derived from the slug, not inherited from Lima**: the reference build (Lima) reads the whole
    tree **minus every registered peer's own scope** (:func:`_peer_scope_prefixes`), so its
    record/timeline/entities domain stops swallowing a sibling's slug-scoped records — a Piqua
    NPDES permit under ``oepa/troy-piqua/`` or a Fort Wayne §401 under ``idem/fort-wayne/`` no
    longer renders inside Lima's Allen-County record (#1505). Every other site defaults to its own
    ``<slug>/`` collection (the #780 safe default — a freshly registered site reads *its own*
    corpus or nothing, never silently inheriting Lima's record); a site whose corpus also lives
    under a jurisdiction prefix (Fort Wayne's ``idem/fort-wayne``) sets the tuple explicitly.
    """
    if profile.corpus_relpaths is not None:
        return CorpusScope(include=profile.corpus_relpaths)
    if is_reference_site(profile.slug):
        return CorpusScope(include=None, exclude=_peer_scope_prefixes(profile.slug))
    return CorpusScope(include=(profile.slug,))


def site_scoped_path(path: Path, slug: str, *, is_dir: bool) -> Path:
    """A curated store's per-site location (#762).

    Lima (the reference build) keeps the flat committed ``path``; every other site reads a
    ``<slug>/`` subdir — a directory becomes ``path/<slug>``, a file becomes
    ``path.parent/<slug>/path.name``. So a non-Lima site reads *its own* committed people / POIs /
    candidates / LEI / exhibits, or an absent/empty one, instead of inheriting Lima's.
    """
    if slug == _REFERENCE_LAYOUT_SITE:
        return path
    return path / slug if is_dir else path.parent / slug / path.name


def output_path_collisions(slug: str) -> dict[str, list[str]]:
    """Other registered sites that share ``slug``'s per-site output relpaths.

    Returns ``{field: [other_slug, …]}`` for each :data:`PER_SITE_OUTPUT_FIELDS` value
    another site also uses — empty when ``slug``'s outputs are safely unique.
    """
    prof = SITES[slug]
    clashes: dict[str, list[str]] = {}
    for field in PER_SITE_OUTPUT_FIELDS:
        value = getattr(prof, field)
        if value is None:
            continue  # optional output (e.g. a facility-less site's demand_pressure_relpath) — no destination to clash
        others = [s for s, p in SITES.items() if s != slug and getattr(p, field) == value]
        if others:
            clashes[field] = others
    return clashes


# --- Authoring tooling (scaffold a new profile + lint a draft) ------------------------------
# Geometry inputs a new site supplies itself (not connector outputs, so not in
# PER_SITE_OUTPUT_FIELDS, but still slug-scoped by the scaffold).
_GEOMETRY_RELPATH_FIELDS = ("parcels_relpath", "footprint_relpath")


def _slug_scope(relpath: str, slug: str) -> str:
    """Insert ``slug`` as a subdir before the filename (Lima's path -> a new site's)."""
    p = PurePosixPath(relpath)
    return str(p.parent / slug / p.name)


def _type_placeholder(annotation: object) -> str:
    """A constructible-but-obviously-empty literal for a field's type (scaffold TODO)."""
    origin = get_origin(annotation)
    if annotation is str:
        return '"TODO"'
    if annotation is bool:
        return "False"
    if annotation is int:
        return "0"
    if annotation is float:
        return "0.0"
    if origin is list:
        return '["TODO"]'
    if origin is tuple:
        n = len([a for a in get_args(annotation) if a is not Ellipsis])
        return "(" + ", ".join(["0.0"] * n) + ")"
    if origin is dict:
        return "{}"
    if origin is Literal:
        return repr(get_args(annotation)[0])  # first allowed value (constructible)
    return "None"


def scaffold_profile_src(slug: str, *, basin: str = "maumee") -> str:
    """A paste-ready ``SiteProfile(...)`` stub for a new site (the #326 authoring aid).

    Identity + the per-site output relpaths are filled (the relpaths pre-slug-scoped, so the
    stub is collision-safe by construction); every other field is a typed ``TODO`` placeholder
    to replace from a cited source (see ``docs/onboarding.md``). Then ``watermark sites check`` flags
    anything still unfilled.

    Note: YAML-backed fields (``place``, ``receiving_water_name``, ``map_view_*``) are omitted
    from the stub — add the site to ``data/sites.yaml`` first and run ``watermark sites sync`` so
    those fields are filled automatically at construction time (#1027).
    """
    from watermark.sites._model import YAML_BACKED_PROFILE_FIELDS

    lima = SITES["lima"]
    lines: list[str] = [f'    "{slug}": SiteProfile(']
    for name, field in SiteProfile.model_fields.items():
        comment = ""
        if name == "slug":
            value = repr(slug)
        elif name in YAML_BACKED_PROFILE_FIELDS:
            continue  # filled from data/sites.yaml — register the site there first
        elif name == "basin":
            value = repr(basin)
            comment = "  # TODO: confirm the basin"
        elif name in PER_SITE_OUTPUT_FIELDS:
            value = repr(_slug_scope(getattr(lima, name), slug))  # pre-slug-scoped, collision-safe
        elif name in _GEOMETRY_RELPATH_FIELDS:
            stem = "reference" if name == "parcels_relpath" else "extracted"
            value = repr(f"{stem}/{slug}/{PurePosixPath(getattr(lima, name)).name}")
            comment = "  # TODO: commit the site's own geometry here"
        elif not field.is_required():  # optional (e.g. facility) — absence is a valid state
            value = repr(field.get_default())
            comment = "  # optional (set only if the site has a documented facility)"
        else:
            value = _type_placeholder(field.annotation)
            comment = "  # TODO"
        lines.append(f"        {name}={value},{comment}")
    lines.append("    ),")
    header = (
        f"# Paste into watermark.sites.SITES (the key must equal slug={slug!r}). Replace every TODO\n"
        "# with this site's value from a cited source — see the field guide in\n"
        "# docs/onboarding.md. The output relpaths are pre-slug-scoped (collision-safe);\n"
        "# Add the site to data/sites.yaml first (identity fields are filled from there).\n"
        f"# run `watermark onboard {slug} --check` to find anything still unfilled.\n"
    )
    return header + "\n".join(lines) + "\n"


class ReadinessFinding(BaseModel):
    """One issue a draft profile lints up before a live onboard run."""

    model_config = ConfigDict(extra="forbid")

    field: str
    kind: Literal["placeholder", "matches-lima"]
    detail: str


def _is_placeholder(value: object) -> bool:
    """True for the scaffold's unfilled sentinels (TODO / zeros / empties)."""
    if isinstance(value, str):
        return value == "" or "TODO" in value
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, (list, tuple)):
        return len(value) == 0 or any(_is_placeholder(v) for v in value)
    if isinstance(value, dict):
        return len(value) == 0
    return value is None


def profile_readiness(slug: str) -> list[ReadinessFinding]:
    """Lint a non-Lima draft profile before onboarding: unfilled placeholders + copied values.

    Flags any field still a scaffold placeholder (``placeholder`` — must fix) and any field
    still equal to Lima's value (``matches-lima`` — verify; some, e.g. an Ohio site's
    ``eia_state``, legitimately match). Empty for Lima itself.

    YAML-backed fields (``place``, ``receiving_water_name``, ``map_view_*``) are excluded —
    they are managed in ``data/sites.yaml`` and filled at construction time (#1027).
    """
    from watermark.sites._model import YAML_BACKED_PROFILE_FIELDS

    if slug == "lima":
        return []
    prof, lima = SITES[slug], SITES["lima"]
    findings: list[ReadinessFinding] = []
    for name, field in SiteProfile.model_fields.items():
        if name == "slug" or name in YAML_BACKED_PROFILE_FIELDS:
            continue
        value = getattr(prof, name)
        # An optional field left at its default (e.g. facilities=()) is a deliberate absence,
        # not an unfilled gap — don't flag it.
        if not field.is_required() and value == field.get_default():
            continue
        if _is_placeholder(value):
            findings.append(
                ReadinessFinding(
                    field=name, kind="placeholder", detail=f"still unfilled: {value!r}"
                )
            )
        elif value == getattr(lima, name):
            findings.append(
                ReadinessFinding(
                    field=name, kind="matches-lima", detail=f"== Lima's value: {value!r}"
                )
            )
    return findings


def grid_knobs_complete(slug: str) -> list[str]:
    """The grid-identity knobs still incomplete for a site — empty when the identity is whole.

    The grid-knob readiness check (B3/#1639): a site can be backdrop-live yet carry an empty
    grid identity (serving utility / RTO / LMP zone unset). This reports the gaps so the grid
    backdrop **locks and asks for the source** rather than rendering an empty/placeholder
    identity — the repo spine, never fake a value to look complete. A knob is incomplete when
    it is unset/zero or still an ``[open]`` pending note.
    """
    prof = SITES[slug]
    gaps: list[str] = []
    if prof.eia861_utility_number == 0:
        gaps.append("eia861_utility_number")
    cite = prof.serving_utility_citation
    if not cite or cite.startswith("[open]"):
        gaps.append("serving_utility_citation")
    # LMP is complete via EITHER a pinned PJM pnode (the live connector) OR a non-zero
    # placeholder carrying a real (non-``[open]``) citation.
    if not prof.lmp_pnode_id and (
        prof.lmp_usd_mwh == 0.0 or prof.lmp_citation.startswith("[open]")
    ):
        gaps.append("lmp")
    return gaps


def grid_identity_todo_violations() -> list[str]:
    """Registered profiles whose grid-identity citations still carry a raw ``TODO`` (B3/#1639).

    The registry-level "reject raw TODO" gate — enforced by ``watermark sites check`` (and so
    CI). A raw ``TODO`` in ``serving_utility_citation`` / ``lmp_citation`` would render verbatim
    on the grid backdrop; an honest ``[open] …`` pending note is required instead. This gates
    only what is **registered** in :data:`SITES` — a scaffolded DRAFT profile may legitimately
    carry ``TODO`` placeholders while it is being authored (``profile_readiness`` lints those).
    """
    violations: list[str] = []
    for slug, prof in SITES.items():
        for field in ("serving_utility_citation", "lmp_citation"):
            value = getattr(prof, field)
            if isinstance(value, str) and "TODO" in value:
                violations.append(f"{slug}.{field} is a raw 'TODO' placeholder")
    return violations
