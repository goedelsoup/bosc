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
import { LENS_ORDER } from "./lenses";
import {
  contextualLeaves,
  navItemDestinations,
  navItemLinks,
  navSurfaces,
  siteTabs,
  type NavItem,
} from "./nav";
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

describe("the Lenses dropdown — route prefix and menu section agree (#1893, inherited by #1915)", () => {
  // #1893 asked that "route prefix and menu section agree for every leaf in the Reference
  // dropdown". #1915 supersedes the clause rather than re-implementing it: the Reference dropdown
  // could not satisfy it — it listed `/environment/map` and `/environment/imagery` under a menu
  // section that no longer named them — and the lens tab IS the reconciliation. Its children are
  // five landings under one prefix, so the criterion holds by construction instead of by audit.
  //
  // The facet leaves are still reachable, from the landing bodies. That is deliberate and it is
  // what makes the agreement real rather than definitional: an in-page contextual cross-link is
  // not a nav surface (this suite's own rule), so no menu section claims them.
  function lensTab(): Extract<NavItem, { kind: "dropdown" }> {
    const tab = siteTabs().find((t) => t.section === "lens");
    expect(tab, "the site-tier bar lost its Lenses tab").toBeDefined();
    expect(tab!.kind, "the Lenses tab must stay a dropdown — its children are the five lenses").toBe(
      "dropdown",
    );
    return tab as Extract<NavItem, { kind: "dropdown" }>;
  }

  function children(): { label: string; href: string }[] {
    return lensTab().children.filter((c): c is { label: string; href: string } => !("divider" in c));
  }

  it("carries the five lenses and nothing else", () => {
    const kids = children();
    expect(kids).toHaveLength(LENS_ORDER.length);
    expect(kids.map((c) => c.href)).toEqual(LENS_ORDER.map((id) => `${siteBase(activeSite())}/lens/${id}`));
  });

  it("every leaf sits under the prefix the menu section names", () => {
    // The criterion itself. The old dropdown needed a per-half regex because its two halves had
    // two prefixes; one tab with one prefix is what retires that shape.
    const base = siteBase(activeSite());
    for (const c of children()) {
      expect(c.href, `${c.href} is filed under Lenses`).toMatch(new RegExp(`^${base}/lens/`));
    }
  });

  it("advertises no facet leaf — those are reached from the landing, not the menu", () => {
    // The regression the merged Reference dropdown was: nine `/environment/*` leaves in a menu,
    // several of which a locked section would have pointed straight at a lock.
    for (const c of children()) {
      expect(c.href).not.toMatch(/\/(environment|economy)\//);
    }
  });

  it("still lights on the surviving section routes", () => {
    // No leaf URL moved, so `/environment/hydrology` and `/economy/grid` are live routes whose
    // pages declare the sections they always did. Without `match` the bar would go blank on them.
    const tab = lensTab();
    expect(tab.match).toContain("environment");
    expect(tab.match).toContain("economy");
  });
});

describe("contextual leaves — the declared non-destinations (#1908)", () => {
  // The other half of "every built page is reachable from the nav model, OR is declared contextual
  // with the reason recorded in nav.ts". Before this register the two cases were indistinguishable:
  // a page the chrome deliberately skipped and a page it had forgotten were both simply absent
  // from `nav.ts`, so nothing marked which was a decision — and search had no stated way to reach
  // either. What makes the declaration worth anything is that it costs something to write.

  it("says where a reader meets it and why the chrome doesn't carry it", () => {
    const leaves = contextualLeaves();
    expect(leaves.length).toBeGreaterThan(0);
    for (const leaf of leaves) {
      expect(leaf.href.startsWith("/"), `${leaf.label}: not root-absolute`).toBe(true);
      expect(leaf.label.length).toBeGreaterThan(0);
      // A one-word reason is an exemption, not a declaration — the bar `searchCoverage.ts` sets
      // for its family notes, applied to the same kind of claim.
      expect(leaf.via.length, `${leaf.label}: no carrier named`).toBeGreaterThan(20);
      expect(leaf.why.length, `${leaf.label}: reason too thin`).toBeGreaterThan(60);
    }
  });

  it("declares nothing the chrome already carries", () => {
    // The failure mode in the other direction: a destination sitting in a menu AND claiming to be
    // a contextual leaf, which would let a nav removal pass unnoticed because the leaf covers for
    // it. Contextual means contextual.
    const inChrome = new Set(navSurfaces().flatMap((s) => s.links.map((l) => l.href)));
    for (const leaf of contextualLeaves()) {
      expect(inChrome.has(leaf.href), `${leaf.label} is in the chrome — drop the declaration`).toBe(false);
    }
  });

  it("is not a navigation surface", () => {
    // #1893's rule is that an in-page cross-link is where a DEMOTED destination goes. Counting
    // these against the two-surface ceiling would invert it into a reason not to write them down.
    expect(navSurfaces().map((s) => s.id)).not.toContain("contextual");
  });
});
