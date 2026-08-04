// Route-shape budgets for the built site (#1887 phase 3, extended by #1889 phase 5).
//
// `check-links.mjs` proves every emitted href resolves. This asserts the things those phases
// bought and that nothing later should quietly give back: routes stay shallow, the corpus's
// machine exhaust stays out of the URL space, listing pages stay bounded, every page tells a
// reader where it sits, and every document that has a page still has exactly one.
//
// Reads only `dist/` — no bundle resolution, and deliberately no second implementation of
// `documentId`. The handle→page mapping is already proved end-to-end by `check-links.mjs`
// (every `/doc/<id>/` href emitted by a listing must resolve) and by the golden vectors in
// `packages/core/src/__fixtures__/document-id-vectors.json`, which are asserted from both Node
// and pytest. What's left for this script is counting and shape, which need neither.
//
// Run after `astro build`:  node scripts/check-routes.mjs  (pnpm run check:routes)

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

// Overridable so the negative cases can be exercised against a synthetic tree — a budget guard
// nobody has watched fail is only a guess that it works.
const DIST = process.env.CHECK_ROUTES_DIST || "dist";

/** Acceptance criterion (#1887): no route deeper than this below a site root, `/network/<slug>/`. */
const MAX_DEPTH_BELOW_SITE_ROOT = 6;

/**
 * Budget for a document-layer page's OWN content, measured above the shared site chrome.
 *
 * Not a total-page budget. The issue asked for "no index.html over ~250 KB", which no page in
 * this build meets and none can until #1893: every `/network/**` page carries ~206 KB of chrome
 * before its first row, ~189 KB of it the topbar site switcher (two implementations × two
 * groupings of all registered sites). Measuring above the floor isolates what this phase
 * actually governs, and the guard tightens on its own the moment the chrome shrinks.
 *
 * Current worst is ~168 KB (the sanitary production's listing pages, 150 rows of long
 * as-received folder trails), so this leaves modest headroom and will catch a regression like
 * un-paginating a listing or re-inlining the catalog.
 */
const DOC_CONTENT_BUDGET = 200 * 1024;

/**
 * Filenames that must never appear as a URL segment. These are files a records custodian swept
 * up with the responsive records — Windows thumbnail caches and the sidecars Office writes when
 * a document is saved as a web page. They stay in the corpus, stay listed in their production's
 * manifest, and stay fetchable at `/api/doc/<rel>`; they are simply not pages. Mirrors
 * `packages/core/src/docRouting.ts` — that module decides, this proves the build obeyed it.
 */
const OS_ARTIFACT_SEGMENT = /^(thumbs\.db|\.ds_store|desktop\.ini)$/i;
const SIDECAR_DIR_SEGMENT = /_files$/;
const INLINE_IMAGE_SEGMENT = /^image[0-9a-f]{4,}\.(?:png|jpe?g|gif|bmp)$/i;

/**
 * Routes that legitimately ship without a breadcrumb trail (#1889).
 *
 * Two, and both for the same reason — there is nothing above them. `/` IS the root of the URL
 * space, so its trail would be a link to itself; `/pre-launch` is the standalone pre-go-live
 * landing, deliberately outside `Base.astro` and the whole data nav (see its own header comment).
 * Anything else with no trail is a page a reader can land on from search or a citation with no
 * way to tell where they are, which is the condition this phase exists to remove.
 */
const TRAILLESS_ROUTES = new Set(["", "pre-launch"]);

if (!existsSync(DIST)) {
  console.error(`check-routes: no ${DIST}/ — run \`astro build\` first.`);
  process.exit(2);
}

/** Every index.html under dist/, as a dist-relative route path (no trailing /index.html). */
function routes() {
  const out = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      if (statSync(p).isDirectory()) walk(p);
      else if (entry === "index.html") out.push(p);
    }
  };
  walk(DIST);
  return out.map((p) => ({ file: p, route: relative(DIST, p).replace(/\/?index\.html$/, "") }));
}

const failures = [];
const all = routes();

// ---------------------------------------------------------------- 1. depth
{
  const deep = [];
  for (const { route } of all) {
    const m = /^network\/[^/]+\/(.+)$/.exec(route);
    if (!m) continue; // network-global page, not under a site root
    const depth = m[1].split("/").length;
    if (depth > MAX_DEPTH_BELOW_SITE_ROOT) deep.push({ depth, route });
  }
  if (deep.length > 0) {
    deep.sort((a, b) => b.depth - a.depth);
    failures.push(
      `${deep.length} route(s) deeper than ${MAX_DEPTH_BELOW_SITE_ROOT} below a site root:\n` +
        deep
          .slice(0, 5)
          .map((d) => `      ${d.depth}  /${d.route}`)
          .join("\n"),
    );
  }
}

// -------------------------------------------- 2. no OS artifact in the URL space
{
  const offenders = [];
  for (const { route } of all) {
    for (const segment of route.split("/")) {
      if (
        OS_ARTIFACT_SEGMENT.test(segment) ||
        SIDECAR_DIR_SEGMENT.test(segment) ||
        INLINE_IMAGE_SEGMENT.test(segment)
      ) {
        offenders.push(`/${route}`);
        break;
      }
    }
  }
  if (offenders.length > 0) {
    failures.push(
      `${offenders.length} route(s) built from a non-evidentiary filename:\n` +
        offenders
          .slice(0, 5)
          .map((r) => `      ${r}`)
          .join("\n"),
    );
  }
}

// ------------------------------------------- 3. document-layer page-weight budget
{
  const sitePages = all.filter(({ route }) => route.startsWith("network/"));
  // The shared chrome floor, measured rather than hardcoded, so the budget tightens on its own
  // when #1893 shrinks the chrome.
  //
  // A LOW PERCENTILE, not the minimum: every `/network/**` page carries the same chrome, so the
  // smallest one estimates it well — until a single unusually small page exists, at which point
  // `min` collapses the floor and every document page looks megabytes over budget. That is a
  // false CI failure waiting for whoever adds the next lightweight route, and it showed up the
  // first time this guard was exercised against a synthetic tree.
  const sizes = sitePages.map(({ file }) => statSync(file).size).sort((a, b) => a - b);
  const floor = sizes[Math.floor(sizes.length * 0.1)] ?? 0;
  const docPages = sitePages.filter(
    ({ route }) => route.includes("/site/documents") || /\/doc\/[^/]+$/.test(route),
  );
  const over = docPages
    .map(({ file, route }) => ({ route, content: statSync(file).size - floor }))
    .filter((p) => p.content > DOC_CONTENT_BUDGET)
    .sort((a, b) => b.content - a.content);
  if (over.length > 0) {
    failures.push(
      `${over.length} document page(s) over the ${(DOC_CONTENT_BUDGET / 1024).toFixed(0)} KB ` +
        `content budget (measured above a ${(floor / 1024).toFixed(0)} KB site-chrome floor):\n` +
        over
          .slice(0, 5)
          .map((p) => `      ${(p.content / 1024).toFixed(0)} KB  /${p.route}`)
          .join("\n"),
    );
  }
  console.log(
    `check-routes: chrome floor ${(floor / 1024).toFixed(0)} KB · ` +
      `${docPages.length.toLocaleString("en-US")} document-layer pages · ` +
      `largest content ${(Math.max(0, ...docPages.map(({ file }) => statSync(file).size - floor)) / 1024).toFixed(0)} KB`,
  );
}

// -------------------------------------------- 4. every page carries a breadcrumb trail
//
// The acceptance criterion of #1889, proved against the build rather than the source: three of
// ninety-nine templates used to render a trail, and the rest left a deep-landing reader — from
// search, from `/ask`, from a study citation — with the browser back button as their only way up.
// `trailCoverage.test.ts` proves each template's route is DECLARED; this proves the HTML shipped.
//
// The BreadcrumbList JSON-LD half is asserted only when the build has a deploy origin. The
// structured-data blocks all key off `Astro.site`, which is set from `SITE_URL` in the Pages
// workflow and is undefined locally and in CI — so requiring it unconditionally would fail every
// offline build. `sawCanonical` reads that off the emitted canonical link rather than the
// environment, so the guard turns itself on in exactly the builds that can satisfy it.
{
  // Whether the build has an origin is decided from the WHOLE pass, not from a sample. Sampling
  // one page looks safe — `SEO.astro` emits the canonical for every page it renders — but
  // `/pre-launch` deliberately bypasses `Base.astro` entirely and so emits none, and `routes()`
  // walks `readdirSync` unsorted. A sample that happened to land on it would silently disarm the
  // whole BreadcrumbList assertion in a production build, which is the one place it has to hold.
  // So candidates are collected unconditionally in the single pass and reported only if an origin
  // turned up anywhere — one read per file either way, and no dependence on directory order.
  let sawCanonical = false;
  const missingTrail = [];
  const ldCandidates = [];
  let trailed = 0;
  for (const { file, route } of all) {
    const html = readFileSync(file, "utf-8");
    if (!sawCanonical && html.includes('<link rel="canonical"')) sawCanonical = true;
    if (TRAILLESS_ROUTES.has(route)) continue;
    if (!html.includes('<nav class="trail"')) missingTrail.push(`/${route}`);
    else {
      trailed++;
      if (!html.includes('"BreadcrumbList"')) ldCandidates.push(`/${route}`);
    }
  }
  const missingLd = sawCanonical ? ldCandidates : [];
  const report = (list, what) => {
    if (list.length === 0) return;
    failures.push(
      `${list.length} route(s) ${what}:\n` +
        list
          .slice(0, 5)
          .map((r) => `      ${r}`)
          .join("\n"),
    );
  };
  report(missingTrail, "with no breadcrumb trail");
  report(missingLd, "with a visible trail but no BreadcrumbList JSON-LD");
  console.log(
    `check-routes: ${trailed.toLocaleString("en-US")} routes carry a breadcrumb trail · ` +
      `BreadcrumbList ${sawCanonical ? "asserted" : "skipped (no SITE_URL in this build)"}`,
  );
}

// ------------------------------- 5. one page per routable document, and no orphans
//
// The strongest invariant the build can assert about the handle scheme without recomputing it:
// a site's catalog says how many of its files are routable, and exactly that many permalink
// pages must exist. Too few means a cited document lost its page; too many means the routing
// filter let machine exhaust back into the URL space.
function checkPermalinkCoverage() {
  for (const { route } of all) {
    const m = /^network\/([^/]+)\/site\/documents$/.exec(route);
    if (!m) continue;
    const site = m[1];
    const catalogPath = join(DIST, "network", site, "site", "documents", "catalog.json");
    if (!existsSync(catalogPath)) {
      failures.push(`${site}: documents landing built but no catalog.json beside it`);
      continue;
    }
    const { rows } = JSON.parse(readFileSync(catalogPath, "utf-8"));
    // `x` carries the non-routable reason; "" means this file gets a page.
    const expected = rows.filter((r) => r.x === "").length;
    const docDir = join(DIST, "network", site, "doc");
    const built = existsSync(docDir)
      ? readdirSync(docDir).filter((d) => existsSync(join(docDir, d, "index.html"))).length
      : 0;
    if (built !== expected) {
      failures.push(
        `${site}: ${expected.toLocaleString("en-US")} routable documents but ` +
          `${built.toLocaleString("en-US")} permalink page(s) — ` +
          (built < expected ? "a cited document lost its page" : "a non-routable file gained one"),
      );
    } else {
      console.log(
        `check-routes: ${site} — ${built.toLocaleString("en-US")} documents, ` +
          `${(rows.length - expected).toLocaleString("en-US")} catalogued but not routed`,
      );
    }
  }
}
checkPermalinkCoverage();

if (failures.length === 0) {
  console.log(`check-routes: OK — ${all.length.toLocaleString("en-US")} routes within budget.`);
  process.exit(0);
}

console.error(`check-routes: ${failures.length} failure(s):`);
for (const f of failures) console.error(`  ✗ ${f}`);
process.exit(1);
