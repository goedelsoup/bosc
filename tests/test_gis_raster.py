"""GIS imagery pull (raster clip): offline fixture-COG replay + provenance sidecar."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import rasterio
import yaml

from bosc.config import Settings
from bosc.gis import imagery, raster
from bosc.gis.sites import TrackingSite


def _campus_scenes(settings: Settings) -> tuple[TrackingSite, list[imagery.Scene]]:
    return imagery.search_site(
        "campus",
        collection="sentinel-2-l2a",
        datetime_range="2024-06-01/2024-09-30",
        max_cloud=20.0,
        limit=5,
        settings=settings,
    )


def test_pull_capture_offline_clips_to_aoi(gis_settings: Settings, tmp_path: Path) -> None:
    site, scenes = _campus_scenes(gis_settings)
    top = scenes[0]  # newest, T17TKF (EPSG 32617) — the one we have a fixture COG for
    assert top.scene_id.endswith("T17TKF_20240920T204040")

    cap = raster.pull_capture(top, site, asset="visual", out_dir=tmp_path, settings=gis_settings)

    # Capture metadata.
    assert cap.collection == "sentinel-2-l2a"
    assert cap.asset == "visual"
    assert cap.epsg == 32617  # native CRS preserved, no reprojection
    assert cap.acquired is not None and cap.acquired.startswith("2024-09-20")
    assert cap.source_url is not None  # unsigned href recorded for re-pull

    # The GeoTIFF exists, is a real 3-band raster, and is an interior clip of the
    # 144x275 padded fixture (i.e. clipping to the exact AOI actually happened).
    tif = Path(cap.path)
    assert tif.is_file() and tif.parent == tmp_path / "campus" / "sentinel-2-l2a"
    assert 0 < cap.width < 144 and 0 < cap.height < 275
    with rasterio.open(tif) as ds:
        assert ds.count == 3 and ds.crs.to_epsg() == 32617
        assert (ds.width, ds.height) == (cap.width, cap.height)

    # sha256 is self-consistent with the bytes on disk.
    assert hashlib.sha256(tif.read_bytes()).hexdigest() == cap.sha256

    # Provenance sidecar.
    sidecar = Path(cap.sidecar)
    assert sidecar.is_file()
    meta = yaml.safe_load(sidecar.read_text())["meta"]
    assert meta["scene_id"] == cap.scene_id
    assert meta["sha256"] == cap.sha256
    assert meta["crs"] == "EPSG:32617"
    assert meta["acquired"] != meta["retrieved_at"]  # sensing vs. pull, kept distinct
    assert meta["source_url"] == cap.source_url


def test_pull_offline_missing_fixture_raises(gis_settings: Settings, tmp_path: Path) -> None:
    _site, scenes = _campus_scenes(gis_settings)
    # The T16TGL scene (other UTM zone) has no committed fixture COG → fail loudly.
    other = next(s for s in scenes if s.scene_id.endswith("T16TGL_20240920T204040"))
    with pytest.raises(raster.ImageryOfflineError):
        raster.pull_capture(other, _site, asset="visual", out_dir=tmp_path, settings=gis_settings)
