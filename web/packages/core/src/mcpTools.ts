// Shared MCP tool schema registry (#917).
// Imported by both the dispatch layer (functions/api/_lib/mcpDispatch.ts) and the
// /network/connect page so the tool reference table is generated from the real schemas,
// not duplicated by hand.

import { FACT_CATEGORY_INPUTS, FACT_FEEDS, factCategorySummary } from "./factCategories";

/** A JSON-Schema property node. `items` is set on `type: "array"` params (e.g. the
 * get_document `fields`/`sections` projections); `properties` on a nested `type: "object"`
 * param (e.g. the search_corpus `filters` facet bag, #1582). */
export interface ToolProperty {
  type: string;
  description: string;
  default?: unknown;
  enum?: readonly string[];
  items?: { type: string; enum?: readonly string[] };
  properties?: Record<string, ToolProperty>;
}

/**
 * A JSON-Schema node (draft 2020-12 subset) for a tool's `outputSchema` (#1577). Richer than
 * the input-only `ToolProperty`: it nests (`properties` / `items`) and admits union/nullable
 * types (`type: ["string", "null"]`), so it can describe the whole governed result envelope and
 * its per-result item shapes — what MCP `structuredContent` is validated against.
 */
export interface JsonSchema {
  type?: string | readonly string[];
  description?: string;
  properties?: Record<string, JsonSchema>;
  required?: readonly string[];
  items?: JsonSchema;
  enum?: readonly unknown[];
  /** Closed only where the shape is fixed (the envelope); item schemas leave it open so a tool
   * can gain a field without breaking a client validating against this contract. */
  additionalProperties?: boolean;
}

export interface ToolSchema {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, ToolProperty>;
    required?: string[];
  };
  /**
   * The result contract (#1577, MCP 2025-06-18): the JSON Schema the tool's `structuredContent`
   * conforms to. Every tool returns the uniform governance envelope
   * `{ results, token_estimate, truncated, next_cursor }` (#1581), so this is that envelope
   * wrapping the tool's per-result item shape.
   */
  outputSchema: JsonSchema;
  /** One representative query that illustrates the tool's use. */
  example?: string;
}

// Response-size governance knobs (#1581), shared by every tool. Enforced peer:
// functions/api/_lib/mcpGovern.ts (this package can't import from @watermark/functions —
// dependency order is core → functions — so the intent names are duplicated here as the
// schema contract). Every tool response is wrapped as
// `{ results, token_estimate, truncated, next_cursor }` and bounded by these knobs.
const INTENT_NAMES = [
  "fact_lookup",
  "evidence_lookup",
  "timeline_reconstruction",
  "entity_research",
  "document_discovery",
  "cross_document_synthesis",
  "exhaustive_audit",
] as const;

const GOVERNANCE_PROPS = {
  intent: {
    type: "string",
    enum: INTENT_NAMES,
    description:
      "Preset that seeds sensible response-size defaults (max_results/max_tokens/max_tokens_per_result, plus the search_corpus response shape). Explicit knobs override it.",
  },
  max_results: {
    type: "integer",
    description: "Cap on results returned in one response (page size).",
  },
  max_tokens: {
    type: "integer",
    description: "Whole-response token ceiling; results are withheld (paginated) to stay under it.",
  },
  max_tokens_per_result: {
    type: "integer",
    description: "Per-result token ceiling; an over-cap result is shortened before it counts.",
  },
  cursor: {
    type: "string",
    description: "Continuation cursor from a prior response's next_cursor, to fetch the next page.",
  },
} as const;

// Duplicate-cluster dedup knobs (#1590), shared by the search tools. Enforced peer:
// functions/api/_lib/mcpDedup.ts, over the version/duplicate-cluster metadata the `documents`
// feed carries (curated from the custody manifests). A filing's versions — a permit's final +
// draft + fact sheet, or byte-identical copies — collapse to the authoritative (canonical) member.
const DEDUP_PROPS = {
  deduplicate: {
    type: "string",
    enum: ["none", "canonical"],
    description:
      "Collapse duplicate/version clusters (default canonical): a filing's versions fold to the canonical (authoritative) member. `none` returns every version separately (the raw ranked pool).",
    default: "canonical",
  },
  version_policy: {
    type: "string",
    enum: ["all", "latest_only", "latest_with_relevant_older_evidence"],
    description:
      "When deduplicate=canonical, how superseded versions are treated (default latest_with_relevant_older_evidence): keep the canonical PLUS any older version that carries a query-relevant term the canonical lacks (e.g. a draft's un-redacted figure). `latest_only` keeps only the canonical; `all` keeps every version (no collapse).",
    default: "latest_with_relevant_older_evidence",
  },
} as const;

// search_passages-specific dedup knobs: passages collapse ONLY byte-identical duplicate documents
// (identical pages) — draft/final page variants are always retained (their pages legitimately
// differ), so `version_policy` here governs only the duplicate pages, not draft-vs-final.
const PASSAGE_DEDUP_PROPS = {
  deduplicate: {
    type: "string",
    enum: ["none", "canonical"],
    description:
      "Collapse byte-identical duplicate documents to the canonical copy (default canonical): identical pages fold to one. Draft/final page variants are ALWAYS kept distinct (their pages differ). `none` returns every page.",
    default: "canonical",
  },
  version_policy: {
    type: "string",
    enum: ["all", "latest_only", "latest_with_relevant_older_evidence"],
    description:
      "Governs ONLY byte-identical duplicate pages here — draft/final page variants are always retained regardless. Both the default (latest_with_relevant_older_evidence) and `latest_only` drop the redundant duplicate pages; `all` disables collapse entirely.",
    default: "latest_with_relevant_older_evidence",
  },
} as const;

// The fact-category axis (#1827). `fact_category` is the written-down grouping over
// `FactItem.feed`; `feed` is the exact underlying axis for a caller who wants one source. Both
// live on get_facts AND aggregate_facts (they share the same pre-filter pair), and both are
// validated against the vocabulary in `factCategories.ts` — an unrecognized value returns that
// vocabulary rather than an empty result set, so a mistyped constraint can never read as "the
// corpus has no such facts". The enum + the per-category feed list are generated from that one
// registry, so schema and filter cannot drift.
const FACT_CATEGORY_PROP: ToolProperty = {
  type: "string",
  // Canonical keys AND the accepted aliases (`water-cooling`, …) — the enum must not reject a
  // value the handler resolves, or a schema-strict client can't use the #1691-published names (#1827).
  enum: [...FACT_CATEGORY_INPUTS],
  description: `Restrict to one fact category — a named grouping over the source feeds each fact was projected from: ${factCategorySummary()}. Note \`economics-demand-pressure\` is grouped under \`energy\`, not \`economics\`: its predicates are grid quantities (demand_share_pct, load_factor, state_retail_sales_gwh, price pressure), not labor-market ones. \`facility-power\` (what the facility draws) is kept separate from \`energy\` (what power costs the public). An unrecognized value returns the vocabulary, not an empty set. For one exact source feed instead of a grouping, use \`feed\`.`,
};

const FACT_FEED_PROP: ToolProperty = {
  type: "array",
  items: { type: "string", enum: FACT_FEEDS },
  description: `Restrict to these exact source feeds — the \`feed\` each fact carries (${FACT_FEEDS.join(", ")}). A single string is also accepted. The precise axis under \`fact_category\`; combined with it they AND, and an impossible pair is reported as a contradiction rather than returning nothing.`,
};

// Structured facet filters for search_corpus (#1582, extended by #1691) — a bag of AND-combined
// constraints over fields the ask-index ALREADY carries, so the ranked pool is narrowed before
// scoring. The canonical feed key is `feed`; `collection` here (and the legacy top-level param) is
// accepted as an alias but names a BUNDLE FEED, not a document-collection slug — reconciling the
// historical collision with get_documents' `collection`. `fact_category` is deliberately NOT a
// facet here (#1827): the `facts` feed is not in the ask index, so the constraint would filter on
// a field no unit carries and silently return nothing. It lives on get_facts / aggregate_facts,
// where the field is real, and the description below points there.
const SEARCH_FILTERS_PROP = {
  filters: {
    type: "object",
    description:
      "Structured facet constraints over indexed corpus fields — all optional and AND-combined, applied before ranking so unrelated feeds/records don't crowd the results. Facets: site, feed (alias collection), source_kind, verified, date_from, date_to, confidence, county, agency, permit_number, document_type, entity, project (alias campus). Every one is a real indexed field: a unit whose feed carries no value for a facet is EXCLUDED when you set it, so combining a narrow facet with a broad one can legitimately return nothing. NOTE: `feed`/`collection` here is a BUNDLE FEED, not a document-collection slug — for oepa/recorder/aedg collections use get_documents. For fact categories (economics / energy / facility-power / water / air / platform) use the `fact_category` filter on get_facts / aggregate_facts — normalized facts are not part of this index.",
    properties: {
      site: {
        type: "string",
        description: "Site slug (e.g. lima, fort-wayne). Mirrors the top-level `site`.",
      },
      feed: {
        type: "string",
        description:
          "Bundle feed: records, documents, timeline, entities, meetings, people, places, concepts. A BUNDLE FEED, NOT a document-collection slug (oepa/recorder/aedg → get_documents). `collection` is an accepted alias.",
      },
      collection: {
        type: "string",
        description:
          "Alias of `feed` (kept for back-compat); names a bundle feed, not a document collection.",
      },
      source_kind: {
        type: "string",
        enum: ["document", "derived"],
        description:
          "Provenance class: `document` (grounded in a primary source) vs `derived` (editorial synthesis, e.g. glossary concepts).",
      },
      verified: {
        type: "boolean",
        description: "Keep only [verified] units (true) or only unverified units (false).",
      },
      date_from: {
        type: "string",
        description:
          "Inclusive ISO-8601 lower bound on a unit's structured date (dated feeds only — timeline/meetings). Undated units are excluded when set.",
      },
      date_to: {
        type: "string",
        description:
          "Inclusive ISO-8601 upper bound on a unit's structured date. Undated units are excluded when set.",
      },
      confidence: {
        type: "string",
        description: "Citation confidence band (e.g. high, medium, low), matched exactly.",
      },
      // --- Enrichment facets (#1691) ---------------------------------------------------------
      county: {
        type: "string",
        description:
          "County the site's records are filed in. The state suffix and the word 'county' are optional — 'Allen', 'Allen County' and 'Allen County, OH' are the same constraint.",
      },
      agency: {
        type: "string",
        description:
          "Issuing/administering body, matched as a case-insensitive SUBSTRING of the record's own agency text (which is the document's wording, e.g. 'Ohio EPA (Division of Surface Water)'). So `Ohio EPA` reaches every Ohio EPA division; `USACE` will not — try 'Army Corps'. Records only; other feeds carry no issuing body and are excluded when this is set.",
      },
      permit_number: {
        type: "string",
        description:
          "Permit / case / filing identifier (NPDES `OH0026069`, Ohio `2PH00006*LD`, an OPSB case number, a WPCLF award no). Separators and case are ignored, and a BASE number matches every modification filed under it — `2PH00006` returns `*LD`, `*MD`, `*PD`; asking for `2PH00006*LD` returns only that one.",
      },
      document_type: {
        type: "string",
        description:
          "Document genre, the axis `feed` can't express (a `records` feed spans all of these): permits-npdes, permits-epa, permits-sos, deeds, land-assembly, enforcement, litigation, local-legislation, finance, labor, plans, opc — plus timeline categories (epa_permit_action, county_resolution, deed_recorded, …) and meeting kinds (minutes).",
      },
      entity: {
        type: "string",
        description:
          "Entity-graph key, exactly as get_entities returns it (e.g. `AMAZON COM SERVICES`) — case and punctuation are ignored. Returns the party's own node plus every record/timeline/meeting/place it is attributed to, joined on the extraction path the entity was read from (never on a name match).",
      },
      project: {
        type: "string",
        description:
          "Campus / named project slug — the `facility` feed's key (`project-bosc`, `project-klondike`, `van-wert-mega-site`), or the slug of a project the corpus names but no facility row covers (`project-dazzler`). `campus` is an accepted alias.",
      },
      campus: {
        type: "string",
        description: "Alias of `project`; names the same campus/project facet.",
      },
    },
  },
} as const;

// --- Output schemas (#1577) --------------------------------------------------------
// The MCP 2025-06-18 revision formalizes `outputSchema` (on the tool) + `structuredContent`
// (on the tool-call result). Every tool returns the uniform governance envelope
// `{ results, token_estimate, truncated, next_cursor }` (see GOVERNANCE_PROPS / mcpGovern), so
// each `outputSchema` is `governedEnvelope(<item shape>)`. An item schema names only the
// always-present fields as `required` and leaves the mode-/projection-/budget-dependent ones
// optional; `additionalProperties` stays open on items so a shape can grow a field without
// breaking a client that validates against this contract.

// Terse scalar-node builders (a JSON Schema is verbose written out longhand).
const str = (description: string): JsonSchema => ({ type: "string", description });
const int = (description: string): JsonSchema => ({ type: "integer", description });
const num = (description: string): JsonSchema => ({ type: "number", description });
const bool = (description: string): JsonSchema => ({ type: "boolean", description });
/** A scalar that is legitimately `null` when absent (a page cite the source never carried, an
 * exhausted cursor) — `type: [<t>, "null"]`, not a dropped key. */
const nullable = (type: string, description: string): JsonSchema => ({
  type: [type, "null"],
  description,
});
/** An opaque nested object (provenance blocks, citations) — described by name, not field-by-field. */
const obj = (description: string): JsonSchema => ({ type: "object", description });
const arr = (description: string, items: JsonSchema): JsonSchema => ({ type: "array", description, items });

/** Wrap a per-result `items` shape in the governed response envelope (#1581) shared by every tool. */
function governedEnvelope(items: JsonSchema, resultsDescription: string): JsonSchema {
  return {
    type: "object",
    description:
      "The uniform governed response envelope (#1581): the ordered result window plus the response's own size accounting.",
    properties: {
      results: arr(resultsDescription, items),
      token_estimate: int("Estimated token cost of the returned `results` array."),
      truncated: bool(
        "True when results were withheld to stay under budget — pass `next_cursor` to fetch the rest.",
      ),
      next_cursor: nullable(
        "string",
        "Opaque continuation cursor for the next page, or null when the result set is exhausted.",
      ),
    },
    required: ["results", "token_estimate", "truncated", "next_cursor"],
    additionalProperties: false,
  };
}

/**
 * The uniform structured-citation object (#1584) every result-bearing tool attaches — the
 * schema peer of `functions/api/_lib/mcpCitation.ts`.
 *
 * Only `verified` / `evidence` / `label` are required: every other field is present **only where
 * the source genuinely carries it**, and an absent one is OMITTED rather than nulled (a page-less
 * connector value has no `page`, not a guessed one — the root CLAUDE.md evidence discipline). That
 * is also what keeps the object cheap enough to ride on every compact discovery card.
 */
const CITATION: JsonSchema = {
  type: "object",
  description:
    "Structured provenance for this result — enough to cite it WITHOUT a follow-up fetch. Absent fields mean the source carries no such value; nothing here is inferred.",
  properties: {
    document_id: str(
      "The addressable source document (a `data/documents` rel) — pass to get_document, or to search_passages.document_ids. Absent when the item isn't grounded in a catalogued file.",
    ),
    source: str(
      "The citable artifact the claim was read from: a repo-relative data/ path (usually the reviewed extraction), a dataset label, or an instrument number.",
    ),
    source_kind: str("Provenance class — document | connector | reference | assumption | derived."),
    page: int("1-based FIRST page within the source. Absent where the source carries no page."),
    pages: arr(
      "Every 1-based page the claim was read from, when the read spanned more than one. A LIST, not a range — extraction reads are often non-contiguous.",
      int("A 1-based page number."),
    ),
    section: str("Sub-page heading within the source, where one is recorded."),
    source_url: str("Absolute URL at which the cited source can be inspected."),
    quote: str(
      "VERBATIM source text, truncated to a lead excerpt. Populated only by search_passages, whose text IS the document's own text layer; a search_corpus snippet is a window over the record's FLATTENED FIELDS and is deliberately never presented as a quote.",
    ),
    note: str(
      "Free-text provenance the source records instead of a path — a projected fact's ProvenancedValue citation. For most facts this is the ONLY provenance there is.",
    ),
    confidence: str("Evidence confidence band recorded on the source (high | medium | low)."),
    verified: bool("True when grounded in a record or a live gauge — `[verified]` in prose."),
    evidence: {
      type: "string",
      enum: ["verified", "inference"],
      description: "The evidence tag this citation renders as.",
    },
    label: str("One-line human-readable rendering — the string to paste into prose."),
  },
  required: ["verified", "evidence", "label"],
};

const SEARCH_CORPUS_HIT: JsonSchema = {
  type: "object",
  description:
    "A ranked evidence card. The field set depends on response_mode: ids_only = {id, score}; compact/snippets add the card fields (title/site/collection/snippet/tier/…); full replaces the card with the whole record (feed/text/url/source/page/…). `id` and `score` are present in every mode.",
  properties: {
    id: str("Item id — pass to get_document to fetch its projected fields + citation."),
    score: num("Hybrid (BM25 + vector RRF) relevance score."),
    // compact / snippets card
    title: str("Item title."),
    site: nullable("string", "Site slug, or null."),
    collection: str("Bundle feed the hit came from (records, timeline, entities, …)."),
    source_kind: nullable("string", "Provenance kind (document, connector, …)."),
    date: nullable("string", "Structured source date, when the feed carries one."),
    snippet: str("Query-focused excerpt (snippets mode) or short head preview (compact mode)."),
    estimated_tokens: int("Token cost of pulling this hit in full mode."),
    verified: bool("Whether the underlying claim is [verified]."),
    tier: {
      type: "string",
      enum: ["direct", "corroborating", "background"],
      description: "Evidence role for the query (#1591). Absent in ids_only mode.",
    },
    tier_reason: str("Why the hit earned its tier."),
    citation: CITATION,
    // full record
    feed: str("Bundle feed (full mode)."),
    text: str("The whole flattened record text (full mode; ~18–24k tokens)."),
    url: str("Deep link to the item's page (full mode)."),
    source: nullable("string", "Source path (full mode)."),
    page: nullable("integer", "Source page (full mode), or null."),
    confidence: nullable("string", "Evidence confidence (full mode)."),
  },
  required: ["id", "score"],
};

const SEARCH_PASSAGES_HIT: JsonSchema = {
  type: "object",
  description: "A page-cited passage hit — the verbatim excerpt plus its provenance and rank score.",
  properties: {
    id: str("Stable passage id (`<document_id>#p<page>`)."),
    document_id: str("Source document rel — the join key to get_document."),
    collection: str("First path segment of document_id (the collection axis)."),
    title: str("Source document catalog name."),
    page: int("1-indexed printed page number."),
    section: nullable("string", "Sub-page heading, or null."),
    text: str("The page's text-layer excerpt (verbatim; garbled OCR for scans)."),
    score: num("Hybrid (BM25 + vector RRF) relevance score."),
    citation: CITATION,
  },
  required: ["id", "document_id", "collection", "title", "page", "section", "text", "score", "citation"],
};

const TIMELINE_EVENT: JsonSchema = {
  type: "object",
  description: "A dated event (permit, filing, meeting, transaction).",
  properties: {
    date: str("ISO-8601 event date."),
    category: str("Event category."),
    title: str("Event title."),
    ref: str("Optional source reference id."),
    parties: arr("Parties involved.", str("Party name.")),
    detail: str("Prose detail (shed first under a per-result budget)."),
    source: str("Source path."),
    citation: CITATION,
  },
  required: ["date", "category", "title", "citation"],
};

const ENTITY_NODE: JsonSchema = {
  type: "object",
  description: "An entity-graph node — a party, company, person, or parcel and its roles.",
  properties: {
    key: str("Stable entity key."),
    display: str("Human display name."),
    kind: str("Entity kind (company, person, parcel, …)."),
    classification: nullable("string", "Optional classification."),
    variants: arr("Name variants.", str("Variant.")),
    roles: obj("Role → count map."),
    parcels: arr("Parcel ids.", str("Parcel id.")),
    addresses: arr("Addresses.", str("Address.")),
    sources: arr("Source paths.", str("Source.")),
    signals: arr("Signal tags.", str("Signal.")),
  },
  required: ["key", "display", "kind"],
};

const HYPOTHESIS: JsonSchema = {
  type: "object",
  description: "A boom-origin hypothesis joined to its signal assessments.",
  properties: {
    id: str("Hypothesis id."),
    number: str("Display number."),
    name: str("Short name."),
    claim: str("The claim under test."),
    thesis: str("The thesis statement."),
    status: str("Assessment status."),
    signals: arr("Signal ids.", str("Signal id.")),
    groups: arr("Signal groups.", str("Group.")),
    assessments: arr(
      "The signal assessments scored against this hypothesis (may be budget-shrunk — compare length to assessments_total).",
      obj("An assessment (site / hypothesis / signal / tag, plus optional group / fields / citations)."),
    ),
    assessments_total: int("True assessment count before any per-result shrink."),
  },
  required: [
    "id",
    "name",
    "claim",
    "thesis",
    "status",
    "signals",
    "groups",
    "assessments",
    "assessments_total",
  ],
};

const DOCUMENT_COLLECTION: JsonSchema = {
  type: "object",
  description: "A source-document collection and its file entries (metadata only).",
  properties: {
    slug: str("Collection slug."),
    title: str("Collection title."),
    description: str("Collection description."),
    entry_count: int("True entry count (the entries list may be budget-capped)."),
    entries: arr("File entries.", {
      type: "object",
      description: "One document file entry.",
      properties: {
        rel: str("Path relative to data/documents — the get_document id."),
        name: str("File name."),
        media_type: str("MIME type."),
        published: bool("Whether the bytes are publicly served."),
        available: bool("Whether the file is present."),
      },
      required: ["rel", "name", "media_type", "published", "available"],
    }),
  },
  required: ["slug", "title", "entry_count", "entries"],
};

const DOCUMENT_VIEW: JsonSchema = {
  type: "object",
  description:
    "One document's metadata joined to its extraction record, with field/section projection. Section-projected: metadata/fields/citation/warnings appear only when requested (default all).",
  properties: {
    document_id: str("Canonical id echoed back (the joined record rel, else the doc rel)."),
    collection: str("First path segment of the id."),
    metadata: obj(
      "Record + source-file metadata (record_rel / title / group / confidence / source_doc_rel / document_file).",
    ),
    fields: obj(
      "The record's extracted fields (projected/shrunk — compare Object.keys length to field_count).",
    ),
    field_count: int("True field count before projection/shrink."),
    citation: CITATION,
    warnings: arr("Extraction warnings.", str("Warning.")),
    source_text: str("Flattened extraction text (only when include_source_text)."),
  },
  required: ["document_id", "collection"],
};

const FACT_VIEW: JsonSchema = {
  type: "object",
  description: "A normalized (subject, predicate, value, unit, status) fact tuple.",
  properties: {
    subject: str("`<kind>:<id>` subject key."),
    subject_label: str("Human subject label (shed first under budget)."),
    subject_kind: str("Subject kind (facility, county, …)."),
    predicate: str("snake_case field name."),
    value: nullable("number", "Numeric value, or null when unquantified."),
    unit: nullable("string", "Unit, when the fact carries one."),
    status: {
      type: "string",
      enum: ["verified", "inference", "reference", "open"],
      description: "Evidence status.",
    },
    low: nullable("number", "Uncertainty-band low, when present."),
    high: nullable("number", "Uncertainty-band high, when present."),
    approximate: bool("True when the value is approximate."),
    feed: str("Source feed."),
    evidence: obj("Raw provenance block (only when include_evidence)."),
    citation: CITATION,
  },
  required: ["subject", "subject_kind", "predicate", "value", "status", "feed"],
};

const FACT_AGGREGATE: JsonSchema = {
  type: "object",
  description:
    "One aggregate row. In normal use a grouped total (metric / op / group / value / unit / derivation / confidence / status / caveat / evidence_ids). With no `metric` it is instead a registered-metric descriptor (key / label / op / inputs / unit / caveat) — discovery mode. An unknown `metric` yields a single {error, available_metrics, grammar} row. No field is universal across the three shapes.",
  properties: {
    // grouped total
    metric: str("The metric key."),
    op: {
      type: "string",
      enum: ["sum", "count", "mean", "product"],
      description: "Aggregation op.",
    },
    group_by: str("Grouping dimension."),
    group: str("Group key."),
    group_label: str("Group label."),
    value: nullable("number", "The total, or null."),
    unit: nullable("string", "Output unit, or null."),
    derivation: str("Human-readable arithmetic, e.g. `114 × 2.75 MW`."),
    n: int("How many source facts fed the total."),
    confidence: str("Weakest input confidence."),
    status: str("Weakest input evidence status."),
    caveat: nullable("string", "Honesty note, or null."),
    evidence_ids: arr("`<subject>/<predicate>` handles that fed the total.", str("Handle.")),
    // discovery (MetricDescriptor)
    key: str("Registered metric key (discovery mode)."),
    label: str("Registered metric label (discovery mode)."),
    inputs: arr("Predicate inputs (discovery mode).", str("Predicate.")),
    // unknown-metric error
    error: str("Error message (unknown metric)."),
    available_metrics: arr("Known metric keys (unknown-metric error).", str("Metric key.")),
    grammar: str("The generic metric grammar (unknown-metric error)."),
  },
  required: [],
};

export const MCP_TOOLS: readonly ToolSchema[] = [
  {
    name: "search_corpus",
    description:
      "Hybrid search across the whole corpus — the discovery entrypoint. Ranking fuses semantic (vector) similarity with BM25 keyword scoring via reciprocal-rank-fusion, degrading to keyword-only when query embeddings are unavailable. Use to FIND relevant items across every feed (records, documents, timeline, entities, …); narrow with a `filters` bag over indexed fields (site, feed, source_kind, verified, date_from/date_to, confidence, county, agency, permit_number, document_type, entity, project/campus — all AND-combined) so unrelated feeds don't crowd the results. Prefer a facet over a keyword when you have one: `filters.permit_number:\"2PH00006\"` finds every action filed under that permit including its modifications, where the same string in `query` merely ranks. This is NOT the way to pull one known document — use get_document for that. Returns ranked evidence cards (id, title, site, collection, date, source_kind, score, snippet, estimated_tokens, verified, tier, tier_reason, citation) — NO full record text by default; pass a hit's id to get_document to fetch its projected fields. Every card carries a structured `citation` (document_id, source, page/pages, source_url, evidence, and a paste-ready `label`), so you can CITE A HIT WITHOUT FETCHING IT — a follow-up get_document is for the record's fields, not for its provenance. Absent citation fields mean the source carries no such value; none of it is inferred, and a card's snippet is a window over the record's flattened fields, so it is never offered as a verbatim quote (use search_passages for that). Each hit is tiered by evidence role so you don't treat every match as equal: `tier` is `direct` (top-relevance-band primary evidence — records/documents/timeline/meetings that answer the query), `corroborating` (relevant supporting material — a secondary entity/person/place view, or primary evidence below the top band), or `background` (definitional/derived context — glossary concepts, or a weak-relevance match); `tier_reason` says why. The tier is an evidence-grounded heuristic (evidence class + score band), never score alone — a glossary hit is never `direct`. A filing's versions (e.g. a permit's final + draft + fact sheet) collapse to the canonical member by default — pass deduplicate:\"none\" to see every version, or version_policy to tune which superseded versions survive. Size knobs: response_mode (ids_only|compact|snippets|full — ids_only omits the tier; full reproduces the whole record, ~18–24k tokens/hit, opt-in), limit/max_results, snippet_tokens, max_tokens, cursor.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        site: {
          type: "string",
          description:
            "Site slug (e.g. lima, fort-wayne). Leave blank to search all sites. Legacy shorthand for `filters.site`.",
        },
        collection: {
          type: "string",
          description:
            "Legacy shorthand for `filters.feed` — restrict to one BUNDLE FEED (records, documents, timeline, entities, meetings, people, places, concepts). Prefer `filters.feed`; NOTE this is a bundle feed, NOT a document-collection slug (oepa/recorder/aedg → get_documents).",
        },
        ...SEARCH_FILTERS_PROP,
        limit: { type: "integer", description: "Max results (default 10)", default: 10 },
        response_mode: {
          type: "string",
          enum: ["ids_only", "compact", "snippets", "full"],
          description:
            "Result shape (default compact). compact = evidence cards, no full text; ids_only = id + score only; snippets = compact plus a query-focused excerpt; full = the whole record text (opt-in, expensive — ~18–24k tokens per record).",
          default: "compact",
        },
        snippet_tokens: {
          type: "integer",
          description:
            "Approx. size (in tokens) of the query-focused excerpt in snippets mode (default 250).",
          default: 250,
        },
        ...DEDUP_PROPS,
        ...GOVERNANCE_PROPS,
      },
      required: ["query"],
    },
    outputSchema: governedEnvelope(
      SEARCH_CORPUS_HIT,
      "Ranked evidence cards (shape governed by response_mode), most-relevant first.",
    ),
    example:
      '{"query": "effluent limits", "filters": {"site": "lima", "permit_number": "2PH00006", "document_type": "permits-npdes"}, "limit": 5}',
  },
  {
    name: "search_passages",
    description:
      "Page-level excerpt search over PUBLISHED source PDFs — returns the exact supporting page(s) with a citation, not a whole record. Use when you need the verbatim passage behind a claim (a permit condition, a board vote, a dollar figure) plus a page cite — especially for PDFs, where one relevant page shouldn't require pulling the full extracted document. This is the deeper peer of search_corpus: search_corpus finds WHICH item is relevant; search_passages finds WHICH PAGE says it. Ranking fuses semantic (vector) similarity with BM25, degrading to keyword-only when query embeddings are unavailable. Scoped to the public-publish allowlist, so it covers only documents whose bytes are publicly served — not the whole corpus. Narrow to specific documents with document_ids (the document_id / rel from search_corpus or get_documents). Returns page excerpts (id, document_id, page, section, title, text, score, citation). This is the one tool whose `citation.quote` is populated — the excerpt IS the document's own text layer, so it is genuinely verbatim (a bounded lead excerpt; the hit's `text` carries the full page). The text is the PDF text layer verbatim — for scanned pages that is garbled OCR, so treat it as a locator for the cited page, not a transcription; open the page itself with get_document. By default pages from a byte-identical duplicate document are collapsed to the canonical copy (deduplicate:\"none\" to disable); draft/final page variants are always kept distinct. Size knobs: max_results, max_tokens, max_tokens_per_result (trims the excerpt), cursor, intent.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        document_ids: {
          type: "array",
          items: { type: "string" },
          description:
            'Restrict to these documents by document_id / rel (e.g. "oepa/2PE00000.pdf"), as returned by search_corpus or get_documents. Leave blank to search all published documents.',
        },
        ...PASSAGE_DEDUP_PROPS,
        ...GOVERNANCE_PROPS,
      },
      required: ["query"],
    },
    outputSchema: governedEnvelope(SEARCH_PASSAGES_HIT, "Page-cited passage excerpts, most-relevant first."),
    example: '{"query": "effluent limit total phosphorus", "document_ids": ["oepa/2PE00000.pdf"]}',
  },
  {
    name: "get_timeline",
    description:
      "Dated events for a site (permits, filings, meetings, transactions), oldest-first. Use to build a chronology or find what happened in a window; filter by since/until/category. Returns event records directly (date, category, title, parties, detail, citation) — every row carries the same structured `citation` object the search tools return, so an event is citable as it stands. A terminal read, not a discovery index; to open the document behind an event, take its parties/title into search_corpus or get_document. Size knobs: max_results, max_tokens, max_tokens_per_result (sheds detail/parties first), cursor, intent.",
    inputSchema: {
      type: "object",
      properties: {
        since: { type: "string", description: "ISO-8601 date lower bound (inclusive)" },
        until: { type: "string", description: "ISO-8601 date upper bound (inclusive)" },
        category: { type: "string", description: "Event category filter" },
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(TIMELINE_EVENT, "Dated events, oldest-first."),
    example: '{"since": "2015-01-01", "until": "2020-12-31", "category": "permit"}',
  },
  {
    name: "get_entities",
    description:
      "Entity graph for a site — parties, companies, people, parcels and their roles/relationships. Use to resolve who is involved or enumerate the parcels/companies on the record; filter by type. Returns entity nodes directly (key, display, kind, roles, parcels, addresses, sources, signals). Not a document fetch — take an entity's name into search_corpus to find the documents behind it. Size knobs: max_results, max_tokens, max_tokens_per_result (sheds variants/addresses/signals/parcels/roles first), cursor, intent.",
    inputSchema: {
      type: "object",
      properties: {
        type: {
          type: "string",
          description: "Entity type filter (e.g. company, person, parcel)",
        },
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(ENTITY_NODE, "Entity-graph nodes."),
    example: '{"type": "company", "site": "fort-wayne"}',
  },
  {
    name: "get_hypotheses",
    description:
      "Per-site boom-origin hypotheses joined to their signal assessments — the investigation's open theses and how the evidence scores against each. Use to see the analytic frame or what is being tested; filter by site. Returns each hypothesis (claim, thesis, status, signals) with its assessments (tag, group, citations); assessments_total flags a budget-shrunk list. Not a document fetch — follow a signal's citation via search_corpus/get_document. Size knobs: max_results, max_tokens, max_tokens_per_result, cursor, intent.",
    inputSchema: {
      type: "object",
      properties: {
        site: { type: "string", description: "Site slug (default: all sites)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(HYPOTHESIS, "Hypotheses joined to their signal assessments."),
    example: '{"site": "lima"}',
  },
  {
    name: "get_documents",
    description:
      "Lists source-document COLLECTIONS and their file entries (metadata only — rel, name, media_type, published, available), by collection. Use to browse what documents exist or find a document's id; filter by collection. Returns collection cards with entry_count + entries, NO document bodies or extracted fields. Then fetch: pass an entry's rel to get_document for its extraction fields + citation. Contrast get_document (one document, projected) and search_corpus (hybrid search across every feed). Size knobs: max_results, max_tokens, max_tokens_per_result (caps the entries list), cursor, intent.",
    inputSchema: {
      type: "object",
      properties: {
        collection: {
          type: "string",
          description: "Collection filter (e.g. oepa, recorder, aedg, commissioners)",
        },
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(
      DOCUMENT_COLLECTION,
      "Document collections with their file entries (metadata only).",
    ),
    example: '{"collection": "oepa", "site": "lima"}',
  },
  {
    name: "get_document",
    description:
      "Fetch ONE document you already have an id for, with field/section projection — the targeted peer of get_documents (which only lists collections). Use it to pull a specific document's evidence AFTER discovery; for discovery itself use search_corpus or get_documents, and note this does no corpus search. Addressed by its `collection/rel` file path (e.g. recorder/bistrozzi-deeds/202508130008300.pdf) OR the joined extraction-record id (e.g. recorder/202508130008300.deed.yaml); ids returned by search_corpus work directly. Returns the document's metadata joined to its extraction record — structured `fields` and a structured `citation` (the same object the search tools return: document_id, source, page/pages, source_url, evidence, and a paste-ready `label`) — bounded by max_tokens, projected by fields/sections. IMPORTANT: the bundle carries document metadata + record `fields`, NOT the raw source-document body text. `fields`/`sections` projection operates over those extracted fields; there is no per-page body-text projection here — use search_passages to retrieve a published PDF's page text with a page cite. `include_source_text` returns the record's flattened extraction text, not scanned page text.",
    inputSchema: {
      type: "object",
      properties: {
        document_id: {
          type: "string",
          description:
            "Document address: a `collection/rel` file path or the joined record id (rel). An id from a search_corpus result (with or without a `records:` prefix) resolves directly.",
        },
        fields: {
          type: "array",
          items: { type: "string" },
          description:
            "Project only these keys from the record's `fields` (default: all). Unknown keys are ignored; `field_count` always reports the record's true total so a subset is detectable.",
        },
        sections: {
          type: "array",
          items: { type: "string", enum: ["metadata", "fields", "citation", "warnings"] },
          description:
            "Project only these top-level response sections (default: all). `metadata` and `citation` are also the sections never shed to satisfy max_tokens.",
        },
        include_source_text: {
          type: "boolean",
          description:
            "Also return `source_text`: the record's flattened, searchable extraction text (a serialization of its `fields`), NOT raw source-document body/page text. Default false.",
        },
        site: { type: "string", description: "Site slug (default: active site)" },
        intent: GOVERNANCE_PROPS.intent,
        max_tokens: GOVERNANCE_PROPS.max_tokens,
      },
      required: ["document_id"],
    },
    outputSchema: governedEnvelope(
      DOCUMENT_VIEW,
      "The single addressed document (a one-element list, or empty when the id resolves to nothing).",
    ),
    example:
      '{"document_id": "recorder/202508130008300.deed.yaml", "fields": ["grantors", "grantees", "parcel_ids"]}',
  },
  {
    name: "get_facts",
    description:
      'Retrieve normalized (subject, predicate, value, unit, status) FACTS — the numbers a site\'s provenanced feeds already carry (economics, energy, water/cooling, air, facility power), flattened into one queryable table so a fact question is a tiny retrieval + arithmetic instead of a whole-record pull. Use it to look up or compute over specific quantities (e.g. genset_count × genset_rating → backup MW; county employment; demand_share_pct); filter by subject, predicate, and/or `fact_category` (economics | energy | facility-power | water | air | platform — the grouping over the source feeds; `feed` takes one exact source instead). `subject` matches flexibly (case-insensitive, over the `<kind>:<id>` key + human label + kind — e.g. "Allen County", "facility", "air-scenario"); `predicate` takes one name or a list of the exact snake_case field names. Returns compact tuples by default (subject, predicate, value, unit, status, low/high band); status is the evidence tag (verified|inference|reference|open). NOT a document fetch and NOT search — for the record behind a fact, take its subject into search_corpus/get_document. Pass include_evidence=true to attach each fact\'s provenance — both the raw `evidence` block (source, source_kind, page, citation, verified) and the same structured `citation` object the other tools return; note page is null/absent where the source carries none — never invented, and for most facts the ONLY provenance is a free-text string, which rides in `citation.note` and becomes its label. Size knobs: max_results, max_tokens, max_tokens_per_result (sheds evidence then the band), cursor, intent.',
    inputSchema: {
      type: "object",
      properties: {
        subject: {
          type: "string",
          description:
            'Flexible subject match (case-insensitive substring over the `<kind>:<id>` key, the human label, and the kind). E.g. "facility", "Allen County", "county:39003", "air-scenario". Omit to return every subject.',
        },
        predicate: {
          type: "array",
          items: { type: "string" },
          description:
            "Filter to these exact predicate names (snake_case field names, e.g. genset_count, genset_rating, total_employment, demand_share_pct, consumptive_loss). A single string is also accepted. Omit for all predicates of the matched subjects.",
        },
        status: {
          type: "string",
          enum: ["verified", "inference", "reference", "open"],
          description:
            "Filter by evidence status: verified (document/live), inference (assumption/derived), reference (published spec), open (asserted but unquantified).",
        },
        fact_category: FACT_CATEGORY_PROP,
        feed: FACT_FEED_PROP,
        include_evidence: {
          type: "boolean",
          description:
            "Attach each fact's evidence block (source, source_kind, page, citation, confidence, asof, verified) plus the uniform structured `citation` object. Default false — compact tuples only. `page` is null where the source value carries none.",
        },
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(FACT_VIEW, "Normalized fact tuples."),
    example: '{"subject": "facility", "predicate": ["genset_count", "genset_rating"]}',
  },
  {
    name: "aggregate_facts",
    description:
      'Compute a deterministic GROUPED TOTAL over the facts feed server-side — sum / count / mean / product — so you never pull every row just to total something. Returns one row per group with the value, unit, a human-readable `derivation` (e.g. "114 × 2.75 MW"), a `confidence`, a `caveat`, and the `evidence_ids` (the <subject>/<predicate> handles) that fed it. `metric` is either a registered recipe (backup_generation_capacity_mw = genset_count × genset_rating; facility_draw_mw = it_load × PUE) or the generic grammar sum:<predicate> | mean:<predicate> | count:<predicate> | product:<a>,<b> (e.g. "sum:annual_avg_employment"). Call it with NO metric to list the registered metrics (discovery). `group_by` partitions the total: project/subject (per facility/county/scenario — the default), kind (subject_kind), feed, or all/site (one whole-site total). A product is computed per subject then summed up to a coarser group. Optionally pre-filter inputs by `subject` (flexible match, like get_facts), `status`, and `fact_category`/`feed` — the same category gate get_facts uses, so a total and the tuples behind it are always taken over the same rows. Status/confidence take the weakest input; a product is never reported stronger than inference (a derivation is not a document). For the raw tuples behind a total, use get_facts with the same subject/predicate.',
    inputSchema: {
      type: "object",
      properties: {
        metric: {
          type: "string",
          description:
            'The aggregation: a registered recipe (backup_generation_capacity_mw, facility_draw_mw) or the generic sum:<predicate> | mean:<predicate> | count:<predicate> | product:<a>,<b> (bare "count" counts every matching fact). Omit to list the registered metrics.',
        },
        group_by: {
          type: "string",
          description:
            'How to partition the total: "project"/"subject" (per facility/county/scenario — default), "kind" (subject_kind), "feed", or "all"/"site" (one whole-site total).',
        },
        subject: {
          type: "string",
          description:
            'Restrict the inputs to matching subjects before aggregating (flexible, case-insensitive over the `<kind>:<id>` key + label + kind — e.g. "facility", "Allen County"). Omit to aggregate over every subject.',
        },
        status: {
          type: "string",
          enum: ["verified", "inference", "reference", "open"],
          description: "Restrict the inputs to this evidence status before aggregating.",
        },
        fact_category: FACT_CATEGORY_PROP,
        feed: FACT_FEED_PROP,
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    outputSchema: governedEnvelope(
      FACT_AGGREGATE,
      "Grouped totals — or the registered-metric list (no metric), or an unknown-metric error row.",
    ),
    example: '{"metric": "backup_generation_capacity_mw", "group_by": "project"}',
  },
];
