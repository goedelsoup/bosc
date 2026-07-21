"""The three-method compute-capacity derivation, the bracket, and provenance."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.facility.compute import (
    _it_load_from_consumptive_mgd,
    _rack_floor_area_sqft,
    derive_compute_capacity,
)


def test_method1_power_is_permit_grounded(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # Method 1 (primary): the IT load is the ~275 MW N+1 inference from the air-permit backup —
    # [inference] (derived), not permit-disclosed (#1697), carrying the permit citation as basis.
    assert cap.it_load_power.value == pytest.approx(275.0)
    assert cap.it_load_power.source == "derived"
    assert "P0138965" in (cap.it_load_power.citation or "")


def test_method2_water_backsolve_recovers_method1(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # The low (power x WUE) cooling figure inverts back to ~275 MW — the loop closes.
    assert cap.it_load_water_low.value == pytest.approx(275.0, abs=2.0)
    assert cap.it_load_water_low.source == "derived"
    # The FM-2 high is a flagged upper bound, larger than the power method.
    assert cap.it_load_water_high.value > cap.it_load_power.value
    assert cap.it_load_water_high.confidence == "low"
    assert "UPPER BOUND" in (cap.it_load_water_high.citation or "")


def test_water_backsolve_inverts_cooling_basis() -> None:
    # 3.14 MGD at 1.8 L/kWh -> ~275 MW (the cooling.py forward calc, inverted).
    assert _it_load_from_consumptive_mgd(3.14, 1.8) == pytest.approx(275.1, abs=1.0)


def test_method2_uses_the_basis_wue_not_a_fixed_constant(
    facility_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A facility that overrides WUE derives its cooling consumptive with that WUE;
    # Method-2 must invert with the *same* WUE so it round-trips to the facility's own
    # IT load — not a fixed 1.8 that silently disagrees with the basis (#1169).
    import watermark.sites as sites

    lima = sites.SITES["lima"]
    assert lima.facility is not None
    override_facility = lima.facility.model_copy(
        update={"wue_l_per_kwh": 2.6, "wue_citation": "test override"}
    )
    monkeypatch.setitem(
        sites.SITES, "lima", lima.model_copy(update={"facilities": (override_facility,)})
    )

    cap = derive_compute_capacity(settings=facility_settings)
    # With the fix the loop still closes; with the old fixed 1.8 the 2.6 basis would
    # invert to ~397 MW, well outside this tolerance.
    assert cap.it_load_water_low.value == pytest.approx(cap.it_load_power.value, abs=2.0)
    assert "2.6 L/kWh" in (cap.it_load_water_low.citation or "")


def test_method2_once_through_recovers_load_from_withdrawal(
    facility_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A once-through facility's consumptive is ~1-2% forced evaporation of its withdrawal,
    # not it_load x WUE. Inverting it with a tower WUE (the old None-> 1.8 fallback) would
    # badly understate the load; Method-2 must recover it from the withdrawal's heat-
    # rejection basis instead, closing the loop to the facility's own IT load.
    import watermark.sites as sites
    from watermark.sites import CoolingModelType

    lima = sites.SITES["lima"]
    assert lima.facility is not None
    once_through = lima.facility.model_copy(update={"cooling_model": CoolingModelType.ONCE_THROUGH})
    monkeypatch.setitem(
        sites.SITES, "lima", lima.model_copy(update={"facilities": (once_through,)})
    )

    cap = derive_compute_capacity(settings=facility_settings)
    assert cap.it_load_water_low.value == pytest.approx(cap.it_load_power.value, abs=2.0)
    assert cap.it_load_water_high.value == pytest.approx(cap.it_load_power.value, abs=2.0)
    assert "once-through withdrawal" in (cap.it_load_water_low.citation or "")


def test_method3_footprint_is_weakest_and_flagged(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # Footprint is an assumption (not document/derived) and dwarfs the power method —
    # it bounds the physical envelope, confirming power is the binding constraint.
    assert cap.it_load_footprint_low.source == "assumption"
    assert cap.it_load_footprint_high.source == "assumption"
    assert cap.it_load_footprint_low.value > cap.it_load_power.value
    assert "LAND != FLOOR AREA" in (cap.it_load_footprint_low.citation or "")


def test_methods1_and_2low_agree(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # The robust agreement: the operative power figure and the water-low cross-check
    # land within a couple MW of each other.
    assert abs(cap.it_load_water_low.value - cap.it_load_power.value) < 2.0


def test_cross_method_bracket(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    assert cap.it_load_bracket_low.value <= cap.it_load_power.value
    assert cap.it_load_bracket_high.value >= cap.it_load_footprint_high.value
    assert cap.it_load_bracket_low.source == "derived"


def test_scenarios_cover_gpus_and_tpus(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    names = {s.spec.name for s in cap.scenarios}
    # Both NVIDIA and Google TPU options are present (end user is Google).
    assert {"H100-SXM5", "B200", "GB200-NVL72"} <= names
    assert {"TPU-v5e", "TPU-v5p", "TPU-v6e"} <= names
    vendors = {s.spec.vendor for s in cap.scenarios}
    assert vendors == {"NVIDIA", "Google"}


def test_scenario_counts_and_flops_are_derived_ranges(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    h100 = cap.scenario("H100-SXM5")
    assert h100 is not None
    # Count is a derived range (low <= central <= high), conditional on the chip.
    assert h100.count_low.value < h100.count_central.value < h100.count_high.value
    assert h100.count_low.source == "derived"
    # Power-method H100 count lands at hyperscale-AI scale (~100k-250k accelerators).
    assert 100_000 < h100.count_central.value < 300_000
    # Aggregate peak dense BF16 is well into the hundreds of EFLOP/s.
    assert h100.bf16_dense_eflops_high.value > 100.0
    # A more power-dense chip (B200) yields fewer accelerators but more FLOPS.
    b200 = cap.scenario("B200")
    assert b200 is not None
    assert b200.count_central.value < h100.count_central.value
    assert b200.bf16_dense_eflops_high.value > h100.bf16_dense_eflops_high.value


def test_delivered_throughput_is_derated_and_separate(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    assert cap.mfu.source == "assumption"
    h100 = cap.scenario("H100-SXM5")
    assert h100 is not None and h100.bf16_delivered_eflops_central is not None
    # Delivered (MFU-derated) is strictly below the central peak between low and high.
    assert h100.bf16_delivered_eflops_central.value < h100.bf16_dense_eflops_high.value


def test_equivalent_h100_figure(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # The cross-scenario unit equals the H100 scenario's own count range (by construction).
    h100 = cap.scenario("H100-SXM5")
    assert h100 is not None
    assert cap.equivalent_h100_low.value == pytest.approx(h100.count_low.value, abs=1)
    assert cap.equivalent_h100_high.value == pytest.approx(h100.count_high.value, abs=1)


def test_overrides_tag_fraction_and_scale_counts(facility_settings: Settings) -> None:
    base = derive_compute_capacity(settings=facility_settings)
    lower = derive_compute_capacity(
        settings=facility_settings, accelerator_power_fraction=(0.3, 0.4)
    )
    # A lower accelerator-power fraction yields fewer accelerators.
    b_h100 = base.scenario("H100-SXM5")
    l_h100 = lower.scenario("H100-SXM5")
    assert b_h100 is not None and l_h100 is not None
    assert l_h100.count_high.value < b_h100.count_high.value
    assert "[override]" in (lower.accelerator_power_fraction_low.citation or "")


def test_profiles_are_chip_level_overhead_scenarios(facility_settings: Settings) -> None:
    """Issue #89: per-data-center-profile chip-level overhead, ≥2 profiles, default kept."""
    cap = derive_compute_capacity(settings=facility_settings)
    names = {p.name for p in cap.profiles}
    assert {"air-hgx", "liquid-gb200-nvl72"} <= names  # ≥2 named profiles
    assert len(cap.profiles) >= 2

    for p in cap.profiles:
        # Overhead is split into a host + network share (assumptions); total is derived.
        assert p.host_overhead.source == "assumption"
        assert p.network_overhead.source == "assumption"
        assert p.total_overhead.source == "derived"
        assert p.total_overhead.value == pytest.approx(
            p.host_overhead.value * p.network_overhead.value, abs=1e-4
        )
        # All-in W and the equivalent-H100 count are derived from the overhead.
        assert p.reference_all_in_w.source == "derived"
        assert p.equivalent_h100_central.source == "derived"

    # A lower-overhead liquid profile fits MORE accelerators than the air-cooled one.
    air = cap.profile("air-hgx")
    gb200 = cap.profile("liquid-gb200-nvl72")
    assert air is not None and gb200 is not None
    assert gb200.total_overhead.value < air.total_overhead.value
    assert gb200.equivalent_h100_central.value > air.equivalent_h100_central.value

    # The default single-overhead per-chip behavior is preserved (H100 all-in = 700 x 1.30).
    h100 = cap.scenario("H100-SXM5")
    assert h100 is not None
    assert h100.spec.all_in_w.value == pytest.approx(910.0)  # round(700 x 1.30)


def test_rack_profile_geometry_drives_floor_area(facility_settings: Settings) -> None:
    """Issue #88: per-rack floor area is derived from rack geometry; depth changes it."""
    cap = derive_compute_capacity(settings=facility_settings)
    # The committed rack_profile (non-standard 1200mm depth) -> ~33 sqft, derived.
    assert cap.rack_floor_area_sqft is not None
    assert cap.rack_floor_area_sqft.source == "derived"
    assert cap.rack_floor_area_sqft.value == pytest.approx(33.3, abs=0.2)
    assert "non-standard" in (cap.rack_floor_area_sqft.citation or "")

    # Non-standard (extended) depth is representable and CHANGES the floor area: the
    # same rack at the standard 1070mm depth yields a smaller per-rack area (~30 sqft).
    common = {"width_mm": 600, "aisle_factor": 4.3, "standard_depth_mm": 1070}
    extended, ext_flag, _ = _rack_floor_area_sqft(
        {"rack_profile": {**common, "depth_mm": 1200, "non_standard_depth": True}}
    )
    standard, std_flag, _ = _rack_floor_area_sqft(
        {"rack_profile": {**common, "depth_mm": 1070, "non_standard_depth": False}}
    )
    assert ext_flag is True and std_flag is False
    assert extended > standard
    assert standard == pytest.approx(29.7, abs=0.3)  # reproduces the legacy ~30 sqft scalar

    # Fallback: no rack_profile -> the bare footprint scalar, flagged standard.
    fallback, fb_flag, _ = _rack_floor_area_sqft({"footprint": {"rack_area_sqft": 30.0}})
    assert fallback == pytest.approx(30.0) and fb_flag is False


def test_every_output_is_provenance_tagged(facility_settings: Settings) -> None:
    cap = derive_compute_capacity(settings=facility_settings)
    # Nothing is presented without a source tag; the IT load is an [inference] (derived from
    # the air-permit backup by N+1), never presented as a permit disclosure (#1697).
    assert cap.it_load_power.source == "derived"
    for s in cap.scenarios:
        assert s.spec.tdp_w.source == "reference"
        assert s.spec.all_in_w.source == "derived"
        assert s.count_central.source == "derived"
        assert s.bf16_dense_eflops_high.source == "derived"
