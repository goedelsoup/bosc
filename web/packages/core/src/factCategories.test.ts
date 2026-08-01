import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed, manifestOrNull } from "./bundle";
import {
  FACT_CATEGORIES,
  FACT_FEEDS,
  factCategoryOf,
  factCategorySummary,
  isFactFeed,
  listFactCategories,
  resolveFactCategory,
} from "./factCategories";
import type { FactItem } from "./feeds";
import { SITES } from "./sites";

// The category vocabulary is a claim ABOUT the shipped data — that these feeds answer the same
// kind of question, and that the grouping covers every feed the facts table actually carries. So
// the drift guard runs against the committed per-site bundles, not a synthetic fixture. Pin
// WATERMARK_BUNDLE_DIR at `web/sites` (absolute, CWD-independent) when the mise task env hasn't,
// so a bare `vitest` can't silently read a stale local `data/site/bundles/`.
process.env.WATERMARK_BUNDLE_DIR ??= resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../sites");

const bundled = SITES.map((s) => s.slug).filter((slug) => manifestOrNull(slug) !== null);

describe("factCategories — the written-down grouping over FactItem.feed (#1827)", () => {
  it("is a partition: no feed is claimed by two categories", () => {
    const seen = new Map<string, string>();
    for (const category of FACT_CATEGORIES) {
      for (const feed of category.feeds) {
        expect(seen.has(feed), `${feed} claimed by ${seen.get(feed)} and ${category.key}`).toBe(false);
        seen.set(feed, category.key);
      }
    }
    expect(FACT_FEEDS.length).toBe(seen.size);
  });

  it("covers every feed the committed bundles actually ship", () => {
    // The projectors live in Python (`watermark.site.facts`); this vocabulary lives in TS. The
    // seam is real, so sweep the shipped data: a new projector that adds a feed fails HERE (in
    // CI, with the feed named) instead of at runtime, where `feed=<new>` would 400 on a caller.
    const shipped = new Set<string>();
    for (const slug of bundled) {
      if (!hasFeed("facts", slug)) continue;
      for (const fact of loadFeed<FactItem[]>("facts", slug)) shipped.add(fact.feed);
    }
    expect(shipped.size).toBeGreaterThan(0); // the sweep saw real data, not a vacuous pass
    for (const feed of shipped) {
      expect(factCategoryOf(feed), `feed "${feed}" belongs to no fact category`).not.toBeNull();
    }
  });

  it("every category carries a defended rationale and at least one feed", () => {
    for (const category of FACT_CATEGORIES) {
      expect(category.feeds.length).toBeGreaterThan(0);
      expect(category.label.length).toBeGreaterThan(0);
      expect(category.rationale.length).toBeGreaterThan(40); // an editorial claim, not a label
    }
  });

  it("files economics-demand-pressure under energy, not economics — content over name", () => {
    // The load-bearing editorial call: the feed's NAME is economics, its predicates are grid
    // quantities (demand_share_pct, load_factor, state_retail_sales_gwh, price pressure).
    expect(factCategoryOf("economics-demand-pressure")?.key).toBe("energy");
    expect(resolveFactCategory("economics")?.feeds).toEqual(["economics-baseline"]);
  });

  it("keeps facility-power out of energy — what the facility draws vs what power costs", () => {
    expect(factCategoryOf("facility-power")?.key).toBe("facility-power");
    expect(resolveFactCategory("energy")?.feeds).not.toContain("facility-power");
  });

  it("keeps the platform's own footprint off the site categories", () => {
    // greenops is subject `platform:bosc` — never summable into a site total.
    expect(factCategoryOf("greenops")?.key).toBe("platform");
    for (const c of FACT_CATEGORIES) {
      if (c.key !== "platform") expect(c.feeds).not.toContain("greenops");
    }
  });

  it("resolves case, underscores, and the small published alias set", () => {
    expect(resolveFactCategory("ENERGY")?.key).toBe("energy");
    expect(resolveFactCategory("facility_power")?.key).toBe("facility-power");
    expect(resolveFactCategory("  water  ")?.key).toBe("water");
    expect(resolveFactCategory("water-cooling")?.key).toBe("water"); // the name #1691 published
    expect(resolveFactCategory("greenops")?.key).toBe("platform");
  });

  it("returns null for anything it doesn't know — never a silent nearest match", () => {
    expect(resolveFactCategory("econ")).toBeNull();
    expect(resolveFactCategory("")).toBeNull();
    // A feed name is NOT a category: resolving it would silently widen the query to its whole
    // category. The handler detects this case and says "pass it as `feed`" instead.
    expect(resolveFactCategory("economics-baseline")).toBeNull();
    expect(isFactFeed("economics-baseline")).toBe(true);
    expect(isFactFeed("no-such-feed")).toBe(false);
  });

  it("publishes the vocabulary a caller gets back on a miss", () => {
    const listed = listFactCategories();
    expect(listed.map((c) => c.category)).toEqual(FACT_CATEGORIES.map((c) => c.key));
    expect(listed.every((c) => c.feeds.length > 0 && c.rationale.length > 0)).toBe(true);
    // The one-liner embedded in the tool schema names every category AND its feeds, so a caller
    // reading the schema never has to guess what a grouping covers.
    const summary = factCategorySummary();
    for (const c of FACT_CATEGORIES) {
      expect(summary).toContain(c.key);
      for (const feed of c.feeds) expect(summary).toContain(feed);
    }
  });
});
