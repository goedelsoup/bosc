"""Routed low-flow network: the pure accumulation solver on synthetic DAGs, plus the
committed Lima topology routed against the real water balance (hermetic)."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import network as net
from watermark.hydrology.balance import build_water_balance
from watermark.hydrology.model import NetworkNode, NetworkTheory, ProvenancedValue


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
    # Σ the LOOP's own tributary 7Q10s = Ottawa 0.2 + Dug Run 0.78 + Pike Run 0.03.
    assert net.loop_natural_total(rn) == pytest.approx(1.01, abs=0.001)
    # The system-wide total (#1488) also carries the outlet's Auglaize-confluence gain — a
    # downstream receiving water's derived 7Q10 (a drainage-area-ratio transfer, not the raw
    # downstream gage value), not one of the loop's own tributaries.
    assert rn.natural_total_cfs == pytest.approx(2.18, abs=0.001)
    # Effluent dwarfs the LOOP's own natural flow; the loop is mostly treated effluent at low flow.
    assert rn.effluent_total_cfs > 10 * net.loop_natural_total(rn)
    assert rn.outlet_effluent_fraction is not None and rn.outlet_effluent_fraction > 0.5
    assert rn.closes
    assert not rn.warnings  # every flow term resolved from a grounded source (cited or derived)
    # #611: the report's per-headwater breakdown is derived from these injected base flows, so
    # the typed-out terms can't silently diverge from the displayed natural_total_cfs. Every
    # reach carrying a base (the loop's 3 headwaters + the outlet's Auglaize gain) sums to the
    # system-wide total; only the headwater-kind ones sum to loop_natural_total.
    all_bases = [r.base.value for r in rn.reaches if r.base is not None]
    assert sum(all_bases) == pytest.approx(rn.natural_total_cfs, abs=0.001)
    outlet = rn.reach("outlet")
    assert outlet is not None and outlet.base is not None
    # Auglaize-at-confluence 7Q10: a drainage-area-ratio transfer (1.91 cfs raw Fort Jennings
    # gage x 0.614 DA ratio), not the raw gage value — see low-flow-7q10.derived.yaml.
    assert outlet.base.value == pytest.approx(1.17, abs=0.001)
    assert outlet.base.source == "derived"


def test_outlet_uses_confluence_transfer_not_raw_downstream_gage(
    hydro_settings: Settings,
) -> None:
    """#1488 review: the raw Fort Jennings gage (04186500) sits BELOW the real confluence and
    already reflects the Ottawa's own historical contribution, so injecting it directly would
    double-count the Ottawa (already separately routed through the loop). The outlet must use
    the drainage-area-ratio TRANSFER entry, not the basin-wide "auglaize river" screening
    proxy — and the transfer must be strictly smaller than the raw gage value it's netted from."""
    from watermark.hydrology import basin

    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    outlet = rn.reach("outlet")
    assert outlet is not None and outlet.base is not None

    lookup = basin.build_low_flow_lookup(settings=hydro_settings)
    raw_gage = lookup[basin._norm("auglaize river")]
    assert outlet.base.value < raw_gage.value  # netted-out estimate, not the raw gage
    assert outlet.base.value == pytest.approx(1.17, abs=0.001)
    # The basin-wide "auglaize river" proxy (used by other sites' own screens) stays untouched.
    assert raw_gage.value == pytest.approx(1.91, abs=0.001)


def test_outlet_credits_auglaize_dilution_over_the_gage(hydro_settings: Settings) -> None:
    """#1488: the outlet used to just repeat the gage's totals (no Auglaize credit), overstating
    the effluent fraction leaving the modeled network. Routed correctly, the Auglaize's own flow
    dilutes it — the outlet's effluent share must be measurably lower than the gage's own."""
    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    gage = rn.reach(rn.assimilative_reach)
    outlet = rn.reach("outlet")
    assert gage is not None and gage.effluent_fraction is not None
    assert outlet is not None and outlet.effluent_fraction is not None
    assert outlet.effluent_fraction < gage.effluent_fraction
    assert rn.outlet_effluent_fraction == pytest.approx(outlet.effluent_fraction, abs=1e-3)


def test_merged_low_flow_lookup_prefers_cited_over_derived(hydro_settings: Settings) -> None:
    """The Ottawa's own cited (document) 7Q10 must win over any derived proxy on a name
    collision — same precedence watermark.hydrology.basin's own screen uses."""
    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    ottawa_head = rn.reach("ottawa-head")
    assert ottawa_head is not None and ottawa_head.base is not None
    assert ottawa_head.base.source == "document"  # cited fact-sheet 7Q10, not the derived proxy
    assert ottawa_head.base.value == pytest.approx(0.2, abs=0.001)


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
    # #1488: the outlet's own receiving-water dilution — the Auglaize-at-confluence transfer
    # (1.17 cfs) against the ~13.7 cfs (mostly effluent) arriving from Lima is itself a
    # violation-band dilution.
    outlet_check = by_check["outlet-receiving-water-dilution"]
    assert outlet_check.ok is False
    assert "violation" in outlet_check.detail


def test_pipeline_run_network(hydro_settings: Settings) -> None:
    from watermark.pipeline import hydrology as hydro_stage

    baseline, buildout, delta = hydro_stage.run_network(settings=hydro_settings, live=False)
    # System-wide (#1488: includes the outlet's Auglaize gain); the loop's own total is 1.01.
    assert baseline.natural_total_cfs == pytest.approx(2.18, abs=0.001)
    assert net.loop_natural_total(baseline) == pytest.approx(1.01, abs=0.001)
    assert buildout.consumptive_cfs > net.loop_natural_total(
        baseline
    )  # draw > the loop's own low flow
    assert delta.mainstem_runs_dry is True
    assert baseline.closes and buildout.closes


# ----------------------------------------------------- toggleable theory overlays


def _inflow_node(node_id: str, downstream: str, cfs: float, component: str) -> NetworkNode:
    return NetworkNode(
        id=node_id,
        name=node_id,
        kind="outfall",
        downstream=downstream,
        status="theorized",
        inject_component=component,  # type: ignore[arg-type]
        inject_cfs=ProvenancedValue.assume(cfs, "cfs", why="test directed inflow"),
    )


def test_solve_handles_inject_natural_and_effluent_components() -> None:
    # A pristine head (1.0) plus two theory inflows: 0.5 natural + 2.0 effluent.
    nodes = [
        _head("head", "conf"),
        _inflow_node("storm", "conf", 0.5, "natural"),
        _inflow_node("pipe", "conf", 2.0, "effluent"),
        NetworkNode(id="conf", name="conf", kind="confluence", downstream="outlet"),
        NetworkNode(id="outlet", name="outlet", kind="outlet"),
    ]
    rn = net.solve_network(nodes, bases={"head": _base(1.0)}, gains={}, theories=["t"])
    out = rn.reach("outlet")
    assert out is not None
    assert out.natural_cfs == pytest.approx(1.5)  # 1.0 head + 0.5 storm
    assert out.effluent_cfs == pytest.approx(2.0)  # injected effluent
    assert rn.natural_total_cfs == pytest.approx(1.5)
    assert rn.effluent_total_cfs == pytest.approx(2.0)
    assert rn.theories == ["t"]
    assert rn.closes
    storm = rn.reach("storm")
    assert (
        storm is not None and storm.inject is not None and storm.inject.value == pytest.approx(0.5)
    )


def test_apply_theories_appends_without_mutating_base() -> None:
    base = [
        NetworkNode(id="a", name="a", kind="confluence", downstream="b"),
        NetworkNode(id="b", name="b", kind="outlet"),
    ]
    theory = NetworkTheory(
        id="t",
        name="t",
        add_nodes=[_inflow_node("x", "a", 1.0, "natural")],
    )
    patched, warnings = net.apply_theories(base, [theory])
    assert len(base) == 2  # original list untouched
    assert {n.id for n in patched} == {"a", "b", "x"}
    assert not warnings


def test_apply_theories_warns_on_dangling_and_collision() -> None:
    base = [NetworkNode(id="a", name="a", kind="outlet")]
    theory = NetworkTheory(
        id="t",
        name="t",
        add_nodes=[
            _inflow_node("a", "a", 1.0, "natural"),  # id collision
            _inflow_node("y", "nowhere", 1.0, "natural"),  # dangling downstream
        ],
    )
    _patched, warnings = net.apply_theories(base, [theory])
    assert any("already exists" in w for w in warnings)
    assert any("unknown" in w and "nowhere" in w for w in warnings)


def test_apply_theories_repoint_reroutes_edge() -> None:
    base = [
        NetworkNode(id="a", name="a", kind="outfall", downstream="b"),
        NetworkNode(id="b", name="b", kind="confluence", downstream="d"),
        NetworkNode(id="c", name="c", kind="confluence", downstream="d"),
        NetworkNode(id="d", name="d", kind="outlet"),
    ]
    theory = NetworkTheory(id="t", name="t", repoint={"a": "c"})
    patched, warnings = net.apply_theories(base, [theory])
    a = next(n for n in patched if n.id == "a")
    assert a.downstream == "c" and not warnings
    # The original node object is unchanged (non-mutating copy).
    assert base[0].downstream == "b"


def test_theories_catalog_loads_and_defaults_off(hydro_settings: Settings) -> None:
    catalog = net.load_theories(settings=hydro_settings)
    ids = {t.id for t in catalog}
    assert {"waterfall-roundabout-pike-run", "shawnee-ii-diverter"} <= ids
    assert all(t.status == "theorized" for t in catalog)
    assert all(not t.enabled for t in catalog)  # every theory ships disabled


def test_theory_disabled_by_default_is_identical_to_cited_baseline(
    hydro_settings: Settings,
) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    cited = net.route_network(balance, consumptive_cfs=0.0, theories=[], settings=hydro_settings)
    catalog_default = net.route_network(
        balance, consumptive_cfs=0.0, theories=None, settings=hydro_settings
    )
    assert catalog_default.theories == []  # nothing on by default
    assert catalog_default.outlet_cfs == cited.outlet_cfs
    assert catalog_default.natural_total_cfs == cited.natural_total_cfs
    assert catalog_default.effluent_total_cfs == cited.effluent_total_cfs


def test_waterfall_theory_augments_pike_run(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    base = net.route_network(balance, consumptive_cfs=0.0, theories=[], settings=hydro_settings)
    wf = net.route_network(
        balance,
        consumptive_cfs=0.0,
        theories=["waterfall-roundabout-pike-run"],
        settings=hydro_settings,
    )
    assert wf.theories == ["waterfall-roundabout-pike-run"]
    # The directed inflow lands as natural-component flow at Pike Run.
    inflow = wf.reach("roundabout-pike-run")
    assert inflow is not None and inflow.inject is not None
    # The inject is now DERIVED (watermark.hydrology.roundabout), a tiny mean-annual smear.
    assert inflow.inject.source == "derived"
    added = inflow.inject.value
    assert added < 0.1  # negligible — the roundabout cannot meaningfully augment Pike Run
    assert wf.natural_total_cfs == pytest.approx(base.natural_total_cfs + added)
    assert wf.outlet_cfs == pytest.approx(base.outlet_cfs + added)
    # Augmentation dilutes: the outlet's effluent share falls.
    assert wf.outlet_effluent_fraction is not None and base.outlet_effluent_fraction is not None
    assert wf.outlet_effluent_fraction < base.outlet_effluent_fraction
    assert wf.closes


def test_waterfall_augmentation_does_not_rescue_the_dry_intake(hydro_settings: Settings) -> None:
    # The roundabout injects DOWNSTREAM of the Ottawa intake, so under a draw that
    # empties the mainstem the intake still runs dry — only the outlet rises.
    balance = build_water_balance(settings=hydro_settings, live=False)
    without = net.route_network(balance, consumptive_cfs=4.85, theories=[], settings=hydro_settings)
    wf = net.route_network(
        balance,
        consumptive_cfs=4.85,
        theories=["waterfall-roundabout-pike-run"],
        settings=hydro_settings,
    )
    assert net._mainstem_runs_dry(wf)  # the intake is unrescued
    abst = wf.reach("lima-abstraction")
    assert abst is not None and abst.routed_cfs == 0.0 and abst.deficit_cfs > 0.0
    assert wf.outlet_cfs > without.outlet_cfs  # but the assimilative reach gains flow
    assert wf.closes


def test_shawnee_diverter_adds_effluent(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    base = net.route_network(balance, consumptive_cfs=0.0, theories=[], settings=hydro_settings)
    sh = net.route_network(
        balance, consumptive_cfs=0.0, theories=["shawnee-ii-diverter"], settings=hydro_settings
    )
    inflow = sh.reach("bosc-fm3-return")
    assert inflow is not None and inflow.inject is not None
    added = inflow.inject.value
    # FM-3 is a campus-wastewater EFFLUENT injection, not natural flow.
    assert sh.effluent_total_cfs == pytest.approx(base.effluent_total_cfs + added)
    assert sh.natural_total_cfs == pytest.approx(base.natural_total_cfs)
    assert sh.closes


def test_unknown_theory_warns_and_solves(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    rn = net.route_network(
        balance, consumptive_cfs=0.0, theories=["no-such"], settings=hydro_settings
    )
    assert any("no-such" in w for w in rn.warnings)
    assert rn.theories == []  # the bogus id contributes nothing
    assert rn.closes


def test_theory_findings_quantify_the_overlay(hydro_settings: Settings) -> None:
    balance = build_water_balance(settings=hydro_settings, live=False)
    without = net.route_network(balance, consumptive_cfs=0.0, theories=[], settings=hydro_settings)
    wf = net.route_network(
        balance,
        consumptive_cfs=0.0,
        theories=["waterfall-roundabout-pike-run"],
        settings=hydro_settings,
    )
    findings = net.theory_findings(without, wf)
    checks = {f.check for f in findings}
    assert {"theory-injected-inflow", "theory-net-effect"} <= checks
    net_effect = next(f for f in findings if f.check == "theory-net-effect")
    assert "THEORIZED" in net_effect.detail and "assumption" in net_effect.detail
    # No theory enabled -> no findings.
    assert net.theory_findings(without, without) == []


def test_pipeline_compare_theory_isolates_overlay(hydro_settings: Settings) -> None:
    from watermark.pipeline import hydrology as hydro_stage

    without, with_theory, findings = hydro_stage.compare_theory(
        ["waterfall-roundabout-pike-run"], settings=hydro_settings, live=False
    )
    # Both sides carry the same cooling draw; only the overlay differs.
    assert without.consumptive_cfs == with_theory.consumptive_cfs
    assert without.theories == [] and with_theory.theories == ["waterfall-roundabout-pike-run"]
    assert with_theory.outlet_cfs > without.outlet_cfs
    assert any(f.check == "theory-net-effect" for f in findings)


# ----------------------------------------------------- report render (#614)


def test_render_routed_network_handles_zero_natural_low_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#614: the routed-balance section divides municipal effluent by the natural total —
    which the section's own premise (the river 'effectively dries') can drive to 0. The
    render must guard the ratio, not raise ZeroDivisionError."""
    from watermark.config import Settings
    from watermark.hydrology import report
    from watermark.hydrology.model import ReachFlow, RoutedNetwork, RoutedNetworkDiff

    def _reach(node_id: str) -> ReachFlow:
        return ReachFlow(
            node_id=node_id,
            name=node_id,
            kind="outfall",
            inflow_cfs=0.0,
            natural_cfs=0.0,
            effluent_cfs=5.0,
            routed_cfs=5.0,
        )

    baseline = RoutedNetwork(
        reaches=[_reach("bosc-fm2-return")],
        natural_total_cfs=0.0,  # the streams have dried — the section's own premise
        effluent_total_cfs=5.0,
        consumptive_cfs=0.0,
        outlet_cfs=5.0,
        outlet_effluent_fraction=1.0,
    )
    buildout = baseline.model_copy(update={"scenario": "buildout"})
    delta = RoutedNetworkDiff(
        baseline="baseline",
        scenario="buildout",
        natural_total_cfs=0.0,
        consumptive_increase_cfs=0.0,
        outlet_decrease_cfs=0.0,
        mainstem_runs_dry=False,
    )
    monkeypatch.setattr(
        "watermark.pipeline.hydrology.run_network", lambda **_: (baseline, buildout, delta)
    )

    lines: list[str] = []
    report._render_routed_network(lines.append, Settings())  # must not raise
    blob = "".join(lines)
    assert "effectively zero at design low flow" in blob  # the guarded phrasing rendered
