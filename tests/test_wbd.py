"""USGS WBD connector + the committed watershed boundaries (issue #61).

Hermetic: the connector replays the recorded WBD responses from
``tests/fixtures/hydrology/wbd/`` (offline), and the committed reference GeoJSON under
``data/reference/hydrology/wbd/`` is checked for shape + provenance. No network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.gis.sites import get_site
from watermark.hydrology.connectors import wbd
from watermark.hydrology.connectors._cache import HydroOfflineError

REPO_ROOT = Path(__file__).resolve().parents[1]
WBD_DIR = REPO_ROOT / "data" / "reference" / "hydrology" / "wbd"


def _campus_centroid(settings: Settings) -> tuple[float, float]:
    """The data-center campus AOI centroid — the point the fixtures were recorded at."""
    site = get_site("data-center-campus", settings=settings)
    assert site is not None, "the data-center-campus tracking site must exist"
    minx, miny, maxx, maxy = site.bbox
    return (minx + maxx) / 2.0, (miny + maxy) / 2.0


def test_fetch_huc12_is_pike_run(hydro_settings: Settings) -> None:
    lon, lat = _campus_centroid(hydro_settings)
    hu = wbd.fetch_huc_at_point(lon, lat, level=12, settings=hydro_settings)
    assert hu is not None
    assert hu.huc == "041000070404"
    assert hu.name == "Pike Run"
    assert hu.level == 12
    assert hu.hu_label == "Subwatershed"
    assert hu.to_huc == "041000070406"
    assert hu.geometry["type"] in ("Polygon", "MultiPolygon")


def test_fetch_huc10_is_middle_ottawa_river(hydro_settings: Settings) -> None:
    lon, lat = _campus_centroid(hydro_settings)
    hu = wbd.fetch_huc_at_point(lon, lat, level=10, settings=hydro_settings)
    assert hu is not None
    assert hu.huc == "0410000704"
    assert hu.name == "Middle Ottawa River"
    assert hu.level == 10


def test_watershed_chain_is_finest_first(hydro_settings: Settings) -> None:
    lon, lat = _campus_centroid(hydro_settings)
    chain = wbd.watershed_chain(lon, lat, settings=hydro_settings)
    assert [hu.level for hu in chain] == [12, 10]
    assert chain[0].name == "Pike Run"


def test_unsupported_level_raises(hydro_settings: Settings) -> None:
    with pytest.raises(ValueError, match="unsupported HU level"):
        wbd.fetch_huc_at_point(-84.12, 40.79, level=6, settings=hydro_settings)


def test_offline_miss_raises_actionably(hydro_settings: Settings) -> None:
    """An unrecorded point must raise (naming the key to record), never fabricate a unit."""
    with pytest.raises(HydroOfflineError):
        wbd.fetch_huc_at_point(-83.0, 40.0, level=12, settings=hydro_settings)


def test_committed_boundaries_are_valid_and_provenanced() -> None:
    files = {p.name for p in WBD_DIR.glob("*.geojson")}
    assert files == {
        "041000070404-pike-run.geojson",
        "0410000704-middle-ottawa-river.geojson",
    }
    for path in sorted(WBD_DIR.glob("*.geojson")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["type"] == "FeatureCollection"
        assert len(doc["features"]) == 1
        meta = doc["meta"]
        assert "USGS" in meta["source"]
        assert meta["crs"].startswith("WGS84")
        feat = doc["features"][0]
        assert feat["properties"]["huc"] == meta["huc"]
        assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")


# --- boundary-tie disambiguation (WS-25 / #1625) ---------------------------------

_LEFT = [[[0.0, 0.0], [0.0, 10.0], [10.0, 10.0], [10.0, 0.0], [0.0, 0.0]]]
_RIGHT = [[[10.0, 0.0], [10.0, 10.0], [20.0, 10.0], [20.0, 0.0], [10.0, 0.0]]]


def _feat(rings: list[list[list[float]]], *, multi: bool = False) -> dict[str, object]:
    geom = (
        {"type": "MultiPolygon", "coordinates": [rings]}
        if multi
        else {"type": "Polygon", "coordinates": rings}
    )
    return {"geometry": geom, "properties": {"huc": "x"}}


def test_geometry_contains_polygon_and_multipolygon() -> None:
    assert wbd._geometry_contains(_feat(_LEFT)["geometry"], 5.0, 5.0) is True
    assert wbd._geometry_contains(_feat(_LEFT)["geometry"], 15.0, 5.0) is False
    # MultiPolygon: the same square wrapped one level deeper.
    assert wbd._geometry_contains(_feat(_RIGHT, multi=True)["geometry"], 15.0, 5.0) is True
    # A hole punched in the exterior excludes an interior point.
    holed = {"type": "Polygon", "coordinates": [_LEFT[0], [[4, 4], [4, 6], [6, 6], [6, 4], [4, 4]]]}
    assert wbd._geometry_contains(holed, 5.0, 5.0) is False  # inside the hole
    assert wbd._geometry_contains(holed, 1.0, 1.0) is True  # inside exterior, outside hole


def test_select_boundary_feature_prefers_container_not_first() -> None:
    """A point in the LEFT unit must pick LEFT even when RIGHT is returned first (WS-25)."""
    features = [_feat(_RIGHT), _feat(_LEFT)]
    chosen = wbd._select_boundary_feature(features, 5.0, 5.0)
    assert chosen is features[1]  # the containing polygon, not features[0]


def test_select_boundary_feature_falls_back_to_first() -> None:
    """No polygon contains the point (exact edge / offshore) -> keep features[0], never fabricate."""
    features = [_feat(_LEFT), _feat(_RIGHT)]
    assert wbd._select_boundary_feature(features, 50.0, 50.0) is features[0]
    # A single feature is returned untouched (the common case; committed outputs unchanged).
    assert wbd._select_boundary_feature([features[0]], 500.0, 500.0) is features[0]
