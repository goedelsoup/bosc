"""The Maumee-at-Waterville (04193500) continuous-monitor read against the Napoleon spill.

Two layers, both hermetic: the NWIS instantaneous-value connector parsing the committed
event fixture, and the attribution-disciplined read built on top of it (#1498).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from watermark.config import Settings
from watermark.hydrology import waterville_monitor as wm
from watermark.hydrology.connectors import nwis
from watermark.hydrology.models import ContinuousMonitorRead, ProvenancedValue

# ------------------------------------------------------- the IV connector


def test_pcode_constants_do_not_confuse_chlorophyll_and_phycocyanin() -> None:
    # The bug #1498's brief made: 32316 is chlorophyll-a, not phycocyanin.
    assert nwis.PHYCOCYANIN_UG_L == "32319"
    assert wm.CHLOROPHYLL_A_UG_L == "32316"
    assert nwis.PHYCOCYANIN_UG_L != wm.CHLOROPHYLL_A_UG_L


def test_fetch_instantaneous_series_parses_the_event_fixture(hydro_settings: Settings) -> None:
    series = wm.load_event_series(settings=hydro_settings)
    by = {s.parameter_cd: s for s in series}
    assert set(by) == set(wm.EVENT_PARAMS)

    turb = by[nwis.TURBIDITY_FNU]
    assert "Turbidity" in turb.variable_name
    assert turb.unit == "FNU"
    # dense sub-daily record, ascending, no-data already dropped
    assert len(turb) > 1000
    assert turb.timestamps == sorted(turb.timestamps)

    q = by[nwis.DISCHARGE_CFS]
    assert min(q.values) == pytest.approx(424.0)

    # Per-point qualifiers are carried, parallel to the values (#1602). A live event
    # record is provisional real-time data, so the series reads as provisional.
    assert len(turb.qualifiers) == len(turb)
    assert turb.provisional is True


def test_offline_miss_on_an_unfixtured_window_raises(hydro_settings: Settings) -> None:
    from watermark.hydrology.connectors._cache import HydroOfflineError

    with pytest.raises(HydroOfflineError):
        nwis.fetch_instantaneous_series(
            "04193500",
            parameter_cds=[nwis.DISCHARGE_CFS],
            start_date="2020-01-01",
            end_date="2020-01-02",
            settings=hydro_settings,
        )


# ------------------------------------------------------- travel-time math


def test_travel_time_is_inverse_in_velocity() -> None:
    slow = wm._travel_hours(wm.REACH_RIVER_KM, wm.VELOCITY_LOW_FPS)
    fast = wm._travel_hours(wm.REACH_RIVER_KM, wm.VELOCITY_HIGH_FPS)
    assert fast < slow  # a faster river => a shorter transit
    # ~42 km at ~1.2-1.8 ft/s is roughly a day, not an hour and not a week
    assert 12.0 < fast < slow < 48.0


# ------------------------------------------------------- the disciplined read


def _seven_q10() -> ProvenancedValue:
    return ProvenancedValue.derived(114.15, "cfs", citation="LP3 7Q10 04193500")


def test_read_monitor_locates_the_storm_turbidity_spikes(hydro_settings: Settings) -> None:
    read = wm.read_monitor(wm.load_event_series(settings=hydro_settings), seven_q10=_seven_q10())
    spikes = {s.timestamp: s.value for s in read.turbidity_spikes}
    assert spikes == {
        "2026-07-10T12:00:00.000-04:00": 324.0,
        "2026-07-10T17:30:00.000-04:00": 363.0,
    }
    assert read.turbidity_baseline.value < 40.0  # spikes are ~10x the baseline


def test_read_monitor_verdict_is_first_flush_not_the_plume(hydro_settings: Settings) -> None:
    read = wm.read_monitor(wm.load_event_series(settings=hydro_settings), seven_q10=_seven_q10())
    # every observed spike pre-dates the overnight dam failure
    assert read.spikes_precede_release is True
    assert all(s.timestamp < read.release_start for s in read.turbidity_spikes)
    assert "first-flush" in read.attribution
    assert "NOT the release plume" in read.attribution
    # the interpretive fields stay [inference]
    assert read.reach_river_km.source == "derived"
    assert read.plume_travel.source == "derived"
    assert read.plume_travel.low is not None and read.plume_travel.high is not None


def test_read_monitor_records_the_low_flow_dilution_and_thermal_do_sag(
    hydro_settings: Settings,
) -> None:
    read = wm.read_monitor(wm.load_event_series(settings=hydro_settings), seven_q10=_seven_q10())
    # the initial spill week bottomed near 3.7x the 7Q10 — a tight denominator, not a violation
    assert read.discharge_min.value == pytest.approx(424.0)
    assert read.low_flow_dilution_ratio == pytest.approx(3.71, abs=0.01)
    # the DO sag and the heat that drove it both pre-date the Jul-10 -> Jul-11 dam failure
    assert read.do_min.value == pytest.approx(4.3)
    assert read.do_min.asof < read.release_start
    assert read.water_temp_max.value >= 35.0
    assert read.water_temp_max.asof < read.release_start


def test_read_monitor_phycocyanin_is_sub_bloom_with_no_spill_spike(
    hydro_settings: Settings,
) -> None:
    read = wm.read_monitor(wm.load_event_series(settings=hydro_settings), seven_q10=_seven_q10())
    # fPC never blooms, and its value at the turbidity spike is BELOW the month's diel peak,
    # so there is no phycocyanin anomaly attributable to the release.
    assert read.phycocyanin_month_max.value < 5.0
    assert read.phycocyanin_at_turbidity_spike.value < read.phycocyanin_month_max.value


def test_read_monitor_conductance_shows_storm_dilution_not_an_ionic_bump(
    hydro_settings: Settings,
) -> None:
    read = wm.read_monitor(wm.load_event_series(settings=hydro_settings), seven_q10=_seven_q10())
    # specific conductance DROPS on the storm (dilution); it does not spike up with a plume
    assert read.conductance_storm_min.value < read.conductance_low_flow_max.value
    assert read.conductance_storm_min.asof[:10] == "2026-07-10"


# ------------------------------------------------------- artifact round-trip


def test_compute_and_roundtrip_the_committed_artifact(
    hydro_settings: Settings, tmp_path: Path
) -> None:
    read = wm.compute_monitor_read(settings=hydro_settings)
    assert read.seven_q10_cfs.value == pytest.approx(114.15)  # from the committed derived file

    tmp_settings = Settings(data_dir=tmp_path)
    path = wm.write_monitor_read(read, settings=tmp_settings)
    assert path.is_file()

    loaded = wm.load_monitor_read(settings=tmp_settings)
    assert loaded is not None
    assert loaded.attribution == read.attribution
    assert loaded.low_flow_dilution_ratio == read.low_flow_dilution_ratio
    assert [s.value for s in loaded.turbidity_spikes] == [s.value for s in read.turbidity_spikes]
    assert loaded.plume_travel.low == read.plume_travel.low


def test_load_monitor_read_absent_returns_none(tmp_path: Path) -> None:
    assert wm.load_monitor_read(settings=Settings(data_dir=tmp_path)) is None


# ------------------------------------------------------- field-level provenance


def test_computed_read_satisfies_the_field_provenance_contract(hydro_settings: Settings) -> None:
    # the real build must pass the validator: observed=connector, interpretive=derived
    read = wm.compute_monitor_read(settings=hydro_settings)
    assert read.discharge_min.source == "connector"
    assert read.reach_river_km.source == "derived"


def test_an_observed_field_may_not_masquerade_as_an_inference(hydro_settings: Settings) -> None:
    payload = wm.compute_monitor_read(settings=hydro_settings).model_dump()
    payload["discharge_min"]["source"] = "derived"  # a reading dressed up as an inference
    with pytest.raises(ValidationError, match="discharge_min"):
        ContinuousMonitorRead.model_validate(payload)


def test_the_travel_time_may_not_masquerade_as_a_gauge_reading(hydro_settings: Settings) -> None:
    payload = wm.compute_monitor_read(settings=hydro_settings).model_dump()
    payload["reach_river_km"]["source"] = "connector"  # an inference dressed up as a reading
    with pytest.raises(ValidationError, match="reach_river_km"):
        ContinuousMonitorRead.model_validate(payload)


def test_the_seven_q10_denominator_must_stay_derived(hydro_settings: Settings) -> None:
    # the screening denominator is an LP3-derived value, not a live gauge reading
    read = wm.compute_monitor_read(settings=hydro_settings)
    assert read.seven_q10_cfs.source == "derived"
    payload = read.model_dump()
    payload["seven_q10_cfs"]["source"] = "connector"
    with pytest.raises(ValidationError, match="seven_q10_cfs"):
        ContinuousMonitorRead.model_validate(payload)
