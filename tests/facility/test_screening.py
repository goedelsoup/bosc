"""The centralized IT-load screening helper + its consistency with the profiles (#1641 D2).

The floor-area / investment brackets used to be hand-typed literals re-typed per site, so
a mistyped bracket (or an off-midpoint central, as Wilmington's 300 was) passed CI. These
tests are the typo guard: every screening site's bracket is re-derived from its own
disclosed field, and ``central`` must be the MW-midpoint of its own low/high.
"""

from __future__ import annotations

import pytest

from watermark.facility.screening import (
    FLOOR_AREA_W_PER_SQFT,
    INVESTMENT_USD_PER_MW_IT,
    PUE_CEILING,
    ceiling_screen,
    floor_area_screen,
    investment_screen,
)
from watermark.sites import SITES


def test_floor_area_screen_arithmetic() -> None:
    """1,000,000 sq ft at the 75-250 W/sq ft band -> 75 / 162.5 / 250 MW."""
    b = floor_area_screen(1_000_000)
    assert b.low == pytest.approx(75.0)
    assert b.high == pytest.approx(250.0)
    assert b.central == pytest.approx(162.5)
    assert b.central == pytest.approx((b.low + b.high) / 2.0)  # MW-midpoint
    assert FLOOR_AREA_W_PER_SQFT == (75.0, 250.0)


def test_investment_screen_arithmetic() -> None:
    """$1B / the $8.5-20M-per-MW band: $20M->50 MW low, $8.5M->~117.6 MW high, midpoint central."""
    b = investment_screen(1_000_000_000)
    assert b.low == pytest.approx(50.0)  # 1e9 / 20e6
    assert b.high == pytest.approx(117.6, abs=0.1)  # 1e9 / 8.5e6
    assert b.central == pytest.approx((b.low + b.high) / 2.0)
    # Low MW divides by the HIGH cost, high MW by the LOW cost.
    assert INVESTMENT_USD_PER_MW_IT == (20_000_000.0, 8_500_000.0)
    assert b.low < b.high


def test_central_is_always_the_midpoint() -> None:
    """The central can never fall outside its own low/high (the Wilmington bug)."""
    for b in (floor_area_screen(1_920_299), investment_screen(3_000_000_000)):
        assert b.low <= b.central <= b.high
        assert b.central == pytest.approx(round((b.low + b.high) / 2.0, 1))


def test_ceiling_screen_arithmetic() -> None:
    """The announced-ceiling screen carries central = high = the ceiling (conservative-high, #1402),
    NOT the midpoint; the low divides out the cooling-dominated PUE ceiling (#1629)."""
    b = ceiling_screen(500.0)
    assert b.high == b.central == 500.0
    assert b.low == pytest.approx(round(500.0 / PUE_CEILING, 1))  # 349.7
    assert b.low < b.central  # deliberately not the midpoint


def test_ceiling_screen_rejects_non_positive_pue() -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        ceiling_screen(500.0, pue_ceiling=0.0)


# (slug, screen) — every PURE floor-area/investment/ceiling screening site: its whole bracket is
# re-derived from its disclosed field, so a mistyped literal fails here.
_FLOOR_AREA_SITES = ("urbana", "troy-piqua", "wilmington")
_INVESTMENT_SITES = ("sidney",)
_CEILING_SITES = ("van-wert",)


@pytest.mark.parametrize("slug", _FLOOR_AREA_SITES)
def test_floor_area_profiles_match_the_helper(slug: str) -> None:
    fac = SITES[slug].facility
    assert fac is not None and fac.gross_floor_area_sqft is not None
    b = floor_area_screen(fac.gross_floor_area_sqft)
    assert (fac.it_load_low_mw, fac.it_load_mw, fac.it_load_high_mw) == (b.low, b.central, b.high)


@pytest.mark.parametrize("slug", _INVESTMENT_SITES)
def test_investment_profiles_match_the_helper(slug: str) -> None:
    fac = SITES[slug].facility
    assert fac is not None and fac.disclosed_investment_usd is not None
    b = investment_screen(fac.disclosed_investment_usd)
    assert (fac.it_load_low_mw, fac.it_load_mw, fac.it_load_high_mw) == (b.low, b.central, b.high)


@pytest.mark.parametrize("slug", _CEILING_SITES)
def test_ceiling_profiles_match_the_helper(slug: str) -> None:
    """Van Wert's whole bracket is re-derived from its announced ceiling (its disclosed high bound),
    so the low (ceiling / PUE) can't drift from a hand-typed literal (#1629)."""
    fac = SITES[slug].facility
    assert fac is not None and fac.it_load_high_mw is not None
    b = ceiling_screen(fac.it_load_high_mw)
    assert (fac.it_load_low_mw, fac.it_load_mw, fac.it_load_high_mw) == (b.low, b.central, b.high)


def test_bowling_green_screen_floor_only() -> None:
    """Bowling Green is MIXED: central/high = the disclosed ~180 MW ceiling (#1435); only the
    LOW is a floor-area screening floor. Guard the floor without disturbing the disclosed pair."""
    fac = SITES["bowling-green"].facility
    assert fac is not None and fac.gross_floor_area_sqft is not None
    assert fac.it_load_low_mw == floor_area_screen(fac.gross_floor_area_sqft).low
    # The central/high are the disclosed design ceiling, NOT the screening midpoint.
    assert fac.it_load_mw == fac.it_load_high_mw == pytest.approx(180.0)
