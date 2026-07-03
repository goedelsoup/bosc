"""Tests for ``watermark catalog diff`` (epic #631, issue #1134).

The committed-snapshot ↔ live-disk delta: the ``git diff`` analogue to reconcile's ``git add``.
Hermetic synthetic-tree tests pin the two axes (entry-set added/removed, per-entry field moves),
the ``--site`` scoping, and the missing-snapshot fallback. Determinism comes from an injected
``now``/``reconciled_at`` (mirrors the reconcile/check test patterns).
"""

from __future__ import annotations

import textwrap
from datetime import UTC, datetime
from pathlib import Path

from watermark.catalog.diff import diff
from watermark.catalog.reconcile import reconcile, write_observed
from watermark.config import Settings

_FIXED = datetime(2026, 6, 24, 12, 0, tzinfo=UTC)


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _data(settings: Settings, relpath: str, body: str = "x: 1\n") -> Path:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _entry(settings: Settings, name: str, body: str) -> None:
    path = settings.catalog_dir / "reference" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(body), encoding="utf-8")


_CONCRETE = """\
    id: {name}
    title: T
    scope: reference
    producer:
      kind: connector
      source: x
    storage:
    - relpath: {relpath}
      media_type: application/x-yaml
    refresh:
      cadence: {cadence}
"""


def _snapshot(settings: Settings) -> None:
    """Record the current disk state as the committed baseline snapshot."""
    write_observed(reconcile(settings=settings, now=_FIXED, reconciled_at="pin"), settings=settings)


# --- no change -----------------------------------------------------------------------------
def test_no_change_is_empty_diff(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "hello: 1\n")
    _entry(
        settings,
        "echo-x",
        _CONCRETE.format(name="echo-x", relpath="reference/echo/x.yaml", cadence="static"),
    )
    _snapshot(settings)
    assert diff(settings=settings, now=_FIXED) == []


# --- per-entry field delta -----------------------------------------------------------------
def test_sha256_and_size_change_is_reported(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "hello: 1\n")
    _entry(
        settings,
        "echo-x",
        _CONCRETE.format(name="echo-x", relpath="reference/echo/x.yaml", cadence="static"),
    )
    _snapshot(settings)
    # the producer re-ran and rewrote the file with different bytes
    _data(settings, "reference/echo/x.yaml", "hello: 2  # more content\n")
    [d] = diff(settings=settings, now=_FIXED)
    assert d.id == "echo-x"
    assert d.status == "changed"
    moved = {c.field for c in d.changes}
    assert "sha256" in moved
    assert "size_bytes" in moved
    sha = next(c for c in d.changes if c.field == "sha256")
    assert sha.before != sha.after and sha.before is not None and sha.after is not None


def test_file_count_change_is_reported(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml")
    _entry(
        settings,
        "eia-consumer-energy",
        """\
        id: eia-consumer-energy
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/eia/{site}/consumer-energy.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    _snapshot(settings)
    # onboarding a second site materializes another member of the {site} template
    _data(settings, "reference/eia/columbus/consumer-energy.yaml")
    [d] = diff(settings=settings, now=_FIXED)
    assert d.status == "changed"
    fc = next(c for c in d.changes if c.field == "file_count")
    assert fc.before == 1 and fc.after == 2


def test_asof_and_stale_change_is_reported(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/x.yaml", "meta:\n  asof: '2020-01-01'\n")
    _entry(
        settings,
        "echo-x",
        """\
        id: echo-x
        title: T
        scope: reference
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/echo/x.yaml
          media_type: application/x-yaml
        refresh:
          cadence: annual
          ttl_days: 30
        """,
    )
    _snapshot(settings)  # stale=True against the old asof
    # a refresh moves asof forward, clearing staleness
    _data(settings, "reference/echo/x.yaml", "meta:\n  asof: '2026-06-01'\n")
    [d] = diff(settings=settings, now=_FIXED)
    moved = {c.field: (c.before, c.after) for c in d.changes}
    assert moved["asof"] == ("2020-01-01", "2026-06-01")
    assert moved["stale"] == (True, False)


# --- entry-set delta -----------------------------------------------------------------------
def test_new_catalog_entry_since_snapshot_is_added(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml")
    _entry(
        settings,
        "echo-a",
        _CONCRETE.format(name="echo-a", relpath="reference/echo/a.yaml", cadence="static"),
    )
    _snapshot(settings)
    # a second dataset was catalogued after the snapshot was recorded
    _data(settings, "reference/echo/b.yaml")
    _entry(
        settings,
        "echo-b",
        _CONCRETE.format(name="echo-b", relpath="reference/echo/b.yaml", cadence="static"),
    )
    [d] = diff(settings=settings, now=_FIXED)
    assert d.id == "echo-b" and d.status == "added" and d.changes == []


def test_deleted_catalog_entry_since_snapshot_is_removed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml")
    _data(settings, "reference/echo/b.yaml")
    _entry(
        settings,
        "echo-a",
        _CONCRETE.format(name="echo-a", relpath="reference/echo/a.yaml", cadence="static"),
    )
    _entry(
        settings,
        "echo-b",
        _CONCRETE.format(name="echo-b", relpath="reference/echo/b.yaml", cadence="static"),
    )
    _snapshot(settings)
    # the entry's catalog YAML was removed after the snapshot
    (settings.catalog_dir / "reference" / "echo-b.yaml").unlink()
    [d] = diff(settings=settings, now=_FIXED)
    assert d.id == "echo-b" and d.status == "removed" and d.changes == []


# --- --site scoping ------------------------------------------------------------------------
def test_site_scoping_filters_to_relevant_entries(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    # a slug-scoped entry with a bryan copy, plus a lima-legacy entry — only the former is
    # relevant to bryan. Change both, then confirm --site bryan reports only the slug-scoped one.
    _data(settings, "reference/eia/bryan/consumer-energy.yaml", "a: 1\n")
    _data(settings, "reference/lima-only/legacy.yaml", "a: 1\n")
    _entry(
        settings,
        "eia-consumer-energy",
        """\
        id: eia-consumer-energy
        title: T
        scope: reference
        site_scope: slug-scoped
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/eia/{site}/consumer-energy.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    _entry(
        settings,
        "lima-legacy-ds",
        """\
        id: lima-legacy-ds
        title: T
        scope: reference
        site_scope: lima-legacy
        producer:
          kind: connector
          source: x
        storage:
        - relpath: reference/lima-only/legacy.yaml
          media_type: application/x-yaml
        refresh:
          cadence: static
        """,
    )
    _snapshot(settings)
    _data(settings, "reference/eia/bryan/consumer-energy.yaml", "a: 2\n")
    _data(settings, "reference/lima-only/legacy.yaml", "a: 2\n")

    unscoped = {d.id for d in diff(settings=settings, now=_FIXED)}
    assert unscoped == {"eia-consumer-energy", "lima-legacy-ds"}

    bryan = [d.id for d in diff(settings=settings, now=_FIXED, site="bryan")]
    assert bryan == ["eia-consumer-energy"]  # lima-legacy filtered out


# --- missing snapshot ----------------------------------------------------------------------
def test_missing_snapshot_reports_all_added(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/echo/a.yaml")
    _data(settings, "reference/echo/b.yaml")
    _entry(
        settings,
        "echo-a",
        _CONCRETE.format(name="echo-a", relpath="reference/echo/a.yaml", cadence="static"),
    )
    _entry(
        settings,
        "echo-b",
        _CONCRETE.format(name="echo-b", relpath="reference/echo/b.yaml", cadence="static"),
    )
    # no _snapshot() call — reconcile has never run
    diffs = diff(settings=settings, now=_FIXED)
    assert [d.id for d in diffs] == ["echo-a", "echo-b"]
    assert all(d.status == "added" and d.changes == [] for d in diffs)
