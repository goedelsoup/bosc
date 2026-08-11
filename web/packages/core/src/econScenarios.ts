/**
 * Build-time reader for the `economics-scenarios` feed (#1665, epic #1659 ME-F).
 *
 * The abatement constants and the four what-if corners used to be declared here in TypeScript —
 * twice, in `craProfiles.ts` and again inside `econLedger.ts` — and a third time in the prose of
 * `docs/the-economic-ledger.md`. Three copies of one county's tax instrument, pinned to each
 * other by tests rather than to the record. They are now computed in Python from the committed
 * CRA extraction, this county's cited tax parameters, and the committed industry priors, and
 * published as a typed feed. This module reads it.
 *
 * NOT client-safe (it imports the node bundle loader). `econLedger.ts` stays client-safe and now
 * takes the corners as an argument; the pages read them here and pass them down, which is how the
 * island already receives `profiles`.
 *
 * Discipline, carried by the feed rather than by comments: every band has `high > low`, every row
 * is tagged `open`/`inference`/`reference` at `low` confidence (the Python model refuses anything
 * else), and the `govcloud` corner is a labeled counterfactual — NOT a defense finding (#233).
 *
 * Per-site by construction: the feed is instrument-gated, so a site with no abatement agreement on
 * the record simply has none and every reader here answers `null`. That is the lock-and-ask path,
 * not a degraded one — never substitute another site's corners.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { CraProfile } from "./craProfiles";
import { type LedgerConstants, netSubsidyOutcome } from "./econLedger";
import type { EconomicScenarios, ScenarioAxis, ScenarioLine, WithheldInput } from "./feeds";
import type { Prior, UncertainOutcome } from "./uncertainty";

const FEED = "economics-scenarios";

/** The active site's scenario bands, or `null` where no abatement instrument is on the record. */
export function economicScenarios(slug?: string): EconomicScenarios | null {
  if (!hasFeed(FEED, slug)) return null;
  const feed = loadFeed<EconomicScenarios>(FEED, slug);
  // Present-but-empty is not publishable: a feed with no corners is not a band (the Python
  // exporter already drops it, so this is belt-and-braces for a hand-written fixture).
  if (!feed.profiles?.length || !feed.lines?.length) return null;
  return feed;
}

/**
 * The site's what-if corners, from the feed — the replacement for the hardcoded `CRA_PROFILES`.
 *
 * `null` (not an empty array, and never a fallback) where the site has no instrument: the caller
 * must lock the report and ask for that site's agreement.
 */
export function craProfilesFromFeed(scenarios = economicScenarios()): CraProfile[] | null {
  if (scenarios === null) return null;
  return (scenarios.profiles ?? []).map((p) => ({
    key: p.key,
    label: p.label,
    buildingShare: p.building_share,
    jobs: p.jobs,
    note: p.note ?? "",
  }));
}

/** The withheld inputs as uncertainty-engine priors, so the simulator's knobs are feed-driven. */
export function priorsFromFeed(scenarios = economicScenarios()): Prior[] | null {
  if (scenarios === null) return null;
  const withheld = scenarios.withheld ?? [];
  if (!withheld.length) return null;
  return withheld.map((w) => priorFromWithheld(w));
}

function priorFromWithheld(w: WithheldInput): Prior {
  const { low, central, high, dist } = w.band;
  return {
    key: w.key,
    label: w.label,
    // The feed's four-tag register vs. the engine's: an `[open]` figure stays `open`; anything
    // else the engine turns is a stated modeling input, i.e. an assumption. `verified` cannot
    // occur — the Python model refuses it — so there is no case for it here.
    register: w.tag === "open" ? "open" : "assumption",
    unit: unitFor(w.band.unit),
    dist: dist === "uniform" ? { kind: "uniform", low, high } : { kind: "triangular", low, central, high },
    source: w.why ?? "",
    resolvingRecord: w.resolving_record ?? "",
  };
}

/** Map the feed's unit vocabulary onto the uncertainty engine's display units. */
function unitFor(unit: string): Prior["unit"] {
  if (unit === "usd" || unit === "usd_per_job") return "usd";
  if (unit === "jobs") return "jobs";
  if (unit === "fraction") return "fraction";
  return "×";
}

/** One named ledger line from the feed (`abatement` | `exemption` | `kept` | `net` | …). */
export function scenarioLine(key: string, scenarios = economicScenarios()): ScenarioLine | null {
  return (scenarios?.lines ?? []).find((l) => l.key === key) ?? null;
}

/** One cited industry axis by key (`govcloud_premium`, `ai_rack_refresh`, …). */
export function scenarioAxis(key: string, scenarios = economicScenarios()): ScenarioAxis | null {
  return (scenarios?.axes ?? []).find((a) => a.key === key) ?? null;
}

/** A named modeling constant's value, or `null` — the auditable arithmetic, not a re-derivation. */
export function scenarioConstant(key: string, scenarios = economicScenarios()): number | null {
  return (scenarios?.constants ?? []).find((c) => c.key === key)?.value.value ?? null;
}

/**
 * The site's abatement constants, for the island's live recompute — or `null` where no instrument
 * is on the record. Every field is read from the feed's cited `constants`; a missing one answers
 * `null` for the whole set rather than substituting a default, because a partially-defaulted
 * instrument would price a real band off a number nobody stated.
 */
export function ledgerConstants(scenarios = economicScenarios()): LedgerConstants | null {
  if (scenarios === null) return null;
  const get = (key: string): number | null => scenarioConstant(key, scenarios);
  const capexUsd = get("capital_investment");
  const assessmentRatio = get("assessment_ratio");
  const effectiveMills = get("effective_commercial_mills");
  const effectiveRate = get("effective_rate");
  const abatePct = get("abatement_percent");
  const termYears = get("term_years");
  const salesTaxRate = get("sales_and_use_rate");
  const refreshCentral = get("equipment_refresh");
  if (
    capexUsd === null ||
    assessmentRatio === null ||
    effectiveMills === null ||
    effectiveRate === null ||
    abatePct === null ||
    termYears === null ||
    salesTaxRate === null ||
    refreshCentral === null
  ) {
    return null;
  }
  return {
    capexUsd,
    assessmentRatio,
    effectiveMills,
    effectiveRate,
    abatePct,
    termYears,
    salesTaxRate,
    refreshCentral,
  };
}

/**
 * The site's non-binding promised job count — the denominator of the load-not-jobs and per-job
 * ratios — or `null` where no such commitment is on the record. Read from the instrument's own
 * `stated_jobs` constant; it must never be assumed for another site.
 */
export function promisedJobs(scenarios = economicScenarios()): number | null {
  return scenarioConstant("stated_jobs", scenarios);
}

/**
 * The site's 15-year net-subsidy band as an `UncertainOutcome` (the public balance sheet's
 * economic row), or `null` where no abatement instrument is on the record — in which case the
 * sheet is simply shorter rather than showing another county's exposure.
 */
export function netSubsidyOutcomeFromFeed(
  scenarios = economicScenarios(),
  dcteTaken = true,
): UncertainOutcome | null {
  const constants = ledgerConstants(scenarios);
  const priors = priorsFromFeed(scenarios);
  if (constants === null || priors === null) return null;
  return netSubsidyOutcome(constants, priors, dcteTaken);
}
