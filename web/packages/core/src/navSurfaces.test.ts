// The nav diet's standing rule (#1893 acceptance): **no destination appears in more than two
// navigation surfaces**, and every leaf of the Reference dropdown sits under the route prefix its
// section names.
//
// Both are the kind of thing that decays one well-meant link at a time. The impact study reached
// readers from four surfaces at once and Reports from four; each addition was defensible on its
// own, and the sum was a nav where everything is one click from everywhere — which emphasizes
// nothing. This suite is what makes the next addition a decision rather than a drift.
//
// What counts as a surface is declared in `nav.ts` (`navSurfaces`): a standing affordance, not a
// rendering of one. The desktop bar and the phone sheet render the same models, so they are one
// surface; a tab and its own dropdown are one surface. In-page contextual cross-links are not
// surfaces at all — they are where a demoted destination goes.
import { describe, expect, it } from "vitest";
import { navItemDestinations, navItemLinks, navSurfaces, siteTabs, type NavChild, type NavItem } from "./nav";
import { activeSite } from "./bundle";
import { siteBase } from "./routes";

/** Every `(href → surface ids)` pair, deduped WITHIN a surface (a tab and its dropdown's first
 *  child are frequently the same href, and that is one affordance, not two). */
function surfacesByHref(): Map<string, string[]> {
  const out = new Map<string, string[]>();
  for (const surface of navSurfaces()) {
    for (const href of new Set(surface.links.map((l) => l.href))) {
      out.set(href, [...(out.get(href) ?? []), surface.id]);
    }
  }
  return out;
}

describe("navigation surfaces — the nav-diet ceiling (#1893)", () => {
  it("counts the surfaces it says it counts", () => {
    // Guards the whole suite against vacuity: a `navSurfaces()` that silently returned fewer
    // surfaces, or empty ones, would satisfy every assertion below while proving nothing.
    const surfaces = navSurfaces();
    expect(surfaces.map((s) => s.id)).toEqual([
      "site-home",
      "header-site",
      "header-network",
      "platform",
      "footer",
    ]);
    for (const s of surfaces) expect(s.links.length, `${s.id} is empty`).toBeGreaterThan(0);
  });

  it("no destination appears in more than two navigation surfaces", () => {
    const over = [...surfacesByHref().entries()]
      .filter(([, ids]) => ids.length > 2)
      .map(([href, ids]) => `${href} — ${ids.join(", ")}`);
    expect(over, "demote one to a contextual cross-link, or drop it").toEqual([]);
  });

  it("the impact study is carried by the home band and the header tab — and nothing else", () => {
    // The regression this exists for. The study is the site's declared primary artifact, so it is
    // AT the ceiling by design: the two surfaces that say "primary artifact". It left the footer
    // (the fourth surface) to get there; a third one added back here is the whole failure mode.
    const study = `${siteBase(activeSite())}/study/`;
    expect(surfacesByHref().get(study)).toEqual(["site-home", "header-site"]);
  });

  it("the story is the mega's spine, not a spine plus a tab beside it", () => {
    // The standalone "The story" tab was the same destination as the mega spine's head, in the
    // same bar, one tab apart. The spine survived; a phone gets the head via `navItemLinks`.
    const tabs = siteTabs();
    const mega = tabs.find((t): t is Extract<NavItem, { kind: "mega" }> => t.kind === "mega");
    expect(mega, "the site-tier bar lost its mega").toBeDefined();
    const spine = mega!.mega.spine.href;
    expect(tabs.filter((t) => t.kind === "link" && t.href === spine)).toEqual([]);
    // …and story routes still light a tab, or the bar would go blank on every chapter.
    expect(mega!.match).toContain("story");
  });

  it("a surface is counted by every destination the mega opens, not by what the sheet shows", () => {
    // These two flatteners answer different questions and must not collapse into one. The sheet
    // (`navItemLinks`) stops at the spine's head on purpose — a phone gets no mega, and its deep
    // chapter list belongs to the desktop menu. The ceiling counts what a reader can REACH, so it
    // has to include those chapters. Asserted on a synthetic mega because the reference site's
    // story is `comingSoon` (#1526), which leaves the real spine with no chapters at all — so
    // going through `siteTabs()` here would prove nothing today and quietly start to matter the
    // day a story surfaces.
    const mega: NavItem = {
      kind: "mega",
      label: "The site",
      section: "home",
      mega: {
        tiles: [{ label: "Overview", href: "/s", blurb: "", icon: "home" }],
        spine: {
          title: "The story",
          href: "/s/stories/x",
          count: "2 chapters",
          blurb: "",
          tocHref: "/s/stories/x/contents",
          items: [
            { label: "One", href: "/s/stories/x/one" },
            { label: "Two", href: "/s/stories/x/two" },
          ],
        },
      },
    };
    expect(navItemLinks(mega).map((l) => l.href)).toEqual(["/s", "/s/stories/x"]);
    expect(navItemDestinations(mega).map((l) => l.href)).toEqual([
      "/s",
      "/s/stories/x",
      "/s/stories/x/one",
      "/s/stories/x/two",
    ]);
  });
});

describe("the Reference dropdown — route prefix and menu section agree (#1893)", () => {
  /** The Reference dropdown's leaves, split at the divider into its environment and economy
   *  halves. Returns null on a peer whose both halves are locked (the tab collapses to a marker). */
  function referenceHalves(): { environment: NavChild[]; economy: NavChild[] } | null {
    const tab = siteTabs().find((t) => t.section === "environment");
    expect(tab, "the site-tier bar lost its Reference tab").toBeDefined();
    if (tab!.kind !== "dropdown") return null;
    const i = tab!.children.findIndex((c) => "divider" in c);
    expect(i, "the merged dropdown lost the divider between its halves").toBeGreaterThan(0);
    return { environment: tab!.children.slice(0, i), economy: tab!.children.slice(i + 1) };
  }

  it("every leaf sits under the prefix of the half it is filed in", () => {
    const halves = referenceHalves();
    expect(halves).not.toBeNull();
    const base = siteBase(activeSite());
    const hrefs = (children: NavChild[]): string[] =>
      children.filter((c): c is { label: string; href: string } => !("divider" in c)).map((c) => c.href);

    // The finding: `/environment/economics-baseline` was a LABOR baseline listed under Economy,
    // and three `/reports/*` long-forms sat under it too. The IA and the routes disagreed.
    for (const href of hrefs(halves!.environment)) {
      expect(href, `${href} is filed under Environment`).toMatch(new RegExp(`^${base}/environment(/|$)`));
    }
    for (const href of hrefs(halves!.economy)) {
      expect(href, `${href} is filed under Economy`).toMatch(new RegExp(`^${base}/economy(/|$)`));
    }
  });

  it("the labor baseline is at its economy address", () => {
    const halves = referenceHalves();
    const economy = halves!.economy.filter((c): c is { label: string; href: string } => !("divider" in c));
    expect(economy.map((c) => c.href)).toContain(`${siteBase(activeSite())}/economy/economics-baseline`);
  });
});
