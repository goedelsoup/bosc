"""Site-profile data models for the BOSC network registry.

Split out of the former monolithic ``sites.py`` (#597). Re-exported by the package
:mod:`watermark.sites` ``__init__`` so ``watermark.sites.SiteProfile`` / ``SiteFacility`` /
``PROFILE_SETTINGS_FIELDS`` are unchanged for callers.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from watermark.connectors.gis_schema import GisFloodSchema, GisParcelSchema, GisZoningSchema

_YAML_PATH = Path(__file__).parents[3] / "data" / "sites.yaml"


class SiteEntry(BaseModel):
    """One entry in ``data/sites.yaml`` — the canonical identity for a watershed-point site."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    place: str
    basin_label: str
    receiving_water: str | None = None
    state: str
    codename: str | None = None
    mono: str
    status: str
    selectable: bool
    issue: str | None = None
    map_lat: float | None = None
    map_lon: float | None = None
    map_zoom: int | None = None


_IDENTITY: dict[str, SiteEntry] | None = None


def _get_identity() -> dict[str, SiteEntry]:
    global _IDENTITY
    if _IDENTITY is None:
        raw = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
        _IDENTITY = {e["slug"]: SiteEntry(**e) for e in raw.get("sites", [])}
    return _IDENTITY


class CoolingModelType(StrEnum):
    """The cooling-water archetype of a data-center facility, keyed on physical mechanism.

    Each member selects one spec in :data:`watermark.hydrology.cooling_models.COOLING_MODELS` —
    its own consumptive/withdrawal math and parameter set. The enum lives here (not in
    ``watermark.hydrology``) because the archetype is a **per-site facility attribute**
    (:class:`SiteFacility.cooling_model`) and ``watermark.config`` imports this package,
    so hydrology modules cannot be imported from here.

    Naming ([reference]): the enum is keyed on mechanism because the data-center industry's
    "open loop / closed loop" labels are ambiguous — EPA WaterSense at Work (§6, Cooling
    Towers) calls a recirculating wet tower an *open recirculating* system, which trade
    usage shortens to "open loop", while "closed loop" is used both for sealed dry/air-
    cooled circuits and (confusingly) for tower condenser-water loops. The open/closed
    labels are display-only **aliases**, documented per spec in
    :mod:`watermark.hydrology.cooling_models`; the engine never dispatches on them.

    ``unknown`` means "facility disclosed, cooling method not on record" — never "no
    cooling". It yields a bracketed range, not a single figure. ``off`` is the explicit
    no-cooling-water-load case; ``SiteProfile.facility is None`` also resolves to it.
    """

    OFF = "off"  # no cooling-water load
    EVAPORATIVE_TOWER = "evaporative_tower"  # recirculating wet tower (alias: "open loop")
    ONCE_THROUGH = "once_through"  # surface-water pass-through (alias: "open once-through")
    CLOSED_LOOP_DRY = "closed_loop_dry"  # sealed fluid + dry/air rejection (alias: "closed loop")
    HYBRID_ADIABATIC = "hybrid_adiabatic"  # dry with seasonal evaporative assist
    UNKNOWN = "unknown"  # disclosed facility, undisclosed method -> bracketed range


class SiteFacility(BaseModel):
    """A site's disclosed data-center facility power basis (air-permit-grounded).

    Present only for a site with an identified, documented facility (Lima, from Ohio EPA
    Air PTI P0138965). A site with no such facility leaves ``SiteProfile.facility = None`` —
    the grid stack then emits the per-site grid backdrop (utility / BA / state denominators)
    **without** fabricating a campus load share. Drives :func:`watermark.facility.power.derive_power_basis`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    genset_count: int  # emergency gensets disclosed in the air permit
    genset_mw: float  # ekW each
    it_load_mw: float  # central IT load (N+1 backup ~= IT)
    it_load_low_mw: float  # low end of the N+1 range
    it_load_high_mw: float  # high end
    air_permit_citation: str  # the disclosing permit + committed extraction
    # Disclosed cooling/industrial blowdown discharge — the independent cross-check for the
    # cooling back-solve (:func:`watermark.hydrology.cooling.derive_cooling_basis`, method 2). Per-site
    # (#607): a site that doesn't disclose one leaves these None and the back-solve uses the
    # site's own power-derived consumptive as the high bound (no Lima FM-2 leak).
    blowdown_mgd: float | None = None
    blowdown_citation: str | None = None
    # Cooling archetype (#1054): selected per site, never hardcoded. The default is
    # ``unknown`` — a disclosed facility whose cooling method is not on record must NOT
    # silently inherit the water-intensive evaporative model (it gets a bracketed range
    # instead). ``SiteProfile.facility is None`` resolves to ``off`` in
    # :func:`watermark.hydrology.cooling_models.resolve_cooling_model`.
    cooling_model: CoolingModelType = CoolingModelType.UNKNOWN
    cooling_model_citation: str = "cooling method not disclosed in the record"
    cooling_model_source: Literal["document", "connector", "reference", "assumption"] = "assumption"
    # Per-archetype parameter overrides — a site cites disclosed values here instead of
    # inheriting the archetype defaults. ``None`` = use the spec default (with its cite).
    # A value and its citation travel together (enforced below): an uncited override would
    # silently pick up the generic archetype citation and misattribute the number.
    wue_l_per_kwh: float | None = None
    wue_citation: str | None = None
    cycles_of_concentration: float | None = None
    cycles_citation: str | None = None

    @model_validator(mode="after")
    def _override_citations_paired(self) -> SiteFacility:
        if (self.wue_l_per_kwh is None) != (self.wue_citation is None):
            raise ValueError("wue_l_per_kwh and wue_citation must be set together")
        if (self.cycles_of_concentration is None) != (self.cycles_citation is None):
            raise ValueError("cycles_of_concentration and cycles_citation must be set together")
        return self


class SiteProfile(BaseModel):
    """Everything specific to one watershed-point site. Frozen — a fixed reference value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _fill_from_yaml(cls, data: object) -> object:
        """Back-fill identity fields from data/sites.yaml (the SSOT for #1027).

        Every SiteProfile must have a matching entry in the YAML registry. The fields
        ``place``, ``receiving_water_name``, and ``map_view_lat/lon/zoom`` are authoritative
        in the YAML; profiles that omit them get them filled here. Profiles that still carry
        them explicitly (e.g. during a migration) take precedence via ``setdefault``.
        """
        if not isinstance(data, dict):
            return data
        slug = data.get("slug")
        if not slug:
            return data
        identity = _get_identity()
        entry = identity.get(str(slug))
        if entry is None:
            # Unregistered slug (e.g. a test stub) — skip filling; `watermark sites check` is the gate.
            return data
        data.setdefault("place", entry.place)
        if entry.receiving_water is not None:
            data.setdefault("receiving_water_name", entry.receiving_water)
        if entry.map_lat is not None:
            data.setdefault("map_view_lat", entry.map_lat)
        if entry.map_lon is not None:
            data.setdefault("map_view_lon", entry.map_lon)
        if entry.map_zoom is not None:
            data.setdefault("map_view_zoom", entry.map_zoom)
        return data

    # --- Identity (mirrors sites.ts; ``basin`` is the shared-across-Maumee axis) ---------
    slug: str
    # place, receiving_water_name, map_view_* are authoritative in data/sites.yaml and filled
    # by _fill_from_yaml at construction time (#1027). Defaults satisfy mypy; the validator
    # ensures they're set for all registered slugs. `watermark sites check` is the enforcement gate.
    place: str = ""
    basin: str

    # --- Config knobs resolved into Settings (see PROFILE_SETTINGS_FIELDS) ---------------
    nwis_sites: list[str]
    nasa_power_lat: float
    nasa_power_lon: float
    rsei_fips: str
    econ_fips: str
    eia861_utility_number: int
    eia_state: str = "OH"  # the network is Ohio-dominant; only non-OH sites (Fort Wayne) override
    # County/City GIS layer endpoints — per-site. The connector code that reads them is now
    # jurisdiction-agnostic: the field names + encodings live in the gis_* schemas below (#237).
    parcels_url: str
    zoning_url: str
    floodzone_url: str
    gnis_default_state: str = "OH"  # only non-OH sites (Fort Wayne) override
    hydro_utm_epsg: int
    # Ohio LSC General Assembly (statusreport.lsc.ohio.gov is Ohio-only); "" disables the
    # connector for an out-of-state site (Fort Wayne). Ohio sites share the 136th GA.
    lsc_default_ga: str = "136"

    # --- GIS layer field-maps (jurisdiction schemas; #237) ------------------------------
    # The ArcGIS field names + value encodings the GIS connectors read, lifted off Lima/Allen
    # so a new jurisdiction is config, not a copied connector (mirrors the OPC Profile idiom).
    # Optional: ``None`` means "no connector for this layer here yet" — the connector/CLI then
    # refuses cleanly rather than querying another jurisdiction's fields. Read via
    # ``active_profile`` (NOT in PROFILE_SETTINGS_FIELDS — never bled into Settings).
    gis_parcel: GisParcelSchema | None = None
    gis_zoning: GisZoningSchema | None = None
    gis_flood: GisFloodSchema | None = None

    # --- Stormwater design point + cited assumptions (hydrology/stormwater.py) -----------
    # The NOAA-Atlas-14 corridor point — distinct from the nasa_power loop centroid above.
    design_lat: float
    design_lon: float
    corridor_name: str  # the Atlas-14 design-storm corridor label (drainage.py meta.subject)
    dominant_hsg: str
    hsg_citation: str
    pre_cover: str
    post_cover: str
    developed_pervious_cover: str
    noaa_fallback_24h_depth_in: dict[int, float]
    parcels_relpath: str  # relative to settings.data_dir
    footprint_relpath: str  # relative to settings.data_dir
    # The frozen external-corroboration corridor geometry dir (corridor.geojson +
    # corridor-centerline.geojson), relative to settings.data_dir — folded into the GIS
    # findings by site/gismap.merge_corridor_layer. ``None`` = no corridor layer for this
    # site (the merge then emits nothing rather than reading another site's geometry).
    corridor_geo_relpath: str | None = None

    # --- Per-site onboard reach outputs (point-specific writes; relative to data_dir) ----
    # The point-specific connector outputs `watermark onboard` writes. Lima keeps its legacy
    # (un-slugged) filenames; a new site slug-scopes them so onboarding never clobbers Lima.
    # Basin/state/PJM/national outputs (derived 7Q10, ECHO POTW, consumer-energy is state-
    # but kept per-site for uniformity, ba-interchange, federal) — the shared ones are NOT here.
    # Hydrology (#326):
    climatology_relpath: str  # NASA-POWER climatology (hydrology/climate.py)
    corridor_ddf_relpath: str  # NOAA Atlas-14 corridor DDF (hydrology/drainage.py)
    # Economics (per-site by county FIPS / state / utility):
    baseline_relpath: str  # Census+QCEW county baseline (economics/baseline.py)
    rsei_relpath: str  # EPA RSEI county toxics inventory (rsei.py)
    consumer_energy_relpath: str  # EIA consumer energy prices (economics/energy.py)
    demand_pressure_relpath: str  # facility demand→price-pressure sensitivity (economics/energy.py)
    grid_relpath: str  # EIA-861 utility + grid profile (grid/utility.py)

    # --- Toxics corridor inference (hydrology/toxics.py) ---------------------------------
    toxic_corridor_bbox: tuple[float, float, float, float]  # lat_min, lat_max, lon_min, lon_max
    receiving_water_name: str = ""  # authoritative in data/sites.yaml; filled by _fill_from_yaml

    # --- Water-balance routing fallback (hydrology/balance.py) ---------------------------
    plant_receiving: dict[str, tuple[str, str]]  # fid -> (receiving water, citation)
    abstraction_gage: str

    # --- Refill supply rivers (hydrology/refill.py) -------------------------------------
    # The site's two refill supply rivers (the model sums both, each passby-adjusted). Named
    # by role, not river: for Lima, primary = Auglaize (Fort Jennings), secondary = Ottawa.
    supply_gage_primary: str
    supply_gage_secondary: str
    passby_primary_cfs: float
    passby_secondary_cfs: float

    # --- Grid / facility (grid/*.py, facility/power.py) ---------------------------------
    # The disclosed DC facility (None = no identified facility yet → grid backdrop only, no
    # fabricated campus load share). The serving-utility *identity* (name) is connector-sourced
    # (EIA-861); only its provenance is per-site: a corpus document for Lima, the EIA-861/PUCO
    # service-territory record for a site without corpus coverage.
    facility: SiteFacility | None = None
    serving_utility_citation: str
    # Default "reference" (EIA-861/PUCO service-territory record); only a corpus-grounded site
    # (Lima, from its air permit) overrides to "document".
    serving_utility_source: Literal["document", "connector", "reference", "assumption"] = (
        "reference"
    )

    # --- Grid market (grid/market.py) ---------------------------------------------------
    lmp_usd_mwh: float  # zonal day-ahead LMP fallback (connector-sourced when lmp_pnode_id is set)
    lmp_citation: str
    # The site's PJM pricing zone for the live LMP connector (grid/lmp.py, #121). When pinned,
    # the connector's zonal day-ahead mean overrides lmp_usd_mwh; 0/"" leaves the placeholder
    # (e.g. Bryan/AMP #411, Fort Wayne/I&M #361 — zones not yet pinned). AEP=8445784, ATSI=116013753.
    lmp_pnode_id: int = 0
    lmp_pnode_name: str = ""

    # --- OEPA permit registry (#844) -----------------------------------------------------
    # Known NPDES permit IDs for this site's facilities. Used by ``watermark oepa discover``
    # to annotate results as "known" vs. "new". Not a Settings knob — per-site constant.
    npdes_permits: list[str] = []

    # --- Civil plan artifacts (hydrology/stormplan.py, #901) -----------------------------
    # Relative path (from settings.data_dir) to the committed storm-plan inventory artifact
    # generated by ``watermark storm-plan --refresh``.  ``None`` = this site has not yet extracted
    # a storm/grading plan — ``load_inventory()`` returns ``None`` rather than reading Lima's
    # artifact. A new site sets this once it commits its own extracted inventory.
    storm_inventory_relpath: str | None = None

    # --- Corpus scope — the content bundle's extracted-tree feeds (#762) -----------------
    # The ``data/extracted/**`` collection prefixes that hold THIS site's records. The bundle's
    # corpus-derived feeds (records/timeline/entities/relationships, via ``load_corpus`` +
    # ``load_records``) read only artifacts whose rel-path is under one of these prefixes, so a
    # non-Lima site never inherits Lima's deeds/permits/filings/meetings. A prefix is a path
    # segment, so it spans both a slug-named collection (``"fort-wayne"``) and a jurisdiction+site
    # hybrid (``"idem/fort-wayne"``). ``None`` = the whole extracted tree — Lima, the reference
    # build that owns the un-slugged Allen-County-OH collections (keeps its bundle byte-identical).
    corpus_relpaths: tuple[str, ...] | None = None

    # --- RSEI county (rsei.py) ----------------------------------------------------------
    county_name: str
    # Optional per-site economic-unit caveat, appended to the ``EconomicBaseline.note`` by
    # ``economics.baseline.build_baseline``. For a site whose single-county econ unit does not
    # capture the signature the site's thesis rests on (e.g. WPAFB straddles Greene+Montgomery
    # and its defense-supplier concentration lives in the *other* county), this states that
    # plainly and points the reader at the county/sibling that carries it. Default "" = no note.
    econ_unit_note: str = ""

    # --- Legacy SSG map default view (site/gismap.py) -----------------------------------
    map_view_lat: float = 0.0  # authoritative in data/sites.yaml; filled by _fill_from_yaml
    map_view_lon: float = 0.0
    map_view_zoom: int = 0


# Fields whose authoritative values live in data/sites.yaml and are filled at construction time
# by _fill_from_yaml (the model_validator). They have empty/zero defaults to satisfy mypy; at
# runtime every registered profile has them set from YAML. `watermark sites check` is the gate.
YAML_BACKED_PROFILE_FIELDS: frozenset[str] = frozenset(
    {"place", "receiving_water_name", "map_view_lat", "map_view_lon", "map_view_zoom"}
)

# The config-knob fields a profile shares 1:1 with Settings; Settings fills any of these the
# caller did not set explicitly (env/dotenv/kwarg) from the active profile.
PROFILE_SETTINGS_FIELDS: tuple[str, ...] = (
    "nwis_sites",
    "nasa_power_lat",
    "nasa_power_lon",
    "rsei_fips",
    "econ_fips",
    "eia861_utility_number",
    "eia_state",
    "parcels_url",
    "zoning_url",
    "floodzone_url",
    "gnis_default_state",
    "hydro_utm_epsg",
    "lsc_default_ga",
)
