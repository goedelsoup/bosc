"""POI discover: corpus place-reference extraction + store-coverage flags."""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.hydrology.connectors.allen_gis import scan_parcel_ids
from bosc.pipeline.entities import build_entity_graph, normalize_name
from bosc.poi.connectors.gnis import GnisFeature
from bosc.poi.discover import _default_roots, discover_candidates
from bosc.poi.resolve import resolve_candidate


def test_discover_parcel_ids_and_coverage(poi_settings: Settings, tmp_path: Path) -> None:
    # One campus parcel (covered by the seed POI) and a fabricated one (not covered).
    (tmp_path / "doc.md").write_text(
        "Parcel 36-0100-03-002.000 was conveyed; cf. 99-9999-99-999.999 elsewhere.\n",
        encoding="utf-8",
    )
    cands = discover_candidates(roots=[tmp_path], settings=poi_settings)
    parcels = {c.normalized: c for c in cands if c.kind == "parcel-id"}

    assert set(parcels) == {"36010003002000", "99999999999999"}
    assert parcels["36010003002000"].covered is True  # a campus parcel, in the store
    assert parcels["99999999999999"].covered is False  # fabricated, not in the store
    assert any("doc.md" in cite for cite in parcels["36010003002000"].citations)


def test_discover_address_extraction(poi_settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "m.md").write_text("The plant at 2801 Centerville Road, Lima.\n", encoding="utf-8")
    cands = discover_candidates(roots=[tmp_path], settings=poi_settings)
    addrs = [c for c in cands if c.kind == "address"]

    assert any(c.normalized == "2801 CENTERVILLE ROAD" for c in addrs)
    assert all(not c.covered for c in addrs)  # only parcel-ids are coverage-checked


def test_discover_matches_scan_parcel_ids(poi_settings: Settings) -> None:
    # Divergence guard: discover's parcel set must equal allen_gis.scan_parcel_ids
    # over the same roots (the two parcel regexes mirror each other).
    roots = _default_roots(poi_settings)
    scan = set(scan_parcel_ids(*roots))
    disc = {c.value for c in discover_candidates(settings=poi_settings) if c.kind == "parcel-id"}
    assert disc == scan and scan  # same canonical parcel set, non-empty


def test_discover_corpus_marks_campus_covered(poi_settings: Settings) -> None:
    cands = discover_candidates(settings=poi_settings)
    by_norm = {c.normalized: c for c in cands if c.kind == "parcel-id"}

    # The campus parcels are cited in the corpus and covered by the seed composite POI…
    campus = by_norm.get("36010003002000")
    assert campus is not None and campus.covered is True
    # …and there is an uncovered worklist (other parcels cited but not yet POIs).
    assert any(not c.covered for c in by_norm.values())


def test_discover_facility_names(poi_settings: Settings) -> None:
    # The name pass surfaces corpus-verified facility/business names as `feature`
    # candidates (the GNIS-funnel kind), with citations and occurrence counts.
    feats = [c for c in discover_candidates(settings=poi_settings) if c.kind == "feature"]
    by_norm = {c.normalized: c for c in feats}

    assert feats  # the corridor corpus names facilities and businesses
    bath = by_norm.get("AMERICAN BATH WWTP")  # an NPDES facility (kind=facility)
    assert bath is not None and bath.value == "American Bath WWTP"
    assert bath.occurrences >= 1 and bath.citations
    assert "BISTROZZI" in by_norm  # the corridor LLC (kind=corporate)
    # None of these org/facility names is a curated POI yet → the whole set is a worklist.
    assert all(not c.covered for c in feats)


def test_discover_names_off_skips_features(poi_settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "d.md").write_text("Parcel 36-0100-03-002.000.\n", encoding="utf-8")
    cands = discover_candidates(roots=[tmp_path], settings=poi_settings, names=False)
    assert not any(c.kind == "feature" for c in cands)  # name pass disabled
    assert any(c.kind == "parcel-id" for c in cands)  # parcel/address passes still run


def test_facility_names_guarded_by_entity_graph(poi_settings: Settings) -> None:
    # Divergence guard (the name analog of discover↔scan_parcel_ids): every `feature`
    # candidate must resolve to a facility/corporate node the entity resolver produced —
    # the name pass can't invent a place the corpus didn't already name.
    graph = build_entity_graph(settings=poi_settings)
    allowed = {
        normalize_name(e.display)
        for e in graph.entities.values()
        if e.kind in ("facility", "corporate")
    }
    found = {
        c.normalized for c in discover_candidates(settings=poi_settings) if c.kind == "feature"
    }
    assert found and found <= allowed


def test_feature_candidate_flows_through_gnis_funnel(
    poi_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Acceptance: a discovered facility-name candidate flows through the resolve funnel's
    # GNIS branch (`_resolve_feature`), not the "unsupported kind" dead end.
    import bosc.poi.resolve as resolve_mod

    cand = next(c for c in discover_candidates(settings=poi_settings) if c.kind == "feature")

    # No GNIS hit → it still reached the feature branch (honest "no GNIS match", not a
    # generic unsupported-kind rejection).
    monkeypatch.setattr(resolve_mod, "find_feature", lambda *a, **k: None)
    miss = resolve_candidate(cand, settings=poi_settings)
    assert miss.method == "unresolved" and miss.note == "no GNIS match"

    # A GNIS hit → resolved as a non-parcel feature keyed by its stable gnis id.
    feat = GnisFeature(
        gnis_id=999,
        name=cand.value,
        feature_class="Locale",
        county="Allen",
        state="OH",
        lon=-84.1,
        lat=40.7,
    )
    monkeypatch.setattr(resolve_mod, "find_feature", lambda *a, **k: feat)
    hit = resolve_candidate(cand, settings=poi_settings)
    assert hit.method == "gnis" and hit.key == "gnis-999" and hit.parcel_no is None
