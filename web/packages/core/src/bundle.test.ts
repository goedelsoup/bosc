import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

const tmpDirs: string[] = [];

function manifestWith(feeds: object[], contractVersion = "1.4"): object {
  return {
    bundle_version: "test",
    contract_version: contractVersion,
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: feeds.length,
    row_total: 0,
    feeds,
  };
}

function makeBundle(manifest: object, files: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-bundle-"));
  tmpDirs.push(dir);
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
  for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, name), body);
  return dir;
}

/** A parent dir holding one bundle per slug under `<parent>/<slug>/` — the per-site layout. */
function makeSiteBundles(
  bySlug: Record<string, { manifest: object; files: Record<string, string> }>,
): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-bundles-"));
  tmpDirs.push(parent);
  for (const [slug, { manifest, files }] of Object.entries(bySlug)) {
    const dir = join(parent, slug);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
    for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, name), body);
  }
  return parent;
}

// bundle.ts memoizes the resolved dir + manifest at module scope, so each case
// points WATERMARK_BUNDLE_DIR at a fresh fixture and re-imports with a clean registry.
async function loadBundleModule(dir: string): Promise<typeof import("./bundle")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./bundle");
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("bundle resolution + JSON feeds", () => {
  it("resolves the explicit WATERMARK_BUNDLE_DIR override and reads its feeds", async () => {
    const dir = makeBundle(
      manifestWith([
        {
          name: "things",
          path: "things.json",
          media_type: "application/json",
          schema: "s",
          kind: "collection",
          count: 2,
        },
      ]),
      { "things.json": JSON.stringify([{ a: 1 }, { a: 2 }]) },
    );
    const m = await loadBundleModule(dir);

    expect(m.bundleDir()).toBe(dir);
    expect(m.loadManifest().contract_version).toBe("1.4");
    expect(m.hasFeed("things")).toBe(true);
    expect(m.hasFeed("absent")).toBe(false);
    expect(m.loadFeed("things")).toEqual([{ a: 1 }, { a: 2 }]);
  });

  it("throws a helpful error for a feed not in the manifest", async () => {
    const dir = makeBundle(manifestWith([]), {});
    const m = await loadBundleModule(dir);
    expect(() => m.loadFeed("missing")).toThrow(/not in the .* bundle manifest/);
  });
});

describe("NDJSON feeds", () => {
  it("parses an .ndjson feed line-by-line, skipping blank lines", async () => {
    const dir = makeBundle(
      manifestWith([
        {
          name: "rows",
          path: "rows.ndjson",
          media_type: "application/x-ndjson",
          schema: "s",
          kind: "collection",
          count: 2,
        },
      ]),
      { "rows.ndjson": '{"a":1}\n{"a":2}\n\n' },
    );
    const m = await loadBundleModule(dir);
    expect(m.loadFeed("rows")).toEqual([{ a: 1 }, { a: 2 }]);
  });
});

describe("contract-version guard", () => {
  it("fails fast when the bundle's contract major differs", async () => {
    const dir = makeBundle(manifestWith([], "2.0"), {});
    const m = await loadBundleModule(dir);
    expect(() => m.loadManifest()).toThrow(/incompatible/);
  });

  it("accepts a matching major with a different minor", async () => {
    const dir = makeBundle(manifestWith([], "1.9"), {});
    const m = await loadBundleModule(dir);
    expect(m.loadManifest().contract_version).toBe("1.9");
  });
});

describe("per-site resolution", () => {
  const feed = (count: number) => ({
    name: "things",
    path: "things.json",
    media_type: "application/json",
    schema: "s",
    kind: "collection",
    count,
  });

  it("reads each site's bundle from its <parent>/<slug> subdir", async () => {
    const parent = makeSiteBundles({
      lima: { manifest: manifestWith([feed(1)]), files: { "things.json": JSON.stringify([{ s: "lima" }]) } },
      "fort-wayne": {
        manifest: manifestWith([feed(1)]),
        files: { "things.json": JSON.stringify([{ s: "fw" }]) },
      },
    });
    const m = await loadBundleModule(parent);

    // Default slug is Lima; an explicit slug reads that site's subdir.
    expect(m.loadFeed("things")).toEqual([{ s: "lima" }]);
    expect(m.loadFeed("things", "lima")).toEqual([{ s: "lima" }]);
    expect(m.loadFeed("things", "fort-wayne")).toEqual([{ s: "fw" }]);
    expect(m.bundleDir("fort-wayne")).toBe(join(parent, "fort-wayne"));
  });

  it("falls back to the override dir itself when it has no per-site subdir (back-compat)", async () => {
    // A flat WATERMARK_BUNDLE_DIR (no <slug>/ inside) still resolves for the default site.
    const dir = makeBundle(manifestWith([feed(1)]), { "things.json": JSON.stringify([{ s: "flat" }]) });
    const m = await loadBundleModule(dir);
    expect(m.bundleDir()).toBe(dir);
    expect(m.loadFeed("things")).toEqual([{ s: "flat" }]);
  });

  it("errors with the site slug when a bundle is missing", async () => {
    const parent = makeSiteBundles({
      lima: { manifest: manifestWith([]), files: {} },
    });
    const m = await loadBundleModule(parent);
    expect(() => m.loadManifest("nope")).toThrow(/site "nope"/);
  });
});
