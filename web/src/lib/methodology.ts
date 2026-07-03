/**
 * The Methodology section content — single source of truth (#1128, epic #1126).
 *
 * Drives both the network-global `/methodology` hub (#1129) and the per-domain
 * `/methodology/[slug]` sub-pages (#1130), so the two never drift. This module is
 * *editorial* network-level content — the method across every site — not per-site
 * corpus data; nothing here is read from a content-bundle feed.
 *
 * Structure and layout follow the Watermark Design System methodology templates
 * (Claude Design → DesignSync). The copy is reconciled to the platform's *actual*
 * connectors and honest, clearly-illustrative examples — no invented sources or
 * figures dressed as real reads — per the repo's own no-fabrication discipline.
 *
 * The evidence-grammar vocabulary is NOT redefined here: it is imported from
 * `evidence.ts`, the canonical tag taxonomy (#579), so the page that explains the
 * tags agrees with the tags the corpus actually carries.
 */
import { type EvidenceKind, EVIDENCE_GLOSS, EVIDENCE_PRIMARY } from "./evidence";

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
    "A tilde before a figure marks it approximate — rounded or read from a range in the source, still tied to that source, never a false precision.",
} as const;

// --- The pipeline ---------------------------------------------------------------

export interface PipelineStage {
  /** Display index, mono (`01`/`02`/`03`). */
  num: string;
  id: "ingest" | "extract" | "analyze";
  title: string;
  body: string;
}

export const PIPELINE: readonly PipelineStage[] = [
  {
    num: "01",
    id: "ingest",
    title: "Ingest",
    body: "Primary documents enter as bytes: county recorder scans, OCR'd PDFs, live public-data feeds. Nothing is summarized before it's stored, and the source bytes are never altered.",
  },
  {
    num: "02",
    id: "extract",
    title: "Extract",
    body: "A structured read is pulled from the 300 DPI page image — tables, figures, signatures, redaction bars — and logged against the exact page and coordinate it came from. The garbled OCR text layer is a hint only.",
  },
  {
    num: "03",
    id: "analyze",
    title: "Analyze",
    body: "The read is reconciled, labeled with its evidence tag, linked into the entity graph and timeline, and set beside its cited source. What isn't corroborated is published anyway, marked open.",
  },
];

// --- Chain of custody -----------------------------------------------------------

export const CUSTODY: readonly { title: string; body: string }[] = [
  {
    title: "Immutable source bytes",
    body: "The original scan or filing, hashed and stored exactly as received — never renamed or edited in place.",
  },
  {
    title: "Reviewed extracted data",
    body: "Every structured read is checked against its source page before it is published.",
  },
  {
    title: "Regenerable reference datasets",
    body: "Anything pulled from a live public feed can be re-run and re-verified at any time.",
  },
];

// --- The method layer (the abstract skills) -------------------------------------

/** The governing skill slug under `.claude/skills/` (the abstract method a domain defers to). */
export type SkillSlug =
  | "evidentiary-discipline"
  | "entity-and-document-deconstruction"
  | "gis-and-siting-analysis"
  | "public-records-and-legal-strategy"
  | "investigative-writing-and-editorial"
  | "data-center-sweep"
  | "document-production-and-ocr";

/** The seven agent-discoverable skills, evidentiary-discipline first (the spine). */
export const SKILLS: readonly { slug: SkillSlug; label: string }[] = [
  { slug: "evidentiary-discipline", label: "Evidentiary discipline" },
  { slug: "entity-and-document-deconstruction", label: "Entity & document deconstruction" },
  { slug: "gis-and-siting-analysis", label: "GIS & siting analysis" },
  { slug: "public-records-and-legal-strategy", label: "Public records & legal strategy" },
  { slug: "investigative-writing-and-editorial", label: "Investigative writing & editorial" },
  { slug: "data-center-sweep", label: "Data-center sweep" },
  { slug: "document-production-and-ocr", label: "Document production & OCR" },
];

// --- The domains ----------------------------------------------------------------

/** A deep prose section on a domain's sub-page. */
export interface DomainSection {
  heading: string;
  body: string;
}

/** The four grammar-valid evidence kinds (the `EVIDENCE_PRIMARY` set) — the render-only
 *  annotation kinds (`filename`/`gap`/`key`) are excluded, so an example can only wear a
 *  tag a reader actually parses as a confidence signal. */
type PrimaryEvidenceKind = Exclude<EvidenceKind, "filename" | "gap" | "key">;

/** A worked example of the evidence grammar applied in a sentence — two tags in context.
 *  Deliberately generic: it shows *what kind* of claim wears each tag, never an invented
 *  figure presented as a real cited read. */
export interface EvidenceExample {
  before: string;
  first: PrimaryEvidenceKind;
  mid: string;
  second: PrimaryEvidenceKind;
  after: string;
}

export interface Domain {
  /** Route slug under `/methodology/`. */
  slug: string;
  /** Card + sub-page title. */
  label: string;
  /** The domain's method in one declarative line — the hub card blurb and the sub-page H1. */
  method: string;
  /** The live connectors / sources this domain reads, as short mono chips. */
  dataSources: readonly string[];
  /** Deep prose sections for the sub-page. */
  sections: readonly DomainSection[];
  /** A worked evidence-grammar example, rendered inline with real tags. */
  example: EvidenceExample;
  /** The honesty constraint — the framed guardrail callout on the sub-page. */
  guardrail: string;
  /** The abstract skill this domain's reasoning defers to, if any. */
  skill?: SkillSlug;
}

export const DOMAINS: readonly Domain[] = [
  {
    slug: "document-pipeline",
    label: "Document pipeline",
    method: "Every filing enters as bytes, then earns its structured read.",
    dataSources: ["County recorder scans", "OCR'd PDFs", "Native filings"],
    sections: [
      {
        heading: "Ingest, don't summarize",
        body: "Every document lands in the corpus exactly as received — a degraded scan, an OCR'd PDF, a native filing. Nothing is condensed or interpreted before it's stored, so the original is always there to walk back to.",
      },
      {
        heading: "Read the image, not the OCR",
        body: "Figures are pulled from the 300 DPI page image itself, never the garbled text layer OCR produces ($109,307.69 arrives from OCR as $108.307.89). The text layer is kept only as a search hint and to route a page to the right format profile.",
      },
      {
        heading: "Log the coordinate",
        body: "Every extracted figure is logged against the exact page, table, and cell it came from, so a reader can walk back to the source in one click, and an approximate read keeps its ~ marker.",
      },
    ],
    example: {
      before: "A dollar figure read straight off the auditor's filing is",
      first: "verified",
      mid: "; the buildout window inferred from the site plan's phasing language is",
      second: "inference",
      after: ".",
    },
    guardrail: "A figure with no source citation does not enter the record — not even as inference.",
    skill: "entity-and-document-deconstruction",
  },
  {
    slug: "hydrology",
    label: "Hydrology",
    method: "Streamflow, precipitation and aquifer draw, read against the site's water ask.",
    dataSources: ["USGS NWIS", "NOAA Atlas-14", "NASA POWER"],
    sections: [
      {
        heading: "Gauge before model",
        body: "Every hydrograph starts from an observed USGS gauge. Where no gauge sits nearby, a modeled estimate is shown and labeled, never blended in as if it were measured.",
      },
      {
        heading: "The demand-pressure band",
        body: "A site's stated water ask is placed against the local flow-duration curve so a reader can see, at a glance, what share of low flow the ask represents — screened against 7Q10 low flow, not an average.",
      },
      {
        heading: "Aquifer draw is regional",
        body: "Groundwater withdrawal is read at the basin scale, since a single well permit rarely shows the cumulative draw of a full build-out.",
      },
    ],
    example: {
      before: "A cooling-water request read from the discharge permit is",
      first: "verified",
      mid: "; the low flow it's screened against, modeled where no gauge sits nearby, is",
      second: "inference",
      after: ".",
    },
    guardrail: "The demand-pressure band is a stylized screen, never a forecast.",
  },
  {
    slug: "economics",
    label: "Economics",
    method: "Tax abatements, land assembly and shell-company cost, traced to public filings.",
    dataSources: ["BLS QCEW", "Census ACS5", "EIA-861"],
    sections: [
      {
        heading: "Follow the parcel",
        body: "Land assembly is read parcel by parcel from auditor and recorder records, so a large site is shown as the sequence of purchases that built it, not one round number.",
      },
      {
        heading: "Name the shell",
        body: "Where a purchaser is a Delaware LLC, the filing is read for its registered agent and any linked entities — never assumed to be the eventual operator.",
      },
      {
        heading: "Withheld is shown, not guessed",
        body: "When a sale price is redacted or reported as $0, the record shows the redaction directly rather than estimating a figure to fill it.",
      },
    ],
    example: {
      before: "A parcel price read from the recorded deed is",
      first: "verified",
      mid: "; the multi-year abatement value derived from the county's published schedule is",
      second: "inference",
      after: ".",
    },
    guardrail: "A shell company's registered agent is not treated as its owner.",
    skill: "entity-and-document-deconstruction",
  },
  {
    slug: "grid-regulatory",
    label: "Grid & regulatory",
    method: "Interconnection queues and utility filings, read for load and capacity signals.",
    dataSources: ["PJM", "EIA-861"],
    sections: [
      {
        heading: "Queue position is a lead",
        body: "A project's place in an interconnection queue is published as a lead — queue entries are withdrawn and re-filed constantly, so a position is never read as a commitment.",
      },
      {
        heading: "Filings over press releases",
        body: "Utility rate-case and tariff filings are the record; a company's own announcement is treated as unverified until a filing corroborates it.",
      },
      {
        heading: "Cumulative load, not one meter",
        body: "Where multiple projects share a substation, the record sums the filed load requests rather than reporting a single interconnection in isolation.",
      },
    ],
    example: {
      before: "A load request read from the PJM queue is",
      first: "verified",
      mid: "; the in-service date drawn from the docket's stated timeline is",
      second: "inference",
      after: ".",
    },
    guardrail: "A queue position is a lead, not a commitment to build.",
  },
  {
    slug: "facility-compute",
    label: "Facility compute",
    method: "Rack count and power draw, estimated from permits and equipment manifests.",
    dataSources: ["Facility permits", "Vendor datasheets"],
    sections: [
      {
        heading: "Square footage first",
        body: "Compute capacity is estimated from permitted floor area and cooling-system tonnage before any equipment manifest is available — always labeled as inference, and reported as a range from three independent methods.",
      },
      {
        heading: "Manifests correct the estimate",
        body: "Where an air permit or equipment manifest lists specific generator or chiller models, the record replaces the floor-area estimate with the manifest figure.",
      },
      {
        heading: "Backup power is a tell",
        body: "The number and size of backup generators, read from air permits, is one of the few figures that scales cleanly with facility size.",
      },
    ],
    example: {
      before: "A backup-generator count read from the air permit is",
      first: "verified",
      mid: "; the IT-load bracket estimated from permitted floor area is",
      second: "inference",
      after: ".",
    },
    guardrail: "A rack-count estimate is never presented with the precision of a manifest figure.",
  },
  {
    slug: "gis-parcels",
    label: "GIS & parcels",
    method: "Parcel assembly, zoning and easements, assembled into one site boundary.",
    dataSources: ["County parcels", "Planetary Computer STAC", "Committed GeoJSON"],
    sections: [
      {
        heading: "Boundary is a union, not a guess",
        body: "A site's footprint is built as the literal union of the deeds and parcels assembled for it — never hand-drawn from a satellite image. The output is a candidate set, not a prediction.",
      },
      {
        heading: "Zoning is read at time of filing",
        body: "The zoning designation shown is the one in effect at the time of the relevant filing, not the current designation, since rezoning often follows the purchase.",
      },
      {
        heading: "Imagery confirms, it doesn't define",
        body: "Aerial imagery is used only to confirm grading and construction progress against the filed boundary, shown verbatim — never to define the boundary itself.",
      },
    ],
    example: {
      before: "A site boundary built from the union of recorded deeds is",
      first: "verified",
      mid: "; adjacent acreage under option, read from neighboring recorder filings, is",
      second: "inference",
      after: ".",
    },
    guardrail: "The boundary shown is only ever what the deeds support.",
    skill: "gis-and-siting-analysis",
  },
  {
    slug: "toxics-air",
    label: "Toxics & air permits",
    method: "Emissions and discharge permits, read against modeled exposure.",
    dataSources: ["Ohio EPA eSuite", "EPA ECHO", "EPA RSEI"],
    sections: [
      {
        heading: "Permits are the ceiling",
        body: "A permit's allowable emissions is a legal ceiling, not a measurement of what a facility actually emits — the record always distinguishes the two.",
      },
      {
        heading: "Scores lag reality",
        body: "RSEI and discharge-monitoring data is typically months old at publication; the record dates every figure so a reader knows how current it is.",
      },
      {
        heading: "Exposure is modeled, and said to be",
        body: "Any dispersion or exposure estimate is clearly labeled as a model, built from public permit limits, not a direct health finding.",
      },
    ],
    example: {
      before: "A permitted emissions ceiling read from the air permit is",
      first: "verified",
      mid: "; the modeled ground-level increase from a standard dispersion run is",
      second: "inference",
      after: ".",
    },
    guardrail: "A modeled exposure estimate is never published as a health finding.",
    skill: "public-records-and-legal-strategy",
  },
  {
    slug: "civic-records",
    label: "Civic records",
    method: "Meeting minutes, board votes and variances, read into the local record.",
    dataSources: ["CivicPlus Agenda Center", "Municipal platform scrapers"],
    sections: [
      {
        heading: "Minutes over memory",
        body: "What a board voted is read from the recorded minutes, not from meeting attendees' recollection or press summary. The download manifest — sha256, bytes, source URL — is the chain of custody.",
      },
      {
        heading: "A variance is a fact, not an opinion",
        body: "Zoning variances and their conditions are logged verbatim; the record does not characterize whether a condition was later honored without a follow-up filing to check it against.",
      },
      {
        heading: "Public comment is preserved",
        body: "Where minutes record public comment, it is kept in the record as testimony, tagged reference — not folded into the board's own findings.",
      },
    ],
    example: {
      before: "A board's recorded vote read from the minutes is",
      first: "verified",
      mid: "; whether a stated jobs commitment is later met stays",
      second: "open",
      after: " until a follow-up filing checks it.",
    },
    guardrail: "A meeting record shows what was said and voted — never what should have happened.",
    skill: "public-records-and-legal-strategy",
  },
  {
    slug: "entity-timeline",
    label: "Entity graph & timeline",
    method: "Shells, subsidiaries and filings, linked into one entity graph over time.",
    dataSources: ["Recorder instruments", "Secretary of State", "GLEIF LEI"],
    sections: [
      {
        heading: "Every link needs a filing",
        body: "An edge between two entities in the graph — a shared registered agent, a subsidiary relationship, a signature — exists only because a specific filing shows it.",
      },
      {
        heading: "Time is part of the record",
        body: "Entities are dated: when they were formed, when they acquired a parcel, when they dissolved or were renamed. The timeline is the graph read in order.",
      },
      {
        heading: "Coincidence is not correlation",
        body: "Two shells sharing a mailing address are flagged as a lead worth checking, not asserted as a single controlling entity, until a filing connects them.",
      },
    ],
    example: {
      before: "A holding LLC's formation read from the Secretary of State filing is",
      first: "verified",
      mid: "; its link to the eventual operator, absent a naming instrument, stays",
      second: "inference",
      after: ".",
    },
    guardrail: "A shared address is a lead. A shared filing is a link.",
    skill: "entity-and-document-deconstruction",
  },
  {
    slug: "places",
    label: "Places",
    method: "Every site located inside its watershed, basin and jurisdiction.",
    dataSources: ["County parcels", "USGS HUC", "Curated POI store"],
    sections: [
      {
        heading: "Basin before address",
        body: "A site is first placed inside its hydrologic unit and basin — the water and grid story reads at that scale before it reads at the parcel scale.",
      },
      {
        heading: "Jurisdiction is layered",
        body: "Township, county, and state jurisdiction are each recorded separately, since permitting and taxation often split across all three for one site.",
      },
      {
        heading: "One site, many boundaries",
        body: "A site's page shows its parcel, its township, its watershed, and its utility territory as four distinct boundaries — never merged into one shape. The parcel number is the identity anchor.",
      },
    ],
    example: {
      before: "A watershed read from USGS HUC boundaries is",
      first: "verified",
      mid: "; a utility service radius, modeled from territory maps, is",
      second: "inference",
      after: ".",
    },
    guardrail: "A basin boundary and a jurisdiction boundary are never drawn as if they were the same line.",
    skill: "gis-and-siting-analysis",
  },
  {
    slug: "research-agent",
    label: "Research agent",
    method: "The retrieval and citation loop that keeps every figure traceable.",
    dataSources: ["Extracted corpus", "In-process MCP tools"],
    sections: [
      {
        heading: "Retrieval is scoped",
        body: "The agent retrieves only from the ingested corpus for a given site or domain — it does not draw figures from general knowledge or unlogged web search, and off the reference build it returns an honest “not yet available”.",
      },
      {
        heading: "Every claim carries its source",
        body: "A finding is not published until the agent attaches the specific page, filing, or feed it came from — the citation is part of the finding, not a footnote.",
      },
      {
        heading: "Review sits before publish",
        body: "A human reviewer checks the agent's structured read against the source before a finding moves from draft to published.",
      },
    ],
    example: {
      before: "The agent's read of a parcel deed, checked against the recorder image, is",
      first: "verified",
      mid: "; its estimate of the buyer's end use stays",
      second: "inference",
      after: " until a permit confirms it.",
    },
    guardrail: "An unreviewed agent finding is a draft, never a record.",
    skill: "evidentiary-discipline",
  },
  {
    slug: "platform-footprint",
    label: "Platform footprint",
    method: "The platform's own compute, power and water draw, published as a report.",
    dataSources: ["AWS Cost Explorer", "Anthropic Admin", "EPA eGRID"],
    sections: [
      {
        heading: "We audit ourselves the same way",
        body: "Watermark's own hosting, storage, and inference costs are read from billing exports and published with the same evidence tags used for every other domain — modeled, not metered.",
      },
      {
        heading: "Static pages cost less to serve",
        body: "Because most pages are static documents rather than a live dashboard, the platform's own compute footprint is a small fraction of a comparable data-driven app.",
      },
      {
        heading: "The report updates, it doesn't reset",
        body: "Each publication cycle appends to the running report rather than replacing it, so the platform's footprint can be read as a trend, not a snapshot.",
      },
    ],
    example: {
      before: "A hosting draw read from the cloud billing export is",
      first: "reference",
      mid: "; the associated water footprint, modeled from the provider's published PUE, is",
      second: "inference",
      after: ".",
    },
    guardrail:
      "The platform reports its own footprint with the same discipline it asks of every site it covers.",
  },
];

/** Lookup by slug — for `getStaticPaths()` and the sub-page route. */
export function domainBySlug(slug: string): Domain | undefined {
  return DOMAINS.find((d) => d.slug === slug);
}
