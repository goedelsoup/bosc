// Bundle reader tests (#914 + governance #1581).
// Each handler fetches its feed from `/feeds/<name>.json` over globalThis.fetch, so every
// case stubs those routes. Asserts filtering/sorting/join behavior AND the governed
// envelope: page-size caps, cursor pagination, and per-result shrink.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  handleGetDocument,
  handleGetDocuments,
  handleGetEntities,
  handleGetFacts,
  handleGetHypotheses,
  handleGetTimeline,
} from "@watermark/functions/api/_lib/mcpTools/bundleReaders";
import { decodeCursorOffset } from "@watermark/functions/api/_lib/mcpGovern";
import { type FetchRoute, jsonResponse, routingFetch } from "./_routeHarness";

const REQ = "https://directory.example/api/mcp";

interface Envelope {
  results: Record<string, unknown>[];
  token_estimate: number;
  truncated: boolean;
  next_cursor: string | null;
}

const TIMELINE = [
  { date: "2020-05-01", category: "permit", title: "C permit", detail: "z".repeat(4000) },
  { date: "2018-01-01", category: "permit", title: "A permit", parties: ["p"] },
  { date: "2019-03-01", category: "land", title: "B land deal" },
];

const ENTITIES = [
  {
    key: "acme",
    display: "Acme LLC",
    kind: "company",
    variants: ["Acme", "ACME"].concat(Array(50).fill("v")),
  },
  { key: "jane", display: "Jane Roe", kind: "person" },
];

const HYPOTHESES = {
  hypotheses: [
    { id: "h1", number: "1", name: "Boom", claim: "c", thesis: "t", status: "open", signals: [], groups: [] },
    { id: "h2", number: "2", name: "Bust", claim: "c", thesis: "t", status: "open", signals: [], groups: [] },
  ],
  assessments: [
    { site: "lima", hypothesis: "h1", signal: "s1", tag: "verified", fields: { big: "y".repeat(4000) } },
    { site: "fort-wayne", hypothesis: "h1", signal: "s2", tag: "inference" },
  ],
};

const DOCUMENTS = [
  {
    slug: "oepa",
    title: "Ohio EPA",
    description: "permits",
    entries: Array.from({ length: 30 }, (_, i) => ({
      rel: `oepa/${i}.pdf`,
      name: `doc ${i}`,
      suffix: ".pdf",
      media_type: "application/pdf",
      published: true,
      available: true,
    })),
  },
  {
    slug: "recorder",
    title: "Recorder",
    description: "deeds",
    entries: [
      {
        rel: "recorder/1.pdf",
        name: "deed",
        suffix: ".pdf",
        media_type: "application/pdf",
        published: true,
        available: true,
      },
      {
        rel: "recorder/scans/deed-1.pdf",
        name: "deed-1.pdf",
        size_bytes: 12345,
        suffix: "pdf",
        media_type: "application/pdf",
        render_class: "pdf",
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
    fields: { grantor: "Alice", grantee: "Bob LLC", parcel_ids: ["1", "2"], note: "z".repeat(4000) },
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
  {
    // Unjoined record — no source document (e.g. an assembled OPC estimate).
    rel: "aedg/roundabouts.opc.yaml",
    group: "opc",
    title: "OPC estimate",
    confidence: "medium",
    warnings: [],
    fields: { total: 1_000_000, sections: { paving: 500_000 } },
    approximate_paths: [],
    citation: {
      source: "aedg/roundabouts.opc.yaml",
      source_kind: "document",
      page: null,
      confidence: "medium",
      verified: false,
    },
    source_doc_rel: null,
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
  {
    subject: "facility:lima",
    subject_label: "Lima data center",
    subject_kind: "facility",
    predicate: "facility_draw",
    value: 347.9,
    unit: "MW",
    status: "inference",
    low: 302.5,
    high: 393.2,
    evidence: ev("derived"),
    feed: "facility-power",
  },
  {
    subject: "county:39003",
    subject_label: "Allen County, Ohio",
    subject_kind: "county",
    predicate: "total_employment",
    value: 49690,
    unit: "jobs",
    status: "verified",
    low: null,
    high: null,
    evidence: ev("connector"),
    feed: "economics-baseline",
  },
];

function feedRoute(name: string, data: unknown): FetchRoute {
  return { test: (url) => url.pathname === `/feeds/${name}.json`, respond: () => jsonResponse(200, data) };
}

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    routingFetch([
      feedRoute("timeline", TIMELINE),
      feedRoute("entities", ENTITIES),
      feedRoute("hypotheses", HYPOTHESES),
      feedRoute("documents", DOCUMENTS),
      feedRoute("records", RECORDS),
      feedRoute("facts", FACTS),
    ]),
  );
});

afterEach(() => vi.unstubAllGlobals());

async function run(
  handler: (p: unknown, u: string) => Promise<Array<{ type: "text"; text: string }>>,
  args: Record<string, unknown>,
): Promise<Envelope> {
  const content = await handler(args, REQ);
  return JSON.parse(content[0].text) as Envelope;
}

describe("handleGetTimeline", () => {
  it("returns a governed envelope, oldest-first", async () => {
    const env = await run(handleGetTimeline, {});
    expect(env.results.map((e) => e.date)).toEqual(["2018-01-01", "2019-03-01", "2020-05-01"]);
    expect(typeof env.token_estimate).toBe("number");
    expect(env.truncated).toBe(false);
    expect(env.next_cursor).toBeNull();
  });

  it("filters by since/until/category", async () => {
    const env = await run(handleGetTimeline, { since: "2019-01-01", category: "permit" });
    expect(env.results).toHaveLength(1);
    expect(env.results[0].title).toBe("C permit");
  });

  it("paginates by max_results with a resumable cursor", async () => {
    const p1 = await run(handleGetTimeline, { max_results: 2 });
    expect(p1.results).toHaveLength(2);
    expect(p1.truncated).toBe(true);
    expect(decodeCursorOffset(p1.next_cursor)).toBe(2);
    const p2 = await run(handleGetTimeline, { max_results: 2, cursor: p1.next_cursor });
    expect(p2.results).toHaveLength(1);
    expect(p2.truncated).toBe(false);
    expect(p2.next_cursor).toBeNull();
  });

  it("drops the heavy `detail` field when a result exceeds max_tokens_per_result", async () => {
    const env = await run(handleGetTimeline, { max_tokens_per_result: 40, max_tokens: 100000 });
    const heavy = env.results.find((e) => e.title === "C permit");
    expect(heavy).toBeDefined();
    expect(heavy).not.toHaveProperty("detail");
  });
});

describe("handleGetEntities", () => {
  it("filters by type and returns an envelope", async () => {
    const env = await run(handleGetEntities, { type: "person" });
    expect(env.results).toHaveLength(1);
    expect(env.results[0].key).toBe("jane");
  });

  it("sheds variant/address lists on an over-cap entity", async () => {
    const env = await run(handleGetEntities, { type: "company", max_tokens_per_result: 30 });
    const acme = env.results[0];
    expect(acme.key).toBe("acme");
    expect(acme).not.toHaveProperty("variants");
  });
});

describe("handleGetHypotheses", () => {
  it("joins assessments onto their hypothesis and filters by site", async () => {
    const env = await run(handleGetHypotheses, { site: "lima" });
    const h1 = env.results.find((h) => h.id === "h1");
    const h2 = env.results.find((h) => h.id === "h2");
    expect((h1?.assessments as unknown[]).length).toBe(1);
    expect((h2?.assessments as unknown[]).length).toBe(0);
    // The true total travels alongside the (possibly capped) list.
    expect(h1?.assessments_total).toBe(1);
    expect(h2?.assessments_total).toBe(0);
  });

  it("strips assessment internals on an over-cap hypothesis, keeping the true total", async () => {
    const env = await run(handleGetHypotheses, { max_tokens_per_result: 60, max_tokens: 100000 });
    const h1 = env.results.find((h) => h.id === "h1");
    const assessments = h1?.assessments as Record<string, unknown>[];
    // Identity retained, heavy `fields` payload gone.
    expect(assessments[0]).toHaveProperty("tag");
    expect(assessments[0]).not.toHaveProperty("fields");
    // assessments_total stays truthful even if the list itself was capped.
    expect(h1?.assessments_total).toBe(2);
  });
});

describe("handleGetDocuments", () => {
  it("filters by collection and preserves the true entry_count", async () => {
    const env = await run(handleGetDocuments, { collection: "oepa" });
    expect(env.results).toHaveLength(1);
    expect(env.results[0].entry_count).toBe(30);
  });

  it("caps the entry list on an over-cap collection while keeping entry_count truthful", async () => {
    const env = await run(handleGetDocuments, { collection: "oepa", max_tokens_per_result: 120 });
    const oepa = env.results[0];
    expect(oepa.entry_count).toBe(30); // reported total unchanged
    expect((oepa.entries as unknown[]).length).toBeLessThan(30); // list trimmed
  });
});

describe("handleGetDocument", () => {
  interface Metadata {
    record_rel: string | null;
    title: string | null;
    source_doc_rel: string | null;
    document_file: { rel: string } | null;
  }

  it("resolves by record id and joins its source document + fields + citation", async () => {
    const env = await run(handleGetDocument, { document_id: "recorder/deed-1.deed.yaml" });
    expect(env.results).toHaveLength(1);
    const doc = env.results[0];
    expect(doc.document_id).toBe("recorder/deed-1.deed.yaml");
    expect(doc.collection).toBe("recorder");
    const meta = doc.metadata as unknown as Metadata;
    expect(meta.title).toBe("Warranty Deed");
    expect(meta.document_file?.rel).toBe("recorder/scans/deed-1.pdf"); // joined via source_doc_rel
    expect((doc.fields as Record<string, unknown>).grantor).toBe("Alice");
    expect(doc.field_count).toBe(4);
    expect((doc.citation as { verified: boolean }).verified).toBe(true);
    expect(doc.warnings).toEqual(["consideration not stated"]);
    expect(doc.source_text).toBeUndefined(); // off by default
    expect(env.truncated).toBe(false);
    expect(env.next_cursor).toBeNull();
  });

  it("resolves by document rel, reverse-joining the record (canonical id = record rel)", async () => {
    const env = await run(handleGetDocument, { document_id: "recorder/scans/deed-1.pdf" });
    expect(env.results).toHaveLength(1);
    const doc = env.results[0];
    expect(doc.document_id).toBe("recorder/deed-1.deed.yaml");
    expect((doc.metadata as unknown as Metadata).document_file?.rel).toBe("recorder/scans/deed-1.pdf");
    expect((doc.fields as Record<string, unknown>).grantee).toBe("Bob LLC");
  });

  it("strips a search_corpus `records:` id prefix", async () => {
    const env = await run(handleGetDocument, { document_id: "records:recorder/deed-1.deed.yaml" });
    expect(env.results[0].document_id).toBe("recorder/deed-1.deed.yaml");
  });

  it("projects only the requested fields, keeping field_count as the true total", async () => {
    const env = await run(handleGetDocument, {
      document_id: "recorder/deed-1.deed.yaml",
      fields: ["grantor", "parcel_ids"],
    });
    const doc = env.results[0];
    expect(Object.keys(doc.fields as object).sort()).toEqual(["grantor", "parcel_ids"]);
    expect(doc.field_count).toBe(4);
  });

  it("projects only the requested sections", async () => {
    const env = await run(handleGetDocument, {
      document_id: "recorder/deed-1.deed.yaml",
      sections: ["metadata"],
    });
    const doc = env.results[0];
    expect(doc.metadata).toBeDefined();
    expect(doc.fields).toBeUndefined();
    expect(doc.citation).toBeUndefined();
    expect(doc.warnings).toBeUndefined();
  });

  it("attaches flattened source_text on request", async () => {
    const env = await run(handleGetDocument, {
      document_id: "recorder/deed-1.deed.yaml",
      include_source_text: true,
    });
    const text = env.results[0].source_text as string;
    expect(typeof text).toBe("string");
    expect(text).toContain("grantor Alice");
  });

  it("resolves an unjoined record with no document_file", async () => {
    const env = await run(handleGetDocument, { document_id: "aedg/roundabouts.opc.yaml" });
    const doc = env.results[0];
    expect((doc.metadata as unknown as Metadata).document_file).toBeNull();
    expect((doc.fields as Record<string, unknown>).total).toBe(1_000_000);
  });

  it("returns an empty result set for an unknown id", async () => {
    const env = await run(handleGetDocument, { document_id: "nope/nope.yaml" });
    expect(env.results).toHaveLength(0);
    expect(env.truncated).toBe(false);
    expect(env.next_cursor).toBeNull();
  });

  it("sheds fields to satisfy max_tokens while keeping citation + a truthful field_count", async () => {
    const env = await run(handleGetDocument, {
      document_id: "recorder/deed-1.deed.yaml",
      max_tokens: 100,
    });
    const doc = env.results[0];
    expect(env.truncated).toBe(true);
    expect(doc.field_count).toBe(4); // true total preserved
    expect(Object.keys(doc.fields as object).length).toBeLessThan(4); // list shed
    expect(doc.citation).toBeDefined(); // provenance never dropped
    expect(doc.metadata).toBeDefined();
  });
});

describe("handleGetFacts", () => {
  it("returns compact tuples (no evidence) in a governed envelope, sorted", async () => {
    const env = await run(handleGetFacts, {});
    expect(env.results.length).toBe(4);
    // county:… sorts before facility:… ; within a subject, predicate ascending.
    expect(env.results.map((f) => `${f.subject}/${f.predicate}`)).toEqual([
      "county:39003/total_employment",
      "facility:lima/facility_draw",
      "facility:lima/genset_count",
      "facility:lima/genset_rating",
    ]);
    expect(env.results[0].evidence).toBeUndefined(); // compact by default
    expect(env.results[0]).toMatchObject({ value: 49690, unit: "jobs", status: "verified" });
    expect(env.next_cursor).toBeNull();
  });

  it("filters by subject flexibly (key / label / kind, case-insensitive)", async () => {
    const byKind = await run(handleGetFacts, { subject: "facility" });
    expect(byKind.results.every((f) => f.subject === "facility:lima")).toBe(true);
    expect(byKind.results.length).toBe(3);
    const byLabel = await run(handleGetFacts, { subject: "allen county" });
    expect(byLabel.results.map((f) => f.subject)).toEqual(["county:39003"]);
  });

  it("filters by predicate list and computes the motivating example", async () => {
    const env = await run(handleGetFacts, {
      subject: "facility",
      predicate: ["genset_count", "genset_rating"],
    });
    const byPred = Object.fromEntries(env.results.map((f) => [f.predicate, f.value as number]));
    expect(Object.keys(byPred).sort()).toEqual(["genset_count", "genset_rating"]);
    expect(byPred.genset_count * byPred.genset_rating).toBeCloseTo(313.5);
  });

  it("accepts a single predicate string and filters by status", async () => {
    const one = await run(handleGetFacts, { predicate: "total_employment" });
    expect(one.results.map((f) => f.subject)).toEqual(["county:39003"]);
    const inf = await run(handleGetFacts, { status: "inference" });
    expect(inf.results.map((f) => f.predicate)).toEqual(["facility_draw"]);
  });

  it("attaches evidence + the uncertainty band only when requested", async () => {
    const withEv = await run(handleGetFacts, {
      subject: "facility",
      predicate: "facility_draw",
      include_evidence: true,
    });
    const draw = withEv.results.find((f) => f.predicate === "facility_draw");
    expect(draw?.evidence).toMatchObject({ source_kind: "derived", page: null, verified: false });
    expect(draw?.low).toBe(302.5);
    expect(draw?.high).toBe(393.2);
    const compact = await run(handleGetFacts, { predicate: "genset_count" });
    expect(compact.results[0].evidence).toBeUndefined();
  });

  it("paginates with a cursor", async () => {
    const first = await run(handleGetFacts, { max_results: 2 });
    expect(first.results.length).toBe(2);
    expect(first.next_cursor).not.toBeNull();
    expect(decodeCursorOffset(first.next_cursor)).toBe(2);
    const second = await run(handleGetFacts, { max_results: 2, cursor: first.next_cursor });
    expect(second.results.length).toBe(2);
    expect(second.next_cursor).toBeNull();
  });
});
