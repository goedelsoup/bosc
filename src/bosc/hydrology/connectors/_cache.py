"""Hydrology connector cache — the hydro-flavored view of :mod:`bosc.connectors`.

Defaults the cache root / offline flag / fixtures dir / TTL to the ``hydro_*``
settings and raises :class:`HydroOfflineError` on an offline miss, so a hydrology
connector calls ``cached_get("nwis", params, fetch, settings=settings)`` with no
boilerplate. The generic machinery (and :class:`~bosc.connectors.OfflineError`, the
base of :class:`HydroOfflineError`) lives in :mod:`bosc.connectors`; ``cache_key`` is
re-exported here for connectors and tests that import it from this module.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from bosc.config import Settings, get_settings
from bosc.connectors._cache import OfflineError, cache_key
from bosc.connectors._cache import cached_get as _cached_get

__all__ = ["HydroOfflineError", "cache_key", "cached_get"]


class HydroOfflineError(OfflineError):
    """Raised when offline mode needs a hydrology cache/fixture entry that is missing."""


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
    """Hydrology ``cached_get``: ``hydro_*`` defaults + :class:`HydroOfflineError`.

    A non-hydrology subsystem should call :func:`bosc.connectors.cached_get` directly
    with its own cache root / offline flag / fixtures dir, not this wrapper.
    """
    settings = settings or get_settings()
    return _cached_get(
        connector,
        params,
        fetch,
        cache_dir=cache_dir if cache_dir is not None else settings.hydro_cache_dir,
        offline=offline if offline is not None else settings.hydro_offline,
        fixtures_dir=fixtures_dir if fixtures_dir is not None else settings.hydro_fixtures_dir,
        ttl_hours=ttl_hours if ttl_hours is not None else settings.hydro_cache_ttl_hours,
        offline_error=HydroOfflineError,
    )
