// The fact-category vocabulary (#1827) — the small, written-down grouping over the `facts`
// feed's `feed` axis that `get_facts` / `aggregate_facts` filter on.
//
// #1691 asked for a `fact_category` constraint (economics / energy / water-cooling / air /
// facility-power) and proposed hanging it off `search_corpus`. It can't hang there: the `facts`
// feed is not in the ask index (`askIndex.ts` covers the citation-bearing feeds only), so the
// constraint would filter on a field no corpus unit carries and every query would return
// nothing — silently, for a question the corpus can plainly answer. The axis it wants already
// exists on the right tool: `FactItem.feed`, the bundle feed each fact was projected from
// (`watermark.site.facts`). This module is the category → feeds grouping over it.
//
// A grouping is an EDITORIAL claim — it asserts that two feeds answer the same KIND of question
// — so every category carries its `rationale` here rather than being inferred from feed names.
// Two of those calls are load-bearing and cut against the names:
//
//   • `economics-demand-pressure` is filed under `energy`, not `economics`. Its predicates are
//     grid quantities — annual_consumption_gwh, demand_share_pct, load_factor,
//     state_retail_sales_gwh, transmission_coefficient, price_pressure_pct_low/high. It measures
//     the facility's load against the state retail market and the ratepayer price pressure that
//     follows. The feed's NAME is economics; its CONTENT is the electricity market, and a caller
//     asking for `economics` wants the labor-market baseline, not a load factor.
//   • `facility-power` is its own category rather than part of `energy`. `energy` is what power
//     costs the public here (EIA retail prices, household burden); `facility-power` is what the
//     facility itself draws — a different subject (`facility:<site>`, not the ratepayer) and a
//     different evidence posture (mostly [inference], derived off a disclosed backup fleet, not
//     a metered disclosure). Merging them would return a document-anchored retail price beside a
//     derived draw as though they answered the same question.
//
// The grouping is a PARTITION: every feed the facts table carries belongs to exactly one
// category, and `factCategories.test.ts` sweeps the committed per-site bundles to keep that true
// as the Python projectors grow. A caller who wants the exact source rather than the grouping
// filters on `feed` directly — the grouping is a convenience, never the only way in.
//
// Pure + DOM-free (`@watermark/core`): the shared tool schema (`mcpTools.ts`) reads the
// vocabulary for its enum, and the Pages Function handlers (`bundleReaders.ts`) resolve the
// caller's param against it, so schema and filter can't drift apart.

/** One fact category: a named set of source feeds, with the editorial claim that groups them. */
export interface FactCategory {
  /** The value a caller passes as `fact_category`. Lowercase, hyphenated. */
  key: string;
  label: string;
  /** The `FactItem.feed` values this category covers — the real, indexed axis. */
  feeds: readonly string[];
  /** Why these feeds answer the same kind of question. Surfaced in the unknown-category error. */
  rationale: string;
}

export const FACT_CATEGORIES: readonly FactCategory[] = [
  {
    key: "economics",
    label: "Local economy",
    feeds: ["economics-baseline"],
    rationale:
      "The county labor market and household income the facility lands in — QCEW/ACS employment, " +
      "establishments, pay, median household income, per-NAICS location quotients. The baseline a " +
      "jobs claim is measured against.",
  },
  {
    key: "energy",
    label: "Energy market & ratepayer burden",
    feeds: ["consumer-energy", "energy-burden", "economics-demand-pressure"],
    rationale:
      "What electricity and gas cost the public here, and what a new load does to that: EIA retail " +
      "prices and sales, household energy burden and spend, and the facility's share of state retail " +
      "demand with the price pressure it implies. `economics-demand-pressure` sits here despite its " +
      "name — its predicates are grid quantities (demand_share_pct, load_factor, " +
      "state_retail_sales_gwh), not labor-market ones.",
  },
  {
    key: "facility-power",
    label: "Facility power basis",
    feeds: ["facility-power"],
    rationale:
      "What the facility itself draws — genset count and rating, backup capacity, IT load, PUE, " +
      "total draw, cooling share. Kept out of `energy` because it is a different subject (the " +
      "facility, not the ratepayer) and mostly [inference] derived from a disclosed backup fleet " +
      "rather than a metered disclosure.",
  },
  {
    key: "water",
    label: "Water & cooling",
    feeds: ["hydrology-scenarios"],
    rationale:
      "The cooling water balance against the receiving stream — consumptive loss and fraction, " +
      "cooling demand, and the 7Q10 / live flow the loss is measured against.",
  },
  {
    key: "air",
    label: "Air emissions",
    feeds: ["air-scenarios"],
    rationale:
      "The genset fleet's modeled annual emissions by pollutant (NOx, CO, PM10, PM2.5 tons/yr) and " +
      "the engine rating behind them.",
  },
  {
    key: "platform",
    label: "Platform footprint (GreenOps)",
    feeds: ["greenops"],
    rationale:
      "Watermark/BOSC's OWN compute, electricity, carbon and water footprint (subject " +
      "`platform:bosc`). Not a site fact at all — its own category so a site question can never " +
      "sum the platform's numbers into the site's.",
  },
] as const;

/**
 * Names a caller may plausibly reach for that aren't the canonical key. Deliberately tiny: it
 * covers the vocabulary #1691 published (`water-cooling`) and the two obvious near-misses. Not a
 * general synonym layer — anything else fails loudly with the vocabulary attached, which is the
 * whole point of this issue (a mistyped constraint must never return a silent empty set).
 */
const CATEGORY_ALIASES: Readonly<Record<string, string>> = {
  "water-cooling": "water",
  cooling: "water",
  hydrology: "water",
  greenops: "platform",
  power: "facility-power",
};

/** Normalize a caller's token: trimmed, lowercased, underscores folded to hyphens. */
function normalize(raw: string): string {
  return raw.trim().toLowerCase().replace(/_/g, "-");
}

/** Every `FactItem.feed` value the categories cover, sorted — the `feed` filter's vocabulary. */
export const FACT_FEEDS: readonly string[] = FACT_CATEGORIES.flatMap((c) => [...c.feeds]).sort();

/** Resolve a `fact_category` param to its category, or null if it names nothing. */
export function resolveFactCategory(raw: string): FactCategory | null {
  const key = normalize(raw);
  if (!key) return null;
  const canonical = CATEGORY_ALIASES[key] ?? key;
  return FACT_CATEGORIES.find((c) => c.key === canonical) ?? null;
}

/** True when `raw` is a known source feed — the `feed` filter's validity check. */
export function isFactFeed(raw: string): boolean {
  return FACT_FEEDS.includes(normalize(raw));
}

/** The category a source feed belongs to (the partition is total, so null ⇒ an unknown feed). */
export function factCategoryOf(feed: string): FactCategory | null {
  const name = normalize(feed);
  return FACT_CATEGORIES.find((c) => c.feeds.includes(name)) ?? null;
}

/** The vocabulary as returned to a caller who named a category that doesn't exist. */
export function listFactCategories(): Array<{
  category: string;
  label: string;
  feeds: string[];
  rationale: string;
}> {
  return FACT_CATEGORIES.map((c) => ({
    category: c.key,
    label: c.label,
    feeds: [...c.feeds],
    rationale: c.rationale,
  }));
}

/** `"economics (economics-baseline); energy (consumer-energy, …); …"` — the one-line vocabulary
 * embedded in the tool schema so a caller never has to guess which feeds a category covers. */
export function factCategorySummary(): string {
  return FACT_CATEGORIES.map((c) => `${c.key} (${c.feeds.join(", ")})`).join("; ");
}
