"""Hydrology connector cache — the hydro-flavored view of :mod:`watermark.connectors`.

Defaults the cache root / offline flag / fixtures dir / TTL to the ``hydro_*``
settings and raises :class:`HydroOfflineError` on an offline miss, so a hydrology
connector calls ``cached_get("nwis", params, fetch, settings=settings)`` with no
boilerplate. The generic machinery (and :class:`~watermark.connectors.OfflineError`, the
base of :class:`HydroOfflineError`) lives in :mod:`watermark.connectors`; ``cache_key`` is
re-exported here for connectors and tests that import it from this module.

A connector that mints a :class:`~watermark.hydrology.model.ProvenancedValue` uses
:func:`cached_get_traced` instead, and dates + rates that value off the returned
:class:`~watermark.connectors.CacheTrace` — see :func:`confidence_for` (WS-21, #1621).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from watermark.config import Settings, get_settings
from watermark.connectors._cache import CacheTrace, OfflineError, cache_key
from watermark.connectors._cache import cached_get_traced as _cached_get_traced
from watermark.provenance import Confidence, degrade

__all__ = [
    "CacheTrace",
    "HydroOfflineError",
    "cache_key",
    "cached_get",
    "cached_get_traced",
    "confidence_for",
]


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

    A non-hydrology subsystem should call :func:`watermark.connectors.cached_get` directly
    with its own cache root / offline flag / fixtures dir, not this wrapper.
    """
    return cached_get_traced(
        connector,
        params,
        fetch,
        settings=settings,
        cache_dir=cache_dir,
        offline=offline,
        fixtures_dir=fixtures_dir,
        ttl_hours=ttl_hours,
    )[0]


def cached_get_traced(
    connector: str,
    params: dict[str, Any],
    fetch: Callable[[], Any],
    *,
    settings: Settings | None = None,
    cache_dir: Path | None = None,
    offline: bool | None = None,
    fixtures_dir: Path | None = None,
    ttl_hours: int | None = None,
) -> tuple[Any, CacheTrace]:
    """:func:`cached_get`, also returning the payload's :class:`CacheTrace`.

    Same resolution and ``hydro_*`` defaults — this is what :func:`cached_get` delegates
    to — but hands back *when* the payload was retrieved and whether that predates the
    connector's own freshness window, which is what a ``ProvenancedValue`` needs to date
    itself honestly instead of reading as current (WS-21, #1621).
    """
    settings = settings or get_settings()
    return _cached_get_traced(
        connector,
        params,
        fetch,
        cache_dir=cache_dir if cache_dir is not None else settings.hydro_cache_dir,
        offline=offline if offline is not None else settings.hydro_offline,
        fixtures_dir=fixtures_dir if fixtures_dir is not None else settings.hydro_fixtures_dir,
        ttl_hours=ttl_hours if ttl_hours is not None else settings.hydro_cache_ttl_hours,
        offline_error=HydroOfflineError,
    )


def confidence_for(base: Confidence = "high", *, replayed: bool) -> Confidence:
    """``base``, stepped down once when the payload was replayed past its freshness window.

    The single place the WS-21 rule is spelled, so the four connector paths that apply it
    cannot drift into four rules: a value replayed from a recording older than the currency
    its own connector declares may not carry that connector's full confidence. It
    **degrades one step and never upgrades** (:func:`watermark.provenance.degrade`), so it
    composes with a caller's own down-weighting rather than fighting it — an NWIS reading
    that is both provisional (already ``low``, #1602) and replayed stays ``low`` rather
    than bouncing.

    ``replayed`` is :attr:`CacheTrace.stale` where the trace is in hand, or the flag a
    connector's own model carried it out on (``NwisReading.replayed``,
    ``SoilHsgSurvey.replayed``) once the payload is behind it.

    Deliberately *not* a re-tagging of ``source``: a committed fixture is a recorded live
    pull, so the value really did come off the service and stays ``connector``-sourced —
    what it may not claim is currency. Pair this with an ``asof`` taken from
    :attr:`CacheTrace.fetched_at` (or the payload's own observation timestamp, which is
    better still) so the value states the date it is true for.
    """
    return degrade(base) if replayed else base
