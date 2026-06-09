"""AOI-clipped GeoTIFF materialization — the imagery *pull* layer (P2).

Given a `Scene` (from `bosc.gis.imagery` search) and a `TrackingSite` AOI, read just
the window of one COG asset that covers the AOI and write a dated GeoTIFF plus a
provenance sidecar. Pixels are taken **as-is in the scene's native CRS** — a windowed
read + clip, never a resample — so the artifact is faithful evidence, and the recorded
``scene_id`` + unsigned ``source_url`` make it re-pullable from the authoritative
archive. Output lands under ``data/reference/imagery/<site>/<collection>/`` with a
``.yaml`` sidecar carrying the sensing date, retrieval timestamp, AOI, and sha256.

Reading a Planetary Computer COG needs a signed (SAS) asset URL — a network step — so
the materialization is **not** routed through the JSON connector cache. Instead, when
``settings.gis_offline`` is set the source resolves to a committed fixture COG under
``<gis_fixtures_dir>/imagery_cog/<scene_id>.<asset>.tif`` (tests stay hermetic); a miss
raises :class:`ImageryOfflineError` naming the key to record. ``rasterio``/GDAL handle
the COG windowed read; ``planetary_computer.sign`` is imported lazily on the live path.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import rasterio
import yaml
from pydantic import BaseModel, ConfigDict
from rasterio.warp import transform_bounds
from rasterio.windows import Window, from_bounds

from bosc.config import Settings, get_settings
from bosc.gis.imagery import Scene
from bosc.gis.sites import TrackingSite
from bosc.logging import get_logger

log = get_logger(__name__)

# Default asset (STAC key) to pull per collection — the human-viewable product.
_DEFAULT_ASSET = {
    "sentinel-2-l2a": "visual",  # true-colour RGB COG (3-band uint8)
    "landsat-c2-l2": "red",
    "naip": "image",
}


class ImageryOfflineError(RuntimeError):
    """Offline pull needs a fixture COG that is not committed (names the key)."""


class Capture(BaseModel):
    """A materialized AOI clip: where it lives + the provenance that makes it evidence."""

    model_config = ConfigDict(extra="forbid")

    site_id: str
    collection: str
    scene_id: str
    asset: str
    acquired: str | None  # sensing datetime (from the scene)
    retrieved_at: str  # when this clip was written
    epsg: int | None  # the scene's native CRS, preserved (no resampling)
    width: int
    height: int
    aoi_bbox: tuple[float, float, float, float]  # WGS84
    path: str
    sidecar: str
    sha256: str
    source: str  # "fixture COG (offline)" or "Microsoft Planetary Computer (signed)"
    source_url: str | None  # the unsigned asset href — re-pull the identical pixels


def default_asset(collection: str) -> str:
    """The default asset key to pull for a collection (falls back to ``visual``)."""
    return _DEFAULT_ASSET.get(collection, "visual")


def _resolve_source(scene: Scene, asset: str, settings: Settings) -> tuple[str, str]:
    """Return ``(readable_source, label)`` for a scene asset — fixture or signed URL."""
    if settings.gis_offline:
        if settings.gis_fixtures_dir is None:
            raise ImageryOfflineError(
                f"offline: no gis_fixtures_dir set to resolve {scene.scene_id} {asset!r}"
            )
        path = settings.gis_fixtures_dir / "imagery_cog" / f"{scene.scene_id}.{asset}.tif"
        if not path.is_file():
            raise ImageryOfflineError(
                f"offline: no fixture COG for scene={scene.scene_id} asset={asset!r}; "
                f"record one at {path}"
            )
        return str(path), "fixture COG (offline)"

    href = scene.asset(asset)
    if href is None:
        raise KeyError(f"scene {scene.scene_id} has no asset {asset!r}")
    import planetary_computer

    return str(planetary_computer.sign(href)), "Microsoft Planetary Computer (signed)"


def _aoi_window(dataset: Any, aoi_wgs84: tuple[float, float, float, float]) -> Window:
    """The integer pixel window of ``dataset`` covering the WGS84 AOI bbox.

    The AOI is reprojected into the dataset CRS, rounded **outward** to whole pixels,
    and clamped to the dataset extent so the read never runs off the raster.
    """
    minx, miny, maxx, maxy = aoi_wgs84
    left, bottom, right, top = transform_bounds("EPSG:4326", dataset.crs, minx, miny, maxx, maxy)
    win = from_bounds(left, bottom, right, top, transform=dataset.transform)
    col_off = max(0, math.floor(win.col_off))
    row_off = max(0, math.floor(win.row_off))
    col_end = min(dataset.width, math.ceil(win.col_off + win.width))
    row_end = min(dataset.height, math.ceil(win.row_off + win.height))
    if col_end <= col_off or row_end <= row_off:
        raise ValueError("AOI does not overlap the scene asset")
    return Window(col_off, row_off, col_end - col_off, row_end - row_off)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def pull_capture(
    scene: Scene,
    site: TrackingSite,
    *,
    asset: str | None = None,
    out_dir: Path | None = None,
    settings: Settings | None = None,
) -> Capture:
    """Clip one scene asset to the site AOI and write a dated GeoTIFF + provenance sidecar."""
    settings = settings or get_settings()
    asset = asset or default_asset(scene.collection)
    out_dir = out_dir if out_dir is not None else (settings.reference_dir / "imagery")

    src, label = _resolve_source(scene, asset, settings)
    with rasterio.open(src) as dataset:
        window = _aoi_window(dataset, site.bbox)
        data = dataset.read(window=window)
        profile = dataset.profile.copy()
        profile.update(
            driver="GTiff",
            height=int(window.height),
            width=int(window.width),
            transform=dataset.window_transform(window),
            compress="deflate",
            tiled=False,
        )
        profile.pop("blockxsize", None)
        profile.pop("blockysize", None)
        epsg = dataset.crs.to_epsg() if dataset.crs else None

    date = (scene.acquired or "unknown")[:10]
    dest = out_dir / site.id / scene.collection
    dest.mkdir(parents=True, exist_ok=True)
    tif_path = dest / f"{date}.{asset}.tif"
    with rasterio.open(tif_path, "w", **profile) as out:
        out.write(data)

    sidecar_path = dest / f"{tif_path.name}.yaml"
    capture = Capture(
        site_id=site.id,
        collection=scene.collection,
        scene_id=scene.scene_id,
        asset=asset,
        acquired=scene.acquired,
        retrieved_at=datetime.now(UTC).isoformat(),
        epsg=epsg,
        width=int(data.shape[-1]),
        height=int(data.shape[-2]),
        aoi_bbox=site.bbox,
        path=str(tif_path),
        sidecar=str(sidecar_path),
        sha256=_sha256(tif_path),
        source=label,
        source_url=scene.asset(asset),
    )
    _write_sidecar(capture, site, sidecar_path)
    log.info("imagery.pull", site=site.id, scene=scene.scene_id, asset=asset, path=str(tif_path))
    return capture


def _write_sidecar(capture: Capture, site: TrackingSite, path: Path) -> None:
    """Write the chain-of-custody sidecar beside the GeoTIFF."""
    doc = {
        "meta": {
            "subject": "AOI-clipped satellite capture",
            "site": {"id": site.id, "name": site.name},
            "collection": capture.collection,
            "scene_id": capture.scene_id,
            "asset": capture.asset,
            "acquired": capture.acquired,  # sensing time (authoritative date)
            "retrieved_at": capture.retrieved_at,  # when this clip was made
            "source": capture.source,
            "source_url": capture.source_url,  # unsigned href — re-pull the same pixels
            "crs": f"EPSG:{capture.epsg}" if capture.epsg else None,
            "width": capture.width,
            "height": capture.height,
            "aoi_bbox_wgs84": list(capture.aoi_bbox),
            "processing": "windowed read clipped to AOI bbox; native CRS, no resampling",
            "sha256": capture.sha256,
            "tool": "bosc imagery pull",
            "caveats": [
                "Pixels are verbatim from the source scene; the clip applies no "
                "radiometric or geometric correction beyond the windowed read.",
                "acquired is the sensing datetime; retrieved_at is the pull time — "
                "they are distinct on purpose (chain of custody).",
            ],
        }
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
