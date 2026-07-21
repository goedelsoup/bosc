"""Reference evapotranspiration (ET0) from the committed NASA POWER climatology.

Computes monthly **FAO-56 Penman-Monteith** reference ET0 — the standard method —
from the climate normals already pulled into
``data/reference/hydrology/nasa-power-climatology.yaml`` (air temperature + its
max/min, relative humidity, 2 m wind, and surface solar irradiance), plus the
point's latitude and elevation. ET0 closes the water-budget context the hydrology
report frames around precipitation: precip *in*, reference ET *out*.

All inputs are the committed POWER normals; nothing is fabricated. The result is a
*reference* (grass) ET0, not an actual-ET or a crop demand — it bounds the
atmospheric water demand the corridor's precipitation must meet.

Reference: Allen et al., FAO Irrigation & Drainage Paper 56, Chapter 4 (the
equation numbers in the comments are FAO-56's).
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.connectors.nasa_power import NasaPowerClimatology
from watermark.hydrology.units import acre_mm_to_mg

_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)  # climatology: leap years ignored
# Day-of-year of each month's ~15th — the FAO-recommended representative day for Ra.
_MID_J = (15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349)

_GSC = 0.0820  # solar constant, MJ m^-2 min^-1
_SIGMA = 4.903e-9  # Stefan-Boltzmann, MJ K^-4 m^-2 day^-1
_ALBEDO = 0.23  # reference grass


class Et0Climatology(BaseModel):
    """Monthly + annual FAO-56 Penman-Monteith reference ET0."""

    model_config = ConfigDict(extra="forbid")

    method: str = "FAO-56 Penman-Monteith"
    monthly_mm_day: dict[str, float]  # JAN..DEC, mm/day (comparable to precip normals)
    annual_mm: float  # mm/yr (sum of monthly mm/day x days-in-month)


def _svp(t: float) -> float:
    """Saturation vapour pressure at temperature ``t`` (°C), kPa — FAO-56 eq. 11."""
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def _ra(latitude: float, j: int) -> float:
    """Extraterrestrial radiation Ra (MJ m^-2 day^-1) for day-of-year ``j`` — eq. 21."""
    phi = math.radians(latitude)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)  # inverse relative Earth-Sun distance
    decl = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)  # solar declination
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))  # sunset hour angle
    return (
        (24 * 60 / math.pi)
        * _GSC
        * dr
        * (ws * math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.sin(ws))
    )


def penman_monteith_et0(
    clim: NasaPowerClimatology,
    *,
    latitude: float | None = None,
    elevation_m: float | None = None,
) -> Et0Climatology:
    """Monthly FAO-56 Penman-Monteith reference ET0 from a POWER climatology.

    Raises ``ValueError`` if the climatology lacks a parameter the method needs.
    """
    lat = clim.latitude if latitude is None else latitude
    elev = (clim.elevation_m if elevation_m is None else elevation_m) or 0.0

    def series(name: str) -> dict[str, float]:
        p = clim.get(name)
        if p is None or not p.monthly:
            raise ValueError(f"climatology missing parameter {name!r} for ET0")
        return p.monthly

    tmean, tmax, tmin = series("T2M"), series("T2M_MAX"), series("T2M_MIN")
    rh, wind, rs_all = series("RH2M"), series("WS2M"), series("ALLSKY_SFC_SW_DWN")

    # Atmospheric pressure + psychrometric constant from elevation (eq. 7, 8).
    pressure = 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26
    gamma = 0.000665 * pressure

    monthly: dict[str, float] = {}
    for i, m in enumerate(_MONTHS):
        t, tx, tn = tmean[m], tmax[m], tmin[m]
        u2 = max(wind[m], 0.5)  # FAO floors wind at 0.5 m/s
        rs = rs_all[m]

        delta = 4098 * _svp(t) / (t + 237.3) ** 2  # vapour-pressure curve slope (eq. 13)
        es = (_svp(tx) + _svp(tn)) / 2  # eq. 12
        ea = es * rh[m] / 100  # actual vapour pressure from mean RH (eq. 19)

        ra = _ra(lat, _MID_J[i])
        rso = (0.75 + 2e-5 * elev) * ra  # clear-sky radiation (eq. 37)
        rns = (1 - _ALBEDO) * rs  # net shortwave (eq. 38)
        # Net longwave (eq. 39); cloud factor clamped to [0,1].
        cloud = min(1.0, max(0.0, 1.35 * (rs / rso if rso else 0) - 0.35))
        rnl = (
            _SIGMA
            * (((tx + 273.16) ** 4 + (tn + 273.16) ** 4) / 2)
            * (0.34 - 0.14 * math.sqrt(max(ea, 0)))
            * cloud
        )
        rn = rns - rnl  # net radiation

        # Monthly soil heat flux from the mean-temp swing to adjacent months (eq. 43).
        t_prev = tmean[_MONTHS[(i - 1) % 12]]
        t_next = tmean[_MONTHS[(i + 1) % 12]]
        g = 0.07 * (t_next - t_prev)

        num = 0.408 * delta * (rn - g) + gamma * (900 / (t + 273)) * u2 * (es - ea)
        den = delta + gamma * (1 + 0.34 * u2)
        monthly[m] = round(max(0.0, num / den), 3)

    annual = round(sum(monthly[m] * _DAYS[i] for i, m in enumerate(_MONTHS)), 1)
    return Et0Climatology(monthly_mm_day=monthly, annual_mm=annual)


# --- Open-water evaporation ------------------------------------------------------------
# A first-order screening sink for a standing water surface (e.g. a reservoir). Reference (grass)
# ET0 is the input, scaled by an **open-water coefficient**: open water evaporates ABOVE grass
# ET0 in the warm season because its albedo is far lower (~0.06-0.08 vs grass 0.23, so it absorbs
# more net shortwave) and it carries no canopy/surface resistance (rs -> 0 vs the grass 70 s/m).
# A Penman open-water estimate therefore runs ~1.05-1.3x annual ET0, weighted to the high-
# radiation months. The caller passes the coefficient (see refill._OPEN_WATER_COEFFICIENT); this
# helper is the units multiply, so its own ``coefficient`` defaults to 1.0 (ET0 as-is).


def reservoir_evaporation_mgd(
    et0: Et0Climatology, surface_acres: float, *, coefficient: float = 1.0
) -> dict[str, float]:
    """Monthly open-water evaporation (MGD) = ET0(mm/day) x coefficient x surface(acres).

    ``coefficient`` is the open-water:grass-ET0 multiplier for a standing-water surface
    (``> 1`` in the warm season — see the section note above); ``1.0`` returns ET0 as-is.
    """
    return {
        m: round(acre_mm_to_mg(et0.monthly_mm_day[m] * coefficient, surface_acres), 4)
        for m in _MONTHS
    }


def annual_evaporation_mg(monthly_mgd: dict[str, float]) -> float:
    """Annual evaporation volume (MG) from a JAN..DEC monthly-MGD map (days-weighted)."""
    return round(sum(monthly_mgd[m] * _DAYS[i] for i, m in enumerate(_MONTHS)), 1)
