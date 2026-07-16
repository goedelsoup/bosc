// Shared MCP tool schema registry (#917).
// Imported by both the dispatch layer (functions/api/_lib/mcpDispatch.ts) and the
// /network/connect page so the tool reference table is generated from the real schemas,
// not duplicated by hand.

export interface ToolSchema {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<
      string,
      { type: string; description: string; default?: unknown; enum?: readonly string[] }
    >;
    required?: string[];
  };
  /** One representative query that illustrates the tool's use. */
  example?: string;
}

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
      },
    },
    example: '{"collection": "oepa", "site": "lima"}',
  },
];
