"""Geospatial subsystem: tracking sites + satellite imagery for the corpus.

`bosc.gis` turns the AOIs already mapped in ``data/site/gis-findings.geojson`` (the
data-center campus parcels, the JSMC reservation, WWTP receivers) into **tracking
sites**, and pulls free/open satellite imagery clipped to each site over time. The
design is in [`docs/imagery-subsystem.md`](../../../docs/imagery-subsystem.md).

Two layers:

* :mod:`bosc.gis.sites` — load tracking-site AOIs from the committed GeoJSON.
* :mod:`bosc.gis.imagery` — search a public STAC catalog (Microsoft Planetary
  Computer) for the scenes covering a site; the raster-clip / GeoTIFF-materialization
  layer (rasterio + asset signing) lands in a later increment.

Imagery search reuses the shared connector cache machinery
(``bosc.connectors.cached_get``) against a GIS-specific cache root — the same neutral
layer the ``civic`` and ``economics`` connectors use — so tests stay hermetic against
committed fixtures. An offline miss raises ``ImageryOfflineError``.
"""

from __future__ import annotations

from bosc.gis.sites import TrackingSite, get_site, load_tracking_sites

__all__ = ["TrackingSite", "get_site", "load_tracking_sites"]
