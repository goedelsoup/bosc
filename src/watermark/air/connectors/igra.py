"""NOAA IGRA v2 upper-air connector — the AERMET UPPERAIR input.

Pulls one station-year of twice-daily radiosonde soundings from NOAA's Integrated Global
Radiosonde Archive (IGRA v2). The raw IGRA text (sounding headers + pressure-level records,
in the fixed-column IGRA v2 layout) is passed through verbatim to the AERMET upper-air
input file; alongside it we parse each sounding's header and levels (pressure, geopotential
height, temperature, dew-point depression, wind) into typed :class:`Sounding`s for QA.

Source: ``{igra_base_url}/access/data-por/{station}-data.txt.zip`` — NCEI's per-station
period-of-record zip; we extract the station file and keep only the requested year's
soundings (so the cached payload / committed fixture stays small). Same connector cache /
offline / committed-fixture discipline as the other air connectors.

Field positions, scale factors, and missing sentinels follow the NOAA *IGRA v2 readme*.
"""

from __future__ import annotations

import io
import zipfile
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.air.connectors._cache import cached_get
from watermark.config import Settings, get_settings

_CONNECTOR = "igra"
_MISSING = {-9999, -8888}  # IGRA v2: -9999 = missing, -8888 = removed / not applicable


class SoundingLevel(BaseModel):
    """One pressure level of a sounding (missing fields → ``None``)."""

    model_config = ConfigDict(extra="forbid")

    pressure_hpa: float | None  # IGRA stores Pa; exposed as hPa (AERMOD's unit)
    height_m: int | None  # geopotential height
    temperature_c: float | None
    dewpoint_depression_c: float | None
    wind_dir_deg: int | None
    wind_speed_ms: float | None


class Sounding(BaseModel):
    """One radiosonde ascent: synoptic time + its pressure levels."""

    model_config = ConfigDict(extra="forbid")

    time: str  # ISO-8601 UTC (from the IGRA header YEAR/MONTH/DAY/HOUR)
    release_time: str | None  # HH:MM balloon-release time, when reported
    n_levels: int
    levels: list[SoundingLevel]


class SoundingSeries(BaseModel):
    """A station-year of IGRA soundings + the raw IGRA text for the AERMET upper-air file."""

    model_config = ConfigDict(extra="forbid")

    station_id: str  # IGRA 11-char id, e.g. "USM00072426"
    latitude: float | None
    longitude: float | None
    year: int
    soundings: list[Sounding]
    raw_igra: str  # verbatim IGRA v2 records — AERMET's UPPERAIR input


def fetch_upperair(
    *,
    station: str | None = None,
    year: int | None = None,
    settings: Settings | None = None,
) -> SoundingSeries:
    """One station-year of NOAA IGRA v2 soundings (AERMET UPPERAIR input).

    ``station`` is the IGRA 11-char id (e.g. ``"USM00072426"``); it defaults to
    ``settings.air_upperair_station`` (per-site, SiteProfile seam → #1180). ``year`` defaults
    to ``settings.air_met_year``.
    """
    settings = settings or get_settings()
    station = station if station is not None else settings.air_upperair_station
    year = year if year is not None else settings.air_met_year
    if not station:
        raise ValueError(
            "air_upperair_station must be an IGRA station id "
            "(set WATERMARK_AIR_UPPERAIR_STATION or pass station=)"
        )
    params = {"station": station, "year": year}

    def fetch() -> Any:
        url = f"{settings.igra_base_url}/access/data-por/{station}-data.txt.zip"
        resp = httpx.get(url, timeout=settings.air_request_timeout_s, follow_redirects=True)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".txt"))
            text = zf.read(name).decode("latin-1")
        return _filter_year(text, year)

    text: str = cached_get(_CONNECTOR, params, fetch, settings=settings)
    return _parse(text, station=station, year=year)


def _filter_year(text: str, year: int) -> str:
    """Keep only the blocks (header + its level lines) whose header YEAR matches ``year``."""
    kept: list[str] = []
    keep = False
    for line in text.splitlines():
        if line.startswith("#"):
            keep = line[13:17].strip() == str(year)
        if keep:
            kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def _int(raw: str) -> int | None:
    try:
        val = int(raw)
    except ValueError:
        return None
    return None if val in _MISSING else val


def _parse(text: str, *, station: str, year: int) -> SoundingSeries:
    soundings: list[Sounding] = []
    lat = lon = None
    header: str | None = None
    levels: list[SoundingLevel] = []

    def flush() -> None:
        nonlocal header
        if header is None:
            return
        soundings.append(_sounding(header, levels))

    for line in text.splitlines():
        if line.startswith("#"):
            flush()
            header = line
            levels = []
            if lat is None:
                lat_i, lon_i = _int(line[55:62]), _int(line[63:71])
                lat = lat_i / 10000.0 if lat_i is not None else None
                lon = lon_i / 10000.0 if lon_i is not None else None
        elif header is not None and len(line) >= 51:
            levels.append(_level(line))
    flush()

    return SoundingSeries(
        station_id=station,
        latitude=lat,
        longitude=lon,
        year=year,
        soundings=soundings,
        raw_igra=text,
    )


def _sounding(header: str, levels: list[SoundingLevel]) -> Sounding:
    year, month, day, hour = header[13:17], header[18:20], header[21:23], header[24:26]
    reltime = header[27:31].strip()
    rel = (
        f"{reltime[0:2]}:{reltime[2:4]}"
        if reltime.isdigit() and reltime not in {"9999", "-999"}
        else None
    )
    hh = "00" if hour.strip() in {"99", "-9"} else hour
    return Sounding(
        time=f"{year}-{month}-{day}T{hh}:00:00Z",
        release_time=rel,
        n_levels=len(levels),
        levels=levels,
    )


def _level(line: str) -> SoundingLevel:
    press_pa = _int(line[9:15])
    temp = _int(line[22:27])
    dpdp = _int(line[34:39])
    wspd = _int(line[46:51])
    return SoundingLevel(
        pressure_hpa=press_pa / 100.0 if press_pa is not None else None,
        height_m=_int(line[16:21]),
        temperature_c=temp / 10.0 if temp is not None else None,
        dewpoint_depression_c=dpdp / 10.0 if dpdp is not None else None,
        wind_dir_deg=_int(line[40:45]),
        wind_speed_ms=wspd / 10.0 if wspd is not None else None,
    )
