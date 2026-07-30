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
from watermark.sites import (
    ALLEN_IN_PARCEL_SCHEMA,
    FORT_WAYNE_ZONING_SCHEMA,
    LIMA_FLOOD_SCHEMA,
    LIMA_PARCEL_SCHEMA,
    LIMA_ZONING_SCHEMA,
    LUCAS_AREIS_PARCEL_SCHEMA,
    LUCAS_ZONING_SCHEMA,
    MIAMI_PARCEL_SCHEMA,
    PER_SITE_OUTPUT_FIELDS,
    PUTNAM_PARCEL_SCHEMA,
    SITES,
    VAN_WERT_PARCEL_SCHEMA,
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
    campus's parcels/footprint, which would misattribute one campus's geometry to another; and a
    placeholder path that isn't committed on disk ships as null, not a phantom link (#1628 review)."""
    from watermark.config import Settings
    from watermark.site.facility import build_facility_feed

    feed = build_facility_feed(Settings(site="wilmington"))
    assert feed is not None and len(feed) == 2
    ardent = feed[1]
    assert not ardent.is_primary and ardent.name == "Ardent/TAC corridor"
    # Wilmington's site-level geometry is an [open] placeholder (not committed) → both rows null.
    assert ardent.parcels_relpath is None and ardent.footprint_relpath is None
    assert feed[0].parcels_relpath is None and feed[0].footprint_relpath is None
