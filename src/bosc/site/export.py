"""Export the committed corpus into the typed content bundle under ``data/site/bundle/``.

The build-alongside data peer of :mod:`bosc.site.build` (issue #53, Tier 1): where
``build_site`` stages markdown for the legacy renderer, :func:`export_bundle` emits the
versioned, schema-validated JSON feeds the Astro/DeckGL frontend reads — reusing the very
same loaders ``build_site`` calls (``load_corpus``, ``build_timeline``,
``build_entity_graph``, ``load_people``, ``load_pois``, …). ``render_X`` and
``bosc site build`` stay intact; this never touches ``web/``.

Layout written under ``out_dir`` (default ``data/site/bundle``):

* ``manifest.json`` — bundle/contract version, ``generated_at``, and the feed index.
* ``schemas/<feed>.schema.json`` — one JSON Schema per feed, generated from the
  :mod:`bosc.site.feeds` models (serialization mode), so schema and code never drift.
* ``feeds/<feed>.json`` (or ``.ndjson`` for a large list) and ``feeds/geo/<feed>.geojson``.

The contract itself (README, schemas, an example manifest) is committed; the generated
``manifest.json`` + ``feeds/`` are regenerable and git-ignored (see the bundle README).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from bosc.candidates import (
    load_cloud_consumer_candidates,
    load_defense_contractors,
    load_defense_scan,
)
from bosc.civic.summarize import load_committed_summaries
from bosc.config import Settings, get_settings
from bosc.economics.baseline import load_baseline as load_econ_baseline
from bosc.gleif import load_inventory as load_lei_inventory
from bosc.hydrology.model import ScenarioResult
from bosc.logging import get_logger
from bosc.people import load_people
from bosc.pipeline.corpus import load_corpus
from bosc.pipeline.entities import build_entity_graph
from bosc.pipeline.timeline import build_timeline
from bosc.poi import load_pois
from bosc.rsei import load_inventory as load_rsei_inventory
from bosc.site import candidates as candidates_mod
from bosc.site import concepts as concepts_mod
from bosc.site import documents as documents_mod
from bosc.site import economics as economics_mod
from bosc.site import exhibits as exhibits_mod
from bosc.site import gismap as gismap_mod
from bosc.site import gleif as gleif_mod
from bosc.site import graph as graph_mod
from bosc.site import meetings as meetings_mod
from bosc.site import people as people_mod
from bosc.site import places as places_mod
from bosc.site import records as records_mod
from bosc.site import rsei as rsei_mod
from bosc.site.feeds import (
    CONTRACT_VERSION,
    CandidateItem,
    Citation,
    ConceptItem,
    DocumentCollectionItem,
    EntityNode,
    ExhibitItem,
    FeedKind,
    FeedRef,
    GeoFeatureCollection,
    Manifest,
    MeetingItem,
    PersonItem,
    PlaceItem,
    RecordItem,
    RelationshipEdge,
    TimelineEntry,
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


def _load_scenarios(settings: Settings) -> list[ScenarioResult]:
    """Load the committed hydrology scenario results (``data/scenarios/*.scenario.yaml``)."""
    sdir = settings.data_dir / "scenarios"
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
    """Load the corpus once and assemble every feed (the loaders ``build_site`` calls)."""
    feeds: list[_Feed] = []

    # Cross-document layer — load the corpus once, reuse for records/timeline/graph.
    corpus = load_corpus(settings)
    events = build_timeline(corpus)
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

    feeds.append(
        _collection_feed("records", RecordItem, records_mod.export_records(settings.extracted_dir))
    )
    feeds.append(_collection_feed("timeline", TimelineEntry, graph_mod.export_timeline(events)))
    feeds.append(_collection_feed("entities", EntityNode, graph_mod.export_entities(egraph)))
    feeds.append(
        _collection_feed("relationships", RelationshipEdge, graph_mod.export_relationships(egraph))
    )

    people = load_people(settings.people_dir)
    feeds.append(
        _collection_feed("people", PersonItem, people_mod.export_people(people, egraph=egraph))
    )

    # Wiki concept-glossary store (issue #68) — curated term/method definitions.
    concepts = concepts_mod.load_concepts(settings.concepts_dir)
    feeds.append(_collection_feed("concepts", ConceptItem, concepts_mod.export_concepts(concepts)))

    pois = load_pois(settings=settings)
    feeds.append(_collection_feed("places", PlaceItem, places_mod.export_places(pois)))

    cand_inv = load_cloud_consumer_candidates(settings.entities_dir)
    if cand_inv is not None:
        feeds.append(
            _collection_feed(
                "candidates",
                CandidateItem,
                candidates_mod.export_candidates(cand_inv, egraph=egraph),
            )
        )

    defense = load_defense_contractors(settings.entities_dir)
    if defense is not None:
        scan = load_defense_scan(settings.reference_dir)
        feeds.append(
            _object_feed(
                "defense-contractors",
                candidates_mod.export_defense_contractors(defense, egraph=egraph, scan=scan),
            )
        )

    summaries = load_committed_summaries(settings)
    feeds.append(_collection_feed("meetings", MeetingItem, meetings_mod.export_meetings(summaries)))

    feeds.append(
        _collection_feed(
            "documents",
            DocumentCollectionItem,
            documents_mod.export_documents(
                settings.documents_dir, mirror_base_url=settings.documents_mirror_base_url
            ),
        )
    )

    feeds.append(
        _collection_feed(
            "exhibits",
            ExhibitItem,
            exhibits_mod.export_exhibits(
                settings.data_dir / "site" / "exhibits.yaml", settings.documents_dir
            ),
        )
    )

    # Already-provenanced inventories — exported as their own Pydantic models (#60).
    rsei_inv = load_rsei_inventory(settings.reference_dir)
    if rsei_inv is not None:
        feeds.append(_object_feed("rsei", rsei_mod.export_rsei(rsei_inv)))
    lei_inv = load_lei_inventory(settings.reference_dir)
    if lei_inv is not None:
        feeds.append(_object_feed("lei", gleif_mod.export_gleif(lei_inv)))
    econ = load_econ_baseline(settings.reference_dir)
    if econ is not None:
        feeds.append(_object_feed("economics-baseline", economics_mod.export_economics(econ)))

    feeds.append(_collection_feed("hydrology-scenarios", ScenarioResult, _load_scenarios(settings)))

    # Typed GeoJSON layer feeds (issue #61).
    findings = settings.data_dir / "site" / "gis-findings.geojson"
    if findings.is_file():
        feeds.extend(_geo_feed(fc) for fc in gismap_mod.export_geo(findings))

    return feeds


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def export_bundle(
    settings: Settings | None = None,
    out_dir: Path | None = None,
    *,
    generated_at: str | None = None,
) -> BundleResult:
    """Write the full content bundle and return a summary.

    ``generated_at`` overrides the manifest timestamp (used by tests for determinism);
    it defaults to the current UTC time.
    """
    settings = settings or get_settings()
    out = out_dir or (settings.data_dir / "site" / "bundle")
    schemas_dir = out / "schemas"
    feeds_dir = out / "feeds"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    feeds_dir.mkdir(parents=True, exist_ok=True)

    feeds = _collect_feeds(settings)

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

    row_total = sum(r.count for r in refs)
    manifest = Manifest(
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
