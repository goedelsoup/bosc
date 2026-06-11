/**
 * TypeScript shapes for the bundle feed rows this app consumes. These mirror the
 * Pydantic models in `bosc.site.feeds`; they're intentionally partial — only the
 * fields the frontend reads are typed. The committed `schemas/*.schema.json` are
 * the authoritative contract (schema validation is issue #62).
 */

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
export function evidenceKind(
  c: Pick<Citation, "verified"> | null | undefined,
): "verified" | "inference" {
  return c?.verified ? "verified" : "inference";
}

export interface RecordItem {
  rel: string;
  group: string;
  title: string;
  confidence?: Confidence | null;
  warnings: string[];
  fields: Record<string, unknown>;
  approximate_paths: string[];
  citation: Citation;
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
}

export interface ScenarioResult {
  scenario: {
    name: string;
    description?: string | null;
    cooling_demand: ProvenancedValue;
    consumptive_fraction: ProvenancedValue;
    basis?: string | null;
  };
  consumptive_loss: ProvenancedValue;
  ottawa_7q10: ProvenancedValue;
  ottawa_live: ProvenancedValue;
  balance: ProvenancedValue;
  assimilative: ProvenancedValue;
}

/** One dated Esri Wayback aerial release (the `geo/imagery` feed's `meta.wayback`). */
export interface WaybackRelease {
  date: string; // e.g. "2014-12"
  release: number; // the Wayback releaseNum, substituted into the tile template
}

/** The `geo/imagery` feed shape (issue #72): AOI footprints + the dated ladder. */
export interface ImageryFeed {
  type: "FeatureCollection";
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
  features: {
    type: "Feature";
    geometry: { type: string; coordinates: unknown };
    properties: { layer: string; label?: string; color?: string; site?: string; bbox?: number[] };
  }[];
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

/** A DoD-prime pattern match (`defense-contractors` feed) — leads, not verdicts. */
export interface DefenseContractor {
  name: string;
  note?: string | null;
  patterns: string[];
  matched_entities: string[]; // entity keys
}
export interface DefenseContractors {
  contractors: DefenseContractor[];
  prime_owned: Record<string, unknown>[];
  army_controlled: Record<string, unknown>[];
  notes?: { subject?: string; source?: string; finding?: string; [k: string]: unknown } | null;
}

/** One GLEIF LEI record (`lei` feed) — corridor entity parents. */
export interface LeiRecord {
  lei: string;
  legal_name: string;
  jurisdiction?: string | null;
  legal_form?: string | null;
  entity_status?: string | null;
  registration_status?: string | null;
  direct_parent?: string | null;
  ultimate_parent?: string | null;
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
  location_quotient?: ProvenancedValue | null;
}
export interface EconTrendPoint {
  year: number;
  total_employment: ProvenancedValue;
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
    sectors: EconSector[];
  };
  trend: EconTrendPoint[];
  population?: { points: EconPopPoint[]; [k: string]: unknown } | null;
  note?: string | null;
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
  const v = n / Math.pow(1024, i);
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}

/** Render a markdown-ish body as plain paragraphs (full MDX migration is #69). */
export function paragraphs(body: string): string[] {
  return body
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
}
