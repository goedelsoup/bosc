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
    # Every routed reach attenuates (outflow peak <= inflow peak) and lags (>= 0).
    assert {r.node_id for r in rn.reaches} == {"head-a", "head-b", "confluence"}
    for r in rn.reaches:
        assert r.outflow_peak_cfs <= r.inflow_peak_cfs + 1e-6
        assert r.lag_hr >= -1e-6


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


def test_route_storm_network_warns_on_orphan_catchment() -> None:
    """A catchment keyed to a node absent from the topology is surfaced, not silently dropped."""
    nodes = [NetworkNode(id="outlet", name="Outlet", kind="outlet")]
    table = ReachTable(catchments={"ghost": _catchment(1000, 80, 1.0)}, reaches={})
    rn = hr.route_storm_network(nodes, table, return_period_yr=25, storm_depth_in=4.0)
    assert any("ghost" in w for w in rn.warnings)


# ----------------------------------------------------------------- loader + committed loop


def test_load_reaches_absent_returns_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert hr.load_reaches(settings=Settings(data_dir=tmp_path)) is None


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


def test_committed_lima_loop_routes_and_attenuates(hydro_settings: Settings) -> None:
    """End-to-end on the committed loop: the outlet peak is attenuated + lagged, no gaps."""
    rn = hr.build_routed_hydrograph(return_period_yr=25, settings=hydro_settings, live=False)
    assert rn is not None
    assert rn.routed_peak_cfs < rn.summed_peak_cfs
    assert 0.0 < rn.peak_attenuation_pct < 100.0
    assert rn.lag_hr > 0.0
    assert rn.reaches, "the committed loop should route several reaches"
    assert not rn.warnings, "every routed node in the committed topology has reach geometry"
    # The findings headline reports the attenuation and passes (attenuation is non-negative).
    findings = hr.hydrograph_findings(rn)
    assert findings and findings[0].ok and "attenuat" in findings[0].detail.lower()
