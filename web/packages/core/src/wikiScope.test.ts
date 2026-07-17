import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { ConceptItem } from "./feeds";

// Per-site glossary scoping (#1567): each site's bundle carries only its own scoped
// `concepts` feed, and `wikiIndex` must resolve against the *active* site — never bleed
// one site's concepts (or a global cache entry) into another site's build.

const tmpDirs: string[] = [];

function concept(slug: string, title: string, aliases: string[] = []): ConceptItem {
  return { slug, title, kind: "concept", aliases, tags: [], summary: title, related: [], body: "" };
}

function manifestWith(concepts: ConceptItem[]): object {
  return {
    bundle_version: "test",
    contract_version: "1.4",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: 1,
    row_total: concepts.length,
    feeds: [
      {
        name: "concepts",
        path: "concepts.json",
        media_type: "application/json",
        schema: "s",
        kind: "collection",
        count: concepts.length,
      },
    ],
  };
}

/** A parent dir holding one bundle per slug under `<parent>/<slug>/`. */
function makeSiteBundles(bySlug: Record<string, ConceptItem[]>): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-wiki-scope-"));
  tmpDirs.push(parent);
  for (const [slug, concepts] of Object.entries(bySlug)) {
    const dir = join(parent, slug);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifestWith(concepts)));
    writeFileSync(join(dir, "concepts.json"), JSON.stringify(concepts));
  }
  return parent;
}

// wiki + bundle must come from the SAME reset boundary so they share one fresh bundle
// module (and thus one AsyncLocalStorage) — otherwise runWithSite and wikiIndex disagree.
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

describe("wikiIndex — per-site scoping (#1567)", () => {
  // Lima carries a network-global term (npdes) plus a Lima-only one (rda); the peer only
  // the global term — exactly what the export-time `sites:` filter produces.
  const parent = () =>
    makeSiteBundles({
      lima: [concept("npdes", "NPDES"), concept("rda", "Roadwork Development Agreement", ["RDA"])],
      "fort-wayne": [concept("npdes", "NPDES")],
    });

  it("resolves concepts against the ACTIVE site, never bleeding a peer's cache entry", async () => {
    const { bundle, wiki } = await load(parent());

    const lima = bundle.runWithSite("lima", () => wiki.wikiIndex({ scoped: true }));
    expect(lima.has(wiki.norm("NPDES"))).toBe(true);
    expect(lima.has(wiki.norm("RDA"))).toBe(true); // Lima's own concept + its alias

    // The peer must NOT see Lima's site-scoped term — the cache-not-keyed-by-site bug.
    const fw = bundle.runWithSite("fort-wayne", () => wiki.wikiIndex({ scoped: true }));
    expect(fw.has(wiki.norm("NPDES"))).toBe(true);
    expect(fw.has(wiki.norm("RDA"))).toBe(false);
  });

  it("scoped concept URLs point at the active site's own glossary", async () => {
    const { bundle, wiki } = await load(parent());

    const limaUrl = bundle.runWithSite(
      "lima",
      () => wiki.wikiIndex({ scoped: true }).get(wiki.norm("NPDES"))?.url,
    );
    expect(limaUrl).toBe("/network/american-sugar-creek-allen-co/site/concepts/npdes/");

    const fwUrl = bundle.runWithSite(
      "fort-wayne",
      () => wiki.wikiIndex({ scoped: true }).get(wiki.norm("NPDES"))?.url,
    );
    expect(fwUrl).toBe("/network/fort-wayne/site/concepts/npdes/");
  });

  it("unscoped (default) concept URLs stay on the network-global wiki", async () => {
    const { bundle, wiki } = await load(parent());
    const url = bundle.runWithSite("lima", () => wiki.wikiIndex().get(wiki.norm("NPDES"))?.url);
    expect(url).toBe("/wiki/concepts/npdes/");
  });
});
