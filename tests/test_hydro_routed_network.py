"""Routed low-flow network: the pure accumulation solver on synthetic DAGs, plus the
committed Lima topology routed against the real water balance (hermetic)."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.hydrology import network as net
from bosc.hydrology.balance import build_water_balance
from bosc.hydrology.model import NetworkNode, ProvenancedValue


def _head(node_id: str, downstream: str) -> NetworkNode:
    return NetworkNode(id=node_id, name=node_id, kind="headwater", downstream=downstream)


def _outfall(node_id: str, downstream: str) -> NetworkNode:
    return NetworkNode(id=node_id, name=node_id, kind="outfall", downstream=downstream)


def _base(value: float) -> ProvenancedValue:
    return ProvenancedValue.from_document(value, "cfs", "test 7Q10")


def _gain(value: float) -> ProvenancedValue:
    return ProvenancedValue.from_document(value, "cfs", "test discharge")


# ----------------------------------------------------------------- toposort


def test_toposort_orders_contributors_before_their_outlet() -> None:
    nodes = [
        NetworkNode(id="outlet", name="o", kind="outlet"),
        _head("head", "outlet"),
        _outfall("plant", "outlet"),
    ]
    order = [n.id for n in net._toposort(nodes)]
    assert order.index("head") < order.index("outlet")
    assert order.index("plant") < order.index("outlet")


def test_toposort_rejects_a_cycle() -> None:
    nodes = [
        NetworkNode(id="a", name="a", kind="confluence", downstream="b"),
        NetworkNode(id="b", name="b", kind="confluence", downstream="a"),
    ]
    with pytest.raises(ValueError):
        net._toposort(nodes)


# ------------------------------------------------------- synthetic accumulation


def test_solve_accumulates_natural_and_effluent() -> None:
    # head (1.0 natural) + outfall (4.0 effluent) -> confluence -> outlet.
    nodes = [
        _head("head", "conf"),
        _outfall("plant", "conf"),
        NetworkNode(id="conf", name="conf", kind="confluence", downstream="outlet"),
        NetworkNode(id="outlet", name="outlet", kind="outlet"),
    ]
    rn = net.solve_network(nodes, bases={"head": _base(1.0)}, gains={"plant": _gain(4.0)})
    out = rn.reach("outlet")
    assert out is not None
    assert out.natural_cfs == pytest.approx(1.0)
    assert out.effluent_cfs == pytest.approx(4.0)
    assert out.routed_cfs == pytest.approx(5.0)
    assert out.effluent_fraction == pytest.approx(0.8)
    assert rn.natural_total_cfs == pytest.approx(1.0)
    assert rn.effluent_total_cfs == pytest.approx(4.0)
    assert rn.closes


def test_consumptive_loss_removes_proportionally() -> None:
    # head (2.0 natural) + outfall (8.0 effluent) meet at a node that loses 5.0.
    nodes = [
        _head("head", "mix"),
        _outfall("plant", "mix"),
        NetworkNode(
            id="mix", name="mix", kind="abstraction", consumptive=True, downstream="outlet"
        ),
        NetworkNode(id="outlet", name="outlet", kind="outlet"),
    ]
    rn = net.solve_network(
        nodes, bases={"head": _base(2.0)}, gains={"plant": _gain(8.0)}, consumptive_cfs=5.0
    )
    mix = rn.reach("mix")
    assert mix is not None
    # 10 in, lose 5 -> scale 0.5: natural 1.0, effluent 4.0.
    assert mix.natural_cfs == pytest.approx(1.0)
    assert mix.effluent_cfs == pytest.approx(4.0)
    assert mix.deficit_cfs == 0.0
    assert rn.closes


def test_loss_exceeding_supply_runs_the_reach_dry() -> None:
    # head (0.2) -> abstraction draws 5.0 -> the reach goes dry with a 4.8 deficit.
    nodes = [
        _head("head", "abs"),
        NetworkNode(
            id="abs", name="abs", kind="abstraction", consumptive=True, downstream="outlet"
        ),
        NetworkNode(id="outlet", name="outlet", kind="outlet"),
    ]
    rn = net.solve_network(nodes, bases={"head": _base(0.2)}, gains={}, consumptive_cfs=5.0)
    abst = rn.reach("abs")
    assert abst is not None
    assert abst.routed_cfs == 0.0
    assert abst.deficit_cfs == pytest.approx(4.8)
    assert rn.reach("outlet").routed_cfs == 0.0  # type: ignore[union-attr]
    assert net._mainstem_runs_dry(rn)
    assert rn.closes  # applied loss = 0.2, supplied = 0.2 - 0.2 = 0 = outlet


def test_loss_provenance_is_derived() -> None:
    nodes = [
        _head("head", "abs"),
        NetworkNode(
            id="abs", name="abs", kind="abstraction", consumptive=True, downstream="outlet"
        ),
        NetworkNode(id="outlet", name="outlet", kind="outlet"),
    ]
    rn = net.solve_network(nodes, bases={"head": _base(1.0)}, gains={}, consumptive_cfs=0.5)
    abst = rn.reach("abs")
    assert abst is not None and abst.loss is not None
    assert abst.loss.source == "derived" and not abst.loss.verified


# --------------------------------------------------- committed Lima topology


def test_committed_topology_is_well_formed(hydro_settings: Settings) -> None:
    nodes = net.load_topology(settings=hydro_settings)
    assert nodes, "data/reference/hydrology/network.yaml must be committed"
    ids = {n.id for n in nodes}
    # Every downstream edge resolves to a real node.
    for n in nodes:
        assert n.downstream is None or n.downstream in ids, f"{n.id} -> {n.downstream}"
    assert sum(1 for n in nodes if n.kind == "gage") == 1
    assert sum(1 for n in nodes if n.kind == "outlet") == 1
    net._toposort(nodes)  # acyclic


def test_route_baseline_system_totals(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(
        balance, consumptive_cfs=0.0, scenario_name="baseline", settings=hydro_settings
    )
    # Σ natural low flow = Ottawa 0.2 + Dug Run 0.78 + Pike Run 0.03.
    assert rn.natural_total_cfs == pytest.approx(1.01, abs=0.001)
    # Effluent dwarfs natural; the loop is mostly treated effluent at low flow.
    assert rn.effluent_total_cfs > 10 * rn.natural_total_cfs
    assert rn.outlet_effluent_fraction is not None and rn.outlet_effluent_fraction > 0.9
    assert rn.closes
    assert not rn.warnings  # every flow term resolved from a grounded source


def test_buildout_draw_runs_the_mainstem_dry(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    # A draw larger than the loop's whole natural low flow (~1 cfs).
    rn = net.route_network(
        balance, consumptive_cfs=4.85, scenario_name="buildout", settings=hydro_settings
    )
    abst = rn.reach("lima-abstraction")
    assert abst is not None
    assert abst.routed_cfs == 0.0 and abst.deficit_cfs > 0.0
    assert net._mainstem_runs_dry(rn)
    assert rn.closes


def test_diff_against_natural_low_flow(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    base = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    build = net.route_network(
        balance, consumptive_cfs=4.85, scenario_name="buildout", settings=hydro_settings
    )
    d = net.diff_networks(base, build)
    assert d.multiple_of_natural is not None and d.multiple_of_natural > 4.0
    assert d.mainstem_runs_dry is True


def test_findings_flag_effluent_dominance_and_conservation(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    findings = net.network_findings(rn)
    by_check = {f.check: f for f in findings}
    assert by_check["effluent-dominance"].ok is False  # effluent dominates -> adverse
    assert by_check["mass-balance-closes"].ok is True


def test_pipeline_run_network(hydro_settings: Settings) -> None:
    from bosc.pipeline import hydrology as hydro_stage

    baseline, buildout, delta = hydro_stage.run_network(settings=hydro_settings, live=False)
    assert baseline.natural_total_cfs == pytest.approx(1.01, abs=0.001)
    assert buildout.consumptive_cfs > baseline.natural_total_cfs  # draw exceeds natural low flow
    assert delta.mainstem_runs_dry is True
    assert baseline.closes and buildout.closes
