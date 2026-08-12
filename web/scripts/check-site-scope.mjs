// Cross-site data-scope guard for the built site (#2005).
//
// Every `/network/<site>/…` page must render ITS OWN site's data. When two different sites emit a
// byte-identical content region for the same route, exactly one thing has happened: the data was
// resolved once and reused — and since the ambient site defaults to Lima outside a render scope,
// what every site published was Lima's record under its own URL. That is an attribution error, not
// a rendering nit, which is why this is a hard gate rather than a warning.
//
// The bug this exists for (#2005): `timeline.astro` declared `export const getStaticPaths = () =>
// availableFacetPaths("timeline")`. With an arrow-form export and no other `Astro` reference in the
// frontmatter, Astro's compiler hoists the whole block to MODULE scope, where it evaluates ONCE for
// the entire build — outside `src/middleware.ts`'s `runWithSite`. Sidney, Troy-Piqua and Lima all
// served Lima's 164 events, byte for byte, and had done since Troy-Piqua was promoted in #1872.
//
// ⚠️ This check reads `dist/`, and that is the point. Three separate SOURCE heuristics were tried
// first — "slug-less bundle call", "no `Astro.` reference before the read", "frontmatter hoisted" —
// and each one both missed real leaks and flagged pages that render correctly, because whether a
// frontmatter is hoisted is a compiler decision that is not reliably legible in the source. The
// emitted HTML is the only thing that knows. Do not replace this with a lint rule.
//
// Run after `astro build`:  node scripts/check-site-scope.mjs  (pnpm run check:site-scope)

import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const DIST = process.env.CHECK_SITE_SCOPE_DIST || "dist";
const NETWORK = join(DIST, "network");

/**
 * Routes that are IDENTICAL across sites on purpose — a page carrying no site data at all.
 *
 * Kept as a named exception rather than a softer rule, because "these two sites render the same
 * thing" is the entire signal this script has: any predicate loose enough to infer intent would
 * also swallow the leak. An entry here is a claim that the page reads no per-site feed — check
 * that before adding one.
 *
 * `submit` is the site-tier submission form. It renders `<SubmitForm>`, shared verbatim with the
 * network-tier `/submit`, and reads no bundle; only the surrounding chrome is site-specific.
 */
const SITE_INVARIANT_ROUTES = new Set(["submit"]);

/**
 * The rendered content region, excluding the shared chrome.
 *
 * Chrome (the topbar, the site switcher, breadcrumbs, the dateline) legitimately differs per site,
 * so hashing a whole page would make every comparison unequal and the guard vacuous — the leaking
 * timeline pages differed in exactly that way while their event lists were identical. `<article
 * class="prose">` is the content wrapper every per-site page opens with, and the breadcrumb trail
 * is the only chrome inside `<main>`; it always PRECEDES that article, which is what lets the
 * region start there and run to the end of `<main>`.
 *
 * ⚠️ It runs to `</main>`, not to the last `</article>`, since #1993. The narrower region stopped
 * at the prose wrapper and therefore compared a HEADING AND A COUNT — the data itself lives in the
 * sibling `<div class="rb-list">` (the record group index, the timeline) that sat outside it. Two
 * sites with entirely different records and the same COUNT hashed identically: `sidney` and
 * `urbana` each publish one `incentive-package` register, and the guard read that as one site's
 * record under the other's URL. Widening can only ever REDUCE false positives without weakening
 * the guard, because a genuine leak — data resolved once and reused — renders the widened region
 * identically too, count and body alike. It was the count that caught #2005; it did not have to be.
 */
function contentRegion(html) {
  const start = html.indexOf('<article class="prose"');
  if (start < 0) return null;
  const end = html.indexOf("</main>", start);
  return end > start ? html.slice(start, end) : null;
}

function* pages(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* pages(p);
    else if (name === "index.html") yield p;
  }
}

if (!existsSync(NETWORK)) {
  console.error(`check-site-scope: ${NETWORK} not found — run \`astro build\` first.`);
  process.exit(1);
}

// route (path below the site root) -> content hash -> [site, …], plus one sample region per hash
// so the empty-state exemption can inspect what actually collided.
const byRoute = new Map();
const regionByHash = new Map();
for (const site of readdirSync(NETWORK)) {
  const siteDir = join(NETWORK, site);
  if (!statSync(siteDir).isDirectory()) continue;
  for (const file of pages(siteDir)) {
    const region = contentRegion(readFileSync(file, "utf-8"));
    if (region === null) continue; // no prose article (redirects, shells) — nothing to compare
    const route = relative(siteDir, file).replace(/(^|\/)index\.html$/, "") || "(root)";
    const hash = createHash("md5").update(region).digest("hex");
    if (!regionByHash.has(hash)) regionByHash.set(hash, region);
    if (!byRoute.has(route)) byRoute.set(route, new Map());
    const bySite = byRoute.get(route);
    if (!bySite.has(hash)) bySite.set(hash, []);
    bySite.get(hash).push(site);
  }
}

/**
 * An EMPTY state — the page rendered its "nothing on the record here yet" stub.
 *
 * Two sites that both have nothing to show legitimately render the same words, so this collision
 * carries no data and is not a leak. Without the exemption the guard cries wolf the first time a
 * second site lacks a feed whose page still builds — `economy/economics-baseline` builds for EVERY
 * selectable site and stubs when the feed is absent, so that is one promotion away, and a guard
 * that fails spuriously gets switched off.
 *
 * `stub-note` is the shared empty-state class (`site.css`), used by economics-baseline, thermal,
 * grid and the walk contents. Deliberately NOT silent: an allowed collision is still printed, so a
 * real leak that happens to carry a stub somewhere on the page leaves a trail rather than
 * vanishing. The exemption says "this region contains an empty state", which is weaker than "this
 * region is only an empty state" — printing is what keeps that gap honest.
 */
const isEmptyState = (region) => region.includes('class="stub-note"');

const leaks = [];
const allowedEmpty = [];
for (const [route, bySite] of byRoute) {
  if (SITE_INVARIANT_ROUTES.has(route)) continue;
  for (const [hash, sites] of bySite) {
    // A route built for only one site cannot leak; identical content across two or more can only
    // mean it was resolved once.
    if (sites.length < 2) continue;
    (isEmptyState(regionByHash.get(hash)) ? allowedEmpty : leaks).push({
      route,
      sites: sites.sort(),
    });
  }
}

for (const { route, sites } of allowedEmpty.sort((a, b) => a.route.localeCompare(b.route))) {
  console.log(
    `check-site-scope: /network/<site>/${route} — identical EMPTY state across ` +
      `${sites.join(", ")} (allowed: carries a stub-note, so no site's data is on the page).`,
  );
}

if (leaks.length > 0) {
  console.error(
    `check-site-scope: ${leaks.length} route(s) render an IDENTICAL content region for two or more ` +
      `sites — each is publishing one site's record under another site's URL (#2005):\n`,
  );
  for (const { route, sites } of leaks.sort((a, b) => a.route.localeCompare(b.route))) {
    console.error(`  /network/<site>/${route}\n      shared by: ${sites.join(", ")}`);
  }
  console.error(
    "\nAlmost always a page whose frontmatter was hoisted to module scope and evaluated once for " +
      "the whole build. Read `Astro.props` and pass the slug explicitly to every bundle read, and " +
      "declare `getStaticPaths` as a function declaration rather than an arrow expression.",
  );
  process.exit(1);
}

const routes = byRoute.size;
const compared = [...byRoute.values()].reduce(
  (n, bySite) => n + [...bySite.values()].reduce((m, s) => m + s.length, 0),
  0,
);
console.log(
  `check-site-scope: clean — ${compared} per-site page(s) across ${routes} route(s); ` +
    "no two sites share a content region carrying data" +
    (allowedEmpty.length > 0 ? ` (${allowedEmpty.length} empty-state collision(s) allowed).` : "."),
);
