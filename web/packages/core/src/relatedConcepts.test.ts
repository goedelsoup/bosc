import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

// `relatedConcepts` (#1572): the glossary terms an entity page cross-links to. The corpus concepts
// don't `[[link]]` entities, so it's a prose match — a concept qualifies when any of the entity's
// names appears as a whole normalized phrase in the concept's title/summary/body — with the same
// specificity floor and site-scoping as the open-question / hypothesis backlinks it sits beside.

const tmpDirs: string[] = [];

function concept(slug: string, title: string, summary: string, body: string) {
  return { slug, title, kind: "concept", aliases: [], tags: [], summary, related: [], body };
}

const CONCEPTS = [
  concept("consumptive-cooling", "Consumptive cooling", "Google runs closed-loop cooling.", ""),
  concept("assimilative-capacity", "Assimilative capacity", "", "The reach below the Amazon campus."),
  concept("gravel-pit", "Gravel pit", "An unrelated glossary term.", "No party named here."),
];

function makeBundle(slug: string, feeds: Record<string, unknown>): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-rc-"));
  tmpDirs.push(parent);
  const dir = join(parent, slug);
  mkdirSync(dir, { recursive: true });
  const entries = Object.entries(feeds);
  const manifest = {
    bundle_version: "test",
    contract_version: "1.27",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: entries.length,
    row_total: 0,
    feeds: entries.map(([name]) => ({
      name,
      path: `${name}.json`,
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: 0,
    })),
  };
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
  for (const [name, rows] of entries) writeFileSync(join(dir, `${name}.json`), JSON.stringify(rows));
  return parent;
}

async function load(dir: string) {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  const bundle = await import("./bundle");
  const wiki = await import("./wiki");
  return { bundle, wiki };
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("relatedConcepts — concepts that name an entity (#1572)", () => {
  it("matches a concept naming the entity in its summary or its body, as a whole phrase", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", { concepts: CONCEPTS }));
    const google = bundle.runWithSite("lima", () => wiki.relatedConcepts(["Google"]));
    expect(google.map((c) => c.slug)).toEqual(["consumptive-cooling"]);
    const amazon = bundle.runWithSite("lima", () => wiki.relatedConcepts(["Amazon"]));
    expect(amazon.map((c) => c.slug)).toEqual(["assimilative-capacity"]);
  });

  it("returns network-global concept URLs by default, site-scoped ones when asked (#1567)", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", { concepts: CONCEPTS }));
    const global = bundle.runWithSite("lima", () => wiki.relatedConcepts(["Google"]));
    expect(global[0].url).toBe("/wiki/concepts/consumptive-cooling/");
    const scoped = bundle.runWithSite("lima", () => wiki.relatedConcepts(["Google"], { scoped: true }));
    expect(scoped[0].url).toContain("/site/concepts/consumptive-cooling/");
  });

  it("holds the specificity floor — a ≤3-char single-token name can't match noise", async () => {
    // A concept body that contains "ADM" as a substring of a longer token must not backlink from
    // a 3-char entity alias; only whole-phrase, ≥4-char (or multi-word) names qualify.
    const concepts = [concept("x", "X", "The ADMINISTRATION acted.", "")];
    const { bundle, wiki } = await load(makeBundle("lima", { concepts }));
    expect(bundle.runWithSite("lima", () => wiki.relatedConcepts(["ADM"]))).toEqual([]);
  });

  it("matches on any of the entity's names (display + variants), deduped by concept", async () => {
    const concepts = [concept("y", "Y", "Alphabet Inc. and Google are the same party.", "")];
    const { bundle, wiki } = await load(makeBundle("lima", { concepts }));
    // Both names hit the one concept — it appears once, not twice.
    const hits = bundle.runWithSite("lima", () => wiki.relatedConcepts(["Google", "Alphabet Inc."]));
    expect(hits).toHaveLength(1);
    expect(hits[0].slug).toBe("y");
  });

  it("returns nothing on a build without a concepts feed", async () => {
    const { bundle, wiki } = await load(makeBundle("thin", { entities: [] }));
    expect(bundle.runWithSite("thin", () => wiki.relatedConcepts(["Google"]))).toEqual([]);
  });
});
