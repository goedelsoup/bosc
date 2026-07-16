/**
 * The economic-ledger model on the uncertainty engine (epic #271 flagship, #269) —
 * client-safe so the SSR build and the island compute the *same* numbers from the same
 * seed. It extends the deployed abatement-per-job model (`moneyFlow.ts`
 * `buildAbatementPerJob`) into the full 15-year public ledger as a function of the four
 * withheld knobs. The abatement constants + the four profiles are re-declared here (this
 * module is client-safe; `moneyFlow` imports the node bundle loader) and pinned to the
 * deployed model by `econLedger.test.ts` so they can never fork.
 *
 * Discipline: the priors are `[assumption]` industry-reference bounds
 * (`data/reference/datacenter-industry/priors.yaml`), "industry reference, NOT this
 * campus." GovCloud is a what-if profile, not a defense finding. The output is a band,
 * not a verdict; every band carries the record whose disclosure would collapse it.
 */
import { CRA_PROFILES } from "./craProfiles";
import { type Model, type Prior, type UncertainOutcome, outcomeBand } from "./uncertainty";

// --- the deployed abatement constants (pinned to moneyFlow by the test) -------
const CAPEX = 500_000_000; // CRA §2 good-faith estimate (not a cap) [verified]
const ASSESS = 0.35; // Ohio real-property assessment ratio [verified]
const MILLS = 0.063; // ~63 effective commercial mills [assumption — exact local rate not in corpus]
const ABATE_PCT = 0.75; // Res #548-25 / CRA §3 [verified]
const YEARS = 15; // CRA §3, per building [verified]
const EFFECTIVE_RATE = ASSESS * MILLS; // tax as a share of market value, per year
// Allen County combined sales-and-use rate; the DCTE exempts equipment + construction
// materials (R.C. 122.175). [verified]
const SALES_TAX = 0.0725;

// --- the ledger as a function of the knobs (pure) -----------------------------
/** 15-yr forgone property tax (the abatement give). Matches buildAbatementPerJob. */
export function abatement(share: number): number {
  return CAPEX * share * EFFECTIVE_RATE * ABATE_PCT * YEARS;
}
/** The 25% the public still collects (un-abated). = abatement × (1−pct)/pct. */
export function keptByPublic(share: number): number {
  return CAPEX * share * EFFECTIVE_RATE * (1 - ABATE_PCT) * YEARS;
}
/** Forgone sales tax on the equipment (the inverse of the building share), with a 15-yr
 *  refresh multiplier. Equipment = (1 − share) × capex. */
export function salesTaxExemption(share: number, refresh: number): number {
  return (1 - share) * CAPEX * SALES_TAX * refresh;
}
/** Per-job *abatement* — the deployed deciding number (matches buildAbatementPerJob). */
export function abatementPerJob(share: number, jobs: number): number {
  return Math.round(abatement(share) / jobs);
}

// --- the four withheld knobs, as priors --------------------------------------
// Bounds are the pooled industry priors (priors.yaml); "industry reference, not Lima".
export const ECON_PRIORS: Prior[] = [
  {
    key: "building_share",
    label: "Building (abated real-property) share of the $500M",
    register: "assumption",
    unit: "fraction",
    dist: { kind: "triangular", low: 0.2, central: 0.3, high: 0.45 },
    source: "datacenter-industry priors · building_real_property_share (shell ~15–21%; +affixed M&E)",
    resolvingRecord: "the building/equipment capex split (CRA §2 detail)",
  },
  {
    key: "jobs",
    label: "Steady-state permanent jobs",
    register: "assumption",
    unit: "jobs",
    // The CRA's ~50 is non-binding ("may differ significantly"); lean ops → ~30.
    dist: { kind: "triangular", low: 30, central: 50, high: 50 },
    source: "CRA ~50 (non-binding) · jobs_per_mw 0.10–0.30 brackets ~28–105 for the load",
    resolvingRecord: "an actual steady-state headcount",
  },
  {
    key: "refresh",
    label: "Equipment refresh over the 15-yr window",
    register: "assumption",
    unit: "×",
    dist: { kind: "triangular", low: 1.0, central: 1.5, high: 2.0 },
    source: "datacenter-industry priors · ai_rack_refresh (~30–40% of cost replaced annually)",
    resolvingRecord: "the equipment spend + refresh schedule",
  },
  {
    key: "school_comp",
    label: "School District Compensation (offset)",
    register: "open",
    unit: "usd",
    // Genuinely undisclosed — a wide screening range, not a number.
    dist: { kind: "uniform", low: 0, high: 30_000_000 },
    source: "withheld — cra-agreement.cra.yaml (amounts_public: false)",
    resolvingRecord: "the School District Compensation Agreement",
  },
];

/** Net public subsidy ($) = forgone property tax + (forgone sales tax, if the DCTE is
 *  taken) − the school-compensation offset. `dcteTaken` is the equipment/DCTE on-off
 *  toggle (the application is `[open]`; default on — the question is the magnitude). */
export function netSubsidyModel(dcteTaken: boolean): Model {
  return (d) =>
    abatement(d.building_share) +
    (dcteTaken ? salesTaxExemption(d.building_share, d.refresh) : 0) -
    d.school_comp;
}

/** Net public subsidy per job — the headline the four knobs all move (the deciding
 *  number, the cost-of-opacity object). */
export function netSubsidyPerJobModel(dcteTaken: boolean): Model {
  const net = netSubsidyModel(dcteTaken);
  return (d) => net(d) / d.jobs;
}

// --- the discrete profiles (the default view; match buildAbatementPerJob) -----
export interface LedgerProfile {
  key: "stated" | "equipment" | "hyperscale" | "govcloud";
  label: string;
  buildingShare: number;
  jobs: number;
  note: string;
  abatementUsd: number;
  keptUsd: number;
  exemptionUsd: number; // DCTE taken, refresh at central
  netSubsidyUsd: number;
  abatementPerJobUsd: number;
}

const REFRESH_CENTRAL = 1.5;

export function ledgerProfiles(): LedgerProfile[] {
  return CRA_PROFILES.map((p) => {
    const ab = abatement(p.buildingShare);
    const ex = salesTaxExemption(p.buildingShare, REFRESH_CENTRAL);
    return {
      ...p,
      abatementUsd: ab,
      keptUsd: keptByPublic(p.buildingShare),
      exemptionUsd: ex,
      netSubsidyUsd: ab + ex,
      abatementPerJobUsd: abatementPerJob(p.buildingShare, p.jobs),
    };
  });
}

// --- the SSR ledger lines (bands; match the essay's "ledger in a band") --------
function profileBand(pick: (p: LedgerProfile) => number): { low: number; high: number; central: number } {
  const profiles = ledgerProfiles();
  const vals = profiles.map(pick);
  const stated = profiles.find((p) => p.key === "stated");
  return { low: Math.min(...vals), high: Math.max(...vals), central: stated ? pick(stated) : vals[0] };
}

export interface LedgerLine {
  key: string;
  label: string;
  band: { low: number; high: number; central: number };
  register: "verified" | "assumption" | "open" | "inference";
  note: string;
}

/** The fifteen-year ledger, every line a band over the four profiles (the SSR table). */
export function ledgerLines(): LedgerLine[] {
  return [
    {
      key: "abatement",
      label: "Property-tax abatement",
      band: profileBand((p) => p.abatementUsd),
      register: "inference",
      note: "75%/15-yr on the real-property share of the $500M",
    },
    {
      key: "exemption",
      label: "Sales-tax exemption (if taken)",
      band: profileBand((p) => p.exemptionUsd),
      register: "open",
      note: "DCTE on equipment + materials; application [open]",
    },
    {
      key: "kept",
      label: "Un-abated property tax (25%, public keeps)",
      band: profileBand((p) => p.keptUsd),
      register: "inference",
      note: "the slice the abatement doesn't touch",
    },
    {
      key: "net",
      label: "Net public subsidy (gives)",
      band: profileBand((p) => p.netSubsidyUsd),
      register: "inference",
      note: "abatement + exemption, before water / grid / school offset",
    },
  ];
}

// --- the headline band contract (for the public balance sheet, #273) ----------
export function netSubsidyOutcome(priors: Prior[] = ECON_PRIORS, dcteTaken = true): UncertainOutcome {
  const band = outcomeBand(priors, netSubsidyModel(dcteTaken));
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

/** County employment baseline — the ~50 jobs against it (BLS QCEW / Census ACS). */
export const COUNTY_JOBS_2023 = 49_577;
