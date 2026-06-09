"""USGS NWIS streamflow connector (Instantaneous Values service).

Grounds the water balance in *real* river flow: discharge (parameter ``00060``,
cfs) and gage height (``00065``, ft) at the gauges bracketing the Lima loop. Used
two ways:

* :func:`fetch_streamflow` — the latest reading per station, as ``connector``-sourced
  context (e.g. how much water the Ottawa is actually carrying right now).
* :func:`observed_min_discharge` — the minimum discharge over a recent window, a
  ``derived`` cross-check on the low-flow condition. **This is not the regulatory
  7Q10** (a fitted 7-day/10-year statistic); the cited 7Q10 lives in
  :mod:`bosc.hydrology.lowflow`. This value only sanity-checks it.

Synchronous (``httpx.Client``) to match BOSC's otherwise-sync pipeline layer.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors._cache import cached_get
from bosc.hydrology.model import ProvenancedValue

DISCHARGE_CFS = "00060"
GAGE_HEIGHT_FT = "00065"
DAILY_MEAN = "00003"  # NWIS statistic code: daily mean (the Daily Values service)


class NwisReading(BaseModel):
    """The latest reading at one station for one parameter."""

    model_config = ConfigDict(extra="forbid")

    site_no: str
    name: str
    parameter_cd: str
    value: float | None
    unit: str
    datetime: str | None
    lat: float | None = None
    lon: float | None = None


class DailyDischargeSeries(BaseModel):
    """A gage's daily-mean discharge record (the Daily Values service).

    Parallel ``dates`` / ``values_cfs`` lists keep a multi-decade record compact.
    Unlike :func:`fetch_streamflow` (the latest instantaneous reading), this is the
    long record a low-flow frequency analysis needs (:mod:`bosc.hydrology.lowflow_frequency`).
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    name: str
    parameter_cd: str = DISCHARGE_CFS
    stat_cd: str = DAILY_MEAN
    unit: str
    lat: float | None = None
    lon: float | None = None
    dates: list[str]  # ISO calendar dates, ascending
    values_cfs: list[float]

    def __len__(self) -> int:
        return len(self.dates)

    def points(self) -> list[tuple[str, float]]:
        """The (date, cfs) pairs, no-data already dropped at parse time."""
        return list(zip(self.dates, self.values_cfs, strict=True))


def _nwis_request(settings: Settings, service: str, query: dict[str, Any]) -> dict[str, Any]:
    """Perform (or replay from cache) one NWIS request against ``service`` (``iv``/``dv``)."""

    def fetch() -> Any:
        url = f"{settings.nwis_base_url}/{service}/"
        resp = httpx.get(url, params=query, timeout=settings.hydro_request_timeout_s)
        resp.raise_for_status()
        return resp.json()

    return cast("dict[str, Any]", cached_get("nwis", query, fetch, settings=settings))


def _iv_request(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    """Perform (or replay from cache) one NWIS IV request, return parsed JSON."""
    return _nwis_request(settings, "iv", {"format": "json", "siteStatus": "active", **params})


def _series(ts: dict[str, Any]) -> list[tuple[str, float]]:
    """Extract (dateTime, value) pairs from one NWIS timeSeries block, dropping no-data."""
    out: list[tuple[str, float]] = []
    for values_block in ts.get("values", []):
        for point in values_block.get("value", []):
            raw = point.get("value")
            try:
                num = float(raw)
            except (TypeError, ValueError):
                continue
            if num <= -999999:  # NWIS no-data sentinel
                continue
            out.append((point.get("dateTime", ""), num))
    return out


def _site_info(ts: dict[str, Any]) -> tuple[str, str, float | None, float | None, str, str]:
    info = ts.get("sourceInfo", {})
    name = info.get("siteName", "")
    codes = info.get("siteCode", [{}])
    site_no = codes[0].get("value", "") if codes else ""
    geo = info.get("geoLocation", {}).get("geogLocation", {})
    lat = _opt_float(geo.get("latitude"))
    lon = _opt_float(geo.get("longitude"))
    variable = ts.get("variable", {})
    var_codes = variable.get("variableCode", [{}])
    parameter_cd = var_codes[0].get("value", "") if var_codes else ""
    unit = variable.get("unit", {}).get("unitCode", "")
    return site_no, name, lat, lon, parameter_cd, unit


def _opt_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_streamflow(
    *,
    sites: list[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    settings: Settings | None = None,
) -> list[NwisReading]:
    """Latest discharge + gage-height reading per station, for the given sites or bbox."""
    settings = settings or get_settings()
    params: dict[str, Any] = {"parameterCd": f"{DISCHARGE_CFS},{GAGE_HEIGHT_FT}"}
    if sites is not None:
        params["sites"] = ",".join(sites)
    elif bbox is not None:
        params["bBox"] = ",".join(f"{c:.6f}" for c in bbox)
    else:
        params["sites"] = ",".join(settings.nwis_sites)

    payload = _iv_request(settings, params)
    readings: list[NwisReading] = []
    for ts in payload.get("value", {}).get("timeSeries", []):
        site_no, name, lat, lon, parameter_cd, unit = _site_info(ts)
        series = _series(ts)
        last = series[-1] if series else (None, None)
        readings.append(
            NwisReading(
                site_no=site_no,
                name=name,
                parameter_cd=parameter_cd,
                value=last[1],
                unit=unit,
                datetime=last[0] or None,
                lat=lat,
                lon=lon,
            )
        )
    return readings


def observed_min_discharge(
    site_no: str,
    *,
    days: int = 7,
    settings: Settings | None = None,
) -> ProvenancedValue | None:
    """Minimum observed discharge (cfs) at a site over the last ``days``.

    A *derived* cross-check on the low-flow condition — NOT the regulatory 7Q10.
    Returns ``None`` if the site reports no discharge data.
    """
    settings = settings or get_settings()
    params = {"sites": site_no, "parameterCd": DISCHARGE_CFS, "period": f"P{days}D"}
    payload = _iv_request(settings, params)
    values: list[float] = []
    for ts in payload.get("value", {}).get("timeSeries", []):
        _, _, _, _, parameter_cd, _ = _site_info(ts)
        if parameter_cd == DISCHARGE_CFS:
            values.extend(v for _, v in _series(ts))
    if not values:
        return None
    return ProvenancedValue.derived(
        min(values),
        "cfs",
        citation=f"NWIS {site_no} min instantaneous discharge over P{days}D (not 7Q10)",
        confidence="low",
    )


def fetch_daily_discharge(
    site_no: str,
    *,
    start_date: str,
    end_date: str,
    statistic_cd: str = DAILY_MEAN,
    settings: Settings | None = None,
) -> DailyDischargeSeries:
    """Fetch the daily-mean discharge record (cfs) for one gage over a date window.

    The long record behind a low-flow frequency analysis — distinct from
    :func:`fetch_streamflow` (the latest instantaneous reading). No-data points are
    dropped at parse time (see :func:`_series`). Raises ``ValueError`` if the gage
    reports no discharge daily values for the window.
    """
    settings = settings or get_settings()
    query = {
        "format": "json",
        "sites": site_no,
        "parameterCd": DISCHARGE_CFS,
        "statCd": statistic_cd,
        "startDT": start_date,
        "endDT": end_date,
    }
    payload = _nwis_request(settings, "dv", query)
    for ts in payload.get("value", {}).get("timeSeries", []):
        resolved_site, name, lat, lon, parameter_cd, unit = _site_info(ts)
        if parameter_cd != DISCHARGE_CFS:
            continue
        series = sorted(_series(ts))  # ascending by ISO dateTime
        return DailyDischargeSeries(
            site_no=resolved_site or site_no,
            name=name,
            parameter_cd=parameter_cd,
            stat_cd=statistic_cd,
            unit=unit,
            lat=lat,
            lon=lon,
            dates=[dt[:10] for dt, _ in series],
            values_cfs=[v for _, v in series],
        )
    raise ValueError(f"NWIS {site_no}: no discharge daily values for {start_date}..{end_date}")
