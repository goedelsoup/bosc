// Output-schema + structuredContent contract tests (#1577).
//
// Two guarantees, asserted at the dispatch boundary (not the handlers directly):
//   1. Every tool in the shared registry declares an `outputSchema` that is the governed
//      response envelope `{ results, token_estimate, truncated, next_cursor }`.
//   2. A dispatched `tools/call` returns `structuredContent` that (a) equals the serialized
//      `content` text block byte-for-byte and (b) validates against that tool's `outputSchema`.
//
// Feeds are stubbed over globalThis.fetch (the same seam the per-handler tests use), and the
// module-scope loader caches are reset each test so fixtures don't bleed across cases.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type JsonSchema, MCP_TOOLS } from "@watermark/core/mcpTools";
import { PROTOCOL_VERSION, dispatch } from "@watermark/functions/api/_lib/mcpDispatch";
import { _resetAskEmbeddingsCache } from "@watermark/functions/api/_lib/askEmbeddingsLoad";
import { _resetAskIndexCache } from "@watermark/functions/api/_lib/askIndexLoad";
import { _resetDocVersionsCache } from "@watermark/functions/api/_lib/docVersionsLoad";
import { _resetPassagesCache } from "@watermark/functions/api/_lib/passagesLoad";
import type { AskUnit } from "@watermark/functions/api/_lib/retrieval";
import { type FetchRoute, jsonResponse, routingFetch } from "./_routeHarness";

const REQ = "https://directory.example/api/mcp";

// --- a minimal JSON-Schema validator (no ajv/zod in the tree) ----------------------
// Supports exactly the constructs the outputSchemas use: `type` (a name or [names], with
// "integer"/"null"), `enum`, `properties`, `required`, `items`, and `additionalProperties:false`.

function matchesType(t: string, v: unknown): boolean {
  switch (t) {
    case "object":
      return v !== null && typeof v === "object" && !Array.isArray(v);
    case "array":
      return Array.isArray(v);
    case "string":
      return typeof v === "string";
    case "integer":
      return typeof v === "number" && Number.isInteger(v);
    case "number":
      return typeof v === "number";
    case "boolean":
      return typeof v === "boolean";
    case "null":
      return v === null;
    default:
      return true; // unknown type name — don't fail on it
  }
}

function jsTypeOf(v: unknown): string {
  return v === null ? "null" : Array.isArray(v) ? "array" : typeof v;
}

/** Return every schema violation in `value` as a `$.path: message` string ([] ⇒ valid). */
function validate(schema: JsonSchema, value: unknown, path = "$"): string[] {
  const errs: string[] = [];
  if (schema.type != null) {
    const types = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!types.some((t) => matchesType(t, value))) {
      return [`${path}: expected ${types.join("|")}, got ${jsTypeOf(value)}`];
    }
  }
  if (schema.enum && !schema.enum.includes(value)) {
    errs.push(`${path}: ${JSON.stringify(value)} not in enum [${schema.enum.join(", ")}]`);
  }
  const isObject = value !== null && typeof value === "object" && !Array.isArray(value);
  if (isObject) {
    const rec = value as Record<string, unknown>;
    for (const r of schema.required ?? []) {
      if (!(r in rec)) errs.push(`${path}: missing required '${r}'`);
    }
    if (schema.properties) {
      for (const [k, sub] of Object.entries(schema.properties)) {
        if (k in rec) errs.push(...validate(sub, rec[k], `${path}.${k}`));
      }
      if (schema.additionalProperties === false) {
        for (const k of Object.keys(rec)) {
          if (!(k in schema.properties)) errs.push(`${path}.${k}: unexpected property`);
        }
      }
    }
  }
  if (Array.isArray(value) && schema.items) {
    const items = schema.items;
    value.forEach((v, i) => {
      errs.push(...validate(items, v, `${path}[${i}]`));
    });
  }
  return errs;
}

// --- fixtures (representative rows so item schemas are exercised, not just empty envelopes) ---

const UNITS: AskUnit[] = [
  {
    id: "records:oepa/permit.npdes.yaml",
    feed: "records",
    title: "NPDES permit — effluent limits",
    url: "/network/lima/site/records/permit/",
    text: "the NPDES permit sets effluent limits for total phosphorus discharge from the facility",
    source: "data/documents/oepa/permit.pdf",
    page: 3,
    source_kind: "document",
    confidence: "high",
    verified: true,
    site: "lima",
    date: "2020-01-01",
    doc_rel: "oepa/permit.pdf",
  },
  {
    id: "timeline:permit-issued",
    feed: "timeline",
    title: "Permit issued",
    url: "/network/lima/timeline",
    text: "the permit was issued to the facility for wastewater discharge",
    source_kind: "document",
    verified: true,
    site: "lima",
    date: "2020-01-15",
  },
];

const PASSAGES = [
  {
    id: "oepa/permit.pdf#p3",
    document_id: "oepa/permit.pdf",
    collection: "oepa",
    title: "NPDES permit",
    page: 3,
    section: "Part I — Effluent Limits",
    text: "Total phosphorus shall not exceed 1.0 mg/L as a monthly average.",
  },
];

const TIMELINE = [
  { date: "2020-05-01", category: "permit", title: "Permit modification", detail: "modified limits" },
  { date: "2018-01-01", category: "permit", title: "Permit issued", parties: ["Ohio EPA", "City"] },
];

const ENTITIES = [
  { key: "acme", display: "Acme LLC", kind: "company", variants: ["Acme", "ACME"], roles: { grantee: 2 } },
  { key: "jane", display: "Jane Roe", kind: "person" },
];

const HYPOTHESES = {
  hypotheses: [
    {
      id: "h1",
      number: "1",
      name: "Boom",
      claim: "c",
      thesis: "t",
      status: "open",
      signals: ["s1"],
      groups: ["g"],
    },
  ],
  assessments: [
    { site: "lima", hypothesis: "h1", signal: "s1", tag: "verified", group: "g", fields: { x: 1 } },
  ],
};

const DOCUMENTS = [
  {
    slug: "oepa",
    title: "Ohio EPA",
    description: "permits",
    entries: [
      {
        rel: "oepa/permit.pdf",
        name: "permit.pdf",
        media_type: "application/pdf",
        render_class: "pdf",
        size_bytes: 2048,
        published: true,
        available: true,
        download_url: null,
      },
    ],
  },
  {
    slug: "recorder",
    title: "Recorder",
    description: "deeds",
    entries: [
      {
        rel: "recorder/scans/deed-1.pdf",
        name: "deed-1.pdf",
        media_type: "application/pdf",
        render_class: "pdf",
        size_bytes: 12345,
        published: true,
        available: true,
        download_url: null,
      },
    ],
  },
];

const RECORDS = [
  {
    rel: "recorder/deed-1.deed.yaml",
    group: "deeds",
    title: "Warranty Deed",
    confidence: "high",
    warnings: ["consideration not stated"],
    fields: { grantor: "Alice", grantee: "Bob LLC", parcel_ids: ["1", "2"] },
    approximate_paths: [],
    citation: {
      source: "recorder/deed-1.deed.yaml",
      source_kind: "document",
      page: null,
      confidence: "high",
      verified: true,
    },
    source_doc_rel: "recorder/scans/deed-1.pdf",
    source_doc_render_class: "pdf",
    source_doc_published: true,
  },
];

const ev = (source_kind: string, extra: Record<string, unknown> = {}) => ({
  source: null,
  source_kind,
  page: null,
  citation: "cite",
  confidence: "high",
  asof: null,
  verified: source_kind === "document" || source_kind === "connector",
  ...extra,
});

const FACTS = [
  {
    subject: "facility:lima",
    subject_label: "Lima data center",
    subject_kind: "facility",
    predicate: "genset_count",
    value: 114,
    unit: "count",
    status: "verified",
    low: null,
    high: null,
    evidence: ev("document"),
    feed: "facility-power",
  },
  {
    subject: "facility:lima",
    subject_label: "Lima data center",
    subject_kind: "facility",
    predicate: "genset_rating",
    value: 2.75,
    unit: "MW",
    status: "verified",
    low: null,
    high: null,
    evidence: ev("document"),
    feed: "facility-power",
  },
];

function feedRoute(name: string, data: unknown): FetchRoute {
  return { test: (url) => url.pathname === `/feeds/${name}.json`, respond: () => jsonResponse(200, data) };
}

const ROUTES: FetchRoute[] = [
  { test: (url) => url.pathname === "/ask-index.json", respond: () => jsonResponse(200, UNITS) },
  feedRoute("passages", PASSAGES),
  feedRoute("timeline", TIMELINE),
  feedRoute("entities", ENTITIES),
  feedRoute("hypotheses", HYPOTHESES),
  feedRoute("documents", DOCUMENTS),
  feedRoute("records", RECORDS),
  feedRoute("facts", FACTS),
];

function resetCaches(): void {
  _resetAskIndexCache();
  _resetAskEmbeddingsCache();
  _resetPassagesCache();
  _resetDocVersionsCache();
}

beforeEach(() => {
  resetCaches();
  vi.stubGlobal("fetch", routingFetch(ROUTES));
});

afterEach(() => {
  vi.unstubAllGlobals();
  resetCaches();
});

// --- helpers -----------------------------------------------------------------------

interface ToolCallResult {
  content: Array<{ type: string; text: string }>;
  isError: boolean;
  structuredContent?: unknown;
}

async function callTool(name: string, args: Record<string, unknown>): Promise<ToolCallResult> {
  const res = await dispatch(
    { jsonrpc: "2.0", id: 1, method: "tools/call", params: { name, arguments: args } },
    REQ,
    {},
  );
  expect(res.error).toBeUndefined();
  return res.result as ToolCallResult;
}

function schemaOf(name: string): JsonSchema {
  const tool = MCP_TOOLS.find((t) => t.name === name);
  if (!tool) throw new Error(`no such tool: ${name}`);
  return tool.outputSchema;
}

// --- registry contract -------------------------------------------------------------

describe("MCP output schemas (#1577)", () => {
  it("every tool declares a governed-envelope outputSchema", () => {
    expect(MCP_TOOLS.length).toBeGreaterThan(0);
    for (const tool of MCP_TOOLS) {
      const s = tool.outputSchema;
      expect(s, tool.name).toBeDefined();
      expect(s.type, tool.name).toBe("object");
      const props = s.properties ?? {};
      expect(Object.keys(props).sort(), tool.name).toEqual([
        "next_cursor",
        "results",
        "token_estimate",
        "truncated",
      ]);
      expect(s.required, tool.name).toEqual(["results", "token_estimate", "truncated", "next_cursor"]);
      // The results item shape is itself an object schema — the contract clients destructure.
      expect(props.results?.type, tool.name).toBe("array");
      expect(props.results?.items?.type, tool.name).toBe("object");
    }
  });

  it("tools/list returns every tool carrying an outputSchema", async () => {
    const res = await dispatch({ jsonrpc: "2.0", id: 1, method: "tools/list" }, REQ, {});
    const tools = (res.result as { tools: Array<{ name: string; outputSchema?: unknown }> }).tools;
    expect(tools.length).toBe(MCP_TOOLS.length);
    for (const t of tools) expect(t.outputSchema, t.name).toBeDefined();
  });

  it("initialize negotiates the 2025-06-18 protocol (structuredContent-capable)", async () => {
    expect(PROTOCOL_VERSION).toBe("2025-06-18");
    const res = await dispatch(
      { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18" } },
      REQ,
      {},
    );
    expect((res.result as { protocolVersion: string }).protocolVersion).toBe("2025-06-18");
  });

  it("downgrades the negotiated protocol for an older client", async () => {
    const res = await dispatch(
      { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-03-26" } },
      REQ,
      {},
    );
    expect((res.result as { protocolVersion: string }).protocolVersion).toBe("2025-03-26");
  });
});

// --- structuredContent contract ----------------------------------------------------

// Each case dispatches a real tools/call whose stubbed feeds yield a non-empty result, so the
// item schema — not just the envelope — is validated against actual handler output.
const CASES: Array<{ label: string; name: string; args: Record<string, unknown>; nonEmpty: boolean }> = [
  { label: "search_corpus (compact)", name: "search_corpus", args: { query: "permit" }, nonEmpty: true },
  {
    label: "search_corpus (full)",
    name: "search_corpus",
    args: { query: "permit", response_mode: "full" },
    nonEmpty: true,
  },
  {
    label: "search_corpus (ids_only)",
    name: "search_corpus",
    args: { query: "permit", response_mode: "ids_only" },
    nonEmpty: true,
  },
  { label: "search_passages", name: "search_passages", args: { query: "phosphorus" }, nonEmpty: true },
  { label: "get_timeline", name: "get_timeline", args: {}, nonEmpty: true },
  { label: "get_entities", name: "get_entities", args: {}, nonEmpty: true },
  { label: "get_hypotheses", name: "get_hypotheses", args: {}, nonEmpty: true },
  { label: "get_documents", name: "get_documents", args: {}, nonEmpty: true },
  {
    label: "get_document",
    name: "get_document",
    args: { document_id: "recorder/deed-1.deed.yaml" },
    nonEmpty: true,
  },
  {
    label: "get_document (source_text)",
    name: "get_document",
    args: { document_id: "recorder/deed-1.deed.yaml", include_source_text: true },
    nonEmpty: true,
  },
  { label: "get_facts", name: "get_facts", args: {}, nonEmpty: true },
  { label: "get_facts (evidence)", name: "get_facts", args: { include_evidence: true }, nonEmpty: true },
  {
    label: "aggregate_facts (metric)",
    name: "aggregate_facts",
    args: { metric: "backup_generation_capacity_mw", group_by: "subject" },
    nonEmpty: true,
  },
  { label: "aggregate_facts (discovery)", name: "aggregate_facts", args: {}, nonEmpty: true },
  {
    label: "aggregate_facts (unknown metric)",
    name: "aggregate_facts",
    args: { metric: "not_a_metric" },
    nonEmpty: true,
  },
];

describe("structuredContent matches content and validates against outputSchema", () => {
  for (const c of CASES) {
    it(c.label, async () => {
      const result = await callTool(c.name, c.args);

      // A back-compat text block is always present…
      expect(result.content).toHaveLength(1);
      expect(result.content[0].type).toBe("text");
      const parsed = JSON.parse(result.content[0].text);

      // …and structuredContent equals it byte-for-byte (single source of truth).
      expect(result.structuredContent).toBeDefined();
      expect(result.structuredContent).toEqual(parsed);

      // structuredContent validates against the tool's declared outputSchema.
      const errors = validate(schemaOf(c.name), result.structuredContent);
      expect(errors, errors.join("\n")).toEqual([]);

      if (c.nonEmpty) {
        expect((result.structuredContent as { results: unknown[] }).results.length).toBeGreaterThan(0);
      }
    });
  }

  it("omits nothing: an empty-result envelope still validates (empty query short-circuit)", async () => {
    const result = await callTool("search_corpus", { query: "   " });
    expect((result.structuredContent as { results: unknown[] }).results).toEqual([]);
    expect(validate(schemaOf("search_corpus"), result.structuredContent)).toEqual([]);
  });
});
