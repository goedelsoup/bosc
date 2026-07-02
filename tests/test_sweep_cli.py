"""Hermetic CLI tests for ``bosc sweep data-centers`` — no live agent, no network."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from watermark.agent.client import AgentResult
from watermark.cli import app
from watermark.config import Settings

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[1]


class _FakeAgent:
    """Minimal stand-in for ResearchAgent — returns a fixed AgentResult synchronously."""

    def __init__(self, settings: Settings | None = None, **kwargs: object) -> None:
        self._settings = settings

    async def converse(self, prompt: str, *, on_text: object = None) -> AgentResult:
        if callable(on_text):
            on_text("Sweep output.")  # type: ignore[operator]
        return AgentResult(text="# Register\n\nContent.", num_turns=2, cost_usd=0.001)


class _ErrorAgent(_FakeAgent):
    """Stand-in that signals is_error=True so the sweep aborts before writing files."""

    async def converse(self, prompt: str, *, on_text: object = None) -> AgentResult:
        return AgentResult(text="", is_error=True)


# ---------------------------------------------------------------------------
# --dry-run: print paths and prompt, write nothing
# ---------------------------------------------------------------------------


def test_dry_run_prints_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)

    result = runner.invoke(app, ["--site", "lima", "sweep", "data-centers", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Register →" in result.output
    assert "Catalog →" in result.output
    # No files written
    assert not (settings.extracted_dir / "lima" / "data-centers.md").exists()
    assert not (settings.data_dir / "catalog" / "extracted" / "data-centers-lima.yaml").exists()


# ---------------------------------------------------------------------------
# --force guard: exit when register already exists and --force not given
# ---------------------------------------------------------------------------


def test_force_guard_exits_when_register_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    register = settings.extracted_dir / "lima" / "data-centers.md"
    register.parent.mkdir(parents=True)
    register.write_text("existing content", encoding="utf-8")
    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)

    result = runner.invoke(app, ["--site", "lima", "sweep", "data-centers"])

    assert result.exit_code == 1
    assert "already exists" in result.output
    # File not overwritten
    assert register.read_text(encoding="utf-8") == "existing content"


# ---------------------------------------------------------------------------
# --offline: research_offline=True is wired into the agent's settings
# ---------------------------------------------------------------------------


def test_offline_flag_sets_research_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Settings] = {}

    class _CapturingAgent(_FakeAgent):
        def __init__(self, settings: Settings | None = None, **kwargs: object) -> None:
            super().__init__(settings=settings, **kwargs)
            if settings is not None:
                captured["settings"] = settings

    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)
    monkeypatch.setattr("watermark.agent.client.ResearchAgent", _CapturingAgent)

    runner.invoke(app, ["--site", "lima", "sweep", "data-centers", "--offline"])

    assert captured.get("settings") is not None
    assert captured["settings"].research_offline is True


# ---------------------------------------------------------------------------
# Successful run: register and catalog written correctly
# ---------------------------------------------------------------------------


def test_successful_run_writes_register_and_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)
    monkeypatch.setattr("watermark.agent.client.ResearchAgent", _FakeAgent)

    result = runner.invoke(app, ["--site", "lima", "sweep", "data-centers"])

    assert result.exit_code == 0, result.output

    register = settings.extracted_dir / "lima" / "data-centers.md"
    assert register.exists()
    assert "# Register" in register.read_text(encoding="utf-8")

    catalog = settings.data_dir / "catalog" / "extracted" / "data-centers-lima.yaml"
    assert catalog.exists()
    catalog_text = catalog.read_text(encoding="utf-8")
    assert "needs-review" in catalog_text
    assert "data-centers-lima" in catalog_text


# ---------------------------------------------------------------------------
# Reviewed status preserved on re-run with --force
# ---------------------------------------------------------------------------


def test_force_preserves_reviewed_catalog_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)

    # Pre-create a "reviewed" catalog entry.
    catalog_path = settings.data_dir / "catalog" / "extracted" / "data-centers-lima.yaml"
    catalog_path.parent.mkdir(parents=True)
    catalog_path.write_text("id: data-centers-lima\nstatus: reviewed\n", encoding="utf-8")

    # Pre-create the register so --force is needed.
    register = settings.extracted_dir / "lima" / "data-centers.md"
    register.parent.mkdir(parents=True)
    register.write_text("old content", encoding="utf-8")

    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)
    monkeypatch.setattr("watermark.agent.client.ResearchAgent", _FakeAgent)

    result = runner.invoke(app, ["--site", "lima", "sweep", "data-centers", "--force"])

    assert result.exit_code == 0, result.output
    assert "# Register" in register.read_text(encoding="utf-8")
    catalog_text = catalog_path.read_text(encoding="utf-8")
    # The status: field must be reviewed; "needs-review" may still appear in prose notes.
    assert "status: reviewed" in catalog_text
    assert "status: needs-review" not in catalog_text


# ---------------------------------------------------------------------------
# Error result: no files written when agent signals is_error
# ---------------------------------------------------------------------------


def test_error_result_aborts_before_file_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr("watermark.cli.sweep.get_settings", lambda: settings)
    monkeypatch.setattr("watermark.agent.client.ResearchAgent", _ErrorAgent)

    result = runner.invoke(app, ["--site", "lima", "sweep", "data-centers"])

    assert result.exit_code == 1
    assert not (settings.extracted_dir / "lima" / "data-centers.md").exists()
    assert not (settings.data_dir / "catalog" / "extracted" / "data-centers-lima.yaml").exists()
