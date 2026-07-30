/**
 * Build-time model for the per-site **grid backdrop** (GP-E #1642, E1/E2) — the reader for the
 * `grid` object feed, its facility-gated companion `economics-demand-pressure`, and (for the load
 * report's backup chain step) the `facility` feed's disclosed genset fleet (#1771).
 *
 * The gap this closes: the richest per-site grid artifact (serving utility, PJM zone, the
 * EIA-861/930/state load denominators) was computed in Python, written to a CLI reference file,
 * and never entered the bundle — so nothing rendered it, and `gridLoad.ts` filled the vacuum with
 * Lima's denominators hand-copied in as TS literals (`AEP_OHIO_RETAIL_GWH = 48_653`), a second
 * uncontrolled copy of EIA figures with no drift guard. Everything the load report divides by now
 * comes from here.
 *
 * Discipline, in the shape `dilution.ts` established: **no Lima fallback**, and equally no
 * Lima-only branch. A site whose bundle carries no `grid` feed returns `null` and its caller locks
 * and asks for the source — it never borrows another site's utility; a site that HAS a record of
 * its own gets its own answer rather than the reference build's. The backdrop describes the
 * *place*, so `loadShare` is null for a facility-less peer (no fabricated campus share) while the
 * cited service chain still renders.
 *
 * The demand-pressure registers travel with the numbers: `demandSharePct` / `householdsEquivalent`
 * are the EIA-cited headline; `pricePressure` is a deliberately STYLIZED screening band off a
 * stated transmission coefficient, and the campus buys at wholesale, not the residential price the
 * band is applied to. Callers must render `caveats`, not drop them.
 *
 * NOT client-safe (imports the node bundle loader) — islands consume the plain objects as props.
 */
import { hasFeed, loadFeed } from "./bundle";
import type { CitedFact, FacilityDemandPressure, FacilityItem, GridProfile, SourceKind } from "./feeds";
import type { BackupRecord, GridBaseline } from "./gridLoad";

/** One cited link in the electric-service chain, flattened for rendering. */
export interface GridChainRow {
  key: "utility" | "holding_company" | "balancing_authority" | "rto" | "retail_regulator";
  label: string;
  value: string;
  cite: string;
  source: SourceKind;
  /** `document`/`connector` ⇒ the `[verified]` badge; the rest are asserted. */
  verified: boolean;
}

/** A denominator the campus load is expressed against, with its citation. */
export interface GridDenominator {
  key: "utility" | "ba" | "state";
  label: string;
  gwh: number;
  cite: string;
  /** The campus's share of this denominator (%), when a campus is disclosed. */
  sharePct: number | null;
}

export interface GridBackdropData {
  /** The five cited identifications, in service-chain order. */
  chain: GridChainRow[];
  utilityName: string;
  /** EIA-861 ownership ("Investor Owned" / "Municipal" / "Cooperative"); null when unread. */
  ownership: string | null;
  baName: string;
  /** Retail customers served by the utility (EIA-861), when the profile carries it. */
  customers: number | null;
  /**
   * The utility's **bundled standard-service (SSO) cohort** price, cents/kWh (EIA-861), when
   * carried — NOT an all-sector average and NOT an industrial/data-center rate (G3/#1644).
   *
   * On the full EIA-861 form this is bundled revenue over bundled sales: the customers who
   * never shopped, which in a restructured state skews residential and lands above even the
   * state residential price (Lima: 18.61¢ against a ~12-13¢ all-sector rate). Rendering it as
   * "the average retail price" invites a reader to take it as the campus's bill. Any surface
   * showing `avgPriceCentsKwh` must name the cohort; `avgPriceCite` is the value's own citation,
   * which carries the full qualification.
   */
  avgPriceCentsKwh: number | null;
  avgPriceCite: string | null;
  /** The utility / BA / state load denominators, largest story first. */
  denominators: GridDenominator[];
  /** The campus load block — **null for a site with no disclosed facility** (#1642). */
  campus: {
    loadMw: number;
    annualGwh: number;
    loadFactor: number;
    cite: string;
  } | null;
  note: string;
}

const CHAIN_LABELS: Record<GridChainRow["key"], string> = {
  utility: "Serving retail utility",
  holding_company: "Holding company",
  balancing_authority: "Balancing authority",
  rto: "Wholesale market (RTO/ISO)",
  retail_regulator: "Retail rate regulator",
};

const VERIFIED_SOURCES: ReadonlySet<SourceKind> = new Set<SourceKind>(["document", "connector"]);

function chainRow(key: GridChainRow["key"], fact: CitedFact): GridChainRow {
  return {
    key,
    label: CHAIN_LABELS[key],
    value: fact.value,
    cite: fact.citation,
    source: fact.source,
    verified: VERIFIED_SOURCES.has(fact.source),
  };
}

/** The raw `grid` feed for a site, or null when it carries none (a site that hasn't run
 *  `watermark grid`, or whose profile was dropped as a zeroed shell). */
export function gridProfile(slug?: string): GridProfile | null {
  if (!hasFeed("grid", slug)) return null;
  return loadFeed<GridProfile>("grid", slug);
}

/**
 * The site's grid backdrop, or null when its bundle carries no `grid` feed.
 *
 * Null means *lock and ask*, not "use Lima's": the serving utility is the one fact this page
 * exists to state, and asserting the wrong one is worse than asserting none.
 */
export function buildGridBackdrop(slug?: string): GridBackdropData | null {
  const gp = gridProfile(slug);
  if (gp === null) return null;

  const su = gp.serving_utility;
  const share = gp.load_share ?? null;
  const denominators: GridDenominator[] = [];
  const push = (
    key: GridDenominator["key"],
    label: string,
    gwh: number | null | undefined,
    cite: string | null | undefined,
    sharePct: number | null | undefined,
  ): void => {
    if (gwh == null || gwh <= 0) return; // never render a zero denominator as a baseline
    denominators.push({ key, label, gwh, cite: cite ?? "", sharePct: sharePct ?? null });
  };
  push(
    "utility",
    gp.utility_profile.utility,
    gp.utility_profile.retail_sales_gwh.value,
    gp.utility_profile.retail_sales_gwh.citation,
    share?.share_of_utility_pct.value,
  );
  push(
    "ba",
    gp.ba_profile.ba,
    gp.ba_profile.annual_load_gwh.value,
    gp.ba_profile.annual_load_gwh.citation,
    share?.share_of_ba_pct.value,
  );
  // The state denominator only exists on the load-share block (it is pulled for the share), so a
  // facility-less peer legitimately has no state row here.
  push(
    "state",
    "State retail sales",
    share?.state_retail_gwh.value,
    share?.state_retail_gwh.citation,
    share?.share_of_state_pct.value,
  );

  return {
    chain: [
      chainRow("utility", su.utility),
      chainRow("holding_company", su.holding_company),
      chainRow("balancing_authority", su.balancing_authority),
      chainRow("rto", su.rto),
      chainRow("retail_regulator", su.retail_regulator),
    ],
    utilityName: gp.utility_profile.utility,
    ownership: gp.utility_profile.ownership || null,
    baName: gp.ba_profile.ba,
    customers: gp.utility_profile.customers?.value ?? null,
    avgPriceCentsKwh: gp.utility_profile.avg_price_cents_kwh?.value ?? null,
    avgPriceCite: gp.utility_profile.avg_price_cents_kwh?.citation ?? null,
    denominators,
    campus:
      share === null || share.campus_load_mw.value == null || share.annual_consumption_gwh.value == null
        ? null
        : {
            loadMw: share.campus_load_mw.value,
            annualGwh: share.annual_consumption_gwh.value,
            loadFactor: share.load_factor.value ?? 0,
            cite: share.campus_load_mw.citation ?? "",
          },
    note: gp.note ?? "",
  };
}

/**
 * The facility demand → consumer-price-pressure sensitivity for a site, or null when the
 * facility-gated feed is absent (#1642, E2 — this feed shipped, gated readiness, and was rendered
 * by nothing until now).
 */
export function buildDemandPressure(slug?: string): FacilityDemandPressure | null {
  if (!hasFeed("economics-demand-pressure", slug)) return null;
  return loadFeed<FacilityDemandPressure>("economics-demand-pressure", slug);
}

/**
 * The per-site baseline the load report's "share of the utility's entire retail sales" and
 * "equivalent homes" lines divide by — assembled from the feeds, replacing `gridLoad.ts`'s
 * hardcoded Lima constants (#1642, E2).
 *
 * Null when the site carries no grid feed: the report locks that readout rather than dividing a
 * modelled load by another utility's sales. The household figure comes from the demand-pressure
 * feed's own cited `avg_household_kwh_yr`, so the report and that feed can never disagree about
 * how big a household is.
 */
export function buildGridBaseline(slug?: string): GridBaseline | null {
  const gp = gridProfile(slug);
  if (gp === null) return null;
  const utilityGwh = gp.utility_profile.retail_sales_gwh.value;
  if (utilityGwh == null || utilityGwh <= 0) return null;

  const dp = buildDemandPressure(slug);
  const householdKwh = dp?.avg_household_kwh_yr.value ?? null;
  return {
    utilityLabel: gp.utility_profile.utility,
    utilityRetailGwh: utilityGwh,
    utilityCite: gp.utility_profile.retail_sales_gwh.citation ?? "",
    householdKwhYr: householdKwh,
    householdCite: dp?.avg_household_kwh_yr.citation ?? null,
    stateArea: dp?.area ?? null,
  };
}

/**
 * The site's disclosed backup-generation fleet, or null where its record carries none (#1771).
 *
 * These figures — Lima's 313 MW / 114 gensets / 2,750 ekW — were the last literals in
 * `gridLoad.ts`, duplicating `SiteFacility.genset_count` / `genset_mw` behind a hardcoded
 * `site === "lima"` branch that returned null for Fort Wayne's real 34-engine fleet. They now
 * come from the primary `facility` row, so there is one copy of each figure and every disclosed
 * fleet on the network reaches the page.
 *
 * The total is the record's own where the feed carries one (Lima's `~313 MW`) and derived from
 * count × rating only where it does not (Fort Wayne) — and `totalBasis` says which, so a derived
 * figure is never mistaken for a disclosed one. That distinction is the reason the cited total
 * exists: multiplying Lima's components prints 313.5 for a site whose permit extraction, essay
 * and docs all say ~313.
 *
 * Null means the fleet is `[open]` for this site — the chain step asks for the permit rather than
 * inheriting another county's gensets.
 */
export function buildBackupRecord(slug?: string): BackupRecord | null {
  if (!hasFeed("facility", slug)) return null;
  const rows = loadFeed<FacilityItem[]>("facility", slug);
  const primary = rows.find((f) => f.is_primary) ?? rows[0];
  // The three travel together in the model (count / rating / rating grade), so a half-set row
  // can't reach here — but read defensively: an older bundle predates these columns entirely.
  if (primary?.genset_count == null || primary.genset_mw == null || !primary.genset_rating_basis) {
    return null;
  }
  const cited = primary.genset_total_mw;
  return {
    backupMw: cited ?? primary.genset_count * primary.genset_mw,
    totalBasis: cited == null ? "derived" : "cited",
    approximate: cited == null ? false : (primary.genset_total_approximate ?? false),
    nEngines: primary.genset_count,
    perEngineMw: primary.genset_mw,
    ratingBasis: primary.genset_rating_basis,
    cite: (cited == null ? null : primary.genset_total_citation) ?? primary.air_permit_citation ?? "",
  };
}
