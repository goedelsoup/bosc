"""The content-bundle contract — typed models for every feed the frontend reads.

These Pydantic models *are* the contract (issue #53, Tier 1). Each ``export_X`` in
the ``watermark.site.*`` modules returns one of these, and :mod:`watermark.site.export` writes
them under ``data/site/bundle/`` with a ``manifest.json`` and a JSON Schema per feed
(generated from these models, so schema and code never drift).

Two primitives carry provenance into every figure-bearing feed (issue #60), so a
consumer can render ``[verified] cite p.X`` or an approximate ``~`` value purely from
the bundle — no re-deriving:

* :class:`Citation` — where a value came from. Its ``source_kind`` maps onto the
  dossier's evidence discipline exactly as :class:`watermark.hydrology.model.ProvenancedValue`
  does (``document``/``connector`` → ``verified``; ``assumption``/``derived`` →
  ``inference``); ``verified`` is a derived boolean the frontend reads directly.
* :class:`Figure` — a number that preserves the ``~`` approximate marker as *data*
  (``approximate: true``), not as formatted text.

The already-provenanced feeds (rsei, lei, economics-baseline, hydrology-scenarios)
export their existing :mod:`watermark` Pydantic models unchanged — they already satisfy the
#60 discipline through ``ProvenancedValue`` / an inventory ``meta.source`` — so this
module only models the feeds whose renderers worked off dataclasses or raw dicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from watermark.provenance import Confidence as Confidence
from watermark.provenance import SourceKind as SourceKind
from watermark.provenance import source_is_verified

# --- bundle contract version ---------------------------------------------------
# Bumped per the back-compat policy in data/site/bundle/README.md: PATCH for additive
# optional fields, MINOR for new feeds, MAJOR for a breaking field change/removal.
# 1.1.0: added the `concepts` feed (issue #68, the wiki concept-glossary store).
# 1.2.0: source-document rendering (epic #274) — `DocumentItem` gains real
#   `media_type`/`render_class` (#275), `RecordItem` gains the `source_doc_*` join (#276).
# 1.3.0: `DocumentItem` gains `published` — the default-deny public allowlist flag (#280).
# 1.4.0: adds the `network` object feed — the cross-site basin synthesis (watermark.network; #308/#323).
# 1.5.0: adds the `hypotheses` + `hypothesis-assessments` feeds — the boom-origin lenses and their
#   (site x hypothesis) evidence cells (watermark.hypotheses; #308). The directory reads these instead of
#   the formerly-hardcoded LENSES/LENS_DATA, so each cell now ships with a Citation.
# 1.6.0: adds the `catalog` feed — the published data catalog (watermark.catalog projected to
#   CatalogItem + the reconcile observed snapshot; epic #631 Phase 3 / #659).
# 1.6.1: the manifest gains `site` — the network-site slug a bundle is for, so it self-identifies
#   (per-site bundle scoping; #762).
# 1.7.0: adds the per-site `leads` feed — the open-leads board read from a committed per-site store
#   (`data/site/leads.yaml`, slug-scoped), so a peer carries its own leads, not Lima's (#796).
# 1.8.0: adds the optional `ask-embeddings` feed — all-MiniLM-L6-v2 document vectors for hybrid
#   BM25 + vector retrieval (#329); absent when `watermark export --no-embeddings` is used.
# 1.9.0: `hydrology-scenarios` rows gain `cooling_model` (top-level, on the scenario, and on its
#   basis) plus the basis honesty flags `method_disclosed` / `is_bracketed` and the hybrid
#   `seasonal_months` — the cooling-model typology (epic #1060). An `unknown` model means the
#   method is undisclosed: render the bracketed range, never a single headline (#1057).
# 1.10.0: keep annual time series (issue #1111). `economics-baseline` trend points (`YearTotal`)
#   gain `establishments` and now span a decade (QCEW 2014-2024, not two years); adds the
#   `consumer-energy` feed — the EIA state price/sales dataset with each series' full annual
#   history (`points`) plus its latest cited value, so the site can chart price trends.
# 1.11.0: adds the `catalog-index` object feed — the hydrated catalog of addressable "grabbable"
#   atoms (handle grammar `<kind>:<site>:<local_id>`) the user-authored Stories write/read paths
#   resolve against, plus `catalog_version` for handle-drift revalidation (epic #1090 / #1093).
CONTRACT_VERSION = "1.11.0"

# SourceKind / Confidence now live in watermark.provenance (shared with watermark.hypotheses +
# hydrology.ProvenancedValue, #605); re-exported here so importers of watermark.site.feeds are
# unchanged.
RecordGroup = Literal[
    "deeds", "permits-epa", "permits-idem", "permits-npdes", "permits-sos", "plans", "opc"
]
# What the frontend document viewer dispatches on — derived from the *real* file
# (extension + content sniff), never from hand-authored genre metadata (epic #274).
RenderClass = Literal["image", "text", "html", "pdf", "office", "other"]


# --- shared provenance primitives (issue #60) ---------------------------------
class Citation(BaseModel):
    """Structured provenance for a feed item or a single figure.

    Mirrors :class:`watermark.hydrology.model.ProvenancedValue`'s evidence discipline so the
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
        return source_is_verified(self.source_kind)


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
    # The real source document this record was read from (epic #274 / #276), joined
    # against the documents catalog so a stale/removed source_path yields ``None``
    # (no broken link) rather than a 404. Connector-only records carry ``None``.
    source_doc_rel: str | None = None  # the source file's data/documents rel
    source_doc_render_class: RenderClass | None = None  # from the documents feed (#275)
    source_doc_published: bool = False  # cleared for public serving (allowlist, #280)


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
    suffix: str  # the file extension, lower-cased and de-dotted (the as-received signal)
    # The renderable type, derived from the *real* file (extension + a content sniff of
    # the leading bytes), not from hand-authored metadata (epic #274 / #275).
    media_type: str  # MIME, e.g. application/pdf, image/jpeg, text/html
    render_class: RenderClass  # what the viewer dispatches on
    # Cleared for *public* serving by the default-deny allowlist (#280); dev/preview
    # serve everything regardless. The /api/doc Function enforces the same flag.
    published: bool
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


# --- leads feed (issue #796) --------------------------------------------------
# The four lead kinds, the lead lifecycle status, and the evidence tag — the data vocabulary the
# frontend's leads board renders (presentation labels stay frontend-side). A lead is *unverified
# inference until a source corroborates it*, so the tag is only ever `open` (a documented gap) or
# `inference` (a labeled reading), never `verified`.
LeadKind = Literal["signal", "question", "redaction", "claim"]
LeadStatus = Literal["low", "unanswered", "withheld", "review"]
LeadTag = Literal["open", "inference"]


class LeadItem(BaseModel):
    """One open lead — a gap we're chasing on a site, each tracing to a real committed source.

    The per-site peer of Lima's curated leads board: read from `data/site/leads.yaml` (slug-scoped),
    so a sibling site carries its own leads, not Lima's (#796). No fabricated contributors or
    timestamps — every lead names where the gap is recorded.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable local id; mirrors the PRR item / source where apt
    kind: LeadKind
    status: LeadStatus
    tag: LeadTag
    title: str
    detail: str
    source: str  # the real citation — where this gap is recorded
    issue: int | None = (
        None  # a linked watermark-directory/the-watermark-directory tracking issue, when one exists
    )
    note: str | None = None  # a short standing note, used sparingly + truthfully


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


# --- data catalog feed (epic #631, Phase 3 / #659) ----------------------------
class CatalogStorageFile(BaseModel):
    """One committed file belonging to a catalogued dataset (a published storage row)."""

    model_config = ConfigDict(extra="forbid")

    relpath: str  # relative to data/, ``{site}`` template kept verbatim for slug-scoped sets
    media_type: str
    lfs: bool = False


class CatalogObserved(BaseModel):
    """The reconcile snapshot's observed half for a dataset (``data/catalog/_observed.yaml``)."""

    model_config = ConfigDict(extra="forbid")

    exists: bool
    sha256: str | None = None
    size_bytes: int = 0
    lfs_materialized: bool = True
    file_count: int = 0
    stale: bool = False
    asof: str | None = None


class CatalogItem(BaseModel):
    """One dataset in the published data catalog — the bundle projection of a ``CatalogEntry``.

    The presentation peer of :class:`watermark.catalog.CatalogEntry`: the declared facts (producer,
    license, access tier, refresh, the per-site ``site_scope`` axis, storage) joined to the
    observed snapshot (:class:`CatalogObserved`). ``citation`` carries the producer as the
    bundle's shared provenance shape so the catalog speaks the same language as every other feed.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    scope: str  # documents | extracted | reference | derived | bundle | people | hypotheses | poi
    collection: str  # the first dir under the scope (e.g. "echo"), or the scope when flat
    status: str  # needs-review | reviewed | deprecated
    producer_kind: str  # connector | derived | vendored | manual | extracted
    command: str | None = None  # the `watermark <cmd>` regenerator
    connector_ref: str | None = None
    source: str  # human upstream label
    external_url: str | None = None
    license: str | None = None
    access_tier: str  # public | keyed | throttled
    site_scope: str  # lima-legacy | slug-scoped | basin-shared
    cadence: str  # daily | weekly | monthly | quarterly | annual | on-demand | static
    ttl_days: int | None = None
    last_refreshed: str | None = None
    tags: list[str] = Field(default_factory=list)
    storage: list[CatalogStorageFile] = Field(default_factory=list)
    observed: CatalogObserved | None = None  # None until `watermark catalog reconcile` has run
    citation: Citation


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


# --- ask-embeddings feed (issue #329) -----------------------------------------
class AskEmbeddingEntry(BaseModel):
    """One precomputed all-MiniLM-L6-v2 embedding for an ask-index unit (#329).

    Stored in the bundle as ``ask-embeddings.json`` and served as a static asset
    so the /api/ask Worker can embed the query at runtime and compute cosine
    similarity without an additional Python/Node dependency.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    """Stable id matching the corresponding AskUnit, ``{feed}:{local_id}``."""
    embedding: list[float]
    """384-dimensional L2-normalised float vector (all-MiniLM-L6-v2)."""


# --- hydrated catalog index feed (epic #1090 / #1093) -------------------------
# The closed catalog kind set — the shared vocabulary of both tiers. The Python builder emits only
# the feed-backed kinds; the Astro overlay (`web/src/lib/catalog.ts`) adds the web-only ones
# (teardown/doc/chapter/figure). Typing `kind` as this Literal makes the generated
# `catalog-index.schema.json` carry a `kind` enum, which the frontend parity-tests against so the
# two tiers' kind sets can't silently drift (`watermark.site.catalog_index.CATALOG_KINDS`).
CatalogKind = Literal[
    "record",
    "timeline",
    "entity",
    "person",
    "place",
    "meeting",
    "exhibit",
    "concept",
    "lead",
    "dataset",
    "teardown",
    "doc",
    "chapter",
    "figure",
]


class CatalogAtom(BaseModel):
    """One addressable, "grabbable" atom in the hydrated catalog (#1093).

    A *pointer*, not a copy: ``feed`` + ``local_id`` name the live bundle row this handle
    resolves against at render time, so a user Story can cite a record without ever forking it
    (chain of custody). ``handle`` is the canonical address ``<kind>:<site>:<local_id>``, where
    ``local_id`` reuses the source feed's **existing** stable key (``rel``/``key``/``slug``/
    ``id``/``ref``) — no new ids are minted.
    """

    model_config = ConfigDict(extra="forbid")

    handle: str  # canonical address: <kind>:<site>:<local_id>
    kind: CatalogKind  # one of the closed catalog kinds (record, entity, timeline, meeting, ...)
    site: str  # the network-site slug this atom belongs to
    local_id: str  # the source feed's existing stable key
    title: str  # human-readable label for the grab UI
    feed: str  # the source feed name this atom resolves into (pointer, not copy)


class CatalogIndex(BaseModel):
    """The hydrated catalog — the addressable atom index the Story write/read paths consume (#1093).

    Emitted as an object feed carrying two version stamps: ``catalog_version`` (a content hash over
    the atom set, so #1099 can detect when a user Story's handles may have drifted) and the source
    ``contract_version``. The Python tier emits the feed-backed kinds here; the Astro build overlays
    the web-only kinds (``teardown``/``doc``/``chapter``/``figure``) at render time, so the resolver
    sees one merged catalog.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    catalog_version: str  # sha256 over the sorted atom handles — stable across identical corpora
    contract_version: str  # the bundle contract these atoms were indexed under
    atoms: list[CatalogAtom] = Field(default_factory=list)


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

    site: str  # the network-site slug this bundle is for (#762) — so a bundle self-identifies
    bundle_version: str  # the data generation's version (bumped on every export)
    contract_version: str  # the schema/contract version these feeds conform to
    generated_at: str  # ISO-8601 UTC
    feed_count: int
    row_total: int  # sum of feed counts — a quick internal-consistency check
    feeds: list[FeedRef] = Field(default_factory=list)
