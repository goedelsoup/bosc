"""Centralized configuration.

Settings load from (in priority order): environment variables, then a local
``.env`` file, then the defaults below. Every setting is namespaced with the
``WATERMARK_`` prefix, except ``ANTHROPIC_API_KEY`` which follows the SDK convention.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from watermark.connectors import DEFAULT_CACHE_TTL_HOURS
from watermark.sites import PROFILE_SETTINGS_FIELDS, SITES
from watermark.tasks import PipelineTask

# Repo root = two levels up from this file (src/watermark/config.py -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_fixtures_dir(*parts: str) -> Path:
    """A committed test/CI fixtures path under ``tests/fixtures/<parts>``.

    Anchored at the repo root via ``_REPO_ROOT`` — NOT ``settings.data_dir.parent``,
    which breaks when ``WATERMARK_DATA_DIR`` is relocated (e.g. a tmp dir in tests) or the
    package is installed without the repo tree (#616). The CLI's ``--offline`` paths
    route their ``*_fixtures_dir`` settings through here.
    """
    return _REPO_ROOT.joinpath("tests", "fixtures", *parts)


class Settings(BaseSettings):
    """Application settings, populated from the environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="WATERMARK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Site axis (the BOSC network; see watermark.sites) ----------------------
    # The active watershed-point site. Selects a SiteProfile from watermark.sites.SITES,
    # whose per-site knobs (PROFILE_SETTINGS_FIELDS) fill the fields below unless a
    # field is set explicitly (env/.env/kwarg). Default = the live Lima reference build.
    site: str = "lima"

    # --- Credentials -------------------------------------------------------
    # Not prefixed: the Anthropic SDK and Claude Agent SDK read this name.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    # Per-task inference keys (GreenOps usage attribution; #1080). Route each pipeline stage
    # (watermark.tasks.PipelineTask) through a distinct Anthropic key — each bound to its own
    # Anthropic workspace — so the Admin usage report (#1078) attributes calls by workspace,
    # which is what turns the "AI by task" donut (#1083) from a modeled assumption into a
    # connector figure. WATERMARK_-prefixed (our `anthropic_key_for` resolver reads them, then
    # hands the key to the SDK explicitly); an empty task key falls back to ANTHROPIC_API_KEY,
    # so a single-key deploy is unchanged. Provisioning: data/reference/greenops/README.md.
    # NEVER logged and NEVER part of any cache key (like every other secret here).
    anthropic_key_extract: str = ""  # WATERMARK_ANTHROPIC_KEY_EXTRACT
    anthropic_key_corroborate: str = ""  # WATERMARK_ANTHROPIC_KEY_CORROBORATE (#40 repair loop)
    anthropic_key_ask: str = ""  # WATERMARK_ANTHROPIC_KEY_ASK (in-process research agent)
    anthropic_key_draft: str = ""  # WATERMARK_ANTHROPIC_KEY_DRAFT
    # Not prefixed: the standard GitHub Actions / gh CLI env-var name.
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    # Override for tests (points at a mock server or fixture endpoint).
    github_base_url: str = "https://api.github.com"
    # GitHub App credentials for the watermark-admin-bot (issue #919).
    # All three must be set together; the raw PEM from GitHub works as-is (PKCS#1 or PKCS#8).
    github_app_id: str = ""
    github_app_private_key: str = ""  # raw PEM — set via WATERMARK_GITHUB_APP_PRIVATE_KEY
    github_app_installation_id: str = ""
    # Comma-separated GitHub logins with platform-wide admin access.
    admin_logins: str = ""
    # When True, a missing GITHUB_ACTOR is treated as a trusted App actor (opt-in for
    # GH Actions contexts where the runner itself is the authorized operator).
    github_app_trusted: bool = False
    # Google Search via serper.dev — OEPA/DAM non-permit document discovery.
    serper_api_key: str = ""

    # --- Models ------------------------------------------------------------
    model: str = "claude-opus-4-8"
    extract_model: str = "claude-sonnet-4-6"
    max_turns: int = 20

    # --- Research runs (the automated-research agent; see watermark.research) ----
    # An investigation run is open-ended (more turns than a single Q&A) and distills
    # its findings into at most this many issue proposals. A hard cost ceiling and a
    # kill switch live with the workflow guardrails (Epic 5.5), not here.
    research_max_turns: int = 30
    research_max_proposals: int = 5
    # Research connector cache/offline/fixture discipline (web-search, URL-fetch).
    # Same pattern as the hydrology/econ/civic connectors: offline=True means no
    # network — serve cached or committed-fixture responses only (tests/CI).
    research_offline: bool = False
    research_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS
    research_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # Max characters returned by fetch_url (proxy for the token budget passed to the agent).
    # ~20 k chars ≈ 5 k tokens — generous for an article, tight for a full PDF.
    research_fetch_max_chars: int = 20_000
    # HTTP timeout for research connectors (Serper, URL fetch). Separate from the civic
    # connector timeout so research latency can be tuned independently.
    research_request_timeout_s: float = 30.0

    # --- Logging -----------------------------------------------------------
    log_level: str = "INFO"

    # --- OpenTelemetry / Honeycomb (#953) ----------------------------------
    otel_enabled: bool = False  # WATERMARK_OTEL_ENABLED; no-op when false
    honeycomb_api_key: str = ""  # WATERMARK_HONEYCOMB_API_KEY
    otel_environment: str = "prod"  # WATERMARK_OTEL_ENVIRONMENT; sets deployment.environment
    otel_trace_content: bool = (
        False  # WATERMARK_OTEL_TRACE_CONTENT; opt-in to exporting prompts/completions
    )

    # --- Air / AERMOD (Tier-1 dispersion; #1178) ---------------------------
    # The EPA AERMOD executable. AERMOD is a Fortran build distributed by EPA SCRAM,
    # not a pip wheel — so unlike SWMM (pyswmm) it is located on disk, not imported.
    # Resolution: this path → `aermod` on PATH → nothing (the engine then degrades to
    # AermodResult(available=False), like swmm_available()). Provenance/pinning: docs/AERMOD.md.
    aermod_bin: str = ""

    # --- Hydrology (live connectors + Tier-0 simulation) -------------------
    # When true, connectors never touch the network: they serve cached/fixture
    # responses only (so tests and CI stay hermetic). A cache miss raises.
    hydro_offline: bool = False
    hydro_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS  # slow-moving records (daily values, etc.)
    # The NWIS *Instantaneous Values* service is intrinsically "right now" (latest
    # reading / relative P<n>D window), so it must NOT inherit the week-long default
    # or it serves week-stale flow after the first pull. Short TTL; the key stays
    # time-invariant (committed fixtures still resolve offline regardless of TTL).
    nwis_iv_cache_ttl_hours: int = 1
    hydro_request_timeout_s: float = 30.0
    # Per-site (from the active SiteProfile): UTM zone for area calcs (Lima = 17N / 32617).
    hydro_utm_epsg: int = 0
    # Committed connector fixtures, consulted on an offline cache miss (tests/CI).
    hydro_fixtures_dir: Path | None = None
    nwis_base_url: str = "https://waterservices.usgs.gov/nwis"
    # Per-site (from the active SiteProfile): the USGS NWIS gauges bracketing the loop.
    nwis_sites: list[str] = Field(default_factory=list)
    noaa_atlas14_base_url: str = "https://hdsc.nws.noaa.gov/cgi-bin/new/cgi_readH5.py"
    # EPA ECHO Clean Water Act REST services (NPDES facility inventory).
    echo_base_url: str = "https://echodata.epa.gov/echo"
    echo_max_retries: int = 5  # backoff retries on a 429 throttle
    echo_retry_base_s: float = 5.0  # first backoff wait; doubles each attempt
    # Ohio LSC Status Report of Legislation (per-GA bill status; not hydrology, but
    # served through the same connector cache/offline/fixture machinery).
    lsc_base_url: str = "https://statusreport.lsc.ohio.gov"
    # Per-site (from the active SiteProfile): the Ohio General Assembly to track.
    lsc_default_ga: str = ""
    # Ohio Revised Code full text (LSC code portal; HTML, no JSON API).
    orc_base_url: str = "https://codes.ohio.gov"
    # County GIS parcels layer — per-site (Lima = Allen County AGOL "Current Parcels" CAMA).
    parcels_url: str = ""
    # City zoning polygon layer — per-site (Lima = City of Lima "Current Lima Zoning",
    # keyed to PARCEL_NO, city-limits only).
    zoning_url: str = ""
    # City floodzone layer — per-site (Lima = FEMA DFIRM panel 39003C SFHAs; spatial lookup).
    floodzone_url: str = ""
    # USGS National Map Watershed Boundary Dataset (WBD) — the authoritative seamless
    # Hydrologic Unit (HUC) polygons. The MapServer's HU-level sublayers are keyed by
    # digit count (8 = Subbasin, 10 = Watershed, 12 = Subwatershed); the WBD connector
    # appends `/<layer>/query`. Served through the shared hydrology cache/fixture path.
    wbd_url: str = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer"
    # USGS NLDI (Network-Linked Data Index) — the hydro-network navigation service over the
    # NHDPlus flowline network. The `nldi` connector snaps a point / gage to its NHDPlus
    # `comid` and navigates upstream/downstream to return real river-centerline geometry
    # (the reach-network the FlowLayer viz advects over). Served through the shared hydrology
    # cache/fixture path. The connector appends `/linked-data/...`.
    nldi_base_url: str = "https://api.water.usgs.gov/nldi"
    # EPA RSEI Public Data Set. The current release — v2.3.12 (March 2024, TRI 1988-2022)
    # — ships as a single ~447 MB zip of per-table CSVs on EPA's public gaftp site, NOT
    # the frozen `epa-rsei-pds` S3 bucket, which stalled at v234/2016 (#1148). `watermark
    # rsei` reduces the relational tables to one county's toxic-release inventory.
    rsei_base_url: str = (
        "https://gaftp.epa.gov/rsei/Current_Version/V2312_RY2022/Public_Release_Data"
    )
    rsei_version: str = "v2312"
    # Distribution layout, so the new source and the frozen bucket don't share one URL
    # template (#1148): "archive" = one zip of per-table CSVs (v2312+, streamed in place);
    # "s3_gz" = the legacy bucket's `{base}/{version}/data_tables/{name}.csv.gz` per table.
    rsei_distribution: str = "archive"
    rsei_archive_name: str = "RSEIv2312_Public_Release_Data.zip"  # archive-mode zip filename
    rsei_fips: str = ""  # per-site (from the active SiteProfile); Lima = Allen County 39003
    rsei_offline: bool = False  # serve cached tables only; never download
    rsei_request_timeout_s: float = 600.0  # the v2312 archive is ~447 MB
    # NASA POWER (AWS Open Data s3://nasa-power) — satellite meteorology/solar. The
    # bucket is gridded zarr/netCDF; for a point we use the supported REST API, which
    # returns small JSON (connector cache + fixture). Default point = Lima loop centroid.
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal"
    # Per-site (from the active SiteProfile): the meteorology point (Lima loop centroid).
    nasa_power_lon: float = 0.0
    nasa_power_lat: float = 0.0
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
    # USDA NRCS SSURGO soils via Soil Data Access (SDA) Tabular REST — the dominant
    # hydrologic soil group (HSG) over the campus footprint, grid-sampled (replaces the
    # hardcoded "C" assumption in the stormwater model). Same connector cache/fixture
    # discipline (offline -> committed fixture under tests/fixtures/hydrology/ssurgo/).
    ssurgo_sda_url: str = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
    # GLEIF Legal Entity Identifier registry (AWS Open Data s3://gleif). The bucket is
    # the bulk golden copy; for our curated watchlist we use the REST API (exact-LEI
    # lookups + parent relationships). `watermark lei` resolves the watchlist to a YAML.
    gleif_base_url: str = "https://api.gleif.org/api/v1"
    gleif_offline: bool = False  # serve cached API responses only; never fetch
    gleif_request_timeout_s: float = 30.0

    # USASpending federal award data (public API, no auth). `watermark usaspending`
    # resolves a pinned recipient watchlist to all-time prime-award obligations —
    # the "who benefits from federal dollars" layer behind the corridor.
    usaspending_base_url: str = "https://api.usaspending.gov/api/v2"
    usaspending_offline: bool = False  # serve cached API responses only; never fetch
    usaspending_request_timeout_s: float = 60.0
    # Beyond the all-time total, resolve an annual flow + PSC/NAICS category mix + a
    # defense-vs-civilian awarding-agency split for each recipient (#1662, ME-C stretch).
    # Off drops to the single lifetime scalar; the annual span is how many trailing federal
    # fiscal years the flow series covers.
    usaspending_breakdown: bool = True
    usaspending_annual_span_years: int = 10

    # --- Air (AERMOD preprocessing connectors; epic #1172, #1179) --------------
    # AERMET (meteorology) + AERMAP (terrain) input connectors, following the same
    # offline/cache/committed-fixture discipline as hydrology. When true, connectors never
    # touch the network: cached/fixture responses only (tests/CI stay hermetic). A miss raises.
    air_offline: bool = False
    air_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS  # met/terrain archives are static
    air_request_timeout_s: float = 120.0  # ISD/IGRA year files + 3DEP raster exports are large
    air_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # The meteorological year the AERMET connectors pull (ISD surface + IGRA upper-air). A real
    # AERMOD data set uses 1-5 recent, quality-assured years; #1179 pulls one representative year.
    air_met_year: int = 2023
    # NOAA ISD (Integrated Surface Database) — hourly surface obs, the AERMET SURFACE input in
    # ISHD format. Raw ISH per station-year lives at {base}/{year}/{usaf}-{wban}-{year}.gz.
    isd_base_url: str = "https://www.ncei.noaa.gov/pub/data/noaa"
    # Per-site (SiteProfile seam → #1180 "met/terrain endpoints"): the representative surface
    # station USAF-WBAN id, e.g. "725330-14827" (Fort Wayne Intl / KFWA). "" disables the pull.
    air_surface_station: str = ""
    # NOAA IGRA v2 (Integrated Global Radiosonde Archive) — twice-daily soundings, the AERMET
    # UPPERAIR input. Per-station year files under {base}/access/data-y2d/{station}-data.txt.zip.
    igra_base_url: str = "https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive"
    # Per-site (SiteProfile seam → #1180): the representative upper-air station IGRA id, e.g.
    # "USM00072426" (Wilmington, OH / ILN — the region's NWS radiosonde). "" disables the pull.
    air_upperair_station: str = ""
    # USGS 3DEP/NED elevation — the AERMAP terrain input. The 3DEPElevation ImageServer's
    # exportImage returns a GeoTIFF DEM for a bbox (3DEP is the NED successor); rasterio samples
    # receptor/source elevations. Committed-fixture-GeoTIFF discipline (like gis/raster.py), NOT
    # the JSON connector cache — a raster payload doesn't fit the JSON cache/fixture shape.
    ned_base_url: str = (
        "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
    )
    # Terrain-domain half-width (degrees) around the AERMAP center point (defaults to the
    # nasa_power loop centroid). Lima's Cole/Bluelick corridor sits well inside ~0.1° (~11 km).
    air_terrain_halfwidth_deg: float = 0.1

    # --- Economics (localized baselines: Census population, BLS employment) -----
    # The "what the campus consumes / what the place is" axis beyond utility draw.
    # Census ACS5 needs a key for a live fetch (a warm cache/fixture is served keyless);
    # BLS QCEW open data needs no key. Same offline/cache/fixture discipline as hydrology,
    # via a generalized `cached_get`.
    census_base_url: str = "https://api.census.gov/data"
    census_api_key: str = ""  # required for a live ACS5 fetch; cache/fixture served keyless
    qcew_base_url: str = "https://data.bls.gov/cew/data/api"
    bea_base_url: str = "https://apps.bea.gov/api/data"
    # EIA API v2 — consumer energy prices (residential electricity + retail fuel) for
    # the demand -> consumer-price-pressure thread (issue #91). Keyed: a free key read
    # from WATERMARK_EIA_API_KEY, sent only on the live request (never in the cache key or
    # the committed fixture). Reuses the shared econ cache/offline/fixtures discipline.
    eia_base_url: str = "https://api.eia.gov/v2"
    eia_api_key: str = ""  # required for live pulls; offline replays committed fixtures
    # Per-site (from the active SiteProfile): the state anchoring consumer energy prices.
    eia_state: str = ""
    # EIA-861 Annual Electric Power Industry Report — the per-utility retail file (sales/
    # customers/price) the v2 seriesid route doesn't expose (#94). A bulk Excel zip,
    # downloaded to econ_cache_dir/eia861/ on the live path only and reduced to one
    # utility's rows; the reduced payload is cached/fixtured like the other econ pulls.
    eia861_base_url: str = "https://www.eia.gov/electricity/data/eia861/zip"
    eia861_year: int = 2024  # latest published EIA-861 vintage
    # TTL (hours) on the raw downloaded EIA-861 zip in econ_cache_dir/eia861/. Unlike the
    # reduced payloads (which ride cached_get's TTL), the raw zip is a plain file download;
    # a stale/poisoned body is otherwise cached forever (A4/#1638), so age it out.
    eia861_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS
    # Per-site (from the active SiteProfile): the retail utility (Lima = AEP Ohio 14006).
    eia861_utility_number: int = 0
    # Per-site (from the active SiteProfile): the county FIPS (Lima = Allen County 39003).
    econ_fips: str = ""
    econ_offline: bool = False  # serve cached/fixture responses only; never fetch
    econ_request_timeout_s: float = 60.0
    econ_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # PJM Data Miner 2 — zonal day-ahead LMP (#121). Keyed: a free subscription key read from
    # WATERMARK_PJM_API_KEY, sent as the Ocp-Apim-Subscription-Key header only on the live request
    # (never in the cache key or the committed fixture). Reuses the shared econ cache/offline/
    # fixtures discipline (the grid connectors do). Offline replays committed fixtures.
    pjm_base_url: str = "https://api.pjm.com/api/v1"
    pjm_api_key: str = ""  # required for live pulls; offline replays committed fixtures

    # --- GreenOps (Watermark's own compute footprint; epic #1076) ----------
    # The self-reported carbon/water footprint of running the platform, published to the
    # same evidence standard as the sites we track (/about/sustainability). Per-source
    # billing/usage connectors — AWS (Cost Explorer + Customer Carbon Footprint Tool),
    # Anthropic (Admin usage/cost API), GitHub Actions, EPA eGRID — land in later issues
    # (#1078-#1082) through the shared cache/offline/fixture discipline. Every figure is
    # modeled (reference/assumption/derived), NEVER connector-"verified" as a metered fact.
    greenops_offline: bool = False  # serve cached/fixture responses only; never fetch
    greenops_request_timeout_s: float = 60.0
    greenops_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS  # billing/usage roll up slowly
    greenops_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # AWS billing/carbon credentials. SDK-convention names (NOT WATERMARK_-prefixed): the
    # boto3/AWS SDK reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION. Absent
    # credentials => the AWS source degrades to a modeled assumption, never a crash. Cost
    # Explorer + CCFT are us-east-1-only endpoints, so that is the default region.
    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    aws_cost_explorer_enabled: bool = True  # WATERMARK_AWS_COST_EXPLORER_ENABLED; CE billing pull
    aws_ccft_enabled: bool = True  # WATERMARK_AWS_CCFT_ENABLED; Customer Carbon Footprint Tool
    # Anthropic Admin API key (usage/cost reporting) — the SDK-convention name, not
    # WATERMARK_-prefixed and distinct from the inference ANTHROPIC_API_KEY. Absent =>
    # the Anthropic source degrades to a modeled assumption.
    anthropic_admin_key: str = Field(default="", alias="ANTHROPIC_ADMIN_KEY")
    # EPA eGRID subregion carbon-intensity + generation-mix factors (#1082). A public
    # annual workbook (no key); the electricity -> CO2e / source-mix conversion reads these
    # rather than a hand-maintained table. A new vintage is a config change: bump the year
    # and point the URL at that release's workbook (the subregion sheet is SRL<yy>). The
    # download lands under greenops_cache_dir/egrid/ on the live path only; offline replays
    # the committed fixture (the reduced subregion rows, not the 20 MB xlsx).
    egrid_year: int = 2023  # latest published eGRID vintage
    egrid_data_url: str = (
        "https://www.epa.gov/system/files/documents/2025-06/egrid2023_data_rev2.xlsx"
    )
    # GitHub Actions minutes + Packages/LFS storage (#1081). The enhanced billing platform
    # is per-organization (/organizations/{org}/settings/billing/usage); this is the org
    # login whose usage the connector pulls, monthly across the window. Auth reuses the
    # existing settings.github_token (a PAT/App token with the "Plan" read scope), excluded
    # from the cache key. Absent token on a live pull => the GitHub source degrades to a
    # modeled assumption, never a crash. Overridable so tests can point at another org.
    github_billing_org: str = "watermark-directory"
    # Which eGRID subregion the compute runs in (#1083) — the electricity → CO2e / source-mix
    # / upstream-water conversion apportions the derived electricity by this subregion's
    # factors. A stated modeling `assumption`, not a metered fact: our primary AWS region is
    # us-east-1 (Northern Virginia), whose eGRID subregion is SERC Virginia/Carolina (SRVC).
    # Override when the workload's region changes; must be a code present in the eGRID table.
    greenops_grid_subregion: str = "SRVC"

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
    gis_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS  # the scene archive is slow-moving
    gis_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # Tracking sites are no longer layers here — they are watched POIs in data/entities/poi/
    # (watermark.gis.load_tracking_sites reads tracked_pois()). See docs/poi-subsystem.md.

    # --- POI / geocoding (the resolve-to-parcel funnel) --------------------
    # Resolve corpus place references to a canonical Allen County parcel. US Census
    # Geocoder (free, no key, public domain) turns an address into a point; the
    # allen_gis parcel-at-point spatial query turns that point into a parcel. Same
    # offline/cache/fixture discipline as the other connectors. See docs/poi-subsystem.md.
    census_geocoder_url: str = "https://geocoding.geo.census.gov/geocoder"
    census_geocoder_benchmark: str = "Public_AR_Current"
    poi_offline: bool = False  # serve cached/fixture geocoder responses only; never fetch
    poi_request_timeout_s: float = 30.0
    poi_cache_ttl_hours: int = (
        DEFAULT_CACHE_TTL_HOURS  # geocodes are stable (was the silent default)
    )
    poi_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)
    # USGS GNIS (geonames) via the National Map ArcGIS service — for non-parcel features
    # (rivers, water bodies, landforms) the parcel funnel can't anchor. Free, no key,
    # public domain. The gaz_id is a stable identity; default to hydrographic layers.
    gnis_url: str = "https://carto.nationalmap.gov/arcgis/rest/services/geonames/MapServer"
    # Per-site (from the active SiteProfile): the default state for GNIS queries.
    gnis_default_state: str = ""
    gnis_layers: list[int] = Field(default_factory=lambda: [6, 7])  # Streams, Other Hydro

    # --- Civic (political-subdivision meeting records) ---------------------
    # The civic discovery + fetchers + downloader reach county CMS/WAF pages through
    # the same connector cache/offline/fixture machinery as every other subsystem,
    # but with their own namespace (fixtures under tests/fixtures/civic/). Browser-like
    # page fetches govern their own timeout — distinct from the streamflow knob they
    # used to borrow (#602).
    civic_offline: bool = False  # serve cached/fixture pages only; never fetch
    civic_request_timeout_s: float = 30.0
    civic_cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS  # meeting listings are slow-moving
    civic_fixtures_dir: Path | None = None  # committed connector fixtures (tests/CI)

    # --- Documents library -------------------------------------------------
    # The full source corpus (~5 GB) is too large to republish on a static host,
    # so the Documents page is a complete *catalog* with direct downloads only for
    # the curated exhibits. Set this to an external mirror base URL (Archive.org /
    # S3 / Drive) to light up a direct per-file download link for every document;
    # empty means catalog-only (the default).
    documents_mirror_base_url: str = ""

    # --- Source-document object store (epic #274, B) -----------------------
    # Cloudflare R2 (S3-compatible) holds the corpus bytes that the /api/doc Pages
    # Function (B2 / #278) streams; `watermark objectstore sync` (B3 / #279) uploads
    # data/documents/** here. The access key id + secret are S3 API tokens — supplied
    # via the environment (WATERMARK_DOCUMENTS_OBJECT_STORE_*), NEVER committed. Empty
    # credentials mean the sync tool is unconfigured (it errors with a clear message);
    # the catalog/export still build. `endpoint` overrides the derived R2 host for a
    # local S3 (minio) or tests.
    documents_object_store_account_id: str = ""  # R2 account id → endpoint host
    documents_object_store_bucket: str = "watermark-documents"  # prod (--target remote)
    documents_object_store_dev_bucket: str = "watermark-documents-dev"  # dev (--target local)
    documents_object_store_access_key_id: str = ""
    documents_object_store_secret_access_key: str = ""
    documents_object_store_endpoint: str = (
        ""  # override; else https://<account>.r2.cloudflarestorage.com
    )

    # --- Retrieval (LanceDB corpus store + pluggable embeddings; #807-#810) -----
    # Embedding provider name (WATERMARK_EMBEDDING_PROVIDER). New providers are
    # registered in watermark.retrieval.embeddings.get_provider.
    embedding_provider: str = "sentence_transformers"
    # sentence-transformers model (WATERMARK_EMBEDDING_MODEL). Controls vector
    # dimension — changing the model requires a full ``watermark index`` rebuild.
    embedding_model: str = "all-MiniLM-L6-v2"

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
    def greenops_cache_dir(self) -> Path:
        """Cached GreenOps connector responses (AWS billing/CCFT, Anthropic usage, GitHub,
        eGRID). Regenerable, not committed."""
        return self.cache_dir / "greenops"

    @property
    def air_cache_dir(self) -> Path:
        """Cached AERMET/AERMAP connector pulls (ISD surface, IGRA upper-air, NED DEM). Not committed."""
        return self.cache_dir / "air"

    @property
    def gis_cache_dir(self) -> Path:
        """Cached GIS/imagery STAC responses (Planetary Computer search). Not committed."""
        return self.cache_dir / "gis"

    @property
    def poi_cache_dir(self) -> Path:
        """Cached POI geocoder responses (US Census Geocoder). Not committed."""
        return self.cache_dir / "poi"

    @property
    def civic_cache_dir(self) -> Path:
        """Cached civic page fetches (county CMS/WAF listings). Not committed."""
        return self.cache_dir / "civic"

    @property
    def research_cache_dir(self) -> Path:
        """Cached research-connector responses (Serper web-search, URL-fetch). Not committed."""
        return self.cache_dir / "research"

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
    def lancedb_dir(self) -> Path:
        """LanceDB corpus retrieval index. Regenerable via ``watermark index``; not committed."""
        return self.cache_dir / "lancedb"

    @property
    def reference_dir(self) -> Path:
        """Authoritative external reference data (committed). e.g. ECHO NPDES pulls."""
        return self.data_dir / "reference"

    @property
    def people_dir(self) -> Path:
        """Curated per-individual profiles (markdown + frontmatter) — the entity
        graph's hand-written detail store. Committed."""
        return self.data_dir / "entities" / "people"

    @property
    def poi_dir(self) -> Path:
        """Curated point-of-interest (place) profiles (markdown + frontmatter) — the
        place peer of people_dir; POIs flagged ``watched`` feed imagery tracking. Committed."""
        return self.data_dir / "entities" / "poi"

    @property
    def concepts_dir(self) -> Path:
        """Wiki concept-glossary store (markdown + frontmatter) — term/method
        definitions cross-linked from the wiki (issue #68). Committed."""
        return self.data_dir / "concepts"

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

    @property
    def research_dir(self) -> Path:
        """Agent-driven research runs (findings + issue-proposal manifests). Committed
        on review: a run lands as a branch/PR a human verifies. Read-only on the
        corpus by construction — a run writes only here, never under documents_dir."""
        return self.data_dir / "research"

    @property
    def hypotheses_dir(self) -> Path:
        """Reviewed (site x hypothesis) evidence cells — the boom-origin assessment
        store (``<hypothesis-id>/<site-slug>.yaml``, each carrying evidentiary tags +
        citations). Hand-authored or promoted from a research run; committed. The
        backend peer of the frontend directory lens (watermark.hypotheses)."""
        return self.data_dir / "hypotheses"

    @property
    def catalog_dir(self) -> Path:
        """The data catalog — one typed :class:`watermark.catalog.CatalogEntry` per dataset
        (``<scope>/<id>.yaml``), the single registry of what lives under ``data/``,
        where it came from, its license/access tier, and how it regenerates. Committed
        (epic #631). The peer of ``hypotheses_dir``; validated by ``watermark catalog check``."""
        return self.data_dir / "catalog"

    def anthropic_key_for(self, task: PipelineTask | str | None = None) -> str:
        """The Anthropic API key for a pipeline ``task``, or the base inference key.

        Routes a stage's calls to its own workspace key
        (``WATERMARK_ANTHROPIC_KEY_<TASK>``) for usage attribution (#1080). An unset task
        key — or ``None``/an unknown task — falls back to :attr:`anthropic_api_key`, so a
        single-key deploy behaves exactly as before per-task keys existed.
        """
        if task is not None:
            try:
                slug = PipelineTask(task).value
            except ValueError:
                slug = ""
            value: str = getattr(self, f"anthropic_key_{slug}", "") if slug else ""
            if value:
                return value
        return self.anthropic_api_key

    def ensure_dirs(self) -> None:
        """Create the data directories if they do not yet exist."""
        for path in (self.documents_dir, self.extracted_dir, self.cache_dir):
            path.mkdir(parents=True, exist_ok=True)

    @model_validator(mode="after")
    def _check_otel_credentials(self) -> Settings:
        if self.otel_enabled and not self.honeycomb_api_key:
            raise ValueError(
                "WATERMARK_HONEYCOMB_API_KEY must be set when WATERMARK_OTEL_ENABLED=true"
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def _resolve_site_profile(cls, data: Any) -> Any:
        """Fill the per-site config knobs from the active site profile.

        A profile field is applied only when the matching setting was *not* set
        explicitly (env vars, ``.env`` and constructor kwargs all land in ``data``
        here), so an explicit ``WATERMARK_NWIS_SITES`` / ``Settings(...)`` override
        still wins. An unknown ``site`` is a hard error.

        Runs in ``mode="before"`` so profile values flow through normal field
        validation, which matters twice over. ``nwis_sites`` is a ``list``: injecting
        it here makes Pydantic re-validate it into a fresh per-instance list rather
        than aliasing the frozen module-level ``SiteProfile`` singleton's list — so a
        connector that sorts/appends/removes can't silently mutate it for every later
        consumer (``get_settings()`` is ``lru_cache``d and ``SITES`` is a singleton).
        And because each knob now enters ``data``, it is recorded in
        ``model_fields_set``, so a ``model_dump(exclude_unset=True)`` echo/snapshot
        keeps the per-site knobs instead of dropping exactly the values that pin the
        run to a site (#1366).
        """
        if not isinstance(data, dict):
            return data
        site = data.get("site", cls.model_fields["site"].default)
        try:
            profile = SITES[site]
        except (KeyError, TypeError):
            raise ValueError(
                f"unknown WATERMARK_SITE {site!r}; known sites: {sorted(SITES)}"
            ) from None
        for field in PROFILE_SETTINGS_FIELDS:
            if field not in data:
                data[field] = getattr(profile, field)
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()
