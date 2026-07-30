import { describe, expect, it } from "vitest";
import { hasFeed, loadFeed, manifestOrNull } from "./bundle";
import { SITES } from "./sites";
import {
  composeStudyChapterModel,
  IMPACT_STUDY_FEED,
  type ImpactStudyFeedRow,
  resolveStudyFacility,
  STUDY_CHAPTERS,
} from "./study";

/**
 * The parity gate (#1804 acceptance): the Python-emitted `impact-study` rows must equal the
 * TS derivation over EVERY committed bundle. The frontend prefers a shipped row wholesale,
 * so a drift between `watermark.site.impact_study` and `study.ts` doesn't fail a build — it
 * silently changes a published verdict. This suite is what makes that impossible to ship:
 * regenerating the bundles with a drifted projector fails here; editing `study.ts` without
 * re-mirroring the projector fails here too. Change the two files together or not at all.
 */

// The two derivations spell an absent optional differently — the Python export serializes
// explicit nulls (the repo's feed convention) where the TS composers omit the key. Same
// datum, so canonicalize both sides: JSON round-trip (drops undefined), then strip nulls.
function stripNulls(x: unknown): unknown {
  if (Array.isArray(x)) return x.map(stripNulls);
  if (x !== null && typeof x === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(x)) {
      if (v !== null && v !== undefined) out[k] = stripNulls(v);
    }
    return out;
  }
  return x;
}
const canon = (x: unknown): unknown => stripNulls(JSON.parse(JSON.stringify(x)));

const bundled = SITES.map((s) => s.slug).filter((slug) => manifestOrNull(slug) !== null);

describe(`impact-study parity — the shipped feed equals the TS derivation (${bundled.length} bundles)`, () => {
  it("every committed bundle ships the feed (the cutover is total, never partial)", () => {
    expect(bundled.length).toBeGreaterThanOrEqual(3);
    for (const slug of bundled) {
      expect(hasFeed(IMPACT_STUDY_FEED, slug), `${slug} ships no impact-study feed`).toBe(true);
    }
  });

  it.each(bundled)("%s — one row per chapter, keyed to the resolved primary facility", (slug) => {
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
    expect(rows.map((r) => r.chapter)).toEqual(STUDY_CHAPTERS.map((c) => c.id));
    const key = resolveStudyFacility(slug)?.key ?? null;
    for (const row of rows) {
      expect(row.facility_key, `${slug}/${row.chapter}`).toBe(key);
      expect(row.model.facilityKey, `${slug}/${row.chapter}`).toBe(key);
    }
  });

  it.each(bundled)("%s — every shipped model equals the TS-composed model", (slug) => {
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
    for (const row of rows) {
      // `composeStudyChapterModel` is the pre-feed derivation (verdict, reasons, stats down
      // to the formatted strings, gaps, caveats, lead joins) — byte-parity or it doesn't ship.
      const composed = composeStudyChapterModel(row.chapter, slug);
      expect(canon(row.model), `${slug}/${row.chapter}`).toEqual(canon(composed));
    }
  });

  it.each(bundled)("%s — every shipped lead join names a lead on the site's own board", (slug) => {
    // The producer refuses a dangling join at export; this is the consumer-side pin, so a
    // hand-edited bundle can't smuggle one past either. Joins are strictly the site's own
    // board — never another site's leads.
    const rows = loadFeed<ImpactStudyFeedRow[]>(IMPACT_STUDY_FEED, slug);
    const board = hasFeed("leads", slug) ? loadFeed<{ id: string }[]>("leads", slug) : [];
    const known = new Set(board.map((l) => l.id));
    for (const row of rows) {
      const joined = [...(row.lead_ids ?? []), ...row.model.gaps.flatMap((g) => g.leadIds ?? [])];
      for (const id of joined) {
        expect(known.has(id), `${slug}/${row.chapter}: lead "${id}" is not on the board`).toBe(true);
      }
    }
  });
});
