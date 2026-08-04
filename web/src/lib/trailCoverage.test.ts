// Every page template must declare a breadcrumb trail (#1889, epic #1884 phase 5).
//
// The acceptance criterion is "a test asserts no content template ships without a trail". The
// render side of that is now structural — `Base.astro` calls `trailFor` for every page, so a
// template cannot forget to *render* one. What it can still do is add a route segment the trail
// model has never heard of, which degrades to a humanized, unlinked crumb ("Rsei" instead of
// "RSEI / toxics", and no link out of the level above).
//
// So this walks `src/pages/**` for the route patterns actually on disk and asks
// `trailDeclared` about each. A new page that isn't in `packages/core/src/trail.ts` fails here,
// at the point where naming it is cheap, rather than shipping a trail that limps.
//
// The complementary end-to-end assertion lives in `scripts/check-routes.mjs`, which proves the
// built HTML really carries the nav and the BreadcrumbList.
import { readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { trailDeclared } from "@watermark/core/trail";

/**
 * Route patterns for every page template, with `[param]` written `*` and `[...rest]` written
 * `**` — the form `trailDeclared` takes, since a dynamic segment's concrete values aren't
 * knowable from the filesystem.
 */
function routePatterns(): string[] {
  const patterns: string[] = [];
  const walk = (dir: string, prefix: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      const name = entry.name
        .replace(/\.(astro|mdx)$/, "")
        .replace(/\[\.\.\.[^\]]+\]/g, "**")
        .replace(/\[[^\]]+\]/g, "*");
      if (entry.isDirectory()) walk(path, `${prefix}/${name}`);
      else if (/\.(astro|mdx)$/.test(entry.name)) {
        patterns.push(name === "index" ? prefix || "/" : `${prefix}/${name}`);
      }
    }
  };
  walk("src/pages", "");
  return patterns;
}

describe("breadcrumb coverage", () => {
  const patterns = routePatterns();

  it("crawled the page tree", () => {
    // Guard against a vacuous pass: an empty crawl would make the assertion below assert nothing.
    expect(patterns.length).toBeGreaterThan(80);
    expect(patterns).toContain("/");
    expect(patterns).toContain("/network/*/site/records/*/*");
  });

  it("declares a trail for every page template", () => {
    const undeclared = patterns.filter((p) => !trailDeclared(p));
    expect(
      undeclared,
      `these routes have no entry in packages/core/src/trail.ts — add one (a URL segment's ` +
        `label is editorial, so it can't be inferred from the slug):\n  ${undeclared.join("\n  ")}`,
    ).toEqual([]);
  });
});
