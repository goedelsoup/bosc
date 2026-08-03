"""Integrity tests for the typed content bundle (issue #53, Tier 1 / #62).

Reads a full bundle exported to a temp dir off the committed corpus (hermetic, no network —
``conftest``'s shared per-site exports, #1773) and asserts the contract holds: every feed
validates against its JSON Schema, the manifest is internally consistent, the committed schemas
match what the models generate (drift guard), and cross-feed references resolve (the bundle's
"no orphaned references" — the spirit of ``tests/test_site_nav.py`` ported to the data tier).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema.validators import Draft202012Validator

from watermark.config import Settings
from watermark.pipeline.corpus import relpath_in_scope
from watermark.sites import SITES, effective_corpus_scope, get_profile

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMITTED_SCHEMAS = REPO_ROOT / "data" / "site" / "bundle" / "schemas"
# The expected bundle contract version (kept in step with `watermark.site.feeds.CONTRACT_VERSION`);
# the fresh-export assertions below pin it so a bump lands here in one place.
_CV = "1.51.0"
# The per-site offline bundles (#727): a full `watermark export` per registered site, the
# committed input the Astro build reads with no Python step (`web/sites/<slug>/`).
COMMITTED_BUNDLES = REPO_ROOT / "web" / "sites"
FRONTEND_SAMPLE = COMMITTED_BUNDLES / "lima"


@pytest.fixture(scope="session")
def bundle(lima_bundle: Path) -> Path:
    """The reference build's freshly exported bundle.

    ``conftest``'s session-wide, cross-worker ``lima_bundle`` under this module's local name —
    here ``bundle`` is the reference build and the siblings are named (``fort_wayne_bundle``,
    ``urbana_bundle``, …), a vocabulary ~18 tests below already speak (#1773).
    """
    return lima_bundle


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


def test_committed_schemas_match_generated(
    bundle: Path, wpafb_bundle: Path, urbana_bundle: Path
) -> None:
    """The committed schemas/ must equal what the models generate — else `watermark export`.

    Compared against the **union** of the producing builds, not Lima alone (#1664). The committed
    `schemas/` are the *network's* shared contract, and a feed can be gated on evidence only some
    sites have: `enclave` exists only where a `federal_installation` facility is registered
    (wpafb), and `cooling-reconciliation` (#1805) only where the cooling-cycling cohort has a
    candidate row (urbana; Lima is not in the cohort) — so a Lima-only comparison would force an
    evidence-gated contract to go uncommitted. Adding producing bundles keeps the guard's real
    job — catching drift between a model and its committed schema — intact.
    """
    produced = {
        p.name: p
        for b in (bundle, wpafb_bundle, urbana_bundle)
        for p in (b / "schemas").glob("*.json")
    }
    committed = {p.name for p in COMMITTED_SCHEMAS.glob("*.json")}
    assert set(produced) == committed, "committed schema set differs — run `watermark export`"
    for name, path in produced.items():
        gen = json.loads(path.read_text(encoding="utf-8"))
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

    # Defense-contractor matches are entity keys, and each joined award reconciles with the
    # entity it resolves through — the entity carries the same federal_obligations (#1662, ME-C).
    if "defense-contractors" in by_name:
        defense = _rows(bundle, by_name["defense-contractors"])[0]
        ents_by_key = {e["key"]: e for e in _rows(bundle, by_name["entities"])}
        for contractor in defense["contractors"]:
            for key in contractor["matched_entities"]:
                assert key in entity_keys, f"defense match {key} not in entities"
            for award in contractor.get("awards", []):
                assert award["entity_key"] in entity_keys
                ent = ents_by_key[award["entity_key"]]
                assert ent["federal_obligations"] == award["total_obligations"], (
                    f"defense award for {award['entity_key']} disagrees with its entity total"
                )

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


# --- Readiness ↔ exporter feed-name coupling (#1631) ----------------------------------------
def test_readiness_feed_names_are_produced_by_export(bundle: Path, wpafb_bundle: Path) -> None:
    """Every manifest feed name ``watermark.site.readiness`` keys a domain on must be a name the
    exporter actually produces (#1631). The two were decoupled string literals — renaming
    ``economics-demand-pressure`` in ``export.py`` without updating ``readiness.py`` would
    silently drop every site's facility to ``seeded`` with green tests. The Lima bundle activates
    all five domains, so its feed set must contain every readiness feed name (incl. the composed
    ``geo/campus`` that ``export.py`` can't share as a literal). ``geo/enclave`` (#1664) is
    activated by evidence Lima does not and cannot have — a registered federal installation — so
    the WPAFB bundle joins the comparison rather than the guard being weakened to ignore it."""
    from watermark.site.readiness import READINESS_FEED_NAMES

    produced = set(_feeds_by_name(bundle)) | set(_feeds_by_name(wpafb_bundle))
    missing = READINESS_FEED_NAMES - produced
    assert not missing, (
        f"readiness keys on feeds the exporter no longer produces: {sorted(missing)} — a feed "
        "was renamed in export.py without updating watermark.site.readiness"
    )


def test_degenerate_demand_pressure_feed_is_dropped(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1631: the #1364 present-but-empty guard on the facility axis. A stale/degenerate
    demand-pressure payload (zero draw, e.g. a rezoning-only campus whose IT load is entirely
    ``[open]`` round-tripped through ``load_demand_pressure``) must be DROPPED — never shipped as a
    ``count == 1`` object shell the frontend's facility-leaf check (``hasFeed(FACILITY_FEED)``)
    would render as a zero-draw sensitivity. Exercised end-to-end on Lima (a facility site).

    Note (#1630 interaction): the demand-pressure feed no longer *grades* facility readiness — that
    is now the profile's documentary depth — so Lima stays ``facility: live`` on its air permit even
    with the feed dropped. This asserts both: the shell is dropped, and facility grading is decoupled
    from the feed (it does not fall to ``seeded`` just because the feed is gone)."""
    from watermark.economics.energy import load_demand_pressure
    from watermark.site import export as export_mod

    settings = Settings(data_dir=REPO_ROOT / "data")  # lima, a permit-grounded facility site
    real = load_demand_pressure(settings)
    assert real is not None and real.has_material_load, (
        "Lima's committed demand-pressure is material"
    )

    degenerate = real.model_copy(
        update={
            "facility_draw_mw": real.facility_draw_mw.model_copy(
                update={"value": 0.0, "low": None, "high": None}
            )
        }
    )
    assert not degenerate.has_material_load
    monkeypatch.setattr(export_mod, "load_demand_pressure", lambda *a, **k: degenerate)

    out = tmp_path_factory.mktemp("degenerate-dp") / "b"
    export_mod.export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert "economics-demand-pressure" not in {f["name"] for f in manifest["feeds"]}, (
        "a zero-draw demand-pressure shell was shipped as a feed"
    )
    # Facility grading is profile-driven (#1630): Lima is air-permit-grounded, so dropping the
    # demand-pressure feed does NOT change its facility state — it stays live, not seeded.
    assert manifest["readiness"]["domains"]["facility"] == "live"


# --- the grid backdrop feed (GP-E E1 / #1642) -----------------------------------------------
def test_grid_backdrop_feed_carries_the_cited_service_chain(bundle: Path) -> None:
    """The `grid` feed is the backdrop the frontend used to hardcode (#1642, E1/E2).

    Before this, the richest per-site grid artifact went only to a CLI reference file, so
    `gridLoad.ts` carried hand-copied Lima constants (`AEP_OHIO_RETAIL_GWH = 48_653`). This pins
    what the feed must deliver so the presentation tier can read the denominators instead of
    re-declaring them: the *cited* service chain, and the utility/BA figures themselves.
    """
    by_name = _feeds_by_name(bundle)
    assert "grid" in by_name, "the reference build must carry the grid backdrop feed"
    assert by_name["grid"]["kind"] == "object"
    grid = _rows(bundle, by_name["grid"])[0]

    # The service chain is cited, never asserted — every identification carries its source.
    chain = grid["serving_utility"]
    for field in ("utility", "holding_company", "balancing_authority", "rto", "retail_regulator"):
        fact = chain[field]
        assert fact["value"], f"serving_utility.{field} is empty"
        assert fact["citation"], f"serving_utility.{field} carries no citation"

    # The denominators the report's "% of the utility's entire retail sales" line divides by.
    assert grid["utility_profile"]["retail_sales_gwh"]["value"] > 0
    assert grid["ba_profile"]["annual_load_gwh"]["value"] > 0
    # Lima has a disclosed campus, so the load-share block is present and cited.
    share = grid["load_share"]
    assert share is not None
    assert share["share_of_utility_pct"]["value"] > 0
    assert share["state_retail_gwh"]["value"] > 0


def test_grid_backdrop_is_present_for_a_facility_less_peer(
    site_bundle: Callable[[str], Path],
) -> None:
    """The grid backdrop describes the *place*, not the campus — so a facility-less peer carries
    it with `load_share` null (#1642). This is why it can sit on the backdrop floor at all: a
    thin site gets the real electric-service chain rather than a lock."""
    out = site_bundle("toledo")  # no disclosed facility
    by_name = _feeds_by_name(out)
    assert "grid" in by_name, "a facility-less peer still carries its grid backdrop"
    grid = _rows(out, by_name["grid"])[0]
    assert grid["serving_utility"]["utility"]["value"], "the peer's serving utility is identified"
    assert grid["load_share"] is None, "no disclosed campus ⇒ no fabricated load share"
    # And the floor it belongs to is intact — grid joining BACKDROP_FLOOR_FEEDS must not have
    # knocked a real backdrop site down a tier.
    assert _manifest(out)["readiness"]["domains"]["backdrop"] == "live"


def _bundles_carrying(*feeds: str) -> list[str]:
    """The committed bundle fixtures whose manifest carries all of ``feeds``.

    Discovered rather than listed so a bundle that *gains* a feed is covered the moment it
    ships — Urbana joined this set only when #1769 un-stuck its `load_share`, and a hardcoded
    list would have quietly left the new pairing unguarded.

    Empty is an error, not an empty parametrization: a moved bundle root or a renamed feed
    would otherwise collect zero cases and report green, disarming the guard in exactly the
    silent way #1769 is about.
    """
    wanted = set(feeds)
    found = sorted(
        m.parent.name
        for m in (REPO_ROOT / "web" / "sites").glob("*/manifest.json")
        if wanted <= {f["name"] for f in json.loads(m.read_text(encoding="utf-8"))["feeds"]}
    )
    if not found:
        raise AssertionError(
            f"no committed bundle under {REPO_ROOT / 'web' / 'sites'} carries all of "
            f"{sorted(wanted)} — the guard would collect zero cases and pass vacuously"
        )
    return found


@pytest.mark.parametrize("slug", _bundles_carrying("grid", "economics-demand-pressure"))
def test_grid_and_demand_pressure_agree_on_the_campus_load(slug: str) -> None:
    """The `grid` and `economics-demand-pressure` feeds must not fork the campus load.

    Both express the SAME quantity — ``PowerBasis.facility_draw`` central (#87) — and both are
    rendered on `/economy/grid`, the grid backdrop's denominators table directly above the
    demand-pressure block. They are produced by different modules (`watermark.grid.utility` vs
    `watermark.economics.energy`) from committed artifacts regenerated at different times, so
    they drift silently: Fort Wayne shipped 113.9 MW / 898.0 GWh on one and 117.0 MW / 922.4 GWh
    on the other, a visible contradiction one scroll apart, because its grid profile predated
    GP-D's power-basis work (#1641) while its demand-pressure was freshly derived (#1642, E3).

    This pins the shared figures across the committed bundles so the next divergence fails here
    rather than on the page. It is deliberately an EQUALITY, not a tolerance: both round the same
    float to one decimal, so any difference at all means one artifact is stale.
    """
    fixture = REPO_ROOT / "web" / "sites" / slug
    by_name = _feeds_by_name(fixture)
    grid = _rows(fixture, by_name["grid"])[0]
    pressure = _rows(fixture, by_name["economics-demand-pressure"])[0]

    share = grid["load_share"]
    assert share is not None, f"{slug} has a demand-pressure feed, so its campus load must exist"
    assert share["campus_load_mw"]["value"] == pressure["facility_draw_mw"]["value"], (
        f"{slug}: grid campus_load_mw != demand-pressure facility_draw_mw — one artifact is "
        "stale; regenerate both from the current power basis"
    )
    assert (
        share["annual_consumption_gwh"]["value"] == pressure["annual_consumption_gwh"]["value"]
    ), f"{slug}: the two feeds disagree on annual consumption at the same load factor"
    assert share["load_factor"]["value"] == pressure["load_factor"]["value"]
    # The state share is the one denominator both feeds resolve independently — pin it too, so a
    # divergence in the *state* retail series (not just the campus load) is caught as well.
    assert share["share_of_state_pct"]["value"] == pressure["demand_share_pct"]["value"], (
        f"{slug}: grid share_of_state_pct != demand-pressure demand_share_pct"
    )


def test_degenerate_grid_profile_feed_is_dropped(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #1364 present-but-empty guard on the grid axis (#1642). A stale YAML with zeroed
    utility/BA denominators establishes neither whose grid nor how big, so it must be DROPPED —
    not shipped as a `count == 1` shell that floats the backdrop domain to `live`. Since `grid`
    is a floor feed, dropping it correctly costs the site its `live` backdrop."""
    from watermark.grid.utility import load_grid_profile
    from watermark.site import export as export_mod

    settings = Settings(data_dir=REPO_ROOT / "data")
    real = load_grid_profile(settings)
    assert real is not None and real.has_real_denominators

    degenerate = real.model_copy(deep=True)
    degenerate.utility_profile.retail_sales_gwh.value = 0.0
    degenerate.ba_profile.annual_load_gwh.value = 0.0
    assert not degenerate.has_real_denominators
    monkeypatch.setattr(export_mod, "load_grid_profile", lambda *a, **k: degenerate)

    out = tmp_path_factory.mktemp("degenerate-grid") / "b"
    export_mod.export_bundle(
        settings, out_dir=out, generated_at="2026-01-01T00:00:00+00:00", skip_embeddings=True
    )
    manifest = _manifest(out)
    assert "grid" not in {f["name"] for f in manifest["feeds"]}, (
        "a zeroed-denominator grid profile was shipped as a feed"
    )
    assert manifest["readiness"]["domains"]["backdrop"] == "seeded", (
        "a dropped floor feed must cost the backdrop domain its `live` grade, not pass silently"
    )


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
    a rename/removal), the ``readiness`` block must equal the fresh export's, and the committed
    manifest must stay internally consistent. Refresh it (see ``web/sites/README.md``) on drift.

    The readiness pin (#1770) was WPAFB-only (#1660, ME-A) until Urbana drifted the other way —
    shipping ``record: live`` over a zero-length ``records`` feed, a stale claim from an older
    export that survived because every other check here is contract-shaped, not evidence-shaped.
    Readiness is a **standing** property recomputed at every export, so a committed snapshot lags
    its own evidence in either direction the moment a source lands or dries up; pinning it for
    every contract-tested bundle is the guard, and it must not depend on the contract version
    also having moved.
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

    assert sample["readiness"] == exported_manifest["readiness"], (
        f"committed {fixture_dir.name} readiness drifted from a fresh export — re-export the "
        "bundle (see web/sites/README.md); an ingest that moves a domain must re-export its site"
    )

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
    _assert_fixture_tracks_export(COMMITTED_BUNDLES / "fort-wayne", _manifest(fort_wayne_bundle))


def test_urbana_sample_bundle_tracks_the_export_contract(urbana_bundle: Path) -> None:
    """The committed Urbana fixture tracks `watermark --site urbana export` (#797) — the network's
    third live site, promoted 2026-07-01."""
    _assert_fixture_tracks_export(COMMITTED_BUNDLES / "urbana", _manifest(urbana_bundle))


def test_wpafb_committed_bundle_is_fresh(wpafb_bundle: Path) -> None:
    """The committed ``web/sites/wpafb/`` bundle must track ``watermark --site wpafb export`` — and
    in particular its **readiness must not lag its own evidence on disk** (#1660, ME-A).

    The original defect this guards: #1397 ingested the two ``permits-epa`` records (the US-EPA
    Sole Source Aquifer designation + the CERCLA §120 Federal Facility Agreement) that clear
    ``RECORD_LIVE_THRESHOLD``, but the committed bundle was never re-exported — so it shipped
    ``tier: backdrop`` / ``record: absent`` with a 0-length ``records`` feed while the exporter
    (and ``test_wpafb_exports_at_case_tier``) already produced ``tier: case`` / ``record: live``.
    The readiness pin that caught it now lives in ``_assert_fixture_tracks_export`` itself, for
    every contract-tested bundle (#1770); what stays here is the site-specific half — the
    ``records`` feed pinned to the two extracted-tree paths, which shouldn't generalize."""
    fixture = COMMITTED_BUNDLES / "wpafb"
    _assert_fixture_tracks_export(fixture, _manifest(wpafb_bundle))

    # The record domain is live because the site owns exactly its two in-scope agency records;
    # pin the committed feed to those extracted-tree source paths so a dropped/renamed record
    # (readiness silently falling back to seeded/absent on disk) fails here, not in production.
    committed_records = {r["rel"] for r in _rows(fixture, _feeds_by_name(fixture)["records"])}
    assert committed_records == {
        "wpafb/ssa-53fr15876.epa.yaml",
        "wpafb/cercla-ffa-1991.epa.yaml",
    }, f"committed wpafb records feed drifted, got {sorted(committed_records)}"


def test_every_committed_bundle_readiness_matches_its_own_feed_counts() -> None:
    """Every committed bundle's ``readiness`` block must be the one its **own** feed counts imply
    (#1770) — the standing, whole-fleet half of the drift guard.

    The fresh-export pin above reaches only the four contract-tested sites; re-exporting all ~26
    to cover the rest would cost the suite a full-fleet export. This costs nothing:
    ``compute_readiness`` is a pure function of ``(profile, feed counts)``, and a manifest carries
    both its own counts *and* the block that was derived from them, so self-consistency is
    checkable without re-exporting anything. It is exactly the check Urbana's committed
    ``record: live`` over a zero-length ``records`` feed failed — a stale claim from an older
    export, on a site the WPAFB-only pin didn't cover.

    Half the *staleness* class comes free: the profile side is read live, so a facility that
    gains instrument grounding, or a site that gains a registered story, without a bundle refresh
    fails here too. What this can't see is a corpus change that would move a feed count — only a
    re-export moves those, which is what the four pinned sites are for.

    (The committed bundles are lean — ``passages`` / ``passage-embeddings`` are dropped, see
    ``web/sites/README.md``. Neither is a ``READINESS_FEED_NAMES`` member, so the trim can't
    perturb the recompute; and were a readiness feed ever trimmed, this fails loudly rather than
    recomputing a quietly-wrong block.)
    """
    from watermark.site.readiness import compute_readiness

    bundles = sorted(d for d in COMMITTED_BUNDLES.iterdir() if (d / "manifest.json").is_file())
    assert bundles, f"no committed site bundles under {COMMITTED_BUNDLES}"

    offenders: list[str] = []
    for bundle_dir in bundles:
        manifest = _manifest(bundle_dir)
        slug = manifest["site"]
        if slug != bundle_dir.name:
            offenders.append(f"{bundle_dir.name}: manifest declares site {slug!r}")
            continue
        if slug not in SITES:
            offenders.append(f"{slug}: committed bundle for a slug not in watermark.sites.SITES")
            continue
        feed_counts = {f["name"]: f["count"] for f in manifest["feeds"]}
        implied = compute_readiness(get_profile(slug), feed_counts)
        if implied != manifest["readiness"]:
            offenders.append(f"{slug}: committed {manifest['readiness']} != implied {implied}")

    assert not offenders, (
        "committed bundle readiness disagrees with the bundle's own feed counts — re-export the "
        "site(s) (see web/sites/README.md):\n" + "\n".join(offenders)
    )


# --- Backdrop-tier network sites (#1220 / #1224) --------------------------------------------
# The epic's promotion-candidate proof: the backdrop-staged sites bundle at `backdrop` tier off
# their committed floor data alone (no fabricated corpus), and the true stubs stay `stub`. We
# assert the derived readiness end-to-end through the real export rather than committing ~370
# unrendered fixture files for these non-selectable sites (their bundles regenerate on promotion).
@pytest.mark.parametrize("slug", ["toledo", "west-union"])
def test_backdrop_staged_site_exports_at_backdrop_tier(
    slug: str, site_bundle: Callable[[str], Path]
) -> None:
    manifest = _manifest(site_bundle(slug))
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "backdrop", f"{slug} should be a Backdrop site, got {readiness}"
    domains = readiness["domains"]
    # The floor is live; nothing above it is scaffolded (the epic's additive rule).
    assert domains["backdrop"] == "live"
    for above_floor in ("facility", "places", "record"):
        assert domains[above_floor] == "absent", f"{slug} {above_floor} must not scaffold"


def test_findlay_exports_at_case_tier(site_bundle: Callable[[str], Path]) -> None:
    """Findlay's floor (economics-baseline, consumer-energy, rsei) is committed. Two above-floor
    domains are live: ``record`` from the #1465 flood-mitigation-chain ingest (the FEMA Flood
    Mitigation Assistance $24M obligation + the USACE Blanchard-watershed feasibility Review Plan,
    two in-scope ``permits-epa`` extractions clearing ``RECORD_LIVE_THRESHOLD``), and ``facility``
    from the disclosed One Power "Findlay Megawatt Hub" / MARA 150 MW take-or-pay ``SiteFacility``
    (#1459). Facility is graded ``live`` on DOCUMENTARY DEPTH (#1630): unlike the site-plan-grounded
    Urbana/Sidney facilities, the MW here is a `[verified]` filed disclosure (One Power's SEC Form
    S-1: 30 MW energized / 150 MW contracted — ``it_load_grounding`` is ``disclosure``), an
    instrument-grounded load, not a screening bracket — so it lifts the domain, not merely seeds it.
    ``story`` is ``seeded`` (the committed per-site leads board,
    ``data/site/findlay/leads.yaml``, is a leads-first resting state — Findlay is not yet in
    ``STORY_SLUGS``). ``places`` went ``absent`` -> ``live`` in #1462, off the committed Megawatt
    Hub parcel assemblage. So four of the five domains are live and only ``story`` is short of it;
    this still needs its own test rather than the backdrop parametrize group (which asserts
    ``record`` stays unscaffolded)."""
    out = site_bundle("findlay")
    manifest = _manifest(out)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"findlay should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["record"] == "live"
    # The disclosed SiteFacility's [verified] filed load disclosure (SEC S-1) grades facility live —
    # instrument-grounded documentary depth, not its demand-pressure feed (#1630 / #1459).
    assert domains["facility"] == "live"
    # ``story`` is seeded off the committed leads board, not a registered guided walk.
    assert domains["story"] == "seeded"
    # ``places`` is live off COMMITTED campus geometry, not scaffolding (#1462): the eight Allen
    # Township parcels standing in three One Energy vehicles (One Energy Enterprises LLC, OEE XX
    # LLC, OEE XXX LAND LLC) — 108.65 ac CAMA / 105.873 ac planar, ``reference/findlay/
    # parcel-assemblage.geojson`` — which surface as the ``geo/campus`` feed. The trigger is the
    # evidence: this asserts the FEED, so a profile relpath pointing at a missing file (which is
    # what it did before #1462) cannot float the domain.
    assert domains["places"] == "live", "findlay places must be live off committed campus geometry"
    campus = _feeds_by_name(out)["geo/campus"]
    assert campus["count"] == 8, f"expected the 8 Megawatt Hub parcels, got {campus}"

    # ``record`` is live off real, in-scope agency records — never scaffolding. The feed is
    # pinned by exact source path so a stray artifact can't quietly float the domain. It began
    # (#1465) as the two flood records; #1460 added the City of Findlay WPCC's own NPDES
    # instrument set, the TMDL phosphorus-allocation chain, the WARN pair and the Brownfield
    # Round 11 awards; #1463 added the filed appellate opinion. Note the two record-bearing
    # collections: ``oepa/findlay/**`` reaches this site because ``*/findlay`` is derived from the
    # slug (#1405), which also subtracts it from Lima's reference-build scope (#1505).
    records = _rows(out, _feeds_by_name(out)["records"])
    assert {r["rel"] for r in records} == {
        "findlay/brownfield/round-11-hancock-2026.award.yaml",
        "findlay/flood/fema-fma-obligation-2026.epa.yaml",
        "findlay/flood/usace-blanchard-review-plan-2024.epa.yaml",
        "findlay/governance/litigation-one-energy-v-allen-twp.yaml",
        "findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml",
        "findlay/warn/goodyear-tall-timbers-mold-2026.warn.yaml",
        "findlay/warn/michigan-sugar-findlay-2025.warn.yaml",
        "oepa/findlay/2PD00008.1abaf306.npdes.yaml",
        "oepa/findlay/2PD00008.fs.npdes.yaml",
        "oepa/findlay/2PD00008.npdes.yaml",
    }, f"unexpected findlay records feed, got {sorted(r['rel'] for r in records)}"
    assert len(records) == 10
    # The WARN pair publishes under ``labor`` — the group added for #1460 (contract 1.47.0),
    # because a state-filed plant-closing notice is not a permit, an order, an award, a deed or
    # a pleading, and filing it under the nearest of those would misrepresent the instrument.
    assert {r["rel"] for r in records if r["group"] == "labor"} == {
        "findlay/warn/goodyear-tall-timbers-mold-2026.warn.yaml",
        "findlay/warn/michigan-sugar-findlay-2025.warn.yaml",
    }
    # #1463's governance ingest contributes exactly ONE record, and it needed no new group: the
    # structured read of *One Energy Ents., Inc. v. Allen Twp. Bd. of Trustees*, 2026-Ohio-405
    # carries a ``case:`` block, so it publishes into the ``litigation`` group added for #1724.
    # Every other governance artifact — the adopted township zoning resolution, the proposed
    # data-center amendment, the SB 52 gap, the city moratorium gap, the timeline — is corpus,
    # NOT a record: there is no zoning ``RecordGroup`` and minting one to publish a proposal
    # that is not yet law would cost a contract bump plus a fleet-wide bundle regeneration.
    assert {r["rel"] for r in records if r["group"] == "litigation"} == {
        "findlay/governance/litigation-one-energy-v-allen-twp.yaml",
    }
    assert not [
        r
        for r in records
        if r["rel"].startswith("findlay/governance/") and r["group"] != "litigation"
    ], "only the filed court instrument may publish as a record from the governance set"

    # The site's source-document catalog spans all four in-scope collections: the permit set
    # under ``oepa/``, the WARN + brownfield + governance instruments under ``findlay/``, the
    # grid-posture captures under ``grid/`` (#1464 — the Rocky Ford OPSB pair, AEP's PJM
    # large-load deck, and Schedule DCT as filed), and the Third District's slip opinion under
    # ``legal/`` (#1463). Before #1460 all of them were empty, so a site with a live ``record``
    # domain published no documents at all.
    doc_collections = _rows(out, _feeds_by_name(out)["documents"])
    assert {c["slug"] for c in doc_collections} == {"findlay", "grid", "legal", "oepa"}
    docs = {e["rel"] for c in doc_collections for e in c["entries"]}
    assert "oepa/findlay/2PD00008.fs.pdf" in docs
    assert "findlay/warn/GoodyearTireRubberCompany.pdf" in docs
    # ``grid/findlay/**`` reaches this site because ``*/findlay`` is derived from the slug (#1405),
    # which is also what keeps a Hancock County siting docket out of Lima's whole-tree reference
    # build (#1505) — the ``grid/`` collection root is otherwise basin-shared.
    assert "grid/findlay/Rocky Ford 138 kV Station Project Letter of Notification.pdf" in docs
    # ...and the grid-posture extractions are deliberately NOT records: a siting docket and a
    # tariff posture get no ``RecordGroup``, exactly as the Lima "Lyka" project record chose
    # (#1476), so those four YAML files add nothing to the ``records`` feed.
    assert not [r for r in records if r["rel"].startswith("grid/")]
    # ``legal/one-energy-v-allen-twp/**`` reaches this site the same way — by being named in
    # ``_FINDLAY.corpus_relpaths`` — and it is filed by CASE rather than by site, following the
    # ``legal/thor-v-urbana`` precedent that Urbana's scope established (#1724).
    assert "legal/one-energy-v-allen-twp/2026-Ohio-405.pdf" in docs
    assert "findlay/governance/Zoning-Book-Effective-05-11-26.pdf" in docs


def test_urbana_record_domain_publishes_its_worked_corpus(urbana_bundle: Path) -> None:
    """Urbana's ``record`` is live off the two extractions its corpus actually holds (#1724).

    The defect this pins: the site had a structured read of the Thor v. Urbana federal complaint
    and a recorded land-assembly register — both reviewed, both cited — and published a
    **zero-length** ``records`` feed, because the site-tier classifier's genre map had no bucket
    for either shape. ``record`` then read ``seeded`` over a corpus that was neither absent nor
    thin, which is the mirror image of the stale ``record: live`` that #1724 opened on: one lied
    about the manifest, this lied about the feed.

    Two genres carry them, and the pair is deliberate. ``land-assembly`` is *not* ``deeds``:
    that group is instrument-level (a vision read of one recorder PDF), while a register is a
    compiled transfer chain sourced to a county CAMA layer. Filing the register under ``deeds``
    would present a compilation as an instrument read.
    """
    manifest = _manifest(urbana_bundle)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["domains"]["record"] == "live", (
        f"urbana record should be live off its two extractions, got {readiness}"
    )
    assert readiness["tier"] == "case"

    records = _rows(urbana_bundle, _feeds_by_name(urbana_bundle)["records"])
    by_rel = {r["rel"]: r for r in records}
    assert set(by_rel) == {
        "urbana/land-assembly.yaml",
        "urbana/litigation-thor-v-urbana.yaml",
    }, f"urbana records feed drifted, got {sorted(by_rel)}"
    assert by_rel["urbana/land-assembly.yaml"]["group"] == "land-assembly"

    filing = by_rel["urbana/litigation-thor-v-urbana.yaml"]
    assert filing["group"] == "litigation"
    # The payload is the whole filing, not the `case:` docket stub — the counts pleaded are the
    # substance, and they sit beside the block.
    assert "counts" in filing["fields"] and "case" in filing["fields"]
    # It joins to the instrument it was read from: the complaint is in Urbana's own document
    # catalog now that `legal/thor-v-urbana` is in its corpus scope (the other half of #1724).
    assert filing["source_doc_rel"] == "legal/thor-v-urbana/1.pdf"
    assert filing["source_doc_render_class"] == "pdf"
    docs = _rows(urbana_bundle, _feeds_by_name(urbana_bundle)["documents"])
    assert filing["source_doc_rel"] in {e["rel"] for c in docs for e in c["entries"]}


def test_wpafb_exports_at_case_tier(wpafb_bundle: Path) -> None:
    """WPAFB's floor (economics-baseline, consumer-energy, rsei, grid) is committed, and three
    above-floor domains are live off real evidence.

    ``record`` came first (#1397): the US-EPA Sole Source Aquifer designation (53 FR 15876) and
    the CERCLA §120 Federal Facility Agreement are two in-scope ``permits-epa`` extractions
    clearing ``RECORD_LIVE_THRESHOLD``. ``facility`` and ``places`` followed with the federal-
    enclave seam (#1664), and neither is scaffolding: ``facility`` is the installation itself,
    graded ``live`` because that same filed FFA is its instrument grounding (documentary depth,
    #1630 — no IT load is invented for a base); ``places`` is the DoD MIRTA boundary, the only
    land path an enclave off the county tax rolls can ever have. ``story`` stays ``absent`` —
    WPAFB is not in ``STORY_SLUGS`` and nothing here changes that. The tier stays ``case``
    (``reference`` needs all five). Its own test rather than the backdrop parametrize group,
    which asserts everything above the floor stays unscaffolded."""
    out = wpafb_bundle
    manifest = _manifest(out)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"wpafb should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["record"] == "live"
    assert domains["facility"] == "live"
    assert domains["places"] == "live"
    assert domains["story"] == "absent", "wpafb story must not scaffold"

    # The facility is the ENCLAVE, not a data center: the `facility` feed row must say so, and
    # the campus columns must be absent rather than null-as-undisclosed. Its enclave detail is a
    # separate feed, and `geo/enclave` is the geometry that lifted `places`.
    by_name = _feeds_by_name(out)
    facilities = _rows(out, by_name["facility"])
    assert [f["kind"] for f in facilities] == ["federal_installation"]
    assert facilities[0]["it_load_mw"] is None
    assert facilities[0]["cooling_model"] == "off"
    assert "enclave" in by_name
    assert "geo/enclave" in by_name
    # No demand-pressure feed: an installation has no derivable campus load to size one against.
    assert "economics-demand-pressure" not in by_name

    # The toxics severance the enclave feed exists to state — the base reports TRI from a county
    # this site's backdrop inventory does not cover.
    enclave = json.loads((out / by_name["enclave"]["path"]).read_text(encoding="utf-8"))
    assert enclave["toxics"]["scope_disagreement"] is True
    assert enclave["toxics"]["tri_county_fips"] != enclave["toxics"]["site_rsei_fips"]

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


def test_troy_piqua_exports_at_case_tier(site_bundle: Callable[[str], Path]) -> None:
    """Troy/Piqua's floor (economics-baseline, consumer-energy, rsei) is committed (#1481). The
    disclosed "Project Klondike" ``SiteFacility`` is SCREENING-only (a floor-area [inference]
    bracket, MW [open]) → ``facility`` grades ``seeded`` on documentary depth (#1630), NOT live.
    ``places`` and ``record`` carry the tier: the committed J5 campus assemblage (#1483) and the
    Piqua WWTP NPDES permit + fact sheet (1PD00008) + DMR are
    all in-scope now that #1484 relocated the two OEPA extractions under ``oepa/troy-piqua/`` —
    which reaches this site because ``*/troy-piqua`` is derived from the slug (#1405; the profile
    enumerated ``oepa/troy-piqua`` until then, now dropped as redundant) — three extractions
    clearing ``RECORD_LIVE_THRESHOLD`` (previously the two permit extractions orphaned in the flat
    ``oepa/`` tree, leaving only the sub-threshold DMR). Its own test rather than the shared
    parametrize group above, since that group asserts ``record``/``facility`` stay fully
    unscaffolded."""
    out = site_bundle("troy-piqua")
    manifest = _manifest(out)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"troy-piqua should be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    # Screening-only facility → seeded, not live (#1630); places + record carry the case tier.
    assert domains["facility"] == "seeded"
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


def test_sidney_exports_at_case_tier(site_bundle: Callable[[str], Path]) -> None:
    """Sidney rose ``backdrop`` -> ``case``, and TWO domains moved to get it there.

    ``places`` moved first, on #1379's committed campus geometry:
    ``data/reference/sidney/parcel-assemblage.geojson`` is the Shelby County auditor CAMA record
    of the single parcel deeded to Amazon Data Services, Inc., which the exporter composes into
    the ``geo/campus`` feed that ``PLACES_GEOMETRY_FEED`` gates on.

    ``record`` moved second, on #1383's standing regulatory watch: it landed the City of Sidney
    WWTP's issued NPDES permit + 2022 fact sheet (``oepa/sidney/1PD00009.npdes.yaml``). Its
    ``oepa/sidney`` and ``grid/sidney`` sub-collections read into Sidney rather than leaking into
    Lima's whole-tree reference scope (the #1505 rule) because both are eponymous — derived from
    the slug by ``*/sidney`` since #1405, so the profile no longer enumerates them. Two
    ``permits-npdes`` records >= ``RECORD_LIVE_THRESHOLD``. That is
    readiness behaving as the STANDING property it is — it rose because sources landed, twice,
    independently.

    What did NOT move is equally the point, and pinning it here is what makes this a guard:
    ``facility`` stays ``seeded`` because the #1630 downgrade still holds — AWS discloses no floor
    area and no interconnection figure, so the IT load is an investment-scaled ``[inference]``
    bracket, never a disclosure. Committing land does not ground a load, and neither do permits:
    five state instruments have now issued across this project and not one states a megawatt.
    ``story`` remains absent. A future change that floats either off geometry or paperwork alone
    fails here."""
    manifest = _manifest(site_bundle("sidney"))
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"sidney should now be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "seeded"  # disclosed but screening-only → seeded (#1630)
    assert domains["places"] == "live"  # committed campus geometry (#1379)
    assert domains["record"] == "live"  # WWTP permit + DMR >= RECORD_LIVE_THRESHOLD (#1383)
    assert domains["story"] == "absent"

    # The geometry that activated the domain is the campus parcel itself, not a stub.
    bundle = site_bundle("sidney")
    ref = _feeds_by_name(bundle)["geo/campus"]
    campus = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))["features"]
    assert [f["properties"]["parcel_id"] for f in campus] == ["26-03-201-002"]
    assert campus[0]["properties"]["owner"] == "AMAZON DATA SERVICES INC"


def test_wilmington_exports_at_case_tier_on_committed_corridor_geometry(
    site_bundle: Callable[[str], Path],
) -> None:
    """Wilmington's ``places`` domain went absent -> live when #1470 committed the corridor
    geometry. The TIER was already ``case``: #1405 derived a site's corpus scope from its slug, so
    the ``oepa/wilmington`` permits that had been sitting outside the very site they document read
    into it and floated ``record`` to live. Two independent domains, two issues — which is
    readiness behaving as the standing property it is.

    Same geometry shape as Sidney's and Van Wert's pins above, with one difference that matters:
    ``data/reference/wilmington/parcel-assemblage.geojson`` is NOT one campus. It is the Clinton
    County auditor CAMA record of SEVEN contiguous parcels in two legally distinct groups — three
    DEEDED to Amazon Data Services, Inc. and four that are a REZONING SCHEDULE (ordinances
    O-26-04 to O-26-07) still in their original owners' names — and the exporter composes all seven
    into the ``geo/campus`` feed that ``PLACES_GEOMETRY_FEED`` gates on. The ``corridor_role``
    property is what keeps a reader from collapsing them into one 1,023-ac campus; this test pins
    that it survives the export.

    What did NOT move is equally the point: ``facility`` remains ``seeded`` because the #1630
    downgrade holds — the campus IT load is a floor-area SCREENING bracket (#1468), and committing
    land does not ground a load, least of all land whose zoning is in remand; ``story`` is absent.
    A future change that floats either off geometry alone fails here."""
    manifest = _manifest(site_bundle("wilmington"))
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"wilmington should now be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "seeded"  # disclosed but screening-only → seeded (#1630)
    assert domains["places"] == "live"  # committed corridor geometry (#1470)
    assert domains["record"] == "live"  # oepa/wilmington permits, in scope since #1405
    assert domains["story"] == "absent"

    # The geometry that activated the domain is the corridor itself, and it stays legible as two
    # kinds of claim rather than one campus.
    bundle = site_bundle("wilmington")
    ref = _feeds_by_name(bundle)["geo/campus"]
    corridor = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))["features"]
    assert len(corridor) == 7
    props = [f["properties"] for f in corridor]
    owned = [p for p in props if p["corridor_role"] == "campus_holding"]
    assert {p["owner"] for p in owned} == {"AMAZON DATA SERVICES INC"}
    assert next(p["parcel_id"] for p in owned) == "285-13-02-01-0000-00"  # 1488 S US 68
    rezoned = [p for p in props if p["corridor_role"] == "petitioned_rezoning"]
    assert len(rezoned) == 4 and not any("ARDENT" in p["owner"].upper() for p in rezoned)


def test_bowling_green_exports_at_case_tier_on_committed_assembly_geometry(
    site_bundle: Callable[[str], Path],
) -> None:
    """Bowling Green rose ``backdrop`` -> ``case`` when #1436 committed the land assembly.

    Two domains moved between the last committed bundle and this one, from two different issues,
    which is readiness behaving as the standing property it is: ``places`` absent -> live on this
    geometry, and ``record`` absent -> live from #1439's water-permit ingest, which had already
    landed on main while the committed bundle still showed the old value.

    The file behind ``geo/campus`` is FOUR kinds of claim, not one campus, and the ``role``
    property is what keeps them apart — this pins that the distinction survives the export.
    Twelve parcels are the recorded LIAMES, LLC holding; the other three are a rezoning still in
    its owner's name, the parcel of record for a *different* facility's air permit, and a
    competitor's colo 4.83 miles away in another jurisdiction. A reader who sums the acreage of
    this feed gets a number that describes no thing.

    What did NOT move is equally the point. ``facility`` stays ``seeded``: the #1630 downgrade
    holds, because the campus IT load is still the disclosed ~180 MW peak carried as
    ``[reference]``, and committing land does not ground a load. ``story`` stays absent. A future
    change that floats either off geometry alone fails here.
    """
    bundle = site_bundle("bowling-green")
    manifest = _manifest(bundle)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"bowling-green should now be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "seeded"  # ~180 MW peak is [reference], not an instrument (#1630)
    assert domains["places"] == "live"  # committed land-assembly geometry (#1436)
    assert domains["record"] == "live"  # the 2PD00009 water instruments (#1439)
    assert domains["story"] == "absent"

    ref = _feeds_by_name(bundle)["geo/campus"]
    features = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))["features"]
    assert len(features) == 15
    props = [f["properties"] for f in features]

    # (1) The campus: twelve parcels, one owner, 775.020 ac deeded.
    assembly = [p for p in props if p["parcel_role"] == "liames_assembly"]
    assert len(assembly) == 12
    assert {p["owner"] for p in assembly} == {"LIAMES LLC"}
    assert round(sum(p["acres"] for p in assembly), 3) == 775.020
    # The county tax roll bills eight of them to Meta's own headquarters — the operator
    # attribution corroborated in the record, independent of the company's announcement.
    assert sum("META WAY" in (p["owner_mailing_address"] or "") for p in assembly) == 8

    # (2) The eight small parcels whose M-1 zoning was still inside its referendum window at pull
    # time. They are flagged rather than quietly folded into the campus, and they still read their
    # PRE-rezoning districts because no published Wood County layer carries the 2026-07-07 grant.
    contestable = [p for p in assembly if p["rezoning_contestable_2026_07_07"]]
    assert len(contestable) == 8
    assert round(sum(p["acres"] for p in contestable), 2) == 21.37
    assert {z["district"] for p in contestable for z in p["township_zoning_2025_11_13"]} == {
        "A-1: Agricultural",
        "R-4: Multiple Dwelling",
    }
    # while the four core tracts are already M-1, from the 2023 rezonings.
    core = [p for p in assembly if not p["rezoning_contestable_2026_07_07"]]
    assert len(core) == 4
    assert all(
        p["township_zoning_2025_11_13"][0]["district"] == "M-1: Light Industrial" for p in core
    )

    # (3) The three rows that are NOT the holding, each a different claim.
    others = {p["parcel_role"]: p for p in props if p["parcel_role"] != "liames_assembly"}
    assert set(others) == {"rezoning_pending", "apollo_permit_situs", "oppidan_colo"}
    assert others["rezoning_pending"]["owner"] == "A SCHALLER LIMITED PARTNERSHIP"
    assert others["apollo_permit_situs"]["owner"] == "JJJ FAMILY PROPERTIES LLC"
    assert others["oppidan_colo"]["owner"] == "CLOP BOWLING GREEN OH LLC"
    assert "LIAMES" not in {p["owner"] for p in others.values()}


def test_van_wert_exports_at_case_tier_on_committed_campus_geometry(
    site_bundle: Callable[[str], Path],
) -> None:
    """Van Wert rose ``backdrop`` -> ``case`` when #1403 committed the campus geometry.

    Same shape as Sidney's pin above and the same reason: the floor was pulled and everything
    above it was a lead. ``places`` moved on evidence — ``data/reference/van-wert/
    parcel-assemblage.geojson`` is the Van Wert County auditor CAMA record of the five parcels
    deeded to QTS Van Wert LLC in June 2026, which the exporter composes into the ``geo/campus``
    feed that ``PLACES_GEOMETRY_FEED`` gates on.

    ``record`` then rose to ``live`` in #1405 — not on new evidence, on plumbing. The 2PD00006*VD
    permit and its fact sheet had been ingested and extracted since #837, but the extractions sat
    flat at ``data/extracted/oepa/`` while the site's scope reached only ``van-wert/``, so they
    rendered inside Lima's Allen-County record and Van Wert owned nothing. #1406 added the
    2PD00006*WD modification package and its draft public notice, so the domain now stands on
    four ``RecordItem``s rather than two — still the honest count (two permit cycles, each with
    its own notice-side document), not a fabricated breadth.

    The other two stay put, and pinning them is the point: ``facility`` remains ``seeded``
    because the #1630 downgrade holds (QTS declines to state capacity, so the IT load is an
    announced-ceiling ``[reference]`` bracket — committing land does not ground a load); ``story``
    is absent. A future change that floats either off geometry alone fails here.
    """
    bundle = site_bundle("van-wert")
    manifest = _manifest(bundle)
    assert manifest["contract_version"] == _CV
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case", f"van-wert should now be a Case site, got {readiness}"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["facility"] == "seeded"  # announced-ceiling bracket, not a disclosure (#1630)
    assert domains["places"] == "live"  # committed campus geometry (#1403)
    assert domains["record"] == "live"  # the 2PD00006 permit + fact sheet, in scope since #1405
    assert domains["story"] == "absent"

    # The records that activated the domain are this site's OEPA instruments — read from the
    # site-attributed subtree that mirrors their source at data/documents/oepa/van-wert/. The
    # two hash-infixed names are the *WD modification package and its draft public notice: Ohio
    # EPA re-serves the DAM's `permits/doc/` slot in place on modification, so both cycles' bytes
    # land under one basename and the fetcher's collision rule appends each file's own sha256
    # prefix (#1406).
    rels = sorted(r["rel"] for r in _rows(bundle, _feeds_by_name(bundle)["records"]))
    assert rels == [
        "oepa/van-wert/2PD00006.36a58063.npdes.yaml",
        "oepa/van-wert/2PD00006.f8aaad0a.npdes.yaml",
        "oepa/van-wert/2PD00006.fs.npdes.yaml",
        "oepa/van-wert/2PD00006.npdes.yaml",
    ]

    # The geometry that activated the domain is the recorded holding, not a stub — and the whole
    # holding, not just the anchor the issue was written against.
    ref = _feeds_by_name(bundle)["geo/campus"]
    campus = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))["features"]
    assert [f["properties"]["parcel_id"] for f in campus] == [
        "12-034459.0000",
        "17-034718.0000",
        "17-034718.0100",
        "17-034718.0200",
        "33-047500.0000",
    ]
    assert {f["properties"]["owner"] for f in campus} == {"QTS VAN WERT LLC"}


def test_ottawa_places_activates_on_a_brownfield_not_a_campus_siting(
    site_bundle: Callable[[str], Path],
) -> None:
    """Ottawa's ``places`` went ``absent`` -> ``live`` when #1420 committed the campus geometry —
    and this one is unlike every other geometry in the network, which is exactly why it is pinned.

    The land is the FORMER Sylvania/GTE/Philips Display Components CRT works at 700-804 N Pratt
    St: a closed plant under a $4.57M brownfield remediation, not a proposed or built data-center
    campus. Ottawa's profile carries ``facilities=()``. So this asserts the readiness model does
    what #1220 says it does — ``places`` activates on *committed geometry a map can be drawn
    from*, with no facility anywhere in sight — and that committing land does NOT drag ``facility``
    up with it. ``facility`` must stay ``absent``: a site with no disclosed facility has none,
    and a brownfield is not a siting.

    The tier does NOT move here (Ottawa was already ``case`` on its live ``record`` — the 2PD00028
    instrument set and the standing water watch), which is the difference from the Sidney and
    Van Wert pins above where ``places`` was the domain that carried the tier.
    """
    bundle = site_bundle("ottawa")
    manifest = _manifest(bundle)
    assert manifest["contract_version"] == _CV  # geo/campus composes from parcels_relpath
    readiness = manifest["readiness"]
    assert readiness["tier"] == "case"
    domains = readiness["domains"]
    assert domains["backdrop"] == "live"
    assert domains["places"] == "live"  # committed campus geometry (#1420)
    assert domains["record"] == "live"  # the 2PD00028 instruments + the water watch (#1422)
    # Committing land grounds no load — and here there is no facility to ground at all.
    assert domains["facility"] == "absent"
    assert domains["story"] == "absent"

    # Two contiguous parcels, two UNRELATED owners — a broken-up works, not one holding.
    ref = _feeds_by_name(bundle)["geo/campus"]
    campus = json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))["features"]
    assert [f["properties"]["parcel_id"] for f in campus] == ["322220000000", "322260000000"]
    assert {f["properties"]["owner"] for f in campus} == {
        "OTTAWA OH LLC",
        "VERHOFF PROPERTIES LLC",
    }
    assert sum(f["properties"]["acres"] for f in campus) == pytest.approx(38.234)


@pytest.mark.parametrize("slug", ["coshocton", "piketon", "sandusky"])
def test_stub_site_exports_at_stub_tier(slug: str, site_bundle: Callable[[str], Path]) -> None:
    readiness = _manifest(site_bundle(slug))["readiness"]
    assert readiness["tier"] == "stub", f"{slug} is profile-only, expected stub, got {readiness}"
    assert readiness["domains"]["backdrop"] != "live"


@pytest.fixture(scope="session")
def fort_wayne_bundle(site_bundle: Callable[[str], Path]) -> Path:
    """A Fort Wayne bundle exported off the committed corpus — the sibling site used to
    prove per-site content scope (#762). Hermetic: no network, same committed data."""
    return site_bundle("fort-wayne")


@pytest.fixture(scope="session")
def urbana_bundle(site_bundle: Callable[[str], Path]) -> Path:
    """An Urbana bundle (#782's validation candidate) — the sibling that still needs an **explicit**
    ``corpus_relpaths`` (``("permits/highland55", "legal/thor-v-urbana")`` — the Highland55
    land-assembly permit set and the filed complaint, #1328/#1724), because those are filed by
    project and by case and no rule derives them from a slug. Its own ``urbana/`` and ``oepa/urbana``
    prefixes are eponymous and dropped from the field since #1405, so it exercises the
    derived-plus-explicit scope. Hermetic: no network, same committed data."""
    return site_bundle("urbana")


@pytest.fixture(scope="session")
def wpafb_bundle(site_bundle: Callable[[str], Path]) -> Path:
    """A WPAFB bundle exported off the committed corpus — the network's federal-enclave site
    whose two ``permits-epa`` records (the SSA designation + the CERCLA FFA, #1397) lift ``record``
    to ``live`` / ``tier`` to ``case``. Backs the committed-bundle freshness guard below (#1660):
    the committed bundle silently drifted a full tier below its own evidence because no drift test
    covered it. Hermetic: no network, same committed data."""
    return site_bundle("wpafb")


@pytest.fixture(scope="session")
def springfield_bundle(site_bundle: Callable[[str], Path]) -> Path:
    """A Springfield bundle — a Mad River sibling that leaves ``corpus_relpaths`` unset (so it
    defaults to ``('springfield',)``) and has **no committed corpus**, exercising the #780
    *default* scope. Hermetic: no network, same committed data."""
    return site_bundle("springfield")


def _assert_corpus_feeds_lima_free(slug: str, bundle_dir: Path) -> None:
    """The reusable new-site smoke test (#762/#780): a sibling site's corpus-derived feeds must
    carry none of Lima's Allen-County-OH record.

    Several feeds are built by readers that once globbed the whole extracted tree (the timeline
    civic builders, the entity-graph subdivision/relation-class overlays, the flat
    ``data/scenarios`` dir); each is now bounded by the site's *effective* corpus scope. A site's
    scope is its two eponymous prefixes (``<slug>`` and the ``*/<slug>`` nesting inside an agency
    collection) plus any non-derivable ``corpus_relpaths`` — **never** the reference build's whole
    tree (only Lima resolves to ``include=None``).

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


def test_collection_nested_sibling_bundle_carries_no_lima_corpus(fort_wayne_bundle: Path) -> None:
    """Fort Wayne — a sibling whose corpus lives under an *agency* collection — is Lima-free
    (#762). Its IDEM (Indiana) records sit at ``idem/fort-wayne/``, which reached the site by an
    enumerated ``corpus_relpaths`` entry until #1405 made the ``*/<slug>`` nesting derivable. The
    profile now names nothing at all, and the subtree must still be the site's."""
    assert get_profile("fort-wayne").corpus_relpaths is None, "FW is fully derived since #1405"
    assert effective_corpus_scope(get_profile("fort-wayne")).contains("idem/fort-wayne/wqc.yaml")
    _assert_corpus_feeds_lima_free("fort-wayne", fort_wayne_bundle)


def test_explicit_scoped_sibling_bundle_carries_no_lima_corpus(urbana_bundle: Path) -> None:
    """Urbana — the sibling that still *needs* an explicit ``corpus_relpaths`` — is Lima-free
    (#762). Its corpus is filed by project and by case (``permits/highland55``,
    ``legal/thor-v-urbana``), which no rule derives from a slug, so this is the shape the field
    exists for after #1405 and the shape that must keep working."""
    assert get_profile("urbana").corpus_relpaths, "Urbana's project/case prefixes are not derivable"
    _assert_corpus_feeds_lima_free("urbana", urbana_bundle)


def test_default_scoped_sibling_bundle_carries_no_lima_corpus(springfield_bundle: Path) -> None:
    """The new-site smoke test (#780): a freshly-registered site on the **default** scope is also
    Lima-free. Springfield leaves ``corpus_relpaths`` unset (so its scope is the eponymous pair)
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
