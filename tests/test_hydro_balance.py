"""End-to-end water balance + low-flow assimilative screen, and the provenance invariant."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import balance as bal
from watermark.hydrology import lowflow
from watermark.hydrology.assimilative import assimilative_findings, check_assimilative
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

    # Three county WWTPs with document design flows; the abstraction reach is live.
    assert len(balance.by_role("wwtp")) == 3
    abstraction = balance.node("lima-wtp")
    assert abstraction is not None and abstraction.inflow is not None
    assert abstraction.inflow.source == "connector"  # grounded by the NWIS fixture

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


def test_check_skips_uncited_receiving_water(hydro_settings: Settings) -> None:
    # A receiving water with no cited 7Q10 is skipped, not invented. (All three real
    # streams are now cited, so inject a plant whose receiving water is uncited.)
    balance = build_water_balance(settings=hydro_settings, live=False)
    flows = dict(lowflow.load_low_flows(settings=hydro_settings))
    flows.pop("ottawa river", None)  # drop the Ottawa citation for this check
    checks = check_assimilative(balance, flows)
    assert "Ottawa River" not in {c.receiving_water for c in checks}
    assert assimilative_findings(checks)  # the tributary checks still produced findings
