"""Tests for the committed Ohio temperature criteria + Great Lakes RIS thermal tolerances and their
loader (epic #1715 Phase 1 / #1716) — the heat-side peer of test_hydro_criteria.py."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology import thermal_criteria as tc

# ---- Ohio temperature criteria ---------------------------------------------------------------


def test_temperature_table_loads_and_axis_is_18_periods() -> None:
    table = tc.load_temperature_criteria(settings=Settings())
    assert table.zones, "no temperature zones committed"
    assert len(table.periods) == 18  # the half-month reporting axis
    assert table.default_zone_hint == "lake_erie_basin_general"  # Lima's Ottawa River zone


def test_fahrenheit_to_celsius_reproduces_ohio_parenthetical() -> None:
    # Ohio prints degF with a rounded (Celsius) parenthetical; the loader must reproduce it.
    assert tc.fahrenheit_to_celsius(85) == 29.4
    assert tc.fahrenheit_to_celsius(82) == 27.8
    assert tc.fahrenheit_to_celsius(47) == 8.3
    assert tc.fahrenheit_to_celsius(32) == 0.0


def test_lima_zone_summer_and_winter_criteria() -> None:
    """The general Lake Erie basin zone (35-11 G) is Lima's; anchor its peak-summer + winter values."""
    table = tc.load_temperature_criteria(settings=Settings())
    zone = table.zone("lake_erie_basin_general")
    assert zone is not None and zone.rule == "OAC 3745-1-35 Table 35-11 (G)"
    jul = table.period_index_for(7, 20)
    assert jul is not None
    assert zone.daily_max_c(jul) == 29.4  # 85 F
    assert zone.average_c(jul) == 27.8  # 82 F
    jan = table.period_index_for(1, 15)
    assert jan is not None
    assert zone.daily_max_c(jan) == 9.4  # 49 F
    assert zone.average_c(jan) == 6.7  # 44 F


def test_period_index_maps_dates_to_half_month_windows() -> None:
    table = tc.load_temperature_criteria(settings=Settings())
    assert table.period_for(3, 10).key == "mar_1_15"
    assert table.period_for(3, 20).key == "mar_16_31"
    assert table.period_for(6, 30).key == "jun_16_30"
    assert table.period_index_for(2, 30) is None  # no Feb 30


def test_null_criterion_omitted_not_guessed() -> None:
    """A period with no printed criterion resolves to None (omit, don't guess)."""
    table = tc.load_temperature_criteria(settings=Settings())
    est = table.zone("lake_erie_tributary_estuaries")
    jan = table.period_index_for(1, 15)
    assert est.average_c(jan) is None  # rule prints no winter average for the estuaries
    assert est.daily_max_c(jan) == tc.fahrenheit_to_celsius(52)  # but does print a daily max


def test_hypolimnetic_monthly_criterion_repeats_across_half_periods() -> None:
    table = tc.load_temperature_criteria(settings=Settings())
    hyp = table.zone("lake_erie_hypolimnetic")
    # Published monthly (daily-max only); July = 59 F = 15.0 C, no average.
    assert hyp.daily_max_c(table.period_index_for(7, 1)) == 15.0
    assert hyp.daily_max_c(table.period_index_for(7, 31)) == 15.0
    assert hyp.average_c(table.period_index_for(7, 1)) is None


def test_zone_array_length_is_validated() -> None:
    """A zone whose arrays don't align to the 18-period axis is a hard error (transcription guard)."""
    with pytest.raises(ValueError, match="expected 18"):
        tc.TemperatureCriteriaTable.model_validate(
            {
                "periods": tc.load_temperature_criteria(settings=Settings()).model_dump()[
                    "periods"
                ],
                "zones": [
                    {"id": "bad", "rule": "x", "name": "x", "average_f": [1, 2], "daily_max_f": [3]}
                ],
            }
        )


def test_thermal_mixing_zone_rule_and_curve() -> None:
    table = tc.load_temperature_criteria(settings=Settings())
    tmz = table.thermal_mixing_zone
    assert tmz is not None
    # (O)(5): closed-cycle blowdown < 5% of 7Q10 is exempt — the screen's off-ramp.
    assert tmz.closed_cycle_blowdown_exempt_fraction_of_7q10 == 0.05
    assert tmz.case_by_case_ambient_c == 15.0
    non = tmz.curve("non_lake_erie")
    assert non is not None
    # ambient 10 C == 50 F -> tabulated limit 75 F == 23.9 C
    assert non.limit_c(10.0) == 23.9
    # at/above 15 C ambient the limit is case-by-case (untabulated) -> None
    assert non.limit_c(20.0) is None
    # below the tabulated ambient range -> None (no extrapolation)
    assert non.limit_c(-5.0) is None
    # interpolates between rows (Lake Erie curve, ambient 5 C == 41 F -> 59.5 F == 15.3 C)
    assert tmz.curve("lake_erie").limit_c(5.0) == 15.3


def test_missing_temperature_dataset_degrades_to_empty_table() -> None:
    settings = Settings(data_dir=Path(tempfile.mkdtemp()) / "nodata")
    table = tc.load_temperature_criteria(settings=settings)
    assert table.zones == []
    assert table.zone("lake_erie_basin_general") is None


# ---- Great Lakes RIS thermal tolerances ------------------------------------------------------


def test_ris_table_loads_with_species_and_references() -> None:
    table = tc.load_thermal_tolerances(settings=Settings())
    assert len(table.species) == 23
    assert len(table.references) == 28
    assert table.region == "great_lakes"


def test_ris_resolves_by_common_and_scientific_name() -> None:
    table = tc.load_thermal_tolerances(settings=Settings())
    assert table.match("Walleye") is table.match("Sander vitreus")
    assert table.match("walleye") is not None  # case-insensitive
    assert table.match("not-a-species") is None
    assert table.match(None) is None


def test_ris_finding_anchor_values() -> None:
    """The two §316(a) headline tolerances from the epic: walleye adult acute, lake trout optimal."""
    table = tc.load_thermal_tolerances(settings=Settings())
    walleye_adult = table.match("Walleye").stage("Adult")
    assert walleye_adult.acute.upper_span() == (34.4, 34.4)
    lake_trout_adult = table.match("Salvelinus namaycush").stage("Adult")
    assert lake_trout_adult.optimal.upper_span() == (12.8, 12.8)
    assert lake_trout_adult.optimal.refs == [5]


def test_ris_range_values_kept_verbatim_and_parse_to_spans() -> None:
    table = tc.load_thermal_tolerances(settings=Settings())
    pike_adult = table.match("Northern Pike").stage("Adult")
    assert pike_adult.chronic.upper_c == "32-35.6"  # verbatim
    assert pike_adult.chronic.upper_span() == (32.0, 35.6)  # parsed
    assert pike_adult.chronic.lower_span() == (3.0, 4.9)  # "3-4.9"


def test_parse_span_edge_cases() -> None:
    assert tc._parse_span("34.4") == (34.4, 34.4)
    assert tc._parse_span("20.6-28.5") == (20.6, 28.5)
    assert tc._parse_span("14.55") == (14.55, 14.55)
    assert tc._parse_span(None) is None
    assert tc._parse_span("") is None
    assert tc._parse_span("n/a") is None


def test_missing_ris_dataset_degrades_to_empty_table() -> None:
    settings = Settings(data_dir=Path(tempfile.mkdtemp()) / "nodata")
    table = tc.load_thermal_tolerances(settings=settings)
    assert table.species == []
    assert table.match("Walleye") is None


def test_committed_yaml_is_wellformed() -> None:
    """The two committed files parse as YAML (a corruption guard independent of the loader)."""
    ref = Settings().reference_dir
    for rel in (
        "wqs/ohio-temperature-criteria.yaml",
        "thermal/great-lakes-ris-thermal-tolerances.yaml",
    ):
        data = yaml.safe_load((ref / rel).read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data
