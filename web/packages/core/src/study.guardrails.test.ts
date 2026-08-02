import { describe, expect, it } from "vitest";
import { manifestOrNull } from "./bundle";
import { SITES } from "./sites";
import {
  type ChapterStatus,
  resolveStudyFacility,
  STUDY_CHAPTERS,
  studyChapterModel,
  studyStatusSummary,
} from "./study";

/**
 * Study guardrails over EVERY committed bundle (the `stories.guardrails` pattern) — the
 * study must derive a coherent model for any site whose bundle is committed, not just the
 * three fixtures the unit tests pin. A bundle regen that breaks a feed shape,
 * a def whose gap copy drifts off the panel grammar, or a model that stops being plain
 * JSON (the future `impact-study` feed contract) fails HERE, before it ships.
 */
const bundled = SITES.map((s) => s.slug).filter((slug) => manifestOrNull(slug) !== null);
const STATUSES: readonly ChapterStatus[] = ["data", "partial", "gap", "na"];

describe(`study guardrails — every committed bundle (${bundled.length} sites)`, () => {
  it("finds a real cohort to guard (the committed fixtures exist)", () => {
    expect(bundled.length).toBeGreaterThanOrEqual(3);
    for (const slug of ["lima", "fort-wayne", "urbana"]) expect(bundled).toContain(slug);
  });

  it.each(bundled)("%s — every chapter derives a coherent, serializable model", (slug) => {
    const facility = resolveStudyFacility(slug);
    for (const def of STUDY_CHAPTERS) {
      const m = studyChapterModel(def.id, slug);
      expect(m.id).toBe(def.id);
      expect(STATUSES).toContain(m.status);

      // `na` is the watch state — it exists ONLY for a site with no disclosed project,
      // and it never carries stats or gap panels (nothing is screened, nothing scolds).
      if (m.status === "na") {
        expect(facility).toBeNull();
        expect(m.stats).toEqual([]);
        expect(m.gaps).toEqual([]);
      }

      // A gap-status chapter always renders at least its chapter-level finding.
      if (m.status === "gap") expect(m.gaps.length).toBeGreaterThan(0);

      // The gap grammar: every panel completes "Computing it requires ___" — a def whose
      // copy drifts back to a full sentence ("no X exists…") re-breaks the panel (PR3).
      for (const g of m.gaps) {
        expect(g.wouldScreen.length).toBeGreaterThan(0);
        expect(g.missingRecord.length).toBeGreaterThan(0);
        expect(g.missingRecord, `${slug}/${def.id}: gap copy must be a noun phrase`).not.toMatch(/^no /i);
      }

      // Every stat wears a real evidence tag (the FigureStat contract).
      for (const s of m.stats) {
        expect(["verified", "inference", "open"]).toContain(s.evidence);
        expect(s.label.length).toBeGreaterThan(0);
        expect(s.value.length).toBeGreaterThan(0);
      }

      // Plain JSON — the model IS the future `impact-study` feed row shape; a def that
      // sneaks a function or undefined-holed object in breaks the seam.
      expect(JSON.parse(JSON.stringify(m))).toEqual(m);
    }
  });

  it.each(bundled)("%s — the verdict rollup accounts for every chapter", (slug) => {
    const s = studyStatusSummary(slug);
    expect(s.total).toBe(STUDY_CHAPTERS.length);
    expect(s.data + s.partial + s.gap + s.na).toBe(s.total);
    // A facility-less site watches instead of scolding; a facility site never watches.
    if (resolveStudyFacility(slug) === null) expect(s.na).toBeGreaterThan(0);
    else expect(s.na).toBe(0);
  });
});
