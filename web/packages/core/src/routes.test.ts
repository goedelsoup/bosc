import { describe, expect, it } from "vitest";
import { DEFAULT_STORY_CODENAME, LIMA_SLUG, SITE_BASE, siteBase, STORY_BASE, storyBase } from "./routes";
import { siteHref, storyHref, withSite, withStory } from "./site";

describe("routes", () => {
  it("SITE_BASE is the network-rooted live site path (was /bosc)", () => {
    expect(SITE_BASE).toBe("/network/american-sugar-creek-allen-co");
  });

  it("STORY_BASE nests the project-bosc story under the site", () => {
    expect(STORY_BASE).toBe(`${SITE_BASE}/stories/project-bosc`);
  });

  it("siteBase resolves Lima's special URL id from its slug", () => {
    expect(siteBase(LIMA_SLUG)).toBe(SITE_BASE);
    expect(siteBase("lima")).toBe("/network/american-sugar-creek-allen-co");
  });

  it("siteBase maps every other slug to itself under /network", () => {
    expect(siteBase("fort-wayne")).toBe("/network/fort-wayne");
    expect(siteBase("defiance")).toBe("/network/defiance");
  });

  it("storyBase nests a codename under a site", () => {
    expect(storyBase(LIMA_SLUG, DEFAULT_STORY_CODENAME)).toBe(STORY_BASE);
    expect(storyBase("fort-wayne", "some-story")).toBe("/network/fort-wayne/stories/some-story");
  });

  it("withSite prefixes the site root (deploy base '/')", () => {
    expect(withSite()).toBe(SITE_BASE);
    expect(withSite("")).toBe(SITE_BASE);
    expect(withSite("/leads")).toBe(`${SITE_BASE}/leads`);
    expect(withSite("/site/")).toBe(`${SITE_BASE}/site/`);
  });

  it("withStory prefixes the story root", () => {
    expect(withStory()).toBe(STORY_BASE);
    expect(withStory("/water")).toBe(`${STORY_BASE}/water`);
  });

  it("siteHref is the slug-parameterized peer of withSite", () => {
    expect(siteHref(LIMA_SLUG, "/site/")).toBe(withSite("/site/"));
    expect(siteHref("fort-wayne")).toBe("/network/fort-wayne");
    expect(siteHref("fort-wayne", "/timeline")).toBe("/network/fort-wayne/timeline");
  });

  it("storyHref is the slug-parameterized peer of withStory", () => {
    expect(storyHref(LIMA_SLUG, DEFAULT_STORY_CODENAME, "/water")).toBe(withStory("/water"));
    expect(storyHref("fort-wayne", "some-story")).toBe("/network/fort-wayne/stories/some-story");
  });
});
