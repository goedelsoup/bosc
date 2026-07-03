import { describe, expect, it } from "vitest";
import { type StoryChapterSpine, buildStory } from "./stories";
import { STORIES, siteOwner, storiesOwnedBy, storyFor } from "./walk";

// The Lima `project-bosc` spine, as authored in the `stories` collection
// (src/content/stories/lima/project-bosc/*.mdx). `buildStory` must reproduce the canonical
// hardcoded story (walk.ts `STORIES`) from it — the guard that the MDX migration (#733) is
// faithful before the collection becomes the live source.
const LIMA_SPINE: StoryChapterSpine[] = [
  {
    step: 1,
    slug: "who",
    title: "Who is actually building this?",
    skill: "Reading a deed · cross-document entity resolution",
    anchor: "The deed chain + the Bistrozzi Delaware shell cluster",
    anchorRecordRels: [
      "recorder/202508130008300.deed.yaml",
      "permits/sos-tilted-gate-llc-2025-09-29.sos.yaml",
    ],
    live: true,
  },
  {
    step: 2,
    slug: "assembly",
    title: "How it was assembled & hidden",
    skill: "Reading an options-to-assignment chain · the confidentiality-first sequence",
    anchor: "The Port Authority options → Bistrozzi assignment + the blank DTE-100 prices",
    anchorRecordRels: [],
    live: true,
  },
  {
    step: 3,
    slug: "scale",
    title: "How big is it — and what won't they tell you?",
    skill: "Reading an air permit · recognizing a CBI redaction",
    anchor: "Ohio EPA Air Permit-to-Install P0138965",
    anchorRecordRels: ["permits/4132514.epa.yaml"],
    live: true,
  },
  {
    step: 4,
    slug: "water",
    title: "What it does to the water",
    skill: "Reading an NPDES permit · the 7Q10 low-flow screen",
    anchor: "NPDES dilution + the cooling-draw screen",
    anchorRecordRels: ["oepa/oepa-2PH00006-american-ii-fact-sheet.npdes.yaml"],
    live: true,
  },
  {
    step: 5,
    slug: "cost",
    title: "What it costs the public",
    skill: "Reading a cost estimate · reading a contract clause",
    anchor: "Tetra Tech OPC + the Roadwork Development Agreement",
    anchorRecordRels: ["aedg/roundabouts.summary.opc.yaml"],
    live: true,
  },
  {
    step: 6,
    slug: "opacity",
    title: "Why you had to dig for this",
    skill: "Reading statutory exemptions",
    anchor: "The withholding stack + the mandamus thread",
    anchorRecordRels: [],
    live: true,
  },
];

describe("buildStory", () => {
  it("reproduces the canonical Lima story from its chapter spine", () => {
    const canonical = storyFor("lima", "project-bosc");
    if (!canonical) throw new Error("Lima story must exist in the store");
    const built = buildStory(
      "lima",
      "project-bosc",
      { title: canonical.title, dek: canonical.dek },
      LIMA_SPINE,
    );
    expect(built).toEqual(canonical);
  });

  it("orders chapters by step regardless of input order", () => {
    const built = buildStory("lima", "project-bosc", { title: "x", dek: "y" }, [
      LIMA_SPINE[3],
      LIMA_SPINE[0],
      LIMA_SPINE[2],
    ]);
    expect(built.chapters.map((c) => c.step)).toEqual([1, 3, 4]);
  });

  it("inverts anchorRecordRels into the record→chapter backlink map", () => {
    const built = buildStory("lima", "project-bosc", { title: "x", dek: "y" }, LIMA_SPINE);
    expect(built.anchors["aedg/roundabouts.summary.opc.yaml"]).toEqual({
      ch: "05",
      slug: "cost",
      label: "What it costs the public",
    });
    // A chapter with two anchored records contributes both.
    expect(built.anchors["recorder/202508130008300.deed.yaml"].slug).toBe("who");
    expect(built.anchors["permits/sos-tilted-gate-llc-2025-09-29.sos.yaml"].slug).toBe("who");
  });
});

describe("owner axis (#1092)", () => {
  it("builds a site-owned story whose owner id is the site slug", () => {
    const built = buildStory("lima", "project-bosc", { title: "x", dek: "y" }, LIMA_SPINE);
    expect(built.owner).toEqual({ kind: "site", id: "lima" });
    expect(built.owner.id).toBe(built.site);
  });

  it("filters stories to a single owner by the (kind, id) pair", () => {
    const lima = buildStory("lima", "project-bosc", { title: "x", dek: "y" }, LIMA_SPINE);
    const other = buildStory("fort-wayne", "some-codename", { title: "x", dek: "y" }, LIMA_SPINE);
    const pool = [lima, other];
    expect(storiesOwnedBy(pool, siteOwner("lima"))).toEqual([lima]);
    // A user owner sharing the string "lima" must not match the site-owned story.
    expect(storiesOwnedBy(pool, { kind: "user", id: "lima" })).toEqual([]);
  });

  it("every editorial story in the collection is site-owned (no behavior change)", () => {
    for (const s of STORIES) expect(s.owner).toEqual({ kind: "site", id: s.site });
  });
});
