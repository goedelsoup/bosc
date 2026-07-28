"""Ohio DNR water-well-log census connector — offline fixture replay (hermetic).

The groundwater peer of the surface-water supply model and the empirical basis for the
aquifer-parameter / well-drawdown thread. Everything here replays the committed Noble
County fixture (686 wells, one page); nothing touches the network. Noble — not Allen — is
the fixture county precisely so the committed test data stays minimal: the full 6,864-well
Allen census lives once, as the committed ``data/reference/ohio-waterwells/allen.csv``
reference dataset (regenerated online), never duplicated as a multi-page JSON fixture.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.connectors._cache import cache_key
from watermark.hydrology.connectors import ohio_waterwells as oww
from watermark.hydrology.connectors._cache import HydroOfflineError


def test_fetch_county_census(hydro_settings: Settings) -> None:
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    assert inv.county == "Noble"
    assert inv.state == "OH"
    assert inv.source_url.endswith("/MapServer/0")
    assert len(inv.wells) == 686
    # Wells come back OBJECTID-sorted (the census — and the CSV it writes — is deterministic).
    oids = [w.object_id for w in inv.wells]
    assert oids == sorted(oids)


def test_well_fields_verbatim(hydro_settings: Settings) -> None:
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    by = {w.object_id: w for w in inv.wells}

    w = by[3980]
    assert w.aquifer_type == "SHALE"
    assert w.total_depth_ft == 75.0
    assert w.static_water_level_ft == 11.0
    assert w.test_rate_gpm == 5.0
    assert w.township == "BUFFALO"
    assert w.county == "NOBLE"  # the service stores the county uppercase, verbatim
    # An epoch-ms COMPLETION_DATE is rendered as an ISO calendar date, not raw millis.
    assert w.completion_date == "1978-03-01"
    assert w.longitude is not None and w.latitude is not None


def test_missing_values_are_none_not_zero(hydro_settings: Settings) -> None:
    """A blank driller field is a genuine None — never a fabricated 0."""
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    dry = {w.object_id: w for w in inv.wells}[3979]  # a DRY/NO WATER log
    assert dry.well_use == "DRY/NO WATER"
    assert dry.aquifer_type is None
    assert dry.static_water_level_ft is None  # not 0.0
    assert dry.total_depth_ft == 100.0  # a present value still parses


def test_pii_columns_are_not_ingested() -> None:
    """Owner / name / street / house-number columns are deliberately omitted (private PII)."""
    for field in ("owner", "last_name", "streetname", "house_no", "street_name"):
        assert field not in oww.WaterWell.model_fields


def test_use_and_aquifer_counts_sorted(hydro_settings: Settings) -> None:
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    use = inv.use_counts()
    aquifer = inv.aquifer_counts()
    # Counts sum to the census and are ordered most-common first.
    assert sum(use.values()) == len(inv.wells)
    assert sum(aquifer.values()) == len(inv.wells)
    assert list(use.values()) == sorted(use.values(), reverse=True)
    assert use["DOMESTIC"] == 104


def test_layer_is_part_of_the_cache_key() -> None:
    """The layer id (URL path, not query string) stays in the cache key — collision-safe."""
    base = {
        "where": "COUNTY = 'NOBLE'",
        "outFields": "*",
        "resultOffset": 0,
        "resultRecordCount": 1000,
    }
    assert cache_key({"layer": 0, **base}) != cache_key({"layer": 1, **base})


def test_offline_unknown_county_raises(hydro_settings: Settings) -> None:
    # No committed fixture for a county nobody pulled -> an actionable offline miss.
    with pytest.raises(HydroOfflineError):
        oww.fetch_county("Cuyahoga", settings=hydro_settings)


def test_inventory_csv_is_deterministic_and_headed(hydro_settings: Settings) -> None:
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    first = oww.inventory_csv(inv)
    second = oww.inventory_csv(inv)
    assert first == second  # byte-stable (no timestamp)
    lines = first.splitlines()
    assert lines[0] == ",".join(oww._CSV_COLUMNS)
    assert len(lines) == len(inv.wells) + 1  # header + one row per well


def test_write_inventory_names_and_writes(hydro_settings: Settings, tmp_path) -> None:
    inv = oww.fetch_county("Noble", settings=hydro_settings)
    path = oww.write_inventory(inv, tmp_path)
    assert path.name == "noble.csv"
    assert path.read_text(encoding="utf-8") == oww.inventory_csv(inv)


def test_county_slug() -> None:
    assert oww.county_slug("Allen") == "allen"
    assert oww.county_slug("Allen County, OH") == "allen"
    assert oww.county_slug("Van Wert County, OH") == "van-wert"
