"""Allen County GIS parcel connector: ArcGIS parsing, date decode, offline replay."""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import allen_gis
from watermark.hydrology.connectors._cache import HydroOfflineError

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _fort_wayne_offline() -> Settings:
    return Settings(
        site="fort-wayne",
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


def test_fetch_parcel_from_fixture(hydro_settings: Settings) -> None:
    p = allen_gis.fetch_parcel("36-0100-03-001.000", settings=hydro_settings)
    assert p is not None
    assert p.parcel_no == "36010003001000"
    assert p.owner == "PATRICK DARLENE S TRUSTEE"
    assert p.situs_address == "N COLE ST"  # HOUSENO blank, dir+street+desc joined
    assert p.acres == pytest.approx(70.62)
    assert p.last_sale_date == "2020-12-21"  # decoded from the M(M)DDYYYY int
    # OWNADR2 already has city/state/zip — not duplicated.
    assert p.owner_address == "N COLE ST LIMA OH 45807"


def test_fetch_parcel_no_match_returns_none(hydro_settings: Settings) -> None:
    assert allen_gis.fetch_parcel("00-0000-00-000.000", settings=hydro_settings) is None


def test_normalize_parcel_id() -> None:
    assert allen_gis.normalize_parcel_id("36-0100-03-002.000") == "36010003002000"
    assert allen_gis.normalize_parcel_id("36010003002000") == "36010003002000"


def test_parse_parcel_date() -> None:
    assert allen_gis._parse_parcel_date(2252008) == "2008-02-25"  # M DD YYYY
    assert allen_gis._parse_parcel_date(8011994) == "1994-08-01"
    assert allen_gis._parse_parcel_date(12312020) == "2020-12-31"  # MM DD YYYY
    assert allen_gis._parse_parcel_date(0) is None
    assert allen_gis._parse_parcel_date(None) is None
    assert allen_gis._parse_parcel_date(99999999) is None  # invalid month/day


def test_scan_parcel_ids(tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "deed.yaml").write_text(
        "parcel_ids:\n  - 36-0100-03-002.000\n  - 46-1300-04-001.005\n"
        "legal_description: Part of 36-1200-02-001.001; not a parcel 12-3.\n",
        encoding="utf-8",
    )
    ids = allen_gis.scan_parcel_ids(tmp_path)
    assert ids == ["36-0100-03-002.000", "36-1200-02-001.001", "46-1300-04-001.005"]


def test_offline_unfetched_parcel_raises(hydro_settings: Settings) -> None:
    with pytest.raises(HydroOfflineError):
        allen_gis.fetch_parcel("99-9999-99-999.999", settings=hydro_settings)


def _seed_primes(settings: Settings) -> list[tuple[str, list[str]]]:
    from watermark.candidates import load_defense_contractors

    dcl = load_defense_contractors(settings.entities_dir)
    assert dcl is not None
    return [(d.name, d.patterns) for d in dcl.defense_contractors]


def test_defense_owner_scan_finds_no_prime_owner(hydro_settings: Settings) -> None:
    # No Allen County parcel is owned by a DoD prime in its own name — the local
    # defense footprint is federally held, not prime-owned.
    hits = allen_gis.defense_owner_scan(_seed_primes(hydro_settings), settings=hydro_settings)
    assert hits == {}


def test_army_controlled_defense_land(hydro_settings: Settings) -> None:
    parcels = allen_gis.army_controlled_defense_land(settings=hydro_settings)
    assert len(parcels) == 5  # the JSMC / Lima Army Tank Plant cluster (Buckeye/Reed)
    by_no = {p.parcel_no: p for p in parcels}
    tank_plant = by_no["46110004005000"]  # 1151 Buckeye Rd
    assert tank_plant.owner == "UNITED STATES"
    assert tank_plant.acres == pytest.approx(133.78)
    assert "BUCKEYE" in (tank_plant.situs_address or "")
    assert all(p.tax_district == "L35" for p in parcels)


def test_decode_land_use_modes() -> None:
    # leading_int parses the numeric code out of Ohio's "<code>: <label>" StateLUC strings;
    # int (Lima's path) is unchanged.
    assert allen_gis._decode_land_use("511: Res-Custom Code", "leading_int") == 511
    assert allen_gis._decode_land_use("110: Agr-CAUV-Vacant Land", "leading_int") == 110
    assert allen_gis._decode_land_use(None, "leading_int") is None
    assert allen_gis._decode_land_use("n/a", "leading_int") is None
    assert allen_gis._decode_land_use("340", "int") == 340  # Lima's bare-code path, unchanged


def test_parse_mmddyy() -> None:
    # MM-DD-YY (Putnam's SALEDATE) decoded with the standard %y century pivot: 69-99 -> 1900s,
    # 00-68 -> 2000s. Single-digit month/day tolerated; junk and missing -> None (never invented).
    assert allen_gis._parse_mmddyy("08-05-94") == "1994-08-05"
    assert allen_gis._parse_mmddyy("06-22-23") == "2023-06-22"
    assert allen_gis._parse_mmddyy("12-24-19") == "2019-12-24"
    assert allen_gis._parse_mmddyy("1-2-05") == "2005-01-02"
    assert allen_gis._parse_mmddyy("10-10-89") == "1989-10-10"  # 89 >= 69 -> 1900s
    assert allen_gis._parse_mmddyy(None) is None
    assert allen_gis._parse_mmddyy("") is None
    assert allen_gis._parse_mmddyy("2024-01-01") is None  # not MM-DD-YY
    assert allen_gis._parse_mmddyy("13-40-99") is None  # invalid month/day
    # Calendar-impossible dates are refused, not emitted: range-checking day <= 31 alone would
    # invent a conveyance date the county never recorded.
    assert allen_gis._parse_mmddyy("02-30-25") is None
    assert allen_gis._parse_mmddyy("02-29-25") is None  # 2025 is not a leap year
    assert allen_gis._parse_mmddyy("02-29-24") == "2024-02-29"  # 2024 is
    # The %y pivot runs BEFORE the calendar check, so 00 -> 2000, a leap year.
    assert allen_gis._parse_mmddyy("02-29-00") == "2000-02-29"


def test_parse_mdyyyy_slash() -> None:
    # M/D/YYYY with an optional trailing clock (Clinton County's Date_Conveyed, served as
    # pre-formatted TEXT rather than an esriFieldTypeDate). Four-digit year, so no century pivot
    # applies — unlike the mmddyy path above. The midnight clock is discarded, not parsed.
    assert allen_gis._parse_mdyyyy_slash("12/10/2025 12:00:00 AM") == "2025-12-10"
    assert allen_gis._parse_mdyyyy_slash("1/4/2001 12:00:00 AM") == "2001-01-04"
    assert allen_gis._parse_mdyyyy_slash("10/1/2008") == "2008-10-01"
    assert allen_gis._parse_mdyyyy_slash(None) is None
    assert allen_gis._parse_mdyyyy_slash("") is None
    assert allen_gis._parse_mdyyyy_slash("2025-12-10") is None  # already ISO -> not this encoding
    assert allen_gis._parse_mdyyyy_slash("13/40/2025") is None  # invalid month/day
    assert allen_gis._parse_mdyyyy_slash("12/10/25") is None  # two-digit year is NOT assumed
    # Calendar-impossible dates are refused, not emitted. A conveyance date is evidence: a parser
    # that range-checks day <= 31 happily returns "2025-02-30", a date that does not exist.
    assert allen_gis._parse_mdyyyy_slash("2/30/2025") is None
    assert allen_gis._parse_mdyyyy_slash("2/29/2025") is None  # 2025 is not a leap year
    assert allen_gis._parse_mdyyyy_slash("2/29/2024") == "2024-02-29"  # 2024 is
    assert allen_gis._parse_mdyyyy_slash("2/29/1900") is None  # 1900 is NOT (century rule)
    assert allen_gis._parse_mdyyyy_slash("2/29/2000") == "2000-02-29"  # 2000 IS (400-year rule)
    assert allen_gis._parse_mdyyyy_slash("4/31/2025") is None  # April has 30 days
    assert allen_gis._parse_mdyyyy_slash("12/10/1799") is None  # outside the plausibility bound
    # And it is reachable through the schema-driven decoder, not just directly.
    assert allen_gis._decode_sale_date("12/10/2025 12:00:00 AM", "mdyyyy_slash") == "2025-12-10"
    # The "iso" mode would have carried the whole string through — the bug this mode exists for.
    assert allen_gis._decode_sale_date("12/10/2025 12:00:00 AM", "iso") == "12/10/2025 12:00:00 AM"


def test_parcels_geojson_by_owner_fort_wayne() -> None:
    # The Hatchworks (Project Zodiac) assemblage as a WGS84 GeoJSON FeatureCollection, offline.
    fc = allen_gis.parcels_geojson_by_owner("Hatchworks", settings=_fort_wayne_offline())
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 11  # the assemblage as of the committed fixture

    by_id = {f["properties"]["parcel_id"]: f for f in fc["features"]}
    anchor = by_id["021327100001000077"]  # 6015 Adams Center Rd
    props = anchor["properties"]
    assert props["owner"] == "Hatchworks LLC"
    assert props["transfer_date"] == "2024-01-10"  # decoded from Esri epoch-millis
    assert "6015 Adams Center Rd" in (props["situs_address"] or "")
    assert anchor["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert anchor["geometry"]["coordinates"]  # geometry actually present

    # Properties are the friendly, schema-decoded keys — never the raw SDE field names.
    assert set(props) == {
        "parcel_id",
        "owner",
        "situs_address",
        "owner_mailing_address",
        "transfer_date",
    }
    assert all("GISPublished" not in k for f in fc["features"] for k in f["properties"])


def test_parse_epoch_millis() -> None:
    # Esri esriFieldTypeDate (ms since the Unix epoch, UTC) — Allen County, IN TransferDate.
    assert allen_gis._parse_epoch_millis(1704844800000) == "2024-01-10"  # Hatchworks anchor parcel
    assert allen_gis._parse_epoch_millis(1761868800000) == "2025-10-31"  # the 2025 assembly wave
    assert allen_gis._parse_epoch_millis(0) is None  # epoch 0 is the "no value" sentinel here
    assert allen_gis._parse_epoch_millis(None) is None
    assert allen_gis._parse_epoch_millis(-1) is None  # never a real transfer date


def test_decode_sale_date_epoch_millis_mode() -> None:
    # The schema-selected encoding routes TransferDate through the epoch-millis decoder.
    assert allen_gis._decode_sale_date(1704844800000, "epoch_millis") == "2024-01-10"
    assert allen_gis._decode_sale_date(None, "epoch_millis") is None


def test_putnam_parcel_full_cama(hydro_settings: Settings) -> None:
    """Ottawa's parcels come from Putnam County's self-hosted ArcGIS (#420) — a FULL fit (owner +
    auditor CAMA values on one layer, unlike Findlay's owner-redacted OGRIP substitute). Every
    attribute decodes by the schema's real field names: owner, the property situs (OWNERC/OWNERD),
    the owner's mailing address (MAILC/MAILD), the CLASS_1 land-use code, acreage, the auditor's
    land/building values, and the MM-DD-YY sale date. Replaying the committed fixture also proves
    the request hashes to the recorded cache key (the zero-drift guard)."""
    fs = hydro_settings.model_copy(update={"site": "ottawa"})
    p = allen_gis.fetch_parcel("010010200000", settings=fs)
    assert p is not None
    assert p.parcel_no == "010010200000"
    assert p.owner == "PATRICK HOLDINGS INC"
    assert p.situs_address == "RD I LEIPSIC OH  45856"  # OWNERC + OWNERD (the property location)
    assert p.owner_address == "100 S WERNER ST LEIPSIC OH  45856-0132"  # MAILC + MAILD (mailing)
    assert p.land_use_code == 110  # CLASS_1 (the populated Ohio use code; `Class` is 0/unused)
    assert p.acres == pytest.approx(81.04)
    assert p.market_land_value == 159114  # auditor's land value, verbatim
    assert p.market_improvement_value == 0
    assert p.market_total_value is None  # no combined-total field on this layer (never summed)
    assert p.last_sale_date == "1994-08-05"  # "08-05-94" decoded via the mmddyy pivot
    assert p.cauv_value is None and p.tax_district is None  # absent on this layer -> None


def test_findlay_statewide_parcel_partial(hydro_settings: Settings) -> None:
    """Findlay's parcels come from the OGRIP Ohio statewide layer (Hancock-scoped, #237): a
    partial, owner-redacted catalog. id/situs/land-use/acreage decode by field name; owner, value,
    and sale are honestly absent. Replaying the committed fixture also proves the scoped request
    (``... AND County='Hancock'``) hashes to the recorded cache key — the zero-drift guard."""
    fs = hydro_settings.model_copy(update={"site": "findlay"})
    p = allen_gis.fetch_parcel("010001025254", settings=fs)
    assert p is not None
    assert p.parcel_no == "010001025254"
    assert p.land_use_code == 511  # "511: Res-Custom Code" -> leading_int decode
    assert p.acres == pytest.approx(5.01)
    assert p.situs_address == "199  COUNTY RD 140   NORTH BALTIMORE 45872"
    assert p.owner is None  # owner-name-redacted in the public statewide view
    assert p.owner_address == "JOHNSON CHARLES W & JOY M NORTH BALTIMORE 45872"  # the mailing label
    assert p.market_total_value is None and p.last_sale_date is None  # fields absent in this layer


def test_bryan_statewide_parcel_verbatim_dashed_id(hydro_settings: Settings) -> None:
    """Bryan/Williams County, OH has no county parcel REST of its own (#410), so — like Findlay —
    parcels come from the OGRIP Ohio statewide layer scoped to County='Williams'. Williams' stored
    LocalParcelID is the DASHED ``NN-NNN-NN-NNN.NNN`` form (not Hancock's dashless 12 digits), so the
    site overrides ``id_normalize='verbatim'``: a fetch by the dashed id matches verbatim, and the
    scoped request (``... AND County='Williams'``) replays the committed fixture (the zero-drift
    guard). The ND ArcGIS the onboarding pass misidentified as "Williams County" is NOT used."""
    fs = hydro_settings.model_copy(update={"site": "bryan"})
    p = allen_gis.fetch_parcel("062-350-02-013.001", settings=fs)
    assert p is not None
    assert p.parcel_no == "062-350-02-013.001"  # dashed id, matched verbatim (not dash-stripped)
    assert p.land_use_code == 510  # "510: Res-Single Family" -> leading_int decode
    assert p.acres == pytest.approx(0.4)
    assert "BRYANT ST" in (p.situs_address or "")
    assert p.owner is None  # owner-name-redacted in the public statewide view
    assert "BRYAN 43506" in (p.owner_address or "")  # the mailing label carries the city/zip
    assert p.market_total_value is None and p.last_sale_date is None  # absent in this layer


def test_lucas_areis_parcel_owner_bearing(hydro_settings: Settings) -> None:
    """Toledo's parcels come from Lucas County AREIS layer 38 (#384) — the network's first
    owner-bearing parcel layer wired from a county's own REST. Owner, the situs (PROPERTY_ADDRESS)
    and owner mailing (MAILING_ADDRESS), the LUC land-use code, and the tax district all decode by
    field name; the appraised values are honestly null (they live on AREIS layer 83, a PARID join
    that's a tracked follow-up). Replaying the committed fixture is the zero-drift guard."""
    fs = hydro_settings.model_copy(update={"site": "toledo"})
    p = allen_gis.fetch_parcel("3850130", settings=fs)
    assert p is not None
    assert p.parcel_no == "3850130"
    assert p.owner == "CRESTRIVER LLC AN OHIO LIMITED LIABILITY"  # owner-bearing
    assert "WATERVILLE OH 43566" in (p.situs_address or "")  # PROPERTY_ADDRESS (situs)
    assert "PERRYSBURG OH 43551" in (p.owner_address or "")  # MAILING_ADDRESS (owner mailing)
    assert p.land_use_code == 550  # LUC bare numeric code
    assert p.tax_district == "38"
    assert p.market_total_value is None  # appraised values are on layer 83 (deferred PARID join)
    assert p.last_sale_date is None  # no sale field on the land-use-classification layer


def test_van_wert_parcel_agol_cama(hydro_settings: Settings) -> None:
    """Van Wert's parcels come from the county's ArcGIS Online auditor-CAMA join (#421) — the
    bhamaps PAT MapServer died with its expired cert and the county migrated to AGOL
    (parcel_joinedVWOH), Champaign's CCEO vendor pattern with different field semantics: the
    numeric Ohio use code is PPClassNumber (PPClassCode is the coarse class letter), there is no
    owner mailing-address field, and the dashed auditor form normalizes onto the dashless stored
    PIN. The fixture parcel is the QTS Mega Site anchor (VAN WERT EAST OWNER LLC, the 221-acre
    Marsh-tract split). Replaying the committed fixture is the zero-drift guard; the GIS returns
    the PIN as two split rows, so fetch_parcel's first-match also exercises the repeat behavior."""
    fs = hydro_settings.model_copy(update={"site": "van-wert"})
    p = allen_gis.fetch_parcel("17-034718.0100", settings=fs)  # dashed auditor form -> dashless PIN
    assert p is not None
    assert p.parcel_no == "170347180100"
    assert p.owner == "VAN WERT EAST OWNER LLC"  # the Mega Site anchor owner of record
    assert p.situs_address == "STRIPE RD"  # PPAddress: situs street only (no city token)
    assert p.owner_address is None  # NO owner mailing-address field on this layer
    assert p.land_use_code == 110  # PPClassNumber (agricultural); PPClassCode is the letter 'A'
    assert p.acres == pytest.approx(221.15)
    assert p.market_land_value == 2268170  # auditor's appraised values, verbatim
    assert p.market_improvement_value == 0
    assert p.market_total_value == 2268170
    assert p.last_sale_date == "2025-08-22"  # PPSaleDate epoch-millis -> ISO (the $10.394M sale)
    assert p.last_sale_amount == 10394000
    assert p.cauv_value is None  # PPOnCauv is a string flag, not a value — unmapped
    assert p.valid_sale is None  # PPSalesType is a conveyance-type code (WD) — unmapped
    assert p.tax_district is None  # encoded in the PIN's leading digits; no separate field


def test_owner_search_refuses_on_owner_redacted_layer(hydro_settings: Settings) -> None:
    """A parcel layer with no owner field refuses owner search cleanly (never a malformed query)."""
    fs = hydro_settings.model_copy(update={"site": "findlay"})
    with pytest.raises(allen_gis.AllenGisError, match="no owner-name field"):
        allen_gis.parcels_by_owner("JOHNSON", settings=fs)


def test_dedupe_keeps_first_per_parcel_no() -> None:
    a = allen_gis.Parcel.from_attrs({"PARCEL_NO": "1", "OWNNAM1": "A"})
    dup = allen_gis.Parcel.from_attrs({"PARCEL_NO": "1", "OWNNAM1": "A2"})
    b = allen_gis.Parcel.from_attrs({"PARCEL_NO": "2", "OWNNAM1": "B"})
    out = allen_gis._dedupe([a, dup, b])
    assert [p.parcel_no for p in out] == ["1", "2"]
    assert out[0].owner == "A"  # first row wins


def _bowling_green_offline() -> Settings:
    return Settings(
        site="bowling-green",
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
    )


def test_bowling_green_wood_county_parcel_decode() -> None:
    """Wood County's Vision CAMA through the new ``wood_gis`` field-map (#1436).

    Three encodings here are unlike every other wired jurisdiction and each of them is a way to
    read this layer wrong: the deeded owner lives in ``Deeded_Name`` while the column literally
    called ``Deeded_Owner`` is empty on every row; there is NO total-value column, so
    ``market_total_value`` is null by construction and a reader has to add the two halves; and
    ``Prc_Ttl_Apprais_Lnd_Alt``, whose name suggests an alternate appraisal, is the CAUV land
    value — 0 meaning NOT ENROLLED rather than unvalued.
    """
    p = allen_gis.fetch_parcel("611190000003500", settings=_bowling_green_offline())
    assert p is not None
    assert p.parcel_no == "611190000003500"
    assert p.owner == "LIAMES LLC"
    assert p.deeded_owner == "LIAMES LLC"  # Deeded_Name, not the empty Deeded_Owner column
    assert p.situs_address == "0 MERCER"  # number + street NAME; no street type, no city token
    # The tax roll bills the nominee entity at Meta's own headquarters (served "MENLOW PARK").
    assert p.owner_address == "1 META WAY MENLOW PARK CA 94025"
    assert p.land_use_code == 101  # Ohio CAMA cash-grain/general farm, served as the STRING "101"
    assert p.acres == pytest.approx(322.5)
    assert p.market_land_value == 2836700
    assert p.market_improvement_value == 181600
    assert p.market_total_value is None  # the layer publishes no total column
    assert p.cauv_value == 0  # Prc_Ttl_Apprais_Lnd_Alt: 0 = not enrolled, NOT unvalued
    assert p.tax_district == "J36"  # Middleton Twp
    assert p.last_sale_date == "2025-04-09"  # esriFieldTypeDate epoch-millis -> ISO
    assert p.last_sale_amount == 0  # the consolidation quitclaim, not a purchase
    assert p.valid_sale == "Q"


def test_bowling_green_parcel_id_normalizes_without_the_district_prefix() -> None:
    """The auditor PRINTS ``J36-611-190000003500``; the layer STORES the 15-digit remainder.

    ``dashless`` maps the printed id minus its district prefix onto the stored one, which is why
    ``deed_id_regex`` starts at the ``611-``. Feeding the full printed form through would keep the
    ``36`` of ``J36`` and produce a 17-digit string that matches nothing — the failure this
    convention exists to avoid, pinned here so a later "fix" to the regex has to face it.
    """
    assert allen_gis.normalize_parcel_id("611-190000003500") == "611190000003500"
    assert allen_gis.normalize_parcel_id("611190000003500") == "611190000003500"
    assert allen_gis.normalize_parcel_id("J36-611-190000003500") == "36611190000003500"


def test_bowling_green_assemblage_geojson_is_one_row_per_polygon_part() -> None:
    """The layer serves one row per polygon PART, not per parcel — and both fixes are wrong.

    Fifteen parcels come back as SIXTEEN features because the A. Schaller tract is served as two
    rows. They are not duplicates: the parts are disjoint and the pair sums to the deeded acreage.
    Deduping on ``parcel_id`` drops 25 of that parcel's 64 acres; summing ``Land_Acres`` over the
    raw rows double-counts, because the acreage is the whole parcel's repeated on each part.
    """
    fc = allen_gis.query_parcels_geojson(
        "Name IN ('611190000003500','611190000029510','611300000001000','611300000002000',"
        "'611190000037000','611190000033000','611190000036001','611190000034000',"
        "'611190000008000','611190000035000','611190000009000','611190000025000',"
        "'611190000006000','611200000011000','511210000002003')",
        settings=_bowling_green_offline(),
    )
    ids = [f["properties"]["parcel_id"] for f in fc["features"]]
    assert len(ids) == 16 and len(set(ids)) == 15
    assert ids.count("611190000006000") == 2  # the Schaller tract, in two disjoint parts

    liames = {
        f["properties"]["parcel_id"]
        for f in fc["features"]
        if f["properties"]["owner"] == "LIAMES LLC"
    }
    assert len(liames) == 12
    # The three rows that are NOT the campus, each a different kind of claim.
    others = {
        f["properties"]["parcel_id"]: f["properties"]["owner"]
        for f in fc["features"]
        if f["properties"]["owner"] != "LIAMES LLC"
    }
    assert others["611190000006000"] == "A SCHALLER LIMITED PARTNERSHIP"  # rezoning pending
    assert others["611200000011000"] == "JJJ FAMILY PROPERTIES LLC"  # the Apollo air-permit situs
    assert others["511210000002003"] == "CLOP BOWLING GREEN OH LLC"  # the Oppidan colo, 4.83 mi off


def test_bowling_green_two_operators_are_invisible_to_an_owner_search() -> None:
    """Two dated negatives, and they mean different things — neither means "no land".

    ``WILL-POWER`` returns nothing because Will-Power OH, LLC really does hold no Wood County
    land: the 350 MW behind-the-meter Apollo plant sits on a parcel still deeded to JJJ Family
    Properties LLC. ``OPPIDAN`` returns nothing because the colo's owner of record is an SPE named
    CLOP BOWLING GREEN OH LLC — the thing that identifies it is its mailing address, Oppidan's own
    headquarters at 400 Water St Suite 200, Excelsior MN. An owner-name search is the wrong
    instrument for a company that buys through a shell, which is the general case here.

    And both are statements about JULY 2025: this layer's newest conveyance anywhere in the county
    is 2025-07-25, so an empty result can never rule out a later acquisition.
    """
    bg = _bowling_green_offline()
    assert allen_gis.parcels_by_owner("WILL-POWER", settings=bg) == []
    assert allen_gis.parcels_by_owner("OPPIDAN", settings=bg) == []
    clop = allen_gis.parcels_by_owner("CLOP BOWLING GREEN", settings=bg)
    assert [p.parcel_no for p in clop] == ["511210000002003"]
    assert clop[0].owner_address == "400 WATER ST SUITE 200 EXCELSIOR MN 55331"
    assert clop[0].acres == pytest.approx(11.8)
    assert clop[0].last_sale_date == "2025-02-03"
    assert clop[0].last_sale_amount == 1_105_000
