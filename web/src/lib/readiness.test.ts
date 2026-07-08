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
  siteDomainStates,
  siteReadiness,
  siteTier,
} from "./readiness";

// Pinned against the committed full-vs-partial fixture pair: `sites/lima` (the live
// reference build, every feed) vs `sites/fort-wayne` (a real partial peer — the Project
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
  it("has every section available — it surfaces its story and hosts the network-global content", () => {
    // Lima surfaces its Project BOSC walk (its overlay entry is not `hidden`), so the `story` section
    // is available like every other section — the reference build hosts all the network-global content.
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
    expect(isAvailable("fort-wayne", "environment")).toBe(true);
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
      ["contacts", "exhibits", "leads", "people", "reports", "timeline"].sort(),
    );
  });
});

// --- the domain-activation block (#1220 / #1223) ----------------------------------------
describe("domain activation (manifest readiness block)", () => {
  it("reads the tier straight from each site's manifest", () => {
    // The Python tier (bosc.site.readiness.site_tier) written at export — the frontend is a reader.
    expect(siteTier("lima")).toBe("reference");
    expect(siteTier("fort-wayne")).toBe("case");
    // Urbana is a floor + leads-board site (no structured corpus, no parcels) → Backdrop tier.
    expect(siteTier("urbana")).toBe("backdrop");
  });

  it("exposes the five domain states from the manifest", () => {
    const lima = siteDomainStates("lima");
    for (const d of ["backdrop", "facility", "places", "record", "story"] as const) {
      expect(lima[d]).toBe("live"); // Lima: every domain lit
    }
    const urbana = siteDomainStates("urbana");
    expect(urbana.backdrop).toBe("live"); // the floor is real
    expect(urbana.record).toBe("absent"); // markdown findings only, no structured corpus
    expect(urbana.places).toBe("absent"); // no committed parcels — the section locks
    expect(urbana.facility).toBe("absent");
  });

  it("opens Urbana's own leads board (feed-driven, #796) without borrowing Lima's", () => {
    // Urbana carries a `leads` feed but no registered story — leads open, the guided walk stays shut.
    expect(sectionStatus("urbana", "leads")).toBe("available");
    expect(sectionStatus("urbana", "story")).toBe("locked");
    // Its floor stands up (environment/economy), but its record domain is absent → record locks.
    expect(sectionStatus("urbana", "economy")).toBe("available");
    expect(sectionStatus("urbana", "record")).toBe("locked");
    expect(sectionStatus("urbana", "places")).toBe("locked");
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
// scenario (`cooling_model: "unknown"`) — the environment section must lock rather than render
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

const LIVE = {
  backdrop: "live",
  facility: "seeded",
  places: "absent",
  record: "absent",
  story: "absent",
} as const;

/** A minimal per-site bundle: a `hydrology-scenarios` feed + a `readiness` block (backdrop live by
 *  default, so the environment section opens unless a cooling lock or an explicit block says otherwise). */
function makePeerBundle(
  slug: string,
  scenarios: object[],
  readiness: object = { tier: "backdrop", domains: LIVE },
): string {
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
      contract_version: "1.17.0",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: scenarios.length,
      readiness,
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
  // resolving sites/ regardless of hook ordering.
  const originalBundleDir = process.env.WATERMARK_BUNDLE_DIR;
  afterEach(() => {
    if (originalBundleDir === undefined) delete process.env.WATERMARK_BUNDLE_DIR;
    else process.env.WATERMARK_BUNDLE_DIR = originalBundleDir;
    vi.resetModules();
  });
  afterAll(() => {
    for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
  });
  it("locks the environment section when a scenario's cooling model is unknown", async () => {
    const root = makePeerBundle("peer", [scenarioRow("unknown", false)]);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(true);
    // The scenario feed has rows, but the undisclosed method overrides the count check.
    expect(r.sectionStatus("peer", "environment")).toBe("locked");
    expect(r.lockedSections("peer")).toContain("environment");
  });

  it("keeps the environment available for a disclosed cooling model", async () => {
    const root = makePeerBundle("peer", [scenarioRow("evaporative_tower", true)]);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(false);
    expect(r.sectionStatus("peer", "environment")).toBe("available");
  });

  it("is false when the site has no scenario feed at all", async () => {
    const root = makePeerBundle("peer", []);
    const r = await loadReadiness(root);
    expect(r.coolingMethodUndisclosed("peer")).toBe(false);
  });
});

// --- a Backdrop-tier peer renders a real page, not a wall of locks (#1220 acceptance) -----
describe("a Backdrop-staged peer (floor data only)", () => {
  const originalBundleDir = process.env.WATERMARK_BUNDLE_DIR;
  afterEach(() => {
    if (originalBundleDir === undefined) delete process.env.WATERMARK_BUNDLE_DIR;
    else process.env.WATERMARK_BUNDLE_DIR = originalBundleDir;
    vi.resetModules();
  });
  afterAll(() => {
    for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
  });

  it("opens environment + economy off the backdrop domain, locks the above-floor domains", async () => {
    const backdropOnly = {
      tier: "backdrop",
      domains: { backdrop: "live", facility: "absent", places: "absent", record: "absent", story: "absent" },
    };
    const root = makePeerBundle("backdrop-peer", [], backdropOnly);
    const r = await loadReadiness(root);
    expect(r.siteTier("backdrop-peer")).toBe("backdrop");
    // The floor reads stand on their own — no fabricated corpus needed.
    expect(r.sectionStatus("backdrop-peer", "environment")).toBe("available");
    expect(r.sectionStatus("backdrop-peer", "economy")).toBe("available");
    // Above the floor: nothing on the record yet → locked, not scaffolded.
    for (const s of ["record", "places", "story", "leads", "reports"] as const) {
      expect(r.sectionStatus("backdrop-peer", s)).toBe("locked");
    }
  });

  it("degrades to all-locked when the bundle predates the readiness block", async () => {
    // No readiness field in the manifest → the safe all-absent fallback, nothing crashes.
    const root = mkdtempSync(join(tmpdir(), "bosc-readiness-"));
    tmpDirs.push(root);
    const dir = join(root, "legacy");
    mkdirSync(dir, { recursive: true });
    writeFileSync(
      join(dir, "manifest.json"),
      JSON.stringify({
        site: "legacy",
        bundle_version: "test",
        contract_version: "1.16.0",
        generated_at: "2026-01-01T00:00:00Z",
        feed_count: 0,
        row_total: 0,
        feeds: [],
      }),
    );
    const r = await loadReadiness(root);
    expect(r.siteTier("legacy")).toBe("stub");
    expect(r.sectionStatus("legacy", "environment")).toBe("locked");
  });
});
