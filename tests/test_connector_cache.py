"""The neutral connector cache/offline contract (``watermark.connectors._cache``).

The resolution order is **fresh on-disk cache → committed fixture (offline) → live
fetch** — see the subsystem ``CLAUDE.md``. These exercise the offline edges directly
so every connector inherits a hermetic, CI-faithful contract (issue #1365).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from watermark.connectors._cache import OfflineError, cache_key, cached_get

_PARAMS = {"site": "04187100"}
_KEY = cache_key(_PARAMS)


def _write_cache(cache_dir: Path, connector: str, *, age_hours: float, payload: Any) -> None:
    fetched_at = (datetime.now(UTC) - timedelta(hours=age_hours)).isoformat()
    path = cache_dir / connector / f"{_KEY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"params": _PARAMS, "fetched_at": fetched_at, "payload": payload}),
        encoding="utf-8",
    )


def _write_fixture(fixtures_dir: Path, connector: str, *, payload: Any) -> None:
    path = fixtures_dir / connector / f"{_KEY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"payload": payload}), encoding="utf-8")


def _boom() -> Any:
    raise AssertionError("fetch must not run on the offline path")


def test_fresh_cache_is_served(tmp_path: Path) -> None:
    _write_cache(tmp_path, "nwis", age_hours=1, payload="fresh")
    got = cached_get("nwis", _PARAMS, _boom, cache_dir=tmp_path, ttl_hours=168)
    assert got == "fresh"


def test_stale_cache_does_not_shadow_fixture_offline(tmp_path: Path) -> None:
    """The #1365 fix: a stale ``data/cache/`` entry must yield to the committed fixture."""
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"
    _write_cache(cache_dir, "nwis", age_hours=200, payload="stale-local")
    _write_fixture(fixtures_dir, "nwis", payload="committed-fixture")

    got = cached_get(
        "nwis", _PARAMS, _boom, cache_dir=cache_dir, offline=True, fixtures_dir=fixtures_dir
    )
    assert got == "committed-fixture"


def test_fresh_cache_wins_over_fixture_offline(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"
    _write_cache(cache_dir, "nwis", age_hours=1, payload="fresh-local")
    _write_fixture(fixtures_dir, "nwis", payload="committed-fixture")

    got = cached_get(
        "nwis", _PARAMS, _boom, cache_dir=cache_dir, offline=True, fixtures_dir=fixtures_dir
    )
    assert got == "fresh-local"


def test_offline_stale_cache_no_fixture_raises(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"
    _write_cache(cache_dir, "nwis", age_hours=200, payload="stale-local")

    with pytest.raises(OfflineError, match="no fresh cache/fixture"):
        cached_get(
            "nwis", _PARAMS, _boom, cache_dir=cache_dir, offline=True, fixtures_dir=fixtures_dir
        )


def test_stale_cache_refetches_online(tmp_path: Path) -> None:
    _write_cache(tmp_path, "nwis", age_hours=200, payload="stale")
    got = cached_get("nwis", _PARAMS, lambda: "refetched", cache_dir=tmp_path, ttl_hours=168)
    assert got == "refetched"
    # ...and the refreshed payload is written back to the cache key.
    on_disk = json.loads((tmp_path / "nwis" / f"{_KEY}.json").read_text())
    assert on_disk["payload"] == "refetched"
