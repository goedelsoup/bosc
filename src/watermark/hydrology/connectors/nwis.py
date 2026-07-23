"""USGS NWIS streamflow connector (Instantaneous Values service).

Grounds the water balance in *real* river flow: discharge (parameter ``00060``,
cfs) and gage height (``00065``, ft) at the gauges bracketing the Lima loop. Used
two ways:

* :func:`fetch_streamflow` — the latest reading per station, as ``connector``-sourced
  context (e.g. how much water the Ottawa is actually carrying right now).
* :func:`observed_min_discharge` — the minimum discharge over a recent window, a
  ``derived`` cross-check on the low-flow condition. **This is not the regulatory
  7Q10** (a fitted 7-day/10-year statistic); the cited 7Q10 lives in
  :mod:`watermark.hydrology.lowflow`. This value only sanity-checks it.
* :func:`fetch_instantaneous_series` — the *full* sub-daily record per parameter over
  a date window (discharge plus the water-quality sondes), for reading a continuous
  monitor against an event timeline (e.g. the Maumee-at-Waterville gage through the
  Napoleon / Huston Creek spill, #1498).

Synchronous (``httpx.Client``) to match BOSC's otherwise-sync pipeline layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict, model_validator

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get
from watermark.hydrology.model import ProvenancedValue

DISCHARGE_CFS = "00060"
GAGE_HEIGHT_FT = "00065"
WATER_TEMP_C = "00010"  # NWIS water temperature, degrees Celsius
DISSOLVED_OXYGEN_MG_L = "00300"
TURBIDITY_FNU = "63680"
PHYCOCYANIN_UG_L = "32319"  # fPC — cyanobacterial pigment fluorescence (NOT 32316 = chlorophyll-a)
DAILY_MEAN = "00003"  # NWIS statistic code: daily mean (the Daily Values service)

# NWIS point qualifier codes (the ``qualifiers`` array carried on every value). "P" =
# provisional (subject to revision), "A" = approved (review complete), "e" = estimated. A
# real-time IV reading is always provisional; the DV historical record is mostly approved.
# Captured per point (#1602) so a provisional value can be filtered out of a design-low-flow
# fit or down-weighted in the water balance — before this they entered indistinguishably.
PROVISIONAL_CODE = "P"
APPROVED_CODE = "A"


class NwisReading(BaseModel):
    """The latest reading at one station for one parameter."""

    model_config = ConfigDict(extra="forbid")

    site_no: str
    name: str
    parameter_cd: str
    value: float | None
    unit: str
    datetime: str | None
    # NWIS qualifier codes on the reported value (e.g. ``["P"]`` provisional, ``["A"]``
    # approved). Empty when NWIS carries none; a real-time IV reading is normally ``["P"]``.
    qualifiers: list[str] = []
    lat: float | None = None
    lon: float | None = None

    @property
    def provisional(self) -> bool:
        """True when the reported value is NWIS provisional (``P`` — subject to revision)."""
        return PROVISIONAL_CODE in self.qualifiers


class InstantaneousSeries(BaseModel):
    """One gage's full sub-daily record for one parameter over a date window (IV service).

    Parallel ``timestamps`` / ``values`` lists, ascending; timestamps are ISO datetimes
    with the gage's UTC offset, carried verbatim from NWIS. Unlike
    :class:`NwisReading` (the latest point only), this is the dense event record a
    monitor read needs — every 15-minute sonde reading through a spill window.
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    name: str
    parameter_cd: str
    variable_name: str  # NWIS variableName, e.g. "Turbidity, water, unfiltered, ... FNU"
    unit: str
    lat: float | None = None
    lon: float | None = None
    timestamps: list[str]
    values: list[float]
    # Per-point NWIS qualifier codes, parallel to ``values`` (#1602). Empty for a
    # hand-built series; a live event record is normally all ``["P"]`` (provisional).
    qualifiers: list[list[str]] = []

    @model_validator(mode="after")
    def _qualifiers_parallel(self) -> InstantaneousSeries:
        if self.qualifiers and len(self.qualifiers) != len(self.timestamps):
            raise ValueError("qualifiers must be parallel to timestamps/values")
        return self

    def __len__(self) -> int:
        return len(self.timestamps)

    def points(self) -> list[tuple[str, float]]:
        """The (timestamp, value) pairs, no-data already dropped at parse time."""
        return list(zip(self.timestamps, self.values, strict=True))

    @property
    def provisional(self) -> bool:
        """True when any point in the record is NWIS provisional (``P``, #1602)."""
        return any(PROVISIONAL_CODE in q for q in self.qualifiers)


class DailyDischargeSeries(BaseModel):
    """A gage's daily-mean discharge record (the Daily Values service).

    Parallel ``dates`` / ``values_cfs`` lists keep a multi-decade record compact.
    Unlike :func:`fetch_streamflow` (the latest instantaneous reading), this is the
    long record a low-flow frequency analysis needs (:mod:`watermark.hydrology.lowflow_frequency`).
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
    # Per-day NWIS qualifier codes, parallel to ``values_cfs`` (#1602). Empty for a
    # hand-built series; a fetched record carries ``["A"]`` (approved) or ``["P"]``
    # (provisional — unreviewed recent water-years) per day.
    qualifiers: list[list[str]] = []

    @model_validator(mode="after")
    def _qualifiers_parallel(self) -> DailyDischargeSeries:
        if self.qualifiers and len(self.qualifiers) != len(self.dates):
            raise ValueError("qualifiers must be parallel to dates/values_cfs")
        return self

    def __len__(self) -> int:
        return len(self.dates)

    def points(self, *, include_provisional: bool = True) -> list[tuple[str, float]]:
        """The (date, cfs) pairs, no-data already dropped at parse time.

        Set ``include_provisional=False`` to drop NWIS provisional (``P``) days — the
        mitigation for the known bias of fitting a design low-flow statistic over
        unreviewed recent water-years (#1602). A series with no qualifiers recorded (a
        hand-built series) returns every point regardless: absence of a code is not
        evidence of provisionality.
        """
        pairs = list(zip(self.dates, self.values_cfs, strict=True))
        if include_provisional or not self.qualifiers:
            return pairs
        return [
            pair
            for pair, quals in zip(pairs, self.qualifiers, strict=True)
            if PROVISIONAL_CODE not in quals
        ]

    @property
    def provisional_fraction(self) -> float:
        """Share of days flagged NWIS provisional (0.0 when no qualifiers are recorded)."""
        if not self.qualifiers:
            return 0.0
        provisional = sum(1 for quals in self.qualifiers if PROVISIONAL_CODE in quals)
        return provisional / len(self.qualifiers)


def _nwis_request(
    settings: Settings,
    service: str,
    query: dict[str, Any],
    *,
    ttl_hours: int | None = None,
) -> dict[str, Any]:
    """Perform (or replay from cache) one NWIS request against ``service`` (``iv``/``dv``).

    ``ttl_hours`` overrides the subsystem default so the "right now" IV service can
    carry a short freshness window (see :attr:`Settings.nwis_iv_cache_ttl_hours`); the
    ``dv`` historical service inherits the slow-moving hydro default.
    """

    def fetch() -> Any:
        url = f"{settings.nwis_base_url}/{service}/"
        resp = httpx.get(url, params=query, timeout=settings.hydro_request_timeout_s)
        resp.raise_for_status()
        return resp.json()

    # Namespace the cache key by service so iv and dv requests never collide.
    return cast(
        "dict[str, Any]",
        cached_get(
            "nwis", {"_service": service, **query}, fetch, settings=settings, ttl_hours=ttl_hours
        ),
    )


def _iv_request(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    """Perform (or replay from cache) one NWIS IV request, return parsed JSON.

    The IV service is "right now" data, so it caches under a short TTL
    (``nwis_iv_cache_ttl_hours``) rather than the week-long hydro default.
    """
    return _nwis_request(
        settings,
        "iv",
        {"format": "json", "siteStatus": "active", **params},
        ttl_hours=settings.nwis_iv_cache_ttl_hours,
    )


def _series(ts: dict[str, Any]) -> list[tuple[str, float, list[str]]]:
    """Extract (dateTime, value, qualifiers) triples from one NWIS timeSeries block.

    No-data points are dropped. Each point's ``qualifiers`` array (P/A/e codes) is
    carried through so a provisional value stays distinguishable from an approved one
    (#1602) — before this the codes were silently discarded.
    """
    out: list[tuple[str, float, list[str]]] = []
    for values_block in ts.get("values", []):
        for point in values_block.get("value", []):
            raw = point.get("value")
            try:
                num = float(raw)
            except (TypeError, ValueError):
                continue
            if num <= -999999:  # NWIS no-data sentinel
                continue
            quals = [str(q) for q in (point.get("qualifiers") or [])]
            out.append((point.get("dateTime", ""), num, quals))
    return out


def _time_series(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The ``value.timeSeries`` blocks of a NWIS payload, raising on envelope drift (#1602).

    NWIS wraps every response as ``{"value": {"timeSeries": [...]}}``. A *missing*
    ``value`` or ``timeSeries`` key means the payload isn't a NWIS response at all (schema
    drift, or an error document) — raise, rather than degrade to ``[]``, which a caller
    reads as "gage carrying no data" instead of "connector failed". An *empty*
    ``timeSeries`` list is a legitimate "no matching series" and passes through.
    """
    value = payload.get("value")
    if not isinstance(value, Mapping):
        raise ValueError("NWIS payload missing 'value' envelope (schema drift)")
    time_series = value.get("timeSeries")
    if not isinstance(time_series, list):
        raise ValueError("NWIS payload missing 'value.timeSeries' (schema drift)")
    return cast("list[dict[str, Any]]", time_series)


def _ts_key(point: tuple[str, float, list[str]]) -> datetime:
    """Chronological sort key for a ``(dateTime, value, qualifiers)`` triple.

    Parses the NWIS ISO timestamp so a series that spans a daylight-saving offset change
    orders by the real instant — a raw-string sort mis-orders across a fall-back, when the
    UTC offset shifts mid-record. Within one ``timeSeries`` the timestamps are homogeneous
    (all tz-aware for IV, all naive for DV), so the parsed keys are mutually comparable.
    """
    return datetime.fromisoformat(point[0])


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
    for ts in _time_series(payload):
        site_no, name, lat, lon, parameter_cd, unit = _site_info(ts)
        series = _series(ts)
        last = series[-1] if series else ("", None, [])
        readings.append(
            NwisReading(
                site_no=site_no,
                name=name,
                parameter_cd=parameter_cd,
                value=last[1],
                unit=unit,
                datetime=last[0] or None,
                qualifiers=last[2],
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
    for ts in _time_series(payload):
        _, _, _, _, parameter_cd, _ = _site_info(ts)
        if parameter_cd == DISCHARGE_CFS:
            values.extend(v for _, v, _ in _series(ts))
    if not values:
        return None
    return ProvenancedValue.derived(
        min(values),
        "cfs",
        citation=f"NWIS {site_no} min instantaneous discharge over P{days}D (not 7Q10)",
        confidence="low",
    )


def observed_water_temperature(
    site_no: str,
    *,
    days: int = 30,
    settings: Settings | None = None,
) -> ProvenancedValue | None:
    """The warm-season peak observed water temperature (deg C) at a gage over the last ``days``.

    A live ``connector`` reading of NWIS parameter ``00010`` — the background receiving-water
    temperature the thermal-discharge screen (:mod:`watermark.hydrology.thermal`) adds a heat
    load's fully-mixed rise onto. Returns the **maximum** over the window (the design-relevant
    warm extreme, the peer of :func:`observed_min_discharge`'s low-flow minimum), tagged with
    the reading's timestamp so a stale/off-season replay is legible. Returns ``None`` when the
    gage carries no ``00010`` block (many small gages report only discharge) — the screen then
    falls back to a stated design ambient rather than fabricating one.
    """
    settings = settings or get_settings()
    params = {"sites": site_no, "parameterCd": WATER_TEMP_C, "period": f"P{days}D"}
    payload = _iv_request(settings, params)
    readings: list[tuple[str, float]] = []
    for ts in _time_series(payload):
        _, _, _, _, parameter_cd, _ = _site_info(ts)
        if parameter_cd == WATER_TEMP_C:
            readings.extend((t, v) for t, v, _ in _series(ts))
    if not readings:
        return None
    asof, peak = max(readings, key=lambda tv: tv[1])
    return ProvenancedValue.from_connector(
        peak,
        "degC",
        citation=f"NWIS {site_no} peak instantaneous water temperature (00010) over P{days}D",
        asof=asof,
        confidence="medium",
    )


def fetch_instantaneous_series(
    site_no: str,
    *,
    parameter_cds: Sequence[str],
    start_date: str,
    end_date: str,
    settings: Settings | None = None,
) -> list[InstantaneousSeries]:
    """The full sub-daily record per parameter for one gage over a date window.

    One :class:`InstantaneousSeries` per NWIS timeSeries block; parameters the gage
    doesn't carry are simply absent from the result (never fabricated). No-data
    points are dropped at parse time (:func:`_series`). Same short-TTL IV caching
    as :func:`fetch_streamflow` — a window ending "today" keeps growing, so a stale
    replay would silently truncate the event record.
    """
    settings = settings or get_settings()
    payload = _iv_request(
        settings,
        {
            "sites": site_no,
            "parameterCd": ",".join(parameter_cds),
            "startDT": start_date,
            "endDT": end_date,
        },
    )
    out: list[InstantaneousSeries] = []
    for ts in _time_series(payload):
        resolved_site, name, lat, lon, parameter_cd, unit = _site_info(ts)
        series = sorted(_series(ts), key=_ts_key)  # ascending by parsed instant
        if not series:
            continue
        out.append(
            InstantaneousSeries(
                site_no=resolved_site or site_no,
                name=name,
                parameter_cd=parameter_cd,
                variable_name=ts.get("variable", {}).get("variableName", ""),
                unit=unit,
                lat=lat,
                lon=lon,
                timestamps=[t for t, _, _ in series],
                values=[v for _, v, _ in series],
                qualifiers=[q for _, _, q in series],
            )
        )
    return out


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
    for ts in _time_series(payload):
        resolved_site, name, lat, lon, parameter_cd, unit = _site_info(ts)
        if parameter_cd != DISCHARGE_CFS:
            continue
        series = sorted(_series(ts), key=_ts_key)  # ascending by parsed instant
        return DailyDischargeSeries(
            site_no=resolved_site or site_no,
            name=name,
            parameter_cd=parameter_cd,
            stat_cd=statistic_cd,
            unit=unit,
            lat=lat,
            lon=lon,
            dates=[dt[:10] for dt, _, _ in series],
            values_cfs=[v for _, v, _ in series],
            qualifiers=[q for _, _, q in series],
        )
    raise ValueError(f"NWIS {site_no}: no discharge daily values for {start_date}..{end_date}")
