"""Shared MW screening-derivation tests (#1629).

The provenance-carrying floor-area / investment / ceiling screens (``watermark.sites._screening``)
and their wiring into the disclosed-input peer-site profiles: every screened site's stored
``it_load`` bracket must BE the shared-helper output for its declared input (regression-locking the
derivation), and the reference band in ``rack-density.yaml`` must be the single lever that moves it.
"""

from __future__ import annotations

import pytest
import yaml

from watermark.sites import (
    _screening,
    ceiling_screen,
    floor_area_screen,
    get_profile,
    investment_screen,
)


def test_floor_area_screen_reproduces_the_troy_piqua_literals_exactly() -> None:
    """The clean derivation reproduces the pre-#1629 hand literals EXACTLY for the site whose
    values already followed the formula (700k sq ft x 75-250 W/sq ft, central = the midpoint)."""
    b = floor_area_screen(700_000)
    assert (b.low, b.central, b.high) == (52.5, 113.75, 175.0)


@pytest.mark.parametrize("slug", ["urbana", "troy-piqua", "wilmington", "sidney", "van-wert"])
def test_screened_site_bracket_is_the_shared_helper_output(slug: str) -> None:
    """Every screened site's stored it_load bracket IS the shared-helper output for THAT profile's
    own declared input (gross floor area / disclosed investment / announced ceiling) — so a hand-edit
    can no longer silently diverge from the reference band, and the test carries no magic screening
    numbers of its own (#1629)."""
    fac = get_profile(slug).facility
    assert fac is not None
    if slug == "sidney":
        assert fac.disclosed_investment_usd is not None
        b = investment_screen(fac.disclosed_investment_usd)
    elif slug == "van-wert":
        # The announced ceiling is not a stored field of its own — it IS the disclosed high bound.
        assert fac.it_load_high_mw is not None
        b = ceiling_screen(fac.it_load_high_mw)
    else:
        assert fac.gross_floor_area_sqft is not None
        b = floor_area_screen(fac.gross_floor_area_sqft)
    assert fac.it_load_mw == b.central
    assert fac.it_load_low_mw == b.low
    assert fac.it_load_high_mw == b.high


def test_bowling_green_low_is_the_floor_area_screen_floor() -> None:
    """Bowling Green is a hybrid: the disclosed ~180 MW peak stays the central/high; only the low
    bound derives from the shared floor-area screen over the profile's own gross floor area (#1629)."""
    fac = get_profile("bowling-green").facility
    assert fac is not None
    assert fac.gross_floor_area_sqft is not None
    assert fac.it_load_low_mw == floor_area_screen(fac.gross_floor_area_sqft).low
    assert fac.it_load_mw == 180.0
    assert fac.it_load_high_mw == 180.0


def test_changing_the_floor_area_band_moves_the_bracket() -> None:
    """A denser W/sq-ft band yields a larger bracket — the reference band is the single lever."""
    default = floor_area_screen(700_000)
    denser = floor_area_screen(700_000, band=(100.0, 300.0))
    assert denser.low > default.low
    assert denser.high > default.high


def test_default_band_path_reads_the_reference_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no ``band`` argument the screen reads ``floor_area_w_per_sqft_band`` from the reference
    yaml — so editing that band in rack-density.yaml moves every screened site's bracket (#1629's
    'change the band, move every bracket'), exercised through the real yaml-read path, not the
    override argument. Injects a modified band via the yaml loader and asserts the default result
    reflects it rather than the committed [75, 250]."""
    baseline = floor_area_screen(700_000)  # committed [75, 250] band
    patched = dict(_screening._bands(), floor_area_w_per_sqft_band=[150, 500])
    monkeypatch.setattr(_screening, "_bands", lambda: patched)
    moved = floor_area_screen(700_000)  # band=None -> reads the patched reference band
    assert moved.low == round(700_000 * 150 / 1e6, 2)  # 105.0, moved off the committed 52.5
    assert moved.high == round(700_000 * 500 / 1e6, 2)  # 350.0, moved off the committed 175.0
    assert moved.low > baseline.low
    assert moved.high > baseline.high


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


def test_invalid_band_or_pue_is_rejected() -> None:
    """The screens reject a malformed band / non-positive PUE rather than emitting a nonsensical
    bracket (negative MW, or low above high) (#1629 review)."""
    with pytest.raises(ValueError, match="0 < low <= high"):
        floor_area_screen(700_000, band=(250.0, 75.0))  # low above high
    with pytest.raises(ValueError, match="0 < low <= high"):
        investment_screen(3_000_000_000, band=(-1.0, 20_000_000.0))  # non-positive low
    with pytest.raises(ValueError, match="strictly positive"):
        ceiling_screen(500.0, pue_ceiling=0.0)


def test_rack_density_yaml_carries_the_screening_bands() -> None:
    """The two new bands live in the committed reference yaml — the single source #1629 declares."""
    data = yaml.safe_load(_screening._RACK_DENSITY_PATH.read_text(encoding="utf-8"))
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
