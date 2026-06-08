"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = REPO_ROOT / "data" / "extracted"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def summary_path() -> Path:
    """Path to the committed roundabouts summary extraction."""
    return EXTRACTED / "aedg" / "roundabouts.summary.opc.yaml"


@pytest.fixture
def hydro_settings() -> Settings:
    """Offline hydrology settings: real repo data dir, connector fixtures, no network.

    Injected into connector / pipeline calls so tests are hermetic without fighting
    ``get_settings()``'s ``lru_cache``.
    """
    return Settings(
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


@pytest.fixture
def econ_settings() -> Settings:
    """Offline economics settings: real repo data dir, connector fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=FIXTURES / "economics",
    )
