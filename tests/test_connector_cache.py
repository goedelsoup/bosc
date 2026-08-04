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

from watermark.connectors._cache import OfflineError, cache_key, cached_get, cached_get_traced

_PARAMS = {"site": "04187100"}
_KEY = cache_key(_PARAMS)


def _stamp(age_hours: float) -> str:
    return (datetime.now(UTC) - timedelta(hours=age_hours)).isoformat()


def _write_cache(cache_dir: Path, connector: str, *, age_hours: float, payload: Any) -> None:
    path = cache_dir / connector / f"{_KEY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"params": _PARAMS, "fetched_at": _stamp(age_hours), "payload": payload}),
        encoding="utf-8",
    )


def _write_fixture(
    fixtures_dir: Path, connector: str, *, payload: Any, fetched_at: str | None = None
) -> None:
    """A committed fixture. ``fetched_at`` absent by default — 39 committed ones predate it."""
    record: dict[str, Any] = {"payload": payload}
    if fetched_at is not None:
        record["fetched_at"] = fetched_at
    path = fixtures_dir / connector / f"{_KEY}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")


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


# --- the retrieval trace (WS-21, #1621) -------------------------------------------------------
# `fetched_at` was recorded in every cache/fixture record but stopped at this module's edge, so a
# connector could not date the value it built and an offline replay read as a current pull.


def test_every_rung_reports_its_own_retrieval_time(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    fixtures_dir = tmp_path / "fixtures"

    _, live = cached_get_traced("nwis", _PARAMS, lambda: "fetched", cache_dir=cache_dir)
    assert live.origin == "live"
    assert live.fetched_at is not None and live.age_hours == pytest.approx(0.0, abs=0.01)

    # The cache entry that live fetch wrote reports the *fetch's* time, not "now".
    _, cached = cached_get_traced("nwis", _PARAMS, _boom, cache_dir=cache_dir, ttl_hours=168)
    assert (cached.origin, cached.fetched_at) == ("cache", live.fetched_at)

    _write_fixture(fixtures_dir, "nwis", payload="committed", fetched_at=_stamp(1500))
    _, replayed = cached_get_traced(
        "nwis",
        _PARAMS,
        _boom,
        cache_dir=tmp_path / "empty",
        offline=True,
        fixtures_dir=fixtures_dir,
    )
    assert replayed.origin == "fixture"
    assert replayed.age_hours == pytest.approx(1500, abs=1)


def test_only_a_replayed_fixture_can_be_stale(tmp_path: Path) -> None:
    """A live fetch and the cache entry it wrote are fresh *by construction*.

    Only a within-TTL cache entry is ever served, so the freshness check upstream of the
    trace already guarantees it — which is what makes ``stale`` pick out exactly the
    replayed committed fixture, the one rung with no freshness gate at all.
    """
    cache_dir = tmp_path / "cache"
    _, live = cached_get_traced("nwis", _PARAMS, lambda: "fetched", cache_dir=cache_dir)
    assert live.stale is False

    _write_cache(cache_dir, "nwis", age_hours=100, payload="aging")
    _, cached = cached_get_traced("nwis", _PARAMS, _boom, cache_dir=cache_dir, ttl_hours=168)
    assert (cached.origin, cached.stale) == ("cache", False)


@pytest.mark.parametrize(
    ("age_hours", "ttl_hours", "expected"),
    [
        # The window is the connector's own declaration of how long its payload stays
        # current, so the same fixture is fresh to a week-long default and stale to the
        # one-hour "right now" NWIS instantaneous-values service.
        (2, 168, False),
        (2, 1, True),
        (200, 168, True),
    ],
)
def test_staleness_is_measured_against_the_connectors_own_window(
    tmp_path: Path, age_hours: float, ttl_hours: int, expected: bool
) -> None:
    fixtures_dir = tmp_path / "fixtures"
    _write_fixture(fixtures_dir, "nwis", payload="committed", fetched_at=_stamp(age_hours))
    _, trace = cached_get_traced(
        "nwis",
        _PARAMS,
        _boom,
        cache_dir=tmp_path / "empty",
        offline=True,
        fixtures_dir=fixtures_dir,
        ttl_hours=ttl_hours,
    )
    assert trace.stale is expected


def test_an_undated_fixture_is_stale(tmp_path: Path) -> None:
    """Absence of a retrieval time cannot establish currency — so it does not.

    A committed fixture recorded before the ``fetched_at`` convention (39 of them) must
    read as "cannot prove this is current", never as "fresh".
    """
    fixtures_dir = tmp_path / "fixtures"
    _write_fixture(fixtures_dir, "nwis", payload="committed")  # no fetched_at
    _, trace = cached_get_traced(
        "nwis",
        _PARAMS,
        _boom,
        cache_dir=tmp_path / "empty",
        offline=True,
        fixtures_dir=fixtures_dir,
    )
    assert (trace.fetched_at, trace.age_hours, trace.stale) == (None, None, True)


def test_a_naive_timestamp_is_read_as_utc_not_a_crash(tmp_path: Path) -> None:
    """A hand-recorded fixture with no UTC offset used to raise ``TypeError`` in the age math."""
    fixtures_dir = tmp_path / "fixtures"
    naive = (datetime.now(UTC) - timedelta(hours=3)).replace(tzinfo=None).isoformat()
    _write_fixture(fixtures_dir, "nwis", payload="committed", fetched_at=naive)
    _, trace = cached_get_traced(
        "nwis",
        _PARAMS,
        _boom,
        cache_dir=tmp_path / "empty",
        offline=True,
        fixtures_dir=fixtures_dir,
    )
    assert trace.age_hours == pytest.approx(3, abs=0.1)
