// The fact-aggregation surface (#1588) — deterministic server-side totals over the `facts`
// feed. `get_facts` (#1587) ships the normalized `(subject, predicate, value, unit, status)`
// tuples; `factAggregate` is the arithmetic tier on top: it does the sum / count / mean /
// product the model would otherwise have to pull every row to compute, and hands back one
// grouped total with a human-readable `derivation`, a `confidence`, a `caveat`, and the
// `evidence_ids` of the facts that fed it.
//
// It generalizes `watermark.facility.power.derive_power_basis`'s inline arithmetic
// (`backup_mw = genset_count × genset_rating`, `facility_draw = it_load × PUE`) into a
// data-driven recipe that reads the exported facts rather than re-deriving off profile
// constants — the same numbers, now one queryable surface (the issue's motivating example,
// `backup_generation_capacity_mw` grouped by project → `114 × 2.75 MW` = 313.5 MW).
//
// Pure + DOM-free (this is `@watermark/core`): the Cloudflare Pages Function
// (`handleAggregateFacts`) fetches `facts.json`, filters, and calls in here; the Astro site
// can import the exact same engine so the MW math is computed once, not hand-duplicated.

import type { Confidence, FactItem, FactStatus } from "./feeds";
import { round } from "./format";

/** How the source facts within a group are combined into one total. */
export type AggOp = "sum" | "count" | "mean" | "product";

/** The dimension a metric is partitioned on. `site` is the single whole-site group. */
export type GroupDim = "subject" | "subject_kind" | "feed" | "site";

/**
 * A named aggregation recipe over the facts feed. `inputs` are the predicate name(s) the
 * metric draws on: for `product` the ordered factors (`genset_count × genset_rating`), for
 * `sum`/`mean` the single predicate, for `count` the optional predicate (empty ⇒ count every
 * matching fact). `subjectKind` scopes the recipe to the rows it means (a product must not
 * sweep in an unrelated predicate that happens to share a name); `unit` is the output unit
 * (null ⇒ inherit the inputs' common unit). `caveat` is the standing, metric-specific honesty
 * note prepended to every result's caveat.
 */
export interface FactMetric {
  key: string;
  label: string;
  op: AggOp;
  inputs: string[];
  unit: string | null;
  subjectKind?: string;
  caveat: string;
}

/**
 * The v1 registry — the cross-predicate derivations that aren't a simple group sum, lifted
 * from `derive_power_basis`. Simple sum/count/mean of any single predicate is served
 * generically via the `<op>:<predicate>` grammar (`resolveMetric`), so the registry only
 * carries the recipes that combine *different* predicates. Keys are lowercase snake_case.
 */
export const FACT_METRICS: readonly FactMetric[] = [
  {
    key: "backup_generation_capacity_mw",
    label: "Backup generation capacity",
    op: "product",
    inputs: ["genset_count", "genset_rating"],
    unit: "MW",
    subjectKind: "facility",
    caveat:
      "Emergency BACKUP generation (air-permit reciprocating gensets), not primary/continuous " +
      "generation; the N+1 fleet is sized to the IT + mechanical load. Whether any primary " +
      "on-site generation exists is an open evidence question.",
  },
  {
    key: "facility_draw_mw",
    label: "Total facility draw (IT × PUE)",
    op: "product",
    inputs: ["it_load", "pue"],
    unit: "MW",
    subjectKind: "facility",
    caveat:
      "Facility draw = IT load × PUE; PUE is a banded ASSUMPTION (total facility power / IT " +
      "power), not a disclosure, so the product is an inference even where the IT load is " +
      "document-anchored.",
  },
] as const;

/** One aggregated total — the answer `aggregate_facts` returns per group. */
export interface FactAggregate {
  metric: string;
  op: AggOp;
  group_by: GroupDim;
  /** The group key, e.g. `"facility:lima"` (subject), `"facility"` (kind), `"site"` (total). */
  group: string;
  group_label: string;
  value: number | null;
  unit: string | null;
  /** Human-readable arithmetic, e.g. `"114 × 2.75 MW"` or `"12000 + 20000 = 32000 jobs"`. */
  derivation: string;
  /** How many source facts fed the total. */
  n: number;
  confidence: Confidence;
  /** The weakest input status — a product never reports stronger than `inference`. */
  status: FactStatus;
  caveat: string | null;
  /** The `<subject>/<predicate>` handles of the facts summed — each re-fetchable via get_facts. */
  evidence_ids: string[];
}

/** A registry row as advertised in discovery mode (no `metric` ⇒ list what can be aggregated). */
export interface MetricDescriptor {
  key: string;
  label: string;
  op: AggOp;
  inputs: string[];
  unit: string | null;
  caveat: string;
}

export function listMetrics(): MetricDescriptor[] {
  return FACT_METRICS.map((m) => ({
    key: m.key,
    label: m.label,
    op: m.op,
    inputs: m.inputs,
    unit: m.unit,
    caveat: m.caveat,
  }));
}

// --- metric resolution --------------------------------------------------------------

const OP_SPEC_RE = /^(sum|count|mean|product):(.+)$/;

/**
 * Resolve a `metric` param to a recipe: a registered key, or the generic `<op>:<predicate>`
 * grammar (`sum:total_employment`, `mean:avg_weekly_wage`, `count:genset_count`,
 * `product:genset_count,genset_rating`), or the bare word `count` (count every matching
 * fact). Returns null for anything unrecognized so the caller can surface the registry.
 */
export function resolveMetric(metric: string): FactMetric | null {
  const raw = metric.trim();
  if (!raw) return null;
  const lower = raw.toLowerCase();

  const named = FACT_METRICS.find((m) => m.key === lower);
  if (named) return named;

  if (lower === "count") {
    return { key: "count", label: "count", op: "count", inputs: [], unit: "facts", caveat: "" };
  }

  const m = OP_SPEC_RE.exec(lower);
  if (!m) return null;
  const op = m[1] as AggOp;
  const preds = m[2]
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (op === "product" && preds.length < 2) return null; // a product needs ≥2 factors
  if ((op === "sum" || op === "mean") && preds.length !== 1) return null;
  return {
    key: lower,
    label: lower,
    op,
    inputs: op === "count" && preds.length === 1 && preds[0] === "*" ? [] : preds,
    unit: null,
    caveat: "",
  };
}

// --- deterministic combination of evidence tags ------------------------------------

const STATUS_RANK: Record<FactStatus, number> = { open: 0, inference: 1, reference: 2, verified: 3 };
const CONF_RANK: Record<Confidence, number> = { low: 0, medium: 1, high: 2 };
const RANK_STATUS = ["open", "inference", "reference", "verified"] as const;
const RANK_CONF = ["low", "medium", "high"] as const;

/** The weakest (lowest-rank) status across the inputs — an aggregate is only as strong as its
 * weakest quantified fact. Empty ⇒ `inference` (a computed total is not itself a document). */
function weakestStatus(statuses: FactStatus[]): FactStatus {
  if (!statuses.length) return "inference";
  return RANK_STATUS[Math.min(...statuses.map((s) => STATUS_RANK[s]))];
}

/** The weakest input confidence; empty ⇒ `medium` (the ProvenancedValue default). */
function weakestConfidence(confs: Confidence[]): Confidence {
  if (!confs.length) return "medium";
  return RANK_CONF[Math.min(...confs.map((c) => CONF_RANK[c]))];
}

// --- helpers -----------------------------------------------------------------------

const MAX_DERIVATION_TERMS = 6;

/** Compact number: integers bare, floats trimmed to 4 places — matches "114 × 2.75". */
function fmtNum(n: number): string {
  return Number.isInteger(n) ? String(n) : String(round(n, 4));
}

/** True for a usable numeric fact value (a null/absent value can't feed arithmetic). */
function hasValue(f: FactItem): f is FactItem & { value: number } {
  return typeof f.value === "number" && Number.isFinite(f.value);
}

function factKey(f: FactItem): string {
  return `${f.subject}/${f.predicate}`;
}

function unitSuffix(unit: string | null): string {
  return unit ? ` ${unit}` : "";
}

/** The (key, label) of the group a fact falls into for the requested dimension. */
function groupOf(f: FactItem, dim: GroupDim): { key: string; label: string } {
  switch (dim) {
    case "subject":
      return { key: f.subject, label: f.subject_label };
    case "subject_kind":
      return { key: f.subject_kind, label: f.subject_kind };
    case "feed":
      return { key: f.feed, label: f.feed };
    case "site":
      return { key: "site", label: "site total" };
  }
}

/** The output unit: the recipe's declared unit, else the inputs' common unit (else null). */
function resolveUnit(metric: FactMetric, facts: FactItem[]): string | null {
  if (metric.unit !== null) return metric.unit;
  const units = new Set(facts.map((f) => f.unit ?? "").filter((u) => u !== ""));
  return units.size === 1 ? [...units][0] : null;
}

/** Assemble the caveat: the recipe note, plus flags for modeled inputs / dropped subjects. */
function buildCaveat(base: string, hasInference: boolean, incomplete: boolean): string | null {
  const parts: string[] = [];
  if (base) parts.push(base);
  if (hasInference) parts.push("Includes modeled/assumption inputs (status ≤ inference).");
  if (incomplete) parts.push("Some subjects lacked the required inputs and were omitted.");
  return parts.length ? parts.join(" ") : null;
}

// --- the aggregation engine ---------------------------------------------------------

/**
 * Aggregate `facts` under `metric`, grouped by `dim`. Deterministic and total: every branch
 * returns one {@link FactAggregate} per non-empty group, ordered by group key. The `product`
 * op is computed per-subject (each subject supplies one value per factor) and then rolled up
 * to a coarser `dim` by summing the sub-products, so a multi-facility site totals correctly.
 */
export function aggregateFacts(facts: FactItem[], metric: FactMetric, dim: GroupDim): FactAggregate[] {
  const scoped = metric.subjectKind ? facts.filter((f) => f.subject_kind === metric.subjectKind) : facts;
  return metric.op === "product"
    ? aggregateProduct(scoped, metric, dim)
    : aggregateReduce(scoped, metric, dim);
}

/** sum / count / mean — a straight reduction over the matching facts in each group. */
function aggregateReduce(facts: FactItem[], metric: FactMetric, dim: GroupDim): FactAggregate[] {
  const preds = new Set(metric.inputs);
  // `count` with no predicate counts every scoped fact; otherwise keep the named predicate(s).
  const matching = facts.filter((f) => preds.size === 0 || preds.has(f.predicate));
  const numeric = metric.op === "count" ? matching : matching.filter(hasValue);

  const groups = new Map<string, { label: string; facts: FactItem[] }>();
  for (const f of numeric) {
    const g = groupOf(f, dim);
    const bucket = groups.get(g.key) ?? { label: g.label, facts: [] };
    bucket.facts.push(f);
    groups.set(g.key, bucket);
  }

  const unit = resolveUnit(metric, numeric);
  const out: FactAggregate[] = [];
  for (const [key, { label, facts: gFacts }] of groups) {
    const values = gFacts.filter(hasValue).map((f) => f.value as number);
    const n = gFacts.length;
    let value: number;
    let unitOut: string | null;
    let derivation: string;
    if (metric.op === "count") {
      value = n;
      unitOut = "facts";
      derivation = preds.size ? `${n} facts with ${[...preds].join("/")}` : `${n} matching facts`;
    } else {
      const total = values.reduce((a, b) => a + b, 0);
      unitOut = unit;
      const terms = values.map(fmtNum);
      const shown =
        terms.length > MAX_DERIVATION_TERMS
          ? `${terms.slice(0, MAX_DERIVATION_TERMS).join(" + ")} + … (${terms.length} terms)`
          : terms.join(" + ");
      if (metric.op === "mean") {
        value = values.length ? round(total / values.length, 4) : 0;
        derivation = `(${shown}) / ${values.length} = ${fmtNum(value)}${unitSuffix(unitOut)}`;
      } else {
        value = round(total, 4);
        derivation =
          values.length > 1
            ? `${shown} = ${fmtNum(value)}${unitSuffix(unitOut)}`
            : `${fmtNum(value)}${unitSuffix(unitOut)}`;
      }
    }
    const statuses = gFacts.map((f) => f.status);
    const confs = gFacts
      .map((f) => f.evidence?.confidence)
      .filter((c): c is Confidence => c === "low" || c === "medium" || c === "high");
    out.push({
      metric: metric.key,
      op: metric.op,
      group_by: dim,
      group: key,
      group_label: label,
      value,
      unit: unitOut,
      derivation,
      n,
      confidence: weakestConfidence(confs),
      status: weakestStatus(statuses),
      caveat: buildCaveat(
        metric.caveat,
        statuses.some((s) => STATUS_RANK[s] <= STATUS_RANK.inference),
        false,
      ),
      evidence_ids: gFacts.map(factKey),
    });
  }
  out.sort((a, b) => a.group.localeCompare(b.group));
  return out;
}

/** One subject's product: one value per factor predicate, multiplied; null if any factor is absent. */
interface SubProduct {
  subject: string;
  subject_label: string;
  value: number;
  factors: FactItem[];
}

/** product — per-subject `a × b × …`, then summed into the requested (possibly coarser) group. */
function aggregateProduct(facts: FactItem[], metric: FactMetric, dim: GroupDim): FactAggregate[] {
  const preds = metric.inputs;
  // Index each subject's factor facts (first wins on a duplicate predicate — the facts feed
  // already deduped on (subject, predicate), so there is at most one).
  const bySubject = new Map<string, { label: string; byPred: Map<string, FactItem> }>();
  for (const f of facts) {
    if (!preds.includes(f.predicate) || !hasValue(f)) continue;
    const s = bySubject.get(f.subject) ?? { label: f.subject_label, byPred: new Map() };
    if (!s.byPred.has(f.predicate)) s.byPred.set(f.predicate, f);
    bySubject.set(f.subject, s);
  }

  let incomplete = false;
  const subProducts: SubProduct[] = [];
  for (const [subject, { label, byPred }] of bySubject) {
    const factors = preds.map((p) => byPred.get(p)).filter((f): f is FactItem => f !== undefined);
    if (factors.length !== preds.length) {
      incomplete = true; // subject is missing at least one factor — omit it
      continue;
    }
    const value = factors.reduce((acc, f) => acc * (f.value as number), 1);
    subProducts.push({ subject, subject_label: label, value: round(value, 4), factors });
  }

  // Roll the per-subject products up to the requested dimension.
  const groups = new Map<string, { label: string; subs: SubProduct[] }>();
  for (const sp of subProducts) {
    // A product's natural row is the subject; coarser dims read the group off any factor fact.
    const g = dim === "subject" ? { key: sp.subject, label: sp.subject_label } : groupOf(sp.factors[0], dim);
    const bucket = groups.get(g.key) ?? { label: g.label, subs: [] };
    bucket.subs.push(sp);
    groups.set(g.key, bucket);
  }

  const out: FactAggregate[] = [];
  for (const [key, { label, subs }] of groups) {
    const value = round(
      subs.reduce((a, s) => a + s.value, 0),
      4,
    );
    const unit = metric.unit;
    let derivation: string;
    if (subs.length === 1) {
      // The headline single-subject case: "114 × 2.75 MW".
      derivation = `${subs[0].factors.map((f) => fmtNum(f.value as number)).join(" × ")}${unitSuffix(unit)}`;
    } else {
      const terms = subs.map((s) => fmtNum(s.value));
      const shown =
        terms.length > MAX_DERIVATION_TERMS
          ? `${terms.slice(0, MAX_DERIVATION_TERMS).join(" + ")} + … (${terms.length} terms)`
          : terms.join(" + ");
      derivation = `${shown} = ${fmtNum(value)}${unitSuffix(unit)}`;
    }
    const allFactors = subs.flatMap((s) => s.factors);
    const statuses = allFactors.map((f) => f.status);
    const confs = allFactors
      .map((f) => f.evidence?.confidence)
      .filter((c): c is Confidence => c === "low" || c === "medium" || c === "high");
    // A product is a derivation: never report it stronger than `inference`, matching
    // derive_power_basis (backup_power / facility_draw are emitted `derived`).
    const status = weakestStatus([...statuses, "inference"]);
    out.push({
      metric: metric.key,
      op: "product",
      group_by: dim,
      group: key,
      group_label: label,
      value,
      unit,
      derivation,
      n: allFactors.length,
      confidence: weakestConfidence(confs),
      status,
      caveat: buildCaveat(metric.caveat, true, incomplete),
      evidence_ids: allFactors.map(factKey),
    });
  }
  out.sort((a, b) => a.group.localeCompare(b.group));
  return out;
}

// --- param parsing (shared with the Pages Function) --------------------------------

/** Map a `group_by` param (with its friendly aliases) to a {@link GroupDim}; default `subject`. */
export function parseGroupBy(v: unknown): GroupDim {
  const s = typeof v === "string" ? v.trim().toLowerCase() : "";
  if (s === "subject_kind" || s === "kind" || s === "type") return "subject_kind";
  if (s === "feed" || s === "source") return "feed";
  if (s === "site" || s === "all" || s === "total") return "site";
  return "subject"; // "subject" / "project" / default
}
