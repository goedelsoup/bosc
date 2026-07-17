"""Export the committed corpus into the typed content bundle under ``data/site/bundles/<slug>/``.

The site's data tier (issue #53, Tier 1): :func:`export_bundle` emits the versioned,
schema-validated JSON feeds the Astro/DeckGL frontend reads at build time, loading the
corpus through the shared loaders (``load_corpus``, ``build_timeline``,
``build_entity_graph``, ``load_people``, ``load_pois``, …) and the per-section builders
in this package (``records``, ``economics``, ``gismap``, …).

The output is **per network site** (#724/#727): each site's feeds land under
``data/site/bundles/<slug>/`` (the active site is ``settings.site``, from the global
``watermark --site <slug>`` flag / ``WATERMARK_SITE``), so the network's sites never clobber each
other. The committed, site-agnostic contract (``schemas/``, README, example manifest) stays
shared at ``data/site/bundle/``.

Layout written under ``out_dir`` (default ``data/site/bundles/<slug>``):

* ``manifest.json`` — bundle/contract version, ``generated_at``, and the feed index.
* ``schemas/<feed>.schema.json`` — one JSON Schema per feed, generated from the
  :mod:`watermark.site.feeds` models (serialization mode), so schema and code never drift.
* ``feeds/<feed>.json`` (or ``.ndjson`` for a large list) and ``feeds/geo/<feed>.geojson``.

The contract itself (README, schemas, an example manifest) is committed; the generated
``manifest.json`` + ``feeds/`` are regenerable and git-ignored (see the bundle README).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel

from watermark.air.aermod.dispersion import DispersionResult, naaqs_for, run_calibration_dispersion
from watermark.air.aermod.engine import run as run_aermod
from watermark.air.aermod.model import AveragePeriod, ReceptorGrid
from watermark.air.aermod.screening import build_screening_deck
from watermark.air.model import Pollutant
from watermark.air.scenario import AirScenarioResult
from watermark.candidates import (
    load_cloud_consumer_candidates,
    load_defense_contractors,
    load_defense_scan,
)
from watermark.civic.summarize import load_committed_summaries
from watermark.config import Settings, get_settings
from watermark.economics.baseline import load_baseline as load_econ_baseline
from watermark.economics.energy import (
    derive_energy_burden,
    load_consumer_energy,
    load_demand_pressure,
)
from watermark.gleif import load_inventory as load_lei_inventory
from watermark.hydrology.hydrograph_routing import build_routed_hydrograph
from watermark.hydrology.model import ScenarioResult
from watermark.hypotheses import HYPOTHESES, Hypothesis, HypothesisAssessment, load_assessments
from watermark.logging import get_logger
from watermark.network import build_basin_network
from watermark.people import load_people
from watermark.pipeline.corpus import load_corpus
from watermark.pipeline.entities import build_entity_graph
from watermark.pipeline.timeline import build_timeline
from watermark.poi import load_pois
from watermark.rsei import load_inventory as load_rsei_inventory
from watermark.site import candidates as candidates_mod
from watermark.site import catalog as catalog_mod
from watermark.site import concepts as concepts_mod
from watermark.site import contacts as contacts_mod
from watermark.site import documents as documents_mod
from watermark.site import economics as economics_mod
from watermark.site import exhibits as exhibits_mod
from watermark.site import gismap as gismap_mod
from watermark.site import gleif as gleif_mod
from watermark.site import graph as graph_mod
from watermark.site import greenops as greenops_mod
from watermark.site import leads as leads_mod
from watermark.site import meetings as meetings_mod
from watermark.site import people as people_mod
from watermark.site import places as places_mod
from watermark.site import records as records_mod
from watermark.site import rsei as rsei_mod
from watermark.site.catalog_index import build_catalog_index
from watermark.site.embeddings import build_ask_embeddings, build_passage_embeddings
from watermark.site.facts import build_facts
from watermark.site.feeds import (
    CONTRACT_VERSION,
    AskEmbeddingEntry,
    CandidateItem,
    CatalogItem,
    Citation,
    ConceptItem,
    ContactItem,
    DispersionField,
    DispersionGeoRef,
    DispersionGrid,
    DocumentCollectionItem,
    EntityNode,
    ExhibitItem,
    FactItem,
    FeedKind,
    FeedRef,
    GeoFeatureCollection,
    LeadItem,
    Manifest,
    MeetingItem,
    OpenQuestionItem,
    PassageEmbeddingEntry,
    PassageItem,
    PersonItem,
    PlaceItem,
    ReachLine,
    ReachNetwork,
    RecordItem,
    RelationshipEdge,
    SeasonalField,
    SeasonalMonthCell,
    SiteReadiness,
    TimelineEntry,
)
from watermark.site.open_questions import build_open_questions
from watermark.site.passages import load_committed_passages
from watermark.site.readiness import compute_readiness
from watermark.sites import (
    active_profile,
    effective_corpus_scope,
    is_reference_site,
    site_scoped_path,
)

log = get_logger(__name__)

# The data generation's version — bump on a regeneration whose data shape/content
# materially changes (distinct from CONTRACT_VERSION, which tracks the schemas).
BUNDLE_VERSION = "1.0.0"
_DIALECT = "https://json-schema.org/draft/2020-12/schema"
# A collection longer than this is written as NDJSON (one row per line) per the #58
# "NDJSON for large lists" contract; shorter lists stay a single JSON array.
_NDJSON_THRESHOLD = 500


@dataclass
class _Feed:
    """One assembled feed, ready to write — its data, its schema, and its manifest row."""

    name: str
    path: str  # relative to the bundle root
    kind: FeedKind
    media_type: str
    schema_file: str  # relative to the bundle root, e.g. schemas/records.schema.json
    schema: dict[str, Any]
    payload: str
    count: int


@dataclass
class BundleResult:
    """Summary of a bundle export — where it landed and what it holds."""

    out_dir: Path
    feeds: list[FeedRef] = field(default_factory=list)
    row_total: int = 0
    # yidam corpus mirror (#1562): the mirror regenerated at the tail of the export, if any.
    mirror_nodes: int = 0
    mirror_graph_issues: int = 0
    mirror_reports_dir: Path | None = None

    @property
    def feed_count(self) -> int:
        return len(self.feeds)


def _object_schema(model: type[BaseModel], title: str) -> dict[str, Any]:
    """The serialization JSON Schema for one model (computed fields + aliases included)."""
    schema = model.model_json_schema(mode="serialization", by_alias=True)
    schema["$schema"] = _DIALECT
    schema.setdefault("title", title)
    return schema


def _array_schema(item_model: type[BaseModel], title: str) -> dict[str, Any]:
    """An ``array``-of-``item_model`` schema, with the model's ``$defs`` hoisted so its
    internal ``#/$defs/...`` references still resolve once nested under ``items``."""
    item = item_model.model_json_schema(mode="serialization", by_alias=True)
    defs = item.pop("$defs", None)
    wrapper: dict[str, Any] = {
        "$schema": _DIALECT,
        "title": title,
        "type": "array",
        "items": item,
    }
    if defs is not None:
        wrapper["$defs"] = defs
    return wrapper


def _dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _collection_feed(name: str, item_model: type[BaseModel], rows: Sequence[BaseModel]) -> _Feed:
    """Assemble a list feed — JSON array, or NDJSON when it crosses the size threshold."""
    dumped = [r.model_dump(mode="json", by_alias=True) for r in rows]
    schema_file = f"schemas/{name}.schema.json"
    if len(dumped) > _NDJSON_THRESHOLD:
        payload = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dumped)
        return _Feed(
            name=name,
            path=f"feeds/{name}.ndjson",
            kind="collection",
            media_type="application/x-ndjson",
            schema_file=schema_file,
            schema=_object_schema(item_model, f"{name} row"),
            payload=payload,
            count=len(dumped),
        )
    return _Feed(
        name=name,
        path=f"feeds/{name}.json",
        kind="collection",
        media_type="application/json",
        schema_file=schema_file,
        schema=_array_schema(item_model, f"{name} feed"),
        payload=_dump_json(dumped),
        count=len(dumped),
    )


def _retrieval_collection_feed(
    name: str, item_model: type[BaseModel], rows: Sequence[BaseModel]
) -> _Feed:
    """A collection feed whose *schema form* is independent of row count (#1589).

    `_collection_feed` picks the array schema below the NDJSON threshold and the per-row object
    schema above it — fine for a corpus-shaped feed whose volume is stable, but the retrieval-index
    feeds (`passages`, the embedding companions) swing across that threshold with the environment
    (LFS-resolved PDFs vs. pointers, `--no-embeddings`), which would flip the committed schema and
    trip the drift guard. This always emits the per-row object schema + compact NDJSON payload (also
    the right encoding for large float-vector rows — no `indent=2` blow-up), so the schema is
    deterministic at 0 rows or 10k.
    """
    dumped = [r.model_dump(mode="json", by_alias=True) for r in rows]
    payload = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dumped)
    return _Feed(
        name=name,
        path=f"feeds/{name}.ndjson",
        kind="collection",
        media_type="application/x-ndjson",
        schema_file=f"schemas/{name}.schema.json",
        schema=_object_schema(item_model, f"{name} row"),
        payload=payload,
        count=len(dumped),
    )


def _object_feed(name: str, model: BaseModel) -> _Feed:
    """Assemble a single-object feed (an inventory/baseline already carrying provenance)."""
    return _Feed(
        name=name,
        path=f"feeds/{name}.json",
        kind="object",
        media_type="application/json",
        schema_file=f"schemas/{name}.schema.json",
        schema=_object_schema(type(model), f"{name} feed"),
        payload=_dump_json(model.model_dump(mode="json", by_alias=True)),
        count=1,
    )


def _geo_feed(fc: GeoFeatureCollection) -> _Feed:
    """Assemble one typed GeoJSON layer feed; all geo feeds share one schema file."""
    return _Feed(
        name=f"geo/{fc.feed}",
        path=f"feeds/geo/{fc.feed}.geojson",
        kind="geojson",
        media_type="application/geo+json",
        schema_file="schemas/geo.schema.json",
        schema=_object_schema(GeoFeatureCollection, "GeoJSON layer feed"),
        payload=_dump_json(fc.model_dump(mode="json", by_alias=True)),
        count=len(fc.features),
    )


def _scoped_assessments(settings: Settings) -> list[HypothesisAssessment]:
    """The (site x hypothesis) evidence cells for this bundle (#762).

    The cells form one cross-site matrix (``data/hypotheses/<hid>/<site>.yaml``). The reference
    build (Lima, the network host the root ``/research/hypotheses`` matrix reads) carries the
    whole matrix; a sibling site's bundle carries only its own rows — strictly its own data.
    """
    cells = load_assessments(settings=settings)
    if is_reference_site(settings.site):
        return cells
    return [c for c in cells if c.site == settings.site]


def _load_scenarios(settings: Settings) -> list[ScenarioResult]:
    """Load the committed hydrology scenario results (``data/scenarios/*.scenario.yaml``).

    Per-site (#762): the committed scenarios are Lima's (the Ottawa-River loop); a sibling
    site reads its own ``scenarios/<slug>/`` (absent today → an empty feed, not Lima's).
    """
    sdir = site_scoped_path(settings.data_dir / "scenarios", settings.site, is_dir=True)
    if not sdir.is_dir():
        return []
    out: list[ScenarioResult] = []
    for path in sorted(sdir.glob("*.scenario.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            out.append(ScenarioResult.model_validate(data))
        except Exception as exc:  # a malformed scenario must not kill the whole export
            log.warning("bundle.scenario.bad", path=str(path), error=str(exc).splitlines()[0])
    return out


def _load_air_scenarios(settings: Settings) -> list[AirScenarioResult]:
    """Load the committed air emissions scenarios (Tier-0, #1177/#1181).

    ``watermark.air.scenario.write_scenario`` writes ``<slug>.air-<name>.scenario.yaml`` into
    ``scenarios_dir`` (slug-prefixed, so a sibling never clobbers Lima). A site with no committed
    air scenarios yields an empty list → the feed carries zero rows and the air section locks.
    """
    out: list[AirScenarioResult] = []
    for path in sorted(settings.scenarios_dir.glob(f"{settings.site}.air-*.scenario.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            out.append(AirScenarioResult.model_validate(data))
        except Exception as exc:  # a malformed scenario must not kill the whole export
            log.warning("bundle.air_scenario.bad", path=str(path), error=str(exc).splitlines()[0])
    return out


# The two capped / short-term-critical criteria pollutants modeled by both air-dispersion feeds:
# NOx (1-hr + annual NO2 NAAQS) and CO (1-hr + 8-hr). Averaging periods line up with the operative
# standards. The screening receptor grid: ±2.5 km at 100 m spacing (a 51x51 single-source grid).
_DISPERSION_SPEC: list[tuple[Pollutant, tuple[AveragePeriod, ...]]] = [
    ("NOx", ("1", "ANNUAL")),
    ("CO", ("1", "8")),
]
_FIELD_GRID_HALF_EXTENT_M = 2500.0
_FIELD_GRID_SPACING_M = 100.0


def _air_dispersion(settings: Settings) -> list[DispersionResult] | None:
    """The Tier-1 AERMOD dispersion screen for the active site (#1178/#1182), or ``None``.

    Facility- and permit-gated: a site with no documented facility, or no wired air permit
    (``SiteFacility.air_permit_relpath is None``), has no fleet/rates to model → ``None`` (feed
    skipped, section locks). Each run is the event-anchored calibration (permit load-point rate,
    cited to the captured dispatch event). When the AERMOD binary/met is absent the runs carry
    ``available=False`` with empty screens — the deck + NAAQS basis are real, no concentration is
    fabricated.
    """
    fac = active_profile(settings).facility
    if fac is None or fac.air_permit_relpath is None:
        return None
    runs: list[DispersionResult] = []
    for pollutant, periods in _DISPERSION_SPEC:
        dr = run_calibration_dispersion(
            pollutant=pollutant, averaging_periods=periods, settings=settings
        )
        if dr is not None:
            runs.append(dr)
    return runs or None


def _grid_geo_ref(grid: ReceptorGrid, *, lon0: float, lat0: float) -> DispersionGeoRef:
    """Project the metre receptor grid onto WGS84 about the source at ``(lon0, lat0)``.

    A local flat-earth approximation (adequate for a ±2.5 km screening grid): metres → degrees at
    ~111,320 m/°lat and ``111,320·cos(lat)`` m/°lon. Inherits the field's ``assumption`` provenance
    (the source anchor is the site's map centre, not a surveyed stack location).
    """
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = m_per_deg_lat * math.cos(math.radians(lat0))
    x_max = grid.x0_m + (grid.nx - 1) * grid.dx_m
    y_max = grid.y0_m + (grid.ny - 1) * grid.dy_m
    return DispersionGeoRef(
        source_lon=lon0,
        source_lat=lat0,
        sw_lon=lon0 + grid.x0_m / m_per_deg_lon,
        sw_lat=lat0 + grid.y0_m / m_per_deg_lat,
        ne_lon=lon0 + x_max / m_per_deg_lon,
        ne_lat=lat0 + y_max / m_per_deg_lat,
    )


def _dispersion_field(settings: Settings) -> list[DispersionField] | None:
    """The gridded AERMOD concentration surfaces (one per pollutant) for the deck.gl field viz.

    Reference-site gated like ``routed-hydrograph`` (the field is a single-site screening artifact,
    not something a thin peer inherits). For each pollutant it builds the same screening deck as the
    ``air-dispersion`` screen, runs the (absent-degrading) engine, and reshapes the receptor grid
    into per-averaging-period ``values[]`` via :meth:`DispersionField.from_receptors`. When the
    binary/met is absent the runs carry ``available=False`` with empty ``values`` — the grid,
    ``geo_ref`` and NAAQS lines are real, no concentration is fabricated. Every value is
    ``assumption``-provenanced (the permit redacts the genset stack as CBI).
    """
    if not is_reference_site(settings.site):
        return None
    profile = active_profile(settings)
    if profile.facility is None:
        return None
    fields: list[DispersionField] = []
    for pollutant, periods in _DISPERSION_SPEC:
        built = build_screening_deck(
            pollutant=pollutant,
            averaging_periods=periods,
            grid_half_extent_m=_FIELD_GRID_HALF_EXTENT_M,
            grid_spacing_m=_FIELD_GRID_SPACING_M,
            settings=settings,
        )
        if built is None:
            continue
        inp_text, plotfiles = built
        result = run_aermod(
            inp_text, met_files={}, plotfiles=plotfiles, pollutant=pollutant, settings=settings
        )
        rgrid = ReceptorGrid.centered(
            half_extent_m=_FIELD_GRID_HALF_EXTENT_M, spacing_m=_FIELD_GRID_SPACING_M
        )
        per_period: dict[str, list[tuple[float, float, float]]] = {str(p): [] for p in periods}
        for rec in result.receptors:
            per_period.setdefault(rec.ave_period, []).append((rec.x_m, rec.y_m, rec.conc))
        naaqs = {
            str(p): (
                std.standard_ug_m3
                if (std := naaqs_for(pollutant, str(p), settings=settings))
                else None
            )
            for p in periods
        }
        available = result.available and bool(result.receptors)
        fields.append(
            DispersionField.from_receptors(
                site=settings.site,
                pollutant=pollutant,
                grid=DispersionGrid(
                    nx=rgrid.nx,
                    ny=rgrid.ny,
                    dx_m=rgrid.dx_m,
                    dy_m=rgrid.dy_m,
                    x0_m=rgrid.x0_m,
                    y0_m=rgrid.y0_m,
                ),
                geo_ref=_grid_geo_ref(rgrid, lon0=profile.map_view_lon, lat0=profile.map_view_lat),
                period_receptors=per_period,
                naaqs=naaqs,
                available=available,
                unit=result.unit or "ug/m3",
                engine_version=result.engine_version,
                caveats=[
                    "Screening field: a single modeled genset source, flat terrain + canned met, "
                    "no monitored background. The genset stack geometry is a CBI-redacted "
                    "assumption, so every concentration is [inference], never [verified].",
                ],
                note=result.note
                or (
                    "AERMOD field gridded from the screening deck."
                    if available
                    else "Deck + NAAQS lines resolved; AERMOD engine/met unavailable, so the field "
                    "carries geometry only (degraded, not fabricated)."
                ),
            )
        )
    return fields or None


def _seasonal_field(settings: Settings) -> SeasonalField | None:
    """The seasonal net-atmospheric-withdrawal climograph — the deck.gl water field (epic #1237 / #1236).

    Reference-site gated like ``routed-hydrograph`` / ``air-dispersion-field``: the buildout scenario
    and the Ottawa low flows are Lima's, not a peer's. Reads the committed buildout scenario's
    consumptive draw + cooling basis, screens it month-by-month via
    :func:`watermark.hydrology.scenario.evaluate_seasonal`, and projects the result into the field
    feed. The field scalar (net atmospheric withdrawal, ET0 - precip) is the cited climate normals
    (``reference``); the per-month low-flow ``multiple`` rests on the *modeled* draw and is
    ``[inference]``. Degrades to ``available=False`` with empty ``months`` (thresholds still resolve)
    when the buildout scenario is missing or the climate/ET normals are absent — nothing fabricated.
    """
    if not is_reference_site(settings.site):
        return None
    build = next((s for s in _load_scenarios(settings) if s.scenario.name == "buildout"), None)
    if build is None:
        return None
    from watermark.hydrology import scenario as hydro_scenario

    sw = hydro_scenario.evaluate_seasonal(
        build.consumptive_loss.value, settings=settings, basis=build.scenario.basis
    )
    caveats = [
        "The climograph (net atmospheric withdrawal = reference ET0 - precip) is the cited NASA "
        "POWER normals + FAO-56 ET0. The per-month low-flow multiple screens the *modeled* buildout "
        "consumptive draw against the cited seasonal low flow (30Q10 summer / 7Q10 annual), so that "
        "read is [inference] — not a measured withdrawal.",
    ]
    if sw is None or not sw.months:
        return SeasonalField(
            site=settings.site,
            scenario="buildout",
            available=False,
            caveats=caveats,
            note="Buildout scenario resolved; climate/ET normals unavailable, so the climograph "
            "carries no monthly surface (degraded, not fabricated).",
        )
    return SeasonalField(
        site=settings.site,
        scenario=sw.scenario,
        cooling_model=sw.cooling_model.value if sw.cooling_model is not None else None,
        available=True,
        consumptive_cfs=sw.consumptive_cfs,
        annual_7q10_cfs=sw.annual_7q10_cfs,
        summer_30q10_cfs=sw.summer_30q10_cfs,
        one_q10_cfs=sw.one_q10_cfs,
        annual_multiple=sw.annual_multiple,
        summer_multiple=sw.summer_multiple,
        growing_season_months=sw.growing_season_months,
        months=[
            SeasonalMonthCell(
                month=m.month,
                growing_season=m.growing_season,
                et0_mm_day=m.et0_mm_day,
                precip_mm_day=m.precip_mm_day,
                net_atmospheric_mm_day=m.net_atmospheric_mm_day,
                low_flow_cfs=m.low_flow_cfs,
                low_flow_basis=m.low_flow_basis,
                consumptive_cfs=m.consumptive_cfs,
                multiple=m.multiple,
            )
            for m in sw.months
        ],
        caveats=caveats,
        note="Seasonal climograph from evaluate_seasonal: cited ET0/precip normals + Ottawa low flows.",
    )


def _reach_network(settings: Settings) -> ReachNetwork | None:
    """The reach network's river-centerline geometry for the deck.gl FlowLayer viz (#1235).

    Reads the committed ``data/reference/hydrology/reaches/<site>.geojson`` (regenerated by
    ``watermark reaches`` from USGS NLDI / NHDPlus — no NLDI call at export time). Reference-site
    gated like ``routed-hydrograph``: the reach network describes the Lima loop and isn't
    slug-scoped, so a sibling doesn't inherit it. Returns ``None`` when the centerline file is
    absent (nothing invented) — the frontend then degrades to the routed-hydrograph table.
    """
    if not is_reference_site(settings.site):
        return None
    path = settings.reference_dir / "hydrology" / "reaches" / f"{settings.site}.geojson"
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    reaches: list[ReachLine] = []
    for feat in doc.get("features") or []:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        if geom.get("type") != "LineString":
            continue
        coords: list[tuple[float, float]] = []
        for pt in geom.get("coordinates") or []:
            try:
                x, y, *_ = pt
                coords.append((float(x), float(y)))
            except (TypeError, ValueError):
                continue  # skip a malformed vertex rather than crashing the whole export
        if len(coords) < 2:
            continue
        reaches.append(
            ReachLine(
                node_id=str(props.get("node_id") or ""),
                name=str(props.get("name") or props.get("node_id") or ""),
                receiving_water=props.get("receiving_water"),
                downstream=props.get("downstream"),
                length_km=float(props.get("length_km") or 0.0),
                coordinates=coords,
            )
        )
    if not reaches:
        return None
    meta = doc.get("meta") or {}
    return ReachNetwork(
        site=settings.site,
        reaches=reaches,
        note=str(meta.get("subject") or "Reach-network river centerlines (NHDPlus via USGS NLDI)."),
        caveats=list(meta.get("caveats") or []),
    )


def _collect_feeds(settings: Settings) -> list[_Feed]:
    """Load the corpus once and assemble every feed."""
    feeds: list[_Feed] = []

    # Cross-document layer — load the corpus once, reuse for records/timeline/graph. The active
    # site's corpus scope (#762) bounds the extracted-tree feeds: `load_corpus` reads it itself;
    # the `records` feed reads the same tree separately, so it's passed the scope explicitly.
    corpus_scope = effective_corpus_scope(active_profile(settings))
    corpus = load_corpus(settings)
    events = build_timeline(corpus, scope=corpus_scope)
    egraph = build_entity_graph(
        corpus,
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        enrich_subdivisions=True,
        enrich_places=True,
        enrich_relation_classes=True,
        settings=settings,
    )

    # Curated exhibits (#56) — also the auto-included sources for the publish allowlist. Per-site
    # (#762): Lima's frozen exhibits.yaml is its own curation; a sibling site reads its own
    # `site/<slug>/exhibits.yaml` (absent today → an empty exhibits feed, not Lima's).
    exhibit_items = exhibits_mod.export_exhibits(
        site_scoped_path(settings.data_dir / "site" / "exhibits.yaml", settings.site, is_dir=False),
        settings.documents_dir,
    )
    # Open leads (#796) — the curated per-site leads board. Like exhibits, Lima reads its flat
    # `data/site/leads.yaml`; a sibling reads its own `site/<slug>/leads.yaml` (absent → an empty
    # leads feed, never Lima's; the frontend then falls back to the readiness-derived needs board).
    lead_items = leads_mod.export_leads(
        site_scoped_path(settings.data_dir / "site" / "leads.yaml", settings.site, is_dir=False),
    )
    # Site-level contacts — the curated per-site directory of human contact points. Like leads,
    # Lima reads its flat `data/site/contacts.yaml`; a sibling reads its own `site/<slug>/contacts.yaml`
    # (absent → an empty contacts feed, never Lima's; the section then locks and asks for the source).
    contact_items = contacts_mod.export_contacts(
        site_scoped_path(settings.data_dir / "site" / "contacts.yaml", settings.site, is_dir=False),
    )
    # The default-deny public allowlist (#280): exhibits + the committed allowlist rules.
    # Only *whole-file* exhibits auto-include their source; a page-sliced exhibit publishes
    # its derivative slice, not the full bundle behind it (#1301).
    allowlist = documents_mod.load_publish_allowlist(
        settings.data_dir / "site" / "published-documents.yaml",
        exhibit_sources=exhibits_mod.publishable_exhibit_sources(exhibit_items),
    )

    # Source-document catalog (#274/#275): real media_type + render_class + publish flag.
    # Built before records so each record can join to its real source document (#276).
    doc_collections = documents_mod.export_documents(
        settings.documents_dir,
        mirror_base_url=settings.documents_mirror_base_url,
        allowlist=allowlist,
        scope=corpus_scope,
    )
    doc_index = documents_mod.build_doc_index(doc_collections)

    # Remaining unconditional source loads + the opt-in inventories (None => the feed is skipped).
    # The curated stores are per-site (#762): Lima reads its flat committed store; a sibling site
    # reads its own `<slug>/` copy (absent today => an empty/skipped feed, never Lima's). `load_pois`
    # site-scopes itself; meetings are extracted-tree-scoped like the corpus. `concepts` (the wiki
    # glossary) and `defense` (the national contractor seed list) are network-shared — left flat.
    people = load_people(site_scoped_path(settings.people_dir, settings.site, is_dir=True))
    concepts = concepts_mod.load_concepts(
        settings.concepts_dir, site=settings.site
    )  # wiki glossary (#68)
    pois = load_pois(settings=settings)
    summaries = load_committed_summaries(settings, scope=corpus_scope)
    cand_inv = load_cloud_consumer_candidates(
        site_scoped_path(settings.entities_dir, settings.site, is_dir=True)
    )
    defense = load_defense_contractors(settings.entities_dir)
    rsei_inv = load_rsei_inventory(settings)
    lei_inv = load_lei_inventory(
        site_scoped_path(settings.reference_dir, settings.site, is_dir=True)
    )
    econ = load_econ_baseline(settings)
    econ_energy = load_consumer_energy(settings)
    econ_demand = load_demand_pressure(settings)
    # Household energy burden (#1110): a fully derived metric from the committed baseline's
    # Census median household income + the committed EIA prices — no live pull. Absent when a
    # site hasn't onboarded income yet OR its consumer-energy dataset lacks a residential
    # electricity/gas price, so the feed is skipped and the section degrades (#781) rather than
    # crashing the whole export on `derive_energy_burden`'s missing-price ValueError.
    econ_burden = (
        None
        if (
            econ is None
            or econ_energy is None
            or econ.median_household_income is None
            or econ_energy.by_metric("electricity", "price") is None
            or econ_energy.by_metric("natural_gas", "price") is None
        )
        else derive_energy_burden(
            costs=econ_energy, income=econ.median_household_income, settings=settings
        )
    )

    # The feed registry — one row per feed, in bundle order. ``model`` set => a collection feed
    # of that item type; ``None`` => an already-provenanced object feed (its own Pydantic model,
    # #60). A ``build`` that returns ``None`` (an absent optional inventory) is skipped. Adding a
    # feed is one row here. The geo feeds (variable count / conditional) stay below.
    specs: list[tuple[str, type[BaseModel] | None, Callable[[], object | None]]] = [
        (
            "records",
            RecordItem,
            lambda: records_mod.export_records(
                settings.extracted_dir, doc_index=doc_index, scope=corpus_scope
            ),
        ),
        ("timeline", TimelineEntry, lambda: graph_mod.export_timeline(events)),
        ("entities", EntityNode, lambda: graph_mod.export_entities(egraph)),
        ("relationships", RelationshipEdge, lambda: graph_mod.export_relationships(egraph)),
        ("people", PersonItem, lambda: people_mod.export_people(people, egraph=egraph)),
        ("concepts", ConceptItem, lambda: concepts_mod.export_concepts(concepts)),
        ("places", PlaceItem, lambda: places_mod.export_places(pois)),
        (
            "candidates",
            CandidateItem,
            lambda: (
                None
                if cand_inv is None
                else candidates_mod.export_candidates(cand_inv, egraph=egraph)
            ),
        ),
        (
            "defense-contractors",
            None,
            lambda: (
                None
                if defense is None
                else candidates_mod.export_defense_contractors(
                    defense, egraph=egraph, scan=load_defense_scan(settings)
                )
            ),
        ),
        ("meetings", MeetingItem, lambda: meetings_mod.export_meetings(summaries)),
        ("documents", DocumentCollectionItem, lambda: doc_collections),
        ("exhibits", ExhibitItem, lambda: exhibit_items),
        # `or None` skips the feed when a site has no curated leads, so `hasFeed("leads")` is false
        # and the frontend cleanly falls back to the readiness-derived needs board (not an empty list).
        ("leads", LeadItem, lambda: lead_items or None),
        # `or None` skips the feed when a site has no curated contacts, so `hasFeed("contacts")` is
        # false and the frontend cleanly locks the section (not an empty list).
        ("contacts", ContactItem, lambda: contact_items or None),
        # Already-provenanced inventories — exported as their own Pydantic models (#60).
        # An object feed serializes with `count == 1` when present, so the readiness floor
        # (`watermark.site.readiness`) reads its presence as content — a present-but-empty
        # inventory must therefore be dropped (return None), not shipped as an empty shell that
        # floats `backdrop` to `live` on zero facilities/sectors/prices (#1364).
        (
            "rsei",
            None,
            lambda: rsei_mod.export_rsei(rsei_inv) if rsei_inv and rsei_inv.facilities else None,
        ),
        ("lei", None, lambda: None if lei_inv is None else gleif_mod.export_gleif(lei_inv)),
        (
            "economics-baseline",
            None,
            lambda: economics_mod.export_economics(econ) if econ and econ.latest.sectors else None,
        ),
        # Consumer energy costs (EIA) with the full annual price/sales series for charting
        # (issue #1111); absent when the site has no committed consumer-energy dataset — or when
        # it loaded with no price series at all (present-but-empty, #1364).
        (
            "consumer-energy",
            None,
            lambda: (
                economics_mod.export_consumer_energy(econ_energy)
                if econ_energy and econ_energy.prices
                else None
            ),
        ),
        # The facility demand→consumer-price-pressure sensitivity (#1105): households-equivalent,
        # demand share, and the STYLIZED price-pressure band. Facility-gated — absent (feed skipped)
        # for a thin site with no documented facility, exactly as the derivation is gated.
        (
            "economics-demand-pressure",
            None,
            lambda: (
                None if econ_demand is None else economics_mod.export_demand_pressure(econ_demand)
            ),
        ),
        # Household energy burden (#1110): % of median household income (Census B19013) on
        # residential electricity + heating (EIA) — a fully derived consumer-impact metric.
        (
            "energy-burden",
            None,
            lambda: (
                None if econ_burden is None else economics_mod.export_energy_burden(econ_burden)
            ),
        ),
        # Cross-site basin synthesis (#308/#323): the watershed points as one connected basin.
        ("network", None, lambda: build_basin_network(settings=settings)),
        # Watermark's own compute footprint (the GreenOps report, #1076/#1084) — the platform's
        # usage → electricity → water derivation. Global like `network`: a property of the
        # platform, emitted into every bundle identically (reads the committed footprint.yaml, or
        # a modeled placeholder when absent — never skipped, never faked).
        ("greenops", None, lambda: greenops_mod.export_greenops(settings)),
        # The loop's design-storm hydrograph routed down the cited confluence graph (#1184):
        # routed vs. naive-summed outlet peak, attenuation + lag. Reference-only: network.yaml +
        # reaches.yaml describe the Lima loop and aren't slug-scoped, so a sibling site must not
        # inherit them — it carries no routed-hydrograph feed until it commits its own reach table.
        (
            "routed-hydrograph",
            None,
            lambda: (
                build_routed_hydrograph(settings=settings)
                if is_reference_site(settings.site)
                else None
            ),
        ),
        # The boom-origin hypotheses (directory lenses) + their (site x hypothesis) evidence
        # cells (#308) — each cell carries a Citation, so the directory shows provenance.
        ("hypotheses", Hypothesis, lambda: list(HYPOTHESES.values())),
        (
            "hypothesis-assessments",
            HypothesisAssessment,
            lambda: _scoped_assessments(settings),
        ),
        ("hydrology-scenarios", ScenarioResult, lambda: _load_scenarios(settings)),
        # Air-quality & backup-generation dispatch modeling (epic #1172). Tier-0 emissions
        # scenarios + their synthetic-minor NSR cap check (#1177); Tier-1 AERMOD dispersion
        # screen vs NAAQS, event-anchored (#1182). Dispersion is facility+permit-gated (None →
        # skipped, section locks); scenarios carry zero rows for a site without committed ones.
        ("air-scenarios", AirScenarioResult, lambda: _load_air_scenarios(settings)),
        ("air-dispersion", DispersionResult, lambda: _air_dispersion(settings)),
        # The gridded concentration surface for the deck.gl field viz (epic #1237 / #1232) —
        # reference-site gated like routed-hydrograph, `assumption`-provenanced (CBI-redacted stack).
        ("air-dispersion-field", DispersionField, lambda: _dispersion_field(settings)),
        # The seasonal net-atmospheric-withdrawal climograph for the deck.gl water field (epic
        # #1237 / #1236) — an object feed, reference-site gated. The climograph is cited climate
        # normals (`reference`); the per-month low-flow multiple screens the modeled draw ([inference]).
        ("water-seasonal-field", None, lambda: _seasonal_field(settings)),
        # The reach-network river centerlines for the deck.gl FlowLayer flow viz (epic #1237 /
        # #1235) — real NHDPlus geometry, reference-site gated; absent when the committed
        # centerline file is missing (the frontend degrades to the routed-hydrograph table).
        ("reach-network", None, lambda: _reach_network(settings)),
        # The published data catalog (epic #631 Phase 3 / #659) — the data tier /about/data reads.
        ("catalog", CatalogItem, lambda: catalog_mod.export_catalog(settings)),
    ]
    for name, model, build in specs:
        result = build()
        if result is None:
            continue
        if model is not None:
            feeds.append(_collection_feed(name, model, cast("Sequence[BaseModel]", result)))
        else:
            feeds.append(_object_feed(name, cast("BaseModel", result)))

    # Typed GeoJSON layer feeds (issue #61). The committed `gis-findings.geojson` is a Lima
    # artifact (Bistrozzi campus + JSMC + the North Cole corridor), so it's read only for Lima
    # (#762): a sibling site would otherwise inherit Lima's parcels, a phantom Army installation,
    # and Lima's corridor/flood/RSEI points. A non-Lima site emits the per-site geo it can derive
    # — today the campus, from its own parcel assemblage (active_profile().parcels_relpath).
    findings = settings.data_dir / "site" / "gis-findings.geojson"
    if settings.site == "lima" and findings.is_file():
        feeds.extend(_geo_feed(fc) for fc in gismap_mod.export_geo(findings))
    elif settings.site != "lima":
        campus = gismap_mod.campus_from_parcels(settings)
        if campus is not None:
            feeds.append(_geo_feed(campus))
    # Two more geo feeds assembled outside gis-findings: the USGS WBD watershed
    # boundaries and the imagery tracking-AOI footprints + Wayback ladder (for #72).
    watershed = gismap_mod.export_watershed_geo(settings)
    if watershed is not None:
        feeds.append(_geo_feed(watershed))
    imagery = gismap_mod.export_imagery_geo(settings)
    if imagery is not None:
        feeds.append(_geo_feed(imagery))

    return feeds


def _collection_rows(feed: _Feed) -> list[dict[str, Any]]:
    """Parse an assembled collection feed's payload back into row dicts (JSON array or NDJSON)."""
    if feed.media_type == "application/x-ndjson":
        return [json.loads(line) for line in feed.payload.splitlines() if line.strip()]
    return cast("list[dict[str, Any]]", json.loads(feed.payload))


def _catalog_index_feed(feeds: Sequence[_Feed], settings: Settings) -> _Feed:
    """Build the hydrated catalog index (#1093) as an object feed from the assembled feeds.

    A cheap normalisation over the collection feeds already assembled (no corpus re-load): the
    feed-backed catalog kinds only. The Astro build overlays the web-only kinds at render time.
    """
    rows_by_feed = {
        feed.name: _collection_rows(feed) for feed in feeds if feed.kind == "collection"
    }
    index = build_catalog_index(rows_by_feed, site=settings.site, contract_version=CONTRACT_VERSION)
    return _object_feed("catalog-index", index)


def _facts_feed(feeds: Sequence[_Feed], settings: Settings) -> _Feed | None:
    """Build the normalized `facts` feed (#1587) as a projection over the assembled feeds.

    Like `_catalog_index_feed`, a post-pass over feeds already in hand (no corpus re-load): it
    re-keys each `ProvenancedValue` in the economics / greenops / hydrology / air feeds (plus the
    derived facility `PowerBasis`) into a flat `(subject, predicate, value, unit, status, evidence)`
    table. `None` (feed skipped) when a site surfaces no projectable facts, so `hasFeed("facts")`
    is false and the section degrades rather than shipping an empty list.
    """
    payloads_by_feed: dict[str, object] = {}
    for feed in feeds:
        if feed.kind == "collection":
            payloads_by_feed[feed.name] = _collection_rows(feed)
        elif feed.kind == "object":
            payloads_by_feed[feed.name] = json.loads(feed.payload)
    facts = build_facts(payloads_by_feed, settings=settings)
    if not facts:
        return None
    return _collection_feed("facts", FactItem, facts)


def _open_questions_feed(feeds: Sequence[_Feed]) -> _Feed | None:
    """Build the `open-questions` feed (#1568) as a projection over the assembled feeds.

    Like `_facts_feed`, a post-pass over feeds already in hand (no corpus re-load): it aggregates
    every `[open]`-tagged row of the `leads` board + `[open]`-tagged cell of the
    `hypothesis-assessments` matrix (labelled via `hypotheses`) into one provenanced list. `None`
    (feed skipped) when a site has no open threads, so `hasFeed("open-questions")` is false and the
    section degrades rather than shipping an empty list.
    """
    sources = ("leads", "hypothesis-assessments", "hypotheses")
    payloads_by_feed: dict[str, object] = {}
    for feed in feeds:
        if feed.name in sources and feed.kind == "collection":
            payloads_by_feed[feed.name] = _collection_rows(feed)
    questions = build_open_questions(payloads_by_feed)
    if not questions:
        return None
    return _collection_feed("open-questions", OpenQuestionItem, questions)


def _passages_feed(feeds: Sequence[_Feed], settings: Settings) -> _Feed:
    """Build the `passages` feed (#1589) — page excerpts for this site's published PDFs.

    Reads the committed, LFS-independent `data/site/passages.ndjson` artifact (regenerated by
    `watermark passages`, not re-extracted here — the frontend build has no LFS) and keeps the
    passages whose document is a *published PDF* in this bundle's just-assembled `documents` feed.
    So the feed stays scoped to the site AND the publish allowlist, and never re-reads the raw PDFs.
    Always emitted (empty when the artifact is absent) so the schema set stays stable, mirroring
    `ask-embeddings`. `search_passages` reads this over BM25 (+ the optional `passage-embeddings`
    vector upgrade).
    """
    documents_rows: list[dict[str, Any]] = []
    for feed in feeds:
        if feed.name == "documents" and feed.kind == "collection":
            documents_rows = _collection_rows(feed)
            break
    published_rels = {
        e["rel"]
        for coll in documents_rows
        for e in coll.get("entries", [])
        if e.get("published") and e.get("render_class") == "pdf" and e.get("rel")
    }
    passages = [p for p in load_committed_passages(settings) if p.document_id in published_rels]
    return _retrieval_collection_feed("passages", PassageItem, passages)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def export_bundle(
    settings: Settings | None = None,
    out_dir: Path | None = None,
    *,
    generated_at: str | None = None,
    skip_embeddings: bool = False,
) -> BundleResult:
    """Write the full content bundle and return a summary.

    ``generated_at`` overrides the manifest timestamp (used by tests for determinism);
    it defaults to the current UTC time.

    ``skip_embeddings`` suppresses the optional ``ask-embeddings`` feed — useful when
    you need a fast bundle without the ~80 MB model download (``watermark export
    --no-embeddings``).
    """
    settings = settings or get_settings()
    # Per-site bundle (#724/#727): the generated feeds + manifest live under a slug-scoped
    # dir so the network's sites don't clobber each other; the active site comes from
    # `settings.site` (the global `watermark --site <slug>` flag / `WATERMARK_SITE`). The committed,
    # site-agnostic contract (schemas/README/example) stays at `data/site/bundle/`.
    out = out_dir or (settings.data_dir / "site" / "bundles" / settings.site)
    schemas_dir = out / "schemas"
    feeds_dir = out / "feeds"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    feeds_dir.mkdir(parents=True, exist_ok=True)

    feeds = _collect_feeds(settings)
    # The normalized facts feed (#1587) — a projection over the just-assembled provenanced feeds,
    # so it is built before the catalog index (which then indexes `facts` as a dataset too) and
    # after `_collect_feeds`. Skipped (None) for a site with no projectable facts.
    facts_feed = _facts_feed(feeds, settings)
    if facts_feed is not None:
        feeds.append(facts_feed)
    # The aggregated `open-questions` feed (#1568) — a projection over the just-assembled `leads`
    # + `hypothesis-assessments` feeds, so it's appended after `_collect_feeds` (like facts).
    # Skipped (None) for a site with no open threads.
    open_questions_feed = _open_questions_feed(feeds)
    if open_questions_feed is not None:
        feeds.append(open_questions_feed)
    # The page-level `passages` index (#1589) — a post-pass over the just-assembled `documents`
    # feed's published PDFs, so it's appended after `_collect_feeds` (like facts). Always emitted
    # (empty when no published PDF is readable) so the schema set is stable. Its `passage-embeddings`
    # vector companion is built after the feeds land on disk, alongside `ask-embeddings` below.
    feeds.append(_passages_feed(feeds, settings))
    # The hydrated catalog index (#1093) — a normalisation over the just-assembled collection
    # feeds, so it must be appended after `_collect_feeds`. Written + indexed through the same
    # loops below like any other feed.
    feeds.append(_catalog_index_feed(feeds, settings))

    # Schema files (geo feeds share one file — dedup by schema_file path).
    written_schemas: set[str] = set()
    for feed in feeds:
        if feed.schema_file in written_schemas:
            continue
        (out / feed.schema_file).write_text(_dump_json(feed.schema), encoding="utf-8")
        written_schemas.add(feed.schema_file)
    # The manifest schema (so the index itself is validatable) and the shared citation
    # schema — the latter is embedded in every feed's $defs, but emitting it standalone
    # documents the #60 provenance shape.
    (schemas_dir / "manifest.schema.json").write_text(
        _dump_json(_object_schema(Manifest, "Manifest")), encoding="utf-8"
    )
    (schemas_dir / "citation.schema.json").write_text(
        _dump_json(_object_schema(Citation, "Citation")), encoding="utf-8"
    )

    # Feed data files + their manifest rows.
    refs: list[FeedRef] = []
    for feed in feeds:
        target = out / feed.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(feed.payload, encoding="utf-8")
        refs.append(
            FeedRef(
                name=feed.name,
                path=feed.path,
                media_type=feed.media_type,
                schema_ref=feed.schema_file,
                kind=feed.kind,
                count=feed.count,
            )
        )

    # Embedding feeds (#329 ask-embeddings, #1589 passage-embeddings): generated after the corpus
    # feeds are written to disk so the builders read fresh data, not the previous export's stale
    # files. Both are always emitted (empty when `--no-embeddings` or the source text is absent) so
    # the schema set is stable and the manifest stays consistent; both degrade retrieval to BM25.
    def _write_extra_feed(feed: _Feed) -> None:
        if feed.schema_file not in written_schemas:
            (out / feed.schema_file).write_text(_dump_json(feed.schema), encoding="utf-8")
            written_schemas.add(feed.schema_file)
        target = out / feed.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(feed.payload, encoding="utf-8")
        refs.append(
            FeedRef(
                name=feed.name,
                path=feed.path,
                media_type=feed.media_type,
                schema_ref=feed.schema_file,
                kind=feed.kind,
                count=feed.count,
            )
        )

    def _encode(build: Callable[[Path], list[dict[str, Any]]], model: type[BaseModel]) -> list[Any]:
        """Run one embedding builder in isolation — a failure of one feed never blocks the other."""
        if skip_embeddings:
            return []
        try:
            return [model.model_validate(r) for r in build(out)]
        except Exception as exc:
            log.warning(
                "embeddings.failed",
                error=next(iter(str(exc).splitlines()), repr(exc)),
                hint="run with --no-embeddings to skip; hybrid retrieval will degrade to BM25",
            )
            return []

    emb_models = _encode(build_ask_embeddings, AskEmbeddingEntry)
    pemb_models = _encode(build_passage_embeddings, PassageEmbeddingEntry)
    _write_extra_feed(_collection_feed("ask-embeddings", AskEmbeddingEntry, emb_models))
    _write_extra_feed(
        _retrieval_collection_feed("passage-embeddings", PassageEmbeddingEntry, pemb_models)
    )

    row_total = sum(r.count for r in refs)
    # Standing domain-activation readiness (#1220/#1222): computed here, at the end of every
    # export, from the just-assembled feed counts + the active profile — so it rises when a
    # source lands and falls when one dries up, without re-running onboard. The frontend reads
    # this block instead of re-deriving section gating (watermark.site.readiness is the SSOT).
    feed_counts = {r.name: r.count for r in refs}
    readiness = SiteReadiness.model_validate(
        compute_readiness(active_profile(settings), feed_counts)
    )
    manifest = Manifest(
        site=settings.site,
        bundle_version=BUNDLE_VERSION,
        contract_version=CONTRACT_VERSION,
        generated_at=generated_at or _now_iso(),
        feed_count=len(refs),
        row_total=row_total,
        readiness=readiness,
        feeds=refs,
    )
    (out / "manifest.json").write_text(
        _dump_json(manifest.model_dump(mode="json", by_alias=True)), encoding="utf-8"
    )

    # yidam corpus mirror + reports (#1562): on the canonical export, project the just-loaded
    # corpus into yidam nodes under the git-ignored .yidam/ (at the repo root, where the yidam
    # CLI reads) and regenerate the corpus-index / open-questions / graph-check / lint reports,
    # so a single `watermark export` yields a fresh, valid mirror for the active site (like the
    # bundle itself). Only when writing to the default location (``out_dir is None``): a
    # redirected one-off bundle (``--out``, tests) must not clobber the repo's canonical mirror,
    # which also keeps `-n auto` test runs from racing on the shared .yidam/ dir. A secondary
    # artifact — a graph-check issue is a warning and never aborts the export (`watermark
    # corpus-mirror` is the hard gate); a mirror failure degrades to a warning, like embeddings.
    mirror_nodes = 0
    mirror_graph_issues = 0
    reports_dir: Path | None = None
    if out_dir is None:
        try:
            from watermark.site.corpus_mirror import regenerate_mirror

            regen = regenerate_mirror(settings)
            mirror_nodes = len(regen.mirror.nodes)
            mirror_graph_issues = len(regen.graph_issues)
            reports_dir = regen.reports_dir
            if regen.graph_issues:
                log.warning(
                    "corpus_mirror.graph_issues", site=settings.site, count=len(regen.graph_issues)
                )
        except Exception as exc:
            log.warning(
                "corpus_mirror.failed",
                error=next(iter(str(exc).splitlines()), repr(exc)),
                hint="run `watermark corpus-mirror` directly to see the failure",
            )

    log.info("bundle.exported", out=str(out), feeds=len(refs), rows=row_total)
    return BundleResult(
        out_dir=out,
        feeds=refs,
        row_total=row_total,
        mirror_nodes=mirror_nodes,
        mirror_graph_issues=mirror_graph_issues,
        mirror_reports_dir=reports_dir,
    )
