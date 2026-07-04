"""US Census ACS 5-year — county population over time.

Pulls total population (``B01003_001E``) for the county across a set of years from
the Census ACS 5-year API. **A live fetch requires a key** (``settings.census_api_key``
/ ``WATERMARK_CENSUS_API_KEY``); a keyless live fetch fails fast rather than hitting the
API. The key is sent only on the live request and is never part of the cache key or the
committed fixture/response — so a warm cache or committed fixture is still served
**keyless** (the miss that needs the key never runs). Fields are selected **by name**
from the header row, never by index.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from watermark.config import Settings, get_settings
from watermark.connectors import cached_get
from watermark.economics.model import PopulationPoint, PopulationSeries
from watermark.hydrology.model import ProvenancedValue

_POP_VAR = "B01003_001E"  # ACS total population


class CensusError(RuntimeError):
    """The Census API returned an unusable response (most often an invalid/inactive key).

    The API answers a bad key with an HTML "Invalid Key" page under HTTP 200, so this
    is raised on a non-JSON body to fail clearly instead of a cryptic decode error.
    """


def _fetch_year(year: int, fips: str, settings: Settings) -> tuple[float, str]:
    """Return ``(population, area_name)`` for one ACS5 year (cached / offline-aware)."""
    state, county = fips[:2], fips[2:]
    # The api key is deliberately excluded from the cache-key params (it's a secret
    # and must not vary the key); it is added only inside the live fetch.
    params = {
        "connector": "census",
        "dataset": "acs/acs5",
        "year": year,
        "var": _POP_VAR,
        "fips": fips,
    }

    def fetch() -> Any:
        # Live fetches require a key. This closure only runs on a cache/fixture miss, so a
        # warm cache or committed fixture is still served keyless (cached_get returns first).
        if not settings.census_api_key:
            raise CensusError(
                "live Census ACS5 fetch requires WATERMARK_CENSUS_API_KEY "
                "(a warm cache or committed fixture is served keyless)"
            )
        query = {
            "get": f"NAME,{_POP_VAR}",
            "for": f"county:{county}",
            "in": f"state:{state}",
            "key": settings.census_api_key,
        }
        resp = httpx.get(
            f"{settings.census_base_url}/{year}/acs/acs5",
            params=query,
            timeout=settings.econ_request_timeout_s,
            follow_redirects=True,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            # Census serves an HTML "Invalid Key" page under HTTP 200 for a bad key.
            raise CensusError(
                "Census API returned non-JSON (invalid or inactive "
                f"WATERMARK_CENSUS_API_KEY): {resp.text[:60]!r}"
            ) from exc

    payload = cast(
        "list[list[str]]",
        cached_get(
            "census",
            params,
            fetch,
            cache_dir=settings.econ_cache_dir,
            offline=settings.econ_offline,
            fixtures_dir=settings.econ_fixtures_dir,
        ),
    )
    header, row = payload[0], payload[1]
    col = {name: i for i, name in enumerate(header)}
    return float(row[col[_POP_VAR]]), str(row[col["NAME"]])


def fetch_population_series(
    *, years: list[int], fips: str | None = None, settings: Settings | None = None
) -> PopulationSeries:
    """County total population across ``years`` (one cached ACS5 call each)."""
    settings = settings or get_settings()
    fips = fips or settings.econ_fips
    points: list[PopulationPoint] = []
    area_name = f"FIPS {fips}"  # overwritten by the Census NAME on the first year
    for year in sorted(years):
        pop, area_name = _fetch_year(year, fips, settings)
        points.append(
            PopulationPoint(
                year=year,
                population=ProvenancedValue.from_connector(
                    pop,
                    "people",
                    citation=f"US Census ACS5 {year} {_POP_VAR} ({area_name})",
                    asof=str(year),
                ),
            )
        )
    return PopulationSeries(fips=fips, area_name=area_name, points=points)
