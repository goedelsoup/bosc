"""Neutral shared connector machinery: on-disk cache + offline/fixture fallback.

Every subsystem's live-data connectors (hydrology, economics, gis, poi, civic) reach
external services through :func:`cached_get`, which gives them one cache / offline /
fixture discipline keyed off the subsystem's own ``settings.<x>_cache_dir``. This
package holds no subsystem-specific logic; a subsystem supplies its cache root and may
pass its own :class:`OfflineError` subclass (e.g. ``HydroOfflineError``,
``ImageryOfflineError``).
"""

from __future__ import annotations

from watermark.connectors._cache import (
    DEFAULT_CACHE_TTL_HOURS,
    CacheOrigin,
    OfflineError,
    cache_key,
    cached_get,
    cached_get_traced,
)
from watermark.connectors._util import to_float, to_int, to_str
from watermark.connectors.serper import serper_search

__all__ = [
    "DEFAULT_CACHE_TTL_HOURS",
    "CacheOrigin",
    "OfflineError",
    "cache_key",
    "cached_get",
    "cached_get_traced",
    "serper_search",
    "to_float",
    "to_int",
    "to_str",
]
