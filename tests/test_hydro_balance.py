"""End-to-end water balance + low-flow assimilative screen, and the provenance invariant."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import balance as bal
from watermark.hydrology import lowflow
from watermark.hydrology.assimilative import (
    assimilative_findings,
    check_assimilative,
    dilution_flag,
)
from watermark.hydrology.balance import build_water_balance
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.model import Node, ProvenancedValue, WaterBalance, WaterBalanceNode
from watermark.pipeline.hydrology import run_baseline


def test_cited_low_flows_load(hydro_settings: Settings) -> None:
    flows = lowflow.load_low_flows(settings=hydro_settings)
    assert flows["dug run"].value == pytest.approx(0.78)
    assert flows["pike run"].value == pytest.approx(0.03)
    # Both are read straight from Ohio EPA fact sheets — document-sourced and cited.
    for pv in flows.values():
        assert pv.source == "document"
        assert pv.citation


def test_low_flow_lookup_normalizes_river_mile(hydro_settings: Settings) -> None:
    pv = lowflow.low_flow_for("Dug Run at River Mile 3.1", settings=hydro_settings)
    assert pv is not None and pv.value == pytest.approx(0.78)


def test_baseline_flags_tributary_violations(hydro_settings: Settings) -> None:
    balance, checks, findings = run_baseline(settings=hydro_settings, live=True)

    # Four WWTPs with document design flows: the three small county plants plus the
    # City of Lima WWTP (18.5 MGD, OEPA 2PE00000 / OH0026069 — the major municipal
    # receiving plant, counted since #1536); the abstraction reach is live.
    assert len(balance.by_role("wwtp")) == 4
    abstraction = balance.node("lima-wtp")
    assert abstraction is not None and abstraction.inflow is not None
    assert abstraction.inflow.source == "connector"  # grounded by the NWIS fixture
    # The fixture reading is NWIS provisional ("P"), so it enters low-confidence, not as
    # an authoritative approved value (#1602).
    assert abstraction.inflow.confidence == "low"

    # American II -> Dug Run is the binding, document-cited near-undiluted case.
    dug = next(c for c in checks if c.receiving_water == "Dug Run")
    assert dug.discharge.value == pytest.approx(1.857, abs=0.01)  # 1.2 MGD
    assert dug.dilution_ratio < 1.0 and dug.flag == "violation"

    # All three plants discharge more than their stream's entire 7Q10 (incl. the
    # Ottawa mainstem, whose 7Q10 is now cited from the Lima Refining fact sheet).
    violations = [f for f in findings if not f.ok]
    assert {f.subject.split(" -> ")[1] for f in violations} == {
        "Dug Run",
        "Pike Run",
        "Ottawa River",
    }


def test_provenance_invariant(hydro_settings: Settings) -> None:
    """Every numeric input carries a source; document values carry a citation."""
    balance, _checks, _findings = run_baseline(settings=hydro_settings, live=True)
    values = balance.all_values()
    assert values  # not vacuous
    for pv in values:
        assert pv.source in ("document", "connector", "assumption", "derived")
        if pv.source == "document":
            assert pv.citation, f"document value without citation: {pv}"


def test_campus_consumptive_is_derived_not_placeholder(hydro_settings: Settings) -> None:
    # The campus cooling consumptive is the sourced power-based central (≈4.86 cfs from
    # the air permit x WUE), `derived` — not the old 0 cfs "unsourced placeholder".
    balance = build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is not None
    cu = campus.consumptive_use
    assert cu.source == "derived"
    assert cu.value == pytest.approx(4.86, abs=0.1)
    assert "cooling basis" in (cu.citation or "")
    # No stale "placeholder"/"unsourced"/"TBD" framing remains in the warnings.
    joined = " ".join(balance.warnings).lower()
    assert "placeholder" not in joined
    assert "unsourced" not in joined
    assert "tbd" not in joined


def test_assimilative_matches_suffixed_receiving_water(hydro_settings: Settings) -> None:
    # A receiving water carrying a river-mile / place suffix ("Dug Run at River Mile 3.1")
    # must still resolve its cited 7Q10 ("dug run"): the lookup normalizes the same way
    # the cited table was keyed. Regression for the silent-skip bug where the suffixed
    # name missed the table and the discharge vanished from the screen.
    node = Node(
        id="x-wwtp", name="X WWTP", role="wwtp", receiving_water="Dug Run at River Mile 3.1"
    )
    wbn = WaterBalanceNode(
        node=node, return_flow=ProvenancedValue.from_document(2.0, "cfs", citation="test 2 cfs")
    )
    balance = WaterBalance(nodes=[wbn], warnings=[])
    checks = check_assimilative(balance, dict(lowflow.load_low_flows(settings=hydro_settings)))
    dug = next((c for c in checks if "Dug Run" in c.receiving_water), None)
    assert dug is not None, "suffixed receiving water must still resolve its cited 7Q10"
    assert dug.design_low_flow.value == pytest.approx(0.78)


def _wwtp(node_id: str, name: str, water: str, cfs: float) -> WaterBalanceNode:
    return WaterBalanceNode(
        node=Node(id=node_id, name=name, role="wwtp", receiving_water=water),
        return_flow=ProvenancedValue.from_document(cfs, "cfs", citation=f"{name} design"),
    )


def test_effluent_credited_denominator_credits_co_reach_permitted_effluent() -> None:
    """WS-15 (#1615): the dilution denominator can credit the permitted effluent already in the
    reach. A plant sharing its receiving water with other permitted dischargers gets a second,
    effluent-credited ratio; a plant alone on its stream stays at the conservative default."""
    low_flows = {
        "Ottawa River": ProvenancedValue.from_document(0.2, "cfs", citation="Ottawa 7Q10"),
        "Dug Run": ProvenancedValue.from_document(0.78, "cfs", citation="Dug Run 7Q10"),
    }
    balance = WaterBalance(
        nodes=[
            _wwtp("big", "Big WWTP", "Ottawa River", 28.0),
            _wwtp("small", "Small WWTP", "Ottawa River", 4.0),
            _wwtp("lone", "Lone WWTP", "Dug Run", 2.0),
        ],
        warnings=[],
    )
    checks = {c.discharger: c for c in check_assimilative(balance, low_flows)}

    # The conservative default (cited 7Q10 / discharge) is unchanged for every plant.
    small = checks["Small WWTP"]
    assert small.dilution_ratio == pytest.approx(0.2 / 4.0)
    assert small.flag == "violation"
    # Small WWTP shares the Ottawa with Big WWTP: its denominator credits Big's 28 cfs of effluent.
    assert small.upstream_returns is not None
    assert small.upstream_returns.source == "derived"
    assert small.upstream_returns.value == pytest.approx(28.0)
    assert "Big WWTP" in (small.upstream_returns.citation or "")
    assert small.effluent_credited_ratio == pytest.approx((0.2 + 28.0) / 4.0)
    assert small.effluent_credited_flag == dilution_flag(small.effluent_credited_ratio)
    # 7.05:1 — crediting the standing effluent flips it out of the violation band.
    assert small.effluent_credited_flag == "tight"

    # Big WWTP credits Small's 4 cfs, but its own 28 cfs still dwarfs it → stays a violation.
    big = checks["Big WWTP"]
    assert big.upstream_returns is not None and big.upstream_returns.value == pytest.approx(4.0)
    assert big.effluent_credited_ratio == pytest.approx((0.2 + 4.0) / 28.0)
    assert big.effluent_credited_flag == "violation"

    # Lone WWTP is the only permitted discharger on Dug Run → nothing to credit, stays default.
    lone = checks["Lone WWTP"]
    assert lone.upstream_returns is None
    assert lone.effluent_credited_ratio is None
    assert lone.effluent_credited_flag is None
    assert lone.dilution_ratio == pytest.approx(0.78 / 2.0) and lone.flag == "violation"


def test_baseline_credits_lima_effluent_into_shawnee_dilution(hydro_settings: Settings) -> None:
    """On the real Lima loop, Shawnee II discharges into the effluent-laden Ottawa: crediting the
    City of Lima WWTP's ~28.6 cfs standing effluent lifts its 0.04:1 natural ratio into the tight
    band (~6.2:1). The tributary-only American II (Dug Run) has no co-reach effluent to credit."""
    _balance, checks, _findings = run_baseline(settings=hydro_settings, live=True)
    shawnee = next(c for c in checks if "Shawnee" in c.discharger)
    assert shawnee.receiving_water == "Ottawa River"
    assert shawnee.flag == "violation"  # conservative default unchanged
    assert shawnee.upstream_returns is not None
    assert shawnee.upstream_returns.value == pytest.approx(28.62, abs=0.1)  # Lima WWTP 18.5 MGD
    assert shawnee.effluent_credited_ratio is not None
    assert shawnee.effluent_credited_ratio > 1.0
    assert shawnee.effluent_credited_flag == "tight"

    dug = next(c for c in checks if c.receiving_water == "Dug Run")
    assert dug.upstream_returns is None and dug.effluent_credited_ratio is None


def test_balance_locks_bracketed_campus_consumptive(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An undisclosed cooling method is a bracket, never a single headline (CLAUDE.md). When
    # the campus basis is bracketed, the balance carries NO scalar consumptive and says so —
    # it must not leak the evaporative envelope as a headline through the data tier.
    unknown = derive_cooling_basis(cooling_model="unknown")
    assert unknown.is_bracketed
    monkeypatch.setattr(bal, "derive_cooling_basis", lambda *a, **k: unknown)
    balance = bal.build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is None
    joined = " ".join(balance.warnings).lower()
    assert "undisclosed" in joined and "bracket" in joined


def test_abstraction_node_is_profile_driven(hydro_settings: Settings) -> None:
    # The intake node identity comes from the active SiteProfile (#1159). A non-Lima site
    # with no configured abstraction node omits the reach rather than labeling its gage as
    # Lima's WTP — so no "lima-wtp" literal leaks under a second --site.
    fs = hydro_settings.model_copy(update={"site": "findlay"})
    balance = build_water_balance(settings=fs, live=True)
    assert balance.node("lima-wtp") is None
    assert not any(n.node.role == "abstraction" for n in balance.nodes)
    assert any("no abstraction node configured" in w for w in balance.warnings)


def test_water_balance_is_an_inventory_not_a_self_closing_check(hydro_settings: Settings) -> None:
    # WS-05 (#1605): the per-node WaterBalance is an inventory of grounded discharges, not
    # a self-closing balance. The old WaterBalance.closes() was vacuous — no assembled node
    # ever held both `inflow` and `return_flow`, so its loop `continue`d on every node and
    # it returned True unconditionally, was never called, and was never asserted. It is
    # gone; guard against reintroducing a self-test that cannot fail.
    balance = build_water_balance(settings=hydro_settings, live=True)
    assert not hasattr(balance, "closes"), "vacuous WaterBalance.closes() must stay removed"
    # The precondition that made the per-node check vacuous — no node carries both an inflow
    # and a return — confirms the inventory shape the docstring now documents.
    assert not any(n.inflow is not None and n.return_flow is not None for n in balance.nodes)

    # The genuine, falsifiable mass-conservation check lives on the routed network: it routes
    # the balance's return flows through the cited confluence graph and holds only when
    # Sum(base) + Sum(gain) - Sum(applied loss) == outlet flow. Lean on it here (#1605 fix), show
    # it actually fails when the inventory is corrupted.
    from watermark.hydrology import network as net

    rn = net.route_network(balance, consumptive_cfs=0.0, settings=hydro_settings)
    assert rn.closes
    broken = rn.model_copy(update={"outlet_cfs": rn.outlet_cfs + 5.0})
    assert not broken.closes


def test_check_skips_uncited_receiving_water(hydro_settings: Settings) -> None:
    # A receiving water with no cited 7Q10 is skipped, not invented. (All three real
    # streams are now cited, so inject a plant whose receiving water is uncited.)
    balance = build_water_balance(settings=hydro_settings, live=False)
    flows = dict(lowflow.load_low_flows(settings=hydro_settings))
    flows.pop("ottawa river", None)  # drop the Ottawa citation for this check
    checks = check_assimilative(balance, flows)
    assert "Ottawa River" not in {c.receiving_water for c in checks}
    assert assimilative_findings(checks)  # the tributary checks still produced findings
