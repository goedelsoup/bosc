"""ECHO NPDES connector — fixture-backed (hermetic, no network).

Replays a committed Blanchard (HUC-8 04100008) ECHO response: 37 active-permit
facilities. Asserts the column-by-name mapping, POTW classification, dedup, and
the inventory-row shaping — none of which may fabricate values ECHO didn't send.
"""

from __future__ import annotations

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
    with pytest.raises(echo.EchoError, match="unknown basin"):
        echo.resolve_basin("muskingum")


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
    paths = echo.write_inventory([result], tmp_path)
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
