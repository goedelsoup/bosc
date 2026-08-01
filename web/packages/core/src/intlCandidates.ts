/**
 * The international data-center candidates register, frontend side (#1394, epic #1387).
 *
 * The types mirror `watermark.international.model` exactly — the `data-center-candidates` feed IS
 * that Pydantic model, serialized. Nothing here re-derives a claim: `tag`, `corroboration` and
 * `is_contested` arrive as computed fields on the feed precisely so the evidentiary rules live in
 * one place (Python) rather than being reimplemented in TypeScript, where the two copies would
 * quietly drift apart.
 *
 * What this module *does* add is presentation-side grouping: the map needs the register split by
 * AOI and by corroboration, and it needs one honest empty state.
 *
 * **This module must stay node-free.** The deck.gl island imports it (for `SOURCE_LABELS` and
 * `aoiSummaries`), and a `client:only` island's imports are bundled for the browser — so a single
 * `./bundle` import here pulls `node:fs` / `node:path` into the client build and fails Rollup
 * with "dirname is not exported by __vite-browser-external". The build-time feed read therefore
 * lives next door in `intlCandidatesFeed.ts`, which only the Astro page imports.
 */

/** `watermark.international.model.PriorSource`. */
export type PriorSource = "peeringdb" | "osm" | "operator_disclosure" | "national_registry" | "trade_press";

/** `watermark.international.model.DetectionBasis`. */
export type DetectionBasis = "priors_only" | "screened" | "vision_adjudicated";

/** `watermark.international.model.CoolingType`. */
export type CoolingType = "evaporative" | "dry" | "closed_loop" | "hybrid" | "seawater" | "unknown";

/** `watermark.international.model.Corroboration`. */
export type Corroboration = "single_source" | "corroborated";

/** The tag an entry renders as. Note the absence of `verified` — that is the contract, not an
 *  oversight: no basis in this funnel maps to it. */
export type CandidateTag = "inference" | "reference" | "open";

/** One open register's row about one location (`PriorObservation`). */
export interface PriorObservation {
  source: PriorSource;
  source_id: string;
  url: string;
  latitude: number;
  longitude: number;
  name?: string | null;
  operator?: string | null;
  address?: string | null;
  country?: string | null;
  license: string;
  retrieved_at: string;
  network_count?: number | null;
  exchange_count?: number | null;
}

/** A different operator name, from a different source, for the same place (`CompetingClaim`). */
export interface CompetingClaim {
  operator: string;
  citation: string;
  source: PriorSource;
}

/** `OperatorAttribution` — cited, or `[open]`, and flagged when sources disagree. */
export interface OperatorAttribution {
  operator?: string | null;
  citation?: string | null;
  source?: PriorSource | null;
  contested: CompetingClaim[];
  is_contested: boolean;
  tag: CandidateTag;
}

/** One international candidate (`Candidate`). */
export interface Candidate {
  key: string;
  aoi: string;
  country: string;
  latitude: number;
  longitude: number;
  name?: string | null;
  attribution: OperatorAttribution;
  basis: DetectionBasis;
  cooling: CoolingType;
  observations: PriorObservation[];
  scene_ids: string[];
  sources: PriorSource[];
  corroboration: Corroboration;
  tag: CandidateTag;
}

/** One swept AOI's outcome, including a null one (`AoiResult`). */
export interface AoiResult {
  slug: string;
  label: string;
  country: string;
  bbox: [number, number, number, number];
  selection_basis: string;
  observations_by_source: Record<string, number>;
  candidate_count: number;
  corroborated_count: number;
  is_negative: boolean;
}

/** One prior source's licence + attribution terms (`SourceTerms`). */
export interface SourceTerms {
  source: PriorSource;
  label: string;
  url: string;
  license: string;
  attribution: string;
  notes?: string | null;
}

/** The whole register (`CandidatesRegister`). */
export interface CandidatesRegister {
  scope: string;
  generated_at: string;
  corroboration_radius_m: number;
  aois: AoiResult[];
  sources: SourceTerms[];
  candidates: Candidate[];
}

export const CANDIDATES_FEED = "data-center-candidates";

/** Reader-facing labels for the source ladder. */
export const SOURCE_LABELS: Record<PriorSource, string> = {
  peeringdb: "PeeringDB",
  osm: "OpenStreetMap",
  operator_disclosure: "Operator disclosure",
  national_registry: "National registry",
  trade_press: "Trade press",
};

/** What each detection basis actually means, in a sentence a reader can act on. */
export const BASIS_GLOSS: Record<DetectionBasis, string> = {
  priors_only:
    "Placed by open registers only — no imagery has been adjudicated, so this relays what others published.",
  screened:
    "Passed a geospatial screen (footprint, substation proximity, construction change) — our inference, not a record.",
  vision_adjudicated:
    "Adjudicated from satellite imagery — our inference about the pixels, carrying the scene ids it read.",
};

/** Only the candidates ≥2 independent sources agree on. */
export function corroborated(register: CandidatesRegister): Candidate[] {
  return register.candidates.filter((c) => c.corroboration === "corroborated");
}

/** Candidates a single register places — real leads, and the coverage gap made visible. */
export function singleSource(register: CandidatesRegister): Candidate[] {
  return register.candidates.filter((c) => c.corroboration === "single_source");
}

/** Candidates whose sources name different operators. */
export function contested(register: CandidatesRegister): Candidate[] {
  return register.candidates.filter((c) => c.attribution.is_contested);
}

/** One AOI's rollup for the summary board, in the register's own AOI order. */
export interface AoiSummary extends AoiResult {
  /** Corroborated share, 0–1. `0` when the AOI produced no candidates at all. */
  corroboratedShare: number;
  /** The AOI's centre, for flying the map to it. */
  center: { latitude: number; longitude: number };
}

export function aoiSummaries(register: CandidatesRegister): AoiSummary[] {
  return register.aois.map((aoi) => {
    const [south, west, north, east] = aoi.bbox;
    return {
      ...aoi,
      corroboratedShare: aoi.candidate_count > 0 ? aoi.corroborated_count / aoi.candidate_count : 0,
      center: { latitude: (south + north) / 2, longitude: (west + east) / 2 },
    };
  });
}

/**
 * How a candidate's operator should be *worded* — the one place attribution turns into prose.
 *
 * Three states, deliberately distinct: a cited name, a contested pair, and `[open]`. Collapsing
 * contested into "the operator is X" is the exact failure the register was built to avoid, so the
 * caller gets a shape it cannot render carelessly rather than a bare string.
 */
export type AttributionView =
  | { kind: "open" }
  | { kind: "cited"; operator: string; citation: string; source: PriorSource }
  | {
      kind: "contested";
      operator: string;
      citation: string;
      source: PriorSource;
      others: CompetingClaim[];
    };

export function attributionView(candidate: Candidate): AttributionView {
  const a = candidate.attribution;
  if (!a.operator || !a.citation || !a.source) return { kind: "open" };
  if (a.is_contested) {
    return {
      kind: "contested",
      operator: a.operator,
      citation: a.citation,
      source: a.source,
      others: a.contested,
    };
  }
  return { kind: "cited", operator: a.operator, citation: a.citation, source: a.source };
}
