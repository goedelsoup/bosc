// Bundle reader tests (#914 + governance #1581).
// Each handler fetches its feed from `/feeds/<name>.json` over globalThis.fetch, so every
// case stubs those routes. Asserts filtering/sorting/join behavior AND the governed
// envelope: page-size caps, cursor pagination, and per-result shrink.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  handleGetDocuments,
  handleGetEntities,
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
    ],
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
  });

  it("strips assessment internals on an over-cap hypothesis", async () => {
    const env = await run(handleGetHypotheses, { max_tokens_per_result: 60, max_tokens: 100000 });
    const h1 = env.results.find((h) => h.id === "h1");
    const assessments = h1?.assessments as Record<string, unknown>[];
    // Identity retained, heavy `fields` payload gone.
    expect(assessments[0]).toHaveProperty("tag");
    expect(assessments[0]).not.toHaveProperty("fields");
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
