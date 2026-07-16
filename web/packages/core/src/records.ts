/** Helpers for rendering the records feed (per-kind pages, #66). */
import type { RecordItem } from "./feeds";

/** Human labels for the contractor-agnostic record groups (mirrors nav.yaml). */
export const RECORD_GROUP_LABELS: Record<string, string> = {
  deeds: "Deeds",
  "permits-epa": "Permits — Ohio EPA / USACE",
  "permits-idem": "Permits — IDEM (Indiana)",
  "permits-npdes": "Permits — NPDES",
  "permits-sos": "Business filings — Secretary of State",
  plans: "Plans",
  opc: "Cost estimates (OPC)",
};

export function groupLabel(group: string): string {
  return RECORD_GROUP_LABELS[group] ?? group;
}

/** Distinct groups present in the feed, in the canonical order above. */
export function groupsOf(records: RecordItem[]): string[] {
  const present = new Set(records.map((r) => r.group));
  const ordered = Object.keys(RECORD_GROUP_LABELS).filter((g) => present.has(g));
  // Any unknown groups (forward-compat) appended in first-seen order.
  for (const g of present) if (!ordered.includes(g)) ordered.push(g);
  return ordered;
}

/**
 * Whether a value is a *structured* field — a non-empty object or array, which
 * renders as a hierarchy (the `FieldValue` component's bullet tree) rather than a
 * flat cell. Scalars (incl. empty containers) are not.
 */
export function isStructured(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0;
  return value !== null && typeof value === "object" && Object.keys(value as object).length > 0;
}

/** Format one scalar field value for display (mirrors the legacy `_fmt_scalar`). */
export function formatScalar(value: unknown): string {
  if (value == null) return "—";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.length ? value.map(formatScalar).join("; ") : "—";
  if (typeof value === "object") return Object.keys(value as object).length ? "{…}" : "—";
  return String(value);
}

/** Whether a top-level field carried the `~` approximate marker. */
export function isApproximate(record: RecordItem, key: string): boolean {
  return record.approximate_paths.some((p) => p === key || p.startsWith(`${key}.`));
}

/**
 * Prepend the `~` approximate marker — but only when the value doesn't already
 * carry one (some values keep the marker inline in the source, and are *also*
 * listed in `approximate_paths`; don't double it to `~~`).
 */
export function withApproxMark(text: string, approx: boolean): string {
  return approx && !text.startsWith("~") ? `~${text}` : text;
}
