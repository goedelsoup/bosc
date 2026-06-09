"""GIS tracking sites + satellite-imagery STAC search: offline fixture replay."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.gis import get_site, imagery, load_tracking_sites
from bosc.hydrology.connectors._cache import HydroOfflineError


def test_campus_site_loads(gis_settings: Settings) -> None:
    sites = load_tracking_sites(settings=gis_settings)
    assert [s.id for s in sites] == ["campus"]  # default gis_tracking_layers

    campus = sites[0]
    assert campus.name == "Data-center campus"
    assert campus.n_features == 10
    assert campus.geometry["type"] == "MultiPolygon"
    assert len(campus.geometry["coordinates"]) == 10
    assert campus.acreage is not None and campus.acreage > 300

    minx, miny, maxx, maxy = campus.bbox
    assert -84.13 < minx < maxx < -84.11  # the Bistrozzi campus, NW of Lima
    assert 40.78 < miny < maxy < 40.81


def test_get_site_unknown_is_none(gis_settings: Settings) -> None:
    assert get_site("not-a-site", settings=gis_settings) is None


def test_search_site_offline_parses_fixture(gis_settings: Settings) -> None:
    site, scenes = imagery.search_site(
        "campus",
        collection="sentinel-2-l2a",
        datetime_range="2024-06-01/2024-09-30",
        max_cloud=20.0,
        limit=5,
        settings=gis_settings,
    )
    assert site.id == "campus"
    assert len(scenes) == 5

    # Newest acquisition first.
    dates = [s.acquired for s in scenes]
    assert dates == sorted(dates, reverse=True)

    top = scenes[0]
    assert top.collection == "sentinel-2-l2a"
    assert top.scene_id.startswith("S2")
    assert top.platform is not None and "Sentinel-2" in top.platform
    assert top.cloud_cover is not None and top.cloud_cover < 20.0
    assert top.epsg in (32616, 32617)  # campus straddles the UTM 16N/17N seam
    assert top.asset("B04") is not None  # red-band COG href, selected by name
    assert top.preview_url is not None  # rendered_preview asset


def test_search_offline_miss_raises(gis_settings: Settings) -> None:
    # An AOI/date we have no committed fixture for must fail loudly, naming the key.
    with pytest.raises(HydroOfflineError):
        imagery.search_scenes(
            (-84.0, 40.0, -83.9, 40.1),
            collection="sentinel-2-l2a",
            settings=gis_settings,
        )
