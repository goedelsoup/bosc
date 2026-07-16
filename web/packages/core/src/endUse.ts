/**
 * Build-time model for the End-use & workloads explorer (#233 / #251 interactive
 * layer). The report's [verified] spine, made selectable: "data center" names
 * businesses that answer the public's two plain questions — *who benefits* and
 * *who can use it* — completely differently. The reader picks a type and sees
 * what the Select-Committee record establishes about it, and what the Lima record
 * does (and does not) say.
 *
 * Curated, dependency-free (no bundle loader) — the content is read from the
 * committee record, not a feed, so this is client-safe and the island imports the
 * type directly. Every cell traces to docs/end-use-and-workloads.md.
 */

export type DcKey = "bitcoin" | "hyperscale" | "colocation" | "enclave";

/** What the Lima record establishes about whether the campus is this type. */
export type LimaStatus = "ruled-out" | "open";

/** How open access to the compute is — the "who can use it" axis that narrows. */
export type AccessLevel = "self" | "commercial" | "private-tenants" | "authorized-only";

/** The evidence register, matching the engine grammar (#272) + the prose tags — the canonical
 *  `TagKind` from `./evidence` (#579). */
export type Register = import("./evidence").TagKind;

export interface DcType {
  key: DcKey;
  label: string;
  tagline: string;
  ownsCompute: string;
  whoBenefits: string;
  whoCanUse: string;
  access: AccessLevel;
  localEconomy: string;
  /** Who captures the abatement subsidy under this model — the demand-side answer to
   *  the economic ledger's "who gets the $X" (#269), register-encoded. */
  benefitCapture: { who: string; register: Register };
  /** The rungs of the FedRAMP/DoD-IL ladder this model's access can occupy
   *  (inclusive indices into IL_LADDER); `null` = off the ladder (self only). */
  ladderReach: [number, number] | null;
  /** The committee-record anchor that establishes this type — register one. */
  evidence: string;
  evidenceRegister: Register;
  limaStatus: LimaStatus;
  limaNote: string;
}

/** A pointed silence in the record — an absence that bears on the [open] question but is
 *  not, itself, a finding. */
export interface Silence {
  label: string;
  note: string;
  register: Register;
}

export interface EndUseData {
  types: DcType[];
  /** What the corpus confirms about Lima (the [verified] anchor). */
  verified: string;
  /** The single question the confirmed facts can't answer (the [open] gap). */
  openQuestion: string;
  /** The two pointed silences (Google omits Lima; PRR item 2 "no records"). */
  silences: Silence[];
}

/** One rung of the "who can use it" ladder — broad commercial → sealed IL-6 enclave. The
 *  access dimension that narrows; structure, not a Lima finding. */
export interface AccessRung {
  key: string;
  label: string;
  note: string;
}

export const IL_LADDER: AccessRung[] = [
  { key: "commercial", label: "Broad commercial", note: "anyone — the open cloud market" },
  { key: "fedramp", label: "FedRAMP", note: "authorized U.S. government cloud" },
  { key: "il4", label: "DoD IL4", note: "controlled unclassified information" },
  { key: "il5", label: "DoD IL5", note: "higher-sensitivity CUI / national security systems" },
  { key: "il6", label: "DoD IL6 enclave", note: "classified up to SECRET — U.S.-citizen-staffed, sealed" },
];

const TYPES: DcType[] = [
  {
    key: "bitcoin",
    label: "Bitcoin mining",
    tagline: "a mine is its own customer",
    ownsCompute: "the operator — it mines on its own account",
    whoBenefits: "the operator; the machines have no external customer",
    whoCanUse: "no one else — “we don’t have customers in Bitcoin”",
    access: "self",
    localEconomy: "behind-the-meter load, minimal permanent jobs",
    benefitCapture: {
      who: "the operator — it mines on its own account; no external customer to share with",
      register: "verified",
    },
    ladderReach: null,
    evidence: "MARA Holdings volunteered the distinction itself (closing session, 2026-06-04)",
    evidenceRegister: "verified",
    limaStatus: "ruled-out",
    limaNote:
      "Not the Lima campus: the developer is Google, a hyperscaler, not a miner. The one type the record lets us cross off.",
  },
  {
    key: "hyperscale",
    label: "Hyperscale",
    tagline: "the owner runs the compute",
    ownsCompute: "the operator runs its own workloads (Google, Meta, AWS, Microsoft)",
    whoBenefits: "the hyperscaler; the company you can name is the company using the machines",
    whoCanUse: "the owner’s own services and its global cloud customers",
    access: "commercial",
    localEconomy: "anchors a cloud-region footprint, but lean permanent headcount",
    benefitCapture: {
      who: "the hyperscaler — it owns the compute, so it captures the abatement on the building it occupies",
      register: "inference",
    },
    ladderReach: [0, 3], // broad commercial, but can run FedRAMP / IL5 authorized regions
    evidence: "the 2026-06-04 morning panel — Google/Meta/AWS/Microsoft",
    evidenceRegister: "verified",
    limaStatus: "open",
    limaNote:
      "Google is the [verified] developer (#234) — but the deed fixes the builder, not the occupant. Whether Google self-runs the Lima halls is open.",
  },
  {
    key: "colocation",
    label: "Colocation",
    tagline: "a landlord; tenants own the compute",
    ownsCompute: "the tenants — the operator builds and powers the hall, others run the racks",
    whoBenefits: "unknown — Vantage “cannot say” whether it or its tenants capture the abatement",
    whoCanUse: "the operator’s tenants, who need not be named on any public record",
    access: "private-tenants",
    localEconomy: "a landlord; the local benefit turns on tenants the public can’t see",
    benefitCapture: {
      who: "cannot say — Vantage testified it “cannot say” whether the operator or its unnamed tenants capture the abatement",
      register: "open",
    },
    ladderReach: [0, 4], // tenants are unnamed — could sit anywhere, up to a sealed enclave
    evidence: "Vantage: “I do not know … passed through … or taken advantage by the tenants themselves”",
    evidenceRegister: "verified",
    limaStatus: "open",
    limaNote:
      "Hyperscale developers do lease capacity. Whether the Lima campus hosts colocation tenants — and who — is open.",
  },
  {
    key: "enclave",
    label: "Federal enclave",
    tagline: "authorized users only",
    ownsCompute: "a wholly dedicated, U.S.-citizen-staffed environment",
    whoBenefits: "the federal government / defense; the supply chain is federal and sealed",
    whoCanUse: "only authorized federal users — FedRAMP, then DoD impact levels IL4–IL6",
    access: "authorized-only",
    localEconomy: "a sealed island: capacity never reaches the open market or the local tech cluster",
    benefitCapture: {
      who: "the federal government / defense — a sealed federal supply chain; no local capture, and no public record of who",
      register: "open",
    },
    ladderReach: [2, 4], // IL4 → IL6: authorized federal users only, the sealed top of the ladder
    evidence:
      "AWS named the Department of War and the CIA before the committee; the DoD CC SRG; Google’s air-gapped appliance holds IL5",
    evidenceRegister: "verified",
    limaStatus: "open",
    limaNote:
      "The sharpest [open] facet. The PRR for County ⇄ DoD/GDLS comms returned “no records”; Google’s own testimony omits Lima. An absence is not a finding.",
  },
];

export function buildEndUse(): EndUseData {
  return {
    types: TYPES,
    verified:
      "The developer is Google ([verified], #234), and the campus is real and large. The industry’s own testimony establishes the taxonomy above.",
    openQuestion:
      "Which of these the Lima campus is — and who can use it. Confirming the customer did not resolve the use.",
    silences: [
      {
        label: "Google’s own testimony omits Lima",
        note: "Google described its data-center business to the committee without naming the Lima campus. A choice of what to say is not a finding about what Lima is.",
        register: "open",
      },
      {
        label: "PRR item 2 — “no records”",
        note: "The public-records request for County ⇄ DoD / GDLS communications returned “no records.” An absence in the file is not evidence of a connection — and not evidence against one.",
        register: "open",
      },
    ],
  };
}

/** The access axis, ordered broad → sealed (drives the “who can use it” meter). */
export const ACCESS_ORDER: AccessLevel[] = ["commercial", "private-tenants", "authorized-only"];

export const ACCESS_LABEL: Record<AccessLevel, string> = {
  self: "no external users",
  commercial: "the owner’s commercial cloud",
  "private-tenants": "private, unnamed tenants",
  "authorized-only": "authorized federal users only",
};
