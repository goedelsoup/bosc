"""On-disk caching + offline/fixture fallback shared by every connector subsystem.

A connector calls :func:`cached_get` with its name, the request params, a ``fetch``
callable that performs the actual HTTP request, and its subsystem's cache root /
offline flag / fixtures dir. ``cached_get`` resolves, in order:

1. a fresh cache file under ``cache_dir/<connector>/<key>.json`` (within TTL);
2. a committed fixture under ``fixtures_dir/<connector>/<key>.json`` when offline
   (tests point ``fixtures_dir`` at ``tests/fixtures/<subsystem>/``);
3. a live fetch (only when ``offline`` is False), which is then cached.

Offline + cache/fixture miss raises ``offline_error`` (default :class:`OfflineError`)
naming the key, so the failure is actionable ("record a fixture for this key").

This module holds no subsystem-specific logic: the caller owns its ``cache_dir``
(``settings.<x>_cache_dir``) and may pass an :class:`OfflineError` subclass — e.g.
``HydroOfflineError`` (:mod:`watermark.hydrology.connectors`) or ``ImageryOfflineError``
(:mod:`watermark.gis.raster`).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from watermark.logging import get_logger

log = get_logger(__name__)

# The single source of truth for the cache freshness window. Subsystems whose
# settings expose a ``*_cache_ttl_hours`` knob default it to this; the others
# (poi, civic) ride it directly. 1 week, for slow-moving public datasets.
DEFAULT_CACHE_TTL_HOURS = 168


class OfflineError(RuntimeError):
    """Raised when offline mode needs a cache/fixture entry that is missing."""


def cache_key(params: dict[str, Any]) -> str:
    """Stable short hash of a request's params (order-independent)."""
    blob = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _cache_path(cache_dir: Path, connector: str, key: str) -> Path:
    return cache_dir / connector / f"{key}.json"


def _now() -> datetime:
    return datetime.now(UTC)


def _is_fresh(fetched_at: str, ttl_hours: int) -> bool:
    try:
        ts = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    age_h = (_now() - ts).total_seconds() / 3600.0
    return age_h <= ttl_hours


def cached_get(
    connector: str,
    params: dict[str, Any],
    fetch: Callable[[], Any],
    *,
    cache_dir: Path,
    offline: bool = False,
    fixtures_dir: Path | None = None,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    offline_error: type[OfflineError] = OfflineError,
) -> Any:
    """Return the (cached or freshly fetched) JSON payload for a request.

    ``fetch`` is only invoked on a live path; it must return JSON-serializable data.
    The caller supplies its subsystem's ``cache_dir`` / ``offline`` / ``fixtures_dir``
    / ``ttl_hours`` (see the per-subsystem ``settings.<x>_cache_dir`` accessors) and,
    optionally, an ``offline_error`` subclass to raise on an offline miss.
    """
    key = cache_key(params)
    path = _cache_path(cache_dir, connector, key)

    cached = _read(path)
    if cached is not None and _is_fresh(cached.get("fetched_at", ""), ttl_hours):
        return cached["payload"]

    if offline:
        # Resolution order (per the subsystem CLAUDE.md): fresh cache → committed
        # fixture → error. A stale or hand-mutated ``data/cache/`` entry must NOT
        # shadow the reviewed committed fixture — otherwise a dev's day-old local
        # cache silently diverges from clean CI. So a non-fresh cache falls through
        # here just like an absent one.
        if fixtures_dir is not None:
            fixture = _read(fixtures_dir / connector / f"{key}.json")
            if fixture is not None:
                return fixture["payload"]
        if cached is not None:
            log.info("connector.cache.stale_offline", connector=connector, key=key)
        raise offline_error(
            f"offline: no fresh cache/fixture for {connector} key={key} "
            f"(params={params}); record one at {path}"
        )

    log.info("connector.fetch", connector=connector, key=key)
    payload = fetch()
    _write(path, {"params": params, "fetched_at": _now().isoformat(), "payload": payload})
    return payload


def _read(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and "payload" in data else None
    except (json.JSONDecodeError, OSError):
        return None


def _write(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
