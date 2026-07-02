"""Unit tests for watermark.research.connectors.serper — all offline / no network."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors._cache import OfflineError, cache_key
from watermark.research.connectors.serper import SearchResult, search_web

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The committed fixture covers this query.
_FIXTURE_QUERY = "data center Sidney Ohio I-75"
_FIXTURE_N = 10


# ---------------------------------------------------------------------------
# Fixture-fallback (offline, no fresh cache, fixture exists)
# ---------------------------------------------------------------------------


def test_fixture_fallback_returns_search_results(tmp_path: Path) -> None:
    """Offline mode with fixture → parses into SearchResult objects."""
    settings = Settings(
        data_dir=Path(__file__).resolve().parents[1] / "data",
        research_offline=True,
        research_fixtures_dir=FIXTURES / "research",
        # tmp_path has no cache entries → forces fixture lookup
    )
    results = search_web(_FIXTURE_QUERY, n=_FIXTURE_N, settings=settings)
    assert len(results) == 3
    assert all(isinstance(r, SearchResult) for r in results)


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def test_search_result_fields(tmp_path: Path) -> None:
    """SearchResult fields are populated from the Serper organic payload."""
    settings = Settings(
        data_dir=Path(__file__).resolve().parents[1] / "data",
        research_offline=True,
        research_fixtures_dir=FIXTURES / "research",
    )
    results = search_web(_FIXTURE_QUERY, n=_FIXTURE_N, settings=settings)
    first = results[0]
    assert first.title == "QTS Data Centers Announces Major Expansion in Sidney, Ohio"
    assert "QTS" in first.snippet
    assert first.url == "https://qts.example.com/sidney-ohio-expansion"
    assert first.date == "May 15, 2025"


def test_search_result_date_optional(tmp_path: Path) -> None:
    """A hit without a 'date' key should produce SearchResult.date == None."""
    params = {"q": "no-date query", "num": 5, "gl": "us", "hl": "en"}
    key = cache_key(params)
    # fixtures_dir is passed as tmp_path; cached_get looks at fixtures_dir/serper/<key>.json
    fixture_dir = tmp_path / "serper"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "params": params,
                "fetched_at": "2026-06-01T00:00:00+00:00",
                "payload": [{"title": "T", "snippet": "S", "link": "https://example.com"}],
            }
        )
    )
    settings = Settings(
        data_dir=tmp_path,
        research_offline=True,
        research_fixtures_dir=tmp_path,
    )
    results = search_web("no-date query", n=5, settings=settings)
    assert results[0].date is None


# ---------------------------------------------------------------------------
# Cache hit (fresh on-disk cache entry → no fixture / live fetch needed)
# ---------------------------------------------------------------------------


def test_cache_hit_serves_without_fixture(tmp_path: Path) -> None:
    """A fresh on-disk cache entry is served even when offline=True and no fixture dir."""
    params = {"q": "cache hit test", "num": 10, "gl": "us", "hl": "en"}
    key = cache_key(params)
    cache_dir = tmp_path / "research" / "serper"
    cache_dir.mkdir(parents=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(
            {
                "params": params,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                "payload": [
                    {
                        "title": "Cached Result",
                        "snippet": "from cache",
                        "link": "https://cached.example.com",
                        "date": "Jan 1, 2026",
                    }
                ],
            }
        )
    )
    # research_cache_dir = data_dir/cache/research — write the cache entry there
    real_cache = tmp_path / "cache" / "research" / "serper"
    real_cache.mkdir(parents=True)
    (real_cache / f"{key}.json").write_text((cache_dir / f"{key}.json").read_text())
    settings2 = Settings(
        data_dir=tmp_path,
        research_offline=True,
        research_fixtures_dir=None,  # no fixture dir — must use cache
    )
    results = search_web("cache hit test", n=10, settings=settings2)
    assert len(results) == 1
    assert results[0].title == "Cached Result"


# ---------------------------------------------------------------------------
# Missing-key offline behavior
# ---------------------------------------------------------------------------


def test_missing_key_offline_uses_fixture() -> None:
    """No API key + offline=True → fixture is served without touching the network."""
    settings = Settings(
        data_dir=Path(__file__).resolve().parents[1] / "data",
        serper_api_key="",  # no key
        research_offline=True,
        research_fixtures_dir=FIXTURES / "research",
    )
    results = search_web(_FIXTURE_QUERY, n=_FIXTURE_N, settings=settings)
    assert len(results) > 0  # fixture served, no key required


def test_missing_key_offline_no_fixture_raises(tmp_path: Path) -> None:
    """No API key + offline=True + no fixture → OfflineError (actionable miss)."""
    settings = Settings(
        data_dir=tmp_path,
        serper_api_key="",
        research_offline=True,
        research_fixtures_dir=tmp_path / "empty",  # nothing here
    )
    with pytest.raises(OfflineError):
        search_web("this query has no fixture", n=5, settings=settings)


def test_missing_key_online_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """No API key + online mode → empty list (graceful degradation, no exception)."""
    import watermark.research.connectors.serper as mod

    def _fake_cached_get(connector, params, fetch, **kwargs):  # type: ignore[no-untyped-def]
        return fetch()

    monkeypatch.setattr(mod, "cached_get", _fake_cached_get)

    settings = Settings(
        data_dir=Path(__file__).resolve().parents[1] / "data",
        serper_api_key="",
        research_offline=False,
    )
    results = search_web("any query", settings=settings)
    assert results == []
