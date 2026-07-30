"""The receiving-water thermal-discharge screen (epic #1715 Phase 2 / #1717) — the heat-side peer
of test_hydro_toxics.py. Hermetic: runs against the committed cooling / low-flow / criteria data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology import cooling_models, thermal, units
from watermark.hydrology.cooling_models import CoolingParams
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import CoolingModelType

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _offline(site: str = "lima") -> Settings:
    """Offline hydrology settings for ``site``: real repo data + committed connector fixtures, no
    network — the site-parameterized peer of ``conftest.hydro_settings``."""
    return Settings(
        site=site,
        data_dir=_REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=_FIXTURES / "hydrology",
    )


def _flow(s: thermal.ThermalDischargeScreen, label: str) -> thermal.ThermalFlowScreen:
    return next(fs for fs in s.flow_screens if fs.flow_label == label)


# --- reject_heat_load accessor (cooling_models, #1717) ---------------------------------------
def test_reject_heat_load_is_it_times_overhead_with_range() -> None:
    """Lima: 275 MW IT x 1.15 overhead = ~316 MW rejected, carrying the 250-300 MW disclosed band."""
    from watermark.sites import active_profile

    fac = active_profile(_offline()).facility
    assert fac is not None
    reject = cooling_models.reject_heat_load(fac)
    assert reject is not None
    assert reject.source == "derived"  # an [inference], never a permit disclosure
    assert reject.value == pytest.approx(316.2, abs=0.1)
    assert reject.low == pytest.approx(287.5, abs=0.1)  # 250 x 1.15
    assert reject.high == pytest.approx(345.0, abs=0.1)  # 300 x 1.15


def test_reject_heat_load_is_none_without_a_resolvable_facility_load() -> None:
    """No facility (or an all-[open] load) -> None, so Lima's 275 MW fallback never leaks (#1697)."""
    assert cooling_models.reject_heat_load(None) is None


def test_reject_heat_load_honours_a_params_override() -> None:
    reject = cooling_models.reject_heat_load(None, CoolingParams(it_load_mw=100.0))
    assert reject is not None and reject.value == pytest.approx(115.0, abs=0.1)  # 100 x 1.15


# --- physics helpers -------------------------------------------------------------------------
def test_instream_delta_t_matches_the_once_through_condenser_rise() -> None:
    """The heat/flow constant is tied to cooling_models': a reject load over its own once-through
    withdrawal reproduces the ~10 degC condenser ΔT (no drift between the two unit chains)."""
    basis = cooling_models._derive_once_through(None, CoolingParams(it_load_mw=100.0), _offline())
    reject = cooling_models.reject_heat_load(None, CoolingParams(it_load_mw=100.0))
    assert reject is not None
    withdrawal_cfs = units.mgd_to_cfs(basis.makeup_demand.value)
    rise = thermal.instream_delta_t_c(reject.value, withdrawal_cfs)
    assert rise is not None and rise == pytest.approx(cooling_models._OT_DELTA_T_C, abs=0.1)


def test_instream_delta_t_is_none_at_zero_flow_never_inf() -> None:
    assert thermal.instream_delta_t_c(300.0, 0.0) is None  # unbounded, not Inf (toxics parity)
    assert thermal.instream_delta_t_c(300.0, 5.0) is not None


def test_thermal_capacity_is_zero_without_flow_or_headroom() -> None:
    assert thermal.thermal_capacity_mw(0.0, 5.0) == 0.0  # no flow -> no capacity
    assert thermal.thermal_capacity_mw(10.0, 0.0) == 0.0  # ambient at the criterion -> no headroom
    assert thermal.thermal_capacity_mw(10.0, -1.0) == 0.0  # ambient over the criterion
    assert thermal.thermal_capacity_mw(10.0, 2.0) > 0.0


# --- Lima screen -----------------------------------------------------------------------------
def _campus(inv: thermal.ThermalDischargeInventory) -> thermal.ThermalDischargeScreen:
    """The site's own modelled cooling facility (the Phase-2 row)."""
    return next(s for s in inv.modelled)


def test_screen_builds_and_lima_is_a_critical_316a_trigger() -> None:
    inv = thermal.build_screen(_offline())
    assert inv.meta["facility_count"] == len(inv.screens)
    assert inv.meta["modelled_count"] == len(inv.modelled) == 1
    assert inv.meta["critical_count"] == len(inv.flagged)
    s = _campus(inv)
    assert "Project BOSC" in s.facility
    assert s.flag == "critical"
    assert s.kind == thermal.KIND_DATA_CENTER
    assert s.cooling_model == "evaporative_tower" and s.method_disclosed is True


def test_lima_reject_receiving_and_zone_are_resolved() -> None:
    s = _campus(thermal.build_screen(_offline()))
    assert s.reject_heat_mw is not None and s.reject_heat_mw.value == pytest.approx(316.2, abs=0.1)
    assert s.receiving_water == "Ottawa River"
    assert s.zone_id == "lake_erie_basin_general"  # the Ottawa's Lake Erie basin zone
    assert s.zone_rule == "OAC 3745-1-35 Table 35-11 (G)"
    assert s.daily_max_c is not None and s.daily_max_c.value == 29.4  # 85 F peak summer
    assert s.daily_max_c.source == "reference"


def test_ambient_falls_back_to_the_reference_design_ambient_without_the_dmr_read() -> None:
    """No live NWIS 00010 and no DMR read -> the zone seasonal-average criterion, stated as such."""
    s = _campus(thermal.build_screen(_offline(), dmr=False))
    assert s.ambient_c is not None
    assert s.ambient_c.source == "reference"
    assert s.ambient_c.value == pytest.approx(27.8, abs=0.1)  # 82 F seasonal average
    assert s.headroom_c == pytest.approx(1.6, abs=0.1)  # 29.4 - 27.8


def test_the_ottawa_1q10_is_zero_capacity_and_7q10_is_a_huge_computed_exceedance() -> None:
    s = _campus(thermal.build_screen(_offline()))
    one = _flow(s, "1Q10")
    assert one.design_flow.value == 0.0
    assert one.flag == "no_capacity"
    assert one.thermal_capacity_mw == 0.0
    assert one.exceedance_factor is None  # unbounded, never Inf
    seven = _flow(s, "7Q10")
    assert seven.design_flow.value == 0.2
    assert seven.flag == "exceedance"
    assert seven.exceedance_factor is not None and seven.exceedance_factor > 1000
    # The partition-robustness metric: a sliver of the rejection exhausts the whole capacity.
    assert seven.capacity_fraction is not None and seven.capacity_fraction < 0.001


def test_summer_30q10_is_the_least_degenerate_flow_and_still_exceeds() -> None:
    s = _campus(thermal.build_screen(_offline()))
    summer = _flow(s, "summer 30Q10")
    assert summer.design_flow.value == 1.6
    assert summer.flag == "exceedance"
    assert summer.exceedance_factor is not None and summer.exceedance_factor > 100
    # Flows are screened worst (lowest) first.
    assert [fs.flow_label for fs in s.flow_screens] == ["1Q10", "7Q10", "summer 30Q10"]


def test_closed_cycle_blowdown_exemption_is_evaluated_and_not_met_at_lima() -> None:
    s = _campus(thermal.build_screen(_offline()))
    assert s.blowdown_exempt is False  # 2.5 MGD >> 5% of the 0.2 cfs 7Q10
    assert s.blowdown_exempt_note is not None
    assert "NOT exempt" in s.blowdown_exempt_note
    assert "(O)(5)" in s.blowdown_exempt_note


def test_ris_biological_context_is_present_and_sorted_most_sensitive_first() -> None:
    s = _campus(thermal.build_screen(_offline()))
    assert s.ris_checks, "no Great Lakes RIS anchors carried"
    limits = [r.limit_c for r in s.ris_checks]
    assert limits == sorted(limits)  # most heat-sensitive first
    # Lima's mixed temperature is unbounded (no capacity) -> exceeded by construction (None).
    assert all(r.exceeded is None for r in s.ris_checks)


def test_detail_leads_with_the_partition_robust_capacity_ratio() -> None:
    s = _campus(thermal.build_screen(_offline()))
    assert "condenser rejection" in s.detail
    assert "exhausts the capacity" in s.detail
    assert "[critical]" in s.detail


# --- flag rollup -----------------------------------------------------------------------------
def _exceeding_flow() -> thermal.ThermalFlowScreen:
    return thermal.ThermalFlowScreen(
        flow_label="7Q10",
        design_flow=ProvenancedValue.from_document(0.2, "cfs", "test"),
        thermal_capacity_mw=0.04,
        delta_t_c=None,
        mixed_c=None,
        exceedance_factor=8000.0,
        capacity_fraction=0.0001,
        flag="exceedance",
    )


def test_disclosed_method_exceedance_is_critical_but_unknown_method_caps_at_elevated() -> None:
    reject = ProvenancedValue.derived(300.0, "MW", "test")
    flows = [_exceeding_flow()]
    disclosed = thermal._facility_flag(
        reject,
        "Ottawa River",
        CoolingModelType.EVAPORATIVE_TOWER,
        3.9,
        flows,
        blowdown_exempt=False,
    )
    undisclosed = thermal._facility_flag(
        reject, "Ottawa River", CoolingModelType.UNKNOWN, 0.0, flows, blowdown_exempt=None
    )
    assert disclosed == "critical"  # method on record -> a genuine §316(a) trigger
    assert undisclosed == "elevated"  # cooling method undisclosed -> not asserted as critical


def test_flag_rollup_edges() -> None:
    reject = ProvenancedValue.derived(300.0, "MW", "test")
    flows = [_exceeding_flow()]
    # No heat load / no receiving water -> uncharacterized.
    assert (
        thermal._facility_flag(
            None, "Ottawa River", CoolingModelType.EVAPORATIVE_TOWER, 0.0, [], None
        )
        == "uncharacterized"
    )
    assert (
        thermal._facility_flag(reject, None, CoolingModelType.EVAPORATIVE_TOWER, 0.0, [], None)
        == "uncharacterized"
    )
    # Dry / no-discharge archetype -> dry (heat to air, ~none to water).
    assert (
        thermal._facility_flag(reject, "R", CoolingModelType.CLOSED_LOOP_DRY, 0.0, flows, None)
        == "dry"
    )
    # A closed-cycle blowdown under the 5%-of-7Q10 exemption -> exempt.
    assert (
        thermal._facility_flag(reject, "R", CoolingModelType.EVAPORATIVE_TOWER, 0.001, flows, True)
        == "exempt"
    )


# --- portability / graceful degradation ------------------------------------------------------
def test_screen_degrades_for_a_peer_site_without_crashing() -> None:
    """A non-Lima site must degrade, not break (the network baseline) — no crash, coherent meta."""
    inv = thermal.build_screen(_offline("fort-wayne"))
    assert inv.meta["site"] == "fort-wayne"
    assert inv.meta["facility_count"] == len(inv.screens)
    for s in inv.screens:
        assert s.flag in {"critical", "elevated", "exempt", "dry", "context", "uncharacterized"}


# --- Phase 3 (#1718): the reported record ------------------------------------------------------
def _by_npdes(inv: thermal.ThermalDischargeInventory, npdes: str) -> thermal.ThermalDischargeScreen:
    return next(s for s in inv.observed if s.npdes_id == npdes)


def test_corridor_cohort_is_resolved_on_the_toxics_receiving_water_ladder() -> None:
    """The reach's permits: ECHO-cited receiving water, else the corridor coordinate cluster.

    Lima's Ottawa corridor box holds six: the refinery and the WWTP carry a cited "Ottawa River"
    (`connector`), the rest are inside the box with no cited receiving water (`assumption`). A
    permit ECHO cites to a *different* water body is excluded, never re-pointed onto this reach.
    """
    permits = thermal._corridor_permits(_offline())
    by_id = {p.npdes_id: p for p in permits}
    assert {"OH0002623", "OH0026069", "OH0002615"} <= set(by_id)
    assert by_id["OH0002623"].source == "connector"  # ECHO cites OTTAWA RIVER
    assert by_id["OH0026069"].source == "connector"  # cited via the #1698 curation overlay
    assert by_id["OH0002615"].source == "assumption"  # corridor cluster; ECHO carries no water
    assert "industrial corridor" in by_id["OH0002615"].citation
    assert all(p.receiving_water == "Ottawa River" for p in permits)


def test_a_peer_site_resolves_no_corridor_cohort_rather_than_leaking_limas() -> None:
    """The cohort is basin- + corridor-scoped, so a peer never inherits the Ottawa's permits."""
    assert [p.npdes_id for p in thermal._corridor_permits(_offline("fort-wayne"))] != [
        p.npdes_id for p in thermal._corridor_permits(_offline())
    ]


def test_design_ambient_prefers_the_reachs_own_reported_instream_monitoring() -> None:
    """The WWTP's downstream station (24.0 degC) beats the 27.8 degC reference design ambient —
    real data CALIBRATES the screen, and here it makes it less severe, not more."""
    inv = thermal.build_screen(_offline())
    s = _campus(inv)
    assert s.ambient_c is not None
    assert s.ambient_c.source == "connector"
    assert s.ambient_c.value == pytest.approx(24.0, abs=0.01)
    assert s.headroom_c == pytest.approx(5.4, abs=0.01)  # vs 1.6 on the reference ambient
    assert inv.meta["observed_instream_station"] == "OH0026069 outfall 901 (Downstream Monitoring)"
    assert inv.meta["reference_ambient_c"] == pytest.approx(27.8, abs=0.1)


def test_lima_refinery_reports_an_effluent_over_ohios_own_criterion() -> None:
    """The headline observation: the corridor's warmest discharger reports 32.2 degC daily-max
    effluent — 2.8 degC OVER the 29.4 degC criterion — and outfall 001 carries no numeric limit."""
    s = _by_npdes(thermal.build_screen(_offline()), "OH0002623")
    assert s.kind == thermal.KIND_PERMITTED
    assert s.facility_type == "NON-POTW"
    assert s.dmr is not None
    assert s.dmr.outfall == "001"
    assert s.dmr.parameter_code == "00011"  # reported in Fahrenheit, converted here
    assert s.dmr.effluent_c is not None
    assert s.dmr.effluent_c.value == pytest.approx(32.22, abs=0.01)
    assert s.dmr.effluent_c.source == "connector"
    assert s.dmr.over_criterion is True
    assert s.dmr.flow is not None and s.dmr.flow.value == pytest.approx(3.7, abs=0.01)
    # The numeric ceiling sits on a different outfall than the one that actually discharges.
    assert s.dmr.permitted_limit_outfall == "003"
    assert s.dmr.permitted_limit_c is not None
    assert s.dmr.permitted_limit_c.value == pytest.approx(29.44, abs=0.01)


def test_an_observed_heat_load_is_screened_like_a_modelled_one() -> None:
    """rho*cp*Q_reported*(T_reported - ambient) at the same reach, flows and criterion."""
    s = _by_npdes(thermal.build_screen(_offline()), "OH0002623")
    assert s.reject_heat_mw is None  # no condenser model: the load is measured, not derived
    assert s.instream_heat_mw is not None
    assert s.instream_heat_mw.value == pytest.approx(5.58, abs=0.05)
    assert s.instream_heat_mw.source == "derived"
    seven = _flow(s, "7Q10")
    # At the 0.2 cfs 7Q10 the reach below the outfall is essentially the effluent.
    assert seven.mixed_c is not None and seven.mixed_c.value == pytest.approx(31.9, abs=0.2)
    assert seven.mixed_over_criterion is True
    assert s.flag == "critical"


def test_a_large_barely_warm_discharge_is_not_called_critical_on_the_loading_ratio() -> None:
    """The Lima WWTP's 12.8 MGD at 25.4 degC reads ~26x the reach's loading CAPACITY but mixes to
    25.4 degC — under the 29.4 degC criterion. Ohio's criterion is a temperature, so the
    temperature is the test; flagging this `critical` would be alarmist and rebuttable."""
    s = _by_npdes(thermal.build_screen(_offline()), "OH0026069")
    seven = _flow(s, "7Q10")
    assert seven.exceedance_factor is not None and seven.exceedance_factor > 20
    assert seven.mixed_c is not None and seven.mixed_c.value < 29.4
    assert seven.mixed_over_criterion is False
    assert seven.headroom_fraction is not None and seven.headroom_fraction < 1.0
    assert seven.flag == "approach"
    assert s.flag == "elevated"


def test_the_ambient_station_owner_declares_the_circularity() -> None:
    """The design ambient comes from the WWTP's own downstream station, so its own screen says so
    rather than presenting the comparison as independent."""
    s = _by_npdes(thermal.build_screen(_offline()), "OH0026069")
    assert s.dmr is not None and s.dmr.note is not None
    assert "this permit's OWN in-stream station" in s.dmr.note
    assert "already warmed" in s.dmr.note


def test_a_permit_with_no_reported_temperature_is_a_cited_absence() -> None:
    s = _by_npdes(thermal.build_screen(_offline()), "OHGC02549")
    assert s.flag == "uncharacterized"
    assert s.instream_heat_mw is None
    assert s.dmr is not None and s.dmr.n_obs == 0
    assert s.dmr.note is not None and "cited absence" in s.dmr.note


def test_monitor_only_permits_are_named_in_the_meta() -> None:
    """A permit that monitors temperature but sets no numeric limit is a finding, not a blank."""
    meta = thermal.build_screen(_offline()).meta
    assert "OH0002615" in meta["monitor_only_permits"]  # PCS Nitrogen: reported, uncapped
    assert set(meta["permits_over_daily_max_criterion"]) == {"OH0002623", "OH0002615"}


# --- Phase 3 (#1718): cooling scenarios --------------------------------------------------------
def _scenario(s: thermal.ThermalDischargeScreen, name: str) -> thermal.ThermalScenario:
    return next(sc for sc in s.scenarios if sc.scenario == name)


def test_every_heat_partition_scenario_still_exceeds_the_reach() -> None:
    """The robustness claim, quantified: the partition spans two orders of magnitude (100% of the
    rejection once-through vs ~1% via blowdown) and every scenario exceeds the criterion."""
    s = _campus(thermal.build_screen(_offline()))
    names = [sc.scenario for sc in s.scenarios]
    assert names == [
        thermal.SCENARIO_BOUND,
        thermal.SCENARIO_ONCE_THROUGH,
        thermal.SCENARIO_EVAPORATIVE,
    ]
    assert all(sc.flag == "critical" for sc in s.scenarios)
    evaporative = _scenario(s, thermal.SCENARIO_EVAPORATIVE)
    assert evaporative.instream_fraction is not None and evaporative.instream_fraction < 0.05
    assert evaporative.instream_heat_mw is not None
    assert evaporative.instream_heat_mw.value == pytest.approx(3.77, abs=0.05)


def test_once_through_mixes_to_the_condenser_rise_above_ambient() -> None:
    """Once-through's whole withdrawal dwarfs the design low flow, so the reach becomes the
    discharge: ambient + the ~10 degC condenser rise, over the criterion and near walleye acute."""
    s = _campus(thermal.build_screen(_offline()))
    ot = _scenario(s, thermal.SCENARIO_ONCE_THROUGH)
    assert ot.instream_fraction == 1.0
    assert ot.effluent_c is not None and ot.effluent_c.value == pytest.approx(34.0, abs=0.2)
    seven = next(fs for fs in ot.flow_screens if fs.flow_label == "7Q10")
    assert seven.mixed_c is not None and seven.mixed_c.value == pytest.approx(34.0, abs=0.2)
    assert seven.mixed_over_criterion is True


def test_the_evaporative_scenario_is_calibrated_to_an_observed_corridor_analog() -> None:
    """The campus holds no discharge permit, so its blowdown temperature is an [inference] by
    analogy to the corridor's own warmest reported effluent — labelled as such, never as its own."""
    s = _campus(thermal.build_screen(_offline()))
    evaporative = _scenario(s, thermal.SCENARIO_EVAPORATIVE)
    assert evaporative.effluent_c is not None
    assert evaporative.effluent_c.value == pytest.approx(32.2, abs=0.1)
    assert "OH0002623" in (evaporative.effluent_c.citation or "")
    assert "analogy" in (evaporative.effluent_c.citation or "")
    assert "no discharge permit of its own" in evaporative.basis


def test_calibration_grades_the_model_against_the_record() -> None:
    s = _campus(thermal.build_screen(_offline()))
    assert s.calibration is not None
    c = s.calibration
    assert c.verdict == thermal._VERDICT_CONSISTENT
    assert c.modeled_effluent_c == pytest.approx(34.0, abs=0.2)
    assert c.observed_effluent_c == pytest.approx(32.22, abs=0.01)
    assert c.observed_source is not None and "OH0002623" in c.observed_source
    assert c.ambient_delta_c == pytest.approx(3.8, abs=0.1)  # reference 27.8 - observed 24.0


def test_no_dmr_read_restores_the_phase_2_screen() -> None:
    """`--no-dmr` is the pure-offline Phase-2 read: no connector call, no observed dischargers,
    no scenarios, and the stated reference design ambient."""
    inv = thermal.build_screen(_offline(), dmr=False)
    assert inv.observed == []
    assert inv.meta["dmr_window"] is None
    assert inv.meta["corridor_permits"] == 0
    s = _campus(inv)
    assert s.scenarios == []
    assert s.calibration is None
    assert s.dmr is None


# --- Phase-3 review fixes ----------------------------------------------------------------------
def test_a_limit_on_another_outfall_is_never_read_as_this_outfalls_exceedance() -> None:
    """The Lima Refinery's only numeric thermal limit (85 degF) sits on outfall 003, which did not
    discharge; outfall 001 — the one screened — carries none. Comparing 001's 32.2 degC against
    003's ceiling would assert a permit-limit exceedance that has not occurred."""
    s = _by_npdes(thermal.build_screen(_offline()), "OH0002623")
    assert s.dmr is not None
    assert s.dmr.outfall == "001"
    assert s.dmr.permitted_limit_outfall == "003"  # the limit is kept, with its outfall named
    assert s.dmr.permitted_limit_c is not None
    assert s.dmr.over_permitted_limit is None  # not True — the limit does not bind this outfall
    # ...and the outfall that actually discharges is monitor-only, which is the sharper finding.
    assert s.dmr.monitor_only is True
    assert s.dmr.note is not None
    assert "does not bind this discharge" in s.dmr.note


def test_notes_are_joined_as_sentences() -> None:
    """Two independently-written clauses must not run together mid-sentence."""
    assert thermal._join_notes("first clause", "second clause") == "first clause. second clause."
    assert thermal._join_notes("already punctuated.", "next") == "already punctuated. next."
    assert thermal._join_notes(None, "only one") == "only one."
    assert thermal._join_notes(None, "") is None
    # The live case: the monitor-only note and the circular-ambient note on the same row.
    note = _by_npdes(thermal.build_screen(_offline()), "OH0026069").dmr
    assert note is not None and note.note is not None
    assert "not capped. The design ambient" in note.note


def test_a_permit_whose_record_cannot_be_read_still_gets_a_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pull failure must not shrink the corridor silently — the permit is reported as
    uncharacterized, with the gap attributed to this pull rather than to the permit."""
    from watermark.hydrology.connectors import echo_dmr

    real = echo_dmr.fetch_thermal_record

    def flaky(npdes_id: str, **kwargs: object) -> echo_dmr.ThermalDmrRecord:
        if npdes_id == "OH0002615":
            raise echo_dmr.EchoDmrError("simulated ECHO outage")
        return real(npdes_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(echo_dmr, "fetch_thermal_record", flaky)
    inv = thermal.build_screen(_offline())
    # Every permit on the reach still has a row, so the counts reconcile.
    assert len(inv.observed) == inv.meta["corridor_permits"]
    s = _by_npdes(inv, "OH0002615")
    assert s.flag == "uncharacterized"
    assert s.instream_heat_mw is None
    assert s.dmr is not None and s.dmr.note is not None
    assert "could not be read" in s.dmr.note
    assert "NOT a finding about the permit" in s.dmr.note
