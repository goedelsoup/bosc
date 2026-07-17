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

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field

from watermark.provenance import Confidence as Confidence
from watermark.provenance import SourceKind as SourceKind
from watermark.provenance import source_is_verified
from watermark.site.readiness import State, Tier  # the readiness vocabulary SSOT (#1220)

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
# 1.12.0: adds the `economics-demand-pressure` object feed (#1105) — the facility demand→consumer-
#   price-pressure sensitivity (`FacilityDemandPressure`): households-equivalent, demand share, and
#   the STYLIZED price-pressure band, each a `ProvenancedValue`. Facility-gated — absent for a thin
#   site with no documented facility (mirrors `derive_demand_pressure`'s own gate).
# 1.13.0: adds the `routed-hydrograph` object feed (#1184) — the loop's design-storm hydrograph
#   routed down the cited confluence graph via Muskingum-Cunge (`RoutedHydrographNetwork`): the
#   routed vs. naive-summed outlet hydrograph series, the peak `attenuation_pct` + `lag_hr`, the
#   per-reach attenuation/lag table, and the `site` label. Absent when the topology or reach
#   table is missing.
# 1.14.0: the cooling `basis` (`CoolingBasis`, embedded in `hydrology-scenarios`) gains the optional
#   `makeup_high` ProvenancedValue — the campus intake at the upper consumptive bound (#1153), read
#   by refill instead of back-calculating consumptive_high/consumptive_fraction across incompatible
#   per-archetype bases. Additive/optional: absent (null) for the fraction-uncertainty archetypes.
# 1.15.0: `economics-baseline` surfaces QCEW wages (#1109) — the county total and each sector gain
#   `avg_annual_pay` (USD/year) and `avg_weekly_wage` (USD/week) `ProvenancedValue`s (already in the
#   fetched CSV, previously dropped). Optional/backward-compatible: a suppressed or zero-wage slice
#   omits the field rather than asserting a fabricated $0.
# 1.16.0: adds the `energy-burden` object feed (#1110) — median household income (Census B19013)
#   with derived electricity / gas / combined household energy burden (% of income), a fully
#   `[derived]` consumer-impact metric alongside `consumer-energy`. Present only where the site's
#   committed baseline carries income; absent (section degrades) otherwise.
# 1.17.0: the manifest gains the `readiness` block (#1220/#1222) — the standing domain-activation
#   readiness (`SiteReadiness`): the five domains' `absent|seeded|live` states plus the derived
#   `tier` (`stub|backdrop|case|reference`), recomputed at every export from feed counts + the
#   profile (watermark.site.readiness). The frontend reads it instead of re-deriving section gating.
# 1.18.0: adds the air-quality & backup-generation dispatch feeds (epic #1172, #1181) —
#   `air-scenarios` (Tier-0 emissions scenarios + synthetic-minor NSR cap check, #1177) and
#   `air-dispersion` (Tier-1 AERMOD concentration screen vs NAAQS, event-anchored, #1182).
#   Dispersion is facility+permit-gated (absent → section locks); dispersion runs carry
#   `available=False` when the AERMOD binary/met is absent (deck + NAAQS basis real, no
#   fabricated concentration). Both reuse the domain models (watermark.air), like hydrology-scenarios.
# 1.19.0: adds the `air-dispersion-field` collection feed (epic #1237 / #1232) — the gridded AERMOD
#   concentration surface per pollutant (`DispersionField`) the deck.gl FieldLayer renders: the
#   receptor grid reshaped into per-averaging-period `values[]`, the model-grid→lon/lat `geo_ref`
#   corner box, per-period NAAQS lines, and a fixed `provenance: assumption` marker (the CBI-redacted
#   stack ⇒ [inference]). Reference-site gated; `available=False` with empty `values` when the AERMOD
#   binary/met is absent (geometry real, no fabricated concentration).
# 1.20.0: adds the `reach-network` object feed (epic #1237 / #1235) — the real river-centerline
#   geometry (`ReachNetwork`) the deck.gl FlowLayer particle-advection viz advects over: one
#   downstream-oriented `ReachLine` (lon/lat polyline) per model reach node, keyed by `node_id`
#   so the frontend joins flow magnitude (routed-hydrograph) + deficit (hydrology-scenarios) by
#   node. Geometry is verbatim NHDPlus via USGS NLDI (watermark.hydrology.reach_geometry),
#   committed under data/reference/hydrology/reaches/. Reference-site gated like routed-hydrograph;
#   absent when the committed centerline file is missing (nothing invented).
# 1.21.0: adds the `greenops` object feed (#1076/#1084) — Watermark's own compute footprint
#   (`GreenopsReport`): the usage → electricity → water derivation, with headline stats,
#   compute-by-function / AI-by-task / monthly-electricity / water breakdowns, and a methodology
#   block, every figure a `ProvenancedValue` tagged reference/derived/assumption (never verified —
#   our own consumption is modeled, not metered). Global like `network`: emitted into every
#   bundle identically from the committed data/reference/greenops/footprint.yaml (a modeled
#   placeholder when that artifact is absent, so the feed is never skipped).
# 1.22.0: adds the `water-seasonal-field` object feed (epic #1237 / #1236) — the seasonal
#   evaporation / net-atmospheric-withdrawal climograph the deck.gl FieldLayer renders as a
#   cartesian month-axis strip (Phase 2, water). The field scalar is net atmospheric withdrawal
#   (reference ET0 - precip, mm/day, from the cited NASA POWER normals + FAO-56 ET0); the deficit
#   boundary (net=0) is the threshold isopleth. The per-month low-flow `multiple` rides along for
#   the SSR table/probe and is [inference] (it screens the modeled buildout draw). Reference-site
#   gated; `available=False` with empty `months` when the climate/scenario inputs are absent.
# 1.23.0: adds an optional quantitative range to `ProvenancedValue` (#760) — `low`/`high`
#   absolute bounds around the central `value`, distinct from the qualitative `confidence`.
#   A measured/derived estimate whose honest representation is a band ("226 ± ~35 ac") now
#   carries the spread as data rather than prose in the citation, so the bundle/frontend and
#   the uncertainty engine (#271) consume it uniformly. Both bounds optional (a document-
#   verbatim figure stays a single value); back-compatible — every feed embedding a
#   `ProvenancedValue` gains the two nullable fields.
# 1.24.0: adds the `contacts` collection feed — the curated per-site directory of human contact
#   points (petitioners, organizers, officials, community groups, outlets) a reader can reach.
#   Slug-scoped committed YAML (`data/site/contacts.yaml`, sibling reads its own `<slug>/`),
#   modeled like `leads` (#796): every contact names a real `source` (no fabricated people, per
#   the data-discipline rules) and carries only *public* routing (`links`) — private hand-off
#   addresses stay server-side. The spine the petition-connect + bulletin surfaces reference;
#   absent → the feed is skipped and the section degrades. Back-compatible (additive feed +
#   the `contact` catalog kind).
# 1.25.0: adds the `facts` collection feed — the normalized `(subject, predicate, value, unit,
#   status, evidence)` projection over the bundle's already-provenanced numeric facts (#1587,
#   epic #1579 Phase 3). A `catalog-index`-style post-pass (`watermark.site.facts`): it mints no
#   values and copies no payloads, it re-keys each `ProvenancedValue` already in the economics /
#   greenops / hydrology / air feeds (plus the derived facility `PowerBasis`) into one flat,
#   queryable table so a fact question is a tiny retrieval + arithmetic, not a whole-record pull.
#   `status` is the evidence-discipline tag derived from each value's `source_kind`
#   (`watermark.provenance.evidence_tag`: document/connector→verified, reference→reference,
#   assumption/derived→inference; `open` is reserved for unquantified facts). `evidence` reuses
#   the shared provenance shape but `page` stays null where the source `ProvenancedValue` carries
#   none — never invented (chain of custody). Powers the `get_facts` MCP tool. `rsei`/`records`
#   projection + `aggregate_facts` (#1588) are deferred follow-ups. Back-compatible (an additive
#   collection feed; registered in the `catalog` like any dataset, no new catalog-index kind).
# 1.26.0: adds the `passages` collection feed + its `passage-embeddings` companion — the page-level
#   excerpt index the `search_passages` MCP tool returns instead of a whole extracted record (#1589,
#   epic #1579 Phase 3). `passages` carries one `PassageItem` per text-bearing page of a *published*
#   source PDF (scoped to the default-deny publish allowlist #280, so no non-published source text
#   ships): `document_id` joins to the `documents` feed / `get_document` by `DocumentItem.rel`, `page`
#   is the 1-indexed printed page, `text` is the pypdf text-layer extraction verbatim (garbled OCR for
#   scans — a locator, never a transcription; image-only pages are omitted). `passage-embeddings` is
#   the all-MiniLM-L6-v2 vector companion (the same 384-dim space as `ask-embeddings`) for the hybrid
#   BM25+vector search; like `ask-embeddings` both feeds are always emitted (empty when the source PDFs
#   are absent / `--no-embeddings`) so the schema set stays stable. Not cataloged (a retrieval index,
#   like `ask-embeddings`). Back-compatible (two additive feeds, no changed shapes).
# 1.27.0: adds the `open-questions` collection feed (#1568, epic #1560 workstream B) — the aggregated
#   still-open threads of the corpus, each with provenance. A post-pass projection
#   (`watermark.site.open_questions`) over the just-assembled `leads` + `hypothesis-assessments` feeds:
#   every `[open]`-tagged lead (wired to the `lead:kind:question` / `lead:status:unanswered` label
#   vocabulary) + every `[open]`-tagged hypothesis cell, ported from yidam's `open-questions` model
#   (open ⇔ the `[open]` tag). Skipped for a site with no open threads, so `hasFeed("open-questions")`
#   is false and the section degrades rather than shipping an empty list. Not cataloged (a derived
#   view — the underlying leads are already cataloged). Back-compatible (one additive feed).
CONTRACT_VERSION = "1.27.0"

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


# --- facts feed (#1587) --------------------------------------------------------
# The evidence-discipline vocabulary a normalized fact renders as: the three tags a
# `source_kind` maps to (`watermark.provenance.evidence_tag`), plus `open` for an asserted-
# but-unquantified fact (a known predicate with no value yet — a lead). A projection over the
# provenanced feeds yields only verified/inference/reference; `open` rides along for the
# readiness/leads tie-in (deferred).
FactStatus = Literal["verified", "inference", "reference", "open"]


class FactEvidence(BaseModel):
    """Where a normalized fact came from — the `Citation` shape, projected from a value's
    provenance.

    A `ProvenancedValue` (the carrier of every typed numeric fact — economics, greenops,
    hydrology, air, facility power) records provenance as a single free-text ``citation``
    with **no structured page**, so a projected fact keeps that text verbatim in
    ``citation`` and lifts a repo-relative artifact path into ``source`` only when the text
    *is* one. ``page`` is populated **only** where the source genuinely carries one and is
    **never invented** — the chain-of-custody discipline (root CLAUDE.md): a value with no
    page yields ``page=null``, honestly.
    """

    model_config = ConfigDict(extra="forbid")

    source: str | None = None  # repo-relative artifact path / dataset label / doc id, when known
    source_kind: SourceKind = "document"
    page: int | None = None  # 1-based page, only where the source carries it — never fabricated
    citation: str | None = None  # the ProvenancedValue free-text citation, verbatim
    confidence: Confidence = "medium"
    asof: str | None = None  # ISO date/datetime for a live (connector) value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        """True when grounded in a record or a live gauge (``[verified]`` in prose)."""
        return source_is_verified(self.source_kind)


class FactItem(BaseModel):
    """One normalized ``(subject, predicate, value, unit, status, evidence)`` fact.

    The `facts` feed is a projection (`watermark.site.facts`), not a new extraction: every row
    re-keys a `ProvenancedValue` the bundle already ships (or the derived facility
    `PowerBasis`) into a flat, queryable tuple, so ``get_facts`` answers a fact question with a
    tiny retrieval instead of a whole-record pull. ``subject`` is a stable ``<kind>:<id>`` key
    (mirroring the catalog handle grammar) with a human ``subject_label``; ``predicate`` is a
    normalized snake_case field name; ``status`` is the evidence-discipline tag
    (`watermark.provenance.evidence_tag`) derived from the value's ``source_kind``; ``feed``
    names the source bundle feed the fact was projected from (a pointer, not a copy).
    """

    model_config = ConfigDict(extra="forbid")

    subject: str  # canonical key, e.g. "facility:lima", "county:39003", "naics:39003:62"
    subject_label: str  # human display, e.g. "Allen County, Ohio"
    subject_kind: str  # site | county | state | facility | sector | hydrology-scenario | ...
    predicate: str  # normalized snake_case field name, e.g. "genset_count", "demand_share_pct"
    value: float | int | None = None  # None ⇒ an asserted-but-unquantified fact (status=open)
    unit: str | None = None
    status: FactStatus
    approximate: bool = False  # the transcription `~` marker, as data
    low: float | None = None  # quantitative uncertainty band (#760), carried through
    high: float | None = None
    evidence: FactEvidence
    feed: str  # the source bundle feed this fact was projected from


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


# --- open-questions feed (issue #1568, epic #1560 workstream B) ----------------
# Where a still-open question was aggregated from: the per-site `leads` board, or an `[open]`-tagged
# cell of the boom-origin hypothesis matrix. Ports yidam's `open-questions` model (a node is open
# when it carries the `[open]` tag) — see `watermark.site.corpus_mirror.render_open_questions`.
OpenQuestionOrigin = Literal["lead", "hypothesis"]


class OpenQuestionItem(BaseModel):
    """One unanswered question in the corpus — an `[open]`-tagged lead or hypothesis cell.

    The `open-questions` feed is a **projection** (`watermark.site.open_questions`), not a new
    extraction: it aggregates every still-open thread the bundle already ships — the `[open]`-tagged
    rows of the `leads` feed (the per-site board, wired to the `lead:kind:question` /
    `lead:status:unanswered` label vocabulary) and the `[open]`-tagged cells of the
    `hypothesis-assessments` matrix (a documented gap under a boom-origin lens) — into one flat,
    provenanced list. It ports yidam's `open-questions` model: a node is open when it carries the
    `[open]` tag (`claim_tag == "open"`), so an `[inference]`-tagged lead (a labeled reading, not a
    gap) is deliberately excluded, exactly as `render_open_questions` excludes it.

    Every row names a real ``source`` — the citation where the gap is recorded (a lead's source, or
    the hypothesis cell's committed matrix file). The lead-derived fields (``kind``/``status``/
    ``issue``) are present only for ``origin == "lead"``; the hypothesis-derived fields
    (``hypothesis``/``hypothesis_label``/``signal``) only for ``origin == "hypothesis"``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable id: the lead id, or `hyp:<hypothesis>:<site>` for a matrix cell
    origin: OpenQuestionOrigin
    question: str  # the open question — the lead title, or a synthesized cell prompt
    detail: str  # one honest paragraph of context (never fabricated)
    source: str  # the real provenance citation — where this gap is recorded
    # lead-derived context (present when origin == "lead") — the lead:kind:* / lead:status:* vocab.
    kind: LeadKind | None = None
    status: LeadStatus | None = None
    issue: int | None = None  # a linked tracking issue, when the lead names one
    # hypothesis-derived context (present when origin == "hypothesis").
    hypothesis: str | None = None  # the lens id ("water" | "defense" | "surveillance")
    hypothesis_label: str | None = None  # the human lens label, e.g. "H1 Water & Coercion"
    signal: str | None = None  # the cell's signal strength ("anchor"|"strong"|"moderate"|"watch")


# --- contacts feed ------------------------------------------------------------
# The kinds of human contact point a site carries. `petitioner` and `organizer` are the ones the
# petition-connect + bulletin surfaces route to; `official`/`group`/`outlet` round out the directory.
ContactKind = Literal["petitioner", "organizer", "official", "group", "outlet"]


class ContactLink(BaseModel):
    """One *public* way to reach or read about a contact — a petition page, website, or social.

    Public routing only: private hand-off addresses (where a petition-connect is delivered) never
    enter the bundle; they live server-side (Phase 2). A bare label + URL, no provenance of its own
    (the parent :class:`ContactItem` carries the ``source``).
    """

    model_config = ConfigDict(extra="forbid")

    label: str  # short human label ("petition", "website", "Facebook")
    # Validated http(s) URL: malformed or non-http(s) values (e.g. `javascript:`) are rejected at
    # load time, so a curated link can never reach the frontend as an unsafe `href`. Serializes to a
    # plain string in the bundle (`model_dump(mode="json")`), so the feed's wire shape is unchanged.
    url: HttpUrl


class ContactItem(BaseModel):
    """One curated site-level contact point — a petitioner, organizer, official, group, or outlet.

    The per-site directory a reader can act on: read from `data/site/contacts.yaml` (slug-scoped),
    so a sibling site carries its own contacts, not Lima's (mirrors `leads`, #796). Every contact
    names a real committed ``source`` — no fabricated people, per the data-discipline rules — and
    exposes only *public* routing via ``links``; private hand-off addresses stay server-side.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable local id (kebab slug), the catalog handle's local_id
    kind: ContactKind
    name: str
    org: str | None = None  # affiliated organization, when distinct from the name
    role: str | None = None  # title / relationship ("lead organizer", "county commissioner")
    summary: str  # what they work on / the cause — one honest sentence
    links: list[ContactLink] = Field(default_factory=list)
    place: str | None = None  # where they're based, when documented
    source: str  # the real citation — where this contact is documented
    tags: list[str] = Field(default_factory=list)
    issue: int | None = None  # a linked tracking issue, when one exists


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


# --- passages feed (issue #1589, epic #1579 Phase 3) --------------------------
class PassageItem(BaseModel):
    """One page-level passage from a *published* source PDF — a page-cited excerpt (#1589).

    The unit the ``search_passages`` MCP tool returns instead of a whole extracted record: one
    relevant permit page shouldn't require pulling the full extraction. Scoped to the default-deny
    public-publish allowlist (#280) so no non-published source text ever ships in the bundle.

    ``document_id`` is the source document's ``DocumentItem.rel`` (path relative to
    ``data/documents``) — the join key to the ``documents`` feed and ``get_document``. ``text`` is
    the pypdf text-layer extraction verbatim; for a scanned document it is garbled OCR (per the root
    CLAUDE.md, never trust its digits), so treat it as a **locator** for the cited page, not a
    transcription. Image-only pages (no text layer) carry no excerpt and are omitted from the feed.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable passage id — ``{document_id}#p{page}``
    document_id: str  # DocumentItem.rel — path relative to data/documents (the join key)
    collection: str  # first path segment of document_id (e.g. "oepa") — the collection axis
    title: str  # the source document's catalog name, for display
    page: int  # 1-indexed printed page number (matches DocumentEntry provenance)
    # Sub-page heading when known; page chunks carry none today. Required-but-nullable (the builder
    # always emits it, `null` for unknown) so the feed contract matches the web `PassageRow` shape.
    section: str | None
    text: str  # the page's text-layer extraction (capped), verbatim


class PassageEmbeddingEntry(BaseModel):
    """One precomputed all-MiniLM-L6-v2 embedding for a :class:`PassageItem` (#1589).

    The passage-level peer of :class:`AskEmbeddingEntry`: stored as ``passage-embeddings.json`` and
    served as a static asset so the ``search_passages`` Worker can embed the query at runtime (the
    same 384-dim space) and compute cosine similarity for the hybrid BM25+vector rank. Absent
    entries degrade the tool to BM25-only, so a partial index is fine.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    """Stable id matching the corresponding :class:`PassageItem`, ``{document_id}#p{page}``."""
    embedding: list[float]
    """384-dimensional L2-normalised float vector (all-MiniLM-L6-v2)."""


# --- hydrated catalog index feed (epic #1090 / #1093) -------------------------
# The closed catalog kind set — the shared vocabulary of both tiers. The Python builder emits only
# the feed-backed kinds; the Astro overlay (`web/packages/core/src/catalog.ts`) adds the web-only ones
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
    "contact",
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


# --- air dispersion field (GPU field/flow viz, epic #1237 / #1232) ------------------------
# A gridded AERMOD concentration surface for one pollutant — the deck.gl FieldLayer reads it
# (epic #1237). Distinct from the `air-dispersion` NAAQS *screen* feed (peak-vs-standard, per
# period): this is the full receptor grid reshaped into per-period `values[]` arrays plus the
# model-grid→lon/lat `geo_ref` the frontend georeferences the field with.


class DispersionGrid(BaseModel):
    """The receptor-grid geometry in AERMOD model metres (source at the origin, X=east, Y=north).

    ``x0_m``/``y0_m`` are the SW corner; ``nx``/``ny`` the counts; ``dx_m``/``dy_m`` the spacing.
    A period's ``values[]`` is row-major over this grid — ``values[iy * nx + ix]`` — so the
    frontend can index it without carrying per-cell coordinates.
    """

    model_config = ConfigDict(extra="forbid")

    nx: int = Field(ge=1)
    ny: int = Field(ge=1)
    dx_m: float = Field(gt=0)
    dy_m: float = Field(gt=0)
    x0_m: float  # SW-corner easting, relative to the source at (0, 0)
    y0_m: float  # SW-corner northing


class DispersionGeoRef(BaseModel):
    """The model grid's WGS84 corner box — how the frontend places the field on the map.

    The source sits at ``(source_lon, source_lat)``; ``sw``/``ne`` bound the axis-aligned grid
    (a deck.gl ``[west, south, east, north]`` box). Derived by a local flat-earth projection of
    the metre grid about the source, so it inherits the field's ``assumption`` provenance.
    """

    model_config = ConfigDict(extra="forbid")

    crs: str = "WGS84 (EPSG:4326)"
    source_lon: float
    source_lat: float
    sw_lon: float
    sw_lat: float
    ne_lon: float
    ne_lat: float


class DispersionPeriodField(BaseModel):
    """One averaging period's gridded concentration surface + its NAAQS reference line."""

    model_config = ConfigDict(extra="forbid")

    averaging_period: str  # the AERMOD AVE token: "1", "8", "24", "ANNUAL", ...
    values: list[float | None] = Field(default_factory=list)  # µg/m³, row-major; null = no receptor
    max_conc_ug_m3: float | None = None  # peak over the grid, when receptors are present
    naaqs_ug_m3: float | None = None  # the standard for this (pollutant, period), when one exists
    exceeds_naaqs: bool = False  # peak > standard (screening only — a flag, not a violation)


class DispersionField(BaseModel):
    """A gridded AERMOD dispersion surface for one pollutant — the #1232 deliverable.

    ``provenance`` is fixed to ``assumption``: the Lima permit redacts the genset stack geometry
    as CBI, so every modeled concentration inherits that assumed input and the frontend must
    render it ``[inference]``, never ``[verified]``. ``available`` is False (with empty ``values``)
    when the AERMOD binary/met is absent — the grid geometry, ``geo_ref`` and NAAQS lines still
    resolve, but no concentration is fabricated (the same honest degrade as ``air-dispersion``).
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    pollutant: str
    unit: str = "ug/m3"
    provenance: Literal["assumption"] = (
        "assumption"  # CBI-redacted stack ⇒ [inference], not [verified]
    )
    available: bool = False
    grid: DispersionGrid
    geo_ref: DispersionGeoRef
    periods: list[DispersionPeriodField] = Field(default_factory=list)
    stack_is_assumption: bool = True
    engine_version: str = ""
    caveats: list[str] = Field(default_factory=list)
    note: str = ""

    @classmethod
    def from_receptors(
        cls,
        *,
        site: str,
        pollutant: str,
        grid: DispersionGrid,
        geo_ref: DispersionGeoRef,
        period_receptors: dict[str, list[tuple[float, float, float]]],
        naaqs: dict[str, float | None],
        available: bool,
        unit: str = "ug/m3",
        stack_is_assumption: bool = True,
        engine_version: str = "",
        caveats: list[str] | None = None,
        note: str = "",
    ) -> DispersionField:
        """Reshape per-period ``(x_m, y_m, conc)`` receptors onto ``grid`` → a ``DispersionField``.

        Each period in ``period_receptors`` becomes a :class:`DispersionPeriodField` whose
        ``values[]`` is the row-major grid (null where no receptor landed — e.g. the source cell).
        ``naaqs`` supplies the per-period standard (µg/m³, or ``None`` where none is defined). An
        empty ``period_receptors`` (the binary/met-absent degrade) yields periods with empty
        ``values`` — the geometry is real, nothing is invented.
        """
        cells = grid.nx * grid.ny
        periods: list[DispersionPeriodField] = []
        for ave in period_receptors:
            recs = period_receptors[ave]
            values: list[float | None] = [None] * cells if recs else []
            peak: float | None = None
            for x_m, y_m, conc in recs:
                ix = round((x_m - grid.x0_m) / grid.dx_m)
                iy = round((y_m - grid.y0_m) / grid.dy_m)
                if 0 <= ix < grid.nx and 0 <= iy < grid.ny:
                    values[iy * grid.nx + ix] = conc
                    peak = conc if peak is None else max(peak, conc)
            std = naaqs.get(ave)
            periods.append(
                DispersionPeriodField(
                    averaging_period=ave,
                    values=values,
                    max_conc_ug_m3=peak,
                    naaqs_ug_m3=std,
                    exceeds_naaqs=bool(std is not None and peak is not None and peak > std),
                )
            )
        return cls(
            site=site,
            pollutant=pollutant,
            unit=unit,
            available=available,
            grid=grid,
            geo_ref=geo_ref,
            periods=periods,
            stack_is_assumption=stack_is_assumption,
            engine_version=engine_version,
            caveats=caveats or [],
            note=note,
        )


# --- reach-network centerlines (GPU flow viz, epic #1237 / #1235) --------------------------
# The real river-centerline geometry the deck.gl FlowLayer advects particles over. The model
# reaches (network.yaml / reaches.yaml) carry no coordinates, so this is verbatim NHDPlus via
# USGS NLDI (watermark.hydrology.reach_geometry), committed under data/reference/hydrology/reaches/.
# Keyed by `node_id`, so the frontend joins each reach's flow magnitude (from routed-hydrograph)
# and deficit state (from hydrology-scenarios) without re-carrying those numbers here.


class ReachLine(BaseModel):
    """One reach node's river centerline — a downstream-oriented (lon, lat) polyline."""

    model_config = ConfigDict(extra="forbid")

    node_id: str  # the network.yaml node id (join key)
    name: str
    receiving_water: str | None = None
    downstream: str | None = None  # the node this reach drains into (None at the outlet)
    length_km: float
    coordinates: list[tuple[float, float]]  # (lon, lat), ordered head → downstream


class ReachNetwork(BaseModel):
    """The reach network's river-centerline geometry for the FlowLayer viz (#1235)."""

    model_config = ConfigDict(extra="forbid")

    site: str
    crs: str = "WGS84 (EPSG:4326)"
    reaches: list[ReachLine] = Field(default_factory=list)
    note: str = ""
    caveats: list[str] = Field(default_factory=list)


# --- water seasonal evaporation / net-atmospheric-withdrawal field (epic #1237 / #1236) ----
# The seasonal climograph the deck.gl FieldLayer renders as a cartesian month-axis strip (Phase-2
# water). The field scalar is net atmospheric withdrawal (reference ET0 - precip, mm/day) from the
# cited NASA POWER normals + FAO-56 ET0; the deficit boundary (net=0) is the load-bearing threshold
# isopleth. Distinct from `hydrology-scenarios` (the annual water balance): this is the month-by-
# month seasonal read `watermark.hydrology.scenario.evaluate_seasonal` produces.


class SeasonalMonthCell(BaseModel):
    """One month of the seasonal climograph: the climate drivers + the low-flow screen.

    ``net_atmospheric_mm_day`` (ET0 - precip) is the field scalar the FieldLayer ramps; a positive
    value is a growing-season deficit (ET exceeds precipitation, so no rainfall buffer).
    ``multiple`` is the draw read against ``low_flow_cfs`` (the cited seasonal floor — 30Q10 summer
    in the growing season, else the annual 7Q10); it rests on the *modeled* buildout draw, so the
    frontend renders it ``[inference]``, never a measured withdrawal.
    """

    model_config = ConfigDict(extra="forbid")

    month: str  # JAN..DEC
    growing_season: bool  # ET0 > precip this month
    et0_mm_day: float
    precip_mm_day: float
    net_atmospheric_mm_day: float  # ET0 - precip — the field scalar
    low_flow_cfs: float  # the cited design low flow applied this month
    low_flow_basis: str  # "30Q10 summer" | "7Q10 annual"
    consumptive_cfs: float  # this month's net consumptive draw (month-varying for hybrid)
    multiple: float | None  # draw / low_flow (None when the floor is 0)


class SeasonalField(BaseModel):
    """The seasonal evaporation / net-atmospheric-withdrawal climograph — the #1236 deliverable.

    A month-axis climograph the deck.gl FieldLayer renders as a cartesian strip (epic #1237, Phase
    2). The field scalar is net atmospheric withdrawal (reference ET0 - precip, mm/day): a one-hue
    bone->forest->ink ramp, with the deficit boundary (net=0) as the threshold isopleth — the
    growing-season edge, where ET starts to exceed precipitation. ``provenance`` is fixed to
    ``reference``: the climograph is the cited NASA POWER normals + FAO-56 ET0. The per-month
    ``multiple`` overlays the *modeled* buildout consumptive draw against the cited seasonal low
    flow, so that read is ``[inference]`` — surfaced in the SSR table/probe, never baked into the
    mm/day raster scalar. ``available`` is False (empty ``months``) when the climate/ET inputs or
    the buildout scenario are absent — the thresholds still resolve, nothing is fabricated.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    scenario: str
    cooling_model: str | None = None
    unit: str = "mm/day"  # the field scalar's unit (net atmospheric withdrawal)
    # The climograph is cited climate normals; the per-month `multiple` alone is [inference].
    provenance: Literal["reference"] = "reference"
    available: bool = False
    consumptive_cfs: float | None = None  # the headline draw screened (cfs)
    annual_7q10_cfs: float | None = None
    summer_30q10_cfs: float | None = None
    one_q10_cfs: float | None = None  # absolute design low flow (often 0)
    annual_multiple: float | None = None  # draw / annual 7Q10
    summer_multiple: float | None = None  # draw / summer 30Q10 — the seasonal headline
    growing_season_months: list[str] = Field(default_factory=list)
    months: list[SeasonalMonthCell] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    note: str = ""


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


class DomainReadiness(BaseModel):
    """Per-domain activation state (#1220): each of the five domains is ``absent|seeded|live``.

    Computed at export from feed counts + the ``SiteProfile`` by :mod:`watermark.site.readiness`
    (the SSOT for the predicates); this is only the wire shape. The ``State``/``Domain``
    vocabulary lives there so the schema and the computation can never drift.
    """

    model_config = ConfigDict(extra="forbid")

    backdrop: State
    facility: State
    places: State
    record: State
    story: State


class SiteReadiness(BaseModel):
    """The manifest's standing **readiness** block (#1220 / #1222): the per-domain states plus
    the tier :func:`watermark.site.readiness.site_tier` derives from them.

    Recomputed at every ``watermark export``, so it rises when a source lands and falls when one
    dries up — a standing property, not an onboard-time snapshot. The frontend
    (``web/packages/core/src/readiness.ts``) reads this instead of re-deriving section gating from raw
    feed counts (#1223).
    """

    model_config = ConfigDict(extra="forbid")

    tier: Tier
    domains: DomainReadiness


class Manifest(BaseModel):
    """The bundle index: version, provenance of the generation, and the feed list."""

    model_config = ConfigDict(extra="forbid")

    site: str  # the network-site slug this bundle is for (#762) — so a bundle self-identifies
    bundle_version: str  # the data generation's version (bumped on every export)
    contract_version: str  # the schema/contract version these feeds conform to
    generated_at: str  # ISO-8601 UTC
    feed_count: int
    row_total: int  # sum of feed counts — a quick internal-consistency check
    readiness: SiteReadiness  # standing domain-activation readiness (#1220) — tier + per-domain
    feeds: list[FeedRef] = Field(default_factory=list)
