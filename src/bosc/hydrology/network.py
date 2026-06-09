"""Route the Lima loop as a directed low-flow stream network.

The per-stream :func:`bosc.hydrology.assimilative.check_assimilative` reads each WWTP
against its own tributary in isolation. That misses the loop-scale picture: at design
low flow the receiving streams carry almost no *natural* water, the WWTP discharges
add far more flow than the streams themselves, and the data-center cooling draw
removes water from the Ottawa mainstem upstream of it all.

This module makes that a routed mass balance. It loads the cited confluence graph
(``data/reference/hydrology/network.yaml``), reads every flow term from an
already-grounded source — cited 7Q10 headwater low flows, document-cited WWTP/campus
discharges from the :class:`~bosc.hydrology.model.WaterBalance`, and the scenario's
consumptive cooling draw — topologically sorts the graph, and accumulates flow
downstream, tracking the **natural** (headwater-origin) and **effluent**
(discharge-origin) components separately. Where the consumptive draw exceeds the
water present in a reach, the shortfall is recorded as a ``deficit`` (a stream drawn
dry at design low flow).

The order-invariant **system** totals (Σ natural low flow, Σ effluent, net draw) are
the robust headline; the per-reach values depend on the cited-but-approximate
confluence order and are screening-grade.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology import lowflow
from bosc.hydrology.model import (
    HydroFinding,
    NetworkNode,
    NetworkTheory,
    ProvenancedValue,
    ReachFlow,
    RoutedNetwork,
    RoutedNetworkDiff,
    WaterBalance,
)
from bosc.logging import get_logger

log = get_logger(__name__)


def _topology_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "network.yaml"


def load_topology(*, settings: Settings | None = None) -> list[NetworkNode]:
    """Load the committed cited network topology, or ``[]`` if the file is absent."""
    settings = settings or get_settings()
    path = _topology_path(settings)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [NetworkNode.model_validate(n) for n in (data.get("nodes") or [])]


def _theories_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "theories.yaml"


def load_theories(*, settings: Settings | None = None) -> list[NetworkTheory]:
    """Load the committed catalog of toggleable network theories, or ``[]`` if absent."""
    settings = settings or get_settings()
    path = _theories_path(settings)
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [NetworkTheory.model_validate(t) for t in (data.get("theories") or [])]


def resolve_theories(
    requested: Sequence[str] | None,
    catalog: list[NetworkTheory],
) -> tuple[list[NetworkTheory], list[str]]:
    """Pick which theories to enable: the named ids, or each catalog ``enabled`` default.

    ``requested is None`` means "use the catalog defaults" (theories with
    ``enabled: true``); an explicit list (even empty) overrides that. Returns the chosen
    theories and warnings for any unknown id.
    """
    by_id = {t.id: t for t in catalog}
    if requested is None:
        return [t for t in catalog if t.enabled], []
    chosen: list[NetworkTheory] = []
    warnings: list[str] = []
    for tid in requested:
        theory = by_id.get(tid)
        if theory is None:
            warnings.append(f"unknown theory {tid!r} (not in theories.yaml)")
            continue
        chosen.append(theory)
    return chosen, warnings


def apply_theories(
    nodes: list[NetworkNode], theories: list[NetworkTheory]
) -> tuple[list[NetworkNode], list[str]]:
    """Overlay enabled theory nodes/edges onto the cited topology (pure, non-mutating).

    For each theory: append its ``add_nodes`` (directed inflows, each carrying its own
    ``inject_cfs``) and apply its ``repoint`` edges (replace a node with a re-pointed
    copy). Returns the patched node list and warnings (id collisions, dangling
    downstreams, unknown repoint endpoints). The base graph is never mutated.
    """
    warnings: list[str] = []
    by_id = {n.id: n for n in nodes}
    out = list(nodes)
    for theory in theories:
        for new in theory.add_nodes:
            if new.id in by_id:
                warnings.append(f"theory {theory.id}: node {new.id!r} already exists; skipped")
                continue
            if new.downstream is not None and new.downstream not in by_id:
                warnings.append(
                    f"theory {theory.id}: node {new.id!r} drains into unknown {new.downstream!r}"
                )
            by_id[new.id] = new
            out.append(new)
        for src, dst in theory.repoint.items():
            node = by_id.get(src)
            if node is None:
                warnings.append(f"theory {theory.id}: repoint source {src!r} not found")
                continue
            if dst not in by_id:
                warnings.append(f"theory {theory.id}: repoint target {dst!r} not found")
                continue
            repointed = node.model_copy(update={"downstream": dst})
            by_id[src] = repointed
            out = [repointed if n.id == src else n for n in out]
    return out, warnings


def _toposort(nodes: list[NetworkNode]) -> list[NetworkNode]:
    """Order nodes so every contributor precedes the node it drains into (Kahn)."""
    by_id = {n.id: n for n in nodes}
    upstream: dict[str, list[str]] = {n.id: [] for n in nodes}
    for n in nodes:
        if n.downstream is not None and n.downstream in by_id:
            upstream[n.downstream].append(n.id)

    solved: list[NetworkNode] = []
    done: set[str] = set()
    remaining = list(nodes)
    while remaining:
        ready = [n for n in remaining if all(u in done for u in upstream[n.id])]
        if not ready:
            raise ValueError("network topology has a cycle or dangling edge")
        for n in ready:
            solved.append(n)
            done.add(n.id)
        remaining = [n for n in remaining if n.id not in done]
    return solved


def route_network(
    balance: WaterBalance,
    *,
    consumptive_cfs: float = 0.0,
    scenario_name: str = "baseline",
    theories: Sequence[str] | None = None,
    settings: Settings | None = None,
) -> RoutedNetwork:
    """Solve the routed low-flow network for one consumptive-draw scenario.

    Resolves every flow term from a grounded source — cited 7Q10 (``low_flow``),
    document-cited discharge in ``balance`` (``balance_return``), scenario draw
    (``consumptive``) — then hands the pre-resolved terms to :func:`solve_network`.

    ``theories`` toggles unproven structural overlays from
    ``data/reference/hydrology/theories.yaml``: ``None`` uses the catalog ``enabled``
    defaults (off), a list of ids enables exactly those, ``[]`` forces the cited
    baseline. Each enabled theory appends its directed-inflow nodes before the solve.
    """
    settings = settings or get_settings()
    nodes = load_topology(settings=settings)
    warnings: list[str] = []
    if not nodes:
        warnings.append("network topology absent (data/reference/hydrology/network.yaml)")
        return solve_network(
            [],
            bases={},
            gains={},
            consumptive_cfs=consumptive_cfs,
            scenario_name=scenario_name,
            warnings=warnings,
        )

    chosen, theory_warnings = resolve_theories(theories, load_theories(settings=settings))
    warnings.extend(theory_warnings)
    if chosen:
        nodes, overlay_warnings = apply_theories(nodes, chosen)
        warnings.extend(overlay_warnings)
    enabled_ids = [t.id for t in chosen]

    norm_low = {k.strip().lower(): v for k, v in lowflow.load_low_flows(settings=settings).items()}
    bases: dict[str, ProvenancedValue] = {}
    gains: dict[str, ProvenancedValue] = {}
    for n in nodes:
        if n.low_flow is not None:
            pv = norm_low.get(n.low_flow.strip().lower())
            if pv is None:
                warnings.append(f"{n.id}: no cited 7Q10 for {n.low_flow!r}; base flow 0.")
            else:
                bases[n.id] = pv
        if n.balance_return is not None:
            wbn = balance.node(n.balance_return)
            if wbn is None or wbn.return_flow is None:
                warnings.append(f"{n.id}: no discharge in balance for {n.balance_return!r}.")
            else:
                gains[n.id] = wbn.return_flow

    return solve_network(
        nodes,
        bases=bases,
        gains=gains,
        consumptive_cfs=consumptive_cfs,
        scenario_name=scenario_name,
        theories=enabled_ids,
        warnings=warnings,
    )


def solve_network(
    nodes: list[NetworkNode],
    *,
    bases: dict[str, ProvenancedValue],
    gains: dict[str, ProvenancedValue],
    consumptive_cfs: float = 0.0,
    scenario_name: str = "baseline",
    theories: list[str] | None = None,
    warnings: list[str] | None = None,
) -> RoutedNetwork:
    """Accumulate pre-resolved flow terms downstream through the topology (pure).

    ``bases`` (headwater 7Q10) and ``gains`` (outfall discharge) are keyed by node id;
    a node's own ``inject_cfs`` (a theory overlay's directed inflow) is read straight
    off the node and added to its ``natural`` or ``effluent`` component. A node tagged
    ``consumptive`` removes ``consumptive_cfs`` as a loss; where the loss exceeds the
    water present the shortfall becomes a ``deficit`` and the reach goes to zero.
    Natural (headwater-origin) and effluent (gain-origin) flow are tracked separately
    and a loss removes them proportionally.
    """
    warnings = warnings if warnings is not None else []
    upstream: dict[str, list[str]] = {n.id: [] for n in nodes}
    for n in nodes:
        if n.downstream is not None and n.downstream in upstream:
            upstream[n.downstream].append(n.id)

    solved: dict[str, ReachFlow] = {}
    for node in _toposort(nodes):
        nat_in = sum(solved[u].natural_cfs for u in upstream[node.id])
        eff_in = sum(solved[u].effluent_cfs for u in upstream[node.id])
        inflow = nat_in + eff_in

        base = bases.get(node.id)
        gain = gains.get(node.id)
        inject = node.inject_cfs
        loss = (
            ProvenancedValue.derived(
                consumptive_cfs,
                "cfs",
                citation=f"consumptive cooling draw (scenario {scenario_name})",
            )
            if node.consumptive and consumptive_cfs > 0.0
            else None
        )
        if base is not None:
            nat_in += base.value
        if gain is not None:
            eff_in += gain.value
        if inject is not None:
            if node.inject_component == "effluent":
                eff_in += inject.value
            else:
                nat_in += inject.value

        total_in = nat_in + eff_in
        loss_val = loss.value if loss is not None else 0.0
        deficit = 0.0
        if loss_val <= total_in and total_in > 0.0:
            scale = (total_in - loss_val) / total_in
            nat_out, eff_out = nat_in * scale, eff_in * scale
        elif loss_val > 0.0:
            nat_out, eff_out = 0.0, 0.0
            deficit = loss_val - total_in
        else:
            nat_out, eff_out = nat_in, eff_in

        solved[node.id] = ReachFlow(
            node_id=node.id,
            name=node.name,
            kind=node.kind,
            base=base,
            gain=gain,
            inject=inject,
            loss=loss,
            inflow_cfs=round(inflow, 4),
            natural_cfs=round(nat_out, 4),
            effluent_cfs=round(eff_out, 4),
            routed_cfs=round(nat_out + eff_out, 4),
            deficit_cfs=round(deficit, 4),
            status=node.status,
        )

    natural_total = sum(r.base.value for r in solved.values() if r.base is not None)
    natural_total += sum(
        n.inject_cfs.value
        for n in nodes
        if n.inject_cfs is not None and n.inject_component == "natural"
    )
    effluent_total = sum(r.gain.value for r in solved.values() if r.gain is not None)
    effluent_total += sum(
        n.inject_cfs.value
        for n in nodes
        if n.inject_cfs is not None and n.inject_component == "effluent"
    )
    gage = next((n.id for n in nodes if n.kind == "gage"), None)
    outlet_id = next((n.id for n in nodes if n.kind == "outlet"), None)
    outlet = solved.get(outlet_id) if outlet_id else None

    rn = RoutedNetwork(
        scenario=scenario_name,
        theories=list(theories or []),
        reaches=list(solved.values()),
        assimilative_reach=gage,
        natural_total_cfs=round(natural_total, 4),
        effluent_total_cfs=round(effluent_total, 4),
        consumptive_cfs=round(consumptive_cfs, 4),
        outlet_cfs=round(outlet.routed_cfs, 4) if outlet else 0.0,
        outlet_effluent_fraction=(
            round(outlet.effluent_fraction, 4)
            if outlet and outlet.effluent_fraction is not None
            else None
        ),
        warnings=warnings,
    )
    log.info(
        "hydro.network",
        scenario=scenario_name,
        theories=rn.theories,
        natural=rn.natural_total_cfs,
        effluent=rn.effluent_total_cfs,
        consumptive=rn.consumptive_cfs,
        outlet=rn.outlet_cfs,
        closes=rn.closes,
    )
    return rn


def _mainstem_runs_dry(rn: RoutedNetwork) -> bool:
    """True if an abstraction reach is drawn to zero flow (a deficit recorded)."""
    return any(
        r.kind == "abstraction" and r.routed_cfs == 0.0 and r.deficit_cfs > 0.0 for r in rn.reaches
    )


def diff_networks(baseline: RoutedNetwork, buildout: RoutedNetwork) -> RoutedNetworkDiff:
    """Baseline vs buildout: the new draw against the loop's natural low flow."""
    increase = buildout.consumptive_cfs - baseline.consumptive_cfs
    natural = buildout.natural_total_cfs
    return RoutedNetworkDiff(
        baseline=baseline.scenario,
        scenario=buildout.scenario,
        theories=list(buildout.theories),
        natural_total_cfs=natural,
        consumptive_increase_cfs=round(increase, 4),
        multiple_of_natural=round(increase / natural, 2) if natural > 0 else None,
        outlet_decrease_cfs=round(baseline.outlet_cfs - buildout.outlet_cfs, 4),
        mainstem_runs_dry=_mainstem_runs_dry(buildout),
    )


def network_findings(rn: RoutedNetwork) -> list[HydroFinding]:
    """System-level findings from the routed network."""
    findings: list[HydroFinding] = []
    if not rn.reaches:
        return findings

    frac = rn.outlet_effluent_fraction
    findings.append(
        HydroFinding(
            subject="Lima loop at design low flow",
            check="effluent-dominance",
            ok=not (frac is not None and frac > 0.5),
            detail=(
                f"natural low flow Σ{rn.natural_total_cfs:g} cfs vs effluent Σ"
                f"{rn.effluent_total_cfs:g} cfs; outlet is "
                f"{frac:.0%} treated effluent"
                if frac is not None
                else "no outlet flow"
            ),
        )
    )
    findings.append(
        HydroFinding(
            subject="routed network conservation",
            check="mass-balance-closes",
            ok=rn.closes,
            detail=(
                f"Sum of base + gain - applied loss reconciles to outlet {rn.outlet_cfs:g} cfs"
            ),
        )
    )
    if rn.consumptive_cfs > 0.0:
        findings.append(
            HydroFinding(
                subject="Ottawa mainstem at the intake",
                check="low-flow-depletion",
                ok=not _mainstem_runs_dry(rn),
                detail=(
                    f"consumptive draw {rn.consumptive_cfs:g} cfs vs natural low flow Σ"
                    f"{rn.natural_total_cfs:g} cfs"
                    + (" — mainstem runs dry" if _mainstem_runs_dry(rn) else "")
                ),
            )
        )
    return findings


def theory_findings(without: RoutedNetwork, with_theory: RoutedNetwork) -> list[HydroFinding]:
    """Quantify what an enabled theory overlay does to the loop vs the cited baseline.

    Pass the same-scenario network solved *without* theories and *with* them. Reports,
    per overlay reach, the directed inflow it injects and where, and the net change in
    outlet flow and effluent share — always carrying the standing caveat that the
    overlay is *theorized* and its magnitude is an assumption, not a measurement.
    """
    findings: list[HydroFinding] = []
    if not with_theory.theories:
        return findings

    ids = ", ".join(with_theory.theories)
    for r in with_theory.reaches:
        if r.inject is None:
            continue
        findings.append(
            HydroFinding(
                subject=f"theory inflow at {r.name}",
                check="theory-injected-inflow",
                ok=True,  # informational: a what-if input, neither pass nor fail
                detail=(
                    f"+{r.inject.value:g} {r.inject.unit} directed inflow [{r.inject.source}] "
                    f"— {r.inject.citation or 'no citation'}"
                ),
            )
        )

    added = round(with_theory.outlet_cfs - without.outlet_cfs, 3)
    fb, fa = without.outlet_effluent_fraction, with_theory.outlet_effluent_fraction
    frac_txt = ""
    if fb is not None and fa is not None:
        frac_txt = f"; outlet effluent share {fb:.0%} -> {fa:.0%}"
    findings.append(
        HydroFinding(
            subject=f"theory overlay [{ids}]",
            check="theory-net-effect",
            ok=True,  # informational, not an adverse finding
            detail=(
                f"enabling [{ids}] changes outlet flow by {added:+g} cfs{frac_txt}. "
                "THEORIZED overlay held out of the cited baseline; the injected magnitude "
                "is an assumption, not a measurement."
            ),
        )
    )
    return findings
