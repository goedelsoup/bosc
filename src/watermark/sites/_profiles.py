"""The registered :class:`SiteProfile` literals + the ``SITES`` registry (#597 split).

One profile per watershed point. Lima is the live reference build; basin sites come online
via their onboarding issues. Per-profile values that equal the network-wide default
(Ohio ``eia_state``/``gnis_default_state``, the 136th GA, ``serving_utility_source``) are
omitted here and supplied by the :class:`SiteProfile` model defaults — only the outliers
(Fort Wayne/Indiana, Lima's corpus-grounded utility source) carry an explicit value.
"""

from __future__ import annotations

from watermark.facility.screening import ceiling_screen, floor_area_screen, investment_screen
from watermark.sites._gis_schemas import (
    ALLEN_IN_PARCEL_SCHEMA,
    CHAMPAIGN_PARCEL_SCHEMA,
    CLINTON_PARCEL_SCHEMA,
    FINDLAY_ZONING_SCHEMA,
    FORT_WAYNE_ZONING_SCHEMA,
    LIMA_FLOOD_SCHEMA,
    LIMA_PARCEL_SCHEMA,
    LIMA_ZONING_SCHEMA,
    LUCAS_AREIS_PARCEL_SCHEMA,
    LUCAS_ZONING_SCHEMA,
    MIAMI_PARCEL_SCHEMA,
    NATIONAL_NFHL_FLOOD_SCHEMA,
    OHIO_STATEWIDE_PARCEL_SCHEMA,
    PIQUA_ZONING_SCHEMA,
    PUTNAM_PARCEL_SCHEMA,
    RICHLAND_PARCEL_SCHEMA,
    SHELBY_PARCEL_SCHEMA,
    SIDNEY_ZONING_SCHEMA,
    VAN_WERT_PARCEL_SCHEMA,
    WILMINGTON_ZONING_SCHEMA,
)
from watermark.sites._model import (
    CoolingModelType,
    DcEndUse,
    DischargeReach,
    FacilityKind,
    FacilityLifecycle,
    FederalInstallation,
    GensetRatingBasis,
    ItLoadGrounding,
    SiteFacility,
    SiteProfile,
)

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
    dewatering_wellfield_relpath="reference/ohio-waterwells/lima-campus-dewatering.csv",
    # The Ottawa River reach bracketing the campus: gains from the Lima gage (upstream, 128 sq mi)
    # to the Kalida gage (downstream, 350 sq mi). A dewatering discharge to the Ottawa would ride in
    # the reach gain, but the 222 sq mi of incremental drainage between them swamps a ~7.6 cfs source.
    dewatering_discharge_reach=DischargeReach(
        upstream_gage="04187100",
        upstream_name="Ottawa River at Lima OH",
        upstream_da_sqmi=128.0,
        downstream_gage="04188100",
        downstream_name="Ottawa River near Kalida OH",
        downstream_da_sqmi=350.0,
    ),
    dewatering_discharge_relpath="reference/hydrology/dewatering-discharge.yaml",
    # Design-storm routing tables (#1806): Lima pins its legacy un-slugged paths; a peer
    # leaves these None and resolves reference/hydrology/<slug>/<file> via site_reference_path.
    hydrology_network_relpath="reference/hydrology/network.yaml",
    hydrology_reaches_relpath="reference/hydrology/reaches.yaml",
    reach_nav_relpath="reference/hydrology/reach-nav.yaml",
    routed_hydrograph_relpath="reference/hydrology/routed-hydrograph.yaml",
    # per-site onboard reach outputs (Lima = legacy un-slugged paths)
    climatology_relpath="reference/hydrology/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/baseline.yaml",
    rsei_relpath="reference/rsei/inventory.yaml",
    consumer_energy_relpath="reference/eia/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/demand-pressure.yaml",
    # The only abatement instrument in the network on the record (CRA No. 1, Res #548-25).
    abatement_parameters_relpath="reference/economics/abatement-parameters.yaml",
    grid_relpath="reference/eia/grid-profile.yaml",
    # Lima pins the un-slugged legacy regulatory-stack paths (#1639/B1); peers use the
    # slug-scoped default. (ba-interchange stays basin-shared — not a per-site relpath.)
    ferc_relpath="reference/ferc/ferc-seam.yaml",
    pjm_relpath="reference/pjm/pjm-market.yaml",
    federal_relpath="reference/federal/federal-energy.yaml",
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
    # (332-128)/332 = 0.614: nets the Ottawa's drainage (128 sq mi at Lima, routed separately as
    # the secondary river) out of the 332-sq-mi Fort-Jennings Auglaize record to isolate the
    # Auglaize's own flow at the intake reach — the committed transfer from low-flow-7q10.derived.yaml.
    intake_da_ratio_primary=0.614,
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
    facilities=(
        SiteFacility(
            name="Project BOSC",
            status=FacilityLifecycle.CONSTRUCTION,  # air-permit-grounded; the disclosed build (#234)
            operator="Google (developer of record)",
            operator_citation=(
                "[verified] Google is the developer of record for the Lima campus (Select-Committee "
                "record #234); the deed fixes the builder, not the occupant."
            ),
            # end_use left [open] on purpose — which type the Lima campus is (and who can use it) is the
            # unresolved question the end-use explorer (endUse.ts / docs/end-use-and-workloads.md) turns on.
            genset_count=114,
            genset_mw=2.75,  # MW each (~2,750 ekW), per the air permit
            # [verified: draft] the ~2,750 ekW rating is on the draft public notice and CBI-redacted
            # in the issued permit — the redaction the whole load report is built on.
            genset_rating_basis=GensetRatingBasis.DRAFT_ONLY,
            # The site's most-cited number, TRANSCRIBED from the corpus, not multiplied out (#1771).
            # The record says "~313 MW" everywhere it appears; 114 x 2.75 = 313.5, so deriving it
            # would restate the headline as 313.5/314 and contradict the permit extraction, the
            # essay and the docs. The `~` rides as data (genset_total_approximate) so every
            # rendering keeps it. The model reconciles this against the components on validation.
            genset_total_mw=313.0,
            genset_total_approximate=True,
            genset_total_citation=(
                "~313 MW backup total, as stated in the committed final-permit extraction "
                "data/extracted/permits/4132514.epa.yaml ('the ~2,750 ekW/engine figure behind "
                "the ~313 MW backup total'). NOT a figure of the issued permit, which withholds "
                "the per-engine rating as trade secret and so cannot state the total: it is the "
                "final permit's unit COUNT (114 hall gensets) x the DRAFT public notice's "
                "~2,750 ekW/engine (eDocs 3987141/3987144), approximate as transcribed."
            ),
            it_load_mw=275.0,  # [inference] midpoint of the 250-300 MW N+1 estimate (IT ~= backup),
            # derived from the disclosed ~313 MW backup — NOT a permit disclosure (#1697)
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
    ),
    serving_utility_source="document",
    serving_utility_citation=(
        "relator data appendix (data/extracted/legal/select-committee-2026/relator-testimony/"
        "bosc-data-appendix-2026-06-01.md): the 25 MW threshold 'matches the AEP Ohio tariff'; "
        "corroborated by Allen County commissioners' minutes (local AEP 3-phase service, "
        "Res #974-25). Formal confirmation: EIA-861 service territory / PUCO map. Further "
        "corroborated (not newly established) by AEP Ohio's own 'Lyka Transmission Project' "
        "(345kV substation + line, same township; data/extracted/grid/"
        "aep-lyka-transmission-2026.project.yaml) — that project names no customer, so it "
        "does not by itself confirm the Bosc campus as the specific Lyka load (#1476)."
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
    # civic corridor vocabulary (#1523): the project-specific subjects that put a subdivision
    # meeting on the corridor timeline. Verbatim the former module constant (bosc/bistrozzi/
    # datacenter/google) — ambiguous names (hume/amazon) stay searchable in the index but off
    # the chronology. Peers default empty until they declare their own.
    corridor_subjects=("bosc", "bistrozzi", "datacenter", "google"),
    # oepa permits (#844); 2PE00000 = the City of Lima WWTP, the municipal receiving
    # plant / un-requested municipal custodian (#1536)
    npdes_permits=["2PH00006", "2PH00007", "2PK00002", "2PE00000"],
)


# The first cohort watershed point (#237): Findlay, OH on the Blanchard River (a Maumee
# tributary via the Auglaize). The data-center dimension is now DISCLOSED (#1459): the One Power
# Co "Findlay Megawatt Hub" and its 150 MW MARA Holdings take-or-pay customer populate the
# `facility` power basis below — SEC-instrument-grounded, not a screening inference (see
# data/extracted/findlay/data-centers.md). The remaining facility-specific hydrology inputs (the
# development land-cover scenario, the toxics corridor, per-WWTP receiving waters, the refill
# supply gages + passby minimums) stay `TODO` pending their own epic #1265 sub-issues — the
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
    # balance — Findlay WPCC (OH0025135 / 2PD00008), the Blanchard subbasin's anchor POTW.
    # Receiving water and the cited low flow are now on the record from the plant's own issued
    # NPDES fact sheet (#1460, closing #352): outfall 2PD00008001 to the Blanchard River at
    # RIVER MILE 56.42, average design flow 15 MGD (23.208 cfs), peak hydraulic 40 MGD.
    # ⚠️ TWO DIFFERENT LOW FLOWS, and the difference is the whole point. Findlay↔Ottawa
    # intra-tributary comparison (#417) screens this plant at 2.68x against the shared DERIVED
    # Blanchard 7Q10 (8.67 cfs at USGS 04189000; low-flow-7q10.derived.yaml, #414). The permit's
    # own Table 12 gives 0.21 cfs AT THE OUTFALL — ~41x smaller — so the cited screen is ~110x,
    # not 2.68x, and the fact sheet computes an acute dilution ratio of 1.0 outright: at design
    # flow the Blanchard below RM 56.42 IS the effluent. Reconciling the derived and cited
    # denominators (and re-basing findlay-ottawa-comparison.yaml) is the hydrology sub-issue
    # #1458; nothing here re-bases it, and the derived artifact is left alone on purpose.
    plant_receiving={
        "findlay-wpcc": (
            "Blanchard River at River Mile 56.42",
            "Ohio EPA NPDES fact sheet 2PD00008*UD (data/documents/oepa/findlay/2PD00008.fs.pdf), "
            "p. 7 — outfall 2PD00008001, HUC 04100008-03-04, Ohio EPA river code 04-160; "
            "Table 12 (p. 28) annual 7Q10 0.21 cfs / 1Q10 0.17 cfs / harmonic mean 1.84 cfs "
            "(USGS gages 04188300 + 04189000), design flow 23.208 cfs, acute dilution ratio 1.0 "
            "(p. 13) — data/extracted/oepa/findlay/2PD00008.fs.npdes.yaml",
        ),
    },  # [verified: OEPA 2PD00008*UD fact sheet]. Key is the future watch-item id (#829) —
    # Findlay has no committed watch-items.geojson yet, so the routed balance does not read this
    # entry; it is the cited datum of record until that file lands, and the two must match then.
    abstraction_gage="04189000",  # [inference] the primary Blanchard gage near Findlay
    # refill (the water-balance supply model is not yet designed for Findlay)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility
    # facility CONFIRMED (#1459) — the One Power Co "Findlay Megawatt Hub" (MWHub 01), the ~170-ac
    # campus in Allen Township (I-75 at TR 215 / CR 99), and its anchor take-or-pay customer MARA
    # Holdings, Inc. (NASDAQ: MARA, ex-Marathon Digital — bitcoin mining). Unlike the network's
    # site-plan-grounded facilities (Urbana #1327 / Sidney #1378 / Van Wert #1402), where NO MW is
    # disclosed and the IT load is a floor-area / investment SCREENING bracket, here the load IS
    # DISCLOSED from both sides via SEC instruments: One Power Co's Form S-1 (EDGAR CIK 2039139)
    # states the hub is "Operating" with "Current Capacity 30 MW, Planned Maximum 150 MW" and names
    # MARA as the 150 MW / 15-yr take-or-pay customer, and MARA's own 2024-11-11 release confirms
    # "a 150-megawatt operation in Findlay, Ohio, which already has 30 megawatts of capacity." So
    # the IT load is grounded on it_load_citation as a [verified] DISCLOSURE (central = the 150 MW
    # contracted take-or-pay; low = the 30 MW currently energized), NOT a screening inference. No
    # air permit / genset bank was findable at web level (an [open] check), so genset_count/
    # genset_mw/air_permit_citation stay None and the air-dispatch fleet model refuses cleanly.
    # cooling_model stays UNKNOWN — MARA's Findlay cooling design is not on the public record (a
    # bracketed range, never the evaporative default). ⚠️ EntityGraph guard: MARA Holdings, Inc.
    # (NASDAQ: MARA) != Marathon Petroleum Corp (the Findlay-HQ refiner + a Hancock-County NPDES
    # permittee) — two unrelated companies; never merge them. See data/extracted/findlay/data-centers.md.
    facilities=(
        SiteFacility(
            name="Findlay Megawatt Hub (MWHub 01)",
            status=FacilityLifecycle.LIVE,  # "Status: Operating" — 30 MW energized (One Power S-1)
            operator="MARA Holdings, Inc. (NASDAQ: MARA); host One Power Co",
            operator_citation=(
                "[verified] One Power Co Form S-1 (EDGAR CIK 2039139) + MARA Holdings 2024-11-11 "
                "release: MARA is the 150 MW, 15-year take-or-pay customer at the One Power Findlay "
                "Megawatt Hub (host/host-operator One Power Co)."
            ),
            end_use=DcEndUse.BITCOIN,
            end_use_citation=(
                "[verified] behind-the-meter bitcoin mining — MARA Holdings, Inc. is a bitcoin miner "
                "(its own customer); MARA volunteered the distinction 'we don't have customers in "
                "Bitcoin' at the 2026-06-04 Lima Select-Committee hearing (data/extracted/legal/"
                "select-committee-2026/hearings-audio/bosc-committee-hearing-2026-06-04-pm2."
                "transcript.md [11:55])."
            ),
            it_load_mw=150.0,  # [verified] contracted take-or-pay / planned maximum; see it_load_citation
            it_load_low_mw=30.0,  # [verified] currently energized ("Current Capacity 30 MW, Status: Operating")
            it_load_high_mw=150.0,  # [verified] contracted / planned maximum (150 MW take-or-pay)
            it_load_source=ItLoadGrounding.DISCLOSURE,
            it_load_citation=(
                "[verified] DISCLOSED load (NOT a screening inference): One Power Co Form S-1 (EDGAR "
                "CIK 2039139) describes MWHub 01 / Findlay Megawatt Hub — 'Current Capacity 30 MW, "
                "Planned Maximum 150 MW, Status: Operating' — and names MARA Holdings, Inc. as the 150 "
                "MW, 15-year take-or-pay customer ('due regardless of whether or not the customer elects "
                "to purchase power'); corroborated by MARA's 2024-11-11 release ('a 150-megawatt "
                "operation in Findlay, Ohio, which already has 30 megawatts of capacity', part of ~372 "
                "MW across three Ohio sites, full energization intended by end-2025). Central = the 150 "
                "MW contracted take-or-pay; low = the 30 MW currently energized; high = the 150 MW "
                "contracted maximum. MARA's energization status as of 2026 is [open — MARA 10-K/ops "
                "updates]. A separate +300 MW 'standalone interconnection site' expansion (S-1, 2024) "
                "has NO named customer and is NOT in this basis (it stays [open], the epic #1265 grid "
                "sub-issue's PUCO/PJM/AEP target). See data/extracted/findlay/data-centers.md."
            ),
            # No disclosed gensets / air permit found at web level (an [open] check — OEPA eSuite, One
            # Power / MARA generator banks) → genset/backup basis + air-dispatch fleet model absent;
            # genset_count/genset_mw/air_permit_citation stay None (no fabricated fleet).
            facility_type=(
                "behind-the-meter compute load — bitcoin mining (MARA Holdings, Inc.; NASDAQ: MARA) at "
                'the One Power Co "Findlay Megawatt Hub" (MWHub 01), Allen Township — Status: Operating'
            ),  # [verified] operator / host / status
            # gross_floor_area_sqft / disclosed_investment_usd = [open]: neither a building size nor a
            # compute-operation capital figure is disclosed for the MARA operation (the $5.9M / 110-ac
            # 2026-03-05 land assembly is a separate recorder/places thread under epic #1265, not this
            # facility's investment; hyperscale end-use for the assembly is press speculation [reference]).
            disclosure_citation=(
                "[verified] One Power Co Form S-1 (EDGAR CIK 2039139: DRS 2024-11-12, IPO S-1 filed "
                "2025-01-23, withdrawn Form RW 2025-05-09, Form D private placement 2025-07-23) + MARA "
                "Holdings 2024-11-11 press release (ir.mara.com/news-events/press-releases/detail/1375). "
                "Host: One Power Co (CEO Jereme Kent); OnSite Partners — funds advised by Basalt "
                "Infrastructure Partners — acquired One Power, announced 2026-02-16. The hub first "
                "energized 2023 with 'the first fully digital substation in the United States.' See "
                "data/extracted/findlay/data-centers.md."
            ),
            # Cooling archetype (#1054): UNKNOWN — MARA's Findlay cooling design is not on the public
            # record, so it gets a bracketed range, never the water-intensive evaporative default. Not
            # asserted. (Bitcoin-mining loads span air-cooled / immersion / hydro-cooled designs.)
            cooling_model=CoolingModelType.UNKNOWN,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] cooling method not disclosed in the record — kept UNKNOWN (bracketed "
                "range). MARA has not stated the Findlay cooling design; the One Power hub is a "
                "behind-the-meter natural-gas-generation compute campus. Refine to a selected model on "
                "a disclosed mechanical/plumbing permit or an ingested cooling spec."
            ),
        ),
    ),
    # The one hand-authored string that reaches the connector-generated grid-profile.yaml
    # (`derive_grid_profile` → `ServingUtility.utility.citation`). The site's qualitative grid
    # POSTURE — Schedule DCT, the OPSB siting pair, the behind-the-meter fleet, the undocumented
    # +300 MW — is NOT inlined there: `GridProfile` is an `extra="forbid"` model of connector-
    # pulled denominators that the next run rewrites, so the posture lives as cited corpus
    # records under data/extracted/grid/findlay/ and this citation points at them (#1464).
    serving_utility_citation=(  # [reference] not Lima's corpus
        "EIA-861 service-territory file (Ohio Power Co #14006) + PUCO certified-territory map; "
        "AEP Ohio serving Findlay corroborated by the City of Findlay (AEP smart-meter notice); "
        "Hancock-Wood Electric Cooperative serves the rural county and has no located large-load "
        "or data-center customer (negative re-checked 2026-07-31). Retail terms for a >25,000 kW "
        "load here are AEP Ohio Schedule DCT, P.U.C.O. No. 22 Original Sheet Nos. 223-1..223-7 "
        "(origin PUCO 24-508-EL-ATA, on appeal as Ohio S.Ct. 2025-1458) — "
        "data/extracted/grid/findlay/aep-dct-tariff-posture.yaml"
    ),
    # grid (same PJM AEP zone as Lima — Ohio Power Co)
    lmp_usd_mwh=45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (same zone as Lima)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, AEP zone (pnode 8445784), 2025 day-ahead annual mean "
        "$45.81/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) — same AEP zone as Lima"
    ),
    lmp_pnode_id=8445784,
    lmp_pnode_name="AEP",
    # OEPA permit registry — what `watermark oepa discover` annotates as "known" (#844).
    npdes_permits=["2PD00008"],  # City of Findlay WPCC / application OH0025135
    # Corpus scope (#762/#780/#1505). Findlay's worked record spans four collections: its own
    # `findlay/` tree (flood, WARN, brownfield, governance, narratives), the site-scoped OEPA
    # sub-collection `oepa/findlay/` holding the 2PD00008 instrument set, `grid/findlay/` — the
    # grid-posture set (#1464: the Rocky Ford OPSB pair, Schedule DCT read against the Megawatt
    # Hub, the behind-the-meter fleet, the +300 MW gap) — and `legal/one-energy-v-allen-twp/`,
    # the published Third District opinion in the Open Meetings Act litigation that shadowed
    # Allen Township's move from unzoned to zoned (#1463). That last one follows the
    # `legal/thor-v-urbana` precedent exactly: a filed court instrument is filed by CASE under
    # `legal/`, not under the site, and the site reaches it by naming the prefix here — no rule
    # derives a case name. The site's own `findlay/` collection and its `oepa/findlay/` +
    # `grid/findlay/` subtrees need no entry (#1405): they are eponymous, so
    # `_eponymous_prefixes` grants them and subtracts them from Lima's scope automatically.
    corpus_relpaths=("legal/one-energy-v-allen-twp",),
    # Civic subject vocabulary (#1523/#1839) — the meeting keywords that put a Hancock County
    # subdivision meeting on this site's chronology. NOT Lima's: `bosc`/`bistrozzi`/`google` are
    # Allen County parties and appear nowhere in this record. Each term below is cited:
    #   datacenter    — Allen Township's July-2026 amendments, which would write "data center"
    #                   into a zoning resolution where the phrase appears ZERO times
    #                   (data/documents/findlay/governance/Res.DataCenters.pdf; the adopted book
    #                   at Zoning-Book-Effective-05-11-26.pdf), plus the county's own SB 52
    #                   restricted-area notice.
    #   one_power     — One Power Co and its "Findlay Megawatt Hub" (MWHub 01), the site's
    #                   disclosed facility. [verified] One Power Form S-1, EDGAR CIK 2039139 —
    #                   data/extracted/findlay/data-centers.md entry 1.
    #   mara_holdings — MARA Holdings, Inc., the hub's 150 MW take-or-pay customer. [verified]
    #                   same S-1 + MARA 2024-11-11 release.
    # Deliberately EXCLUDED: `interstate_capital` (the live SR-613 rezoning applicant). Nothing
    # in the corpus connects it to a data center — allen-twp-rezoning-interstate-capital-2026.yaml
    # says so outright — and a corridor subject is an assertion of relevance, so naming it here
    # would manufacture the very link that artifact refuses to draw. Generic township topics
    # (annexation/rezoning/solar/easement, the actual bulk of these minutes' hits) stay
    # searchable in the index but off the chronology, exactly as at Lima.
    corridor_subjects=("datacenter", "one_power", "mara_holdings"),
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
    dominant_hsg="C/D",  # [verified] SSURGO over the assemblage: 50% C/D + 50% D — the dual group, verbatim
    hsg_citation=(
        "Allen County, IN dominant hydrologic soil group C/D — [verified] USDA NRCS SSURGO via Soil "
        "Data Access, a 30-point grid sample over the committed Hatchworks parcel assemblage "
        "(parcel-assemblage.geojson): 50% C/D + 50% D (Pewamo / Blount-Glynwood lake-plain clays of "
        "the upper Maumee). Carried as the DUAL group rather than pre-collapsed to its drained C: "
        "drained it runs as C — confirming the prior NRCS-narrative inference — and undrained, the "
        "natural condition of every sampled point here, as D (high runoff). WS-20 / #1620 resolves "
        "which per scenario. See data/extracted/fort-wayne/bosc-site-footprint.yaml (#362). A "
        "SURVEYED developed footprint is still pending the stormwater-permit extraction."
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
    facilities=(
        SiteFacility(
            name="Project Zodiac",
            status=FacilityLifecycle.LIVE,  # operating data center on an issued IDEM Title V permit
            operator="Hatchworks LLC (Project Zodiac) — 'a stationary data center'",
            operator_citation=(
                "[verified] IDEM Title V air permit 003-47378-00530 (issued 2024-09-06) names the "
                "operator as 'a stationary data center' (SIC 7374); developer entity Hatchworks LLC."
            ),
            # end_use left [open] — the permit discloses a stationary data center, not the workload
            # type or the ultimate operator identity (the GCP attribution is [inference], not on record).
            # Project Zodiac (Hatchworks LLC) — IDEM Title V air permit 003-47378-00530. The permit
            # discloses heat input (26.4 MMBTU/hr per engine), NOT an electrical rating, so genset_mw
            # is DERIVED (heat-input x efficiency), unlike Lima's disclosed ekW. genset_count is verbatim.
            genset_count=34,  # [verified] "Thirty-four (34) diesel-fired emergency generators, Gen 1..34" (A.2)
            genset_mw=3.0,  # [inference] 26.4 MMBTU/hr HHV / engine at ~38-43% electrical eff -> ~2.9-3.3 MWe
            # [inference] the rating is back-derived from heat input — the permit states no
            # electrical rating at all, so any backup total resting on it is an inference too.
            genset_rating_basis=GensetRatingBasis.DERIVED,
            # No genset_total_mw: unlike Lima's ~313 MW, no backup TOTAL is stated on this record
            # (the ~102 MW below is this profile's own arithmetic). A consumer that needs one
            # derives it from the components and must label it derived — never [verified].
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
    # corpus scope (#762): only Fort Wayne's own extracted records — the `fort-wayne/` collection
    # plus the IDEM (Indiana) jurisdiction+site subtree `idem/fort-wayne/`. Both are eponymous, so
    # since #1405 `_eponymous_prefixes` derives them and no `corpus_relpaths` entry is needed;
    # Fort Wayne files nothing under a case/project name.
    # rsei
    county_name="Allen County, IN",  # [verified]
)


# The small-stream headwaters comparator: Van Wert, OH — the Auglaize-subbasin point. Unlike
# the mainstem comparators (Defiance 12 MGD, Fort Wayne 74 MGD), Van Wert's WWTP is a 4.0 MGD
# plant discharging to a *small tributary* (Town Creek → Little Auglaize → Auglaize → Maumee),
# so the dilution denominator is tiny — the effluent-dominance end of the basin spectrum. A
# *coming-soon* point; an Ohio site (AEP Ohio / PJM AEP zone, the Ohio LSC connector applies),
# so the cross-state connector axis is not re-exercised. Geography is sourced + cited below. The
# data-center dimension is no longer undisclosed: the QTS Van Wert Mega Site went public 2026-05-29
# ($10B, 902 ac of the ~962 ac annexed 2026-05-11), so a SITE-PLAN-grounded `SiteFacility` is now
# pinned below (#1402, the #1327 Urbana precedent) — the campus MW is a [reference] bracket, never
# a fabricated disclosure. See data/extracted/van-wert/data-centers.md.
# Neither floor area nor investment-scaled load screens Van Wert; the only MW figure is the
# announced "up to 500 MW" ceiling → the announced-ceiling screen (watermark.facility.screening,
# #1629; central/high = the ceiling, low divides out the PUE ceiling). Replaces the old literal.
_VAN_WERT_LOAD = ceiling_screen(500.0)
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
    # GIS — schema-driven (#237/#421): parcels = the county's AGOL auditor-CAMA join (the bhamaps
    # PAT MapServer died with its expired cert — ArcGIS Server removed from the host — and the
    # county migrated to ArcGIS Online); flood = the shared national NFHL; zoning stays a
    # confirmed negative (townships are map-only; city zoning is static PDFs + amlegal).
    parcels_url=(  # [verified] Van Wert County GIS AGOL — parcel_joinedVWOH layer 0 (auditor CAMA)
        "https://services8.arcgis.com/G5sGKRBVtJMunpVA/arcgis/rest/services/"
        "parcel_joinedVWOH/FeatureServer/0"
    ),
    zoning_url="TODO",  # [open] no Van Wert zoning REST anywhere (map-only/PDF) — unchanged negative
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=VAN_WERT_PARCEL_SCHEMA,  # [verified] AGOL parcel_joinedVWOH — owner + CAMA (#421)
    gis_zoning=None,  # [open] no City of Van Wert zoning REST found (map-only/PDF)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "van-wert-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Van Wert ~84.58 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=40.8696,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-84.5829,
    corridor_name="Town Creek / Little Auglaize corridor",  # [inference] the receiving-water reach
    # [verified] SSURGO over the committed campus assemblage (#1403). The old [inference] named the
    # right ground — the Great Black Swamp lake plain — but pre-collapsed a DUAL rating to its
    # undrained letter. Recorded verbatim per WS-20/#1620 so pre_/post_drainage_condition resolve
    # it (drained C on the tile-drained CAUV cropland it is today, undrained D once site work
    # severs that tile) instead of the profile fixing one letter where no scenario can see it.
    dominant_hsg="C/D",
    hsg_citation=(
        "Van Wert Mega Site campus — SSURGO dominant hydrologic soil group C/D at 44 of 45 grid "
        "points over data/reference/van-wert/parcel-assemblage.geojson "
        "(watermark.hydrology.connectors.ssurgo.dominant_hsg, grid_n=8, read 2026-07-31): "
        "Hoytville silty clay 0-1% slopes (40 points) + Hoytville silty clay loam 0-1% (1) and "
        "Wabasha silty clay loam (3), all very poorly drained; the lone D point is Nappanee silt "
        "loam 0-2%, somewhat poorly drained. Great Black Swamp lake-plain clays, as the prior "
        "[inference] read them — but NRCS rates Hoytville C/D, not flat D: C where the field tile "
        "is installed and maintained, D in the natural undrained condition. "
        "See data/extracted/van-wert/bosc-site-footprint.yaml"
    ),
    # [verified] pre-development cover from the auditor CAMA land use across the five committed
    # campus parcels — 110 'cash-grain/general farm' + 199 'other agricultural', three of them
    # CAUV-flagged, i.e. CAUV row crop with no campus improvement yet on the tax record.
    # post/developed_pervious are the network's standard screening pair (NLCD 24 high-intensity +
    # NLCD 21 developed open space): QTS has disclosed NO floor area and no site plan, so those
    # two stay `source: assumption`-grade until the Rule-5 SWPPP / site plan lands (#1401).
    pre_cover="cropland",
    post_cover="developed_campus",
    developed_pervious_cover="open_space",
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
    # [verified] committed #1403 — the five parcels deeded to QTS VAN WERT LLC in June 2026
    # (900.59 ac CAMA / 901.502 ac planar, against the 902-ac campus figure QTS quotes) + the
    # footprint record derived from them.
    parcels_relpath="reference/van-wert/parcel-assemblage.geojson",
    footprint_relpath="extracted/van-wert/bosc-site-footprint.yaml",
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
    # grid / facility — the disclosed QTS Van Wert Mega Site (#1402). SITE-PLAN-grounded (#1327 Urbana
    # precedent), NOT air-permit-grounded (contrast Lima / Fort Wayne): operator/type/investment are
    # disclosed [verified], but the campus MW is NOT officially disclosed — QTS's own FAQ declines to
    # state capacity. The only MW figure is Thor/Form8tion's "up to 500 MW" [reference], carried as a
    # bracket (never a point disclosure). Unlike Urbana/Troy-Piqua/Bowling Green, no gross floor area
    # is disclosed, so the it_load bracket is built off the 500 MW ceiling (not a floor-area screen):
    # 500 MW central/high (the announced "up to" ceiling — conservative-high downstream, like the
    # Bowling Green disclosed-peak pin #1435), and a low that reads the same 500 MW as the ALL-IN
    # campus draw and divides out the PUE ceiling (500 / 1.43 ~= 350 MW implied IT). No on-site
    # gensets or air permit are disclosed (emergency backup only, no PTI found), so genset_count/
    # genset_mw/air_permit_citation stay None and the it_load is grounded by it_load_citation.
    # See data/extracted/van-wert/data-centers.md.
    facilities=(
        SiteFacility(
            name="Van Wert Mega Site",
            status=FacilityLifecycle.CONFIRMED,  # land assembled/annexed/zoned; groundbreaking Q4 2026
            operator="QTS Data Centers (QTS Realty Trust, LLC — Blackstone); developer Thor Equities Group",
            operator_citation=(
                "[verified] QTS Data Centers publicly named as the Van Wert Mega Site end user/owner "
                "2026-05-29 (q.com/data-centers/van-wert; Data Center Dynamics; VW Independent); land "
                "assembled by Thor Equities / Form8tion."
            ),
            end_use=DcEndUse.COLOCATION,
            end_use_citation=(
                "[verified] colocation — QTS Data Centers is a landlord/colocation operator (it "
                "builds and powers the hall; tenants own the compute), the network's canonical "
                "colocation example (docs/end-use-and-workloads.md), NOT an owner-runs-own-workloads "
                "hyperscaler; public disclosure 2026-05-29 (q.com/data-centers/van-wert)."
            ),
            it_load_mw=_VAN_WERT_LOAD.central,  # [reference] the announced "up to 500 MW" ceiling — carried central/high
            it_load_low_mw=_VAN_WERT_LOAD.low,  # ceiling / PUE ceiling (implied IT); see it_load_citation
            it_load_high_mw=_VAN_WERT_LOAD.high,  # the announced "up to 500 MW" ceiling
            it_load_source=ItLoadGrounding.REFERENCE,
            it_load_citation=(
                "[reference] 'up to 500 MW' — Thor Equities / Form8tion's 2025-08-19 land-acquisition "
                "release (GlobeNewswire; citybiz; Data Center Dynamics) and local press; NOT an "
                "air-permit or PJM-interconnection disclosure of the campus's own load. QTS's own site "
                "DECLINES to state capacity ('we don't disclose specific power capacity', "
                "q.com/data-centers/van-wert), so this stays a [reference] bracket, never a point "
                "disclosure — the official/interconnection MW is [open]. Carried central at the announced "
                "500 MW ceiling per #1402 (like the Bowling Green disclosed-peak precedent, #1435): 500 is "
                "an 'up to'/campus-draw ceiling, so treating it as the IT load makes downstream figures "
                "(facility_draw = IT x PUE, then x load factor) run conservative-high. The low bound reads "
                "the same 'up to 500 MW' as the ALL-IN campus/grid-interconnection draw and divides out "
                "the cooling-dominated PUE ceiling (the announced-ceiling screen, "
                f"watermark.facility.screening — #1629): 500 / 1.43 ~= {_VAN_WERT_LOAD.low:g} MW implied "
                f"IT load — the bracket ({_VAN_WERT_LOAD.low:g}-{_VAN_WERT_LOAD.high:g} MW) thus spans "
                "the campus-total-vs-IT-only interpretive ambiguity. No floor-area screen is possible (gross "
                "floor area is not disclosed, unlike Urbana #1327 / Troy-Piqua #1482 / Bowling Green "
                "#1435). Replace with the disclosed load when an OEPA air PTI, a PJM interconnection "
                "filing, or the AEP Ohio load contract (PUCO tariff 24-508-EL-ATA) surfaces it; the "
                "AEP Ohio Transco Van Wert-Haviland 138 kV LON (OPSB 25-0697-EL-BLN, $45M, in-service "
                "Dec 2026) is a [reference] transmission signal whose stated need is generic (#1401)."
            ),
            # No disclosed gensets or air permit (site-plan-grounded) → the N+1 backup cross-check and the
            # air-dispatch fleet model are absent; QTS states the generators are emergency backup only
            # (tested monthly) and no facility-specific PTI was found (#1408).
            facility_type=(
                'hyperscale data-center campus ("Van Wert Mega Site"; end user/operator QTS Data Centers '
                "(QTS Realty Trust, LLC — Blackstone); developer of record Thor Equities Group via "
                "Form8tion; land-holding entity QTS Van Wert LLC)"
            ),  # [verified] operator/developer; [reference] land-holding LLC (pending deed/SOS pulls, #1404)
            # gross_floor_area_sqft NOT disclosed → left None (up to 7 buildings; no floor area on record).
            disclosed_investment_usd=10_000_000_000,  # [verified] ~$10B total capital investment (QTS; all outlets)
            disclosure_citation=(
                "[verified] QTS Data Centers publicly named as the Van Wert Mega Site end user/owner on "
                "2026-05-29 (q.com/data-centers/van-wert; Data Center Dynamics; VW Independent 2026-05-29; "
                "corroborated by Toledo Blade, WANE): a ~$10B campus on 902 ac of the ~962 ac annexed by "
                "the City on 2026-05-11 (emergency ordinances, 6-0 — annexed + zoned I-2 General "
                "Industrial with conditional data-center use), up to 7 buildings, ~200 permanent "
                "full-time jobs (>1,500 construction), groundbreaking Q4 2026, first building operational "
                "Q1 2029, buildout ~2032. Land assembled by Thor Equities / Form8tion from the Marsh "
                "Foundation (~221-ac initial buy Aug 2025, anchor parcel 170347180100). Gross floor area "
                "is NOT disclosed (left None). End-use [verified] (public disclosure by the named "
                "operator); ingesting the naming annexation/site-plan instrument set is #1401's job. See "
                "data/extracted/van-wert/data-centers.md."
            ),
            # Cooling archetype (#1054): CLOSED_LOOP_DRY recorded as the operator's [reference] claim —
            # the same closed-loop pattern that undercut the Urbana water thesis (#1327), not a document
            # extraction. The initial-fill volume + still-negotiated water/sewer carry an [open]
            # discrepancy tracked at the water-service / leads sub-issues, not decided here.
            cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] operator/developer claim (NOT instrument-confirmed): closed-loop cooling "
                "(Danfoss-patented equipment); QTS states the campus 'does not consume water for cooling "
                "once operational', characterizing ongoing use as 'about what 4 households use per month' "
                "(q.com/data-centers/van-wert; vanwert.org/water-treatment). Same closed-loop pattern that "
                "undercut the Urbana water thesis (#1327). Carries an [open] discrepancy on the initial "
                "closed-loop fill (~660,000 gal from the City of Van Wert — local press frames it "
                "'annually' while the 2026-06-11 event framed it as a one-time fill); reconciling the fill "
                "volume + the still-negotiated water/sewer service agreement is the water-service "
                "instrument (#1407) / water-contradiction lead (#1409), not this pin. B2 (#1682) ran the "
                "A3 cooling-cycling reconciliation harness (`watermark cooling-reconcile`) on this claim: "
                "with no metered makeup (A1 built no Van Wert County withdrawal) and no facility-own "
                "blowdown (A2 OHD000001 draft), the outcome is a `gap` that KEEPS this [reference] pin — "
                "the ~660k gal figure is a single-source self-report, not an instrument, so it can "
                "neither upgrade the source nor re-archetype; the initial-fill open quantity is sharpened "
                "into a C2 records request (#1688/#1409). Replace with a "
                "documented cooling design when an NPDES/mechanical instrument lands (the OHD000001 draft "
                "data-center general permit is not yet linked to the facility by name, #1408)."
            ),
        ),
    ),
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
    facilities=(),  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
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
    facilities=(),  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
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
    facilities=(),  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
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
    # shared national NFHL; zoning is a searched negative — the Village publishes none (see below).
    parcels_url=(  # [verified] Putnam County GIS — Parcels layer 0 (auditor CAMA + geometry)
        "https://putnamcountygis.com/arcgis/rest/services/Parcels/Parcels/MapServer/0"
    ),
    # [open] SEARCHED AND NEGATIVE, not undiscovered (#1420, 2026-07-31). The Village publishes
    # NO zoning GIS of any kind: its ordinances are text-only on American Legal
    # (codelibrary.amlegal.com/codes/ottawa/latest/ottawa_oh/), its own site offers no mapping
    # application, and an ArcGIS Online org search for Putnam/Ottawa zoning returns four items,
    # none of them zoning (an Indiana DNR flood layer, a county drainage web map, and two ODNR
    # download links). The county's own ArcGIS server publishes only Parcels, Sections and an
    # Ottawa water-utility folder. Its /services/Zoning path answers `499 Token Required`, but so
    # does a folder name that certainly does not exist — 499 is this server's generic reply to any
    # unlisted path, so it is NOT evidence a secured zoning service exists. The posture is also
    # IN FLUX and dated: the Village issued a Request for Proposals for "Zoning, Development, and
    # Related Regulatory Code Modernization Services" on 2026-06-23 (questions due 2026-07-14,
    # proposals due 2026-08-04 16:00; ottawaohio.us/DocumentCenter/View/3308), so the code itself
    # is under active procurement to be rewritten. Re-check after that award, not before.
    zoning_url="TODO",
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=PUTNAM_PARCEL_SCHEMA,  # [verified] Putnam County Parcels (owner + CAMA values; #420)
    gis_zoning=None,  # [open] no Village of Ottawa zoning layer exists to wire — see zoning_url
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "ottawa-gis"}),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Ottawa ~84.05 degW; zone 16 spans 90-84 degW)
    # stormwater (the Atlas-14 corridor point = village centroid; cover scenario from the campus)
    design_lat=41.0192,  # [verified] village centroid = NOAA Atlas-14 point
    design_lon=-84.0472,
    corridor_name="Lower Blanchard River corridor",  # [inference] the receiving-water reach below Findlay
    # [verified] SSURGO over the committed campus assemblage (#1420) — and it CORRECTS the prior
    # [inference] D by one notch. The geology the inference reasoned from is right (Great Black
    # Swamp lake plain) but the series it named are not the ones under this ground, and NRCS rates
    # the ones that are as the DUAL group C/D, not flat D. Recorded verbatim per WS-20/#1620 so
    # pre_/post_drainage_condition resolve it rather than the profile pre-collapsing a letter.
    dominant_hsg="C/D",
    hsg_citation=(
        "Former Philips/Sylvania CRT campus, 700-804 N Pratt St — SSURGO dominant hydrologic soil "
        "group C/D at 22 of the 23 RATED grid points over "
        "data/reference/ottawa/parcel-assemblage.geojson "
        "(watermark.hydrology.connectors.ssurgo.dominant_hsg, grid_n=8, read 2026-07-31): Toledo "
        "silty clay loam (10 points) + Fulton silty clay loam 2-6% (7) and 0-2% (5); the lone C "
        "point is Lucas silty clay loam 6-12%, moderately eroded. The same answer comes back "
        "unanimously on two coarser grids — the onboard default grid_n=6 (14 of 14 rated points) "
        "and grid_n=4 (5 of 5). Great Black Swamp lake-plain soils, as the prior "
        "[inference] read them — but Toledo/Fulton, not the Hoytville/Latty/Paulding it named, and "
        "NRCS rates these C/D: C where drainage is installed and maintained, D in the natural "
        "undrained condition. CAVEAT, and it is the point of the site: 36 of the 59 grid points "
        "(61%) return NO rated component because they map to URBAN LAND — the built-over plant. "
        "So this group describes the campus's unbuilt remainder, and a runoff model driven by it "
        "is modelling the soil under a site that is already largely impervious. CORROBORATED "
        "independently by the county's own per-parcel soil split (Land_Features/LandUseParcels, "
        "by area): Urban land 57.7% of 38.257 ac, then Toledo/Fulton/Lucas — the same map units, "
        "and 700 N Pratt alone is 91.4% Urban land. "
        "See data/extracted/ottawa/bosc-site-footprint.yaml (dominant_hsg)."
    ),
    # [verified] The pre-development cover here is DEVELOPED, not farmland — this is a brownfield,
    # not a greenfield, and two independent sources say so: the auditor's use code is 350
    # (industrial/manufacturing) with standing building value on both parcels, and SSURGO maps 61%
    # of the campus as Urban land. That makes pre_cover == post_cover, and the equality is the
    # FINDING, not an unfilled knob: redeveloping this campus adds no new impervious area at
    # screening grade, unlike every greenfield site in the network. The measured impervious
    # FRACTION is still [open] — no site plan, Rule-5 SWPPP or floor area is in the corpus (#1421)
    # — so these stay screening-grade NLCD proxies (24 high-intensity / 21 developed open space).
    pre_cover="developed_campus",
    post_cover="developed_campus",
    developed_pervious_cover="open_space",
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
    # [verified] committed #1420 — the two contiguous parcels the former Sylvania/GTE/Philips
    # Display Components CRT campus was subdivided into and sold as in 2006 (38.234 ac CAMA /
    # 38.293 ac planar) + the footprint record derived from them. This is the site's anchor PLACE,
    # a FORMER industrial works — NOT a data-center campus (facilities=() below is not an omission).
    parcels_relpath="reference/ottawa/parcel-assemblage.geojson",
    footprint_relpath="extracted/ottawa/bosc-site-footprint.yaml",
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
    # balance — the Ottawa WWTP fact sheet is now committed (#1422, closing the #415 pull).
    # Findlay↔Ottawa intra-tributary comparison (#417): the Ottawa WWTP (OH0026921, 3.0 MGD →
    # 4.64 cfs) screens TIGHT against the shared derived Blanchard 7Q10 (8.67 cfs, USGS 04189000;
    # low-flow-7q10.derived.yaml, #414) at 0.54x, and TIGHT again at 0.60x against Ohio EPA's own
    # 7.78 cfs — the band does not turn on the choice here, unlike at Findlay. Its upstream sibling
    # screens VIOLATION on either basis. The outfalls are 34.32 river miles apart (RM 56.42 vs
    # RM 22.1), now cited to both fact sheets rather than estimated. See the committed artifact
    # data/reference/network/findlay-ottawa-comparison.yaml, whose `regulatory_denominators` block
    # carries the derived and regulatory values side by side and prefers neither.
    plant_receiving={
        "ottawa-wwtp": (
            "Blanchard River at River Mile 22.1",
            "Ohio EPA NPDES fact sheet 2PD00028*PD (data/documents/oepa/ottawa/2PD00028.fs.pdf), "
            "p. 6 — outfall 2PD00028001, HUC 04100008-06-02, Ohio EPA river code 04-160; Table 12 "
            "(p. 28) annual 7Q10 7.78 cfs / 1Q10 5.42 cfs / 90Q10 21.66 cfs / harmonic mean "
            "55.13 cfs (USGS gauge 04189500 at Glandorf, 1921-1951, drainage-adjusted), design "
            "flow 4.6417 cfs, acute dilution ratio 2.2 (p. 11) — "
            "data/extracted/oepa/ottawa/2PD00028.fs.npdes.yaml",
        ),
    },  # [verified: OEPA 2PD00028*PD fact sheet]. Key is the future watch-item id (#829) — Ottawa
    # has no committed watch-items.geojson yet, so the routed balance does not read this entry; it
    # is the cited datum of record until that file lands, and the two must match then.
    abstraction_gage="04189260",  # [inference] the Blanchard-at-Ottawa receiving-reach gage
    # refill (the water-balance supply model is not yet designed for Ottawa)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility (no identified data-center facility → grid backdrop only, no campus share)
    # [verified] SWEPT AND NEGATIVE, not unfilled (#1423, 2026-07-31). This empty tuple is a
    # FINDING with a register behind it — data/extracted/ottawa/data-centers.md — not a knob nobody
    # got to. Six record systems were queried record-by-record: PJM's public planning queue (9,263
    # projects; 9 in Putnam, ALL generation, all wind/solar, nothing above 138 kV — and note the
    # queue carries no load-interconnection project type at all, so it corroborates without being
    # dispositive, and its SubmittedDate frontier is 2025-06-03); the ODJFS WARN lists for 2024,
    # 2025 and 2026 (241 notices, ONE Putnam hit and it is a CLOSURE — RK Industries, 725 N Locust
    # St, 80 jobs, ceasing 2024-07-14, notice 007-24-042); EPA ECHO ICIS-Air (33 county facilities,
    # 3 majors, ZERO NAICS 518210, no genset bank); ECHO CWA (48 permits, 14 active construction
    # NOIs, every one a road/utility/municipal job); RSEI v234 (14 TRI reporters, no 518210); and
    # BLS QCEW 2023 (Information LQ 0.21 on 50 jobs vs Manufacturing LQ 3.72). The county's own
    # SB 52 blanket restriction (Sept 2023) capped its pipeline at two grandfathered solar projects,
    # and the sharper fact is that one of them — Blue Harvest, 49.9 MW, in service 2023-11-22 —
    # sells its output to AMAZON/AWS: Putnam exports to the build-out it does not host. Do NOT
    # scaffold a facility here to light up the readiness domain; the lock is the answer. ⚠️
    # Disambiguation: Putnam County, WEST VIRGINIA has a live multibillion-dollar Google campus
    # (~1,700 ac at Buffalo, announced March 2026) and owns the obvious search terms — it is not
    # this county. One check stays [open]: the paywalled Toledo Blade article of 2025-12-13.
    facilities=(),  # [verified] no disclosed facility — see data/extracted/ottawa/data-centers.md
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
    # OEPA permit registry — what `watermark oepa discover` annotates as "known" (#844).
    npdes_permits=["2PD00028"],  # Village of Ottawa WWTP / application OH0026921
    # Corpus scope (#762/#780/#1505/#1405). Ottawa's worked record spans two collections: its own
    # `ottawa/` tree (the standing water watch and the drinking-water instruments — the SDWA half
    # of this site's story) and the site-scoped OEPA sub-collection `oepa/ottawa/` holding the
    # 2PD00028 instrument set (the CWA half). Both are eponymous, so `_eponymous_prefixes` grants
    # them and subtracts them from Lima's reference-build scope with no entry here.
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
# IT load is undisclosed → a floor-area SCREENING bracket off the disclosed 460k sq ft
# (watermark.facility.screening, the single home for the 75-250 W/sq ft band — #1641 D2).
_URBANA_LOAD = floor_area_screen(460_000)
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
    dominant_hsg="C",  # [verified] SSURGO area-weighted survey over the committed site assemblage (was [inference] B)
    hsg_citation=(
        "[verified] USDA NRCS SSURGO via Soil Data Access, 30-point grid sample over the committed "
        "Urbana Technology Hub assemblage (reference/urbana/parcel-assemblage.geojson; "
        "watermark.hydrology.connectors.ssurgo.dominant_hsg, grid_n=8, 2026-07-08): C 47% + C/D 33% "
        "+ B 20% -> drained-basis HSG C. This CORRECTS the prior [inference] of HSG B: the deep Mad "
        "River buried-valley aquifer (glacial outwash sand & gravel, a US-EPA sole-source aquifer "
        "feeding the Springfield/Dayton/Wright-Patterson AFB corridor) is well-drained, but the "
        "SURFACE till/lacustrine soils governing the runoff CN across this specific site are "
        "dominantly the C/C-D units (consistent with the Vance Brands 401 approved-JD soil list). "
        "See data/extracted/urbana/bosc-site-footprint.yaml (dominant_hsg)."
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified site
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    # corpus scope (#762): Urbana's committed corpus doesn't live under a `urbana/` collection —
    # it's the Highland55 land-assembly permit bundle (permits/highland55, the Thor §401 WQC /
    # Corps JD instruments, PR #803) and the City-of-Urbana OEPA/NPDES record (oepa/urbana). Scope
    # to those two prefixes plus the slug so the bundle's documents/timeline feeds carry Urbana's
    # actual record (flips the `record` readiness domain live) — never Lima's Allen-County tree.
    # `legal/thor-v-urbana` joins them (#1724): the filed federal complaint (S.D. Ohio
    # 3:26-cv-00196) is the legal spine of THIS site's dispute and the source of its
    # `litigation-thor-v-urbana.yaml` read, but it sat outside every peer prefix — so Lima's
    # whole-tree-minus-peers scope swallowed it and Urbana's own document catalog didn't carry
    # the instrument its record cites. Naming it here moves it in both directions at once
    # (#1505), because Lima's exclusion set IS the union of the peers' scopes.
    # `urbana` and `oepa/urbana` are eponymous and derived (#1405); only the two project-/case-named
    # collections need naming here.
    corpus_relpaths=("permits/highland55", "legal/thor-v-urbana"),
    parcels_relpath="reference/urbana/parcel-assemblage.geojson",  # [verified] 4 parcels / 3 Thor SPEs / ~230 ac (#1326)
    footprint_relpath="extracted/urbana/bosc-site-footprint.yaml",  # [verified] recorded ownership assemblage (#1326)
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
    # Source-water / abstraction screen (#441 self-research). RE-SCOPED (#1330): these fields are a
    # REACH-LEVEL screen — valid for the Mad River sole-source buried-valley aquifer generally, and
    # for any future high-water abstractor — but they are NOT the binding constraint for the disclosed
    # Urbana Technology Hub facility, which uses CLOSED-LOOP cooling (water "comparable to a standard
    # office building", see facility.cooling_model below). For THAT facility the binding constraint is
    # grid/power (end-user-funded transmission upgrades, AES Ohio / PJM DAY) + land use, not consumptive
    # cooling draw. Retained, not deleted — the abstraction thesis still holds for the aquifer at large.
    abstraction_gage="03267000",  # [verified] Mad River near Urbana OH
    supply_gage_primary="03267000",  # [verified] Mad River near Urbana
    supply_gage_secondary="03267900",  # [verified] Mad River at Eagle City (downstream)
    # [verified] Regulatory annual 7Q10 = 35 cfs at USGS 03267000 (Mad River near Urbana),
    # from the Ohio EPA NPDES fact sheet for permit 1PD00011 (OH0027880) — Stream Flows table,
    # source "USGS gage 03267000, 1997 flow document". This is the design low flow OEPA uses
    # for the Mad River wasteload allocation; it supersedes the earlier [derived] LP3 value
    # (53.67 cfs, 1980-2024). The 2025-cycle renewal (app eDoc 3832476, filed 2025-05-29) had
    # not issued as of the 2026-07-10 re-check (#1355) — OEPA doc library still serves the 2020
    # issuance byte-identical, ECHO reports the permit "Expired" — permit in administrative
    # continuance past its 2025-11-30 expiry, so the 2020 fact sheet (corpus:
    # oepa/urbana/1PD00011.fs.pdf) is the effective instrument. Re-verify this passby if/when the
    # renewal issues and its fact sheet revises the 7Q10.
    passby_primary_cfs=35.0,
    passby_secondary_cfs=0.0,  # [open]
    # facility CONFIRMED (#1327) — the "Urbana Technology Hub" data-center campus, corner of
    # SR-55 & US-68, disclosed at the Feb-2026 City of Urbana meeting + the Feb-2026 site-plan
    # application (developer Thor Equities via Form8tion / Urbana Owner I LLC + Highland55
    # Investments LLC). This RESOLVES the corpus's central [open] "is Highland55 a data center?"
    # question. This is a SITE-PLAN-grounded facility, not an air-permit one: the disclosed
    # non-power attributes (type / 460k sqft / ~$1B / closed-loop cooling / AES Ohio serving)
    # are populated, but the MW load is NOT disclosed — it is a floor-area SCREENING bracket
    # ([inference], see it_load_citation), never presented as a disclosure. The disclosed
    # interconnection/air-permit MW stays [open] (a tracked #1263 sub-lead: PJM queue position,
    # air permit). See data/extracted/urbana/datacenter-facility.md.
    facilities=(
        SiteFacility(
            name="Urbana Technology Hub",
            status=FacilityLifecycle.CONFIRMED,  # disclosed Feb 2026; MW load still [open] (#1327/#1353)
            operator="Thor Equities Group (developer of record)",
            operator_citation=(
                "[reference] Disclosed at the Feb-2026 City of Urbana meeting + site-plan application "
                "(Urbana Daily Citizen 2026-02-18; DataCenterDynamics) — Thor Equities' 460,000 sq ft "
                "Urbana Technology Hub campus."
            ),
            # end_use left [open] — a Thor-developed campus whose ultimate tenant/workload is undisclosed
            # (the naming site-plan/permit instrument was not reachable to ingest, #1263).
            it_load_mw=_URBANA_LOAD.central,  # [inference] SCREENING central (MW-midpoint); see it_load_citation
            it_load_low_mw=_URBANA_LOAD.low,  # 460k sqft x 75 W/sqft whole-building IT density (low)
            it_load_high_mw=_URBANA_LOAD.high,  # 460k sqft x 250 W/sqft whole-building IT density (high)
            it_load_source=ItLoadGrounding.SCREENING,
            it_load_citation=(
                "[inference] SCREENING bracket — NOT a disclosure; the disclosed interconnection/"
                "air-permit MW is [open] (#1263 sub-lead: PJM queue position / air permit). Derived "
                "from the disclosed 460,000 sq ft gross floor area (Urbana Technology Hub site-plan "
                "application, Feb 2026) x a whole-building IT power-density band of 75-250 W/sq ft "
                "(stated screening assumption): ~34.5 MW low, ~74.8 MW central (MW-midpoint), 115 MW "
                "high (watermark.facility.screening — #1641 D2). The "
                "single-story ~40 ft form factor + the disclosed CLOSED-LOOP DRY cooling ('water use "
                "comparable to a standard office building') argue against the max-density liquid-AI "
                "archetype, so the band is bounded well below GB200-class rack densities. Replace with "
                "the disclosed load when a PJM interconnection application or an air permit surfaces it. "
                "RETAINED after a documented NEGATIVE search (#1353, 2026-07-10): the AES Ohio (Dayton) "
                "PJM TEAC large-load customer requests name Piqua/Adams/Marysville/Tipp City/"
                "Jeffersonville/Wilmington — NOT Champaign County/Urbana; the only Champaign PJM-queue "
                "item is Woodstock Solar AE2-342 (40 MW, withdrawn); and US-EPA ECHO ICIS-AIR shows no "
                "campus air permit at the SR-55/US-68 site (7 pre-existing Urbana sources only). No MW "
                "was disclosed at the Feb-2026 city meeting; no figure fabricated. NB: the 100 MW->1.3 GW "
                "AES Ohio figure is ADAMS COUNTY (Stuart substation) and the ~500 MW figure is Thor's "
                "VAN WERT campus — neither is Urbana. Full record: "
                "data/extracted/urbana/facility-power-instrument-search.md."
            ),
            # No disclosed gensets or air permit (site-plan-grounded) → genset/backup basis and the
            # air-dispatch fleet model are absent; genset_count/genset_mw/air_permit_citation stay None.
            # Confirmed still None by the #1353 negative air-permit search (ECHO ICIS-AIR, 2026-07-10).
            facility_type="data-center campus (Urbana Technology Hub)",  # [reference]
            gross_floor_area_sqft=460_000,  # [reference] disclosed site plan — 460k sqft, single-story, ~40 ft
            disclosed_investment_usd=1_000_000_000,  # [reference] ~$1B disclosed investment
            disclosure_citation=(
                "[reference] Disclosed at the Feb-2026 City of Urbana meeting + the Feb-2026 site-plan "
                "application; Urbana Daily Citizen 'Data center plans revealed at city meeting' "
                "(2026-02-18); DataCenterDynamics 'Thor Equities ... 460,000 sq ft data center campus "
                "near Urbana'. End-use [reference] (public disclosure), not yet [verified] — the naming "
                "site-plan/permit instrument was not reachable to ingest from this build env (#1263)."
            ),
            # Cooling archetype (#1054): CLOSED_LOOP_DRY — the key water-thesis finding. The developer
            # disclosed closed-loop cooling with 'water use comparable to a standard office building',
            # which undercuts the Mad River water-abstraction thesis. [reference], not a document extraction.
            cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] Closed-loop cooling disclosed at the Feb-2026 City of Urbana meeting — "
                "developer stated water use 'comparable to a standard office building' (Urbana Daily "
                "Citizen 2026-02-18). Undercuts the buried-valley water-abstraction thesis. Not a "
                "document extraction; refine to [verified] on an ingested mechanical/plumbing permit."
            ),
        ),
    ),
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
    # 5C Data Centers USA / Vultr "CMH01" at PrimeOhio Corporate Park — the facility domain (#1412).
    # FAQ-grounded (as Urbana #1327 is site-plan-grounded / Sidney #1378 investment-grounded): the
    # City of Springfield 5C FAQ + JobsOhio DISCLOSE a max load, a footprint and an investment, but
    # no air permit is pinned yet — that's #1414, which upgrades the grounding mode and fills the
    # genset/air fields. The IT load is therefore a DISCLOSURE-anchored bracket, not a permit figure:
    # it_load_citation grounds it and the disclosed interconnection/air-permit MW stays [open].
    facilities=(
        SiteFacility(
            name='5C Data Centers "CMH01"',
            status=FacilityLifecycle.CONSTRUCTION,  # "under construction" (5C FAQ / JobsOhio)
            operator="5C Data Centers USA, Inc. (anchor tenant Vultr)",
            operator_citation=(
                "[verified] City of Springfield 5C FAQ (springfieldohio.gov/5c-data-center-faqs) — 5C "
                "Data Centers USA, Inc., anchor tenant Vultr, 601 Benjamin Drive, PrimeOhio Corporate Park."
            ),
            end_use=DcEndUse.COLOCATION,
            end_use_citation=(
                "[verified] colocation — 5C Data Centers is the landlord/operator that builds and "
                "powers the hall; its anchor TENANT Vultr owns and runs the compute (a named tenant, "
                "not an owner-operated hyperscale campus). City of Springfield 5C FAQ."
            ),
            it_load_mw=100.0,  # central = midpoint of the disclosed 50->150 MW corridor; NOT the 900 MW buildout
            it_load_low_mw=50.0,  # [verified] disclosed first tranche — 50 MW / 24,000-GPU AMD MI355X supercluster (2025-12)
            it_load_high_mw=150.0,  # [verified] disclosed "up to 150 MW max load" ceiling (City of Springfield 5C FAQ)
            it_load_source=ItLoadGrounding.REFERENCE,
            it_load_citation=(
                "[verified/inference] DISCLOSURE-anchored bracket — NOT an air-permit figure (the "
                "disclosed interconnection/air-permit MW stays [open] until the Ohio EPA Air PTI lands, "
                "#1414). Anchored on two disclosed hard figures: the City of Springfield 5C FAQ "
                "'up to 150 MW max load' (springfieldohio.gov/5c-data-center-faqs) as the HIGH, and the "
                "announced first tranche — a 50 MW / 24,000-GPU AMD MI355X supercluster (2025-12) — as "
                "the LOW; the 100 MW central is the midpoint of that disclosed 50-150 MW corridor. The "
                "register (data/extracted/springfield/data-centers.md, hydrology hook) treats the 150 MW "
                "max as the IT-load screening input. The ~900 MW ultimate buildout (datacentermap "
                "facility 'CMH01') and the 75/200 MW interim-phase figures are [open] — unconfirmed by "
                "any primary instrument and DELIBERATELY EXCLUDED from this band; the air permit settles "
                "the stack. Crusoe (75 MW, parcel undisclosed) is a SEPARATE register and is not blended "
                "in. Replace with the disclosed load when the Ohio EPA Air PTI or a PJM interconnection "
                "filing names 5C's MW."
            ),
            # No air permit pinned yet (#1414) and no genset figures ingested → genset_count / genset_mw /
            # air_permit_citation stay None: the register's "3 existing + 16 planned diesel gensets" is a
            # FAQ CLAIM, not an extracted permit — #1414 fills these and flips the grounding to a PTI.
            facility_type=(
                'data-center campus (5C Data Centers USA, Inc. / anchor tenant Vultr, "CMH01") — '
                "601 Benjamin Drive, PrimeOhio Corporate Park; under construction"
            ),  # [verified] operator/tenant + site + status
            gross_floor_area_sqft=214_000,  # [verified] buildout footprint (67,000 existing -> 214,000; JobsOhio)
            disclosed_investment_usd=1_300_000_000,  # [verified] up to $1.3B total (Constant Company capital $901.3M/JobsOhio)
            disclosure_citation=(
                "[verified] City of Springfield 5C FAQ (springfieldohio.gov/5c-data-center-faqs) + "
                "JobsOhio (Vultr / The Constant Company, LLC capital $901,311,378) + Springfield "
                "News-Sun (2026-07-10). Operator 5C Data Centers USA, Inc. (parent 5C Group Inc., "
                "Montreal); anchor cloud tenant Vultr (product of The Constant Company, LLC); site the "
                "former LexisNexis data center at 601 Benjamin Drive, PrimeOhio Corporate Park. "
                "Investment up to $1.3B total; footprint 67,000 -> 214,000 sq ft; ~120 FT jobs. Status: "
                "UNDER CONSTRUCTION (Vultr operational target early 2026, full build 'late 2027 if "
                "financing and construction move forward', News-Sun 2026-07-10); no Vultr Ohio "
                "public-cloud region live (api.vultr.com/v2/regions checked 2026-07-10). Enterprise-Zone "
                "counterparty CMH01 Holdings Inc. (SOS pull -> #1413). See "
                "data/extracted/springfield/data-centers.md, 'Project 1'."
            ),
            # Cooling archetype (#1054): CLOSED_LOOP_DRY — the City FAQ discloses closed-loop /
            # direct-liquid recirculating cooling, EXPLICITLY "not evaporative". [reference] disclosure,
            # not a document extraction; the water sub-issue (#1415) owns the discharge / receiving-water
            # screen. blowdown_mgd stays None — the disclosed 300,000 gal/day is a permitted WITHDRAWAL
            # ceiling (~30k gal/day realistic), not a blowdown discharge, so there is no FM-2-style cross-check.
            cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] Closed-loop / direct-liquid recirculating cooling, disclosed 'not "
                "evaporative' by the City of Springfield 5C FAQ (springfieldohio.gov/5c-data-center-"
                "faqs); up to 300,000 gal/day permitted from the municipal system at an >80degF "
                "extreme-heat max ('near zero' most of the year, ~30k gal/day realistic), with an "
                "on-site reservoir under study to avoid the municipal tap. A largely dry recirculating "
                "design undercuts the Mad River buried-valley abstraction thesis. B3 (#1683) ran the A3 "
                "cooling-cycling reconciliation harness (`watermark cooling-reconcile`) on this claim: "
                "with no matching makeup record on file (the Ohio DNR WWFRP water-withdrawal registry has "
                "no Clark County withdrawal pull built) and no matching facility-own discharge record on "
                "file (OHD000001 still draft, unlinked to the facility by name; no facility-specific "
                "NPDES/DMR located) — an absence of records, not evidence of zero use — the outcome is a "
                "`gap` that KEEPS this "
                "[reference] pin. The 300,000 gal/day is a permitted-withdrawal CEILING self-disclosed by "
                "this same FAQ — NOT an independently-negotiated reservation, so (unlike Troy-Piqua B1) "
                "it is not a reservation_conflict: a dry loop sits far below it, and a self-report cannot "
                "corroborate its own claim. The actual metered withdrawal vs the ceiling is sharpened "
                "into a C2 records request (#1688/#1415). Not a document extraction; refine to [verified] "
                "on an ingested mechanical/plumbing permit. The receiving-water / source-water screen is "
                "the water sub-issue (#1415)."
            ),
        ),
    ),
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
    facilities=(),  # [open] the WPAFB-corridor defense/data-center dimension is the research target (#444)
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
# Mad River Buried Valley Aquifer** (US-EPA sole-source, 53 Fed. Reg. 15876 (May 4, 1988), FRL-3369-5
# [verified]) and is the source of a documented **TCE / PFAS groundwater plume** on that same
# drinking-water aquifer (CERCLA §120 FFA; NPL listing 1989-10-04, 54 FR 41021 [verified]). Both were
# to-verify at onboarding; the primary records are now in the corpus (#1397 — data/extracted/wpafb/
# ssa-53fr15876.epa.yaml + cercla-ffa-1991.epa.yaml). The buried-valley supply (not surface
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
        "sand & gravel, a US-EPA designated sole-source aquifer [verified: 53 Fed. Reg. 15876 "
        "(May 4, 1988), FRL-3369-5, SDWA 1424(e); the Dayton municipal + WPAFB production well fields "
        "draw on it - data/extracted/wpafb/ssa-53fr15876.epa.yaml] - so the valley fill is "
        "well-drained HSG A/B, the INVERSE of the Maumee lake-plain Black Swamp clays (HSG D); the "
        "HSG A/B letter itself stays [inference] pending an SSURGO area-weighted confirmation "
        "(onboard SSURGO needs a footprint)"
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
    # facility=None (the DoD-cloud dimension is the #442 research target), so there is no facility
    # to size a demand→price-pressure sensitivity against — the feed is facility-gated and omitted.
    # None (no destination) rather than a dangling path to a file that can never be written (#1660).
    demand_pressure_relpath=None,
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
    # The enclave itself is the facility (#1664). NOT the data-center dimension — the DoD-cloud /
    # GDIT-RSO question stays the open research target (#442) and would be a SECOND, `data_center`
    # facility if it ever lands. What is on the record today is the installation: 8,200 acres, its
    # own two community water systems, its own two NPDES outfalls, and its own Superfund listing.
    # Its electrical load is [open] and stays that way — the base is unmistakably a large power
    # user, which is exactly why no figure may be invented for it.
    facilities=(
        SiteFacility(
            name="Wright-Patterson Air Force Base",
            key="wright-patterson-afb",
            kind=FacilityKind.FEDERAL_INSTALLATION,
            status=FacilityLifecycle.LIVE,  # [verified] MIRTA SITEOPERATIONALSTATUS "Act"
            operator="United States Department of the Air Force",
            operator_citation=(
                "CERCLA §120 Federal Facility Agreement, U.S. EPA Region V and the U.S. Department "
                "of the Air Force, executed 1991-03-31 — data/extracted/wpafb/"
                "cercla-ffa-1991.epa.yaml [verified]"
            ),
            # Pinned `off` because there is no IT load to derive a cooling-water demand from — the
            # base's water is potable supply from its own wells, not condenser cooling. This is a
            # statement about the MODEL's scope, not a disclosure about the base, so it travels as
            # an assumption; the SiteFacility validator requires `off` for a federal installation.
            cooling_model=CoolingModelType.OFF,
            cooling_model_source="assumption",
            cooling_model_citation=(
                "not a data-center facility: a federal installation has no IT-load-driven "
                "cooling-water demand to derive, so the data-center cooling model reports an "
                "explicit zero rather than a bracket. The enclave's actual water is its two "
                "community water systems on the Miami Buried Valley Aquifer — see the "
                "installation record, data/extracted/wpafb/cercla-ffa-1991.epa.yaml"
            ),
            installation=FederalInstallation(
                component="U.S. Air Force",  # [verified] MIRTA SITEREPORTINGCOMPONENT "USAF"
                agency="U.S. Department of Defense",  # [verified] EPA TRI asgn_agency "DOD"
                register_name="Wright-Patterson Air Force Base",
                register_citation=(
                    "DoD MIRTA (Military Installations, Ranges, and Training Areas) site-boundary "
                    "register, FEATURENAME 'Wright-Patterson Air Force Base' (SITEREPORTINGCOMPONENT "
                    "USAF, STATENAMECODE OH) — the authoritative DoD boundary layer, published via "
                    "Esri US Federal Data; boundaries encompass federally owned or otherwise "
                    "managed lands per the Base Structure Report, planning-grade, not a survey "
                    "[connector — watermark federal-land]"
                ),
                record_relpath="wpafb/cercla-ffa-1991.epa.yaml",
                record_citation=(
                    "CERCLA §120 Federal Facility Agreement (U.S. EPA Region V / U.S. Air Force, "
                    "executed 1991-03-31), Findings of Fact: ~8,200 acres in Areas A/C and B over "
                    "the Miami Buried Valley Aquifer; three well fields with 17 drinking-water "
                    "supply wells; five air-stripping units; ≥58 waste-disposal sites; NPL listing "
                    "1989-10-04, 54 Fed. Reg. 41021 [verified]"
                ),
                pwsids=("OH2903412", "OH2903312"),  # Area A, then Area B
                pws_citation=(
                    "EPA SDWIS (Envirofacts water_system) — OH2903412 'WRIGHT-PATTERSON AFB AREA A "
                    "PWS' and OH2903312 'WRIGHT-PATTERSON AFB AREA B PWS', both active community "
                    "water systems on GROUND WATER (the Miami Buried Valley Aquifer of the FFA "
                    "Findings of Fact); cross-referenced from the SDWAIDs on both of the base's "
                    "ECHO NPDES records [connector — watermark enclave]"
                ),
                npdes_permits=("OH0010243", "OH0105422"),
                npdes_citation=(
                    "EPA ECHO CWA facility records — OH0010243 'WRIGHT-PATTERSON AIR FORCE BASE' "
                    "and OH0105422 'U.S. AIR FORCE WRIGHT-PATTERSON AIR FORCE BASE', both "
                    "Effective NPDES individual permits, FacFederalAgencyName 'Defense: Air "
                    "Force', Greene County OH (39057) [connector — watermark enclave]"
                ),
                # [open] — the installation's electrical load and raw-water withdrawal. Neither is
                # disclosed by any instrument in the corpus; the grid stack carries the AES Ohio /
                # PJM DAY backdrop with load_share=None rather than sizing the base.
                tri_facility_id="45433SDDSFDEPAR",
                tri_county_fips="39057",  # GREENE — NOT this site's rsei_fips/econ_fips (39113)
                tri_county_name="Greene County, OH",
                epa_registry_id="110001987958",  # EPA FRS; matches ECHO RegistryID on both permits
                tri_citation=(
                    "EPA TRI facility register (Envirofacts tri_facility): 45433SDDSFDEPAR 'U.S. "
                    "DOD USAF WRIGHT-PATTERSON AFB OH', asgn_federal_ind 'F', asgn_agency 'DOD', "
                    "county GREENE / state_county_fips_code 39057, EPA registry id 110001987958 "
                    "[verified]"
                ),
            ),
        ),
    ),
    # The enclave's own toxics row lives in Greene County (39057) — the county this profile did
    # NOT pick as its economic/RSEI unit — so the county backdrop above misses the base by
    # construction. This second, one-facility reduction reconciles them (#1664).
    enclave_rsei_relpath="reference/rsei/wpafb/enclave.yaml",
    federal_land_relpath="reference/wpafb/federal-land.geojson",
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
    # (NAICS 54) LQ 0.82, Information (NAICS 51) LQ 0.85, neither elevated. That concentration lives
    # in adjacent Greene County (NAICS 54 LQ 2.11), carried by the Xenia baseline (FIPS 39057, #444).
    econ_unit_note=(
        "Economic-unit caveat: Wright-Patterson AFB straddles Greene + Montgomery counties; this "
        "baseline is Montgomery County (39113) — the well-field / TCE-PFAS-plume / Dayton-metro "
        "toxics context. The defense-supplier Professional/Scientific/Technical concentration the "
        "WPAFB thesis rests on is NOT visible in this unit (Montgomery NAICS 54 LQ 0.82, NAICS 51 "
        "LQ 0.85 — neither elevated); it lives in adjacent Greene County (NAICS 54 LQ 2.11), "
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
    ba_code="PJM",  # off the confirmed _UTILITY_GRID map (#3542), so pin the BA (Duke = PJM DEOK) — B2/#1639
    rto_name="PJM Interconnection",
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
    facilities=(),  # [open] the I-75-corridor data-center dimension is the research target (#443)
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
# utility** (AMP member, Great Miami hydro), Troy/Miami County otherwise AES Ohio (DP&L #4922,
# confirmed #830 — and the Klondike campus's disclosed intended long-term utility via a proposed
# 40-yr franchise, first reading only / pending adoption). The site
# also carries a distinct second supply water — the **Stillwater River** (gage 03265000). Both cities
# sit west of the 84 degW meridian, so this is a **UTM 16N** site (like WPAFB / Hamilton-Middletown).
# IT load undisclosed → floor-area SCREENING bracket off the disclosed 700k sq ft (#1641 D2).
_TROY_PIQUA_LOAD = floor_area_screen(700_000)
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
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — county-dominant IOU AND the Klondike campus's disclosed intended long-term utility (40-yr franchise ordinance PENDING adoption, first reading only, #830) [verified]; Piqua muni #15095 (full-form, not 861S) serves the city + construction power — see serving_utility_citation
    parcels_url=(  # [verified] Miami County AGOL parcel_joined layer 0 (auditor CAMA + geometry, #1483)
        "https://services3.arcgis.com/wCWf4EGMg4PzHwzA/arcgis/rest/services/"
        "parcel_joined/FeatureServer/0"
    ),
    zoning_url=(  # [verified] City of Piqua zoning FeatureServer/17 'Code Piqua' (#830); carries the auditor PARCEL id
        "https://services8.arcgis.com/kZPPWTIJ6kOFJTWc/arcgis/rest/services/"
        "Zoning_Districts_public_view/FeatureServer/17"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Troy ~84.20 degW; zone 16 spans 90-84 degW) — NOT zone 17
    gis_parcel=MIAMI_PARCEL_SCHEMA,  # [verified] Miami County AGOL parcel_joined — owner + CAMA (#1483)
    gis_zoning=PIQUA_ZONING_SCHEMA,  # [verified] City of Piqua 'Code Piqua' — form-based code, parcel-join (#830)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "troy-piqua-gis"}),
    design_lat=40.0392,  # [verified] Troy centroid = NOAA Atlas-14 point
    design_lon=-84.2033,
    corridor_name="Upper Great Miami industrial corridor",  # [inference] the Troy-Piqua mainstem reach
    dominant_hsg="C/D",  # [verified] SSURGO dual C/D over the committed footprint (#1483) — see hsg_citation
    hsg_citation=(
        "[verified] USDA NRCS SSURGO via Soil Data Access, 8x8 grid (48 interior points) over the "
        "committed campus footprint (data/reference/troy-piqua/parcel-assemblage.geojson), 2026-07-13: "
        "C/D 47 pts (97.9%) + C 1 pt (2.1%) -> the DUAL hydrologic soil group C/D, carried verbatim. "
        "Drained (the tile-drained CAUV cropland now on the ground) it runs as C; undrained — the "
        "natural condition, and the basis for developed ground that severs the tile — it runs as D "
        "(WS-20 / #1620 resolves which per scenario; this profile no longer pre-collapses it to the "
        "drained C, which understated post-development runoff over 98% of the footprint). This also "
        "CORRECTS the prior [inference] of HSG 'B': the deep Great Miami Buried Valley Aquifer "
        "(glacial outwash sand & gravel, a US-EPA sole-source aquifer the Troy/Piqua well fields "
        "draw on) is well-drained, but the SURFACE till/lacustrine soils that govern the runoff CN "
        "across this Farrington-Rd footprint are the C/D units - the same surface-vs-aquifer "
        "correction found at Urbana (B->C). Full survey in "
        "data/extracted/troy-piqua/bosc-site-footprint.yaml (dominant_hsg)."
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
    # [verified footprint-anchored / inference extent] (lat_min, lat_max, lon_min, lon_max) — set
    # once the committed campus footprint landed (#1483, deferred from #1481). Anchored on the J5
    # "Project Klondike" campus (data/reference/troy-piqua/parcel-assemblage.geojson, lat
    # 40.104-40.124 / lon -84.259 to -84.242) and extended NE to span the Piqua Great-Miami
    # manufacturing reach — the RSEI water-relevant cluster (Hobart Brothers filler-metals 40.161/
    # -84.232, Copperweld 40.166/-84.222, French Oil 40.150/-84.255, Hartzell 40.141/-84.269) and
    # the Piqua WWTP receptor. Miami County's RSEI water_pounds are all 0, so the box frames the
    # corridor for the map, not an active water-discharge screen.
    toxic_corridor_bbox=(40.104, 40.168, -84.272, -84.221),
    plant_receiving={
        "piqua-wwtp": (
            # Receiving water named "Upper Great Miami River" (not bare "Great Miami River")
            # so the assimilative screen (watermark.hydrology.assimilative) resolves the
            # reach-specific cited 7Q10 in low-flow-7q10.yaml ("upper great miami river",
            # 24.0 cfs) instead of the bare "great miami river" key, which is the basin-screen's
            # derived Hamilton mainstem proxy (407.67 cfs) and must not stand in for this reach.
            # HUC-8 05080001 = Upper Great Miami (ECHO FRS 110000578919). (#829)
            "Upper Great Miami River",
            # OEPA NPDES 1PD00008 / App. OH0027049 (Piqua WWTP), fact sheet Public Notice
            # 22-006-011 (2022-06-21) — extracted/oepa/troy-piqua/1PD00008.fs.npdes.yaml + …/1PD00008.npdes.yaml.
            # Outfall 001 → Great Miami River (→ Ohio River; HUC-8 05080001); average design flow
            # 8.7 MGD (13.46 cfs), peak hydraulic 22.5 MGD. WLA basis (fact-sheet Stream Flows,
            # printed p.28): GMR above Sidney 7Q10 = 24.0 cfs annual (USGS #03261500, 1927-2021).
            # Reported 2023 actual mean 3.224 MGD (37.1% of design, 0 CSO/exceedances) —
            # data/extracted/troy-piqua/wwtp-oh0027049.dmr.yaml [verified — OEPA fact sheet + ECHO DMR].
            "OEPA NPDES 1PD00008 (OH0027049, Piqua WWTP) → Great Miami River; design 8.7 MGD, "
            "actual ~3.224 MGD (2023 DMR); fact-sheet 7Q10 24.0 cfs (GMR above Sidney, USGS 03261500) "
            "— data/extracted/oepa/troy-piqua/1PD00008.fs.npdes.yaml [verified]",
        ),
    },
    abstraction_gage="03262700",  # [verified] Great Miami River at Troy OH
    supply_gage_primary="03262700",  # [verified] Great Miami River at Troy
    supply_gage_secondary="03262500",  # [verified] Great Miami River at Piqua (the upstream reach)
    # [derived] LP3 7Q10 at USGS 03262700 (Great Miami River at Troy OH, 44 yr 1980-2024) —
    # conservative abstraction screen floor and the receiving-reach denominator for the Troy/Piqua
    # WWTP assimilative screen. The Piqua WWTP fact sheet (1PD00008, #828) is now in-corpus; its
    # WLA cites a GMR-above-Sidney 7Q10 of 24.0 cfs at USGS 03261500 (upstream of the Piqua outfall),
    # the conservative regulatory receptor — the Troy-gage LP3 value below stays the local passby floor.
    passby_primary_cfs=44.75,
    passby_secondary_cfs=0.0,  # [open] Great Miami at Piqua (03262500) daily record starts 2012 (<20 yr) — no derived 7Q10; passby pending
    # facility CONFIRMED (#1482) — "Project Klondike" (J5 LLC dba Shaytura LLC), Piqua I-75
    # Business & Industrial Park, disclosed on the City of Piqua's project page + approved by
    # the Piqua City Commission 4-0 on 2025-11-03. This is a SITE-PLAN-grounded facility, not an
    # air-permit one (contrast Lima / Fort Wayne): the disclosed non-power attributes (type /
    # 700k sqft / ~$1B) are populated, but the MW load is NOT disclosed — it is a floor-area
    # SCREENING bracket ([inference], see it_load_citation), never presented as a disclosure.
    # cooling_model stays UNKNOWN (deliberately not picked) — the City's closed-loop FAQ and the
    # 2.0 MGD water-agreement reservation conflict, and resolving that tension is #1486's job,
    # not this one. See data/extracted/troy-piqua/data-centers.md.
    facilities=(
        SiteFacility(
            name="Project Klondike",
            status=FacilityLifecycle.CONFIRMED,  # approved 4-0 2025-11-03; MW load still [open] (#1482)
            operator="J5 LLC dba Shaytura LLC (developer of record)",
            operator_citation=(
                "[verified] City of Piqua project page (piquaoh.gov/1673); approved by the Piqua City "
                "Commission 4-0 on 2025-11-03. Developer of record J5 LLC dba Shaytura LLC; the Meta "
                "attribution is [reported], not confirmed."
            ),
            # end_use left [open] — the developer of record is J5 LLC/Shaytura; the end user (Meta) is
            # [reported] only, so the workload archetype is not on the record.
            it_load_mw=_TROY_PIQUA_LOAD.central,  # [inference] SCREENING central (MW-midpoint); see it_load_citation
            it_load_low_mw=_TROY_PIQUA_LOAD.low,  # 700k sqft x 75 W/sqft whole-building IT density (low)
            it_load_high_mw=_TROY_PIQUA_LOAD.high,  # 700k sqft x 250 W/sqft whole-building IT density (high)
            it_load_source=ItLoadGrounding.SCREENING,
            it_load_citation=(
                "[inference] SCREENING bracket — NOT a disclosure; the disclosed interconnection/"
                "air-permit MW stays [open] (a direct OEPA eSuite/DAPC search for 'J5 LLC' / "
                "'Shaytura LLC' / the Farrington Road address found no PTI filing, confirmed-negative "
                "as of 2026-07-11). Derived from the disclosed 700,000 sq ft gross floor area (two "
                "~350,000 sq ft buildings; City of Piqua project page piquaoh.gov/1673, approved by "
                "the Piqua City Commission 4-0 on 2025-11-03) x the same whole-building IT "
                "power-density screening band used elsewhere in the network (75-250 W/sq ft, the "
                "Urbana Technology Hub precedent, #1327): 52.5 MW low, ~113.8 MW central (MW-midpoint), "
                "175 MW high (watermark.facility.screening — #1641 D2). Unlike Urbana, this band is "
                "NOT bounded by a disclosed cooling design — the "
                "facility's cooling_model stays UNKNOWN pending #1486 (the unreconciled closed-loop-"
                "FAQ-vs-2.0-MGD-water-agreement conflict). A candidate-site tracker (ryangrissinger.com, "
                "OH-DC-0028) reports ~180 MW peak IT for the initial two buildings — [reported], not "
                "officially disclosed (the City page and Data Center Dynamics state capacity figures "
                "'weren't shared') — sitting just above (~3%) the top of this screening bracket, "
                "within the screening estimate's uncertainty (a ~3% gap, not rounding), not a "
                "reconciliation. Replace "
                "with the disclosed load when the 40-yr AES Ohio franchise ordinance's load schedule, "
                "an air permit, or a PJM interconnection filing surfaces it."
            ),
            # No disclosed gensets or air permit (site-plan-grounded) → genset/backup basis and the
            # air-dispatch fleet model are absent; genset_count/genset_mw/air_permit_citation stay None.
            facility_type='data-center campus ("Project Klondike"; developer of record J5 LLC dba Shaytura LLC)',  # [verified]
            gross_floor_area_sqft=700_000,  # [verified] two ~350,000 sq ft buildings
            disclosed_investment_usd=1_000_000_000,  # [verified] "$1 billion plus" fixed-asset investment
            disclosure_citation=(
                "[verified] Disclosed on the City of Piqua's official project page "
                "(piquaoh.gov/1673/Data-Center-Project); approved by the Piqua City Commission 4-0 on "
                "2025-11-03 (emergency resolution, three readings waived); Data Center Dynamics 'Data "
                "center project coming to Piqua, Ohio'; Miami Valley Today commission coverage. Two "
                "~350,000 sq ft buildings (~700,000 sq ft total), '$1 billion plus' fixed-asset "
                "investment plus ~$76M developer-funded utility infrastructure, in the Piqua I-75 "
                "Business & Industrial Park. The Miami County auditor pull (#1483) shows the "
                "developer-owned campus is ~607.8 ac (three parcels deeded to J5 LLC, purchased "
                "2025-12-24 for $62.23M; data/reference/troy-piqua/parcel-assemblage.geojson) — a "
                "NESTED SCOPE within the ~1,026-ac cumulative annexation record (2022-2025) and the "
                "~1,200-ac whole business park, not a fourth-parcel gap (reconciliation in "
                "data/extracted/troy-piqua/bosc-site-footprint.yaml). See "
                "data/extracted/troy-piqua/data-centers.md."
            ),
            # Cooling archetype (#1054): deliberately left UNKNOWN — a real, unresolved conflict
            # between two public disclosures (not a case of "cooling method not disclosed"). #1486
            # (the standing water & regulatory watch) owns reconciling it; never pick a side here.
            # B1 (#1681) RAN the A3 reconciliation harness on this conflict and KEPT UNKNOWN: the
            # reservation is a ceiling, not a discharge/withdrawal instrument, so it cannot re-pin
            # the archetype (see cooling_model_citation).
            cooling_model=CoolingModelType.UNKNOWN,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] UNRESOLVED, deliberately not picked: the City's public FAQ describes "
                "closed-loop cooling with only an 'initial fill-up' + occasional top-offs "
                "(domestic-only ongoing use), but the negotiated Water & Wastewater Agreement "
                "(effective 2026-01-23) reserves up to 500,000 GPD (Tier I) scaling to 2.0 MGD "
                "(Tier II / full operation) — these two public disclosures conflict. B1 (#1681) ran "
                "the A3 cooling-cycling reconciliation harness (watermark cooling-reconcile, epic "
                "#1676) on this conflict: outcome reservation_conflict — the reserved 2.0 MGD makeup "
                "+ ~1.0 MGD wastewater back-solve to cycles-of-concentration ~2.0 (1.7-2.3), an "
                "[inference] bracket in evaporative-tower territory, inconsistent with a dry sealed "
                "loop's ~0. But a reservation is a CEILING, not a metered use and not a discharge/"
                "withdrawal instrument, so per the epic's re-archetype gate it CANNOT re-pin the "
                "archetype: UNKNOWN stays, and #1486 is restated as a quantified [open] gap (the 2.0 "
                "MGD is an upper-bound ceiling, never a headline consumptive). Tracked at #1486 (the "
                "standing water & regulatory watch); evidence packet "
                "data/reference/oepa/cooling-reconciliation.yaml (row troy-piqua); see "
                "data/extracted/troy-piqua/data-centers.md, 'Water / hydrology hook'."
            ),
        ),
    ),
    serving_utility_citation=(  # confirmed for #830 (primary EIA-861 2024 file + the franchise ordinance)
        "EIA-861 2024: Miami County, OH is served by two utilities, both confirmed against the "
        "2024 bulk file's Sales_Ult_Cust + Service_Territory sheets — Dayton Power & Light Co "
        "(AES Ohio, #4922, Investor Owned; a full-form filer whose territory spans 24 OH counties "
        "incl. Miami) is the county-dominant IOU (Troy + most of the county), and the City of "
        "Piqua - (OH) (#15095, Municipal, an AMP member) serves the City of Piqua. Pinned to "
        "DP&L #4922: it is both the county-dominant IOU AND the campus's disclosed intended "
        "LONG-TERM serving utility — the Piqua Commission gave FIRST READING only (3-1, 2026-07-07) "
        "to a 40-year AES Ohio franchise ordinance for permanent service; the ordinance is PENDING "
        "adoption (not yet enacted), and the Piqua muni supplies only temporary construction power "
        "(up to 10 MW) [verified: Dayton Daily News 2026-07-09; piquaoh.gov/228]. The #830 "
        "'municipal EIA-861S short-form' watch resolves NEGATIVE: Piqua #15095 files the FULL "
        "EIA-861 form (present in Sales_Ult_Cust — 10,943 customers, 281,641 MWh 2024; ABSENT from "
        "Short_Form_2024), so neither the backdrop nor the campus load basis rides the short-form "
        "path. The county geographic muni/IOU boundary split is [inference]; the #4922 pin and both "
        "utility identities/forms are [verified]; the campus's long-term AES Ohio arrangement is "
        "disclosed but its franchise ordinance is pending adoption (first reading only). See "
        "data/extracted/troy-piqua/data-centers.md."
    ),
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Miami County, OH; Piqua muni on AMP (same DAY wholesale zone) [verified]"
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Miami County, OH",  # [verified]
    # Corpus scope (#1484): the OEPA document extractions mirror the source tree under
    # oepa/troy-piqua/ (like the docs at data/documents/oepa/troy-piqua/), so that prefix must
    # reach this site — else the Piqua WWTP permit + fact sheet orphan out of its
    # record/timeline/entities and leak into Lima's whole-tree corpus. It was enumerated here
    # until #1405 made the eponymous nesting derivable for every site at once.
)


# The UPPER-UPPER Great Miami node (Shelby County) — the next mainstem city UPSTREAM of Troy/Piqua
# (#475): headwaters (Indian Lake) -> Sidney -> Piqua -> Troy -> Dayton, on I-75. Same upper Great
# Miami buried-valley sole-source aquifer as Troy/Piqua (groundwater-dominated HSG A/B), and a
# compressor/refrigeration-manufacturing town (Emerson/Copeland HQ) — the upstream sibling of the
# Troy/Piqua manufacturing reach. Tracking -> onboarding (#481 / epic #440).
# Neither floor area nor load disclosed → INVESTMENT SCREENING off the disclosed $3B campus
# ($8.5-20M per MW-IT band; watermark.facility.screening — #1641 D2).
_SIDNEY_LOAD = investment_screen(3_000_000_000)
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
    parcels_url=(  # [verified] Shelby County Engineer's Office AGOL — auditor CAMA + geometry (#1379)
        "https://services6.arcgis.com/fzPZZJiNVtryYcsC/arcgis/rest/services/Parcels/FeatureServer/0"
    ),
    zoning_url=(  # [verified] City of Sidney GIS zoning districts (polygon-only; city limits only)
        "https://cama.shelbycountyauditors.com/arcgis/rest/services/City_of_Sidney/"
        "SidneyGIS_AllLayers/MapServer/270"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32616,  # [verified] UTM 16N (Sidney ~84.16 degW; zone 16 spans 90-84 degW) — NOT zone 17
    # #1379: was the OGRIP statewide substitute, which for Shelby is owner-redacted AND a
    # 2023-05-23 extract — it predates the whole Project Galaxy transfer and can name no grantee.
    # The county engineer's own layer carries the full auditor CAMA (owner / deed / conveyance).
    gis_parcel=SHELBY_PARCEL_SCHEMA,
    gis_zoning=SIDNEY_ZONING_SCHEMA,
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "sidney-gis"}),
    design_lat=40.2842,  # [verified] Sidney centroid = NOAA Atlas-14 point
    design_lon=-84.1558,
    corridor_name="Upper Great Miami headwaters corridor",  # [inference] the Sidney mainstem reach (I-75)
    dominant_hsg="D",  # [verified] SSURGO over the committed campus footprint (#1379) — see citation
    hsg_citation=(
        "[verified] USDA NRCS SSURGO via Soil Data Access, 8x8 grid sample (64 interior points) "
        "over data/reference/sidney/parcel-assemblage.geojson - the AWS Project Galaxy campus "
        "parcel 26-03-201-002 (watermark.hydrology.connectors.ssurgo.dominant_hsg, grid_n=8, "
        "2026-07-31): D 62 pts (96.9%) + C/D 2 pts (3.1%). A SINGLE group, so the drained-vs-"
        "undrained switch is inert here. Dominant map units: Blount silt loam, end moraine, 2-4% "
        "slopes (mukey 2765022) and Glynwood silt loam, end moraine, 2-6% slopes (mukey 2856692), "
        "both HSG D. This REPLACES the prior [inference] of HSG 'B' and its reasoning: that "
        "argued from the Great Miami Buried Valley sole-source aquifer (glacial outwash sand & "
        "gravel, well-drained), which is true of the Sidney WELL FIELD but not of this campus - "
        "the site sits ~2 mi west of the valley on the Wisconsinan END MORAINE, whose till "
        "surface governs the runoff CN. Same surface-vs-aquifer correction as Urbana (B->C) and "
        "Troy-Piqua (B->C/D), sharper here because the ground is moraine, not valley fill. "
        "See data/extracted/sidney/bosc-site-footprint.yaml"
    ),
    # [verified] pre-development cover from the auditor CAMA land use across the campus and its
    # five pre-consolidation predecessors - 110/111 'Agr-CAUV' + 101 'Agr-Cash-Grain Farm', i.e.
    # CAUV row crop (the campus parcel is still land use 110 today). post/developed_pervious are
    # the network's standard screening pair (NLCD 24 high-intensity + NLCD 21 developed open
    # space): AWS has disclosed NO floor area or site plan for Project Galaxy, so these are
    # `source: assumption`-grade until the Rule-5 SWPPP / site plan lands (#1380).
    pre_cover="cropland",
    post_cover="developed_campus",
    developed_pervious_cover="open_space",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    # [verified] committed #1379 — the single consolidated parcel 26-03-201-002 deeded to Amazon
    # Data Services, Inc. (243.092 ac CAMA / 235.468 ac planar) + its footprint record.
    parcels_relpath="reference/sidney/parcel-assemblage.geojson",
    footprint_relpath="extracted/sidney/bosc-site-footprint.yaml",
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
            # Permit-sourced since #1383: Ohio EPA 1PD00009*SD (application OH0027421), City of
            # Sidney WWTP, 1091 Children's Home Road; outfall 1PD00009001 → Great Miami River at
            # RM 128.68; average design 7.0 MGD, peak hydraulic 13.5 MGD; effective 2023-01-01,
            # expires 2027-12-31 (renewal due ~2027-07-04). Serves Sidney, Port Jefferson, the
            # Mill Creek Subdivision and the Honda of America plant at Anna; allocated jointly
            # with the Piqua and Troy WWTPs as interactive dischargers. The #833 "fact sheet
            # pending" note is discharged — the fact sheet is committed and read.
            "Ohio EPA NPDES 1PD00009*SD / OH0027421 (City of Sidney WWTP) → Great Miami River "
            "at RM 128.68; average design 7.0 MGD (peak hydraulic 13.5 MGD), actual ~4.01 MGD "
            "(2023 DMR, MO AVG mean) — data/extracted/oepa/sidney/1PD00009.npdes.yaml + "
            "data/extracted/sidney/wwtp-oh0027421.dmr.yaml [verified — permit + ECHO]",
        ),
    },
    abstraction_gage="03261500",  # [verified] Great Miami River at Sidney OH
    supply_gage_primary="03261500",  # [verified] Great Miami River at Sidney
    supply_gage_secondary="03262000",  # [verified] Loramie Creek at Lockington (the major local tributary)
    # [verified] CITED regulatory stream design flow, not a BOSC derivation (#1383). Ohio EPA's
    # "Fact Sheet for NPDES Permit Renewal, City of Sidney WWTP, 2022" (permit 1PD00009*SD,
    # application OH0027421), Table 14 "Instream Conditions and Discharger Flow", p.32:
    # Great Miami River above Sidney, annual 7Q10 = 24.0 cfs (USGS 03261500, 1927-2021); the
    # same table gives annual 1Q10 19.4, summer 30Q10 29.0, harmonic mean 119.2 cfs. This
    # SUPERSEDES the 30.95 cfs placeholder carried here since onboarding, which was a BOSC LP3
    # derivation over 1980-2024 explicitly held "pending the OEPA NPDES fact sheet" (#833) — the
    # regulator's long-record value is 22% lower, so the placeholder was the more permissive of
    # the two. Source bytes: data/documents/oepa/sidney/1PD00009.c43b66fd.pdf; structured read
    # data/extracted/oepa/sidney/1PD00009.npdes.yaml.
    passby_primary_cfs=24.0,
    # [verified] same Table 14: Loramie Creek at Mouth, annual 7Q10 = 3.43 cfs (USGS 03262000,
    # 1916-2020). Closes the [open] that carried 0.0 with a derived 3.55 cfs noted alongside —
    # the derivation corroborates the cited value within 3.5%.
    passby_secondary_cfs=3.43,
    # facility CONFIRMED (#1378) — the $3B Amazon hyperscale campus at
    # 2388 W. Millcreek Road (NW corner Vandemark & Millcreek), Sidney. A SITE-PLAN-grounded
    # facility (contrast air-permit-grounded Lima / Fort Wayne): the disclosed non-power
    # attributes (operator/developer, $3B investment, location, construction status, ops target)
    # are populated, but NEITHER a gross floor area NOR the MW load is disclosed — no OEPA air
    # PTI or PJM interconnection instrument is public yet. So unlike Urbana (#1327) / Troy-Piqua /
    # Bowling Green there is no floor area to screen from, and the IT load is an INVESTMENT-scaled
    # screening bracket ([inference], see it_load_citation) — never a disclosure, the MW stays
    # [open]. cooling_model stays UNKNOWN (the register discloses water figures, not a cooling
    # design). genset_count/genset_mw/air_permit_citation stay None (no disclosed on-site
    # generation / air permit found). See data/extracted/sidney/data-centers.md (2026-07-02) and
    # the standing regulatory watch data/extracted/sidney/regulatory-watch.yaml (#1383,
    # re-checked 2026-07-31) — five state permits have since issued across this project and NONE
    # of them states a load, so the site-plan grounding stands and the MW stays [open].
    facilities=(
        SiteFacility(
            # Ohio EPA's own name for it. The local codename "Project Galaxy" is deliberately
            # NOT in the published identity: on the agency's record that name belongs to a
            # DIFFERENT Amazon campus in Fayette County (#1383), so publishing it as this site's
            # primary_name would broadcast the collision the register exists to prevent. It is
            # kept, with its caveat, in facility_type / disclosure_citation and the register.
            name="AWS Sidney Data Center Campus",
            # Pinned rather than minted from `name` (`_fill_key`). This key is a ROUTE segment
            # (`/study/f/<facility-key>/…`) and a cross-feed join, so it must not move when the
            # display name is edited — which it just did. CMH-232 is Amazon Data Services' own
            # project identifier on its Ohio EPA §401 filings: stable, machine-readable, and free
            # of the codename collision.
            key="cmh-232",
            status=FacilityLifecycle.CONSTRUCTION,  # grading permit 2026-05-14; groundbreaking ~Jan 2026
            operator="Amazon Web Services, Inc. (operator); Amazon Data Services, Inc. (developer)",
            operator_citation=(
                "[verified] City of Sidney FAQ (sidneyoh.com/526) + Data Center Dynamics (Oct 2025) — "
                "Amazon's $3B campus, locally called 'Project Galaxy'; grading permit issued "
                "2026-05-14. Ohio EPA permits it as 'Sidney Data Center Campus' / 'CMH-232' "
                "(#1383) — the codename is not a search key, see disclosure_citation."
            ),
            end_use=DcEndUse.HYPERSCALE,
            end_use_citation=(
                "[verified] hyperscale data-center campus — Amazon Web Services (public disclosure)."
            ),
            it_load_mw=_SIDNEY_LOAD.central,  # [inference] SCREENING central (MW-midpoint); see it_load_citation
            it_load_low_mw=_SIDNEY_LOAD.low,  # $3B / ~$20M per MW-IT (capex-intensive / liquid-AI) whole-campus screen
            it_load_high_mw=_SIDNEY_LOAD.high,  # $3B / ~$8.5M per MW-IT (capex-light / air-cooled) whole-campus screen
            it_load_source=ItLoadGrounding.SCREENING,
            it_load_citation=(
                "[inference] SCREENING bracket — NOT a disclosure; the disclosed interconnection/"
                "air-permit MW stays [open]. Re-checked 2026-07-31 (#1383) and still absent: Ohio "
                "EPA's eDocument portal returns ZERO air-permit documents for Shelby County under "
                "any of the three names this campus is filed as ('Sidney Data Center Campus', "
                "'CMH-232', 'Amazon Data Services'), and EPA's FRS carries the site with NPDES as "
                "its ONLY program system — while the same query shape returns 19 Amazon air-permit "
                "documents statewide (including the Licking County CMH050 draft, public notice and "
                "permit), so the zero is a zero and not a broken search. The state permits that HAVE "
                "issued for this project — construction stormwater 1GC10596*AG, isolated-wetland "
                "authorization 251911W, sanitary-sewer PTI DSWPTI-260517, the City's own road "
                "wetland permit 252256W, and AES's adjacent transmission-reroute coverage "
                "1GC11112*AG — carry no megawatt field at all. "
                "See data/extracted/sidney/regulatory-watch.yaml. "
                "AWS discloses NEITHER a gross floor area NOR a load for this campus, so "
                "the floor-area screen used elsewhere in the network (Urbana #1327 / Troy-Piqua / "
                "Bowling Green) has no input; this brackets instead off the ONE disclosed hard figure "
                "— the $3 billion campus investment (sidneyoh.com/526; Data Center Dynamics Oct 2025) "
                "— divided by a hyperscale critical-IT construction-cost band of ~$8.5-20M per MW-IT "
                "([reference] industry cost norm, NOT a Sidney disclosure): $20M/MW -> 150 MW low, "
                "~353 MW high ($8.5M/MW), ~251 MW central (MW-midpoint; watermark.facility.screening "
                "— #1641 D2). $3B spans land + shell + all "
                "phases (screen runs high) while it is a multi-year campus (near-term load runs low), "
                "the two roughly offsetting to an order-of-magnitude ~150-350 MW. Corroborated (not a "
                "second source): comparable disclosed AWS-Ohio hyperscale-campus interconnections sit "
                "~100-250 MW/campus (interconnection.fyi [reference], a DIFFERENT Amazon campus in "
                "Franklin County — not Sidney's figure). Replace with the disclosed load the moment an "
                "OEPA air PTI or a PJM interconnection filing names this campus's MW."
            ),
            # No disclosed gensets or air permit (site-plan-grounded) → genset/backup basis and the
            # air-dispatch fleet model are absent; genset_count/genset_mw/air_permit_citation stay None.
            facility_type=(
                'hyperscale data-center campus (Ohio EPA: "Sidney Data Center Campus" / "CMH-232"; '
                'locally "Project Galaxy"; operator Amazon Web Services, Inc.; '
                "developer Amazon Data Services, Inc.) — under construction"
            ),  # [verified] operator/developer + status
            # gross_floor_area_sqft = [open]: AWS has disclosed no building size for this campus.
            disclosed_investment_usd=3_000_000_000,  # [verified] $3 billion campus (DCD Oct 2025; sidneyoh.com/526)
            disclosure_citation=(
                "[verified] City of Sidney FAQ (sidneyoh.com/526/Proposed-Data-Center-FAQ) + Data "
                "Center Dynamics 'Amazon secures tax break for $3bn data center campus in Sidney, "
                "Ohio' (Oct 2025). Amazon Data Services, Inc. (developer) / Amazon Web Services, Inc. "
                "(operator); $3B campus at 2388 W. Millcreek Road (NW corner of Vandemark & Millcreek "
                "Roads), Sidney. Status: UNDER CONSTRUCTION — grading permit issued 2026-05-14, "
                "groundbreaking ~January 2026, site plan under City-staff review as of June 2026; "
                "operations target 2028-12-31 (CRA Agreement 80-25 deadline). ~75 long-term jobs by "
                "2030 / $6.75M annual payroll; 30-yr 100% CRA real-property abatement (Res 18-25); "
                "$50M PILOT over 15 yr; up to $8.0M AWS Millcreek Road reconstruction (Res 27-26, "
                "adopted 2026-04-27). SITE EXTENT now permit-sourced (#1383): Amazon Data Services' "
                "own Ohio EPA filings state 236.7 acres 'of agricultural and residential land' "
                "converted (401 application, project name CMH-232) and 230.7 acres of total land "
                "disturbance (construction-stormwater NOI); coverage 1GC10596*AG under general "
                "permit OHC000006 ran effective 2025-12-05, 160 days (a little over five months) "
                "before the City's grading permit of 2026-05-14. NAMING: Ohio EPA files this campus as 'Sidney Data Center Campus' and "
                "'CMH-232', never as 'Project Galaxy' — that name in Ohio EPA's own records belongs "
                "to a DIFFERENT Amazon Data Services campus at 1000 Innovation Way, Jeffersonville "
                "(Fayette County), which does hold an individual NPDES permit and a cooling-water "
                "discharge force main. See data/extracted/sidney/data-centers.md and "
                "data/extracted/sidney/regulatory-watch.yaml."
            ),
            # Cooling archetype (#1054): UNKNOWN — the register discloses WATER FIGURES, not a cooling
            # DESIGN, so the method is not on record (a disclosed facility with an undisclosed method
            # gets a bracketed range, never the water-intensive evaporative default). Not asserted.
            cooling_model=CoolingModelType.UNKNOWN,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] cooling method not disclosed in the record — kept UNKNOWN (bracketed "
                "range). The Res 26-26 water/sewer agreement (adopted 2026-04-27; sidneyoh.com/526) "
                "discloses a 1.0 MGD peak-withdrawal ceiling (694 gpm) and a projected 4.6M gal/yr "
                "(~12,600 GPD avg) cooling-water CONSUMPTION; that consumption is <1.3% of the 1.0 MGD "
                "ceiling, consistent with a largely closed-loop/dry design rather than an evaporative "
                "tower — but AWS has not stated the cooling design, so this is NOT selected as "
                "closed_loop_dry. Facility wastewater returns to the Sidney sanitary sewer -> "
                "1PD00009*SD / OH0027421 -> Great Miami River at RM 128.68; the City states flatly "
                "that 'Cooling systems are not permitted to discharge to the storm sewer system' and "
                "the campus's own stormwater NOI answers 'Individual NPDES: NO', so there is no "
                "surface-water cooling discharge to permit here — which is also why Ohio EPA's "
                "abandonment of the draft data-center general permit OHD000001 (Community Notice "
                "2026-07-21) changes nothing for this site. Net consumptive draw ~= 0.0195 cfs avg "
                "vs the CITED regulatory Great Miami 7Q10 of 24.0 cfs (0.08%) — [inference] from the "
                "cited water figures (see data/extracted/sidney/data-centers.md, 'Water / hydrology "
                "hook'); the passby is now the fact-sheet value, not a derivation (#1383)."
            ),
        ),
    ),
    serving_utility_citation="EIA-861 2024 Service_Territory: Dayton Power & Light Co (AES Ohio, #4922) is the IOU serving Shelby County, OH / Sidney — distinct from 'City of Shelby' (#17043, a Richland-County muni). [verified]",
    lmp_usd_mwh=46.42,  # connector-sourced DAY-zone 2025 day-ahead annual mean [verified]
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, DAY zone (pnode 34508503), 2025 day-ahead annual mean "
        "$46.42/MWh (8760 h); connector-sourced 2026-07-01 (watermark lmp) — AES Ohio (DP&L) "
        "territory, Shelby County, OH [verified]. TARIFF POSTURE (#1383, checked 2026-07-31): the "
        "retail terms this zone's data centers will actually pay under are not settled — AES Ohio "
        "announced on 2026-07-21 an UNOPPOSED Stipulation with PUCO Staff and 16 parties in Case "
        "No. 25-958-EL-AIR for a three-year rate plan including 'a new Data Center Tariff as "
        "recommended by the PUCO', with distribution rates planned through 2029 [reference — the "
        "utility's own account of its own filing, data/documents/grid/sidney/]. The four DCT rate "
        "classes the PUCO Staff Report recommended (secondary / primary / primary-substation / "
        "high-voltage) are NOT confirmed from the stipulation itself: PUCO's docketing system is "
        "WAF-blocked, so the docket is unsearched, not empty. No AES service agreement or "
        "interconnection filing naming this campus is on the record [open]."
    ),
    lmp_pnode_id=34508503,  # [verified] PJM DAY zone (AES Ohio / Dayton Power & Light)
    lmp_pnode_name="DAY",
    county_name="Shelby County, OH",  # [verified]
    # Sidney owns two sub-collections outside its slug directory (#1383): the Ohio EPA
    # permits under oepa/sidney/ (the campus's stormwater / wetland / PTI instruments and
    # the receiving POTW's NPDES permit) and the utility record under grid/sidney/. Both are
    # eponymous, so #1405 derives them; enumerating them here was never sufficient anyway —
    # 1PV00037's extraction still sat flat at extracted/oepa/ and reached Lima, not Sidney.
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
    facilities=(),  # [verified] zero Greenville/Darke-County data-center records in RSEI, ECHO NPDES,
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
# -> Little Miami (a National & State Scenic River, the same anti-degradation overlay as Xenia).
# Todd Fork has NO CURRENTLY REPORTING discharge gage — but it is not unstudied: the discontinued
# 03244000 (Todd Fork near Roachester, DA 219 mi²) holds 21 complete climatic years of daily
# discharge, 1952-09-01..1974-10-29, which is now the at-site 7Q10 anchor (#1472). That record is
# invisible to these knobs by construction — they resolve through the NWIS INSTANTANEOUS-values
# service, and 03244000 has produced no IV since 1974 — so the gages below stay the nearest ACTIVE
# mainstem integrators and the low-flow statistic lives in the screen doc, not in a knob. Two water
# threads, kept separate: the City WITHDRAWS from Caesar Creek Lake (USACE storage contract) and
# DISCHARGES to Lytle Creek -> Todd Fork; neither screens the other. Full derivation, drainage areas
# and instruments: data/extracted/wilmington/low-flow-screen.md.
# Tracking -> onboarding (#492 / epic #440).
# IT load undisclosed → floor-area SCREENING off the disclosed 1,920,299 sq ft site plan
# (watermark.facility.screening — #1641 D2; reconciles the old off-midpoint 300 MW central).
_WILMINGTON_LOAD = floor_area_screen(1_920_299)
_WILMINGTON = SiteProfile(
    slug="wilmington",
    basin="little-miami",  # [verified] Todd Fork → Little Miami River → Ohio River (HUC-8 05090202)
    # Live-reading gages only (NWIS instantaneous values). Deliberately EXCLUDES the two Todd Fork
    # stations, for reasons that differ (#1472): 03244000 (Roachester) carries the 21-year daily
    # record that anchors the at-site 7Q10 but has been dark since 1974, and 03243150 (Clarksville,
    # DA 56.6 mi²) is a water-quality/partial-record site whose entire "record" is ONE sample visit
    # on 1981-08-21 — no daily or unit values in any form. Neither can serve a latest-reading knob.
    nwis_sites=[
        "03245500",  # [verified] Little Miami River at Milford OH (downstream mainstem integrator, incl. Todd Fork)
        "03240000",  # [verified] Little Miami River near Oldtown OH (upstream Xenia reach — brackets Todd Fork above)
        "03242350",  # [verified] Caesar Creek near Wellman OH — the WITHDRAWAL-side gage (Caesar Creek Lake is the
        # City's principal raw supply since 1994); reports stage + temperature only, no discharge since 1974-06-30
    ],
    nasa_power_lat=39.4453,  # [verified] Wilmington, OH city centroid (39deg26'43"N 83deg49'43"W)
    nasa_power_lon=-83.8285,
    rsei_fips="39027",  # [verified] Clinton County, OH
    econ_fips="39027",
    eia861_utility_number=4922,  # Dayton Power & Light (AES Ohio) — EIA-861 2024 Service_Territory, Clinton Co [verified]
    parcels_url=(  # [verified] the Clinton County GIS Department's own auditor CAMA join, which
        # REPLACED the OGRIP Ohio statewide substitute this profile carried (#1470). That layer is
        # owner-redacted by construction and for Clinton reports a NULL `CurrentTo` — no stated
        # export date at all — with SitusAddressAll/LandArea null on a large share of rows, so the
        # whole Cosler Farm / Ardent-TAC corridor was unreadable through it. This layer names the
        # grantee and carries deed instrument + conveyance + appraised values (2026-07-30 extract).
        "https://services1.arcgis.com/tAhcHWpOD9ygNPbJ/arcgis/rest/services/"
        "cntyparcelsRealPropData_gdb/FeatureServer/0"
    ),
    zoning_url=(  # [verified] City of Wilmington zoning, published by the Clinton County Regional
        # Planning Commission — the Zoning layer of the City's own "Wilmington Zoning Map 2024"
        # app. Polygon-only (13 districts / 29 polygons), city limits only, edited 2026-02-10.
        "https://services7.arcgis.com/5ML1cxkkvVfOhDrS/arcgis/rest/services/"
        "ProposedZoning9/FeatureServer/0"
    ),
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Wilmington ~83.83 degW; zone 17 spans 84-78 degW) — east of 84 degW
    gis_parcel=CLINTON_PARCEL_SCHEMA,  # [verified] Clinton County auditor CAMA join (#1470)
    gis_zoning=WILMINGTON_ZONING_SCHEMA,  # [verified] City of Wilmington districts, catalog-only (#1470)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "wilmington-gis"}),
    design_lat=39.4453,  # [verified] Wilmington centroid = NOAA Atlas-14 point
    design_lon=-83.8285,
    corridor_name="Wilmington Air Park (single-tenant) corridor",  # [reference] ILN — Amazon Air / ATSG cargo hub
    dominant_hsg="C",  # [verified] SSURGO over the committed campus geometry (#1470) — see citation
    hsg_citation=(
        "[verified] USDA NRCS SSURGO via Soil Data Access (SDA), grid-sampled over the committed "
        "data/reference/wilmington/parcel-assemblage.geojson "
        "(watermark.hydrology.connectors.ssurgo.dominant_hsg, 2026-08-01). The AWS campus tract "
        "285-13-02-01 alone returns C at EVERY grid resolution tested — 8x8 (41 interior points: "
        "C 16 / B/D 15 / C/D 10), 10x10 (61), 12x12 (89) and 16x16 (158 pts: C 43.7%, B/D 34.8%, "
        "C/D 21.5%) — so the letter is not a grid artefact. Dominant map units are the Southern "
        "Ohio Till Plain association: Miamian silt loam 6-12% eroded (C), Xenia silt loam 2-6% "
        "(C), Sligo silt loam occasionally flooded (C), Fincastle silt loam 0-4% (B/D and C/D) "
        "and Treaty silty clay loam 0-1% (B/D). This CONFIRMS the prior [inference] letter 'C' "
        "and its reasoning (glaciated till plain, NOT buried-valley outwash) and upgrades it to "
        "[verified]. TWO CAVEATS THAT MATTER. (1) It is a PLURALITY over a genuinely mixed "
        "mosaic, not a uniform C: ~60% of sampled campus points carry a DUAL rating whose "
        "undrained letter is D, so post-development (tile severed, watermark.hsg / WS-20 "
        "post_drainage_condition='undrained') the runoff basis brackets materially above a flat "
        "C — the screen should state that bracket rather than read C as settled. (2) The letter "
        "is grid-STABLE for the campus but NOT for the whole 1,023-ac corridor, which flips C/D "
        "at 8x8/10x10/12x12 and back to C at 16x16 as the four petitioned Ardent/TAC tracts pull "
        "it wetter; the profile value characterizes the disclosed CAMPUS, which is what the "
        "stormwater screen models. onboard's default 6x6 over the corridor also returns C."
    ),
    # [verified] land-cover scenario — grounded on the corridor's own auditor land use: every one
    # of the five annexed tracts is Ohio use 111 "CASH-GRAIN OR GENERAL FARM (CAUV)" or 110
    # "AGRICULTURAL VACANT LAND (CAUV)", i.e. working cropland, and the disclosed build is a
    # near-impervious data-center campus (#1468).
    pre_cover="cropland",
    post_cover="developed_campus",
    developed_pervious_cover="open_space",
    noaa_fallback_24h_depth_in={},  # [open] pending the NOAA Atlas-14 pull (onboard corridor-DDF step)
    parcels_relpath="reference/wilmington/parcel-assemblage.geojson",  # [verified] the US-68 S / SR-730 corridor (#1470)
    footprint_relpath="extracted/wilmington/bosc-site-footprint.yaml",  # [verified] parcel-grounded (#1470)
    climatology_relpath="reference/hydrology/wilmington/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/wilmington/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/wilmington/baseline.yaml",
    rsei_relpath="reference/rsei/wilmington/inventory.yaml",
    consumer_energy_relpath="reference/eia/wilmington/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/wilmington/demand-pressure.yaml",
    grid_relpath="reference/eia/wilmington/grid-profile.yaml",
    # "Corridor" sense 3 (TOXICS SCREENING WINDOW) — DERIVED, not drawn: the WGS84 envelope of the
    # committed corridor geometry (data/reference/wilmington/parcel-assemblage.geojson: seven
    # contiguous auditor parcels, union bounds 39.400429-39.428541 N / -83.869890--83.833400 W),
    # rounded OUTWARD to 3 decimals. #1470. Deliberately NOT the Air Park reach the profile's
    # corridor_name (sense 1) refers to, and deliberately NOT extended north to the Wilmington
    # WWTP (39.4391, -83.85132), which is 1,224 m beyond the nearest campus boundary: this is a
    # land window for the RSEI receiving-water inference, not a discharge window. It captures
    # exactly one inventoried facility — AHRESTY WILMINGTON CORP (39.413526, -83.844830, NAICS
    # 331523 aluminum die-casting), whose RSEI record has water_releases false and no NPDES id,
    # so the inference it licenses is the POTW pathway (844.7 lb to the Wilmington WWTP ->
    # NPDES OH0028134 -> Lytle Creek), which is this site's receiving_water_name.
    toxic_corridor_bbox=(
        39.400,
        39.429,
        -83.870,
        -83.833,
    ),  # [verified — derived from the geometry]
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
    # [open] Nearest ACTIVE discharge gage, not the right one: Milford's DA is 1203 mi² (NWIS
    # published — NOT the 1664 this repo previously carried) against an at-site 79.0 mi² just below
    # the Lytle Creek confluence, a 15x overstatement of contributing area and so of dilution. There
    # is no live discharge gage on Todd Fork, Lytle Creek, or Caesar Creek below the dam (#1472).
    abstraction_gage="03245500",
    supply_gage_primary="03245500",  # [verified] Little Miami River at Milford (downstream integrator)
    supply_gage_secondary="03240000",  # [verified] Little Miami River near Oldtown (upstream reach; brackets Todd Fork)
    # [open] and STRUCTURALLY MISMATCHED, which is the honest finding rather than a gap to fill: the
    # refill model passes these against the two Little Miami mainstem gages, but the City does not
    # abstract from the Little Miami mainstem at all — it draws a CONTRACTED STORAGE ALLOCATION
    # (~12 billion gal) from Caesar Creek Lake under the 1970 USACE/ODNR contract, which the refill
    # model has no slot for. A plausible-looking passby here would make an inapplicable model emit a
    # confident number, so it stays 0.0/[open] until either an Ohio EPA anti-degradation in-stream
    # minimum lands or the supply is remodeled as a reservoir allocation (#1472 §3.2).
    passby_primary_cfs=0.0,
    passby_secondary_cfs=0.0,
    # grid / facility — the disclosed AWS "Cosler Farm" campus (#1468). Site-plan-grounded (the
    # Urbana #1327 seam): a floor-area/investment [inference] IT-load bracket, NOT a fabricated MW.
    # The disclosed interconnection/air-permit MW stays [open] (#1469). Ardent/TAC (§2 of the
    # register) is now this site's SECOND facility (#1628) — known by its rezoning only, every
    # figure [open]; the primary Cosler Farm campus (first) is what drives the water/power math.
    facilities=(
        SiteFacility(
            name="Cosler Farm campus",
            status=FacilityLifecycle.CONFIRMED,  # proposed/disclosed; zoning ordinances in remand (Sharp v. City)
            operator="Amazon Data Services, Inc. (AWS)",
            operator_citation=(
                "[verified] joint Clinton County Port Authority / City of Wilmington Data Center FAQs — "
                "AWS acquired the former Cosler Farm in a private transaction; Amazon Data Services, Inc. "
                "is the intervenor in Sharp v. City of Wilmington (S.D. Ohio 1:26-cv-00448)."
            ),
            end_use=DcEndUse.HYPERSCALE,
            end_use_citation=(
                "[reported] hyperscale data-center campus — Amazon Data Services, Inc. (wnewsj 2025-12-03; WCPO)."
            ),
            it_load_mw=_WILMINGTON_LOAD.central,  # [inference] SCREENING central (MW-midpoint); see it_load_citation
            it_load_low_mw=_WILMINGTON_LOAD.low,  # floor-area low (1,920,299 sqft x 75 W/sqft = 144.0)
            it_load_high_mw=_WILMINGTON_LOAD.high,  # floor-area high (1,920,299 sqft x 250 W/sqft = 480.1)
            it_load_source=ItLoadGrounding.SCREENING,
            it_load_citation=(
                "[inference] SCREENING bracket — NOT a disclosure; the disclosed interconnection/"
                "air-permit MW stays [open] (#1469: OPSB 25-0871-EL-BLN 345kV build-out + the PJM-queue "
                "lead). No MW figure is primary-sourced for the campus. Primary basis = the network "
                "floor-area screen (cf. Urbana #1327 / Troy-Piqua): the disclosed 9-building site plan's "
                "1,920,299 sq ft gross floor area (Nov/Dec 2025) x a whole-building IT power-density band "
                "of 75-250 W/sq ft (stated screening assumption) -> 144.0 MW low, ~312 MW central "
                "(MW-midpoint; watermark.facility.screening — #1641 D2), 480.1 MW high. Corroborated "
                "(not a second source) by the investment screen (cf. Sidney): the "
                "[reported] $4B campus / a hyperscale ~$8.5-20M-per-MW-IT construction-cost band -> ~200 "
                "MW ($20M/MW) .. ~470 MW ($8.5M/MW) — the two independent screens agree at an "
                "order-of-magnitude ~150-480 MW, so the bracket is set there (central ~312 MW). Signals "
                "that point HIGHER but are NOT adopted into the bracket: (a) the 9->12-building revision "
                "tabled 2026-03-27 is unreconciled [open] and would scale the floor area up; (b) the "
                "[reported] 252 Tier-4 diesel gensets, at a typical hyperscale per-unit rating (undisclosed), "
                "imply a larger N+1 backup envelope; (c) the widely repeated '1.5 GW' is [reference] press "
                "analysis of PJM interconnection filings (interconnection capacity != near-term IT load) — "
                "a lead tracked on #1469, not a document in hand. Replace with the disclosed load the "
                "moment a PJM interconnection / OPSB / SWOAQA air-permit instrument names the campus MW. "
                "Full record: data/extracted/wilmington/data-centers.md. Discipline: this Clinton-County "
                "thread is SELF-CONTAINED — do NOT bridge the Lima/Allen Bistrozzi land-assembly graph."
            ),
            # 252 Tier-4 gensets are disclosed by COUNT only (no per-unit rating on the record), so no
            # backup figure can be formed without inventing the rating: genset_count/genset_mw stay None
            # (site-plan-grounded, like Urbana/Sidney). The count lives in the register + the citation
            # above, not the power basis; the air-dispatch fleet model refuses cleanly.
            facility_type=(
                'hyperscale data-center campus ("Cosler Farm"; developer/operator Amazon Data Services, '
                "Inc., the intervenor in Sharp v. City of Wilmington) — proposed"
            ),  # [verified] entity + [reported] type
            gross_floor_area_sqft=1_920_299,  # [reported] 9-building site plan (Nov/Dec 2025); 9->12 revision unreconciled [open]
            disclosed_investment_usd=4_000_000_000,  # [reported — wnewsj 2025-12-03; WCPO] $4B proposal
            disclosure_citation=(
                "Disclosed Nov 2025 via the joint Clinton County Port Authority / City of Wilmington "
                "Data Center FAQs [verified — chooseclintoncountyoh.org/news/data-center-faqs, "
                "wilmingtonohio.gov/data-center-faqs]: a ~471-acre campus on the former Cosler Farm at "
                "1488 S US Route 68 (SW Wilmington), acquired by AWS in a PRIVATE transaction (not "
                "brokered by the Port Authority / City / JobsOhio); minimum 100 permanent jobs / ~$8M "
                "annual payroll. The $4B investment and the 9-building / 1,920,299 sq ft site plan are "
                "[reported — wnewsj 2025-12-03 'officials detail $4B AWS data center proposal'; WCPO]; a "
                "revised 12-building plan tabled 2026-03-27 is UNRECONCILED against the 9-building figure "
                "[open — resolve from the site-plan PDFs, #1470]. Legal posture (carried honestly): a "
                "federal court ordered the City to REDO three ordinances underpinning the campus — the "
                "data-center zoning-text amendment, the generator-noise exemption, and the Cosler Farm "
                "map rezoning — for defective public notice (Sharp v. City of Wilmington, S.D. Ohio "
                "1:26-cv-00448, ruling ~2026-07-09/10 [reported — WCPO/WDTN/wnewsj converging]); the "
                "conditional-use ordinance O-26-33 has its final vote 2026-07-16. A proposed campus whose "
                "zoning basis is in remand is still a disclosed facility with pullable instruments, not a "
                "reason to zero the domain out. Ardent/TAC (a second ~545-ac rezoning corridor, O-26-04-07, "
                "5-2 on 2026-02-19/20) is now structured as this site's SECOND facility (below), its "
                "investment / MW / instruments all [open]. See data/extracted/wilmington/data-centers.md."
            ),
            # Cooling archetype (#1054): HYBRID_ADIABATIC — the FAQs disclose DIRECT EVAPORATIVE cooling
            # operated only ~11 days/yr (dry/free-cooling the rest of the year), the defining seasonal-
            # evaporative-assist signature. The deep water back-solve / WUE reconciliation is the water
            # plan's job (#1472); the reserved withdrawal MGD is [open]. Recorded metadata here — the
            # cooling model does not run in export for a non-reference site.
            cooling_model=CoolingModelType.HYBRID_ADIABATIC,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] DIRECT EVAPORATIVE cooling disclosed in the joint Port Authority / City "
                "Data Center FAQs, with a projected ~6M gal/yr cooling-water CONSUMPTION and water-cooled "
                "operation only ~11 days/yr (dry/free-cooling otherwise) — mapped to the HYBRID_ADIABATIC "
                "archetype (dry with seasonal evaporative assist). The disclosed ~6M gal/yr at the "
                "screening IT load implies a very low water-use effectiveness (near-dry operation), which "
                "UNDERCUTS a large-abstraction premise — the water-thesis finding. Not a document "
                "extraction; the reserved withdrawal MGD, the Caesar Creek Lake source contract, and the "
                "WUE/back-solve reconciliation are the water plan (#1472). Wastewater returns to the City "
                "WWTP -> NPDES OH0028134 -> Lytle Creek -> Todd Fork -> Little Miami."
            ),
        ),
        SiteFacility(
            name="Ardent/TAC corridor",
            status=FacilityLifecycle.CONFIRMED,  # rezoning O-26-04-07 passed 5-2 (2026-02-19/20)
            # No operator / end_use / IT-load / cooling on the record — the campus is known by its
            # rezoning ONLY, so every disclosed figure stays [open]. facility_type + its paired
            # disclosure_citation record that the corridor exists and cite the rezoning; nothing more.
            facility_type=(
                "second ~545-ac data-center rezoning corridor (Ardent / TAC) — investment / MW / "
                "instruments all undisclosed"
            ),
            disclosure_citation=(
                "[reference] Ardent/TAC — a second ~545-ac data-center rezoning corridor, ordinance "
                "O-26-04-07, passed 5-2 on 2026-02-19/20; investment / MW / cooling / air + "
                "interconnection instruments all [open]. See data/extracted/wilmington/data-centers.md."
            ),
        ),
    ),
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
    facilities=(),  # [open] data-center dimension = Intel "Ohio One" + Google/Meta/AWS/Microsoft/QTS (#485); pending a pinned facility
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
    facilities=(),  # [open] data-center dimension = the Columbus-metro cluster + AEP tariff exposure (#486); pending a pinned facility
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
    facilities=(),  # [open] data-center dimension = Aligned Conesville AI campus (#495); pending a pinned facility
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
    facilities=(),  # [open] data-center dimension = SB Energy PORTS Technology Campus; pending a pinned facility
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
    ba_code="PJM",  # off the confirmed _UTILITY_GRID map (#13998), so pin the BA (Ohio Edison = PJM ATSI) — B2/#1639
    rto_name="PJM Interconnection",
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
    facilities=(),  # [open] data-center dimension = Aligned NEO-01 campus; pending a pinned facility
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
    facilities=(),  # [open] the data-center dimension onboarding doesn't capture (no disclosed facility)
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


# Mansfield / Richland County — the network's first Rocky Fork Mohican headwaters node (Black
# Fork → Mohican → Walhonding → Muskingum → Ohio; shares Coshocton's `muskingum` basin further
# downstream). Registered #1426 (identity + lat/lon, county FIPS, NWIS gages, EIA-861 utility
# number). The **backdrop floor** (#1427) adds the onboard-derived knobs: the design point +
# corridor name + SSURGO dominant HSG (the corridor-DDF/floor inputs), the serving-utility
# citation, and county_name — so the floor connectors (economics/consumer-energy/RSEI + Atlas-14
# + grid) write clean, TODO-free reference datasets. The hydrology design/facility fields still
# below stay TODO — the site earns those tiers from evidence (#1428 facility, #1429/#1430 record,
# #1431 places already live).
_MANSFIELD = SiteProfile(
    slug="mansfield",
    basin="muskingum",  # [verified] Rocky Fork → Mohican → Walhonding → Muskingum River → Ohio River;
    # shares Coshocton's basin slug (subregion 0504)
    nwis_sites=[
        "03131000",  # [verified] Rocky Fork near Mansfield OH — the WWTP's (2PE00001*ND) receiving
        # water; DA 39.0 mi²
        "03130500",  # [verified] Touby Run at Mansfield OH — the downtown-Mansfield creek; DA 5.44 mi²
        "03132500",  # [verified] Clear Fork at Newville OH — downstream of Clear Fork Reservoir
        # (the city's water supply); DA 174 mi²
    ],
    nasa_power_lat=40.7585,  # [verified] downtown Mansfield square centroid (data/sites.yaml map_lat)
    nasa_power_lon=-82.5155,
    rsei_fips="39139",  # [verified] Richland County, OH
    econ_fips="39139",
    eia861_utility_number=13998,  # [verified] Ohio Edison Co — EIA-861 2024 Service_Territory file
    ba_code="PJM",  # off the confirmed _UTILITY_GRID map (#13998), so pin the BA (Ohio Edison = PJM ATSI) — B2/#1639
    rto_name="PJM Interconnection",
    # confirms Ohio Edison serves Richland County (Ohio Power Co/AEP #14006 also serves rural
    # Richland Co territory; City of Shelby is a separate Richland-County municipal utility, #17043
    # — NOT Ohio Edison — the footgun already flagged on the Sidney profile)
    eia_state="OH",
    parcels_url=(  # [verified] Richland County GIS — Parcel_CAMA MapServer layer 0 (auditor CAMA + geometry, #1431)
        "https://maps.richlandcountyoh.us/richlandgis/rest/services/Parcel_CAMA/MapServer/0"
    ),
    zoning_url="TODO",  # [open] no public per-parcel Richland Co / City of Mansfield zoning REST found
    floodzone_url="TODO",
    gnis_default_state="OH",
    hydro_utm_epsg=0,  # TODO
    lsc_default_ga="136",
    gis_parcel=RICHLAND_PARCEL_SCHEMA,  # [verified] Parcel_CAMA layer 0 — owner + CAMA values (#1431)
    gis_zoning=None,
    gis_flood=None,
    design_lat=40.7585,  # [verified] downtown Mansfield square centroid = NOAA Atlas-14 point
    design_lon=-82.5155,
    corridor_name="Rocky Fork Mohican corridor",  # [inference] the receiving-water reach at Mansfield
    # (Touby Run → Rocky Fork of Mohican River); the Black Fork is a separate Shelby stream, not the city's
    dominant_hsg="D",  # [verified] USDA SSURGO (SDA) dominant hydrologic soil group over the
    # parcel-assemblage geometry — 13/13 sampled points HSG D (high runoff potential), onboard #1427
    hsg_citation="USDA SSURGO (Soil Data Access) dominant hydrologic soil group sampled over the "
    "parcel-assemblage geometry (Airport West rezone footprint) — 13/13 points HSG D. [verified]",
    pre_cover="TODO",
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},  # TODO
    parcels_relpath="reference/mansfield/parcel-assemblage.geojson",  # [verified] Ord. 25-086 Airport West I-1->I-2 rezone footprint, 10/16 lots ~309 ac (#1431)
    footprint_relpath="extracted/mansfield/bosc-site-footprint.yaml",  # TODO: pending an identified site
    climatology_relpath="reference/hydrology/mansfield/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/mansfield/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/mansfield/baseline.yaml",
    rsei_relpath="reference/rsei/mansfield/inventory.yaml",
    consumer_energy_relpath="reference/eia/mansfield/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/mansfield/demand-pressure.yaml",
    grid_relpath="reference/eia/mansfield/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # TODO
    plant_receiving={},  # TODO
    abstraction_gage="TODO",
    supply_gage_primary="TODO",
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # TODO
    passby_secondary_cfs=0.0,  # TODO
    facilities=(),  # [open] pending the facility instrument hunt (#1428)
    serving_utility_citation="EIA-861 2024 Service_Territory: Ohio Edison Co (#13998, FirstEnergy — "
    "PJM ATSI zone) is the IOU serving Richland County, OH / Mansfield; Ohio Power Co/AEP (#14006) "
    "also serves rural Richland-Co territory. 'City of Shelby' (#17043) is a separate Richland-County "
    "municipal utility — NOT Ohio Edison. [verified]",
    lmp_usd_mwh=35.0,  # [inference] PJM ATSI-zone placeholder (Ohio Edison, same zone as Defiance/Toledo) — verify via PJM Data Miner 2 (not the AEP value)
    lmp_citation=(
        "PJM ATSI zone (FirstEnergy / Ohio Edison) ~2024 annual average LMP ($/MWh) via PJM Data "
        "Miner 2 da_hrl_lmps; [inference] not the AEP-zone value used by the AEP OH sites — verify"
    ),
    county_name="Richland County",  # [verified] FIPS 39139
)


# The Portage/Maumee-divide node (#1433, discovery sweep 2026-07-10) — Bowling Green / Middleton
# Twp, Wood County. Unusual in the network: it sits on the Great Black Swamp lakebed **straddling
# the Maumee-Portage divide**, so it DRINKS the Maumee (Waterville intake 04193500 → 170 MG
# up-ground reservoir) and DISCHARGES to the Portage (WPC 2PD00009/OH0024139 → Poe Ditch →
# North Branch Portage). `basin="portage"` holds for the receiving-water/POTW screen (no committed
# Portage POTW inventory exists yet → the basin screen degrades to empty, which is correct, not a
# gap — #1434); the intake side is carried by `abstraction_gage` on the Maumee. The **facility**
# domain is ACTIVE (#1435): Meta's "Bowling Green Data Center" ("Project Accordion") is
# site-plan-grounded (#1327 Urbana precedent) — operator disclosed, campus under construction, and
# a sibling OPSB instrument (25-0973-EL-BLN, the Apollo BTM plant) names Liames, LLC as customer of
# record. See data/extracted/bowling-green/data-centers.md. Backdrop floor + facility only; places/
# record/story stay locked pending their sub-issues (#1436/#1438/#1439/#1441).
# CASE SUFFIX — it is 25-0973-EL-**BLN**, not -BGN, and every -BGN in this file was wrong until
# #1437 read the filing. BLN is the Board Letter of Notification (the accelerated,
# automatic-approval track); BGN is the adjudicated generation-certificate track. OPSB's own
# 2026-02-03 news release says "25-973-EL-BGN" — wrong suffix AND a dropped zero — which is where
# the error came from; the docket caption, every Staff Report page footer and the DIS filing stamp
# all read 25-0973-EL-BLN, and OPSB's structured gas-fleet case table agrees. Do not "restore" BGN.
# MIXED basis: central/high = the DISCLOSED ~180 MW design ceiling (#1435, carried as central);
# only the LOW bound is a floor-area SCREENING floor off the disclosed 715k sq ft (#1641 D2).
_BOWLING_GREEN_SCREEN = floor_area_screen(715_000)
_BOWLING_GREEN = SiteProfile(
    slug="bowling-green",
    basin="portage",  # [verified] discharges to North Branch Portage → Portage River → Lake Erie;
    # HUC-8 04100010 (the receiving/POTW-screen basin). The city DRINKS the Maumee (HUC 04100009,
    # Waterville intake) — that intake side is the `abstraction_gage` below, not the `basin`.
    # config knobs
    nwis_sites=[
        "04193500",  # [verified] Maumee River at Waterville OH — the intake/HAB-load reach (the WTP
        # intake sits just upstream of the gage); shared with Toledo as the basin 7Q10 reference
        "04195061",  # [verified] North Branch Portage River at Scotch Ridge OH — the effluent branch (active)
        "04195500",  # [verified] Portage River at Woodville OH — the Portage mainstem
    ],
    nasa_power_lat=41.3748,  # [verified] City of Bowling Green centroid (the Meta campus is ~6 mi N
    nasa_power_lon=-83.6513,  # in Middleton Twp; the county-level floor connectors key on the city)
    rsei_fips="39173",  # [verified] Wood County, OH
    econ_fips="39173",
    ba_code="PJM",  # off the confirmed _UTILITY_GRID map (#2054), so pin the BA (Bowling Green muni → AMP/PJM) — B2/#1639
    rto_name="PJM Interconnection",
    eia861_utility_number=2054,  # [verified] City of Bowling Green - (OH), Municipal (AMP member) —
    # EIA-861 2024 Utility_Data / Sales_Ult_Cust (f8612024.zip, released 2025-10-06), BA=PJM.
    # NB the Bowling Green, KY muni is #2056 (SERC/TVA) — the KY disambiguation trap, avoided here.
    eia_state="OH",
    # GIS — schema-driven (#237): flood = the shared national NFHL; parcels/zoning REST endpoints
    # are DISCOVERED (both live, owner/district-bearing) but the per-jurisdiction field-map schemas
    # (gis_parcel/gis_zoning) are the places-domain lift (#1436) — left None here so the connector
    # refuses cleanly rather than half-wiring a facility-scoped PR. Endpoints for #1436 to wire:
    #   parcels: https://wcohiogis.woodcountyohio.gov/server/rest/services/Services_for_Web_Apps/Vision_Parcels/MapServer/0
    #            (Wood County Vision/CAMA — Owner_Name + Deeded_Owner + Sale_Date/Transfer_Price; parcel id in Name; 73,839 features)
    #   zoning:  https://gis.bgohio.org/arcgis/rest/services/PublicData/UtilitiesWithZoning/MapServer/2
    #            (City of Bowling Green "Current Zoning" — district in F2023_Desc; 14 districts)
    parcels_url="TODO",  # [open] endpoint discovered (see above); field-map schema pending #1436
    zoning_url="TODO",  # [open] endpoint discovered (see above); field-map schema pending #1436
    floodzone_url=(  # [verified] FEMA NFHL S_FLD_HAZ_AR (national layer 28)
        "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28"
    ),
    gis_parcel=None,  # [open] pending Wood County, OH parcel-layer discovery (#1436)
    gis_zoning=None,  # [open] pending City of Bowling Green zoning-layer discovery (#1436)
    gis_flood=NATIONAL_NFHL_FLOOD_SCHEMA.model_copy(update={"reference_dir": "bowling-green-gis"}),
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Bowling Green ~83.65 degW; zone 17 spans 84-78 degW)
    # stormwater (the Atlas-14 corridor point = city centroid; cover scenario pending a site)
    design_lat=41.3748,  # [verified] city centroid = NOAA Atlas-14 point
    design_lon=-83.6513,
    corridor_name="North Branch Portage corridor",  # [inference] the effluent receiving-water reach
    dominant_hsg="D",  # [inference] Wood County Great Black Swamp lakebed clays (Hoytville/Nappanee/Latty) → HSG D
    hsg_citation=(
        "Wood County, OH dominant hydrologic soil group D — very-poorly-drained Great Black Swamp "
        "lakebed clays (Hoytville/Nappanee/Latty; NRCS Soil Survey of Wood County); [inference] "
        "pending an SSURGO area-weighted confirmation (onboard SSURGO step needs a footprint)"
    ),
    pre_cover="TODO",  # [open] development land-cover scenario — pending an identified stormwater site (#1436)
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={  # [reference] NOAA Atlas-14 Vol 2 (Ohio River Basin) PDS at 41.3748/-83.6513
        1: 1.99,
        2: 2.40,
        5: 2.98,
        10: 3.46,
        25: 4.14,
        50: 4.69,
        100: 5.28,
        200: 5.90,
        500: 6.76,
        1000: 7.47,
    },
    parcels_relpath="reference/bowling-green/parcel-assemblage.geojson",  # [open] commit the campus geometry (#1436)
    footprint_relpath="extracted/bowling-green/bosc-site-footprint.yaml",  # [open] pending the site footprint (#1436)
    # per-site onboard reach outputs (slug-scoped — never clobber Lima/the other sites)
    climatology_relpath="reference/hydrology/bowling-green/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/bowling-green/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/bowling-green/baseline.yaml",
    rsei_relpath="reference/rsei/bowling-green/inventory.yaml",
    consumer_energy_relpath="reference/eia/bowling-green/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/bowling-green/demand-pressure.yaml",
    grid_relpath="reference/eia/bowling-green/grid-profile.yaml",
    # toxics (no identified industrial corridor yet)
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),  # [open] pending an identified corridor
    # balance — the Portage-side receiving chain, resolved from the permit's own fact sheet (#1439).
    # The city's only municipal POTW. NB the receiving water is NOT the Maumee: BG drinks the Maumee
    # (see `abstraction_gage` below) and discharges to the Portage. Effluent screens key on the North
    # Branch Portage (active gage 04195061), never on the intake reach.
    plant_receiving={
        "bowling-green-wpc": (
            "Poe Ditch RM 2.5 (→ North Branch Portage River RM 8.56 → Portage River → Lake Erie)",
            "Ohio EPA NPDES permit 2PD00009*TD / application OH0024139 (Bowling Green Water "
            "Pollution Control, 901 N. Dunbridge Rd, Wood County); average design flow 10 MGD, "
            "peak hydraulic 30 MGD. Immediate receptor Poe Ditch at River Mile 2.5 (Ohio EPA "
            "river code 16-108, HUC 04100010-03-01, Limited Resource Water), entering the North "
            "Branch Portage River at River Mile 8.56 (river code 16-007, Warmwater Habitat / "
            "Primary Contact Recreation) — and the North Branch Portage's criteria are the ones "
            "applied to this discharge, 'to be protective of this higher quality stream'. "
            "Regulatory low flows (Table 12, drainage-area-adjusted from USGS 04195500 over "
            "1951-97): annual 7Q10 0.364 cfs, 1Q10 0.285 cfs, harmonic mean 3.233 cfs, against a "
            "stated discharger flow of 15.47 cfs — the plant is ~42x the 7Q10 of the water it "
            "enters. Fact Sheet 2PD00009 pp. 1, 6, 30; permit p. 1 — "
            "data/extracted/oepa/bowling-green/2PD00009.fs.npdes.yaml [verified]",
        ),
    },
    abstraction_gage="04193500",  # [inference] the Maumee-at-Waterville intake reach (the city drinks the Maumee)
    # refill (the water-balance supply model is not yet designed for Bowling Green)
    supply_gage_primary="TODO",  # [open] refill supply gage — pending the site's water-balance model
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,  # [open] in-stream passby minimums — pending the model
    passby_secondary_cfs=0.0,
    # grid / facility — the disclosed Meta campus (#1435). SITE-PLAN-grounded (#1327 Urbana precedent):
    # operator/type/floor-area/investment are disclosed [verified]; the IT load is carried as the
    # disclosed ~180 MW peak [reference] (a design ceiling, NOT an air-permit disclosure of the DC's
    # own load — that stays [open]); the campus is designed self-powered BEHIND THE METER by the
    # Apollo plant (350 MW net gas + 119.5 MW / 239 MWh BESS, OPSB 25-0973-EL-BLN — #1437), so
    # the ~2x 350-vs-180 MW oversizing is a Phase-2 signal. No on-site emergency gensets are disclosed
    # for the DC itself (the Apollo gensets are a SEPARATE OPSB-permitted power facility), so
    # genset_count/genset_mw/air_permit_citation stay None. Because the load is served behind the
    # meter ([reference] the Ohio HB 15 self-generation pathway), the economics-demand-pressure feed
    # is a GRID-SERVED COUNTERFACTUAL — the actual grid draw is ~0; the grid-posture modeling is the
    # grid sub-issue (#1440). See data/extracted/bowling-green/data-centers.md.
    facilities=(
        SiteFacility(
            name="Bowling Green Data Center (Project Accordion)",
            status=FacilityLifecycle.CONFIRMED,  # Meta announced 2025-04-09; Apollo OPSB approved 2026-02-03
            operator="Meta Platforms; land/nominee entity Liames, LLC",
            operator_citation=(
                "[verified] Meta, 'Hello, Bowling Green' (2025-04-09); land/nominee entity Liames, LLC "
                "is the customer of record on OPSB 25-0973-EL-BLN."
            ),
            end_use=DcEndUse.HYPERSCALE,
            end_use_citation=(
                "[verified] hyperscale data center — Meta Platforms (Meta 'Hello, Bowling Green', 2025-04-09)."
            ),
            it_load_mw=180.0,  # [reference] the disclosed "up to ~180 MW at peak" — a design ceiling, not an air-permit disclosure
            it_load_low_mw=_BOWLING_GREEN_SCREEN.low,  # 715,000 sq ft x 75 W/sq ft screening floor (avg draw is below the disclosed peak)
            it_load_high_mw=180.0,  # the disclosed ~180 MW peak (the 715k sq ft x 250 W/sq ft screen reproduces 178.75 MW, corroborating it)
            it_load_source=ItLoadGrounding.REFERENCE,
            it_load_citation=(
                "[reference] the disclosed 'up to ~180 MW at peak' for the initial phase — reported via "
                "the Apollo OPSB filings (25-0973-EL-BLN) in press (BG Independent, Data Center "
                "Dynamics), NOT an air-permit or PJM-interconnection disclosure of the data center's own "
                "load, so the official/interconnection MW stays [open]. Carried as the it_load central "
                "per #1435; it is a design CEILING (peak), so downstream figures (peak x PUE x load "
                "factor) run conservative-high. The low bound is a floor-area SCREENING floor — the "
                "disclosed 715,000 sq ft initial building x 75 W/sq ft whole-building IT density (53.6 "
                "MW); the same screen at 250 W/sq ft yields 178.75 MW, closely corroborating the "
                "disclosed ~180 MW peak from just under it (a corroboration, not a second source). The campus is "
                "designed SELF-POWERED behind the meter by the Apollo plant (350 MW NET gas — 491 MW gross, "
                "derated — plus 119.5 MW / 239 MWh of BESS, Will-Power OH LLC, OPSB 25-0973-EL-BLN, approved "
                "2026-02-03, Ohio EPA PTI P0139272 issued 2026-06-02 — #1437); the ~2x 350-vs-180 "
                "MW oversizing signals Phase 2 (Meta's 2026-01-07 trustees letter). NOTE the Apollo air "
                "permit does NOT close this [open]: it permits the PLANT's emissions and names no customer "
                "load. Replace with the disclosed load when an air permit or interconnection filing names it."
            ),
            # No disclosed gensets or air permit for the DC itself (site-plan-grounded) → the N+1 backup
            # cross-check and the air-dispatch fleet model are absent; the Apollo gensets belong to a
            # separate OPSB-permitted power facility (#1437), not the DC's own emergency fleet.
            facility_type=(
                'hyperscale data center campus ("Bowling Green Data Center"; operator Meta Platforms; '
                'land/nominee entity Liames, LLC; codename "Project Accordion")'
            ),  # [verified] operator; [reference] codename
            gross_floor_area_sqft=715_000,  # [verified] Meta — 715,000 sq ft initial phase (+ ~1,700 parking spaces)
            disclosed_investment_usd=800_000_000,  # [verified] Meta ">$800M" (earlier Liames pro-forma ~$750M is [reference])
            disclosure_citation=(
                "[verified] Meta, 'Hello, Bowling Green' (2025-04-09) — the 'Bowling Green Data Center', "
                "Meta's 24th US / 28th global, 2nd in Ohio: 715,000 sq ft initial phase + ~1,700 parking "
                "spaces, >$800M, ~100 permanent jobs (avg ~mid-$80k) / >1,000 peak construction; "
                "corroborated by Middleton Township ('Meta introduced as company behind township data "
                "center'). Site: Middleton Twp, SR-582 between SR-25 and I-75, adjacent the FirstEnergy "
                "Mercer Rd substation; ~280-ac initial site inside a ~750-ac Liames, LLC assembly "
                "([reference] acreage; deeds from 2023-09-05). Liames is the customer of record on OPSB "
                "25-0973-EL-BLN. Phase 2 signaled in Meta's 2026-01-07 trustees letter. See "
                "data/extracted/bowling-green/data-centers.md."
            ),
            # No disclosed cooling/industrial blowdown → None (the cooling back-solve uses the power-
            # derived consumptive as the high bound, no Lima FM-2 leak). The company claims "no
            # operational water".
            # Cooling archetype (#1054): the COMPANY'S CLAIM, recorded as [reference] pending an
            # instrument. Meta describes closed-loop, liquid-cooled with dry coolers ("no operational
            # water"; domestic/cleaning/fire only) → closed_loop_dry. This is in tension with the NWWSD
            # BG-water wholesale (1.5 MGD contract ceiling; conflicting ~50k vs ~600k GPD) — reconciling
            # that is the water sub-issue's job (#1439), not this pin's. Not asserted as verified.
            cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
            cooling_model_source="reference",
            cooling_model_citation=(
                "[reference] company claim (NOT instrument-confirmed): Meta describes closed-loop, "
                "liquid-cooled with dry coolers — 'no operational water', with domestic/cleaning/fire "
                "use only. In tension with the NWWSD wholesaling BG water to Meta (contract ceiling 1.5 "
                "MGD, Aug 2024; conflicting ~50k vs ~600k GPD figures; a Meta-funded 2 MG tank + 16-in "
                "main) — that reconciliation is tracked at the water sub-issue #1439, not decided here. "
                "Replace with a documented cooling design when an NPDES/water instrument lands."
            ),
        ),
    ),
    serving_utility_citation=(  # [reference] not corpus
        "The City of Bowling Green operates a municipal electric utility (an American Municipal "
        "Power member) serving the city proper — EIA-861 2024 Service_Territory confirms it as "
        "utility #2054 (resolved, #1434). The Meta campus in Middleton Twp interconnects to Toledo "
        "Edison (FirstEnergy / PJM ATSI), NOT the muni, and is designed self-powered BEHIND THE "
        "METER by the Apollo plant (OPSB 25-0973-EL-BLN) — so its modelled grid draw is ~0. The "
        "per-utility load share below is therefore a MAGNITUDE comparison against the muni's retail "
        "(the campus dwarfs it at ~3.5x — the point being that the muni could never serve it), NOT "
        "the campus's actual interconnecting utility; a per-facility serving-utility denominator is "
        "a grid-model follow-up (#1440)."
    ),
    # grid (Bowling Green is inside the Toledo Edison / PJM ATSI footprint — the FirstEnergy zone,
    # same as Toledo/Defiance — NOT the AEP zone of the other OH sites)
    lmp_usd_mwh=45.84,  # connector-sourced ATSI-zone 2025 day-ahead annual mean (same zone as Toledo)
    lmp_citation=(
        "PJM Data Miner 2 da_hrl_lmps, ATSI zone (FirstEnergy / Toledo Edison, pnode 116013753), "
        "2025 day-ahead annual mean $45.84/MWh (8760 h); connector-sourced 2026-06-21 (watermark lmp) "
        "— Bowling Green is inside the Toledo Edison/ATSI footprint, not the AEP zone"
    ),
    lmp_pnode_id=116013753,
    lmp_pnode_name="ATSI",
    # rsei
    county_name="Wood County, OH",  # [verified]
)


# Portsmouth / Scioto County — the network's lower-Scioto / Ohio-River-confluence node, registered
# to HOME "Project Dazzler" (the hyperscale campus in Green Township, Scioto County — Google's LLC
# on ~792-914 ac west of U.S. Route 52 near Franklin Furnace/Jr. Furnace, ~38.6067,-82.8392). The
# ten Dazzler §401/PTI wetland-mitigation filings landed FLAT in `data/extracted/permits/*.epa.yaml`
# (their source PDFs are correctly under `data/documents/permits/dazzler-permits/`), so with no site
# owning them they fell through Lima's whole-tree-minus-peers scope and rendered inside Lima's
# Allen-County record/documents/timeline feeds — the #1505 leak, one collection deeper. Registering
# this profile with `corpus_relpaths=("portsmouth", "permits/dazzler-permits")` (the extracted YAMLs
# were relocated under that subdir to mirror the source, per the "extracted mirrors documents by
# collection" rule) subtracts the Dazzler subtree from Lima and homes it here — the same fix pattern
# as Troy/Piqua's #1484 relocation. Thin/registered-only for now (backdrop floor + hydrology/grid/GIS
# knobs are follow-on onboarding, its own readiness epic); `record` is the one active domain.
_PORTSMOUTH = SiteProfile(
    slug="portsmouth",
    # [inference] Scioto County / lower-Scioto / Ohio-confluence region (subregion 0506). The Green
    # Township footprint discharges directly to the OHIO RIVER mainstem below the Scioto confluence
    # (~RM 348), not the Scioto River — the precise receiving-water HUC-12 is [open] pending the
    # source-water/POTW screen. The basin slug is the regional grouping only; no committed POTW
    # inventory exists yet, so the basin screen degrades to empty (correct, not a gap).
    basin="scioto",
    nwis_sites=["TODO"],  # [open] pending the receiving-reach gage (Ohio River / Little Scioto)
    nasa_power_lat=38.606686,  # [verified] Dazzler footprint (permits/dazzler-permits/4081910.epa.yaml)
    nasa_power_lon=-82.839197,  # [verified] "approx. 38.606686 latitude, -82.839197 longitude"
    rsei_fips="39145",  # [verified] Scioto County, OH (state 39 / county 145)
    econ_fips="39145",
    eia861_utility_number=0,  # [open] pending the Scioto County serving-utility EIA-861 id
    eia_state="OH",
    parcels_url="TODO",  # [open] pending the Scioto County OH parcel FeatureServer/MapServer REST endpoint
    zoning_url="TODO",  # [open] pending a Scioto County / Green Township zoning REST endpoint
    floodzone_url="TODO",
    gnis_default_state="OH",
    hydro_utm_epsg=32617,  # [verified] UTM 17N (Portsmouth area ~82.84 degW; zone 17 spans 84-78 degW)
    lsc_default_ga="136",
    gis_parcel=None,  # [open] pending Scioto County OH parcel-layer discovery
    gis_zoning=None,
    gis_flood=None,
    design_lat=38.606686,  # [verified] Dazzler footprint = NOAA Atlas-14 point
    design_lon=-82.839197,
    corridor_name="TODO",  # [open] pending the receiving-water design corridor
    dominant_hsg="TODO",  # [open] pending an SSURGO pull over the campus footprint
    hsg_citation="TODO",
    pre_cover="TODO",
    post_cover="TODO",
    developed_pervious_cover="TODO",
    noaa_fallback_24h_depth_in={},
    parcels_relpath="reference/portsmouth/parcel-assemblage.geojson",  # [open] commit the site's own geometry
    footprint_relpath="extracted/portsmouth/bosc-site-footprint.yaml",  # [open] pending the campus footprint
    climatology_relpath="reference/hydrology/portsmouth/nasa-power-climatology.yaml",
    corridor_ddf_relpath="reference/hydrology/portsmouth/atlas14-corridor-ddf.yaml",
    baseline_relpath="reference/economics/portsmouth/baseline.yaml",
    rsei_relpath="reference/rsei/portsmouth/inventory.yaml",
    consumer_energy_relpath="reference/eia/portsmouth/consumer-energy.yaml",
    demand_pressure_relpath="reference/eia/portsmouth/demand-pressure.yaml",
    grid_relpath="reference/eia/portsmouth/grid-profile.yaml",
    toxic_corridor_bbox=(0.0, 0.0, 0.0, 0.0),
    plant_receiving={},
    abstraction_gage="TODO",
    supply_gage_primary="TODO",
    supply_gage_secondary="TODO",
    passby_primary_cfs=0.0,
    passby_secondary_cfs=0.0,
    facilities=(),  # [open] the disclosed Project Dazzler SiteFacility — pending the site-plan/permit hunt
    # [open] grid identity unconfirmed — Scioto County serving utility + PJM pricing zone pending
    # (eia861_utility_number=0). Honest [open] citations, not raw "TODO" (B3/#1639): the grid-knob
    # readiness check flags this site's grid identity as incomplete so it locks rather than renders.
    serving_utility_citation="[open] Scioto County serving-utility EIA-861 record pending — not yet confirmed",
    lmp_usd_mwh=0.0,
    lmp_citation="[open] PJM pricing zone pending the Scioto County serving-utility confirmation",
    # Home the Dazzler filings here and off Lima: the relocated `permits/dazzler-permits/`
    # collection is filed by PROJECT, not by site, so no rule derives it (subtracted from Lima by
    # `_peer_scope_prefixes`, #1505). This site's own `portsmouth/` subtree is eponymous (#1405).
    corpus_relpaths=("permits/dazzler-permits",),
    county_name="Scioto County, OH",  # [verified] FIPS 39145
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
    _MANSFIELD.slug: _MANSFIELD,
    _BOWLING_GREEN.slug: _BOWLING_GREEN,
    _PORTSMOUTH.slug: _PORTSMOUTH,
}

# The per-site output relpaths `watermark onboard` writes. Each must be unique to its site so
# onboarding never overwrites another site's committed data — a profile that copies Lima
# without slug-scoping these would otherwise clobber Lima's files (#326 hardening).
PER_SITE_OUTPUT_FIELDS: tuple[str, ...] = (
    "climatology_relpath",
    "corridor_ddf_relpath",
    "baseline_relpath",
    "rsei_relpath",
    "enclave_rsei_relpath",
    "consumer_energy_relpath",
    "demand_pressure_relpath",
    "grid_relpath",
    "federal_land_relpath",
)
