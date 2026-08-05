import { describe, expect, it } from "vitest";
import { DEFAULT_STORY_CODENAME, LIMA_SLUG, SITE_BASE, siteBase, WALK_BASE, walkBase } from "./routes";
import { siteHref, walkUrl, withSite, withStory } from "./site";

describe("routes", () => {
  it("SITE_BASE is the network-rooted live site path (was /bosc)", () => {
    expect(SITE_BASE).toBe("/network/american-sugar-creek-allen-co");
  });

  it("WALK_BASE nests the project-bosc story under the site", () => {
    expect(WALK_BASE).toBe(`${SITE_BASE}/walk/project-bosc`);
  });

  it("siteBase resolves Lima's special URL id from its slug", () => {
    expect(siteBase(LIMA_SLUG)).toBe(SITE_BASE);
    expect(siteBase("lima")).toBe("/network/american-sugar-creek-allen-co");
  });

  it("siteBase maps every other slug to itself under /network", () => {
    expect(siteBase("fort-wayne")).toBe("/network/fort-wayne");
    expect(siteBase("defiance")).toBe("/network/defiance");
  });

  it("walkBase nests a codename under a site", () => {
    expect(walkBase(LIMA_SLUG, DEFAULT_STORY_CODENAME)).toBe(WALK_BASE);
    expect(walkBase("fort-wayne", "some-story")).toBe("/network/fort-wayne/walk/some-story");
  });

  it("withSite prefixes the site root (deploy base '/')", () => {
    expect(withSite()).toBe(SITE_BASE);
    expect(withSite("")).toBe(SITE_BASE);
    expect(withSite("/leads")).toBe(`${SITE_BASE}/leads`);
    expect(withSite("/site/")).toBe(`${SITE_BASE}/site/`);
  });

  it("withStory prefixes the story root", () => {
    expect(withStory()).toBe(WALK_BASE);
    expect(withStory("/water")).toBe(`${WALK_BASE}/water`);
  });

  it("siteHref is the slug-parameterized peer of withSite", () => {
    expect(siteHref(LIMA_SLUG, "/site/")).toBe(withSite("/site/"));
    expect(siteHref("fort-wayne")).toBe("/network/fort-wayne");
    expect(siteHref("fort-wayne", "/timeline")).toBe("/network/fort-wayne/timeline");
  });

  it("walkUrl is the slug-parameterized peer of withStory", () => {
    expect(walkUrl(LIMA_SLUG, DEFAULT_STORY_CODENAME, "/water")).toBe(withStory("/water"));
    expect(walkUrl("fort-wayne", "some-story")).toBe("/network/fort-wayne/walk/some-story");
  });
});
