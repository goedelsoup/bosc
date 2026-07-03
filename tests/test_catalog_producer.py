"""Tests for the producer→entry drift gate (epic #631, issue #629).

The pure gate ``producer_drift(entries, changed_paths)`` is exercised directly; the git
plumbing + waiver + skip behaviour is exercised against a throwaway git repo.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from watermark.catalog import CatalogEntry
from watermark.catalog.producer import (
    producer_drift,
    run_producer_check,
)
from watermark.config import Settings


def _entry(entry_id: str, connector_ref: str | None, scope: str = "reference") -> CatalogEntry:
    producer: dict[str, str] = {"kind": "connector", "source": "x"}
    if connector_ref:
        producer["connector_ref"] = connector_ref
    return CatalogEntry.model_validate(
        {
            "id": entry_id,
            "title": "T",
            "scope": scope,
            "producer": producer,
            "refresh": {"cadence": "static"},
        }
    )


# --- pure gate -----------------------------------------------------------------------------
def test_producer_changed_without_its_entry_is_drift() -> None:
    entries = [_entry("echo-x", "watermark.hydrology.connectors.echo")]
    findings = producer_drift(entries, {"src/watermark/hydrology/connectors/echo.py"})
    assert len(findings) == 1
    assert findings[0].connector_ref == "watermark.hydrology.connectors.echo"
    assert findings[0].expected_entries == ["echo-x"]


def test_producer_changed_with_its_entry_is_clean() -> None:
    entries = [_entry("echo-x", "watermark.hydrology.connectors.echo")]
    changed = {
        "src/watermark/hydrology/connectors/echo.py",
        "data/catalog/reference/echo-x.yaml",  # the entry was updated in the same diff
    }
    assert producer_drift(entries, changed) == []


def test_unrelated_change_is_clean() -> None:
    entries = [_entry("echo-x", "watermark.hydrology.connectors.echo")]
    assert producer_drift(entries, {"src/watermark/site/export.py"}) == []


def test_package_init_change_triggers() -> None:
    entries = [_entry("rsei-x", "watermark.rsei")]
    assert producer_drift(entries, {"src/watermark/rsei/__init__.py"})  # package form
    assert producer_drift(entries, {"src/watermark/rsei.py"})  # module form


def test_a_sibling_entry_does_not_satisfy_a_different_producer() -> None:
    entries = [
        _entry("echo-x", "watermark.hydrology.connectors.echo"),
        _entry("rsei-x", "watermark.rsei"),
    ]
    # echo changed; only rsei's entry was touched -> echo is still drifting
    changed = {"src/watermark/hydrology/connectors/echo.py", "data/catalog/reference/rsei-x.yaml"}
    findings = producer_drift(entries, changed)
    assert [f.connector_ref for f in findings] == ["watermark.hydrology.connectors.echo"]


def test_entries_without_a_connector_ref_are_ignored() -> None:
    assert producer_drift([_entry("manual", None)], {"src/watermark/anything.py"}) == []


# --- git-backed CLI flow -------------------------------------------------------------------
def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> tuple[Settings, Path]:
    """A throwaway git repo with a catalog entry + its connector committed on main."""
    repo = tmp_path
    (repo / "data").mkdir()
    settings = Settings(data_dir=repo / "data")
    # the connector and its catalog entry
    conn = repo / "src" / "watermark" / "hydrology" / "connectors" / "echo.py"
    conn.parent.mkdir(parents=True)
    conn.write_text("# echo connector\n", encoding="utf-8")
    entry = settings.catalog_dir / "reference" / "echo-x.yaml"
    entry.parent.mkdir(parents=True)
    entry.write_text(
        "id: echo-x\ntitle: T\nscope: reference\nproducer:\n  kind: connector\n"
        "  source: x\n  connector_ref: watermark.hydrology.connectors.echo\n"
        "refresh:\n  cadence: static\n",
        encoding="utf-8",
    )
    _run(repo, "init", "-q", "-b", "main")
    _run(repo, "config", "user.email", "t@t.t")
    _run(repo, "config", "user.name", "t")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "base")
    return settings, repo


def test_run_skips_when_base_unavailable(tmp_path: Path) -> None:
    settings, _ = _repo(tmp_path)
    result = run_producer_check(base="origin/does-not-exist", settings=settings)
    assert result.status == "skipped"


def test_run_detects_drift_then_waiver(tmp_path: Path) -> None:
    settings, repo = _repo(tmp_path)
    _run(repo, "checkout", "-q", "-b", "feature")
    # change the connector, commit WITHOUT touching the catalog entry
    (repo / "src/watermark/hydrology/connectors/echo.py").write_text(
        "# changed\n", encoding="utf-8"
    )
    _run(repo, "commit", "-qam", "tweak echo connector")

    drift = run_producer_check(base="main", settings=settings)
    assert drift.status == "drift"
    assert [f.connector_ref for f in drift.findings] == ["watermark.hydrology.connectors.echo"]

    # a waiver token in a later commit bypasses the gate
    (repo / "note.txt").write_text("x\n", encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-qm", "proceed [catalog-waiver: connector refactor, entries unchanged]")
    waived = run_producer_check(base="main", settings=settings)
    assert waived.status == "waived"
    assert "connector refactor" in waived.detail


def test_run_clean_when_entry_updated_with_producer(tmp_path: Path) -> None:
    settings, repo = _repo(tmp_path)
    _run(repo, "checkout", "-q", "-b", "feature")
    (repo / "src/watermark/hydrology/connectors/echo.py").write_text(
        "# changed\n", encoding="utf-8"
    )
    entry = settings.catalog_dir / "reference" / "echo-x.yaml"
    entry.write_text(entry.read_text("utf-8") + "tags:\n- updated\n", encoding="utf-8")
    _run(repo, "commit", "-qam", "change connector + its entry")
    assert run_producer_check(base="main", settings=settings).status == "clean"
