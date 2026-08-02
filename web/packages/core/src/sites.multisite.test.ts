import { describe, expect, it } from "vitest";
import { comingSoonSiteTabs } from "./nav";
import { siteBase } from "./routes";
import {
  type NetworkSite,
  SITES,
  comingSoonFrom,
  currentSiteForPath,
  selectablePathsFrom,
  siteForPathIn,
} from "./sites";
import { storyFor } from "./walk";

// Multi-site chrome parity (#746, closing #740's Done-when). As of #1872, the live registry
// has four selectable sites: Lima, Urbana, Fort Wayne, and Troy-Piqua. These tests lock the
// per-site routing logic by exercising the `*From(sites)` seam with both the real registry and a
// fixture that promotes an additional non-selectable site (Defiance), so the "promotion flips the
// tier" invariant stays tested even after each real promotion.

/** A fixture with Defiance promoted to selectable — used to exercise the promotion flip. */
const WITH_DEFIANCE: NetworkSite[] = SITES.map((s) =>
  s.slug === "defiance" ? { ...s, selectable: true, status: "live" } : s,
);

describe("multi-site chrome parity (#746)", () => {
  const real = selectablePathsFrom(SITES); // Lima + Urbana + Fort Wayne + Troy-Piqua
  const withDef = selectablePathsFrom(WITH_DEFIANCE); // ...+ Defiance

  it("today's build has exactly four selectable sites (Lima + Urbana + Fort Wayne + Troy-Piqua)", () => {
    expect(real.map((p) => p.props.slug).sort()).toEqual(["fort-wayne", "lima", "troy-piqua", "urbana"]);
  });

  it("one more selectable site (Defiance) adds its own route, keyed by its own siteBase", () => {
    expect(withDef.map((p) => p.props.slug).sort()).toEqual([
      "defiance",
      "fort-wayne",
      "lima",
      "troy-piqua",
      "urbana",
    ]);
    const def = withDef.find((p) => p.props.slug === "defiance");
    expect(def?.params.site).toBe(siteBase("defiance").replace("/network/", ""));
  });

  it("leaves Lima's path+props byte-identical (the discipline held through every #724 merge)", () => {
    const limaReal = real.find((p) => p.props.slug === "lima");
    const limaDef = withDef.find((p) => p.props.slug === "lima");
    expect(limaDef).toEqual(limaReal);
  });

  it("routes each selectable site to its own chrome tier; promotion flips the tier", () => {
    // Fort Wayne is selectable — resolves to its own chrome tier.
    expect(siteForPathIn(SITES, "/network/fort-wayne/environment")?.slug).toBe("fort-wayne");
    // Defiance is NOT selectable in SITES — network chrome (null); promotion flips it.
    expect(siteForPathIn(SITES, "/network/defiance/environment")).toBeNull();
    expect(siteForPathIn(WITH_DEFIANCE, "/network/defiance/environment")?.slug).toBe("defiance");
    // Lima still routes to Lima, unaffected by any other site's presence.
    expect(siteForPathIn(WITH_DEFIANCE, "/network/american-sugar-creek-allen-co/timeline")?.slug).toBe(
      "lima",
    );
    expect(siteForPathIn(SITES, "/network/fort-wayne")?.slug).toBe("fort-wayne");
  });

  it("each selectable site resolves its OWN story (#733 made this real)", () => {
    const lima = storyFor("lima", "project-bosc");
    const fw = storyFor("fort-wayne", "project-zodiac");
    expect(lima?.chapters.map((c) => c.slug)).toEqual([
      "who",
      "assembly",
      "scale",
      "water",
      "cost",
      "opacity",
    ]);
    expect(fw?.chapters.map((c) => c.slug)).toEqual(["who", "power", "water"]);
    expect(lima?.codename).not.toBe(fw?.codename);
  });

  it("the switcher's current state reacts to a coming-soon site, where the tab tier does not (#793)", () => {
    // Defiance is a coming-soon site: tab-tier resolver returns null...
    expect(siteForPathIn(SITES, "/network/defiance")).toBeNull();
    // ...but the switcher resolver names the current site regardless of `selectable`.
    expect(currentSiteForPath("/network/defiance")?.slug).toBe("defiance");
    // Fort Wayne is selectable — both resolvers return it.
    expect(siteForPathIn(SITES, "/network/fort-wayne")?.slug).toBe("fort-wayne");
    expect(currentSiteForPath("/network/fort-wayne")?.slug).toBe("fort-wayne");
    expect(currentSiteForPath("/network/american-sugar-creek-allen-co/timeline")?.slug).toBe("lima");
    // Off the network (the directory + cross-cutting globals) → no current site.
    expect(currentSiteForPath("/")).toBeNull();
    expect(currentSiteForPath("/about")).toBeNull();
  });

  it("a coming-soon site gets a registry-only, mostly-locked site-tier tab bar (#793)", () => {
    const def = SITES.find((s) => s.slug === "defiance") as NetworkSite;
    const tabs = comingSoonSiteTabs(def);
    // All registry-only plain links pointing at the site's own watch page (never a 404 into an
    // unbuilt tree); the overview is live, the unbuilt sections are locked markers.
    const base = siteBase("defiance");
    const links = tabs.map((t) => (t.kind === "link" ? t : null));
    expect(links.map((t) => t?.label)).toEqual(["The site", "The story", "The record"]);
    expect(links.map((t) => Boolean(t?.locked))).toEqual([false, true, true]);
    for (const t of links) expect(t?.href).toBe(base);
  });

  it("promoting a site removes it from the coming-soon set", () => {
    // Defiance is in coming-soon; Fort Wayne is not (it's selectable now).
    expect(comingSoonFrom(SITES).map((s) => s.slug)).toContain("defiance");
    expect(comingSoonFrom(SITES).map((s) => s.slug)).not.toContain("fort-wayne");
    expect(comingSoonFrom(WITH_DEFIANCE).map((s) => s.slug)).not.toContain("defiance");
    // Lima is never coming-soon in either world.
    expect(comingSoonFrom(WITH_DEFIANCE).map((s) => s.slug)).not.toContain("lima");
  });
});
