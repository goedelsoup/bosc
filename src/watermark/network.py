"""The BOSC network synthesis — the Maumee watershed points as one connected basin.

Each site is onboarded independently (its own hydrology / economics / grid / toxics artifacts
under ``data/reference/**/<slug>/``). This module assembles the **cross-site** view the per-site
artifacts can't express on their own: that every point drains to the same Maumee → Lake Erie
system under the same nutrient cap, so the sites are *nested nodes on one basin*, not parallel
points. It joins the curated basin topology (``data/reference/network/topology.yaml`` — sink +
shared TMDL constraint + per-node position/regime/representative-POTW) with each node's committed
reference data (economic baseline, grid profile, RSEI inventory) and its low-flow screen, into one
provenance-aware :class:`BasinNetwork`.

Read-only over committed reference data — no network calls. The dilution screen is **one
dimension among several**; many nodes are honestly *unscreened* (ECHO has no receiving water, or
the tributary is ungaged), and that data gap is surfaced rather than papered over.

Note: distinct from :mod:`watermark.hydrology.network` (the routed *Lima-loop* stream solver). This is
the multi-site BOSC network (Epic #308 / #323).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.economics.model import EconomicBaseline
from watermark.grid.model import GridProfile
from watermark.hydrology.basin import build_low_flow_lookup, load_dischargers, screen_facility
from watermark.logging import get_logger
from watermark.rsei import RseiInventory
from watermark.sites import SITES, DcEndUse, FacilityLifecycle, SiteFacility, get_profile

log = get_logger(__name__)

_TOPOLOGY = ("network", "topology.yaml")

# NAICS sectors whose location quotient we surface (the "load-not-jobs onto a shrinking
# industrial base" shape): manufacturing and information (the data-center sector).
_NAICS_MANUFACTURING = "31-33"
_NAICS_INFORMATION = "51"

# Screen bands, most-binding first (for picking a node's representative discharger).
_BAND_RANK = {"violation": 0, "tight": 1, "ok": 2}


class NodeScreen(BaseModel):
    """The node's low-flow dilution screen — its representative discharger, screened or not."""

    model_config = ConfigDict(extra="forbid")

    npdes: str
    discharger: str
    receiving_water: str | None = None
    design_flow_mgd: float | None = None
    dilution_ratio: float | None = None
    flag: str | None = None  # ok / tight / violation (when screened)
    status: str  # screened / no_receiving_water / no_7q10 / no_design_flow / not_in_inventory
    detail: str = ""


class NodeGrid(BaseModel):
    """The node's serving-utility / grid backdrop (from its committed grid profile)."""

    model_config = ConfigDict(extra="forbid")

    utility: str | None = None
    ownership: str | None = None  # Investor Owned / Municipal / Cooperative
    holding_company: str | None = None
    balancing_authority: str | None = None
    retail_regulator: str | None = None
    # The EIA-861 bundled standard-service-offer COHORT price, NOT the utility's all-sector
    # average and NOT an industrial/data-center rate (G3/#1644; the qualification rides on the
    # source value's citation — see `watermark.grid.model.UtilityProfile`). Comparable
    # node-to-node because every node reads the same cohort definition, which is what this
    # cross-site table uses it for.
    avg_price_cents_kwh: float | None = None


class NodeEconomy(BaseModel):
    """The node's county economic base (from its committed QCEW/Census baseline)."""

    model_config = ConfigDict(extra="forbid")

    year: int | None = None
    total_employment: float | None = None
    employment_change_pct: float | None = None  # first→last point on the trend
    population: int | None = None
    manufacturing_lq: float | None = None  # NAICS 31-33 location quotient
    information_lq: float | None = None  # NAICS 51 (the data-center sector)


class NodeToxics(BaseModel):
    """The node's county toxics legacy (from its committed RSEI inventory)."""

    model_config = ConfigDict(extra="forbid")

    facility_count: int | None = None
    top_emitter: str | None = None
    vintage_last_year: int | None = None  # newest reporting year across the county's facilities


class NodeActivity(BaseModel):
    """The node's disclosed data-center activity (from the primary ``SiteProfile`` **campus**).

    Carries the primary campus's real-world lifecycle ``facility_status`` (#1628) so the pure
    basin/directory builders read it off the ``network`` feed instead of a hardcoded per-slug dict —
    ``None`` when the site has no disclosed campus (the reader defaults to ``investigation``).
    ``facility_count`` counts the site's data-center campuses.

    Data-center only, by construction (#1664): a ``federal_installation`` facility (WPAFB) is a
    documented facility but not data-center activity, so it is excluded here rather than reported
    as a campus with an ``[open]`` IT load. The enclave surfaces through the ``enclave`` feed and
    the ``facility`` domain instead.
    """

    model_config = ConfigDict(extra="forbid")

    has_disclosed_facility: bool = False
    facility_count: int = 0
    facility_status: FacilityLifecycle | None = None
    operator: str | None = None
    end_use: DcEndUse | None = None
    it_load_mw: float | None = None
    summary: str = "no disclosed data-center facility"


class WatershedNode(BaseModel):
    """One watershed point as a node in the connected basin — position + multi-attribute card."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    place: str
    county: str
    huc8: str
    receiving_water: str
    drainage_path: list[str]
    subtree: str  # Auglaize / Tiffin / Maumee mainstem
    downstream: str  # the collector node it drains into, or the basin sink
    regime: str  # the receiving-water taxonomy [inference]
    screen: NodeScreen
    grid: NodeGrid
    economy: NodeEconomy
    toxics: NodeToxics
    activity: NodeActivity


class BasinNetwork(BaseModel):
    """The assembled cross-site synthesis: the shared basin + every node, ordered upstream→down."""

    model_config = ConfigDict(extra="forbid")

    sink: str
    shared_constraint: str
    generated_at: str | None = None
    nodes: list[WatershedNode]


# --- artifact loading -----------------------------------------------------------------------
def _load_model(path: Path, model: type[Any]) -> Any | None:
    """Validate a committed YAML artifact into ``model``, or ``None`` if absent/invalid."""
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return model.model_validate(data) if isinstance(data, dict) else None
    except Exception as exc:  # a malformed artifact shouldn't sink the whole synthesis
        log.warning("network.artifact.skip", path=str(path), error=str(exc)[:160])
        return None


def _topology(settings: Settings) -> dict[str, Any]:
    path = settings.reference_dir / Path(*_TOPOLOGY)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None
    return data if isinstance(data, dict) else {}


# --- topology derivation --------------------------------------------------------------------
def _river_label(reach: str) -> str:
    """A reach name as a subtree label — drop a trailing ``River`` (``Auglaize River`` → ``Auglaize``)."""
    return reach.removesuffix(" River").strip()


def _subtree(drainage_path: list[str]) -> str:
    """The major tributary subtree a node sits in, derived from its drainage path (basin-agnostic).

    The path is ordered headwater→mainstem (``[tributary…, major_tributary, basin_mainstem]``), so
    the subtree is the trunk tributary feeding the mainstem (the second-to-last reach), or the basin
    mainstem itself for a node discharging directly to it. This generalizes the former Maumee-only
    literal table (#610): a Maumee node still yields ``Auglaize`` / ``Tiffin`` / ``Maumee mainstem``
    exactly as before, and a cross-basin (Miami / Scioto) node yields its own basin's grouping rather
    than mis-bucketing to ``Maumee mainstem``.
    """
    if not drainage_path:
        return "unrooted"
    if len(drainage_path) == 1:
        return f"{_river_label(drainage_path[-1])} mainstem"
    return _river_label(drainage_path[-2])


def _downstream(slug: str, sink: str, spine: list[str]) -> str:
    """The collector a node drains into: the next node down the lower-Maumee spine, or the sink.

    ``spine`` is the lower-Maumee collector order (e.g. ``[defiance, toledo]``). Every node above
    the confluence drains to the first collector; the last collector drains to the basin sink.
    """
    if not spine:
        return sink
    if slug in spine:
        i = spine.index(slug)
        return spine[i + 1] if i + 1 < len(spine) else sink
    return spine[0]


def _node_rank(node: WatershedNode, spine: list[str]) -> tuple[int, int, str]:
    """Upstream→downstream display order: tributary subtrees first, then each basin's upper
    mainstem, then the collector spine (downstream order).

    Basin-agnostic (#610): groups by subtree name rather than a Maumee-only literal table — a
    tributary node sorts before a mainstem one, then by ``subtree:slug`` so a basin's tributaries
    stay grouped. For the Maumee-only network today this reproduces the prior order exactly
    (``Auglaize`` < ``Tiffin`` alphabetically matches the old explicit ordering).
    """
    if node.slug in spine:
        return (3, spine.index(node.slug), node.slug)
    tier = 2 if node.subtree.endswith("mainstem") else 0
    return (tier, 0, f"{node.subtree}:{node.slug}")


# --- per-node dimension extraction ----------------------------------------------------------
def _screen_node(
    npdes_list: list[str],
    disch: dict[str, dict[str, Any]],
    lookup: dict[str, Any],
) -> NodeScreen:
    """Screen a node's representative POTW(s); return the binding (worst screened) result.

    A node may list several POTWs (Lima's loop). Each is screened; the most-binding *screened*
    result wins (violation < tight < ok). If none screen, the first POTW's status (with its
    reason) is reported — the honest "unscreened, because …".
    """
    screened: list[NodeScreen] = []
    unscreened: list[NodeScreen] = []
    for npdes in npdes_list:
        fac = disch.get(npdes)
        if fac is None:
            unscreened.append(NodeScreen(npdes=npdes, discharger=npdes, status="not_in_inventory"))
            continue
        check, status = screen_facility(fac, lookup)
        name = str(fac.get("name") or npdes)
        if check is not None:
            screened.append(
                NodeScreen(
                    npdes=npdes,
                    discharger=name,
                    receiving_water=check.receiving_water,
                    design_flow_mgd=fac.get("design_flow_mgd"),
                    dilution_ratio=check.dilution_ratio,
                    flag=check.flag,
                    status="screened",
                    detail=check.detail,
                )
            )
        else:
            rw = fac.get("receiving_water")
            unscreened.append(
                NodeScreen(
                    npdes=npdes,
                    discharger=name,
                    receiving_water=str(rw) if rw else None,
                    design_flow_mgd=fac.get("design_flow_mgd"),
                    status=status,
                    detail=f"unscreened ({status})",
                )
            )
    if screened:
        return min(
            screened, key=lambda s: (_BAND_RANK.get(s.flag or "ok", 3), s.dilution_ratio or 0.0)
        )
    return unscreened[0] if unscreened else NodeScreen(npdes="", discharger="", status="no_potw")


def _grid_of(gp: GridProfile | None) -> NodeGrid:
    if gp is None:
        return NodeGrid()
    su = gp.serving_utility
    up = gp.utility_profile
    price = up.avg_price_cents_kwh.value if up.avg_price_cents_kwh else None
    return NodeGrid(
        utility=su.utility.value,
        ownership=up.ownership or None,
        holding_company=su.holding_company.value,
        balancing_authority=su.balancing_authority.value,
        retail_regulator=su.retail_regulator.value,
        avg_price_cents_kwh=price,
    )


def _economy_of(base: EconomicBaseline | None) -> NodeEconomy:
    if base is None:
        return NodeEconomy()
    lq = {s.naics: s.location_quotient.value for s in base.latest.sectors if s.location_quotient}
    change = None
    if len(base.trend) >= 2:
        first, last = base.trend[0].total_employment.value, base.trend[-1].total_employment.value
        if first:
            change = round((last - first) / first * 100.0, 1)
    pop = (
        base.population.points[-1].population.value
        if base.population and base.population.points
        else None
    )
    return NodeEconomy(
        year=base.latest.year,
        total_employment=base.latest.total_employment.value,
        employment_change_pct=change,
        population=int(pop) if pop is not None else None,
        manufacturing_lq=lq.get(_NAICS_MANUFACTURING),
        information_lq=lq.get(_NAICS_INFORMATION),
    )


def _toxics_of(inv: RseiInventory | None) -> NodeToxics:
    if inv is None or not inv.facilities:
        return NodeToxics(facility_count=0 if inv is not None else None)
    top = max(inv.facilities, key=lambda f: f.score)
    last_years = [f.last_year for f in inv.facilities if f.last_year is not None]
    return NodeToxics(
        facility_count=len(inv.facilities),
        top_emitter=top.name,
        vintage_last_year=max(last_years) if last_years else None,
    )


def _activity_summary(facility: SiteFacility | None, count: int) -> str:
    """The node card's one-line data-center activity summary (#1628) — lifecycle-aware and safe for
    a facility whose IT load is entirely ``[open]`` (never the primary today, but guarded)."""
    if facility is None:
        return "no disclosed data-center facility"
    load = (
        f"IT load ~{facility.it_load_mw:g} MW"
        if facility.it_load_mw is not None
        else "IT load [open]"
    )
    extra = f" (+{count - 1} more campus)" if count > 1 else ""
    return f"disclosed facility ({facility.status.value}) — {load}{extra}"


def build_basin_network(
    *, settings: Settings | None = None, generated_at: str | None = None
) -> BasinNetwork:
    """Assemble the cross-site synthesis from the topology + each node's committed artifacts."""
    settings = settings or get_settings()
    topo = _topology(settings)
    meta = topo.get("meta", {})
    sink = str(meta.get("sink", "Lake Erie"))
    spine = list(meta.get("collector_spine", []))
    constraint = str((meta.get("shared_constraint") or {}).get("name", ""))

    lookup = build_low_flow_lookup(settings=settings)
    disch = {
        str(f.get("npdes_id")): f for f in load_dischargers(settings=settings) if f.get("npdes_id")
    }

    nodes: list[WatershedNode] = []
    for slug, ndata in topo.get("nodes", {}).items():
        if slug not in SITES:
            log.warning("network.unknown_slug", slug=slug)
            continue
        prof = get_profile(slug)
        path = list(ndata.get("drainage_path", []))
        base = _load_model(settings.data_dir / prof.baseline_relpath, EconomicBaseline)
        grid = _load_model(settings.data_dir / prof.grid_relpath, GridProfile)
        inv = _load_model(settings.data_dir / prof.rsei_relpath, RseiInventory)
        # `campus`, not `facility` (#1664): this card is the node's DATA-CENTER activity, and a
        # federal installation is a facility that is emphatically not that. Counting WPAFB's
        # enclave here would read as "disclosed data-center facility" on an Air Force base.
        facility = prof.campus
        dc_count = sum(1 for f in prof.facilities if f.is_data_center)
        nodes.append(
            WatershedNode(
                slug=slug,
                place=prof.place,
                county=prof.county_name,
                huc8=str(ndata.get("huc8", "")),
                receiving_water=prof.receiving_water_name,
                drainage_path=path,
                subtree=_subtree(path),
                downstream=_downstream(slug, sink, spine),
                regime=str(ndata.get("regime", "")),
                screen=_screen_node(list(ndata.get("wwtp_npdes", [])), disch, lookup),
                grid=_grid_of(grid),
                economy=_economy_of(base),
                toxics=_toxics_of(inv),
                activity=NodeActivity(
                    has_disclosed_facility=facility is not None,
                    facility_count=dc_count,
                    facility_status=facility.status if facility else None,
                    operator=facility.operator if facility else None,
                    end_use=facility.end_use if facility else None,
                    it_load_mw=facility.it_load_mw if facility else None,
                    summary=_activity_summary(facility, dc_count),
                ),
            )
        )

    nodes.sort(key=lambda n: _node_rank(n, spine))
    log.info(
        "network.synthesis",
        nodes=len(nodes),
        screened=sum(n.screen.status == "screened" for n in nodes),
    )
    return BasinNetwork(
        sink=sink, shared_constraint=constraint, generated_at=generated_at, nodes=nodes
    )


def write_basin_network(network: BasinNetwork, *, settings: Settings | None = None) -> Path:
    """Persist the computed synthesis to ``data/reference/network/basin-network.yaml``."""
    settings = settings or get_settings()
    out = settings.reference_dir / "network" / "basin-network.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        # mode="json" so the FacilityLifecycle/DcEndUse StrEnum fields (#1628) serialize to their
        # string values — plain model_dump keeps enum instances that safe_dump can't represent.
        yaml.safe_dump(network.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("network.write", path=str(out), nodes=len(network.nodes))
    return out
