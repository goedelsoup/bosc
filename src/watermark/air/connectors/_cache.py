"""Air connector cache — the air-flavored view of :mod:`watermark.connectors`.

Defaults the cache root / offline flag / fixtures dir / TTL to the ``air_*`` settings and
raises :class:`AirOfflineError` on an offline miss, so an AERMET/AERMAP input connector
calls ``cached_get("isd", params, fetch, settings=settings)`` with no boilerplate — the
direct sibling of :mod:`watermark.hydrology.connectors._cache`.

The JSON connector cache covers the text pulls (ISD surface, IGRA upper-air). The NED DEM
connector (``ned.py``) is a *raster* pull and does NOT route through here — it follows the
committed-fixture-GeoTIFF discipline of :mod:`watermark.gis.raster` and raises
:class:`AirOfflineError` itself on an offline fixture miss.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from watermark.config import Settings, get_settings
from watermark.connectors._cache import OfflineError, cache_key
from watermark.connectors._cache import cached_get as _cached_get

__all__ = ["AirOfflineError", "cache_key", "cached_get"]


class AirOfflineError(OfflineError):
    """Raised when offline mode needs an air-connector cache/fixture entry that is missing."""


def cached_get(
    connector: str,
    params: dict[str, Any],
    fetch: Callable[[], Any],
    *,
    settings: Settings | None = None,
    cache_dir: Path | None = None,
    offline: bool | None = None,
    fixtures_dir: Path | None = None,
    ttl_hours: int | None = None,
) -> Any:
    """Air ``cached_get``: ``air_*`` defaults + :class:`AirOfflineError`."""
    settings = settings or get_settings()
    return _cached_get(
        connector,
        params,
        fetch,
        cache_dir=cache_dir if cache_dir is not None else settings.air_cache_dir,
        offline=offline if offline is not None else settings.air_offline,
        fixtures_dir=fixtures_dir if fixtures_dir is not None else settings.air_fixtures_dir,
        ttl_hours=ttl_hours if ttl_hours is not None else settings.air_cache_ttl_hours,
        offline_error=AirOfflineError,
    )
