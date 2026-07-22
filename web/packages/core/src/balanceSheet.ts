/**
 * The public balance sheet (epic #271 Phase 4 capstone, #273) — composes every
 * narrative's `UncertainOutcome` into one register-encoded sheet and prices the opacity
 * in aggregate. **No new data:** it reads the existing consumer models (econ ledger, grid,
 * toxics) through the shared band contract the engine was built to feed from day one.
 *
 * Client-safe. The toxics outcome needs the feed-sourced discharge constants (effluent +
 * natural low flow), so they're passed in (from `buildDilution()` at build time) rather
 * than re-derived — the balance sheet never forks a narrative's numbers.
 *
 * Discipline: a map of what *isn't* known, not a verdict. The aggregate is a band; every
 * row carries its register and the specific record whose disclosure would collapse it.
 */
import { reportUrl } from "./reports";
import { netSubsidyOutcome } from "./econLedger";
import { facilityDrawOutcome, gridPriorsFromFacility } from "./gridLoad";
import { assimilativeOutcome } from "./toxicsDilution";
import type { UncertainOutcome } from "./uncertainty";

export type BalanceUnit = "usd" | "pct" | "mw";

/** The facility's disclosed IT-load bracket (from the `facility` feed) — passed so the grid
 *  row sources the same figure the load report and /basin do (#1632). Null ⇒ Lima defaults. */
export interface GridItLoad {
  central: number;
  low?: number | null;
  high?: number | null;
}

export interface BalanceRow {
  outcome: UncertainOutcome;
  unit: BalanceUnit;
  /** The narrative companion this band comes from. */
  href: string;
  narrative: string;
}

export interface BalanceSheetData {
  rows: BalanceRow[];
  /** Distinct withheld records that, produced, would collapse one or more bands — the
   *  mandamus tie-in (each is a record the county has not disclosed). */
  resolvingRecords: string[];
  /** The monetized public exposure: the economic net-subsidy band ($). */
  econExposure: { low: number; high: number; central: number };
}

/**
 * Compose the balance sheet. `toxicsEffluentCfs` / `toxicsNaturalAnnualCfs` come from the
 * hydrology feed (`buildDilution().discharge`) so the toxics band matches its narrative.
 * `siteSlug` scopes each band's narrative companion link to the active site (#1145).
 */
export function buildBalanceSheet(
  toxicsEffluentCfs: number,
  toxicsNaturalAnnualCfs: number,
  siteSlug: string,
  gridItLoad?: GridItLoad | null,
): BalanceSheetData {
  const econ = netSubsidyOutcome();
  // #1632: source the grid band's IT-load prior from the facility feed when supplied, so this
  // sheet's load row matches the-load-and-the-grid and /basin (one sourced IT figure, not a
  // hardcoded band). Falls back to the Lima GRID_PRIORS default when absent.
  const gridPriors = gridItLoad
    ? gridPriorsFromFacility(gridItLoad.central, gridItLoad.low, gridItLoad.high)
    : undefined;
  const grid = facilityDrawOutcome(gridPriors);
  const toxics = assimilativeOutcome(toxicsEffluentCfs, toxicsNaturalAnnualCfs);

  const rows: BalanceRow[] = [
    {
      outcome: econ,
      unit: "usd",
      href: reportUrl("the-economic-ledger", siteSlug),
      narrative: "The economic ledger",
    },
    {
      outcome: grid,
      unit: "mw",
      href: reportUrl("the-load-and-the-grid", siteSlug),
      narrative: "The load and the grid",
    },
    {
      outcome: toxics,
      unit: "pct",
      href: reportUrl("toxics-and-the-corridor", siteSlug),
      narrative: "Toxics and the corridor",
    },
  ];

  // The withheld records that would collapse the bands — the outcome's own resolving
  // record plus each driving prior's, deduped.
  const records = new Set<string>();
  for (const r of rows) {
    if (r.outcome.resolvingRecord) records.add(r.outcome.resolvingRecord);
    for (const d of r.outcome.drivers) {
      if (d.resolvingRecord) records.add(d.resolvingRecord);
    }
  }

  return {
    rows,
    resolvingRecords: [...records],
    econExposure: { low: econ.low, high: econ.high, central: econ.central },
  };
}
