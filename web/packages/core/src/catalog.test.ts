import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { Catalog, CatalogAtom } from "./catalog";
import { CATALOG_KINDS, parseHandle, resolveHandle } from "./catalog";

// --- parseHandle: pure, no bundle -----------------------------------------------------------
describe("parseHandle", () => {
  it("parses <kind>:<site>:<localId> and validates the kind", () => {
    expect(parseHandle("record:lima:recorder/x.deed.yaml")).toEqual({
      kind: "record",
      site: "lima",
      localId: "recorder/x.deed.yaml",
    });
  });

  it("keeps a colon inside the localId (splits on the first two only)", () => {
    // A composite/synthetic localId could carry a colon — the grammar must not lose it.
    expect(parseHandle("figure:lima:money:flow")?.localId).toBe("money:flow");
  });

  it("rejects an unknown kind and a malformed handle", () => {
    expect(parseHandle("bogus:lima:x")).toBeNull();
    expect(parseHandle("record:lima:")).toBeNull(); // empty localId
    expect(parseHandle("record::x")).toBeNull(); // empty site
    expect(parseHandle("recordlima-x")).toBeNull(); // no separators
  });
});

// --- resolveHandle: against a hand-built catalog (the contract's three failure reasons) ------
function catalogOf(atoms: CatalogAtom[]): Catalog {
  const byHandle = new Map(atoms.map((a) => [a.handle, a]));
  const sites = new Set(atoms.map((a) => a.site));
  return { site: "lima", version: "v", byHandle, sites };
}

describe("resolveHandle", () => {
  const atom: CatalogAtom = {
    handle: "record:lima:x.deed.yaml",
    kind: "record",
    site: "lima",
    localId: "x.deed.yaml",
    title: "A deed",
    feed: "records",
  };
  const catalog = catalogOf([atom]);

  it("resolves a live handle to its atom (pointer, not copy)", () => {
    const r = resolveHandle("record:lima:x.deed.yaml", catalog);
    expect(r).toEqual({ ok: true, atom });
  });

  it("reports unknown_kind for a malformed / off-set handle", () => {
    expect(resolveHandle("bogus:lima:x", catalog)).toEqual({ ok: false, reason: "unknown_kind" });
  });

  it("reports unknown_site for a well-formed handle to a site the catalog has no atoms for", () => {
    expect(resolveHandle("record:nowhere:x", catalog)).toEqual({
      ok: false,
      reason: "unknown_site",
    });
  });

  it("reports dangling for a known site but a missing atom", () => {
    expect(resolveHandle("record:lima:retired.deed.yaml", catalog)).toEqual({
      ok: false,
      reason: "dangling",
    });
  });
});

// --- loadCatalog: merges the bundle feed-backed tier with the web-only overlay ---------------
const tmpDirs: string[] = [];

function makeBundle(atoms: object[], version = "abc123"): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-catalog-"));
  tmpDirs.push(dir);
  const feed = {
    name: "catalog-index",
    path: "catalog-index.json",
    media_type: "application/json",
    schema: "s",
    kind: "object",
    count: 1,
  };
  const manifest = {
    site: "lima",
    bundle_version: "test",
    contract_version: "1.10.0",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: 1,
    row_total: 1,
    feeds: [feed],
  };
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
  writeFileSync(
    join(dir, "catalog-index.json"),
    JSON.stringify({ site: "lima", catalog_version: version, contract_version: "1.10.0", atoms }),
  );
  return dir;
}

async function loadCatalogModule(dir: string): Promise<typeof import("./catalogBuild")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./catalogBuild");
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("loadCatalog", () => {
  it("merges the catalog-index feed with the web-only overlay and resolves both", async () => {
    const dir = makeBundle([
      {
        handle: "record:lima:recorder/x.deed.yaml",
        kind: "record",
        site: "lima",
        local_id: "recorder/x.deed.yaml",
        title: "A deed",
        feed: "records",
      },
    ]);
    const m = await loadCatalogModule(dir);
    const catalog = m.loadCatalog("lima");

    expect(catalog.version).toBe("abc123");

    // Feed-backed atom (snake_case wire → camelCase) resolves.
    const rec = resolveHandle("record:lima:recorder/x.deed.yaml", catalog);
    expect(rec.ok).toBe(true);
    if (rec.ok) expect(rec.atom.localId).toBe("recorder/x.deed.yaml");

    // The overlay contributed the web-only kinds the bundle can't see (real Lima content).
    const kinds = new Set([...catalog.byHandle.values()].map((a) => a.kind));
    expect(kinds.has("doc")).toBe(true); // narrative/legal/reference
    expect(kinds.has("teardown")).toBe(true); // ALL_TEARDOWNS with a recordRel
    expect(kinds.has("figure")).toBe(true); // curated viz registry
    // Lima's Project BOSC walk is `comingSoon` (#1526) → not a *readable* surface, so it contributes
    // NO chapter atoms: a held story is grabbable nowhere. The catalog carries no `chapter` kind.
    expect(kinds.has("chapter")).toBe(false);
    expect(m.webOnlyAtoms("lima").some((a) => a.kind === "chapter")).toBe(false);
  });

  it("emits no chapter atoms for a site whose only story is held coming-soon (#1526)", async () => {
    const dir = makeBundle([]);
    const m = await loadCatalogModule(dir);
    // Fort Wayne's Project Zodiac overlay is `comingSoon`, so its chapters are grabbable nowhere —
    // a held walk contributes no readable atoms, just like Lima's.
    expect(m.webOnlyAtoms("fort-wayne").filter((a) => a.kind === "chapter")).toHaveLength(0);
  });

  it("degrades to overlay-only when the bundle ships no catalog-index feed", async () => {
    const dir = mkdtempSync(join(tmpdir(), "bosc-catalog-thin-"));
    tmpDirs.push(dir);
    writeFileSync(
      join(dir, "manifest.json"),
      JSON.stringify({
        site: "lima",
        bundle_version: "test",
        contract_version: "1.10.0",
        generated_at: "2026-01-01T00:00:00Z",
        feed_count: 0,
        row_total: 0,
        feeds: [],
      }),
    );
    const m = await loadCatalogModule(dir);
    const catalog = m.loadCatalog("lima");
    expect(catalog.version).toBe(""); // no feed
    expect(catalog.byHandle.size).toBeGreaterThan(0); // overlay still populated
  });

  it("keeps the first doc atom on a cross-collection slug collision (narrative wins)", async () => {
    // The three doc collections fold into one `doc` kind; a slug unique within a collection can
    // still collide across them. Force it, and assert keep-first (narrative → legal → reference)
    // so a later collection can't silently clobber an earlier doc when the catalog merges by handle.
    vi.doMock("./narrative", () => ({ NARRATIVE: [{ slug: "dup", title: "From narrative" }] }));
    vi.doMock("./legal", () => ({ LEGAL: [{ slug: "dup", title: "From legal" }] }));
    vi.doMock("./reference", () => ({ REFERENCE: [{ slug: "dup", title: "From reference" }] }));
    try {
      const dir = makeBundle([]); // overlay-only; the collision is in the web-only doc kind
      const m = await loadCatalogModule(dir);
      const catalog = m.loadCatalog("lima");

      const doc = catalog.byHandle.get("doc:lima:dup");
      expect(doc?.title).toBe("From narrative"); // first wins
      expect(doc?.feed).toBe("narrative");
      // Exactly one atom for the colliding handle — the legal/reference dups were dropped, not kept.
      const dups = [...catalog.byHandle.values()].filter((a) => a.handle === "doc:lima:dup");
      expect(dups).toHaveLength(1);
    } finally {
      vi.doUnmock("./narrative");
      vi.doUnmock("./legal");
      vi.doUnmock("./reference");
      vi.resetModules();
    }
  });
});

// --- cross-tier parity: the closed kind set can't drift from the Python data tier -----------
describe("catalog kind parity (#1093)", () => {
  it("CATALOG_KINDS matches the committed catalog-index.schema.json `kind` enum", () => {
    // The schema is generated from `bosc.site.feeds.CatalogKind`, so this pins the two tiers'
    // kind vocabularies together — adding a kind on one side without the other fails CI.
    const schemaPath = fileURLToPath(
      new URL("../../../../data/site/bundle/schemas/catalog-index.schema.json", import.meta.url),
    );
    const schema = JSON.parse(readFileSync(schemaPath, "utf-8")) as {
      $defs: { CatalogAtom: { properties: { kind: { enum: string[] } } } };
    };
    const enumKinds = schema.$defs.CatalogAtom.properties.kind.enum;
    expect([...enumKinds].sort()).toEqual([...CATALOG_KINDS].sort());
  });
});
