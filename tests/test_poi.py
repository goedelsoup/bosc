"""POI store: load + validate the committed data/poi/ profiles, and the tracked view."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.poi import load_poi, load_pois, tracked_pois
from bosc.poi.model import POIFrontmatter
from bosc.poi.store import split_frontmatter


def test_store_loads_and_validates(poi_settings: Settings) -> None:
    pois = load_pois(settings=poi_settings)
    assert pois, "the committed data/poi/ store should not be empty"
    # Every committed profile validates (extra='forbid' + Literal depth/kind ladders).
    for p in pois:
        assert p.front.name
        assert p.front.depth in {"mention", "located", "characterized", "watched"}
        assert p.front.kind in {
            "parcel",
            "facility",
            "address",
            "feature",
            "jurisdiction",
            "composite",
        }
        assert p.front.citations, f"{p.slug} has no citations — not evidence"


def test_campus_composite_seed(poi_settings: Settings) -> None:
    campus = load_poi("data-center-campus", settings=poi_settings)
    assert campus is not None
    assert campus.kind == "composite"
    assert campus.depth == "watched"
    assert campus.tracked  # watched + track.enabled -> feeds imagery
    assert len(campus.front.parcels) == 10
    assert campus.bbox is not None
    minx, miny, maxx, maxy = campus.bbox
    assert -84.13 < minx < maxx < -84.11 and 40.78 < miny < maxy < 40.81
    assert campus.front.track is not None
    assert "sentinel-2-l2a" in campus.front.track.collections


def test_tracked_pois_view(poi_settings: Settings) -> None:
    tracked = tracked_pois(settings=poi_settings)
    # Every tracked POI is watched, track-enabled, and has an AOI to clip imagery to.
    assert tracked
    for p in tracked:
        assert p.depth == "watched" and p.bbox is not None
    assert "data-center-campus" in {p.slug for p in tracked}


def test_load_poi_unknown_is_none(poi_settings: Settings) -> None:
    assert load_poi("not-a-place", settings=poi_settings) is None


def test_frontmatter_extra_key_is_rejected() -> None:
    # extra='forbid' — a typo'd key must be a loud error, not a silent drop.
    with pytest.raises(ValueError):
        POIFrontmatter.model_validate({"name": "X", "kind": "parcel", "typoed_field": 1})


def test_split_frontmatter_requires_delimiters() -> None:
    header, body = split_frontmatter("---\nname: X\n---\nbody text\n")
    assert "name: X" in header and body == "body text"
    with pytest.raises(ValueError):
        split_frontmatter("no frontmatter here")
