import { describe, expect, it } from "vitest";
import { runWithSite } from "./bundle";
import { SITES, comingSoonWalks, walkComingSoon, surfacedWalks } from "./sites";
import {
  WALK_ANCHORS,
  WALK_CHAPTERS,
  WALK_INDEX_HREF,
  WALK_TOTAL,
  activeWalk,
  activeWalkAnchorFor,
  chapterByStep,
  chapterHref,
  siteSurfacesWalk,
  walkAnchorForIn,
  walkChapterByStep,
  walkContentsHref,
  walkFor,
  walkAnchorFor,
  walkHref,
} from "./walk";

describe("WALK_CHAPTERS invariants", () => {
  it("holds exactly WALK_TOTAL chapters, all live", () => {
    expect(WALK_CHAPTERS).toHaveLength(WALK_TOTAL);
    expect(WALK_CHAPTERS.every((c) => c.live)).toBe(true);
  });

  it("numbers the steps 1..WALK_TOTAL in order", () => {
    expect(WALK_TOTAL).toBe(6);
    expect(WALK_CHAPTERS.map((c) => c.step)).toEqual([1, 2, 3, 4, 5, 6]);
  });

  it("has the assembly chapter at step 2 (#219)", () => {
    expect(chapterByStep(2)?.slug).toBe("assembly");
    expect(chapterByStep(6)?.slug).toBe("opacity");
  });

  it("has unique slugs", () => {
    const slugs = WALK_CHAPTERS.map((c) => c.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});

describe("walkHref", () => {
  // BASE_URL is "/" under vitest, so withBase is a no-op prefix.
  it("builds a /walk/<slug> route", () => {
    // The test name has said `/walk/` since it was written; #1972 made it true, by moving the
    // editorial walk off the `/stories/` namespace it shared with the reader-composed Walk.
    expect(walkHref("who")).toBe("/network/american-sugar-creek-allen-co/walk/project-bosc/who");
  });
});

describe("chapterByStep", () => {
  it("returns the matching chapter", () => {
    expect(chapterByStep(3)?.slug).toBe("scale");
  });
  it("returns undefined for an out-of-range step", () => {
    expect(chapterByStep(0)).toBeUndefined();
    expect(chapterByStep(99)).toBeUndefined();
  });
});

describe("walkAnchorFor", () => {
  it("resolves a known record rel to its chapter anchor (renumbered for #219)", () => {
    const a = walkAnchorFor("aedg/roundabouts.summary.opc.yaml");
    expect(a).toEqual({ ch: "05", slug: "cost", label: "What it costs the public" });
  });

  it("resolves the air-permit anchor, now Ch.3 after the assembly chapter (#219)", () => {
    const a = walkAnchorFor("permits/4132514.epa.yaml");
    expect(a).toEqual({ ch: "03", slug: "scale", label: "How big is it — and what won't they tell you?" });
  });

  it("returns undefined for a rel with no anchor", () => {
    expect(walkAnchorFor("permits/4132514.epa.yaml.nope")).toBeUndefined();
  });

  it("every anchor slug points at a real chapter", () => {
    const slugs = new Set(WALK_CHAPTERS.map((c) => c.slug));
    for (const a of Object.values(WALK_ANCHORS)) {
      expect(slugs.has(a.slug)).toBe(true);
    }
  });
});

describe("Walk model", () => {
  it("registers Lima's project-bosc story and resolves it by (site, codename)", () => {
    const story = walkFor("lima", "project-bosc");
    expect(story?.title).toBe("Project BOSC");
    expect(story?.chapters).toHaveLength(WALK_TOTAL);
  });

  it("returns undefined for an unregistered (site, codename)", () => {
    expect(walkFor("lima", "nope")).toBeUndefined();
    expect(walkFor("fort-wayne", "project-bosc")).toBeUndefined();
  });

  it("derives the Lima-pinned conveniences from the Lima story", () => {
    const story = walkFor("lima", "project-bosc");
    if (!story) throw new Error("Lima story must exist");
    expect(chapterHref(story, "who")).toBe(walkHref("who"));
    expect(walkContentsHref(story)).toBe(WALK_INDEX_HREF);
    expect(walkChapterByStep(story, 3)?.slug).toBe(chapterByStep(3)?.slug);
    expect(walkAnchorForIn(story, "aedg/roundabouts.summary.opc.yaml")).toEqual(
      walkAnchorFor("aedg/roundabouts.summary.opc.yaml"),
    );
  });

  it("the registry's story refs resolve to a real story in the store", () => {
    for (const site of SITES) {
      for (const ref of site.stories ?? []) {
        const story = walkFor(site.slug, ref.codename);
        expect(story, `${site.slug}/${ref.codename} must resolve`).toBeDefined();
        expect(story?.title).toBe(ref.title);
      }
    }
  });

  it("the absorbed walks no longer resolve — the collection is Lima's alone (#1971)", () => {
    // #1970 moved Fort Wayne's, Findlay's and Bowling Green's chapters into their impact studies
    // and #1971 retired their registry entries. Both halves must go together: a registered
    // codename whose MDX is gone fails the resolution guard above, and orphan MDX under a
    // codename nothing registers is dead content. This pins the pair.
    for (const [slug, codename] of [
      ["fort-wayne", "project-zodiac"],
      ["findlay", "flagpole"],
      ["bowling-green", "project-accordion"],
    ] as const) {
      expect(walkFor(slug, codename), `${slug}/${codename} must no longer resolve`).toBeUndefined();
    }
  });
});

describe("story surface resolution — Lima is the only walk (#1526/#1971)", () => {
  it("surfaces Lima's readable walk, and nothing else registers one", () => {
    // Lima's MDX content, the WALK_* guard, and its metadata resolve — and its record is finished,
    // so the walk *surfaces* (readable): included in surfacedWalks, excluded from comingSoon.
    const story = walkFor("lima", "project-bosc");
    expect(story?.title).toBe("Project BOSC");
    expect(WALK_CHAPTERS.length).toBe(WALK_TOTAL);
    expect(siteSurfacesWalk("lima", "project-bosc")).toBe(true);
    expect(surfacedWalks("lima").map((s) => s.codename)).toEqual(["project-bosc"]);
    expect(comingSoonWalks("lima")).toHaveLength(0);
    expect(walkComingSoon("lima", "project-bosc")).toBe(false);
    // The three absorbed walks surface nothing on either axis. They are not `comingSoon` (held
    // content waiting to publish) — their prose HAS published, as study notes, and the walk is
    // gone. Asserting both emptinesses is what keeps "absorbed" from decaying back into "held".
    for (const [slug, codename] of [
      ["fort-wayne", "project-zodiac"],
      ["findlay", "flagpole"],
      ["bowling-green", "project-accordion"],
    ] as const) {
      expect(siteSurfacesWalk(slug, codename)).toBe(false);
      expect(surfacedWalks(slug)).toHaveLength(0);
      expect(comingSoonWalks(slug)).toHaveLength(0);
      expect(walkComingSoon(slug, codename)).toBe(false);
    }
  });

  it("resolves Lima's ambient readable story + backlinks, but none for a held or story-less site", () => {
    // Lima (default active site): its walk surfaces → the ambient readable story is Project BOSC, and
    // the record→chapter backlink resolves (aedg roundabouts OPC anchors the `cost` chapter).
    expect(activeWalk()?.codename).toBe("project-bosc");
    expect(activeWalkAnchorFor("aedg/roundabouts.summary.opc.yaml")?.slug).toBe("cost");
    // Fort Wayne: its own walk is held → no ambient readable story (and never Lima's).
    runWithSite("fort-wayne", () => {
      expect(activeWalk()).toBeUndefined();
    });
    // Urbana surfaces no story at all → undefined, and it's not coming-soon (nothing to advertise).
    runWithSite("urbana", () => {
      expect(activeWalk()).toBeUndefined();
      expect(comingSoonWalks("urbana")).toHaveLength(0);
      expect(walkComingSoon("urbana", "project-bosc")).toBe(false);
    });
  });
});
