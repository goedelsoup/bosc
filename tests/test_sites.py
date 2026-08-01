"""Tests for the site-axis registry (#325).

The Lima profile is the live reference build: its values must reproduce the pre-#325
hardcoded defaults exactly. The golden snapshot below is the zero-drift contract — if a
literal was mistranscribed when it moved into ``watermark.sites``, this test fails before any
hydrology output can quietly change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from watermark.config import Settings
from watermark.connectors._cache import cache_key
from watermark.hsg import normalize_hsg
from watermark.sites import (
    ALLEN_IN_PARCEL_SCHEMA,
    CLINTON_PARCEL_SCHEMA,
    FORT_WAYNE_ZONING_SCHEMA,
    LIMA_FLOOD_SCHEMA,
    LIMA_PARCEL_SCHEMA,
    LIMA_ZONING_SCHEMA,
    LUCAS_AREIS_PARCEL_SCHEMA,
    LUCAS_ZONING_SCHEMA,
    MIAMI_PARCEL_SCHEMA,
    MIDDLETON_ZONING_SCHEMA,
    PER_SITE_OUTPUT_FIELDS,
    PUTNAM_PARCEL_SCHEMA,
    SHELBY_PARCEL_SCHEMA,
    SIDNEY_ZONING_SCHEMA,
    SITES,
    VAN_WERT_PARCEL_SCHEMA,
    WILMINGTON_ZONING_SCHEMA,
    WOOD_PARCEL_SCHEMA,
    SiteFacility,
    SiteProfile,
    active_profile,
    get_profile,
    output_path_collisions,
    profile_readiness,
    scaffold_profile_src,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# The exact pre-#325 Lima values, transcribed from the original module constants.
_LIMA_GOLDEN = {
    "slug": "lima",
    "basin": "maumee",
    "nwis_sites": ["04187100", "04186500"],
    "nasa_power_lat": 40.74,
    "nasa_power_lon": -84.11,
    "rsei_fips": "39003",
    "econ_fips": "39003",
    "eia861_utility_number": 14006,
    "eia_state": "OH",
    "gnis_default_state": "OH",
    "hydro_utm_epsg": 32617,
    "lsc_default_ga": "136",
    "design_lat": 40.797,
    "design_lon": -84.123,
    "corridor_name": "Cole St / Bluelick corridor",
    "dominant_hsg": "C",
    "pre_cover": "cropland",
    "post_cover": "developed_campus",
    "developed_pervious_cover": "open_space",
    "noaa_fallback_24h_depth_in": {
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
    "parcels_relpath": "reference/periplus/bosc-parcels.geojson",
    "footprint_relpath": "extracted/plans/bosc-site-footprint.yaml",
    "corridor_geo_relpath": "reference/periplus",
    "climatology_relpath": "reference/hydrology/nasa-power-climatology.yaml",
    "corridor_ddf_relpath": "reference/hydrology/atlas14-corridor-ddf.yaml",
    "baseline_relpath": "reference/economics/baseline.yaml",
    "rsei_relpath": "reference/rsei/inventory.yaml",
    "consumer_energy_relpath": "reference/eia/consumer-energy.yaml",
    "grid_relpath": "reference/eia/grid-profile.yaml",
    "toxic_corridor_bbox": (40.695, 40.725, -84.140, -84.105),
    "receiving_water_name": "Ottawa River",
    "abstraction_gage": "04187100",
    "abstraction_node_id": "lima-wtp",
    "abstraction_node_name": "Lima WTP intake (Ottawa/Auglaize)",
    "abstraction_river": "Ottawa River",
    "supply_gage_primary": "04186500",
    "supply_gage_secondary": "04187100",
    "passby_primary_cfs": 2.5,
    "passby_secondary_cfs": 0.2,
    "supply_river_primary": "Auglaize River",
    "supply_river_secondary": "Ottawa River",
    "intake_da_ratio_primary": 0.614,
    "forcemain_labels": {"bosc-fm1": "FM-1", "bosc-fm2": "FM-2"},
    "sanitary_receiver_names": {
        "watch-lima-fm2-terminus": "City of Lima WWTP",
        "watch-american-bath-wwtp": "American Bath WWTP",
        "watch-american-ii-wwtp": "American II WWTP",
    },
    "sanitary_capacity_fallback": [
        (
            "American II WWTP",
            3.6,
            "FM-1",
            "Ohio EPA fact sheet 2PH00006: peak hydraulic capacity 3.6 MGD",
        ),
    ],
    "campus_dry_weather_mgd": 2.5,
    "lmp_usd_mwh": 45.81,  # connector-sourced AEP-zone 2025 day-ahead annual mean (#121)
    "county_name": "Allen County, OH",
    "corridor_subjects": ("bosc", "bistrozzi", "datacenter", "google"),  # #1523 reference set
    "map_view_lat": 40.792,
    "map_view_lon": -84.122,
    "map_view_zoom": 14,
}


def test_lima_golden_snapshot() -> None:
    lima = get_profile("lima")
    for field, expected in _LIMA_GOLDEN.items():
        assert getattr(lima, field) == expected, field
    # The Lima GIS URLs carry their host as evidence; spot-check they're populated + correct.
    assert lima.parcels_url.startswith("https://gis.allencountyohio.com/")
    assert "Lima_Zoning/MapServer/6" in lima.zoning_url
    assert "Lima_Zoning/MapServer/4" in lima.floodzone_url
    assert lima.hsg_citation.startswith("Allen County, OH dominant hydrologic soil group C")
    assert lima.plant_receiving["watch-shawnee-ii-wwtp"][0] == "Ottawa River"


def test_settings_resolves_active_profile() -> None:
    settings = Settings()
    assert active_profile(settings) is SITES["lima"]
    assert settings.nwis_sites == _LIMA_GOLDEN["nwis_sites"]
    assert settings.eia_state == "OH"


def test_second_profile_overrides_all_knobs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A synthetic site swaps in cleanly without touching Lima.
    fw = SITES["lima"].model_copy(
        update={
            "slug": "fw",
            "place": "Fort Wayne, IN",
            "nwis_sites": ["04183000"],
            "eia_state": "IN",
        }
    )
    monkeypatch.setitem(SITES, "fw", fw)
    settings = Settings(site="fw")
    assert settings.nwis_sites == ["04183000"]
    assert settings.eia_state == "IN"
    # And Lima is unchanged in the same process.
    assert Settings(site="lima").nwis_sites == ["04187100", "04186500"]


def test_explicit_kwarg_beats_profile() -> None:
    assert Settings(nwis_sites=["Y"]).nwis_sites == ["Y"]


def test_unknown_site_errors() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(site="atlantis")
    assert "atlantis" in str(exc.value)
    assert "lima" in str(exc.value)  # the message lists the known sites


def test_profile_is_frozen() -> None:
    with pytest.raises(ValidationError):
        SITES["lima"].slug = "nope"  # type: ignore[misc]


def test_sites_keyed_by_slug() -> None:
    # The registry key must equal the profile's slug (onboard scaffolds dirs by prof.slug).
    for key, prof in SITES.items():
        assert key == prof.slug


def test_per_site_output_relpaths_unique() -> None:
    # No two sites may share a per-site output relpath, or onboarding one clobbers the other
    # (#326 hardening). Fires the moment a colliding profile is added.
    for slug in SITES:
        assert output_path_collisions(slug) == {}, slug
    for field in PER_SITE_OUTPUT_FIELDS:
        # ``None`` is a valid "no destination" for an optional output (a facility-less site's
        # ``demand_pressure_relpath``, #1660) — only the concrete paths must be unique.
        values = [v for p in SITES.values() if (v := getattr(p, field)) is not None]
        assert len(values) == len(set(values)), f"duplicate {field} across SITES"


def test_facility_less_site_declares_no_demand_pressure_destination() -> None:
    # ``demand_pressure_relpath`` is gated on a DERIVABLE CAMPUS LOAD: the feed is sized against
    # one (``derive_demand_pressure`` raises otherwise), so a site without one must declare
    # ``None`` — no destination — rather than a dangling path to a file that can never be written
    # (#1660, ME-A: WPAFB shipped a path to a nonexistent demand-pressure.yaml). Enforced at model
    # construction: a profile entitled to the feed must carry a destination. Forcing an entitled
    # profile to None must raise.
    lima = SITES["lima"]
    assert lima.has_facility_power_basis and lima.demand_pressure_relpath is not None
    with pytest.raises(ValidationError, match="demand_pressure_relpath"):
        SiteProfile.model_validate({**lima.model_dump(), "demand_pressure_relpath": None})

    # WPAFB has a facility — a ``federal_installation``, #1664 — but no data-center campus and so
    # no IT load to size a demand→price sensitivity against. The gate is the power basis, not mere
    # facility presence; an enclave is as unentitled to this feed as a facility-less site.
    wpafb = SITES["wpafb"]
    assert wpafb.facility is not None
    assert wpafb.campus is None
    assert wpafb.has_facility_power_basis is False
    assert wpafb.demand_pressure_relpath is None, (
        "a site with no derivable campus load must not carry a demand_pressure_relpath pointing "
        "at a file that can never be written"
    )


def test_summer_season_months_validation() -> None:
    # The regulatory summer window (#1624) must be canonical month tokens: an unknown token or a
    # duplicate is a profile error (a typo would otherwise silently vanish from the seasonal
    # screen), lowercase input is normalized, and the empty tuple is the inherit-default signal.
    lima = SITES["lima"]
    with pytest.raises(ValidationError, match="unrecognized month"):
        SiteProfile.model_validate({**lima.model_dump(), "summer_season_months": ["JLY"]})
    with pytest.raises(ValidationError, match="duplicate month"):
        SiteProfile.model_validate({**lima.model_dump(), "summer_season_months": ["MAY", "MAY"]})
    normalized = SiteProfile.model_validate(
        {**lima.model_dump(), "summer_season_months": ["jun", "jul"]}
    )
    assert normalized.summer_season_months == ("JUN", "JUL")
    assert lima.summer_season_months == ()  # unset → inherit the Ohio EPA default


def test_scaffold_stub_is_constructible_and_collision_safe(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # The generated stub must (a) construct a SiteProfile and (b) slug-scope its outputs so it
    # passes the collision guard against Lima — the whole point of the scaffold (#326 authoring).
    src = scaffold_profile_src("findlay")
    assert "slug='findlay'" in src
    # Execute the stub's SiteProfile(...) call.
    body = src[src.index("SiteProfile(") :].rstrip().rstrip(",")
    prof = eval(body, {"SiteProfile": SiteProfile})
    assert prof.slug == "findlay"
    assert prof.climatology_relpath == "reference/hydrology/findlay/nasa-power-climatology.yaml"
    monkeypatch.setitem(SITES, "findlay", prof)
    assert output_path_collisions("findlay") == {}  # collision-safe vs Lima


def test_readiness_flags_placeholders_and_lima_copies(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A bare Lima copy: every field matches Lima (verify) and the slug differs.
    copy = SITES["lima"].model_copy(update={"slug": "copycat"})
    monkeypatch.setitem(SITES, "copycat", copy)
    kinds = {f.field: f.kind for f in profile_readiness("copycat")}
    assert kinds["nwis_sites"] == "matches-lima"
    assert kinds["rsei_fips"] == "matches-lima"
    assert "slug" not in kinds  # the slug differs (it's the key); not flagged

    # A scaffold stub: the unfilled fields are placeholders, not Lima copies.
    src = scaffold_profile_src("draftsite")
    body = src[src.index("SiteProfile(") :].rstrip().rstrip(",")
    stub = eval(body, {"SiteProfile": SiteProfile})
    monkeypatch.setitem(SITES, "draftsite", stub)
    found = {f.field: f.kind for f in profile_readiness("draftsite")}
    # YAML-backed fields (place, receiving_water_name, map_view_*) are excluded from readiness
    # — they're managed in data/sites.yaml, not scaffold-generated (#1027).
    assert "place" not in found
    assert found.get("nwis_sites") == "placeholder"
    # The pre-scoped output relpaths are neither placeholders nor Lima copies → not flagged.
    assert "climatology_relpath" not in found


def test_readiness_clean_for_lima() -> None:
    assert profile_readiness("lima") == []


def test_grid_knobs_complete_flags_incomplete_and_passes_lima() -> None:
    """B3/#1639: the grid-knob readiness check locks an incomplete grid identity, passes Lima."""
    from watermark.sites import grid_knobs_complete

    # Portsmouth is a stub: no serving utility (#0), no LMP zone → grid identity incomplete.
    gaps = grid_knobs_complete("portsmouth")
    assert set(gaps) >= {"eia861_utility_number", "serving_utility_citation", "lmp"}
    # Lima's grid identity is complete (AEP Ohio #14006, pinned AEP LMP zone).
    assert grid_knobs_complete("lima") == []


def test_no_registered_profile_renders_raw_todo_grid_identity() -> None:
    """B3/#1639: no registered site carries a raw 'TODO' in a grid-identity citation."""
    from watermark.sites import grid_identity_todo_violations

    assert grid_identity_todo_violations() == []


def test_grid_identity_todo_gate_detects_a_registered_violation(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """B3/#1639: the `watermark sites check` gate flags a registered raw-'TODO' grid citation."""
    from watermark.sites import grid_identity_todo_violations

    bad = SITES["lima"].model_copy(update={"slug": "badgrid", "lmp_citation": "TODO"})
    monkeypatch.setitem(SITES, "badgrid", bad)
    assert any("badgrid.lmp_citation" in v for v in grid_identity_todo_violations())


def test_python_sites_registered_in_frontend() -> None:
    # Every Python-registered site must also exist in the shared identity registry (#1027).
    # The registry JSON is the SSOT consumed by both Python (via _model.py) and TypeScript.
    # The registry moved into @watermark/core when web/ was split into packages (Epic #1549).
    registry = json.loads(
        (REPO_ROOT / "web" / "packages" / "core" / "src" / "sites-registry.json").read_text(
            encoding="utf-8"
        )
    )
    registry_slugs = {entry["slug"] for entry in registry["sites"]}
    assert registry_slugs, "sites-registry.json has no entries — run `watermark sites sync`"
    assert set(SITES) <= registry_slugs, set(SITES) - registry_slugs


def test_per_site_output_paths_resolve(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # The per-site onboard outputs (#326) resolve to Lima's legacy paths for lima and to
    # slug-scoped paths for a new site, so onboarding never clobbers Lima.
    from watermark.hydrology.climate import _reference_path as climatology_path
    from watermark.hydrology.drainage import _ddf_path

    lima = Settings(site="lima", data_dir=tmp_path)
    assert climatology_path(lima) == tmp_path / "reference/hydrology/nasa-power-climatology.yaml"
    assert _ddf_path(lima) == tmp_path / "reference/hydrology/atlas14-corridor-ddf.yaml"

    fw = SITES["lima"].model_copy(
        update={
            "slug": "fw",
            "climatology_relpath": "reference/hydrology/fw/nasa-power-climatology.yaml",
            "corridor_ddf_relpath": "reference/hydrology/fw/atlas14-corridor-ddf.yaml",
        }
    )
    monkeypatch.setitem(SITES, "fw", fw)
    fws = Settings(site="fw", data_dir=tmp_path)
    assert climatology_path(fws) == tmp_path / "reference/hydrology/fw/nasa-power-climatology.yaml"
    assert _ddf_path(fws) == tmp_path / "reference/hydrology/fw/atlas14-corridor-ddf.yaml"


# --- GIS field-map schemas (#237) ----------------------------------------------------------
# The connector field names + encodings moved onto per-site GisSchemas. Lima's must reproduce
# the pre-#237 hardcoded values exactly (zero-drift); the tests below are that contract.

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "hydrology"


def test_gis_schema_golden_lima() -> None:
    """Lima's GIS schemas transcribe the old hardcoded field names / encodings exactly."""
    p = LIMA_PARCEL_SCHEMA
    assert p.connector == "allen_gis" and p.reference_dir == "allen-gis" and p.page_size == 1000
    assert p.out_fields[:4] == ("PARCEL_NO", "OWNNAM1", "OWNNAM2", "DEEDOWN")
    assert p.out_fields[-3:] == ("DATE", "SALEAMT", "VAL_SAL") and len(p.out_fields) == 24
    assert (p.id_field, p.acres_field, p.tax_district_field) == ("PARCEL_NO", "ACRES", "TAXDIST")
    assert p.id_normalize == "dashless" and p.date_decode == "mmddyyyy"
    assert p.deed_id_regex == r"\b\d{2}-\d{4}-\d{2}-\d{3}\.\d{3}\b"
    assert p.defense is not None
    assert p.defense.enclave_owner == "UNITED STATES" and p.defense.enclave_tax_district == "L35"
    assert p.defense.owner_scan_fields == ("OWNNAM1", "DEEDOWN", "OWNNAM2")  # OR-clause order

    z = LIMA_ZONING_SCHEMA
    assert z.connector == "lima_gis" and z.reference_dir == "lima-gis" and z.http_method == "POST"
    assert z.out_fields == ("OBJECTID", "PARCEL_NO", "ZONING")

    f = LIMA_FLOOD_SCHEMA
    assert (
        f.connector == "lima_gis_flood" and f.bfe_sentinel == -9999.0 and f.sfha_true_value == "T"
    )
    assert f.out_fields == (
        "OBJECTID",
        "FLD_ZONE",
        "ZONE_SUBTY",
        "SFHA_TF",
        "STATIC_BFE",
        "DFIRM_ID",
        "SOURCE_CIT",
    )


def test_gis_param_stability_matches_committed_fixtures() -> None:
    """The zero-drift invariant, stated explicitly: a request built from each Lima schema
    hashes to a committed connector fixture. A mistranscribed field name changes the key and
    this fails *before* the replay tests — with a precise pointer to the drift."""
    base = {"f": "json", "returnGeometry": "false"}

    # zoning_districts groupBy (lima_gis)
    z = LIMA_ZONING_SCHEMA
    zstats = [
        {
            "statisticType": "count",
            "onStatisticField": z.object_id_field,
            "outStatisticFieldName": "n",
        }
    ]
    zkey = cache_key(
        {
            **base,
            "where": "1=1",
            "outFields": z.zoning_field,
            "groupByFieldsForStatistics": z.zoning_field,
            "outStatistics": json.dumps(zstats),
        }
    )
    assert (FIXTURES / z.connector / f"{zkey}.json").is_file(), f"zoning param drift: {zkey}"

    # floodzone_catalog groupBy (lima_gis_flood)
    f = LIMA_FLOOD_SCHEMA
    group = ",".join((f.fld_zone_field, f.zone_subtype_field, f.sfha_field))
    fstats = [
        {
            "statisticType": "count",
            "onStatisticField": f.object_id_field,
            "outStatisticFieldName": "n",
        }
    ]
    fkey = cache_key(
        {
            **base,
            "where": "1=1",
            "outFields": group,
            "groupByFieldsForStatistics": group,
            "outStatistics": json.dumps(fstats),
        }
    )
    assert (FIXTURES / f.connector / f"{fkey}.json").is_file(), f"flood param drift: {fkey}"

    # army_controlled fixed-where parcel query (allen_gis)
    p = LIMA_PARCEL_SCHEMA
    assert p.defense is not None
    where = (
        f"{p.owner_field}='{p.defense.enclave_owner}' "
        f"AND {p.tax_district_field}='{p.defense.enclave_tax_district}'"
    )
    akey = cache_key(
        {
            **base,
            "where": where,
            "outFields": ",".join(p.out_fields),
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{akey}.json").is_file(), f"parcel param drift: {akey}"


def test_gis_connector_decodes_by_field_name_for_a_new_jurisdiction(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A second jurisdiction with *different* ArcGIS field names decodes correctly — proof the
    connector selects by name (from the schema), not by Lima's hardcoded fields. Fully offline:
    a hand-rolled fixture under the synthetic connector's key."""
    from watermark.connectors.gis_schema import GisCitedZoningMeta, GisMeta, GisZoningSchema
    from watermark.hydrology.connectors import lima_gis

    alt = GisZoningSchema(
        connector="synthj_gis",
        reference_dir="synthj-gis",
        page_size=2000,
        object_id_field="FID",
        parcel_field="PARCELID",
        zoning_field="ZONE_DISTRICT",
        http_method="GET",
        id_normalize="dashless",
        meta=GisMeta(subject="s", source="s", source_url="s", caveats=()),
        cited_meta=GisCitedZoningMeta(
            subject="s",
            source="s",
            finding_lead="x",
            in_city_finding=".",
            out_of_city_finding="-",
            caveats=(),
        ),
    )
    synth = SITES["lima"].model_copy(update={"slug": "synthj", "gis_zoning": alt})
    monkeypatch.setitem(SITES, "synthj", synth)

    # Hand-roll the offline fixture for the exact request zoning_for_parcel("12345") builds.
    params = {
        "f": "json",
        "returnGeometry": "false",
        "where": f"{alt.parcel_field}='12345'",
        "outFields": ",".join(alt.out_fields),
        "resultOffset": 0,
        "resultRecordCount": alt.page_size,
        "orderByFields": alt.object_id_field,
    }
    key = cache_key(params)
    fx = tmp_path / alt.connector / f"{key}.json"
    fx.parent.mkdir(parents=True)
    fx.write_text(
        json.dumps(
            {
                "payload": {
                    "features": [
                        {"attributes": {"FID": 7, "PARCELID": "12345", "ZONE_DISTRICT": "C-2 COMM"}}
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    settings = Settings(
        site="synthj",
        hydro_offline=True,
        hydro_fixtures_dir=tmp_path,
        hydro_cache_dir=tmp_path / "c",
    )
    rec = lima_gis.zoning_for_parcel("12345", settings=settings)
    assert rec is not None
    assert rec.parcel_no == "12345" and rec.zoning == "C-2 COMM" and rec.object_id == 7


def test_gis_connectors_refuse_a_schemaless_site() -> None:
    """A site with no parcel GIS schema refuses cleanly rather than running Lima's fields."""
    import pytest

    from watermark.hydrology.connectors import allen_gis

    assert SITES["springfield"].gis_parcel is None  # an Ohio site with no parcel schema wired yet
    with pytest.raises(allen_gis.AllenGisError, match="no parcel GIS schema"):
        allen_gis.fetch_parcel("12-34", settings=Settings(site="springfield"))


def test_toxic_corridors_defined_for_defiance_and_bryan() -> None:
    """The Defiance (#393) and Bryan (#412) toxic corridors are delineated (no longer [0,0,0,0]):
    each box covers its receiving-water industrial cluster and excludes facilities on other
    drainages, so the RSEI corridor-inference (toxics._in_corridor) scopes correctly."""
    from watermark.hydrology.toxics import _in_corridor

    dz = SITES["defiance"].toxic_corridor_bbox
    assert dz != (0.0, 0.0, 0.0, 0.0)
    assert _in_corridor(41.28244, -84.292089, dz)  # GM Defiance Casting (on the Maumee corridor)
    assert _in_corridor(41.2859, -84.3648, dz)  # Johns Manville Plant 2
    assert not _in_corridor(41.2958, -84.74941, dz)  # Syn Ind. / Trident (far-west Hicksville)

    bz = SITES["bryan"].toxic_corridor_bbox
    assert bz != (0.0, 0.0, 0.0, 0.0)
    assert _in_corridor(41.478, -84.55926, bz)  # NEW ERA OHIO (Prairie Creek, Bryan city)
    assert _in_corridor(41.46679, -84.53046, bz)  # Titan Tire of Bryan
    assert not _in_corridor(
        41.608115, -84.563041, bz
    )  # Chase Brass (Montpelier, off Prairie Creek)


def test_findlay_parcel_schema_is_owner_redacted_statewide() -> None:
    """Findlay's parcel gap (#237) is closed by the OGRIP Ohio statewide layer scoped to Hancock —
    a partial, owner-redacted catalog: county-scoped, no owner field, land use decoded leading_int."""
    p = SITES["findlay"].gis_parcel
    assert p is not None and p.connector == "ohio_parcels"
    assert p.reference_dir == "findlay-gis"
    assert p.query_scope == "County='Hancock'"  # the statewide layer scoped to FIPS 39063
    assert p.owner_field == "" and p.defense is None  # owner-redacted; no defense scan
    assert p.land_use_decode == "leading_int"  # "511: Res-Custom Code" -> 511
    assert p.id_field == "LocalParcelID" and p.id_normalize == "dashless"
    assert "OhioStatewidePacels_full_view" in p.meta.source_url


def test_putnam_parcel_schema_is_full_cama() -> None:
    """Ottawa's parcel gap (#420) is closed by Putnam County's self-hosted ArcGIS — a FULL fit
    (owner + auditor CAMA values on one layer), unlike Findlay's owner-redacted OGRIP substitute.
    Golden + param-stability: the schema reproduces the live field-map, and a fetch_parcel request
    built from it hashes to the committed fixture (the new connector's zero-drift guard)."""
    p = SITES["ottawa"].gis_parcel
    assert p is not None and p is PUTNAM_PARCEL_SCHEMA
    assert p.connector == "putnam_gis" and p.reference_dir == "ottawa-gis"
    assert p.id_field == "PIN" and p.id_normalize == "dashless"
    assert p.owner_field == "OWNER" and p.defense is None  # owner present; no federal-enclave scan
    assert p.land_use_field == "CLASS_1" and p.land_use_decode == "int"
    assert p.date_decode == "mmddyy"  # MM-DD-YY SALEDATE
    assert p.market_total_field == "" and p.query_scope == ""  # no total field; single-jurisdiction
    assert "putnamcountygis.com" in p.meta.source_url

    base = {"f": "json", "returnGeometry": "false"}
    key = cache_key(
        {
            **base,
            "where": f"{p.id_field}='010010200000'",
            "outFields": ",".join(p.out_fields),
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"putnam param drift: {key}"

    # Param stability for the committed assemblage's PIN-list pull too (#1420). Ottawa's campus
    # has TWO unrelated owners, so unlike Van Wert/Sidney it cannot be pulled by an owner scan —
    # the geojson that produced data/reference/ottawa/parcel-assemblage.geojson is a PIN query.
    pin_key = cache_key(
        {
            "f": "geojson",
            "returnGeometry": "true",
            "where": "PIN IN ('322220000000','322260000000')",
            "outFields": ",".join(p.out_fields),
            "outSR": "4326",
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{pin_key}.json").is_file(), (
        f"ottawa assemblage param drift: {pin_key}"
    )


def test_ottawa_hsg_is_ssurgo_verified_dual_over_a_mostly_urban_campus() -> None:
    """#1420: committing the campus assemblage let SSURGO run, and it corrected the profile's
    [inference] in BOTH halves. The rating: NRCS rates Toledo/Fulton as the dual group C/D, so a
    flat "D" pre-committed the undrained letter for every scenario (WS-20/#1620). And the series:
    the old citation named Hoytville/Latty/Paulding/Nappanee, and NONE of those is under this
    campus — only the general Black-Swamp reasoning survived. The caveat is load-bearing and must
    stay in the citation: 61% of the grid is URBAN LAND, so the group describes the campus's
    unbuilt remainder. A future edit that re-flattens the group, drops the Urban-land caveat, or
    reinstates the wrong series is the bug this test exists to catch."""
    s = SITES["ottawa"]
    assert s.dominant_hsg == "C/D"
    assert normalize_hsg(s.dominant_hsg) != normalize_hsg("D")  # a dual group, not its letter
    assert "SSURGO" in s.hsg_citation
    assert "Toledo" in s.hsg_citation and "Fulton" in s.hsg_citation
    # The superseded series is still NAMED, but explicitly as what this campus is NOT — the
    # citation has to keep showing its work, or the correction reads like a silent overwrite.
    assert "not the Hoytville/Latty/Paulding it named" in s.hsg_citation
    assert "22 of the 23 RATED" in s.hsg_citation  # the sample the correction rests on
    assert "URBAN LAND" in s.hsg_citation  # 61% unrated — the caveat is the point of the site
    # The scenario switch is LIVE here (unlike Sidney's single group) — both conditions resolve.
    assert (s.pre_drainage_condition, s.post_drainage_condition) == ("drained", "undrained")
    # A BROWNFIELD, so pre == post: redeveloping it adds no new impervious at screening grade.
    # That equality is the finding — the knobs were TODO "pending an identified site" before.
    assert (s.pre_cover, s.post_cover, s.developed_pervious_cover) == (
        "developed_campus",
        "developed_campus",
        "open_space",
    )
    # The committed geometry + footprint the SSURGO run and the places domain both read.
    assert s.parcels_relpath == "reference/ottawa/parcel-assemblage.geojson"
    assert s.footprint_relpath == "extracted/ottawa/bosc-site-footprint.yaml"
    # Ottawa's anchor place is a FORMER WORKS, not a campus siting — no facility is disclosed.
    assert s.facilities == () and s.facility is None and s.campus is None


def test_ottawa_zoning_is_a_searched_negative_not_a_pending_discovery() -> None:
    """#1420 closed the zoning acceptance criterion as a NEGATIVE: the Village publishes no zoning
    GIS, so there is nothing to wire and `zoning_url` keeps the sentinel the connector contract
    needs. What must survive is the SEARCH — in particular that the county server's `499 Token
    Required` on /services/Zoning is not evidence a secured zoning service exists (a folder name
    that certainly does not exist answers 499 too). Losing that note would turn a documented
    negative back into a speculative "pending endpoint discovery"."""
    s = SITES["ottawa"]
    assert s.gis_zoning is None and s.zoning_url == "TODO"
    src = (REPO_ROOT / "src" / "watermark" / "sites" / "_profiles.py").read_text()
    block = src[src.index('slug="ottawa"') : src.index('county_name="Putnam County, OH"')]
    assert "SEARCHED AND NEGATIVE" in block
    # The 499 must stay paired with WHY it proves nothing, or a later reader will mistake it
    # for a secured-but-existing zoning service and go hunting for a token.
    assert "499 Token Required" in block
    assert "does not exist" in block and "NOT evidence" in block
    assert "amlegal.com" in block  # the code is text-only, and where
    assert "2026-08-04" in block  # the modernization RFP's proposal deadline


def test_ottawa_parcel_assemblage_is_the_philips_campus_not_the_inlot_run() -> None:
    """The committed geometry is the FORMER SYLVANIA/PHILIPS CRT WORKS (#1420) — two contiguous
    parcels, two unrelated owners, both conveyed by warranty deed in the 2006 Chapter 11 year.
    The load-bearing correction is that the issue's own table is wrong: it lists inlots 1541-1543
    as the rest of the subdivided campus, and they are 207-1,090 m away because Putnam issues
    inlot numbers in PLATTING order, not geographic order. That disproof, the across-the-street
    IL 1536 lead, and the tax cross-check that settles which of two published improvement values
    is live all have to keep being stated."""
    fc = json.loads(
        (REPO_ROOT / "data" / "reference" / "ottawa" / "parcel-assemblage.geojson").read_text()
    )
    assert len(fc["features"]) == 2
    props = {f["properties"]["parcel_id"]: f["properties"] for f in fc["features"]}
    assert set(props) == {"322220000000", "322260000000"}
    # Two UNRELATED owners — this is a broken-up works, not one operator's holding.
    assert {p["owner"] for p in props.values()} == {"OTTAWA OH LLC", "VERHOFF PROPERTIES LLC"}
    remediation = props["322220000000"]
    assert remediation["situs_address"].startswith("700 N PRATT ST")
    assert remediation["acres"] == 22.842 and remediation["inlot"] == 1540
    assert remediation["last_sale_date"] == "2006-12-21"
    assert remediation["last_sale_amount"] == 500000
    endera = props["322260000000"]
    assert endera["acres"] == 15.392 and endera["inlot"] == 1544
    assert endera["last_sale_date"] == "2006-07-11" and endera["last_sale_amount"] == 350000
    # Both industrial, both warranty deeds, both 2006 — the disposition signature.
    assert {p["land_use_code"] for p in props.values()} == {350}
    assert {p["conveyance_type"] for p in props.values()} == {"WAR"}
    assert all(p["last_sale_date"].startswith("2006-") for p in props.values())
    # The auditor citation is the LAYER's own PARCELURL, asserted equal at build time.
    for pid, p in props.items():
        assert p["auditor_url"].endswith(f"Parcel?Parcel={pid}")
    prov = fc["bosc:provenance"]
    assert prov["total_cama_acres"] == 38.234 and prov["total_planar_acres"] == 38.293
    assert sum(p["acres"] for p in props.values()) == pytest.approx(prov["total_cama_acres"])
    caveats = prov["caveats"]
    # The inlot-adjacency disproof — the issue's table said these were part of the campus.
    assert any("1541" in c and "1,090.26 m" in c and "platting order" in c for c in caveats)
    # The across-the-street industrial neighbour is a LEAD, excluded, not a member.
    assert any("IL 1536" in c and "20.13 m" in c for c in caveats)
    # Contiguity, the two-layer ownership corroboration, and the tax cross-check.
    assert any("CONTIGUOUS" in c for c in caveats)
    assert any("ParcelsJoined" in c and "AGREE" in c for c in caveats)
    assert any("0.0065989" in c and "0.0031671" in c for c in caveats)
    # It must keep saying this is NOT a data-center campus.
    assert any("FORMER industrial works" in c and "not a proposed" in c for c in caveats)


def test_van_wert_parcel_schema_is_agol_cama() -> None:
    """Van Wert's parcel gap (#421) is closed by the county's ArcGIS Online migration: the
    bhamaps PAT MapServer died with its expired cert (the ArcGIS Server was removed from the
    host), and the AGOL parcel_joinedVWOH layer is the owner-bearing auditor-CAMA join —
    Champaign's CCEO vendor pattern, with Van-Wert-specific semantics (PPClassNumber is the
    numeric use code, no owner mailing-address field, dashless stored PIN). Golden +
    param-stability: the schema reproduces the live field-map, and a fetch_parcel request built
    from it hashes to the committed fixture (the new connector's zero-drift guard)."""
    p = SITES["van-wert"].gis_parcel
    assert p is not None and p is VAN_WERT_PARCEL_SCHEMA
    assert p.connector == "van_wert_gis" and p.reference_dir == "van-wert-gis"
    assert p.id_field == "PIN" and p.id_normalize == "dashless"  # dashed auditor form -> PIN
    assert p.owner_field == "PPOwner" and p.defense is None  # owner present; no enclave scan
    assert p.land_use_field == "PPClassNumber" and p.land_use_decode == "int"
    assert p.date_decode == "epoch_millis"  # esriFieldTypeDate PPSaleDate
    assert p.owner_addr_fields == ()  # no owner mailing-address field on this layer
    assert p.cauv_field == "" and p.valid_sale_field == ""  # PPOnCauv/PPSalesType unmapped
    assert p.query_scope == ""  # single-jurisdiction layer
    assert "services8.arcgis.com/G5sGKRBVtJMunpVA" in p.meta.source_url
    assert "ags.bhamaps.com" not in SITES["van-wert"].parcels_url  # the dead host, never re-wired

    base = {"f": "json", "returnGeometry": "false"}
    key = cache_key(
        {
            **base,
            "where": f"{p.id_field}='170347180100'",
            "outFields": ",".join(p.out_fields),
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"van wert param drift: {key}"

    # Param stability for the committed assemblage's OWNER scan too (#1403) — the geojson pull
    # that produced data/reference/van-wert/parcel-assemblage.geojson replays from its fixture.
    owner_key = cache_key(
        {
            "f": "geojson",
            "returnGeometry": "true",
            "where": f"UPPER({p.owner_field}) LIKE '%QTS VAN WERT%'",
            "outFields": ",".join(p.out_fields),
            "outSR": "4326",
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{owner_key}.json").is_file(), (
        f"van wert owner-scan param drift: {owner_key}"
    )


def test_van_wert_hsg_is_ssurgo_verified_dual_not_a_flat_d() -> None:
    """#1403: the committed campus assemblage let SSURGO run, and it CORRECTED the profile's
    [inference]. The old flat "D" read the ground right — Great Black Swamp lake-plain clays, and
    it even named Hoytville — but NRCS rates Hoytville C/D, and a dual group is two drainage
    conditions rather than a spelling (WS-20/#1620). Collapsing it to the undrained letter is not
    the safe direction: it inflates the PRE-development curve number of ground that is tile-drained
    CAUV row crop today, and so understates the pre-to-post delta the screen exists to measure.
    Guard the dual letter AND the reasoning — a future edit that re-flattens it is the bug this
    test exists to catch."""
    s = SITES["van-wert"]
    assert s.dominant_hsg == "C/D"
    assert normalize_hsg(s.dominant_hsg) != normalize_hsg("D")  # a dual group, not its letter
    assert "SSURGO" in s.hsg_citation and "Hoytville" in s.hsg_citation
    assert "44 of 45" in s.hsg_citation  # the sample the correction rests on
    # The scenario switch is LIVE here (unlike Sidney's single group) — both conditions resolve.
    assert (s.pre_drainage_condition, s.post_drainage_condition) == ("drained", "undrained")
    # The cover knobs the assemblage unblocked — no TODO left on the stormwater scenario.
    assert (s.pre_cover, s.post_cover, s.developed_pervious_cover) == (
        "cropland",
        "developed_campus",
        "open_space",
    )
    # The committed geometry + footprint the SSURGO run and the places domain both read.
    assert s.parcels_relpath == "reference/van-wert/parcel-assemblage.geojson"
    assert s.footprint_relpath == "extracted/van-wert/bosc-site-footprint.yaml"


def test_van_wert_parcel_assemblage_is_the_qts_holding_not_the_annexation() -> None:
    """The committed geometry closes the register's deed-grantee [open] (#1403): FIVE parcels, all
    QTS VAN WERT LLC, 900.59 ac deeded / 901.502 ac planar. Two reconciliations are pinned because
    they point opposite ways — the holding meets QTS's own quoted 902-ac campus to 0.16%, and falls
    61.4 ac short of the ~962 ac annexed, so the committed boundary is the OWNERSHIP holding and
    never the annexation. The provenance also has to keep saying that the four same-day parcels'
    shared consideration is not summed, and that the Marsh remainder next door is excluded."""
    fc = json.loads(
        (REPO_ROOT / "data" / "reference" / "van-wert" / "parcel-assemblage.geojson").read_text()
    )
    assert len(fc["features"]) == 5
    props = {f["properties"]["parcel_id"]: f["properties"] for f in fc["features"]}
    assert {p["owner"] for p in props.values()} == {"QTS VAN WERT LLC"}
    anchor = props["17-034718.0100"]
    assert anchor["acres"] == 221.15 and anchor["planar_acres"] == 221.21
    assert anchor["last_sale_date"] == "2026-06-18" and anchor["last_sale_amount"] == 110575000
    assert anchor["last_sale_amount"] == round(anchor["acres"] * 500_000)  # exactly $500k/ac
    # The other four share one date + one consideration — one multi-parcel deed, never summed.
    others = [p for k, p in props.items() if k != "17-034718.0100"]
    assert {p["last_sale_date"] for p in others} == {"2026-06-16"}
    assert {p["last_sale_amount"] for p in others} == {39117825}
    prov = fc["bosc:provenance"]
    assert prov["owner_of_record"] == "QTS VAN WERT LLC"
    assert prov["total_cama_acres"] == 900.59 and prov["total_planar_acres"] == 901.502
    assert abs(prov["total_cama_acres"] - 902) / 902 < 0.005  # meets the quoted campus figure
    assert 962 - prov["total_cama_acres"] > 60  # but NOT the annexation — that gap stays [open]
    assert any("902" in c and "962" in c for c in prov["caveats"])
    assert any("NOT added across them" in c for c in prov["caveats"])
    assert any("19-041272.0000" in c and "EXCLUDED" in c for c in prov["caveats"])
    # The campus straddles two school districts — the register had only Lincolnview.
    assert {p["school_district"] for p in props.values()} == {
        "Lincolnview School District",
        "Van Wert School District",
    }


def test_miami_parcel_schema_is_agol_cama() -> None:
    """Troy·Piqua's parcel gap (#1483) is closed by Miami County's ArcGIS Online parcel_joined
    layer — Champaign's CCEO vendor pattern (same service name), with Miami-specific semantics:
    the numeric use code is PPClassNumber (PPClassCode is the class LETTER, like Van Wert),
    owner mailing is assembled from the four tax-payer columns, and PPHasCAUV is a 0/1 flag left
    unmapped. Golden field-map lock (no fixture-replay: the campus feed reads the committed
    parcel-assemblage.geojson, so no test drives the live miami_gis connector offline)."""
    p = SITES["troy-piqua"].gis_parcel
    assert p is not None and p is MIAMI_PARCEL_SCHEMA
    assert p.connector == "miami_gis" and p.reference_dir == "troy-piqua-gis"
    assert p.id_field == "PARCEL" and p.id_normalize == "verbatim"  # dashed prefixed auditor form
    assert p.owner_field == "PPOwner" and p.defense is None  # owner present; no enclave scan
    assert p.land_use_field == "PPClassNumber" and p.land_use_decode == "int"
    assert p.date_decode == "epoch_millis"  # esriFieldTypeDate PPSaleDate
    assert p.owner_addr_fields == ("TaxPAddr", "TaxPCity", "TaxPState", "TaxPZip")  # 4-part mailing
    assert p.cauv_field == "" and p.valid_sale_field == ""  # PPHasCAUV 0/1 flag unmapped
    assert p.query_scope == ""  # single-jurisdiction layer (no statewide County= scope)
    assert "services3.arcgis.com/wCWf4EGMg4PzHwzA" in p.meta.source_url
    assert "wCWf4EGMg4PzHwzA" in SITES["troy-piqua"].parcels_url  # profile endpoint matches schema


def test_shelby_parcel_schema_replaces_the_ogrip_substitute() -> None:
    """Sidney's parcel gap (#1379) is closed by the Shelby County Engineer's Office AGOL Parcels
    layer — the FULL auditor CAMA join (owner, deed book/page, conveyance, appraised values),
    replacing the OGRIP statewide substitute the profile carried. That substitute was not merely
    partial here: for Shelby it is owner-redacted AND a 2023-05-23 extract, so it predates the
    whole Project Galaxy transfer and can name no grantee. Golden field-map lock + the param-
    stability guard against the committed owner-scan fixture."""
    p = SITES["sidney"].gis_parcel
    assert p is not None and p is SHELBY_PARCEL_SCHEMA
    assert p.connector == "shelby_gis" and p.reference_dir == "sidney-gis"
    assert p.id_field == "PIN" and p.id_normalize == "verbatim"  # dashed "26-03-201-002"
    assert p.owner_field == "Listed_Name" and p.defense is None  # owner present; no enclave scan
    assert p.land_use_field == "Land_Use_Code" and p.land_use_decode == "int"
    assert p.date_decode == "epoch_millis"  # esriFieldTypeDate Date_Conveyed
    assert p.market_total_field == "Appraised_Total_100"  # the 100% market value, NOT Taxable_*
    assert p.cauv_field == ""  # Has_CAUV is a YES/NO flag, not a value
    assert p.valid_sale_field == "Valid_Sale"
    assert p.query_scope == ""  # single-jurisdiction layer (no statewide County= scope)
    assert "services6.arcgis.com/fzPZZJiNVtryYcsC" in p.meta.source_url
    assert "fzPZZJiNVtryYcsC" in SITES["sidney"].parcels_url  # profile endpoint matches schema
    # The OGRIP substitute is gone from Sidney — its stale extract is the reason (#1379).
    assert "OhioStatewidePacels_full_view" not in SITES["sidney"].parcels_url
    assert p.connector != "ohio_parcels"

    # Param stability: the committed assemblage's owner scan replays from its fixture.
    key = cache_key(
        {
            "f": "geojson",
            "returnGeometry": "true",
            "where": f"UPPER({p.owner_field}) LIKE '%AMAZON DATA SERVICES%'",
            "outFields": ",".join(p.out_fields),
            "outSR": "4326",
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"shelby param drift: {key}"


def test_sidney_zoning_schema_is_polygon_only_and_predates_the_campus() -> None:
    """Sidney's zoning endpoint EXISTS and is now wired (#1379) — but it cannot answer the campus
    question, and the schema says so rather than leaving the profile's `zoning_url="TODO"`. It is
    the Findlay shape (polygon-only, no parcel id -> per-parcel joins refuse cleanly), city-limits
    only, and a 2016-adopted layer whose sibling annexation layer stops at 2023-08-28 — so the
    2025-conveyed campus parcel falls in a hole in it and its district stays [open]."""
    z = SITES["sidney"].gis_zoning
    assert z is not None and z is SIDNEY_ZONING_SCHEMA
    assert z.connector == "sidney_gis" and z.reference_dir == "sidney-gis"
    assert z.parcel_field is None  # polygon-only: the district catalog works, parcel joins don't
    assert z.out_fields == ("OBJECTID_1", "CODE")  # the parcel field drops out of the request
    assert z.zoning_field == "CODE" and z.cited_meta is None  # no parcel join -> no cited scan
    assert "SidneyGIS_AllLayers/MapServer/270" in z.meta.source_url
    assert SITES["sidney"].zoning_url == z.meta.source_url  # profile endpoint matches schema
    # The currency gap is recorded as a caveat, not discovered again at read time.
    assert any("2023-08-28" in c for c in z.meta.caveats)
    assert any("26-03-201-002" in c for c in z.meta.caveats)


def test_sidney_hsg_is_ssurgo_verified_end_moraine_not_buried_valley() -> None:
    """#1379: the committed campus footprint let SSURGO run, and it INVERTED the profile's
    [inference]. The old "B" argued from the Great Miami buried-valley sole-source aquifer; the
    campus sits ~2 mi west of the valley on the Wisconsinan end moraine, whose till surface is
    group D (62/64 sampled points). Guard the letter AND the reasoning — a future edit that
    restores the aquifer argument for this footprint is the bug this test exists to catch."""
    s = SITES["sidney"]
    assert s.dominant_hsg == "D"
    # The claim's OWN register leads the citation; the later "[inference]" mention is the
    # superseded reading being narrated, not this value's tag.
    assert s.hsg_citation.startswith("[verified]") and "SSURGO" in s.hsg_citation
    assert "end moraine" in s.hsg_citation.lower()
    assert "prior [inference] of HSG 'B'" in s.hsg_citation
    # The cover knobs the footprint unblocked — no TODO left on the stormwater scenario.
    assert (s.pre_cover, s.post_cover, s.developed_pervious_cover) == (
        "cropland",
        "developed_campus",
        "open_space",
    )
    # The committed geometry + footprint the SSURGO run and the places domain both read.
    assert s.parcels_relpath == "reference/sidney/parcel-assemblage.geojson"
    assert s.footprint_relpath == "extracted/sidney/bosc-site-footprint.yaml"


def test_sidney_parcel_assemblage_is_the_consolidated_amazon_parcel() -> None:
    """The committed geometry backs the register's closed acreage [open] (#1379/#511): ONE parcel,
    Amazon Data Services Inc, 243.092 ac deeded vs 235.468 ac planar (the two are deliberately not
    reconciled), and the provenance records that the register's "2388 W. Millcreek Rd" situs was
    retired by a consolidation plat rather than being wrong."""
    fc = json.loads(
        (REPO_ROOT / "data" / "reference" / "sidney" / "parcel-assemblage.geojson").read_text()
    )
    assert len(fc["features"]) == 1
    props = fc["features"][0]["properties"]
    assert props["parcel_id"] == "26-03-201-002"
    assert props["owner"] == "AMAZON DATA SERVICES INC"
    assert props["acres"] == 243.092 and props["planar_acres"] == 235.468
    assert props["deed_reference"] == "OR2329/454"
    assert props["last_sale_date"] == "2025-11-24" and props["last_sale_amount"] == 5621490
    prov = fc["bosc:provenance"]
    assert prov["parcel_ids"] == ["26-03-201-002"] and prov["total_cama_acres"] == 243.092
    # The retired-situs reconciliation and the excluded DP&L lead are both on the record.
    assert any("26-03-226-001" in c and "2388" in c for c in prov["caveats"])
    assert any("26-03-429-009" in c and "[inference]" in c for c in prov["caveats"])


def test_clinton_parcel_schema_replaces_the_ogrip_substitute() -> None:
    """Wilmington's parcel gap (#1470) is closed by the Clinton County GIS Department's own
    auditor CAMA join — the layer the City's published zoning application uses as its Parcel
    layer — replacing the OGRIP statewide substitute the profile carried scoped to
    ``County='Clinton'``. That substitute is owner-redacted by construction AND, for Clinton,
    reports a NULL ``CurrentTo`` (no stated export date at all), so it can name no grantee: the
    whole Cosler Farm / Ardent-TAC corridor was invisible through it. Golden field-map lock +
    the param-stability guard against the committed assemblage fixture."""
    p = SITES["wilmington"].gis_parcel
    assert p is not None and p is CLINTON_PARCEL_SCHEMA
    assert p.connector == "clinton_gis" and p.reference_dir == "wilmington-gis"
    assert p.id_field == "PIN" and p.id_normalize == "verbatim"  # dashed "285-13-02-01-0000-00"
    assert p.owner_field == "Listed_Name" and p.defense is None  # owner present; no enclave scan
    assert p.land_use_field == "Land_Use_Code" and p.land_use_decode == "int"
    # Clinton serves Date_Conveyed as pre-formatted TEXT ("12/10/2025 12:00:00 AM"), NOT as an
    # esriFieldTypeDate — decoding it as "iso" would carry that whole string through as a date.
    assert p.date_decode == "mdyyyy_slash"
    assert p.market_total_field == "Appraised_Total_100"  # the 100% market value, NOT Taxable_*
    assert p.cauv_field == ""  # Has_CAUV is a YES/NO flag, not a value
    assert p.valid_sale_field == "Valid_Sale"
    assert p.query_scope == ""  # single-jurisdiction layer (no statewide County= scope)
    assert "services1.arcgis.com/tAhcHWpOD9ygNPbJ" in p.meta.source_url
    assert "tAhcHWpOD9ygNPbJ" in SITES["wilmington"].parcels_url  # profile matches schema
    # The OGRIP substitute is gone from Wilmington — its null CurrentTo is the reason (#1470).
    assert "OhioStatewidePacels_full_view" not in SITES["wilmington"].parcels_url
    assert p.connector != "ohio_parcels"
    # The two traps that cost the most on this layer are caveats, not rediscoveries.
    assert any("Consideration is the WHOLE DEED" in c for c in p.meta.caveats)
    assert any("cntyparcels" in c and "2023-08-28" in c for c in p.meta.caveats)

    # Param stability: the committed assemblage's PIN-list query replays from its fixture.
    pins = (
        "285-13-02-01-0000-00",
        "290-26-01-12-0000-00",
        "270-13-02-01-0000-00",
        "285-13-02-02-0000-00",
        "285-13-04-01-0000-00",
        "285-13-11-02-0000-00",
        "285-13-03-01-0000-00",
    )
    key = cache_key(
        {
            "f": "geojson",
            "returnGeometry": "true",
            "where": f"PIN IN ({','.join(repr(pin) for pin in pins)})",
            "outFields": ",".join(p.out_fields),
            "outSR": "4326",
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"clinton param drift: {key}"


def test_wilmington_zoning_schema_postdates_the_campus_and_predates_the_rezonings() -> None:
    """Wilmington's zoning endpoint EXISTS and is now wired (#1470), replacing the profile's
    ``zoning_url="TODO"``. It is the Findlay/Sidney shape (polygon-only, no parcel id -> per-parcel
    joins refuse cleanly) and city-limits only. Its CURRENCY is the finding: last edited
    2026-02-10, it DOES carry the Cosler Farm map rezoning and CANNOT carry the four Ardent/TAC
    rezonings Council passed nine days later — so those four parcels reading no city district is a
    publication lag, not a fact about their zoning. The schema says that rather than leaving a
    reader to re-derive it."""
    z = SITES["wilmington"].gis_zoning
    assert z is not None and z is WILMINGTON_ZONING_SCHEMA
    assert z.connector == "wilmington_gis" and z.reference_dir == "wilmington-gis"
    assert z.parcel_field is None  # polygon-only: the district catalog works, parcel joins don't
    assert z.out_fields == ("OBJECTID", "ZONING")  # the parcel field drops out of the request
    assert z.zoning_field == "ZONING" and z.cited_meta is None  # no parcel join -> no cited scan
    assert "ProposedZoning9/FeatureServer/0" in z.meta.source_url
    assert SITES["wilmington"].zoning_url == z.meta.source_url  # profile endpoint matches schema
    # The publication lag and the remand are recorded as caveats, not discovered at read time.
    assert any("2026-02-10" in c and "2026-02-19/20" in c for c in z.meta.caveats)
    assert any("Sharp" in c for c in z.meta.caveats)
    # "ProposedZoning9" is a publication artifact, not a status — say so once, here.
    assert any("publication artifact" in c for c in z.meta.caveats)


def test_wilmington_hsg_is_ssurgo_verified_and_confirms_the_prior_inference() -> None:
    """#1470: the committed corridor geometry let SSURGO run, and unlike Sidney (B->D), Urbana
    (B->C) and Troy-Piqua (B->C/D) it CONFIRMED the profile's prior [inference] rather than
    inverting it — the old reasoning argued from the surface (glaciated till plain, not
    buried-valley outwash) and was right. Guard the letter, the upgrade to [verified], and the two
    caveats that keep 'C' from being read as settled: it is a plurality on a mosaic where ~60% of
    campus points carry a dual rating whose undrained letter is D, and it is grid-stable for the
    campus but not for the whole corridor."""
    s = SITES["wilmington"]
    assert s.dominant_hsg == "C"
    assert s.hsg_citation.startswith("[verified]") and "SSURGO" in s.hsg_citation
    assert "PLURALITY" in s.hsg_citation and "undrained letter is D" in s.hsg_citation
    assert "prior [inference]" in s.hsg_citation
    # The cover knobs the footprint unblocked — no TODO left on the stormwater scenario.
    assert (s.pre_cover, s.post_cover, s.developed_pervious_cover) == (
        "cropland",
        "developed_campus",
        "open_space",
    )
    # The committed geometry + footprint the SSURGO run and the places domain both read.
    assert s.parcels_relpath == "reference/wilmington/parcel-assemblage.geojson"
    assert s.footprint_relpath == "extracted/wilmington/bosc-site-footprint.yaml"
    # The toxics window is DERIVED from that geometry, not drawn: it contains the corridor's
    # union bounds and nothing much more.
    lat_min, lat_max, lon_min, lon_max = s.toxic_corridor_bbox
    assert (lat_min, lat_max, lon_min, lon_max) == (39.400, 39.429, -83.870, -83.833)
    fc = json.loads(
        (REPO_ROOT / "data" / "reference" / "wilmington" / "parcel-assemblage.geojson").read_text()
    )
    lons = [x for f in fc["features"] for ring in f["geometry"]["coordinates"] for x, _ in ring]
    lats = [y for f in fc["features"] for ring in f["geometry"]["coordinates"] for _, y in ring]
    assert lat_min <= min(lats) and max(lats) <= lat_max
    assert lon_min <= min(lons) and max(lons) <= lon_max


def test_wilmington_parcel_assemblage_keeps_ownership_and_rezoning_apart() -> None:
    """The committed corridor is the one assemblage in the network that mixes two kinds of
    boundary, and ``corridor_role`` is what keeps them from being read as one campus (#1470):
    three parcels DEEDED to Amazon Data Services Inc on a single instrument, and four tracts that
    are a REZONING SCHEDULE still in their original owners' names. The union being a single
    polygon is what upgrades the register's '~1,000+ acre corridor' from a sum of press acreages
    to a measurement."""
    fc = json.loads(
        (REPO_ROOT / "data" / "reference" / "wilmington" / "parcel-assemblage.geojson").read_text()
    )
    props = [f["properties"] for f in fc["features"]]
    assert len(props) == 7
    campus = [p for p in props if p["corridor_role"] == "campus_holding"]
    rezone = [p for p in props if p["corridor_role"] == "petitioned_rezoning"]
    assert len(campus) == 3 and len(rezone) == 4
    # Ownership: one grantee, one deed, one consideration repeated across the three rows.
    assert {p["owner"] for p in campus} == {"AMAZON DATA SERVICES INC"}
    assert {p["deed_reference"] for p in campus} == {"2025-00005287"}
    assert {p["last_sale_date"] for p in campus} == {"2025-12-10"}
    assert {p["last_sale_amount"] for p in campus} == {86436000}
    tract = next(p for p in campus if p["parcel_id"] == "285-13-02-01-0000-00")
    assert tract["situs_address"].startswith("1488 S US 68") and tract["acres"] == 471.609
    # Rezoning: four ordinances, four DIFFERENT owners, none of them an Ardent/TAC entity.
    assert {p["rezoning_ordinance"] for p in rezone} == {"O-26-04", "O-26-05", "O-26-06", "O-26-07"}
    assert len({p["owner"] for p in rezone}) == 4
    assert not any("ARDENT" in p["owner"].upper() for p in rezone)
    assert all(p["rezoning_ordinance"] is None for p in campus)
    prov = fc["bosc:provenance"]
    assert prov["campus_holding_cama_acres"] == 478.885
    assert prov["petitioned_rezoning_cama_acres"] == 544.879
    assert prov["total_cama_acres"] == 1023.764
    # One contiguous block: the union equals the sum of the parts, so nothing overlaps.
    assert prov["union_planar_acres"] == prov["total_planar_acres"]
    assert any("SINGLE polygon" in c for c in prov["caveats"])
    assert any("NO Ardent/TAC entity holds any land" in c for c in prov["caveats"])


def test_bryan_parcel_schema_is_ogrip_statewide_williams() -> None:
    """Bryan's parcel gap (#410) is closed by the OGRIP Ohio statewide layer scoped to County=
    'Williams' — the same owner-redacted substitute as Findlay (Hancock has no county REST; Williams'
    bhamaps host is cert-blocked, #421/#394). It overrides id_normalize to 'verbatim' because
    Williams' stored LocalParcelID is dashed. The ArcGIS the onboarding pass flagged as "Williams
    County" is North Dakota — explicitly NOT wired (the cross-state guard)."""
    p = SITES["bryan"].gis_parcel
    assert p is not None and p.connector == "ohio_parcels"  # the shared statewide substitute
    assert p.reference_dir == "bryan-gis"
    assert p.query_scope == "County='Williams'"  # scoped to FIPS 39171
    assert p.id_normalize == "verbatim"  # Williams' LocalParcelID is dashed, not dashless
    assert p.owner_field == "" and p.defense is None  # owner-redacted; no defense scan
    assert p.land_use_decode == "leading_int"

    # The North Dakota org must never be referenced by the Ohio Bryan profile (cross-state guard).
    bryan = SITES["bryan"]
    assert "D85sDZoJyameepNh" not in bryan.parcels_url
    assert "OhioStatewidePacels_full_view" in bryan.parcels_url

    base = {"f": "json", "returnGeometry": "false"}
    key = cache_key(
        {
            **base,
            "where": f"({p.id_field}='062-350-02-013.001') AND ({p.query_scope})",
            "outFields": ",".join(p.out_fields),
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"bryan param drift: {key}"


def test_toledo_gis_is_lucas_areis_owner_bearing() -> None:
    """Toledo's GIS (#384) is Lucas County AREIS — the network's richest: an owner-bearing parcel
    layer (AREIS/38, OWNER + situs + land-use, the first wired from a county's own REST since Lima/
    Putnam) AND a parcel-level zoning catalog (Parcel_Zoning, with a PARID join, unlike Findlay).
    Golden + param-stability: each schema reproduces the live field-map and a request built from it
    hashes to the committed fixture. Appraised values are deliberately absent (the layer-83 join)."""
    t = SITES["toledo"]
    pp = t.gis_parcel
    assert pp is not None and pp is LUCAS_AREIS_PARCEL_SCHEMA
    assert pp.connector == "lucas_areis" and pp.reference_dir == "toledo-gis"
    assert pp.id_field == "PARID" and pp.owner_field == "OWNER"  # owner-bearing
    assert pp.land_use_field == "LUC" and pp.land_use_decode == "int"
    assert pp.market_total_field == "" and pp.defense is None  # values on layer 83 (deferred join)
    assert "lcaudgis.co.lucas.oh.us" in pp.meta.source_url

    zz = t.gis_zoning
    assert zz is not None and zz is LUCAS_ZONING_SCHEMA
    assert zz.connector == "lucas_zoning" and zz.parcel_field == "PARID"  # parcel-level (joinable)
    assert zz.zoning_field == "ZONING" and zz.http_method == "GET"

    base = {"f": "json", "returnGeometry": "false"}
    pkey = cache_key(
        {
            **base,
            "where": f"{pp.id_field}='3850130'",
            "outFields": ",".join(pp.out_fields),
            "resultOffset": 0,
            "resultRecordCount": pp.page_size,
        }
    )
    assert (FIXTURES / pp.connector / f"{pkey}.json").is_file(), f"lucas parcel param drift: {pkey}"
    zkey = cache_key(
        {
            **base,
            "where": f"{zz.parcel_field}='3850130'",
            "outFields": ",".join(zz.out_fields),
            "resultOffset": 0,
            "resultRecordCount": zz.page_size,
            "orderByFields": zz.object_id_field,
        }
    )
    assert (FIXTURES / zz.connector / f"{zkey}.json").is_file(), f"lucas zoning param drift: {zkey}"


def test_fort_wayne_gis_is_allen_in_imap_owner_bearing() -> None:
    """Fort Wayne's parcel/zoning gap (#235/#360) is closed by the Allen County (IN) iMap ArcGIS —
    the first non-Ohio GIS in the network. The parcel layer is owner-bearing (owner + situs + the
    deed TransferDate, decoded from Esri epoch-millis) but NOT a CAMA layer (no market/land-use/
    acreage fields). Zoning is a county-wide polygon-only catalog (no parcel join, like Findlay).
    Golden + param-stability: the parcel schema reproduces the live field-map and a fetch_parcel
    request built from it hashes to the committed fixture (the new connector's zero-drift guard)."""
    fw = SITES["fort-wayne"]
    p = fw.gis_parcel
    assert p is not None and p is ALLEN_IN_PARCEL_SCHEMA
    assert p.connector == "allen_in_gis" and p.reference_dir == "fort-wayne-gis"
    assert p.id_field == "GISPublished.SDE.Parcel_Poly.PIN" and p.id_normalize == "dashless"
    assert p.owner_field == "GISPublished.SDE.CurrentOwner.OwnerofRecord"  # owner-bearing
    assert p.date_decode == "epoch_millis"  # esriFieldTypeDate (ms since epoch)
    assert p.market_total_field == "" and p.land_use_field == ""  # not a CAMA layer
    assert p.defense is None and p.query_scope == ""  # no federal-enclave scan; single jurisdiction
    assert "gis1.acimap.us" in p.meta.source_url

    z = fw.gis_zoning
    assert z is not None and z is FORT_WAYNE_ZONING_SCHEMA
    assert z.connector == "allen_in_gis_zoning" and z.reference_dir == "fort-wayne-gis"
    assert z.parcel_field is None  # polygon-only — per-parcel zoning join refuses (like Findlay)
    assert z.zoning_field == "GISPublished.SDE.Zoning_Polygons.ZONING_CLASS"
    assert z.http_method == "GET" and z.cited_meta is None

    base = {"f": "json", "returnGeometry": "false"}
    key = cache_key(
        {
            **base,
            "where": f"{p.id_field}='021327100001000077'",
            "outFields": ",".join(p.out_fields),
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"allen-in param drift: {key}"


# --- Multi-facility model (#1628, epic #1626 F2) -------------------------------------------
def _fac(name: str, **kw: object) -> SiteFacility:
    from watermark.sites import FacilityLifecycle

    kw.setdefault("status", FacilityLifecycle.CONFIRMED)
    return SiteFacility(name=name, **kw)


def test_facility_property_returns_the_primary_campus() -> None:
    """`facility` is the first of `facilities` (the modeled campus) — every legacy `.facility`
    reader keeps working through it; a facility-less site resolves to None."""
    wilmington = SITES["wilmington"]
    assert len(wilmington.facilities) >= 2, "Wilmington is the migrated multi-campus site"
    assert wilmington.facility is wilmington.facilities[0]
    assert wilmington.facility is not None and wilmington.facility.name == "Cosler Farm campus"
    assert SITES["toledo"].facilities == () and SITES["toledo"].facility is None


def test_facility_key_is_minted_from_name_and_unique_within_a_site() -> None:
    from pydantic import ValidationError

    from watermark.sites import SiteProfile

    assert SITES["lima"].facility is not None
    assert SITES["lima"].facility.key == "project-bosc"  # auto-filled from name
    # Two facilities that slug to the same key are rejected within one site.
    dup = SITES["toledo"].model_copy(
        update={"facilities": (_fac("Same Name"), _fac("Same Name"))}
    )  # model_copy re-validates
    with pytest.raises(ValidationError, match="facility keys must be unique"):
        SiteProfile.model_validate(dup.model_dump())


def test_facility_load_may_be_entirely_open() -> None:
    """A rezoning-only second campus (Wilmington Ardent/TAC) is a valid facility with no IT load —
    the three it_load fields move together and carry no basis citation when all-open."""
    from pydantic import ValidationError

    ardent = SITES["wilmington"].facilities[1]
    assert ardent.name == "Ardent/TAC corridor"
    assert ardent.it_load_mw is None and ardent.it_load_low_mw is None
    assert ardent.air_permit_citation is None and ardent.it_load_citation is None
    # A partial load triple is rejected (all set, or all None).
    with pytest.raises(ValidationError, match="set together"):
        _fac("Bad", it_load_mw=100.0)  # low/high omitted


def test_it_load_grounding_grades_documentary_depth() -> None:
    """The #1630 grounding grade drives facility readiness. ``permit`` is DERIVED from a wired air
    permit; a non-permit disclosed load reports its declared grade; an [open] load has none.
    ``is_instrument_grounded`` (the readiness ``live`` signal) is true only for permit / disclosure
    grounding (or a document-disclosed cooling mechanism)."""
    from watermark.sites import ItLoadGrounding

    lima = SITES["lima"].facility  # air-permit-grounded (OEPA PTI)
    assert lima is not None
    assert lima.it_load_grounding is ItLoadGrounding.PERMIT and lima.is_instrument_grounded
    findlay = SITES["findlay"].facility  # filed SEC S-1 disclosure
    assert findlay is not None
    assert (
        findlay.it_load_grounding is ItLoadGrounding.DISCLOSURE and findlay.is_instrument_grounded
    )
    urbana = SITES["urbana"].facility  # floor-area SCREENING [inference]
    assert urbana is not None
    assert urbana.it_load_grounding is ItLoadGrounding.SCREENING
    assert not urbana.is_instrument_grounded
    van_wert = SITES["van-wert"].facility  # announced-ceiling [reference]
    assert van_wert is not None
    assert van_wert.it_load_grounding is ItLoadGrounding.REFERENCE
    assert not van_wert.is_instrument_grounded
    # An [open] load has no grade at all (a rezoning-only campus).
    ardent = SITES["wilmington"].facilities[1]
    assert ardent.it_load_mw is None and ardent.it_load_grounding is None


def test_it_load_source_pairs_with_the_non_permit_basis() -> None:
    """``it_load_source`` grades a NON-permit disclosed load only (#1630): a permit-grounded or
    [open] load leaves it None (permit grounding is derived from the air permit), and a non-permit
    disclosed load must declare a non-``permit`` grade — the readiness grade is structured, never
    re-keyed from the [verified]/[inference] tag in citation prose."""
    from pydantic import ValidationError

    # A non-permit disclosed load without a grade is rejected.
    with pytest.raises(ValidationError, match="must declare it_load_source"):
        _fac(
            "NoGrade",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="a floor-area screen",
        )
    # 'permit' is derived from a wired air permit, never hand-set on a non-permit basis.
    with pytest.raises(ValidationError, match="must declare it_load_source"):
        _fac(
            "PermitByHand",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="a floor-area screen",
            it_load_source="permit",
        )
    # A grade with no non-permit basis (an [open] load) is rejected.
    with pytest.raises(ValidationError, match="set it only alongside it_load_citation"):
        _fac(
            "OpenWithGrade",
            it_load_source="screening",
            facility_type="a rezoning corridor",
            disclosure_citation="[reference] a rezoning ordinance",
        )
    # A properly graded screening load validates and resolves to its declared grade.
    ok = _fac(
        "Screened",
        it_load_mw=70.0,
        it_load_low_mw=35.0,
        it_load_high_mw=115.0,
        it_load_citation="a floor-area screen",
        it_load_source="screening",
    )
    assert ok.it_load_grounding is not None and ok.it_load_grounding.value == "screening"
    assert not ok.is_instrument_grounded


# --- The disclosed backup fleet (#1771) ----------------------------------------------------
def test_lima_carries_the_cited_backup_total_not_the_product() -> None:
    """The site's most-cited number is TRANSCRIBED, never multiplied out.

    Lima's corpus, essay and docs all say ``~313 MW``; the components multiply to 313.5. Before
    #1771 the frontend carried 313 as a TS literal precisely because deriving it would restate
    the headline — so the cited total lives here, with its marker and its own citation, and the
    components stay for the arithmetic.
    """
    from watermark.sites import GensetRatingBasis

    lima = SITES["lima"].facility
    assert lima is not None
    assert lima.genset_count == 114 and lima.genset_mw == 2.75
    assert lima.genset_total_mw == 313.0  # the record's figure, not 114 * 2.75 = 313.5
    assert lima.genset_count * lima.genset_mw == 313.5
    assert lima.genset_total_approximate is True  # the "~" survives as data
    assert lima.genset_total_citation is not None
    # The total's citation is NOT the air permit's: the issued permit redacts the per-engine
    # rating and so cannot state the total — attributing ~313 MW to it would misattribute it.
    assert lima.genset_total_citation != lima.air_permit_citation
    assert lima.genset_rating_basis is GensetRatingBasis.DRAFT_ONLY


def test_fort_wayne_declares_a_derived_rating_and_no_cited_total() -> None:
    """Fort Wayne's permit states heat input, not an electrical rating, and states no total.

    So its rating is graded ``derived`` and ``genset_total_mw`` stays None — a consumer that
    needs a total derives it and must label it derived. Fabricating a "cited" 102 MW here would
    launder this platform's arithmetic into a disclosure.
    """
    from watermark.sites import GensetRatingBasis

    fw = SITES["fort-wayne"].facility
    assert fw is not None
    assert fw.genset_count == 34 and fw.genset_mw == 3.0
    assert fw.genset_rating_basis is GensetRatingBasis.DERIVED
    assert fw.genset_total_mw is None and fw.genset_total_citation is None
    assert fw.genset_total_approximate is False


def test_a_cited_backup_total_must_reconcile_with_its_own_fleet() -> None:
    """The guard that makes the cited total a second *representation*, not a second *source*.

    A hand-carried copy with nothing tying it to its components is the defect #1771 was filed
    about, so a total that stops reconciling refuses the write rather than shipping two numbers
    for one fleet.
    """
    from watermark.sites import GensetRatingBasis

    kw: dict[str, object] = {
        "air_permit_citation": "the permit",
        "genset_count": 114,
        "genset_mw": 2.75,
        "genset_rating_basis": GensetRatingBasis.DRAFT_ONLY,
    }
    # The real pairing: ~313 against a 313.5 product is a rounded transcription, and passes.
    ok = _fac("Cited", genset_total_mw=313.0, genset_total_citation="c", **kw)
    assert ok.genset_total_mw == 313.0
    # Restating the count as 115 (the permit's 114 hall gensets + the smaller HUBGEN) forks the
    # two: 313 against 316.25. The total is not silently corrected — the write is refused.
    with pytest.raises(ValidationError, match="no longer reconciles"):
        _fac(
            "Forked",
            genset_total_mw=313.0,
            genset_total_citation="c",
            **{**kw, "genset_count": 115},
        )
    # A total can never pass uncited, nor stand without the fleet it totals.
    with pytest.raises(ValidationError, match="set together"):
        _fac("Uncited", genset_total_mw=313.0, **kw)
    with pytest.raises(ValidationError, match="the fleet it totals"):
        _fac(
            "Fleetless",
            genset_total_mw=313.0,
            genset_total_citation="c",
            it_load_mw=275.0,
            it_load_low_mw=250.0,
            it_load_high_mw=300.0,
            it_load_citation="a floor-area screen",
            it_load_source="screening",
        )
    # And the "~" marker means nothing without a number to mark.
    with pytest.raises(ValidationError, match="marks a transcribed genset_total_mw"):
        _fac("BareMarker", genset_total_approximate=True, **kw)


def test_a_genset_rating_never_passes_ungraded() -> None:
    """Count / rating / rating-grade travel together (#1771).

    The count is a verbatim permit disclosure everywhere it appears; the rating is not. Letting a
    rating pass without its grade is what let a back-derived figure render beside a disclosed one
    under the same ``[verified]`` badge.
    """
    with pytest.raises(ValidationError, match="the genset fleet"):
        _fac("Ungraded", air_permit_citation="the permit", genset_count=34, genset_mw=3.0)
    # A facility with no disclosed generation leaves all three None — the common case.
    urbana = SITES["urbana"].facility
    assert urbana is not None
    assert urbana.genset_count is None and urbana.genset_rating_basis is None
    assert urbana.genset_total_mw is None


def test_facility_geometry_inherits_the_site_default() -> None:
    """`facility_geometry` resolves a facility's parcels/footprint, falling back to the site-level
    paths when the facility carries none of its own."""
    lima = SITES["lima"]
    assert lima.facility is not None
    parcels, footprint = lima.facility_geometry(lima.facility)
    assert parcels == lima.parcels_relpath and footprint == lima.footprint_relpath


def test_facility_feed_and_summary_project_the_model() -> None:
    """The `facility` feed + manifest summary are a faithful projection of `SiteProfile.facilities`
    (facility-gated: absent for a facility-less site)."""
    from watermark.config import Settings
    from watermark.site.facility import build_facility_feed, build_facility_summary
    from watermark.sites import DcEndUse, FacilityLifecycle

    feed = build_facility_feed(Settings(site="wilmington"))
    assert feed is not None and len(feed) == 2
    primary = feed[0]
    assert primary.is_primary and primary.key == "cosler-farm-campus"
    assert primary.end_use == DcEndUse.HYPERSCALE and primary.status == FacilityLifecycle.CONFIRMED
    assert not feed[1].is_primary and feed[1].it_load_mw is None  # Ardent/TAC — load [open]

    summary = build_facility_summary(Settings(site="wilmington"))
    assert summary is not None and summary.count == 2
    assert (
        summary.status == FacilityLifecycle.CONFIRMED
        and summary.primary_name == "Cosler Farm campus"
    )

    # Facility-gated: a facility-less site emits neither.
    assert build_facility_feed(Settings(site="toledo")) is None
    assert build_facility_summary(Settings(site="toledo")) is None


def test_facility_feed_carries_the_backup_fleet_across_the_seam() -> None:
    """The genset columns reach the bundle verbatim (#1771).

    They are disclosed campus data and belong in the facility inventory regardless; the immediate
    consumer is the frontend load report, which carried Lima's 313 MW / 114 gensets / 2,750 ekW as
    TS literals duplicating these very fields. Crossing the seam must not launder a grade: the
    cited total keeps its marker and its own citation, and Fort Wayne's total stays absent so the
    reader derives-and-labels rather than reading a disclosure that isn't there.
    """
    from watermark.config import Settings
    from watermark.site.facility import build_facility_feed
    from watermark.sites import GensetRatingBasis

    lima = (build_facility_feed(Settings(site="lima")) or [])[0]
    assert lima.genset_count == 114 and lima.genset_mw == 2.75
    assert lima.genset_total_mw == 313.0 and lima.genset_total_approximate is True
    assert lima.genset_rating_basis is GensetRatingBasis.DRAFT_ONLY
    assert lima.genset_total_citation and "313 MW" in lima.genset_total_citation

    fw = (build_facility_feed(Settings(site="fort-wayne")) or [])[0]
    assert fw.genset_count == 34 and fw.genset_mw == 3.0
    assert fw.genset_rating_basis is GensetRatingBasis.DERIVED
    assert fw.genset_total_mw is None and fw.genset_total_citation is None

    # A site-plan-grounded facility discloses no generation — all columns null, never zero.
    urbana = (build_facility_feed(Settings(site="urbana")) or [])[0]
    assert urbana.genset_count is None and urbana.genset_mw is None
    assert urbana.genset_rating_basis is None and urbana.genset_total_mw is None


def test_network_activity_carries_the_primary_facility_status() -> None:
    """The `network` feed's NodeActivity exposes the primary campus's lifecycle status (#1628), so
    the pure basin/directory builders read it off the feed instead of a hardcoded dict."""
    from watermark.config import Settings
    from watermark.network import build_basin_network
    from watermark.sites import FacilityLifecycle

    net = build_basin_network(settings=Settings(site="lima"))
    by_slug = {n.slug: n for n in net.nodes}
    lima_act = by_slug["lima"].activity
    assert lima_act.has_disclosed_facility and lima_act.facility_count == 1
    assert lima_act.facility_status == FacilityLifecycle.CONSTRUCTION
    if "findlay" in by_slug:  # a bitcoin/live campus in the same cross-site synthesis
        assert by_slug["findlay"].activity.facility_status == FacilityLifecycle.LIVE


def test_investigation_status_on_a_disclosed_facility_is_rejected() -> None:
    """A disclosed SiteFacility must be at least `confirmed` (#1628 review) — `investigation` is
    the facility-absent floor, so it can't attach to a facility that exists."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="at least"):
        _fac("Ghost Campus", status="investigation")


def test_open_load_facility_has_no_power_basis_and_leaks_no_lima_figures(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A rezoning-only primary (load entirely [open]) is not a derivable power basis, and the
    cooling model refuses it rather than substituting Lima's 275 MW / air-permit citation
    (#1628 review — the parallel leak `derive_power_basis` was already guarded against)."""
    import watermark.sites as sites
    from watermark.config import Settings
    from watermark.facility.power import derive_power_basis
    from watermark.hydrology.cooling import derive_cooling_basis

    open_primary = _fac(
        "Rezoning-Only Campus",
        facility_type="a rezoning corridor — every figure [open]",
        disclosure_citation="[reference] a rezoning ordinance",
    )
    assert open_primary.it_load_mw is None
    stub = sites.SITES["toledo"].model_copy(update={"facilities": (open_primary,)})
    monkeypatch.setitem(sites.SITES, "toledo", stub)
    assert stub.facility is not None and not stub.has_facility_power_basis
    # `derive_power_basis`'s it-load guard is NOT dead code (#1634 item 2 was filed before #1628
    # made `it_load_mw` optional): a disclosed facility whose load is entirely [open] reaches it.
    assert derive_power_basis(settings=Settings(site="toledo")) is None
    with pytest.raises(ValueError, match="no resolvable IT load"):
        derive_cooling_basis(Settings(site="toledo"), cooling_model="evaporative_tower")


def test_facility_feed_keeps_permit_vs_screening_grounding_distinct() -> None:
    """The `facility` feed carries air_permit_citation and it_load_citation as SEPARATE fields so a
    permit-grounded load (Lima) is structurally distinguishable from a screening bracket (Urbana),
    not collapsed into one prose blob (#1697 / #1628 review)."""
    from watermark.config import Settings
    from watermark.site.facility import build_facility_feed

    lima = build_facility_feed(Settings(site="lima"))
    assert lima is not None
    assert lima[0].air_permit_citation is not None and lima[0].it_load_citation is None
    assert (
        lima[0].cooling_model_source == "assumption"
    )  # Lima's archetype is asserted, not disclosed

    urbana = build_facility_feed(Settings(site="urbana"))
    assert urbana is not None
    assert urbana[0].it_load_citation is not None and urbana[0].air_permit_citation is None


def test_secondary_facility_does_not_inherit_the_primary_geometry() -> None:
    """A non-primary campus carries only its own geometry (None when unset) — never the primary
    campus's parcels/footprint, which would misattribute one campus's geometry to another
    (#1628 review).

    Wilmington is the sharp case, and #1470 sharpened it further. Before that issue the site's
    geometry knobs were uncommitted ``[open]`` placeholders, so BOTH rows shipped null and the
    test could only prove that a placeholder path doesn't become a phantom link. Now the geometry
    IS committed — and it deliberately covers the Ardent/TAC tracts too, because they adjoin the
    Cosler Farm campus in one contiguous corridor. So the primary inherits the site-level paths
    and the secondary still must not: the same file would otherwise read as *the Ardent campus's*
    footprint, when it is a rezoning schedule the corridor record keeps explicitly apart from the
    ownership holding. Ardent's own figures are all ``[open]`` (#1471) and its geometry stays
    null until it has one of its own."""
    from watermark.config import Settings
    from watermark.site.facility import build_facility_feed

    feed = build_facility_feed(Settings(site="wilmington"))
    assert feed is not None and len(feed) == 2
    ardent = feed[1]
    assert not ardent.is_primary and ardent.name == "Ardent/TAC corridor"
    assert ardent.parcels_relpath is None and ardent.footprint_relpath is None
    # The primary DOES inherit the site-level geometry #1470 committed.
    assert feed[0].is_primary and feed[0].name == "Cosler Farm campus"
    assert feed[0].parcels_relpath == "reference/wilmington/parcel-assemblage.geojson"
    assert feed[0].footprint_relpath == "extracted/wilmington/bosc-site-footprint.yaml"


def test_wood_parcel_schema_probes_a_vintage_the_server_does_not_publish() -> None:
    """Bowling Green's parcel gap (#1436) is closed by Wood County's own Vision CAMA join.

    Three field mappings on this layer are traps rather than conventions, and each is pinned here
    because the obvious reading is wrong. The deeded owner is ``Deeded_Name``: the column
    literally named ``Deeded_Owner`` is empty on every row. There is NO total-value column, so
    ``market_total_field`` is deliberately empty and ``market_total_value`` is null by
    construction — reading ``Prc_Ttl_Apprais_Lnd_Alt`` as the total would be wrong twice over,
    because that column is the CAUV land value. And the corpus deed pattern starts at the ``611-``
    rather than the auditor's printed ``J36-611-…`` prefix, because ``dashless`` normalization
    keeps the ``36`` of ``J36`` and would produce a 17-digit string matching nothing.
    """
    p = SITES["bowling-green"].gis_parcel
    assert p is not None and p is WOOD_PARCEL_SCHEMA
    assert p.connector == "wood_gis" and p.reference_dir == "bowling-green-gis"
    assert p.id_field == "Name" and p.id_normalize == "dashless"
    assert p.owner_field == "Owner_Name" and p.defense is None  # owner present; no enclave scan
    assert p.deeded_owner_field == "Deeded_Name"  # NOT the empty Deeded_Owner column
    assert p.date_decode == "epoch_millis"  # an esriFieldTypeDate, unlike Clinton's text field
    assert p.land_use_field == "Primary_Use" and p.land_use_decode == "int"  # a numeric STRING
    assert p.market_total_field == ""  # the layer publishes no total column at all
    assert p.cauv_field == "Prc_Ttl_Apprais_Lnd_Alt"  # the CAUV land value, despite the name
    assert p.valid_sale_field == "Qualified"  # "Q"/"U", the auditor's arms-length flag
    assert p.neighborhood_field == ""
    assert p.query_scope == ""  # single-jurisdiction layer (no statewide County= scope)
    assert p.deed_id_regex == r"\b\d{3}-\d{12}\b"  # the printed id MINUS its district prefix
    assert "Vision_Parcels/MapServer/0" in p.meta.source_url
    assert SITES["bowling-green"].parcels_url == p.meta.source_url  # profile matches schema
    # The vintage this server does not publish, and the row shape that reads as duplication.
    assert any("2025-07-25" in c and "editingInfo" in c for c in p.meta.caveats)
    assert any("ONE ROW PER POLYGON PART" in c for c in p.meta.caveats)
    assert any("CAUV LAND VALUE" in c.upper() for c in p.meta.caveats)
    assert any("Bowling Green KENTUCKY" in c for c in p.meta.caveats)

    # Param stability: the committed assemblage's Name-list query replays from its fixture.
    names = (
        "611190000003500",
        "611190000029510",
        "611300000001000",
        "611300000002000",
        "611190000037000",
        "611190000033000",
        "611190000036001",
        "611190000034000",
        "611190000008000",
        "611190000035000",
        "611190000009000",
        "611190000025000",
        "611190000006000",
        "611200000011000",
        "511210000002003",
    )
    key = cache_key(
        {
            "f": "geojson",
            "returnGeometry": "true",
            "where": "Name IN ('" + "','".join(names) + "')",
            "outFields": ",".join(p.out_fields),
            "outSR": "4326",
            "resultOffset": 0,
            "resultRecordCount": p.page_size,
        }
    )
    assert (FIXTURES / p.connector / f"{key}.json").is_file(), f"wood param drift: {key}"


def test_middleton_zoning_schema_is_the_townships_not_the_citys() -> None:
    """Bowling Green's zoning endpoint is the TOWNSHIP'S, and that is the finding (#1436).

    The campus sits in Middleton Township about 6 mi north of the corporation limits, so the City
    of Bowling Green's own ``Current Zoning`` layer — the endpoint the profile's TODO comment
    named — covers the Oppidan colo and not the campus. Of the two layers that do cover the
    township, the countywide one is a 2013 snapshot; this hosted one was built 2025-11-13 and
    therefore carries the 2023 agricultural-to-M-1 rezonings of the campus core. Neither carries
    the 2026-07-07 rezoning of the thirteen small parcels, which is a publication lag rather than
    a fact about their zoning — and the schema says so instead of leaving it to be rediscovered.
    """
    z = SITES["bowling-green"].gis_zoning
    assert z is not None and z is MIDDLETON_ZONING_SCHEMA
    assert z.connector == "middleton_gis" and z.reference_dir == "bowling-green-gis"
    assert z.parcel_field == "name"  # parcel-joined, unlike Findlay/Sidney/Wilmington's polygons
    assert z.zoning_field == "zone" and z.cited_meta is None
    assert z.page_size == 1000  # half the parcel layer's — a paging trap if assumed equal
    assert "Middleton_Twp_Zoning_Viewer26/FeatureServer/1" in z.meta.source_url
    assert SITES["bowling-green"].zoning_url == z.meta.source_url  # profile matches schema
    # It is NOT the city layer, and the reason is jurisdictional, not editorial.
    assert "gis.bgohio.org" not in z.meta.source_url
    assert any("gis.bgohio.org" in c and "Oppidan" in c for c in z.meta.caveats)
    # The three facts a reader would otherwise have to rediscover the hard way.
    assert any("2026-07-07" in c and "publication lag" in c for c in z.meta.caveats)
    assert any("OLDER PARCEL FABRIC" in c for c in z.meta.caveats)
    assert any("ZONE STRING IS CODE AND LABEL TOGETHER" in c for c in z.meta.caveats)


def test_bowling_green_hsg_corrects_the_form_of_the_rating_not_just_the_letter() -> None:
    """#1436: the committed geometry let SSURGO run and it returned a DUAL rating, C/D, where the
    profile carried a plain ``D``.

    Unlike Sidney (B->D), Urbana (B->C), Troy-Piqua (B->C/D) and Wilmington (C confirmed), the
    correction here is not about which letter: the prior inference read the Great Black Swamp
    lakebed clays correctly. What it got wrong is that the survey rates them dual — C where field
    tile is maintained, D in the natural undrained condition. Collapsing that to D pre-selects the
    high-runoff condition for every scenario including the pre-development one, where the ground
    IS drained, and puts the choice somewhere no per-scenario switch can see it.
    """
    s = SITES["bowling-green"]
    assert s.dominant_hsg == "C/D"  # the dual rating VERBATIM — never pre-collapsed
    assert s.hsg_citation.startswith("Hydrologic soil group C/D") and "SSURGO" in s.hsg_citation
    assert "428 of 428" in s.hsg_citation  # every point, every grid density
    assert "REPLACES the pre-#1436 [inference]" in s.hsg_citation
    # The dual-rating switches are live for this site in a way they are inert for a single group.
    assert (s.pre_drainage_condition, s.post_drainage_condition) == ("drained", "undrained")
    # The cover knobs the footprint unblocked — no TODO left on the stormwater scenario.
    assert (s.pre_cover, s.post_cover, s.developed_pervious_cover) == (
        "cropland",
        "developed_campus",
        "open_space",
    )
    assert s.parcels_relpath == "reference/bowling-green/parcel-assemblage.geojson"
    assert s.footprint_relpath == "extracted/bowling-green/bosc-site-footprint.yaml"
    # The toxics window is DERIVED from the campus geometry, not drawn.
    lat_min, lat_max, lon_min, lon_max = s.toxic_corridor_bbox
    assert (lat_min, lat_max, lon_min, lon_max) == (41.448, 41.475, -83.653, -83.626)
    fc = json.loads(
        (
            REPO_ROOT / "data" / "reference" / "bowling-green" / "parcel-assemblage.geojson"
        ).read_text()
    )
    campus = [f for f in fc["features"] if f["properties"]["parcel_role"] == "liames_assembly"]
    lons = [x for f in campus for ring in f["geometry"]["coordinates"] for x, _ in ring]
    lats = [y for f in campus for ring in f["geometry"]["coordinates"] for _, y in ring]
    assert lat_min <= min(lats) and max(lats) <= lat_max
    assert lon_min <= min(lons) and max(lons) <= lon_max


def test_bowling_green_assemblage_is_one_holding_and_three_other_claims() -> None:
    """``parcel_role`` keeps four different claims from being read as one 775-acre campus (#1436).

    The name is not cosmetic: the exporter's ``campus_from_parcels`` reserves ``role`` for its own
    display field and drops a source property of that name, so a discriminator called ``role``
    would vanish from the published feed and leave fifteen parcels all reading as campus.

    The measurement that matters is the contiguity. The register carried "~750-ac Liames
    assembly" as a press figure; the union of the twelve deeded parcels is a SINGLE polygon whose
    area equals the sum of the parts to within 0.005 ac, so the acreage is now a measurement of
    one block rather than an arithmetic total.
    """
    fc = json.loads(
        (
            REPO_ROOT / "data" / "reference" / "bowling-green" / "parcel-assemblage.geojson"
        ).read_text()
    )
    props = [f["properties"] for f in fc["features"]]
    assert len(props) == 15
    assembly = [p for p in props if p["parcel_role"] == "liames_assembly"]
    assert len(assembly) == 12 and {p["owner"] for p in assembly} == {"LIAMES LLC"}
    assert {p["parcel_role"] for p in props if p["parcel_role"] != "liames_assembly"} == {
        "rezoning_pending",
        "apollo_permit_situs",
        "oppidan_colo",
    }

    prov = fc["bosc:provenance"]
    assert prov["liames_cama_acres"] == 775.020
    assert prov["liames_union_planar_acres"] == 774.878  # ONE polygon, not a sum
    assert abs(prov["liames_planar_acres"] - prov["liames_union_planar_acres"]) < 0.01
    assert prov["liames_core_cama_acres"] == 753.65
    assert prov["liames_small_parcel_cama_acres"] == 21.37

    # The eight parcels whose zoning was still contestable are flagged, not folded in silently.
    contestable = [p for p in assembly if p["rezoning_contestable_2026_07_07"]]
    assert len(contestable) == 8
    assert round(sum(p["acres"] for p in contestable), 2) == 21.37

    # The traps that would have produced a wrong number are caveats, not rediscoveries.
    assert any("SUM OF THE TRANSFER PRICES IS NOT WHAT THE LAND COST" in c for c in prov["caveats"])
    assert any("PARCEL FABRIC MOVED" in c for c in prov["caveats"])
    assert any("`parcel_role`, NOT `role`" in c for c in prov["caveats"])
    assert any("THE WINDOW WAS STILL OPEN" in c and "2026-08-06" in c for c in prov["caveats"])
    assert any("LIMES" in c and "one letter" in c for c in prov["caveats"])
