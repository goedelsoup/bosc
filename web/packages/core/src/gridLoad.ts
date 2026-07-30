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
 * Per-site (#1642, GP-E E2/E4; #1771). This module holds the *model*, never a site's numbers:
 *  - the load denominators arrive as a {@link GridBaseline}, read from the `grid` feed by
 *    `gridBackdrop.buildGridBaseline` — they used to be Lima's EIA figures hand-copied in as
 *    literals (`AEP_OHIO_RETAIL_GWH = 48_653`) and tagged as if connector-sourced;
 *  - the backup fleet arrives as a {@link BackupRecord}, read from the `facility` feed by
 *    `gridBackdrop.buildBackupRecord` — Lima's 313 MW / 114 gensets / 2,750 ekW were the last
 *    literals here, duplicating `SiteFacility.genset_*` with nothing pinning the copies together
 *    and a hardcoded Lima-only branch that refused Fort Wayne's real fleet (#1771).
 * So a second selectable site can no longer render Lima's grid as its own — and no longer has to
 * render nothing where it has a record of its own.
 */
import type { GensetRatingBasis } from "./feeds";
import { type Prior, type UncertainOutcome, outcomeBand, sample, summarize } from "./uncertainty";

// --- the backup-generation record --------------------------------------------

/**
 * A site's disclosed backup-generation fleet, as the `facility` feed carries it (#1771).
 *
 * Every field is the record's, not this module's. The two grades are what keep it honest across
 * sites: {@link totalBasis} says whether the printed MW is the record's own figure or this
 * platform's arithmetic, and {@link ratingBasis} says how firmly the per-engine rating under it
 * is grounded. Lima is `cited` + `draft_only` — the corpus states `~313 MW` (hence
 * {@link approximate}) and the rating behind it survives only on the draft the issued permit
 * redacts. Fort Wayne is `derived` + `derived` — 34 engines are a verbatim disclosure, but the
 * permit states heat input rather than an electrical rating, so both the rating and the total
 * resting on it are inferences and must never render as `[verified]`.
 */
export interface BackupRecord {
  /** Total backup capacity, MW. */
  backupMw: number;
  /** `cited` — transcribed from the record; `derived` — count × rating, because no total is on
   *  the record. Deriving Lima's would print 313.5 for a site whose every published surface says
   *  ~313, which is why the cited total exists as its own field. */
  totalBasis: "cited" | "derived";
  /** The transcription `~` marker, carried as data — render the tilde where it is true. */
  approximate: boolean;
  nEngines: number;
  /** Per-engine rating, MW. */
  perEngineMw: number;
  ratingBasis: GensetRatingBasis;
  /** The total's own citation where one is cited, else the permit that discloses the fleet. */
  cite: string;
}

/**
 * The evidence register the backup figure renders under.
 *
 * `[verified]` only where BOTH the total is the record's own and the rating under it is a record
 * figure (Lima's draft counts — it is a document, redaction notwithstanding). A derived total, or
 * one resting on a back-derived rating, is an `assumption`: the platform's arithmetic over a
 * disclosure, which is not the same as a disclosure.
 */
export function backupRegister(backup: BackupRecord): "verified" | "assumption" {
  return backup.totalBasis === "cited" && backup.ratingBasis !== "derived" ? "verified" : "assumption";
}

/** The backup total as text, keeping the record's `~` marker where it carries one. */
export function fmtBackupMw(backup: BackupRecord): string {
  const n = Number.isInteger(backup.backupMw) ? String(backup.backupMw) : backup.backupMw.toFixed(1);
  return `${backup.approximate ? "~" : ""}${n} MW`;
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
