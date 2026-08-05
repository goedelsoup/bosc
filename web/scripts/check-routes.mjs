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
import { gzipSync } from "node:zlib";
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
 * this build met: every `/network/**` page carried ~206 KB of chrome before its first row, ~189 KB
 * of it the topbar site switcher — two implementations of the panel, each rendering all registered
 * sites twice so a CSS pivot could show one grouping. #1893 deleted three of those four copies.
 * Measuring above the floor still isolates what this phase governs, and keeps the guard honest
 * about page content when the chrome moves again; guard 7 below is what holds the chrome itself.
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

/**
 * The deploy budget (#1894). Cloudflare Pages caps a deployment at **20,000 files** and **25 MiB
 * per file**; there is no documented cap on the total, but upload time is real and the artifact is
 * what every deploy pushes.
 *
 * Measured at **3,962 files / 315 MB** when this landed, of which Lima is 3,394 files (86%) and
 * 280 MB (89%) — so "a site" costs anywhere between 3 files and 3,400 depending on its corpus, and
 * the only unit worth quoting headroom in is a Lima-sized one.
 *
 * Against the Pages cap that is **four more Lima-sized sites**. Against this budget it is about
 * two-thirds of one — deliberately. The budget is ~1.5× the current build and ~30% of the cap:
 * loose enough that ordinary work never touches it, tight enough that onboarding a site with a real
 * corpus raises it in a reviewed diff. That is the whole point of a budget under the limit; the
 * alternative is discovering the cap on a deploy, after review, on main.
 *
 * Raising these numbers is a legitimate edit — that is what a budget is for. Raising them without
 * saying what got bigger is not, which is why the guard prints the measurement either way.
 *
 * **This is the CI build, which is not byte-identical to production.** The offline gate reads the
 * committed fixtures under `web/sites/` (`WATERMARK_BUNDLE_DIR=sites`) while a deploy exports the
 * slugs in `astro.config.ts`, so per-site CONTENT can differ. The route SET is the same either way
 * (it comes from the `sites.ts` registry, not the bundle list), which is what the file count is
 * mostly made of — so the count is a faithful guard and the byte total is a close approximation.
 */
const FILE_BUDGET = 6_000;
const SIZE_BUDGET = 420 * 1024 * 1024;
/** Cloudflare's own per-file hard limit — not a budget, an upload failure. */
const PAGES_MAX_FILE_BYTES = 25 * 1024 * 1024;
/** Cloudflare's own per-deployment file cap, quoted so the headroom below is checkable. */
const PAGES_MAX_FILES = 20_000;

/**
 * Routes that ship with **no inbound internal link, on purpose** (#1894, guard 9).
 *
 * Everything else the build emits must be linked from some other built page. That is a deliberately
 * blunt rule, and the register is what keeps it honest: an entry has to say why the page exists
 * without a way in, and the guard fails if a declared pattern stops matching anything — so a
 * decision can't outlive the route it was made about.
 *
 * This is NOT the same register as `nav.ts`'s contextual leaves. Those ARE linked, from body copy
 * rather than from the chrome, and guard 6b proves it. These are linked from nothing at all.
 *
 * A future entrant worth naming now: a **`hidden` story** (#1256) publishes routes and advertises
 * nothing — "reachable by direct URL, just not advertised" — so its chapters would land here. None
 * is registered today, and writing a speculative pattern would be asserting a decision nobody has
 * made. If one is registered, this guard will fail, and the right fix is a line here saying so.
 */
const UNLINKED_BY_DESIGN = [
  {
    pattern: /^account(\/|$)/,
    why:
      "The auth flow. Sign-in, the OAuth callback, sign-out, unsubscribe and the admin console are " +
      "arrived at by redirect, from an email, or by an operator who already knows the address — " +
      "there is nothing to link them FROM, and a public link to a sign-out is not a feature.",
  },
  {
    pattern: /^pre-launch$/,
    why:
      "The pre-go-live landing. Unlinked is the point: `functions/_middleware.ts` rewrites `/` to it " +
      "when `preLaunch` is on in deploy/features.yaml and redirects every other route to `/`, so it " +
      "is the only page a reader sees. It must ship even while the flag is off, or flipping the " +
      "switch would serve a 404 as the front door.",
  },
];

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

// ------------------------------------------------ 6. search coverage (#1890)
//
// "Search coverage is a stated, tested fraction of content routes, not an accident." Before #1890
// the index held 531 rows against 4,078 routes — 13% — and nothing measured it, so nothing said so.
//
// The statement lives in `packages/core/src/searchCoverage.ts` and ships as `/search-coverage.json`;
// this reads it out of the build rather than keeping a second copy, for the same reason this file
// doesn't reimplement `documentId`. Content routes are the built routes minus the families declared
// `not-content` or `represented`; a family declared `gap` stays in the denominator on purpose, so a
// known miss lowers the number instead of being defined away.
function checkSearchCoverage() {
  const declPath = join(DIST, "search-coverage.json");
  if (!existsSync(declPath)) {
    failures.push("no search-coverage.json in the build — the coverage declaration didn't emit");
    return;
  }
  const { families, floor, shardGzipBudget, shards } = JSON.parse(readFileSync(declPath, "utf-8"));

  // Every shard the declaration says this build owes: the network-global one at the root, plus one
  // per site that publishes rows of its own — the selectable sites and, since #1907, any peer
  // publishing a held walk. Compared as a SET, not a count — one site's shard silently ceasing to
  // emit leaves the others in place, so "at least two exist" would pass while that site's record
  // went unsearchable, which is exactly the state #1890 fixed.
  const missing = shards.filter((s) => !existsSync(join(DIST, s.replace(/^\//, ""))));
  if (missing.length > 0) {
    failures.push(
      `${missing.length} declared search shard(s) missing from the build — that site's record is ` +
        `unsearchable:\n${missing.map((s) => `      ${s}`).join("\n")}`,
    );
    return;
  }
  const shardPaths = shards.map((s) => join(DIST, s.replace(/^\//, "")));

  const indexed = new Set();
  let rows = 0;
  for (const p of shardPaths) {
    const raw = readFileSync(p);
    const shard = JSON.parse(raw.toString("utf-8"));
    if (shard.length === 0) {
      failures.push(`${relative(DIST, p)} is empty — every built site must ship a non-empty index`);
    }
    rows += shard.length;
    // A row's URL may carry an anchor (a section's TOC entry, an exhibit); the route is the part
    // before it. Normalized with a trailing slash to match `routes()`.
    for (const d of shard) {
      const path = d.url.split("#")[0].split("?")[0];
      indexed.add(path.endsWith("/") ? path : `${path}/`);
    }
    const gz = gzipSync(raw).length;
    if (gz > shardGzipBudget) {
      failures.push(
        `${relative(DIST, p)} is ${(gz / 1024).toFixed(0)} KB gzipped, over the ` +
          `${(shardGzipBudget / 1024).toFixed(0)} KB shard budget — a reader who typed two ` +
          "characters pays for this",
      );
    }
  }

  // A `gap` family stays in the denominator — that is what makes it a gap rather than an excuse.
  const excluded = families.filter((f) => f.verdict !== "gap").map((f) => new RegExp(f.pattern));
  const content = all.map(({ route }) => (route === "" ? "/" : `/${route}/`));
  const denominator = content.filter((r) => !excluded.some((re) => re.test(r)));
  // An empty denominator means the exclusions swallowed the build (a `.*` pattern would do it), and
  // 0/0 is NaN — which compares false against the floor and would report green while asserting
  // nothing at all. The guard has to fail loudly on the one input that makes it vacuous.
  if (denominator.length === 0) {
    failures.push(
      "search coverage has no content routes to measure — the declared families exclude every " +
        `built route (${all.length.toLocaleString("en-US")} of them). Check the patterns in ` +
        "packages/core/src/searchCoverage.ts.",
    );
    return;
  }
  const covered = denominator.filter((r) => indexed.has(r));
  const fraction = covered.length / denominator.length;

  if (fraction < floor) {
    const missed = denominator.filter((r) => !indexed.has(r));
    failures.push(
      `search covers ${(fraction * 100).toFixed(1)}% of ${denominator.length.toLocaleString("en-US")} ` +
        `content routes, under the declared ${(floor * 100).toFixed(0)}% floor. ` +
        `${missed.length.toLocaleString("en-US")} uncovered — index them, or declare the family in ` +
        "packages/core/src/searchCoverage.ts with a reason:\n" +
        missed
          .slice(0, 8)
          .map((r) => `      ${r}`)
          .join("\n"),
    );
  } else {
    const gaps = families.filter((f) => f.verdict === "gap").length;
    console.log(
      `check-routes: search covers ${(fraction * 100).toFixed(1)}% of ` +
        `${denominator.length.toLocaleString("en-US")} content routes · ` +
        `${rows.toLocaleString("en-US")} rows across ${shardPaths.length} shards · ` +
        `${gaps} declared gap${gaps === 1 ? "" : "s"}`,
    );
  }
}
checkSearchCoverage();

// ------------------------------------------- 6b. contextual leaves are actually linked (#1908)
//
// `nav.ts` lets a page opt out of the chrome by declaring itself a contextual leaf — real content
// reached from another page's body copy, with the carrier and the reason written down. That is a
// legitimate answer to "every built page must be reachable", and #1893 spent a whole issue proving
// that not everything belongs in a menu.
//
// It is also the easiest claim in the codebase to make falsely. "Reached from the records index"
// stays true only until somebody rewrites that paragraph, and nothing about the declaration would
// change — so the register would go on asserting reachability for a page that had become an orphan,
// which is worse than the silence it replaced, because now it reads as checked.
//
// So it is checked, against the built HTML rather than the source: at least one OTHER page must
// emit an href to the leaf. Deliberately not "the page named in `via`" — `via` is prose describing
// a carrier that may be a component rendered on many routes, and pinning it to one route would fail
// for the right reason on the wrong day. What must not happen is nobody linking it at all.
function checkContextualLeaves() {
  const declPath = join(DIST, "search-coverage.json");
  if (!existsSync(declPath)) return; // already reported by checkSearchCoverage
  const { contextual } = JSON.parse(readFileSync(declPath, "utf-8"));
  if (!Array.isArray(contextual) || contextual.length === 0) {
    failures.push(
      "search-coverage.json declares no contextual leaves — `contextualLeaves()` emitted nothing, " +
        "so this guard is asserting reachability for an empty set",
    );
    return;
  }
  // `href="…<leaf>"` with an optional trailing slash and an optional query/fragment: the submit
  // leaf is deep-linked as `…/submit?ref_kind=place&amp;…` from every record page that offers a
  // correction. Prefixed loosely so a non-empty deploy base still matches.
  const linkers = contextual.map((leaf) => ({
    ...leaf,
    re: new RegExp(`href="[^"]*${leaf.href.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}/?(?:["?#])`),
  }));
  const found = new Map(contextual.map((leaf) => [leaf.href, 0]));
  for (const { file, route } of all) {
    const html = readFileSync(file, "utf-8");
    for (const leaf of linkers) {
      // Its own page linking itself proves nothing — `/about/sustainability`'s footer used to be
      // the only thing pointing at `/about/data`, which is how that page went unreachable.
      if (`/${route}` === leaf.href || `/${route}/` === `${leaf.href}/`) continue;
      if (leaf.re.test(html)) found.set(leaf.href, found.get(leaf.href) + 1);
    }
  }
  const orphaned = contextual.filter((leaf) => found.get(leaf.href) === 0);
  if (orphaned.length > 0) {
    failures.push(
      `${orphaned.length} contextual leaf/leaves are linked from no other built page — they are ` +
        "orphans, not contextual. Restore the link, or drop the declaration in " +
        `packages/core/src/nav.ts:\n${orphaned.map((l) => `      ${l.href} — via ${l.via}`).join("\n")}`,
    );
    return;
  }
  console.log(
    `check-routes: ${contextual.length} contextual leaf/leaves carried by ` +
      `${contextual.map((l) => found.get(l.href)).join(" / ")} page(s)`,
  );
}
checkContextualLeaves();

// -------------------------------------- 7. one site switcher, one copy of the registry (#1893)
//
// The acceptance criterion of the nav diet: "exactly one site-switcher implementation in the built
// HTML". It has to be asserted against `dist/` because the failure was invisible in the source —
// two panels were rendered deliberately, with CSS and a `localStorage` flag choosing between them
// at runtime, so both were correct-looking code and both shipped on all 4,078 pages.
//
// Two things are counted, because the duplication had two independent axes and killing one would
// have left the other: how many PANELS a page carries, and how many times the registry is rendered
// INSIDE one. A panel used to hold every site twice — once per State/Basin lens — so "one panel"
// alone would still have allowed 76 rows for 38 sites. Rows carry `data-place`, so the second
// question is answerable without knowing the registry: a page renders the network once when its
// row count equals its distinct-place count.
{
  const PANEL = /<div class="switcher-menu"/g;
  const ROW = /class="switcher-row[ "]/g;
  const PLACE = /data-place="([^"]*)"/g;
  // The retired flag and its dead panel. A page that still names any of these is one where the
  // deletion was reverted or half-applied.
  const RETIRED = ["switcher-menu-v2", "switcher-row-v2", "site-selector-v2", "data-ssv2"];

  const wrongPanelCount = [];
  const duplicated = [];
  const retired = [];
  let rowsPerPage = 0;
  let chromed = 0;
  for (const { file, route } of all) {
    const html = readFileSync(file, "utf-8");
    // `/pre-launch` deliberately bypasses `Base.astro` and ships no chrome at all — no topbar,
    // so no switcher to count. Keyed off the topbar rather than a route list so a future
    // chrome-less page is exempt by being chrome-less, not by being remembered here.
    if (!html.includes('class="topbar')) continue;
    chromed++;
    const panels = (html.match(PANEL) ?? []).length;
    if (panels !== 1) wrongPanelCount.push(`/${route} — ${panels} panel(s)`);
    const rows = (html.match(ROW) ?? []).length;
    const places = new Set([...html.matchAll(PLACE)].map((m) => m[1]));
    if (rows !== places.size) duplicated.push(`/${route} — ${rows} rows for ${places.size} sites`);
    rowsPerPage = Math.max(rowsPerPage, rows);
    const found = RETIRED.filter((token) => html.includes(token));
    if (found.length > 0) retired.push(`/${route} — ${found.join(", ")}`);
  }
  const report = (list, what) => {
    if (list.length === 0) return;
    failures.push(
      `${list.length} page(s) ${what}:\n` +
        list
          .slice(0, 5)
          .map((r) => `      ${r}`)
          .join("\n"),
    );
  };
  report(wrongPanelCount, "without exactly one site-switcher panel");
  report(duplicated, "rendering the site registry more than once in the switcher");
  report(retired, "still carrying the retired v2-switcher flag");
  // A build with no chrome at all would pass every assertion above by having nothing to check.
  if (chromed === 0) failures.push("no built page carries the topbar — the chrome assertions are vacuous");
  console.log(
    `check-routes: one switcher panel on ${chromed.toLocaleString("en-US")} chromed pages · ` +
      `${rowsPerPage} site rows each`,
  );
}

// ------------------------------------------------- 8. the deploy budget (#1894)
//
// "A CI check asserts file count and artifact size against a committed budget." The cap this is
// really about is Cloudflare's 20,000 files per deployment, which the build has no way of noticing
// until a deploy fails — and a deploy fails after review, after merge, on main.
//
// Counted over EVERY file in `dist/`, not just the routes: the `_astro` bundle, the search shards,
// the per-site catalogs and the `public/` passthrough all upload, and the cap does not care which
// of them is a page. `du` and `find` on the same tree are the reproduction.
{
  const files = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir)) {
      const p = join(dir, entry);
      const s = statSync(p);
      if (s.isDirectory()) walk(p);
      else files.push({ path: p, size: s.size });
    }
  };
  walk(DIST);
  const bytes = files.reduce((n, f) => n + f.size, 0);
  const mb = (n) => `${(n / 1024 / 1024).toFixed(0)} MB`;

  if (files.length > FILE_BUDGET) {
    failures.push(
      `${files.length.toLocaleString("en-US")} files in ${DIST}/, over the ` +
        `${FILE_BUDGET.toLocaleString("en-US")}-file budget (Cloudflare Pages caps a deployment at ` +
        `${PAGES_MAX_FILES.toLocaleString("en-US")}). Either the build grew a route family it ` +
        "shouldn't have, or the network gained a site and the budget in check-routes.mjs needs " +
        "raising — with a note saying which.",
    );
  }
  if (bytes > SIZE_BUDGET) {
    failures.push(
      `${DIST}/ is ${mb(bytes)}, over the ${mb(SIZE_BUDGET)} artifact budget. Every deploy uploads ` +
        "this. Find what got bigger before raising the number.",
    );
  }
  // Not a budget — Cloudflare refuses the upload outright above this.
  const oversize = files.filter((f) => f.size > PAGES_MAX_FILE_BYTES);
  if (oversize.length > 0) {
    failures.push(
      `${oversize.length} file(s) over the Pages ${mb(PAGES_MAX_FILE_BYTES)} per-file limit — the ` +
        `deploy will be REJECTED, not merely slow:\n` +
        oversize
          .slice(0, 5)
          .map((f) => `      ${mb(f.size)}  ${relative(DIST, f.path)}`)
          .join("\n"),
    );
  }
  const headroom = Math.floor((PAGES_MAX_FILES - files.length) / Math.max(1, files.length));
  console.log(
    `check-routes: deploy ${files.length.toLocaleString("en-US")} files · ${mb(bytes)} · ` +
      `budget ${FILE_BUDGET.toLocaleString("en-US")} / ${mb(SIZE_BUDGET)} · ` +
      `${headroom} more build(s) this size fit under the Pages ${PAGES_MAX_FILES.toLocaleString("en-US")}-file cap`,
  );
}

// ------------------------------- 9. every built route is reachable from another page (#1894)
//
// The acceptance criterion: "no orphaned non-auth route in the production build". Eight non-auth
// routes had zero inbound links when #1894 was written and fifty-five by the time it was worked —
// the difference is not rot, it is two sites being promoted, because most of them were routes a
// gate had already closed. `site/index.astro` stopped drawing a locked facet's door (#1886) and
// `search.ts` stopped indexing its row (#1908), and both were right; what neither could do is stop
// the page from being built. A lock nobody can reach asks nobody for anything.
//
// So this is the third consumer of every gate in `readiness.ts`, asserted from the outside: if the
// door is gone and the row is gone, the route has to be gone too. It is also the only guard that
// can catch the reverse — a real page that quietly loses its last link.
//
// `check-links.mjs` proves every href RESOLVES; this proves every route is POINTED AT. They are
// opposite directions over the same edge set and neither implies the other.
{
  // Both spellings of every route: Astro emits a route whose param carries a URL-special character
  // (the as-received public-record filenames with `#`, `&`, `%`) percent-encoded in the directory
  // name, while most hrefs are written literally. Indexing both ends the encoding question here
  // rather than at every lookup.
  const key = (r) => (r.endsWith("/") ? r.slice(0, -1) : r);
  const inbound = new Map();
  const alias = new Map();
  for (const { route } of all) {
    const k = key(route);
    inbound.set(k, 0);
    alias.set(k, k);
  }
  // Decoded spellings in a SECOND pass, and never over a real route: if some site ever emits both
  // `A %26 B` and `A & B`, the literal directory has to keep its own name, and only the spelling
  // nothing occupies becomes an alias.
  for (const k of [...inbound.keys()]) {
    try {
      const decoded = decodeURIComponent(k);
      if (decoded !== k && !alias.has(decoded)) alias.set(decoded, k);
    } catch {
      // A malformed escape sequence is not decodable; the as-written key still stands.
    }
  }

  // The same entity decode `check-links.mjs` does, and load-bearing for the same reason: the PRR
  // production tree has directories like `Contracts & Agreements`, whose href is emitted `&#38;`.
  // Undecoded, that `#` reads as a fragment delimiter and truncates the target to `Contracts &` —
  // so the link would go uncounted and the container it points at would be reported an orphan.
  // Numeric/named first, `&amp;` LAST, so `&amp;#38;` isn't decoded twice.
  const decodeEntities = (s) =>
    s
      .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
      .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(Number.parseInt(h, 16)))
      .replace(/&quot;/g, '"')
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&amp;/g, "&");

  const EXTERNAL = /^(https?:|mailto:|tel:|data:|javascript:|#)/i;
  for (const { file, route } of all) {
    const html = readFileSync(file, "utf-8");
    const self = key(route);
    for (const m of html.matchAll(/href="([^"]*)"/g)) {
      const raw = decodeEntities(m[1].trim());
      if (!raw || EXTERNAL.test(raw) || raw.startsWith("//") || !raw.startsWith("/")) continue;
      const target = key(raw.split(/[?#]/)[0].replace(/^\//, ""));
      let k = alias.get(target);
      if (k === undefined) {
        try {
          k = alias.get(decodeURIComponent(target));
        } catch {
          k = undefined;
        }
      }
      // A page linking ITSELF proves nothing — the canonical link, the trail's own leaf and the
      // switcher's current-site row all point home on every page, which would make every route
      // its own referrer and this guard vacuous.
      if (k === undefined || k === self) continue;
      inbound.set(k, inbound.get(k) + 1);
    }
  }

  const orphans = [...inbound]
    .filter(([, n]) => n === 0)
    .map(([r]) => r)
    .sort();
  const undeclared = orphans.filter((r) => !UNLINKED_BY_DESIGN.some((d) => d.pattern.test(r)));
  if (undeclared.length > 0) {
    failures.push(
      `${undeclared.length} built route(s) are linked from no other page. Link them, stop building ` +
        "them, or declare them in check-routes.mjs's UNLINKED_BY_DESIGN with the reason:\n" +
        undeclared
          .slice(0, 10)
          .map((r) => `      /${r}`)
          .join("\n"),
    );
  }
  // A declaration that no longer matches an orphan is a decision about a route that has since been
  // linked or deleted. Left standing it would silently excuse the NEXT route that matches it.
  const stale = UNLINKED_BY_DESIGN.filter((d) => !orphans.some((r) => d.pattern.test(r)));
  if (stale.length > 0) {
    failures.push(
      `${stale.length} UNLINKED_BY_DESIGN entr(ies) match no orphan in this build — the route is ` +
        `linked or gone, so the exemption should be too:\n` +
        stale.map((d) => `      ${d.pattern}`).join("\n"),
    );
  }
  if (undeclared.length === 0 && stale.length === 0) {
    console.log(
      `check-routes: every route reachable · ${orphans.length} declared unlinked ` +
        `(${UNLINKED_BY_DESIGN.length} rule${UNLINKED_BY_DESIGN.length === 1 ? "" : "s"})`,
    );
  }
}

if (failures.length === 0) {
  console.log(`check-routes: OK — ${all.length.toLocaleString("en-US")} routes within budget.`);
  process.exit(0);
}

console.error(`check-routes: ${failures.length} failure(s):`);
for (const f of failures) console.error(`  ✗ ${f}`);
process.exit(1);
