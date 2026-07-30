// The what-if profile SHAPE. The four corners themselves used to be declared here as a literal
// array (#581) — building share x jobs, hand-copied from `docs/the-economic-ledger.md` and pinned
// to `econLedger.ts` by a test. They are now computed in Python from the committed abatement
// instrument and this county's cited tax parameters, and published in the `economics-scenarios`
// feed (#1665, epic #1659 ME-F): read them with `econScenarios.craProfilesFromFeed()`.
//
// Only the type stays here, because it must remain client-safe — `econLedger.ts` is bundled into
// the simulator island and cannot import the node bundle loader.

/** The knobs one what-if corner turns. The priced fields live on the feed's `ScenarioProfile`. */
export interface CraProfile {
  /** "stated" | "equipment" | "hyperscale" | "govcloud" — open, so a site's parameters file can
   *  declare corners of its own without a type change here. */
  key: string;
  label: string;
  /** Building/structure share of the stated capex = the abated base (equipment is personal
   *  property, not abated — CRA `real_property_only: true`). [assumption] */
  buildingShare: number;
  /** Modeled jobs. The agreement's own estimate is non-binding ("actuals may differ
   *  significantly"), which is why this is a knob and not a figure. */
  jobs: number;
  note: string;
}
