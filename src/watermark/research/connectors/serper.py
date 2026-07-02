"""Serper web-search connector for the research layer.

Wraps the Serper.dev Google Search API with the standard cached_get discipline
(on-disk cache + TTL + committed-fixture fallback).  The API key
(``WATERMARK_SERPER_API_KEY``) is checked only inside the live-fetch closure, so
the cache and offline-fixture paths work without a key — CI and tests stay
hermetic with committed fixtures under ``tests/fixtures/research/serper/``.

This is the typed, research-specific counterpart of the generic
:func:`watermark.connectors.serper.serper_search`.  Use :func:`search_web` from
research tool registrations (#1048); for civic/discovery use cases (OEPA document
discovery, etc.) use the shared connector instead.

Serper free-tier operator constraints (return 400 otherwise):
- ``site:`` and ``inurl:`` — blocked; phrase ``domain`` keywords instead
- Quoted strings (``"..."``) — blocked; keep query terms unquoted
- ``filetype:`` — allowed
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import httpx
from pydantic import BaseModel

from watermark.connectors._cache import DEFAULT_CACHE_TTL_HOURS, cached_get
from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

_CONNECTOR = "serper"
_SERPER_URL = "https://google.serper.dev/search"


class SearchResult(BaseModel):
    """One organic result returned by the Serper Google Search API."""

    title: str
    snippet: str
    url: str
    date: str | None = None


def search_web(
    query: str,
    *,
    n: int = 10,
    gl: str = "us",
    hl: str = "en",
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    settings: Settings | None = None,
) -> list[SearchResult]:
    """Search Google via Serper and return typed :class:`SearchResult` objects.

    The API key (``WATERMARK_SERPER_API_KEY``) is only required for live fetches.
    If a fresh cache entry or an offline fixture exists, the key is not consulted
    — enabling hermetic offline use and CI without credentials.

    Returns an empty list when no key is set and no cached/fixture result is
    available (graceful degradation for the agent tool layer).

    Args:
        query:     Search query string (no quoted terms — Serper free-tier block).
        n:         Max results to request (Serper cap: 100).
        gl/hl:     Country / language codes forwarded to Google.
        ttl_hours: Cache freshness window (default: 7 days).
        settings:  Supply explicitly in tests; omit to use ``get_settings()``.
    """
    from watermark.config import get_settings

    settings = settings or get_settings()

    params: dict[str, Any] = {"q": query, "num": n, "gl": gl, "hl": hl}

    def _live() -> list[dict[str, Any]]:
        if not settings.serper_api_key:
            log.warning("research.serper.no_api_key", note="set WATERMARK_SERPER_API_KEY")
            return []
        try:
            resp = httpx.post(
                _SERPER_URL,
                json=params,
                headers={"X-API-KEY": settings.serper_api_key},
                timeout=settings.civic_request_timeout_s,
            )
            resp.raise_for_status()
            return cast("list[dict[str, Any]]", resp.json().get("organic", []))
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("research.serper.fetch_failed", query=query, error=str(exc))
            return []

    raw = cast(
        "list[dict[str, Any]]",
        cached_get(
            _CONNECTOR,
            params,
            _live,
            cache_dir=settings.research_cache_dir,
            offline=settings.research_offline,
            fixtures_dir=settings.research_fixtures_dir,
            ttl_hours=ttl_hours,
        ),
    )

    return [
        SearchResult(
            title=hit.get("title", ""),
            snippet=hit.get("snippet", ""),
            url=hit.get("link", ""),
            date=hit.get("date"),
        )
        for hit in raw
    ]
