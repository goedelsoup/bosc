"""NASA POWER meteorology / solar connector (climatology point service).

Grounds the water balance in long-run *climate normals* for the Lima loop: monthly
and annual climatology of corrected precipitation, air temperature, humidity, wind,
and surface solar irradiance from NASA's Prediction Of Worldwide Energy Resources
(POWER) project — satellite-derived, Analysis-Ready Data.

POWER's AWS Open Data bucket (``s3://nasa-power``) is gridded zarr/netCDF; for a
single point we use POWER's supported REST API, which returns a small JSON payload
that caches and fixtures cleanly like the other connectors. ``fetch_climatology``
returns the 12 monthly normals + the annual value per parameter; the precipitation
normal feeds the annual water-balance context (NOAA Atlas-14 still supplies the
design-storm depths — the two are complementary, not interchangeable).

Synchronous (``httpx``) to match BOSC's otherwise-sync pipeline layer.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get

_CONNECTOR = "nasa_power"
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_FILL = -999.0  # POWER no-data sentinel
# Non-leap calendar days per month; monthly normals are mm/day, so a days-weighted
# sum gives the annual depth without trusting POWER's ambiguous ANN field.
_DAYS_IN_MONTH = {
    "JAN": 31,
    "FEB": 28,
    "MAR": 31,
    "APR": 30,
    "MAY": 31,
    "JUN": 30,
    "JUL": 31,
    "AUG": 31,
    "SEP": 30,
    "OCT": 31,
    "NOV": 30,
    "DEC": 31,
}
_DAYS_PER_YEAR = 365.25
_PRECIP_CROSSCHECK_TOL = 0.05  # fractional; a ~365x ANN unit flip blows past this


class NasaPowerUnitError(RuntimeError):
    """A POWER value failed its unit cross-check (e.g. ANN drifted off mm/day)."""


class ClimatologyParameter(BaseModel):
    """One parameter's monthly normals + annual value."""

    model_config = ConfigDict(extra="forbid")

    parameter: str
    units: str
    longname: str
    monthly: dict[str, float]  # JAN..DEC (fill months dropped)
    annual: float | None


class NasaPowerClimatology(BaseModel):
    """A POWER climatology point response, reduced to the parameters requested."""

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    elevation_m: float | None
    source_title: str
    parameters: list[ClimatologyParameter]

    def get(self, name: str) -> ClimatologyParameter | None:
        return next((p for p in self.parameters if p.parameter == name), None)

    def annual_precip_mm(self) -> float | None:
        """Annual precipitation depth (mm/yr), summed from the 12 monthly mm/day normals.

        Derived from the monthly normals (``sum(mm/day x days_in_month)``) so the total
        is robust to what POWER ships in ``ANN`` — that field has historically been
        either a daily-mean rate or an annual total depending on parameter/version. When
        ``ANN`` is present it is cross-checked against the monthly-derived total on the
        assumption that ``ANN`` is a mm/day rate; a mismatch (e.g. POWER switching ``ANN``
        to an annual total — a ~365x drift) raises :class:`NasaPowerUnitError` rather than
        silently mis-reporting the user-visible precip headline.
        """
        p = self.get("PRECTOTCORR")
        if p is None or len(p.monthly) < len(_MONTHS):
            return None
        derived = sum(p.monthly[m] * _DAYS_IN_MONTH[m] for m in _MONTHS)
        if p.annual is not None:
            ann_as_rate = p.annual * _DAYS_PER_YEAR
            if abs(ann_as_rate - derived) > _PRECIP_CROSSCHECK_TOL * derived:
                raise NasaPowerUnitError(
                    f"NASA POWER PRECTOTCORR ANN ({p.annual}) is inconsistent with the "
                    f"monthly-normal-derived annual total ({derived:.1f} mm/yr) under a "
                    f"mm/day reading (ANN x {_DAYS_PER_YEAR}={ann_as_rate:.1f} mm/yr, "
                    f"drift >{_PRECIP_CROSSCHECK_TOL:.0%}) — POWER may have changed the "
                    f"ANN unit; verify before trusting the precip headline."
                )
        return round(derived, 1)

    def wettest_month(self) -> tuple[str, float] | None:
        p = self.get("PRECTOTCORR")
        if p is None or not p.monthly:
            return None
        return max(p.monthly.items(), key=lambda kv: kv[1])

    def driest_month(self) -> tuple[str, float] | None:
        p = self.get("PRECTOTCORR")
        if p is None or not p.monthly:
            return None
        return min(p.monthly.items(), key=lambda kv: kv[1])


def fetch_climatology(
    *,
    lon: float | None = None,
    lat: float | None = None,
    parameters: list[str] | None = None,
    community: str | None = None,
    settings: Settings | None = None,
) -> NasaPowerClimatology:
    """Monthly + annual climate normals at a point from the NASA POWER REST API."""
    settings = settings or get_settings()
    lon = settings.nasa_power_lon if lon is None else lon
    lat = settings.nasa_power_lat if lat is None else lat
    params = parameters or list(settings.nasa_power_parameters)
    community = community or settings.nasa_power_community

    query = {
        "parameters": ",".join(params),
        "community": community,
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "format": "json",
    }

    def fetch() -> Any:
        url = f"{settings.nasa_power_base_url}/climatology/point"
        resp = httpx.get(url, params=query, timeout=settings.hydro_request_timeout_s)
        resp.raise_for_status()
        return resp.json()

    payload = cast("dict[str, Any]", cached_get(_CONNECTOR, query, fetch, settings=settings))
    return _parse(payload, requested=params)


def _parse(payload: dict[str, Any], *, requested: list[str]) -> NasaPowerClimatology:
    """Reduce the POWER JSON to the requested parameters, dropping fill values."""
    geom = payload.get("geometry", {}).get("coordinates", [None, None, None])
    lon, lat = geom[0], geom[1]
    elev = geom[2] if len(geom) > 2 else None
    header = payload.get("header", {})
    units_meta = payload.get("parameters", {})
    values = payload.get("properties", {}).get("parameter", {})

    out: list[ClimatologyParameter] = []
    for name in requested:
        block = values.get(name)
        if not block:
            continue
        meta = units_meta.get(name, {})
        monthly = {m: float(block[m]) for m in _MONTHS if m in block and block[m] != _FILL}
        ann_raw = block.get("ANN")
        annual = float(ann_raw) if ann_raw is not None and ann_raw != _FILL else None
        out.append(
            ClimatologyParameter(
                parameter=name,
                units=meta.get("units", ""),
                longname=meta.get("longname", name),
                monthly=monthly,
                annual=annual,
            )
        )
    return NasaPowerClimatology(
        latitude=float(lat),
        longitude=float(lon),
        elevation_m=float(elev) if elev is not None else None,
        source_title=header.get("title", "NASA POWER climatology"),
        parameters=out,
    )
