/**
 * The economic-ledger arithmetic on the uncertainty engine (epic #271 flagship, #269) —
 * client-safe, so the SSR build and the simulator island compute the *same* numbers from the same
 * seed.
 *
 * **What changed in #1665 (epic #1659 ME-F).** This module used to *declare* Allen County's
 * abatement instrument: the $500M capex, 75%/15-yr, ~63 effective mills, the 7.25% sales-and-use
 * rate, the four what-if corners, the four withheld priors, and the ~50 promised jobs — a third
 * copy of figures that also lived in `moneyFlow.ts` and in the prose of
 * `docs/the-economic-ledger.md`, kept honest only by tests pinning the copies to each other. They
 * are now read from the committed record in Python and published in the `economics-scenarios`
 * feed; `econScenarios.ts` reads it and hands the constants, corners and priors in.
 *
 * So what is left here is exactly what must stay client-safe: the **pure formulas**, as functions
 * of a `LedgerConstants` argument. The *priced* corners and ledger lines are no longer recomputed
 * here at all — the feed carries them, computed once — and `econScenarios.test.ts` pins these
 * formulas to those priced rows so the interactive recompute can never drift from the published
 * band.
 *
 * Site-gating is now by INSTRUMENT rather than by slug (it used to compare against `LIMA_SLUG`):
 * a site with no abatement agreement on the record simply has no feed, so every reader answers
 * null and the report locks and asks for that site's agreement. Same behaviour, sourced from the
 * record instead of hardcoded.
 *
 * Discipline: the priors are `[assumption]`/`[open]` bounds — "industry reference, NOT this
 * campus." The GovCloud corner is a what-if, not a defense finding (#233). The output is a band,
 * and every band carries the record whose disclosure would collapse it.
 */
import type { CraProfile } from "./craProfiles";
import { type Model, type Prior, type UncertainOutcome, outcomeBand } from "./uncertainty";

/**
 * The abatement constants the formulas below are functions of — one county's instrument, read
 * off the `economics-scenarios` feed's `constants` (`econScenarios.ledgerConstants()`), never
 * declared here. Passing them in is what keeps this module site-agnostic while the *numbers*
 * stay strictly one site's.
 */
export interface LedgerConstants {
  /** The stated capital investment [verified: the agreement's good-faith estimate, not a cap]. */
  capexUsd: number;
  /** Market → assessed ratio [verified: statutory]. */
  assessmentRatio: number;
  /** Effective commercial millage on assessed value [assumption — the exact local rate is not in
   *  the corpus, and it scales every dollar figure linearly]. */
  effectiveMills: number;
  /** assessmentRatio × effectiveMills — tax as a share of market value, per year. */
  effectiveRate: number;
  /** Abated share [verified] and term in years [verified]. */
  abatePct: number;
  termYears: number;
  /** Combined sales-and-use rate the equipment exemption is scored against [verified]. */
  salesTaxRate: number;
  /** Equipment-refresh multiplier across the term, central [assumption]. */
  refreshCentral: number;
}

// --- the ledger as a function of the knobs (pure) -----------------------------
/** 15-yr forgone property tax at one building share (the abatement give). */
export function abatement(k: LedgerConstants, share: number): number {
  return k.capexUsd * share * k.effectiveRate * k.abatePct * k.termYears;
}

/** The un-abated share the public still collects. = abatement × (1−pct)/pct. */
export function keptByPublic(k: LedgerConstants, share: number): number {
  return k.capexUsd * share * k.effectiveRate * (1 - k.abatePct) * k.termYears;
}

/** Forgone sales tax on the equipment (the INVERSE of the building share), refreshed. */
export function salesTaxExemption(k: LedgerConstants, share: number, refresh: number): number {
  return (1 - share) * k.capexUsd * k.salesTaxRate * refresh;
}

/** Per-job *abatement* — the deciding number the withheld figures all move. */
export function abatementPerJob(k: LedgerConstants, share: number, jobs: number): number {
  return Math.round(abatement(k, share) / jobs);
}

/**
 * Net public subsidy ($) = forgone property tax + (forgone sales tax, if the DCTE is taken) −
 * the school-compensation offset. `dcteTaken` is the exemption on-off toggle: the application is
 * `[open]`, and the default is on because the open question is the magnitude, not the existence.
 */
export function netSubsidyModel(k: LedgerConstants, dcteTaken: boolean): Model {
  return (d) =>
    abatement(k, d.building_share) +
    (dcteTaken ? salesTaxExemption(k, d.building_share, d.equipment_refresh) : 0) -
    d.school_compensation;
}

/** Net public subsidy per job — the headline all four withheld figures move. */
export function netSubsidyPerJobModel(k: LedgerConstants, dcteTaken: boolean): Model {
  const net = netSubsidyModel(k, dcteTaken);
  return (d) => net(d) / d.jobs;
}

/**
 * One what-if corner, priced by these formulas. The canonical priced corners come from the feed
 * (`ScenarioProfile`, computed in Python); this exists for the island's *live* recompute as a
 * reader drags the knobs off the declared corners, and is pinned to the feed by a test.
 */
export interface PricedCorner extends CraProfile {
  abatementUsd: number;
  keptUsd: number;
  exemptionUsd: number;
  netSubsidyUsd: number;
  abatementPerJobUsd: number;
}

/** Price one corner with these constants — the same arithmetic the feed publishes. */
export function priceCorner(k: LedgerConstants, p: CraProfile): PricedCorner {
  const ab = abatement(k, p.buildingShare);
  const ex = salesTaxExemption(k, p.buildingShare, k.refreshCentral);
  return {
    ...p,
    abatementUsd: ab,
    keptUsd: keptByPublic(k, p.buildingShare),
    exemptionUsd: ex,
    netSubsidyUsd: ab + ex,
    abatementPerJobUsd: abatementPerJob(k, p.buildingShare, p.jobs),
  };
}

// --- the headline band contract (for the public balance sheet, #273) ----------
/**
 * The 15-year net-subsidy band. Site-agnostic by construction (a function of its arguments) —
 * but `k` and `priors` ARE one county's instrument, so callers reach it through
 * `econScenarios.netSubsidyOutcomeFromFeed()`, which answers null where there is none.
 */
export function netSubsidyOutcome(k: LedgerConstants, priors: Prior[], dcteTaken = true): UncertainOutcome {
  const band = outcomeBand(priors, netSubsidyModel(k, dcteTaken));
  return {
    key: "econ_net_subsidy",
    label: "15-year net public subsidy",
    unit: "usd",
    central: band.central,
    low: band.low,
    high: band.high,
    register: "open", // the band spans an [open] school-comp offset + [open] DCTE application
    drivers: priors,
    resolvingRecord:
      "the four withheld figures (building share · job count · equipment spend · school compensation)",
  };
}

// The county employment baseline the promised jobs is read against used to live here as
// `COUNTY_JOBS_2023 = 49_577` — a hand-copied, one-vintage-stale duplicate of a figure the
// `economics-baseline` feed already carries as a cited `total_employment` (QCEW, with its own
// `asof`). It is read from the feed now (#1642, E2): one source, self-dating, per-site. The
// abatement constants and the what-if corners followed it out for the same reason (#1665).
