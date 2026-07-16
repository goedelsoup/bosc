/**
 * The OPC roundabout-scenario model — a native successor to the retired marimo
 * `opc_scenario.py` notebook (the marimo investigation is `docs/marimo-integration-
 * investigation.md`; the platform consolidated on the Astro frontend, so the notebook
 * was reimplemented as the `OpcScenario` island rather than a WASM export).
 *
 * Client-safe (no `node:` imports): the `.astro` page loads the `records` feed with the
 * node bundle reader, hands the already-parsed rows to `opcScenarioFromRecords` here, and
 * passes the plain result to the island as a prop — and the island and the SSR `<noscript>`
 * fallback share `modeledRows`/`programTotal`, so they can never compute different numbers.
 *
 * Discipline: the per-intersection `construction_subtotal` is the high-confidence figure
 * `[verified]`; the modeled total is `subtotal × (1 + rate)` `[inference]` — a re-derivation
 * under a chosen contingency+inflation rate, NOT a second source of truth. At the source's
 * own 25% convention it reproduces the source totals (enforced by `opcScenario.test.ts`),
 * which is the chain-of-custody check: the explorer reads the reviewed corpus and re-prices
 * it, it never edits it.
 */
import type { RecordItem } from "./feeds";

/** The OPC summary artifact's `rel` in the records feed (mirrors `moneyFlow.OPC_REL`). */
export const OPC_REL = "aedg/roundabouts.summary.opc.yaml";

/** Fallback contingency+inflation convention if the record omits it (Tetra Tech: 25%). */
export const FALLBACK_CONTINGENCY_PCT = 25;

/** One Tetra Tech sub-estimate, narrowed to what the scenario needs. */
export interface OpcSubEstimate {
  name: string;
  /** High-confidence construction subtotal `[verified]`. */
  constructionSubtotal: number;
  /** The source total at the source's own contingency convention. */
  sourceTotal: number;
}

/** The plain, serializable scenario the page passes to the island as a prop. */
export interface OpcScenario {
  subs: OpcSubEstimate[];
  /** The source's contingency+inflation convention (Tetra Tech: 25%). */
  sourceContingencyPct: number;
  estimator: string;
  basis: string;
}

/** A sub-estimate with its re-derived total under a chosen rate. */
export interface ModeledRow extends OpcSubEstimate {
  modeledTotal: number;
}

interface RawSub {
  name?: unknown;
  construction_subtotal?: unknown;
  total?: unknown;
}
interface RawOpcFields {
  meta?: { contingency_and_inflation_pct?: unknown; estimator?: unknown; basis?: unknown };
  sub_estimates?: unknown;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/**
 * Extract the typed scenario from the OPC summary record in the `records` feed, or
 * `null` when it isn't present (the page renders a graceful note rather than break).
 */
export function opcScenarioFromRecords(records: RecordItem[]): OpcScenario | null {
  const rec = records.find((r) => r.rel === OPC_REL) ?? records.find((r) => r.group === "opc");
  if (!rec) return null;
  const f = rec.fields as RawOpcFields;
  const raw = Array.isArray(f.sub_estimates) ? (f.sub_estimates as RawSub[]) : [];
  const subs: OpcSubEstimate[] = [];
  for (const s of raw) {
    const subtotal = num(s.construction_subtotal);
    if (typeof s.name !== "string" || subtotal === null) continue;
    subs.push({ name: s.name, constructionSubtotal: subtotal, sourceTotal: num(s.total) ?? subtotal });
  }
  if (subs.length === 0) return null;
  return {
    subs,
    sourceContingencyPct: num(f.meta?.contingency_and_inflation_pct) ?? FALLBACK_CONTINGENCY_PCT,
    estimator: typeof f.meta?.estimator === "string" ? f.meta.estimator : "the contractor",
    basis: typeof f.meta?.basis === "string" ? f.meta.basis : "Conceptual",
  };
}

/**
 * Re-derive each selected total from its high-confidence construction subtotal under a
 * chosen contingency+inflation rate (the source convention is `sourceContingencyPct`).
 */
export function modeledRows(
  subs: readonly OpcSubEstimate[],
  ratePct: number,
  selected: ReadonlySet<string>,
): ModeledRow[] {
  const rate = 1 + ratePct / 100;
  return subs
    .filter((s) => selected.has(s.name))
    .map((s) => ({ ...s, modeledTotal: Math.round(s.constructionSubtotal * rate) }));
}

/** The modeled program construction cost — the sum of the selected modeled totals. */
export function programTotal(rows: readonly ModeledRow[]): number {
  return rows.reduce((sum, r) => sum + r.modeledTotal, 0);
}

/** The source program total — the sum of the selected source totals (for comparison). */
export function sourceProgramTotal(rows: readonly { sourceTotal: number }[]): number {
  return rows.reduce((sum, r) => sum + r.sourceTotal, 0);
}
