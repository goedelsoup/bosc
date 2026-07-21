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

from watermark.config import Settings
from watermark.pipeline.corpus import relpath_in_scope
from watermark.site.export import export_bundle
from watermark.sites import effective_corpus_scope, get_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_SCHEMAS = REPO_ROOT / "data" / "site" / "bundle" / "schemas"
# The per-site offline bundle (#727): the committed Lima bundle the frontend build reads
# (`web/sites/<slug>/`, a full `watermark export` per registered site).
FRONTEND_SAMPLE = REPO_ROOT / "web" / "sites" / "lima"


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
    """The committed schemas/ must equal what the models generate — else `watermark export`."""
    generated = {p.name for p in (bundle / "schemas").glob("*.json")}
    committed = {p.name for p in COMMITTED_SCHEMAS.glob("*.json")}
    assert generated == committed, "committed schema set differs — run `watermark export`"
    for name in generated:
        gen = json.loads((bundle / "schemas" / name).read_text(encoding="utf-8"))
        com = json.loads((COMMITTED_SCHEMAS / name).read_text(encoding="utf-8"))
        assert gen == com, f"schema drift in {name} — regenerate with `watermark export`"


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
    # The #276 record→source-document join must resolve to a real catalog entry.
    docs_by_rel = {
        e["rel"]: e for coll in _rows(bundle, by_name["documents"]) for e in coll["entries"]
    }
    joined = 0
    for record in _rows(bundle, by_name["records"]):
        assert (extracted / record["rel"]).exists(), f"record path missing: {record['rel']}"
        assert record["citation"]["source"] == record["rel"]
        src_rel = record.get("source_doc_rel")
        if src_rel is not None:
            assert src_rel in docs_by_rel, f"record {record['rel']} → uncatalogued source {src_rel}"
            assert record["source_doc_render_class"] == docs_by_rel[src_rel]["render_class"]
            joined += 1
    assert joined, "no record joined to a source document — the #276 join is dead"

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


def test_documents_carry_version_cluster_metadata(bundle: Path) -> None:
    """The exported documents feed carries the #1590 version/dedup metadata from the curated
    manifest: the OEPA permit triad clusters, its final permit canonical + superseding the draft
    and fact sheet."""
    by_name = _feeds_by_name(bundle)
    docs_by_rel = {
        e["rel"]: e for coll in _rows(bundle, by_name["documents"]) for e in coll["entries"]
    }
    permit = "oepa/oepa-2PH00006-american-ii-permit.pdf"
    draft = "oepa/oepa-2PH00006-american-ii-draft-pn-2025-04.pdf"
    fact = "oepa/oepa-2PH00006-american-ii-fact-sheet.pdf"
    assert {permit, draft, fact} <= docs_by_rel.keys(), "OEPA 2PH00006 triad missing from catalog"

    for rel in (permit, draft, fact):
        e = docs_by_rel[rel]
        assert e["duplicate_cluster"] == "oepa:2PH00006"
        assert e["canonical_document_id"] == permit
    assert docs_by_rel[permit]["version"] == "final"
    assert docs_by_rel[draft]["version"] == "draft"
    assert docs_by_rel[fact]["version"] == "fact_sheet"
    # Only the canonical member enumerates what it supersedes.
    assert set(docs_by_rel[permit]["supersedes"]) == {draft, fact}
    assert docs_by_rel[draft]["supersedes"] == []

    # An unclustered document carries the fields defaulted (additive/optional — never invented).
    unclustered = next(e for e in docs_by_rel.values() if e["rel"] not in {permit, draft, fact})
    assert unclustered["duplicate_cluster"] is None
    assert unclustered["supersedes"] == []


def _assert_lima_bundle_peer_free(bundle_dir: Path) -> None:
    """#1505 — the reference build must not swallow a peer's slug-scoped records. A Lima bundle's
    corpus-derived feeds (records, documents, timeline) may cite only paths inside Lima's own
    effective corpus scope (the whole tree minus every registered peer's subtree), so a Fort Wayne
    §401 under ``idem/fort-wayne/`` or a Piqua NPDES permit under ``oepa/troy-piqua/`` never renders
    inside Lima's Allen-County record. The scope prefixes match both trees (``data/documents`` and
    ``data/extracted``) since a peer's layout mirrors across them.
    """
    scope = effective_corpus_scope(get_profile("lima"))
    by_name = _feeds_by_name(bundle_dir)
    offenders: list[str] = []
    for record in _rows(bundle_dir, by_name["records"]):
        if not scope.contains(record["rel"]):
            offenders.append(f"records: {record['rel']}")
    for coll in _rows(bundle_dir, by_name["documents"]):
        for entry in coll["entries"]:
            if not scope.contains(entry["rel"]):
                offenders.append(f"documents: {entry['rel']}")
    for event in _rows(bundle_dir, by_name["timeline"]):
        src = event.get("source")
        if src and not scope.contains(src):
            offenders.append(f"timeline: {src}")
    assert not offenders, (
        "Lima bundle swallows peer records (#1505) — these feeds cite a registered peer's "
        "subtree:\n" + "\n".join(sorted(offenders))
    )


def test_fresh_lima_export_excludes_peer_records(bundle: Path) -> None:
    """The export path honors Lima's peer-exclusion (#1505): a freshly exported Lima bundle carries
    none of a sibling's slug-scoped records."""
    _assert_lima_bundle_peer_free(bundle)


def test_committed_lima_bundle_excludes_peer_records() -> None:
    """The *committed* ``web/sites/lima/`` bundle the frontend ships must also be peer-free (#1505).
    No content test gated the committed feeds before — only schemas — so the bundle drifted silently
    and re-accreted fort-wayne / troy-piqua / urbana / sidney rows (#1505). This is that guard: it
    fails until the committed bundle is re-exported against the current corpus + scope."""
    _assert_lima_bundle_peer_free(FRONTEND_SAMPLE)


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


def _assert_fixture_tracks_export(fixture_dir: Path, exported_manifest: dict[str, Any]) -> None:
    """A committed ``sites/<slug>/`` bundle must not silently drift from its
    ``watermark … export`` (issue #179). It's a full export (schemas/ and the embedding vectors
    aside), so its feed set matches — but the check stays a *subset* assertion so a lean committed
    bundle can never carry a feed the exporter no longer produces. The ``contract_version`` and
    ``site`` must match exactly, every committed feed must still exist in the real export (catches
    a rename/removal), and the committed manifest must stay internally consistent. Refresh it
    (see ``web/sites/README.md``) on drift.
    """
    sample = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))

    assert sample["contract_version"] == exported_manifest["contract_version"], (
        f"{fixture_dir.name} contract_version {sample['contract_version']} != exported "
        f"{exported_manifest['contract_version']} — refresh the fixture"
    )
    assert sample["site"] == exported_manifest["site"], (
        f"{fixture_dir.name} fixture is for site {sample['site']!r} but exported {exported_manifest['site']!r}"
    )

    exported_feeds = {f["name"] for f in exported_manifest["feeds"]}
    stale = {f["name"] for f in sample["feeds"]} - exported_feeds
    assert not stale, f"{fixture_dir.name} fixture has feeds no longer produced by export: {stale}"

    # The trimmed manifest must stay internally consistent and its feed files present.
    assert sample["feed_count"] == len(sample["feeds"])
    assert sample["row_total"] == sum(f["count"] for f in sample["feeds"])
    for f in sample["feeds"]:
        assert (fixture_dir / f["path"]).is_file(), f"{fixture_dir.name} missing file {f['path']}"


def test_frontend_sample_bundle_tracks_the_export_contract(bundle: Path) -> None:
    """The committed Lima CI fixture tracks `watermark export` (the reference build)."""
    _assert_fixture_tracks_export(FRONTEND_SAMPLE, _manifest(bundle))


def test_fort_wayne_sample_bundle_tracks_the_export_contract(fort_wayne_bundle: Path) -> None:
    """The committed Fort Wayne fixture tracks **`watermark --site fort-wayne export` (#741) — the
    first non-Lima committed site bundle, so this also guards that a sibling fixture stays a real,
    per-site-scoped slice of its own export."""
    _assert_fixture_tracks_export(
        REPO_ROOT / "web" / "sites" / "fort-wayne", _manifest(fort_wayne_bundle)
    )


def test_urbana_sample_bundle_tracks_the_export_contract(urbana_bundle: Path) -> None:
    """The committed Urbana fixture tracks `watermark --site urbana export` (#797) — the network's
    third live site, promoted 2026-07-01."""
    _assert_fixture_tracks_export(REPO_ROOT / "web" / "sites" / "urbana", _manifest(urbana_bundle))


def test_wpafb_committed_bundle_is_fresh(wpafb_bundle: Path) -> None:
    """The committed ``web/sites/wpafb/`` bundle must track ``watermark --site wpafb export`` — and
    in particular its **readiness must not lag its own evidence on disk** (#1660, ME-A).

    The original defect this guards: #1397 ingested the two ``permits-epa`` records (the US-EPA
    Sole Source Aquifer designation + the CERCLA §120 Federal Facility Agreement) that clear
    ``RECORD_LIVE_THRESHOLD``, but the committed bundle was never re-exported — so it shipped
    ``tier: backdrop`` / ``record: absent`` with a 0-length ``records`` feed while the exporter
    (and ``test_wpafb_exports_at_case_tier``) already produced ``tier: case`` / ``record: live``.
    The generic ``_assert_fixture_tracks_export`` alone would have caught it *only because* the
    contract version had also moved (1.29.0 → 1.30.2); to catch the "live in code, absent on
    disk" class even at a steady contract, this additionally pins the committed readiness block
    and the ``records`` feed to what a fresh export produces."""
    fixture = REPO_ROOT / "web" / "sites" / "wpafb"
    fresh = _manifest(wpafb_bundle)
    _assert_fixture_tracks_export(fixture, fresh)

    committed = _manifest(fixture)
    assert committed["readiness"] == fresh["readiness"], (
        "committed wpafb readiness drifted from a fresh export — re-export the bundle "
        "(see web/sites/README.md); a record ingest must re-export the affected site"
    )
    # The record domain is live because the site owns exactly its two in-scope agency records;
    # pin the committed feed to those extracted-tree source paths so a dropped/renamed record
    # (readiness silently falling back to seeded/absent on disk) fails here, not in production.
    committed_records = {r["rel"] for r in _rows(fixture, _feeds_by_name(fixture)["records"])}
    assert committed_records == {
        "wpafb/ssa-53fr15876.epa.yaml",
        "wpafb/cercla-ffa-1991.epa.yaml",
    }, f"committed wpafb records feed drifted, got {sorted(committed_records)}"


# --- Backdrop-tier network sites (#1220 / #1224) --------------------------------------------
# The epic's promotion-candidate proof: the backdrop-staged sites bundle at `backdrop` tier off
# their committed floor data alone (no fabricated corpus), and the true stubs stay `stub`. We
# assert the derived readiness end-to-end through the real export rather than committing ~370
# unrendered fixture files for these non-selectable sites (their bundles regenerate on promotion).
@pytest.mark.parametrize("slug", ["toledo", "west-union"])
def test_backdrop_staged_site_exports_at_backdrop_tier(
    slug: str, tmp_path_factory: pytest.TempPathFactory
) -> None:
    out = tmp_path_factory.mktemp(f"backdrop-{slug}") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site=slug)
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert manifest["contract_version"] == "1.30.3"
    readiness = manifest["readiness"]
    assert readiness["tier"] == "backdrop", f"{slug} should be a Backdrop site, got {readiness}"
    domains = readiness["domains"]
    # The floor is live; nothing above it is scaffolded (the epic's additive rule).
    assert domains["backdrop"] == "live"
    for above_floor in ("facility", "places", "record"):
        assert domains[above_floor] == "absent", f"{slug} {above_floor} must not scaffold"


def test_findlay_exports_at_case_tier(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Findlay's floor (economics-baseline, consumer-energy, rsei) is committed. Two above-floor
    domains are live: ``record`` from the #1465 flood-mitigation-chain ingest (the FEMA Flood
    Mitigation Assistance $24M obligation + the USACE Blanchard-watershed feasibility Review Plan,
    two in-scope ``permits-epa`` extractions clearing ``RECORD_LIVE_THRESHOLD``), and ``facility``
    from the disclosed One Power "Findlay Megawatt Hub" / MARA 150 MW take-or-pay ``SiteFacility``
    + its demand-pressure feed (#1459). Unlike the site-plan-grounded Urbana/Sidney facilities, the
    MW here is a `[verified]` disclosure (30 MW energized / 150 MW contracted), not a screening
    bracket. ``story`` is ``seeded`` (the committed per-site leads board,
    ``data/site/findlay/leads.yaml``, is a leads-first resting state — Findlay is not yet in
    ``STORY_SLUGS``). ``places`` stays ``absent`` (no committed campus geometry), so this needs its
    own test rather than the backdrop parametrize group (which asserts ``record`` stays
    unscaffolded)."""
    out = tmp_path_factory.mktemp("case-findlay") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="findlay")
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert manifest["contract_version"] == "1.30.3"
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"findlay should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["record"] == "live"
    # The disclosed SiteFacility + its committed demand-pressure feed lift facility to live (#1459).
    assert domains["facility"] == "live"
    # ``story`` is seeded off the committed leads board, not a registered guided walk.
    assert domains["story"] == "seeded"
    # ``places`` stays absent: no committed campus geometry (a separate epic #1265 sub-issue).
    assert domains["places"] == "absent", "findlay places must not scaffold"

    # ``record`` is live because the site owns exactly its two real, in-scope agency records — the
    # FEMA FMA obligation and the USACE feasibility Review Plan — not scaffolding: assert the
    # records feed holds precisely those two artifacts by their extracted-tree source paths (#1465).
    records = _rows(out, _feeds_by_name(out)["records"])
    assert {r["rel"] for r in records} == {
        "findlay/flood/fema-fma-obligation-2026.epa.yaml",
        "findlay/flood/usace-blanchard-review-plan-2024.epa.yaml",
    }, (
        f"records feed should hold exactly the two in-scope flood records, got {sorted(r['rel'] for r in records)}"
    )
    assert len(records) == 2


def test_wpafb_exports_at_case_tier(tmp_path_factory: pytest.TempPathFactory) -> None:
    """WPAFB's floor (economics-baseline, consumer-energy, rsei) is committed, and the #1397
    primary-record ingest lifts ``record`` to ``live``: the US-EPA Sole Source Aquifer
    designation (53 FR 15876) and the CERCLA §120 Federal Facility Agreement are two in-scope
    ``permits-epa`` extractions clearing ``RECORD_LIVE_THRESHOLD`` — one above-floor domain live
    over the floor is enough for ``case``. ``facility``/``places``/``story`` stay ``absent`` (no
    disclosed SiteFacility, no committed campus geometry, not in ``STORY_SLUGS``), so this needs
    its own test rather than the backdrop parametrize group (which asserts ``record`` stays
    unscaffolded)."""
    out = tmp_path_factory.mktemp("case-wpafb") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="wpafb")
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert manifest["contract_version"] == "1.30.3"
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"wpafb should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["record"] == "live"
    # Nothing else above the floor is scaffolded: no disclosed facility, no committed campus
    # geometry, no registered story.
    for absent_domain in ("facility", "places", "story"):
        assert domains[absent_domain] == "absent", f"wpafb {absent_domain} must not scaffold"

    # ``record`` is live because the site owns exactly its two real, in-scope agency records —
    # the SSA designation and the CERCLA FFA — not scaffolding: assert the records feed holds
    # precisely those two artifacts by their extracted-tree source paths (#1397).
    records = _rows(out, _feeds_by_name(out)["records"])
    assert {r["rel"] for r in records} == {
        "wpafb/ssa-53fr15876.epa.yaml",
        "wpafb/cercla-ffa-1991.epa.yaml",
    }, (
        f"records feed should hold exactly the two in-scope agency records, got {sorted(r['rel'] for r in records)}"
    )
    assert len(records) == 2


def test_troy_piqua_exports_at_case_tier(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Troy/Piqua's floor (economics-baseline, consumer-energy, rsei) is committed (#1481), and
    the disclosed "Project Klondike" ``SiteFacility`` + its demand-pressure feed (#1482) lift
    ``facility`` to ``live`` — one above-floor domain live over the floor is enough for ``case``.
    ``record`` is ``live``: the Piqua WWTP NPDES permit + fact sheet (1PD00008) and the DMR are
    all in-scope now that #1484 relocated the two OEPA extractions under ``oepa/troy-piqua/`` and
    set ``corpus_relpaths=("troy-piqua", "oepa/troy-piqua")`` — three extractions clearing
    ``RECORD_LIVE_THRESHOLD`` (previously the two permit extractions orphaned in the flat
    ``oepa/`` tree, leaving only the sub-threshold DMR). Its own test rather than the shared
    parametrize group above, since that group asserts ``record``/``facility`` stay fully
    unscaffolded."""
    out = tmp_path_factory.mktemp("case-troy-piqua") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="troy-piqua")
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert manifest["contract_version"] == "1.30.3"
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"troy-piqua should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "live"
    assert domains["places"] == "live"  # committed J5 "Project Klondike" campus assemblage (#1483)
    assert domains["record"] == "live"
    # ``story`` is ``seeded``: the site's curated leads board (data/site/troy-piqua/leads.yaml, #1485)
    # ships as the ``leads`` feed, but troy-piqua is not yet in ``STORY_SLUGS`` — a registered story
    # is a separate, later editorial call. Leads-only ⇒ seeded (the Findlay/Defiance precedent).
    assert domains["story"] == "seeded"

    # ``record`` is live because the site owns exactly its three real, in-scope extractions
    # (#1484) — the NPDES permit, its fact sheet, and the DMR — not scaffolding: assert the
    # records feed holds precisely those three artifacts by their extracted-tree source paths.
    records = _rows(out, _feeds_by_name(out)["records"])
    assert {r["rel"] for r in records} == {
        "oepa/troy-piqua/1PD00008.npdes.yaml",
        "oepa/troy-piqua/1PD00008.fs.npdes.yaml",
        "troy-piqua/wwtp-oh0027049.dmr.yaml",
    }, (
        f"records feed should hold exactly the three in-scope extractions, got {sorted(r['rel'] for r in records)}"
    )
    assert len(records) == 3


def test_sidney_exports_at_case_tier(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Sidney's floor (economics-baseline, consumer-energy, rsei) is committed, and the disclosed
    AWS "Project Galaxy" ``SiteFacility`` + its demand-pressure feed (#1378) lift ``facility`` to
    ``live`` — one above-floor domain live over the floor is enough for ``case``. The MW load is
    NOT disclosed (AWS discloses no floor area or interconnection figure): the IT load is an
    investment-scaled ``[inference]`` screening bracket, never a disclosure. ``record`` stays
    ``seeded`` (one in-scope DMR extraction, below ``RECORD_LIVE_THRESHOLD``). Its own test rather
    than the shared parametrize group above, since that group asserts ``record``/``facility`` stay
    fully unscaffolded."""
    out = tmp_path_factory.mktemp("case-sidney") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="sidney")
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert manifest["contract_version"] == "1.30.3"
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"sidney should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "live"
    assert domains["places"] == "absent"
    assert domains["record"] == "seeded"
    assert domains["story"] == "absent"


@pytest.mark.parametrize("slug", ["coshocton", "piketon", "sandusky"])
def test_stub_site_exports_at_stub_tier(
    slug: str, tmp_path_factory: pytest.TempPathFactory
) -> None:
    out = tmp_path_factory.mktemp(f"stub-{slug}") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site=slug)
    export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    readiness = _manifest(out)["readiness"]
    assert readiness["tier"] == "stub", f"{slug} is profile-only, expected stub, got {readiness}"
    assert readiness["domains"]["backdrop"] != "live"


@pytest.fixture(scope="module")
def fort_wayne_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A Fort Wayne bundle exported off the committed corpus — the sibling site used to
    prove per-site content scope (#762). Hermetic: no network, same committed data."""
    out = tmp_path_factory.mktemp("fwbundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="fort-wayne")
    export_bundle(settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00")
    return out


@pytest.fixture(scope="module")
def urbana_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An Urbana bundle (#782's validation candidate) — a sibling with an **explicit**
    ``corpus_relpaths`` (``("urbana", "permits/highland55", "oepa/urbana")`` — its own slug plus the
    Highland55 land-assembly permit + OEPA prefixes, #1328), so it exercises a slug-plus-jurisdiction
    scope. Hermetic: no network, same committed data."""
    out = tmp_path_factory.mktemp("urbanabundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="urbana")
    export_bundle(settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00")
    return out


@pytest.fixture(scope="module")
def wpafb_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A WPAFB bundle exported off the committed corpus — the network's federal-enclave site
    whose two ``permits-epa`` records (the SSA designation + the CERCLA FFA, #1397) lift ``record``
    to ``live`` / ``tier`` to ``case``. Backs the committed-bundle freshness guard below (#1660):
    the committed bundle silently drifted a full tier below its own evidence because no drift test
    covered it. Hermetic: no network, same committed data."""
    out = tmp_path_factory.mktemp("wpafbbundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="wpafb")
    export_bundle(settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00")
    return out


@pytest.fixture(scope="module")
def springfield_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A Springfield bundle — a Mad River sibling that leaves ``corpus_relpaths`` unset (so it
    defaults to ``('springfield',)``) and has **no committed corpus**, exercising the #780
    *default* scope. Hermetic: no network, same committed data."""
    out = tmp_path_factory.mktemp("springfieldbundle") / "b"
    settings = Settings(data_dir=REPO_ROOT / "data", site="springfield")
    export_bundle(settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00")
    return out


def _assert_corpus_feeds_lima_free(slug: str, bundle_dir: Path) -> None:
    """The reusable new-site smoke test (#762/#780): a sibling site's corpus-derived feeds must
    carry none of Lima's Allen-County-OH record.

    Several feeds are built by readers that once globbed the whole extracted tree (the timeline
    civic builders, the entity-graph subdivision/relation-class overlays, the flat
    ``data/scenarios`` dir); each is now bounded by the site's *effective* corpus scope. A site's
    scope is its explicit ``corpus_relpaths`` or, when unset, its own slug — **never** the
    reference build's whole tree (only Lima resolves to ``None``).

    The basin-/network-shared lenses (``network``, ``concepts``, the ``hypotheses`` *definitions*)
    are cross-site by design. ``catalog`` and ``hypothesis-assessments`` are narrowed separately
    (:func:`test_sibling_bundle_narrows_cross_site_feeds`); the residual Fort-Wayne-specific
    ``catalog`` rows are the #778 taxonomy gap and out of scope for this corpus guard.
    """
    scope = effective_corpus_scope(get_profile(slug))
    assert scope.include is not None, (
        f"{slug} is not the reference build, so its scope must be bounded (a peer includes its own "
        "prefixes, never the whole tree)"
    )

    feeds = _feeds_by_name(bundle_dir)
    # Every timeline event must cite a source inside the site's own corpus scope.
    for event in _rows(bundle_dir, feeds["timeline"]):
        assert relpath_in_scope(event["source"], scope), (
            f"{slug} timeline leaks an out-of-scope source: {event['source']}"
        )

    # No per-site corpus feed may name a Lima-only collection (the markers these leaks left).
    lima_markers = (
        "commissioners/",
        "lacrpc/",
        "perry-township/",
        "american-township/",
        "shawnee-township/",
        "scenarios/baseline",
        "scenarios/buildout",
    )
    for name in ("timeline", "entities", "relationships", "hydrology-scenarios"):
        ref = feeds.get(name)
        if ref is None:
            continue
        text = (bundle_dir / ref["path"]).read_text(encoding="utf-8")
        for marker in lima_markers:
            assert marker not in text, f"{slug} feed {name!r} leaks Lima marker {marker!r}"


def test_explicit_scoped_sibling_bundle_carries_no_lima_corpus(fort_wayne_bundle: Path) -> None:
    """Fort Wayne — a sibling with an *explicit* ``corpus_relpaths`` — is Lima-free (#762)."""
    assert get_profile("fort-wayne").corpus_relpaths is not None, "FW sets an explicit scope"
    _assert_corpus_feeds_lima_free("fort-wayne", fort_wayne_bundle)


def test_default_scoped_sibling_bundle_carries_no_lima_corpus(springfield_bundle: Path) -> None:
    """The new-site smoke test (#780): a freshly-registered site on the **default** scope is also
    Lima-free. Springfield leaves ``corpus_relpaths`` unset (so it defaults to ``('springfield',)``)
    and has no committed corpus — before #780 its ``None`` scope meant the whole tree, silently
    inheriting Lima's 174 timeline events and 72 entities. Adding a new site to this guard is one
    line. (Urbana, the prior stand-in, gained an explicit scope + real corpus in #1328.)"""
    assert get_profile("springfield").corpus_relpaths is None, (
        "Springfield relies on the default scope"
    )
    _assert_corpus_feeds_lima_free("springfield", springfield_bundle)


def test_sibling_bundle_narrows_cross_site_feeds(bundle: Path, fort_wayne_bundle: Path) -> None:
    """The two site-tagged cross-site feeds are strictly the sibling's own slice (#762).

    ``catalog`` and ``hypothesis-assessments`` form network-global sets, but each row is tagged
    with the site it belongs to. A sibling site's bundle carries only its own rows; the reference
    build (Lima) keeps the whole set — it's the network host the root ``/about/data`` and
    ``/research/hypotheses`` pages read, so narrowing it too would regress those views.
    """
    ref_feeds = _feeds_by_name(bundle)
    fw_feeds = _feeds_by_name(fort_wayne_bundle)

    # hypothesis-assessments: Lima carries the cross-site matrix; Fort Wayne only its own cells
    # (none committed yet → an empty feed, not other sites' rows).
    ref_cells = _rows(bundle, ref_feeds["hypothesis-assessments"])
    fw_cells = _rows(fort_wayne_bundle, fw_feeds["hypothesis-assessments"])
    assert {c["site"] for c in ref_cells} > {"lima"}, "reference build must keep the full matrix"
    assert all(c["site"] == "fort-wayne" for c in fw_cells), "sibling carries only its own cells"

    # catalog: the sibling drops Lima's pre-network legacy rows; the reference build keeps them.
    ref_scopes = {r["site_scope"] for r in _rows(bundle, ref_feeds["catalog"])}
    fw_scopes = {r["site_scope"] for r in _rows(fort_wayne_bundle, fw_feeds["catalog"])}
    assert "lima-legacy" in ref_scopes, "reference build keeps lima-legacy catalog rows"
    assert "lima-legacy" not in fw_scopes, "sibling bundle must drop lima-legacy catalog rows"


def test_approximate_markers_are_preserved_as_data(bundle: Path) -> None:
    """OPC figures transcribed with ``~`` surface as ``approximate_paths`` (issue #60)."""
    records = _rows(bundle, _feeds_by_name(bundle)["records"])
    opc = [r for r in records if r["group"] == "opc"]
    assert opc, "expected at least one OPC record"
    # The Tetra Tech roundabouts summary carries ~-marked program totals.
    assert any(r["approximate_paths"] for r in opc), "no ~ approximate markers preserved"


# --- leads feed (#796) ---------------------------------------------------------------------
def test_lima_bundle_carries_its_curated_leads(bundle: Path) -> None:
    """The reference build ships its committed leads board (`data/site/leads.yaml`) as the
    per-site `leads` feed, with the evidence discipline intact (#796)."""
    feeds = _feeds_by_name(bundle)
    assert "leads" in feeds, "Lima bundle should carry its curated leads board (#796)"
    rows = _rows(bundle, feeds["leads"])
    ids = {r["id"] for r in rows}
    assert {"PRR-04", "H1-DRAW"} <= ids
    # A lead is unverified inference until a source corroborates it: only [open] or [inference].
    assert all(r["tag"] in ("open", "inference") for r in rows)
    assert all(r["source"] for r in rows), "every lead must name where the gap is recorded"


def test_sibling_bundle_has_no_leads_feed(fort_wayne_bundle: Path) -> None:
    """A site with no committed leads store carries no `leads` feed — so the frontend falls back
    to the readiness-derived needs board, never Lima's leads (#796/#762)."""
    assert "leads" not in _feeds_by_name(fort_wayne_bundle)


def test_export_leads_is_empty_for_an_absent_store(tmp_path: Path) -> None:
    from watermark.site.leads import export_leads

    assert export_leads(tmp_path / "nope.yaml") == []


# --- contacts feed -------------------------------------------------------------------------
def test_lima_bundle_carries_its_curated_contacts(bundle: Path) -> None:
    """The reference build ships its committed contacts directory (`data/site/contacts.yaml`) as
    the per-site `contacts` feed, with the data discipline intact (every contact names a source)."""
    feeds = _feeds_by_name(bundle)
    assert "contacts" in feeds, "Lima bundle should carry its curated contacts directory"
    rows = _rows(bundle, feeds["contacts"])
    ids = {r["id"] for r in rows}
    assert {"allen-county-commissioners", "ohio-epa-dapc"} <= ids
    valid_kinds = {"petitioner", "organizer", "official", "group", "outlet"}
    assert all(r["kind"] in valid_kinds for r in rows)
    assert all(r["source"] for r in rows), "every contact must name where it is documented"
    # Public routing only — the bundle never carries a private hand-off address.
    assert all("email" not in r for r in rows), "contacts feed must not expose private addresses"


def test_sibling_bundle_has_no_contacts_feed(fort_wayne_bundle: Path) -> None:
    """A site with no committed contacts store carries no `contacts` feed — so the section locks
    and asks for the source, never Lima's contacts."""
    assert "contacts" not in _feeds_by_name(fort_wayne_bundle)


def test_export_contacts_is_empty_for_an_absent_store(tmp_path: Path) -> None:
    from watermark.site.contacts import export_contacts

    assert export_contacts(tmp_path / "nope.yaml") == []
