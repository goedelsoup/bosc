"""Corridor view: spatial join of BOSC facilities/parcels/roadwork to corridor geography.

Hermetic — reads only the committed frozen Periplus GeoJSON (study area + centerline +
watch items + parcels); no network, no reprojection beyond shapely+pyproj.
"""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.gis.corridor import build_corridor_view
from bosc.site import gismap


def test_corridor_view_joins_facilities(gis_settings: Settings) -> None:
    view = build_corridor_view(settings=gis_settings)

    # The study area + the roadwork centerline the roundabouts OPC prices.
    assert view.study_area_acres == pytest.approx(1321.7, abs=2.0)
    assert view.road_length_m == pytest.approx(5522.7, abs=10.0)
    assert any(r.role == "road" for r in view.routes)

    by_id = {m.id: m for m in view.members}
    assert by_id  # facilities + force mains + recorded parcels

    # The Lyka substation and the FM-2 terminus sit *inside* the corridor; the distant
    # county WWTPs do not — the join cleanly separates corridor-proximate from far.
    lyka = by_id["watch-lyka-substation"]
    assert lyka.in_study_area and lyka.distance_to_route_m < 100
    far = by_id["watch-american-ii-wwtp"]
    assert not far.in_study_area and far.distance_to_route_m > 5000

    # The force mains are classified as line features; a recorded campus parcel is in.
    assert by_id["bosc-fm2"].kind == "forcemain"
    assert by_id["36-0100-03-002.000"].kind == "parcel"
    assert by_id["36-0100-03-002.000"].in_study_area

    # in_corridor is exactly the in-study-area subset, and members sort it first.
    assert view.in_corridor == [m for m in view.members if m.in_study_area]
    assert view.members[0].in_study_area


def test_corridor_view_provenance(gis_settings: Settings) -> None:
    view = build_corridor_view(settings=gis_settings)
    # The corridor geometry is frozen external corroboration — cited, never claimed as
    # BOSC's own, and never edited in place.
    assert "periplus" in view.source.lower()
    assert "external corroboration" in view.source.lower()
    for m in view.members:
        assert "data/reference/periplus/" in m.source


def test_merge_corridor_layer_idempotent(gis_settings: Settings) -> None:
    fc: dict = {"type": "FeatureCollection", "features": []}
    fc, added = gismap.merge_corridor_layer(fc, settings=gis_settings)
    assert added == 2  # the study-area polygon + the road centerline

    layers = [f["properties"]["layer"] for f in fc["features"]]
    assert layers.count("corridor") == 1 and layers.count("roadwork") == 1
    assert all(f["properties"].get("label") for f in fc["features"])
    assert any("Periplus frozen corridor" in s for s in fc["meta"]["sources"])

    # Re-running drops the prior corridor/roadwork features first → no duplication.
    fc, added2 = gismap.merge_corridor_layer(fc, settings=gis_settings)
    assert added2 == 2
    layers = [f["properties"]["layer"] for f in fc["features"]]
    assert layers.count("corridor") == 1 and layers.count("roadwork") == 1
    assert sum(1 for s in fc["meta"]["sources"] if "Periplus frozen corridor" in s) == 1
