import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import {
  domainPresent,
  facilityLoadAvailable,
  facilityState,
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
  it("has every section available, including its now-readable story", () => {
    // Lima hosts all the network-global content, so every section opens — including `story`: its
    // Project BOSC walk is readable now (its record is finished), so the facet unlocks and the story
    // door renders instead of a coming-soon teaser.
    const readiness = siteReadiness("lima");
    for (const section of Object.keys(SECTION_META) as ReadinessSection[]) {
      expect(readiness[section]).toBe("available");
    }
    expect(readiness.story).toBe("available");
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

  it("holds its story as coming-soon (locked facet) even though one is registered", () => {
    // FW carries the Project Zodiac StoryRef, but it's `comingSoon` (#1526) — so the story facet
    // locks: a visible teaser + interstitial stands in for the readable walk, not an open on-ramp.
    expect(sectionStatus("fort-wayne", "story")).toBe("locked");
  });

  it("locks the network-global sections (reports/leads) for any peer", () => {
    // reports + leads read the Lima-global narrative/audit — reference-only until a per-site feed.
    expect(sectionStatus("fort-wayne", "reports")).toBe("locked");
    expect(sectionStatus("fort-wayne", "leads")).toBe("locked");
  });

  it("reports the full locked set", () => {
    // `story` is locked too now — its walk is held coming-soon (#1526), not open.
    expect(lockedSections("fort-wayne").sort()).toEqual(
      ["contacts", "exhibits", "leads", "people", "reports", "story", "timeline"].sort(),
    );
  });
});

// --- the domain-activation block (#1220 / #1223) ----------------------------------------
describe("domain activation (manifest readiness block)", () => {
  it("reads the tier straight from each site's manifest", () => {
    // The Python tier (bosc.site.readiness.site_tier) written at export — the frontend is a reader.
    expect(siteTier("lima")).toBe("reference");
    expect(siteTier("fort-wayne")).toBe("case");
    // Urbana is a Case site after the Highland55 land-assembly sourcing (#1328): the floor plus a
    // committed parcel footprint (`places` live) was already enough, and the tier is unmoved by
    // `record` going seeded (#1642) and then live on its published extractions (#1724) — one
    // above-floor domain is the bar, and Urbana has had one throughout.
    expect(siteTier("urbana")).toBe("case");
  });

  it("exposes the five domain states from the manifest", () => {
    const lima = siteDomainStates("lima");
    for (const d of ["backdrop", "facility", "places", "record", "story"] as const) {
      expect(lima[d]).toBe("live"); // Lima: every domain lit
    }
    const urbana = siteDomainStates("urbana");
    expect(urbana.backdrop).toBe("live"); // the floor is real
    // `live`, but only since the feed caught up with the corpus (#1724). Two corrections in
    // sequence, in opposite directions: the committed manifest used to assert `record: live` over
    // a zero-length `records` feed and was re-derived to `seeded` for the grid feed (#1642); then
    // the site-tier classifier gained the two genres Urbana's corpus actually carries — its
    // structured read of the Thor v. Urbana complaint (`litigation`) and its recorded conveyance
    // chain (`land-assembly`) — which clears `RECORD_LIVE_THRESHOLD` on real extractions rather
    // than on a stale claim. The manifest is a reader of the feed at every step.
    expect(urbana.record).toBe("live");
    expect(urbana.places).toBe("live"); // committed parcel footprint (parcel-assemblage.geojson)
    // The Urbana Technology Hub facility is SCREENING-only (floor-area [inference] load, MW [open]) →
    // `seeded`, distinguished from a permit-grounded facility, not floated to `live` (#1630).
    expect(urbana.facility).toBe("seeded");
  });

  it("opens Urbana's own leads board (feed-driven, #796) without borrowing Lima's", () => {
    // Urbana carries a `leads` feed but no registered story — leads open, the guided walk stays shut.
    expect(sectionStatus("urbana", "leads")).toBe("available");
    expect(sectionStatus("urbana", "story")).toBe("locked");
    // Floor + its now-live record/places domains open (#1328): the Highland55 land-assembly record.
    expect(sectionStatus("urbana", "economy")).toBe("available");
    expect(sectionStatus("urbana", "record")).toBe("available");
    expect(sectionStatus("urbana", "places")).toBe("available");
  });
});

// --- facility-domain gating (#1630) -------------------------------------------------------
describe("facility-domain gating", () => {
  it("gates the campus-load read on the facility domain being live, not merely present", () => {
    // Lima's facility is permit-grounded (instrument depth) → live → its load read renders.
    expect(facilityState("lima")).toBe("live");
    expect(facilityLoadAvailable("lima")).toBe(true);
    // Urbana's facility is disclosed but SCREENING-only → seeded: the domain is PRESENT, but the
    // load read is withheld — the #1630 distinction the old `live`-collapse erased.
    expect(facilityState("urbana")).toBe("seeded");
    expect(domainPresent("urbana", "facility")).toBe(true); // present…
    expect(facilityLoadAvailable("urbana")).toBe(false); //   …but not grounded → gate closed
    // A live → seeded regression visibly flips the gate (the acceptance's observability check).
    expect(facilityLoadAvailable("lima")).not.toBe(facilityLoadAvailable("urbana"));
  });

  it("is closed for a facility-less site (no campus load to read)", () => {
    // xenia carries no SiteFacility → facility absent → the load read is off, not fabricated.
    expect(facilityState("xenia")).toBe("absent");
    expect(domainPresent("xenia", "facility")).toBe(false);
    expect(facilityLoadAvailable("xenia")).toBe(false);
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
