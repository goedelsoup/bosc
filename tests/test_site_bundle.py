"""Integrity tests for the typed content bundle (issue #53, Tier 1 / #62).

Exports a full bundle to a temp dir off the committed corpus (hermetic, no network) and
asserts the contract holds: every feed validates against its JSON Schema, the manifest is
internally consistent, the committed schemas match what the models generate (drift guard),
and cross-feed references resolve (the bundle's "no orphaned references" — the spirit of
``tests/test_site_nav.py`` ported to the data tier).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema.validators import Draft202012Validator

from bosc.config import Settings
from bosc.site.export import export_bundle

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_SCHEMAS = REPO_ROOT / "data" / "site" / "bundle" / "schemas"


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A freshly exported bundle, generated once for the module from the committed data."""
    out = tmp_path_factory.mktemp("bundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data")
    export_bundle(settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00")
    return out


def _manifest(bundle: Path) -> dict[str, Any]:
    return json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))


def _feeds_by_name(bundle: Path) -> dict[str, dict[str, Any]]:
    return {f["name"]: f for f in _manifest(bundle)["feeds"]}


def _rows(bundle: Path, ref: dict[str, Any]) -> list[Any]:
    """The rows of a feed, regardless of media type (NDJSON / JSON array / single object)."""
    text = (bundle / ref["path"]).read_text(encoding="utf-8")
    if ref["media_type"] == "application/x-ndjson":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    parsed = json.loads(text)
    return parsed if ref["kind"] == "collection" else [parsed]


def test_manifest_validates_and_is_internally_consistent(bundle: Path) -> None:
    manifest = _manifest(bundle)
    schema = json.loads((bundle / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(manifest)

    feeds = manifest["feeds"]
    assert manifest["feed_count"] == len(feeds)
    assert manifest["row_total"] == sum(f["count"] for f in feeds)
    names = [f["name"] for f in feeds]
    assert len(names) == len(set(names)), "duplicate feed names"
    for f in feeds:
        assert (bundle / f["path"]).is_file(), f"missing feed file {f['path']}"
        assert (bundle / f["schema"]).is_file(), f"missing schema {f['schema']}"


def test_every_feed_validates_against_its_schema(bundle: Path) -> None:
    manifest = _manifest(bundle)
    assert manifest["feeds"], "bundle has no feeds"
    for f in manifest["feeds"]:
        schema = json.loads((bundle / f["schema"]).read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        data_path = bundle / f["path"]
        if f["media_type"] == "application/x-ndjson":
            seen = 0
            for line in data_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    validator.validate(json.loads(line))
                    seen += 1
            assert seen == f["count"], f"{f['name']}: count {f['count']} != {seen} rows"
        else:
            doc = json.loads(data_path.read_text(encoding="utf-8"))
            validator.validate(doc)
            if f["kind"] == "collection":
                assert len(doc) == f["count"], f"{f['name']}: count mismatch"
            elif f["kind"] == "geojson":
                assert doc["type"] == "FeatureCollection"
                assert len(doc["features"]) == f["count"], f"{f['name']}: feature count mismatch"
            else:
                assert f["count"] == 1


def test_all_schemas_are_valid_draft_2020_12(bundle: Path) -> None:
    for path in sorted((bundle / "schemas").glob("*.json")):
        Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))


def test_committed_schemas_match_generated(bundle: Path) -> None:
    """The committed schemas/ must equal what the models generate — else `bosc export`."""
    generated = {p.name for p in (bundle / "schemas").glob("*.json")}
    committed = {p.name for p in COMMITTED_SCHEMAS.glob("*.json")}
    assert generated == committed, "committed schema set differs — run `bosc export`"
    for name in generated:
        gen = json.loads((bundle / "schemas" / name).read_text(encoding="utf-8"))
        com = json.loads((COMMITTED_SCHEMAS / name).read_text(encoding="utf-8"))
        assert gen == com, f"schema drift in {name} — regenerate with `bosc export`"


def test_cross_feed_references_resolve(bundle: Path) -> None:
    by_name = _feeds_by_name(bundle)
    entity_keys = {e["key"] for e in _rows(bundle, by_name["entities"])}

    # Every relationship endpoint is a real entity key.
    for rel in _rows(bundle, by_name["relationships"]):
        assert rel["src"] in entity_keys, f"relationship src {rel['src']} not in entities"
        assert rel["dst"] in entity_keys, f"relationship dst {rel['dst']} not in entities"

    # People / candidate cross-links resolve when present.
    for person in _rows(bundle, by_name["people"]):
        if person["entity_key"]:
            assert person["entity_key"] in entity_keys
    if "candidates" in by_name:
        for cand in _rows(bundle, by_name["candidates"]):
            if cand["entity_key"]:
                assert cand["entity_key"] in entity_keys

    # Defense-contractor matches are entity keys.
    if "defense-contractors" in by_name:
        defense = _rows(bundle, by_name["defense-contractors"])[0]
        for contractor in defense["contractors"]:
            for key in contractor["matched_entities"]:
                assert key in entity_keys, f"defense match {key} not in entities"

    # Every record cites an extraction artifact that exists (chain of custody).
    extracted = REPO_ROOT / "data" / "extracted"
    for record in _rows(bundle, by_name["records"]):
        assert (extracted / record["rel"]).exists(), f"record path missing: {record['rel']}"
        assert record["citation"]["source"] == record["rel"]

    # Every timeline event's source resolves to a committed extraction (chain of custody).
    for event in _rows(bundle, by_name["timeline"]):
        if event.get("source"):
            assert (extracted / event["source"]).exists(), (
                f"timeline source missing: {event['source']}"
            )

    # Concept `related` siblings are real concept slugs (no orphaned wiki links).
    if "concepts" in by_name:
        concepts = _rows(bundle, by_name["concepts"])
        slugs = {c["slug"] for c in concepts}
        for c in concepts:
            for sib in c.get("related", []):
                assert sib in slugs, f"concept {c['slug']} relates to unknown concept {sib}"


def test_feed_slugs_are_unique(bundle: Path) -> None:
    """Slug-keyed feeds (the per-item page ids) must have no duplicates."""
    by_name = _feeds_by_name(bundle)
    for feed in ("people", "places", "concepts", "documents"):
        if feed not in by_name:
            continue
        slugs = [r["slug"] for r in _rows(bundle, by_name[feed])]
        assert len(slugs) == len(set(slugs)), f"{feed}: duplicate slugs"
        assert all(s and s == s.strip() for s in slugs), f"{feed}: blank/untrimmed slug"


def test_e14_watershed_and_imagery_geo_feeds_are_coherent(bundle: Path) -> None:
    """The E1.4 geo feeds (#61) for the #72 map exist and carry their metadata."""
    by_name = _feeds_by_name(bundle)

    watershed = json.loads((bundle / by_name["geo/watershed"]["path"]).read_text(encoding="utf-8"))
    assert watershed["features"], "watershed feed has no boundaries"
    for f in watershed["features"]:
        p = f["properties"]
        assert p["layer"] == "watershed"
        assert p["role"] == "area"
        assert str(p["huc"]).isdigit() and p["level"] in (8, 10, 12)
        assert p["name"], "watershed feature missing HU name"
    # Coarsest → finest so the finer subwatershed draws on top.
    levels = [f["properties"]["level"] for f in watershed["features"]]
    assert levels == sorted(levels)

    imagery = json.loads((bundle / by_name["geo/imagery"]["path"]).read_text(encoding="utf-8"))
    wayback = imagery["meta"]["wayback"]
    assert wayback["releases"], "imagery feed missing the dated Wayback ladder"
    assert "{release}" in wayback["tile_url_template"]
    assert all("date" in r and "release" in r for r in wayback["releases"])
    assert imagery["features"], "imagery feed missing an AOI footprint"
    assert all(f["properties"]["layer"] == "imagery" for f in imagery["features"])


def test_geo_features_carry_layer_metadata(bundle: Path) -> None:
    for name, ref in _feeds_by_name(bundle).items():
        if ref["kind"] != "geojson":
            continue
        fc = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))
        assert fc["meta"]["crs"].startswith("WGS84"), f"{name}: geometry must be WGS84 verbatim"
        for feature in fc["features"]:
            props = feature["properties"]
            assert props.get("layer"), f"{name}: feature missing layer"
            assert props.get("role") in ("area", "line", "point")


def test_approximate_markers_are_preserved_as_data(bundle: Path) -> None:
    """OPC figures transcribed with ``~`` surface as ``approximate_paths`` (issue #60)."""
    records = _rows(bundle, _feeds_by_name(bundle)["records"])
    opc = [r for r in records if r["group"] == "opc"]
    assert opc, "expected at least one OPC record"
    # The Tetra Tech roundabouts summary carries ~-marked program totals.
    assert any(r["approximate_paths"] for r in opc), "no ~ approximate markers preserved"
