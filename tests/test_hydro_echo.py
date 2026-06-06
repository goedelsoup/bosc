"""ECHO NPDES connector — fixture-backed (hermetic, no network).

Replays a committed Blanchard (HUC-8 04100008) ECHO response: 37 active-permit
facilities. Asserts the column-by-name mapping, POTW classification, dedup, and
the inventory-row shaping — none of which may fabricate values ECHO didn't send.
"""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.hydrology.connectors import echo
from bosc.hydrology.connectors._cache import HydroOfflineError


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


def test_facility_row_blank_is_genuine_null() -> None:
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
    row = echo.facility_row(fac)
    assert row["design_flow_mgd"] == ""  # blank, not 0 — ECHO returned nothing
    assert row["design_flow_missing"] == "Y"
    assert row["in_lima_subbasin"] == "Y"  # Blanchard is a Lima-area subbasin
