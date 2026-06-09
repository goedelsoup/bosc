"""``bosc.poi`` — the point-of-interest (place) research store.

Places are the third curated entity type, peer to *person* (`bosc.people`) and *org*
(`data/entities/`): markdown + frontmatter under ``data/poi/<slug>.md``, cited and
**depth-marked** (`mention → located → characterized → watched`). The place-specific
enrichment is geometry (geocoding); a POI flagged ``watched`` feeds the imagery tracking
machinery (`bosc.gis`). Design + roadmap: [`docs/poi-subsystem.md`](../../../docs/poi-subsystem.md).

P0 is the store + model. The ``discover`` (corpus → candidates) and ``resolve``
(parcel-anchored dedup funnel + merge) layers, and the geocoding connectors, land in
later increments.
"""

from __future__ import annotations

from bosc.poi.model import POIFrontmatter, POIProfile
from bosc.poi.store import load_poi, load_pois, tracked_pois

__all__ = ["POIFrontmatter", "POIProfile", "load_poi", "load_pois", "tracked_pois"]
