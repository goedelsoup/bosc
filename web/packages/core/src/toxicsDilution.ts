/**
 * Toxics seasonal-dilution model (epic #271 Phase 2, #264) — the consumer of the
 * uncertainty engine for the Water-corridor narrative. Client-safe so the island and the
 * SSR fallback agree.
 *
 * The argument you discover by dragging: the river's low flow shrinks across the cited
 * regimes (summer 30Q10 → annual 7Q10 → driest 1Q10 = 0) while the treated-effluent +
 * campus loads stay constant, so the Ottawa leaving Lima climbs toward 100% effluent and
 * the dilution collapses. The effluent/natural constants come from `buildDilution()` (the
 * feed — no fork), passed in; the regimes + RSEI layer are cited constants here.
 *
 * Discipline (load-bearing): EPA's RSEI is a *modeled, comparative* screen — it ranks who
 * releases what, it does NOT measure the river. The per-discharger screening
 * concentrations are `[inference: derived]` (annual pounds fully mixed at the 7Q10, no
 * mixing zone / decay / volatilization). Only Lima Refining's Ottawa receiving water is
 * independently ECHO-cited. There is no "exceeds capacity" verdict — the resolving record
 * (DMRs, ambient sampling) is `[open]`.
 */
import type { Prior, UncertainOutcome } from "./uncertainty";

/** The Ottawa's cited annual 7Q10 (cfs) — the anchor the regimes scale from. */
export const ANNUAL_OTTAWA_7Q10 = 0.2;

export interface FlowRegime {
  key: "summer" | "annual" | "driest";
  label: string;
  ottawaCfs: number;
  note: string;
}

/** The cited low-flow regimes (Ohio EPA NPDES fact sheets · USGS 04187100). */
export const FLOW_REGIMES: FlowRegime[] = [
  {
    key: "summer",
    label: "Summer 30Q10",
    ottawaCfs: 1.6,
    note: "the May–Oct pinch, when the cooling draw also peaks",
  },
  {
    key: "annual",
    label: "Annual 7Q10",
    ottawaCfs: 0.2,
    note: "the drought flow Ohio writes discharge permits at — the river is 93% effluent",
  },
  {
    key: "driest",
    label: "Driest week 1Q10",
    ottawaCfs: 0.0,
    note: "the Ottawa mainstem nearly dries — what's left is effluent",
  },
];

/** The slider's upper bound (summer 30Q10). */
export const MAX_OTTAWA_CFS = 1.6;

/** Receiving-stream natural low flow at a given Ottawa flow — the cited summed low flow
 *  scaled proportionally, since all streams pinch together toward the dry floor. */
export function naturalAt(ottawaCfs: number, naturalAnnualCfs: number): number {
  return naturalAnnualCfs * (ottawaCfs / ANNUAL_OTTAWA_7Q10);
}

/** Effluent share of the river leaving Lima (%). → 100% as the river dries. */
export function effluentPct(effluentCfs: number, naturalCfs: number): number {
  return (effluentCfs / (effluentCfs + naturalCfs)) * 100;
}

/** How many times the river's own flow the effluent is (effluent ÷ natural). → ∞ at the
 *  dry floor — the dilution collapse, in one number. */
export function effluentMultiple(effluentCfs: number, naturalCfs: number): number {
  return naturalCfs > 0 ? effluentCfs / naturalCfs : Number.POSITIVE_INFINITY;
}

export interface RseiDischarger {
  name: string;
  score: number;
  /** Screening concentration at the cited 7Q10 (mg/L) — a coarse derived screen, NOT a
   *  measurement (annual pounds fully mixed at the 7Q10; no mixing zone / decay). */
  conc7q10MgL: number;
  topChemical: string;
  /** True only for the one whose receiving water is independently ECHO-cited (the rest
   *  are inferred from the coordinate cluster). */
  receivingCited: boolean;
  note: string;
}

/** The three RSEI water dischargers on the near-undiluted Ottawa reach (of 12 in the
 *  county) — `data/reference/rsei/` · docs/HYDROLOGY.md §1. Scores + screening concs cited. */
export const RSEI_DISCHARGERS: RseiDischarger[] = [
  {
    name: "INEOS USA LLC",
    score: 23_483_255,
    conc7q10MgL: 66,
    topChemical: "acrylonitrile (~99% cancer-weighted)",
    receivingCited: false,
    note: "the corridor's largest RSEI score; receiving water inferred from the coordinate cluster",
  },
  {
    name: "Lima Refining Co.",
    score: 1_899_615,
    conc7q10MgL: 165,
    topChemical: "benzene",
    receivingCited: true,
    note: "heaviest reported water release (~1.75M lb cumulative); the only ECHO-cited Ottawa receiving water (NPDES OH0002623)",
  },
  {
    name: "PCS Nitrogen Ohio LP",
    score: 532_740,
    conc7q10MgL: 274,
    topChemical: "formaldehyde",
    receivingCited: false,
    note: "receiving water inferred",
  },
];

/** Screening concentration at a given Ottawa flow (mg/L) — scales inversely with flow
 *  from the 7Q10 anchor. A coarse `[inference: derived]` screen, never a measurement. */
export function screeningConc(d: RseiDischarger, ottawaCfs: number): number {
  return ottawaCfs > 0 ? d.conc7q10MgL * (ANNUAL_OTTAWA_7Q10 / ottawaCfs) : Number.POSITIVE_INFINITY;
}

/** The low-flow driver, as an `[open]` prior — the operative low flow is seasonal and the
 *  in-stream reality is unmeasured. */
export const LOW_FLOW_PRIOR: Prior = {
  key: "ottawa_low_flow",
  label: "Ottawa low-flow regime",
  register: "open",
  unit: "cfs",
  dist: { kind: "uniform", low: 0, high: MAX_OTTAWA_CFS },
  source: "Ohio EPA NPDES fact sheets · 7Q10 / 30Q10 / 1Q10 (USGS 04187100)",
  resolvingRecord: "in-stream ambient sampling / DMRs (none in the record)",
};

/** The assimilative band — effluent share across the low-flow regimes. `[open]`: the
 *  actual capacity is unmeasured (no DMRs, no ambient). Summer (least) → driest (100%),
 *  central = the cited annual-7Q10 93%. Emitted for the public balance sheet (#273). */
export function assimilativeOutcome(effluentCfs: number, naturalAnnualCfs: number): UncertainOutcome {
  return {
    key: "toxics_effluent_share",
    label: "River leaving Lima that is treated effluent",
    unit: "pct",
    central: effluentPct(effluentCfs, naturalAt(ANNUAL_OTTAWA_7Q10, naturalAnnualCfs)),
    low: effluentPct(effluentCfs, naturalAt(MAX_OTTAWA_CFS, naturalAnnualCfs)),
    high: 100,
    register: "open",
    drivers: [LOW_FLOW_PRIOR],
    resolvingRecord: "in-stream ambient sampling / DMRs (none in the record)",
  };
}
