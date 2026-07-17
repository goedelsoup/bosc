// Evidence tiering for search_corpus results (#1591).
//
// A hybrid-ranked hit list treats every semantic match as equally useful: a caller that
// pours all of them into a synthesis can't tell the record that literally answers the
// question from a glossary definition that merely shares a word. This module annotates each
// hit with an evidence *tier* — `direct` / `corroborating` / `background` — so the caller can
// weight the response instead of flattening it.
//
// The verdict rests on two intrinsic, always-available signals (no extra fetch):
//
//   1. Evidence class of the feed + source_kind, grounded in the ask-index producer
//      (`@watermark/core/askIndex`):
//        - primary    — records / documents / timeline / meetings: extracted, document-sourced
//                       material, the litigation-grade evidence.
//        - secondary  — entities / people / places: grounded, but derived organizational views
//                       over that evidence.
//        - background — concepts (the glossary is, in the producer's own words, "editorial
//                       synthesis over the corpus, not a single source") and anything whose
//                       source_kind is `derived`.
//   2. Relevance band — the hit's hybrid score as a ratio of the pool's top score. A ratio is
//      scale-free, so the same bands work for RRF fusion and BM25-only alike, and normalizing to
//      the *pool* top (not the page top) keeps bands stable across cursor pages.
//
// The heuristic is deliberately evidence-grounded, never score-alone — the issue's explicit
// guard is that we "must not manufacture a 'direct evidence' tier that isn't evidence-grounded":
//   - a background-class hit is context no matter how high it scores (a glossary entry is never
//     "direct evidence"), and
//   - `direct` requires primary, document-sourced provenance AND a top-band score — a strong
//     match to a derived/secondary view is corroboration, not the direct answer.
//
// Fact-linkage (join a hit to a query-relevant fact in the facts feed to promote it) is a
// documented NON-GOAL here. The facts feed (#1587) is projected from connector/derived numeric
// feeds (economics, energy, air, hydrology, facility-power) and carries a citation string but no
// `evidence.source` document path; search_corpus indexes record/document/timeline units. The two
// provenance universes barely overlap, so a provenance join would essentially never fire — and a
// fuzzy topical join would reintroduce exactly the score-alone "direct" tier this guard forbids.

/** The evidence role a hit plays for the query. */
export type Tier = "direct" | "corroborating" | "background";

export interface TierVerdict {
  tier: Tier;
  reason: string;
}

/** Feeds carrying extracted, document-sourced evidence — the litigation-grade material. */
const PRIMARY_FEEDS: ReadonlySet<string> = new Set(["records", "documents", "timeline", "meetings"]);
/** Feeds that are editorial/definitional synthesis, not evidence of a fact. */
const BACKGROUND_FEEDS: ReadonlySet<string> = new Set(["concepts"]);

/** A hit scoring at least this fraction of the pool's top score is in the top relevance band. */
export const DIRECT_BAND = 0.6;
/** A hit below this fraction of the top score is too weak to be more than context. */
export const BACKGROUND_BAND = 0.3;

export type EvidenceClass = "primary" | "secondary" | "background";

/**
 * Classify a unit by its feed + source_kind. `derived` provenance (or a background feed like
 * the glossary) is editorial context regardless of feed; the primary feeds are the extracted,
 * document-sourced ones; everything else is a grounded-but-secondary view (entities/people/places).
 */
export function evidenceClass(feed: string, sourceKind: string | null | undefined): EvidenceClass {
  if (BACKGROUND_FEEDS.has(feed) || sourceKind === "derived") return "background";
  if (PRIMARY_FEEDS.has(feed)) return "primary";
  return "secondary";
}

/**
 * Tier one hit against the pool's top score. `topScore` is the strongest score in the whole
 * ranked pool (not just the current page), so the relevance bands stay stable across cursor pages.
 * With no positive top score (empty pool), everything degrades to `background`.
 */
export function tierHit(
  feed: string,
  sourceKind: string | null | undefined,
  score: number,
  topScore: number,
): TierVerdict {
  const cls = evidenceClass(feed, sourceKind);
  const ratio = topScore > 0 ? score / topScore : 0;
  const pct = Math.round(ratio * 100);

  // Editorial / derived material is context by construction — never promoted on score alone.
  if (cls === "background") {
    return { tier: "background", reason: "definitional or derived source — context, not evidence of a fact" };
  }
  // Weak match to the query: relevant enough to surface, not enough to lean on.
  if (ratio < BACKGROUND_BAND) {
    return { tier: "background", reason: `weak relevance (${pct}% of top score)` };
  }
  // Top-band, document-sourced evidence directly on the query — the only path to `direct`.
  if (cls === "primary" && ratio >= DIRECT_BAND) {
    return { tier: "direct", reason: `primary evidence, top relevance band (${pct}% of top score)` };
  }
  // Relevant supporting material: a secondary-class view, or primary evidence below the top band.
  return {
    tier: "corroborating",
    reason:
      cls === "primary"
        ? `primary evidence, supporting relevance band (${pct}% of top score)`
        : `secondary view (${pct}% of top score)`,
  };
}
