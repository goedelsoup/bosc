import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import {
  isAvailable,
  isReferenceSite,
  lockedSections,
  SECTION_META,
  type ReadinessSection,
  sectionStatus,
  siteReadiness,
} from "./readiness";

// Pinned against the committed full-vs-partial fixture pair: `sample-bundle/lima` (the live
// reference build, every feed) vs `sample-bundle/fort-wayne` (a real partial peer — the Project
// Zodiac campus + rsei/econ/network, but no timeline / people / exhibits). The readiness model is
// what keeps a thin peer navigable without ever borrowing Lima's record.

describe("isReferenceSite", () => {
  it("is the live reference build alone", () => {
    expect(isReferenceSite("lima")).toBe(true);
    expect(isReferenceSite("fort-wayne")).toBe(false);
    expect(isReferenceSite("urbana")).toBe(false);
  });
});

describe("the reference build", () => {
  it("has every section available regardless of counts — it hosts the network-global content", () => {
    const readiness = siteReadiness("lima");
    for (const section of Object.keys(SECTION_META) as ReadinessSection[]) {
      expect(readiness[section]).toBe("available");
    }
    expect(lockedSections("lima")).toEqual([]);
  });
});

describe("a partial peer (Fort Wayne)", () => {
  it("opens the sections it has real data for", () => {
    // records / places / geo+rsei / econ+network are all present in the FW bundle.
    expect(isAvailable("fort-wayne", "record")).toBe(true);
    expect(isAvailable("fort-wayne", "places")).toBe(true);
    expect(isAvailable("fort-wayne", "watershed")).toBe(true);
    expect(isAvailable("fort-wayne", "economy")).toBe(true);
  });

  it("locks the sections whose feeds are empty — not fabricated from Lima", () => {
    // timeline:0 / people:0 / exhibits:0 in the FW bundle.
    expect(sectionStatus("fort-wayne", "timeline")).toBe("locked");
    expect(sectionStatus("fort-wayne", "people")).toBe("locked");
    expect(sectionStatus("fort-wayne", "exhibits")).toBe("locked");
  });

  it("opens the story when one is registered, even on a thin peer", () => {
    // FW carries the Project Zodiac StoryRef in the registry — the on-ramp works day one.
    expect(sectionStatus("fort-wayne", "story")).toBe("available");
  });

  it("locks the network-global sections (reports/leads) for any peer", () => {
    // reports + leads read the Lima-global narrative/audit — reference-only until a per-site feed.
    expect(sectionStatus("fort-wayne", "reports")).toBe("locked");
    expect(sectionStatus("fort-wayne", "leads")).toBe("locked");
  });

  it("reports the full locked set", () => {
    expect(lockedSections("fort-wayne").sort()).toEqual(
      ["exhibits", "leads", "people", "reports", "timeline"].sort(),
    );
  });
});

describe("SECTION_META", () => {
  it("carries a label + a 'what lands here' line for every gateable section", () => {
    for (const meta of Object.values(SECTION_META)) {
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.holds.length).toBeGreaterThan(0);
    }
  });
});

// --- the cooling-method honesty lock (#1057) --------------------------------------------
// A peer whose facility is on the record but whose cooling method is NOT gets a bracketed
// scenario (`cooling_model: "unknown"`) — the watershed section must lock rather than render
// the range as a single headline. Content-based, so it needs a synthetic bundle (the same
// tmp-dir harness as dilution.test.ts / bundle.test.ts).
const tmpDirs: string[] = [];

function pv(value: number) {
  return { value, unit: "MGD", source: "derived", citation: "t", confidence: "low", asof: null };
}

function scenarioRow(coolingModel: string, methodDisclosed: boolean) {
  return {
    scenario: {
      name: "buildout",
      cooling_model: coolingModel,
      cooling_demand: pv(3.9),
      consumptive_fraction: pv(0.8),
      basis: { method_disclosed: methodDisclosed, is_bracketed: !methodDisclosed },
    },
    cooling_model: coolingModel,
    consumptive_loss: pv(4.8),
    balance: { nodes: [], tier: "tier0", warnings: [] },
    assimilative: [],
  };
}

/** A minimal per-site bundle whose only feed is hydrology-scenarios. */
function makePeerBundle(slug: string, scenarios: object[]): string {
  const root = mkdtempSync(join(tmpdir(), "bosc-readiness-"));
  tmpDirs.push(root);
  const dir = join(root, slug);
  mkdirSync(dir, { recursive: true });
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
      site: slug,
      bundle_version: "test",
      contract_version: "1.9.0",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: scenarios.length,
      feeds,
    }),
  );
  writeFileSync(join(dir, "hydrology-scenarios.json"), JSON.stringify(scenarios));
  return root;
}

async function loadReadiness(root: string): Promise<typeof import("./readiness")> {
  process.env.WATERMARK_BUNDLE_DIR = root;
  vi.resetModules();
  return import("./readiness");
}

describe("coolingMethodUndisclosed (#1057)", () => {
  // Restore (not delete) the suite's bundle dir so the fixture-pinned tests above keep
  // resolving sample-bundle/ regardless of hook ordering.
  const originalBundleDir = process.env.WATERMARK_BUNDLE_DIR;
  afterEach(() => {
    if (originalBundleDir === undefined) delete process.env.WATERMARK_BUNDLE_DIR;
    else process.env.WATERMARK_BUNDLE_DIR = originalBundleDir;
    vi.resetModules();
  });
  afterAll(() => {
    for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
  });
  it("locks the watershed section when a scenario's cooling model is unknown", async () => {
    const root = makePeerBundle("peer", [scenarioRow("unknown", false)]);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(true);
    // The scenario feed has rows, but the undisclosed method overrides the count check.
    expect(r.sectionStatus("peer", "watershed")).toBe("locked");
    expect(r.lockedSections("peer")).toContain("watershed");
  });

  it("keeps the watershed available for a disclosed cooling model", async () => {
    const root = makePeerBundle("peer", [scenarioRow("evaporative_tower", true)]);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(false);
    expect(r.sectionStatus("peer", "watershed")).toBe("available");
  });

  it("is false when the site has no scenario feed at all", async () => {
    const root = makePeerBundle("peer", []);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(false);
  });
});
