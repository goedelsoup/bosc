/**
 * What search covers, declared (#1890, epic #1884 phase 6).
 *
 * The issue's acceptance criterion is that coverage be "a stated, tested fraction of content
 * routes, not an accident". Before it, coverage was 531 rows against 4,078 routes — 13% — and
 * nobody knew, because nothing measured it and nothing said what the target was. A number that
 * drifts silently is the same failure whether it reads 13% or 95%.
 *
 * So this module is the statement, in the same shape `RECORD_FACETS` (#1886) and `taxonomy.ts`
 * (#1892) use for their decisions: **every built route is expected to be searchable unless a
 * family below says otherwise, with a reason.** `scripts/check-routes.mjs` reads the emitted
 * `/search-coverage.json`, subtracts these families from the built routes, and fails the build if
 * the remainder isn't covered to {@link COVERAGE_FLOOR}. Adding a page therefore either makes it
 * searchable or makes someone write down why not.
 *
 * The verdicts are deliberately distinct — "there is nothing to find here" and "you will find this
 * by another name" are different claims, and only the second is a promise to the reader:
 *
 *  - `not-content` — not a reader destination at all (an auth callback, a dev gallery). Excluded
 *    from the denominator.
 *  - `represented` — real content, reachable through a row that IS indexed (a paginated page
 *    through its landing). Excluded from the denominator, and the note must name the row.
 *  - `gap` — real content that a reader would want and search does not reach. **Counted as a
 *    miss**, so it stays in the denominator and keeps the measured number honest. Listing a family
 *    here buys nothing but a name and a reason; the only way to raise the number is to fix it.
 *
 * That third verdict is the one that matters. It would have been easy to define every remaining
 * miss as "not content" and report 100%, which is precisely the kind of number this module exists
 * to stop.
 */

import { siteBase } from "./routes";
import { searchShardRefs } from "./search";
import { SITES } from "./sites";

/** How a family of built routes relates to the search index. */
export type CoverageVerdict = "not-content" | "represented" | "gap";

export interface CoverageFamily {
  /**
   * Anchored regular expression over the root-absolute route (leading slash, trailing slash,
   * no deploy base) — stored as a source string so the declaration survives the trip through
   * `/search-coverage.json` to the build-time guard.
   */
  pattern: string;
  label: string;
  verdict: CoverageVerdict;
  /** Why. For `represented`, name the indexed row that reaches this content. */
  note: string;
}

/**
 * The `/network/<id>` segments that DO ship a search shard, as a regex alternation.
 *
 * Derived from the registry through `siteBase`, never written out: the URL id differs from the
 * registry slug for the reference site (`lima` → `american-sugar-creek-allen-co`), and promoting a
 * site to `selectable` must not leave a hardcoded list behind describing the network as it was.
 * "Add a site by registering a profile; never re-hardcode a Lima/Allen-County value."
 */
const SHARDED_SITE_IDS = SITES.filter((s) => s.selectable)
  .map((s) => siteBase(s.slug).replace("/network/", ""))
  .join("|");

export const COVERAGE_FAMILIES: CoverageFamily[] = [
  {
    pattern: "^/network/[^/]+/site/documents/.*/page-\\d+/$",
    label: "Paginated document listings",
    verdict: "represented",
    note:
      "`page-2` and beyond hold no content their container landing doesn't reach — same rows, " +
      "next 150. The landing is indexed (kind `Production`), and every document on these pages is " +
      "indexed individually by its own handle, which is the better destination anyway.",
  },
  {
    pattern: "^/account(/.*)?$",
    label: "Account and auth flow",
    verdict: "not-content",
    note:
      "Sign-in, callback, sign-out, unsubscribe, and the admin console. Machinery, not record: " +
      "there is nothing here to find by searching for it, and the callback routes are only ever " +
      "arrived at by redirect.",
  },
  {
    pattern: "^/showcase/.*$",
    label: "Component showcases",
    verdict: "not-content",
    note:
      "Design galleries for the chart, icon, and teardown primitives — developer surface, " +
      "deliberately excluded from the sitemap already (`astro.config.ts`), and slated for " +
      "retirement in #1894.",
  },
  {
    pattern: "^/network/[^/]+/stories/(compose|mine|read|grab-demo)/$",
    label: "Story composer",
    verdict: "not-content",
    note:
      "The user-authored stories surface (#1090), dark behind `STORIES_ENABLED`. These are tools " +
      "for making a story, not published record; the story a site actually publishes is indexed " +
      "chapter by chapter.",
  },
  {
    pattern: "^/(pre-launch|locked-preview)/$",
    label: "Build-state landings",
    verdict: "not-content",
    note:
      "The pre-go-live landing and the locked-section preview. Both sit outside the nav and the " +
      "layout on purpose (`pre-launch` bypasses `Base.astro` entirely, and is one of the two " +
      "routes `check-routes.mjs` exempts from the breadcrumb trail).",
  },
  {
    pattern: "^/search/$",
    label: "The search page",
    verdict: "not-content",
    note: "Search finding itself is noise in every result set that contains the word.",
  },
  {
    pattern: `^/network/(?!${SHARDED_SITE_IDS})[^/]+/`,
    label: "A non-selectable site's own pages",
    verdict: "gap",
    note:
      "#1907. Search is sharded per SELECTABLE site, and a site can publish pages before it is " +
      "selectable — Findlay's `flagpole` story is eight routes of real, reachable prose today, " +
      "because story ROUTE emission gates on story registration, not on switchability (#1466). " +
      "So those pages exist, are linked from that site's home, and cannot be searched. Closing " +
      "this means either shipping a shard for every route-emitting site or folding their few " +
      "pages into the network shard; both are decisions about what the network advertises, not " +
      "about indexing, so it is named here rather than guessed at.",
  },
  {
    pattern: "^/network/[^/]+/(environment/(enclave|groundwater)|site/records/how-to-read|submit)/$",
    label: "Pages the nav model doesn't carry",
    verdict: "gap",
    note:
      "#1908. Real per-site pages reachable only from inside another page — the enclave and groundwater " +
      "reads, the record's how-to-read primer, the per-site submit form. Everything else at this " +
      "level is indexed by walking `siteTabs()`, on the rule that search reaches whatever the " +
      "chrome navigates to; these are the routes that rule exposes as missing FROM THE NAV. " +
      "Hardcoding them here would hide a wayfinding bug (#1893's territory) behind a search fix.",
  },
  {
    pattern: "^/(about/(data|sustainability|catalog|contributing)|privacy|network/connect)/$",
    label: "Network pages the nav model doesn't carry",
    verdict: "gap",
    note: "#1908, the same finding at the root: real pages, linked from body copy but not from the nav model.",
  },
];

/**
 * The fraction of content routes that must carry a search row.
 *
 * **98.1%, against 98.2% measured** — 3,782 of 3,853 content routes, up from 13%.
 *
 * A note on what closing #1906 bought, because the arithmetic is instructive. The `Peer-only wiki
 * entities` family was declared a `gap` on the theory that it "holds the measured number down until
 * it's fixed". It did not, and could not: the entities it named had **no route at all**, so they
 * were missing from the numerator and the denominator alike, and every entity route that did exist
 * was already indexed. Widening the wiki to the network union (`networkEntities`) added five routes
 * and five rows — it moved the fraction by two thousandths of a point. What it actually changed is
 * the record: five parties that existed in the graph and nowhere in the site now have a page, and
 * the family is gone rather than standing as a permanent asterisk. **A `gap` family can only
 * depress the number when the content it names is routed but unindexed** — worth remembering before
 * the next one is written down.
 *
 * The remaining shortfall is the three surviving `gap` families (#1907, #1908) plus the routes no
 * family has declared yet — the reports/exhibits/legal/people landings on the peers promoted since
 * #1890, and the wiki's own hypothesis and open-questions pages. Those are the ones a raise is
 * really waiting on.
 *
 * The margin is deliberately thin. A new page family that nobody indexes will breach this, which is
 * the intended pressure: adding routes should force a choice between indexing them and writing down
 * why not, and a floor with comfortable headroom would let coverage rot back toward 13% one page at
 * a time — which is precisely how it got there.
 */
export const COVERAGE_FLOOR = 0.981;

/**
 * A ceiling on the largest emitted shard, gzipped, in bytes.
 *
 * The reference build's shard carries every one of its ~3,500 documents. That is a lot of rows and
 * a small payload — the as-received folder trails repeat heavily and compress about ten to one —
 * but it is fetched by a reader who typed two characters, so it needs a watched number rather than
 * a hope. Well above the current worst; a regression like inlining document *body* text, or
 * dropping the `isRoutableDoc` filter, would land here first.
 */
export const SHARD_GZIP_BUDGET = 200 * 1024;

export interface CoverageDeclaration {
  families: CoverageFamily[];
  floor: number;
  shardGzipBudget: number;
  /**
   * Every shard the build is expected to emit, root-absolute. The post-build guard compares what
   * it finds against this exact set rather than counting: a shard that silently stops emitting for
   * one site leaves the others in place, so "at least two exist" would have passed while that
   * site's record became unsearchable — the very failure #1890 fixed.
   */
  shards: string[];
}

/** The declaration, as emitted to `/search-coverage.json` for the post-build guard. */
export function searchCoverage(): CoverageDeclaration {
  return {
    families: COVERAGE_FAMILIES,
    floor: COVERAGE_FLOOR,
    shardGzipBudget: SHARD_GZIP_BUDGET,
    shards: ["/search-index.json", ...searchShardRefs().map((r) => r.path)],
  };
}
