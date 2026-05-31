"""Centralized configuration.

Settings load from (in priority order): environment variables, then a local
``.env`` file, then the defaults below. Every setting is namespaced with the
``BOSC_`` prefix, except ``ANTHROPIC_API_KEY`` which follows the SDK convention.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# USGS NWIS gauges that bracket the municipal water loop: the Ottawa at Lima
# (the abstraction + WWTP-discharge reach) and the Auglaize (the other source river).
_DEFAULT_NWIS_SITES = ["04187100", "04186500"]

# Repo root = two levels up from this file (src/bosc/config.py -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings, populated from the environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="BOSC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Credentials -------------------------------------------------------
    # Not prefixed: the Anthropic SDK and Claude Agent SDK read this name.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # --- Models ------------------------------------------------------------
    model: str = "claude-opus-4-8"
    extract_model: str = "claude-sonnet-4-6"
    max_turns: int = 20

    # --- Logging -----------------------------------------------------------
    log_level: str = "INFO"

    # --- Hydrology (live connectors + Tier-0 simulation) -------------------
    # When true, connectors never touch the network: they serve cached/fixture
    # responses only (so tests and CI stay hermetic). A cache miss raises.
    hydro_offline: bool = False
    hydro_cache_ttl_hours: int = 168  # 1 week; streamflow is slow-moving here
    hydro_request_timeout_s: float = 30.0
    hydro_utm_epsg: int = 32617  # UTM zone 17N — Allen County, OH (for areas)
    # Committed connector fixtures, consulted on an offline cache miss (tests/CI).
    hydro_fixtures_dir: Path | None = None
    nwis_base_url: str = "https://waterservices.usgs.gov/nwis"
    nwis_sites: list[str] = Field(default_factory=lambda: list(_DEFAULT_NWIS_SITES))
    noaa_atlas14_base_url: str = "https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py"

    # --- Paths -------------------------------------------------------------
    data_dir: Path = _REPO_ROOT / "data"

    @property
    def documents_dir(self) -> Path:
        """Raw source documents (PDFs, scans). Not committed to git."""
        return self.data_dir / "documents"

    @property
    def extracted_dir(self) -> Path:
        """Reviewed structured extractions (YAML/JSON). The durable artifact."""
        return self.data_dir / "extracted"

    @property
    def cache_dir(self) -> Path:
        """Intermediate / regenerable working files. Not committed."""
        return self.data_dir / "cache"

    @property
    def hydro_cache_dir(self) -> Path:
        """Cached live-connector responses (NWIS, etc.). Regenerable, not committed."""
        return self.cache_dir / "hydrology"

    @property
    def scenarios_dir(self) -> Path:
        """Reviewed hydrology scenario artifacts (committed). Reserved for Increment 3."""
        return self.data_dir / "scenarios"

    def ensure_dirs(self) -> None:
        """Create the data directories if they do not yet exist."""
        for path in (self.documents_dir, self.extracted_dir, self.cache_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()
