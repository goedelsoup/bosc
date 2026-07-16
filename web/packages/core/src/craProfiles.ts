// The four CRA-abatement what-if profiles (#581) — building-share × jobs scenarios shared by the
// money-flow (`moneyFlow.ts`) and economic-ledger (`econLedger.ts`) derivations. These were
// maintained as two byte-identical arrays; `label`/`note` drift in one would have passed silently
// (the tests pin only per-job output), so they live here once.

/** The base shape both `AbatementProfile` and `LedgerProfile` extend (with their computed fields). */
export interface CraProfile {
  key: "stated" | "equipment" | "hyperscale" | "govcloud";
  label: string;
  /** Building/structure share of the ~$500M capex = the abated base (equipment is personal
   *  property, not abated — CRA `real_property_only: true`). [assumption] */
  buildingShare: number;
  /** Modeled jobs. The CRA's ~50 is non-binding ("actuals may differ significantly"). */
  jobs: number;
  note: string;
}

export const CRA_PROFILES: CraProfile[] = [
  {
    key: "stated",
    label: "Take the application at its word",
    buildingShare: 0.35,
    jobs: 50,
    note: "the CRA's own ~50 jobs; a mid building-shell share of the $500M",
  },
  {
    key: "equipment",
    label: "AI / GPU-dense (equipment-heavy)",
    buildingShare: 0.25,
    jobs: 50,
    note: "most value is servers + electrical — personal property, not abated — so the abated base shrinks",
  },
  {
    key: "hyperscale",
    label: "Hyperscale-realistic (lean ops)",
    buildingShare: 0.35,
    jobs: 30,
    note: "data centers staff lean at steady state; the CRA warns actuals 'may differ significantly'",
  },
  {
    key: "govcloud",
    label: "GovCloud / defense-hardened",
    buildingShare: 0.5,
    jobs: 30,
    note: "hardened construction lifts the real-property share, cleared ops run lean — a what-if profile, not a finding (#233)",
  },
];
