"""US EIA API v2 — consumer energy prices + retail sales for the state/region.

The consumer-price half of the demand thread (issue #91): residential electricity
price, residential natural-gas price, and total electricity retail sales, against
which the data-center load's pressure is screened. We use EIA's uniform
``/v2/seriesid/{id}`` route so every pull is one cached call. The ``response.data``
rows carry ``period`` plus a **series-specific value column** named after the data
column (``price`` for the price series, ``sales`` for the sales series, ``value`` for
the natural-gas series) — *not* a uniform ``value`` field — so each series declares
its value column (``_SERIES[...]["col"]``) and the latest point is read **by name**,
never by index. Keyed: a free key read from
``settings.eia_api_key`` (``BOSC_EIA_API_KEY``), sent only on the live request and
never part of the cache key or the committed fixture.

The three series that anchor Ohio's consumer energy costs:

* ``ELEC.PRICE.OH-RES.A`` — residential electricity price (cents/kWh, annual).
* ``ELEC.SALES.OH-ALL.A`` — total electricity retail sales, all sectors (million kWh).
* ``NG.N3010OH3.A`` — residential natural-gas price ($/Mcf, annual).
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from bosc.config import Settings, get_settings
from bosc.connectors import cached_get
from bosc.economics.model import ConsumerEnergyCosts, ConsumerEnergyPrice
from bosc.hydrology.model import ProvenancedValue

# The Ohio consumer-energy series this thread pulls. Keyed by EIA legacy series id;
# unit is the EIA-reported unit (recorded for provenance, not parsed from the digits).
# ``col`` is the EIA data-column name the value lives under on the /v2/seriesid route
# (it varies by series; the route does NOT expose a uniform ``value`` field).
_SERIES: dict[str, dict[str, str]] = {
    "ELEC.PRICE.OH-RES.A": {
        "label": "Ohio residential electricity price",
        "fuel": "electricity",
        "metric": "price",
        "unit": "cents/kWh",
        "col": "price",
    },
    "ELEC.SALES.OH-ALL.A": {
        "label": "Ohio electricity retail sales (all sectors)",
        "fuel": "electricity",
        "metric": "sales",
        "unit": "million kWh",
        "col": "sales",
    },
    "NG.N3010OH3.A": {
        "label": "Ohio residential natural-gas price",
        "fuel": "natural_gas",
        "metric": "price",
        "unit": "$/Mcf",
        "col": "value",
    },
    # --- US national series (the federal backdrop, #98). `area: US`. ---
    "ELEC.GEN.ALL-US-99.A": {
        "label": "US total electricity net generation (all sectors)",
        "fuel": "electricity",
        "metric": "generation",
        "unit": "thousand MWh",
        "col": "generation",
        "area": "US",
    },
    "ELEC.PRICE.US-ALL.A": {
        "label": "US average retail electricity price (all sectors)",
        "fuel": "electricity",
        "metric": "price",
        "unit": "cents/kWh",
        "col": "price",
        "area": "US",
    },
}

# The Ohio consumer trio `fetch_consumer_energy` assembles by default — an explicit list
# so adding other series (e.g. the US-national ones above) to `_SERIES` does not leak
# into the consumer-energy dataset.
_OH_CONSUMER_SERIES: tuple[str, ...] = (
    "ELEC.PRICE.OH-RES.A",
    "ELEC.SALES.OH-ALL.A",
    "NG.N3010OH3.A",
)

# Row fields on the /v2/seriesid route that are never the value (period + the dimension
# labels EIA echoes back). Used only by the value-column fallback below.
_NON_VALUE_FIELDS = frozenset(
    {"period", "stateid", "stateDescription", "sectorid", "sectorName", "seriesId", "units"}
)


def _row_value(row: dict[str, Any], col: str) -> float | None:
    """The numeric value of an EIA seriesid row, read from its declared column.

    Reads ``row[col]`` when present; otherwise falls back to the sole numeric column
    that is not ``period``, a dimension label, or a ``*-units`` string — so a series
    whose column EIA renames still resolves rather than silently returning nothing.
    """
    v = row.get(col)
    if v is not None and not isinstance(v, bool):
        return float(v)
    for k, val in row.items():
        if k in _NON_VALUE_FIELDS or k.endswith("-units"):
            continue
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val)
    return None


class EiaError(RuntimeError):
    """The EIA API returned an unusable response (most often a missing/invalid key).

    EIA answers a bad/absent key with an error JSON or an HTML page; this is raised on
    a body without the expected ``response.data`` so the failure is clear, not cryptic.
    """


def _latest_point(payload: dict[str, Any], value_col: str) -> dict[str, Any]:
    """The most recent ``{period, value}`` row from an EIA v2 seriesid payload.

    ``value_col`` is the series' EIA data-column name (``price`` / ``sales`` / ``value``).
    EIA returns rows newest-first when sorted by period desc; we defend against either
    order by taking the max period. The value is read by column name (with a fallback,
    see :func:`_row_value`); the period is read from ``period``.
    """
    data = (((payload or {}).get("response") or {}).get("data")) or []
    rows = [r for r in data if _row_value(r, value_col) is not None]
    if not rows:
        raise EiaError(f"EIA response carried no data points (value column {value_col!r})")
    best = max(rows, key=lambda r: str(r.get("period", "")))
    value = _row_value(best, value_col)
    assert value is not None  # guaranteed by the rows filter above
    return {"period": str(best.get("period", "")), "value": value}


def fetch_eia_series(series_id: str, *, settings: Settings | None = None) -> ConsumerEnergyPrice:
    """One EIA consumer-energy series, reduced to its latest annual point (cached)."""
    settings = settings or get_settings()
    meta = _SERIES.get(series_id)
    if meta is None:
        raise ValueError(f"unknown EIA series id {series_id!r}; known: {sorted(_SERIES)}")
    # The api key is deliberately excluded from the cache-key params (a secret that
    # must not vary the key); it is added only inside the live fetch.
    params = {"connector": "eia", "route": "seriesid", "series_id": series_id}

    def fetch() -> Any:
        query: dict[str, str] = {}
        if settings.eia_api_key:
            query["api_key"] = settings.eia_api_key
        resp = httpx.get(
            f"{settings.eia_base_url}/seriesid/{series_id}",
            params=query,
            timeout=settings.econ_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        try:
            body = resp.json()
        except json.JSONDecodeError as exc:
            hint = "invalid BOSC_EIA_API_KEY" if settings.eia_api_key else "no key set"
            raise EiaError(f"EIA returned non-JSON ({hint}): {resp.text[:60]!r}") from exc
        # Reduce to the latest point so the cached payload / fixture stays small.
        return _latest_point(body, meta["col"])

    payload = cast(
        "dict[str, Any]",
        cached_get(
            "eia",
            params,
            fetch,
            cache_dir=settings.econ_cache_dir,
            offline=settings.econ_offline,
            fixtures_dir=settings.econ_fixtures_dir,
        ),
    )
    cite = f"EIA API v2 seriesid {series_id} ({payload['period']})"
    return ConsumerEnergyPrice(
        series_id=series_id,
        label=meta["label"],
        fuel=meta["fuel"],
        metric=meta["metric"],
        period=str(payload["period"]),
        area=meta.get("area", settings.eia_state),  # national series set area="US"
        value=ProvenancedValue.from_connector(float(payload["value"]), meta["unit"], citation=cite),
    )


def fetch_consumer_energy(
    *, series_ids: list[str] | None = None, settings: Settings | None = None
) -> ConsumerEnergyCosts:
    """Assemble the state's consumer energy-cost dataset (price + sales) from EIA."""
    settings = settings or get_settings()
    ids = series_ids or list(_OH_CONSUMER_SERIES)
    prices = [fetch_eia_series(sid, settings=settings) for sid in ids]
    return ConsumerEnergyCosts(
        area=settings.eia_state,
        area_name="Ohio",
        prices=prices,
        note=(
            "EIA API v2 (seriesid route): residential electricity + natural-gas prices "
            "and total electricity retail sales for Ohio. Annual averages; regenerable "
            "via `bosc eia` with BOSC_EIA_API_KEY."
        ),
    )
