"""Refill adequacy: the pure sequent-peak/flow-duration math (synthetic) + the committed
drought storage-requirement artifact (offline)."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.hydrology import refill

# ----------------------------------------------------------- pure algorithm


def test_sequent_peak_accumulates_the_worst_deficit() -> None:
    # demand 10; three deficit days (net +8 each) then surplus refills.
    avail = [2.0, 2.0, 2.0, 20.0, 20.0]
    required, start, length = refill._sequent_peak(avail, demand_mgd=10.0)
    assert required == pytest.approx(24.0)  # 8 + 8 + 8
    assert start == 0 and length == 3


def test_sequent_peak_zero_when_supply_always_meets_demand() -> None:
    required, _start, length = refill._sequent_peak([12.0, 15.0, 11.0], demand_mgd=10.0)
    assert required == 0.0 and length == 0


def test_sequent_peak_picks_the_largest_of_two_spells() -> None:
    # a small early deficit (net +3) then a bigger later one (net +5 x2 = 10).
    avail = [7.0, 20.0, 5.0, 5.0, 20.0]
    required, start, length = refill._sequent_peak(avail, demand_mgd=10.0)
    assert required == pytest.approx(10.0)
    assert start == 2 and length == 2  # the second, deeper spell wins


def test_exceedance_reads_low_flow_tail() -> None:
    asc = [float(v) for v in range(1, 101)]  # 1..100 ascending
    assert refill._exceedance(asc, 0.5) == pytest.approx(50.0, abs=1.0)  # median
    assert refill._exceedance(asc, 0.90) == pytest.approx(10.0, abs=1.0)  # exceeded 90% of days
    assert refill._exceedance(asc, 0.99) == pytest.approx(1.0, abs=1.0)


# ------------------------------------------------- committed artifact (offline)


def test_committed_refill_artifact_is_well_formed(hydro_settings: Settings) -> None:
    ra = refill.load_refill_adequacy(settings=hydro_settings)
    assert ra is not None, "data/reference/hydrology/refill-adequacy.yaml must be committed"
    assert len(ra.rivers) == 2
    assert {r.site_no for r in ra.rivers} == {"04186500", "04187100"}
    assert ra.storage_capacity_mg == pytest.approx(14413.0, abs=1.0)
    # Normal-year supply dwarfs demand.
    assert ra.annual_supply_multiple > 1.0
    assert ra.caveats  # the optimism caveats are recorded


def test_campus_raises_the_drought_storage_requirement(hydro_settings: Settings) -> None:
    ra = refill.load_refill_adequacy(settings=hydro_settings)
    assert ra is not None
    base = ra.scenario("baseline city")
    campus = ra.scenario("+campus (central)")
    high = ra.scenario("+campus (high bound)")
    assert base is not None and campus is not None and high is not None
    # The campus demand raises the storage the worst drought calls on.
    assert campus.required_storage_mg > base.required_storage_mg
    assert high.required_storage_mg > campus.required_storage_mg
    assert campus.pct_of_capacity > base.pct_of_capacity
    # All three survive the gauged record (required < the committed storage capacity).
    assert base.survives and campus.survives and high.survives
    assert campus.worst_spell_start is not None and campus.worst_spell_days > 0


def test_refill_findings_cover_normal_drought_and_residual_risk(hydro_settings: Settings) -> None:
    ra = refill.load_refill_adequacy(settings=hydro_settings)
    assert ra is not None
    findings = refill.refill_findings(ra)
    checks = {f.check for f in findings}
    assert {
        "refill-annual-surplus",
        "refill-drought-drawdown",
        "refill-margin-erosion",
        "refill-extended-drought",
    } <= checks
    annual = next(f for f in findings if f.check == "refill-annual-surplus")
    assert annual.ok  # refill adequate in a normal year
    drought = next(f for f in findings if f.check == "refill-drought-drawdown")
    assert drought.ok  # survives the worst gauged drought


def test_pipeline_run_refill(hydro_settings: Settings) -> None:
    from bosc.pipeline import hydrology as hydro_stage

    ra, findings = hydro_stage.run_refill(settings=hydro_settings)
    assert ra is not None
    assert len(ra.scenarios) == 3
    assert findings
