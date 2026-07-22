"""Provenance-carrying MW screening derivations for disclosed-input peer sites (issue #1629).

Three shared SCREENS that bracket a data-center campus's IT load when the load itself is **not**
disclosed, each off ONE disclosed hard figure plus a reference band read from
``data/reference/compute/rack-density.yaml`` (the single source — change a band there and every
screened site's bracket moves):

* :func:`floor_area_screen` — a disclosed gross floor area x a whole-building W/sq-ft density band
  (Urbana / Troy-Piqua / Wilmington; also Bowling Green's floor-area *floor*).
* :func:`investment_screen` — a disclosed capital investment ÷ a hyperscale $/MW-IT cost band
  (Sidney). A higher $/MW yields *fewer* MW, so the band's high cost gives the low MW bound.
* :func:`ceiling_screen` — an announced "up to" MW ceiling carried central/high, its low bound
  dividing out the cooling-dominated PUE ceiling (Van Wert).

Each returns a :class:`ScreenBracket` (``low <= central <= high`` MW) carrying the derivation
**basis** as a citation fragment; the bracket floats populate the declared
``SiteFacility.it_load_mw`` / ``it_load_low_mw`` / ``it_load_high_mw`` in
:mod:`watermark.sites._profiles`, replacing the hand-computed float literals the screens used to
duplicate site-by-site (the basis rides into each site's ``it_load_citation`` so the prose numbers
can never drift from the derived bracket). :meth:`ScreenBracket.provenanced` lifts the bracket to a
:class:`watermark.hydrology.model.ProvenancedValue` with ``.with_range(low, high)`` for callers that
want one.

This module lives in :mod:`watermark.sites` (not :mod:`watermark.facility`) because ``_profiles``
calls it at import time and ``watermark.facility`` imports ``watermark.sites`` — so the helper must
sit on the *sites* side of that edge. For the same reason it must **not** import
``watermark.hydrology`` at module scope (``watermark.sites`` never does — cf. ``CoolingModelType`` in
``_model.py``): the optional ``ProvenancedValue`` lift is a lazy import inside
:meth:`ScreenBracket.provenanced`, so nothing triggers the hydrology package during ``_profiles``
import.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import yaml

if TYPE_CHECKING:
    from watermark.hydrology.model import ProvenancedValue

# The committed reference bands, read at the fixed repo-relative path (mirrors ``_model.py``'s
# ``_YAML_PATH`` — screening runs at profile-definition time, where there is no ``Settings``).
_RACK_DENSITY_PATH = (
    Path(__file__).parents[3] / "data" / "reference" / "compute" / "rack-density.yaml"
)
_RACK_CITE = "data/reference/compute/rack-density.yaml"
_W_PER_MW = 1_000_000.0  # 1 MW = 1e6 W (IT load is derived in W, reported in MW)

_Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ScreenBracket:
    """A screening IT-load bracket (MW): a central value, its ``low``/``high`` bounds, and the
    derivation ``basis``.

    ``low <= central <= high``. ``basis`` is the citation fragment naming the disclosed input, the
    reference band, and the three derived outputs — embedded verbatim in the site's
    ``it_load_citation`` so the prose figures can never drift from the derived bracket.
    """

    low: float
    central: float
    high: float
    basis: str

    def provenanced(
        self, *, unit: str = "MW", confidence: _Confidence = "medium"
    ) -> ProvenancedValue:
        """Lift to a :meth:`ProvenancedValue.derived` central with ``.with_range(low, high)``.

        Lazy import: :mod:`watermark.sites` must not import :mod:`watermark.hydrology` at module
        scope (the import edge runs facility/hydrology → sites, not back), so ``ProvenancedValue`` is
        pulled in here, at call time — never during ``_profiles`` import.
        """
        from watermark.hydrology.model import ProvenancedValue

        return ProvenancedValue.derived(
            self.central,
            unit,
            citation=self.basis,
            confidence=confidence,
            low=self.low,
            high=self.high,
        )


def _bands() -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(_RACK_DENSITY_PATH.read_text(encoding="utf-8")))


def _pair(band: tuple[float, float] | None, key: str) -> tuple[float, float]:
    """The (low, high) band from ``band`` if given, else the committed ``key`` in the reference yaml."""
    if band is not None:
        return float(band[0]), float(band[1])
    raw = _bands()[key]
    return float(raw[0]), float(raw[1])


def _r(x: float) -> float:
    """Round a MW figure to 2 dp — the precision the hand-written literals used (e.g. 113.75)."""
    return round(x, 2)


def floor_area_screen(
    gross_floor_area_sqft: float, *, band: tuple[float, float] | None = None
) -> ScreenBracket:
    """Bracket IT load from a disclosed gross floor area x a whole-building W/sq-ft density band.

    ``low = area x w_lo``, ``high = area x w_hi``, ``central`` = the arithmetic midpoint. The band
    defaults to ``floor_area_w_per_sqft_band`` in the reference yaml (75-250 W/sq ft); pass ``band``
    to move it. Distinct from the land-area footprint envelope in
    :func:`watermark.facility.compute._footprint_it_load_mw`, which derives floor area from *land*
    when none is disclosed.
    """
    w_lo, w_hi = _pair(band, "floor_area_w_per_sqft_band")
    low = _r(gross_floor_area_sqft * w_lo / _W_PER_MW)
    high = _r(gross_floor_area_sqft * w_hi / _W_PER_MW)
    central = _r((low + high) / 2.0)
    basis = (
        f"the disclosed {gross_floor_area_sqft:,.0f} sq ft gross floor area x a whole-building IT "
        f"power-density band of {w_lo:g}-{w_hi:g} W/sq ft ({_RACK_CITE} floor_area_w_per_sqft_band, "
        f"a stated screening assumption): {low:g} MW low, {central:g} MW central, {high:g} MW high"
    )
    return ScreenBracket(low, central, high, basis)


def investment_screen(
    disclosed_investment_usd: float, *, band: tuple[float, float] | None = None
) -> ScreenBracket:
    """Bracket IT load from a disclosed capital investment ÷ a hyperscale $/MW-IT cost band.

    The band is ``(low_cost, high_cost)`` USD per MW-IT; a *higher* cost yields *fewer* MW, so the
    high cost gives the ``low`` MW bound and the low cost the ``high``. ``central`` = the midpoint.
    Defaults to ``investment_usd_per_mw_band`` in the reference yaml (~$8.5-20M/MW-IT).
    """
    cost_lo, cost_hi = _pair(band, "investment_usd_per_mw_band")
    low = _r(disclosed_investment_usd / cost_hi)
    high = _r(disclosed_investment_usd / cost_lo)
    central = _r((low + high) / 2.0)
    basis = (
        f"the disclosed ${disclosed_investment_usd / 1e9:g}B campus investment / a hyperscale "
        f"critical-IT construction-cost band of ~${cost_lo / 1e6:g}-{cost_hi / 1e6:g}M per MW-IT "
        f"({_RACK_CITE} investment_usd_per_mw_band, a [reference] industry norm, NOT a disclosure): "
        f"{low:g} MW low (${cost_hi / 1e6:g}M/MW), {central:g} MW central, "
        f"{high:g} MW high (${cost_lo / 1e6:g}M/MW)"
    )
    return ScreenBracket(low, central, high, basis)


def ceiling_screen(
    announced_ceiling_mw: float, *, pue_ceiling: float | None = None
) -> ScreenBracket:
    """Bracket IT load from an announced "up to" MW ceiling.

    ``central = high = ceiling`` (an "up to"/all-in figure, carried conservative-high downstream);
    the ``low`` reads the same ceiling as the ALL-IN campus draw and divides out the
    cooling-dominated PUE ceiling (``pue_band`` high in the reference yaml, ~1.43). Pass
    ``pue_ceiling`` to move it.
    """
    pue_hi = pue_ceiling if pue_ceiling is not None else _pair(None, "pue_band")[1]
    high = _r(announced_ceiling_mw)
    central = high
    low = _r(announced_ceiling_mw / pue_hi)
    basis = (
        f"the announced 'up to {announced_ceiling_mw:g} MW' ceiling — carried central/high (an "
        f"'up to'/all-in figure, so downstream runs conservative-high); the low reads the same "
        f"ceiling as the ALL-IN campus draw and divides out the cooling-dominated PUE ceiling "
        f"({pue_hi:g}, {_RACK_CITE} pue_band): {low:g} MW implied IT — bracket {low:g}-{high:g} MW"
    )
    return ScreenBracket(low, central, high, basis)
