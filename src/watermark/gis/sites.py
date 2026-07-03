"""Tracking sites — the imagery AOIs, sourced from the POI store.

A *tracking site* is a POI at depth ``watched`` (with ``track.enabled``): the single
source of truth for what gets imagery is the ``track`` flag in a ``data/entities/poi/<slug>.md``
profile, not a layer of ``gis-findings.geojson``. ``watermark.gis`` is a **consumer** of
``watermark.poi`` — this reads ``tracked_pois()`` and exposes each as a ``TrackingSite`` whose
``bbox`` is the AOI ``watermark imagery search``/``pull`` clips to. See
[`docs/poi-subsystem.md`](../../../docs/poi-subsystem.md) (decision #7).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.poi.model import POIProfile
from watermark.poi.store import load_poi, tracked_pois

log = get_logger(__name__)

Bbox = tuple[float, float, float, float]  # WGS84 (minx, miny, maxx, maxy)


class TrackingSite(BaseModel):
    """A named AOI to track over time — a watched POI projected for the imagery layer."""

    model_config = ConfigDict(extra="forbid")

    id: str  # the POI slug
    name: str
    bbox: Bbox  # WGS84 (minx, miny, maxx, maxy) — the tracking AOI
    parcels: list[str] = []  # the POI's anchor parcels (for reference)
    source: str  # the POI profile this came from

    def padded_bbox(self, pad_deg: float = 0.0) -> Bbox:
        """The site bbox grown by ``pad_deg`` degrees — a search envelope."""
        minx, miny, maxx, maxy = self.bbox
        return (minx - pad_deg, miny - pad_deg, maxx + pad_deg, maxy + pad_deg)


def _from_poi(poi: POIProfile, bbox: Bbox) -> TrackingSite:
    return TrackingSite(
        id=poi.slug,
        name=poi.name,
        bbox=bbox,
        parcels=list(poi.front.parcels),
        source=f"data/entities/poi/{poi.slug}.md",
    )


def load_tracking_sites(*, settings: Settings | None = None) -> list[TrackingSite]:
    """The tracking sites: every ``watched`` POI that carries a tracking ``bbox``.

    A watched POI with no ``location.bbox`` can't be tracked (no AOI) — it is skipped
    with a warning rather than silently dropped.
    """
    settings = settings or get_settings()
    sites: list[TrackingSite] = []
    for poi in tracked_pois(settings=settings):
        bbox = poi.bbox
        if bbox is None:
            log.warning("gis.watched_poi_without_bbox", slug=poi.slug)
            continue
        sites.append(_from_poi(poi, bbox))
    return sites


def get_site(site_id: str, *, settings: Settings | None = None) -> TrackingSite | None:
    """One tracking site by POI slug, or ``None`` if absent / not watched / no AOI."""
    settings = settings or get_settings()
    poi = load_poi(site_id, settings=settings)
    if poi is None or not poi.tracked:
        return None
    bbox = poi.bbox
    if bbox is None:
        return None
    return _from_poi(poi, bbox)
