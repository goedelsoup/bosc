"""Tests for settings loading and derived paths."""

from __future__ import annotations

from pathlib import Path

from bosc.config import Settings


def test_defaults() -> None:
    settings = Settings()
    assert settings.model == "claude-opus-4-8"
    assert settings.max_turns == 20


def test_env_prefix_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BOSC_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("BOSC_MAX_TURNS", "5")
    settings = Settings()
    assert settings.model == "claude-sonnet-4-6"
    assert settings.max_turns == 5


def test_derived_paths(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert settings.documents_dir == tmp_path / "documents"
    assert settings.extracted_dir == tmp_path / "extracted"
    settings.ensure_dirs()
    assert settings.documents_dir.is_dir()
    assert settings.extracted_dir.is_dir()
