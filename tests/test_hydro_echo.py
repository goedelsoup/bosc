"""ECHO NPDES connector — fixture-backed (hermetic, no network).

Replays a committed Blanchard (HUC-8 04100008) ECHO response: 37 active-permit
facilities. Asserts the column-by-name mapping, POTW classification, dedup, and
the inventory-row shaping — none of which may fabricate values ECHO didn't send.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology.connectors import echo
from watermark.hydrology.connectors._cache import HydroOfflineError


def test_maumee_is_seven_subbasins() -> None:
    assert list(echo.MAUMEE_HUC8S) == [
        "04100003",
        "04100004",
        "04100005",
        "04100006",
        "04100007",
        "04100008",
        "04100009",
    ]
    # Adjacent Western Lake Erie subbasins must NOT be present.
    for excluded in ("04100001", "04100002", "04100010"):
        assert excluded not in echo.MAUMEE_HUC8S


def test_basin_registry_and_resolve() -> None:
    assert echo.resolve_basin("maumee") is echo.MAUMEE
    assert echo.resolve_basin("great-miami") is echo.GREAT_MIAMI
    assert echo.resolve_basin("little-miami") is echo.LITTLE_MIAMI
    assert echo.resolve_basin("scioto") is echo.SCIOTO
    assert echo.resolve_basin(echo.GREAT_MIAMI) is echo.GREAT_MIAMI  # idempotent
    # The Great Miami is the two Ohio HUC-8s; Whitewater (mostly IN) is excluded.
    assert list(echo.GREAT_MIAMI_HUC8S) == ["05080001", "05080002"]
    assert "05080003" not in echo.GREAT_MIAMI_HUC8S
    # The Little Miami is a single HUC-8 (Xenia + Wilmington/Todd Fork); Mill Creek excluded.
    assert list(echo.LITTLE_MIAMI_HUC8S) == ["05090202"]
    assert "05090203" not in echo.LITTLE_MIAMI_HUC8S
    assert echo.LITTLE_MIAMI.file_stem == "little-miami-wwtp"
    # The Scioto is its three HUC-8s (Upper/Lower Scioto + Paint).
    assert list(echo.SCIOTO_HUC8S) == ["05060001", "05060002", "05060003"]
    assert echo.SCIOTO.file_stem == "scioto-wwtp"
    # Ohio Brush Creek (#1120) is the single direct-to-Ohio HUC-8. Pinned here because nothing
    # else fails on a typo: `basin._inventory_path` falls back to `<basin>-wwtp.potw.yaml` and a
    # missing file screens an empty set, so a wrong slug/HUC-8/file_stem would silently revert
    # west-union's basin screen to 0/0 rather than raise.
    assert echo.resolve_basin("ohio-brush-creek") is echo.OHIO_BRUSH_CREEK
    assert list(echo.OHIO_BRUSH_CREEK_HUC8S) == ["05090201"]
    assert echo.OHIO_BRUSH_CREEK.file_stem == "ohio-brush-creek-wwtp"
    # The Muskingum is all six HUC-8s of subregion 0504, enumerated from the USGS WBD service.
    # Pinned for the same reason as Ohio Brush Creek above — a typo reverts mansfield's and
    # coshocton's screen to 0/0 silently.
    assert echo.resolve_basin("muskingum") is echo.MUSKINGUM
    assert list(echo.MUSKINGUM_HUC8S) == [
        "05040001",
        "05040002",
        "05040003",
        "05040004",
        "05040005",
        "05040006",
    ]
    assert echo.MUSKINGUM.file_stem == "muskingum-wwtp"
    # The Sandusky is the single WLE HUC-8 that is neither Maumee nor Portage drainage.
    assert echo.resolve_basin("sandusky") is echo.SANDUSKY
    assert list(echo.SANDUSKY_HUC8S) == ["04100011"]
    assert echo.SANDUSKY.file_stem == "sandusky-wwtp"
    assert "04100011" not in echo.MAUMEE_HUC8S and "04100011" not in echo.PORTAGE_HUC8S
    # An unregistered basin must RAISE rather than fall through to an empty screen.
    # ⚠️ Use a synthetic slug, never a real Ohio basin: this assertion previously named
    # "muskingum", which quietly became wrong the moment that basin was registered. Any real
    # name here is a landmine armed for whoever onboards a site in it next.
    with pytest.raises(echo.EchoError, match="unknown basin"):
        echo.resolve_basin("not-a-registered-basin")


def test_huc8_names_cover_every_registered_basin() -> None:
    # The per-HUC display label is DERIVED from the registry, not a second hand-kept copy: an
    # omitted subbasin would not raise, it would write the raw HUC code into the committed
    # huc-counts.yaml `name:` field (`_HUC8_NAMES.get(huc8, huc8)`).
    for basin in echo.BASINS.values():
        for huc8, name in basin.huc8s.items():
            assert echo._HUC8_NAMES[huc8] == name


def test_basin_caveats_carry_no_pull_specific_counts() -> None:
    # Caveats are re-stamped verbatim into every regenerated file, so a count typed into one is
    # republished as current by the next quarterly pull. Dated headline counts belong in
    # data/reference/echo/README.md, under the pull date that produced them.
    for basin in echo.BASINS.values():
        for caveat in basin.caveats:
            assert not re.search(r"\d+\s+of\s+\d+", caveat), (basin.slug, caveat)


def test_fetch_blanchard_from_fixture(hydro_settings: Settings) -> None:
    result = echo.fetch_huc_facilities("04100008", settings=hydro_settings)
    assert result.huc8 == "04100008"
    assert result.name == "Blanchard"
    assert result.reported_count == 37
    # Every reported facility was actually pulled (no pagination loss).
    assert len(result.facilities) == 37

    by_name = {f.name: f for f in result.facilities}
    bluffton = by_name["BLUFFTON WWTP"]
    assert bluffton.is_potw
    assert bluffton.npdes_id == "OH0020851"
    assert bluffton.design_flow_mgd == pytest.approx(1.9)
    assert bluffton.huc8 == "04100008"  # FacDerivedHuc, not the null RadWBDHu8

    # A non-POTW industrial user must not be misclassified as a POTW.
    blue_beacon = by_name["BLUE BEACON INTL"]
    assert not blue_beacon.is_potw
    assert blue_beacon.facility_type == "NON-POTW"


def test_stale_low_reported_does_not_truncate(
    hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ECHO's QueryRows (`reported`) is a summary stat that can be stale-low. It must
    # never terminate pagination early: only a short/empty page ends the pull (#1157).
    page_size = 2
    rows_by_page = {1: 2, 2: 2, 3: 1}  # two full pages then a short page: 5 rows total

    def fake_get(settings: Settings, service: str, params: dict[str, object]) -> dict[str, object]:
        if service == "get_facilities":
            return {"QueryID": "QID-STALE", "QueryRows": 2}  # stale-low: claims only 2
        n = rows_by_page.get(int(params["pageno"]), 0)  # type: ignore[call-overload]
        return {
            "Facilities": [
                {"CWPName": f"F{params['pageno']}-{i}", "RegistryID": f"{params['pageno']}{i}"}
                for i in range(n)
            ]
        }

    monkeypatch.setattr(echo, "_get", fake_get)
    result = echo.fetch_huc_facilities("04100008", page_size=page_size, settings=hydro_settings)

    assert result.reported_count == 2  # the stale stat is recorded verbatim...
    assert len(result.facilities) == 5  # ...but every row is pulled, not truncated at 2


def test_offline_cache_miss_raises(hydro_settings: Settings) -> None:
    # A HUC with no committed fixture (and never queried) -> offline miss must be
    # loud, not silent. 00000000 is deliberately not a real Maumee subbasin.
    with pytest.raises(HydroOfflineError):
        echo.fetch_huc_facilities("00000000", settings=hydro_settings)


def test_deduplicate_keys_on_frs_and_keeps_distinct_names() -> None:
    a = echo.Facility(
        name="PLANT A",
        frs_registry_id="111",
        npdes_id="OH0000001",
        npdes_ids_all="OH0000001",
        facility_type="POTW",
        facility_type_code=None,
        permit_type=None,
        design_flow_mgd=2.0,
        receiving_water=None,
        huc8="04100008",
        huc12=None,
        latitude=None,
        longitude=None,
        county=None,
        federal_agency=None,
        compliance_status=None,
        informal_enf_count=None,
        formal_enf_count=None,
        queried_huc8="04100008",
    )
    # Same FRS, a second outfall permit -> collapses, secondary permit retained.
    a2 = a.model_copy(update={"npdes_id": "OH0000002", "npdes_ids_all": "OH0000002"})
    # Different FRS, same name -> must stay distinct.
    b = a.model_copy(update={"frs_registry_id": "222"})

    deduped = echo.deduplicate(
        [
            echo.HucResult(
                huc8="04100008",
                name="Blanchard",
                query_id="1",
                reported_count=3,
                stats={},
                facilities=[a, a2, b],
            )
        ]
    )
    assert len(deduped) == 2
    primary = next(f for f in deduped if f.frs_registry_id == "111")
    assert "OH0000002" in echo._secondary_npdes(primary)


def test_facility_record_null_is_none() -> None:
    fac = echo.Facility(
        name="NO FLOW PLANT",
        frs_registry_id="999",
        npdes_id="MIG000001",
        npdes_ids_all="MIG000001",
        facility_type="POTW",
        facility_type_code=None,
        permit_type="General Permit Covered Facility",
        design_flow_mgd=None,
        receiving_water=None,
        huc8="04100008",
        huc12=None,
        latitude=None,
        longitude=None,
        county=None,
        federal_agency=None,
        compliance_status=None,
        informal_enf_count=None,
        formal_enf_count=None,
        queried_huc8="04100008",
    )
    rec = echo.facility_record(fac)
    assert rec["design_flow_mgd"] is None  # genuine ECHO null, never 0/estimated
    assert rec["design_flow_missing"] is True
    assert rec["in_lima_subbasin"] is True  # Blanchard is a Lima-area subbasin


def test_facility_record_basin_aware() -> None:
    # A Great Miami record carries the basin's HUC-8 names and omits the Maumee/Lima flags.
    fac = echo.Facility(
        name="CITY OF SPRINGFIELD WWTP",
        frs_registry_id="100",
        npdes_id="OH0027481",
        npdes_ids_all="OH0027481",
        facility_type="POTW",
        facility_type_code=None,
        permit_type="NPDES Individual Permit",
        design_flow_mgd=25.0,
        receiving_water=None,
        huc8="05080001",
        huc12=None,
        latitude=None,
        longitude=None,
        county="CLARK",
        federal_agency=None,
        compliance_status=None,
        informal_enf_count=None,
        formal_enf_count=None,
        queried_huc8="05080001",
    )
    rec = echo.facility_record(fac, basin=echo.GREAT_MIAMI)
    assert rec["huc8_name"] == "Upper Great Miami"
    assert "in_lima_subbasin" not in rec  # a Maumee/Lima concept; absent for other basins
    assert "ottawa_discharge" not in rec


def test_write_inventory_yaml_round_trips(hydro_settings: Settings, tmp_path: Path) -> None:
    result = echo.fetch_huc_facilities("04100008", settings=hydro_settings)
    # A Blanchard-only pull: the Maumee's curated corrections all sit in the Auglaize
    # (04100007), so they're out of scope here and the write proceeds untouched (#1698).
    paths = echo.write_inventory([result], tmp_path, settings=hydro_settings)
    assert {p.suffix for p in paths.values()} == {".yaml"}

    all_doc = yaml.safe_load(paths["all"].read_text())
    assert all_doc["meta"]["dedup_key"] == "FRS RegistryID"
    assert all_doc["meta"]["count"] == len(all_doc["facilities"]) == 37
    bluffton = next(f for f in all_doc["facilities"] if f["name"] == "BLUFFTON WWTP")
    assert bluffton["ownership"] == "POTW"
    assert bluffton["design_flow_mgd"] == pytest.approx(1.9)

    potw_doc = yaml.safe_load(paths["potw"].read_text())
    assert potw_doc["facilities"]  # non-empty
    assert all(f["facility_type"] == "POTW" for f in potw_doc["facilities"])

    counts = yaml.safe_load(paths["counts"].read_text())
    assert counts["totals"]["raw"] == 37
