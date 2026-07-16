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
 */
import { type Prior, type UncertainOutcome, outcomeBand, sample, summarize } from "./uncertainty";

// --- the cited backup + its redaction -----------------------------------------
export const BACKUP_MW = 313; // 114 emergency gensets × ~2,750 ekW [verified: DRAFT 3987141]
export const N_ENGINES = 114;
export const PER_ENGINE_EKW_DRAFT = 2750; // survives only on the draft public notice

// --- the load-vs-baseline constants (cited) -----------------------------------
const LOAD_FACTOR = 0.9; // annual average ÷ peak (hyperscale runs near-flat)
const HOURS_YR = 8760;
export const AEP_OHIO_RETAIL_GWH = 48_653; // [connector: EIA-861, 2024]
export const OHIO_RETAIL_GWH = 161_934; // [connector: EIA]
const HOME_MWH_YR = 10.5; // avg Ohio home annual consumption (~10.5 MWh)
export const PROMISED_JOBS = 50; // CRA ~50 (non-binding)

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

/** Facility draw (MW) = IT load × PUE — the headline the inference chain produces. */
export function facilityDrawModel(draw: Record<string, number>): number {
  return draw.it_load * draw.pue;
}

/** Annual energy (GWh/yr) at the facility draw and a hyperscale load factor. */
export function annualGwh(facilityMw: number): number {
  return (facilityMw * LOAD_FACTOR * HOURS_YR) / 1000;
}
/** Share of AEP Ohio's entire retail electricity sales (%). */
export function pctOfAepRetail(gwh: number): number {
  return (gwh / AEP_OHIO_RETAIL_GWH) * 100;
}
/** Annual consumption expressed as equivalent Ohio homes. */
export function equivalentHomes(gwh: number): number {
  return (gwh * 1000) / HOME_MWH_YR;
}
/** Electrical load per promised job (MW/job) — the load-not-jobs ratio. */
export function mwPerJob(itMw: number): number {
  return itMw / PROMISED_JOBS;
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
