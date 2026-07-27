/**
 * Grid load-band model (epic #271 Phase 2, #265) — the grid consumer of the uncertainty
 * engine. Client-safe so the island and the SSR fallback agree.
 *
 * The headline "313 MW" is **backup generation, not the operating load**, and the per-engine
 * rating behind it is **redacted in the issued permit** (it survives only on the draft). So
 * the working load can only be *inferred*, and the inference chain itself is the uncertainty:
 *   313 MW backup `[verified, draft]` → IT load via N+1 (≈ backup) `[inference]` ~250–300
 *   → facility = IT × PUE `[inference]` ~303–393 (central ~348).
 *
 * Discipline (load-bearing): 313 MW = backup, NOT load; the per-engine ekW is redacted
 * `[open]`; "behind-the-meter" is a proponent claim `[open]` (the campus is a PUCO-regulated
 * retail customer of AEP Ohio); PJM dollar figures are `[reference]` / screening. The
 * resolving record is the operating-load disclosure + the un-redacted per-engine rating.
 *
 * Per-site (#1642, GP-E E2/E4). This module holds the *model*, never a site's numbers:
 *  - the load denominators arrive as a {@link GridBaseline}, read from the `grid` feed by
 *    `gridBackdrop.buildGridBaseline` — they used to be Lima's EIA figures hand-copied in as
 *    literals (`AEP_OHIO_RETAIL_GWH = 48_653`) and tagged as if connector-sourced;
 *  - the 313 MW / 114-genset backup record is reached through {@link backupRecord}, which
 *    answers only for the site whose permit it is.
 * So a second selectable site can no longer render Lima's grid as its own.
 */
import { LIMA_SLUG } from "./routes";
import { type Prior, type UncertainOutcome, outcomeBand, sample, summarize } from "./uncertainty";

// --- the cited backup + its redaction (Lima's air-permit record) --------------
// These are the *Lima* record's figures — permit 4132514's 114 emergency gensets and the
// per-engine rating that survives only on draft 3987141. They are not a general property of a
// data-center site, so they are reached through `backupRecord(site)` (#1642, E4): another site
// gets null and its caller asks for that site's permit rather than inheriting Lima's gensets.
const LIMA_BACKUP: BackupRecord = {
  backupMw: 313, // 114 emergency gensets × ~2,750 ekW [verified: DRAFT 3987141]
  nEngines: 114,
  perEngineEkwDraft: 2750, // survives only on the draft public notice
  finalPermit: "4132514",
  draftPermit: "3987141",
};

/** The cited backup-generation record behind a site's headline MW figure. */
export interface BackupRecord {
  backupMw: number;
  nEngines: number;
  /** The per-engine rating — redacted in the issued permit, surviving on the draft. */
  perEngineEkwDraft: number;
  finalPermit: string;
  draftPermit: string;
}

/**
 * The backup-generation record for a site, or null where none is on the record (#1642, E4).
 *
 * Mirrors `buildEndUse(site)` (#1633): the 313 MW / 114-genset / redacted-per-engine chain is
 * Lima's air permit, so a different site reads null and its page asks for the source instead of
 * republishing Lima's figures under another county's name.
 */
export function backupRecord(site: string): BackupRecord | null {
  return site === LIMA_SLUG ? LIMA_BACKUP : null;
}

// --- the load-vs-baseline model ----------------------------------------------
const LOAD_FACTOR = 0.9; // annual average ÷ peak (hyperscale runs near-flat)
const HOURS_YR = 8760;

/**
 * The per-site denominators the "share of retail sales" / "equivalent homes" readouts divide by,
 * read from the `grid` + `economics-demand-pressure` feeds by `gridBackdrop.buildGridBaseline`
 * (#1642, E2).
 *
 * These used to live here as literals — `AEP_OHIO_RETAIL_GWH = 48_653`, `OHIO_RETAIL_GWH`,
 * `HOME_MWH_YR` — hand-copied from the EIA pulls the Python tier already did and tagged as if
 * connector-sourced, a second uncontrolled copy that could drift silently against the reference
 * data. They are now inputs, so there is exactly one source for each figure.
 */
export interface GridBaseline {
  /** The serving utility, as the feed names it ("AEP Ohio (Ohio Power Company)"). */
  utilityLabel: string;
  /** The utility's total annual retail sales, GWh — the share denominator (EIA-861). */
  utilityRetailGwh: number;
  utilityCite: string;
  /** Average household annual electricity use, kWh — the cited figure the demand-pressure feed
   *  divides by. Null when that feed is absent, in which case the homes readout is withheld. */
  householdKwhYr: number | null;
  householdCite: string | null;
  /** The state the household/price figures are for ("OH"), when known. */
  stateArea: string | null;
}

// --- the inference chain, as priors -------------------------------------------
export const GRID_PRIORS: Prior[] = [
  {
    key: "it_load",
    label: "IT load (via N+1 backup ≈ IT)",
    register: "assumption",
    unit: "MW",
    dist: { kind: "triangular", low: 250, central: 275, high: 300 },
    source: "N+1 design: backup ≈ IT load (313 MW backup → ~250–300 MW IT)",
    resolvingRecord: "the operating-load disclosure (metered IT load)",
  },
  {
    key: "pue",
    label: "Facility PUE (IT → total facility draw)",
    register: "assumption",
    unit: "×",
    dist: { kind: "triangular", low: 1.21, central: 1.265, high: 1.31 },
    source: "hyperscale PUE ~1.2–1.3 (facility = IT × PUE)",
    resolvingRecord: "the facility electrical design / metered total draw",
  },
];

/**
 * The grid priors with the IT-load prior sourced from the `facility` feed's disclosed
 * range (#1632) instead of the hardcoded 250–300. This is the reconciliation: `/basin`
 * sums the same feed-scoped `it_load_mw`, so the basin scalar and this report's band now
 * trace to ONE sourced IT figure (the report additionally carries it through × PUE to the
 * facility draw). The PUE prior is unchanged; the it-load key/label/resolvingRecord stay so
 * the disclosure UI (`applyDisclosures`) still collapses it. Falls back to `GRID_PRIORS`
 * (Lima) when a facility carries no disclosed load — `low`/`high` default to the central
 * (the sampler treats a zero-width triangular as a point).
 */
export function gridPriorsFromFacility(
  itCentral: number,
  itLow?: number | null,
  itHigh?: number | null,
): Prior[] {
  const pue = GRID_PRIORS.find((p) => p.key === "pue");
  const itLoad: Prior = {
    key: "it_load",
    label: "IT load (disclosed range)",
    register: "assumption",
    unit: "MW",
    dist: { kind: "triangular", low: itLow ?? itCentral, central: itCentral, high: itHigh ?? itCentral },
    source: "disclosed IT-load bracket (facility feed) — the same figure /basin sums",
    resolvingRecord: "the operating-load disclosure (metered IT load)",
  };
  return pue ? [itLoad, pue] : [itLoad];
}

/** Facility draw (MW) = IT load × PUE — the headline the inference chain produces. */
export function facilityDrawModel(draw: Record<string, number>): number {
  return draw.it_load * draw.pue;
}

/** Annual energy (GWh/yr) at the facility draw and a hyperscale load factor. */
export function annualGwh(facilityMw: number): number {
  return (facilityMw * LOAD_FACTOR * HOURS_YR) / 1000;
}
/** Share of the serving utility's entire annual retail electricity sales (%), against the
 *  feed-sourced denominator (#1642 — was hardcoded to AEP Ohio's 48,653 GWh). */
export function pctOfUtilityRetail(gwh: number, utilityRetailGwh: number): number {
  return (gwh / utilityRetailGwh) * 100;
}
/** Annual consumption expressed as equivalent households, at the feed's cited household use. */
export function equivalentHomes(gwh: number, householdKwhYr: number): number {
  return (gwh * 1_000_000) / householdKwhYr;
}
/** Electrical load per promised job (MW/job) — the load-not-jobs ratio. The job count is the
 *  site's own non-binding commitment (Lima's CRA ~50), passed in rather than assumed. */
export function mwPerJob(itMw: number, jobs: number): number {
  return itMw / jobs;
}

/** The facility-draw band (MW), `[inference]` — the inference chain IS the uncertainty.
 *  Emitted for the public balance sheet (#273). */
export function facilityDrawOutcome(priors: Prior[] = GRID_PRIORS): UncertainOutcome {
  const band = outcomeBand(priors, facilityDrawModel);
  return {
    key: "grid_facility_draw",
    label: "Inferred facility electrical draw",
    unit: "MW",
    central: band.central,
    low: band.low,
    high: band.high,
    // A bounded, cited inference chain (the prose tag is [inference]); maps to the
    // engine's `assumption` register — not [verified] (no disclosed load), not [open].
    register: "assumption",
    drivers: priors,
    resolvingRecord:
      "the operating-load disclosure + the un-redacted per-engine rating (redacted in final permit 4132514)",
  };
}

/** A precomputed Monte-Carlo summary of the facility-draw band (deterministic seed). */
export function facilityDrawSummary(priors: Prior[] = GRID_PRIORS, n = 6000) {
  return summarize(sample(priors, facilityDrawModel, n), 24);
}
