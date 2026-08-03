import { describe, expect, it } from "vitest";
import { runWithSite } from "./bundle";
import { SITES, comingSoonStories, storyComingSoon, surfacedStories } from "./sites";
import {
  WALK_ANCHORS,
  WALK_CHAPTERS,
  WALK_INDEX_HREF,
  WALK_TOTAL,
  activeStory,
  activeStoryAnchorFor,
  chapterByStep,
  chapterHref,
  siteSurfacesStory,
  storyAnchorFor,
  storyChapterByStep,
  storyContentsHref,
  storyFor,
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
    expect(walkHref("who")).toBe("/network/american-sugar-creek-allen-co/stories/project-bosc/who");
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

describe("Story model", () => {
  it("registers Lima's project-bosc story and resolves it by (site, codename)", () => {
    const story = storyFor("lima", "project-bosc");
    expect(story?.title).toBe("Project BOSC");
    expect(story?.chapters).toHaveLength(WALK_TOTAL);
  });

  it("returns undefined for an unregistered (site, codename)", () => {
    expect(storyFor("lima", "nope")).toBeUndefined();
    expect(storyFor("fort-wayne", "project-bosc")).toBeUndefined();
  });

  it("derives the Lima-pinned conveniences from the Lima story", () => {
    const story = storyFor("lima", "project-bosc");
    if (!story) throw new Error("Lima story must exist");
    expect(chapterHref(story, "who")).toBe(walkHref("who"));
    expect(storyContentsHref(story)).toBe(WALK_INDEX_HREF);
    expect(storyChapterByStep(story, 3)?.slug).toBe(chapterByStep(3)?.slug);
    expect(storyAnchorFor(story, "aedg/roundabouts.summary.opc.yaml")).toEqual(
      walkAnchorFor("aedg/roundabouts.summary.opc.yaml"),
    );
  });

  it("the registry's story refs resolve to a real story in the store", () => {
    for (const site of SITES) {
      for (const ref of site.stories ?? []) {
        const story = storyFor(site.slug, ref.codename);
        expect(story, `${site.slug}/${ref.codename} must resolve`).toBeDefined();
        expect(story?.title).toBe(ref.title);
      }
    }
  });

  it("surfaces a second site's story from the collection, not just Lima (#733)", () => {
    // The flip's payoff: a non-Lima story registers + resolves with no hand-edit to this module.
    const fw = storyFor("fort-wayne", "project-zodiac");
    expect(fw, "Fort Wayne's project-zodiac story must resolve from the collection").toBeDefined();
    expect(fw?.title).toBe("Project Zodiac");
    expect(fw?.chapters.map((c) => c.slug)).toEqual(["who", "power", "water"]);
    expect(fw?.chapters.every((c) => c.live)).toBe(true);
  });

  it("resolves Findlay's flagpole walk in reading order (#1466)", () => {
    const fin = storyFor("findlay", "flagpole");
    expect(fin, "Findlay's flagpole story must resolve from the collection").toBeDefined();
    expect(fin?.title).toBe("Flagpole");
    // Ordered cause → consequence, so no chapter leans on a figure a later one establishes: the
    // disclosed load, then the tariff it would sit under, then the ground it sits on, then the
    // river's denominator, then the load reconstruction that denominator's permit governs, then
    // what the river has already cost.
    expect(fin?.chapters.map((c) => c.slug)).toEqual([
      "who",
      "power",
      "ground",
      "water",
      "phosphorus",
      "flood",
    ]);
    expect(fin?.chapters.map((c) => c.step)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(fin?.chapters.every((c) => c.live)).toBe(true);
    // Record → chapter backlinks invert from the chapters' own anchorRecordRels.
    expect(storyAnchorFor(fin!, "oepa/findlay/2PD00008.fs.npdes.yaml")?.slug).toBe("water");
    expect(storyAnchorFor(fin!, "findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml")?.slug).toBe("phosphorus");
  });
});

describe("story surface resolution — Lima readable, Fort Wayne coming-soon (#1526)", () => {
  it("surfaces Lima's readable walk while holding Fort Wayne's from every readable surface", () => {
    // Lima's MDX content, the WALK_* guard, and its metadata resolve — and its record is finished, so
    // the walk now *surfaces* (readable): included in surfacedStories, excluded from comingSoon.
    const story = storyFor("lima", "project-bosc");
    expect(story?.title).toBe("Project BOSC");
    expect(WALK_CHAPTERS.length).toBe(WALK_TOTAL);
    expect(siteSurfacesStory("lima", "project-bosc")).toBe(true);
    expect(surfacedStories("lima").map((s) => s.codename)).toEqual(["project-bosc"]);
    expect(comingSoonStories("lima")).toHaveLength(0);
    expect(storyComingSoon("lima", "project-bosc")).toBe(false);
    // Fort Wayne's walk stays `comingSoon`, so it never *surfaces* (readable). The teaser-vs-held
    // distinction is explicit: surfaced excludes it, comingSoon includes it.
    expect(siteSurfacesStory("fort-wayne", "project-zodiac")).toBe(false);
    expect(surfacedStories("fort-wayne")).toHaveLength(0);
    expect(comingSoonStories("fort-wayne").map((s) => s.codename)).toEqual(["project-zodiac"]);
    expect(storyComingSoon("fort-wayne", "project-zodiac")).toBe(true);
    // Findlay's flagpole is held on the same terms (#1466) — so the readiness `story` FACET stays
    // locked for it even though its manifest `story` DOMAIN is live. The two measure different
    // things: the domain measures whether a walk exists over the record, the facet whether it reads.
    expect(siteSurfacesStory("findlay", "flagpole")).toBe(false);
    expect(surfacedStories("findlay")).toHaveLength(0);
    expect(comingSoonStories("findlay").map((s) => s.codename)).toEqual(["flagpole"]);
    expect(storyComingSoon("findlay", "flagpole")).toBe(true);
  });

  it("resolves Lima's ambient readable story + backlinks, but none for a held or story-less site", () => {
    // Lima (default active site): its walk surfaces → the ambient readable story is Project BOSC, and
    // the record→chapter backlink resolves (aedg roundabouts OPC anchors the `cost` chapter).
    expect(activeStory()?.codename).toBe("project-bosc");
    expect(activeStoryAnchorFor("aedg/roundabouts.summary.opc.yaml")?.slug).toBe("cost");
    // Fort Wayne: its own walk is held → no ambient readable story (and never Lima's).
    runWithSite("fort-wayne", () => {
      expect(activeStory()).toBeUndefined();
    });
    // Urbana surfaces no story at all → undefined, and it's not coming-soon (nothing to advertise).
    runWithSite("urbana", () => {
      expect(activeStory()).toBeUndefined();
      expect(comingSoonStories("urbana")).toHaveLength(0);
      expect(storyComingSoon("urbana", "project-bosc")).toBe(false);
    });
  });
});
