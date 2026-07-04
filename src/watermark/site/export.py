"""Export the committed corpus into the typed content bundle under ``data/site/bundles/<slug>/``.

The site's data tier (issue #53, Tier 1): :func:`export_bundle` emits the versioned,
schema-validated JSON feeds the Astro/DeckGL frontend reads at build time, loading the
corpus through the shared loaders (``load_corpus``, ``build_timeline``,
``build_entity_graph``, ``load_people``, ``load_pois``, …) and the per-section builders
in this package (``records``, ``economics``, ``gismap``, …).

The output is **per network site** (#724/#727): each site's feeds land under
``data/site/bundles/<slug>/`` (the active site is ``settings.site``, from the global
``watermark --site <slug>`` flag / ``WATERMARK_SITE``), so the network's sites never clobber each
other. The committed, site-agnostic contract (``schemas/``, README, example manifest) stays
shared at ``data/site/bundle/``.

Layout written under ``out_dir`` (default ``data/site/bundles/<slug>``):

* ``manifest.json`` — bundle/contract version, ``generated_at``, and the feed index.
* ``schemas/<feed>.schema.json`` — one JSON Schema per feed, generated from the
  :mod:`watermark.site.feeds` models (serialization mode), so schema and code never drift.
* ``feeds/<feed>.json`` (or ``.ndjson`` for a large list) and ``feeds/geo/<feed>.geojson``.

The contract itself (README, schemas, an example manifest) is committed; the generated
``manifest.json`` + ``feeds/`` are regenerable and git-ignored (see the bundle README).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel

from watermark.candidates import (
    load_cloud_consumer_candidates,
    load_defense_contractors,
    load_defense_scan,
)
from watermark.civic.summarize import load_committed_summaries
from watermark.config import Settings, get_settings
from watermark.economics.baseline import load_baseline as load_econ_baseline
from watermark.economics.energy import load_consumer_energy, load_demand_pressure
from watermark.gleif import load_inventory as load_lei_inventory
from watermark.hydrology.model import ScenarioResult
from watermark.hypotheses import HYPOTHESES, Hypothesis, HypothesisAssessment, load_assessments
from watermark.logging import get_logger
from watermark.network import build_basin_network
from watermark.people import load_people
from watermark.pipeline.corpus import load_corpus
from watermark.pipeline.entities import build_entity_graph
from watermark.pipeline.timeline import build_timeline
from watermark.poi import load_pois
from watermark.rsei import load_inventory as load_rsei_inventory
from watermark.site import candidates as candidates_mod
from watermark.site import catalog as catalog_mod
from watermark.site import concepts as concepts_mod
from watermark.site import documents as documents_mod
from watermark.site import economics as economics_mod
from watermark.site import exhibits as exhibits_mod
from watermark.site import gismap as gismap_mod
from watermark.site import gleif as gleif_mod
from watermark.site import graph as graph_mod
from watermark.site import leads as leads_mod
from watermark.site import meetings as meetings_mod
from watermark.site import people as people_mod
from watermark.site import places as places_mod
from watermark.site import records as records_mod
from watermark.site import rsei as rsei_mod
from watermark.site.catalog_index import build_catalog_index
from watermark.site.embeddings import build_ask_embeddings
from watermark.site.feeds import (
    CONTRACT_VERSION,
    AskEmbeddingEntry,
    CandidateItem,
    CatalogItem,
    Citation,
    ConceptItem,
    DocumentCollectionItem,
    EntityNode,
    ExhibitItem,
    FeedKind,
    FeedRef,
    GeoFeatureCollection,
    LeadItem,
    Manifest,
    MeetingItem,
    PersonItem,
    PlaceItem,
    RecordItem,
    RelationshipEdge,
    TimelineEntry,
)
from watermark.sites import (
    active_profile,
    effective_corpus_scope,
    is_reference_site,
    site_scoped_path,
)

log = get_logger(__name__)

# The data generation's version — bump on a regeneration whose data shape/content
# materially changes (distinct from CONTRACT_VERSION, which tracks the schemas).
BUNDLE_VERSION = "1.0.0"
_DIALECT = "https://json-schema.org/draft/2020-12/schema"
# A collection longer than this is written as NDJSON (one row per line) per the #58
# "NDJSON for large lists" contract; shorter lists stay a single JSON array.
_NDJSON_THRESHOLD = 500


@dataclass
class _Feed:
    """One assembled feed, ready to write — its data, its schema, and its manifest row."""

    name: str
    path: str  # relative to the bundle root
    kind: FeedKind
    media_type: str
    schema_file: str  # relative to the bundle root, e.g. schemas/records.schema.json
    schema: dict[str, Any]
    payload: str
    count: int


@dataclass
class BundleResult:
    """Summary of a bundle export — where it landed and what it holds."""

    out_dir: Path
    feeds: list[FeedRef] = field(default_factory=list)
    row_total: int = 0

    @property
    def feed_count(self) -> int:
        return len(self.feeds)


def _object_schema(model: type[BaseModel], title: str) -> dict[str, Any]:
    """The serialization JSON Schema for one model (computed fields + aliases included)."""
    schema = model.model_json_schema(mode="serialization", by_alias=True)
    schema["$schema"] = _DIALECT
    schema.setdefault("title", title)
    return schema


def _array_schema(item_model: type[BaseModel], title: str) -> dict[str, Any]:
    """An ``array``-of-``item_model`` schema, with the model's ``$defs`` hoisted so its
    internal ``#/$defs/...`` references still resolve once nested under ``items``."""
    item = item_model.model_json_schema(mode="serialization", by_alias=True)
    defs = item.pop("$defs", None)
    wrapper: dict[str, Any] = {
        "$schema": _DIALECT,
        "title": title,
        "type": "array",
        "items": item,
    }
    if defs is not None:
        wrapper["$defs"] = defs
    return wrapper


def _dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def _collection_feed(name: str, item_model: type[BaseModel], rows: Sequence[BaseModel]) -> _Feed:
    """Assemble a list feed — JSON array, or NDJSON when it crosses the size threshold."""
    dumped = [r.model_dump(mode="json", by_alias=True) for r in rows]
    schema_file = f"schemas/{name}.schema.json"
    if len(dumped) > _NDJSON_THRESHOLD:
        payload = "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in dumped)
        return _Feed(
            name=name,
            path=f"feeds/{name}.ndjson",
            kind="collection",
            media_type="application/x-ndjson",
            schema_file=schema_file,
            schema=_object_schema(item_model, f"{name} row"),
            payload=payload,
            count=len(dumped),
        )
    return _Feed(
        name=name,
        path=f"feeds/{name}.json",
        kind="collection",
        media_type="application/json",
        schema_file=schema_file,
        schema=_array_schema(item_model, f"{name} feed"),
        payload=_dump_json(dumped),
        count=len(dumped),
    )


def _object_feed(name: str, model: BaseModel) -> _Feed:
    """Assemble a single-object feed (an inventory/baseline already carrying provenance)."""
    return _Feed(
        name=name,
        path=f"feeds/{name}.json",
        kind="object",
        media_type="application/json",
        schema_file=f"schemas/{name}.schema.json",
        schema=_object_schema(type(model), f"{name} feed"),
        payload=_dump_json(model.model_dump(mode="json", by_alias=True)),
        count=1,
    )


def _geo_feed(fc: GeoFeatureCollection) -> _Feed:
    """Assemble one typed GeoJSON layer feed; all geo feeds share one schema file."""
    return _Feed(
        name=f"geo/{fc.feed}",
        path=f"feeds/geo/{fc.feed}.geojson",
        kind="geojson",
        media_type="application/geo+json",
        schema_file="schemas/geo.schema.json",
        schema=_object_schema(GeoFeatureCollection, "GeoJSON layer feed"),
        payload=_dump_json(fc.model_dump(mode="json", by_alias=True)),
        count=len(fc.features),
    )


def _scoped_assessments(settings: Settings) -> list[HypothesisAssessment]:
    """The (site x hypothesis) evidence cells for this bundle (#762).

    The cells form one cross-site matrix (``data/hypotheses/<hid>/<site>.yaml``). The reference
    build (Lima, the network host the root ``/research/hypotheses`` matrix reads) carries the
    whole matrix; a sibling site's bundle carries only its own rows — strictly its own data.
    """
    cells = load_assessments(settings=settings)
    if is_reference_site(settings.site):
        return cells
    return [c for c in cells if c.site == settings.site]


def _load_scenarios(settings: Settings) -> list[ScenarioResult]:
    """Load the committed hydrology scenario results (``data/scenarios/*.scenario.yaml``).

    Per-site (#762): the committed scenarios are Lima's (the Ottawa-River loop); a sibling
    site reads its own ``scenarios/<slug>/`` (absent today → an empty feed, not Lima's).
    """
    sdir = site_scoped_path(settings.data_dir / "scenarios", settings.site, is_dir=True)
    if not sdir.is_dir():
        return []
    out: list[ScenarioResult] = []
    for path in sorted(sdir.glob("*.scenario.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            out.append(ScenarioResult.model_validate(data))
        except Exception as exc:  # a malformed scenario must not kill the whole export
            log.warning("bundle.scenario.bad", path=str(path), error=str(exc).splitlines()[0])
    return out


def _collect_feeds(settings: Settings) -> list[_Feed]:
    """Load the corpus once and assemble every feed."""
    feeds: list[_Feed] = []

    # Cross-document layer — load the corpus once, reuse for records/timeline/graph. The active
    # site's corpus scope (#762) bounds the extracted-tree feeds: `load_corpus` reads it itself;
    # the `records` feed reads the same tree separately, so it's passed the scope explicitly.
    corpus_scope = effective_corpus_scope(active_profile(settings))
    corpus = load_corpus(settings)
    events = build_timeline(corpus, scope=corpus_scope)
    egraph = build_entity_graph(
        corpus,
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        enrich_subdivisions=True,
        enrich_places=True,
        enrich_relation_classes=True,
        settings=settings,
    )

    # Curated exhibits (#56) — also the auto-included sources for the publish allowlist. Per-site
    # (#762): Lima's frozen exhibits.yaml is its own curation; a sibling site reads its own
    # `site/<slug>/exhibits.yaml` (absent today → an empty exhibits feed, not Lima's).
    exhibit_items = exhibits_mod.export_exhibits(
        site_scoped_path(settings.data_dir / "site" / "exhibits.yaml", settings.site, is_dir=False),
        settings.documents_dir,
    )
    # Open leads (#796) — the curated per-site leads board. Like exhibits, Lima reads its flat
    # `data/site/leads.yaml`; a sibling reads its own `site/<slug>/leads.yaml` (absent → an empty
    # leads feed, never Lima's; the frontend then falls back to the readiness-derived needs board).
    lead_items = leads_mod.export_leads(
        site_scoped_path(settings.data_dir / "site" / "leads.yaml", settings.site, is_dir=False),
    )
    # The default-deny public allowlist (#280): exhibits + the committed allowlist rules.
    allowlist = documents_mod.load_publish_allowlist(
        settings.data_dir / "site" / "published-documents.yaml",
        exhibit_sources=(ex.source for ex in exhibit_items),
    )

    # Source-document catalog (#274/#275): real media_type + render_class + publish flag.
    # Built before records so each record can join to its real source document (#276).
    doc_collections = documents_mod.export_documents(
        settings.documents_dir,
        mirror_base_url=settings.documents_mirror_base_url,
        allowlist=allowlist,
        scope=corpus_scope,
    )
    doc_index = documents_mod.build_doc_index(doc_collections)

    # Remaining unconditional source loads + the opt-in inventories (None => the feed is skipped).
    # The curated stores are per-site (#762): Lima reads its flat committed store; a sibling site
    # reads its own `<slug>/` copy (absent today => an empty/skipped feed, never Lima's). `load_pois`
    # site-scopes itself; meetings are extracted-tree-scoped like the corpus. `concepts` (the wiki
    # glossary) and `defense` (the national contractor seed list) are network-shared — left flat.
    people = load_people(site_scoped_path(settings.people_dir, settings.site, is_dir=True))
    concepts = concepts_mod.load_concepts(
        settings.concepts_dir, site=settings.site
    )  # wiki glossary (#68)
    pois = load_pois(settings=settings)
    summaries = load_committed_summaries(settings, scope=corpus_scope)
    cand_inv = load_cloud_consumer_candidates(
        site_scoped_path(settings.entities_dir, settings.site, is_dir=True)
    )
    defense = load_defense_contractors(settings.entities_dir)
    rsei_inv = load_rsei_inventory(settings)
    lei_inv = load_lei_inventory(
        site_scoped_path(settings.reference_dir, settings.site, is_dir=True)
    )
    econ = load_econ_baseline(settings)
    econ_energy = load_consumer_energy(settings)
    econ_demand = load_demand_pressure(settings)

    # The feed registry — one row per feed, in bundle order. ``model`` set => a collection feed
    # of that item type; ``None`` => an already-provenanced object feed (its own Pydantic model,
    # #60). A ``build`` that returns ``None`` (an absent optional inventory) is skipped. Adding a
    # feed is one row here. The geo feeds (variable count / conditional) stay below.
    specs: list[tuple[str, type[BaseModel] | None, Callable[[], object | None]]] = [
        (
            "records",
            RecordItem,
            lambda: records_mod.export_records(
                settings.extracted_dir, doc_index=doc_index, scope=corpus_scope
            ),
        ),
        ("timeline", TimelineEntry, lambda: graph_mod.export_timeline(events)),
        ("entities", EntityNode, lambda: graph_mod.export_entities(egraph)),
        ("relationships", RelationshipEdge, lambda: graph_mod.export_relationships(egraph)),
        ("people", PersonItem, lambda: people_mod.export_people(people, egraph=egraph)),
        ("concepts", ConceptItem, lambda: concepts_mod.export_concepts(concepts)),
        ("places", PlaceItem, lambda: places_mod.export_places(pois)),
        (
            "candidates",
            CandidateItem,
            lambda: (
                None
                if cand_inv is None
                else candidates_mod.export_candidates(cand_inv, egraph=egraph)
            ),
        ),
        (
            "defense-contractors",
            None,
            lambda: (
                None
                if defense is None
                else candidates_mod.export_defense_contractors(
                    defense, egraph=egraph, scan=load_defense_scan(settings)
                )
            ),
        ),
        ("meetings", MeetingItem, lambda: meetings_mod.export_meetings(summaries)),
        ("documents", DocumentCollectionItem, lambda: doc_collections),
        ("exhibits", ExhibitItem, lambda: exhibit_items),
        # `or None` skips the feed when a site has no curated leads, so `hasFeed("leads")` is false
        # and the frontend cleanly falls back to the readiness-derived needs board (not an empty list).
        ("leads", LeadItem, lambda: lead_items or None),
        # Already-provenanced inventories — exported as their own Pydantic models (#60).
        ("rsei", None, lambda: None if rsei_inv is None else rsei_mod.export_rsei(rsei_inv)),
        ("lei", None, lambda: None if lei_inv is None else gleif_mod.export_gleif(lei_inv)),
        (
            "economics-baseline",
            None,
            lambda: None if econ is None else economics_mod.export_economics(econ),
        ),
        # Consumer energy costs (EIA) with the full annual price/sales series for charting
        # (issue #1111); absent when the site has no committed consumer-energy dataset.
        (
            "consumer-energy",
            None,
            lambda: (
                None if econ_energy is None else economics_mod.export_consumer_energy(econ_energy)
            ),
        ),
        # The facility demand→consumer-price-pressure sensitivity (#1105): households-equivalent,
        # demand share, and the STYLIZED price-pressure band. Facility-gated — absent (feed skipped)
        # for a thin site with no documented facility, exactly as the derivation is gated.
        (
            "economics-demand-pressure",
            None,
            lambda: (
                None if econ_demand is None else economics_mod.export_demand_pressure(econ_demand)
            ),
        ),
        # Cross-site basin synthesis (#308/#323): the watershed points as one connected basin.
        ("network", None, lambda: build_basin_network(settings=settings)),
        # The boom-origin hypotheses (directory lenses) + their (site x hypothesis) evidence
        # cells (#308) — each cell carries a Citation, so the directory shows provenance.
        ("hypotheses", Hypothesis, lambda: list(HYPOTHESES.values())),
        (
            "hypothesis-assessments",
            HypothesisAssessment,
            lambda: _scoped_assessments(settings),
        ),
        ("hydrology-scenarios", ScenarioResult, lambda: _load_scenarios(settings)),
        # The published data catalog (epic #631 Phase 3 / #659) — the data tier /about/data reads.
        ("catalog", CatalogItem, lambda: catalog_mod.export_catalog(settings)),
    ]
    for name, model, build in specs:
        result = build()
        if result is None:
            continue
        if model is not None:
            feeds.append(_collection_feed(name, model, cast("Sequence[BaseModel]", result)))
        else:
            feeds.append(_object_feed(name, cast("BaseModel", result)))

    # Typed GeoJSON layer feeds (issue #61). The committed `gis-findings.geojson` is a Lima
    # artifact (Bistrozzi campus + JSMC + the North Cole corridor), so it's read only for Lima
    # (#762): a sibling site would otherwise inherit Lima's parcels, a phantom Army installation,
    # and Lima's corridor/flood/RSEI points. A non-Lima site emits the per-site geo it can derive
    # — today the campus, from its own parcel assemblage (active_profile().parcels_relpath).
    findings = settings.data_dir / "site" / "gis-findings.geojson"
    if settings.site == "lima" and findings.is_file():
        feeds.extend(_geo_feed(fc) for fc in gismap_mod.export_geo(findings))
    elif settings.site != "lima":
        campus = gismap_mod.campus_from_parcels(settings)
        if campus is not None:
            feeds.append(_geo_feed(campus))
    # Two more geo feeds assembled outside gis-findings: the USGS WBD watershed
    # boundaries and the imagery tracking-AOI footprints + Wayback ladder (for #72).
    watershed = gismap_mod.export_watershed_geo(settings)
    if watershed is not None:
        feeds.append(_geo_feed(watershed))
    imagery = gismap_mod.export_imagery_geo(settings)
    if imagery is not None:
        feeds.append(_geo_feed(imagery))

    return feeds


def _collection_rows(feed: _Feed) -> list[dict[str, Any]]:
    """Parse an assembled collection feed's payload back into row dicts (JSON array or NDJSON)."""
    if feed.media_type == "application/x-ndjson":
        return [json.loads(line) for line in feed.payload.splitlines() if line.strip()]
    return cast("list[dict[str, Any]]", json.loads(feed.payload))


def _catalog_index_feed(feeds: Sequence[_Feed], settings: Settings) -> _Feed:
    """Build the hydrated catalog index (#1093) as an object feed from the assembled feeds.

    A cheap normalisation over the collection feeds already assembled (no corpus re-load): the
    feed-backed catalog kinds only. The Astro build overlays the web-only kinds at render time.
    """
    rows_by_feed = {
        feed.name: _collection_rows(feed) for feed in feeds if feed.kind == "collection"
    }
    index = build_catalog_index(rows_by_feed, site=settings.site, contract_version=CONTRACT_VERSION)
    return _object_feed("catalog-index", index)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def export_bundle(
    settings: Settings | None = None,
    out_dir: Path | None = None,
    *,
    generated_at: str | None = None,
    skip_embeddings: bool = False,
) -> BundleResult:
    """Write the full content bundle and return a summary.

    ``generated_at`` overrides the manifest timestamp (used by tests for determinism);
    it defaults to the current UTC time.

    ``skip_embeddings`` suppresses the optional ``ask-embeddings`` feed — useful when
    you need a fast bundle without the ~80 MB model download (``watermark export
    --no-embeddings``).
    """
    settings = settings or get_settings()
    # Per-site bundle (#724/#727): the generated feeds + manifest live under a slug-scoped
    # dir so the network's sites don't clobber each other; the active site comes from
    # `settings.site` (the global `watermark --site <slug>` flag / `WATERMARK_SITE`). The committed,
    # site-agnostic contract (schemas/README/example) stays at `data/site/bundle/`.
    out = out_dir or (settings.data_dir / "site" / "bundles" / settings.site)
    schemas_dir = out / "schemas"
    feeds_dir = out / "feeds"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    feeds_dir.mkdir(parents=True, exist_ok=True)

    feeds = _collect_feeds(settings)
    # The hydrated catalog index (#1093) — a normalisation over the just-assembled collection
    # feeds, so it must be appended after `_collect_feeds`. Written + indexed through the same
    # loops below like any other feed.
    feeds.append(_catalog_index_feed(feeds, settings))

    # Schema files (geo feeds share one file — dedup by schema_file path).
    written_schemas: set[str] = set()
    for feed in feeds:
        if feed.schema_file in written_schemas:
            continue
        (out / feed.schema_file).write_text(_dump_json(feed.schema), encoding="utf-8")
        written_schemas.add(feed.schema_file)
    # The manifest schema (so the index itself is validatable) and the shared citation
    # schema — the latter is embedded in every feed's $defs, but emitting it standalone
    # documents the #60 provenance shape.
    (schemas_dir / "manifest.schema.json").write_text(
        _dump_json(_object_schema(Manifest, "Manifest")), encoding="utf-8"
    )
    (schemas_dir / "citation.schema.json").write_text(
        _dump_json(_object_schema(Citation, "Citation")), encoding="utf-8"
    )

    # Feed data files + their manifest rows.
    refs: list[FeedRef] = []
    for feed in feeds:
        target = out / feed.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(feed.payload, encoding="utf-8")
        refs.append(
            FeedRef(
                name=feed.name,
                path=feed.path,
                media_type=feed.media_type,
                schema_ref=feed.schema_file,
                kind=feed.kind,
                count=feed.count,
            )
        )

    # ask-embeddings feed (#329): generated after the corpus feeds are written to disk so
    # build_ask_embeddings() reads fresh data, not the previous export's stale files.
    # Always emitted (empty when skipped) so the schema is stable and manifest stays consistent.
    emb_models: list[AskEmbeddingEntry] = []
    if not skip_embeddings:
        try:
            emb_rows = build_ask_embeddings(out)
            emb_models = [AskEmbeddingEntry.model_validate(r) for r in emb_rows]
        except Exception as exc:
            log.warning(
                "embeddings.failed",
                error=next(iter(str(exc).splitlines()), repr(exc)),
                hint="run with --no-embeddings to skip; hybrid retrieval will degrade to BM25",
            )
    emb_feed = _collection_feed("ask-embeddings", AskEmbeddingEntry, emb_models)
    if emb_feed.schema_file not in written_schemas:
        (out / emb_feed.schema_file).write_text(_dump_json(emb_feed.schema), encoding="utf-8")
    emb_target = out / emb_feed.path
    emb_target.parent.mkdir(parents=True, exist_ok=True)
    emb_target.write_text(emb_feed.payload, encoding="utf-8")
    refs.append(
        FeedRef(
            name=emb_feed.name,
            path=emb_feed.path,
            media_type=emb_feed.media_type,
            schema_ref=emb_feed.schema_file,
            kind=emb_feed.kind,
            count=emb_feed.count,
        )
    )

    row_total = sum(r.count for r in refs)
    manifest = Manifest(
        site=settings.site,
        bundle_version=BUNDLE_VERSION,
        contract_version=CONTRACT_VERSION,
        generated_at=generated_at or _now_iso(),
        feed_count=len(refs),
        row_total=row_total,
        feeds=refs,
    )
    (out / "manifest.json").write_text(
        _dump_json(manifest.model_dump(mode="json", by_alias=True)), encoding="utf-8"
    )

    log.info("bundle.exported", out=str(out), feeds=len(refs), rows=row_total)
    return BundleResult(out_dir=out, feeds=refs, row_total=row_total)
