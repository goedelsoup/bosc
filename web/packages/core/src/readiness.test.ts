import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import { LENS_ORDER, type LensId } from "./lenses";
import {
  availableFacetPaths,
  domainPresent,
  facetAvailable,
  facilityLoadAvailable,
  facilityState,
  isAvailable,
  isReferenceSite,
  lensAvailable,
  lensStatus,
  lockedSections,
  openSectionPaths,
  RECORD_FACETS,
  type RecordFacet,
  SECTION_META,
  type ReadinessSection,
  sectionStatus,
  siteDomainStates,
  siteReadiness,
  siteRouteOffered,
  siteTier,
} from "./readiness";
import { selectableSitePaths } from "./sites";

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

  it("locks the legal record it does not own (#1886)", () => {
    // `record` is LIVE here — FW has its own extractions — so the domain alone was never going to
    // catch this. The section additionally asks whether any published filing came out of THIS
    // site's corpus; none did, so an Indiana watershed point stops serving an Ohio hearing.
    expect(domainPresent("fort-wayne", "record")).toBe(true);
    expect(sectionStatus("fort-wayne", "legal")).toBe("locked");
  });

  it("reports the full locked set, and never asks a peer for a walk", () => {
    // `legal` joined the set at #1886: it is a real gap on a peer, and the needs board asks for it.
    // `story` is DELIBERATELY absent (#1971). Its section still locks — `sectionStatus` says so
    // below — but a guided walk stopped being something a site owes the network when epic #1968
    // retired the per-site walk, so it must never surface as a need. This is the assertion that
    // catches that expectation creeping back in through the needs UI.
    expect(lockedSections("fort-wayne").sort()).toEqual(
      ["contacts", "exhibits", "leads", "legal", "people", "reports", "timeline"].sort(),
    );
    expect(sectionStatus("fort-wayne", "story")).toBe("locked");
    expect(lockedSections("fort-wayne")).not.toContain("story");
  });
});

// --- the domain-activation block (#1220 / #1223) ----------------------------------------
describe("domain activation (manifest readiness block)", () => {
  it("reads the tier straight from each site's manifest", () => {
    // The Python tier (bosc.site.readiness.site_tier) written at export — the frontend is a reader.
    expect(siteTier("lima")).toBe("reference");
    // Fort Wayne rose `case` -> `reference` in #1971 without gaining a source: all four
    // record-bearing domains were already live, and the only thing holding it was the retired
    // `story` domain, which #1457 proposed clearing by committing a leads YAML.
    expect(siteTier("fort-wayne")).toBe("reference");
    // Urbana is a Case site after the Highland55 land-assembly sourcing (#1328): the floor plus a
    // committed parcel footprint (`places` live) was already enough, and the tier is unmoved by
    // `record` going seeded (#1642) and then live on its published extractions (#1724) — one
    // above-floor domain is the bar, and Urbana has had one throughout.
    expect(siteTier("urbana")).toBe("case");
  });

  it("exposes the five domain states from the manifest", () => {
    const lima = siteDomainStates("lima");
    for (const d of ["backdrop", "facility", "places", "record", "inquiry"] as const) {
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

// --- the lens band (#1913, epic #1911) ----------------------------------------------------
// `lensStatus` composes the two gates above; the model it reads is pure and lives in
// `lenses.ts` (tested there, offline). What matters here is that the composition is driven by
// each site's OWN manifest block — never by a reference-site shortcut.
describe("lensStatus (#1913)", () => {
  // This block re-imports the module under a synthetic bundle dir for its last case, so it
  // restores the suite's dir the same way the two blocks below do (captured at collection time,
  // before any test has run).
  const originalBundleDir = process.env.WATERMARK_BUNDLE_DIR;
  afterEach(() => {
    if (originalBundleDir === undefined) delete process.env.WATERMARK_BUNDLE_DIR;
    else process.env.WATERMARK_BUNDLE_DIR = originalBundleDir;
    vi.resetModules();
  });

  const statuses = (slug: string): Record<LensId, string> =>
    Object.fromEntries(LENS_ORDER.map((id) => [id, lensStatus(slug, id)])) as Record<LensId, string>;

  it("opens all five on the reference build", () => {
    for (const id of LENS_ORDER) expect(lensStatus("lima", id), id).toBe("available");
  });

  it("opens all five on a reference-TIER peer that is not the reference SITE", () => {
    // The acceptance's real check. Findlay's manifest reports every domain live, so its five
    // lenses open exactly as Lima's do — and `isReferenceSite` is false for it. If the gate had
    // a reference-site backdoor, this site would be the one it failed on.
    expect(isReferenceSite("findlay")).toBe(false);
    expect(siteTier("findlay")).toBe("reference");
    for (const id of LENS_ORDER) expect(lensStatus("findlay", id), id).toBe("available");
    expect(statuses("findlay")).toEqual(statuses("lima"));
  });

  it("locks all five on a stub-tier peer", () => {
    // Coshocton: registered, committed bundle, every domain absent. Nothing is scaffolded for it.
    expect(siteTier("coshocton")).toBe("stub");
    for (const id of LENS_ORDER) expect(lensStatus("coshocton", id), id).toBe("locked");
  });

  it("opens the lenses a partial peer has the domains for, and only those", () => {
    // Mansfield is the clean mid-tier read: places live (a committed footprint) and the backdrop
    // floor pulled, but no record and no disclosed facility. So Land opens off `places`, the two
    // floor lenses open off the backdrop — and Power and Disclosure lock, each on its own domain.
    expect(statuses("mansfield")).toEqual({
      land: "available",
      power: "locked",
      environment: "available",
      economy: "available",
      disclosure: "locked",
    });
    // Power's lock here is the FACILITY half, not the section half: the economy section is open.
    expect(sectionStatus("mansfield", "economy")).toBe("available");
    expect(domainPresent("mansfield", "facility")).toBe(false);
  });

  it("opens Power on a screening-only facility — the lens gates on presence, not depth", () => {
    // Urbana's facility is `seeded` (a floor-area [inference] load, MW still [open]). That is
    // enough for "whose grid carries it" to be a question worth asking; whether the LOAD READ may
    // render as grounded output stays the narrower `facilityLoadAvailable` gate (#1630), which the
    // lens deliberately does not duplicate.
    expect(facilityState("urbana")).toBe("seeded");
    expect(lensAvailable("urbana", "power")).toBe(true);
    expect(facilityLoadAvailable("urbana")).toBe(false);
  });

  it("inherits the environment section's cooling lock rather than routing around it (#1057)", async () => {
    // A lens is a view over a gate, so it can never be more open than the gate. An undisclosed
    // cooling method locks the environment section; the Environment lens must lock with it.
    const root = makePeerBundle("cooling-peer", [scenarioRow("unknown", false)]);
    const r = await loadReadiness(root);
    expect(r.sectionStatus("cooling-peer", "environment")).toBe("locked");
    expect(r.lensStatus("cooling-peer", "environment")).toBe("locked");
    // The floor is otherwise live, so Economy — same domain, different section — stays open.
    expect(r.lensStatus("cooling-peer", "economy")).toBe("available");
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
  inquiry: "absent",
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
      contract_version: "2.0.0",
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
      domains: {
        backdrop: "live",
        facility: "absent",
        places: "absent",
        record: "absent",
        inquiry: "absent",
      },
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
        contract_version: "2.0.0",
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

// --- the route half of the gate (#1894, epic #1884 phase 10) ------------------
//
// #1908 made `facetOffered` one gate with three consumers — the landing that draws the door, the
// route that emits the leaf, the walk that indexes it — and deliberately stopped short of the
// record facets and the reports section, whose pages kept building everywhere and rendering a lock.
// Measured against `dist/`, those locks were linked from no door and named by no search row: 17
// unreachable pages. These are the two gates that closed that, plus the link-side predicate that
// keeps a hand-written cross-link from outliving the page it points at.

describe("availableFacetPaths (#1894)", () => {
  it("emits a facet's route only where the facet actually opens", () => {
    for (const facet of Object.keys(RECORD_FACETS) as RecordFacet[]) {
      const emitted = availableFacetPaths(facet).map((p) => p.props.slug);
      const open = selectableSitePaths()
        .map((p) => p.props.slug)
        .filter((slug) => facetAvailable(slug, facet));
      expect(emitted, `${facet}: route set disagrees with the door's gate`).toEqual(open);
    }
  });

  it("still emits the reference build, which opens every facet", () => {
    for (const facet of Object.keys(RECORD_FACETS) as RecordFacet[]) {
      expect(
        availableFacetPaths(facet).map((p) => p.props.slug),
        facet,
      ).toContain("lima");
    }
  });

  it("withholds at least one facet from at least one peer — otherwise this asserts nothing", () => {
    // Fort Wayne carries the Zodiac campus and no timeline / people / exhibits. If the fixtures ever
    // fill in so completely that no facet is withheld anywhere, the assertions above go vacuous and
    // this is the line that says so.
    const withheld = (Object.keys(RECORD_FACETS) as RecordFacet[]).filter(
      (f) => availableFacetPaths(f).length < selectableSitePaths().length,
    );
    expect(withheld.length).toBeGreaterThan(0);
  });
});

describe("openSectionPaths (#1894)", () => {
  it("emits a section's interior pages at exactly the sites where the section is open", () => {
    // Set EQUALITY, not "every emitted one is open". The one-directional form passes on a
    // regression that drops an open site — which is the failure that loses seven real report pages
    // rather than seven copies of a lock.
    const emitted = openSectionPaths("reports").map((p) => p.props.slug);
    const open = selectableSitePaths()
      .map((p) => p.props.slug)
      .filter((slug) => isAvailable(slug, "reports"));
    expect(emitted).toEqual(open);
    expect(emitted).toContain("lima");
  });

  it("locks the reports section on a peer — the seven companions used to render one lock each", () => {
    const locked = selectableSitePaths()
      .map((p) => p.props.slug)
      .filter((slug) => !isAvailable(slug, "reports"));
    expect(locked.length, "no peer locks reports — this asserts nothing").toBeGreaterThan(0);
    const emitted = new Set(openSectionPaths("reports").map((p) => p.props.slug));
    for (const slug of locked) expect(emitted.has(slug), slug).toBe(false);
  });
});

describe("siteRouteOffered (#1894)", () => {
  it("answers for a report companion the way the section gate does", () => {
    for (const { props } of selectableSitePaths()) {
      expect(siteRouteOffered(props.slug, "/reports/the-load-and-the-grid"), props.slug).toBe(
        isAvailable(props.slug, "reports"),
      );
    }
  });

  it("answers for a record facet the way the facet gate does, trailing slash or not", () => {
    for (const { props } of selectableSitePaths()) {
      const want = facetAvailable(props.slug, "people");
      expect(siteRouteOffered(props.slug, "/site/people/"), props.slug).toBe(want);
      expect(siteRouteOffered(props.slug, "/site/people"), props.slug).toBe(want);
    }
  });

  it("defaults open for a route no gate claims", () => {
    // A study reference may point at `/methodology`; a caller must be able to ask about any path
    // without special-casing. This is the ONE place that defaults open.
    expect(siteRouteOffered("fort-wayne", "/methodology")).toBe(true);
    expect(siteRouteOffered("fort-wayne", "/site/")).toBe(true);
  });

  it("ignores a fragment or query on the way in", () => {
    // Asserted on a CLOSED route, which is the only place it can fail. On Lima both are open, so
    // dropping the strip would leave the path unmatched by every gate, fall through to the
    // defaults-open branch, and still answer `true` — a test that cannot go red.
    const shut = selectableSitePaths()
      .map((p) => p.props.slug)
      .find((slug) => !isAvailable(slug, "reports") && !facetAvailable(slug, "people"));
    expect(shut, "no site locks both reports and people — this asserts nothing").toBeDefined();
    expect(siteRouteOffered(shut as string, "/reports/the-load-and-the-grid#chain")).toBe(false);
    expect(siteRouteOffered(shut as string, "/site/people/?q=x")).toBe(false);
    // …and the open answers still come back open, so the strip isn't over-matching.
    expect(siteRouteOffered("lima", "/reports/the-load-and-the-grid#chain")).toBe(true);
    expect(siteRouteOffered("lima", "/site/people/?q=x")).toBe(true);
  });
});
