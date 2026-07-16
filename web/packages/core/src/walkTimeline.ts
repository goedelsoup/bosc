/**
 * The sequence-as-argument timeline spine (#225) — the walk's connective tissue.
 * Project BOSC's confidentiality went on *first*: the Mutual NDA was authorized
 * before the CRA abatement was voted, before the deeds were recorded — and the
 * public still could not name the customer from any of it. **The order is the
 * argument.**
 *
 * The three dated milestones are present-checked against the live `timeline` feed
 * (`inFeed`) so the spine and the library read the same events — no fork. The
 * fourth beat is the customer confirmation: the customer **is** Google
 * (`[verified]` — the AEDG release, allencountydatacenter.com, Liz Schwab's
 * committee testimony), and the sequence point is that it comes *last*, ~10 months
 * after the NDA. In the entity graph Google is an **annotation, not a node** — a
 * method choice (it's the customer, not a deal-mechanics party), not an open
 * question.
 *
 * NOT client-safe (imports the node bundle loader); rendered SSR by
 * `WalkTimeline.astro`.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { TimelineEntry } from "./feeds";

export type MilestoneKind = "confidential" | "approval" | "land" | "reveal";

export interface SpineMilestone {
  /** ISO date, or null for the undated reveal annotation. */
  date: string | null;
  label: string;
  detail: string;
  kind: MilestoneKind;
  cite: string;
  /** True when an event on this date is present in the live timeline feed. */
  inFeed: boolean;
}

export interface WalkSpine {
  milestones: SpineMilestone[];
  /** Total dated events in the feed the spine is drawn from (context). */
  totalEvents: number;
}

/** The curated confidentiality-first sequence (dates are the load-bearing facts). */
const SEQUENCE: Omit<SpineMilestone, "inFeed">[] = [
  {
    date: "2025-05-27",
    label: "Confidentiality goes on — Mutual NDA (Res #417-25)",
    detail:
      "The County authorizes a Mutual NDA with Bistrozzi (executed 2025-07-01) — a notify-and-minimize protocol agreed before any public-records request could be answered.",
    kind: "confidential",
    cite: "timeline · Res #417-25 (2025-05-27) · NDA executed 2025-07-01",
  },
  {
    date: "2025-07-10",
    label: "The public benefit is voted — CRA approved (Res #548-25)",
    detail:
      "The 75% / 15-year tax abatement is approved — first deliberated in a closed (G)(8) session on 2025-05-27, behind the NDA.",
    kind: "approval",
    cite: "timeline · Res #548-25 (2025-07-10)",
  },
  {
    date: "2025-08-13",
    label: "The land moves — deeds recorded → BISTROZZI LLC",
    detail:
      "Three Limited Warranty Deeds convey the assembled farms to a Delaware LLC — for “valuable consideration,” the price left blank on the DTE-100s.",
    kind: "land",
    cite: "timeline · deeds 202508130008300 / …312 / …316 (2025-08-13)",
  },
  {
    date: "2026-03-16",
    label: "The customer is confirmed: Google",
    detail:
      "Google is the data-center customer — [verified]: AEDG's release names a Google official (Molly Kocour Boyle), the allencountydatacenter.com community site launches, and Google testifies to the Ohio Select Committee (Liz Schwab). The point of the sequence is the timing — the public confirmation comes ~10 months after the NDA, last, not first. (In the entity graph Google is an annotation, not a node: it's the customer, not a party to the deal mechanics — a method choice, not an open question.)",
    kind: "reveal",
    cite: "AEDG release 2026-03-16 (Molly Kocour Boyle) · allencountydatacenter.com · Liz Schwab (Google) committee testimony · annotation in the graph, not a node",
  },
];

export function buildWalkSpine(): WalkSpine {
  const events = hasFeed("timeline") ? loadFeed<TimelineEntry[]>("timeline") : [];
  const dates = new Set(events.map((e) => e.date));
  return {
    milestones: SEQUENCE.map((m) => ({ ...m, inFeed: m.date != null && dates.has(m.date) })),
    totalEvents: events.length,
  };
}
