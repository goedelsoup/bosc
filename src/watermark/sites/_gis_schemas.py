"""GIS field-map schema *instances* for the registered jurisdictions (#237).

Split out of the former monolithic ``sites.py`` (#597). The schema *models* are the
pure-pydantic leaf :mod:`watermark.connectors.gis_schema`; the per-jurisdiction *instances*
live here (and are re-exported by :mod:`watermark.sites`), where site-specific field names /
encodings / write-meta belong. Lima's schemas reproduce the pre-#237 hardcoded behavior
exactly — see ``tests/test_sites.py`` for the golden + param-stability tests.
"""

from __future__ import annotations

from watermark.connectors.gis_schema import (
    GisCitedZoningMeta,
    GisDefenseConfig,
    GisDefenseMeta,
    GisFloodSchema,
    GisMeta,
    GisParcelSchema,
    GisZoningSchema,
)

# --- GIS field-map schema constants (#237) -------------------------------------------------
# Lima's schemas reproduce the pre-#237 hardcoded field names / encodings / write-meta prose
# exactly (zero-drift): the connector emits the identical request params, so the committed
# fixtures replay and the committed reference YAML stays byte-identical. See tests/test_sites.py
# for the schema golden + param-stability tests. NATIONAL_NFHL_FLOOD_SCHEMA / FINDLAY_* are
# defined just below, from a live FeatureServer metadata read (never fabricated field names).

# Allen County, OH parcel/CAMA layer (was allen_gis._OUT_FIELDS + the inline write-meta).
LIMA_PARCEL_SCHEMA = GisParcelSchema(
    connector="allen_gis",
    reference_dir="allen-gis",
    page_size=1000,
    out_fields=(
        "PARCEL_NO",
        "OWNNAM1",
        "OWNNAM2",
        "DEEDOWN",
        "HOUSENO",
        "ST_DIR",
        "STREET",
        "ST_DESC",
        "OWNADR1",
        "OWNADR2",
        "OWNST",
        "OWNZIP",
        "LNDUSECD",
        "ACRES",
        "MKTLNDVAL",
        "MKTIMPVAL",
        "MKTTOTVAL",
        "CAUVVAL",
        "TAXDIST",
        "SCHOOL",
        "NBRHCODE",
        "DATE",
        "SALEAMT",
        "VAL_SAL",
    ),
    id_field="PARCEL_NO",
    owner_field="OWNNAM1",
    owner_2_field="OWNNAM2",
    deeded_owner_field="DEEDOWN",
    situs_fields=("HOUSENO", "ST_DIR", "STREET", "ST_DESC"),
    owner_addr_fields=("OWNADR1", "OWNADR2"),
    land_use_field="LNDUSECD",
    acres_field="ACRES",
    market_land_field="MKTLNDVAL",
    market_improvement_field="MKTIMPVAL",
    market_total_field="MKTTOTVAL",
    cauv_field="CAUVVAL",
    tax_district_field="TAXDIST",
    school_field="SCHOOL",
    neighborhood_field="NBRHCODE",
    sale_date_field="DATE",
    sale_amount_field="SALEAMT",
    valid_sale_field="VAL_SAL",
    id_normalize="dashless",
    date_decode="mmddyyyy",
    deed_id_regex=r"\b\d{2}-\d{4}-\d{2}-\d{3}\.\d{3}\b",
    meta=GisMeta(
        subject="Allen County, Ohio parcels (CAMA)",
        source="Allen County GIS — ArcGIS REST, Current Parcels (AGOL_NonEditLayers/1)",
        source_url="https://gis.allencountyohio.com/arcgis/rest/services/AGOL/AGOL_NonEditLayers/MapServer/1",
        caveats=(
            "Values are verbatim from the county GIS; null means the service had no value.",
            "Market values are the auditor's appraised values, not sale prices.",
            "last_sale_date is decoded from the GIS M(M)DDYYYY integer; verify against the deed.",
        ),
    ),
    defense=GisDefenseConfig(
        owner_scan_fields=("OWNNAM1", "DEEDOWN", "OWNNAM2"),
        enclave_owner="UNITED STATES",
        enclave_tax_district="L35",
        meta=GisDefenseMeta(
            subject="Allen County, Ohio defense-industry land scan",
            source="Allen County GIS — ArcGIS REST, Current Parcels (AGOL_NonEditLayers/1)",
            source_url="https://gis.allencountyohio.com/arcgis/rest/services/AGOL/AGOL_NonEditLayers/MapServer/1",
            scan="Owner-name match of the curated DoD-prime seed list "
            "(data/entities/profiles/defense-contractors.yaml) against the CAMA "
            "owner / deeded-owner / second-owner fields.",
            finding="No Allen County parcel is owned by a DoD prime in its own name. "
            "The local defense footprint is the federally-held JSMC reservation below.",
            army_controlled_note="[inference] the UNITED STATES-owned cluster in tax "
            "district L35 on Buckeye/Reed Rd is the Joint Systems Manufacturing Center "
            "(Lima Army Tank Plant; 1151 Buckeye Rd), operated by General Dynamics Land "
            "Systems. Ownership is verbatim from the GIS; the JSMC identification is an "
            "analyst inference — verify against the deed/lease before relying on it.",
            caveats=(
                "Values are verbatim from the county GIS; null means the service had no value.",
                "A pattern match is a lead to verify, not a classification or accusation.",
            ),
        ),
    ),
)

# City of Lima, OH zoning layer (was lima_gis zoning fields + the inline write-meta/finding).
LIMA_ZONING_SCHEMA = GisZoningSchema(
    connector="lima_gis",
    reference_dir="lima-gis",
    page_size=10000,
    object_id_field="OBJECTID",
    parcel_field="PARCEL_NO",
    zoning_field="ZONING",
    http_method="POST",
    id_normalize="dashless",
    meta=GisMeta(
        subject="City of Lima, Ohio zoning districts (catalog)",
        source="City of Lima GIS — ArcGIS REST, CitywideMaps/Lima_Zoning, layer 6 'Current Lima Zoning'",
        source_url=(
            "https://colgis.cityhall.lima.oh.us/server/rest/services/"
            "CitywideMaps/Lima_Zoning/MapServer/6"
        ),
        caveats=(
            "Values are verbatim from the City of Lima GIS.",
            "Coverage is Lima CITY LIMITS ONLY; unincorporated Allen County parcels "
            "(e.g. the American Township corridor) are not in this layer.",
            "polygon_count counts zoning polygons, not distinct parcels (a parcel may "
            "carry more than one polygon).",
        ),
    ),
    cited_meta=GisCitedZoningMeta(
        subject="City of Lima zoning for cited corpus parcels (jurisdiction scan)",
        source="City of Lima GIS — ArcGIS REST, CitywideMaps/Lima_Zoning, layer 6, "
        "joined by PARCEL_NO to corpus-cited parcel ids",
        finding_lead="fall within the City of Lima zoning jurisdiction",
        in_city_finding=".",
        out_of_city_finding=" — the corridor (data-center campus + JSMC) sits in American/county "
        "townships, so it is NOT subject to the City of Lima zoning code. Allen County "
        "GIS publishes no county/township zoning layer (only Tax and School districts), "
        "so land-use authority here is township/county, not GIS-mapped.",
        caveats=(
            "Coverage is Lima CITY LIMITS ONLY; in_city=false is a verified outside-"
            "city result, not a missing lookup.",
            "Parcel ids are scanned from data/extracted; normalized to the dashless "
            "PARCEL_NO the GIS join uses.",
        ),
    ),
)

# FEMA DFIRM floodzone layer as served by the City of Lima GIS (was lima_gis flood fields).
LIMA_FLOOD_SCHEMA = GisFloodSchema(
    connector="lima_gis_flood",
    reference_dir="lima-gis",
    page_size=10000,
    object_id_field="OBJECTID",
    fld_zone_field="FLD_ZONE",
    zone_subtype_field="ZONE_SUBTY",
    sfha_field="SFHA_TF",
    static_bfe_field="STATIC_BFE",
    dfirm_id_field="DFIRM_ID",
    source_cit_field="SOURCE_CIT",
    http_method="POST",
    bfe_sentinel=-9999.0,
    sfha_true_value="T",
    meta=GisMeta(
        subject="FEMA flood-hazard zones over Allen County (DFIRM panel 39003C)",
        source="City of Lima GIS — ArcGIS REST, CitywideMaps/Lima_Zoning, layer 4 'Floodzone' (FEMA DFIRM)",
        source_url=(
            "https://colgis.cityhall.lima.oh.us/server/rest/services/"
            "CitywideMaps/Lima_Zoning/MapServer/4"
        ),
        caveats=(
            "Values are verbatim from the FEMA DFIRM served by the City of Lima GIS.",
            "Only Special Flood Hazard Areas (1%-annual-chance: A/AE incl. floodway, AO) "
            "are mapped here; areas outside the SFHA carry no polygon.",
            "A site's flood zone is a SPATIAL question (no PARCEL_NO on this layer) — use "
            "footprint_floodzones() / watermark floodzone --footprint.",
        ),
    ),
)

# The national FEMA NFHL flood layer (S_FLD_HAZ_AR) — the shared, any-US-site flood field-map.
# A site without a local flood REST service points its floodzone_url at this MapServer layer
# and references this schema (overriding reference_dir per site). Field names confirmed from the
# layer metadata 2026-06-19 (they match the FEMA DFIRM standard). Lima keeps its own City-served
# DFIRM schema for zero-drift; it is NOT migrated onto NFHL here (that would change request params).
NATIONAL_NFHL_FLOOD_SCHEMA = GisFloodSchema(
    connector="nfhl_flood",
    reference_dir="nfhl",
    page_size=2000,
    object_id_field="OBJECTID",
    fld_zone_field="FLD_ZONE",
    zone_subtype_field="ZONE_SUBTY",
    sfha_field="SFHA_TF",
    static_bfe_field="STATIC_BFE",
    dfirm_id_field="DFIRM_ID",
    source_cit_field="SOURCE_CIT",
    http_method="POST",
    bfe_sentinel=-9999.0,
    sfha_true_value="T",
    meta=GisMeta(
        subject="FEMA flood-hazard zones (National Flood Hazard Layer, S_FLD_HAZ_AR)",
        source="FEMA NFHL — ArcGIS REST, public/NFHL/MapServer/28 'Flood Hazard Zones'",
        source_url="https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28",
        caveats=(
            "Values are verbatim from the FEMA National Flood Hazard Layer (NFHL).",
            "Only Special Flood Hazard Areas (1%-annual-chance: A/AE incl. floodway, AO) "
            "are mapped; areas outside the SFHA carry no polygon.",
            "A site's flood zone is a SPATIAL question (no parcel id on this layer) — use "
            "footprint_floodzones() / watermark floodzone --footprint.",
            "Field names confirmed from the NFHL layer-28 metadata (2026-06-19).",
        ),
    ),
)

# City of Findlay, OH zoning — a hosted ArcGIS Online FeatureServer. Field names confirmed live
# from the layer-0 metadata 2026-06-19: it is POLYGON-ONLY (no parcel-id field), so the district
# catalog is supported but per-parcel zoning joins are not (cited_meta=None).
FINDLAY_ZONING_SCHEMA = GisZoningSchema(
    connector="findlay_gis",
    reference_dir="findlay-gis",
    page_size=2000,
    object_id_field="FID",
    parcel_field=None,  # polygon-only layer — no parcel id to join on
    zoning_field="Zoning",  # current district label (Category = coarse group; OLDZONING = prior)
    http_method="POST",
    id_normalize="dashless",
    meta=GisMeta(
        subject="City of Findlay, Ohio zoning districts (catalog)",
        source="City of Findlay GIS — ArcGIS Online hosted FeatureServer 'FindlayZoning' "
        "(org XMr9uonP553LyU3o), layer 0",
        source_url=(
            "https://services6.arcgis.com/XMr9uonP553LyU3o/arcgis/rest/services/"
            "FindlayZoning/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the City of Findlay hosted zoning FeatureServer.",
            "Polygon-only layer (no parcel id): the district catalog is supported; per-parcel "
            "zoning joins are not.",
            "Field names confirmed from the layer-0 metadata (2026-06-19).",
        ),
    ),
)


# The OGRIP "Ohio Statewide Parcels Public View" — the shared parcel substitute for any Ohio
# watershed point whose county has no public parcel ArcGIS REST of its own (#237 Findlay follow-up).
# It is one statewide layer, so each site filters it to its county via `query_scope` (e.g.
# `County='Hancock'`), with a site-scoped `reference_dir`, exactly like NATIONAL_NFHL_FLOOD_SCHEMA.
# It is a deliberately PARTIAL fit: the public view is owner-name-redacted (owner appears only
# inside the mailing label, so owner_field is empty and owner searches refuse cleanly), land use is
# a "<code>: <label>" string (decoded leading_int), and there are no market/CAUV/sale/tax fields.
# What it does give, cleanly: the parcel id, situs address, land use code, acreage, and geometry —
# i.e. the parcel catalog + the resolve-to-parcel funnel. Field names confirmed from the live
# layer-0 metadata + a Hancock sample (2026-06-20). Never run an owner/defense scan against it.
OHIO_STATEWIDE_PARCEL_SCHEMA = GisParcelSchema(
    connector="ohio_parcels",
    reference_dir="ohio-parcels",  # per-site override (e.g. "findlay-gis")
    page_size=2000,
    out_fields=(
        "OBJECTID",
        "County",
        "LocalParcelID",
        "StateParcelID",
        "StateLUC",
        "SitusAddressAll",
        "MailAddressAll",
        "LandArea",
    ),
    id_field="LocalParcelID",  # the county-local parcel number (dashless digits)
    owner_field="",  # owner-redacted in the public view (only embedded in the mailing label)
    owner_2_field="",
    deeded_owner_field="",
    situs_fields=("SitusAddressAll",),  # a single pre-assembled situs string
    owner_addr_fields=("MailAddressAll",),  # the mailing label (recipient + city + zip)
    land_use_field="StateLUC",
    acres_field="LandArea",
    market_land_field="",  # absent in this layer -> None (never fabricated)
    market_improvement_field="",
    market_total_field="",
    cauv_field="",
    tax_district_field="",
    school_field="",
    neighborhood_field="",
    sale_date_field="",
    sale_amount_field="",
    valid_sale_field="",
    id_normalize="dashless",
    date_decode="none",
    land_use_decode="leading_int",  # "511: Res-Custom Code" -> 511
    query_scope="",  # set per site (e.g. "County='Hancock'") — base is unscoped (never queried bare)
    deed_id_regex=r"\b\d{12}\b",  # Hancock LocalParcelID is 12 dashless digits (stored; no corpus scan)
    meta=GisMeta(
        subject="Ohio statewide parcels (OGRIP public view), scoped per county",
        source="OGRIP — Ohio Statewide Parcels Public View (owner ogrip_agol), FeatureServer layer 0",
        source_url=(
            "https://services2.arcgis.com/MlJ0G8iWUyC7jAmu/arcgis/rest/services/"
            "OhioStatewidePacels_full_view/FeatureServer/0"
        ),
        caveats=(
            "OGRIP statewide compilation of county parcels; currency varies by county (CurrentTo).",
            "The public view is owner-name-redacted: no owner field (only the mailing label in "
            "MailAddressAll); no market/CAUV value, sale, or tax-district fields.",
            "Land use is a '<code>: <label>' string (StateLUC); the numeric code is parsed out.",
            "Field names confirmed from the live layer-0 metadata + a Hancock sample (2026-06-20).",
        ),
    ),
)


# Putnam County, OH parcels (Ottawa watershed point; #420). Putnam self-hosts a valid-cert ArcGIS
# (`putnamcountygis.com`) whose `Parcels` layer carries owner AND auditor CAMA values on one layer —
# the full fit Findlay's owner-redacted OGRIP substitute can't give. Field names confirmed from the
# live layer-0 `?f=json` + samples (2026-06-21). Notes: OWNER holds the whole owner string (no
# separate second/deeded-owner field); OWNERC/OWNERD are the property situs (an owner may mail to a
# different state — verified against a parcel whose mailing city is The Woodlands, TX); MAILC/MAILD
# are the owner's mailing address; the populated land-use code lives in CLASS_1 (the `Class` field is
# 0/unused here); LANDVALUE/BLDGVALUE are the auditor's land/building values with no combined-total
# field; SALEDATE is a MM-DD-YY string (date_decode="mmddyy"). No CAUV/school/neighborhood/tax-
# district/valid-sale fields on this layer (they stay absent → None, never fabricated); CAUV + the
# full appraisal split live on the separate LandUseParcels CAMA layer, not joined here.
PUTNAM_PARCEL_SCHEMA = GisParcelSchema(
    connector="putnam_gis",
    reference_dir="ottawa-gis",
    page_size=1000,
    out_fields=(
        "PIN",
        "OWNER",
        "OWNERC",
        "OWNERD",
        "MAILC",
        "MAILD",
        "CLASS_1",
        "ACRESOWNED",
        "LANDVALUE",
        "BLDGVALUE",
        "SALEDATE",
        "PURPRI",
    ),
    id_field="PIN",  # 12-digit zero-padded parcel id string (PARCELNUM is the same digits as a float)
    owner_field="OWNER",
    owner_2_field="",  # no separate second-owner field (OWNER carries the full string)
    deeded_owner_field="",  # no separate deeded-owner field
    situs_fields=("OWNERC", "OWNERD"),  # the property situs (location + city/state/zip)
    owner_addr_fields=(
        "MAILC",
        "MAILD",
    ),  # the owner's mailing address (may be out of county/state)
    land_use_field="CLASS_1",  # the populated 3-digit Ohio use code (`Class` is 0/unused here)
    acres_field="ACRESOWNED",
    market_land_field="LANDVALUE",
    market_improvement_field="BLDGVALUE",
    market_total_field="",  # no combined-total field on this layer (never summed/fabricated)
    cauv_field="",  # CAUV lives on the separate LandUseParcels CAMA layer, not joined here
    tax_district_field="",
    school_field="",
    neighborhood_field="",
    sale_date_field="SALEDATE",  # MM-DD-YY string
    sale_amount_field="PURPRI",
    valid_sale_field="",  # PURCOD is a conveyance-type code, not a validity flag — left unmapped
    id_normalize="dashless",
    date_decode="mmddyy",
    deed_id_regex=r"\b\d{12}\b",  # 12 dashless digits (no Putnam corpus scan; pattern for parity)
    meta=GisMeta(
        subject="Putnam County, Ohio parcels (CAMA)",
        source="Putnam County GIS — ArcGIS REST, Parcels/Parcels layer 0 (auditor CAMA + geometry)",
        source_url="https://putnamcountygis.com/arcgis/rest/services/Parcels/Parcels/MapServer/0",
        caveats=(
            "Values are verbatim from the county GIS; null means the service had no value.",
            "Market values are the auditor's land/building appraised values; this layer has no "
            "combined total field, so market_total_value is always null (never summed here).",
            "Land use is the auditor's 3-digit Ohio use code in CLASS_1; the `Class` field is "
            "0/unused in this layer.",
            "OWNERC/OWNERD are the property situs; MAILC/MAILD the owner's (possibly out-of-state) "
            "mailing address.",
            "last_sale_date is decoded from the MM-DD-YY string with the standard %y century pivot "
            "(69-99 -> 1900s, 00-68 -> 2000s); verify the century against the deed near the pivot.",
            "Field names confirmed from the live layer-0 metadata + samples (2026-06-21).",
        ),
    ),
)


# Lucas County, OH parcels (Toledo watershed point; #384). Lucas County's AREIS is the richest GIS
# in the network: a full, valid-cert, self-hosted ArcGIS (lcaudgis.co.lucas.oh.us). The owner-bearing
# CAMA lives on AREIS_Web_Map_MIL1/MapServer layer 38 ("Parcels Land Use Classification"): one polygon
# layer carrying PARID + OWNER + PROPERTY_ADDRESS (situs) + MAILING_ADDRESS + LUC (use code) + ZONING
# + TAXDIST. This is the network's first owner-bearing parcel layer wired from a county's own REST
# (Putnam has owner+value but is a different host; Findlay/Bryan are OGRIP owner-redacted substitutes).
# Field names confirmed from the live layer-38 `?f=json` + Waterville-area samples (2026-06-21).
# NOTE: the auditor's appraised values (APRLAND/APRBLDG/APRTOT) are NOT on this layer — they live on
# layer 83 ("Land Values"), joined by PARID. The single-layer connector can't join, so market values
# stay null here; the PARID value-join is a tracked follow-up (the network's first multi-layer parcel
# connector). No sale-date/amount or CAUV fields on layer 38 either (absent -> None, never fabricated).
LUCAS_AREIS_PARCEL_SCHEMA = GisParcelSchema(
    connector="lucas_areis",
    reference_dir="toledo-gis",
    page_size=2000,
    out_fields=(
        "PARID",
        "OWNER",
        "PROPERTY_ADDRESS",
        "MAILING_ADDRESS",
        "LUC",
        "ACREAGE",
        "TAXDIST",
    ),
    id_field="PARID",  # AREIS parcel id (plain digits, e.g. "3850130")
    owner_field="OWNER",
    owner_2_field="",  # no separate second-owner field on this layer
    deeded_owner_field="",
    situs_fields=(
        "PROPERTY_ADDRESS",
    ),  # a single pre-assembled situs string ("... , WATERVILLE OH 43566")
    owner_addr_fields=("MAILING_ADDRESS",),  # the pre-assembled owner mailing address
    land_use_field="LUC",  # the auditor's land-use code (bare numeric string, e.g. "550")
    acres_field="ACREAGE",
    market_land_field="",  # appraised values are on layer 83 (PARID join) — deferred follow-up
    market_improvement_field="",
    market_total_field="",
    cauv_field="",  # CAUV split is a separate AREIS layer, not joined here
    tax_district_field="TAXDIST",
    school_field="",
    neighborhood_field="",
    sale_date_field="",  # no sale date/amount on the land-use-classification layer
    sale_amount_field="",
    valid_sale_field="",
    id_normalize="dashless",  # PARID is plain digits; dashless tolerates a dotted/dashed input form
    date_decode="none",
    land_use_decode="int",  # bare numeric LUC code
    deed_id_regex=r"\b\d{7}\b",  # AREIS PARID is ~7 digits (no Toledo corpus scan; pattern for parity)
    meta=GisMeta(
        subject="Lucas County, Ohio parcels (AREIS CAMA — land-use classification)",
        source="Lucas County Auditor AREIS — ArcGIS REST, AREIS_Web_Map_MIL1/MapServer layer 38 "
        "('Parcels Land Use Classification')",
        source_url=(
            "https://lcaudgis.co.lucas.oh.us/gisaudserver/rest/services/"
            "AREIS_Web_Map_MIL1/MapServer/38"
        ),
        caveats=(
            "Values are verbatim from the county AREIS; null means the service had no value.",
            "Appraised values (APRLAND/APRBLDG/APRTOT) are NOT on this layer — they live on AREIS "
            "layer 83 (PARID join), so market_*_value is always null here (never fabricated).",
            "PROPERTY_ADDRESS is the situs; MAILING_ADDRESS the owner's mailing address; both are "
            "pre-assembled single strings.",
            "LUC is the auditor's numeric land-use code; CLASS (R/C/E/...) is the coarse use group.",
            "Field names confirmed from the live layer-38 metadata + samples (2026-06-21).",
        ),
    ),
)


# Champaign County, OH parcels (Urbana watershed point; #441/#797). The county auditor map
# (auditor.co.champaign.oh.us/Map) is a Cloudflare-fronted SPA backed by the Champaign County
# Engineer ArcGIS Online org (CCEO, orgId HBIN2hfRscrws7eM); the owner-bearing CAMA join is the
# `parcel_joined` FeatureServer layer 0 — PPOwner + PPAddress (situs street) + PPOwnerAddress
# (mailing, full one-line) + PPClassCode (Ohio CAMA use code) + PPAcres + land/improvement/total
# appraised values + the last sale. SAME-NAME-COUNTY GUARD: this is verified Champaign County
# **OHIO** (FIPS 39021) — owner cities Urbana / St Paris / Mechanicsburg OH (ZIP 43078/43044) and
# WKID 3735 (NAD83 Ohio South ftUS). The same-named Champaign County **ILLINOIS** (FIPS 17019;
# ccgisc.org / gisportal.champaignil.gov / services3.arcgis.com/hrGHbYKdjpN9Dagg) surfaced first in
# discovery and was rejected — it is NOT wired here (#797).
CHAMPAIGN_PARCEL_SCHEMA = GisParcelSchema(
    connector="champaign_cceo",
    reference_dir="urbana-gis",
    page_size=2000,
    out_fields=(
        "Parcel",
        "PPOwner",
        "PPOwnerAddress",
        "PPAddress",
        "PPClassCode",
        "PPAcres",
        "PPLandValue",
        "PPImprValue",
        "PPTotalValue",
        "PPSaleDate",
        "PPAmount",
        "PPHasCAUV",
    ),
    id_field="Parcel",  # dashed, district-letter-prefixed, e.g. "K41-11-10-06-00-005-07"
    owner_field="PPOwner",
    owner_2_field="",  # no separate second-owner field (PPOwner carries the full string)
    deeded_owner_field="",
    situs_fields=("PPAddress",),  # the situs STREET only — no city token (see caveats)
    owner_addr_fields=("PPOwnerAddress",),  # full one-line owner mailing (incl. city/state/ZIP)
    land_use_field="PPClassCode",  # the Ohio CAMA use code (bare int, e.g. 511 res / 111 ag)
    acres_field="PPAcres",
    market_land_field="PPLandValue",
    market_improvement_field="PPImprValue",
    market_total_field="PPTotalValue",
    cauv_field="PPHasCAUV",
    tax_district_field="",  # encoded in the parcel-id leading district letter; no separate field
    school_field="",
    neighborhood_field="",
    sale_date_field="PPSaleDate",  # epoch-millis (e.g. 1718323200000)
    sale_amount_field="PPAmount",
    valid_sale_field="",
    id_normalize="verbatim",  # the dashed, prefixed id is stored verbatim
    date_decode="epoch_millis",
    land_use_decode="int",  # bare numeric CAMA code
    deed_id_regex=r"\b[A-Z]\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-\d{3}-\d{2}\b",
    meta=GisMeta(
        subject="Champaign County, Ohio parcels (CCEO parcel_joined — auditor CAMA)",
        source="Champaign County Engineer ArcGIS Online org (CCEO, HBIN2hfRscrws7eM) — "
        "parcel_joined FeatureServer layer 0 (auditor CAMA + geometry)",
        source_url=(
            "https://services5.arcgis.com/HBIN2hfRscrws7eM/arcgis/rest/services/"
            "parcel_joined/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA; null means the service had no value.",
            "PPAddress is the situs STREET only (no city token); the municipality is derived from "
            "geometry / the parcel-id district prefix, not a column.",
            "PPOwnerAddress is the full one-line owner mailing address (incl. city/state/ZIP).",
            "Verified Champaign County OHIO (FIPS 39021): owner cities Urbana/St Paris/Mechanicsburg "
            "OH, ZIP 43078/43044, WKID 3735 (NAD83 Ohio South). The same-named Champaign Co ILLINOIS "
            "(ccgisc.org / gisportal.champaignil.gov) was found and rejected during discovery (#797).",
            "Field names + samples confirmed from the live layer-0 query (2026-06-27).",
        ),
    ),
)


# City of Toledo / Lucas County zoning (#384): the AREIS Parcel_Zoning layer — a PARCEL-level zoning
# catalog (PARID + ZONING), so unlike Findlay's polygon-only layer it supports the per-parcel join.
LUCAS_ZONING_SCHEMA = GisZoningSchema(
    connector="lucas_zoning",
    reference_dir="toledo-gis",
    page_size=2000,
    object_id_field="OBJECTID",
    parcel_field="PARID",  # parcel-level layer (supports zoning_for_parcel, unlike Findlay)
    zoning_field="ZONING",
    http_method="GET",
    id_normalize="dashless",
    meta=GisMeta(
        subject="Lucas County / City of Toledo zoning districts (catalog)",
        source="Lucas County Auditor AREIS — ArcGIS REST, LandUse_Zoning/Parcel_Zoning/MapServer "
        "layer 0 ('Parcels Zoning')",
        source_url=(
            "https://lcaudgis.co.lucas.oh.us/gisaudserver/rest/services/"
            "LandUse_Zoning/Parcel_Zoning/MapServer/0"
        ),
        caveats=(
            "Values are verbatim from the county AREIS Parcel_Zoning layer.",
            "ZONING is the parcel-level district code (a jurisdiction prefix + district, e.g. "
            "'17-R3'); coverage is county-wide across Lucas jurisdictions, not Toledo city-only.",
            "polygon_count counts zoning polygons, not distinct parcels.",
            "Field names confirmed from the live layer metadata + samples (2026-06-21).",
        ),
    ),
)


# Allen County, IN parcels (Fort Wayne watershed point; #235/#360). The county's iMap ArcGIS
# (`gis1.acimap.us`) serves an owner-bearing Parcel_Poly layer (10) that SDE-joins CurrentOwner —
# owner, situs/mailing address, legal description, and a TransferDate (the deed-transfer date). It
# is the live replacement for the Allen-IN / City-of-Fort-Wayne endpoints the 2026-06-19 onboarding
# pass found, which 404'd by 2026-06-23. A PARTIAL fit vs. an Ohio CAMA layer: no auditor market
# values, land-use code, acreage, CAUV, tax-district, sale-amount, or valid-sale fields on this
# layer (those empty -> None, never fabricated). What it gives cleanly: parcel id, owner of record,
# situs + mailing address, and the transfer date — i.e. the parcel catalog + owner/assembly trail.
# Field names are the fully-qualified SDE names the service returns (selected by name, never index);
# confirmed from the live layer-10 ``?f=json`` + samples (2026-06-26). No federal-enclave defense
# scan is wired (Fort Wayne has no JSMC-equivalent cluster to surface) -> defense=None.
ALLEN_IN_PARCEL_SCHEMA = GisParcelSchema(
    connector="allen_in_gis",
    reference_dir="fort-wayne-gis",
    page_size=1000,
    out_fields=(
        "GISPublished.SDE.Parcel_Poly.PIN",
        "GISPublished.SDE.CurrentOwner.OwnerofRecord",
        "GISPublished.SDE.CurrentOwner.PropertyAddress1",
        "GISPublished.SDE.CurrentOwner.PropertyCity",
        "GISPublished.SDE.CurrentOwner.MailingAddress1",
        "GISPublished.SDE.CurrentOwner.MailingCity",
        "GISPublished.SDE.CurrentOwner.MailingState",
        "GISPublished.SDE.CurrentOwner.MailingZip",
        "GISPublished.SDE.CurrentOwner.TransferDate",
    ),
    id_field="GISPublished.SDE.Parcel_Poly.PIN",
    owner_field="GISPublished.SDE.CurrentOwner.OwnerofRecord",
    owner_2_field="",  # one owner-of-record string (no separate second/deeded owner field)
    deeded_owner_field="",
    situs_fields=(
        "GISPublished.SDE.CurrentOwner.PropertyAddress1",
        "GISPublished.SDE.CurrentOwner.PropertyCity",
    ),
    owner_addr_fields=(
        "GISPublished.SDE.CurrentOwner.MailingAddress1",
        "GISPublished.SDE.CurrentOwner.MailingCity",
        "GISPublished.SDE.CurrentOwner.MailingState",
        "GISPublished.SDE.CurrentOwner.MailingZip",
    ),
    land_use_field="",  # absent on this layer -> None (never fabricated)
    acres_field="",  # acreage is in the legal-description text, not a numeric field
    market_land_field="",
    market_improvement_field="",
    market_total_field="",
    cauv_field="",
    tax_district_field="",
    school_field="",
    neighborhood_field="",
    sale_date_field="GISPublished.SDE.CurrentOwner.TransferDate",
    sale_amount_field="",
    valid_sale_field="",
    id_normalize="dashless",  # the 18-digit PIN; an Indiana state key 02-13-27-100-001.000-077
    date_decode="epoch_millis",  # esriFieldTypeDate (ms since epoch) -> ISO
    # Indiana state parcel number: cc-tt-ss-qqq-ppp.ddd-rrr (county-township-section-...); dashless
    # of that is the stored 18-digit PIN.
    deed_id_regex=r"\b\d{2}-\d{2}-\d{2}-\d{3}-\d{3}\.\d{3}-\d{3}\b",
    meta=GisMeta(
        subject="Allen County, Indiana parcels (owner of record)",
        source="Allen County GIS (iMap) — ArcGIS REST, QueryLayers Parcel_Poly (layer 10) "
        "SDE-joined to CurrentOwner",
        source_url=(
            "https://gis1.acimap.us/imapweb/rest/services/QueryLayers/QueryLayers/MapServer/10"
        ),
        caveats=(
            "Values are verbatim from the county GIS; null means the service had no value.",
            "Owner-bearing but NOT a CAMA layer: no auditor market values, land-use code, acreage, "
            "CAUV, tax district, or sale amount — those fields are empty and resolve to None.",
            "last_sale_date is the CurrentOwner TransferDate (deed transfer), decoded from Esri "
            "epoch-millis; it is the transfer date, not necessarily an arm's-length sale price.",
            "Native CRS is WKID 2244 (Indiana East State Plane, ftUS); request outSR=4326 for WGS84.",
            "Field names are the fully-qualified SDE names the service returns; confirmed from the "
            "live layer-10 metadata + samples (2026-06-26).",
        ),
    ),
)


# Allen County, IN zoning (Fort Wayne; #235/#360). The same iMap MapServer serves a county-wide
# Zoning_Polygons layer (9) carrying a ZONING_CLASS + JURISDICTION_NAME — broader than Lima's
# city-only layer. Polygon-only (no parcel-id field to join on), so — like Findlay — the district
# catalog is supported but per-parcel zoning joins are not (parcel_field=None, cited_meta=None).
FORT_WAYNE_ZONING_SCHEMA = GisZoningSchema(
    connector="allen_in_gis_zoning",
    reference_dir="fort-wayne-gis",
    page_size=1000,
    object_id_field="GISPublished.SDE.Zoning_Polygons.OBJECTID",
    parcel_field=None,  # polygon-only layer — no parcel id to join on (per-parcel join refuses)
    zoning_field="GISPublished.SDE.Zoning_Polygons.ZONING_CLASS",
    http_method="GET",
    id_normalize="dashless",
    meta=GisMeta(
        subject="Allen County, Indiana zoning districts (catalog)",
        source="Allen County GIS (iMap) — ArcGIS REST, QueryLayers Zoning_Polygons (layer 9)",
        source_url=(
            "https://gis1.acimap.us/imapweb/rest/services/QueryLayers/QueryLayers/MapServer/9"
        ),
        caveats=(
            "Values are verbatim from the Allen County (IN) GIS.",
            "Coverage is county-wide (a JURISDICTION_NAME field distinguishes city vs. county), "
            "unlike Lima's city-limits-only zoning layer.",
            "Polygon-only layer (no parcel id): the district catalog is supported; per-parcel "
            "zoning joins are not.",
            "polygon_count counts zoning polygons, not distinct parcels.",
            "Field names confirmed from the live layer-9 metadata (2026-06-26).",
        ),
    ),
)
