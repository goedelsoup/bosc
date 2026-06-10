"""US Census Geocoder — address → point (free, no key, public domain).

The geocoding step of the resolve-to-parcel funnel. Hits the Census Geocoder
``locations/onelineaddress`` service (``settings.census_geocoder_url``) and returns the
top match's coordinates + the service's normalized ``matched_address``. No API key; the
data is US public domain. Reuses the shared connector cache against the POI cache root,
so tests replay from a committed fixture and never hit the network.

**Geocoding is fuzzy.** An under-qualified address (no city) can match the wrong place
entirely, so a geocode is a *lead* — the funnel treats address→parcel as a proposal, not
an automatic identity (see ``bosc.poi.resolve`` and the merge-strictness decision).
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.connectors import cached_get
from bosc.logging import get_logger

log = get_logger(__name__)

_CONNECTOR = "census_geocoder"


class GeocodeMatch(BaseModel):
    """One geocoder match: a point + the service's normalized address."""

    model_config = ConfigDict(extra="forbid")

    query: str  # the address as asked
    matched_address: str
    lon: float
    lat: float
    source: str = "US Census Geocoder (Public_AR_Current)"


def geocode_address(address: str, *, settings: Settings | None = None) -> GeocodeMatch | None:
    """The top Census Geocoder match for ``address``, or ``None`` if nothing matched."""
    settings = settings or get_settings()
    benchmark = settings.census_geocoder_benchmark
    params = {"address": address, "benchmark": benchmark}

    def fetch() -> Any:
        log.info("census_geocoder.fetch", address=address)
        resp = httpx.get(
            f"{settings.census_geocoder_url}/locations/onelineaddress",
            params={**params, "format": "json"},
            timeout=settings.poi_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cast(
        "dict[str, Any]",
        cached_get(
            _CONNECTOR,
            params,
            fetch,
            cache_dir=settings.poi_cache_dir,
            offline=settings.poi_offline,
            fixtures_dir=settings.poi_fixtures_dir,
        ),
    )
    return _parse(payload, query=address)


def _parse(payload: dict[str, Any], *, query: str) -> GeocodeMatch | None:
    matches = payload.get("result", {}).get("addressMatches") or []
    if not matches:
        return None
    top = matches[0]
    coords = top.get("coordinates") or {}
    lon, lat = coords.get("x"), coords.get("y")
    if lon is None or lat is None:
        return None
    return GeocodeMatch(
        query=query,
        matched_address=str(top.get("matchedAddress", "")),
        lon=float(lon),
        lat=float(lat),
    )
