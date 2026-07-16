import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

// buildDilution reads the bundle at call time; point WATERMARK_BUNDLE_DIR at a fixture
// and re-import with a clean registry (same harness as bundle.test.ts).
const tmpDirs: string[] = [];

function pv(value: number) {
  return { value, unit: "x", source: "test", citation: "t", confidence: "high", asof: null };
}

function makeBundle(scenarios: object[]): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-dil-"));
  tmpDirs.push(dir);
  const feeds = [
    {
      name: "hydrology-scenarios",
      path: "hydrology-scenarios.json",
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: scenarios.length,
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
  writeFileSync(join(dir, "hydrology-scenarios.json"), JSON.stringify(scenarios));
  return dir;
}

async function loadDilution(dir: string): Promise<typeof import("./dilution")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./dilution");
}

const assim = (discharger: string, receiving: string, discharge: number, lowFlow: number) => ({
  discharger,
  receiving_water: receiving,
  discharge: pv(discharge),
  design_low_flow: pv(lowFlow),
  flag: "violation",
});

const BUILDOUT = {
  scenario: {
    name: "buildout",
    cooling_demand: pv(3.92),
    consumptive_fraction: pv(0.8),
  },
  consumptive_loss: pv(4.851392),
  receiving_7q10: pv(0.2),
  receiving_live: pv(36.3),
  balance: pv(0),
  assimilative: [
    assim("Shawnee II WWTP", "Ottawa River", 4.641, 0.2),
    assim("American Bath WWTP", "Pike Run", 2.3205, 0.03),
    assim("American II WWTP", "Dug Run", 1.8564, 0.78),
  ],
};

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("dilution math", () => {
  it("drawCfs scales cooling demand by the per-MGD slope", async () => {
    const { buildDilution, drawCfs } = await loadDilution(makeBundle([BUILDOUT]));
    const data = buildDilution();
    // Full buildout reproduces the feed's consumptive loss exactly (no fork).
    expect(drawCfs(data, data.maxCoolingMgd)).toBeCloseTo(4.851392, 5);
    // Half the cooling → half the draw.
    expect(drawCfs(data, data.maxCoolingMgd / 2)).toBeCloseTo(4.851392 / 2, 5);
  });

  it("dilutionMultiple divides by the floor, and is Infinity when the river is dry", async () => {
    const { dilutionMultiple } = await loadDilution(makeBundle([BUILDOUT]));
    expect(dilutionMultiple(4.851392, 0.2)).toBeCloseTo(24.26, 1);
    expect(dilutionMultiple(4.851392, 1.6)).toBeCloseTo(3.03, 1);
    expect(dilutionMultiple(4.851392, 0)).toBe(Number.POSITIVE_INFINITY);
  });
});

describe("buildDilution — feed-sourced (no fork)", () => {
  it("reads the buildout draw + annual 7Q10 from the feed", async () => {
    const { buildDilution } = await loadDilution(makeBundle([BUILDOUT]));
    const data = buildDilution();
    expect(data.fromFeed).toBe(true);
    expect(data.maxCoolingMgd).toBe(3.92);
    expect(data.consumptiveFraction).toBe(0.8);
    expect(data.drawAtBuildoutCfs).toBeCloseTo(4.851392, 5);
    // annual floor is the feed's receiving_7q10; the seasonal floors are cited consts.
    expect(data.floors.find((f) => f.key === "annual")?.cfs).toBe(0.2);
    expect(data.floors.find((f) => f.key === "summer")?.cfs).toBe(1.6);
    expect(data.floors.find((f) => f.key === "driest")?.cfs).toBe(0);
  });

  it("falls back to curated defaults when the feed is absent (CI fixture path)", async () => {
    const { buildDilution } = await loadDilution(makeBundle([]));
    const data = buildDilution();
    expect(data.fromFeed).toBe(false);
    expect(data.maxCoolingMgd).toBeGreaterThan(0);
    expect(data.floors).toHaveLength(3);
    // The discharge finding still resolves from the curated fallback rows.
    expect(data.discharge.rows).toHaveLength(3);
  });
});

describe("the discharge finding — the river is already effluent ([verified])", () => {
  it("sums the WWTP discharges + natural low flows from the feed and derives the effluent share", async () => {
    const { buildDilution } = await loadDilution(makeBundle([BUILDOUT]));
    const { discharge } = buildDilution();
    expect(discharge.wwtpCfs).toBeCloseTo(8.82, 2); // 4.64 + 2.32 + 1.86
    expect(discharge.naturalCfs).toBeCloseTo(1.01, 2); // 0.2 + 0.03 + 0.78
    expect(discharge.campusFm2Cfs).toBe(3.87); // cited water-balance constant, not in the feed
    // (8.82 + 3.87) / (8.82 + 3.87 + 1.01) ≈ 93%
    expect(discharge.effluentPct).toBe(93);
    expect(discharge.rows).toHaveLength(3);
  });
});
