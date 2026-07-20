"""Tests for the EPA RSEI per-county reduction (`watermark rsei`).

The current release (v2.3.12, #1148) ships as a single zip of per-table CSVs; the
connector streams each table straight out of it. These tests build a tiny v2312-format
archive in the (offline) cache and also read a committed real Allen County slice.
"""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from watermark import rsei
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "rsei" / "RSEIv2312_Public_Release_Data.zip"


def _write_archive(settings: Settings, tables: dict[str, list[dict[str, object]]]) -> None:
    """Write a v2312-format RSEI archive (per-table CSV members) into the offline cache."""
    path = rsei.archive_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, rows in tables.items():
            member = f"{rsei._ARCHIVE_TABLE[name]}_data_rsei_{settings.rsei_version}.csv"
            buf = io.StringIO(newline="")
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
            zf.writestr(member, buf.getvalue().encode("latin-1"))


def _seed_tables(settings: Settings) -> None:
    """Write a tiny self-consistent RSEI table set (v2312 schema) into the cache zip."""
    _write_archive(
        settings,
        {
            "media": [
                {"Media": "1", "MediaCode": "1"},  # air
                {"Media": "3", "MediaCode": "3"},  # direct water
            ],
            "chemical": [
                {
                    "ChemicalNumber": "100",
                    "Chemical": "Nickel and nickel compounds",
                    "CASStandard": "7440-02-0",
                    "ToxicityCategory": "Carcinogen",
                },
                {
                    "ChemicalNumber": "200",
                    "Chemical": "Toluene",
                    "CASStandard": "108-88-3",
                    "ToxicityCategory": "Non-carcinogen",
                },
            ],
            # v2312 facility carries no NPDESPermit / SIC1 columns — codes are NAICS-only.
            "facility": [
                {
                    "FacilityID": "ACME1",
                    "FacilityNumber": "1",
                    "FacilityName": "ACME FORGE",
                    "ParentName": "ACME CORP",
                    "FederalFacilityFlag": "",
                    "Latitude": "40.7",
                    "Longitude": "-84.1",
                    "Street": "1 MAIN ST",
                    "City": "LIMA",
                    "State": "OH",
                    "FIPS": "39003",
                    "NAICS1": "331110",
                    "WaterReleases": "1",
                },
                {
                    "FacilityID": "OTHER",
                    "FacilityNumber": "2",
                    "FacilityName": "OUT OF COUNTY",
                    "ParentName": "X",
                    "FederalFacilityFlag": "",
                    "Latitude": "0",
                    "Longitude": "0",
                    "Street": "",
                    "City": "",
                    "State": "OH",
                    "FIPS": "39999",
                    "NAICS1": "0",
                    "WaterReleases": "0",
                },
            ],
            "submission": [
                {
                    "SubmissionNumber": "S1",
                    "FacilityNumber": "1",
                    "ChemicalNumber": "100",
                    "SubmissionYear": "2000",
                },
                {
                    "SubmissionNumber": "S2",
                    "FacilityNumber": "1",
                    "ChemicalNumber": "200",
                    "SubmissionYear": "2001",
                },
                {
                    "SubmissionNumber": "S9",
                    "FacilityNumber": "2",
                    "ChemicalNumber": "100",
                    "SubmissionYear": "2000",
                },
            ],
            "release": [
                {
                    "ReleaseNumber": "R1",
                    "SubmissionNumber": "S1",
                    "Media": "1",
                    "PoundsReleased": "100",
                },
                {
                    "ReleaseNumber": "R2",
                    "SubmissionNumber": "S2",
                    "Media": "3",
                    "PoundsReleased": "50",
                },  # reported pounds, no modeled element
                {
                    "ReleaseNumber": "R9",
                    "SubmissionNumber": "S9",
                    "Media": "1",
                    "PoundsReleased": "999",
                },
            ],
            "elements": [
                {
                    "ElementNumber": "1",
                    "ReleaseNumber": "R1",
                    "Score": "1000",
                    "CScore": "900",
                    "NCScore": "100",
                    "Hazard": "5000",
                },
                {
                    "ElementNumber": "2",
                    "ReleaseNumber": "R9",
                    "Score": "777",
                    "CScore": "777",
                    "NCScore": "0",
                    "Hazard": "1234",
                },  # out-of-county; must be dropped
            ],
        },
    )


def test_build_inventory_joins_and_rolls_up(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data", rsei_offline=True)
    _seed_tables(settings)

    inv = rsei.build_inventory(settings)

    # Only the in-county facility survives.
    assert inv.county_fips == "39003"
    assert [f.facility_number for f in inv.facilities] == ["1"]
    f = inv.facilities[0]

    # Pounds sum across both releases; Score only from the modeled element.
    assert f.pounds == 150.0
    assert f.score == 1000.0
    assert f.cancer_score == 900.0
    assert f.noncancer_score == 100.0
    assert f.hazard == 5000.0

    # Media split + provenance fields.
    assert f.pounds_by_media == {"air": 100.0, "water": 50.0}
    assert f.naics == "331110"  # NAICS1, not the "0" out-of-county code
    # v2312 dropped NPDESPermit / SIC1 from the facility table — both are None now.
    assert f.npdes_permit is None
    assert f.sic is None
    assert f.water_releases is True

    # Per-year series spans both report years.
    assert [y.year for y in f.years] == [2000, 2001]
    assert {y.year: y.pounds for y in f.years} == {2000: 100.0, 2001: 50.0}

    # Top chemical is the modeled (scored) Nickel, ahead of unscored Toluene.
    assert f.top_chemicals[0].chemical.startswith("Nickel")
    assert f.top_chemicals[0].toxicity_category == "Carcinogen"

    assert inv.meta["scored_facility_count"] == 1
    assert inv.meta["version"] == "v2312"


def test_committed_v2312_fixture_parses(tmp_path: Path) -> None:
    """The committed real v2.3.12 Allen County slice parses through the archive path."""
    settings = Settings(data_dir=tmp_path / "data", rsei_offline=True)
    # Pre-warm the cache with the committed fixture (a real, FIPS-39003-filtered slice).
    dest = rsei.archive_path(settings)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(FIXTURE.read_bytes())

    inv = rsei.build_inventory(settings, fips="39003", county_name="Allen County, OH")

    assert inv.county_fips == "39003"
    assert inv.facilities, "fixture produced no facilities"
    # Real v2312 columns parsed: ranked descending by Score, at least one modeled facility.
    scores = [f.score for f in inv.facilities]
    assert scores == sorted(scores, reverse=True)
    assert any(f.score > 0 for f in inv.facilities)
    # The JSMC / GDLS defense footprint is in the slice and scored.
    gdls = next((f for f in inv.facilities if "GENERAL DYNAMICS" in f.name.upper()), None)
    assert gdls is not None and gdls.score > 0


def test_committed_inventory_loads() -> None:
    """The committed Allen County inventory loads and has the expected shape."""
    inv = rsei.load_inventory(Settings())
    assert inv is not None, "data/reference/rsei/inventory.yaml is missing"
    assert inv.county_fips == "39003"
    assert len(inv.facilities) >= 40
    # Ranked descending by Score.
    scores = [f.score for f in inv.facilities]
    assert scores == sorted(scores, reverse=True)
    # The JSMC / GDLS defense footprint is present and scored.
    gdls = next((f for f in inv.facilities if "GENERAL DYNAMICS" in f.name.upper()), None)
    assert gdls is not None and gdls.score > 0
    assert gdls.parent_name is not None and gdls.parent_name.startswith("GENERAL DYNAMICS")


def test_water_chemical_breakdown_reconciles(tmp_path: Path) -> None:
    """`top_water_chemicals` (media-3 per chemical) sums to `pounds_by_media['water']` (#1607).

    And it surfaces the actual top *water* pollutant (ammonia at INEOS), which the all-media
    `top_chemicals` ranking (dominated by underground injection) omits entirely.
    """
    settings = Settings(data_dir=tmp_path / "data", rsei_offline=True)
    dest = rsei.archive_path(settings)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(FIXTURE.read_bytes())
    inv = rsei.build_inventory(settings, fips="39003", county_name="Allen County, OH")

    releasers = [f for f in inv.facilities if f.top_water_chemicals]
    assert releasers, "no facility carried a per-chemical water breakdown"
    for fac in releasers:
        water_total = round((fac.pounds_by_media or {}).get("water", 0.0), 1)
        chem_sum = round(sum(w.water_pounds for w in fac.top_water_chemicals), 1)
        assert abs(chem_sum - water_total) < 0.5, f"{fac.name}: {chem_sum} != {water_total}"
        # Ranked descending by water pounds; every entry positive with >=1 reporting year.
        pounds = [w.water_pounds for w in fac.top_water_chemicals]
        assert pounds == sorted(pounds, reverse=True)
        assert all(w.water_pounds > 0 and w.reporting_years >= 1 for w in fac.top_water_chemicals)

    ineos = next(f for f in inv.facilities if "INEOS" in f.name)
    # The top water chemical is ammonia — NOT INEOS's top-by-score chemical (cobalt/acrylonitrile,
    # which are underground/air-driven and carry ~0 water pounds).
    assert ineos.top_water_chemicals[0].cas == "7664-41-7"
    assert "Ammonia" in ineos.top_water_chemicals[0].chemical
    assert ineos.top_chemicals[0].cas != "7664-41-7"
