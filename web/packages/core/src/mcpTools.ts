// Shared MCP tool schema registry (#917).
// Imported by both the dispatch layer (functions/api/_lib/mcpDispatch.ts) and the
// /network/connect page so the tool reference table is generated from the real schemas,
// not duplicated by hand.

/** A JSON-Schema property node. `items` is set on `type: "array"` params (e.g. the
 * get_document `fields`/`sections` projections). */
export interface ToolProperty {
  type: string;
  description: string;
  default?: unknown;
  enum?: readonly string[];
  items?: { type: string; enum?: readonly string[] };
}

export interface ToolSchema {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, ToolProperty>;
    required?: string[];
  };
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

export const MCP_TOOLS: readonly ToolSchema[] = [
  {
    name: "search_corpus",
    description:
      "Hybrid search across the whole corpus — the discovery entrypoint. Ranking fuses semantic (vector) similarity with BM25 keyword scoring via reciprocal-rank-fusion, degrading to keyword-only when query embeddings are unavailable. Use to FIND relevant items across every feed (records, documents, timeline, entities, …); narrow with site/collection. This is NOT the way to pull one known document — use get_document for that. Returns ranked evidence cards (id, title, site, collection, date, source_kind, score, snippet, estimated_tokens, verified) — NO full record text by default; pass a hit's id to get_document to fetch its projected fields + citation. Size knobs: response_mode (ids_only|compact|snippets|full — full reproduces the whole record, ~18–24k tokens/hit, opt-in), limit/max_results, snippet_tokens, max_tokens, cursor.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        site: {
          type: "string",
          description: "Site slug (e.g. lima, fort-wayne). Leave blank to search all sites.",
        },
        collection: {
          type: "string",
          description:
            "Feed filter — restrict to one bundle feed: records, documents, timeline, entities, meetings, people, places, concepts.",
        },
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
        ...GOVERNANCE_PROPS,
      },
      required: ["query"],
    },
    example: '{"query": "NPDES permit violations", "site": "lima", "limit": 5}',
  },
  {
    name: "search_passages",
    description:
      "Page-level excerpt search over PUBLISHED source PDFs — returns the exact supporting page(s) with a citation, not a whole record. Use when you need the verbatim passage behind a claim (a permit condition, a board vote, a dollar figure) plus a page cite — especially for PDFs, where one relevant page shouldn't require pulling the full extracted document. This is the deeper peer of search_corpus: search_corpus finds WHICH item is relevant; search_passages finds WHICH PAGE says it. Ranking fuses semantic (vector) similarity with BM25, degrading to keyword-only when query embeddings are unavailable. Scoped to the public-publish allowlist, so it covers only documents whose bytes are publicly served — not the whole corpus. Narrow to specific documents with document_ids (the document_id / rel from search_corpus or get_documents). Returns page excerpts (id, document_id, page, section, title, text, score). The text is the PDF text layer verbatim — for scanned pages that is garbled OCR, so treat it as a locator for the cited page, not a transcription; open the page itself with get_document. Size knobs: max_results, max_tokens, max_tokens_per_result (trims the excerpt), cursor, intent.",
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
        ...GOVERNANCE_PROPS,
      },
      required: ["query"],
    },
    example: '{"query": "effluent limit total phosphorus", "document_ids": ["oepa/2PE00000.pdf"]}',
  },
  {
    name: "get_timeline",
    description:
      "Dated events for a site (permits, filings, meetings, transactions), oldest-first. Use to build a chronology or find what happened in a window; filter by since/until/category. Returns event records directly (date, category, title, parties, detail, citation) — a terminal read, not a discovery index; to open the document behind an event, take its parties/title into search_corpus or get_document. Size knobs: max_results, max_tokens, max_tokens_per_result (sheds detail/parties first), cursor, intent.",
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
    example: '{"collection": "oepa", "site": "lima"}',
  },
  {
    name: "get_document",
    description:
      "Fetch ONE document you already have an id for, with field/section projection — the targeted peer of get_documents (which only lists collections). Use it to pull a specific document's evidence AFTER discovery; for discovery itself use search_corpus or get_documents, and note this does no corpus search. Addressed by its `collection/rel` file path (e.g. recorder/bistrozzi-deeds/202508130008300.pdf) OR the joined extraction-record id (e.g. recorder/202508130008300.deed.yaml); ids returned by search_corpus work directly. Returns the document's metadata joined to its extraction record — structured `fields` and a `Citation` — bounded by max_tokens, projected by fields/sections. IMPORTANT: the bundle carries document metadata + record `fields`, NOT the raw source-document body text. `fields`/`sections` projection operates over those extracted fields; there is no per-page body-text projection here — use search_passages to retrieve a published PDF's page text with a page cite. `include_source_text` returns the record's flattened extraction text, not scanned page text.",
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
    example:
      '{"document_id": "recorder/202508130008300.deed.yaml", "fields": ["grantors", "grantees", "parcel_ids"]}',
  },
  {
    name: "get_facts",
    description:
      'Retrieve normalized (subject, predicate, value, unit, status) FACTS — the numbers a site\'s provenanced feeds already carry (economics, energy, water/cooling, air, facility power), flattened into one queryable table so a fact question is a tiny retrieval + arithmetic instead of a whole-record pull. Use it to look up or compute over specific quantities (e.g. genset_count × genset_rating → backup MW; county employment; demand_share_pct); filter by subject and/or predicate. `subject` matches flexibly (case-insensitive, over the `<kind>:<id>` key + human label + kind — e.g. "Allen County", "facility", "air-scenario"); `predicate` takes one name or a list of the exact snake_case field names. Returns compact tuples by default (subject, predicate, value, unit, status, low/high band); status is the evidence tag (verified|inference|reference|open). NOT a document fetch and NOT search — for the record behind a fact, take its subject into search_corpus/get_document. Pass include_evidence=true to attach each fact\'s provenance (source, source_kind, page, citation, verified); note page is null where the source carries none — never invented. Size knobs: max_results, max_tokens, max_tokens_per_result (sheds evidence then the band), cursor, intent.',
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
        include_evidence: {
          type: "boolean",
          description:
            "Attach each fact's evidence block (source, source_kind, page, citation, confidence, asof, verified). Default false — compact tuples only. `page` is null where the source value carries none.",
        },
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    example: '{"subject": "facility", "predicate": ["genset_count", "genset_rating"]}',
  },
  {
    name: "aggregate_facts",
    description:
      'Compute a deterministic GROUPED TOTAL over the facts feed server-side — sum / count / mean / product — so you never pull every row just to total something. Returns one row per group with the value, unit, a human-readable `derivation` (e.g. "114 × 2.75 MW"), a `confidence`, a `caveat`, and the `evidence_ids` (the <subject>/<predicate> handles) that fed it. `metric` is either a registered recipe (backup_generation_capacity_mw = genset_count × genset_rating; facility_draw_mw = it_load × PUE) or the generic grammar sum:<predicate> | mean:<predicate> | count:<predicate> | product:<a>,<b> (e.g. "sum:annual_avg_employment"). Call it with NO metric to list the registered metrics (discovery). `group_by` partitions the total: project/subject (per facility/county/scenario — the default), kind (subject_kind), feed, or all/site (one whole-site total). A product is computed per subject then summed up to a coarser group. Optionally pre-filter inputs by `subject` (flexible match, like get_facts) and `status`. Status/confidence take the weakest input; a product is never reported stronger than inference (a derivation is not a document). For the raw tuples behind a total, use get_facts with the same subject/predicate.',
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
        site: { type: "string", description: "Site slug (default: active site)" },
        ...GOVERNANCE_PROPS,
      },
    },
    example: '{"metric": "backup_generation_capacity_mw", "group_by": "project"}',
  },
];
