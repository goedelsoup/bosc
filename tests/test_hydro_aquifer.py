"""Aquifer-parameter derivation over the committed Allen County well-log census (hermetic).

Runs on the reviewed ``data/reference/ohio-waterwells/allen.csv`` (6,864 wells) and the cited
literature table — no network. Guards the Phase-2 method decision: no specific capacity, a
literature-K x census-thickness transmissivity BRACKET, correct provenance tags.
"""

from __future__ import annotations

from pathlib import Path

from watermark.config import Settings
from watermark.hydrology import aquifer
from watermark.hydrology.connectors import ohio_waterwells as oww

REPO = Path(__file__).resolve().parents[1]
ALLEN_CSV = REPO / "data" / "reference" / "ohio-waterwells" / "allen.csv"


def _params(hydro_settings: Settings) -> aquifer.AquiferParameters:
    inv = oww.read_inventory(ALLEN_CSV, settings=hydro_settings)
    return aquifer.compute_aquifer_parameters(inv, settings=hydro_settings)


def test_census_round_trip(hydro_settings: Settings) -> None:
    inv = oww.read_inventory(ALLEN_CSV, settings=hydro_settings)
    assert len(inv.wells) == 6864
    assert inv.county == "Allen"
    assert inv.use_counts()["DOMESTIC"] == 5808


def test_domestic_population_and_dominant_material(hydro_settings: Settings) -> None:
    p = _params(hydro_settings)
    assert p.well_count == 6864
    assert p.domestic_well_count == 5808  # the private-well population
    dom = p.dominant()
    assert dom is not None and dom.material == "LIMESTONE"
    assert dom.well_count == 4441
    assert dom.confinement == "confined"  # NW Ohio carbonate aquifer


def test_static_level_is_census_derived_inference(hydro_settings: Settings) -> None:
    lime = _params(hydro_settings).material("LIMESTONE")
    assert lime is not None and lime.static_water_level_ft is not None
    swl = lime.static_water_level_ft
    assert swl.source == "derived"  # [inference], from the census
    assert swl.unit == "ft"
    # A median with a p25-p75 band.
    assert swl.has_range and swl.low is not None and swl.low <= swl.value <= swl.high


def test_transmissivity_is_a_reference_backed_bracket(hydro_settings: Settings) -> None:
    lime = _params(hydro_settings).material("LIMESTONE")
    assert lime is not None
    # K/Sy/storativity are literature [reference], not measured.
    assert lime.hydraulic_conductivity_ft_day.source == "reference"
    assert lime.specific_yield.source == "reference"
    assert lime.specific_yield.value == 0.01  # fractured carbonate drains little
    # T = K*b is a derived [inference] bracket spanning orders of magnitude — never a scalar.
    t = lime.transmissivity_ft2_day
    assert t is not None and t.source == "derived"
    assert t.low is not None and t.high is not None
    assert t.low < t.value < t.high
    assert t.high / max(t.low, 1e-6) > 100  # the honest, wide screening spread


def test_shale_is_an_aquitard(hydro_settings: Settings) -> None:
    shale = _params(hydro_settings).material("SHALE")
    assert shale is not None and shale.confinement == "confined"
    t = shale.transmissivity_ft2_day
    assert t is not None and t.high_or_value < 10  # near-zero transmissivity


def test_specific_capacity_gap_is_surfaced(hydro_settings: Settings) -> None:
    """The method decision is a standing, surfaced gap — not silently hidden."""
    findings = aquifer.aquifer_findings(_params(hydro_settings))
    sc = next(f for f in findings if f.check == "aquifer-specific-capacity")
    assert sc.ok is False
    assert "pumping-water-level" in sc.detail
    census = next(f for f in findings if f.check == "aquifer-well-census")
    assert census.ok is True and "5808" in census.detail


def test_load_via_active_profile(hydro_settings: Settings) -> None:
    """`load_aquifer_parameters` resolves the active site's county census (Lima -> Allen)."""
    p = aquifer.load_aquifer_parameters(settings=hydro_settings)
    assert p is not None
    assert p.county == "Allen"
    assert p.domestic_well_count == 5808


def test_literature_yaml_matches_fallback_defaults(hydro_settings: Settings) -> None:
    """Coupling guard: the committed YAML and the hard-coded fallback stay in sync (WS-23)."""
    yaml_props = aquifer.load_aquifer_properties(settings=hydro_settings)
    defaults = aquifer._DEFAULT_PROPERTIES
    assert set(yaml_props) == set(defaults)
    for name, d in defaults.items():
        y = yaml_props[name]
        for field in ("k_ft_day_low", "k_ft_day_high", "specific_yield", "storativity"):
            assert float(y[field]) == float(d[field]), f"{name}.{field} drifted"
