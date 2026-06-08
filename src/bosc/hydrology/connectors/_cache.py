"""On-disk caching + offline/fixture fallback shared by all connectors.

A connector calls :func:`cached_get` with its name, the request params, and a
``fetch`` callable that performs the actual HTTP request. ``cached_get`` resolves,
in order:

1. a fresh cache file under ``settings.hydro_cache_dir/<connector>/<key>.json``
   (within TTL);
2. a committed fixture under ``settings.hydro_cache_dir/<connector>/<key>.json``
   when offline (the test settings point ``hydro_cache_dir`` at ``tests/fixtures``);
3. a live fetch (only when ``hydro_offline`` is False), which is then cached.

Offline + cache/fixture miss raises :class:`HydroOfflineError` naming the key, so
the failure is actionable ("record a fixture for this key").
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)


class HydroOfflineError(RuntimeError):
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
    settings: Settings | None = None,
    cache_dir: Path | None = None,
    offline: bool | None = None,
    fixtures_dir: Path | None = None,
    ttl_hours: int | None = None,
) -> Any:
    """Return the (cached or freshly fetched) JSON payload for a request.

    ``fetch`` is only invoked on a live path; it must return JSON-serializable data.

    By default the cache dir / offline flag / fixtures dir / TTL come from the
    ``hydro_*`` settings. A non-hydrology connector (e.g. economics) passes its own
    ``cache_dir`` / ``offline`` / ``fixtures_dir`` to reuse this machinery against a
    different cache root — fully backward compatible.
    """
    settings = settings or get_settings()
    cache_dir = cache_dir if cache_dir is not None else settings.hydro_cache_dir
    offline = offline if offline is not None else settings.hydro_offline
    fixtures_dir = fixtures_dir if fixtures_dir is not None else settings.hydro_fixtures_dir
    ttl_hours = ttl_hours if ttl_hours is not None else settings.hydro_cache_ttl_hours

    key = cache_key(params)
    path = _cache_path(cache_dir, connector, key)

    cached = _read(path)
    if cached is not None:
        fresh = _is_fresh(cached.get("fetched_at", ""), ttl_hours)
        if offline or fresh:
            if offline and not fresh:
                log.info("hydro.cache.stale_offline", connector=connector, key=key)
            return cached["payload"]

    if offline:
        # Fall back to a committed fixture before giving up (keeps tests/CI hermetic).
        if fixtures_dir is not None:
            fixture = _read(fixtures_dir / connector / f"{key}.json")
            if fixture is not None:
                return fixture["payload"]
        raise HydroOfflineError(
            f"offline: no cache/fixture for {connector} key={key} "
            f"(params={params}); record one at {path}"
        )

    log.info("hydro.fetch", connector=connector, key=key)
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
