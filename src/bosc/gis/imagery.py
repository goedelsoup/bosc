"""Satellite imagery search over a public STAC catalog (Microsoft Planetary Computer).

Given a tracking-site AOI, find the scenes that cover it. Planetary Computer's STAC
API (``settings.pc_stac_url``) fronts the free/open collections — ``sentinel-2-l2a``
(10 m, ~5-day), ``naip`` (0.3-0.6 m), ``landsat-c2-l2`` (30 m archive) — behind one
``/search`` endpoint that returns a GeoJSON ``FeatureCollection`` of STAC items.

This is the **search** layer only (P1 in [`docs/imagery-subsystem.md`](../../../docs/imagery-subsystem.md)).
It records, per scene, the acquisition date, cloud cover, platform, and the (unsigned)
COG asset hrefs — enough to choose scenes and, later, to materialize AOI-clipped
GeoTIFFs. The raster-read / asset-signing layer (rasterio + ``planetary-computer``
signing) is a separate increment and intentionally not pulled in here.

A plain ``httpx`` POST wrapped in the shared connector cache keeps it hermetic: the
search JSON caches and replays from a committed fixture exactly like every other
connector. Fields are read from the STAC response **by name**, never by index.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.gis.sites import TrackingSite, get_site
from bosc.hydrology.connectors._cache import cached_get

_CONNECTOR = "pc_stac_search"
_SOURCE = "Microsoft Planetary Computer STAC"

Bbox = tuple[float, float, float, float]


class Scene(BaseModel):
    """One STAC item covering an AOI: acquisition metadata + (unsigned) asset hrefs."""

    model_config = ConfigDict(extra="forbid")

    collection: str
    scene_id: str  # the STAC item id (re-pull the identical scene from the archive)
    acquired: str | None  # properties.datetime (sensing time, ISO 8601)
    platform: str | None
    cloud_cover: float | None  # eo:cloud_cover (percent)
    epsg: int | None  # proj:epsg (the scene's native CRS)
    bbox: list[float] | None
    assets: dict[str, str]  # asset key -> href (band COGs, preview, metadata)
    source: str = _SOURCE

    @property
    def preview_url(self) -> str | None:
        """The catalog's rendered RGB preview, when present (handy for a quick look)."""
        return self.assets.get("rendered_preview")

    def asset(self, name: str) -> str | None:
        """One asset href by its STAC key (e.g. ``B04``, ``visual``)."""
        return self.assets.get(name)


def _f(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def search_scenes(
    bbox: Bbox,
    *,
    collection: str | None = None,
    datetime_range: str | None = None,
    max_cloud: float | None = None,
    limit: int | None = None,
    settings: Settings | None = None,
) -> list[Scene]:
    """Scenes from one collection covering ``bbox``, newest first.

    ``datetime_range`` is a STAC interval (``"2024-01-01/2024-12-31"`` or open-ended
    ``"2024-01-01/.."``); ``max_cloud`` filters on ``eo:cloud_cover`` (percent). The
    search JSON is cached/fixtured through the shared connector machinery.
    """
    settings = settings or get_settings()
    collection = collection or settings.gis_default_collection
    limit = limit if limit is not None else settings.gis_search_limit
    bbox_q = [round(c, 6) for c in bbox]

    # The cache key captures every search input; the POST body is built inside fetch().
    params: dict[str, Any] = {
        "collection": collection,
        "bbox": bbox_q,
        "datetime": datetime_range,
        "max_cloud": max_cloud,
        "limit": limit,
    }

    def fetch() -> Any:
        body: dict[str, Any] = {"collections": [collection], "bbox": bbox_q, "limit": limit}
        if datetime_range:
            body["datetime"] = datetime_range
        if max_cloud is not None:
            body["query"] = {"eo:cloud_cover": {"lt": max_cloud}}
        resp = httpx.post(
            f"{settings.pc_stac_url}/search",
            json=body,
            timeout=settings.gis_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cast(
        "dict[str, Any]",
        cached_get(
            _CONNECTOR,
            params,
            fetch,
            settings=settings,
            cache_dir=settings.gis_cache_dir,
            offline=settings.gis_offline,
            fixtures_dir=settings.gis_fixtures_dir,
            ttl_hours=settings.gis_cache_ttl_hours,
        ),
    )
    return _parse(payload, requested_collection=collection)


def search_site(
    site_id: str,
    *,
    collection: str | None = None,
    datetime_range: str | None = None,
    max_cloud: float | None = None,
    limit: int | None = None,
    pad_deg: float = 0.0,
    settings: Settings | None = None,
) -> tuple[TrackingSite, list[Scene]]:
    """Resolve a tracking site, then search its (optionally padded) bbox.

    Raises ``KeyError`` if ``site_id`` is not a known trackable site.
    """
    settings = settings or get_settings()
    site = get_site(site_id, settings=settings)
    if site is None:
        raise KeyError(f"unknown tracking site: {site_id!r}")
    scenes = search_scenes(
        site.padded_bbox(pad_deg),
        collection=collection,
        datetime_range=datetime_range,
        max_cloud=max_cloud,
        limit=limit,
        settings=settings,
    )
    return site, scenes


def _parse(payload: dict[str, Any], *, requested_collection: str) -> list[Scene]:
    """Reduce a STAC ``FeatureCollection`` to ``Scene``s, newest acquisition first."""
    scenes: list[Scene] = []
    for item in payload.get("features") or []:
        props = item.get("properties") or {}
        assets = {
            key: asset["href"]
            for key, asset in (item.get("assets") or {}).items()
            if isinstance(asset, dict) and asset.get("href")
        }
        scenes.append(
            Scene(
                collection=str(item.get("collection") or requested_collection),
                scene_id=str(item.get("id")),
                acquired=props.get("datetime"),
                platform=props.get("platform"),
                cloud_cover=_f(props.get("eo:cloud_cover")),
                epsg=_i(props.get("proj:epsg")),
                bbox=item.get("bbox"),
                assets=assets,
            )
        )
    # Newest first; items with no datetime sort last (ISO strings sort chronologically).
    scenes.sort(key=lambda s: s.acquired or "", reverse=True)
    return scenes
