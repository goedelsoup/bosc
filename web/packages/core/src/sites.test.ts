import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { loadFeed, loadManifest } from "./bundle";
import type { DocumentCollectionItem } from "./feeds";
import { placementViolations } from "./placement";
import {
  ACTIVE_SITE_SLUG,
  activeSite,
  comingSoonSites,
  comingSoonStories,
  FACILITY_STAGES,
  facilityStageIndex,
  facilityStatus,
  groupSites,
  groupSitesIn,
  networkRollup,
  SITE_STATUS_META,
  SITES,
  siteBadge,
  siteForPath,
  siteForSlug,
  siteRollup,
  storyComingSoon,
  surfacedStories,
} from "./sites";

// `facilityStatus` is bundle-backed (#1628), so the facility-rail assertions below read the
// committed per-site bundles. Pin `WATERMARK_BUNDLE_DIR` at `web/sites` (absolute, CWD-independent)
// when it isn't already set by the mise task env — so this stays hermetic under a bare `vitest`
// (matching the readiness/directory tests' bundle dependency) instead of silently reading a stale
// local `data/site/bundles/` and drifting to "investigation".
process.env.WATERMARK_BUNDLE_DIR ??= resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../sites");

describe("sites registry — the Watermark network (#304)", () => {
  it("has unique slugs; the active build (Lima) is selectable; a selectable site is live or building", () => {
    const slugs = SITES.map((s) => s.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
    const selectable = SITES.filter((s) => s.selectable);
    expect(selectable.some((s) => s.slug === ACTIVE_SITE_SLUG)).toBe(true);
    // Lima moved to an early build state (#1256): still selectable, now `building` (not `live`).
    // A selectable site is either `live` or `building` — never `queued`/`tracking`.
    for (const s of selectable) expect(["live", "building"]).toContain(s.status);
    expect(activeSite().slug).toBe(ACTIVE_SITE_SLUG);
  });

  it("keeps Lima selectable in its early build state (#1256): status `building`", () => {
    const lima = SITES.find((s) => s.slug === ACTIVE_SITE_SLUG);
    expect(lima?.selectable).toBe(true);
    expect(lima?.status).toBe("building");
  });

  it("promotes Fort Wayne to selectable (live facility + story ready, #741)", () => {
    const ftw = SITES.find((s) => s.slug === "fort-wayne");
    expect(ftw).toBeDefined();
    expect(ftw?.selectable).toBe(true);
    expect(ftw?.status).toBe("live"); // facility is operational; Project Zodiac Phase 1 running
    expect(ftw?.codename).toBe("GCP");
  });

  it("promotes Troy-Piqua to selectable on Urbana parity, not on Lima-shape-matching (#1872)", () => {
    const trp = SITES.find((s) => s.slug === "troy-piqua");
    expect(trp?.selectable).toBe(true);
    expect(trp?.status).toBe("live");
    // The promotion rests on domain activation, not on a full taxonomy: troy-piqua carries the
    // SAME readiness shape as Urbana, which was promoted on it. `facility` and `story` are
    // deliberate resting states (no PTI exists; STORY_SLUGS registration is a later editorial
    // call) — if a regen ever drops one of the three `live` domains, the parity claim is gone
    // and this fails rather than leaving a hollow site in the switcher.
    const trpReadiness = loadManifest("troy-piqua").readiness;
    expect(trpReadiness).toEqual(loadManifest("urbana").readiness);
    expect(trpReadiness?.tier).toBe("case");
    expect(trpReadiness?.domains).toEqual({
      backdrop: "live",
      facility: "seeded",
      places: "live",
      record: "live",
      story: "seeded",
    });
  });

  it("routes every site under /network/<slug>; Lima uses its canonical watershed name", () => {
    for (const s of SITES) {
      if (s.slug === ACTIVE_SITE_SLUG) expect(s.href).toBe("/network/american-sugar-creek-allen-co");
      else expect(s.href).toBe(`/network/${s.slug}`);
    }
  });

  it("comingSoonSites() is every non-selectable site (not Lima, Urbana, Fort Wayne, or Troy-Piqua), each carrying a tracking issue", () => {
    const soon = comingSoonSites();
    expect(soon.some((s) => s.slug === ACTIVE_SITE_SLUG)).toBe(false);
    expect(soon.some((s) => s.slug === "fort-wayne")).toBe(false); // Fort Wayne is now selectable (#741)
    expect(soon.some((s) => s.slug === "troy-piqua")).toBe(false); // Troy-Piqua is now selectable (#1872)
    expect(soon.map((s) => s.slug)).toEqual([
      "defiance",
      "findlay",
      "toledo",
      "bowling-green",
      "van-wert",
      "bryan",
      "ottawa",
      "springfield",
      "xenia",
      "wpafb",
      "hamilton-middletown",
      "sidney",
      "greenville",
      "wilmington",
      "west-union",
      "new-albany",
      "columbus",
      "coshocton",
      "piketon",
      "sandusky",
      "mansfield",
      "portsmouth",
      "newark",
      "zanesville",
      "fremont",
      "tiffin",
      "bucyrus",
      "cleveland",
      "akron",
      "lordstown",
      "youngstown",
      "lancaster",
      "athens",
      "logan",
    ]);
    for (const s of soon) expect(s.issue).toBeTruthy();
  });

  it("badges a site by codename, falling back to its mono", () => {
    expect(siteBadge({ ...SITES[0] })).toBe("BOSC");
    const defiance = SITES.find((s) => s.slug === "defiance")!;
    expect(siteBadge(defiance)).toBe("DEF"); // no codename → mono
  });
});

describe("editorial story states — live vs coming-soon vs hidden (#1526/#1527)", () => {
  it("Lima's walk is readable (live), Fort Wayne's stays `comingSoon`, and no story anywhere `hidden`", () => {
    // The two in-line stories are Lima's project-bosc and Fort Wayne's project-zodiac. Lima's record
    // is finished, so its walk is readable; Fort Wayne's is still held behind the coming-soon teaser.
    const lima = siteForSlug("lima")?.stories ?? [];
    const ftw = siteForSlug("fort-wayne")?.stories ?? [];
    expect(lima.map((s) => s.codename)).toEqual(["project-bosc"]);
    expect(ftw.map((s) => s.codename)).toEqual(["project-zodiac"]);
    expect(lima.every((s) => !s.comingSoon)).toBe(true);
    expect(ftw.every((s) => s.comingSoon === true)).toBe(true);
    // The silent `hidden` state is unused today — every registered story is either live or coming-soon.
    expect(SITES.every((s) => (s.stories ?? []).every((r) => !r.hidden))).toBe(true);
  });

  it("surfacedStories returns Lima's, comingSoonStories returns Fort Wayne's — the states are distinguishable", () => {
    // Lima: readable — surfaced, and NOT coming-soon.
    expect(surfacedStories("lima").map((r) => r.codename)).toEqual(["project-bosc"]);
    expect(comingSoonStories("lima")).toHaveLength(0);
    expect(storyComingSoon("lima", "project-bosc")).toBe(false);

    // Fort Wayne: held — excluded from every readable surface, but advertised (teaser) + interstitial-gated.
    expect(surfacedStories("fort-wayne")).toHaveLength(0);
    expect(comingSoonStories("fort-wayne").map((r) => r.codename)).toEqual(["project-zodiac"]);
    expect(storyComingSoon("fort-wayne", "project-zodiac")).toBe(true);
    // title/dek stay on the ref so the teaser + interstitial can render them.
    expect(comingSoonStories("fort-wayne")[0]?.title.length).toBeGreaterThan(0);
    expect(comingSoonStories("fort-wayne")[0]?.dek.length).toBeGreaterThan(0);

    // A site with no registered story is neither surfaced nor coming-soon (nothing to advertise).
    expect(surfacedStories("urbana")).toHaveLength(0);
    expect(comingSoonStories("urbana")).toHaveLength(0);
    expect(storyComingSoon("urbana", "project-bosc")).toBe(false);
    expect(storyComingSoon("lima", "nope")).toBe(false);
  });
});

describe("site build phases — the four-phase clock (#308 dictate B)", () => {
  it("SITE_STATUS_META covers every status, including tracking", () => {
    for (const status of ["live", "building", "queued", "tracking"] as const) {
      expect(SITE_STATUS_META[status]?.label).toBeTruthy();
      expect(SITE_STATUS_META[status]?.cls).toMatch(/^is-/);
    }
  });
  it("tracking sites exist (issue-only candidates), all non-selectable with a tracking issue", () => {
    const tracked = SITES.filter((s) => s.status === "tracking");
    expect(tracked.length).toBeGreaterThanOrEqual(15);
    for (const s of tracked) {
      expect(s.selectable).toBe(false);
      expect(s.issue).toBeTruthy();
      expect(s.codename).toBeNull();
    }
  });
  it("the full network the selector depicts — 38 sites across 11 basins", () => {
    expect(SITES.length).toBe(38);
    expect(groupSites("basin").length).toBe(11);
  });
});

describe("promotion gate — the onboarding review invariant (#326)", () => {
  // `bosc onboard` proposes; promotion to a selectable build is a manual, parity-gated edit here.
  // These encode the gate: a `selectable` site is one under active build — `live` (parity-complete)
  // or `building` (an early build state, e.g. Lima post-#1256) — and only ever those. A `queued` or
  // `tracking` site can't slip selectable without the deliberate promotion.
  it("every selectable site is live or building", () => {
    for (const s of SITES) if (s.selectable) expect(["live", "building"]).toContain(s.status);
  });

  it("no queued/tracking site is selectable before explicit promotion", () => {
    for (const s of SITES) {
      if (s.status !== "live" && s.status !== "building") expect(s.selectable).toBe(false);
    }
  });
});

describe("grouped selector — State / Basin lenses (#307/#308)", () => {
  it("groups every site under both axes, no orphans", () => {
    for (const by of ["state", "basin"] as const) {
      const total = groupSites(by).reduce((n, g) => n + g.sites.length, 0);
      expect(total).toBe(SITES.length);
    }
  });

  // The named peer of the count check above (#1863). Both lenses read the registry's `state` /
  // `basin_major`, so a site can only fall out of one by being placed somewhere `./placement`
  // doesn't know — and this says which site and which value, where the count above says only
  // that the arithmetic stopped working.
  it("every registered site is placed in a known state and basin", () => {
    expect(placementViolations(SITES)).toEqual([]);
  });

  it("an unplaced site is a named throw, never a silently dropped row", () => {
    // What the old hand-maintained PLACEMENT table did instead: `continue`. A slug registered in
    // data/sites.yaml but absent there vanished from both lenses AND the water-lens scorecard,
    // and nothing named it. Registry placement is repo-authoring data — it fails the build.
    const stray = { ...SITES[0], slug: "kokosing-falls", basinMajor: "kokosing" };
    for (const by of ["state", "basin"] as const) {
      expect(() => groupSitesIn([...SITES, stray], by)).toThrow(/kokosing-falls/);
    }
    expect(() => groupSitesIn([{ ...SITES[0], state: "MI" }], "state")).toThrow(/UNKNOWN/);
  });
  it("by state: Indiana holds only Fort Wayne; Ohio carries the OH abbr tag", () => {
    const groups = groupSites("state");
    expect(groups.find((g) => g.label === "Indiana")?.sites.map((s) => s.slug)).toEqual(["fort-wayne"]);
    expect(groups.find((g) => g.label === "Ohio")?.tag).toBe("OH");
  });
  it("by basin: the eleven basins nested under four regions (design 'Site Selector')", () => {
    const groups = groupSites("basin");
    // Region order (maumee → the two miamis → southeastern → northeast), basins within each.
    expect(groups.map((g) => g.label)).toEqual([
      "Maumee",
      "Portage",
      "Great Miami",
      "Little Miami",
      "Scioto",
      "Muskingum",
      "Hocking",
      "Ohio Brush Creek",
      "Sandusky",
      "Cuyahoga",
      "Mahoning",
    ]);
    expect(groups.find((g) => g.label === "Maumee")?.tag).toBe("MAU");
    // the Portage basin (the Maumee-Portage divide node) carries Bowling Green
    expect(groups.find((g) => g.label === "Portage")?.sites.map((s) => s.slug)).toContain("bowling-green");
    // the lower/upper Great Miami siblings collapse into one basin group
    expect(groups.find((g) => g.label === "Great Miami")?.sites.map((s) => s.slug)).toContain("wpafb");
    expect(groups.find((g) => g.label === "Great Miami")?.sites.map((s) => s.slug)).toContain("troy-piqua");
  });
  it("by basin: a region header bar opens each region (showRegion on the first basin)", () => {
    const groups = groupSites("basin");
    const regionHeads = groups.filter((g) => g.showRegion);
    expect(regionHeads.map((g) => g.regionLabel)).toEqual([
      "Maumee Basin",
      "The Two Miamis",
      "Southeastern Basins",
      "Northeast Basins",
    ]);
    // The Two Miamis header opens on Great Miami and counts both its basins' sites.
    const miamis = groups.find((g) => g.region === "miamis" && g.showRegion);
    expect(miamis?.label).toBe("Great Miami");
    expect(miamis?.regionTag).toBe("2MI");
    const miamiSites = groups.filter((g) => g.region === "miamis").reduce((n, g) => n + g.sites.length, 0);
    expect(miamis?.regionCount).toBe(miamiSites);
    // The state lens carries no region fields.
    expect(groupSites("state").every((g) => g.region === undefined)).toBe(true);
  });
  it("the locked field is a capability — orthogonal to status, none set by default", () => {
    expect(SITES.every((s) => !s.locked)).toBe(true);
  });
});

describe("facility-status rail — the 4-stage facility clock (#401)", () => {
  it("orders the lifecycle investigation → confirmed → construction → live", () => {
    expect(FACILITY_STAGES.map((s) => s.status)).toEqual([
      "investigation",
      "confirmed",
      "construction",
      "live",
    ]);
  });

  it("places each known facility on the right step of the rail", () => {
    expect(facilityStageIndex(facilityStatus("lima"))).toBe(2); // under construction
    expect(facilityStageIndex(facilityStatus("fort-wayne"))).toBe(3); // live
    expect(facilityStatus("urbana")).toBe("confirmed"); // Urbana Technology Hub disclosed (#1327)
    expect(facilityStageIndex(facilityStatus("urbana"))).toBe(1);
    expect(facilityStatus("troy-piqua")).toBe("confirmed"); // Project Klondike disclosed (#1482)
    expect(facilityStageIndex(facilityStatus("troy-piqua"))).toBe(1);
    expect(facilityStatus("sidney")).toBe("construction"); // AWS "Project Galaxy" under construction (#1378)
    expect(facilityStageIndex(facilityStatus("sidney"))).toBe(2);
  });

  it("defaults an undisclosed facility to step 0 (investigation)", () => {
    expect(facilityStatus("toledo")).toBe("investigation");
    expect(facilityStageIndex(facilityStatus("toledo"))).toBe(0);
  });
});

describe("siteRollup / networkRollup — the directory's per-site record depth (#1861)", () => {
  // Reads the same committed bundles as the facility rail above. Assertions are pinned to
  // invariants and tier, not to exact volatile counts, so a re-export doesn't break the suite.

  it("counts DOCUMENTS as individual files, not the manifest's collection count", () => {
    // The semantic choice this issue had to make: a manifest `documents` feed `count` is the
    // number of *collections* (Lima: 21); the column says "Documents", so it sums their entries.
    const collections = loadManifest("lima").feeds.find((f) => f.name === "documents")?.count ?? 0;
    const files = siteRollup("lima").documents ?? 0;
    expect(collections).toBeGreaterThan(0);
    expect(files).toBeGreaterThan(collections);
    expect(files).toBe(
      loadFeed<DocumentCollectionItem[]>("documents", "lima").reduce((n, c) => n + c.entries.length, 0),
    );
  });

  it("rolls up a worked peer's own figures — the row that used to read '—/—' beside a facility pill", () => {
    const bg = siteRollup("bowling-green");
    expect(bg.tier).toBe("case");
    expect(bg.documents).toBeGreaterThan(0);
    expect(bg.records).toBeGreaterThan(0);
    // Lima is no longer the only site with numbers: every committed bundle reports its own.
    expect(siteRollup("lima").tier).toBe("reference");
  });

  it("reports nulls — not zeros — for a registered site with no committed bundle", () => {
    // Lordstown is in the registry (it carries a defense assessment) but has never been exported.
    expect(siteRollup("lordstown")).toEqual({ documents: null, records: null, tier: null });
  });

  it("sums the network over built sites only, holding the unbuilt out of every tier", () => {
    const net = networkRollup();
    const tiered = Object.values(net.byTier).reduce((a, b) => a + b, 0);
    // Every registered site is counted exactly once — either at a tier, or as unbuilt.
    expect(tiered + net.unbuilt).toBe(SITES.length);
    expect(net.unbuilt).toBeGreaterThan(0);
    expect(net.byTier.reference).toBe(1); // Lima alone
    // The sums are the per-site rollups, so the ledger and the scorecard can never disagree.
    const built = SITES.map((s) => siteRollup(s.slug)).filter((r) => r.tier !== null);
    expect(net.documents).toBe(built.reduce((n, r) => n + (r.documents ?? 0), 0));
    expect(net.records).toBe(built.reduce((n, r) => n + (r.records ?? 0), 0));
    expect(net.documents).toBeGreaterThan(siteRollup("lima").documents ?? 0); // peers contribute
  });
});

describe("siteForPath — the switcher's current-site resolution (#316)", () => {
  it("resolves the live Lima build for /network/american-sugar-creek-allen-co and any page beneath it", () => {
    for (const p of [
      "/network/american-sugar-creek-allen-co",
      "/network/american-sugar-creek-allen-co/",
      "/network/american-sugar-creek-allen-co/site/",
      "/network/american-sugar-creek-allen-co/environment/map",
      "/network/american-sugar-creek-allen-co/timeline",
    ]) {
      expect(siteForPath(p)?.slug).toBe("lima");
    }
  });

  it("resolves Urbana as a selectable site for /network/urbana and pages beneath it", () => {
    expect(siteForPath("/network/urbana")?.slug).toBe("urbana");
    expect(siteForPath("/network/urbana/")?.slug).toBe("urbana");
    expect(siteForPath("/network/urbana/site/")?.slug).toBe("urbana");
  });

  it("keeps coming-soon sites on the neutral network tier (only selectable sites resolve)", () => {
    // They live at /network/<slug> too, but aren't selectable → null (network chrome, not site).
    expect(siteForPath("/network/fort-wayne")?.slug).toBe("fort-wayne"); // now selectable (#741)
    expect(siteForPath("/network/defiance/")).toBeNull();
    expect(siteForPath("/network/toledo")).toBeNull();
  });

  it("returns null for the directory root and the cross-cutting globals (neutral state)", () => {
    for (const p of [
      "/",
      "/about",
      "/about-me",
      "/wiki/entities/",
      "/ask",
      "/research/hypotheses",
      "/basin",
    ]) {
      expect(siteForPath(p)).toBeNull();
    }
  });

  it("does not mistake an unknown /network/<slug> for a real site", () => {
    expect(siteForPath("/network/cincinnati")).toBeNull();
  });

  it("strips a non-root Astro base before matching", () => {
    expect(siteForPath("/app/network/american-sugar-creek-allen-co/site/", "/app")?.slug).toBe("lima");
    expect(siteForPath("/app/network/findlay", "/app")).toBeNull(); // coming-soon → neutral, even with a base
    expect(siteForPath("/network/american-sugar-creek-allen-co/site/", "/")?.slug).toBe("lima"); // base "/" is a no-op
  });
});
