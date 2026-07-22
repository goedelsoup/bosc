"""Shared MW screening-derivation tests (#1629).

The provenance-carrying floor-area / investment / ceiling screens (``watermark.sites._screening``)
and their wiring into the disclosed-input peer-site profiles: every screened site's stored
``it_load`` bracket must BE the shared-helper output for its declared input (regression-locking the
derivation), and the reference band in ``rack-density.yaml`` must be the single lever that moves it.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
import yaml

from watermark.sites import (
    ceiling_screen,
    floor_area_screen,
    get_profile,
    investment_screen,
)
from watermark.sites._screening import _RACK_DENSITY_PATH, ScreenBracket


def test_floor_area_screen_reproduces_the_troy_piqua_literals_exactly() -> None:
    """The clean derivation reproduces the pre-#1629 hand literals EXACTLY for the site whose
    values already followed the formula (700k sq ft x 75-250 W/sq ft, central = the midpoint)."""
    b = floor_area_screen(700_000)
    assert (b.low, b.central, b.high) == (52.5, 113.75, 175.0)


@pytest.mark.parametrize(
    ("slug", "screen"),
    [
        ("urbana", lambda: floor_area_screen(460_000)),
        ("troy-piqua", lambda: floor_area_screen(700_000)),
        ("wilmington", lambda: floor_area_screen(1_920_299)),
        ("sidney", lambda: investment_screen(3_000_000_000)),
        ("van-wert", lambda: ceiling_screen(500.0)),
    ],
)
def test_screened_site_bracket_is_the_shared_helper_output(
    slug: str, screen: Callable[[], ScreenBracket]
) -> None:
    """Every screened site's stored it_load bracket IS the shared-helper output for its declared
    input — so a hand-edit can no longer silently diverge from the reference band (#1629)."""
    fac = get_profile(slug).facility
    assert fac is not None
    b = screen()
    assert fac.it_load_mw == b.central
    assert fac.it_load_low_mw == b.low
    assert fac.it_load_high_mw == b.high


def test_bowling_green_low_is_the_floor_area_screen_floor() -> None:
    """Bowling Green is a hybrid: the disclosed ~180 MW peak stays the central/high; only the low
    bound derives from the shared floor-area screen (#1629)."""
    fac = get_profile("bowling-green").facility
    assert fac is not None
    assert fac.it_load_low_mw == floor_area_screen(715_000).low
    assert fac.it_load_mw == 180.0
    assert fac.it_load_high_mw == 180.0


def test_changing_the_floor_area_band_moves_the_bracket() -> None:
    """A denser W/sq-ft band yields a larger bracket — the reference band is the single lever."""
    default = floor_area_screen(700_000)
    denser = floor_area_screen(700_000, band=(100.0, 300.0))
    assert denser.low > default.low
    assert denser.high > default.high


def test_investment_screen_inverts_cost_to_mw() -> None:
    """A HIGHER $/MW construction cost yields FEWER MW: the high cost gives the low MW bound."""
    b = investment_screen(3_000_000_000, band=(10_000_000.0, 20_000_000.0))
    assert b.low == 150.0  # 3e9 / 20e6 (high cost -> low MW)
    assert b.high == 300.0  # 3e9 / 10e6 (low cost -> high MW)
    assert b.central == 225.0


def test_changing_the_investment_band_moves_the_bracket() -> None:
    default = investment_screen(3_000_000_000)
    cheaper = investment_screen(3_000_000_000, band=(5_000_000.0, 15_000_000.0))
    assert cheaper.low > default.low
    assert cheaper.high > default.high


def test_ceiling_screen_divides_out_the_pue_ceiling() -> None:
    """The announced ceiling is carried central/high; the low divides out the PUE ceiling."""
    b = ceiling_screen(500.0, pue_ceiling=1.43)
    assert b.central == 500.0
    assert b.high == 500.0
    assert b.low == round(500.0 / 1.43, 2)


def test_rack_density_yaml_carries_the_screening_bands() -> None:
    """The two new bands live in the committed reference yaml — the single source #1629 declares."""
    data = yaml.safe_load(_RACK_DENSITY_PATH.read_text(encoding="utf-8"))
    assert data["floor_area_w_per_sqft_band"] == [75, 250]
    assert data["investment_usd_per_mw_band"] == [8_500_000, 20_000_000]


def test_screen_bracket_lifts_to_a_provenanced_value_with_range() -> None:
    """``ScreenBracket.provenanced()`` -> a derived ProvenancedValue carrying the low/high band and
    the reference-band citation (the '#1629 each returning ProvenancedValue with .with_range')."""
    b = floor_area_screen(460_000)
    pv = b.provenanced()
    assert pv.source == "derived"
    assert pv.unit == "MW"
    assert pv.value == b.central
    assert pv.low == b.low
    assert pv.high == b.high
    assert "floor_area_w_per_sqft_band" in (pv.citation or "")
