"""US EIA API v2 — consumer energy prices + retail sales for the state/region.

The consumer-price half of the demand thread (issue #91): residential electricity
price, residential natural-gas price, and total electricity retail sales, against
which the data-center load's pressure is screened. We use EIA's uniform
``/v2/seriesid/{id}`` route so every pull is one cached call returning the same
shape (``response.data`` rows with ``period`` + ``value`` + ``units``); columns are
selected **by name**, never by index. Keyed: a free key read from
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
_SERIES: dict[str, dict[str, str]] = {
    "ELEC.PRICE.OH-RES.A": {
        "label": "Ohio residential electricity price",
        "fuel": "electricity",
        "metric": "price",
        "unit": "cents/kWh",
    },
    "ELEC.SALES.OH-ALL.A": {
        "label": "Ohio electricity retail sales (all sectors)",
        "fuel": "electricity",
        "metric": "sales",
        "unit": "million kWh",
    },
    "NG.N3010OH3.A": {
        "label": "Ohio residential natural-gas price",
        "fuel": "natural_gas",
        "metric": "price",
        "unit": "$/Mcf",
    },
}


class EiaError(RuntimeError):
    """The EIA API returned an unusable response (most often a missing/invalid key).

    EIA answers a bad/absent key with an error JSON or an HTML page; this is raised on
    a body without the expected ``response.data`` so the failure is clear, not cryptic.
    """


def _latest_point(payload: dict[str, Any]) -> dict[str, Any]:
    """The most recent ``{period, value}`` row from an EIA v2 seriesid payload.

    EIA returns rows newest-first when sorted by period desc; we defend against either
    order by taking the max period. Fields are read by name (``period`` / ``value``).
    """
    data = (((payload or {}).get("response") or {}).get("data")) or []
    rows = [r for r in data if r.get("value") is not None]
    if not rows:
        raise EiaError("EIA response carried no data points")
    best = max(rows, key=lambda r: str(r.get("period", "")))
    return {"period": str(best.get("period", "")), "value": float(best["value"])}


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
        return _latest_point(body)

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
        area=settings.eia_state,
        value=ProvenancedValue.from_connector(float(payload["value"]), meta["unit"], citation=cite),
    )


def fetch_consumer_energy(
    *, series_ids: list[str] | None = None, settings: Settings | None = None
) -> ConsumerEnergyCosts:
    """Assemble the state's consumer energy-cost dataset (price + sales) from EIA."""
    settings = settings or get_settings()
    ids = series_ids or list(_SERIES)
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
