import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { fmtUsd, fmtUsdFull } from "./money";

const tmpDirs: string[] = [];

function makeBundle(records: object[]): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-mf-"));
  tmpDirs.push(dir);
  const feeds = [
    {
      name: "records",
      path: "records.json",
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: records.length,
    },
  ];
  writeFileSync(
    join(dir, "manifest.json"),
    JSON.stringify({
      bundle_version: "test",
      contract_version: "1.4",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: 0,
      feeds,
    }),
  );
  writeFileSync(join(dir, "records.json"), JSON.stringify(records));
  return dir;
}

async function loadMoneyFlow(dir: string): Promise<typeof import("./moneyFlow")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./moneyFlow");
}

const OPC_RECORD = {
  rel: "aedg/roundabouts.summary.opc.yaml",
  group: "opc",
  title: "OPC",
  warnings: [],
  fields: {
    meta: { summary_construction_total: 14223081 },
    sub_estimates: [
      { name: "Cole Street Corridor", total: 3899800 },
      { name: "Bluelick Road Corridor", total: 2180907 },
    ],
  },
  approximate_paths: [],
  citation: { source: "x", source_kind: "document", verified: true },
};

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("USD formatters", () => {
  it("compact form keeps significant decimals and whole-million integers", () => {
    expect(fmtUsd(14_500_000)).toBe("$14.5M");
    expect(fmtUsd(3_520_000)).toBe("$3.52M");
    expect(fmtUsd(14_223_081)).toBe("$14.22M");
    // The trailing-zero strip must NOT eat integer zeros (regression guard).
    expect(fmtUsd(500_000_000)).toBe("$500M");
    expect(fmtUsd(14_000_000)).toBe("$14M");
  });

  it("full form groups thousands", () => {
    expect(fmtUsdFull(14223081)).toBe("$14,223,081");
    expect(fmtUsdFull(1535218)).toBe("$1,535,218");
  });
});

describe("buildMoneyFlow", () => {
  it("reads the OPC line items + total from the records feed (no fork)", async () => {
    const { buildMoneyFlow } = await loadMoneyFlow(makeBundle([OPC_RECORD]));
    const m = buildMoneyFlow();
    expect(m.opcFromFeed).toBe(true);
    expect(m.opcTotalUsd).toBe(14223081);
    expect(m.opcItems).toHaveLength(2);
    expect(m.opcItems[0]).toEqual({ name: "Cole Street Corridor", usd: 3899800 });
    expect(m.collectedUsd).toBe(14_500_000);
    expect(m.firstAward.usd).toBe(3_520_000);
  });

  it("models the abatement-per-job as a labeled [open] band, never a record read", async () => {
    const { buildMoneyFlow } = await loadMoneyFlow(makeBundle([OPC_RECORD]));
    const m = buildMoneyFlow();
    // The actual School District Compensation $ stay non-public...
    expect(m.abatement.schoolTermsPublic).toBe(false);
    // ...so the per-job is carried as a modeled [open] band, not a verified figure.
    const pj = m.abatementPerJob;
    expect(pj.tag).toBe("open");
    expect(pj.lowUsd).toBeLessThan(pj.highUsd);
    expect(pj.centralUsd).toBeGreaterThanOrEqual(pj.lowUsd);
    expect(pj.centralUsd).toBeLessThanOrEqual(pj.highUsd);
  });

  it("computes each profile deterministically from the labeled constants", async () => {
    const { buildAbatementPerJob } = await loadMoneyFlow(makeBundle([OPC_RECORD]));
    const pj = buildAbatementPerJob();
    const keys = pj.profiles.map((p) => p.key);
    // The defense/GovCloud case is one modeling profile among a few.
    expect(keys).toContain("govcloud");
    expect(pj.profiles.length).toBeGreaterThanOrEqual(3);
    // Per-job = capex × buildingShare × (assess × mills) × pct × years ÷ jobs.
    const { capexUsd, effectiveRate, abatePct, termYears } = pj.assumptions;
    for (const p of pj.profiles) {
      const expected = Math.round(
        (capexUsd * p.buildingShare * effectiveRate * abatePct * termYears) / p.jobs,
      );
      expect(p.perJobUsd).toBe(expected);
    }
    // The "stated" profile is the central reference; the hardened build is the ceiling.
    expect(pj.centralUsd).toBe(pj.profiles.find((p) => p.key === "stated")?.perJobUsd);
    expect(pj.highUsd).toBe(pj.profiles.find((p) => p.key === "govcloud")?.perJobUsd);
  });

  it("falls back to the curated OPC items when the feed is absent (CI fixture)", async () => {
    const { buildMoneyFlow } = await loadMoneyFlow(makeBundle([]));
    const m = buildMoneyFlow();
    expect(m.opcFromFeed).toBe(false);
    expect(m.opcItems).toHaveLength(6);
    expect(m.opcTotalUsd).toBeGreaterThan(0);
  });
});
