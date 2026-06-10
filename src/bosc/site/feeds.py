"""The content-bundle contract — typed models for every feed the frontend reads.

These Pydantic models *are* the contract (issue #53, Tier 1). Each ``export_X`` in
the ``bosc.site.*`` modules returns one of these, and :mod:`bosc.site.export` writes
them under ``data/site/bundle/`` with a ``manifest.json`` and a JSON Schema per feed
(generated from these models, so schema and code never drift).

Two primitives carry provenance into every figure-bearing feed (issue #60), so a
consumer can render ``[verified] cite p.X`` or an approximate ``~`` value purely from
the bundle — no re-deriving:

* :class:`Citation` — where a value came from. Its ``source_kind`` maps onto the
  dossier's evidence discipline exactly as :class:`bosc.hydrology.model.ProvenancedValue`
  does (``document``/``connector`` → ``verified``; ``assumption``/``derived`` →
  ``inference``); ``verified`` is a derived boolean the frontend reads directly.
* :class:`Figure` — a number that preserves the ``~`` approximate marker as *data*
  (``approximate: true``), not as formatted text.

The already-provenanced feeds (rsei, lei, economics-baseline, hydrology-scenarios)
export their existing :mod:`bosc` Pydantic models unchanged — they already satisfy the
#60 discipline through ``ProvenancedValue`` / an inventory ``meta.source`` — so this
module only models the feeds whose renderers worked off dataclasses or raw dicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# --- bundle contract version ---------------------------------------------------
# Bumped per the back-compat policy in data/site/bundle/README.md: PATCH for additive
# optional fields, MINOR for new feeds, MAJOR for a breaking field change/removal.
# 1.1.0: added the `concepts` feed (issue #68, the wiki concept-glossary store).
CONTRACT_VERSION = "1.1.0"

SourceKind = Literal["document", "connector", "reference", "assumption", "derived"]
Confidence = Literal["high", "medium", "low"]
RecordGroup = Literal["deeds", "permits-epa", "permits-npdes", "permits-sos", "plans", "opc"]


# --- shared provenance primitives (issue #60) ---------------------------------
class Citation(BaseModel):
    """Structured provenance for a feed item or a single figure.

    Mirrors :class:`bosc.hydrology.model.ProvenancedValue`'s evidence discipline so the
    whole bundle speaks one provenance language: ``source_kind`` says where the value
    came from, ``source`` is the citable artifact (a repo-relative ``data/`` path, an
    external dataset label, a permit/instrument number), ``page`` locates it within a
    multi-page source, and ``verified`` is derived so a consumer never re-computes it.
    """

    model_config = ConfigDict(extra="forbid")

    source: str | None = None  # repo-relative artifact path, dataset label, or doc id
    source_kind: SourceKind = "document"
    page: int | None = None  # 1-based page within the source, if applicable
    confidence: Confidence = "medium"
    note: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        """True when grounded in a record or a live gauge (``[verified]`` in prose)."""
        return self.source_kind in ("document", "connector")


class Figure(BaseModel):
    """A number that keeps the ``~`` approximate marker as data, not formatted text.

    ``approximate`` is the transcription ``~`` lifted out of the YAML string so a
    consumer renders the tilde from the bundle; ``citation`` ties the figure to its
    source page/file. Dollar totals are high-confidence (``approximate=False``);
    transcribed quantities marked ``~`` in the source set ``approximate=True``.
    """

    model_config = ConfigDict(extra="forbid")

    value: float | int | None = None
    approximate: bool = False
    unit: str | None = None
    citation: Citation | None = None


# --- records feed --------------------------------------------------------------
class RecordItem(BaseModel):
    """One committed extraction, contractor-/genre-agnostic (mirrors records.py).

    ``fields`` is the raw payload block verbatim (so the ``~`` marker survives in any
    transcribed scalar); ``approximate_paths`` lists the dotted field paths whose value
    carried that marker, and ``citation`` is the structured provenance footer.
    """

    model_config = ConfigDict(extra="forbid")

    rel: str  # path relative to data/extracted — the stable record id
    group: RecordGroup
    title: str
    confidence: str | None = None
    warnings: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
    approximate_paths: list[str] = Field(default_factory=list)
    citation: Citation


# --- timeline feed -------------------------------------------------------------
class TimelineEntry(BaseModel):
    """One dated event, traceable to the extraction(s) that supplied it."""

    model_config = ConfigDict(extra="forbid")

    date: str  # as transcribed (ISO where legible; "" when undated)
    category: str
    title: str
    ref: str = ""  # logical id (instrument / permit no) for cross-doc dedup
    parties: list[str] = Field(default_factory=list)
    detail: str = ""
    source: str  # primary extraction path, relative to data/extracted
    also_sources: list[str] = Field(default_factory=list)
    citation: Citation


# --- entities + relationships feeds -------------------------------------------
class EntityNode(BaseModel):
    """A resolved party in the entity graph, keyed by its canonical name."""

    model_config = ConfigDict(extra="forbid")

    key: str  # canonical, normalized key — the cross-feed reference id
    display: str
    kind: str
    classification: str
    relation_class: str | None = None
    relation_basis: str | None = None
    variants: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    roles: dict[str, int] = Field(default_factory=dict)
    parcels: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    lei: str | None = None
    uei: str | None = None
    federal_obligations: float | None = None


class RelationshipEdge(BaseModel):
    """A directed edge between two entity keys, traceable to one document."""

    model_config = ConfigDict(extra="forbid")

    src: str  # source entity key (resolves into the entities feed)
    rel: str
    dst: str  # destination entity key (resolves into the entities feed)
    date: str = ""
    ref: str = ""
    source: str = ""
    relation_class: str | None = None
    relation_basis: str | None = None


# --- people feed ---------------------------------------------------------------
class PersonItem(BaseModel):
    """A curated individual profile (only expanded-research ones are published)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    entity_key: str | None = None  # resolves into the entities feed
    aliases: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    summary: str | None = None
    expanded: bool = False
    tags: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    body: str = ""


# --- places feed ---------------------------------------------------------------
class PlaceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str | None = None
    confidence: str | None = None
    asof: str | None = None
    bbox: list[float] | None = None  # [minx, miny, maxx, maxy], WGS84


class PlaceTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    collections: list[str] = Field(default_factory=list)
    since: str | None = None


class PlaceRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    entity: str  # resolves into the entities feed


class PlaceItem(BaseModel):
    """A curated place (POI) profile — the place peer of a person profile."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    kind: str
    depth: str
    parcels: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)  # composite member slugs
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    location: PlaceLocation | None = None
    track: PlaceTrack | None = None
    relationships: list[PlaceRelationship] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    body: str = ""


# --- candidates + defense-contractors feeds -----------------------------------
class CandidateItem(BaseModel):
    """A demand-fit cloud-consumer candidate (curated, not corpus-derived)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tier: int
    kind: str
    sector: str | None = None
    location: str | None = None
    workload_classes: list[str] = Field(default_factory=list)
    confirmed_cloud_relationship: str | None = None
    speculative: bool = False
    basis: str | None = None
    entity_key: str | None = None  # resolves into the entities feed when matched


class ScanParcel(BaseModel):
    """A parcel row from the defense-land GIS scan (extra GIS columns allowed)."""

    model_config = ConfigDict(extra="allow")


class DefenseContractorItem(BaseModel):
    """A seed prime defense contractor + the corpus entities its patterns matched."""

    model_config = ConfigDict(extra="forbid")

    name: str
    note: str | None = None
    patterns: list[str] = Field(default_factory=list)
    matched_entities: list[str] = Field(default_factory=list)  # entity keys


class DefenseFeed(BaseModel):
    """The defense-contractors feed: the seed list + the parcel-scan findings."""

    model_config = ConfigDict(extra="forbid")

    contractors: list[DefenseContractorItem] = Field(default_factory=list)
    prime_owned: list[ScanParcel] = Field(default_factory=list)
    army_controlled: list[ScanParcel] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)


# --- meetings feed -------------------------------------------------------------
class MeetingItem(BaseModel):
    """One corridor-relevant subdivision meeting summary (grounded, no inference)."""

    model_config = ConfigDict(extra="forbid")

    slug: str  # the subdivision body (e.g. "lacrpc", "lima")
    date: str | None = None
    kind: str | None = None
    summary: str = ""
    corridor_relevance: str = ""
    decisions: list[str] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    parcels: list[str] = Field(default_factory=list)
    dollar_figures: list[str] = Field(default_factory=list)
    hits: list[str] = Field(default_factory=list)
    citation: Citation


# --- documents + exhibits feeds -----------------------------------------------
class DocumentItem(BaseModel):
    """One source document in the catalog, addressed by its corpus path."""

    model_config = ConfigDict(extra="forbid")

    rel: str  # path relative to data/documents — the as-received chain-of-custody name
    name: str
    size_bytes: int
    suffix: str
    available: bool  # locally present (not an unresolved Git-LFS pointer)
    download_url: str | None = None


class DocumentCollectionItem(BaseModel):
    """A first-level collection under data/documents and its catalogued entries."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    description: str = ""
    entries: list[DocumentItem] = Field(default_factory=list)


class ExhibitItem(BaseModel):
    """A curated, published exhibit — a source PDF or a page-range slice of a bundle."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    caption: str = ""
    source: str  # path relative to data/documents
    pages: str | None = None  # "317-327" (0-based inclusive) or None for the whole file
    available: bool


# --- concepts feed (issue #68) ------------------------------------------------
class ConceptItem(BaseModel):
    """One glossary concept from the wiki concept store (``data/concepts/*.md``).

    The lightweight peer of a person profile: a frontmatter header (identity +
    cross-links) plus a hand-written markdown body. ``related`` holds the slugs of
    sibling concepts; the frontend additionally resolves inline ``[[wiki links]]``
    in the body against the concepts, entities, and people feeds.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str  # the stable concept id (file stem)
    title: str
    kind: str = "concept"  # concept | term | method
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    related: list[str] = Field(default_factory=list)  # sibling concept slugs
    body: str = ""


# --- typed GeoJSON feeds (issue #61) ------------------------------------------
class GeoProperties(BaseModel):
    """Layer metadata carried on every feature (extra popup fields allowed)."""

    model_config = ConfigDict(extra="allow")

    layer: str
    label: str | None = None
    color: str | None = None  # the legend swatch the renderer uses
    role: str | None = None  # geometry role: area | line | point


class GeoFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]  # WGS84 verbatim, display-only (no reprojection)
    properties: GeoProperties


class GeoFeatureCollection(BaseModel):
    """One typed GeoJSON layer feed for DeckGL (a valid FeatureCollection + ``feed``)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["FeatureCollection"] = "FeatureCollection"
    feed: str  # the feed/layer name (campus, jsmc, corridor, femaflood, rsei, ...)
    meta: dict[str, Any] = Field(default_factory=dict)
    features: list[GeoFeature] = Field(default_factory=list)


# --- manifest ------------------------------------------------------------------
FeedKind = Literal["collection", "object", "geojson"]


class FeedRef(BaseModel):
    """One entry in the manifest's feed index — what it is and how to read it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    path: str  # relative to the bundle root, e.g. "feeds/records.json"
    media_type: str  # application/json | application/geo+json | application/x-ndjson
    schema_ref: str = Field(serialization_alias="schema", validation_alias="schema")
    kind: FeedKind
    count: int  # rows (collection), features (geojson), or 1 (object)


class Manifest(BaseModel):
    """The bundle index: version, provenance of the generation, and the feed list."""

    model_config = ConfigDict(extra="forbid")

    bundle_version: str  # the data generation's version (bumped on every export)
    contract_version: str  # the schema/contract version these feeds conform to
    generated_at: str  # ISO-8601 UTC
    feed_count: int
    row_total: int  # sum of feed counts — a quick internal-consistency check
    feeds: list[FeedRef] = Field(default_factory=list)
