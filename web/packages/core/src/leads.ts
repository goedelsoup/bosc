/**
 * Open leads (design "Site Leads") — the presentation vocabulary + helpers for a site's
 * open-leads board.
 *
 * The lead DATA is now a per-site bundle feed (`leads`, #796), read from each site's committed
 * `data/site/leads.yaml` — so a peer carries its own leads, not Lima's. This module is what's
 * left once the data moved out: the `Lead` shape (the feed row type), the kind/status/filter
 * presentation maps, the (Lima-curated, presentation-only) `RECENTLY_CLOSED` + `LEAD_LIFECYCLE`
 * rails, and the `leadStats` / `leadCount` reducers — all now taking the feed's leads as input.
 *
 * PROVENANCE DISCIPLINE (enforced in the feed model `bosc.site.feeds.LeadItem`): a lead is
 * *unverified inference until a source corroborates it* — its evidence `tag` is only ever `open`
 * (a documented gap) or `inference` (a labeled reading), never `verified`, and `source` names
 * where the gap is recorded. No fabricated contributors or timestamps.
 */

/** The four lead kinds — the rail colour + the call-to-action verb come from `KIND_META`. */
export type LeadKind = "signal" | "question" | "redaction" | "claim";
/** Lead status — drives the chip; maps onto the repo's evidence palette. */
export type LeadStatus = "low" | "unanswered" | "withheld" | "review";
/** Evidence tag — a lead is only ever `[open]` (a gap) or `[inference]` (a reading), never
 *  `[verified]`; a narrowing of the canonical `TagKind` from `./evidence` (#579). */
export type LeadTag = Exclude<import("./evidence").TagKind, "verified">;

export interface Lead {
  /** Stable local id; mirrors the PRR item / source where apt (shown mono, like the comp). */
  id: string;
  kind: LeadKind;
  status: LeadStatus;
  tag: LeadTag;
  title: string;
  detail: string;
  /** The real citation — where this gap is recorded. */
  source: string;
  /** A linked GitHub tracking issue (watermark-directory/the-watermark-directory), when one exists. */
  issue?: number;
  /** A short standing note (the comp's "3 working on this" slot), used sparingly + truthfully. */
  note?: string;
}

/** Presentation vocab per kind: the board label, the CTA verb, a CSS modifier key. */
export const KIND_META: Record<LeadKind, { label: string; action: string; mod: string }> = {
  signal: { label: "Signal", action: "Help confirm", mod: "signal" },
  question: { label: "Open question", action: "Answer this", mod: "question" },
  redaction: { label: "Redaction", action: "Fill the gap", mod: "redaction" },
  claim: { label: "Claim", action: "Corroborate", mod: "claim" },
};

/** Presentation vocab per status: the chip label + a CSS modifier key. */
export const STATUS_META: Record<LeadStatus, { label: string; mod: string }> = {
  low: { label: "Low confidence", mod: "low" },
  unanswered: { label: "Unanswered", mod: "unanswered" },
  withheld: { label: "Withheld", mod: "withheld" },
  review: { label: "Under review", mod: "review" },
};

/** The board filters, in order (All first). */
export const LEAD_FILTERS: { key: "all" | LeadKind; label: string }[] = [
  { key: "all", label: "All" },
  { key: "signal", label: "Signals" },
  { key: "question", label: "Questions" },
  { key: "redaction", label: "Redactions" },
  { key: "claim", label: "Claims" },
];

/** Recently closed — real corpus closures (the comp's "Recently closed" rail). */
export interface ClosedLead {
  title: string;
  meta: string;
}

export const RECENTLY_CLOSED: ClosedLead[] = [
  {
    title: "NPDES construction-stormwater coverage located — 2GC08468*AG, effective 2025-11-10",
    meta: "closes #143 + #154 · sourced 2026-06-16",
  },
  {
    title: "County wastewater universe (PRR items 5–15) produced",
    meta: "PRR batch 2 · sourced 2026-06-12",
  },
  {
    title: "GLRI funding source resolved — OSU $327,450, 2023–2025",
    meta: "Shedekar CV · sourced 2026-06-06",
  },
];

/** How a lead closes — the real lead lifecycle (mirrors the submissions seam, not a verdict). */
export const LEAD_LIFECYCLE: { num: string; title: string; desc: string }[] = [
  {
    num: "1",
    title: "Logged as open",
    desc: "It joins this queue immediately, labeled as unverified inference.",
  },
  { num: "2", title: "Picked up", desc: "Contributors gather sources; the record team reviews them." },
  {
    num: "3",
    title: "Corroborated",
    desc: "If a source checks out, the lead enters the record with its citation.",
  },
  { num: "✓", title: "The bar moves", desc: "A closed lead nudges the site up the completeness curve." },
];

/** Board summary stats — derived from the site's own leads (the `leads` bundle feed, #796), not
 *  invented. `closedCount` is the recently-closed tally (the reference build's `RECENTLY_CLOSED`;
 *  0 for a site with no closed-leads record yet). */
export function leadStats(leads: Lead[], closedCount: number): { n: number; label: string; mod: string }[] {
  const withheld = leads.filter((l) => l.status === "withheld").length;
  const review = leads.filter((l) => l.status === "review").length;
  return [
    { n: leads.length, label: "open leads", mod: "inference" },
    { n: withheld, label: "withheld / sealed", mod: "open" },
    { n: review, label: "under review", mod: "inference" },
    { n: closedCount, label: "closed recently", mod: "verified" },
  ];
}

/** Count of leads in a filter bucket (`all` = every lead). */
export function leadCount(leads: Lead[], key: "all" | LeadKind): number {
  return key === "all" ? leads.length : leads.filter((l) => l.kind === key).length;
}
