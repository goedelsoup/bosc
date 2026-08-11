"""Storm-hydrograph routing down the confluence graph (#1184).

Three layers: the Muskingum-Cunge ``route`` primitive (volume conservation + attenuation +
lag on a synthetic hydrograph), the pure ``route_storm_network`` accumulator on a synthetic
two-tributary DAG (a routed outlet peak is below the naive sum, and later), and the committed
Lima loop routed end-to-end against ``network.yaml`` + ``reaches.yaml`` (hermetic).
"""

from __future__ import annotations

import numpy as np
import pytest

from watermark.config import Settings
from watermark.hydrology import hydrograph_routing as hr
from watermark.hydrology.model import (
    Catchment,
    NetworkNode,
    ProvenancedValue,
    Reach,
    ReachTable,
)
from watermark.hydrology.solver.routing import route
from watermark.sites import SITES

# The three per-site tables a peer commits to have a reach network at all (reach-nav.yaml is
# the navigation plan, not a loader input, so a site carrying only that one still loads nothing).
_REACH_TABLES = ("reaches.yaml", "network.yaml", "reach-nav.yaml")


def _pv(value: float, unit: str) -> ProvenancedValue:
    return ProvenancedValue.assume(value, unit, why="test")


def _catchment(area: float, cn: float, tc: float) -> Catchment:
    return Catchment(area_acres=_pv(area, "acre"), curve_number=_pv(cn, ""), tc_hr=_pv(tc, "hr"))


def _reach(length: float, slope: float) -> Reach:
    return Reach(length_ft=_pv(length, "ft"), slope=_pv(slope, "ft/ft"))


# ----------------------------------------------------------------- the route() primitive


def test_route_conserves_volume() -> None:
    """Muskingum coefficients sum to 1, so the routed volume matches the inflow (within tol)."""
    inflow = np.concatenate([np.linspace(0, 500, 40), np.linspace(500, 0, 60), np.zeros(300)])
    out = route(inflow, length_ft=20000, slope=0.001, dt_hr=0.1)
    assert out.sum() == pytest.approx(inflow.sum(), rel=0.02)


def test_route_attenuates_and_lags_the_peak() -> None:
    """A routed reach lowers the peak and shifts its time-to-peak later — never earlier."""
    inflow = np.concatenate([np.linspace(0, 500, 40), np.linspace(500, 0, 60), np.zeros(300)])
    out = route(inflow, length_ft=30000, slope=0.0008, dt_hr=0.1)
    assert out.max() < inflow.max()  # attenuated
    assert int(np.argmax(out)) >= int(np.argmax(inflow))  # lagged (or coincident), never earlier
    assert (out >= 0).all()  # the clamp holds


def test_route_passthrough_on_zero_inflow() -> None:
    """A dry reach (no peak to derive parameters from) passes the series through unchanged."""
    inflow = np.zeros(50)
    out = route(inflow, length_ft=1000, slope=0.001)
    assert np.array_equal(out, inflow)


# ----------------------------------------------------------------- the pure accumulator


def _two_tributary_dag() -> tuple[list[NetworkNode], ReachTable]:
    """head_a + head_b -> confluence -> outlet, each tributary a routed reach."""
    nodes = [
        NetworkNode(id="head-a", name="Trib A", kind="headwater", downstream="confluence"),
        NetworkNode(id="head-b", name="Trib B", kind="headwater", downstream="confluence"),
        NetworkNode(id="confluence", name="Confluence", kind="confluence", downstream="outlet"),
        NetworkNode(id="outlet", name="Outlet", kind="outlet"),
    ]
    table = ReachTable(
        catchments={
            "head-a": _catchment(8000, 80, 2.0),
            "head-b": _catchment(6000, 78, 2.5),
        },
        reaches={
            "head-a": _reach(30000, 0.002),
            "head-b": _reach(24000, 0.002),
            "confluence": _reach(15000, 0.0012),
        },
    )
    return nodes, table


def test_routed_outlet_peak_is_below_the_naive_sum_and_later() -> None:
    """Routing two tributary hydrographs to the outlet attenuates + lags the peak vs. the sum."""
    nodes, table = _two_tributary_dag()
    rn = hr.route_storm_network(nodes, table, return_period_yr=25, storm_depth_in=4.0)

    assert rn.summed_peak_cfs > 0
    assert rn.routed_peak_cfs < rn.summed_peak_cfs  # attenuated below the naive stack
    assert 0.0 < rn.peak_attenuation_pct < 100.0
    assert rn.lag_hr > 0.0  # the routed peak arrives later than the un-routed sum
    # Series share one horizon and are non-trivial.
    assert len(rn.times_hr) == len(rn.outlet_hydrograph_cfs) == len(rn.summed_hydrograph_cfs) > 0
    # Every routed reach attenuates (outflow peak <= inflow peak) and lags (>= 0), and records
    # the sub-reach discretization it was routed at (WS-09 / #1609): Courant ≈ 1, coeffs positive.
    assert {r.node_id for r in rn.reaches} == {"head-a", "head-b", "confluence"}
    for r in rn.reaches:
        assert r.outflow_peak_cfs <= r.inflow_peak_cfs + 1e-6
        assert r.lag_hr >= -1e-6
        assert r.subreaches >= 1
        assert 0.5 <= r.courant <= 2.0  # near 1 by construction — the routing validity flag


def test_node_without_a_reach_passes_flow_through_unrouted() -> None:
    """An outfall sitting at a confluence (no reach entry) contributes its inflow unrouted."""
    nodes = [
        NetworkNode(id="head", name="Head", kind="headwater", downstream="outlet"),
        NetworkNode(id="plant", name="Outfall", kind="outfall", downstream="outlet"),
        NetworkNode(id="outlet", name="Outlet", kind="outlet"),
    ]
    # `plant` has a catchment but no reach → its local hydrograph reaches the outlet unrouted.
    table = ReachTable(
        catchments={"head": _catchment(5000, 80, 2.0), "plant": _catchment(2000, 85, 1.0)},
        reaches={"head": _reach(20000, 0.002)},
    )
    rn = hr.route_storm_network(nodes, table, return_period_yr=25, storm_depth_in=4.0)
    # Only `head` is a routed reach; `plant` and the outlet are pass-throughs (no warning).
    assert {r.node_id for r in rn.reaches} == {"head"}
    assert not rn.warnings
    assert rn.routed_peak_cfs > 0


def test_route_storm_network_warns_on_orphan_catchment_and_reach() -> None:
    """A catchment OR reach keyed to a node absent from the topology is surfaced, not dropped."""
    nodes = [
        NetworkNode(id="head", name="Head", kind="headwater", downstream="outlet"),
        NetworkNode(id="outlet", name="Outlet", kind="outlet"),
    ]
    table = ReachTable(
        catchments={"head": _catchment(5000, 80, 2.0), "ghost-catch": _catchment(1000, 80, 1.0)},
        reaches={"head": _reach(20000, 0.002), "ghost-reach": _reach(1000, 0.001)},
    )
    rn = hr.route_storm_network(nodes, table, return_period_yr=25, storm_depth_in=4.0)
    assert any("ghost-catch" in w and "catchment" in w for w in rn.warnings)
    assert any("ghost-reach" in w and "reach" in w for w in rn.warnings)


def test_short_tc_catchment_drops_the_whole_network_onto_one_finer_grid(
    hydro_settings: Settings,
) -> None:
    """WS-10 / #1610: superposing at a confluence needs ONE clock.

    The SCS unit-duration rule (D <= 0.133*Tc) refines the step for a small, fast catchment. If
    each catchment kept its own step, the confluence would sum series sampled on different
    clocks; the network drops to the finest step required instead, and says so.
    """
    nodes, table = _two_tributary_dag()
    table.catchments["head-b"] = _catchment(6000, 78, 0.3)  # a fast catchment: 0.133*Tc = 0.04 hr
    rn = hr.route_storm_network(
        nodes, table, return_period_yr=25, storm_depth_in=4.0, settings=hydro_settings
    )
    assert rn.dt_hr == pytest.approx(0.1 / 3)  # the coarsest sub-multiple of 0.1 under 0.0399
    assert any("one time grid" in w for w in rn.warnings)
    assert len(rn.times_hr) == len(rn.outlet_hydrograph_cfs) == len(rn.summed_hydrograph_cfs)
    assert rn.times_hr[0] == pytest.approx(0.1 / 3, abs=1e-4)  # stored to 4 decimals
    # The committed loop's catchments are all slow (Tc >= 2 hr), so it stays on the 0.1-hr grid.
    slow = hr.route_storm_network(
        *_two_tributary_dag(), return_period_yr=25, storm_depth_in=4.0, settings=hydro_settings
    )
    assert slow.dt_hr == pytest.approx(0.1)
    assert not any("one time grid" in w for w in slow.warnings)


def test_route_storm_network_carries_the_site_label() -> None:
    """The site label flows onto the result and into the finding subject (not hardcoded Lima)."""
    nodes, table = _two_tributary_dag()
    rn = hr.route_storm_network(
        nodes, table, return_period_yr=25, storm_depth_in=4.0, site_label="Findlay"
    )
    assert rn.site == "Findlay"
    assert hr.hydrograph_findings(rn)[0].subject.startswith("Findlay loop")


# ----------------------------------------------------------------- loader + committed loop


def test_load_reaches_absent_returns_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert hr.load_reaches(settings=Settings(data_dir=tmp_path)) is None


def test_peer_tables_resolve_slug_scoped_never_limas(hydro_settings: Settings) -> None:
    """#1806: a peer's loaders resolve reference/hydrology/<slug>/ — with Lima's legacy
    files committed right there in the shared dir, a peer without its OWN tables must load
    NOTHING (the inheritance leak the slug-scoping closes), and Lima's pins still resolve
    the legacy paths byte-identically.

    The peer is RESOLVED, not named. ``sidney`` was hardcoded here until #1996 committed its
    reach network, at which point this failed for the best possible reason — a site had gained
    the very tables the test relied on it lacking. Picking the first registered site with no
    committed tables keeps the assertion about the slug-scoping RULE rather than about one
    site's data state, so the next peer to commit a reach network moves the example instead of
    breaking the test.
    """
    hydro_dir = hydro_settings.reference_dir / "hydrology"
    slug = next(
        (
            s
            for s in SITES
            if s != "lima" and not any((hydro_dir / s / f).is_file() for f in _REACH_TABLES)
        ),
        None,
    )
    assert slug is not None, "every registered peer now commits its own reach tables"
    peer = hydro_settings.model_copy(update={"site": slug})
    assert hr._reaches_path(peer).parts[-3:] == ("hydrology", slug, "reaches.yaml")
    assert hr.load_reaches(settings=peer) is None
    assert hr.network.load_topology(settings=peer) == []
    assert hr.build_routed_hydrograph(settings=peer, live=False) is None
    lima = hr._reaches_path(hydro_settings)
    assert lima.parts[-3:] == ("reference", "hydrology", "reaches.yaml")


def test_committed_peer_tables_are_geometry_grade(hydro_settings: Settings) -> None:
    """The other half of #1806, which the slug-scoping test above can no longer cover: a peer
    that HAS committed its tables loads its own, keyed to its own topology — and does not
    thereby acquire a routed storm model. Every peer set committed so far is geometry-grade
    (``catchments: {}``, the #1364 rule), so the routed-hydrograph feed must still self-skip.

    Selected on ANY of :data:`_REACH_TABLES`, then asserted COMPLETE — deliberately the same
    predicate the test above negates, so the two partition every peer between them. Selecting on
    ``reaches.yaml`` alone left a hole: a site that committed only a topology or only a nav plan
    was excluded from the test above (which needs *none* of them) and silently skipped by this
    one, so a half-landed reach set would have been checked by neither.
    """
    hydro_dir = hydro_settings.reference_dir / "hydrology"
    peers = [
        s
        for s in SITES
        if s != "lima" and any((hydro_dir / s / f).is_file() for f in _REACH_TABLES)
    ]
    assert peers, "expected at least one peer reach table (fort-wayne, sidney)"
    for slug in peers:
        missing = [f for f in _REACH_TABLES if not (hydro_dir / slug / f).is_file()]
        assert not missing, f"{slug} committed a PARTIAL reach set — missing {missing}"
        settings = hydro_settings.model_copy(update={"site": slug})
        table = hr.load_reaches(settings=settings)
        assert table is not None, slug
        node_ids = {n.id for n in hr.network.load_topology(settings=settings)}
        assert node_ids, slug
        assert set(table.reaches) <= node_ids, slug
        assert not table.catchments, f"{slug} committed catchments — see #1364 before routing"
        assert hr.build_routed_hydrograph(settings=settings, live=False) is None, slug


def test_geometry_grade_table_skips_the_routed_feed(tmp_path, hydro_settings: Settings) -> None:  # type: ignore[no-untyped-def]
    """#1364 on the routing axis: a committed table with topology + reach geometry but NO
    catchments (the honest geometry-grade artifact a peer commits for the reach-network map)
    must NOT produce an all-zero routed-hydrograph feed. Derived from `hydro_settings` so the
    hermetic offline/fixture config holds even if the guard ordering ever changes."""
    d = tmp_path / "reference" / "hydrology" / "sidney"
    d.mkdir(parents=True)
    (d / "network.yaml").write_text(
        "nodes:\n"
        "- id: head\n  name: Head\n  kind: headwater\n  downstream: outlet\n"
        "- id: outlet\n  name: Outlet\n  kind: outlet\n",
        encoding="utf-8",
    )
    (d / "reaches.yaml").write_text(
        "catchments: {}\n"
        "reaches:\n"
        "  head:\n"
        "    length_ft: {value: 5000.0, unit: ft, source: derived, citation: test}\n"
        "    slope: {value: 0.001, unit: ft/ft, source: assumption, citation: test}\n",
        encoding="utf-8",
    )
    settings = hydro_settings.model_copy(update={"data_dir": tmp_path, "site": "sidney"})
    table = hr.load_reaches(settings=settings)
    assert table is not None and not table.catchments  # the table itself loads fine
    assert hr.build_routed_hydrograph(settings=settings, live=False) is None


def test_committed_reaches_table_loads(hydro_settings: Settings) -> None:
    """The committed reaches.yaml validates and keys onto the network.yaml nodes."""
    table = hr.load_reaches(settings=hydro_settings)
    assert table is not None
    assert {"ottawa-head", "dug-run-head", "pike-run-head"} <= set(table.catchments)
    # Pike Run's area is DERIVED from the committed WBD polygon (provenance discipline).
    assert table.catchments["pike-run-head"].area_acres.source == "derived"
    # Every reach key is a real node id in the committed topology.
    node_ids = {n.id for n in hr.network.load_topology(settings=hydro_settings)}
    assert set(table.reaches) <= node_ids


def test_committed_fort_wayne_tables_are_geometry_grade(hydro_settings: Settings) -> None:
    """#1806's first peer set: the committed Fort Wayne tables load slug-scoped, key onto
    their own topology, and stay geometry-grade — reach-network geometry without a routed
    storm model (catchments deliberately empty, so the routed feed self-skips)."""
    fw = hydro_settings.model_copy(update={"site": "fort-wayne"})
    table = hr.load_reaches(settings=fw)
    assert table is not None
    assert table.catchments == {}  # geometry-grade by design — no fabricated CN/Tc/areas
    node_ids = {n.id for n in hr.network.load_topology(settings=fw)}
    assert node_ids, "fort-wayne commits its own topology under reference/hydrology/fort-wayne/"
    assert set(table.reaches) <= node_ids
    assert hr.build_routed_hydrograph(settings=fw, live=False) is None
    # The committed centerlines are spatially CONNECTED at the Three Rivers junction: both
    # fork lines terminate on the maumee-head line's upstream vertex (the St. Joseph via the
    # nav plan's confluence_point trim — its mouth rides a flowline fused into the Maumee
    # levelpath, so no navigation distance alone can end there).
    import json as _json

    doc = _json.loads(
        (fw.data_dir / "reference" / "hydrology" / "reaches" / "fort-wayne.geojson").read_text(
            encoding="utf-8"
        )
    )
    lines = {f["properties"]["node_id"]: f["geometry"]["coordinates"] for f in doc["features"]}
    junction = lines["maumee-head"][0]
    for fork in ("st-joseph-confluence", "st-marys-confluence"):
        end = lines[fork][-1]
        assert end == junction, f"{fork} does not terminate at the junction vertex: {end}"


def test_committed_lima_loop_routes_and_attenuates(hydro_settings: Settings) -> None:
    """End-to-end on the committed loop: the outlet peak is attenuated + lagged, no gaps."""
    rn = hr.build_routed_hydrograph(return_period_yr=25, settings=hydro_settings, live=False)
    assert rn is not None
    assert rn.routed_peak_cfs < rn.summed_peak_cfs
    assert 0.0 < rn.peak_attenuation_pct < 100.0
    assert rn.lag_hr > 0.0
    assert rn.reaches, "the committed loop should route several reaches"
    assert not rn.warnings, "every routed node in the committed topology has reach geometry"
    # Every reach is sub-reach-resolved to Courant ≈ 1 (WS-09 / #1609): a long reach is split
    # into several steps, and no reach is under-resolved (a single step with a large Courant).
    assert any(r.subreaches > 1 for r in rn.reaches), "the long mainstem reaches should subdivide"
    for r in rn.reaches:
        assert 0.5 <= r.courant <= 2.0, f"{r.node_id} Courant {r.courant} off the validity band"
    assert rn.site == "Lima", "the reference-build loop is labelled from the active SiteProfile"
    # The findings headline is site-labelled, reports the attenuation, and passes.
    findings = hr.hydrograph_findings(rn)
    assert findings and findings[0].ok and "attenuat" in findings[0].detail.lower()
    assert findings[0].subject.startswith("Lima loop")
