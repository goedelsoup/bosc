/**
 * Build-time data for the Cost chapter's follow-the-money flow (#222 → #223).
 * The public's roadwork money, traced: $14.5M "Company Contribution" collected up
 * front → the Tetra Tech OPC estimate (6 corridor line items) → the first actual
 * award (Eagle Bridge, far under) → the §5.5 grant-refund arrow back to the
 * developer. Plus the parallel abatement strand.
 *
 * The OPC line items + total are read from the `records` feed (the same numbers
 * the library renders — no fork). The contribution, the actual award, and the
 * abatement terms are cited constants from the committed extractions (the RDA, the
 * PAAC minutes, the CRA, ECONOMICS.md) — those records aren't in the `records`
 * feed. NOT client-safe (imports the node bundle loader); the island consumes the
 * plain `MoneyFlowData` object this returns, passed as a prop.
 *
 * Discipline: the §5.5 refund consequence is flagged `[inference]` (it turns on
 * grant awards not in the document). The abatement value **per job** is the
 * deciding number, and the record that would pin it — the School District
 * Compensation Agreement — is non-public (`cra-agreement.cra.yaml`
 * `amounts_public: false`). Rather than leave the blank or invent a figure, it is
 * carried as a transparent **[open] screening model** (`buildAbatementPerJob`): a
 * best-effort band across a few facility profiles, every constant labeled, the
 * actual number still owed to the record. The defense/GovCloud-hardened case is
 * one modeling profile — a what-if on the building share + staffing, NOT a claim
 * the facility is defense (that thread stays [open], tracked in #233).
 */
import { hasFeed, loadFeed } from "./bundle";
import { CRA_PROFILES } from "./craProfiles";
import type { RecordItem } from "./feeds";

export { fmtUsd, fmtUsdFull, fmtUsdM } from "./money";

export interface MoneyNode {
  name: string;
  usd: number;
}

export interface MoneyFlowData {
  /** "Company Contribution" collected up front (RDA §3.2(a)). */
  collectedUsd: number;
  collectedCite: string;
  /** Tetra Tech OPC construction total (feed). */
  opcTotalUsd: number;
  /** The 6 OPC corridor line items (feed). */
  opcItems: MoneyNode[];
  /** True when the OPC resolved from the records feed (else curated fallback). */
  opcFromFeed: boolean;
  /** The first actual construction award — Eagle Bridge, N. Cole (PAAC minutes). */
  firstAward: { label: string; usd: number; cite: string };
  /** The §5.5 grant-refund consequence, flagged [inference]. */
  refund: { note: string; cite: string };
  /** The parallel abatement strand — verified components. */
  abatement: {
    pct: number;
    years: number;
    buildUsd: number;
    jobs: number;
    payrollUsd: number;
    taxBase: string;
    /** False — the School District Compensation $ are non-public. */
    schoolTermsPublic: boolean;
    cite: string;
  };
  /** The per-job abatement value, modeled as an [open] band (school terms non-public). */
  abatementPerJob: AbatementPerJob;
}

/** One facility profile in the abatement-per-job model. The two knobs that move
 *  the answer — the real-property (building) share of capex and the steady-state
 *  job count — are both genuinely uncertain and facility-type-dependent. */
export interface AbatementProfile {
  key: "stated" | "equipment" | "hyperscale" | "govcloud";
  label: string;
  /** Building/structure share of the ~$500M capex = the abated base. Equipment is
   *  personal property, not abated (CRA `real_property_only: true`). [assumption] */
  buildingShare: number;
  /** Modeled jobs. The CRA's ~50 is a non-binding estimate ("actuals may differ
   *  significantly"); lower counts are [inference]. */
  jobs: number;
  /** 15-yr abatement value ÷ jobs (computed). */
  perJobUsd: number;
  note: string;
}

/** Abatement value per job — a transparent screening model, carried as [open].
 *  The actual figure turns on the non-public School District Compensation
 *  Agreement; this is a labeled band, not a record read. */
export interface AbatementPerJob {
  tag: "open";
  /** Modeled band across the profiles (low → high). */
  lowUsd: number;
  highUsd: number;
  /** The "take the application at its word" profile (the central reference). */
  centralUsd: number;
  profiles: AbatementProfile[];
  /** The modeling constants, each labeled where it surfaces in the UI. */
  assumptions: {
    capexUsd: number;
    /** Ohio market → assessed (0.35). [verified] */
    assessmentRatio: number;
    /** Effective commercial millage as a fraction. [assumption] — exact
     *  Elida/American-Twp rate isn't in the corpus. */
    effectiveMills: number;
    /** assessmentRatio × effectiveMills — effective tax as a share of market value/yr. */
    effectiveRate: number;
    abatePct: number;
    termYears: number;
  };
  cite: string;
}

const OPC_REL = "aedg/roundabouts.summary.opc.yaml";

/** Curated OPC fallback (the 6 line items), for the minimal CI fixture only. */
const FALLBACK_OPC: MoneyNode[] = [
  { name: "Cole Street / Diller Road Roundabout", usd: 1535218 },
  { name: "Cole Street / Bluelick Road Roundabout", usd: 1704502 },
  { name: "Primary Access Entrance to Project Site (Roundabout)", usd: 2663045 },
  { name: "Cole Street / West Street (SR 115) Roundabout", usd: 2249609 },
  { name: "Cole Street Corridor", usd: 3899800 },
  { name: "Bluelick Road Corridor", usd: 2180907 },
];

interface OpcSubEstimate {
  name?: string | null;
  total?: number | null;
}

// Abatement-per-job model — all constants explicit so the arithmetic is auditable.
const ABATE_CAPEX = 500_000_000; // CRA §2 good-faith estimate (not a cap) [verified]
const ABATE_ASSESS = 0.35; // Ohio real-property assessment ratio [verified]
const ABATE_MILLS = 0.063; // ~63 effective commercial mills [assumption — exact local rate not in corpus]
const ABATE_PCT = 0.75; // Res #548-25 / CRA §3 [verified]
const ABATE_YEARS = 15; // CRA §3, per building [verified]

/** Compute the abatement-per-job band from the labeled constants + profiles.
 *  Per-job = (capex × building share × effective rate × 75% × 15 yr) ÷ jobs. */
export function buildAbatementPerJob(): AbatementPerJob {
  const effectiveRate = ABATE_ASSESS * ABATE_MILLS; // of market value, per year
  const perJob = (share: number, jobs: number): number =>
    Math.round((ABATE_CAPEX * share * effectiveRate * ABATE_PCT * ABATE_YEARS) / jobs);
  const profiles: AbatementProfile[] = CRA_PROFILES.map((p) => ({
    ...p,
    perJobUsd: perJob(p.buildingShare, p.jobs),
  }));
  const vals = profiles.map((p) => p.perJobUsd);
  const central = profiles.find((p) => p.key === "stated")?.perJobUsd ?? vals[0];
  return {
    tag: "open",
    lowUsd: Math.min(...vals),
    highUsd: Math.max(...vals),
    centralUsd: central,
    profiles,
    assumptions: {
      capexUsd: ABATE_CAPEX,
      assessmentRatio: ABATE_ASSESS,
      effectiveMills: ABATE_MILLS,
      effectiveRate,
      abatePct: ABATE_PCT,
      termYears: ABATE_YEARS,
    },
    cite: "Modeled · [open]. 75%/15-yr (Res #548-25) on a real-property share of the ~$500M build (CRA §2); the exact figure turns on the non-public School District Compensation Agreement.",
  };
}

export function buildMoneyFlow(): MoneyFlowData {
  const records = hasFeed("records") ? loadFeed<RecordItem[]>("records") : [];
  const opc = records.find((r) => r.rel === OPC_REL);

  const meta = (opc?.fields.meta ?? null) as { summary_construction_total?: number } | null;
  const subs = (opc?.fields.sub_estimates ?? null) as OpcSubEstimate[] | null;
  const opcItems: MoneyNode[] =
    subs && subs.length > 0 ? subs.map((s) => ({ name: s.name ?? "—", usd: s.total ?? 0 })) : FALLBACK_OPC;
  const opcTotalUsd = meta?.summary_construction_total ?? opcItems.reduce((a, b) => a + b.usd, 0);

  return {
    collectedUsd: 14_500_000,
    collectedCite: "RDA §3.2(a) — one-time Company Contribution, due within 30 business days",
    opcTotalUsd,
    opcItems,
    opcFromFeed: !!opc,
    firstAward: {
      label: "Eagle Bridge · N. Cole design-build (first award)",
      usd: 3_520_000,
      cite: "PAAC board minutes 2026-04-23 (p.78) — ~$3.52M; the rest of the program is still being awarded",
    },
    refund: {
      note: "§5.5 — if certified Total Cost is less than the Contribution + public grants, the surplus is refunded to the Company; grants received later are likewise refunded.",
      cite: "RDA §5.5 Overpayment Amount · turns on grant awards not in the document",
    },
    abatement: {
      pct: 75,
      years: 15,
      buildUsd: 500_000_000,
      jobs: 50,
      payrollUsd: 4_000_000,
      taxBase: "Elida Local School District",
      schoolTermsPublic: false,
      cite: "CRA No. 1 (Res #548-25) · docs/ECONOMICS.md — ~$500M build, 15-yr/75%, ~50 jobs / ~$4M payroll",
    },
    abatementPerJob: buildAbatementPerJob(),
  };
}
