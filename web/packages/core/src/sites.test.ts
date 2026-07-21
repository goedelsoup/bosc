import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  ACTIVE_SITE_SLUG,
  activeSite,
  comingSoonSites,
  comingSoonStories,
  FACILITY_STAGES,
  facilityStageIndex,
  facilityStatus,
  groupSites,
  SITE_STATUS_META,
  SITES,
  siteBadge,
  siteForPath,
  siteForSlug,
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

  it("routes every site under /network/<slug>; Lima uses its canonical watershed name", () => {
    for (const s of SITES) {
      if (s.slug === ACTIVE_SITE_SLUG) expect(s.href).toBe("/network/american-sugar-creek-allen-co");
      else expect(s.href).toBe(`/network/${s.slug}`);
    }
  });

  it("comingSoonSites() is every non-selectable site (not Lima, Urbana, or Fort Wayne), each carrying a tracking issue", () => {
    const soon = comingSoonSites();
    expect(soon.some((s) => s.slug === ACTIVE_SITE_SLUG)).toBe(false);
    expect(soon.some((s) => s.slug === "fort-wayne")).toBe(false); // Fort Wayne is now selectable (#741)
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
      "troy-piqua",
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
  it("marks both editorial walks `comingSoon`, and no story anywhere `hidden`", () => {
    // The two in-line stories are Lima's project-bosc and Fort Wayne's project-zodiac; both are held.
    const lima = siteForSlug("lima")?.stories ?? [];
    const ftw = siteForSlug("fort-wayne")?.stories ?? [];
    expect(lima.map((s) => s.codename)).toEqual(["project-bosc"]);
    expect(ftw.map((s) => s.codename)).toEqual(["project-zodiac"]);
    expect(lima.every((s) => s.comingSoon === true)).toBe(true);
    expect(ftw.every((s) => s.comingSoon === true)).toBe(true);
    // The silent `hidden` state is unused today — every registered story is either live or coming-soon.
    expect(SITES.every((s) => (s.stories ?? []).every((r) => !r.hidden))).toBe(true);
  });

  it("surfacedStories returns neither, comingSoonStories returns both — the states are distinguishable", () => {
    for (const [slug, codename] of [
      ["lima", "project-bosc"],
      ["fort-wayne", "project-zodiac"],
    ] as const) {
      // Held: excluded from every readable surface, but advertised (teaser) + interstitial-gated.
      expect(surfacedStories(slug)).toHaveLength(0);
      expect(comingSoonStories(slug).map((r) => r.codename)).toEqual([codename]);
      expect(storyComingSoon(slug, codename)).toBe(true);
      // title/dek stay on the ref so the teaser + interstitial can render them.
      expect(comingSoonStories(slug)[0]?.title.length).toBeGreaterThan(0);
      expect(comingSoonStories(slug)[0]?.dek.length).toBeGreaterThan(0);
    }
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
