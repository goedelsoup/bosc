"""US EIA API v2 — consumer energy prices + retail sales for the state/region.

The consumer-price half of the demand thread (issue #91): residential electricity
price, residential natural-gas price, and total electricity retail sales, against
which the data-center load's pressure is screened. We use EIA's uniform
``/v2/seriesid/{id}`` route so every pull is one cached call. The ``response.data``
rows carry ``period`` plus a **series-specific value column** named after the data
column (``price`` for the price series, ``sales`` for the sales series, ``value`` for
the natural-gas series) — *not* a uniform ``value`` field — so each series declares
its value column (``_SERIES[...]["col"]``) and every point is read **by name**, never by
index. The connector keeps the **full annual series** (``points``) plus the latest point
as a convenience (issue #1111), not just the latest. Keyed: a free key read from
``settings.eia_api_key`` (``WATERMARK_EIA_API_KEY``), sent only on the live request and
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

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get
from watermark.economics.model import ConsumerEnergyCosts, ConsumerEnergyPrice, EnergyPricePoint
from watermark.hydrology.model import ProvenancedValue
from watermark.states import state_name

# EIA data-column metadata. ``col`` is the data-column name the value lives under on the
# /v2/seriesid route (it varies by series; the route does NOT expose a uniform ``value`` field);
# ``unit`` is the EIA-reported unit (recorded for provenance, not parsed from the digits).
#
# State consumer-energy series are templated by the two-letter state code — the same EIA legacy
# ids with the state substituted (OH-RES/OH-ALL/N3010OH3 → IN-RES/IN-ALL/N3010IN3). A new state
# is config (its name in watermark.states.STATE_NAME, the one map the grid stack reads too —
# H2/#1645), not a new hardcoded series; only the US-national backdrop series (#98) are static.

# Version of the *cached payload shape*. Part of the cache key (below), so a shape change
# invalidates prior entries by producing a new key rather than a hit on an incompatible
# payload. Bumped to 2 at the #1111 latest-point -> full-series (`{"points": [...]}`)
# migration; a stale pre-#1111 `{period, value}` entry would otherwise KeyError on read.
_PAYLOAD_SCHEMA = 2


def _state_consumer_series(state: str) -> dict[str, dict[str, str]]:
    """The state's residential-electricity, retail-sales, and residential-gas series (by id)."""
    name = state_name(state)
    return {
        f"ELEC.PRICE.{state}-RES.A": {
            "label": f"{name} residential electricity price",
            "fuel": "electricity",
            "metric": "price",
            "unit": "cents/kWh",
            "col": "price",
        },
        f"ELEC.SALES.{state}-ALL.A": {
            "label": f"{name} electricity retail sales (all sectors)",
            "fuel": "electricity",
            "metric": "sales",
            "unit": "million kWh",
            "col": "sales",
        },
        f"NG.N3010{state}3.A": {
            "label": f"{name} residential natural-gas price",
            "fuel": "natural_gas",
            "metric": "price",
            "unit": "$/Mcf",
            "col": "value",
        },
    }


def _consumer_series_ids(state: str) -> tuple[str, ...]:
    """The state consumer trio, in committed order (elec price, elec sales, gas price)."""
    return (f"ELEC.PRICE.{state}-RES.A", f"ELEC.SALES.{state}-ALL.A", f"NG.N3010{state}3.A")


_SERIES: dict[str, dict[str, str]] = {
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

    The fallback is safe *only* because exactly one such column exists. If EIA ever adds
    a second numeric non-dimension field (a revision counter, a secondary measure),
    guessing which one is the value would return a wrong number with full ``[verified]``
    provenance — exactly the drift by-name reads exist to prevent — so an ambiguous row
    raises :class:`EiaError` (the declared column name must be updated) rather than
    silently grabbing whichever iterates first.
    """
    v = row.get(col)
    if v is not None and not isinstance(v, bool):
        return float(v)
    candidates = [
        val
        for k, val in row.items()
        if k not in _NON_VALUE_FIELDS
        and not k.endswith("-units")
        and isinstance(val, (int, float))
        and not isinstance(val, bool)
    ]
    if len(candidates) > 1:
        raise EiaError(
            f"EIA row has {len(candidates)} numeric non-dimension columns; the value "
            f"column {col!r} is absent and the fallback is ambiguous — update the "
            f"declared column name for this series."
        )
    return float(candidates[0]) if candidates else None


class EiaError(RuntimeError):
    """The EIA API returned an unusable response (most often a missing/invalid key).

    EIA answers a bad/absent key with an error JSON or an HTML page; this is raised on
    a body without the expected ``response.data`` so the failure is clear, not cryptic.
    """


def _series_points(payload: dict[str, Any], value_col: str) -> list[dict[str, Any]]:
    """The full annual series as ``[{period, value}, ...]`` sorted oldest→newest.

    ``value_col`` is the series' EIA data-column name (``price`` / ``sales`` / ``value``).
    Rows are read by column name (with a fallback, see :func:`_row_value`); the period is
    read from ``period``. Keeping the full series (not just the latest point) lets the site
    chart the price/sales trend while the fixture stays tiny (issue #1111). Raises when no
    row carries a value, so an empty/garbled payload fails loudly rather than silently.
    """
    data = (((payload or {}).get("response") or {}).get("data")) or []
    points = [
        {"period": str(r.get("period", "")), "value": v}
        for r in data
        if (v := _row_value(r, value_col)) is not None
    ]
    if not points:
        raise EiaError(f"EIA response carried no data points (value column {value_col!r})")
    points.sort(key=lambda p: str(p["period"]))
    return points


def _latest_point(payload: dict[str, Any], value_col: str) -> dict[str, Any]:
    """The most recent ``{period, value}`` row from an EIA v2 seriesid payload.

    A convenience over :func:`_series_points` (the newest point); see it for the
    column/period semantics. EIA returns rows newest-first when sorted by period desc; we
    defend against either order by taking the latest of the sorted series.
    """
    return _series_points(payload, value_col)[-1]


def fetch_eia_series(series_id: str, *, settings: Settings | None = None) -> ConsumerEnergyPrice:
    """One EIA consumer-energy series with its full annual history + latest point (cached)."""
    settings = settings or get_settings()
    known = {**_state_consumer_series(settings.eia_state), **_SERIES}
    meta = known.get(series_id)
    if meta is None:
        raise ValueError(f"unknown EIA series id {series_id!r}; known: {sorted(known)}")
    # The api key is deliberately excluded from the cache-key params (a secret that
    # must not vary the key); it is added only inside the live fetch. ``schema`` versions the
    # cached payload shape so a shape change invalidates old entries (see _PAYLOAD_SCHEMA).
    params = {
        "connector": "eia",
        "route": "seriesid",
        "series_id": series_id,
        "schema": _PAYLOAD_SCHEMA,
    }

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
            hint = "invalid WATERMARK_EIA_API_KEY" if settings.eia_api_key else "no key set"
            raise EiaError(f"EIA returned non-JSON ({hint}): {resp.text[:60]!r}") from exc
        # Reduce to the annual {period, value} series so the cached payload / fixture stays
        # small but keeps the full trend (issue #1111), not just the latest point.
        return {"points": _series_points(body, meta["col"])}

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

    # Re-sort by period rather than trusting input order: a hand-edited or externally-sourced
    # cache/fixture payload may be unordered, so ``points[-1]`` must derive from ordering, not
    # trust (the live path sorts in _series_points; the cache/fixture path does not).
    points = sorted(
        (
            EnergyPricePoint(period=str(p["period"]), value=float(p["value"]))
            for p in payload["points"]
        ),
        key=lambda pt: pt.period,
    )
    latest = points[-1]
    cite = f"EIA API v2 seriesid {series_id} ({latest.period})"
    return ConsumerEnergyPrice(
        series_id=series_id,
        label=meta["label"],
        fuel=meta["fuel"],
        metric=meta["metric"],
        period=latest.period,
        area=meta.get("area", settings.eia_state),  # national series set area="US"
        value=ProvenancedValue.from_connector(
            latest.value, meta["unit"], citation=cite, asof=latest.period
        ),
        points=points,
    )


def fetch_consumer_energy(
    *, series_ids: list[str] | None = None, settings: Settings | None = None
) -> ConsumerEnergyCosts:
    """Assemble the state's consumer energy-cost dataset (price + sales) from EIA."""
    settings = settings or get_settings()
    name = state_name(settings.eia_state)
    ids = series_ids or list(_consumer_series_ids(settings.eia_state))
    prices = [fetch_eia_series(sid, settings=settings) for sid in ids]
    return ConsumerEnergyCosts(
        area=settings.eia_state,
        area_name=name,
        prices=prices,
        note=(
            f"EIA API v2 (seriesid route): residential electricity + natural-gas prices "
            f"and total electricity retail sales for {name}. Annual averages; regenerable "
            "via `watermark eia` with WATERMARK_EIA_API_KEY."
        ),
    )
