"""Neutral shared connector machinery: on-disk cache + offline/fixture fallback.

Every subsystem's live-data connectors (hydrology, economics, gis, poi, civic) reach
external services through :func:`cached_get`, which gives them one cache / offline /
fixture discipline keyed off the subsystem's own ``settings.<x>_cache_dir``. This
package holds no subsystem-specific logic; a subsystem supplies its cache root and may
pass its own :class:`OfflineError` subclass (e.g. ``HydroOfflineError``,
``ImageryOfflineError``).
"""

from __future__ import annotations

from bosc.connectors._cache import OfflineError, cache_key, cached_get

__all__ = ["OfflineError", "cache_key", "cached_get"]
