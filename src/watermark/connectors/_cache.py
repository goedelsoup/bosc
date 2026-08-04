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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from watermark.logging import get_logger

log = get_logger(__name__)

CacheOrigin = Literal["cache", "fixture", "live"]
"""Which rung of the resolution order actually served a payload.

``cache`` — a fresh on-disk entry (written by an earlier live fetch); ``fixture`` — a
committed offline fixture; ``live`` — a fresh fetch. Callers that must distinguish a
*replayed sample* from a *real pull* (the GreenOps ``illustrative``/``measured`` basis,
#1643) read this via :func:`cached_get_traced`; everyone else uses :func:`cached_get`
and never sees it.
"""


@dataclass(frozen=True, slots=True)
class CacheTrace:
    """How a payload reached the caller: which rung served it, and *when it was retrieved*.

    The retrieval time is recorded in every cache/fixture record but used to stop at this
    module's edge, so a connector had no way to date the value it built (WS-21, #1621). A
    committed fixture is a **recorded live pull** — evidentially it is a connector reading
    taken at :attr:`fetched_at`, not a fabrication — but replaying one months later and
    tagging the result as though it were current is a real provenance defect, sharpest for
    a "right now" quantity like instantaneous streamflow. Surfacing the retrieval time is
    what lets a connector date the reading honestly instead.

    :attr:`ttl_hours` is the freshness window that governed *this* resolution — the
    connector's own declaration of how long its payload may be served as current (NWIS's
    instantaneous-values service declares one hour; the slow-moving default is a week).
    Reusing it as the staleness yardstick is deliberate: it keeps :attr:`stale` an
    invariant of the connector's stated currency rather than a per-call-site judgement
    that can be forgotten. A connector whose quantity really does stay current longer
    should say so by widening its TTL, where the claim is reviewable.
    """

    origin: CacheOrigin
    fetched_at: str | None
    """ISO-8601 retrieval time. ``None`` only for a fixture recorded before the convention."""
    ttl_hours: int

    @property
    def age_hours(self) -> float | None:
        """Hours since the payload was retrieved; ``None`` when it carries no usable time."""
        return _age_hours(self.fetched_at)

    @property
    def stale(self) -> bool:
        """True when the payload is older than the window its connector calls current.

        A ``live`` fetch and the ``cache`` entry it wrote are fresh by construction (only a
        within-TTL cache entry is served at all), so in practice this selects exactly the
        replayed ``fixture`` rung — and an *undated* fixture is stale by default: absence of
        a retrieval time cannot establish currency.
        """
        age = self.age_hours
        return age is None or age > self.ttl_hours


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


def _age_hours(fetched_at: str | None) -> float | None:
    """Hours since an ISO-8601 retrieval stamp, or ``None`` if it is absent/unparseable.

    A stamp with no UTC offset is read as UTC rather than raising: every writer here emits
    an aware timestamp, but a hand-recorded fixture may not, and a naive one used to blow up
    the subtraction with ``TypeError`` (which :func:`_is_fresh` did not catch).
    """
    if not fetched_at:
        return None
    try:
        ts = datetime.fromisoformat(fetched_at)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return (_now() - ts).total_seconds() / 3600.0


def _is_fresh(fetched_at: str, ttl_hours: int) -> bool:
    age_h = _age_hours(fetched_at)
    return age_h is not None and age_h <= ttl_hours


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
    return cached_get_traced(
        connector,
        params,
        fetch,
        cache_dir=cache_dir,
        offline=offline,
        fixtures_dir=fixtures_dir,
        ttl_hours=ttl_hours,
        offline_error=offline_error,
    )[0]


def cached_get_traced(
    connector: str,
    params: dict[str, Any],
    fetch: Callable[[], Any],
    *,
    cache_dir: Path,
    offline: bool = False,
    fixtures_dir: Path | None = None,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    offline_error: type[OfflineError] = OfflineError,
) -> tuple[Any, CacheTrace]:
    """:func:`cached_get`, additionally reporting *how* the payload was resolved.

    Identical resolution and side effects — this is the implementation :func:`cached_get`
    delegates to — but returns ``(payload, trace)`` so a caller can tell a replayed
    committed **fixture** from a real **live** pull or its **cache** entry, and can read
    the payload's own retrieval time. Only a caller that publishes that distinction
    should need it; see :class:`CacheTrace`.
    """
    key = cache_key(params)
    path = _cache_path(cache_dir, connector, key)

    cached = _read(path)
    if cached is not None and _is_fresh(cached.get("fetched_at", ""), ttl_hours):
        return cached["payload"], CacheTrace("cache", cached.get("fetched_at"), ttl_hours)

    if offline:
        # Resolution order (per the subsystem CLAUDE.md): fresh cache → committed
        # fixture → error. A stale or hand-mutated ``data/cache/`` entry must NOT
        # shadow the reviewed committed fixture — otherwise a dev's day-old local
        # cache silently diverges from clean CI. So a non-fresh cache falls through
        # here just like an absent one.
        if fixtures_dir is not None:
            fixture = _read(fixtures_dir / connector / f"{key}.json")
            if fixture is not None:
                return fixture["payload"], CacheTrace(
                    "fixture", fixture.get("fetched_at"), ttl_hours
                )
        if cached is not None:
            log.info("connector.cache.stale_offline", connector=connector, key=key)
        raise offline_error(
            f"offline: no fresh cache/fixture for {connector} key={key} "
            f"(params={params}); record one at {path}"
        )

    log.info("connector.fetch", connector=connector, key=key)
    payload = fetch()
    fetched_at = _now().isoformat()
    _write(path, {"params": params, "fetched_at": fetched_at, "payload": payload})
    return payload, CacheTrace("live", fetched_at, ttl_hours)


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
