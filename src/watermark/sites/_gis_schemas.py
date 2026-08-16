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
            # The same claim as data (#1663) — stamped per-parcel onto the feed so the
            # `[inference]` above is a typed field, not a prefix a consumer has to parse.
            enclave_attribution="Joint Systems Manufacturing Center (Lima Army Tank Plant), "
            "operated by General Dynamics Land Systems",
            enclave_attribution_tag="inference",
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


# Van Wert County, OH parcels (#421). The county's Bruce Harris & Assoc. PAT MapServer
# (`ags.bhamaps.com`) is DEAD, not just cert-expired: the wildcard cert lapsed 2026-05-19 and the
# ArcGIS Server was then removed from the host (bare Microsoft-HTTPAPI 404s) — the county migrated
# to ArcGIS Online (`vanwertcountygis.maps.arcgis.com`, org G5sGKRBVtJMunpVA), the same vendor
# pattern as Champaign's CCEO `parcel_joined`. The owner-bearing auditor CAMA join is the
# `parcel_joinedVWOH` FeatureServer layer 0. Semantics differ from Champaign's twin in four ways:
# the numeric Ohio CAMA use code is **PPClassNumber** (110 ag / 510 res; `PPClassCode` here is the
# coarse class LETTER, A/R/...); there is NO owner mailing-address field (owner_address stays
# None); `PPOnCauv` is a 'True'/'False' string FLAG, not a CAUV dollar value (unmapped — coercing
# it would decode every row to None and read as "no CAUV"); and the stored PIN is the dashless
# 12-digit id (the dashed auditor form `17-034718.0100` is the separate `Parcel` field, so
# id_normalize="dashless" maps a deed-style citation onto the PIN). PPSalesType is a conveyance-
# type code (WD/SV), not a validity flag — left unmapped like Putnam's PURCOD. Field names +
# samples confirmed from the live layer-0 ``?f=json`` + queries (2026-07-11); data vintage
# 2026-05-01 (dataLastEditDate); WKID 3735 (NAD83 Ohio South ftUS) — the right-state guard.
VAN_WERT_PARCEL_SCHEMA = GisParcelSchema(
    connector="van_wert_gis",
    reference_dir="van-wert-gis",
    page_size=2000,
    out_fields=(
        "PIN",
        "PPOwner",
        "PPAddress",
        "PPClassNumber",
        "PPAcres",
        "PPLandValue",
        "PPImprValue",
        "PPTotalValue",
        "PPSaleDate",
        "PPAmount",
    ),
    id_field="PIN",  # dashless 12-digit id (the dashed auditor form is the `Parcel` field)
    owner_field="PPOwner",
    owner_2_field="",  # no separate second-owner field (PPOwner carries the full string)
    deeded_owner_field="",
    situs_fields=("PPAddress",),  # house number + situs STREET only — no city token (see caveats)
    owner_addr_fields=(),  # NO owner mailing-address field on this layer (unlike Champaign's twin)
    land_use_field="PPClassNumber",  # the numeric Ohio use code (PPClassCode = the class letter)
    acres_field="PPAcres",
    market_land_field="PPLandValue",
    market_improvement_field="PPImprValue",
    market_total_field="PPTotalValue",
    cauv_field="",  # PPOnCauv is a 'True'/'False' string flag, not a value — unmapped (caveat)
    tax_district_field="",  # encoded in the PIN's leading district digits; no separate field
    school_field="",
    neighborhood_field="",
    sale_date_field="PPSaleDate",  # epoch-millis (esriFieldTypeDate)
    sale_amount_field="PPAmount",
    valid_sale_field="",  # PPSalesType is a conveyance-type code (WD/SV), not a validity flag
    id_normalize="dashless",  # "17-034718.0100" (deed/auditor form) -> the stored "170347180100"
    date_decode="epoch_millis",
    land_use_decode="int",  # bare numeric PPClassNumber
    deed_id_regex=r"\b\d{2}-\d{6}\.\d{4}\b",  # the auditor's dashed form; dashless of it = the PIN
    meta=GisMeta(
        subject="Van Wert County, Ohio parcels (auditor CAMA join)",
        source="Van Wert County GIS ArcGIS Online org (vanwertcountygis, G5sGKRBVtJMunpVA) — "
        "parcel_joinedVWOH FeatureServer layer 0 (auditor CAMA + geometry)",
        source_url=(
            "https://services8.arcgis.com/G5sGKRBVtJMunpVA/arcgis/rest/services/"
            "parcel_joinedVWOH/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA join; null means the service had no value.",
            "PPAddress is the situs street (house number + street, no city token); there is NO "
            "owner mailing-address field on this layer, so owner_mailing_address is always null.",
            "Land use is the numeric Ohio use code in PPClassNumber; PPClassCode is the coarse "
            "class letter (A/R/...), not the code.",
            "PPOnCauv (a 'True'/'False' string flag) and PPSalesType (a conveyance-type code, "
            "e.g. WD/SV) are not mapped — cauv_value and valid_sale are always null here.",
            "last_sale_date is decoded from the Esri epoch-millis PPSaleDate; verify against "
            "the deed.",
            "The GIS repeats split rows (one PIN can return multiple identical-attribute "
            "polygons); readers dedupe by parcel id.",
            "Field names + samples confirmed from the live layer-0 metadata + queries "
            "(2026-07-11); replaces the retired ags.bhamaps.com PAT MapServer (#421).",
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


# Richland County, OH parcels (Mansfield watershed point; #1431). The county GIS is an on-prem
# ArcGIS Server 10.3 (maps.richlandcountyoh.us) whose Parcel_CAMA MapServer layer 0 ('Parcel')
# joins the auditor CAMA to parcel geometry: parcel id, owner(s), situs + owner mailing address,
# Ohio DTE land-use code, legal acreage, appraised values, tax/school district, and an epoch-millis
# sale date. Two Richland quirks vs. the Champaign/Van Wert ArcGIS-Online twins: (1) the server is
# 10.3, so ``f=geojson`` is NOT supported (only Esri ``f=json`` — the geojson pull for the committed
# parcel-assemblage is done by an esri-rings->GeoJSON recipe, see data/reference/mansfield/README.md;
# owner/attribute queries via ``f=json`` work unchanged); and (2) the auditor ZONING and USEDSCRP
# columns are UNPOPULATED on this layer, so zoning is never read from CAMA here (the I-1->I-2 status
# on the Airport West lots is the Ordinance 25-086 instrument, not an auditor attribute). No
# federal-enclave defense scan is wired -> defense=None. Field names + samples confirmed from the
# live layer-0 ``?f=json`` + queries (2026-07-12); WKID 3734 (NAD83 Ohio North ftUS) — the
# right-state guard for Richland County OHIO (FIPS 39139), not the same-named Richland Co WI/SC/IL.
RICHLAND_PARCEL_SCHEMA = GisParcelSchema(
    connector="richland_gis",
    reference_dir="mansfield-gis",
    page_size=1000,  # the layer's maxRecordCount
    out_fields=(
        "PARCELID",
        "OWNER1",
        "OWNER2",
        "PARCEL_ADDRESS",
        "OWNER_ADDRESS_1",
        "OWNER_ADDRESS_2",
        "OWNER_CSZ",
        "LAND_USE_CODE",
        "LEGAL_ACRES",
        "APPRAISED_LAND_VALUE",
        "APPRAISED_BLDG_VALUE",
        "TOTAL_APPRAISED_VALUE",
        "TAX_DISTRICT",
        "SCHOOL_DISTRICT",
        "NEIGHBORHOOD",
        "SALES_DATE",
        "SALES_PRICE",
        "SALES_VALIDITY_CODE",
    ),
    id_field="PARCELID",  # dashed 3-2-3-2-3 form, e.g. "028-90-150-49-000"
    owner_field="OWNER1",
    owner_2_field="OWNER2",
    deeded_owner_field="",  # no separate deeded-owner column
    situs_fields=("PARCEL_ADDRESS",),
    owner_addr_fields=("OWNER_ADDRESS_1", "OWNER_ADDRESS_2", "OWNER_CSZ"),
    land_use_field="LAND_USE_CODE",  # bare 3-digit Ohio DTE use code (e.g. 640 industrial)
    acres_field="LEGAL_ACRES",  # the recorded legal acreage (CALCULATED_ACRES is planar)
    market_land_field="APPRAISED_LAND_VALUE",
    market_improvement_field="APPRAISED_BLDG_VALUE",
    market_total_field="TOTAL_APPRAISED_VALUE",
    cauv_field="",  # no CAUV value column exposed on this layer -> cauv_value always null
    tax_district_field="TAX_DISTRICT",
    school_field="SCHOOL_DISTRICT",
    neighborhood_field="NEIGHBORHOOD",
    sale_date_field="SALES_DATE",  # Esri esriFieldTypeDate (epoch millis, UTC)
    sale_amount_field="SALES_PRICE",
    valid_sale_field="SALES_VALIDITY_CODE",
    id_normalize="verbatim",  # the dashed id is stored verbatim in PARCELID
    date_decode="epoch_millis",
    land_use_decode="int",  # bare numeric DTE code
    deed_id_regex=r"\b\d{3}-\d{2}-\d{3}-\d{2}-\d{3}\b",
    meta=GisMeta(
        subject="Richland County, Ohio parcels (Parcel_CAMA — auditor CAMA + geometry)",
        source="Richland County GIS (County Engineer Tax Map Office / Auditor CAMA) — "
        "Parcel_CAMA MapServer, layer 0 ('Parcel')",
        source_url=(
            "https://maps.richlandcountyoh.us/richlandgis/rest/services/Parcel_CAMA/MapServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA; null means the service had no value.",
            "ArcGIS Server 10.3: f=geojson is NOT supported (Esri f=json only). Attribute/owner "
            "queries work; the committed parcel geojson uses an esri-rings->GeoJSON recipe "
            "(data/reference/mansfield/README.md), not the f=geojson connector path.",
            "The auditor ZONING and USEDSCRP columns are UNPOPULATED on this layer — zoning is "
            "never read from CAMA here; the Airport West I-1->I-2 status is Ordinance 25-086.",
            "acres is the recorded LEGAL_ACRES; CALCULATED_ACRES (planar) can differ by a few "
            "percent and is not the mapped value.",
            "Multipart parcels are returned as repeated single-ring features (one row per part); "
            "readers assemble them into one MultiPolygon and dedupe attributes by parcel id.",
            "Right-state guard: Richland County OHIO (FIPS 39139), owner city Mansfield OH 449xx, "
            "WKID 3734 (NAD83 Ohio North ftUS). Not the same-named Richland Co WI/SC/IL.",
            "Field names + samples confirmed from the live layer-0 metadata + queries (2026-07-12).",
        ),
    ),
)


# Miami County, OH parcels (Troy/Piqua watershed point; #1483). The county publishes an ArcGIS
# Online `parcel_joined` FeatureServer (org MiamiCountyOhio, wCWf4EGMg4PzHwzA) — the SAME vendor
# pattern and service name as Champaign's CCEO twin, but a DIFFERENT field vocabulary: the numeric
# Ohio CAMA use code is `PPClassNumber` (an Integer, e.g. 101 ag; `PPClassCode` here is the coarse
# class LETTER "A"/"R", like Van Wert's), the owner mailing address is split across four tax-payer
# columns (`TaxPAddr`/`TaxPCity`/`TaxPState`/`TaxPZip`), and `PPHasCAUV` is a 0/1 Integer FLAG (not a
# dollar value) so it is left unmapped like Van Wert's `PPOnCauv`. `PPNote` carries the auditor
# split/merge lineage ("SMDA#: M40-WA022 -005-00") — the parent-parcel trail that tied the Project
# Klondike (J5 LLC) assemblage together. The dashless id is the separate `Parcel2` field; the dashed,
# district-letter-prefixed `PARCEL` ("N44-101834") is the canonical/auditor form, stored verbatim.
# Field names + samples confirmed from the live layer-0 `?f=json` metadata + queries (2026-07-13);
# WKID 3735 (NAD83 Ohio South ftUS) — the right-state guard.
MIAMI_PARCEL_SCHEMA = GisParcelSchema(
    connector="miami_gis",
    reference_dir="troy-piqua-gis",
    page_size=2000,  # the layer's maxRecordCount
    out_fields=(
        "PARCEL",
        "PPOwner",
        "PPAddress",
        "PPClassNumber",
        "PPAcres",
        "TaxPAddr",
        "TaxPCity",
        "TaxPState",
        "TaxPZip",
        "TaxDist",
        "School",
        "Neighborhood",
        "PPLandValue",
        "PPImprValue",
        "PPTotalValue",
        "PPSaleDate",
        "PPAmount",
    ),
    id_field="PARCEL",  # dashed, district-letter-prefixed, e.g. "N44-101834" (Parcel2 = dashless)
    owner_field="PPOwner",
    owner_2_field="",  # no separate second-owner field (PPOwner carries the full string)
    deeded_owner_field="",
    situs_fields=("PPAddress",),  # the situs STREET only — no city token (see caveats)
    owner_addr_fields=("TaxPAddr", "TaxPCity", "TaxPState", "TaxPZip"),  # tax-payer mailing, split
    land_use_field="PPClassNumber",  # the numeric Ohio CAMA use code (PPClassCode = the class letter)
    acres_field="PPAcres",
    market_land_field="PPLandValue",
    market_improvement_field="PPImprValue",
    market_total_field="PPTotalValue",
    cauv_field="",  # PPHasCAUV is a 0/1 Integer flag, not a value — unmapped (caveat), like Van Wert
    tax_district_field="TaxDist",
    school_field="School",
    neighborhood_field="Neighborhood",
    sale_date_field="PPSaleDate",  # Esri esriFieldTypeDate (epoch millis)
    sale_amount_field="PPAmount",
    valid_sale_field="",
    id_normalize="verbatim",  # the dashed, prefixed id is stored verbatim (like Champaign's twin)
    date_decode="epoch_millis",
    land_use_decode="int",  # bare numeric PPClassNumber
    deed_id_regex=r"\b[A-Z]\d{2}-\d{6}\b",  # the auditor PARCEL form (N44-101834); deed-cited form [inference]
    meta=GisMeta(
        subject="Miami County, Ohio parcels (parcel_joined — auditor CAMA + geometry)",
        source="Miami County, Ohio ArcGIS Online org (MiamiCountyOhio, wCWf4EGMg4PzHwzA) — "
        "parcel_joined FeatureServer layer 0 (auditor CAMA + geometry)",
        source_url=(
            "https://services3.arcgis.com/wCWf4EGMg4PzHwzA/arcgis/rest/services/"
            "parcel_joined/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA join; null means the service had no value.",
            "PPAddress is the situs STREET only (no city token); the municipality is in the "
            "separate City/Twp columns, not appended here.",
            "Owner mailing address is assembled from the four tax-payer columns "
            "(TaxPAddr/TaxPCity/TaxPState/TaxPZip).",
            "Land use is the numeric Ohio use code in PPClassNumber; PPClassCode is the coarse "
            "class letter (A/R/...), not the code.",
            "PPHasCAUV (a 0/1 Integer flag) is not mapped — cauv_value is always null here; the "
            "committed assemblage geojson carries the boolean has_cauv separately.",
            "PPNote carries the auditor split/merge lineage (SMDA#), the parent-parcel trail.",
            "last_sale_date is decoded from the Esri epoch-millis PPSaleDate; verify against "
            "the deed. The GIS can repeat split rows (one PARCEL, multiple polygons); readers "
            "dedupe/assemble by parcel id.",
            "Right-state guard: Miami County OHIO (FIPS 39109), owner cities Piqua/Troy OH "
            "45356/45373, WKID 3735 (NAD83 Ohio South ftUS). Not the same-named Miami-Dade FL / "
            "Miami County IN / KS / OH-Hamilton 'Miami' townships.",
            "Field names + samples confirmed from the live layer-0 metadata + queries (2026-07-13).",
        ),
    ),
)


# City of Piqua, OH zoning (Troy/Piqua watershed point; #830). The City publishes its form-based
# code on its own ArcGIS Online org ("City of Piqua", kZPPWTIJ6kOFJTWc) — a single polygon layer,
# `Zoning_Districts_public_view/FeatureServer/17` ("Code Piqua"). Unlike Findlay's polygon-only
# layer, this one carries the auditor `PARCEL` id (dashed "N44-…" — the SAME canonical form as the
# Miami County parcel layer above), so per-parcel zoning joins work: the Project Klondike campus
# parcel `N44-101770` returns `IH` (Industrial Heavy), and the adjacent `N44-101808` returns `IL`
# (Industrial Light) — the situs check that confirms the campus footprint sits in the City of
# Piqua's heavy/light-industrial districts (matching the "annexed and zoned heavy-industrial"
# record in data/extracted/troy-piqua/data-centers.md). The district label is `CPZoneDist` (a
# coded-value domain: 26 districts; IH/IL are the two industrial ones). Coverage is CITY LIMITS
# ONLY — unincorporated Miami County townships are a separate county layer, and the two other
# J5 campus parcels (N44-101834/-101846) post-date this layer's 2025-02 snapshot, a currency gap.
# Field names + the parcel-join sample confirmed from the live layer-17 `?f=pjson` + queries
# (2026-07-13); it is the public view (its internal twin carries an "informational only" disclaimer).
PIQUA_ZONING_SCHEMA = GisZoningSchema(
    connector="piqua_gis",
    reference_dir="troy-piqua-gis",  # shared with the Miami parcel + NFHL flood schemas
    page_size=2000,
    object_id_field="OBJECTID_1",
    parcel_field="PARCEL",  # dashed auditor id "N44-101770" (Parcel2 = dashless) — joins to Miami CAMA
    zoning_field="CPZoneDist",  # the form-based district code (coded-value domain; IH/IL = industrial)
    http_method="POST",
    id_normalize="verbatim",  # the dashed, prefixed id is stored verbatim (like the parcel layer)
    meta=GisMeta(
        subject="City of Piqua, Ohio zoning districts (form-based code catalog)",
        source="City of Piqua GIS — ArcGIS Online hosted FeatureServer 'Zoning_Districts_public_view' "
        "(org kZPPWTIJ6kOFJTWc), layer 17 'Code Piqua'",
        source_url=(
            "https://services8.arcgis.com/kZPPWTIJ6kOFJTWc/arcgis/rest/services/"
            "Zoning_Districts_public_view/FeatureServer/17"
        ),
        caveats=(
            "Values are verbatim from the City of Piqua hosted zoning FeatureServer.",
            "Coverage is Piqua CITY LIMITS ONLY; unincorporated Miami County townships (and the "
            "City of Troy) carry their own separate zoning layers, not this one.",
            "polygon_count counts zoning polygons, not distinct parcels (a parcel may carry more "
            "than one polygon).",
            "Currency: rows last edited 2025-02; the J5 campus parcels N44-101834/-101846 "
            "(re-platted/conveyed Dec 2025) are not yet in this snapshot — N44-101770 is, as IH.",
            "Right-state guard: City of Piqua, MIAMI County OHIO (auditor PARCEL 'N44-…'); not "
            "the same-named Piqua elsewhere. Prefer the public view over its internal twin "
            "('informational purposes only' disclaimer).",
            "Field names confirmed from the live layer-17 metadata + queries (2026-07-13).",
        ),
    ),
    cited_meta=GisCitedZoningMeta(
        subject="City of Piqua zoning for cited corpus parcels (jurisdiction scan)",
        source="City of Piqua GIS — Zoning_Districts_public_view layer 17, joined by PARCEL to "
        "corpus-cited parcel ids",
        finding_lead="fall within the City of Piqua zoning jurisdiction",
        in_city_finding=".",
        out_of_city_finding=" — a no-match here does NOT by itself confirm they are outside the "
        "city: each unmatched parcel is EITHER in unincorporated Miami County / the City of Troy "
        "(a separate zoning layer) OR in-city but post-dating this layer's 2025-02 snapshot (e.g. "
        "the J5 campus parcels N44-101834 / N44-101846, annexed/re-platted after the snapshot) — "
        "which of the two is UNKNOWN without separate jurisdiction evidence.",
        caveats=(
            "Coverage is Piqua CITY LIMITS ONLY, and the layer is a 2025-02 snapshot — so a "
            "no-match is NOT necessarily an outside-city result: a parcel annexed/re-platted after "
            "the snapshot (e.g. J5 campus N44-101834 / N44-101846) is absent yet in-city. Treat a "
            "no-match as UNKNOWN pending separate jurisdiction evidence; only a parcel independently "
            "placed in an unincorporated township / the City of Troy is a verified outside-city result.",
            "Parcel ids are scanned from data/extracted and matched verbatim to the dashed "
            "PARCEL the GIS join uses (no dash-stripping — the layer stores 'N44-101770').",
        ),
    ),
)


# Shelby County, OH parcels (Sidney watershed point; #1379). Sidney's profile had been pointed at
# the OGRIP statewide substitute, which for Shelby is BOTH owner-redacted AND a 2023-05-23 county
# extract (`CurrentTo`) — i.e. it predates the entire Project Galaxy land transfer and cannot name
# a grantee. The Shelby County Engineer's Office publishes the auditor CAMA join on its own AGOL org
# instead: owner, deed volume/page, conveyance date + consideration, appraised values, CAUV /
# exemption / abatement flags, legal description and tax district all on layer 0 with the geometry —
# the same full fit Miami/Champaign give Troy-Piqua/Urbana. That upgrade is what closes the register's
# acreage `[open]`: it resolves 2388 W. Millcreek Rd to `26-03-201-002` (243.092 ac, AMAZON DATA
# SERVICES INC, conveyed 2025-11-24 for $5,621,490, OR2329/454). Field names + samples confirmed
# from the live layer-0 metadata + queries (2026-07-31).
SHELBY_PARCEL_SCHEMA = GisParcelSchema(
    connector="shelby_gis",
    reference_dir="sidney-gis",
    page_size=2000,  # the layer's maxRecordCount
    out_fields=(
        "PIN",
        "Listed_Name",
        "Location_Address",
        "Location_City_State_Zip",
        "Acres",
        "Land_Use_Code",
        "District_Name",
        "School_District",
        "Appraised_Land_100",
        "Appraised_Improvement_100",
        "Appraised_Total_100",
        "Date_Conveyed",
        "Consideration",
        "Valid_Sale",
        "Owner_Contact_Address",
        "Owner_Contact_City",
        "Owner_Contact_State",
        "Owner_Contact_ZipCode",
    ),
    id_field="PIN",  # the dashed auditor parcel number, e.g. "26-03-201-002"
    owner_field="Listed_Name",  # the CAMA owner of record
    owner_2_field="",  # no second-owner field (Listed_Name carries the whole string)
    deeded_owner_field="",  # Owner_Contact_Name duplicates Listed_Name here — not a distinct slot
    situs_fields=("Location_Address", "Location_City_State_Zip"),
    owner_addr_fields=(
        "Owner_Contact_Address",
        "Owner_Contact_City",
        "Owner_Contact_State",
        "Owner_Contact_ZipCode",
    ),
    land_use_field="Land_Use_Code",  # bare numeric Ohio use code (Land_Use_Name = the label)
    acres_field="Acres",  # the auditor's DEEDED acreage, not a GIS planar measure (CalcAcres is null)
    market_land_field="Appraised_Land_100",
    market_improvement_field="Appraised_Improvement_100",
    market_total_field="Appraised_Total_100",
    cauv_field="",  # Has_CAUV is a YES/NO flag, not a value — unmapped, like Miami/Van Wert
    tax_district_field="District_Name",
    school_field="School_District",
    neighborhood_field="",  # absent in this layer -> None (never fabricated)
    sale_date_field="Date_Conveyed",  # Esri esriFieldTypeDate (epoch millis)
    sale_amount_field="Consideration",
    valid_sale_field="Valid_Sale",  # a "True"/"False" string, stored verbatim
    id_normalize="verbatim",  # the dashed PIN is stored verbatim (PIN_No_Dash is the dashless twin)
    date_decode="epoch_millis",
    land_use_decode="int",
    deed_id_regex=r"\b\d{2}-\d{2}-\d{3}-\d{3}\b",  # the dashed auditor PIN form (26-03-201-002)
    meta=GisMeta(
        subject="Shelby County, Ohio parcels (auditor CAMA + geometry)",
        source="Shelby County Engineer's Office ArcGIS Online org (BHA_sceo, fzPZZJiNVtryYcsC) — "
        "Parcels FeatureServer layer 0 (auditor CAMA join)",
        source_url=(
            "https://services6.arcgis.com/fzPZZJiNVtryYcsC/arcgis/rest/services/"
            "Parcels/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA join; null means the service had no value.",
            "Acres is the auditor's DEEDED acreage from the tax record, not a GIS planar measure "
            "(the layer's CalcAcres column is null throughout) — the two differ, so a planar "
            "acreage must be measured from the geometry and reported as a separate figure.",
            "Appraised_*_100 are the 100% appraised (market) values; the Taxable_*_100 twins are "
            "the assessed 35% figures and are NOT what market_* carries here.",
            "Has_CAUV / Has_Exemption / Has_Abatement are YES/NO flags, not values — cauv_value is "
            "always null; the committed assemblage geojson carries the booleans separately.",
            "Deed_Volume/Deed_Page (the auditor Official-Record locator, e.g. OR2329/454) and "
            "Legal_Description are on the layer but have no GisParcelSchema slot; the assemblage "
            "recipe reads them directly.",
            "A consolidation plat retires its predecessor parcels: the current layer holds only the "
            "surviving PIN, so a pre-consolidation situs address (e.g. '2388 W. Millcreek Rd') "
            "resolves to NOTHING here — reconcile it geometrically against a prior-vintage layer.",
            "Right-state guard: Shelby County OHIO (FIPS 39149), districts 'CLINTON TWP SIDNEY "
            "CORP …', WKID 3735 (NAD83 Ohio South ftUS). Not the same-named Shelby County in "
            "TN / KY / IN / IL / AL / MO / TX.",
            "Field names + samples confirmed from the live layer-0 metadata + queries (2026-07-31).",
        ),
    ),
)


# City of Sidney, OH zoning (Sidney watershed point; #1379). The City's GIS Department publishes its
# districts through the county auditor's ArcGIS server, as a polygon-only layer (ZONING label + CODE)
# with NO parcel id — the Findlay shape, not Piqua's: the district catalog works, per-parcel joins do
# not. Nine districts (CC / CSD / IIM / NC / R-1 / R-2 / R-3 / TND). Coverage is CITY LIMITS ONLY and
# the layer was "officially adopted on October 24, 2016"; the sibling Annexation layer's most recent
# record is ordinance A-3145 (2023-08-28). The Project Galaxy campus parcel (26-03-201-002) therefore
# falls in a HOLE in all three city polygon layers — zoning, corp limits, and annexation all MISS its
# interior point, while its two district-01 neighbours (SEMCORP 26-03-301-001 -> IIM, DP&L
# 26-03-429-009 -> CC) hit all three. So the campus's zoning district is UNKNOWN from this layer, not
# unzoned: the auditor's TY2025 tax district already places it inside the Sidney corporate limits.
# Field names + the coverage probe confirmed from the live layer-270 metadata + queries (2026-07-31).
SIDNEY_ZONING_SCHEMA = GisZoningSchema(
    connector="sidney_gis",
    reference_dir="sidney-gis",  # shared with the Shelby parcel + NFHL flood schemas
    page_size=1000,  # the layer's maxRecordCount
    object_id_field="OBJECTID_1",
    parcel_field=None,  # polygon-only layer — no parcel id to join on (the Findlay case)
    zoning_field="CODE",  # the district code (ZONING = the long label)
    http_method="GET",
    id_normalize="verbatim",
    meta=GisMeta(
        subject="City of Sidney, Ohio zoning districts (catalog)",
        source="City of Sidney GIS Department — ArcGIS MapServer "
        "'City_of_Sidney/SidneyGIS_AllLayers', layer 270 'Zoning' (hosted on the Shelby County "
        "Auditor's server; twin at City_of_Sidney/Intranet_Map_Original_CAD layer 23)",
        source_url=(
            "https://cama.shelbycountyauditors.com/arcgis/rest/services/City_of_Sidney/"
            "SidneyGIS_AllLayers/MapServer/270"
        ),
        caveats=(
            "Values are verbatim from the City of Sidney zoning layer.",
            "Polygon-only layer (no parcel id): the district catalog is supported; per-parcel "
            "zoning joins are not.",
            "Coverage is Sidney CITY LIMITS ONLY; unincorporated Shelby County townships carry no "
            "district here.",
            "Currency: the layer is described as 'Officially adopted on October 24, 2016' and the "
            "sibling Annexation layer (SidneyGIS_AllLayers/76) stops at ordinance A-3145, "
            "2023-08-28 — so land annexed after that is absent from zoning, corp limits AND "
            "annexation alike.",
            "The Project Galaxy campus parcel 26-03-201-002 is exactly that gap: all three city "
            "layers MISS its interior point while its district-01 neighbours hit them, so its "
            "zoning district is UNKNOWN here — NOT 'unzoned' and NOT 'outside the city' (the "
            "auditor's TY2025 tax district 01 places it inside the Sidney corporate limits).",
            "Right-state guard: City of Sidney, SHELBY County OHIO 45365 (GIS Dept, 201 W Poplar "
            "St). Not the same-named Sidney in NY / MT / NE / IA / OH-Champaign 'Sidney' usages.",
            "Field names confirmed from the live layer-270 metadata + queries (2026-07-31).",
        ),
    ),
)


# Clinton County, OH parcels (Wilmington watershed point; #1470). Wilmington's profile had been
# pointed at the OGRIP statewide substitute scoped to `County='Clinton'` — a layer that is
# owner-redacted by construction AND, for Clinton, carries a NULL `CurrentTo` (no stated export
# date at all) with `SitusAddressAll` / `LandArea` null on a large share of rows. It cannot name a
# grantee, so the whole Cosler Farm / Ardent-TAC corridor was invisible through it. The Clinton
# County GIS Department publishes the auditor CAMA join on its own AGOL org instead
# (`cntyparcelsRealPropData_gdb` layer 0 — the layer the City's own "Wilmington Zoning Updated" web
# map uses as its Parcel layer): owner, deed instrument, conveyance date + consideration, appraised
# values, CAUV / exemption / abatement flags, legal description, tax district, situs and a
# per-parcel county-zoning join, all with the geometry. That upgrade is what makes the corridor
# readable — it resolves 1488 S US 68 to `285-13-02-01-0000-00` (471.609 ac, AMAZON DATA SERVICES
# INC, conveyed 2025-12-10 for $86,436,000 on instrument 2025-00005287) and puts the four
# Ardent/TAC rezoning tracts in the annexed tax district 285. Field names + samples confirmed from
# the live layer-0 metadata + queries (2026-08-01).
#
# NOTE the county publishes THREE parcel layers on two orgs and only this one is current:
# `cntyparcels` (the CCRPC org, services7/5ML1cxkkvVfOhDrS) is a TAX-YEAR-2022 snapshot whose
# `dataLastEditDate` is 2023-08-28, and `cntyparcelsRealPropData_gdb_ZONING` is a 2026-06-03 cut of
# the same join. Pull from `cntyparcelsRealPropData_gdb`; check `editingInfo.dataLastEditDate`
# before believing a negative.
CLINTON_PARCEL_SCHEMA = GisParcelSchema(
    connector="clinton_gis",
    reference_dir="wilmington-gis",
    page_size=2000,  # the layer's maxRecordCount
    out_fields=(
        "PIN",
        "Listed_Name",
        "Location_Address",
        "Location_City_State_Zip",
        "Acres",
        "Land_Use_Code",
        "District_Name",
        "School_District",
        "Neighborhood_Name",
        "Appraised_Land_100",
        "Appraised_Improvement_100",
        "Appraised_Total_100",
        "Date_Conveyed",
        "Consideration",
        "Valid_Sale",
        "Owner_Contact_Address",
        "Owner_Contact_City",
        "Owner_Contact_State",
        "Owner_Contact_ZipCode",
    ),
    id_field="PIN",  # the dashed auditor parcel number, e.g. "285-13-02-01-0000-00"
    owner_field="Listed_Name",  # the CAMA owner of record
    owner_2_field="",  # no second-owner field (Listed_Name carries the whole string)
    deeded_owner_field="",  # Owner_Contact_Name duplicates Listed_Name here — not a distinct slot
    situs_fields=("Location_Address", "Location_City_State_Zip"),
    owner_addr_fields=(
        "Owner_Contact_Address",
        "Owner_Contact_City",
        "Owner_Contact_State",
        "Owner_Contact_ZipCode",
    ),
    land_use_field="Land_Use_Code",  # bare numeric Ohio use code (Land_Use_Name = the label)
    acres_field="Acres",  # the auditor's DEEDED acreage, not a GIS planar measure
    market_land_field="Appraised_Land_100",
    market_improvement_field="Appraised_Improvement_100",
    market_total_field="Appraised_Total_100",
    cauv_field="",  # Has_CAUV is a YES/NO flag, not a value — unmapped, like Shelby/Miami
    tax_district_field="District_Name",
    school_field="School_District",
    neighborhood_field="Neighborhood_Name",
    sale_date_field="Date_Conveyed",  # an already-formatted "M/D/YYYY h:mm:ss AM" STRING, not a date
    sale_amount_field="Consideration",
    valid_sale_field="Valid_Sale",  # a "True"/"False" string, stored verbatim
    id_normalize="verbatim",  # the dashed PIN is stored verbatim (PARCELID is the dashless twin)
    date_decode="mdyyyy_slash",  # "12/10/2025 12:00:00 AM" -> 2025-12-10 (text, not an Esri date)
    land_use_decode="int",
    deed_id_regex=r"\b\d{3}-\d{2}-\d{2}-\d{2}-\d{4}-\d{2}\b",  # 285-13-02-01-0000-00
    meta=GisMeta(
        subject="Clinton County, Ohio parcels (auditor CAMA + geometry)",
        source="Clinton County GIS Department ArcGIS Online org (tAhcHWpOD9ygNPbJ) — "
        "cntyparcelsRealPropData_gdb FeatureServer layer 0 (auditor CAMA join)",
        source_url=(
            "https://services1.arcgis.com/tAhcHWpOD9ygNPbJ/arcgis/rest/services/"
            "cntyparcelsRealPropData_gdb/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA join; null means the service had no value.",
            "Acres is the auditor's DEEDED acreage from the tax record, not a GIS planar measure — "
            "the two differ, so a planar acreage must be measured from the geometry and reported "
            "as a separate figure.",
            "Appraised_*_100 are the 100% appraised (market) values; the Taxable_*_100 twins are "
            "the assessed 35% figures and are NOT what market_* carries here.",
            "Has_CAUV / Has_Exemption / Has_Abatement are YES/NO flags, not values — cauv_value is "
            "always null; the committed assemblage geojson carries the booleans separately.",
            "Deed_Volume carries the RECORDER INSTRUMENT NUMBER (e.g. '2025-00005287') for recent "
            "conveyances and a book number for older ones, with Deed_Page empty in the first case; "
            "it has no GisParcelSchema slot, so the assemblage recipe reads it directly.",
            "Consideration is the WHOLE DEED's consideration repeated on every parcel it conveyed "
            "— the three Amazon parcels each read $86,436,000 for the one instrument "
            "2025-00005287. Never sum it across parcels.",
            "Date_Conveyed is a STRING ('12/10/2025 12:00:00 AM'), not an esriFieldTypeDate — a "
            "date-typed query predicate against it will not behave; filter on it as text.",
            "Auditor_Link is published with an UNSUBSTITUTED '{Property ID}' placeholder and does "
            "not resolve; AudWeb (…/RealEstate/Default/Lookup?number=<dashless PIN>) is the "
            "working per-parcel auditor URL.",
            "ZoningDist / ZoningDi_1 / CntyZoning / Township are the COUNTY (township) zoning "
            "join and are NULL for any parcel inside a municipality — a null there means "
            "'municipally zoned, look at the city layer', not 'unzoned'.",
            "The county publishes older twins of this layer: 'cntyparcels' on the CCRPC org "
            "(services7/5ML1cxkkvVfOhDrS) is a tax-year-2022 snapshot last edited 2023-08-28, and "
            "'cntyparcelsRealPropData_gdb_ZONING' is a 2026-06-03 cut. Check "
            "editingInfo.dataLastEditDate before believing a negative result.",
            "Right-state guard: Clinton County OHIO (FIPS 39027), districts '285-UNION "
            "TWP-WILMINGTON' / '290-CITY OF WILMINGTON', WKID 3857 as served. Not the same-named "
            "Clinton County in PA / NY / IN / MI / IA / IL / KY / MO / OH-adjacent usages — the "
            "Clinton County, PA data-center moratorium is a live search trap for this site.",
            "Field names + samples confirmed from the live layer-0 metadata + queries "
            "(2026-08-01); tax year 2025, Extract_ID 1135, dataLastEditDate 2026-07-30.",
        ),
    ),
)


# City of Wilmington, OH zoning (Wilmington watershed point; #1470). The City's districts are
# published by the Clinton County Regional Planning Commission as a polygon-only layer (a single
# `ZONING` code, no parcel id) — the Findlay/Sidney shape, not Piqua's: the district catalog works,
# per-parcel joins do not. Thirteen districts over 29 polygons, city limits only. The service is
# named "ProposedZoning9" but it is the layer the City's published "Wilmington Zoning Map 2024"
# application and the CCRPC "Wilmington Zoning Updated" web map both render as **Zoning**; its
# `dataLastEditDate` is 2026-02-10, which is the fact that matters here — see the caveats.
WILMINGTON_ZONING_SCHEMA = GisZoningSchema(
    connector="wilmington_gis",
    reference_dir="wilmington-gis",  # shared with the Clinton parcel + NFHL flood schemas
    page_size=2000,  # the layer's maxRecordCount
    object_id_field="OBJECTID",
    parcel_field=None,  # polygon-only layer — no parcel id to join on (the Findlay case)
    zoning_field="ZONING",
    http_method="GET",
    id_normalize="verbatim",
    meta=GisMeta(
        subject="City of Wilmington, Ohio zoning districts (catalog)",
        source="Clinton County Regional Planning Commission ArcGIS Online org "
        "(services7/5ML1cxkkvVfOhDrS) — 'ProposedZoning9' FeatureServer layer 0, the Zoning layer "
        "of the City's 'Wilmington Zoning Map 2024' application and the CCRPC 'Wilmington Zoning "
        "Updated' web map",
        source_url=(
            "https://services7.arcgis.com/5ML1cxkkvVfOhDrS/arcgis/rest/services/"
            "ProposedZoning9/FeatureServer/0"
        ),
        caveats=(
            "Values are verbatim from the CCRPC zoning layer.",
            "Polygon-only layer (no parcel id): the district catalog is supported; per-parcel "
            "zoning joins are not.",
            "Coverage is Wilmington CITY LIMITS ONLY; unincorporated Clinton County townships "
            "carry their district on the county layers instead (CountyWideZoning, or the "
            "ZoningDist column of the parcel CAMA join).",
            "CURRENCY IS THE POINT OF THIS LAYER FOR #1470: dataLastEditDate is 2026-02-10. It "
            "therefore DOES carry the Cosler Farm map rezoning (a discrete 471.272-ac LI polygon "
            "over parcel 285-13-02-01-0000-00) and CANNOT carry the four Ardent/TAC rezonings, "
            "which City Council passed 5-2 on 2026-02-19/20 — nine days later. Those four "
            "parcels' interior points fall in NO city polygon and still read the COUNTY's 'S-R' "
            "Suburban Residential; that is a publication lag, not a finding about their zoning.",
            "How well that polygon fits the parcel, stated as a measurement rather than a ratio "
            "of two totals: intersecting the two geometries in UTM 17N (EPSG:32617) gives 470.931 "
            "ac of overlap, which is 99.73% OF THE PARCEL (470.931 / 472.221 ac planar) and "
            "99.93% OF THE LI POLYGON (470.931 / 471.272 ac). Quote the first — 'the zoning "
            "covers the land' is the claim being made. Do NOT derive either figure by dividing "
            "the polygon's area by the parcel's DEEDED 471.609 ac: that arithmetic never "
            "intersects the shapes, so it would report a fit even for a polygon lying somewhere "
            "else entirely, and it happens to land on 99.93% here by coincidence.",
            "The Cosler Farm LI polygon is one of the three ordinances a federal court ordered the "
            "City to redo for defective 30-day notice (Sharp v. City of Wilmington, S.D. Ohio "
            "1:26-cv-00448, ~2026-07-09/10) — a published district here is a MAPPED entitlement, "
            "not an adjudicated one. Carry the legal status with any zoning claim about it.",
            "The service name 'ProposedZoning9' is a publication artifact, not a status: the "
            "City's own zoning application and the CCRPC web map both render this layer as the "
            "City's zoning. The genuinely proposed/undecided layers are the sibling "
            "ZoningProposedChanges_gdb / ZoningChangeParcels services.",
            "Right-state guard: City of Wilmington, CLINTON County OHIO 45177 (the Air Park is "
            "ILN). Not Wilmington DE / NC (ILM) / MA / VT, and not Clinton County PA.",
            "Field names confirmed from the live layer-0 metadata + queries (2026-08-01).",
        ),
    ),
)


# Wood County, OH parcels (Bowling Green / Middleton Twp watershed point; #1436). The county
# publishes its own ArcGIS Server; the owner-bearing auditor CAMA join is the `Vision_Parcels`
# MapServer layer 0 (Vision Government Solutions is the county's CAMA vendor — hence the name),
# 73,839 features countywide. The sibling `Services_for_Web_Apps/Parcels` layer is the ArcGIS
# *parcel fabric* (survey geometry: PLSS, misclose, legal acreage) and carries NO owner — a
# fabric layer is not a CAMA layer, and querying it for a grantee returns a silent nothing.
#
# TWO CURRENCY FACTS ABOUT THIS LAYER, BOTH LOAD-BEARING (there is no `editingInfo` on this
# server, so the vintage has to be probed from the data itself):
#   * the newest conveyance ANYWHERE in the layer is 2025-07-25 (max(Sale_Date) over all 73,839
#     rows; zero rows with Sale_Date > 2026-05-01). It is a ~2025-07 snapshot, so it cannot show
#     a 2026 acquisition and a "not owned by X" read against it is a statement about July 2025.
#   * the parcel FABRIC is current-to-2025 as well, which is why it carries the two consolidated
#     Liames tracts (611190000003500 / 611190000029510, both quitclaimed to themselves 2025-04-09
#     at $0) and the township zoning twin below still carries their eleven predecessors.
# Field names + samples + the vintage probes confirmed from the live layer-0 `?f=json` +
# queries (2026-08-01). WKID 102100/3857 as served; outSR=4326 for the committed geometry.
WOOD_PARCEL_SCHEMA = GisParcelSchema(
    connector="wood_gis",
    reference_dir="bowling-green-gis",
    page_size=2000,  # the layer's maxRecordCount
    out_fields=(
        "Name",
        "Owner_Name",
        "Deeded_Name",
        "Street_Number",
        "Street_Name",
        "Suffix",
        "Primary_Use",
        "Land_Acres",
        "Total_Land",
        "Total_Improved",
        "Prc_Ttl_Apprais_Lnd_Alt",
        "District",
        "School_District",
        "Sale_Date",
        "Transfer_Price",
        "Qualified",
        "Mail_Address_Line_1",
        "Mail_Address_Line_2",
        "Mail_City",
        "Mail_State",
        "Mail_Zip",
    ),
    id_field="Name",  # the bare 15-digit stored id, e.g. "611190000003500"
    owner_field="Owner_Name",  # the CAMA owner of record
    owner_2_field="",  # no second-owner field (Owner_Name carries the whole string)
    deeded_owner_field="Deeded_Name",  # NB: the column literally named Deeded_Owner is EMPTY
    situs_fields=("Street_Number", "Street_Name", "Suffix"),  # no city/ZIP token — see caveats
    owner_addr_fields=(
        "Mail_Address_Line_1",
        "Mail_Address_Line_2",
        "Mail_City",
        "Mail_State",
        "Mail_Zip",
    ),
    land_use_field="Primary_Use",  # the Ohio CAMA use code, served as a STRING ("101", "511")
    acres_field="Land_Acres",  # the auditor's DEEDED acreage, not a GIS planar measure
    market_land_field="Total_Land",
    market_improvement_field="Total_Improved",
    market_total_field="",  # the layer publishes NO total column — see caveats
    cauv_field="Prc_Ttl_Apprais_Lnd_Alt",  # the CAUV land value (0 = not enrolled) — see caveats
    tax_district_field="District",  # the letter-prefixed district, e.g. "J34"/"J36" (Middleton)
    school_field="School_District",
    neighborhood_field="",  # no neighborhood column
    sale_date_field="Sale_Date",  # an esriFieldTypeDate (epoch millis)
    sale_amount_field="Transfer_Price",
    valid_sale_field="Qualified",  # the auditor's arms-length flag: "Q" qualified / "U" not
    id_normalize="dashless",  # "611-190000003500" -> "611190000003500" (see the deed-id caveat)
    date_decode="epoch_millis",
    land_use_decode="int",  # a bare numeric code served as text; _i() coerces it
    deed_id_regex=r"\b\d{3}-\d{12}\b",  # the auditor id MINUS its district prefix — see caveats
    meta=GisMeta(
        subject="Wood County, Ohio parcels (auditor CAMA + geometry)",
        source="Wood County, Ohio ArcGIS Server — Services_for_Web_Apps/Vision_Parcels "
        "MapServer layer 0 (Vision Government Solutions CAMA joined to parcel geometry)",
        source_url=(
            "https://wcohiogis.woodcountyohio.gov/server/rest/services/"
            "Services_for_Web_Apps/Vision_Parcels/MapServer/0"
        ),
        caveats=(
            "Values are verbatim from the county CAMA join; null means the service had no value.",
            "VINTAGE, PROBED NOT PUBLISHED: this server exposes no editingInfo, so the layer's "
            "currency has to be read out of the data. max(Sale_Date) over all 73,839 rows is "
            "2025-07-25 and there are ZERO rows with Sale_Date > 2026-05-01 — it is a ~2025-07 "
            "snapshot. A negative result ('X owns no land here') is therefore a statement about "
            "July 2025, not about today; re-probe max(Sale_Date) before believing one.",
            "ONE ROW PER POLYGON PART, NOT PER PARCEL — AND THE TWO OBVIOUS FIXES ARE BOTH "
            "WRONG. A `Name` is not unique: 12 of the 774 distinct parcels in the Middleton Twp "
            "neighbourhood come back on 2-6 rows carrying IDENTICAL attributes. They are not "
            "duplicates. Every one of those repeat sets is pairwise DISJOINT (0.000 ac of "
            "overlap across all 12) and the parts sum to the deeded acreage: 611190000006000, "
            "the A. Schaller tract, is 39.621 ac + 25.294 ac = 64.915 ac planar against 64.55 ac "
            "deeded. So deduping on Name SILENTLY DROPS LAND (25 of that parcel's 64 acres), "
            "while summing Land_Acres over the raw rows DOUBLE-COUNTS, because Land_Acres is the "
            "whole parcel's figure repeated on each part. Union the geometry per Name and take "
            "Land_Acres once.",
            "Land_Acres is the auditor's DEEDED acreage and is 0.0 on platted city lots — a 0 "
            "there means 'lot, not acreage', not 'no land'. A planar acreage must be measured "
            "from the geometry and reported as a separate figure.",
            "THERE IS NO TOTAL-VALUE COLUMN. The layer publishes Total_Land and Total_Improved "
            "and nothing that sums them, so market_total_value is always null here; a reader "
            "who needs the total adds the two. Do NOT read Prc_Ttl_Apprais_Lnd_Alt as the total.",
            "Prc_Ttl_Apprais_Lnd_Alt IS THE CAUV LAND VALUE, and its name says nothing of the "
            "kind. Across the 774-parcel Middleton neighbourhood it is 0 on 493 parcels and "
            "strictly BELOW Total_Land on 270 of the remaining 281 — on enrolled farmland it "
            "runs ~35-40% of market (49.23 ac: $459,800 market land vs $172,690, i.e. $9,340/ac "
            "vs $3,508/ac). 0 means NOT ENROLLED, not 'unvalued'.",
            "Suffix, Post_Direc, City and Zip are unpopulated on this layer (0/774, 0/774, 4/774 "
            "and 6/774 in the Middleton neighbourhood), so the situs is a house number plus a "
            "street NAME with no street type and no municipality token — '21443 MERCER', not "
            "'21443 Mercer Rd'. Deeded_Owner is likewise empty on every row; the deeded name "
            "lives in Deeded_Name, which is what deeded_owner_field points at.",
            "THE DEED-ID REGEX DELIBERATELY OMITS THE DISTRICT PREFIX. The auditor prints a "
            "parcel as 'J34-611-190000003500' (the layer's own Identification__ column: tax "
            "district, then the stored id split 3/12). The stored id is the 15-digit remainder, "
            "so the corpus pattern matches from the '611-' on (\\b still fires after the prefix's "
            "hyphen) and id_normalize='dashless' maps it onto Name. Passing the FULL printed form "
            "to fetch_parcel does NOT work — dashless keeps the 34 of J34 and yields a 17-digit "
            "string. Strip the district prefix, or query Identification__ directly.",
            "The sibling Services_for_Web_Apps/Parcels layer is the ArcGIS PARCEL FABRIC (PLSS, "
            "misclose, Legal_Acreage) and has no owner column at all. It is not a stale twin of "
            "this layer, it is a different kind of layer; an owner query against it fails silent.",
            "Right-county guard: Wood County OHIO (FIPS 39173), tax districts 'J34'/'J36' "
            "(Middleton Twp) and 'B07'/'B08' (City of Bowling Green). Bowling Green KENTUCKY "
            "(Warren County) is the standing search trap for this site — it is also where the "
            "other municipal utility numbered 2056 lives.",
        ),
    ),
)


# Middleton Township, OH zoning (Bowling Green watershed point; #1436). The Meta campus is in
# MIDDLETON TOWNSHIP, ~6 mi north of the city, so the City of Bowling Green's own zoning layer
# (gis.bgohio.org PublicData/UtilitiesWithZoning/MapServer/2, "Current Zoning", 14 districts) is
# the WRONG instrument for it — that one covers the corporation limits and the Oppidan colo, not
# the campus. The township's districts are published by the county in two places and they are
# NOT the same layer:
#   * Services_for_Web_Apps/Zoning_Districts/MapServer/1 — countywide, polygon-only, and a 2013
#     SNAPSHOT: LASTUPDATE is 2013-07-18..2013-08-08 on 1,338 of its 1,339 polygons (one 2016
#     edit). It predates every rezoning this site is about.
#   * Hosted/Middleton_Twp_Zoning_Viewer26/FeatureServer/1 — the one wired here: the township's
#     own parcel-JOINED zoning, built 2025-11-13, so it carries the 2023 ag -> M-1 rezonings of
#     the campus core that the countywide layer cannot.
# Two twins of the hosted service exist (Hosted/MiddletonTwpZoningWFL1, identical lastEditDate
# 2026-07-14; Hosted/Middleton_twp_zoning_WFL1, STALE at 2025-11-03). Read lastEditDate before
# picking one. Field names + the edit-date probes confirmed live 2026-08-01.
MIDDLETON_ZONING_SCHEMA = GisZoningSchema(
    connector="middleton_gis",
    reference_dir="bowling-green-gis",  # shared with the Wood parcel + NFHL flood schemas
    page_size=1000,  # the layer's maxRecordCount (half the parcel layer's)
    object_id_field="objectid",
    parcel_field="name",  # the same 15-digit id as WOOD_PARCEL_SCHEMA.id_field — but see caveats
    zoning_field="zone",  # "M-1: Light Industrial" — code AND label in one string
    http_method="GET",
    id_normalize="dashless",  # matches the parcel schema, so one id form serves both layers
    meta=GisMeta(
        subject="Middleton Township, Wood County, Ohio zoning districts (parcel-joined)",
        source="Wood County, Ohio ArcGIS Server — Hosted/Middleton_Twp_Zoning_Viewer26 "
        "FeatureServer layer 1 (Middleton_TWP_Zoning_Parcels: the township's zoning joined to "
        "a Vision CAMA parcel extract)",
        source_url=(
            "https://wcohiogis.woodcountyohio.gov/server/rest/services/"
            "Hosted/Middleton_Twp_Zoning_Viewer26/FeatureServer/1"
        ),
        caveats=(
            "Values are verbatim from the township zoning layer.",
            "THE ZONE STRING IS CODE AND LABEL TOGETHER — 'M-1: Light Industrial', not 'M-1'. "
            "Ten districts appear: R-3 Residence, A-1 Agricultural, V Village, R-1 Estate "
            "Residence, R-2 Suburban Residence, M-1 Light Industrial, B-1 Neighborhood Business, "
            "B-3 Highway Business, U Unzoned, R-4 Multiple Dwelling. The zonelong column is null "
            "on every row and the resolution column — which would carry the trustees' resolution "
            "number for each district — is EMPTY on every row. The instrument is not published "
            "here; it is the resolution itself.",
            "ROWS REPEAT PER NAME, BUT NOT UNIFORMLY — do not assume a factor of two. The "
            "full layer is 6,816 rows over 3,409 distinct `name` values, all created 2025-11-13 "
            "11:52 by the same editor; 6,816/3,409 is 1.9994, not 2, because the multiplicity "
            "varies. In the committed campus-envelope fixture it is 296 rows over 145 names — "
            "142 names on two rows and THREE on four. Aggregate per name; never divide a row "
            "count by two to get a parcel count.",
            "THIS LAYER RIDES AN OLDER PARCEL FABRIC THAN Vision_Parcels, so a parcel-id join "
            "between the two SILENTLY MISSES the campus. Liames' 322.5-ac and 196.5-ac tracts "
            "(611190000003500 / 611190000029510 in the CAMA layer, consolidated 2025-04-09) "
            "appear here as their eleven predecessors — 611190000002500/2501/3000/4000/5000/"
            "7000/20000/29500/32000/32002 and 611190000037000 — summing to 195.86 ac and 319.99 "
            "ac against the successors' 196.5 ac and 322.5 ac. Match on geometry, not on id.",
            "CURRENCY IS THE POINT OF THIS LAYER FOR #1436, and its two sources are not the "
            "same evidence. What the COMMITTED fixture shows, and what replays offline, is the "
            "campus envelope: 296 rows all created 2025-11-13, a handful re-touched 2025-11-21, "
            "and one 2026-05-12 (parcel 611190000002501) as the newest stamp in it. The wider "
            "claim — that the layer's only other 2026 edits countywide are three unrelated Hull "
            "Prairie parcels on 2026-07-14 — comes from a full-layer paged probe of all 6,816 "
            "rows run 2026-08-01 that is NOT committed as a fixture, and the service's own "
            "lastEditDate of 2026-07-14 is layer metadata rather than a row. Re-run that probe "
            "before restating it. Either way the zoning content DOES "
            "carry the 2023 agricultural -> M-1 rezonings of the campus core, and it CANNOT "
            "carry the 2026-07-07 rezoning of the thirteen 31.82-ac parcels, which still read "
            "A-1 and R-4 here. That is a publication lag, not a finding about their zoning — and "
            "the trustees' 2-1 vote that granted it is itself subject to a referendum petition. "
            "NO published Wood County layer carried that rezoning as of 2026-08-01.",
            "B-4, the State Route 25 and 582 Overlay Zone, is an OVERLAY and is served as a "
            "SEPARATE LAYER (FeatureServer/0 of the same service; the countywide 2013 layer "
            "instead mixes it in with the base districts, where a parcel reads 100% A-1 AND 100% "
            "B-4 and looks self-contradictory). An overlay does not replace the base district.",
            "Coverage is MIDDLETON TOWNSHIP ONLY. The City of Bowling Green publishes its own "
            "districts at gis.bgohio.org/arcgis/rest/services/PublicData/UtilitiesWithZoning/"
            "MapServer/2 ('Current Zoning', district in F2023_Desc, with Year_2015..Year_2027 "
            "columns carrying a per-parcel zoning history) — that is the layer for the Oppidan "
            "colo in the Woodbridge Business Park, not for the campus.",
            "Right-township guard: MIDDLETON Township, WOOD County OHIO. Ohio has a second "
            "Middleton Township in Columbiana County.",
        ),
    ),
)


# Adams County, Ohio — the county Engineer/GIS tax-map parcel layer (#2049).
#
# ⚠️ THIS LAYER CARRIES NO CAMA JOIN. It is a tax-MAP layer: geometry, parcel number, two
# acreage columns, township, and a path to the surveyor's plat PDF. There is no owner, no situs
# address, no conveyance date, no valuation and no land-use code anywhere in the FeatureServer
# (its single layer is `4: MasterParcel`; the `CAMA_LINK` column exists but is blank on every row
# sampled, including the campus parcel). Every such field below is therefore `""` — the schema's
# documented "absent" marker, which `Parcel.from_attrs` decodes to None rather than inventing a
# value. Owner search is unavailable here and `parcels_geojson_by_owner` refuses cleanly.
#
# Right-county guard: there are Adams Counties in PA, CO, IL, IN, MS, NE, ND, WA and WI, and a
# hub/AGOL search for "Adams County parcels" returns several of them. This layer is verified as
# Adams County OHIO three ways: its org is the one behind the county's own GIS hub
# (acgis-adamso.hub.arcgis.com, org eFMIGXUWac5mgGdc), its spatial reference is EPSG:3735
# (NAD83 / Ohio South, ftUS), and the same org publishes a "VMS Boundary Lines" layer — the
# Virginia Military Survey, which is the survey system of exactly this part of Ohio.
ADAMS_PARCEL_SCHEMA = GisParcelSchema(
    connector="adams_gis",
    reference_dir="west-union-gis",
    page_size=2000,  # the layer's maxRecordCount
    out_fields=(
        "PARCEL_NUM",
        "Cal_Ac",
        "Acreage",
        "Township",
        "Plat",
        "SUB_PLAT",
        "GISPLAT",
        "Notes",
    ),
    id_field="PARCEL_NUM",  # 13-digit undashed auditor parcel number, e.g. "1830000079000"
    owner_field="",  # ⚠️ no owner column in the layer — see the header note
    owner_2_field="",
    deeded_owner_field="",
    situs_fields=(),  # no address columns
    owner_addr_fields=(),
    land_use_field="",
    # `Cal_Ac` is the GIS PLANAR acreage and is the only numeric acreage column. The county's
    # DEEDED acreage lives in `Acreage`, which is a STRING carrying a unit and a survey suffix
    # ("1016.2174 ac S") that `_f()` cannot parse — it is pulled in `out_fields` so it reaches the
    # cache, but it is deliberately not mapped here rather than silently truncated.
    acres_field="Cal_Ac",
    market_land_field="",
    market_improvement_field="",
    market_total_field="",
    cauv_field="",
    tax_district_field="Township",  # the civil township, the nearest thing the layer has
    school_field="",
    neighborhood_field="",
    sale_date_field="",
    sale_amount_field="",
    valid_sale_field="",
    id_normalize="verbatim",  # the 13-digit form is stored verbatim (no dashes anywhere)
    date_decode="none",  # no date column to decode
    land_use_decode="int",  # unused (land_use_field is empty)
    deed_id_regex=r"\b\d{13}\b",  # the undashed 13-digit auditor parcel form
    meta=GisMeta(
        subject="Adams County, Ohio parcels (county tax-map geometry; NO CAMA/owner join)",
        source="Adams County, Ohio GIS org (eFMIGXUWac5mgGdc, the org behind the county's "
        "acgis-adamso.hub.arcgis.com hub) — Parcel_Layer FeatureServer layer 4 'MasterParcel'",
        source_url=(
            "https://services6.arcgis.com/eFMIGXUWac5mgGdc/arcgis/rest/services/"
            "Parcel_Layer/FeatureServer/4"
        ),
        caveats=(
            "NO OWNER, SITUS, SALE OR VALUATION DATA EXISTS IN THIS LAYER. A committed feature's "
            "owner / situs_address / owner_mailing_address / transfer_date are null because the "
            "county serves none of them here, NOT because the parcel is unowned or unsold. "
            "Ownership must come from the Adams County Auditor (adamscountyauditor.org) or a "
            "recorded instrument, and is a separate, uncommitted pull.",
            "Two acreage columns disagree by design and BOTH matter: `Acreage` is the auditor's "
            "DEEDED acreage as a string with a survey suffix ('1016.2174 ac S'), and `Cal_Ac` is "
            "the GIS PLANAR calculation ('1009.50056252729'). The typed `acres` field carries the "
            "planar figure; the deeded string is preserved only in the cached response.",
            "`CAMA_LINK` is present in the schema but blank on every row sampled — it is not a "
            "usable join key.",
            "Right-county guard: ADAMS County OHIO. At least nine other states have an Adams "
            "County, and several publish similarly-named parcel layers.",
        ),
    ),
)
