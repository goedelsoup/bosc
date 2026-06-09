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


@pytest.fixture
def gis_settings() -> Settings:
    """Offline GIS/imagery settings: real repo data dir, STAC fixtures, no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        gis_offline=True,
        gis_fixtures_dir=FIXTURES / "gis",
    )


@pytest.fixture
def poi_settings() -> Settings:
    """Settings for the committed POI store (data/poi/) — no network, no connector."""
    return Settings(data_dir=REPO_ROOT / "data")


@pytest.fixture
def facility_settings() -> Settings:
    """Settings for the facility compute-capacity derivation.

    Reads committed reference data only (data/reference/compute + the parcels
    geojson) — no network, no connector — so a plain real-data-dir Settings is
    hermetic. Offline flags set defensively in case the footprint method's parcels
    path ever grows a connector fallback.
    """
    return Settings(data_dir=REPO_ROOT / "data", hydro_offline=True)
