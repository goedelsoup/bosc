/**
 * The Methodology section content — single source of truth (#1128, epic #1126).
 *
 * Drives both the network-global `/methodology` hub (#1129) and the per-domain
 * `/methodology/[slug]` sub-pages (#1130), so the two never drift. This module is
 * *editorial* network-level content — the method across every site — not per-site
 * corpus data; nothing here is read from a content-bundle feed.
 *
 * The evidence-grammar vocabulary is NOT redefined here: it is imported from
 * `evidence.ts`, the canonical tag taxonomy (#579), so the page that explains the
 * tags agrees with the tags the corpus actually carries.
 */
import { EVIDENCE_GLOSS, EVIDENCE_PRIMARY, type EvidenceKind } from "./evidence";

/** The one-line thesis, as the `source → structured read → meaning → verify` chip flow. */
export const THESIS_FLOW: readonly string[] = ["source", "structured read", "meaning", "verify"];

/** The evidence grammar, in reading order — the four canonical tags + their reader gloss.
 *  Derived from the canonical taxonomy so the legend can never disagree with the data. */
export const EVIDENCE_GRAMMAR: readonly { kind: EvidenceKind; gloss: string }[] = EVIDENCE_PRIMARY.map(
  (kind) => ({ kind, gloss: EVIDENCE_GLOSS[kind] }),
);

/** The approximate-figure marker preserved from source transcription (`~12345`). */
export const APPROX_MARKER = {
  symbol: "~",
  gloss:
    "An approximate figure — read from a degraded source and preserved as approximate, never silently rounded to a false precision.",
} as const;

// --- The pipeline ---------------------------------------------------------------

export interface PipelineStage {
  /** Display index, mono (`01`/`02`/`03`). */
  num: string;
  id: "ingest" | "extract" | "analyze";
  title: string;
  /** One-line description of what the stage does. */
  method: string;
  /** The discipline that keeps the stage honest. */
  discipline: string;
}

export const PIPELINE: readonly PipelineStage[] = [
  {
    num: "01",
    id: "ingest",
    title: "Ingest",
    method:
      "Primary-source documents — degraded scans, OCR'd PDFs — are inventoried immutably, byte-for-byte, under chain of custody.",
    discipline:
      "Source bytes are never altered; a malformed filename is aliased, not renamed. The corpus is litigation evidence.",
  },
  {
    num: "02",
    id: "extract",
    title: "Extract",
    method:
      "A 300 DPI render is read by Claude vision under forced tool use into a typed, schema-validated row — figures taken from the image.",
    discipline:
      "The OCR text layer is a hint only; its digits are never trusted. Approximate reads keep their ~ marker.",
  },
  {
    num: "03",
    id: "analyze",
    title: "Analyze",
    method:
      "The reviewed rows are reconciled, linked into an entity graph and timeline, and read by live public-data connectors.",
    discipline:
      "Every derived figure carries a source, a confidence, and an as-of date; inference is labelled, never dressed as a record.",
  },
];

// --- The domains ----------------------------------------------------------------

/** The governing skill slug under `.claude/skills/` (the abstract method a domain defers to). */
export type SkillSlug =
  | "evidentiary-discipline"
  | "entity-and-document-deconstruction"
  | "gis-and-siting-analysis"
  | "public-records-and-legal-strategy"
  | "investigative-writing-and-editorial"
  | "data-center-sweep"
  | "document-production-and-ocr";

/** A worked example of the evidence grammar applied: a real claim and the tag it wears. */
export interface EvidenceExample {
  claim: string;
  kind: EvidenceKind;
}

/** A deep prose section on a domain's sub-page. */
export interface DomainSection {
  heading: string;
  body: string;
}

export interface Domain {
  /** Route slug under `/methodology/`. */
  slug: string;
  /** Card + sub-page title. */
  label: string;
  /** The domain's method in one declarative line — the hub card blurb and the sub-page H1 lead. */
  method: string;
  /** The live connectors / sources this domain pulls, as short mono chips. */
  dataSources: readonly string[];
  /** The honesty constraint — the framed guardrail callout on the sub-page. */
  guardrail: string;
  /** The abstract skill this domain's reasoning defers to, if any. */
  skill?: SkillSlug;
  /** Repo-relative source docs / packages the sub-page cites (the written record behind it). */
  sources: readonly string[];
  /** Deep prose sections (filled out per-domain in #1131). */
  sections: readonly DomainSection[];
  /** Worked evidence-grammar examples (filled out per-domain in #1131). */
  examples: readonly EvidenceExample[];
}

export const DOMAINS: readonly Domain[] = [
  {
    slug: "document-pipeline",
    label: "Document pipeline",
    method:
      "Degraded scans and OCR'd PDFs are read into typed, schema-validated rows — figures taken from the 300 DPI image, never the garbled OCR text layer.",
    dataSources: ["data/documents/**", "pypdfium2 render", "Claude vision"],
    guardrail:
      "Never trust the OCR digits: every figure is read off the image and validated against a Pydantic model, and an approximate read keeps its ~ marker.",
    skill: "entity-and-document-deconstruction",
    sources: ["src/watermark/pipeline", "CLAUDE.md"],
    sections: [
      {
        heading: "Read the image, not the text layer",
        body: "The OCR text layer is badly garbled — $109,307.69 arrives as $108.307.89 — so it is used only as a hint to route a page to the right format profile. The load-bearing figures are read from a 300 DPI render by a forced-tool-use vision pass, then validated against a contractor-agnostic Estimate model. Section taxonomy and markup rate come from the data, not from hardcoded fields.",
      },
    ],
    examples: [
      {
        claim: "The six Tetra Tech OPC sub-estimates total the roadwork figure printed on the summary sheet.",
        kind: "verified",
      },
    ],
  },
  {
    slug: "hydrology",
    label: "Hydrology & water balance",
    method:
      "A Tier-0 water balance and low-flow assimilative screen over the municipal loop — auditable and fast, not a SWMM/HEC-RAS substitute.",
    dataSources: ["USGS NWIS", "NOAA Atlas-14", "NASA POWER"],
    guardrail:
      "The Tier-0 screen flags where a fuller model is warranted; it does not replace one. Discharge is screened against 7Q10 low flow, not an average.",
    sources: ["docs/HYDROLOGY.md", "src/watermark/hydrology"],
    sections: [],
    examples: [],
  },
  {
    slug: "economics",
    label: "Economics & demand",
    method:
      "A county QCEW employment baseline and state EIA energy costs combined into a facility demand-pressure band.",
    dataSources: ["BLS QCEW", "Census ACS5", "EIA-861"],
    guardrail: "The demand-pressure band is a stylized screen, never a forecast.",
    sources: ["docs/ECONOMICS.md", "src/watermark/economics"],
    sections: [],
    examples: [],
  },
  {
    slug: "grid",
    label: "Grid & regulatory",
    method:
      "The campus load traced through the utility, the PJM balancing authority, the wholesale market, FERC, and federal policy.",
    dataSources: ["PJM", "EIA-861"],
    guardrail:
      "Each link in the chain is cited to its regulator; where the public record stops, the tag flips to [open].",
    sources: ["docs/GRID.md", "src/watermark/grid"],
    sections: [],
    examples: [],
  },
  {
    slug: "facility-compute",
    label: "Facility compute",
    method:
      "Power, water, and footprint resolved into an accelerator count and FLOPS by three independent bracketing methods.",
    dataSources: ["Facility permits", "Vendor datasheets"],
    guardrail: "Compute is reported as a range from three methods, never a single headline number.",
    sources: ["docs/COMPUTE.md", "src/watermark/facility"],
    sections: [],
    examples: [],
  },
  {
    slug: "gis-parcels",
    label: "GIS, parcels & imagery",
    method:
      "Public geospatial layers and satellite imagery joined to identify candidate parcels and infrastructure corridors.",
    dataSources: ["Planetary Computer STAC", "County parcels", "Committed GeoJSON"],
    guardrail:
      "The output is a candidate set, never a prediction; pixels are shown verbatim and corridors come from recorded instruments.",
    skill: "gis-and-siting-analysis",
    sources: ["docs/imagery-subsystem.md", "src/watermark/gis"],
    sections: [],
    examples: [],
  },
  {
    slug: "toxics-permits",
    label: "Toxics & air permits",
    method:
      "Air permits-to-install, NPDES discharge permits, and RSEI facility toxics scores assembled per facility.",
    dataSources: ["Ohio EPA eSuite", "EPA ECHO", "EPA RSEI"],
    guardrail:
      "Permit scope is read from the permit itself — coverage is stated, gaps are marked [open], nothing is inferred into a permit.",
    skill: "public-records-and-legal-strategy",
    sources: ["docs/toxics-and-the-corridor.md", "src/watermark/oepa"],
    sections: [],
    examples: [],
  },
  {
    slug: "civic-records",
    label: "Civic records & governance",
    method:
      "County political-subdivision meeting records discovered, fetched, OCR'd, indexed, and placed on a timeline.",
    dataSources: ["CivicPlus Agenda Center", "Municipal platform scrapers"],
    guardrail:
      "Only corridor-subject meetings surface; the download manifest — sha256, bytes, source URL — is the chain of custody.",
    skill: "public-records-and-legal-strategy",
    sources: ["src/watermark/civic"],
    sections: [],
    examples: [],
  },
  {
    slug: "entity-graph",
    label: "Entity graph & timeline",
    method: "A documented-edge-only entity graph and a dated timeline across every thread of the record.",
    dataSources: ["Recorder instruments", "Secretary of State filings", "GLEIF LEI"],
    guardrail:
      "An edge exists only when an instrument names it, and a node is added only when the record names it — no inferred relationships.",
    skill: "entity-and-document-deconstruction",
    sources: ["data/extracted/legal/corpus-completeness-audit.md", "src/watermark/pipeline"],
    sections: [],
    examples: [],
  },
  {
    slug: "places",
    label: "Places (POI)",
    method:
      "Curated points of interest, depth-marked from mention to watched, each resolved to a parcel number as its identity anchor.",
    dataSources: ["County parcels", "Curated POI store"],
    guardrail:
      "The parcel number is the dedup anchor; geometry carries a method, a confidence, and an as-of date, and is never fabricated.",
    sources: ["docs/poi-subsystem.md", "src/watermark/poi"],
    sections: [],
    examples: [],
  },
  {
    slug: "research-agent",
    label: "Research agent & MCP",
    method:
      "A Claude Agent SDK loop over the extracted corpus, exposing in-process MCP tools that read the real data.",
    dataSources: ["The extracted corpus", "In-process MCP tools"],
    guardrail:
      "The agent is site-scoped and never invents — off the reference build it serves the active site's own corpus or returns an honest “not yet available.”",
    skill: "evidentiary-discipline",
    sources: ["docs/investigative-method/SYSTEM_PROMPT.md", "src/watermark/agent"],
    sections: [],
    examples: [],
  },
  {
    slug: "platform-footprint",
    label: "Platform footprint",
    method: "The platform's own compute footprint modeled from its cloud, model, and CI usage.",
    dataSources: ["AWS Cost Explorer", "Anthropic Admin", "GitHub Actions", "EPA eGRID"],
    guardrail: "Every figure is modeled, not metered — [reference] or [inference], never connector-verified.",
    sources: ["src/watermark/greenops"],
    sections: [],
    examples: [],
  },
];

/** Lookup by slug — for `getStaticPaths()` and the sub-page route. */
export function domainBySlug(slug: string): Domain | undefined {
  return DOMAINS.find((d) => d.slug === slug);
}
