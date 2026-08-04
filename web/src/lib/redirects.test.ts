// `public/_redirects` vs the real routes — the one failure mode every other gate misses (#1888).
//
// On Cloudflare Pages a redirect ALWAYS fires before a matching static asset, so a rule that
// shadows a real page produces a build that is correct in `astro dev`, correct in `dist/`, and
// green in `check-links` — and 301s away in production only. `_redirects` is a plain text file
// that nothing typechecks, so this is the guard.
//
// The file's own header states the invariant ("NO `/submit` / `/research` / `/network/*` broad
// rules: those are real pages now"); this asserts it against the pages actually on disk instead of
// trusting the comment to stay true.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const REDIRECTS = readFileSync("public/_redirects", "utf8");

/** `[from, to, status]` for every rule line (comments and blanks dropped). */
const RULES: [string, string, string][] = REDIRECTS.split("\n")
  .map((l) => l.trim())
  .filter((l) => l.length > 0 && !l.startsWith("#"))
  .map((l) => l.split(/\s+/) as [string, string, string]);

/** Does `rule` (which may end in `/*`) capture `path`? */
function shadows(rule: string, path: string): boolean {
  if (rule.endsWith("/*")) return path === rule.slice(0, -2) || path.startsWith(rule.slice(0, -1));
  // A `:param` segment matches exactly one segment.
  if (rule.includes(":")) {
    const re = new RegExp(`^${rule.replace(/:[^/]+/g, "[^/]+")}$`);
    return re.test(path);
  }
  return rule === path;
}

/**
 * Top-level static routes, from the page files themselves — `foo.astro`, `foo/index.astro`, and
 * the static endpoints (`foo.json.ts`).
 *
 * The endpoints matter as much as the pages and are easier to lose: a shadowed `.json` doesn't
 * render a wrong page, it makes a `fetch` 301 away and a feature silently do nothing. Search is now
 * exactly that shape (#1890) — the index ships as `/search-index.json` and one shard per site — so
 * a rule capturing it would leave a search box that finds nothing, in production only, with every
 * local check green.
 */
function staticRoutes(): string[] {
  const routes: string[] = [];
  const walk = (dir: string, prefix: string): void => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name.startsWith("[")) continue; // dynamic route — its params aren't knowable here
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path, `${prefix}/${entry.name}`);
      else if (entry.name === "index.astro") routes.push(prefix || "/");
      else if (entry.name.endsWith(".astro")) routes.push(`${prefix}/${entry.name.replace(/\.astro$/, "")}`);
      else if (entry.name.endsWith(".ts")) routes.push(`${prefix}/${entry.name.replace(/\.ts$/, "")}`);
    }
  };
  walk("src/pages", "");
  return routes;
}

/**
 * Routes under a dynamic segment that the crawl above can't enumerate, but that must not be
 * shadowed. Kept short and specific — a hand-maintained list is only defensible for the cases the
 * file walk genuinely cannot see.
 */
const DYNAMIC_ROUTES = [
  // One search shard per selectable site (#1890). `/network/:site/docs` and
  // `/network/:site/watershed` are real rules one segment away from this one.
  "/network/american-sugar-creek-allen-co/search-index.json",
  "/network/fort-wayne/search-index.json",
];

describe("public/_redirects", () => {
  it("does not shadow /network — the site index is a real page, not a redirect", () => {
    // The specific regression this guards: `/network` was a 301 to `/` from when the hub moved to
    // the root (pre-#402). #1888 made `/network` the canonical listing of every registered site.
    const shadowing = RULES.filter(([from]) => shadows(from, "/network"));
    expect(shadowing, `these rules capture /network: ${JSON.stringify(shadowing)}`).toEqual([]);
  });

  it("does not shadow any static page route, or any static endpoint", () => {
    const routes = [...staticRoutes(), ...DYNAMIC_ROUTES];
    // Guard against a vacuous pass — an empty crawl would make this test assert nothing.
    expect(routes.length).toBeGreaterThan(20);
    expect(routes).toContain("/network");
    // …and specifically that the crawl reached the endpoints, not just the pages.
    expect(routes).toContain("/search-index.json");
    expect(routes).toContain("/search-coverage.json");
    const collisions = routes.flatMap((route) =>
      RULES.filter(([from]) => shadows(from, route)).map(([from, to]) => `${from} -> ${to} shadows ${route}`),
    );
    expect(collisions).toEqual([]);
  });

  it("still redirects the routes that really did move", () => {
    // The sibling rule survives — /network/hypotheses predates /research/hypotheses.
    expect(RULES).toContainEqual(["/network/hypotheses", "/research/hypotheses", "301"]);
    // The per-site glossary collapsed into the one network-global build (#1892): the retired
    // `/site/concepts/` routes must keep resolving, at their canonical.
    expect(RULES).toContainEqual(["/network/:site/site/concepts", "/wiki/concepts/", "301"]);
    expect(RULES).toContainEqual(["/network/:site/site/concepts/*", "/wiki/concepts/:splat", "301"]);
  });
});
