"""GIS tracking sites + satellite-imagery STAC search: offline fixture replay."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.gis import get_site, imagery, load_tracking_sites


def test_campus_site_loads(gis_settings: Settings) -> None:
    sites = load_tracking_sites(settings=gis_settings)
    assert [s.id for s in sites] == ["data-center-campus"]  # the watched POI

    campus = sites[0]
    assert campus.name == "Data-center campus"
    assert len(campus.parcels) == 10
    assert campus.source == "data/poi/data-center-campus.md"

    minx, miny, maxx, maxy = campus.bbox
    assert -84.13 < minx < maxx < -84.11  # the Bistrozzi campus, NW of Lima
    assert 40.78 < miny < maxy < 40.81


def test_get_site_unknown_is_none(gis_settings: Settings) -> None:
    assert get_site("not-a-site", settings=gis_settings) is None


def test_search_site_offline_parses_fixture(gis_settings: Settings) -> None:
    site, scenes = imagery.search_site(
        "data-center-campus",
        collection="sentinel-2-l2a",
        datetime_range="2024-06-01/2024-09-30",
        max_cloud=20.0,
        limit=5,
        settings=gis_settings,
    )
    assert site.id == "data-center-campus"
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
    with pytest.raises(imagery.ImageryOfflineError):
        imagery.search_scenes(
            (-84.0, 40.0, -83.9, 40.1),
            collection="sentinel-2-l2a",
            settings=gis_settings,
        )


def test_search_naip_offline(gis_settings: Settings) -> None:
    _site, scenes = imagery.search_site(
        "data-center-campus",
        collection="naip",
        datetime_range="2017-01-01/2023-12-31",
        limit=3,
        settings=gis_settings,
    )
    assert len(scenes) == 3
    top = scenes[0]
    assert top.collection == "naip"
    assert top.scene_id.startswith("oh_m_4008415_se_17_030_20230526")
    assert top.epsg == 26917  # NAD83 / UTM 17N — NAIP's native grid
    assert top.cloud_cover is None  # NAIP (aerial) carries no eo:cloud_cover
    assert top.asset("image") is not None  # the 4-band RGBN COG


def test_search_landsat_offline(gis_settings: Settings) -> None:
    _site, scenes = imagery.search_site(
        "data-center-campus",
        collection="landsat-c2-l2",
        datetime_range="2024-06-01/2024-09-30",
        max_cloud=20.0,
        limit=3,
        settings=gis_settings,
    )
    assert len(scenes) == 3
    dates = [s.acquired for s in scenes]
    assert dates == sorted(dates, reverse=True)  # newest first
    top = scenes[0]
    assert top.collection == "landsat-c2-l2"
    assert top.scene_id == "LC09_L2SP_020032_20240921_02_T1"
    assert top.platform == "landsat-9"
    assert top.cloud_cover is not None and top.cloud_cover < 20.0
    assert top.epsg == 32616
    assert top.asset("red") is not None  # per-band SR COG (no single 'visual' asset)
