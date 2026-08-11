"""GIS findings geojson + RSEI-layer-merge tests for the watermark.site data layer."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bundle_feeds_are_per_site_not_lima_bound() -> None:
    """#762: a non-Lima bundle must carry its OWN data, not Lima's. Fort Wayne's campus geo and
    RSEI inventory are the first two leaks fixed — guard them so they can't silently regress."""
    from watermark.config import Settings
    from watermark.rsei import load_inventory
    from watermark.site.gismap import campus_from_parcels

    fw = Settings(site="fort-wayne", data_dir=REPO_ROOT / "data")
    lima = Settings(site="lima", data_dir=REPO_ROOT / "data")

    # geo/campus: built from the active site's parcel assemblage (not the frozen Lima findings).
    fw_campus = campus_from_parcels(fw)
    assert fw_campus is not None and fw_campus.feed == "campus"
    grantees = {f.properties.model_dump().get("grantee") for f in fw_campus.features}
    assert grantees == {"Hatchworks LLC"}  # the Project Zodiac assemblage, not "Bistrozzi LLC"

    # rsei: the active site's committed inventory (FW = Allen County, IN), not Lima's (Allen Co, OH).
    assert load_inventory(fw).county_fips == "18003"  # type: ignore[union-attr]
    assert load_inventory(lima).county_fips == "39003"  # type: ignore[union-attr]


def test_relpath_in_scope_matches_path_segments() -> None:
    """#762: a corpus prefix matches a path segment — a slug collection or a jurisdiction+site
    subtree — but never a partial name."""
    from watermark.pipeline.corpus import relpath_in_scope

    scope = ("fort-wayne", "idem/fort-wayne")
    assert relpath_in_scope("fort-wayne/footprint.yaml", scope)
    assert relpath_in_scope("idem/fort-wayne/wqc.yaml", scope)
    assert not relpath_in_scope("recorder/deed.yaml", scope)  # a Lima collection
    assert not relpath_in_scope("fort-wayne-foo/x.yaml", scope)  # not a segment match
    # None = the whole tree (Lima, the reference build that owns the un-slugged collections).
    assert relpath_in_scope("recorder/deed.yaml", None)


def test_corpus_feeds_are_site_scoped_not_lima_bound() -> None:
    """#762 (the structural fix): the extracted-tree feeds (records/timeline/entities) read only
    the active site's collections. Fort Wayne must not inherit Lima's deeds/permits/filings; Lima,
    the reference build, still reads the whole tree (its `corpus_relpaths` is None)."""
    from watermark.config import Settings
    from watermark.pipeline.corpus import load_corpus
    from watermark.site.records import load_records
    from watermark.sites import active_profile, effective_corpus_scope

    fw = Settings(site="fort-wayne", data_dir=REPO_ROOT / "data")
    lima = Settings(site="lima", data_dir=REPO_ROOT / "data")

    # The cross-document corpus (timeline/entities/relationships derive from this): every Fort
    # Wayne artifact sits under its own scope — no Lima recorder/oepa/commissioners records.
    fw_corpus = load_corpus(fw)
    fw_rels = fw_corpus.rel_paths()
    assert fw_rels, "expected Fort Wayne to have at least one in-scope extraction"
    bad_rels = [
        r for r in fw_rels if not (r.startswith("fort-wayne/") or r.startswith("idem/fort-wayne/"))
    ]
    assert not bad_rels, f"out-of-scope rels in Fort Wayne corpus: {bad_rels}"

    # Lima (scope None) keeps reading the whole tree — strictly larger than Fort Wayne's slice.
    assert len(load_corpus(lima)) > len(fw_corpus)

    # The `records` feed reads the extracted tree separately; it honors the same scope. Resolve it
    # through `effective_corpus_scope`, never off the raw `corpus_relpaths` field: since #1405 the
    # field carries only the prefixes no rule can derive (a case/project name), so reading it
    # directly would hand a peer `None` — i.e. Lima's whole tree — which is the bug this guards.
    fw_records = load_records(fw.extracted_dir, scope=effective_corpus_scope(active_profile(fw)))
    assert fw_records, "expected Fort Wayne to have at least one in-scope record"
    bad_records = [
        r.rel
        for r in fw_records
        if not (r.rel.startswith("fort-wayne/") or r.rel.startswith("idem/fort-wayne/"))
    ]
    assert not bad_records, f"out-of-scope records in Fort Wayne slice: {bad_records}"


def test_site_scoped_path_is_flat_for_lima_subdir_for_others() -> None:
    """#762: a curated store is flat for Lima (the reference build) and under a `<slug>/` subdir
    for every other site — a directory gets the slug appended; a file gets it before the name."""
    from watermark.sites import site_scoped_path

    d = Path("/data/poi")
    assert site_scoped_path(d, "lima", is_dir=True) == d
    assert site_scoped_path(d, "fort-wayne", is_dir=True) == d / "fort-wayne"
    f = Path("/data/site/exhibits.yaml")
    assert site_scoped_path(f, "lima", is_dir=False) == f
    assert site_scoped_path(f, "fort-wayne", is_dir=False) == Path(
        "/data/site/fort-wayne/exhibits.yaml"
    )


def test_curated_stores_are_per_site_not_lima_bound() -> None:
    """#762: the curated stores (people, POIs) and the meetings feed read the active site's OWN
    copy — Fort Wayne carries its own places/people, never Lima's. (POI scoping also fixes the
    imagery feed, which derives its tracking sites from watched POIs.)"""
    from watermark.civic.summarize import load_committed_summaries
    from watermark.config import Settings
    from watermark.people import load_people
    from watermark.poi.store import load_pois
    from watermark.sites import active_profile, effective_corpus_scope, site_scoped_path

    fw = Settings(site="fort-wayne", data_dir=REPO_ROOT / "data")
    lima = Settings(site="lima", data_dir=REPO_ROOT / "data")
    fw_scope = effective_corpus_scope(active_profile(fw))  # resolved, not the raw field (#1405)

    # POIs (places + imagery tracking): FW reads data/entities/poi/fort-wayne/ — its own campus, not Lima's.
    fw_poi_slugs = {p.slug for p in load_pois(settings=fw)}
    assert "project-zodiac-campus" in fw_poi_slugs  # the FW Hatchworks assemblage
    assert "data-center-campus" not in fw_poi_slugs  # NOT Lima's Bistrozzi campus
    assert load_pois(settings=lima)  # Lima still reads its flat POI store

    # People: same slug-subdir convention — FW carries its own named actors, not Lima's.
    fw_people = load_people(site_scoped_path(fw.people_dir, "fort-wayne", is_dir=True))
    fw_person_names = {p.name for p in fw_people}
    assert "Marc Stern" in fw_person_names  # the FW §401 applicant
    assert "Amanda Davis" not in fw_person_names  # NOT a Lima actor
    assert load_people(site_scoped_path(lima.people_dir, "lima", is_dir=True))

    # Meetings: extracted-tree scope → FW has no in-scope bodies; Lima reads all.
    assert load_committed_summaries(fw, scope=fw_scope) == []
    assert load_committed_summaries(lima, scope=None)


def test_export_documents_honors_site_scope(tmp_path: Path) -> None:
    """#762: a non-Lima site's document catalog carries only its own in-scope source docs; a
    collection left with no in-scope entry is dropped. Lima (scope=None) keeps the whole tree."""
    from watermark.site.documents import export_documents

    docs = tmp_path / "documents"
    (docs / "recorder").mkdir(parents=True)  # a Lima collection
    (docs / "recorder" / "deed.pdf").write_bytes(b"%PDF-1.4 lima")
    (docs / "idem" / "fort-wayne").mkdir(parents=True)  # the FW jurisdiction+site subtree
    (docs / "idem" / "fort-wayne" / "permit.pdf").write_bytes(b"%PDF-1.4 fw")

    scoped = export_documents(docs, scope=("fort-wayne", "idem/fort-wayne"))
    rels = [e.rel for c in scoped for e in c.entries]
    assert rels == ["idem/fort-wayne/permit.pdf"]  # the Lima recorder collection is dropped

    everything = [e.rel for c in export_documents(docs, scope=None) for e in c.entries]
    assert set(everything) == {"recorder/deed.pdf", "idem/fort-wayne/permit.pdf"}


def test_gis_findings_geojson_is_valid() -> None:
    import json

    path = REPO_ROOT / "data" / "site" / "gis-findings.geojson"
    fc = json.loads(path.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    layers = {f["properties"]["layer"] for f in fc["features"]}
    required_layers = {
        "campus",
        "jsmc",
        "wwtp",
        "floodway",
        "floodplain",
        "rsei",
        "corridor",
        "roadwork",
    }
    missing_layers = required_layers - layers
    assert not missing_layers, f"missing GIS layers: {missing_layers}; got: {layers}"
    # Every feature has non-empty geometry (polygons for areas, points for WWTPs/RSEI,
    # a line for the corridor roadwork centerline).
    for f in fc["features"]:
        assert f["geometry"]["type"] in (
            "Polygon",
            "MultiPolygon",
            "Point",
            "LineString",
            "MultiLineString",
        )
        assert f["geometry"]["coordinates"]
    # RSEI points carry a graduated radius + score for the sized overlay markers.
    rsei = [f for f in fc["features"] if f["properties"]["layer"] == "rsei"]
    assert len(rsei) >= 40
    bad_geom = [f["properties"].get("label") for f in rsei if f["geometry"]["type"] != "Point"]
    assert not bad_geom, f"non-Point RSEI features: {bad_geom}"
    bad_props = [
        f["properties"].get("label")
        for f in rsei
        if "radius" not in f["properties"] or "score" not in f["properties"]
    ]
    assert not bad_props, f"RSEI features missing radius/score: {bad_props}"


def test_merge_rsei_layer_is_idempotent() -> None:
    """Merging RSEI points twice yields the same single rsei layer (no duplication)."""
    from watermark.config import Settings
    from watermark.rsei import load_inventory
    from watermark.site.gismap import merge_rsei_layer

    inv = load_inventory(Settings(data_dir=REPO_ROOT / "data"))
    assert inv is not None
    base: dict = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "properties": {"layer": "wwtp", "label": "x"},
            }
        ],
    }
    once, n1 = merge_rsei_layer(base, inv)
    twice, n2 = merge_rsei_layer(once, inv)
    assert n1 == n2 > 0
    rsei_once = [f for f in once["features"] if f["properties"]["layer"] == "rsei"]
    rsei_twice = [f for f in twice["features"] if f["properties"]["layer"] == "rsei"]
    assert len(rsei_once) == len(rsei_twice) == n1
    # The pre-existing non-rsei feature is preserved.
    assert any(f["properties"]["layer"] == "wwtp" for f in twice["features"])


def test_merge_rsei_layer_rings_flagged_water_dischargers() -> None:
    """With the toxic screen, critical water dischargers get a water_flag property."""
    from watermark.config import Settings
    from watermark.hydrology import toxics
    from watermark.rsei import load_inventory
    from watermark.site.gismap import merge_rsei_layer

    settings = Settings(data_dir=REPO_ROOT / "data")
    inv = load_inventory(settings)
    screen = toxics.build_screen(settings)
    assert inv is not None
    base: dict = {"type": "FeatureCollection", "features": []}
    fc, _ = merge_rsei_layer(base, inv, screen)
    flagged = [f for f in fc["features"] if f["properties"].get("water_flag")]
    # Critical/elevated water dischargers on the Ottawa corridor (per-chemical screen, WS-07).
    unexpected_flags = {f["properties"]["water_flag"] for f in flagged} - {"critical", "elevated"}
    assert not unexpected_flags, f"unexpected water_flag values: {unexpected_flags}"
    # The map's critical rings match the screen's critical count exactly (no over/under-flagging).
    ringed_critical = sum(1 for f in flagged if f["properties"]["water_flag"] == "critical")
    assert ringed_critical == screen.meta["critical_count"] >= 3
    # A ringed feature names its receiving water in the popup label.
    crit_list = [f for f in flagged if f["properties"]["water_flag"] == "critical"]
    assert crit_list, (
        f"no 'critical' flagged feature; flags: {[f['properties']['water_flag'] for f in flagged]}"
    )
    crit = crit_list[0]
    assert "toxic water discharger" in crit["properties"]["label"]
    # Without the screen, no rings.
    plain, _ = merge_rsei_layer({"type": "FeatureCollection", "features": []}, inv)
    assert not any(f["properties"].get("water_flag") for f in plain["features"])
