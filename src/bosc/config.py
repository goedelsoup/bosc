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
    # EPA ECHO Clean Water Act REST services (NPDES facility inventory).
    echo_base_url: str = "https://echodata.epa.gov/echo"
    echo_max_retries: int = 5  # backoff retries on a 429 throttle
    echo_retry_base_s: float = 5.0  # first backoff wait; doubles each attempt
    # Ohio LSC Status Report of Legislation (per-GA bill status; not hydrology, but
    # served through the same connector cache/offline/fixture machinery).
    lsc_base_url: str = "https://statusreport.lsc.ohio.gov"
    lsc_default_ga: str = "136"
    # Ohio Revised Code full text (LSC code portal; HTML, no JSON API).
    orc_base_url: str = "https://codes.ohio.gov"
    # Allen County GIS — ArcGIS REST "Current Parcels" (CAMA) layer.
    allen_parcels_url: str = (
        "https://gis.allencountyohio.com/arcgis/rest/services/AGOL/AGOL_NonEditLayers/MapServer/1"
    )
    # City of Lima GIS — "Current Lima Zoning" polygon layer (keyed to PARCEL_NO);
    # City-limits only. Server uses the /server web adaptor, folder CitywideMaps.
    lima_zoning_url: str = (
        "https://colgis.cityhall.lima.oh.us/server/rest/services/"
        "CitywideMaps/Lima_Zoning/MapServer/6"
    )
    # Same service, "Floodzone" layer — the FEMA DFIRM (panel 39003C, Allen County)
    # Special Flood Hazard Areas. Polygon, no PARCEL_NO: site lookups are spatial.
    lima_floodzone_url: str = (
        "https://colgis.cityhall.lima.oh.us/server/rest/services/"
        "CitywideMaps/Lima_Zoning/MapServer/4"
    )
    # EPA RSEI Public Data Set (AWS Open Data s3://epa-rsei-pds). Bulk relational
    # tables; `bosc rsei` reduces them to one county's toxic-release inventory.
    rsei_base_url: str = "https://epa-rsei-pds.s3.amazonaws.com"
    rsei_version: str = "v234"
    rsei_fips: str = "39003"  # Allen County, OH
    rsei_offline: bool = False  # serve cached tables only; never download
    rsei_request_timeout_s: float = 300.0  # elements.csv.gz is ~250 MB
    # NASA POWER (AWS Open Data s3://nasa-power) — satellite meteorology/solar. The
    # bucket is gridded zarr/netCDF; for a point we use the supported REST API, which
    # returns small JSON (connector cache + fixture). Default point = Lima loop centroid.
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal"
    nasa_power_lon: float = -84.11
    nasa_power_lat: float = 40.74
    nasa_power_community: str = "AG"  # agroclimatology (vs RE renewable, SB buildings)
    nasa_power_parameters: list[str] = Field(
        default_factory=lambda: [
            "PRECTOTCORR",
            "T2M",
            "T2M_MAX",
            "T2M_MIN",
            "RH2M",
            "WS2M",
            "ALLSKY_SFC_SW_DWN",
        ]
    )
    # GLEIF Legal Entity Identifier registry (AWS Open Data s3://gleif). The bucket is
    # the bulk golden copy; for our curated watchlist we use the REST API (exact-LEI
    # lookups + parent relationships). `bosc lei` resolves the watchlist to a YAML.
    gleif_base_url: str = "https://api.gleif.org/api/v1"
    gleif_offline: bool = False  # serve cached API responses only; never fetch
    gleif_request_timeout_s: float = 30.0

    # USASpending federal award data (public API, no auth). `bosc usaspending`
    # resolves a pinned recipient watchlist to all-time prime-award obligations —
    # the "who benefits from federal dollars" layer behind the corridor.
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
    usaspending_offline: bool = False  # serve cached API responses only; never fetch
    usaspending_request_timeout_s: float = 60.0

    # --- Economics (localized baselines: Census population, BLS employment) -----
    # The "what the campus consumes / what the place is" axis beyond utility draw.
    # Census ACS works keyless at low volume; BLS QCEW open data needs no key. Same
    # offline/cache/fixture discipline as hydrology, via a generalized `cached_get`.
    census_base_url: str = "https://api.census.gov/data"
    census_api_key: str = ""  # optional; ACS works keyless at low volume
    qcew_base_url: str = "https://data.bls.gov/cew/data/api"
    bea_base_url: str = "https://apps.bea.gov/api/data"
    econ_fips: str = "39003"  # Allen County, OH (state 39 + county 003)
    econ_offline: bool = False  # serve cached/fixture responses only; never fetch
    econ_request_timeout_s: float = 60.0
    econ_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)

    # --- GIS / satellite imagery -------------------------------------------
    # Pull AOI-clipped satellite imagery for tracking sites (the campus/footprints
    # already mapped in data/site/gis-findings.geojson). The catalog is Microsoft
    # Planetary Computer's STAC API, which fronts the free/open collections
    # (Sentinel-2 L2A, NAIP, Landsat C2 L2) behind one search endpoint. Same
    # offline/cache/fixture discipline as the other connectors. See
    # docs/imagery-subsystem.md. P1 is search-only (no rasterio/pystac yet).
    pc_stac_url: str = "https://planetarycomputer.microsoft.com/api/stac/v1"
    gis_default_collection: str = "sentinel-2-l2a"
    gis_search_limit: int = 50
    gis_offline: bool = False  # serve cached/fixture STAC responses only; never fetch
    gis_request_timeout_s: float = 60.0
    gis_cache_ttl_hours: int = 168  # 1 week; the scene archive is slow-moving
    gis_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # gis-findings layers treated as trackable sites (grouped into one AOI each).
    gis_tracking_layers: list[str] = Field(default_factory=lambda: ["campus"])

    # --- Documents library -------------------------------------------------
    # The full source corpus (~5 GB) is too large to republish on a static host,
    # so the Documents page is a complete *catalog* with direct downloads only for
    # the curated exhibits. Set this to an external mirror base URL (Archive.org /
    # S3 / Drive) to light up a direct per-file download link for every document;
    # empty means catalog-only (the default).
    documents_mirror_base_url: str = ""

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
    def rsei_cache_dir(self) -> Path:
        """Cached EPA RSEI bulk tables (the big .gz files). Regenerable, not committed."""
        return self.cache_dir / "rsei"

    @property
    def econ_cache_dir(self) -> Path:
        """Cached economics-connector responses (Census, BLS QCEW). Not committed."""
        return self.cache_dir / "economics"

    @property
    def gis_cache_dir(self) -> Path:
        """Cached GIS/imagery STAC responses (Planetary Computer search). Not committed."""
        return self.cache_dir / "gis"

    @property
    def gis_findings_path(self) -> Path:
        """The committed GIS findings GeoJSON — source of tracking-site geometry."""
        return self.data_dir / "site" / "gis-findings.geojson"

    @property
    def gleif_cache_dir(self) -> Path:
        """Cached GLEIF API responses (LEI records, parents). Regenerable, not committed."""
        return self.cache_dir / "gleif"

    @property
    def usaspending_cache_dir(self) -> Path:
        """Cached USASpending API responses (recipient search + profiles). Not committed."""
        return self.cache_dir / "usaspending"

    @property
    def reference_dir(self) -> Path:
        """Authoritative external reference data (committed). e.g. ECHO NPDES pulls."""
        return self.data_dir / "reference"

    @property
    def people_dir(self) -> Path:
        """Curated per-individual profiles (markdown + frontmatter) — the entity
        graph's hand-written detail store. Committed."""
        return self.data_dir / "people"

    @property
    def poi_dir(self) -> Path:
        """Curated point-of-interest (place) profiles (markdown + frontmatter) — the
        place peer of people_dir; POIs flagged ``watched`` feed imagery tracking. Committed."""
        return self.data_dir / "poi"

    @property
    def entities_dir(self) -> Path:
        """Curated entity inputs not derived from the corpus. The inventories live
        under ``entities/profiles/`` (cloud-consumer candidates, defense
        contractors). Committed."""
        return self.data_dir / "entities"

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
