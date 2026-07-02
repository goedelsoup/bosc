"""Tests for ``watermark catalog run`` — the DAG-aware producer runner (epic #1019, #1021).

Hermetic synthetic-catalog tests: the plan half (topological order, fresh-skip, {site}
expansion, --force) observes a tmp data tree; the execute half runs against an injected
``execute`` callable, so no subprocess is ever spawned.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from watermark.catalog.runner import PlanStep, execute_plan, plan
from watermark.config import Settings


def _settings(tmp_path: Path) -> Settings:
    (tmp_path / "data").mkdir()
    return Settings(data_dir=tmp_path / "data")


def _data(settings: Settings, relpath: str, body: str = "x: 1\n") -> Path:
    path = settings.data_dir / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _entry(
    settings: Settings,
    name: str,
    *,
    command: str | None,
    relpath: str | None,
    depends_on: list[str] | None = None,
    refresh: str = "  cadence: on-demand\n",
) -> None:
    # assemble line-by-line so every optional part (command/deps/storage) stays valid YAML
    lines = [f"id: {name}", "title: T", "scope: reference", "producer:", "  kind: connector"]
    if command:
        lines.append(f"  command: {command}")
    lines.append("  source: x")
    if depends_on:
        lines.append("depends_on:")
        lines.extend(f"- {d}" for d in depends_on)
    if relpath:
        lines.append("storage:")
        lines.append(f"- relpath: {relpath}")
        lines.append("  media_type: application/x-yaml")
    lines.append("refresh:")
    lines.append(refresh.rstrip())
    body = "\n".join(lines) + "\n"
    path = settings.catalog_dir / "reference" / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# --- plan --------------------------------------------------------------------------------
def test_plan_is_upstream_first_and_marks_missing_output_as_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/a/a.yaml")
    _entry(settings, "up", command="up-cmd", relpath="reference/a/a.yaml")
    _entry(
        settings,
        "down",
        command="down-cmd",
        relpath="reference/a/gone.yaml",  # never produced -> must run
        depends_on=["up"],
    )
    steps = plan("down", site="lima", settings=settings)
    assert [s.entry_id for s in steps] == ["up", "down"]
    by_id = {s.entry_id: s for s in steps}
    assert by_id["up"].action == "skip-fresh"  # exists, no TTL -> fresh
    assert by_id["down"].action == "run"
    assert "missing" in by_id["down"].reason


def test_plan_marks_stale_entry_as_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/a/a.yaml", "meta:\n  last_refreshed: '2020-01-01'\n")
    _entry(
        settings,
        "conn",
        command="conn-cmd",
        relpath="reference/a/a.yaml",
        refresh="  cadence: annual\n  ttl_days: 30\n",
    )
    steps = plan("conn", site="lima", settings=settings)
    assert steps[0].action == "run"
    assert "stale" in steps[0].reason
    assert "2020-01-01" in steps[0].reason


def test_plan_force_runs_fresh_entries(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/a/a.yaml")
    _entry(settings, "conn", command="conn-cmd", relpath="reference/a/a.yaml")
    steps = plan("conn", site="lima", settings=settings, force=True)
    assert steps[0].action == "run"
    assert steps[0].reason == "forced"


def test_plan_expands_site_placeholder(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _entry(settings, "conn", command="pull --site-dir {site}", relpath="reference/a/gone.yaml")
    steps = plan("conn", site="fort-wayne", settings=settings)
    assert steps[0].command == "pull --site-dir fort-wayne"


def test_plan_virtual_node_has_no_command(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _data(settings, "reference/a/a.yaml")
    _entry(settings, "leaf", command="leaf-cmd", relpath="reference/a/a.yaml")
    _entry(settings, "agg", command=None, relpath=None, depends_on=["leaf"])
    steps = plan("agg", site="lima", settings=settings)
    assert [s.action for s in steps] == ["skip-fresh", "virtual"]
    assert steps[1].command is None


def test_plan_unknown_entry_raises(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(KeyError):
        plan("no-such-entry", site="lima", settings=settings)


# --- execute -----------------------------------------------------------------------------
def _step(entry_id: str, action: str = "run", command: str | None = "cmd") -> PlanStep:
    reasons = {"run": "forced", "skip-fresh": "fresh — last x", "virtual": "no producer command"}
    return PlanStep(
        entry_id=entry_id,
        command=None if action == "virtual" else command,
        action=action,  # type: ignore[arg-type]
        reason=reasons[action],
    )


def test_execute_runs_in_order_with_module_argv() -> None:
    calls: list[list[str]] = []
    steps = [_step("up", command="up-cmd --flag"), _step("down", command="down-cmd")]
    report = execute_plan(steps, site="lima", execute=lambda argv: (calls.append(argv), 0)[1])
    assert [r.status for r in report.results] == ["ran", "ran"]
    assert calls[0] == [sys.executable, "-m", "watermark", "--site", "lima", "up-cmd", "--flag"]
    assert calls[1][-1] == "down-cmd"


def test_execute_aborts_remaining_steps_on_failure() -> None:
    steps = [_step("a"), _step("b"), _step("c")]
    codes = iter([0, 3])
    report = execute_plan(steps, site="lima", execute=lambda argv: next(codes))
    assert [r.status for r in report.results] == ["ran", "failed", "aborted"]
    assert report.failed is not None
    assert report.failed.step.entry_id == "b"
    assert report.failed.exit_code == 3


def test_execute_converts_subprocess_exception_to_failed_step() -> None:
    import subprocess

    def boom(argv: list[str]) -> int:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

    steps = [_step("a"), _step("b")]
    report = execute_plan(steps, site="lima", execute=boom)
    assert [r.status for r in report.results] == ["failed", "aborted"]
    assert report.failed is not None
    assert report.failed.step.entry_id == "a"
    assert report.failed.exit_code is None  # no clean exit code — a timeout, not a non-zero exit


def test_execute_carries_fresh_and_virtual_through_without_spawning() -> None:
    calls: list[list[str]] = []
    steps = [_step("a", action="skip-fresh"), _step("agg", action="virtual")]
    report = execute_plan(steps, site="lima", execute=lambda argv: (calls.append(argv), 0)[1])
    assert calls == []
    assert [r.status for r in report.results] == ["fresh", "virtual"]
