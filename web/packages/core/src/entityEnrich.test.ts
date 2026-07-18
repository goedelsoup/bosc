import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { LeiInventory, RelationshipEdge } from "./feeds";
import { entityDegree, leiAddress } from "./entityEnrich";

// Entity-page enrichment (#1572, epic #1560 workstream C): the corpus-grounded joins behind the
// richer entity wiki page — graph degree (off the `relationships` edge set), the GLEIF registry
// record (joined by exact LEI), and its parent chain resolved to entity pages. `entityDegree` and
// `leiAddress` are pure; `entityLei`/`leiParent` read the active build's feeds, so they're driven
// against a tmp bundle the way the hypothesis-node helpers are.

const tmpDirs: string[] = [];

function edge(src: string, dst: string): RelationshipEdge {
  return { src, rel: "owns", dst, date: "", ref: "", source: "recorder/x.yaml" };
}

describe("entityDegree — a node's graph degree (#1572)", () => {
  it("counts directed edges and distinct neighbors", () => {
    const out = [edge("A", "B"), edge("A", "C")];
    const inc = [edge("D", "A")];
    expect(entityDegree("A", out, inc)).toEqual({ out: 2, in: 1, total: 3, neighbors: 3 });
  });

  it("dedupes neighbors — two edges to the same party are degree 2, one neighbor", () => {
    const out = [edge("A", "B"), edge("A", "B")];
    expect(entityDegree("A", out, []).neighbors).toBe(1);
    expect(entityDegree("A", out, []).total).toBe(2);
  });

  it("does not count a self-edge as a neighbor", () => {
    const d = entityDegree("A", [edge("A", "A")], [edge("A", "A")]);
    expect(d).toEqual({ out: 1, in: 1, total: 2, neighbors: 0 });
  });

  it("is zero for an isolated node", () => {
    expect(entityDegree("A", [], [])).toEqual({ out: 0, in: 0, total: 0, neighbors: 0 });
  });
});

describe("leiAddress — a one-line GLEIF address", () => {
  it("joins the non-empty parts, order city → region → country", () => {
    expect(leiAddress({ city: "CALGARY", region: "CA-AB", country: "CA" })).toBe("CALGARY, CA-AB, CA");
    expect(leiAddress({ country: "US" })).toBe("US");
  });
  it("is null when empty or missing", () => {
    expect(leiAddress(null)).toBeNull();
    expect(leiAddress({})).toBeNull();
    expect(leiAddress(undefined)).toBeNull();
  });
});

// --- feed-backed joins (entityLei / leiParent) ------------------------------------------------

const INVENTORY: LeiInventory = {
  meta: {},
  leads: [],
  records: [
    {
      watchlist_name: "Cenovus Energy Inc.",
      lei: "254900LJGL2N2XEMD470",
      legal_name: "Cenovus Energy Inc.",
      jurisdiction: "CA",
      legal_form: "UDLA",
      entity_status: "ACTIVE",
      registration_status: "ISSUED",
      last_update: "2026-02-19T19:01:07Z",
      legal_address: { city: "CALGARY", region: "CA-AB", country: "CA" },
      direct_parent: null,
      ultimate_parent: null,
      note: "Successor to Husky Energy.",
    },
    {
      watchlist_name: "General Dynamics Land Systems Inc.",
      lei: "GDLS0000000000000000",
      legal_name: "General Dynamics Land Systems Inc.",
      direct_parent: null,
      // The ultimate parent is a `{lei, name}` ref (the shape the feed actually carries) — never a
      // bare code, which the old TS type wrongly assumed and which rendered `[object Object]`.
      ultimate_parent: { lei: "9C1X8XOOTYY2FNYTVH06", name: "GENERAL DYNAMICS CORPORATION" },
    },
  ],
};

// An entity node whose `lei` matches the General Dynamics ultimate parent — so the parent resolves
// to a clickable entity page.
const ENTITIES = [
  { key: "GENERAL DYNAMICS", display: "General Dynamics Corp.", lei: "9C1X8XOOTYY2FNYTVH06" },
];

function makeBundle(slug: string, feeds: Record<string, unknown>): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-ee-"));
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
      kind: name === "lei" ? "object" : "collection",
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
  const enrich = await import("./entityEnrich");
  return { bundle, enrich };
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("entityLei — GLEIF join by exact code (#1572)", () => {
  it("joins an entity's LEI to its registry record", async () => {
    const { bundle, enrich } = await load(makeBundle("lima", { lei: INVENTORY, entities: ENTITIES }));
    const rec = bundle.runWithSite("lima", () => enrich.entityLei({ lei: "254900LJGL2N2XEMD470" }));
    expect(rec?.legal_name).toBe("Cenovus Energy Inc.");
    expect(rec?.jurisdiction).toBe("CA");
  });

  it("returns null for an entity with no LEI or an unknown LEI", async () => {
    const { bundle, enrich } = await load(makeBundle("lima", { lei: INVENTORY }));
    expect(bundle.runWithSite("lima", () => enrich.entityLei({ lei: null }))).toBeNull();
    expect(bundle.runWithSite("lima", () => enrich.entityLei({ lei: "NOPE" }))).toBeNull();
  });

  it("returns null on a build without the lei feed", async () => {
    const { bundle, enrich } = await load(makeBundle("thin", { entities: ENTITIES }));
    expect(bundle.runWithSite("thin", () => enrich.entityLei({ lei: "254900LJGL2N2XEMD470" }))).toBeNull();
  });
});

describe("leiParent — resolve a GLEIF parent ref (#1572)", () => {
  it("resolves a parent LEI that is itself an entity node to a clickable page", async () => {
    const { bundle, enrich } = await load(makeBundle("lima", { lei: INVENTORY, entities: ENTITIES }));
    const parent = bundle.runWithSite("lima", () =>
      enrich.leiParent({ lei: "9C1X8XOOTYY2FNYTVH06", name: "GENERAL DYNAMICS CORPORATION" }),
    );
    expect(parent?.name).toBe("GENERAL DYNAMICS CORPORATION");
    expect(parent?.href).toBe("/wiki/entities/general-dynamics/");
  });

  it("keeps the authoritative name but no href when the parent isn't a node", async () => {
    const { bundle, enrich } = await load(makeBundle("lima", { lei: INVENTORY, entities: ENTITIES }));
    const parent = bundle.runWithSite("lima", () =>
      enrich.leiParent({ lei: "UNKNOWNPARENTLEI0000", name: "Some Holding Co" }),
    );
    expect(parent).toEqual({ lei: "UNKNOWNPARENTLEI0000", name: "Some Holding Co", href: undefined });
  });

  it("is null for a missing ref", async () => {
    const { bundle, enrich } = await load(makeBundle("lima", { lei: INVENTORY, entities: ENTITIES }));
    expect(bundle.runWithSite("lima", () => enrich.leiParent(null))).toBeNull();
    expect(bundle.runWithSite("lima", () => enrich.leiParent(undefined))).toBeNull();
  });
});
