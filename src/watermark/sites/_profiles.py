"""The registered :class:`SiteProfile` literals + the ``SITES`` registry (#597 split).

One profile per watershed point. Lima is the live reference build; basin sites come online
via their onboarding issues. Per-profile values that equal the network-wide default
(Ohio ``eia_state``/``gnis_default_state``, the 136th GA, ``serving_utility_source``) are
omitted here and supplied by the :class:`SiteProfile` model defaults — only the outliers
(Fort Wayne/Indiana, Lima's corpus-grounded utility source) carry an explicit value.
"""

from __future__ import annotations

from watermark.sites._gis_schemas import (
    ALLEN_IN_PARCEL_SCHEMA,
    CHAMPAIGN_PARCEL_SCHEMA,
    FINDLAY_ZONING_SCHEMA,
    FORT_WAYNE_ZONING_SCHEMA,
    LIMA_FLOOD_SCHEMA,
    LIMA_PARCEL_SCHEMA,
    LIMA_ZONING_SCHEMA,
    LUCAS_AREIS_PARCEL_SCHEMA,
    LUCAS_ZONING_SCHEMA,
    NATIONAL_NFHL_FLOOD_SCHEMA,
    OHIO_STATEWIDE_PARCEL_SCHEMA,
    PUTNAM_PARCEL_SCHEMA,
)
from watermark.sites._model import CoolingModelType, SiteFacility, SiteProfile

# The live reference build. Every value reproduces the pre-#325 hardcoded default exactly —
# see tests/test_sites.py for the zero-drift golden snapshot.
_LIMA = SiteProfile(
    slug="lima",
    basin="maumee",
    # config knobs
    nwis_sites=["04187100", "04186500"],
    nasa_power_lat=40.74,
    nasa_power_lon=-84.11,
    rsei_fips="39003",
    econ_fips="39003",
    eia861_utility_number=14006,
    parcels_url=(
        "https://gis.allencountyohio.com/arcgis/rest/services/AGOL/AGOL_NonEditLayers/MapServer/1"
    ),
    zoning_url=(
        "https://colgis.cityhall.lima.oh.us/server/rest/services/"
        "CitywideMaps/Lima_Zoning/MapServer/6"
    ),
    floodzone_url=(
        "https://colgis.cityhall.lima.oh.us/server/rest/services/"
        "CitywideMaps/Lima_Zoning/MapServer/4"
    ),
    hydro_utm_epsg=32617,
    # GIS field-maps (Allen County parcels + City of Lima zoning/floodzone)
    gis_parcel=LIMA_PARCEL_SCHEMA,
    gis_zoning=LIMA_ZONING_SCHEMA,
    gis_flood=LIMA_FLOOD_SCHEMA,
    # stormwater
    design_lat=40.797,
    design_lon=-84.123,
    corridor_name="Cole St / Bluelick corridor",
    dominant_hsg="C",
    hsg_citation=(
        "Allen County, OH dominant hydrologic soil group C (NRCS soil survey; assumption)"
    ),
    pre_cover="cropland",
    post_cover="developed_campus",
    developed_pervious_cover="open_space",
    # Tc bounds (hr): cropland catchment ~1.0 hr; a fully-paved campus routes ~3x faster
    # (paved gutter/pipe velocities vs sheet flow over cropland) -> ~0.35 hr. Screening-grade.
    pre_tc_hr=1.0,
    post_tc_hr=0.35,
    roundabout_tc_hr=0.2,  # small Cole/Beery roundabout catchment (Pike Run theory)
    noaa_fallback_24h_depth_in={
        1: 2.11,
        2: 2.52,
        5: 3.10,
        10: 3.58,
        25: 4.25,
        50: 4.81,
        100: 5.39,
        200: 6.01,
        500: 6.88,
        1000: 7.59,
    },
    parcels_relpath="reference/periplus/bosc-parcels.geojson",
    footprint_relpath="extracted/plans/bosc-site-footprint.yaml",
    corridor_geo_relpath="reference/periplus",  # the frozen Periplus corridor study area + centerline
    # per-site onboard reach outputs (Lima = legacy un-slugged paths)
    climatology_relpath="reference/hydrology/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/baseline.yaml",
    rsei_relpath="reference/rsei/inventory.yaml",
    consumer_energy_relpath="reference/eia/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/demand-pressure.yaml",
    grid_relpath="reference/eia/grid-profile.yaml",
    # civil plan artifact (#901)
    storm_inventory_relpath="extracted/plans/lma1a.storm-inventory.yaml",
    # toxics
    toxic_corridor_bbox=(40.695, 40.725, -84.140, -84.105),
    # balance
    plant_receiving={
        "watch-american-ii-wwtp": ("Dug Run", "Ohio EPA fact sheet 2PH00006 (American II WWTP)"),
        "watch-american-bath-wwtp": (
            "Pike Run",
            "Ohio EPA fact sheet 2PH00007 (American Bath WWTP)",
        ),
        "watch-shawnee-ii-wwtp": (
            "Ottawa River",
            "Ohio EPA fact sheet 2PK00002 (Shawnee II WWTP)",
        ),
    },
    abstraction_gage="04187100",
    # the Lima WTP intake reach (#1159): grounded with live Ottawa-at-Lima streamflow
    abstraction_node_id="lima-wtp",
    abstraction_node_name="Lima WTP intake (Ottawa/Auglaize)",
    abstraction_river="Ottawa River",
    # refill (primary = Auglaize @ Fort Jennings; secondary = Ottawa @ Lima)
    supply_gage_primary="04186500",
    supply_gage_secondary="04187100",
    passby_primary_cfs=2.5,
    passby_secondary_cfs=0.2,
    supply_river_primary="Auglaize River",
    supply_river_secondary="Ottawa River",
    supply_note_primary=(
        "gauged at Fort Jennings, DOWNSTREAM of Lima's Auglaize intakes with more "
        "drainage area — overstates the flow at the intake (optimistic refill)"
    ),
    supply_note_secondary="net of Lima's upstream Ottawa intakes; reaches 0 cfs in drought",
    # tier-1 SWMM campus sanitary routing (#1159): FM labels, receiving-plant names, the
    # dry-weather base + capacity fallback consulted only when the cited basis is absent
    forcemain_labels={"bosc-fm1": "FM-1", "bosc-fm2": "FM-2"},
    sanitary_receiver_names={
        "watch-lima-fm2-terminus": "City of Lima WWTP",
        "watch-american-bath-wwtp": "American Bath WWTP",
        "watch-american-ii-wwtp": "American II WWTP",
    },
    sanitary_capacity_fallback=[
        (
            "American II WWTP",
            3.6,
            "FM-1",
            "Ohio EPA fact sheet 2PH00006: peak hydraulic capacity 3.6 MGD",
        ),
    ],
    campus_dry_weather_mgd=2.5,  # documented FM-2 industrial discharge (fallback dry base)
    # grid / facility (the disclosed Lima campus; serving-utility provenance = the corpus)
    facility=SiteFacility(
        genset_count=114,
        genset_mw=2.75,  # MW each (~2,750 ekW), per the air permit
        it_load_mw=275.0,  # midpoint of the 250-300 MW estimate (IT ~= backup at N+1)
        it_load_low_mw=250.0,
        it_load_high_mw=300.0,
        air_permit_citation=(
            "OEPA Air PTI P0138965 (Facility 0302022054), committed "
            "data/extracted/permits/4132514.epa.yaml (final, 2026-05-28): "
            "114 hall gensets x 2.75 MW (~2,750 ekW) = ~313 MW backup; IT ~250-300 MW (N+1). "
            "Per-engine rating from the draft public notice (3987141/3987144); engine "
            "size CBI-redacted in the final permit under an Ohio EPA trade-secret grant "
            "(OAC 3745-49-03, 2025-10-08; data/extracted/permits/3859883.epa.yaml)."
        ),
        blowdown_mgd=2.5,  # documented FM-2 industrial discharge, as a blowdown upper bound
        blowdown_citation=(
            "bosc-fm2 2.5 MGD industrial discharge (CMAR RFQ §A.6), taken as cooling "
            "blowdown upper bound"
        ),
        # Cooling archetype (#1054): makes the platform's historical implicit assumption
        # EXPLICIT — [inference] the air permit lists 36 cooling towers (consistent with an
        # open recirculating evaporative plant), but no cooling-system flowrates (CBI-
        # withheld), so the archetype is an assumption, not a documented disclosure.
        # Numbers must not move: the WUE/CoC overrides below carry the exact pre-taxonomy
        # defaults + citations (regression-locked by tests/test_hydro_cooling.py).
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        cooling_model_source="assumption",
        cooling_model_citation=(
            "36 cooling towers on OEPA Air PTI P0138965 imply an evaporative (open "
            "recirculating) plant; cooling-system flowrates are CBI-withheld, so the "
            "archetype is asserted, not disclosed"
        ),
        wue_l_per_kwh=1.8,  # evaporative hyperscale; Google fleet avg ~1.1, evaporative higher
        wue_citation=(
            "evaporative-cooled hyperscale WUE ~1.8 L/kWh (Google fleet avg ~1.1; "
            "36 cooling towers on the air permit)"
        ),
        cycles_of_concentration=5.0,  # cooling-tower cycles of concentration (typical 4-6)
        cycles_citation="cooling-tower cycles of concentration ~5 (typical 4-6)",
        # Air-quality modeling (#1172/#1180): the committed OEPA PTI P0138965 extraction that
        # grounds the fleet's emission rates + synthetic-minor NSR caps. Stack geometry is
        # deliberately left unset — the final permit redacts engine make/model/size as CBI, so
        # the AERMOD deck uses the assumption-tagged screening geometry, never a fabricated fact.
        air_permit_relpath="permits/4132514.epa.yaml",
    ),
    serving_utility_source="document",
    serving_utility_citation=(
        "relator data appendix (data/extracted/legal/select-committee-2026/relator-testimony/"
        "bosc-data-appendix-2026-06-01.md): the 25 MW threshold 'matches the AEP Ohio tariff'; "
        "corroborated by Allen County commissioners' minutes (local AEP 3-phase service, "
        "Res #974-25). Formal confirmation: EIA-861 service territory / PUCO map."
    ),
    # grid
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (#121)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp)"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Allen County, OH",
    # oepa permits (#844)
    npdes_permits=["2PH00006", "2PH00007", "2PK00002"],
)


# The first cohort watershed point (#237): Findlay, OH on the Blanchard River (a Maumee
# tributary via the Auglaize). A *coming-soon* point — its watershed identity is sourced and
# cited below; the facility-specific model inputs (the development land-cover scenario, the
# toxics corridor, per-WWTP receiving waters, the refill supply gages + passby minimums) stay
# `TODO` until an actual data-center development site is identified — that's the data-center
# dimension onboard does not capture, and `watermark onboard findlay --check` tracks the gaps.
# Provenance tags inline: [verified] cited primary source; [inference] grounded reasoning;
# [reference] authoritative dataset; [open] genuinely unsourced (a known lift / pending a site).
_FINDLAY = SiteProfile(
    slug="findlay",
    basin="maumee",  # [verified] Blanchard R. → Auglaize → Maumee → Lake Erie; HUC-8 04100008
    # config knobs
    nwis_sites=[
        "04189000",  # [verified] Blanchard River near Findlay OH (primary, active since 1990; 346 sq mi)
        "04188496",  # [verified] Eagle Creek above Findlay OH (water-quality super-gage; ~51 sq mi)
    ],
    nasa_power_lat=41.0428,  # [verified] Findlay city centroid (Census Gazetteer place 3927048)
    nasa_power_lon=-83.6422,
    rsei_fips="39063",  # [verified] Hancock County, OH
    econ_fips="39063",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio); no municipal electric utility
    # GIS — schema-driven (#237): the field-maps live in gis_parcel/gis_zoning/gis_flood below.
    parcels_url=(  # [reference] Hancock County has no county parcel REST (Beacon/Schneider-only);
        # substitute = the OGRIP Ohio statewide parcels public view, scoped to County='Hancock'
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url=(  # [verified] City of Findlay hosted zoning FeatureServer (ArcGIS Online org XMr9uonP553LyU3o)
        "https://services6.arcgis.com/XMr9uonP553LyU3o/arcgis/rest/services/FindlayZoning/FeatureServer/0"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28) — confirmed 2026-06-19
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    # GIS field-maps: parcels = the OGRIP statewide layer scoped to Hancock (FIPS 39063) — a partial
    # owner-redacted catalog (no owner/value/sale; see OHIO_STATEWIDE_PARCEL_SCHEMA); zoning = the
    # verified City FeatureServer (polygon-only catalog); flood = the shared national NFHL layer.
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "findlay-gis", "query_scope": "County='Hancock'"}
    ),
    gis_zoning=FINDLAY_ZONING_SCHEMA,
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "findlay-gis"}),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Findlay ~83.64degW; zone 17 spans 84-78degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.0428,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.6422,
    corridor_name="Blanchard River corridor",  # [inference] the receiving-water design corridor
    dominant_hsg="D",  # [inference] Great Black Swamp very-poorly-drained clays (Hoytville/Pewamo) → HSG D
    hsg_citation=(
        "Hancock County, OH (NRCS area OH063) dominant hydrologic soil group D — very-poorly-"
        "drained Great Black Swamp clays (Hoytville/Pewamo); NRCS Soil Survey of Hancock County "
        "2006 + Hoytville OSD; [inference] pending an SSURGO area-weighted confirmation"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 v3 (Ohio River Basin) PDS at 41.0428/-83.6422
        1: 2.04,
        2: 2.44,
        5: 3.01,
        10: 3.48,
        25: 4.14,
        50: 4.69,
        100: 5.26,
        200: 5.87,
        500: 6.72,
        1000: 7.42,
    },
    parcels_relpath="reference/findlay/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/findlay/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber Lima)
    climatology_relpath="reference/hydrology/findlay/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/findlay/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/findlay/baseline.yaml",
    rsei_relpath="reference/rsei/findlay/inventory.yaml",
    consumer_energy_relpath="reference/eia/findlay/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/findlay/demand-pressure.yaml",
    grid_relpath="reference/eia/findlay/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on the Blanchard
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    # Findlay↔Ottawa intra-tributary comparison (#417): the Findlay WPCC (OH0025135, 15.0 MGD →
    # 23.21 cfs) screens VIOLATION (2.68x — effluent exceeds the whole low flow) against the shared
    # derived Blanchard 7Q10 (8.67 cfs, USGS 04189000; low-flow-7q10.derived.yaml, #414) vs its
    # downstream Ottawa sibling's TIGHT band (0.54x) — the network's only along-one-river control.
    # See data/reference/network/findlay-ottawa-comparison.yaml (watershed held constant, discharge point varied).
    plant_receiving={},  # [open] cited fact-sheet 7Q10 still pending the Findlay WPCC NPDES fact sheet (#352)
    abstraction_gage="04189000",  # [inference] the primary Blanchard gage near Findlay
    # refill (the water-balance supply model is not yet designed for Findlay)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboard doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not Lima's corpus
        "EIA-861 service-territory file (Ohio Power Co #14006) + PUCO certified-territory map; "
        "AEP Ohio serving Findlay corroborated by the City of Findlay (AEP smart-meter notice)"
    ),
    # grid (same PJM AEP zone as Lima — Ohio Power Co)
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (same zone as Lima)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — same AEP zone as Lima"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Hancock County, OH",  # [verified]
)


# The marquee Maumee comparison node (#235): Fort Wayne, IN — the basin's largest discharger
# (Fort Wayne WWTP 74.0 MGD → Baldwin Ditch → Maumee mainstem; ~4x Lima; ECHO effluent
# [violation]). A *coming-soon* point. The first **out-of-state** site, so it exercises the
# per-site axis across a jurisdiction boundary: Indiana FIPS/state/utility, a UTM-16 reach, the
# national NFHL for flood, and the Ohio-only LSC connector falling away. Geography is sourced +
# cited below. The data-center dimension is now DOCUMENTED (#360): the disclosed facility is Google's
# $2B "Project Zodiac" campus (700+ ac, SE Fort Wayne, served by I&M, operational Dec 2025) — see
# data/extracted/fort-wayne/datacenter-facility.md. The Hatchworks=Google link is [verified] (no longer
# inference): the IDEM §401 WQC001454 record names the applicant verbatim as "Google Data Center"
# (data/extracted/idem/fort-wayne/wqc001454.idem.yaml). The `facility` power basis is now populated from
# the committed IDEM Title V air-permit extraction (data/extracted/idem/fort-wayne/47378f.idem.yaml,
# #360): 34 diesel gensets → ~90 MW IT (genset_mw DERIVED from heat input). The grid `load_share` in
# grid-profile.yaml is still null — it's now derivable (derive_grid_profile reads the power basis) but
# regenerating it needs a live EIA-861 pull for I&M (#9324) + Indiana state retail (WATERMARK_EIA_API_KEY);
# offline it falls back to Ohio denominators, so the regen is a keyed follow-up.
_FORT_WAYNE = SiteProfile(
    slug="fort-wayne",
    basin="maumee",  # [verified] St. Joseph + St. Marys form the Maumee at Fort Wayne; HUC-8 04100005
    # config knobs
    nwis_sites=[
        "04182900",  # [verified] Maumee River at Fort Wayne IN (mainstem, the receiving reach)
        "04180500",  # [verified] St. Joseph River near Fort Wayne IN (north fork of the Maumee)
        "04182000",  # [verified] St. Marys River near Fort Wayne IN (south fork of the Maumee)
    ],
    nasa_power_lat=41.0891,  # [verified] Fort Wayne city centroid (Census 2023 Gazetteer place 1825000)
    nasa_power_lon=-85.1439,
    rsei_fips="18003",  # [verified] Allen County, IN
    econ_fips="18003",
    eia861_utility_number=9324,  # [verified] Indiana Michigan Power Co (AEP subsidiary); EIA-860 via EIA API
    eia_state="IN",
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning = the Allen
    # County (IN) iMap ArcGIS (gis1.acimap.us), the live replacement for the endpoints the
    # 2026-06-19 onboarding found (they 404'd by 2026-06-23). Confirmed live 2026-06-26 (#360).
    parcels_url=(  # [verified] Allen County IN iMap — Parcel_Poly layer 10 (owner + TransferDate)
        "https://gis1.acimap.us/imapweb/rest/services/QueryLayers/QueryLayers/MapServer/10"
    ),
    zoning_url=(  # [verified] Allen County IN iMap — Zoning_Polygons layer 9 (county-wide catalog)
        "https://gis1.acimap.us/imapweb/rest/services/QueryLayers/QueryLayers/MapServer/9"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=ALLEN_IN_PARCEL_SCHEMA,  # [verified] owner-bearing, owner + transfer date (#360)
    gis_zoning=FORT_WAYNE_ZONING_SCHEMA,  # [verified] county-wide zoning catalog (polygon-only)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "fort-wayne-gis"}),
    gnis_default_state="IN",
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Fort Wayne ~85.14 degW; zone 16 spans 90-84 degW)
    lsc_default_ga="",  # [n/a] the LSC connector is Ohio-only (statusreport.lsc.ohio.gov); FW is in Indiana
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.0891,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-85.1439,
    corridor_name="Maumee headwaters corridor",  # [inference] the St. Joseph/St. Marys → Maumee reach
    dominant_hsg="C",  # [verified] SSURGO over the assemblage: 50% C/D + 50% D → HSG C (drained basis)
    hsg_citation=(
        "Allen County, IN dominant hydrologic soil group C (drained basis) — [verified] USDA NRCS "
        "SSURGO via Soil Data Access, a 30-point grid sample over the committed Hatchworks parcel "
        "assemblage (parcel-assemblage.geojson): 50% C/D + 50% D (Pewamo / Blount-Glynwood lake-plain "
        "clays of the upper Maumee). HSG C confirms the prior NRCS-narrative inference; undrained "
        "these soils are group D (high runoff). See data/extracted/fort-wayne/bosc-site-footprint.yaml "
        "(#362). A SURVEYED developed footprint is still pending the stormwater-permit extraction."
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending the Project Zodiac stormwater permit (#360)
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.0891/-85.1439
        1: 2.18,
        2: 2.61,
        5: 3.26,
        10: 3.78,
        25: 4.51,
        50: 5.11,
        100: 5.73,
        200: 6.39,
        500: 7.30,
        1000: 8.04,
    },
    parcels_relpath="reference/fort-wayne/parcel-assemblage.geojson",  # [reference] the Hatchworks assemblage
    # [reference] #362: the facility is Google "Project Zodiac" (#360); the Allen County (IN) parcel REST
    # is wired (gis1.acimap.us, gis_parcel above) and the assemblage geometry is committed — the 11
    # Hatchworks LLC parcels (anchor 6015 Adams Center Rd, mailing Mountain View CA; transferred Jan-2024
    # + a second wave Oct-2025), pulled as WGS84 GeoJSON (parcel-assemblage.geojson, catalogued fort-wayne-
    # parcels). Measured planar acreage ~856 ac (UTM 16N). This is the recorded OWNERSHIP assemblage,
    # NOT a surveyed developed footprint — the developed/impervious boundary stays [open] pending the
    # #360 deed/rezoning/stormwater-permit extraction (mirrors Findlay #355).
    footprint_relpath="extracted/fort-wayne/bosc-site-footprint.yaml",
    # per-site onboard reach outputs (slug-scoped — never clobber Lima/Findlay)
    climatology_relpath="reference/hydrology/fort-wayne/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/fort-wayne/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/fort-wayne/baseline.yaml",
    rsei_relpath="reference/rsei/fort-wayne/inventory.yaml",
    consumer_energy_relpath="reference/eia/fort-wayne/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/fort-wayne/demand-pressure.yaml",
    grid_relpath="reference/eia/fort-wayne/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor on the Maumee
    # balance — Fort Wayne WWTP (IN0032191), the basin's largest POTW. Immediate receptor is
    # Baldwin Ditch (an ungaged ditch → the screen leaves it unscreened, omit-don't-guess); the
    # ditch joins the Maumee at the St. Joseph/St. Marys headwaters (derived 7Q10 ≈ 69.7 cfs). #358/#359.
    plant_receiving={
        "fort-wayne-wwtp": (
            "Baldwin Ditch (immediate receptor) → Maumee River at the St. Joseph/St. Marys headwaters",
            "ECHO NPDES IN0032191 receiving water "
            "(BALDWIN DITCH, MAUMEE R TO ST MARYS RIVER, MAUMEE RIVER); design 74.0 MGD, "
            "actual ~43.9 MGD (2023 DMR) — data/extracted/fort-wayne/wwtp-in0032191.dmr.yaml",
        ),
    },  # [verified: ECHO IN0032191]
    abstraction_gage="04182900",  # [inference] the Maumee-at-Fort-Wayne mainstem gage
    # refill (the water-balance supply model is not yet designed for Fort Wayne)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    # Facility CONFIRMED — Google "Project Zodiac" $2B campus (#360, data/extracted/fort-wayne/
    # datacenter-facility.md). Power basis populated from the committed IDEM Title V air-permit
    # extraction (data/extracted/idem/fort-wayne/47378f.idem.yaml).
    facility=SiteFacility(
        # Project Zodiac (Hatchworks LLC) — IDEM Title V air permit 003-47378-00530. The permit
        # discloses heat input (26.4 MMBTU/hr per engine), NOT an electrical rating, so genset_mw
        # is DERIVED (heat-input x efficiency), unlike Lima's disclosed ekW. genset_count is verbatim.
        genset_count=34,  # [verified] "Thirty-four (34) diesel-fired emergency generators, Gen 1..34" (A.2)
        genset_mw=3.0,  # [inference] 26.4 MMBTU/hr HHV / engine at ~38-43% electrical eff -> ~2.9-3.3 MWe
        it_load_mw=90.0,  # [inference] N+1: IT ~= 0.88 x backup (Lima 275/313 convention); 34 x 3.0 ~= 102 MW backup
        it_load_low_mw=80.0,
        it_load_high_mw=100.0,
        air_permit_citation=(
            "IDEM Title V air permit 003-47378-00530 (issued 2024-09-06), committed "
            "data/extracted/idem/fort-wayne/47378f.idem.yaml: 34 diesel emergency gensets "
            "(Gen 1-34), each 26.4 MMBTU/hr heat input (A.2), operator 'a stationary data center' "
            "(SIC 7374, 650-area phone). genset_mw/it_load are DERIVED from heat input (no disclosed "
            "ekW); refine if the engine nameplate surfaces in the application or the 003-48739 "
            "significant modification (data/documents/idem/fort-wayne/48739d.pdf)."
        ),
        # No disclosed cooling/industrial blowdown (the air permit doesn't cover discharge) → None,
        # so the cooling back-solve uses the power-derived consumptive as the high bound (no Lima leak).
        # Cooling archetype (#1054): [open] the facility is confirmed (IDEM Title V, §401)
        # but no water-cooling method is on record — the Title V permit covers the gensets,
        # not the cooling plant. `unknown` ⇒ a bracketed range (closed_loop_dry…evaporative_
        # tower), never a defaulted evaporative headline (#1057). Refine when the cooling
        # method surfaces (utility water contract, wastewater permit, or the 003-48739 mod).
        cooling_model=CoolingModelType.UNKNOWN,
        cooling_model_source="assumption",
        cooling_model_citation=(
            "cooling method not disclosed: IDEM Title V 003-47378-00530 covers the emergency "
            "gensets only, no cooling-system disclosure on record for Project Zodiac"
        ),
    ),
    serving_utility_citation=(  # [reference] not corpus
        "EIA-861 service-territory file (Indiana Michigan Power Co #9324, an AEP subsidiary) + "
        "Indiana IURC certified-territory; I&M serves the Fort Wayne area (Google Project Zodiac campus)"
    ),
    # grid: Indiana Michigan Power (I&M) settles in PJM's AEP zone — PJM has no separate I&M zone
    # (the 23 ZONE pnodes carry no I&M), so Fort Wayne's zonal LMP IS the AEP zone (#361, verified
    # 2026-06-21 against the live PJM Data Miner 2 zone list). Same AEP pnode/fixture as Lima.
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (I&M is in the AEP zone)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — I&M settles in the PJM AEP zone"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # corpus scope (#762): only Fort Wayne's own extracted records — the slug collection plus the
    # IDEM (Indiana) jurisdiction+site subtree. Without this the bundle inherits Lima's whole corpus.
    corpus_relpaths=("fort-wayne", "idem/fort-wayne"),
    # rsei
    county_name="Allen County, IN",  # [verified]
)


# The small-stream headwaters comparator: Van Wert, OH — the Auglaize-subbasin point. Unlike
# the mainstem comparators (Defiance 12 MGD, Fort Wayne 74 MGD), Van Wert's WWTP is a 4.0 MGD
# plant discharging to a *small tributary* (Town Creek → Little Auglaize → Auglaize → Maumee),
# so the dilution denominator is tiny — the effluent-dominance end of the basin spectrum. A
# *coming-soon* point; an Ohio site (AEP Ohio / PJM AEP zone, the Ohio LSC connector applies),
# so the cross-state connector axis is not re-exercised. Geography is sourced + cited below; the
# data-center dimension and facility-specific model inputs stay `[open]` until a site is
# identified (Van Wert-area discovery is `--research` + corpus follow-up).
_VAN_WERT = SiteProfile(
    slug="van-wert",
    basin="maumee",  # [verified] Town Creek → Little Auglaize → Auglaize → Maumee; HUC-8 04100007
    # config knobs
    nwis_sites=[
        "04191000",  # [verified] Town Creek near Van Wert OH (the WWTP receiving reach; HUC 04100007)
        "04191003",  # [verified] Stripe Creek near Van Wert OH (adjacent Little Auglaize tributary)
    ],
    nasa_power_lat=40.8696,  # [verified] Van Wert city centroid (OSM admin boundary; Census place 45891)
    nasa_power_lon=-84.5829,
    rsei_fips="39161",  # [verified] Van Wert County, OH
    econ_fips="39161",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio); the Van Wert County AEP aggregation
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning discovered in
    # a follow-up live metadata read (Van Wert County GIS + City of Van Wert GIS).
    parcels_url="TODO",  # [open] pending the Van Wert County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Van Wert GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=None,  # [open] pending Van Wert County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Van Wert zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "van-wert-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Van Wert ~84.58 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=40.8696,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-84.5829,
    corridor_name="Town Creek / Little Auglaize corridor",  # [inference] the receiving-water reach
    dominant_hsg="D",  # [inference] Van Wert lake-plain Black Swamp clays (Paulding/Latty/Hoytville) → HSG D
    hsg_citation=(
        "Van Wert County, OH dominant hydrologic soil group D — very-poorly-drained Great Black "
        "Swamp lake-plain clays (Paulding/Latty/Hoytville; NRCS Soil Survey of Van Wert County); "
        "[inference] pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 40.8696/-84.5829
        1: 2.13,
        2: 2.56,
        5: 3.15,
        10: 3.64,
        25: 4.33,
        50: 4.89,
        100: 5.48,
        200: 6.10,
        500: 6.98,
        1000: 7.68,
    },
    parcels_relpath="reference/van-wert/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/van-wert/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber Lima/Findlay/Fort Wayne)
    climatology_relpath="reference/hydrology/van-wert/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/van-wert/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/van-wert/baseline.yaml",
    rsei_relpath="reference/rsei/van-wert/inventory.yaml",
    consumer_energy_relpath="reference/eia/van-wert/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/van-wert/demand-pressure.yaml",
    grid_relpath="reference/eia/van-wert/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor on Town Creek
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    plant_receiving={
        "van-wert-wwtp": ("Town Creek", "Ohio EPA fact sheet 2PD00006 (Van Wert WWTP)"),
    },  # [verified] OH0027910 → Town Creek RM 13.87; design flow 4.0 MGD; fact sheet 2PD00006
    abstraction_gage="04191000",  # [inference] the Town Creek near Van Wert receiving-reach gage
    # refill (the water-balance supply model is not yet designed for Van Wert)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not corpus
        "EIA-861 service-territory file (Ohio Power Co #14006) + PUCO certified-territory; AEP Ohio "
        "serving the City of Van Wert corroborated by the Van Wert County AEP Ohio electric-aggregation program"
    ),
    # grid (same PJM AEP zone as Lima/Findlay — Ohio Power Co)
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (same zone as Lima)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — same AEP zone as Lima"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Van Wert County, OH",  # [verified]
)


# The tidal/lake comparator: Toledo, OH — the Lower Maumee at Lake Erie (#236). Where Lima
# discharges to tiny tributaries and Fort Wayne to the headwaters, the Lucas Co WRRF (22.5 MGD,
# NPDES OH0034223) discharges to the **tidal lower Maumee** at the lake — a fundamentally
# different dilution regime (the "is Lima's tributary siting the outlier?" contrast). A
# *coming-soon* point. The first Ohio site **not on AEP**: Toledo Edison (FirstEnergy, EIA
# #18997) in PJM's **ATSI** zone — so it exercises the grid connector across a utility/holding-
# company/market-zone boundary the AEP sites (Lima/Findlay/Van Wert) never do, while staying in
# Ohio (PUCO, the Ohio LSC). Geography is sourced + cited; the data-center dimension and
# facility-specific model inputs stay `[open]` until a site is identified.
_TOLEDO = SiteProfile(
    slug="toledo",
    basin="maumee",  # [verified] Lower Maumee → Lake Erie; HUC-8 04100009 (Lucas Co WRRF discharge)
    # config knobs
    nwis_sites=[
        "04193500",  # [verified] Maumee River at Waterville OH (mainstem, long record — the basin 7Q10 ref)
        "04193990",  # [verified] Maumee River at Anthony Wayne Bridge, Toledo OH (the tidal lower reach)
    ],
    nasa_power_lat=41.6529,  # [verified] Toledo city centroid (OSM admin boundary; Lucas County)
    nasa_power_lon=-83.5378,
    rsei_fips="39095",  # [verified] Lucas County, OH
    econ_fips="39095",
    eia861_utility_number=18997,  # [verified] The Toledo Edison Co (FirstEnergy); EIA-861 2024 States sheet
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning discovered in
    # a follow-up live metadata read (Lucas County GIS / AREIS + City of Toledo GIS).
    # GIS — schema-driven (#237 / #384). Lucas County's AREIS is the richest GIS in the network:
    # parcels = the owner-bearing AREIS land-use-classification layer (38); zoning = the parcel-level
    # AREIS Parcel_Zoning layer; flood = the shared national NFHL. The appraised-value PARID join
    # (AREIS layer 83) is a tracked follow-up — market values stay null until then.
    parcels_url=(  # [verified] Lucas County Auditor AREIS — layer 38 (owner + land-use CAMA)
        "https://lcaudgis.co.lucas.oh.us/gisaudserver/rest/services/AREIS_Web_Map_MIL1/MapServer/38"
    ),
    zoning_url=(  # [verified] Lucas County AREIS — Parcel_Zoning layer 0 (parcel-level zoning)
        "https://lcaudgis.co.lucas.oh.us/gisaudserver/rest/services/"
        "LandUse_Zoning/Parcel_Zoning/MapServer/0"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=LUCAS_AREIS_PARCEL_SCHEMA,  # [verified] AREIS layer 38 — owner + land-use (#384)
    gis_zoning=LUCAS_ZONING_SCHEMA,  # [verified] AREIS Parcel_Zoning — parcel-level catalog (#384)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "toledo-gis"}),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Toledo ~83.54 degW; zone 17 spans 84-78 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.6529,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.5378,
    corridor_name="Lower Maumee / tidal corridor",  # [inference] the tidal Maumee → Lake Erie reach
    dominant_hsg="D",  # [inference] Lucas Co lake-plain Black Swamp clays (Hoytville/Toledo/Lucas) → HSG D
    hsg_citation=(
        "Lucas County, OH dominant hydrologic soil group D — very-poorly-drained Great Black "
        "Swamp lake-plain clays (Hoytville/Toledo/Lucas series; NRCS Soil Survey of Lucas County); "
        "[inference] pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.6529/-83.5378
        1: 2.01,
        2: 2.42,
        5: 3.03,
        10: 3.53,
        25: 4.25,
        50: 4.84,
        100: 5.47,
        200: 6.15,
        500: 7.12,
        1000: 7.92,
    },
    parcels_relpath="reference/toledo/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/toledo/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber Lima/Findlay/Fort Wayne/Van Wert)
    climatology_relpath="reference/hydrology/toledo/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/toledo/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/toledo/baseline.yaml",
    rsei_relpath="reference/rsei/toledo/inventory.yaml",
    consumer_energy_relpath="reference/eia/toledo/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/toledo/demand-pressure.yaml",
    grid_relpath="reference/eia/toledo/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on the Lower Maumee
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    plant_receiving={},  # [open] pending Toledo-area WWTP NPDES fact sheets
    abstraction_gage="04193500",  # [inference] the Maumee-at-Waterville mainstem gage (nearest the WRRF reach)
    # refill (the water-balance supply model is not yet designed for Toledo)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not corpus
        "EIA-861 service-territory file (The Toledo Edison Co #18997, a FirstEnergy operating "
        "company) + PUCO certified-territory; Toledo Edison serves the Toledo metro"
    ),
    # grid (Toledo Edison is in PJM's ATSI / FirstEnergy zone — NOT the AEP zone of the other OH sites)
    lmp_usd_mwh=45.84,  # connector-sourced ATSI-zone 2025 day-ahead annual mean (#387; not the AEP value)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, ATSI zone (FirstEnergy / Toledo Edison, pnode 116013753), "
        "2025 day-ahead annual mean $45.84/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp)"
    ),
    lmp_pnode_id=116013753,
    lmp_pnode_name="ATSI",
    # rsei
    county_name="Lucas County, OH",  # [verified]
)


# The Maumee-mainstem comparator: Defiance, OH (#238). The Defiance WWTP (12.0 MGD, NPDES
# OH0024899) discharges to the **Maumee mainstem** right at the Maumee/Auglaize/Tiffin
# confluence — where the river carries far more flow than Lima's tributaries, so the screen
# reads "tight" (~6.2:1) rather than violation (docs/bigger-picture.md §2): the cleanest test
# of "is Lima's tributary siting what drives its violation?". A *coming-soon* point. Served by
# Toledo Edison (FirstEnergy / PJM ATSI, EIA #18997 — same as Toledo, the largest IOU in
# Defiance County), so it reuses the non-AEP grid path (#236) and stays in Ohio (PUCO, the
# Ohio LSC). Geography is sourced + cited; the data-center dimension and facility-specific
# model inputs stay `[open]` until a site is identified.
_DEFIANCE = SiteProfile(
    slug="defiance",
    basin="maumee",  # [verified] Maumee mainstem at the Auglaize/Tiffin confluence; HUC-8 04100009
    # config knobs
    nwis_sites=[
        "04192500",  # [verified] Maumee River near Defiance OH (the mainstem receiving reach, below the confluence)
        "04191500",  # [verified] Auglaize River near Defiance OH (the major tributary joining at Defiance)
    ],
    nasa_power_lat=41.2868,  # [verified] Defiance city centroid (OSM admin boundary; Defiance County)
    nasa_power_lon=-84.3621,
    rsei_fips="39039",  # [verified] Defiance County, OH
    econ_fips="39039",
    eia861_utility_number=18997,  # [reference] The Toledo Edison Co (FirstEnergy) — largest IOU in Defiance Co
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning discovered in
    # a follow-up live metadata read (Defiance County GIS + City of Defiance GIS).
    parcels_url="TODO",  # [open] pending the Defiance County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Defiance GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=None,  # [open] pending Defiance County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Defiance zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "defiance-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Defiance ~84.36 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.2868,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-84.3621,
    corridor_name="Maumee-Auglaize confluence corridor",  # [inference] the Maumee mainstem reach at Defiance
    dominant_hsg="D",  # [inference] Defiance Co Maumee lake-plain Black Swamp clays (Hoytville/Nappanee) → HSG D
    hsg_citation=(
        "Defiance County, OH dominant hydrologic soil group D — very-poorly-drained Great Black "
        "Swamp lake-plain clays (Hoytville/Nappanee/Paulding; NRCS Soil Survey of Defiance County); "
        "[inference] pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.2868/-84.3621
        1: 2.06,
        2: 2.48,
        5: 3.08,
        10: 3.57,
        25: 4.26,
        50: 4.82,
        100: 5.41,
        200: 6.03,
        500: 6.90,
        1000: 7.60,
    },
    parcels_relpath="reference/defiance/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/defiance/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber the other sites)
    climatology_relpath="reference/hydrology/defiance/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/defiance/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/defiance/baseline.yaml",
    rsei_relpath="reference/rsei/defiance/inventory.yaml",
    consumer_energy_relpath="reference/eia/defiance/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/defiance/demand-pressure.yaml",
    grid_relpath="reference/eia/defiance/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    # [inference] the Defiance industrial cluster on the Maumee/Auglaize mainstem from the
    # Auglaize/Tiffin confluence downstream (#393): covers GM Defiance Casting (now GM Global
    # Propulsion Systems, 41.282/-84.292), the three Johns Manville fiberglass plants (~41.28-41.30/
    # -84.34 to -84.36), and GT Technologies (41.27/-84.39); excludes the far-west Hicksville cluster
    # (Syn Ind. -84.75). A water-releasing RSEI facility inside the box is inferred to discharge to
    # the Maumee (tagged `assumption`). (lat_min, lat_max, lon_min, lon_max)
    toxic_corridor_bbox=(41.26, 41.31, -84.40, -84.28),
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    plant_receiving={},  # [open] pending Defiance-area WWTP NPDES fact sheets
    abstraction_gage="04192500",  # [inference] the Maumee-near-Defiance mainstem gage (below the confluence)
    # refill (the water-balance supply model is not yet designed for Defiance)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not corpus
        "EIA-861 service-territory file (The Toledo Edison Co #18997, a FirstEnergy operating "
        "company; the largest IOU in Defiance County) + PUCO certified-territory; the City of "
        "Defiance electric-aggregation program rides Toledo Edison distribution"
    ),
    # grid (Toledo Edison is in PJM's ATSI / FirstEnergy zone — same non-AEP path as Toledo)
    lmp_usd_mwh=35.0,  # [inference] PJM ATSI-zone placeholder — verify via PJM Data Miner 2 (not the AEP value)
    lmp_citation=(
        "PJM ATSI zone (FirstEnergy / Toledo Edison) ~2024 annual average LMP ($/MWh) via PJM Data "
        "Miner 2 da_hrl_lmps; [inference] not the AEP-zone value used by the AEP OH sites — verify"
    ),
    # rsei
    county_name="Defiance County, OH",  # [verified]
)


# The municipal-utility / Tiffin-subbasin headwaters comparator: Bryan, OH (#380). The Bryan
# WWTP (NPDES OH0020532) discharges to Prairie Creek → Tiffin River → Maumee → Lake Erie at the
# far NW corner of the basin (HUC-8 04100006 Tiffin) — a small-tributary headwaters point like
# Van Wert, but in the Tiffin subbasin rather than the Auglaize. A *coming-soon* point. Its
# distinguishing feature is the GRID: Bryan is the network's **first municipal electric utility**
# (City of Bryan, EIA #2439; an American Municipal Power member, PJM) — not an IOU like every
# other registered site, so it exercises the grid connector's short-form (EIA-861S) path and the
# ownership-aware retail-regulator (municipal home rule, not PUCO). Geography is sourced + cited;
# the data-center dimension and facility-specific model inputs stay `[open]` until a site is found.
_BRYAN = SiteProfile(
    slug="bryan",
    basin="maumee",  # [verified] Prairie Creek → Tiffin River → Maumee → Lake Erie; HUC-8 04100006
    # config knobs
    nwis_sites=[
        "04185000",  # [verified] Tiffin River at Stryker OH (receiving Tiffin mainstem below Bryan; long record)
        "04184500",  # [verified] Bean Creek at Powers OH (the Tiffin's principal gaged headwaters tributary)
    ],
    nasa_power_lat=41.4748,  # [verified] Bryan city centroid (OSM admin boundary relation 182831; Census place 09064)
    nasa_power_lon=-84.5525,
    rsei_fips="39171",  # [verified] Williams County, OH
    econ_fips="39171",
    eia861_utility_number=2439,  # [verified] City of Bryan - (OH); MUNICIPAL, EIA-861S short-form filer (BA=PJM)
    # GIS — schema-driven (#237). Parcels (#410): Williams County, OH publishes NO county parcel
    # REST of its own (the bhamaps PAT MapServer that would host one has the same expired TLS cert
    # as Van Wert/Defiance, #421/#394), so — exactly like Findlay/Hancock — the substitute is the
    # OGRIP Ohio statewide parcels public view scoped to County='Williams'. NOTE: the ArcGIS org the
    # onboarding GIS-discovery pass flagged as a "wire-ready Williams County ArcGIS"
    # (services1.arcgis.com/D85sDZoJyameepNh) is Williams County, NORTH DAKOTA — a same-named-county
    # cross-state misidentification (situs cities Williston/Tioga/Grenora; owner Hess Tioga Gas
    # Plant). It is NOT wired here. Flood = the shared national NFHL; zoning stays [open].
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels, scoped to County='Williams' (39171)
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending a real City of Bryan / Williams Co OH zoning REST (none found)
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        # Williams' OGRIP LocalParcelID is the dashed NN-NNN-NN-NNN.NNN form (e.g. "062-350-02-013.001"),
        # not Hancock's dashless 12 digits — so id lookups are verbatim, with the dashed deed_id_regex.
        update={
            "reference_dir": "bryan-gis",
            "query_scope": "County='Williams'",
            "id_normalize": "verbatim",
            "deed_id_regex": r"\b\d{3}-\d{3}-\d{2}-\d{3}\.\d{3}\b",
        }
    ),
    gis_zoning=None,  # [open] no real City of Bryan/Williams OH zoning REST (the discovered one was ND)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "bryan-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Bryan ~84.55 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.4748,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-84.5525,
    corridor_name="Prairie Creek / Tiffin River corridor",  # [inference] the receiving-water reach
    dominant_hsg="C",  # [inference] Williams Co upper-Maumee/Tiffin till plain (Blount/Glynwood/Pewamo) → HSG C
    hsg_citation=(
        "Williams County, OH dominant hydrologic soil group C — upper-Maumee/Tiffin till-plain "
        "soils (Blount/Glynwood/Pewamo association; NRCS Soil Survey of Williams County), the "
        "till-plain headwaters rather than the lake-plain Black Swamp clays (HSG D) downstream; "
        "[inference] pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.4748/-84.5525
        1: 2.07,
        2: 2.48,
        5: 3.10,
        10: 3.60,
        25: 4.30,
        50: 4.87,
        100: 5.48,
        200: 6.12,
        500: 7.04,
        1000: 7.78,
    },
    parcels_relpath="reference/bryan/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/bryan/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber the other sites)
    climatology_relpath="reference/hydrology/bryan/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/bryan/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/bryan/baseline.yaml",
    rsei_relpath="reference/rsei/bryan/inventory.yaml",
    consumer_energy_relpath="reference/eia/bryan/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/bryan/demand-pressure.yaml",
    grid_relpath="reference/eia/bryan/grid-profile.yaml",
    # [inference] the City of Bryan reach of Prairie Creek (#412): covers the Bryan-city industrial
    # cluster — NEW ERA OHIO (41.478/-84.559; now CLOSED, a legacy emitter), Titan Tire of Bryan
    # (41.467/-84.530; active), Hayes-Albion, Ohio Art, A-Stamp, Plastech — and excludes the
    # Montpelier/Edgerton/Stryker facilities on other drainages (Chase Brass 41.61, A Schulman
    # -84.43, Edgerton -84.75). A water-releasing RSEI facility inside the box is inferred to
    # discharge to Prairie Creek (tagged `assumption`). (lat_min, lat_max, lon_min, lon_max)
    toxic_corridor_bbox=(41.46, 41.49, -84.57, -84.52),
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    plant_receiving={},  # [open] pending Bryan-area WWTP NPDES fact sheets
    abstraction_gage="04185000",  # [inference] the Tiffin-at-Stryker mainstem gage (receiving reach below Bryan)
    # refill (the water-balance supply model is not yet designed for Bryan)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] municipal home-rule electric (NOT PUCO rate-regulated)
        "EIA-861S Short Form (City of Bryan - OH, #2439; Municipal, BA=PJM, ~160 GWh sold 2024) — "
        "Bryan Municipal Utilities, a municipally-owned electric system and American Municipal "
        "Power (AMP) member; municipal home-rule retail, the network's first municipal/short-form "
        "utility. Wholesale power + PJM scheduling are through AMP, not an IOU holding company"
    ),
    # grid: Bryan municipal load is scheduled into PJM via AMP, but the City-of-Bryan load settles
    # in the PJM AEP zone — the live PJM Data Miner 2 pnode table lists CTYBRYAN ("City of Bryan",
    # LOAD pnodes 32411011/32411013) in zone AEP (#411, verified 2026-06-21). So Bryan's zonal LMP
    # IS the AEP zone (same pnode/fixture as the AEP OH sites), despite the AMP wholesale arrangement.
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (CTYBRYAN is in AEP)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — the City-of-Bryan load "
        "(CTYBRYAN) settles in the PJM AEP zone"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Williams County, OH",  # [verified]
)


# The intra-tributary (same-river) comparator: Ottawa, OH (#381) — the **Village** of Ottawa,
# Putnam County, on the **Blanchard River**, the downstream sibling of Findlay (#237, also on the
# Blanchard). The Ottawa WWTP (NPDES OH0026921, 3.0 MGD) discharges to the Blanchard → Auglaize →
# Maumee → Lake Erie (HUC-8 04100008). Where most network points compare *across* tributaries,
# Findlay↔Ottawa is a comparison *along one river* — same receiving water, two points ~40 river-mi
# apart — a clean control on watershed identity. A *coming-soon* point; an Ohio AEP site (AEP Ohio /
# PJM AEP zone, the Ohio LSC applies), so the cross-state / non-AEP connector axes are not
# re-exercised. (Disambiguation: NOT Ottawa County / Port Clinton, and NOT the Ottawa River of Lima
# or Toledo.) Geography is sourced + cited; the data-center dimension and facility-specific model
# inputs stay `[open]` until a site is identified.
_OTTAWA = SiteProfile(
    slug="ottawa",
    basin="maumee",  # [verified] Blanchard R. → Auglaize → Maumee → Lake Erie; HUC-8 04100008 (Blanchard)
    # config knobs
    nwis_sites=[
        "04189260",  # [verified] Blanchard River at Ottawa OH (the WWTP receiving reach, at the village)
        "04189500",  # [verified] Blanchard River at Glandorf OH (the long-record Blanchard gage just downstream)
    ],
    nasa_power_lat=41.0192,  # [verified] Ottawa village centroid (OSM admin boundary relation 182178; Putnam Co)
    nasa_power_lon=-84.0472,
    rsei_fips="39137",  # [verified] Putnam County, OH
    econ_fips="39137",
    eia861_utility_number=14006,  # [reference] Ohio Power Co (AEP Ohio) — the IOU serving the incorporated village
    # GIS — schema-driven (#237): parcels = Putnam County's self-hosted ArcGIS (#420); flood = the
    # shared national NFHL; zoning still pending (the village's zoning is class-coded / map-only).
    parcels_url=(  # [verified] Putnam County GIS — Parcels layer 0 (auditor CAMA + geometry)
        "https://putnamcountygis.com/arcgis/rest/services/Parcels/Parcels/MapServer/0"
    ),
    zoning_url="TODO",  # [open] pending the Village of Ottawa, OH GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=PUTNAM_PARCEL_SCHEMA,  # [verified] Putnam County Parcels (owner + CAMA values; #420)
    gis_zoning=None,  # [open] pending Village of Ottawa zoning-layer discovery (class-coded/map-only)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "ottawa-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Ottawa ~84.05 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = village centroid; cover scenario pending a site)
    design_lat=41.0192,  # [verified] village centroid = NOAA Atlas-14 point
    design_lon=-84.0472,
    corridor_name="Lower Blanchard River corridor",  # [inference] the receiving-water reach below Findlay
    dominant_hsg="D",  # [inference] Putnam Co lake-plain Black Swamp clays (Hoytville/Latty/Paulding) → HSG D
    hsg_citation=(
        "Putnam County, OH dominant hydrologic soil group D — very-poorly-drained Great Black "
        "Swamp lake-plain clays (Hoytville/Latty/Paulding/Nappanee; NRCS Soil Survey of Putnam "
        "County); [inference] pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.0192/-84.0472
        1: 2.07,
        2: 2.48,
        5: 3.05,
        10: 3.52,
        25: 4.19,
        50: 4.74,
        100: 5.31,
        200: 5.91,
        500: 6.75,
        1000: 7.44,
    },
    parcels_relpath="reference/ottawa/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/ottawa/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber the other sites)
    climatology_relpath="reference/hydrology/ottawa/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/ottawa/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/ottawa/baseline.yaml",
    rsei_relpath="reference/rsei/ottawa/inventory.yaml",
    consumer_energy_relpath="reference/eia/ottawa/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/ottawa/demand-pressure.yaml",
    grid_relpath="reference/eia/ottawa/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on the Blanchard
    # balance (per-WWTP receiving waters pending the site's NPDES fact sheets)
    # Findlay↔Ottawa intra-tributary comparison (#417): the Ottawa WWTP (OH0026921, 3.0 MGD →
    # 4.64 cfs) screens TIGHT (0.54x) against the shared derived Blanchard 7Q10 (8.67 cfs, USGS
    # 04189000; low-flow-7q10.derived.yaml, #414) vs its upstream Findlay sibling's VIOLATION band
    # (2.68x) — the network's only along-one-river control. See the committed artifact
    # data/reference/network/findlay-ottawa-comparison.yaml (watershed held constant, discharge point varied).
    plant_receiving={},  # [open] cited fact-sheet 7Q10 still pending the Ottawa WWTP NPDES fact sheet (#415)
    abstraction_gage="04189260",  # [inference] the Blanchard-at-Ottawa receiving-reach gage
    # refill (the water-balance supply model is not yet designed for Ottawa)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not corpus
        "EIA-861 service-territory file (Ohio Power Co #14006) + PUCO certified-territory: AEP Ohio "
        "serves the incorporated Village of Ottawa; rural Putnam County is served by cooperatives "
        "(Paulding-Putnam, Midwest, Hancock-Wood, Tricounty) — the village seat is AEP Ohio"
    ),
    # grid (same PJM AEP zone as Lima/Findlay/Van Wert — Ohio Power Co; Findlay is the Blanchard sibling)
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (same zone as Lima)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — same AEP zone as Lima/Findlay"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Putnam County, OH",  # [verified]
)


# The network's FIRST Miami-basin site (the second basin branch) and the flagship of the
# Wright-Patterson / Mad River corridor expansion. Urbana sits on the **Mad River** in
# Champaign County — the clean headwaters of the **Mad River buried-valley aquifer** (glacial
# outwash sand & gravel; a US-EPA sole-source aquifer that supplies the Springfield/Dayton/
# Wright-Patterson AFB corridor downstream). That geology is the deliberate CONTRAST with the
# Maumee lake-plain sites: a groundwater-dominated, highly permeable HSG A/B valley fill, the
# inverse of the poorly-drained Black Swamp clays (HSG D). Sink is the Ohio River, not Lake
# Erie, and there is no Maumee-style basin TMDL — a genuinely different mix of influences.
# Registered for onboarding (#440); most fields are [open] research targets filled by
# `watermark onboard urbana --research` — only the verified geography/gages are set here.
_URBANA = SiteProfile(
    slug="urbana",
    basin="great-miami",  # [verified] Mad River → Great Miami River → Ohio River (HUC-8 05080001)
    nwis_sites=[
        "03267000",  # [verified] Mad River near Urbana OH (the at-site supply/abstraction reach)
        "03267900",  # [verified] Mad River at St Paris Pike at Eagle City OH (downstream of Urbana)
    ],
    nasa_power_lat=40.1084,  # [verified] Urbana city centroid (Census place 3979002)
    nasa_power_lon=-83.7524,
    rsei_fips="39021",  # [verified] Champaign County, OH
    econ_fips="39021",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Champaign Co [verified]
    parcels_url=(  # [verified] Champaign County Engineer (CCEO) AGOL — parcel_joined layer 0 (owner CAMA)
        "https://services5.arcgis.com/HBIN2hfRscrws7eM/arcgis/rest/services/"
        "parcel_joined/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] no public per-parcel City of Urbana / Champaign Co OH zoning REST found
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Urbana ~83.75 degW; zone 17 spans 84-78 degW)
    gis_parcel=CHAMPAIGN_PARCEL_SCHEMA,  # [verified] CCEO parcel_joined — owner + CAMA values (#797)
    gis_zoning=None,  # [open] pending City of Urbana zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "urbana-gis"}),
    design_lat=40.1084,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.7524,
    corridor_name="Mad River buried-valley corridor",  # [inference] the Mad River valley reach at Urbana
    dominant_hsg="B",  # [inference] Mad River buried-valley outwash sand & gravel (well-drained valley fill)
    hsg_citation=(
        "Champaign County / Mad River valley at Urbana sits on the Mad River buried-valley aquifer "
        "— glacial outwash sand & gravel, a US-EPA designated sole-source aquifer feeding the "
        "Springfield/Dayton/Wright-Patterson AFB corridor downstream — so the valley fill is "
        "well-drained HSG B, the INVERSE of the Maumee lake-plain Black Swamp clays (HSG D); "
        "[inference] pending an SSURGO area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/urbana/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/urbana/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/urbana/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/urbana/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/urbana/baseline.yaml",
    rsei_relpath="reference/rsei/urbana/inventory.yaml",
    consumer_energy_relpath="reference/eia/urbana/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/urbana/demand-pressure.yaml",
    grid_relpath="reference/eia/urbana/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on the Mad River
    plant_receiving={
        "urbana-wpcf": (
            "Mad River",
            # NPDES OH0027880 / Ohio EPA 1PD00011 (City of Urbana WPCF); outfall 001 at
            # 40.095278 -83.797222 (0.38 mi south SR 36); design flow 4.5 MGD; avg ~1.6 MGD.
            # Source: permit renewal application eDoc 3832476 (filed 2025-05-29) [verified].
            "NPDES OH0027880/1PD00011 (City of Urbana WPCF); outfall 001 → Mad River; "
            "design flow 4.5 MGD [verified — permit renewal app eDoc 3832476]",
        ),
    },
    abstraction_gage="03267000",  # [verified] Mad River near Urbana OH
    supply_gage_primary="03267000",  # [verified] Mad River near Urbana
    supply_gage_secondary="03267900",  # [verified] Mad River at Eagle City (downstream)
    # [derived] LP3 7Q10 at USGS 03267000 (Mad River near Urbana, 39 yr 1980-2024) —
    # conservative abstraction screen floor; regulatory passby pending the OEPA permit fact sheet.
    passby_primary_cfs=53.67,
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] the WPAFB-corridor data-center dimension is the research target (#440)
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) is the IOU serving Champaign County, OH — the Urbana LSE (no municipal electric). [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Champaign County, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Champaign County, OH",  # [verified]
)


# The network's SECOND Miami-basin site (onboarding #452 under epic #451) and the MID-CORRIDOR
# node of the Mad River line: Springfield sits ~20 mi downstream of Urbana and ~25 mi upstream
# of Dayton / Wright-Patterson AFB, on the same **Mad River buried-valley sole-source aquifer**
# (US-EPA designated) — the Springfield municipal well field is the textbook draw on that
# outwash sand & gravel. What distinguishes Springfield from headwater Urbana is a SECOND
# supply water: **Buck Creek**, regulated by USACE **C.J. Brown Reservoir** (a flood-control +
# water-supply impoundment NE of the city), joining the Mad River at Springfield — a managed,
# two-source hydrology versus Urbana's single free-flowing reach. The data-center dimension
# (the thread the Springfield epic #451 tracks) is the 5C Data Centers / Vultr build at
# PrimeOhio (601 Benjamin Drive) plus a separate Crusoe build (discovered #454, 2026-06-22) —
# the Roshel / International Motors "Springfield APA" (2026-03-30) is an armored-vehicle plant
# Asset Purchase Agreement (manufacturing, NOT a data center) and is scoped out of the graph
# (#453). All such fields stay [open] research targets filled by `watermark onboard springfield`.
_SPRINGFIELD = SiteProfile(
    slug="springfield",
    basin="great-miami",  # [verified] Mad River → Great Miami River → Ohio River (HUC-8 05080001)
    nwis_sites=[
        "03269500",  # [verified] Mad River near Springfield OH (the at-site supply/abstraction reach)
        "03267900",  # [verified] Mad River at St Paris Pike at Eagle City OH (upstream, Urbana→Springfield)
        "03268100",  # [verified] Buck Creek bl CJ Brown Reservoir nr Springfield OH (the second supply water)
    ],
    nasa_power_lat=39.9242,  # [verified] Springfield, OH city centroid (39deg55'27"N 83deg48'32"W)
    nasa_power_lon=-83.8089,
    rsei_fips="39023",  # [verified] Clark County, OH
    econ_fips="39023",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Clark Co [verified]
    parcels_url="TODO",  # [open] pending the Clark County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Springfield, OH GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Springfield ~83.81 degW; zone 17 spans 84-78 degW)
    gis_parcel=None,  # [open] pending Clark County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Springfield zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "springfield-gis"}),
    design_lat=39.9242,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.8089,
    corridor_name="Mad River buried-valley corridor",  # [inference] the Mad River valley reach at Springfield
    dominant_hsg="B",  # [inference] Mad River buried-valley outwash sand & gravel (well-drained valley fill)
    hsg_citation=(
        "Clark County / Springfield sits on the Mad River buried-valley aquifer - glacial "
        "outwash sand & gravel, a US-EPA designated sole-source aquifer tapped directly by the "
        "Springfield municipal well field - so the valley fill is well-drained HSG B, the "
        "INVERSE of the Maumee lake-plain Black Swamp clays (HSG D); [inference] pending an "
        "SSURGO area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/springfield/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/springfield/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/springfield/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/springfield/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/springfield/baseline.yaml",
    rsei_relpath="reference/rsei/springfield/inventory.yaml",
    consumer_energy_relpath="reference/eia/springfield/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/springfield/demand-pressure.yaml",
    grid_relpath="reference/eia/springfield/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on the Mad River
    plant_receiving={},  # [open] pending the Springfield-area WWTP NPDES fact sheet(s)
    abstraction_gage="03269500",  # [verified] Mad River near Springfield OH
    supply_gage_primary="03269500",  # [verified] Mad River near Springfield
    supply_gage_secondary="03268100",  # [verified] Buck Creek bl CJ Brown Reservoir (the second supply water)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] data-center dimension = 5C/Vultr + Crusoe at PrimeOhio (#454); pending a pinned facility
    serving_utility_citation="EIA-861 2024 Service_Territory: Clark County, OH is served by Dayton Power & Light (#4922), Duke Energy Ohio (#3542) and Ohio Edison — no AEP; the Springfield city LSE is DP&L #4922. [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — city LSE is AES Ohio "
        "(DP&L) #4922; EIA-861 shows no AEP in Clark County, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light, Clark County)
    lmp_pnode_name="DAY",
    county_name="Clark County, OH",  # [verified]
)


# The network's FIRST Little Miami-basin site (a THIRD basin branch, after Maumee and Great
# Miami) and the WPAFB-adjacent node: Xenia / Greene County sits on the **Little Miami River**,
# SE of Wright-Patterson AFB. Its distinguishing influence is NOT a new geology but a heightened
# **regulatory overlay** the other sites lack — the Little Miami is a **National & State Scenic
# River** (NPS Wild & Scenic + Ohio Scenic River), a protected receiving water that materially
# constrains a large new discharger/withdrawal. The aquifer is the same buried-valley sole-source
# system (Greene County's Xenia/Beavercreek well fields draw on the Mad River / Little Miami
# outwash valleys), but the inter-valley till uplands at Xenia proper are less permeable than the
# Mad River outwash - so the dominant HSG is footprint-dependent. The WPAFB defense-supplier
# corridor + the base groundwater plume are the [open] data-center/contamination overlays (#444).
_XENIA = SiteProfile(
    slug="xenia",
    basin="little-miami",  # [verified] Little Miami River → Ohio River (HUC-8 05090202); a 3rd basin branch
    nwis_sites=[
        "03240000",  # [verified] Little Miami River near Oldtown OH (at-site reach, just N of Xenia)
        "03241500",  # [verified] Massies Creek at Wilberforce OH (the local tributary E of Xenia)
        "03242050",  # [verified] Little Miami River near Spring Valley OH (downstream, Greene/Warren)
    ],
    nasa_power_lat=39.6861,  # [verified] Xenia, OH city centroid (39deg41'10"N 83deg55'44"W)
    nasa_power_lon=-83.9289,
    rsei_fips="39057",  # [verified] Greene County, OH
    econ_fips="39057",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Greene Co [verified]
    parcels_url="TODO",  # [open] pending the Greene County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Xenia / Greene County zoning REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Xenia ~83.93 degW; zone 17 spans 84-78 degW)
    gis_parcel=None,  # [open] pending Greene County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Xenia / Greene County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "xenia-gis"}),
    design_lat=39.6861,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.9289,
    corridor_name="Little Miami buried-valley corridor",  # [inference] the Little Miami valley reach at Xenia
    dominant_hsg="B",  # [inference] Greene County buried-valley outwash (valley fill); footprint-dependent
    hsg_citation=(
        "Greene County is underlain by the Mad River / Little Miami buried-valley aquifer system "
        "- glacial outwash sand & gravel, a US-EPA sole-source aquifer the Xenia/Beavercreek well "
        "fields draw on [reference: ODNR/USGS] - so the valley fill is well-drained HSG A/B; but "
        "the inter-valley till uplands at Xenia proper are less permeable (HSG C/D), so the "
        "dominant class is footprint-dependent; [inference] pending an SSURGO area-weighted "
        "confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/xenia/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/xenia/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/xenia/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/xenia/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/xenia/baseline.yaml",
    rsei_relpath="reference/rsei/xenia/inventory.yaml",
    consumer_energy_relpath="reference/eia/xenia/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/xenia/demand-pressure.yaml",
    grid_relpath="reference/eia/xenia/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor (incl. the WPAFB plume overlay)
    plant_receiving={},  # [open] pending the Xenia-area WWTP NPDES fact sheet(s)
    abstraction_gage="03240000",  # [verified] Little Miami River near Oldtown OH
    supply_gage_primary="03240000",  # [verified] Little Miami River near Oldtown
    supply_gage_secondary="03241500",  # [verified] Massies Creek at Wilberforce (the local tributary)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum (scenic-river protection likely raises it)
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] the WPAFB-corridor defense/data-center dimension is the research target (#444)
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) is the IOU serving Greene County, OH — the Xenia LSE (Duke #3542 fringes the SW county; Village of Yellow Springs muni is separate). [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Greene County, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Greene County, OH",  # [verified]
)


# The DOWNSTREAM TERMINUS of the Mad River corridor (Urbana → Springfield → **Dayton/WPAFB**) and
# the richest node of the Miami expansion: the SW-Ohio analog to Lima's JSMC / tank-plant defense
# nexus. Wright-Patterson AFB (AFRL, the Air Force Rapid Sustainment Office, AFLCMC) is one of
# Ohio's largest single-site employers, and — unlike the bare greenfield Miami sites — **the corpus
# already carries this thread**: written testimony §8 "Ohio defense footprint" (Google Distributed
# Cloud air-gapped DoD IL5, RSO a named early customer, GDIT + Google Public Sector at Exercise
# Mobility Guardian 2025) + the `cloud-consumer-candidates.yaml` WPAFB-adjacent corridor entry. The
# distinctive data-center variant here is **regulated/air-gapped DoD cloud**, not hyperscale. Two
# overlays make it load-bearing: WPAFB runs its own production well-field on the **Great Miami /
# Mad River Buried Valley Aquifer** (US-EPA sole-source) and is the source of a documented **TCE /
# PFAS groundwater plume** on that same drinking-water aquifer. The buried-valley supply (not surface
# 7Q10 dilution) is the water story. GEOGRAPHY NOTES: the base STRADDLES Greene + Montgomery counties
# — the economic/toxics unit chosen here is **Montgomery County (Dayton metro, FIPS 39113)** (the
# well-field + defense-metro + plume context), distinct from the Greene-County (Xenia #444) economics
# on the Little Miami side; and at ~84.05 degW the base is WEST of the 84 degW meridian, so it is the
# network's first **UTM zone 16N** site (NOT the zone 17 the other Miami sites use).
_WPAFB = SiteProfile(
    slug="wpafb",
    basin="great-miami",  # [verified] Mad River → Great Miami River → Ohio River (HUC-8 05080001/2)
    nwis_sites=[
        "03270000",  # [verified] Mad River near Dayton OH (the at-base reach; corridor terminus)
        "03270500",  # [verified] Great Miami River at Dayton OH (metro mainstem / well-field reach)
        "03263000",  # [verified] Great Miami River at Taylorsville OH (upstream of the Mad confluence)
    ],
    nasa_power_lat=39.8261,  # [verified] Wright-Patterson AFB centroid (39deg49'34"N 84deg02'58"W)
    nasa_power_lon=-84.0494,
    rsei_fips="39113",  # [verified] Montgomery County, OH (Dayton metro; base straddles Greene+Montgomery)
    econ_fips="39113",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Greene+Montgomery Co [verified]
    parcels_url="TODO",  # [open] pending the Montgomery County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Dayton / Montgomery County zoning REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (WPAFB ~84.05 degW; zone 16 spans 90-84 degW) — NOT zone 17
    gis_parcel=None,  # [open] pending Montgomery County, OH parcel-layer discovery (+ the WPAFB federal enclave)
    gis_zoning=None,  # [open] pending City of Dayton / Montgomery County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "wpafb-gis"}),
    design_lat=39.8261,  # [verified] base centroid = NOAA Atlas-14 point
    design_lon=-84.0494,
    corridor_name="Great Miami / Mad River buried-valley corridor (Dayton terminus)",  # [inference]
    dominant_hsg="B",  # [inference] Great Miami / Mad River buried-valley outwash (well-drained valley fill)
    hsg_citation=(
        "Dayton / WPAFB sits on the Great Miami / Mad River Buried Valley Aquifer - glacial outwash "
        "sand & gravel, a US-EPA designated sole-source aquifer (the Dayton municipal + WPAFB "
        "production well fields draw on it) - so the valley fill is well-drained HSG A/B, the INVERSE "
        "of the Maumee lake-plain Black Swamp clays (HSG D); [inference] pending an SSURGO "
        "area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/wpafb/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/wpafb/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/wpafb/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/wpafb/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/wpafb/baseline.yaml",
    rsei_relpath="reference/rsei/wpafb/inventory.yaml",
    consumer_energy_relpath="reference/eia/wpafb/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/wpafb/demand-pressure.yaml",
    grid_relpath="reference/eia/wpafb/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending the identified corridor (the WPAFB TCE/PFAS plume + Dayton industrial reach)
    plant_receiving={
        "fairborn-wrc": (
            "Mad River",
            # NPDES OH0025062 (Fairborn Water Reclamation Center); design flow 6.0 MGD; outfall
            # at 39.8365 -84.0606, on the northern edge of WPAFB — the at-base Mad River reach
            # (USGS 03270000). Source: EPA ECHO CWA inventory, great-miami-wwtp.potw.yaml.
            "NPDES OH0025062 (Fairborn Water Reclamation Center); → Mad River; design flow "
            "6.0 MGD [connector — EPA ECHO CWA, great-miami-wwtp.potw.yaml]",
        ),
        "western-regional-wrf": (
            "Great Miami River",
            # NPDES OH0026638 (Montgomery Co. Western Regional WRF); design flow 20.0 MGD; the
            # metro-mainstem discharger on the well-field reach (Great Miami at Dayton, 03270500).
            # Source: EPA ECHO CWA inventory, great-miami-wwtp.potw.yaml.
            "NPDES OH0026638 (Western Regional WRF, Montgomery Co.); → Great Miami River; design "
            "flow 20.0 MGD [connector — EPA ECHO CWA, great-miami-wwtp.potw.yaml]",
        ),
    },  # [connector] Fairborn WRC (at-base Mad River) + Western Regional WRF (Great Miami); the
    # City of Dayton WRF (OH0024881, 72 MGD) and Tri-Cities North Regional WWA (OH0049646, 11.2
    # MGD) are the larger metro dischargers but ECHO returned no receiving_water — [open] pending
    # their OEPA permit fact sheets. Regulatory passby minimums also pending the fact sheets.
    abstraction_gage="03270000",  # [verified] Mad River near Dayton OH
    supply_gage_primary="03270000",  # [verified] Mad River near Dayton (the buried-valley supply reach)
    supply_gage_secondary="03270500",  # [verified] Great Miami River at Dayton (the well-field mainstem)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] the DoD-cloud / GDIT-RSO data-center dimension is the research target (#442)
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) serves both Greene and Montgomery counties, OH — the WPAFB-area LSE. [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Montgomery/Greene counties, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Montgomery County, OH",  # [verified] (Dayton metro; base straddles Greene+Montgomery)
    # [inference] Reader guard (#465): WPAFB straddles Greene + Montgomery; the econ unit here is
    # Montgomery (well-field/plume/Dayton-metro toxics context). The defense-supplier signature the
    # WPAFB thesis rests on is NOT in this unit — Montgomery Professional/Scientific/Technical
    # (NAICS 54) LQ 0.81, Information (NAICS 51) LQ 0.90, neither elevated. That concentration lives
    # in adjacent Greene County (NAICS 54 LQ 2.11), carried by the Xenia baseline (FIPS 39057, #444).
    econ_unit_note=(
        "Economic-unit caveat: Wright-Patterson AFB straddles Greene + Montgomery counties; this "
        "baseline is Montgomery County (39113) — the well-field / TCE-PFAS-plume / Dayton-metro "
        "toxics context. The defense-supplier Professional/Scientific/Technical concentration the "
        "WPAFB thesis rests on is NOT visible in this unit (Montgomery NAICS 54 LQ 0.81, NAICS 51 "
        "LQ 0.90 — neither elevated); it lives in adjacent Greene County (NAICS 54 LQ 2.11), "
        "covered by the Xenia baseline (Greene County, FIPS 39057). Do not read this single-county "
        "unit as 'no defense concentration.'"
    ),
)


# The LOWER Great Miami **heavy-industry** node and the I-75 Cincinnati-Dayton corridor's southern
# anchor, near the Great Miami's Ohio River confluence. This is the **established-industry comparator**
# to the speculative-greenfield Miami sites: **Cleveland-Cliffs Middletown Works** (the former AK Steel
# integrated mill) anchors a legacy steel/paper/chemicals corridor of large existing water users +
# NPDES dischargers on the Great Miami **mainstem** — so unlike the bare headwaters, the toxics/NPDES
# dimension here is REAL and rich. The water story shifts too: the lower Great Miami is a large
# mainstem (genuine dilution capacity), not a buried-valley headwater 7Q10 — though the buried-valley
# sole-source aquifer is wider here near the confluence. The grid story is distinctive: the City of
# Hamilton runs its own **municipal electric utility** (AMP member, home-rule — the EIA-861S short-form
# pattern), while Middletown is Duke Energy Ohio; both settle in PJM's **DEOK** (Duke Energy Ohio/
# Kentucky) zone — a third PJM zone for the network (after AEP and DAY). DISAMBIGUATION: the City of
# Hamilton is the seat of **Butler County (FIPS 39017)** — NOT Hamilton County, OH (which is
# Cincinnati). Both cities sit west of the 84 degW meridian, so this is a **UTM 16N** site (like WPAFB).
_HAMILTON_MIDDLETOWN = SiteProfile(
    slug="hamilton-middletown",
    basin="great-miami",  # [verified] lower Great Miami River → Ohio River (HUC-8 05080002)
    nwis_sites=[
        "03274000",  # [verified] Great Miami River at Hamilton OH (downstream reach; Hamilton well-field)
        "03272100",  # [verified] Great Miami River at Middletown OH (the Middletown Works reach)
    ],
    nasa_power_lat=39.3994,  # [verified] Hamilton, OH city centroid (39deg23'58"N 84deg33'41"W)
    nasa_power_lon=-84.5613,
    rsei_fips="39017",  # [verified] Butler County, OH (seat = City of Hamilton; NOT Hamilton County/Cincinnati)
    econ_fips="39017",
    eia861_utility_number=3542,  # Duke Energy Ohio (dominant Butler Co IOU, PJM DEOK) — EIA-861 2024 Service_Territory [verified]; Hamilton muni #7977 is the Hamilton-side split [inference]
    parcels_url="TODO",  # [open] pending the Butler County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Hamilton / Middletown GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Hamilton ~84.56 degW; zone 16 spans 90-84 degW) — NOT zone 17
    gis_parcel=None,  # [open] pending Butler County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Hamilton / Middletown zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(
        update={"reference_dir": "hamilton-middletown-gis"}
    ),
    design_lat=39.3994,  # [verified] Hamilton centroid = NOAA Atlas-14 point
    design_lon=-84.5613,
    corridor_name="Lower Great Miami industrial corridor",  # [inference] the Hamilton-Middletown mainstem reach
    dominant_hsg="B",  # [inference] lower Great Miami buried-valley outwash (wider near the Ohio confluence)
    hsg_citation=(
        "The lower Great Miami valley (Hamilton/Middletown, Butler County) sits on the Great Miami "
        "Buried Valley Aquifer - glacial outwash sand & gravel, a US-EPA designated sole-source "
        "aquifer, wider near the Ohio River confluence - so the valley fill is well-drained HSG A/B, "
        "the INVERSE of the Maumee lake-plain Black Swamp clays (HSG D); [inference] pending an "
        "SSURGO area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/hamilton-middletown/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/hamilton-middletown/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/hamilton-middletown/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/hamilton-middletown/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/hamilton-middletown/baseline.yaml",
    rsei_relpath="reference/rsei/hamilton-middletown/inventory.yaml",
    consumer_energy_relpath="reference/eia/hamilton-middletown/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/hamilton-middletown/demand-pressure.yaml",
    grid_relpath="reference/eia/hamilton-middletown/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending the identified corridor (the Middletown Works + Hamilton industrial reach)
    plant_receiving={},  # [open] pending the Hamilton/Middletown WWTP + industrial NPDES fact sheet(s)
    abstraction_gage="03274000",  # [verified] Great Miami River at Hamilton OH
    supply_gage_primary="03274000",  # [verified] Great Miami River at Hamilton
    supply_gage_secondary="03272100",  # [verified] Great Miami River at Middletown (the Works reach)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] the I-75-corridor data-center dimension is the research target (#443)
    serving_utility_citation="EIA-861 2024 Service_Territory: Butler County, OH is split — Duke Energy Ohio Inc (#3542, PJM DEOK) serves Middletown + most of the county; the City of Hamilton municipal (#7977) serves Hamilton. Pinned to Duke #3542 as the dominant IOU (the Middletown Works mainstem load); the Hamilton-muni share is [inference]. [verified]",
    lmp_usd_mwh=45.10,  # connector-sourced DEOK-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DEOK zone (pnode 124076095), 2025 day-ahead annual mean "
        "$45.10/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — Duke Energy Ohio (DEOK) "
        "territory, Butler County, OH; Hamilton muni on AMP (same DEOK wholesale zone) [verified]"
    ),
    lmp_pnode_id=124076095,  # [verified] PJM DEOK zone (Duke Energy Ohio)
    lmp_pnode_name="DEOK",
    county_name="Butler County, OH",  # [verified] (seat = City of Hamilton; NOT Hamilton County/Cincinnati)
)


# The UPPER Great Miami mainstem node (Miami County) — the I-75 corridor between the Great Miami
# headwaters (Indian Lake / Sidney) and Dayton, **upstream of WPAFB** — the upstream complement to
# the lower-mainstem Hamilton/Middletown node. Same buried-valley sole-source aquifer, but a mid-size
# **manufacturing** county (Hobart commercial food equipment HQ in Troy, auto parts) rather than
# Butler's heavy steel, and a second muni-power story: **Piqua runs its own municipal electric
# utility** (AMP member, Great Miami hydro), Troy/Miami County otherwise likely AES Ohio. The site
# also carries a distinct second supply water — the **Stillwater River** (gage 03265000). Both cities
# sit west of the 84 degW meridian, so this is a **UTM 16N** site (like WPAFB / Hamilton-Middletown).
_TROY_PIQUA = SiteProfile(
    slug="troy-piqua",
    basin="great-miami",  # [verified] upper Great Miami River → Ohio River (HUC-8 05080001)
    nwis_sites=[
        "03262700",  # [verified] Great Miami River at Troy OH (the Troy reach; county seat)
        "03262500",  # [verified] Great Miami River at Piqua OH (the upstream Piqua reach)
        "03265000",  # [verified] Stillwater River at Pleasant Hill OH (the second supply water)
    ],
    nasa_power_lat=40.0392,  # [verified] Troy, OH city centroid (40deg02'21"N 84deg12'12"W)
    nasa_power_lon=-84.2033,
    rsei_fips="39109",  # [verified] Miami County, OH
    econ_fips="39109",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio, county-dominant IOU) — EIA-861 2024 Service_Territory, Miami Co [verified]; City of Piqua muni #15095 is the Piqua split
    parcels_url="TODO",  # [open] pending the Miami County, OH GIS REST endpoint discovery
    zoning_url="TODO",  # [open] pending the City of Troy / Piqua GIS REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Troy ~84.20 degW; zone 16 spans 90-84 degW) — NOT zone 17
    gis_parcel=None,  # [open] pending Miami County, OH parcel-layer discovery
    gis_zoning=None,  # [open] pending City of Troy / Piqua zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "troy-piqua-gis"}),
    design_lat=40.0392,  # [verified] Troy centroid = NOAA Atlas-14 point
    design_lon=-84.2033,
    corridor_name="Upper Great Miami industrial corridor",  # [inference] the Troy-Piqua mainstem reach
    dominant_hsg="B",  # [inference] upper Great Miami buried-valley outwash (well-drained valley fill)
    hsg_citation=(
        "The upper Great Miami valley (Troy/Piqua, Miami County) sits on the Great Miami Buried "
        "Valley Aquifer - glacial outwash sand & gravel, a US-EPA designated sole-source aquifer "
        "the Troy/Piqua well fields draw on - so the valley fill is well-drained HSG A/B, the "
        "INVERSE of the Maumee lake-plain Black Swamp clays (HSG D); [inference] pending an SSURGO "
        "area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/troy-piqua/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/troy-piqua/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/troy-piqua/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/troy-piqua/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/troy-piqua/baseline.yaml",
    rsei_relpath="reference/rsei/troy-piqua/inventory.yaml",
    consumer_energy_relpath="reference/eia/troy-piqua/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/troy-piqua/demand-pressure.yaml",
    grid_relpath="reference/eia/troy-piqua/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending the identified corridor (the Troy/Piqua manufacturing reach)
    plant_receiving={},  # [open] pending the Troy/Piqua WWTP NPDES fact sheet(s)
    abstraction_gage="03262700",  # [verified] Great Miami River at Troy OH
    supply_gage_primary="03262700",  # [verified] Great Miami River at Troy
    supply_gage_secondary="03262500",  # [verified] Great Miami River at Piqua (the upstream reach)
    # [derived] LP3 7Q10 at USGS 03262700 (Great Miami River at Troy OH, 44 yr 1980-2024) —
    # conservative abstraction screen floor and the receiving-reach denominator for the Troy/Piqua
    # WWTP assimilative screen; regulatory passby minimum pending the OEPA NPDES fact sheet (#828).
    passby_primary_cfs=44.75,
    passby_secondary_cfs=0.0,  # [open] Great Miami at Piqua (03262500) daily record starts 2012 (<20 yr) — no derived 7Q10; passby pending
    facility=None,  # [open] the I-75-corridor data-center dimension is the research target (#475)
    serving_utility_citation="EIA-861 2024 Service_Territory: Miami County, OH is split — Dayton Power & Light (AES Ohio, #4922) serves Troy + most of the county; the City of Piqua municipal (#15095) serves Piqua. Pinned to DP&L #4922 (county-dominant IOU); the Piqua-muni share is [inference]. [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Miami County, OH; Piqua muni on AMP (same DAY wholesale zone) [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Miami County, OH",  # [verified]
)


# The UPPER-UPPER Great Miami node (Shelby County) — the next mainstem city UPSTREAM of Troy/Piqua
# (#475): headwaters (Indian Lake) -> Sidney -> Piqua -> Troy -> Dayton, on I-75. Same upper Great
# Miami buried-valley sole-source aquifer as Troy/Piqua (groundwater-dominated HSG A/B), and a
# compressor/refrigeration-manufacturing town (Emerson/Copeland HQ) — the upstream sibling of the
# Troy/Piqua manufacturing reach. Tracking -> onboarding (#481 / epic #440).
_SIDNEY = SiteProfile(
    slug="sidney",
    basin="great-miami",  # [verified] upper Great Miami River → Ohio River (HUC-8 05080001)
    nwis_sites=[
        "03261500",  # [verified] Great Miami River at Sidney OH (the at-site mainstem reach)
        "03262000",  # [verified] Loramie Creek at Lockington OH (the major local tributary; Lockington dam)
        "03261950",  # [verified] Loramie Creek near Newport OH (upstream Loramie tributary)
    ],
    nasa_power_lat=40.2842,  # [verified] Sidney, OH city centroid (40deg17'03"N 84deg09'21"W)
    nasa_power_lon=-84.1558,
    rsei_fips="39149",  # [verified] Shelby County, OH
    econ_fips="39149",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Shelby Co [verified] (not 'City of Shelby' #17043, a Richland-Co muni)
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels, scoped to County='Shelby' (39149)
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending City of Sidney zoning REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Sidney ~84.16 degW; zone 16 spans 90-84 degW) — NOT zone 17
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        # Shelby County OGRIP layer — owner-redacted public view. LocalParcelID format
        # pending a live sample verification; defaulting to dashless-12-digit (Hancock pattern).
        update={"reference_dir": "sidney-gis", "query_scope": "County='Shelby'"}
    ),
    gis_zoning=None,  # [open] pending City of Sidney zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "sidney-gis"}),
    design_lat=40.2842,  # [verified] Sidney centroid = NOAA Atlas-14 point
    design_lon=-84.1558,
    corridor_name="Upper Great Miami headwaters corridor",  # [inference] the Sidney mainstem reach (I-75)
    dominant_hsg="B",  # [inference] upper Great Miami buried-valley outwash (well-drained valley fill)
    hsg_citation=(
        "Sidney (Shelby County) sits on the upper Great Miami Buried Valley Aquifer - glacial "
        "outwash sand & gravel, a US-EPA designated sole-source aquifer the Sidney well field "
        "draws on - so the valley fill is well-drained HSG A/B, the INVERSE of the Maumee "
        "lake-plain Black Swamp clays (HSG D); [inference] pending an SSURGO area-weighted "
        "confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/sidney/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/sidney/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/sidney/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/sidney/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/sidney/baseline.yaml",
    rsei_relpath="reference/rsei/sidney/inventory.yaml",
    consumer_energy_relpath="reference/eia/sidney/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/sidney/demand-pressure.yaml",
    grid_relpath="reference/eia/sidney/grid-profile.yaml",
    # [inference] the Sidney manufacturing reach: Emerson Climate Technologies (1675 W Campbell Rd,
    # 40.280/-84.182) + Copeland Shelby Mfg (320 Adams St, 40.289/-84.152) + Copeland Condensing
    # Unit Div. (756 S Brooklyn Ave, 40.277/-84.148), the three Emerson Electric subsidiaries that
    # anchor Sidney's compressor/refrigeration complex. Box extends to cover the adjacent heavy-
    # industrial cluster (Thermoseal, American Trim, ITW Food Equipment, Reliable Castings,
    # Mechanical Galv-Plating, Ross Aluminum Castings, LEROI, Masland, NORCOLD, Stolle);
    # excludes Anna Engine Plant (~40.37) and GKN/Airstream (~40.44) in Anna/Jackson Center,
    # and Ross Aluminum Avon Div (~40.253) south of Sidney proper. (lat_min, lat_max, lon_min, lon_max)
    toxic_corridor_bbox=(40.268, 40.308, -84.210, -84.140),
    plant_receiving={
        "sidney-wwtp": (
            "Great Miami River",
            # ECHO NPDES OH0027421 (Sidney WWTP); outfall 001 → Great Miami River (HUC12 050800010703);
            # design 7.0 MGD, actual ~5.382 MGD (2023 DMR, 76.9% of design); CSO/bypass outfalls: 1;
            # no ECHO-flagged exceedances 2023. NPDES fact sheet pending for cited 7Q10 (#833).
            "ECHO NPDES OH0027421 (Sidney WWTP) → Great Miami River; design 7.0 MGD, "
            "actual ~4.01 MGD (2023 DMR, MO AVG mean) — data/extracted/sidney/wwtp-oh0027421.dmr.yaml [verified — ECHO]",
        ),
    },
    abstraction_gage="03261500",  # [verified] Great Miami River at Sidney OH
    supply_gage_primary="03261500",  # [verified] Great Miami River at Sidney
    supply_gage_secondary="03262000",  # [verified] Loramie Creek at Lockington (the major local tributary)
    # [derived] LP3 7Q10 at USGS 03261500 (Great Miami River at Sidney OH, 44 yr 1980-2024) —
    # conservative abstraction screen floor; regulatory passby minimum pending the OEPA NPDES
    # fact sheet for OH0027421 (Sidney WWTP) (#833).
    passby_primary_cfs=30.95,
    passby_secondary_cfs=0.0,  # [open] Loramie Creek derived 7Q10 = 3.55 cfs (03262000); passby pending
    facility=None,  # [open] the Sidney / I-75-corridor data-center dimension is the research target (#481)
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) is the IOU serving Shelby County, OH / Sidney — distinct from 'City of Shelby' (#17043, a Richland-County muni). [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Shelby County, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Shelby County, OH",  # [verified]
)


# The AGRICULTURAL / basin-edge node (Darke County, seat Greenville) — WEST of Miami County on the
# Indiana border, the most DIFFERENT Miami-basin candidate and a deliberate contrast to the
# industrial mainstem nodes. Darke straddles a drainage divide: eastern Darke (Greenville Creek ->
# Stillwater R. -> Great Miami -> Ohio R.) is the Great-Miami headwaters edge; western Darke drains
# to the Wabash (direct Mississippi). A till-plain county (NOT buried-valley) and one of Ohio's top
# agricultural counties — the data-center angle is greenfield farmland conversion, and the likely
# utility is a rural electric co-op (a third utility type for the network). Tracking -> onboarding
# (#482 / epic #440).
_GREENVILLE = SiteProfile(
    slug="greenville",
    basin="great-miami",  # [verified] eastern Darke: Greenville Creek → Stillwater R. → Great Miami → Ohio R.
    nwis_sites=[
        "03264000",  # [verified] Greenville Creek near Bradford OH (the at-site receiving-water reach)
        "03265000",  # [verified] Stillwater River at Pleasant Hill OH (downstream Stillwater context; Greenville Ck feeds it)
    ],
    nasa_power_lat=40.1023,  # [verified] Greenville, OH city centroid (40deg06'08"N 84deg37'59"W)
    nasa_power_lon=-84.6330,
    rsei_fips="39037",  # [verified] Darke County, OH
    econ_fips="39037",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — the City of Greenville distribution LSE [verified]; rural Darke is a Darke-REC-co-op / AEP / muni patchwork (#514 reconciled — same IOU-over-co-op convention as West Union)
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels, scoped to County='Darke' (39037) —
        # Darke County self-hosts no public parcel ArcGIS REST (the auditor's darkecountyrealestate.org
        # is a Cloudflare-fronted vendor SPA with no exposed service), so use the shared OGRIP view.
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending the City of Greenville / Darke County zoning REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Greenville ~84.63 degW; zone 16 spans 90-84 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        # Darke County OGRIP layer — owner-redacted public view (31,368 parcels). LocalParcelID is a
        # district-letter prefix + 17 digits (e.g. "L45021118000010600"), verified against a live
        # Greenville sample 2026-07-03 — hence the deed_id_regex override off the Hancock-12-digit base.
        # id_normalize="verbatim" (not the base "dashless"): dashless strips the leading letter and
        # breaks exact fetch_parcel lookups; the IDs carry no dashes, so verbatim preserves them.
        update={
            "reference_dir": "greenville-gis",
            "query_scope": "County='Darke'",
            "deed_id_regex": r"\b[A-Z]\d{17}\b",
            "id_normalize": "verbatim",
        }
    ),
    gis_zoning=None,  # [open] pending City of Greenville / Darke County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "greenville-gis"}),
    design_lat=40.1023,  # [verified] Greenville centroid = NOAA Atlas-14 point
    design_lon=-84.6330,
    corridor_name="Greenville Creek agricultural headwaters",  # [inference] the basin-edge / ag reach (not industrial)
    dominant_hsg="C",  # [inference] Darke till plain (ground moraine) — less-permeable uplands, NOT buried valley
    hsg_citation=(
        "Darke County is largely glaciated till plain (Wisconsinan ground moraine) - likely "
        "less-permeable HSG C/D uplands, with glacial outwash only in the Stillwater/Greenville "
        "Creek valleys - the till-plain CONTRAST to the Great Miami buried-valley aquifer at "
        "Troy/Piqua/Sidney; [inference] pending an SSURGO area-weighted confirmation (onboard "
        "SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 40.1023/-84.633
        1: 2.22,
        2: 2.66,
        5: 3.25,
        10: 3.74,
        25: 4.40,
        50: 4.92,
        100: 5.47,
        200: 6.04,
        500: 6.82,
        1000: 7.43,
    },
    parcels_relpath="reference/greenville/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/greenville/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/greenville/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/greenville/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/greenville/baseline.yaml",
    rsei_relpath="reference/rsei/greenville/inventory.yaml",
    consumer_energy_relpath="reference/eia/greenville/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/greenville/demand-pressure.yaml",
    grid_relpath="reference/eia/greenville/grid-profile.yaml",
    # [inference] Greenville urban-industrial corridor: the RSEI-dominant cluster is NOT
    # ag/food-processing (as expected going in) but a mixed manufacturing core —
    # BASF Corp (1175 Martin St, plastics/chemicals, RSEI #2 by score), Honeywell
    # (851 Jackson St, auto parts/formaldehyde, RSEI #1 historically 1988-2000), Greif
    # Packaging (526 Markwith Ave, steel drums), Corning Inc (1025 Martin St, glass),
    # Whirlpool KitchenAid (1701 KitchenAid Way, appliances), and the Jaysville-St Johns
    # Rd industrial park (Textron Cadillac Gage, Spartech, Greenville Technology Inc,
    # The Andersons Marathon Ethanol). Box covers the tight Greenville urban industrial
    # zone; excludes Union City Non-Ferrous (~17 mi NW), Norcold/Gettysburg (~10 mi E),
    # Production Paint Finishers/Bradford (~13 mi E), Florida Production Engineering/
    # New Madison (~8 mi S), and Midmark/Versailles (~15 mi N). (lat_min, lat_max,
    # lon_min, lon_max)
    toxic_corridor_bbox=(40.063, 40.140, -84.650, -84.578),
    # [verified] ECHO POTW record (FRS 110002345472, NPDES OH0025429): Greenville WWTP
    # → Greenville Creek, design flow 3.5 MGD. Fact sheet not yet in corpus; receiving
    # water and NPDES ID sourced from EPA ECHO great-miami-wwtp.potw.yaml.
    plant_receiving={
        "greenville-wwtp": (
            "Greenville Creek",
            "EPA ECHO POTW record, NPDES OH0025429 (Greenville WWTP, 3.5 MGD design flow)",
        ),
    },
    abstraction_gage="03264000",  # [verified] Greenville Creek near Bradford OH
    supply_gage_primary="03264000",  # [verified] Greenville Creek near Bradford
    supply_gage_secondary="03265000",  # [verified] Stillwater River at Pleasant Hill (downstream context)
    # [inference] LP3 7Q10 from USGS NWIS as conservative supply passby proxy (no abstraction
    # permit on record); regenerable via `watermark derive-low-flows`.
    # Greenville Creek near Bradford (03264000): 7Q10 = 11.34 cfs, 41 yr 1980-2024.
    # Stillwater at Pleasant Hill (03265000): 7Q10 = 15.69 cfs, 44 yr 1980-2024.
    passby_primary_cfs=11.34,
    passby_secondary_cfs=15.69,
    facility=None,  # [verified] zero Greenville/Darke-County data-center records in RSEI, ECHO NPDES,
    # and the onboarding self-research pass (#482/#515); the site angle is greenfield ag-land
    # conversion — no disclosed facility as of 2026-07-02.
    serving_utility_citation=(
        # #514 reconciliation: the issue's premise was that heavily-rural Darke County is likely
        # served by a co-op (Darke REC / Pioneer), so #4922 (an IOU) might be wrong. Resolved to
        # the IOU for the site as defined: AES Ohio (DP&L)'s published delivery-service territory
        # explicitly lists the City of Greenville (with Dayton/Springfield/Troy/Xenia/Piqua), and
        # Greenville has no municipal electric — so the city/industrial-core distribution LSE is
        # DP&L #4922. Darke Rural Electric Cooperative (#4796; HQ 1120 Fort Jefferson Ave, Greenville)
        # serves the RURAL remainder of Darke/Preble/Mercer (~5,000 meters), not the city core — being
        # HQ'd in the county seat ≠ serving it, and Ohio co-ops sit outside retail choice. EIA IDs
        # 4922 (DP&L) and 4796 (Darke REC) both cross-checked against OpenEI's EIA-861 records. Pinned
        # #4922 as the design-point (city + RSEI industrial corridor) distribution IOU, per the same
        # IOU-over-rural-co-op convention as West Union (#4796/#14006 are the fallbacks a rural-
        # greenfield facility would flip the pin to).
        "EIA-861 2024 Service_Territory: Darke County, OH is a patchwork — DP&L (AES Ohio) #4922, "
        "AEP #14006 on the east fringe, Darke Rural Electric co-op #4796 (rural Darke/Preble/Mercer), "
        "village munis Arcanum/Versailles. The City of Greenville LSE is Dayton Power & Light #4922: "
        "AES Ohio's delivery territory lists Greenville and the city has no municipal electric; Darke "
        "REC (HQ in Greenville) serves the rural remainder, not the city core. Pinned #4922 as the "
        "design-point distribution IOU; a rural-greenfield facility would flip the LSE to Darke REC "
        "#4796 or AEP #14006 (cf. West Union). EIA IDs 4922/4796 cross-checked against OpenEI. [verified]"
    ),
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — City of Greenville LSE "
        "is AES Ohio (DP&L) #4922, whose PJM transmission zone is DAY (Dayton). [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Darke County, OH",  # [verified] FIPS 39037
)


# The Little Miami's SECOND tracking point (with Xenia #444), east of the river in Clinton County —
# defined by a single dominant large-load tenant: the Wilmington Air Park (ILN), the former DHL /
# Airborne Express super-hub (the 2008 DHL pullout is a landmark company-town economic collapse),
# now an Amazon Air cargo hub + ATSG base. The "place shaped by one tenant" comparator and an
# Amazon footprint to set against the Lima Amazon data-center tenant. Receiving water is Todd Fork
# -> Little Miami (a National & State Scenic River, the same anti-degradation overlay as Xenia) — but
# Todd Fork is UNGAGED (the old 03244000 is discontinued; Clinton County has no active gage), so the
# nearest mainstem integrators bracket it. Tracking -> onboarding (#492 / epic #440).
_WILMINGTON = SiteProfile(
    slug="wilmington",
    basin="little-miami",  # [verified] Todd Fork → Little Miami River → Ohio River (HUC-8 05090202)
    nwis_sites=[
        "03245500",  # [verified] Little Miami River at Milford OH (downstream mainstem integrator, incl. Todd Fork)
        "03240000",  # [verified] Little Miami River near Oldtown OH (upstream Xenia reach — brackets Todd Fork above)
        "03242350",  # [verified] Caesar Creek near Wellman OH (a nearer Little Miami tributary; reservoir-regulated)
    ],
    nasa_power_lat=39.4453,  # [verified] Wilmington, OH city centroid (39deg26'43"N 83deg49'43"W)
    nasa_power_lon=-83.8285,
    rsei_fips="39027",  # [verified] Clinton County, OH
    econ_fips="39027",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Clinton Co [verified]
    parcels_url=(  # [reference] Clinton County has no confirmed county-hosted parcel REST;
        # substitute = the OGRIP Ohio statewide parcels public view, scoped to County='Clinton'
        # (Ohio-only layer → situs-safe; 26,962 Clinton parcels, ~99% with SitusAddressAll +
        # StateLUC + geometry, e.g. "1475 TODDS FORK RD" — verified 2026-07-03). [verified — situs]
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending the City of Wilmington / Clinton County zoning REST endpoint discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Wilmington ~83.83 degW; zone 17 spans 84-78 degW) — east of 84 degW
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "wilmington-gis", "query_scope": "County='Clinton'"}
    ),  # [reference] OGRIP scoped to Clinton (situs-verified 2026-07-03; LandArea sparse but present)
    gis_zoning=None,  # [open] pending City of Wilmington / Clinton County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "wilmington-gis"}),
    design_lat=39.4453,  # [verified] Wilmington centroid = NOAA Atlas-14 point
    design_lon=-83.8285,
    corridor_name="Wilmington Air Park (single-tenant) corridor",  # [reference] ILN — Amazon Air / ATSG cargo hub
    dominant_hsg="C",  # [inference] Clinton County glaciated till plain — less-permeable HSG C/D uplands (cf. Xenia uplands)
    hsg_citation=(
        "Clinton County is glaciated till plain - likely less-permeable HSG C/D uplands (cf. the "
        "Xenia inter-valley till uplands), NOT the buried-valley outwash of the Mad River / Great "
        "Miami sites; [inference] pending an SSURGO area-weighted confirmation (onboard SSURGO "
        "needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/wilmington/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/wilmington/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/wilmington/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/wilmington/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/wilmington/baseline.yaml",
    rsei_relpath="reference/rsei/wilmington/inventory.yaml",
    consumer_energy_relpath="reference/eia/wilmington/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/wilmington/demand-pressure.yaml",
    grid_relpath="reference/eia/wilmington/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending the corridor (the Air Park reach)
    plant_receiving={
        "wilmington-wwtp": (
            "Lytle Creek",
            # NPDES OH0028134 / Ohio EPA 1PD00013*QD (City of Wilmington WWTP); outfall 001 at
            # Lytle Creek RM 6.83, 475 S Nelson Ave, Wilmington OH; current design flow 3.0 MGD;
            # PTI #1543170 expansion to 4.5 MGD (new limits effective 2026-03-01).
            # Source: Ohio EPA NPDES fact sheet 1PD00013.fs (2023-05-19) [verified].
            "NPDES OH0028134/1PD00013*QD (City of Wilmington WWTP); outfall 001 → Lytle Creek "
            "RM 6.83; design flow 3.0 MGD (expanding to 4.5 MGD per PTI #1543170) [verified — "
            "Ohio EPA NPDES fact sheet 1PD00013.fs, 2023-05-19]",
        ),
    },
    abstraction_gage="03245500",  # [open] Lytle Creek / Todd Fork ungaged — Little Miami at Milford is the nearest downstream integrator (overstates at-site dilution)
    supply_gage_primary="03245500",  # [verified] Little Miami River at Milford (downstream integrator)
    supply_gage_secondary="03240000",  # [verified] Little Miami River near Oldtown (upstream reach; brackets Todd Fork)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum (scenic-river protection likely raises it)
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] the Air Park large-load / data-center dimension is the research target (#492)
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) is the IOU serving Clinton County, OH — the Wilmington / Air Park LSE (Duke #3542 + South Central Power co-op also in-county). [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Clinton County, OH [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Clinton County, OH",  # [verified] FIPS 39027
)


# The network's THIRD-basin branch and the data-center EPICENTER (Scioto epic #484, onboarding
# #485): New Albany / Licking County, OH — Intel "Ohio One" fab + Google/Meta/AWS/Microsoft/QTS in
# the New Albany International Business Park. It STRADDLES the Scioto↔Muskingum divide: the city
# core (Franklin Co) drains Rocky Fork + Blacklick → Big Walnut Creek → Scioto (HUC 05060001); the
# Intel/business-park epicenter (Licking Co, Jersey Twp) drains the South Fork Licking → Licking →
# Muskingum (HUC 05040006). The DC footprint is [verified] on the Beech Rd / Licking / Muskingum
# side (#485 register); `basin="scioto"` holds for the SOURCE-WATER screen — the cluster's cooling
# draw is on the City of Columbus / Scioto system (Intel ~5 MGD, its effluent routed to Columbus'
# Scioto-discharging WWTPs) — while surface drainage is Muskingum (no S. Fork Licking 7Q10 yet,
# [open]). Grid is PINNED: AEP Ohio (Ohio Power #14006), PJM AEP zone — back to the Maumee sites'
# zone, unlike the Miami branch's DAY/DEOK.
_NEW_ALBANY = SiteProfile(
    slug="new-albany",
    # [verified] Big Walnut Creek → Scioto → Ohio River (HUC-8 05060001); [open] the Intel/Licking
    # epicenter drains S. Fork Licking → Muskingum (05040006) — flip if the footprint lands Licking.
    basin="scioto",
    nwis_sites=[
        "03228500",  # [verified] Big Walnut Creek at Central College OH (at-site Scioto-side reach; DV since 1938)
        "03229500",  # [verified] Big Walnut Creek at Rees OH (downstream Big Walnut→Scioto integrator; DV since 1921)
        "03145000",  # [verified] South Fork Licking River near Hebron OH (the Muskingum-side Intel/Licking drainage; DV since 1939)
    ],
    nasa_power_lat=40.09,  # [verified] New Albany city centroid (Census Gazetteer 2024 place 3953970)
    nasa_power_lon=-82.7763,
    rsei_fips="39089",  # [verified] Licking County, OH — the Intel/business-park epicenter (city core is Franklin 39049)
    econ_fips="39089",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio); serves New Albany + the business park — PJM AEP zone
    parcels_url=(  # [reference] Licking County's own ArcGIS parcel/zoning REST is currently stopped (HTTP 500);
        # substitute = the OGRIP Ohio statewide parcels public view, scoped to County='Licking'
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] Licking Planning/Zoning REST is stopped; no confirmed New Albany / Jersey Twp zoning REST
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (New Albany ~82.78 degW; zone 17 spans 84-78 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "new-albany-gis", "query_scope": "County='Licking'"}
    ),  # [reference] OGRIP scoped to Licking (operative-for-DC); SitusAddressAll is null for Licking (thin catalog)
    gis_zoning=None,  # [open] pending a New Albany / Licking zoning-layer discovery (Licking REST stopped)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "new-albany-gis"}),
    design_lat=40.09,  # [verified] New Albany centroid = NOAA Atlas-14 point
    design_lon=-82.7763,
    corridor_name="Rocky Fork-Blacklick / Big Walnut corridor",  # [inference] the Scioto-side New Albany reach
    dominant_hsg="C",  # [inference] central-Ohio glaciated till plain (Big Walnut headwaters), moderately-to-poorly drained
    hsg_citation=(
        "New Albany / Licking County sits on the central-Ohio glaciated till plain (Big Walnut / "
        "Rocky Fork headwaters), not a buried-valley outwash aquifer - so the soils are the "
        "moderately-to-poorly-drained till HSG C/D, unlike the Miami branch's well-drained HSG B "
        "buried valleys; [inference] pending an SSURGO area-weighted confirmation (onboard SSURGO "
        "needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/new-albany/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/new-albany/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/new-albany/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/new-albany/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/new-albany/baseline.yaml",
    rsei_relpath="reference/rsei/new-albany/inventory.yaml",
    consumer_energy_relpath="reference/eia/new-albany/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/new-albany/demand-pressure.yaml",
    grid_relpath="reference/eia/new-albany/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending the corridor (the New Albany business-park reach)
    # [verified] Scioto-side (Rocky Fork+Blacklick→Big Walnut→Scioto); [open] the Intel/Licking side
    # discharges S. Fork Licking→Muskingum, and Intel's PROCESS wastewater goes to Columbus' sewer.
    plant_receiving={},  # [open] pending the New Albany-area WWTP NPDES fact sheet(s)
    abstraction_gage="03228500",  # [verified] Big Walnut Creek at Central College OH (Scioto-side at-site reach)
    supply_gage_primary="03228500",  # [verified] Big Walnut Creek at Central College
    supply_gage_secondary="03229500",  # [verified] Big Walnut Creek at Rees (the larger downstream reach)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] data-center dimension = Intel "Ohio One" + Google/Meta/AWS/Microsoft/QTS (#485); pending a pinned facility
    serving_utility_citation=(
        "EIA-861 service territory (Ohio Power Co #14006) + PJM AEP zone; AEP Ohio serves New "
        "Albany / the New Albany International Business Park. [verified] No municipal electric utility."
    ),
    lmp_usd_mwh=45.81,  # [reference] connector-sourced AEP-zone day-ahead annual mean (same PJM AEP zone as Lima, #121)
    lmp_citation=(
        "PJM AEP-zone day-ahead annual-mean LMP applied to New Albany (AEP Ohio territory, PJM AEP "
        "zone — the same zone as the Maumee sites); [reference] connector-sourced (#121)"
    ),
    lmp_pnode_id=8445784,  # [verified] PJM AEP zone (same pnode as Lima)
    lmp_pnode_name="AEP",
    county_name="Licking County, OH",  # [verified] (city core spans Franklin Co 39049; DC cluster = Licking 39089)
)


# The Scioto mainstem METRO CORE (Scioto epic #484, onboarding #486): Columbus / Franklin County —
# the largest municipal water user in the basin and AEP's HQ city. Receiving water = the Scioto
# River (the Olentangy joins downtown); supply is a MANAGED metro system (the O'Shaughnessy / Hoover
# / Griggs upground reservoirs + well fields), not a sole-source headwater. Sink = Ohio R. at
# Portsmouth. Grid is PINNED: AEP Ohio (Ohio Power #14006), PJM AEP zone (AEP HQ is Columbus).
_COLUMBUS = SiteProfile(
    slug="columbus",
    basin="scioto",  # [verified] Scioto River mainstem → Ohio River (HUC-8 05060001)
    nwis_sites=[
        "03227500",  # [verified] Scioto River at Columbus OH (at-site mainstem/abstraction reach; DV since 1920)
        "03226800",  # [verified] Olentangy River near Worthington OH (Olentangy supply reach; 03227000 at Columbus has no discharge record)
    ],
    nasa_power_lat=39.9859,  # [verified] Columbus, OH city centroid (Census TIGER place 3918000)
    nasa_power_lon=-82.9856,
    rsei_fips="39049",  # [verified] Franklin County, OH
    econ_fips="39049",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio HQ Columbus); PJM AEP zone
    parcels_url=(  # [reference] substitute = the OGRIP Ohio statewide parcels public view, scoped to County='Franklin'
        # (the Franklin County Auditor also hosts a fuller native owner+CAMA layer — a follow-up upgrade)
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url=(  # [verified] City of Columbus "All Base Zoning" (polygon-only district catalog; city limits only)
        "https://maps2.columbus.gov/arcgis/rest/services/Applications/Zoning/MapServer/31"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Columbus ~82.99 degW; zone 17 spans 84-78 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "columbus-gis", "query_scope": "County='Franklin'"}
    ),  # [reference] OGRIP scoped to Franklin; the Franklin County Auditor native owner+CAMA layer is a follow-up upgrade
    gis_zoning=None,  # [open] City of Columbus zoning is polygon-only (district catalog, city limits); schema-wiring deferred
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "columbus-gis"}),
    design_lat=39.9859,  # [verified] Columbus centroid = NOAA Atlas-14 point
    design_lon=-82.9856,
    corridor_name="Scioto-Olentangy metro corridor",  # [inference] the downtown Scioto mainstem reach
    dominant_hsg="C",  # [inference] central-Ohio glaciated till plain (Scioto valley), moderately-to-poorly drained
    hsg_citation=(
        "Columbus / Franklin County sits in the central-Ohio Scioto valley on glaciated till + "
        "valley-fill alluvium - a managed metro supply (the O'Shaughnessy/Hoover/Griggs upground "
        "reservoirs + well fields), not a sole-source buried-valley aquifer - so the uplands are "
        "moderately-to-poorly-drained till HSG C/D; [inference] pending an SSURGO area-weighted "
        "confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/columbus/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/columbus/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/columbus/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/columbus/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/columbus/baseline.yaml",
    rsei_relpath="reference/rsei/columbus/inventory.yaml",
    consumer_energy_relpath="reference/eia/columbus/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/columbus/demand-pressure.yaml",
    grid_relpath="reference/eia/columbus/grid-profile.yaml",
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending the corridor (the Columbus metro industrial reach)
    plant_receiving={},  # [open] pending the Columbus WWTP NPDES fact sheet(s) (Jackson Pike / Southerly)
    abstraction_gage="03227500",  # [verified] Scioto River at Columbus OH
    supply_gage_primary="03227500",  # [verified] Scioto River at Columbus
    supply_gage_secondary="03226800",  # [verified] Olentangy River near Worthington
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] data-center dimension = the Columbus-metro cluster + AEP tariff exposure (#486); pending a pinned facility
    serving_utility_citation=(
        "EIA-861 service territory (Ohio Power Co #14006, AEP HQ Columbus) + PJM AEP zone. [verified]"
    ),
    lmp_usd_mwh=45.81,  # [reference] connector-sourced AEP-zone day-ahead annual mean (same PJM AEP zone as Lima, #121)
    lmp_citation=(
        "PJM AEP-zone day-ahead annual-mean LMP applied to Columbus (AEP Ohio HQ, PJM AEP zone); "
        "[reference] connector-sourced (#121)"
    ),
    lmp_pnode_id=8445784,  # [verified] PJM AEP zone (same pnode as Lima)
    lmp_pnode_name="AEP",
    county_name="Franklin County, OH",  # [verified]
)


# The Muskingum basin's confluence city (epic #495, onboarding 2026-07-02): Coshocton /
# Coshocton County — where the Tuscarawas + Walhonding join to form the Muskingum. Data-center
# driver = Aligned Data Centers' Conesville mega-scale AI campus (~197 ac at the former AEP
# Conesville coal plant, groundbreaking Oct 11 2025, initial capacity mid-2026). Grid is PINNED:
# AEP Ohio (Ohio Power #14006, PJM AEP zone) — the Conesville Industrial Park is fed by on-site
# 138/345-kV AEP substations; Frontier Power co-op serves the surrounding rural territory, not the
# park load. No committed Muskingum POTW inventory yet → the basin screen degrades to empty (the
# documented behavior in hydrology/basin.py), never borrowing another basin's dischargers.
_COSHOCTON = SiteProfile(
    slug="coshocton",
    basin="muskingum",  # [verified] Tuscarawas + Walhonding → Muskingum River → Ohio River (subregion 0504)
    nwis_sites=[
        "03129000",  # [verified] Tuscarawas River at Newcomerstown OH (upstream confluence input; DA 2,443 mi²)
        "03138500",  # [verified] Walhonding River below Mohawk Dam at Nellie OH (Walhonding confluence input; DA 1,505 mi²)
        "03150000",  # [verified] Muskingum River at McConnelsville OH (downstream mainstem; DA 7,422 mi²)
    ],
    nasa_power_lat=40.272,  # [verified] City of Coshocton centroid
    nasa_power_lon=-81.860,
    rsei_fips="39031",  # [verified] Coshocton County, OH
    econ_fips="39031",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio); the Conesville Industrial Park/DC load is AEP (138/345-kV substations), not the Frontier Power rural co-op
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels public view, scoped to County='Coshocton'
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending a Coshocton County / City of Coshocton zoning REST discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Coshocton ~81.86 degW; zone 17 spans 84-78 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "coshocton-gis", "query_scope": "County='Coshocton'"}
    ),  # [reference] OGRIP scoped to Coshocton
    gis_zoning=None,  # [open] pending a Coshocton zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "coshocton-gis"}),
    design_lat=40.272,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-81.860,
    corridor_name="Tuscarawas-Walhonding-Muskingum confluence corridor",  # [inference]
    dominant_hsg="C",  # [inference] Muskingum valley: valley-fill alluvium over unglaciated-plateau till/bedrock
    hsg_citation=(
        "Coshocton sits at the Tuscarawas/Walhonding confluence in the unglaciated Allegheny "
        "Plateau's Muskingum valley — valley-fill alluvium in the floodplain over till/bedrock "
        "uplands; [inference] pending an SSURGO area-weighted confirmation (onboard SSURGO needs "
        "a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/coshocton/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/coshocton/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/coshocton/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/coshocton/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/coshocton/baseline.yaml",
    rsei_relpath="reference/rsei/coshocton/inventory.yaml",
    consumer_energy_relpath="reference/eia/coshocton/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/coshocton/demand-pressure.yaml",
    grid_relpath="reference/eia/coshocton/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor
    plant_receiving={},  # [open] pending the Coshocton WWTP NPDES fact sheet (4.4 MGD → Muskingum River)
    abstraction_gage="03150000",  # [inference] Muskingum at McConnelsville (downstream mainstem; no discharge gage at Coshocton)
    supply_gage_primary="03129000",  # [verified] Tuscarawas at Newcomerstown (confluence input)
    supply_gage_secondary="03138500",  # [verified] Walhonding below Mohawk Dam at Nellie (confluence input)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] data-center dimension = Aligned Conesville AI campus (#495); pending a pinned facility
    serving_utility_citation=(
        "AEP Ohio (Ohio Power Co #14006, PJM AEP zone) — the Conesville Industrial Park is fed by "
        "on-site 138/345-kV AEP substations per the park utility page; Frontier Power Company co-op "
        "serves the surrounding rural territory, not the park / data-center load. [verified]"
    ),
    lmp_usd_mwh=45.81,  # [reference] connector-sourced AEP-zone day-ahead annual mean (same PJM AEP zone as Lima)
    lmp_citation=(
        "PJM AEP-zone day-ahead annual-mean LMP applied to Coshocton (AEP Ohio, PJM AEP zone); "
        "[reference] connector-sourced (#121)"
    ),
    lmp_pnode_id=8445784,  # [verified] PJM AEP zone (same pnode as Lima)
    lmp_pnode_name="AEP",
    county_name="Coshocton County, OH",  # [verified]
)


# The Scioto basin's southern anchor (onboarding 2026-07-02): Piketon / Pike County — the former
# Portsmouth Gaseous Diffusion Plant (a DOE reservation). Data-center driver = SB Energy's PORTS
# Technology Campus (operating entity New Day Data Centers LLC): a 10 GW data-center load with
# ~9.2 GW of on-site natural-gas generation, groundbreaking March 20 2026 — the largest single
# data-center project announced in the U.S. Grid interconnect = AEP Ohio (Ohio Power #14006, PJM
# AEP zone; $4.2B in AEP 765-kV upgrades, SB-Energy-funded). South Central Power co-op serves the
# surrounding rural territory, not the campus interconnect. Water is officially undisclosed — the
# Scioto is the likely receiving water but is [open] pending a permit, not asserted here.
_PIKETON = SiteProfile(
    slug="piketon",
    basin="scioto",  # [verified] Scioto River mainstem → Ohio River (subregion 0506)
    nwis_sites=[
        "03237020",  # [verified] Scioto River at Piketon OH (at-site reach; DA 5,836 mi²; DV since 2001)
        "03234500",  # [verified] Scioto River at Higby OH (upstream long-record mainstem; DA 5,131 mi²; DV since 1930)
    ],
    nasa_power_lat=39.068,  # [verified] Piketon village centroid
    nasa_power_lon=-83.014,
    rsei_fips="39131",  # [verified] Pike County, OH
    econ_fips="39131",
    eia861_utility_number=14006,  # [verified] Ohio Power Co (AEP Ohio); the PORTS interconnect is AEP (765-kV), not the South Central Power rural co-op
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels public view, scoped to County='Pike'
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending a Pike County / Scioto Township zoning REST discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Piketon ~83.01 degW; zone 17 spans 84-78 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "piketon-gis", "query_scope": "County='Pike'"}
    ),  # [reference] OGRIP scoped to Pike
    gis_zoning=None,  # [open] pending a Pike County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "piketon-gis"}),
    design_lat=39.068,  # [verified] village centroid = NOAA Atlas-14 point
    design_lon=-83.014,
    corridor_name="Scioto River (Piketon) corridor",  # [inference] the at-site Scioto reach
    dominant_hsg="C",  # [inference] Scioto valley-fill alluvium over unglaciated-plateau uplands
    hsg_citation=(
        "Piketon sits in the Scioto River valley at the edge of the unglaciated Allegheny Plateau "
        "— valley-fill alluvium/terrace in the floodplain over till/bedrock uplands; [inference] "
        "pending an SSURGO area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/piketon/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/piketon/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/piketon/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/piketon/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/piketon/baseline.yaml",
    rsei_relpath="reference/rsei/piketon/inventory.yaml",
    consumer_energy_relpath="reference/eia/piketon/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/piketon/demand-pressure.yaml",
    grid_relpath="reference/eia/piketon/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor
    plant_receiving={},  # [open] the PORTS water/wastewater plan is officially undisclosed (no NPDES issued)
    abstraction_gage="03237020",  # [verified] Scioto River at Piketon (at-site reach)
    supply_gage_primary="03237020",  # [verified] Scioto River at Piketon
    supply_gage_secondary="03234500",  # [verified] Scioto River at Higby (upstream long-record)
    passby_primary_cfs=0.0,  # [open] pending the in-stream passby minimum
    passby_secondary_cfs=0.0,  # [open]
    facility=None,  # [open] data-center dimension = SB Energy PORTS Technology Campus; pending a pinned facility
    serving_utility_citation=(
        "AEP Ohio (Ohio Power Co #14006, PJM AEP zone) — the PORTS Technology Campus interconnect is "
        "AEP Ohio ($4.2B in 765-kV transmission upgrades, SB-Energy-funded); South Central Power "
        "Company co-op serves the surrounding rural Pike County territory, not the campus. [verified]"
    ),
    lmp_usd_mwh=45.81,  # [reference] connector-sourced AEP-zone day-ahead annual mean (same PJM AEP zone as Lima)
    lmp_citation=(
        "PJM AEP-zone day-ahead annual-mean LMP applied to Piketon (AEP Ohio, PJM AEP zone); "
        "[reference] connector-sourced (#121)"
    ),
    lmp_pnode_id=8445784,  # [verified] PJM AEP zone (same pnode as Lima)
    lmp_pnode_name="AEP",
    county_name="Pike County, OH",  # [verified]
)


# The Sandusky/Lake-Erie shoreline point (onboarding 2026-07-02): Sandusky / Erie County — a
# DIRECT-to-Lake-Erie site, NOT the Sandusky River mainstem. Data-center driver = Aligned Data
# Centers' NEO-01 campus (Perkins Township, 2509 Hayes Ave, ~129 ac brownfield of the former
# KBI/GM bearing plant; groundbreaking May 2024; first building 96 MW, campus >200 MW). Basin
# nuance: the Aligned parcel + the Sandusky WWTP discharge to Sandusky Bay → Lake Erie; the local
# creeks (Pipe/Mills) are coded HUC 04100011 "Sandusky River & Sandusky Bay Tributaries" while the
# adjacent direct-Lake-Erie tributaries are 04100012 (Huron-Vermilion). Registered under the
# network's `sandusky` branch (the Sandusky Bay estuary system), receiving water = Sandusky Bay,
# NOT the Sandusky River — do not screen against a Sandusky-River 7Q10. Grid = FirstEnergy / PJM
# ATSI (Ohio Edison #13998; Toledo Edison #18997 is the alternative — parcel-specific confirmation
# is [open]). No committed Sandusky POTW inventory yet → basin screen degrades to empty.
_SANDUSKY = SiteProfile(
    slug="sandusky",
    basin="sandusky",  # [verified as Sandusky-Bay estuary system] direct to Sandusky Bay → Lake Erie; NOT the Sandusky River mainstem (see note above)
    nwis_sites=[
        "04199000",  # [reference] Huron River at Milan OH (nearest active discharge gage; DA 371 mi²) — Pipe/Mills Creek have no USGS flow gage
        "04199155",  # [reference] Old Woman Creek at Berlin Rd near Huron OH (nearest small-watershed gage; DA 22.1 mi²)
    ],
    nasa_power_lat=41.4489,  # [verified] City of Sandusky centroid (the Aligned parcel is in Perkins Twp just south, ~41.42/-82.71)
    nasa_power_lon=-82.7080,
    rsei_fips="39043",  # [verified] Erie County, OH
    econ_fips="39043",
    eia861_utility_number=13998,  # [inference] Ohio Edison Co (FirstEnergy, PJM ATSI) — City of Sandusky aggregation points to Ohio Edison; Toledo Edison #18997 is the alternative; parcel-specific confirmation [open]
    parcels_url=(  # [reference] OGRIP Ohio statewide parcels public view, scoped to County='Erie'
        "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
        "OhioStatewidePacels_full_view/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] pending a Perkins Township / City of Sandusky zoning REST discovery
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Sandusky ~82.71 degW; zone 17 spans 84-78 degW)
    gis_parcel=OHIO_STATEWIDE_PARCEL_SCHEMA.model_copy(
        update={"reference_dir": "sandusky-gis", "query_scope": "County='Erie'"}
    ),  # [reference] OGRIP scoped to Erie
    gis_zoning=None,  # [open] pending a Perkins Twp / Sandusky zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "sandusky-gis"}),
    design_lat=41.4489,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-82.7080,
    corridor_name="Sandusky Bay / Lake Erie shoreline corridor",  # [inference] the direct-to-bay reach
    dominant_hsg="C",  # [inference] Lake Erie lake-plain clays/silts near the shoreline
    hsg_citation=(
        "Sandusky / Perkins Township sits on the Lake Erie lake plain near Sandusky Bay — poorly-"
        "drained lacustrine clays/silts (HSG C/D) typical of the shoreline; [inference] pending an "
        "SSURGO area-weighted confirmation (onboard SSURGO needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/sandusky/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/sandusky/bosc-site-footprint.yaml",  # [open] pending an identified site
    climatology_relpath="reference/hydrology/sandusky/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/sandusky/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/sandusky/baseline.yaml",
    rsei_relpath="reference/rsei/sandusky/inventory.yaml",
    consumer_energy_relpath="reference/eia/sandusky/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/sandusky/demand-pressure.yaml",
    grid_relpath="reference/eia/sandusky/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor
    plant_receiving={},  # [open] the Aligned site water/wastewater plan is undisclosed; Sandusky WWTP (3.8 MGD) → Sandusky Bay/Lake Erie
    abstraction_gage="04199000",  # [reference] Huron River at Milan (nearest active discharge gage; no gage on the site's own creeks)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    facility=None,  # [open] data-center dimension = Aligned NEO-01 campus; pending a pinned facility
    serving_utility_citation=(
        "FirstEnergy / PJM ATSI zone — City of Sandusky aggregation materials point to Ohio Edison "
        "Co (#13998) as the distribution utility; The Toledo Edison Co (#18997) also serves parts of "
        "Erie County. The utility serving the Aligned parcel specifically is [open] pending the "
        "interconnection/PUCO filing. [inference]"
    ),
    lmp_usd_mwh=45.84,  # [reference] connector-sourced PJM ATSI-zone day-ahead annual mean (committed ATSI fixture)
    lmp_citation=(
        "PJM ATSI-zone day-ahead annual-mean LMP applied to Sandusky (FirstEnergy/Ohio Edison, PJM "
        "ATSI zone); [reference] connector-sourced (#121)"
    ),
    lmp_pnode_id=116013753,  # [verified] PJM ATSI zone
    lmp_pnode_name="ATSI",
    county_name="Erie County, OH",  # [verified]
)


# The network's first **Ohio River (direct)** node — West Union, Adams County, OHIO (#1117). Where
# every prior site drains to Lake Erie (Maumee/Sandusky/Cuyahoga) or the Ohio via a glaciated Miami/
# Scioto loop, Adams County is **far-southern, unglaciated Appalachian** (Western Allegheny Plateau,
# MLRA 124): no buried-valley aquifer, no till plain — Ohio Brush Creek drains straight to the Ohio
# River. A *coming-soon* point; geography/hydrology/grid are sourced + cited below, and the data-
# center dimension + the facility-specific model inputs (covers, footprint, refill passby minimums)
# stay `[open]` until an actual development site is identified (Adams County discovery is the "boom"
# research target, `--research` + corpus follow-up). NB: the ADAMS COUNTY NPDES rows in the Maumee
# reference data are Adams County **Indiana** (St. Marys headwaters) — a different place; this site
# has no existing data feeding it.
_WEST_UNION = SiteProfile(
    slug="west-union",
    basin="ohio-brush-creek",  # [verified] Ohio Brush Creek → Ohio River; HUC-8 05090201 "Ohio Brush-Whiteoak"
    # config knobs
    nwis_sites=[
        "03237500",  # [verified] Ohio Brush Creek near West Union OH — DA 387 mi², daily discharge since 1926;
        # the only substantive active gage on the creek (the West Fork gages are trivial/short-record)
    ],
    nasa_power_lat=38.7945,  # [reference] West Union village centroid (Adams Co seat; GNIS 1074014, Census place)
    nasa_power_lon=-83.5452,
    rsei_fips="39001",  # [verified] Adams County, OH (state 39 / county 001)
    econ_fips="39001",
    # [reference] grid backdrop = AEP Ohio (Ohio Power Co #14006) — the AEP transmission + PJM-settlement
    # provider for Adams County, and the LSE on the village edge. The DOMINANT rural-county retail LSE is
    # **Adams Rural Electric Cooperative** (EIA ~118, ~9,274 meters; a Buckeye Power member) — see
    # serving_utility_citation; confirming the co-op's EIA-861 id against the primary file is a follow-up.
    eia861_utility_number=14006,
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning pending the raw
    # ArcGIS REST endpoint behind the Adams County OH GIS hub (acgis-adamso.hub.arcgis.com, an ArcGIS
    # Online hosted item — no on-prem MapServer directory surfaced yet).
    parcels_url="TODO",  # [open] pending the Adams County OH parcel FeatureServer/MapServer REST endpoint
    zoning_url="TODO",  # [open] pending an Adams County OH / Village of West Union zoning REST endpoint
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=None,  # [open] pending Adams County OH parcel-layer discovery
    gis_zoning=None,  # [open] pending Village of West Union / Adams County zoning-layer discovery
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "west-union-gis"}),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (West Union ~83.54 degW; zone 17 spans 84-78 degW)
    # stormwater (the Atlas-14 corridor point = village centroid; cover scenario pending a site)
    design_lat=38.7945,  # [reference] village centroid = NOAA Atlas-14 point
    design_lon=-83.5452,
    corridor_name="Ohio Brush Creek corridor",  # [inference] the receiving-water design corridor
    dominant_hsg="C",  # [inference] unglaciated Appalachian shale residuum (Latham/Rarden/Gilpin) → HSG C/D
    hsg_citation=(
        "Adams County, OH dominant hydrologic soil group C (grading to D) — [inference] far-southern "
        "UNGLACIATED Appalachian uplands (Western Allegheny Plateau, MLRA 124): silt loams over slowly-"
        "permeable acid-shale residuum with a perched seasonal water table (Latham/Rarden/Gilpin series; "
        "NRCS OSDs), the classic HSG C/D signature — the INVERSE of the glacial-outwash HSG B valleys "
        "(Urbana) and distinct from the Maumee lake-plain HSG D clays. Ohio Brush Creek floodplain "
        "alluvium is better-drained (B/C). Pending an SSURGO area-weighted confirmation (Web Soil "
        "Survey area OH001; onboard SSURGO step needs a footprint)."
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/west-union/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/west-union/bosc-site-footprint.yaml",  # [open] pending an identified site
    # per-site onboard reach outputs (slug-scoped — never clobber the other sites)
    climatology_relpath="reference/hydrology/west-union/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/west-union/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/west-union/baseline.yaml",
    rsei_relpath="reference/rsei/west-union/inventory.yaml",
    consumer_energy_relpath="reference/eia/west-union/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/west-union/demand-pressure.yaml",
    grid_relpath="reference/eia/west-union/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(
        0.0,
        0.0,
        0.0,
        0.0,
    ),  # [open] pending an identified corridor on Ohio Brush Creek
    # balance — West Union WWTP (Village of West Union), the only municipal POTW on record.
    plant_receiving={
        "west-union-wwtp": (
            "Beasley Fork (→ Ohio Brush Creek → Ohio River)",
            "US EPA NPDES OH0028088 / Ohio EPA permit 0PC00019 (West Union WWTP); design 0.7 MGD "
            "(Municipality 0.5-1.0 MGD class); immediate receptor Beasley Fork (warmwater habitat), "
            "a tributary within the Ohio Brush Creek system — data/reference (Ohio EPA NPDES service) "
            "[verified]",
        ),
    },
    abstraction_gage="03237500",  # [inference] the Ohio Brush Creek near West Union receiving-reach gage
    # refill (the water-balance supply model is not yet designed for West Union)
    supply_gage_primary="03237500",  # [verified] Ohio Brush Creek near West Union
    supply_gage_secondary="TODO",  # [open] no second active gage on Ohio Brush Creek
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    facility=None,  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
    serving_utility_citation=(  # [reference] not corpus
        "Adams County, OH is predominantly served by Adams Rural Electric Cooperative, Inc. — EIA-861 "
        "#118 [verified] against the primary EIA-861 2024 Service_Territory file (utility 'Adams Rural "
        "Electric Coop, Inc', OH; counties Adams/Brown/Highland/Pike/Scioto; ~9,274 meters secondary; "
        "HQ West Union; a Buckeye Power / Ohio's Electric Cooperatives member). #118 is a short-form "
        "EIA-861 filer, so it reports no Sales_Ult_Cust retail line — the co-op cannot back a "
        "connector-sourced retail denominator. Ohio Power Co (AEP Ohio, EIA-861 #14006, full-filing) "
        "serves the Village of West Union edge and provides the AEP transmission + PJM-settlement "
        "footprint (AEP 'West Union Loop' projects); the profile therefore keeps AEP Ohio / the PJM AEP "
        "zone as the resolvable grid backdrop rather than the co-op's (unavailable) retail line."
    ),
    # grid (same PJM AEP zone as the AEP-Ohio sites — Ohio Power / co-op both settle in AEP)
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (same zone as Lima)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (bosc lmp) — Adams County OH settles in "
        "the PJM AEP zone (AEP transmission; Adams Rural Electric is a Buckeye Power member on AEP)"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # rsei
    county_name="Adams County, OH",  # [verified]
)


SITES: dict[str, SiteProfile] = {
    _LIMA.slug: _LIMA,
    _FINDLAY.slug: _FINDLAY,
    _FORT_WAYNE.slug: _FORT_WAYNE,
    _VAN_WERT.slug: _VAN_WERT,
    _TOLEDO.slug: _TOLEDO,
    _DEFIANCE.slug: _DEFIANCE,
    _BRYAN.slug: _BRYAN,
    _OTTAWA.slug: _OTTAWA,
    _URBANA.slug: _URBANA,
    _SPRINGFIELD.slug: _SPRINGFIELD,
    _XENIA.slug: _XENIA,
    _WPAFB.slug: _WPAFB,
    _HAMILTON_MIDDLETOWN.slug: _HAMILTON_MIDDLETOWN,
    _TROY_PIQUA.slug: _TROY_PIQUA,
    _SIDNEY.slug: _SIDNEY,
    _GREENVILLE.slug: _GREENVILLE,
    _WILMINGTON.slug: _WILMINGTON,
    _NEW_ALBANY.slug: _NEW_ALBANY,
    _COLUMBUS.slug: _COLUMBUS,
    _COSHOCTON.slug: _COSHOCTON,
    _PIKETON.slug: _PIKETON,
    _SANDUSKY.slug: _SANDUSKY,
    _WEST_UNION.slug: _WEST_UNION,
}

# The per-site output relpaths `watermark onboard` writes. Each must be unique to its site so
# onboarding never overwrites another site's committed data — a profile that copies Lima
# without slug-scoping these would otherwise clobber Lima's files (#326 hardening).
PER_SITE_OUTPUT_FIELDS: tuple[str, ...] = (
    "climatology_relpath",
    "corridor_ddf_relpath",
    "baseline_relpath",
    "rsei_relpath",
    "consumer_energy_relpath",
    "demand_pressure_relpath",
    "grid_relpath",
)
