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

import { runWithSite } from "./bundle";
import { contextualLeaves } from "./nav";
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
 * A held story's **interior** routes were declared here as a `represented` family (#1907), on the
 * reading that a `comingSoon` story serves the identical `StoryComingSoon` interstitial at its
 * contents page and every chapter, so indexing all eight of Findlay's would put eight
 * near-identical "coming soon" results in one result set. That was true and it is why the family
 * existed.
 *
 * #1894 removed the routes instead, which is the stronger form of the same argument. Eleven interior
 * routes across Findlay and Fort Wayne were built, excused from the search denominator here, and
 * linked from nothing — the walk's own chapter list is not rendered while it is held, the catalog
 * drops its atoms (`catalogBuild.ts`) and a record shows no walk chip (`recordBlock.ts`). A route
 * that is unreachable AND unindexed is not represented by anything; it is an orphan with a
 * declaration in front of it. The story ROOT still builds, still carries the interstitial, and is
 * still indexed as `<title> — coming soon` (`storyRows`), which is what a reader searching the
 * walk's name was ever going to find.
 *
 * Nothing replaces this in the denominator: with the interiors unbuilt there is nothing to excuse,
 * and if they ever come back unindexed the coverage number will fall and say so — which is the
 * behaviour a `represented` family was suppressing.
 *
 * The `hidden` story (#1256) case is unchanged and still deliberately undeclared: it publishes
 * routes and advertises nothing, so its chapters would surface as undeclared misses and the build
 * would say so. See `check-routes.mjs` guard 9, which is where that decision now has to be written
 * down if a hidden story is ever registered.
 */

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
    pattern: "^/network/[^/]+/stories/(compose|mine|read|grab-demo)/$",
    label: "Walk composer",
    verdict: "not-content",
    note:
      "The user-authored stories surface (#1090), dark behind `STORIES_ENABLED`. These are tools " +
      "for making a story, not published record; the story a site actually publishes is indexed " +
      "chapter by chapter. Since #1894 they are built only when the flag is ON, so today this " +
      "family matches nothing — it is kept for the build that flips it, not as a live exclusion.",
  },
  {
    pattern: "^/pre-launch/$",
    label: "The pre-launch landing",
    verdict: "not-content",
    note:
      "The pre-go-live landing the Pages middleware rewrites `/` to when `preLaunch` is on. It " +
      "sits outside the nav and the layout on purpose — it bypasses `Base.astro` entirely, and is " +
      "one of the two routes `check-routes.mjs` exempts from the breadcrumb trail. The component " +
      "galleries and the locked preview used to be declared here beside it; #1894 retired them " +
      "from the production artifact instead, which is the stronger answer — an unbuilt route " +
      "needs no exclusion.",
  },
  {
    pattern: "^/search/$",
    label: "The search page",
    verdict: "not-content",
    note: "Search finding itself is noise in every result set that contains the word.",
  },
  {
    pattern: "^/network/[^/]+/submit/$",
    label: "The site-tier submit form",
    verdict: "represented",
    note:
      "#1908. The same `<SubmitForm>` the network-tier `/submit` renders, at a site-rooted address " +
      "so a correction raised inside a site keeps that site's chrome and carries the `?ref_kind=` " +
      "of the record being corrected. That row IS indexed (`Submit a lead`, kind `Page`, off the " +
      "platform cluster), and it is the destination a reader searching 'submit' means; four " +
      "site-rooted copies of one form would be three near-identical results. The route is declared " +
      "a contextual leaf in `nav.ts` — reachable, deliberately not in the chrome.",
  },
];

/**
 * The fraction of content routes that must carry a search row.
 *
 * **98.85%, against 98.905% measured** — 3,794 of 3,836 content routes, up from 13% before #1890.
 *
 * Four closures moved it since, and their arithmetic is worth keeping side by side, because it is
 * four different kinds of arithmetic.
 *
 * What closing **#1907** bought is the counter-example to the #1906 note below. That family named
 * eight routes that were **routed and unindexed** — Findlay's held `flagpole` walk — so it really
 * was holding the number down, and closing it moved the fraction a third of a point: two story
 * roots became rows, and eleven interior routes left the denominator as `represented`. Eleven, not
 * seven, because the fix keyed off what a story *publishes* rather than off `selectable`, and the
 * same rule reached Fort Wayne's held `project-zodiac` — five routes on a SELECTABLE site that were
 * missing for exactly the same reason. That the fix landed on a site the issue never mentioned is
 * the evidence that `selectable` was never the axis.
 *
 * What closing **#1906** bought is instructive in the other direction. The `Peer-only wiki entities`
 * family was declared a `gap` on the theory that it "holds the measured number down until it's
 * fixed". It did not, and could not: the entities it named had **no route at all**, so they were
 * missing from the numerator and the denominator alike, and every entity route that did exist was
 * already indexed. Widening the wiki to the network union (`networkEntities`) added five routes and
 * five rows — it moved the fraction by two thousandths of a point. What it actually changed is the
 * record: five parties that existed in the graph and nowhere in the site now have a page, and the
 * family is gone rather than standing as a permanent asterisk. **A `gap` family can only depress
 * the number when the content it names is routed but unindexed** — worth remembering before the
 * next one is written down.
 *
 * **#1915** is the third shape, and the one this module was really designed for: the enclave and
 * groundwater reads left the "pages the nav model doesn't carry" family by **being carried**. They
 * were routed and unindexed (so, like #1907, genuinely depressing), but nothing was indexed to fix
 * it — the lens landings navigate to them now, and the standing rule ("search reaches whatever the
 * chrome navigates to") reached them on its own. The gap closed by fixing the wayfinding, which is
 * exactly what declaring it rather than indexing around it was for.
 *
 * **#1908** is the fourth, and the only one where the measured number went **down** — from 99.0% to
 * 98.905% — while the declaration got strictly more honest. Both remaining `gap` families closed,
 * so there are now none. Read alone that is a raise; the arithmetic underneath is four separate
 * movements, and flattening them would hide the one that matters:
 *
 *  - **−19 routes, −19 rows.** Seven `/environment/*` leaves are gated on feeds their lens landing
 *    already checks before drawing a door (`LensFacet.requires`, #1915). The landing was the only
 *    surface holding that rule, so the route built and the index indexed on every selectable site
 *    regardless — nineteen pages that no landing and no menu linked, findable by search alone. All
 *    four `/environment/enclave` copies were among them: the `enclave` feed exists on wpafb, which
 *    is not selectable, so every built copy said the site has no federal enclave. Now `getStaticPaths`
 *    reads the same gate and the pages don't exist.
 *  - **−13 rows, no routes.** The same walk indexed the record facets past their own `facetStatus`,
 *    so a locked `/site/legal/` or `/site/reference/` on a peer had a row pointing at its lock. Those
 *    routes still build — a lock is a real destination with a real ask — but they are misses again,
 *    which they always were before #1915 covered them by accident.
 *  - **−5 routes.** `/about/data` retired to `/about/catalog` (one feed had two addresses, and only
 *    one was reachable), and the four site-tier `/submit` routes became `represented` by the network
 *    `/submit` they share a form with.
 *  - **+3 rows.** `/about/sustainability` joined the About menu, `/network/connect` became reachable
 *    by the index it was already in the chrome for, and the how-to-read primer is indexed as a
 *    declared contextual leaf.
 *
 * **A number that falls because rows were withdrawn is worth more than one that rose because rows
 * were added.** Thirteen of those rows were promises that there was somewhere to land, delivering a
 * lock; nineteen more pointed at pages that should never have been built. The floor rises anyway —
 * 0.988 → 0.9885 — because the misses that remain are fewer, but the raise is a tenth of what
 * closing two gap families would suggest, and that gap between expectation and arithmetic IS the
 * finding.
 *
 * The remaining shortfall is the 42 routes no family has declared yet — the reports and record
 * landings on the peers promoted since #1890, and the wiki's own hypothesis and open-questions
 * pages. Those are the ones the next raise is waiting on.
 *
 * The margin is deliberately thin — about two routes. A new page family that nobody indexes will breach this, which is
 * the intended pressure: adding routes should force a choice between indexing them and writing down
 * why not, and a floor with comfortable headroom would let coverage rot back toward 13% one page at
 * a time — which is precisely how it got there.
 */
export const COVERAGE_FLOOR = 0.9885;

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

/**
 * Every contextual leaf `nav.ts` declares, across every site that builds one (#1908).
 *
 * Emitted so `check-routes.mjs` can hold each to its `via` — assert some OTHER built page really
 * links it. Without that the declaration is only a promise: "reached from another page's body copy"
 * is exactly the claim that stops being true when the carrying paragraph is rewritten, and the
 * whole point of writing it down was to stop a decision and an orphan from looking the same.
 *
 * Read per site rather than once, because the leaves are per site — Lima's how-to-read primer is
 * one route the whole network points at, while the submit form is one per site.
 */
function contextualDeclarations(): { href: string; via: string }[] {
  const out = new Map<string, string>();
  for (const site of SITES.filter((s) => s.selectable)) {
    for (const leaf of runWithSite(site.slug, () => contextualLeaves())) out.set(leaf.href, leaf.via);
  }
  return [...out].map(([href, via]) => ({ href, via }));
}

export interface CoverageDeclaration {
  families: CoverageFamily[];
  floor: number;
  shardGzipBudget: number;
  /** The declared contextual leaves — see {@link contextualDeclarations}. */
  contextual: { href: string; via: string }[];
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
    contextual: contextualDeclarations(),
    shards: ["/search-index.json", ...searchShardRefs().map((r) => r.path)],
  };
}
