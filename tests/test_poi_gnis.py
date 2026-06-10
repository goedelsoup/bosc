"""POI GNIS: non-parcel feature resolution + geohash fallback + merge by fallback key."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.connectors import OfflineError
from bosc.poi.connectors.gnis import find_feature
from bosc.poi.merge import Item, merge_resolutions
from bosc.poi.model import POICandidate
from bosc.poi.resolve import Resolution, _geohash, resolve_value


def test_geohash_is_deterministic() -> None:
    h = _geohash(40.7969, -84.1234)
    assert h == "dpk0jdz5n"  # a real geohash of the campus-ish point
    assert _geohash(40.7969, -84.1234) == h  # stable
    assert _geohash(0.0, 0.0) != h  # different point, different hash


def test_find_feature_offline(poi_offline_settings: Settings) -> None:
    feat = find_feature("Ottawa River", settings=poi_offline_settings)
    assert feat is not None
    assert feat.gnis_id == 1070882  # the stable GNIS identity
    assert feat.feature_class == "Stream"
    assert feat.state == "OH"
    assert feat.key == "gnis-1070882"
    assert -85 < feat.lon < -83 and 40 < feat.lat < 42  # NW Ohio


def test_resolve_feature_offline(poi_offline_settings: Settings) -> None:
    r = resolve_value("feature", "Ottawa River", settings=poi_offline_settings)
    assert r.method == "gnis"
    assert r.confidence == "medium" and r.auto_mergeable is False  # a proposal, never auto
    assert r.parcel_no is None  # a feature has no parcel
    assert r.fallback_key == "gnis-1070882"
    assert r.key == "gnis-1070882"  # the blocking key falls back to the GNIS id
    assert r.point is not None


def test_gnis_offline_miss_raises(poi_offline_settings: Settings) -> None:
    with pytest.raises(OfflineError):
        find_feature("Nonexistent Creek", settings=poi_offline_settings)


def test_merge_blocks_feature_by_fallback_key(poi_settings: Settings) -> None:
    def cand(kind: str, value: str) -> POICandidate:
        return POICandidate(
            kind=kind, value=value, normalized=value.upper(), occurrences=1, citations=["x"]
        )

    def res(
        kind: str, value: str, parcel_no: str | None, fallback: str | None, auto: bool
    ) -> Resolution:
        return Resolution(
            kind=kind,
            value=value,
            method="gnis" if kind == "feature" else "parcel-id",
            confidence="medium",
            parcel_no=parcel_no,
            parcel=None,
            point=None,
            matched_address=None,
            auto_mergeable=auto,
            fallback_key=fallback,
        )

    items: list[Item] = [
        # two surface forms of the same GNIS feature → one 'review' group keyed by gnis id
        (
            cand("feature", "Ottawa River"),
            res("feature", "Ottawa River", None, "gnis-1070882", False),
        ),
        (cand("feature", "the Ottawa"), res("feature", "the Ottawa", None, "gnis-1070882", False)),
        # a campus parcel (in the store) → its own 'covered' group
        (
            cand("parcel-id", "36-0100-03-002.000"),
            res("parcel-id", "x", "36010003002000", None, True),
        ),
    ]
    groups = merge_resolutions(items, settings=poi_settings)
    by_key = {g.key: g for g in groups}

    feature = by_key["gnis-1070882"]
    assert feature.status == "review" and feature.has_exact_id is False
    assert feature.parcel_no is None
    assert len(feature.members) == 2  # the two forms merged on the GNIS key

    assert by_key["36010003002000"].status == "covered"
