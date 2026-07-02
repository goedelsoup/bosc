/**
 * Build-time data for the Water chapter (#222, corrected pass). Two *distinct*
 * water stories the corpus keeps separate (and an earlier draft conflated):
 *
 *  1. **The discharge story — "the river is already effluent"** (`discharge`).
 *     What the campus discharges *into*: at design low flow the county WWTP
 *     discharges + the campus's routed FM-2 industrial discharge vastly exceed the
 *     streams' natural low flow — the Ottawa leaving Lima runs ~93% treated
 *     effluent. `[verified: document]` from the NPDES fact sheets (the feed's
 *     `assimilative` rows) + the cited water balance.
 *  2. **The consumptive-draw story** (`floors` + the draw model). What the campus
 *     takes *out of the basin*: the net evaporative loss (feed `consumptive_loss`),
 *     a permanent basin loss. The campus draws from Lima's **off-stream reservoirs
 *     (filled at high flow), NOT the Ottawa** — so setting the loss against the
 *     river's low flow is a basin-scale **worst-case bound**, carried as
 *     `[inference]`, never a river withdrawal.
 *
 * Figures come from the `hydrology-scenarios` feed (the same numbers the hydrology
 * dashboard renders — no fork): the buildout cooling demand / consumptive fraction
 * / consumptive loss, the assimilative discharge rows, and `receiving_7q10`. The
 * seasonal floors (summer 30Q10, driest 1Q10) and the campus FM-2 discharge are
 * cited constants. NOT client-safe; the island consumes the plain `DilutionData`.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { ScenarioResult } from "./feeds";
import { round } from "./format";

export interface DilutionFloor {
  key: "annual" | "summer" | "driest";
  label: string;
  /** The river's low-flow floor, cfs. */
  cfs: number;
  cite: string;
  note?: string;
}

/** One WWTP discharge vs its receiving stream's design low flow (feed-sourced). */
export interface DischargeRow {
  discharger: string;
  receiving: string;
  dischargeCfs: number;
  lowFlowCfs: number;
}

/**
 * The DISCHARGE story — "the river is already effluent." At design low flow the
 * county WWTP discharges (and the campus's own routed industrial discharge) vastly
 * exceed the streams' natural low flow. This is what the campus discharges *into* —
 * distinct from the consumptive draw, and `[verified: document]` from the fact
 * sheets, not an inference.
 */
export interface DilutionDischarge {
  /** WWTP discharges summed, cfs (from the feed's assimilative rows). */
  wwtpCfs: number;
  /** Natural low flow of the receiving streams summed, cfs (feed). */
  naturalCfs: number;
  /** The campus's routed FM-2 industrial discharge, cfs (cited; not in this feed). */
  campusFm2Cfs: number;
  /** Effluent share of the Ottawa leaving Lima at design low flow, % (derived). */
  effluentPct: number;
  /** Per-WWTP rows (feed). */
  rows: DischargeRow[];
  cite: string;
}

export interface DilutionData {
  /** Max cooling draw of the cited buildout scenario, MGD. */
  maxCoolingMgd: number;
  /** Consumptive fraction (buildout assumption). */
  consumptiveFraction: number;
  /** Net consumptive draw per MGD of cooling, cfs (bakes in cfrac × MGD→cfs). */
  cfsPerCoolingMgd: number;
  /** Net consumptive draw at full buildout, cfs (feed-sourced). */
  drawAtBuildoutCfs: number;
  /** The Ottawa's live USGS flow, cfs (context — the dashboard re-runs on it). */
  ottawaLiveCfs: number | null;
  /** Receiving-stream low-flow floors: annual + the seasonal pinch (cited). */
  floors: DilutionFloor[];
  /** The discharge story — what the campus discharges into (the river is effluent). */
  discharge: DilutionDischarge;
  /** True when the buildout scenario resolved from the feed (else curated fallback). */
  fromFeed: boolean;
}

// MGD → cfs (1 million gallons/day = 1.547 cubic feet/second). A standard unit
// conversion, used only as the fallback slope when the feed is absent.
const CFS_PER_MGD = 1.547;

const OTTAWA_SEASONAL_CITE =
  "data/reference/hydrology/low-flow-7q10.yaml · Ottawa River context (Ohio EPA NPDES 2IG00001, USGS 04187100)";

// The campus's routed FM-2 industrial discharge, cfs — the cited water-balance
// figure (docs/HYDROLOGY.md §1); not carried in the hydrology-scenarios feed.
const CAMPUS_FM2_CFS = 3.87;

const FALLBACK_DISCHARGE_ROWS: DischargeRow[] = [
  { discharger: "Shawnee II WWTP", receiving: "Ottawa River", dischargeCfs: 4.64, lowFlowCfs: 0.2 },
  { discharger: "American Bath WWTP", receiving: "Pike Run", dischargeCfs: 2.32, lowFlowCfs: 0.03 },
  { discharger: "American II WWTP", receiving: "Dug Run", dischargeCfs: 1.86, lowFlowCfs: 0.78 },
];

export function buildDilution(): DilutionData {
  const scenarios = hasFeed("hydrology-scenarios") ? loadFeed<ScenarioResult[]>("hydrology-scenarios") : [];
  const buildout = scenarios.find((s) => s.scenario.name === "buildout");

  // Feed-sourced (no fork); curated fallbacks only for the minimal CI fixture.
  const maxCoolingMgd = buildout?.scenario.cooling_demand.value ?? 3.92;
  const consumptiveFraction = buildout?.scenario.consumptive_fraction.value ?? 0.8;
  const drawAtBuildoutCfs =
    buildout?.consumptive_loss.value ?? maxCoolingMgd * consumptiveFraction * CFS_PER_MGD;
  const annual7q10 = buildout?.receiving_7q10?.value ?? 0.2;
  const ottawaLiveCfs = buildout?.receiving_live?.value ?? null;
  const cfsPerCoolingMgd =
    maxCoolingMgd > 0 ? drawAtBuildoutCfs / maxCoolingMgd : consumptiveFraction * CFS_PER_MGD;

  const floors: DilutionFloor[] = [
    {
      key: "annual",
      label: "Annual 7Q10",
      cfs: annual7q10,
      cite: "Ohio EPA NPDES fact sheet 2IG00001 (Ottawa at Lima, USGS 04187100)",
    },
    {
      key: "summer",
      label: "Summer 30Q10",
      cfs: 1.6,
      cite: OTTAWA_SEASONAL_CITE,
      note: "the May–Oct pinch — when the cooling draw also peaks",
    },
    {
      key: "driest",
      label: "Driest week 1Q10",
      cfs: 0.0,
      cite: OTTAWA_SEASONAL_CITE,
      note: "the Ottawa mainstem nearly dries — 1Q10 = 0 cfs",
    },
  ];

  // The discharge story (the river is already effluent): WWTP discharges + the
  // receiving streams' natural low flows from the feed's assimilative rows; the
  // campus FM-2 routed discharge is the cited constant; the effluent share derives.
  const assim = buildout?.assimilative ?? [];
  const rows: DischargeRow[] = assim.map((a) => ({
    discharger: a.discharger,
    receiving: a.receiving_water,
    dischargeCfs: round(a.discharge.value ?? 0, 2),
    lowFlowCfs: a.design_low_flow.value ?? 0,
  }));
  const dischargeRows = rows.length > 0 ? rows : FALLBACK_DISCHARGE_ROWS;
  const wwtpCfs = round(
    dischargeRows.reduce((s, r) => s + r.dischargeCfs, 0),
    2,
  );
  const naturalCfs = round(
    dischargeRows.reduce((s, r) => s + r.lowFlowCfs, 0),
    2,
  );
  const effluentCfs = wwtpCfs + CAMPUS_FM2_CFS;
  const discharge: DilutionDischarge = {
    wwtpCfs,
    naturalCfs,
    campusFm2Cfs: CAMPUS_FM2_CFS,
    effluentPct: Math.round((effluentCfs / (effluentCfs + naturalCfs)) * 100),
    rows: dischargeRows,
    cite: "docs/HYDROLOGY.md §1 · feed assimilative (Ohio EPA NPDES fact sheets) + the cited campus FM-2 routed discharge",
  };

  return {
    maxCoolingMgd,
    consumptiveFraction,
    cfsPerCoolingMgd,
    drawAtBuildoutCfs,
    ottawaLiveCfs,
    floors,
    discharge,
    fromFeed: !!buildout,
  };
}

/** Net consumptive draw (cfs) at a given cooling demand (MGD), per the model. */
export function drawCfs(data: DilutionData, coolingMgd: number): number {
  return coolingMgd * data.cfsPerCoolingMgd;
}

/** Draw ÷ floor — how many times the river's low flow the draw is.
 *  `Infinity` when the floor is zero (the river is gone). */
export function dilutionMultiple(drawCfsValue: number, floorCfs: number): number {
  return floorCfs > 0 ? drawCfsValue / floorCfs : Number.POSITIVE_INFINITY;
}
