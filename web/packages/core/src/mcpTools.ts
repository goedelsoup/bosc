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
      "Semantic + keyword search over the documentary corpus. Returns compact evidence cards by default (id, title, site, collection, date, source_kind, score, snippet, estimated_tokens, verified) — no full record text. Use response_mode=full to pull a hit's whole text.",
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
          description: "Collection filter (e.g. oepa, recorder, aedg)",
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
    name: "get_timeline",
    description: "Dated events filterable by date range and category",
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
    description: "Entity graph: parties, roles, parcels, and relationships",
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
    description: "Boom-origin hypothesis signals per site",
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
    description: "Ingested source documents by collection",
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
      "Fetch ONE document by id, with field/section projection — the targeted peer of get_documents (which only lists collections). Addressed by its `collection/rel` file path (e.g. recorder/bistrozzi-deeds/202508130008300.pdf) OR the joined extraction-record id (e.g. recorder/202508130008300.deed.yaml); ids returned by search_corpus work directly. Returns the document's metadata joined to its extraction record — structured `fields` and a `Citation` — bounded by max_tokens. IMPORTANT: the bundle carries document metadata + record `fields`, NOT the raw source-document body text. `fields`/`sections` projection operates over those extracted fields; there is no per-page body-text projection here (that is separate search_passages work). `include_source_text` returns the record's flattened extraction text, not scanned page text.",
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
];
