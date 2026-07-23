"""The receiving-water thermal-discharge screen (epic #1715 Phase 2 / #1717) — the heat-side peer
of test_hydro_toxics.py. Hermetic: runs against the committed cooling / low-flow / criteria data.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import cooling_models, thermal, units
from watermark.hydrology.cooling_models import CoolingParams
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import CoolingModelType


def _offline(site: str = "lima") -> Settings:
    return Settings(site=site, hydro_offline=True)


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
def test_screen_builds_and_lima_is_a_critical_316a_trigger() -> None:
    inv = thermal.build_screen(_offline())
    assert inv.meta["facility_count"] == len(inv.screens) == 1
    assert inv.meta["critical_count"] == len(inv.flagged) == 1
    s = inv.screens[0]
    assert "Shawnee" in s.facility
    assert s.flag == "critical"
    assert s.cooling_model == "evaporative_tower" and s.method_disclosed is True


def test_lima_reject_receiving_and_zone_are_resolved() -> None:
    s = thermal.build_screen(_offline()).screens[0]
    assert s.reject_heat_mw is not None and s.reject_heat_mw.value == pytest.approx(316.2, abs=0.1)
    assert s.receiving_water == "Ottawa River"
    assert s.zone_id == "lake_erie_basin_general"  # the Ottawa's Lake Erie basin zone
    assert s.zone_rule == "OAC 3745-1-35 Table 35-11 (G)"
    assert s.daily_max_c is not None and s.daily_max_c.value == 29.4  # 85 F peak summer
    assert s.daily_max_c.source == "reference"


def test_ambient_falls_back_to_the_reference_design_ambient_offline() -> None:
    """No live NWIS 00010 offline -> the zone seasonal-average criterion as a stated design ambient."""
    s = thermal.build_screen(_offline()).screens[0]
    assert s.ambient_c is not None
    assert s.ambient_c.source == "reference"
    assert s.ambient_c.value == pytest.approx(27.8, abs=0.1)  # 82 F seasonal average
    assert s.headroom_c == pytest.approx(1.6, abs=0.1)  # 29.4 - 27.8


def test_the_ottawa_1q10_is_zero_capacity_and_7q10_is_a_huge_computed_exceedance() -> None:
    s = thermal.build_screen(_offline()).screens[0]
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
    s = thermal.build_screen(_offline()).screens[0]
    summer = _flow(s, "summer 30Q10")
    assert summer.design_flow.value == 1.6
    assert summer.flag == "exceedance"
    assert summer.exceedance_factor is not None and summer.exceedance_factor > 100
    # Flows are screened worst (lowest) first.
    assert [fs.flow_label for fs in s.flow_screens] == ["1Q10", "7Q10", "summer 30Q10"]


def test_closed_cycle_blowdown_exemption_is_evaluated_and_not_met_at_lima() -> None:
    s = thermal.build_screen(_offline()).screens[0]
    assert s.blowdown_exempt is False  # 2.5 MGD >> 5% of the 0.2 cfs 7Q10
    assert s.blowdown_exempt_note is not None
    assert "NOT exempt" in s.blowdown_exempt_note
    assert "(O)(5)" in s.blowdown_exempt_note


def test_ris_biological_context_is_present_and_sorted_most_sensitive_first() -> None:
    s = thermal.build_screen(_offline()).screens[0]
    assert s.ris_checks, "no Great Lakes RIS anchors carried"
    limits = [r.limit_c for r in s.ris_checks]
    assert limits == sorted(limits)  # most heat-sensitive first
    # Lima's mixed temperature is unbounded (no capacity) -> exceeded by construction (None).
    assert all(r.exceeded is None for r in s.ris_checks)


def test_detail_leads_with_the_partition_robust_capacity_ratio() -> None:
    s = thermal.build_screen(_offline()).screens[0]
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
