import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

// Mirrors bundle.test.ts: askIndex.ts reads through bundle.ts, which memoizes the
// resolved dir + manifest at module scope, so each case points WATERMARK_BUNDLE_DIR at a
// fresh fixture and re-imports with a clean registry.
const tmpDirs: string[] = [];

function feedRef(name: string, path: string, count: number, kind = "collection"): object {
  return { name, path, media_type: "application/json", schema: "s", kind, count };
}

function makeBundle(feeds: object[], files: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-ask-"));
  tmpDirs.push(dir);
  writeFileSync(
    join(dir, "manifest.json"),
    JSON.stringify({
      bundle_version: "test",
      contract_version: "1.1",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: 0,
      feeds,
    }),
  );
  for (const [name, body] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), body);
  }
  return dir;
}

async function loadAskIndex(dir: string): Promise<typeof import("./askIndex")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./askIndex");
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

const RECORD = {
  rel: "aedg/roundabouts.summary.opc.yaml",
  group: "opc",
  title: "Roundabouts OPC — summary",
  confidence: "high",
  warnings: [],
  fields: { instrument_no: "12345", roadway_subtotal: "$1,200,000", nested: { skip: 1 } },
  approximate_paths: [],
  citation: {
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    source_kind: "document",
    page: 318,
    confidence: "high",
    verified: true,
  },
};

const ENTITY = {
  key: "AMAZON COM SERVICES",
  display: "Amazon.com Services LLC",
  kind: "company",
  variants: ["AWS"],
  signals: [],
  roles: { buyer: 2 },
  parcels: [],
  addresses: [],
  sources: ["data/extracted/entities/graph.yaml"],
};

describe("buildAskIndex", () => {
  it("emits one citation-keyed, deep-linked unit per record with its figures in text", async () => {
    const dir = makeBundle([feedRef("records", "feeds/records.json", 1)], {
      "feeds/records.json": JSON.stringify([RECORD]),
    });
    const m = await loadAskIndex(dir);
    const units = m.buildAskIndex();

    expect(units).toHaveLength(1);
    const u = units[0];
    expect(u.id).toBe("records:aedg/roundabouts.summary.opc.yaml");
    expect(u.url).toBe("/network/american-sugar-creek-allen-co/site/records/opc/");
    expect(u.source).toBe("data/documents/aedg/PRR-01-bundle.ocr.pdf");
    expect(u.page).toBe(318);
    expect(u.verified).toBe(true);
    // Scalar fields are flattened; nested objects are recursed so their leaf values are indexed.
    expect(u.text).toContain("instrument_no 12345");
    expect(u.text).toContain("roadway_subtotal");
    expect(u.text).toContain("skip 1"); // nested: { skip: 1 } — leaf included (#327)
  });

  it("synthesizes provenance for entities (source paths, not a Citation)", async () => {
    const dir = makeBundle([feedRef("entities", "feeds/entities.json", 1)], {
      "feeds/entities.json": JSON.stringify([ENTITY]),
    });
    const m = await loadAskIndex(dir);
    const [u] = m.buildAskIndex();
    expect(u.id).toBe("entities:AMAZON COM SERVICES");
    expect(u.url).toBe("/wiki/entities/amazon-com-services/");
    expect(u.source).toBe("data/extracted/entities/graph.yaml");
  });

  it("skips feeds absent from the manifest", async () => {
    const dir = makeBundle([], {});
    const m = await loadAskIndex(dir);
    expect(m.buildAskIndex()).toEqual([]);
  });
});
