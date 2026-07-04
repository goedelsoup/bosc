"""NOAA ISD (Integrated Surface Database) surface-met connector — the AERMET SURFACE input.

Pulls one station-year of hourly surface observations in NOAA's raw ISH ("ISHD") format —
the fixed-column TD-3505 layout AERMET's Stage-1 ``SURFACE ... ISHD`` pathway reads
directly. The raw text is passed through verbatim to the AERMET surface input file (no
re-encoding, so the AERMET extraction sees authoritative bytes); alongside it we parse the
*mandatory data section* (wind, air temperature, dew point, ceiling, sea-level pressure)
into typed :class:`SurfaceObservation`s for QA and typed access.

Source: ``{isd_base_url}/{year}/{usaf}-{wban}-{year}.gz`` (NCEI's per-station-year gzip).
Same connector cache / offline / committed-fixture discipline as the hydrology connectors
(``cached_get``); the decompressed text is the cached payload, so an offline replay never
touches the network. Synchronous ``httpx`` to match the sync pipeline layer.

The ISH mandatory-section field positions and missing sentinels follow the NOAA
*Federal Climate Complex Data Documentation for ISD* (TD-3505). Figures are QC'd by the
archive's own quality flags; we keep values whose flag is not a documented failing code.
"""

from __future__ import annotations

import gzip
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.air.connectors._cache import cached_get
from watermark.config import Settings, get_settings

_CONNECTOR = "isd"

# ISH mandatory-section slices (0-based half-open), per NOAA TD-3505. The control section
# carries station/position; the mandatory section is always present (additional ADD groups
# follow and are ignored here — AERMET reads them off the raw file, not our parse).
_SL_USAF = slice(4, 10)
_SL_WBAN = slice(10, 15)
_SL_DATE = slice(15, 23)  # YYYYMMDD (UTC)
_SL_TIME = slice(23, 27)  # HHMM (UTC)
_SL_LAT = slice(28, 34)  # thousandths of a degree, signed
_SL_LON = slice(34, 41)  # thousandths of a degree, signed
_SL_ELEV = slice(46, 51)  # metres, signed
_SL_CALL = slice(51, 56)
_SL_WIND_DIR = slice(60, 63)  # degrees true
_SL_WIND_DIR_Q = slice(63, 64)
_SL_WIND_SPD = slice(65, 69)  # m/s x10
_SL_WIND_SPD_Q = slice(69, 70)
_SL_CEIL = slice(70, 75)  # metres AGL
_SL_CEIL_Q = slice(75, 76)
_SL_TEMP = slice(87, 92)  # deg C x10, signed
_SL_TEMP_Q = slice(92, 93)
_SL_DEW = slice(93, 98)  # deg C x10, signed
_SL_DEW_Q = slice(98, 99)
_SL_SLP = slice(99, 104)  # hPa x10
_SL_SLP_Q = slice(104, 105)

# Documented missing sentinels (all-nines) per field width.
_MISSING = {"999", "9999", "99999", "999999", "+9999", "+99999"}
# ISH quality flags that mark a value as erroneous / rejected (keep the rest).
_BAD_Q = {"3", "7"}
_MANDATORY_LEN = 105


class SurfaceObservation(BaseModel):
    """One hourly ISH surface observation, mandatory-section fields (missing → ``None``)."""

    model_config = ConfigDict(extra="forbid")

    time: str  # ISO-8601 UTC (from the ISH YYYYMMDD/HHMM)
    wind_dir_deg: int | None
    wind_speed_ms: float | None
    air_temp_c: float | None
    dew_point_c: float | None
    ceiling_m: int | None
    sea_level_pressure_hpa: float | None


class SurfaceSeries(BaseModel):
    """A station-year of ISD surface obs + the raw ISHD text for the AERMET surface file."""

    model_config = ConfigDict(extra="forbid")

    station_id: str  # "USAF-WBAN"
    usaf: str
    wban: str
    call_sign: str | None
    latitude: float | None
    longitude: float | None
    elevation_m: float | None
    year: int
    observations: list[SurfaceObservation]
    raw_ishd: str  # verbatim ISH lines — AERMET's SURFACE ... ISHD input

    def coverage_fraction(self) -> float:
        """Fraction of the year's ~8760 hours with at least an hourly observation present."""
        return round(len(self.observations) / 8760.0, 3)


def fetch_surface(
    *,
    station: str | None = None,
    year: int | None = None,
    settings: Settings | None = None,
) -> SurfaceSeries:
    """One station-year of NOAA ISD hourly surface obs (AERMET SURFACE / ISHD input).

    ``station`` is the ``"USAF-WBAN"`` id (e.g. ``"725330-14827"``); it defaults to
    ``settings.air_surface_station`` (per-site, SiteProfile seam → #1180). ``year`` defaults
    to ``settings.air_met_year``.
    """
    settings = settings or get_settings()
    station = station if station is not None else settings.air_surface_station
    year = year if year is not None else settings.air_met_year
    if not station or "-" not in station:
        raise ValueError(
            f"air_surface_station must be a 'USAF-WBAN' id, got {station!r} "
            "(set WATERMARK_AIR_SURFACE_STATION or pass station=)"
        )
    usaf, wban = station.split("-", 1)
    params = {"usaf": usaf, "wban": wban, "year": year}

    def fetch() -> Any:
        url = f"{settings.isd_base_url}/{year}/{usaf}-{wban}-{year}.gz"
        resp = httpx.get(url, timeout=settings.air_request_timeout_s, follow_redirects=True)
        resp.raise_for_status()
        return gzip.decompress(resp.content).decode("latin-1")

    text: str = cached_get(_CONNECTOR, params, fetch, settings=settings)
    return _parse(text, usaf=usaf, wban=wban, year=year)


def _num(raw: str, *, scale: float = 1.0, signed: bool = False) -> float | None:
    token = raw.strip()
    if not token or token in _MISSING or set(token.lstrip("+-")) == {"9"}:
        return None
    try:
        return int(token) / scale if signed or scale != 1.0 else int(token)
    except ValueError:
        return None


def _kept(raw_val: str, flag: str, *, scale: float, signed: bool) -> float | None:
    if flag.strip() in _BAD_Q:
        return None
    return _num(raw_val, scale=scale, signed=signed)


def _kept_int(raw_val: str, flag: str) -> int | None:
    """A QC-kept unscaled integer mandatory field (wind direction °, ceiling m), or ``None``."""
    val = _kept(raw_val, flag, scale=1.0, signed=False)
    return int(val) if val is not None else None


def _parse(text: str, *, usaf: str, wban: str, year: int) -> SurfaceSeries:
    """Parse the ISH mandatory section of each line; keep the raw text for AERMET."""
    obs: list[SurfaceObservation] = []
    lat = lon = elev = None
    call: str | None = None
    for line in text.splitlines():
        if len(line) < _MANDATORY_LEN:
            continue
        if lat is None:
            lat = _num(line[_SL_LAT], scale=1000.0, signed=True)
            lon = _num(line[_SL_LON], scale=1000.0, signed=True)
            elev = _num(line[_SL_ELEV], scale=1.0, signed=True)
            call_raw = line[_SL_CALL].strip()
            call = call_raw if call_raw and call_raw != "99999" else None
        date, hhmm = line[_SL_DATE], line[_SL_TIME]
        iso = f"{date[0:4]}-{date[4:6]}-{date[6:8]}T{hhmm[0:2]}:{hhmm[2:4]}:00Z"
        obs.append(
            SurfaceObservation(
                time=iso,
                wind_dir_deg=_kept_int(line[_SL_WIND_DIR], line[_SL_WIND_DIR_Q]),
                wind_speed_ms=_kept(
                    line[_SL_WIND_SPD], line[_SL_WIND_SPD_Q], scale=10.0, signed=True
                ),
                air_temp_c=_kept(line[_SL_TEMP], line[_SL_TEMP_Q], scale=10.0, signed=True),
                dew_point_c=_kept(line[_SL_DEW], line[_SL_DEW_Q], scale=10.0, signed=True),
                ceiling_m=_kept_int(line[_SL_CEIL], line[_SL_CEIL_Q]),
                sea_level_pressure_hpa=_kept(
                    line[_SL_SLP], line[_SL_SLP_Q], scale=10.0, signed=True
                ),
            )
        )
    return SurfaceSeries(
        station_id=f"{usaf}-{wban}",
        usaf=usaf,
        wban=wban,
        call_sign=call,
        latitude=lat,
        longitude=lon,
        elevation_m=elev,
        year=year,
        observations=obs,
        raw_ishd=text,
    )
