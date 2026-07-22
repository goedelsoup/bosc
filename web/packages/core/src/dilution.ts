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
 * Figures come entirely from the `hydrology-scenarios` feed (the same numbers the hydrology
 * dashboard renders — no fork): the buildout cooling demand / consumptive fraction /
 * consumptive loss, the assimilative discharge rows, `receiving_7q10`, and — since #1633 — the
 * cited **seasonal floors** (`receiving_summer_30q10` / `receiving_1q10`) and the campus's own
 * routed **industrial discharge** (`campus_routed_discharge`, Lima's FM-2). No Lima constant is
 * baked in here: a site whose feed carries no buildout scenario **locks** (`fromFeed: false`,
 * empty floors/rows) rather than rendering Lima's numbers as a fallback. NOT client-safe; the
 * island consumes the plain `DilutionData`.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { ProvenancedValue, ScenarioResult } from "./feeds";
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
  /** The campus's own routed industrial discharge, cfs — the feed's `campus_routed_discharge`
   *  (Lima's FM-2); 0 when the scenario's balance has no discharging demand node. */
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

// The locked shell for a thin site (no buildout scenario in its feed): empty, never Lima's
// numbers. Consumers gate on `fromFeed` and render an "ask for the source" panel instead (#1633).
const LOCKED: DilutionData = {
  maxCoolingMgd: 0,
  consumptiveFraction: 0,
  cfsPerCoolingMgd: 0,
  drawAtBuildoutCfs: 0,
  ottawaLiveCfs: null,
  floors: [],
  discharge: { wwtpCfs: 0, naturalCfs: 0, campusFm2Cfs: 0, effluentPct: 0, rows: [], cite: "" },
  fromFeed: false,
};

/** One cited low-flow floor from a feed provenanced value, or null when the feed omits it. */
function floorFrom(
  key: DilutionFloor["key"],
  label: string,
  v: ProvenancedValue | null | undefined,
  note?: string,
): DilutionFloor | null {
  if (v?.value == null) return null;
  return { key, label, cfs: v.value, cite: v.citation ?? v.source ?? "", note };
}

export function buildDilution(): DilutionData {
  const scenarios = hasFeed("hydrology-scenarios") ? loadFeed<ScenarioResult[]>("hydrology-scenarios") : [];
  const buildout = scenarios.find((s) => s.scenario.name === "buildout");
  // Thin site: lock rather than fall back to Lima's constants (the #1633 discipline).
  if (!buildout) return LOCKED;

  // Every figure is feed-sourced — no fork, no Lima literal.
  const maxCoolingMgd = buildout.scenario.cooling_demand.value ?? 0;
  const consumptiveFraction = buildout.scenario.consumptive_fraction.value ?? 0;
  const drawAtBuildoutCfs = buildout.consumptive_loss.value ?? 0;
  const ottawaLiveCfs = buildout.receiving_live?.value ?? null;
  const cfsPerCoolingMgd = maxCoolingMgd > 0 ? drawAtBuildoutCfs / maxCoolingMgd : 0;

  // The cited low-flow floors: annual 7Q10 + the two seasonal floors, all from the feed (#1633).
  // A driest-week floor of 0 means the mainstem effectively dries at design low flow.
  const driest = buildout.receiving_1q10;
  const floors: DilutionFloor[] = [
    floorFrom("annual", "Annual 7Q10", buildout.receiving_7q10),
    floorFrom(
      "summer",
      "Summer 30Q10",
      buildout.receiving_summer_30q10,
      "the growing-season pinch — when the cooling draw also peaks",
    ),
    floorFrom(
      "driest",
      "Driest week 1Q10",
      driest,
      driest?.value === 0 ? "the mainstem nearly dries — 1Q10 = 0 cfs" : undefined,
    ),
  ].filter((f): f is DilutionFloor => f !== null);

  // The discharge story (the river is already effluent): WWTP discharges + the receiving streams'
  // natural low flows from the feed's assimilative rows; the campus's own routed discharge from the
  // feed's `campus_routed_discharge` (Lima's FM-2); the effluent share derives.
  const assim = buildout.assimilative ?? [];
  const rows: DischargeRow[] = assim.map((a) => ({
    discharger: a.discharger,
    receiving: a.receiving_water,
    dischargeCfs: round(a.discharge.value ?? 0, 2),
    lowFlowCfs: a.design_low_flow.value ?? 0,
  }));
  const wwtpCfs = round(
    rows.reduce((s, r) => s + r.dischargeCfs, 0),
    2,
  );
  const naturalCfs = round(
    rows.reduce((s, r) => s + r.lowFlowCfs, 0),
    2,
  );
  const campusFm2Cfs = round(buildout.campus_routed_discharge?.value ?? 0, 2);
  const effluentCfs = wwtpCfs + campusFm2Cfs;
  const denom = effluentCfs + naturalCfs;
  const discharge: DilutionDischarge = {
    wwtpCfs,
    naturalCfs,
    campusFm2Cfs,
    effluentPct: denom > 0 ? Math.round((effluentCfs / denom) * 100) : 0,
    rows,
    cite: "feed assimilative (NPDES fact sheets) + the campus's cited routed discharge (hydrology-scenarios)",
  };

  return {
    maxCoolingMgd,
    consumptiveFraction,
    cfsPerCoolingMgd,
    drawAtBuildoutCfs,
    ottawaLiveCfs,
    floors,
    discharge,
    fromFeed: true,
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
