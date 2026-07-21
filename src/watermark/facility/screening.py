"""Centralized data-center IT-load screening brackets (#1641 D2).

When a campus's IT load is undisclosed, two screening methods turn a *disclosed* size
into an ``[inference]`` MW bracket:

* **floor-area** — gross building floor area x a whole-building IT power-density band
  (75-250 W/sq ft).
* **investment** — disclosed capital investment / a hyperscale critical-IT
  construction-cost band (~$8.5-20M per MW-IT).

Both are stated SCREENING assumptions, never disclosures. The constants live here **once**
— they used to be re-typed as literals in every screening profile in ``_profiles.py``, so
a mistyped bracket (or a ``central`` that wasn't the midpoint of its own low/high, as
Wilmington's was) sailed through CI (#1641 D2). Now each screening site calls the helper
on its own disclosed field, and ``tests/facility/test_screening.py`` re-derives every
site's bracket from that field, so a typo fails the gate.

``central`` is the **MW-midpoint** of the bracket, so it can never fall outside its own
``low``/``high`` — a method-agnostic central that matches the network's existing
floor-area/investment screens.
"""

from __future__ import annotations

from typing import NamedTuple

# Whole-building IT power density (W/sq ft): low = conservative, high = a dense AI hall.
# The band applied across the network's floor-area screens (the Urbana #1327 precedent).
FLOOR_AREA_W_PER_SQFT: tuple[float, float] = (75.0, 250.0)

# Hyperscale critical-IT construction cost ($/MW-IT). The LOW MW bound divides by the HIGH
# cost (capex-intensive / liquid-AI -> fewer MW per dollar); the HIGH MW bound divides by
# the LOW cost (capex-light / air-cooled -> more MW per dollar). Ordered (cost_for_low_mw,
# cost_for_high_mw) so the tuple reads in the same low..high MW order as the floor-area band.
INVESTMENT_USD_PER_MW_IT: tuple[float, float] = (20_000_000.0, 8_500_000.0)


class ScreeningBracket(NamedTuple):
    """A screening IT-load bracket in MW: ``low <= central <= high`` + its derivation."""

    low: float
    central: float
    high: float
    citation: str


def _bracket(low: float, high: float, citation: str) -> ScreeningBracket:
    """Round to 1 dp and set ``central`` to the MW-midpoint of the rounded bounds."""
    lo, hi = round(low, 1), round(high, 1)
    return ScreeningBracket(lo, round((lo + hi) / 2.0, 1), hi, citation)


def floor_area_screen(gross_floor_area_sqft: float) -> ScreeningBracket:
    """IT-load bracket (MW) = gross floor area x the 75-250 W/sq ft density band."""
    lo_wsf, hi_wsf = FLOOR_AREA_W_PER_SQFT
    low = gross_floor_area_sqft * lo_wsf / 1_000_000.0
    high = gross_floor_area_sqft * hi_wsf / 1_000_000.0
    cite = (
        f"floor-area screening (watermark.facility.screening): {gross_floor_area_sqft:,.0f} "
        f"sq ft x a whole-building IT power-density band of {lo_wsf:g}-{hi_wsf:g} W/sq ft "
        f"(stated screening assumption) -> {round(low, 1):g} MW low .. {round(high, 1):g} MW "
        "high, MW-midpoint central"
    )
    return _bracket(low, high, cite)


def investment_screen(disclosed_investment_usd: float) -> ScreeningBracket:
    """IT-load bracket (MW) = disclosed investment / the ~$8.5-20M per MW-IT cost band."""
    cost_for_low_mw, cost_for_high_mw = INVESTMENT_USD_PER_MW_IT
    low = disclosed_investment_usd / cost_for_low_mw
    high = disclosed_investment_usd / cost_for_high_mw
    cite = (
        f"investment screening (watermark.facility.screening): "
        f"${disclosed_investment_usd / 1e9:g}B disclosed campus investment / a hyperscale "
        f"critical-IT construction-cost band of ~${cost_for_high_mw / 1e6:g}-"
        f"{cost_for_low_mw / 1e6:g}M per MW-IT (stated screening assumption) -> "
        f"{round(low, 1):g} MW low .. {round(high, 1):g} MW high, MW-midpoint central"
    )
    return _bracket(low, high, cite)
