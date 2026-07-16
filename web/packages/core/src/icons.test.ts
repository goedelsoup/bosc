import { describe, expect, it } from "vitest";
import { ICONS } from "./icons";

describe("icon set (#309)", () => {
  it("includes the design's new site-build glyphs", () => {
    for (const n of [
      "email",
      "notify",
      "locked",
      "secure",
      "repo",
      "map",
      "submit",
      "cost",
      "power",
      "discharge",
    ]) {
      expect(ICONS[n], n).toBeDefined();
      expect(ICONS[n].body.length).toBeGreaterThan(0);
    }
  });

  it("repo is the lone filled (foreign) mark; stroke icons are not filled", () => {
    expect(ICONS.repo.filled).toBe(true);
    expect(ICONS.locked.filled).toBeFalsy();
    expect(ICONS.search.filled).toBeFalsy();
  });
});
