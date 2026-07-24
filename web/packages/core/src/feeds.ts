/**
 * TypeScript shapes for the bundle feed rows this app consumes. These mirror the
 * Pydantic models in `bosc.site.feeds`; they're intentionally partial — only the
 * fields the frontend reads are typed. The committed `schemas/*.schema.json` are
 * the authoritative contract (schema validation is issue #62).
 */
import type { FeatureCollection, Geometry } from "geojson";

export type Confidence = "high" | "medium" | "low";

/** Shared provenance (`bosc.site.feeds.Citation`). */
export interface Citation {
  source?: string | null;
  source_kind: string;
  page?: number | null;
  confidence?: Confidence | null;
  note?: string | null;
  verified: boolean;
}

/** Map a citation/confidence onto an evidence badge kind (see EvidenceTag). */
export function evidenceKind(c: Pick<Citation, "verified"> | null | undefined): "verified" | "inference" {
  return c?.verified ? "verified" : "inference";
}

/** What the document viewer dispatches on — derived from the real file (epic #274). */
export type RenderClass = "image" | "text" | "html" | "pdf" | "office" | "other";

export interface RecordItem {
  rel: string;
  group: string;
  title: string;
  confidence?: Confidence | null;
  warnings: string[];
  fields: Record<string, unknown>;
  approximate_paths: string[];
  citation: Citation;
  /** The real source document this record was read from (#276); null if unjoined. */
  source_doc_rel?: string | null;
  source_doc_render_class?: RenderClass | null;
  source_doc_published?: boolean;
}

export interface TimelineEntry {
  date: string;
  category: string;
  title: string;
  ref: string;
  parties: string[];
  detail?: string | null;
  source: string;
  also_sources: string[];
  citation?: Citation | null;
}

/** The evidence-discipline tag a normalized fact renders as (`bosc.site.feeds.FactStatus`). */
export type FactStatus = "verified" | "inference" | "reference" | "open";

/** Where a normalized fact came from — the `Citation` shape projected from a value's provenance
 * (`bosc.site.feeds.FactEvidence`). `page` is populated only where the source carries one. */
export interface FactEvidence {
  source?: string | null;
  source_kind: string;
  page?: number | null;
  citation?: string | null;
  confidence?: Confidence | null;
  asof?: string | null;
  verified: boolean;
}

/** One normalized `(subject, predicate, value, unit, status, evidence)` fact
 * (`bosc.site.feeds.FactItem`) — a projection over the bundle's provenanced values (#1587),
 * the tuple `get_facts` retrieves. */
export interface FactItem {
  subject: string;
  subject_label: string;
  subject_kind: string;
  predicate: string;
  value?: number | null;
  unit?: string | null;
  status: FactStatus;
  approximate?: boolean;
  low?: number | null;
  high?: number | null;
  evidence: FactEvidence;
  feed: string;
}

export interface EntityNode {
  key: string;
  display: string;
  kind: string;
  classification?: string | null;
  relation_class?: string | null;
  relation_basis?: string | null;
  variants: string[];
  signals: string[];
  roles: Record<string, number>;
  parcels: string[];
  addresses: string[];
  sources: string[];
  lei?: string | null;
  uei?: string | null;
  federal_obligations?: number | null;
}

export interface RelationshipEdge {
  src: string;
  rel: string;
  dst: string;
  date: string;
  ref: string;
  source: string;
  relation_class?: string | null;
  relation_basis?: string | null;
}

export interface PersonItem {
  slug: string;
  name: string;
  entity_key?: string | null;
  aliases: string[];
  roles: string[];
  affiliations: string[];
  summary?: string | null;
  expanded: boolean;
  tags: string[];
  sources: Citation[];
  body: string;
}

export interface PlaceRelationship {
  role: string;
  entity: string;
}

export interface PlaceItem {
  slug: string;
  name: string;
  kind: string;
  depth: string;
  parcels: string[];
  members: string[];
  aliases: string[];
  tags: string[];
  location?: { method?: string | null; confidence?: string | null; bbox?: number[] | null } | null;
  relationships: PlaceRelationship[];
  citations: Citation[];
  body: string;
}

export interface MeetingItem {
  slug: string;
  date?: string | null;
  kind?: string | null;
  summary: string;
  corridor_relevance: string;
  decisions: string[];
  parties: string[];
  parcels: string[];
  dollar_figures: string[];
  hits: string[];
  citation: Citation;
}

export interface DocumentEntry {
  rel: string;
  name: string;
  size_bytes: number;
  suffix: string;
  /** MIME + render class derived from the real file (extension + content sniff, #275). */
  media_type: string;
  render_class: RenderClass;
  /** Cleared for public serving by the default-deny allowlist (#280); dev serves all. */
  published: boolean;
  available: boolean;
  download_url?: string | null;
}

export interface DocumentCollectionItem {
  slug: string;
  title: string;
  description?: string | null;
  entries: DocumentEntry[];
}

export interface ExhibitItem {
  slug: string;
  title: string;
  caption: string;
  source: string;
  pages?: string | null;
  available: boolean;
}

/** A provenanced number (`bosc.hydrology.model.ProvenancedValue`). */
export interface ProvenancedValue {
  value: number | null;
  unit?: string | null;
  source?: string | null;
  citation?: string | null;
  confidence?: Confidence | null;
  asof?: string | null;
  // Optional quantitative uncertainty band (#760), distinct from the qualitative
  // `confidence`. Absolute bounds around `value`, either/both present.
  low?: number | null;
  high?: number | null;
}

/** A screening dilution band (`bosc.hydrology.model.Flag`): violation < tight < ok. */
export type DilutionFlag = "ok" | "tight" | "violation";

/** A point in the municipal water loop (`bosc.hydrology.model.Node`). */
export interface WaterNode {
  id: string;
  name: string;
  role: string;
  receiving_water?: string | null;
  lat?: number | null;
  lon?: number | null;
}

/** One node's flow terms in the Tier-0 balance (`bosc.hydrology.model.WaterBalanceNode`). */
export interface WaterBalanceNode {
  node: WaterNode;
  inflow?: ProvenancedValue | null;
  consumptive_use?: ProvenancedValue | null;
  return_flow?: ProvenancedValue | null;
  stormwater?: ProvenancedValue | null;
}

/** The assembled source→use→WWTP→receiving loop (`bosc.hydrology.model.WaterBalance`). */
export interface WaterBalance {
  nodes: WaterBalanceNode[];
  tier: "tier0";
  warnings: string[];
}

/** One low-flow dilution check (`bosc.hydrology.model.AssimilativeCheck`). */
export interface AssimilativeCheck {
  receiving_water: string;
  discharger: string;
  design_low_flow: ProvenancedValue; // the CHRONIC design flow: cited 7Q10
  discharge: ProvenancedValue;
  // Permitted effluent already in the reach (Σ other WWTPs on this receiving water),
  // credited into `effluent_credited_ratio`; null when the plant is alone on its stream (WS-15).
  upstream_returns?: ProvenancedValue | null;
  dilution_ratio: number; // conservative CHRONIC: cited 7Q10 / discharge (no effluent credit)
  flag: DilutionFlag; // band on `dilution_ratio`
  // Effluent-credited: (7Q10 + upstream_returns) / discharge; null when nothing to credit.
  effluent_credited_ratio?: number | null;
  effluent_credited_flag?: DilutionFlag | null;
  // Acute pair (WS-08): the cited 1Q10 and the discharge's dilution against it — the design flow
  // matched to an acute aquatic-life criterion. null when the fact sheet omits the 1Q10; a cited
  // 1Q10 = 0 cfs (a stream that runs dry at design low flow) gives a 0:1 ratio (no acute capacity).
  acute_low_flow?: ProvenancedValue | null; // the ACUTE design flow: cited 1Q10
  acute_dilution_ratio?: number | null; // cited 1Q10 / discharge
  acute_flag?: DilutionFlag | null; // band on `acute_dilution_ratio`
  detail: string;
}

/**
 * The cooling archetype a scenario's water math assumes (`bosc.sites.CoolingModelType`,
 * epic #1060). Keyed on physical mechanism — "open loop / closed loop" are display-only
 * aliases. `unknown` = the facility is disclosed but its cooling method is not on record:
 * the basis is a bracketed range and no single consumptive headline may be rendered (#1057).
 */
export type CoolingModel =
  | "off"
  | "evaporative_tower"
  | "once_through"
  | "closed_loop_dry"
  | "hybrid_adiabatic"
  | "unknown";

/** The sourced cooling design basis (`bosc.hydrology.model.CoolingBasis`, contract 1.9.0). */
export interface CoolingBasis {
  cooling_model?: CoolingModel | null;
  it_load: ProvenancedValue;
  wue?: ProvenancedValue | null; // null for archetypes where WUE does not apply
  cycles_of_concentration?: ProvenancedValue | null;
  consumptive_fraction: ProvenancedValue;
  makeup_demand: ProvenancedValue;
  consumptive_low: ProvenancedValue;
  consumptive_high: ProvenancedValue;
  method?: string | null;
  method_disclosed?: boolean; // false = `unknown` archetype (undisclosed method)
  is_bracketed?: boolean; // true = low/high span candidate archetypes, not an estimate
  seasonal_months?: string[] | null; // hybrid_adiabatic: the evaporative-assist months
}

export interface ScenarioResult {
  scenario: {
    name: string;
    description?: string | null;
    cooling_model?: CoolingModel | null;
    cooling_demand: ProvenancedValue;
    consumptive_fraction: ProvenancedValue;
    basis?: CoolingBasis | null;
  };
  cooling_model?: CoolingModel | null;
  consumptive_loss: ProvenancedValue;
  // Renamed from ottawa_* in the backend's per-site generalization (#900); nullable —
  // a site without a cited receiving-water low flow carries null, never a faked figure.
  receiving_7q10?: ProvenancedValue | null;
  // Per-site cited seasonal design low flows (#1633) — the growing-season 30Q10 and the absolute
  // driest-week 1Q10 (often 0). The dilution model reads these instead of hardcoding Lima's floors;
  // null when the cited low-flow table omits them.
  receiving_summer_30q10?: ProvenancedValue | null;
  receiving_1q10?: ProvenancedValue | null;
  receiving_live?: ProvenancedValue | null;
  receiving_water_name?: string | null;
  // The campus's own routed industrial discharge (cfs) — the demand node's return flow (Lima's
  // FM-2), surfaced top-level (#1633) so the effluent-share model is feed-sourced, not a constant.
  campus_routed_discharge?: ProvenancedValue | null;
  // `balance` is the composite Tier-0 loop and `assimilative` is a per-discharger
  // array — NOT scalar provenanced values. (Previously both mistyped as
  // ProvenancedValue, which rendered blank, falsely-tagged headline tiles — #635.)
  balance: WaterBalance;
  assimilative: AssimilativeCheck[];
}

/** One dated Esri Wayback aerial release (the `geo/imagery` feed's `meta.wayback`). */
export interface WaybackRelease {
  date: string; // e.g. "2014-12"
  release: number; // the Wayback releaseNum, substituted into the tile template
}

/** Properties on an imagery-AOI feature (the footprint + its bbox for the view fit). */
export interface ImageryAoiProps {
  layer: string;
  label?: string;
  color?: string;
  site?: string;
  bbox?: number[];
}

/** The `geo/imagery` feed shape (issue #72): AOI footprints + the dated ladder. A real
 *  GeoJSON FeatureCollection (typed with geojson `Feature`/`Geometry`) so consumers read
 *  it without an `as unknown as` cast (#585). */
export interface ImageryFeed extends FeatureCollection<Geometry, ImageryAoiProps> {
  feed?: string;
  meta?: {
    crs?: string;
    subject?: string;
    wayback?: {
      tile_url_template: string; // carries `{release}` + `{z}/{y}/{x}`
      attribution?: string;
      note?: string;
      releases: WaybackRelease[];
    };
  };
}

export interface RseiFacility {
  name?: string | null;
  city?: string | null;
  pounds?: number | null;
  score?: number | null;
  [k: string]: unknown;
}

export interface RseiInventory {
  meta: {
    subject?: string;
    source?: string;
    version?: string;
    facility_count?: number;
    scored_facility_count?: number;
    caveats?: string[];
    [k: string]: unknown;
  };
  county_name?: string;
  facilities: RseiFacility[];
}

/** A glossary concept (`bosc.site.feeds.ConceptItem`, issue #68). */
export interface ConceptItem {
  slug: string;
  title: string;
  kind: string;
  aliases: string[];
  tags: string[];
  summary: string;
  related: string[];
  body: string;
}

// --- curated-entity + economics feeds (Pages cutover, #103) -------------------

/** A cloud-consumer candidate (`candidates` feed) — demand-fit, not corpus-derived. */
export interface CandidateItem {
  name: string;
  entity_key?: string | null; // resolves into the entities feed when in the graph
  tier: number;
  kind?: string | null;
  sector?: string | null;
  location?: string | null;
  workload_classes: string[];
  confirmed_cloud_relationship?: string | null;
  speculative?: boolean;
  basis?: string | null;
}

/** One federal fiscal year's prime-award obligations (annual flow, #1662). */
export interface FederalAnnualFlow {
  fiscal_year: number;
  obligations: number;
}
/** One PSC/NAICS category's share of a recipient's federal obligations (#1662). */
export interface FederalCategory {
  code: string;
  name: string;
  obligations: number;
}
/** A USASpending federal-award record joined to a matched corpus entity (#1662, ME-C). */
export interface ContractorAward {
  entity_key: string;
  recipient_name: string;
  uei: string;
  total_obligations: number;
  nexus: string; // verified | context | open
  defense_share?: number | null; // DoD-family / all-agency obligations, 0..1
  annual_obligations: FederalAnnualFlow[];
  by_psc: FederalCategory[];
  by_naics: FederalCategory[];
}

/** A DoD-prime pattern match (`defense-contractors` feed) — leads, not verdicts. Each match that
 *  resolves to a USASpending recipient carries the federal dollars it already reached (#1662). */
export interface DefenseContractor {
  name: string;
  note?: string | null;
  patterns: string[];
  matched_entities: string[]; // entity keys
  awards?: ContractorAward[];
  total_obligations?: number | null; // Σ distinct matched awards (USD); null if none
  nexus?: string | null; // strongest matched nexus (verified > context > open); null if none
}
export interface DefenseContractors {
  contractors: DefenseContractor[];
  prime_owned: Record<string, unknown>[];
  army_controlled: Record<string, unknown>[];
  notes?: { subject?: string; source?: string; finding?: string; [k: string]: unknown } | null;
}

/** A minimal reference to a related LEI entity — the `direct`/`ultimate` parent of an
 *  LEI record (`watermark.gleif.LeiRef`), an `{lei, name}` pair, never a bare code. */
export interface LeiRef {
  lei: string;
  name: string;
}

/** One GLEIF LEI record (`lei` feed) — corridor entity parents. */
export interface LeiRecord {
  lei: string;
  legal_name: string;
  jurisdiction?: string | null;
  legal_form?: string | null;
  entity_status?: string | null;
  registration_status?: string | null;
  direct_parent?: LeiRef | null;
  ultimate_parent?: LeiRef | null;
  legal_address?: { city?: string; region?: string; country?: string } | null;
  last_update?: string | null;
  watchlist_name?: string | null;
  note?: string | null;
}
export interface LeiInventory {
  meta: {
    subject?: string;
    source?: string;
    record_count?: number;
    with_reported_parent?: number;
    method?: string;
    [k: string]: unknown;
  };
  records: LeiRecord[];
  leads: unknown[];
}

/** The localized BLS QCEW / Census baseline (`economics-baseline` feed). */
export interface EconSector {
  naics: string;
  sector_name: string;
  annual_avg_employment: ProvenancedValue;
  establishments?: ProvenancedValue | null;
  avg_annual_pay?: ProvenancedValue | null; // QCEW average annual pay per covered job (USD/year)
  avg_weekly_wage?: ProvenancedValue | null; // QCEW average weekly wage (USD/week)
  location_quotient?: ProvenancedValue | null;
}
/** One government-ownership slice of county employment (QCEW own 1/2/3, agglvl 71, #1661) — the
 *  federal/state/local jobs the private-only `sectors` mix cannot show; their sum plus the private
 *  sectors reconciles the all-ownership total. Same provenanced shape as `EconSector`. */
export interface EconOwnership {
  ownership: string; // QCEW own_code: "1" (federal), "2" (state), "3" (local)
  ownership_name: string; // "Federal Government" | "State Government" | "Local Government"
  annual_avg_employment: ProvenancedValue;
  establishments?: ProvenancedValue | null;
  avg_annual_pay?: ProvenancedValue | null;
  avg_weekly_wage?: ProvenancedValue | null;
  location_quotient?: ProvenancedValue | null;
}
export interface EconTrendPoint {
  year: number;
  total_employment: ProvenancedValue;
  establishments?: ProvenancedValue | null;
}
export interface EconPopPoint {
  year: number;
  population: ProvenancedValue;
}
export interface EconomicBaseline {
  fips: string;
  area_name: string;
  latest: {
    year: number;
    area_name?: string;
    total_employment?: ProvenancedValue;
    establishments?: ProvenancedValue;
    avg_annual_pay?: ProvenancedValue | null; // county-wide average annual pay (all ownerships)
    avg_weekly_wage?: ProvenancedValue | null;
    sectors: EconSector[];
    government?: EconOwnership[]; // federal/state/local ownership (QCEW own 1/2/3), #1661
  };
  trend: EconTrendPoint[];
  population?: { points: EconPopPoint[]; [k: string]: unknown } | null;
  median_household_income?: ProvenancedValue | null; // ACS5 B19013 (#1110)
  unit_caveat?: string | null; // county-straddle caveat promoted from prose note (#1661)
  coverage_note?: string | null; // QCEW coverage boundary — excludes active-duty military (#1661)
  note?: string | null;
}

/** Household energy burden (`energy-burden` feed, #1110): % of median household income
 *  (Census B19013) spent on residential electricity + heating (EIA). A fully `[derived]`
 *  consumer-impact metric — every figure carries its citation. */
export interface EnergyBurden {
  area: string;
  area_name: string;
  median_household_income: ProvenancedValue; // connector (Census B19013)
  avg_household_kwh_yr: ProvenancedValue; // assumption
  residential_electricity_price: ProvenancedValue; // connector (EIA)
  electricity_annual_cost: ProvenancedValue; // derived
  electricity_burden_pct: ProvenancedValue; // derived
  avg_household_mcf_yr: ProvenancedValue; // assumption
  residential_gas_price: ProvenancedValue; // connector (EIA)
  gas_annual_cost: ProvenancedValue; // derived
  gas_burden_pct: ProvenancedValue; // derived
  combined_annual_cost: ProvenancedValue; // derived: electricity + gas $/yr
  combined_burden_pct: ProvenancedValue; // derived
  method?: string;
  caveats?: string[];
}

/** One annual point on an EIA series (`consumer-energy` feed): `period` + native-unit `value`.
 *  Provenance is carried once at the series level, not repeated per point (`bosc.economics.model`). */
export interface EnergyPricePoint {
  period: string; // "2023" (annual) or "2023-12"
  value: number; // native units — see the series' `value.unit`
}
/** One EIA consumer energy-price (or sales) series, with its full annual history. */
export interface ConsumerEnergyPrice {
  series_id: string;
  label: string;
  fuel: "electricity" | "natural_gas";
  metric: "price" | "sales";
  period: string; // latest period; mirrors points[-1].period
  area: string;
  value: ProvenancedValue; // latest point; native units in `.unit`
  points: EnergyPricePoint[]; // full annual series, oldest→newest
}
/** The committed EIA consumer energy-cost reference (`consumer-energy` feed). */
export interface ConsumerEnergyCosts {
  area: string;
  area_name: string;
  prices: ConsumerEnergyPrice[];
  source?: string;
  note?: string;
}

// --- network: the cross-site basin synthesis (object feed; bosc.network, #308/#323) ---
export interface NodeScreen {
  npdes: string;
  discharger: string;
  receiving_water?: string | null;
  design_flow_mgd?: number | null;
  dilution_ratio?: number | null;
  flag?: string | null; // ok | tight | violation (when screened)
  status: string; // screened | no_receiving_water | no_7q10 | no_design_flow | not_in_inventory
  detail?: string;
}
export interface NodeGrid {
  utility?: string | null;
  ownership?: string | null;
  holding_company?: string | null;
  balancing_authority?: string | null;
  retail_regulator?: string | null;
  avg_price_cents_kwh?: number | null;
}
export interface NodeEconomy {
  year?: number | null;
  total_employment?: number | null;
  employment_change_pct?: number | null;
  population?: number | null;
  manufacturing_lq?: number | null;
  information_lq?: number | null;
}
export interface NodeToxics {
  facility_count?: number | null;
  top_emitter?: string | null;
  vintage_last_year?: number | null;
}
/** A disclosed facility's real-world lifecycle stage (`bosc.sites.FacilityLifecycle`, #1628) — the
 *  four-stage clock the facility-status rail walks. Read off the bundle, not a hardcoded dict. */
export type FacilityStatus = "investigation" | "confirmed" | "construction" | "live";

/** The disclosed data-center end-use archetype (`bosc.sites.DcEndUse`) — the SAME vocabulary as the
 *  end-use explorer's `DcKey`, aliased (not re-typed) so the two can never drift (#1628 review).
 *  `null`/absent ⇒ the end use is `[open]` (never asserted). */
export type FacilityEndUse = import("./endUse").DcKey;

export interface NodeActivity {
  has_disclosed_facility: boolean;
  facility_count?: number;
  facility_status?: FacilityStatus | null;
  operator?: string | null;
  end_use?: FacilityEndUse | null;
  it_load_mw?: number | null;
  summary?: string;
}

/** One disclosed data-center campus — the `facility` feed row (`bosc.site.feeds.FacilityItem`, #1628). */
export interface FacilityItem {
  key: string;
  name: string;
  is_primary: boolean;
  status: FacilityStatus;
  operator?: string | null;
  operator_citation?: string | null;
  end_use?: FacilityEndUse | null;
  end_use_citation?: string | null;
  facility_type?: string | null;
  it_load_mw?: number | null;
  it_load_low_mw?: number | null;
  it_load_high_mw?: number | null;
  // The two IT-load groundings stay distinct so permit-grounded vs screening-bracket is a typed
  // discriminant, not a prose regex (#1697 / #1628 review): exactly one is set on a disclosed load.
  air_permit_citation?: string | null;
  air_permit_relpath?: string | null;
  it_load_citation?: string | null;
  gross_floor_area_sqft?: number | null;
  disclosed_investment_usd?: number | null;
  disclosure_citation?: string | null;
  cooling_model: CoolingModel;
  cooling_model_source: "document" | "connector" | "reference" | "assumption";
  cooling_model_citation: string;
  parcels_relpath?: string | null;
  footprint_relpath?: string | null;
}

/** The manifest's compact facility block (`bosc.site.feeds.FacilitySummary`, #1628) — the primary
 *  campus's lifecycle status + the facility count, the per-slug source the badge reads. */
export interface FacilitySummary {
  status: FacilityStatus;
  count: number;
  primary_name: string;
  primary_operator?: string | null;
  primary_end_use?: FacilityEndUse | null;
}
export interface WatershedNode {
  slug: string;
  place: string;
  county: string;
  huc8: string;
  receiving_water: string;
  drainage_path: string[];
  subtree: string; // Auglaize | Tiffin | Maumee mainstem
  downstream: string; // the collector node it drains into, or the basin sink
  regime: string; // receiving-water taxonomy
  screen: NodeScreen;
  grid: NodeGrid;
  economy: NodeEconomy;
  toxics: NodeToxics;
  activity: NodeActivity;
}
export interface BasinNetwork {
  sink: string;
  shared_constraint: string;
  generated_at?: string | null;
  nodes: WatershedNode[];
}

// --- routed storm hydrograph (#1184) ------------------------------------------------------
// The loop's design-storm hydrograph routed down the cited confluence graph via Muskingum-Cunge:
// how much a channel attenuates + lags one reach's inflow peak. Mirrors the Python
// `watermark.hydrology.model.ReachRouting`.
export interface ReachRouting {
  node_id: string;
  name: string;
  length_ft: number;
  slope: number;
  inflow_peak_cfs: number;
  inflow_time_to_peak_hr: number;
  outflow_peak_cfs: number;
  outflow_time_to_peak_hr: number;
  attenuation_pct: number; // peak reduction across the reach, >= 0
  lag_hr: number; // delay in time-to-peak across the reach, >= 0
  subreaches?: number; // series Courant≈1 sub-reaches the reach was split into (WS-09 / #1609)
  courant?: number; // sub-reach Courant number c·Δt/Δx — routing validity flag, ≈ 1
}

// The `routed-hydrograph` object feed — the routed outlet hydrograph vs. the naive summed
// (un-routed) one, plus the per-reach attenuation/lag. Mirrors `RoutedHydrographNetwork`.
export interface RoutedHydrographNetwork {
  tier: "tier0";
  scenario: string;
  site: string; // the loop's site label (e.g. "Lima")
  return_period_yr: number;
  storm_depth_in: number;
  dt_hr: number;
  times_hr: number[];
  outlet_hydrograph_cfs: number[]; // routed at the outlet
  summed_hydrograph_cfs: number[]; // naive superposition of local inflows (un-routed)
  routed_peak_cfs: number;
  summed_peak_cfs: number;
  peak_attenuation_pct: number; // 100 * (summed_peak - routed_peak) / summed_peak
  routed_time_to_peak_hr: number;
  summed_time_to_peak_hr: number;
  lag_hr: number; // routed_time_to_peak - summed_time_to_peak
  reaches: ReachRouting[];
  warnings: string[];
}

// --- air dispersion field (GPU field/flow viz, epic #1237 / #1232) ------------------------
// The gridded AERMOD concentration surface the deck.gl FieldLayer renders. Distinct from the
// `air-dispersion` NAAQS *screen* feed. Mirrors `bosc.site.feeds.DispersionField`.

/** The receptor-grid geometry in AERMOD model metres (source at the origin, X=east, Y=north). */
export interface DispersionGrid {
  nx: number;
  ny: number;
  dx_m: number;
  dy_m: number;
  x0_m: number; // SW-corner easting, relative to the source at (0, 0)
  y0_m: number; // SW-corner northing
}

/** The model grid's WGS84 corner box — a deck.gl `[west, south, east, north]` bounds box. */
export interface DispersionGeoRef {
  crs: string; // "WGS84 (EPSG:4326)"
  source_lon: number;
  source_lat: number;
  sw_lon: number;
  sw_lat: number;
  ne_lon: number;
  ne_lat: number;
}

/** One averaging period's gridded surface + its NAAQS reference line. */
export interface DispersionPeriodField {
  averaging_period: string; // AERMOD AVE token: "1" | "8" | "24" | "ANNUAL" | ...
  values: (number | null)[]; // µg/m³, row-major `values[iy * nx + ix]`; null = no receptor
  max_conc_ug_m3: number | null;
  naaqs_ug_m3: number | null;
  exceeds_naaqs: boolean; // peak > standard (screening only — a flag, not a violation)
}

/**
 * A gridded AERMOD dispersion surface for one pollutant (`bosc.site.feeds.DispersionField`).
 * `provenance` is fixed to `"assumption"` — the permit redacts the genset stack as CBI, so every
 * concentration is `[inference]`, never `[verified]`. `available` is false (with empty `values`)
 * when the AERMOD binary/met was absent: the geometry/geo_ref/NAAQS lines are real, nothing faked.
 */
export interface DispersionField {
  site: string;
  pollutant: string;
  unit: string; // "ug/m3"
  provenance: "assumption";
  available: boolean;
  grid: DispersionGrid;
  geo_ref: DispersionGeoRef;
  periods: DispersionPeriodField[];
  stack_is_assumption: boolean;
  engine_version: string;
  caveats: string[];
  note: string;
}

// --- reach-network centerlines (GPU flow viz, epic #1237 / #1235) --------------------------
// The real river-centerline geometry the deck.gl FlowLayer advects particles over. Mirrors
// `bosc.site.feeds.ReachNetwork`. Verbatim NHDPlus (USGS NLDI), keyed by `node_id` so the
// FlowMap island joins each reach's flow magnitude (routed-hydrograph) and deficit state
// (hydrology-scenarios) by node — this feed carries geometry only.

/** One reach node's river centerline — a downstream-oriented (lon, lat) polyline. */
export interface ReachLine {
  node_id: string; // the network.yaml node id (join key into routed-hydrograph / scenarios)
  name: string;
  receiving_water?: string | null;
  downstream?: string | null; // the node this reach drains into (null at the outlet)
  length_km: number;
  coordinates: [number, number][]; // (lon, lat), ordered head → downstream
}

/** The reach network's river-centerline geometry (`bosc.site.feeds.ReachNetwork`). */
export interface ReachNetwork {
  site: string;
  crs: string;
  reaches: ReachLine[];
  note: string;
  caveats: string[];
}

// --- water seasonal evaporation / net-atmospheric-withdrawal field (epic #1237 / #1236) ----
// The seasonal climograph the deck.gl FieldLayer renders as a cartesian month-axis strip. The
// field scalar is net atmospheric withdrawal (reference ET0 - precip, mm/day). Mirrors
// `bosc.site.feeds.SeasonalField`.

/** One month of the seasonal climograph: the climate drivers + the low-flow screen. */
export interface SeasonalMonthCell {
  month: string; // JAN..DEC
  growing_season: boolean; // ET0 > precip this month
  et0_mm_day: number;
  precip_mm_day: number;
  net_atmospheric_mm_day: number; // ET0 - precip — the field scalar
  low_flow_cfs: number; // the cited design low flow applied this month
  low_flow_basis: string; // "30Q10 summer" | "7Q10 annual"
  consumptive_cfs: number; // this month's net consumptive draw
  multiple: number | null; // draw / low_flow (null when the floor is 0)
}

/**
 * The seasonal evaporation / net-atmospheric-withdrawal climograph (`bosc.site.feeds.SeasonalField`).
 * `provenance` is fixed to `"reference"` — the climograph is the cited NASA POWER normals + FAO-56
 * ET0. The per-month `multiple` overlays the *modeled* buildout draw against the cited seasonal low
 * flow, so that read alone is `[inference]` (surfaced in the SSR table/probe, not the mm/day raster).
 * `available` is false (with empty `months`) when the climate/scenario inputs were absent.
 */
export interface SeasonalField {
  site: string;
  scenario: string;
  cooling_model: string | null;
  unit: string; // "mm/day" — the field scalar's unit
  provenance: "reference";
  available: boolean;
  consumptive_cfs: number | null; // the headline draw screened (cfs)
  annual_7q10_cfs: number | null;
  summer_30q10_cfs: number | null;
  one_q10_cfs: number | null;
  annual_multiple: number | null; // draw / annual 7Q10
  summer_multiple: number | null; // draw / summer 30Q10 — the seasonal headline
  growing_season_months: string[];
  months: SeasonalMonthCell[];
  caveats: string[];
  note: string;
}

// --- boom-origin hypotheses (the directory lenses) + their evidence cells (#308) ----------
/** One reading of the boom — content of a directory lens (`bosc.hypotheses.Hypothesis`). */
export interface HypothesisItem {
  id: string; // "water" | "defense" | "surveillance"
  number: string; // "H1" | "H2" | "H3"
  name: string;
  claim: string;
  thesis: string;
  status: "reference" | "emerging";
  signals: string[];
  groups: string[];
  fields: string[];
  related_docs: string[];
  predicted_evidence: string[];
}

/** One (site x hypothesis) evidence cell (`bosc.hypotheses.HypothesisAssessment`). */
export interface HypothesisAssessmentItem {
  site: string;
  hypothesis: string;
  signal?: string | null;
  tag: import("./evidence").TagKind; // the canonical evidence vocabulary (#579)
  sub_thesis?: string | null; // investigative-frame tag (#905): coercion | end-use | capture | opacity | nexus
  group?: string | null;
  fields: Record<string, string>;
  citations: Citation[];
}

// --- open-questions feed (`bosc.site.feeds.OpenQuestionItem`, issue #1568, epic #1560 wk B) ---
/** Where a still-open question was aggregated from: a `leads`-board row or a hypothesis-matrix cell. */
export type OpenQuestionOrigin = "lead" | "hypothesis";

/**
 * One unanswered question in the corpus — an `[open]`-tagged lead or hypothesis cell.
 *
 * A **projection** feed (`bosc.site.open_questions`), not a new extraction: it aggregates every
 * still-open thread the bundle already ships — the `[open]`-tagged rows of the `leads` board and
 * the `[open]`-tagged cells of the `hypothesis-assessments` matrix — into one flat, provenanced
 * list (an `[inference]` lead, a labelled reading rather than a gap, is deliberately excluded, so
 * every row is `[open]`). The lead-derived fields (`kind`/`status`/`issue`) are present only for
 * `origin === "lead"`; the hypothesis-derived fields (`hypothesis`/`hypothesis_label`/`signal`)
 * only for `origin === "hypothesis"`.
 */
export interface OpenQuestionItem {
  /** Stable id: the lead id, or `hyp:<hypothesis>:<site>` for a matrix cell. */
  id: string;
  origin: OpenQuestionOrigin;
  /** The open question — the lead title, or a synthesized cell prompt. */
  question: string;
  /** One honest paragraph of context (never fabricated). */
  detail: string;
  /** The real provenance citation — where this gap is recorded. */
  source: string;
  // lead-derived context (present when origin === "lead") — the lead:kind:* / lead:status:* vocab.
  kind?: import("./leads").LeadKind | null;
  status?: import("./leads").LeadStatus | null;
  issue?: number | null;
  // hypothesis-derived context (present when origin === "hypothesis").
  hypothesis?: string | null; // the lens id ("water" | "defense" | "surveillance")
  hypothesis_label?: string | null; // the human lens label, e.g. "H1 Water & Coercion"
  signal?: string | null; // the cell's signal strength ("anchor"|"strong"|"moderate"|"watch")
}

// --- corpus-index feed (`bosc.site.feeds.CorpusNodeItem`, issue #1573, epic #1560 wk C) ------
/** The BOSC display kind of a corpus node — the yidam `class` folds several of these into one. */
export type CorpusNodeKind =
  | "site"
  | "entity"
  | "person"
  | "concept"
  | "hypothesis"
  | "lead"
  | "open-question"
  | "relation"
  | "node";

/**
 * One node of the yidam corpus mirror — a browsable row for the `/wiki/corpus` node-index page.
 *
 * A **projection** feed (`bosc.site.corpus_index`), not a new extraction: it re-reads the projected
 * corpus mirror into a flat, sortable table. `node_class` is the yidam class
 * (`artifact`/`concept`/`hypothesis`/`question`/`relation`); `kind` is the finer BOSC display kind
 * (an `artifact` is a site anchor, an entity, or a person; a `question` is a lead or an open cell).
 * `links_out` is the node's outgoing-edge count, `links_in` the edges pointing at it, `lines` the
 * serialized-node line count (parity with `yidam corpus-index`). `updated` is the newest commit
 * date (`YYYY-MM-DD`) of the committed source the node derives from — null when it has none.
 */
export interface CorpusNodeItem {
  /** The yidam node id — `<class>/<name>`. */
  id: string;
  /** The yidam class — `artifact` | `concept` | `hypothesis` | `question` | `relation`. */
  node_class: string;
  /** The finer BOSC display kind, refined from the node's meta. */
  kind: CorpusNodeKind;
  label: string;
  /** `"site"` | `"network"` (from the node's meta), when known. */
  scope?: string | null;
  links_out: number;
  links_in: number;
  lines: number;
  /** ISO date of the newest commit touching the node's source(s), or null when unknown. */
  updated?: string | null;
}

// --- corpus-nodes retrieval feed (`bosc.site.feeds.CorpusRetrievalNodeItem`, #1575, wk D2) ----
/**
 * One corpus-mirror node as a client-side retrieval unit — the searchable peer of `CorpusNodeItem`.
 *
 * The `corpus-nodes` feed (`bosc.site.corpus_nodes`) is the substrate behind the wiki "ask this
 * concept" affordance: the same mirror the `/wiki/corpus` map projects, but carrying each node's
 * searchable `text` (the canonical `node_text` the semantic index also embeds — so lexical and
 * vector surfaces tokenize the same content), its `evidence` tag when it bears one, its wiki page
 * key `ref` (the concept slug for a `concept` node), and its undirected 1-hop `neighbors`. A concept
 * page loads it, scopes to the concept's neighborhood, and runs client-side lexical retrieval over
 * that subset — offline, no server (the D3 spike's verdict, #1576).
 */
export interface CorpusRetrievalNodeItem {
  /** The yidam node id — `<class>/<name>`. */
  id: string;
  /** The BOSC display kind (same mapping as `corpus-index`). */
  kind: CorpusNodeKind;
  label: string;
  /** Searchable blob — label · description · class · salient meta (reconciled with the vector index). */
  text: string;
  /** The node's evidence tag when it bears one (`[open]` leads/questions, `[inference]`), else null. */
  evidence?: FactStatus | null;
  /** Wiki page key — the concept slug for a `concept` node (slug↔node join + route param), else null. */
  ref?: string | null;
  /** Undirected 1-hop neighbor ids (out-links ∪ in-links), the graph a concept's neighborhood walks. */
  neighbors: string[];
}

// --- the data catalog (`bosc.site.feeds.CatalogItem`, epic #631 Phase 3 / #659) -----------
/** One storage file of a catalog dataset. */
export interface CatalogStorageFile {
  relpath: string;
  media_type: string;
  lfs: boolean;
}
/** The reconcile snapshot for a dataset (`data/catalog/_observed.yaml`). */
export interface CatalogObserved {
  exists: boolean;
  sha256?: string | null;
  size_bytes: number;
  lfs_materialized: boolean;
  file_count: number;
  stale: boolean;
  asof?: string | null;
}
/** One registered dataset in the data catalog — what exists, where from, license, freshness. */
export interface CatalogItem {
  id: string;
  title: string;
  scope: string;
  collection: string;
  status: string;
  producer_kind: string;
  command?: string | null;
  connector_ref?: string | null;
  source: string;
  external_url?: string | null;
  license?: string | null;
  access_tier: string;
  site_scope: string;
  cadence: string;
  ttl_days?: number | null;
  last_refreshed?: string | null;
  tags: string[];
  storage: CatalogStorageFile[];
  observed?: CatalogObserved | null;
  citation: Citation;
}

/** A dataset's freshness state, derived from its reconcile snapshot. */
export type CatalogFreshness = "fresh" | "stale" | "missing" | "unmaterialized" | "unknown";

/** Reduce the observed snapshot to a single freshness state for display. */
export function catalogFreshness(o: CatalogObserved | null | undefined): CatalogFreshness {
  if (!o) return "unknown";
  if (!o.exists) return "missing";
  if (!o.lfs_materialized) return "unmaterialized"; // LFS pointer in this checkout — expected
  if (o.stale) return "stale";
  return "fresh";
}

// --- greenops: Watermark's own compute footprint (`bosc.greenops.model.GreenopsReport`) ---
// The self-reported usage → electricity → water derivation the sustainability page reads
// (#1076/#1084, bundle contract 1.21.0). Intentionally a PARTIAL mirror — only the fields
// `/about/sustainability` renders; the committed `schemas/greenops.schema.json` stays
// authoritative. Every numeric is a `ProvenancedValue` whose `source` is `derived` or
// `assumption` — never `document`/`connector`, so no figure ever renders `[verified]`
// (enforced Python-side by `GreenopsReport.assert_no_verified`).

/** A labeled provenanced quantity — one bar / slice / month in a breakdown series. */
export interface GreenopsQuantity {
  label: string;
  value: ProvenancedValue;
}

/** One of the four report headline stats (compute / AI inferences / electricity / water). */
export interface GreenopsHeadline {
  key: string;
  label: string;
  value: ProvenancedValue;
  sub: string;
  source_label: string; // display name of where it came from (not the ProvenancedValue citation)
}

/** One derivation note under the methodology block. */
export interface GreenopsMethodology {
  title: string;
  body: string;
}

/** The assembled compute-footprint report the sustainability page reads. */
export interface GreenopsReport {
  period: { label: string; start: string; end: string; kind: string };
  headline: GreenopsHeadline[];
  compute_by_function: { unit: string; functions: GreenopsQuantity[] };
  ai_by_task: { unit: string; tasks: GreenopsQuantity[] };
  electricity: {
    unit: string;
    monthly: GreenopsQuantity[];
    grid: ProvenancedValue;
    renewable: ProvenancedValue;
  };
  water: {
    unit: string;
    direct: ProvenancedValue;
    indirect: ProvenancedValue;
    budget_cap: ProvenancedValue;
  };
  methodology: GreenopsMethodology[];
  sources: string[];
  note: string;
}

/** Map a provenanced value's `source` onto an evidence badge — greenops figures are modeled,
 *  so `derived`/`assumption` (and anything not `document`/`connector`) render `[inference]`,
 *  never `[verified]`. */
export function provenanceEvidence(
  pv: Pick<ProvenancedValue, "source"> | null | undefined,
): "verified" | "inference" {
  return pv?.source === "document" || pv?.source === "connector" ? "verified" : "inference";
}

// --- helpers -----------------------------------------------------------------

/** A URL-safe slug from any label/key (e.g. an entity key "AMAZON COM SERVICES"). */
export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Human-readable byte size. */
export function formatBytes(n: number): string {
  if (!n) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  const v = n / 1024 ** i;
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}
