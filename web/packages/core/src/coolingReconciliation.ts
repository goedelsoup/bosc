/**
 * Build-time reader for the **`cooling-reconciliation`** object feed (#1805, epic #1803 P2) —
 * the site's own claim-vs-record cooling-cycling account (epic #1676: the A3 harness, the A4
 * secondary corroborators, the B1-B3 provenance slots), shipped verbatim from the committed
 * reference artifact by `watermark.site.cooling_reconciliation`.
 *
 * Discipline, in the shape `dilution.ts`/`thermal.ts` established: **no fallback, no other
 * site's account**. A site outside the cohort ships no feed and this returns `null` — the
 * water chapter simply renders without the reconciliation block. The feed's `caveats` are the
 * harness's discipline rules (a ceiling is not an instrument; a self-report never upgrades
 * the source; corroborators never change the outcome; a back-solved CoC is a bracket; an
 * instrument that cannot reach a facility returns absence, not zero) — callers MUST render
 * them, never drop them (the `gridBackdrop.ts` rule).
 *
 * NOT client-safe (imports the node bundle loader) — pages render these plain objects.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { CoolingReconciliation, ReconcileOutcome } from "./feeds";

export const COOLING_RECONCILIATION_FEED = "cooling-reconciliation";

/** Display copy per outcome — labels + the one-line gloss the chip's title carries. The chip
 *  colors live with the component (the facility-status register, never the evidence palette). */
export const RECONCILE_OUTCOME_META: Record<ReconcileOutcome, { label: string; gloss: string }> = {
  discrepancy: {
    label: "Discrepancy",
    gloss: "the documented water account contradicts the claimed cooling archetype",
  },
  corroborated: {
    label: "Corroborated",
    gloss: "the documented account matches the archetype's predicted band",
  },
  reservation_conflict: {
    label: "Reservation conflict",
    gloss:
      "a disclosed reservation ceiling contradicts the low-water claim — but a ceiling is not an instrument, so the pin holds",
  },
  gap: {
    label: "Gap",
    gloss:
      "no documented makeup or blowdown exists to test the claim — an open records request, never read as confirmed",
  },
  route_blind: {
    label: "Out of instrument reach",
    gloss:
      "the facility buys its water from a municipal system and/or discharges to a sanitary sewer, so the withdrawal registry and the NPDES record cannot see its cooling account — their ~0 is jurisdiction, not measurement, and never corroborates a claim",
  },
};

/** The site's reconciliation feed, or `null` when its bundle carries none (not in the cohort). */
export function buildCoolingReconciliation(slug?: string): CoolingReconciliation | null {
  if (!hasFeed(COOLING_RECONCILIATION_FEED, slug)) return null;
  return loadFeed<CoolingReconciliation>(COOLING_RECONCILIATION_FEED, slug);
}
