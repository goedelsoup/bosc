"""Tests for settings loading and derived paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings, repo_fixtures_dir
from watermark.sites import SITES


def test_defaults() -> None:
    settings = Settings()
    assert settings.model == "claude-opus-4-8"
    assert settings.max_turns == 20


def test_env_prefix_override(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("WATERMARK_MODEL", "claude-sonnet-4-6")
    monkeypatch.setenv("WATERMARK_MAX_TURNS", "5")
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


def test_repo_fixtures_dir_anchored_to_repo_not_data_dir(tmp_path: Path) -> None:
    """#616: offline `--offline` fixture paths must resolve relative to the repo, not
    `data_dir.parent` — which breaks under a relocated WATERMARK_DATA_DIR (e.g. a tmp dir)."""
    relocated = Settings(data_dir=tmp_path)
    fixtures = repo_fixtures_dir("hydrology")
    # Anchored at the real repo tree (these are committed), independent of data_dir.
    assert fixtures.is_dir()
    assert tmp_path not in fixtures.parents
    # And the committed gis/poi fixtures resolve the same way.
    assert repo_fixtures_dir("gis").is_dir()
    assert repo_fixtures_dir("poi").is_dir()
    # The relocated settings didn't change where fixtures live.
    assert relocated.data_dir == tmp_path


def test_site_default_resolves_lima() -> None:
    # The per-site knobs resolve from the active (default Lima) site profile (#325).
    settings = Settings()
    assert settings.site == "lima"
    assert settings.nwis_sites == ["04187100", "04186500"]
    assert settings.nasa_power_lat == 40.74
    assert settings.rsei_fips == "39003"
    assert settings.econ_fips == "39003"
    assert settings.eia861_utility_number == 14006
    assert settings.hydro_utm_epsg == 32617


def test_env_overrides_site_profile(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # An explicit env var still wins over the profile, but unrelated knobs stay profile-sourced.
    monkeypatch.setenv("WATERMARK_NWIS_SITES", '["99999999"]')
    settings = Settings()
    assert settings.nwis_sites == ["99999999"]
    assert settings.rsei_fips == "39003"  # untouched -> from the Lima profile


def test_profile_list_not_aliased_to_singleton() -> None:
    # #1366 finding 1: the resolved list must be a fresh per-instance copy, NOT the
    # frozen SITES["lima"] singleton's list — otherwise a connector doing
    # settings.nwis_sites.sort()/.append() silently mutates the module-level profile
    # for every later consumer (get_settings() is lru_cached, SITES is a singleton).
    settings = Settings()
    assert settings.nwis_sites == SITES["lima"].nwis_sites
    assert settings.nwis_sites is not SITES["lima"].nwis_sites
    before = list(SITES["lima"].nwis_sites)
    settings.nwis_sites.append("00000000")
    assert SITES["lima"].nwis_sites == before  # singleton untouched


def test_profile_fields_recorded_in_fields_set() -> None:
    # #1366 finding 2: profile-resolved knobs must land in model_fields_set so a
    # model_dump(exclude_unset=True) echo/snapshot reproduces the run instead of
    # silently dropping exactly the per-site knobs.
    settings = Settings()
    assert "nwis_sites" in settings.model_fields_set
    assert "rsei_fips" in settings.model_fields_set
    dumped = settings.model_dump(exclude_unset=True)
    assert dumped["nwis_sites"] == ["04187100", "04186500"]
    assert dumped["rsei_fips"] == "39003"


def test_unknown_site_is_a_hard_error(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("WATERMARK_SITE", "atlantis")
    with pytest.raises(ValueError, match="unknown WATERMARK_SITE 'atlantis'"):
        Settings()
