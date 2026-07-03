/**
 * A typed, self-contained fixture for the Story authoring/rendering UI (#1096/#1097) — the port of
 * the design's `stories-shared/atomCatalog.js`. It stands in for the live catalog resolver + the
 * `stories`/`story_refs` tables: one `HydratedAtom` per catalog kind (all 14), plus two sample SDM
 * Story bodies (a reader-owned and a site-owned one, which share the renderer).
 *
 * Used by: the preview reader route (renders a full-fidelity Story with no D1/auth), the render-
 * catalog asset builder (enriches real thin handles it recognizes), and the unit tests. It is
 * **fixture data**, never shipped as a Story — the shapes mirror what a live resolver would return.
 */
import type { StoryDocument } from "./sdm";
import type { HydratedAtom, HydratedCatalog } from "./storyAtoms";

const ATOMS: HydratedAtom[] = [
  {
    id: "rec-deed",
    kind: "record",
    handle: "record:lima:deed-0008300",
    kindLabel: "Record · deed",
    title: "Limited Warranty Deed",
    evidence: "verified",
    record: {
      kind: "Record · deed",
      title: "Limited Warranty Deed",
      recordId: "instr. 202508130008300",
      evidence: "verified",
      fields: [
        { label: "Grantor", value: "Brenneman Family Trusts" },
        { label: "Grantee", value: "Bistrozzi LLC" },
        { label: "Acreage", value: "340.2 ac" },
      ],
      source: { file: "ALLE-2025-0008300.pdf", pages: "p. 1 of 4", collection: "Allen County Recorder" },
    },
  },
  {
    id: "time-clearing",
    kind: "timeline",
    handle: "timeline:lima:site-clearing",
    kindLabel: "Timeline · event",
    title: "Site clearing begins",
    evidence: "verified",
    event: {
      year: "2025",
      date: "2025-03-11",
      kind: "construction",
      title: "Site clearing begins",
      summary: "Clearing starts before the water permit is even public — ref. permit PZ-2024-118.",
      evidence: "verified",
      connect: [{ kind: "record", label: "PZ-2024-118" }],
    },
  },
  {
    id: "ent-bistrozzi",
    kind: "entity",
    handle: "entity:lima:bistrozzi-llc",
    kindLabel: "Entity · shell",
    title: "Bistrozzi LLC",
    evidence: "inference",
    profile: {
      kindLabel: "Entity · shell",
      name: "Bistrozzi LLC",
      variants: ["Bistrozzi Holdings"],
      descriptor:
        "A Delaware-registered LLC that took title to seven parcels six weeks before clearing began.",
      evidence: "inference",
    },
  },
  {
    id: "per-official",
    kind: "person",
    handle: "person:lima:county-recorder",
    kindLabel: "Person · public official",
    title: "Allen County Recorder",
    evidence: "verified",
    profile: {
      kindLabel: "Person · public official",
      name: "Allen County Recorder",
      descriptor: "Custodian of record for the deed filing — the office that stamped the instrument.",
      evidence: "verified",
    },
  },
  {
    id: "place-parcel",
    kind: "place",
    handle: "place:lima:parcel-0100-03-002",
    kindLabel: "Place · parcel",
    title: "Parcel 0100-03-002.000",
    evidence: "verified",
    profile: {
      kindLabel: "Place · parcel",
      name: "Parcel 0100-03-002.000",
      descriptor: "5.0 acres — the only parcel in the seven-parcel transfer to carry a public sale price.",
      evidence: "verified",
    },
  },
  {
    id: "meet-exec",
    kind: "meeting",
    handle: "meeting:lima:exec-session-0527",
    kindLabel: "Meeting · closed session",
    title: "Executive session closed to the public",
    evidence: "open",
    event: {
      year: "2025",
      date: "2025-05-27",
      kind: "governance",
      title: "First executive session closed to the public",
      summary:
        "An R.C. 121.22(G)(8) session seals the earliest discussions — the start of the withholding stack.",
      evidence: "open",
    },
  },
  {
    id: "ex-opc",
    kind: "exhibit",
    handle: "exhibit:lima:opc-p317",
    kindLabel: "Exhibit · scan",
    title: "Opinion of Probable Cost, p. 317",
    evidence: "verified",
    source: {
      file: "PRR-01-bundle.pdf",
      badge: "SCAN",
      pages: "pp. 317–328",
      collection: "Public Records Request 01",
      fields: [
        { label: "Program total", value: "$14,223,081" },
        { label: "Drainage line", value: "$1,068,530 · 7.5%" },
      ],
    },
  },
  {
    id: "con-7q10",
    kind: "concept",
    handle: "concept:lima:7q10",
    kindLabel: "Concept",
    title: "7Q10 low-flow threshold",
    evidence: "verified",
    concept: {
      term: "7Q10",
      descriptor:
        "The regulatory low-flow baseline used to test a discharge or withdrawal against the stream at its driest.",
      evidence: "verified",
    },
  },
  {
    id: "lead-intake",
    kind: "lead",
    handle: "lead:lima:intake-not-named",
    kindLabel: "Lead · open thread",
    title: "Intake of record never named",
    evidence: "open",
    lead: {
      kind: "Signal",
      confidence: "unanswered",
      title: "Intake of record never named",
      detail: "The NPDES file never names the specific withdrawal point behind the 24.3× ratio.",
      action: "Help confirm",
      count: "3 readers watching",
    },
  },
  {
    id: "ds-dilution",
    kind: "dataset",
    handle: "dataset:lima:dilution-runs",
    kindLabel: "Dataset · model output",
    title: "Dilution model, five runs",
    evidence: "inference",
    dataset: {
      label: "Dilution ratio",
      value: "24.3×",
      unit: "peak, of 5 runs",
      evidence: "inference",
      basis: "modeled",
      sub: "5 model runs across a wet-to-dry range",
      bars: [
        { label: "Q1", value: 18.2 },
        { label: "Q2", value: 21.7 },
        { label: "Q3", value: 24.3, highlight: true },
        { label: "Q4", value: 19.9 },
        { label: "Q5", value: 22.4 },
      ],
    },
  },
  {
    id: "tear-air",
    kind: "teardown",
    handle: "teardown:lima:air-permit",
    kindLabel: "Teardown · 5-beat",
    title: "Air Permit-to-Install — full teardown",
    evidence: "verified",
    teardown: {
      title: "Air Permit-to-Install P0138965",
      beats: 5,
      headline: "115 emissions units in 3 matched groups · ~313 MW modeled backup",
    },
  },
  {
    id: "doc-npdes",
    kind: "doc",
    handle: "document:lima:npdes-draft",
    kindLabel: "Document · draft permit",
    title: "NPDES water permit, draft",
    evidence: "open",
    record: {
      kind: "Document · draft permit",
      title: "NPDES water permit, draft",
      recordId: "public comment open",
      evidence: "open",
      fields: [
        { label: "Outfall", value: "001 · cooling" },
        { label: "Thermal limit", value: "draft only" },
      ],
    },
  },
  {
    id: "chap-water",
    kind: "chapter",
    handle: "chapter:network:h1-water-power",
    kindLabel: "Chapter · hypothesis",
    title: "H1 · Water & Power",
    evidence: "verified",
    chapter: {
      n: "H1",
      name: "Water & Power",
      claim: "Where compute meets the watershed.",
      status: "Reference build",
    },
  },
  {
    id: "fig-dilution",
    kind: "figure",
    handle: "figure:lima:dilution-curve",
    kindLabel: "Figure · deck.gl chart",
    title: "Cooling draw ÷ 7Q10, visualized",
    evidence: "inference",
    figure: {
      label: "Cooling draw ÷ design low flow",
      value: "24.3×",
      unit: "at 7Q10",
      sub: "4.85 cfs ÷ 0.2 cfs",
      spark: [12, 15, 14, 18, 21, 19, 24.3],
    },
  },
];

/** A handle that resolved once and no longer does — the dangling placeholder demo. */
export const FIXTURE_DANGLING: HydratedAtom = {
  id: "rec-withdrawn",
  kind: "record",
  handle: "record:lima:withdrawn-filing-0091",
  kindLabel: "Record · filing",
  title: "Withdrawn filing",
  evidence: "open",
  dangling: true,
};

/** The fixture catalog, keyed by handle (what an island resolves each SDM `atom` against). */
export const FIXTURE_CATALOG: HydratedCatalog = Object.fromEntries(ATOMS.map((a) => [a.handle, a]));

/** The ordered fixture atoms — the editor's grab-panel source in preview mode. */
export const FIXTURE_ATOMS: HydratedAtom[] = ATOMS;

// --- SDM builders (fixture prose) -----------------------------------------------------------
const p = (value: string): StoryDocument["blocks"][number] => ({
  type: "paragraph",
  children: [{ type: "text", value }],
});
const h = (level: 2 | 3 | 4, value: string): StoryDocument["blocks"][number] => ({
  type: "heading",
  level,
  children: [{ type: "text", value }],
});
const quote = (value: string): StoryDocument["blocks"][number] => ({
  type: "blockquote",
  children: [{ type: "paragraph", children: [{ type: "text", value }] }],
});
const bullets = (...items: string[]): StoryDocument["blocks"][number] => ({
  type: "list",
  ordered: false,
  items: items.map((value) => [{ type: "paragraph", children: [{ type: "text", value }] }]),
});
const note = (variant: "note" | "info" | "warning", value: string): StoryDocument["blocks"][number] => ({
  type: "callout",
  variant,
  children: [{ type: "paragraph", children: [{ type: "text", value }] }],
});
const cite = (handle: string): StoryDocument["blocks"][number] => {
  const atom = FIXTURE_CATALOG[handle] ?? FIXTURE_DANGLING;
  return { type: "atom", handle, kind: atom.kind, title: atom.title };
};

export interface FixtureStory {
  id: string;
  ownerKind: "site" | "user";
  title: string;
  dek: string;
  author: string;
  updated: string;
  doc: StoryDocument;
}

export const FIXTURE_READER_STORY: FixtureStory = {
  id: "pub-1",
  ownerKind: "user",
  title: "The parcels nobody named",
  dek: "A curated read through the deed, the shell, and the six weeks before clearing.",
  author: "J. Alvarez",
  updated: "3 days ago",
  doc: {
    version: "1.0.0",
    blocks: [
      h(2, "Who actually holds the land"),
      p(
        "Three parcels changed hands inside of a month, all to the same buyer of record — a Delaware entity that didn't exist a year earlier.",
      ),
      cite("record:lima:deed-0008300"),
      p(
        "The seller's name is on file. The buyer's is a shell. Here's who's actually behind it, as far as the record goes.",
      ),
      cite("entity:lima:bistrozzi-llc"),
      note(
        "note",
        "This is a lead, not a verdict — the shell's ultimate owner wasn't confirmed until the 2026 AEDG disclosure, cited below.",
      ),
      quote(
        "“A Delaware shell. Withheld land prices. Backup generators by the hundred.” — the site's own framing of the assembled record.",
      ),
      h(3, "Then it moved fast"),
      p("Six weeks later, clearing starts — before the water permit is even public."),
      cite("timeline:lima:site-clearing"),
      bullets(
        "Deed recorded, 2025-08-13",
        "Site clearing begins, 2025-03-11 (ref. permit)",
        "Water permit still in draft",
      ),
      cite("record:lima:withdrawn-filing-0091"),
      p("One filing in this chain has since been withdrawn — the record still shows where it stood."),
    ],
  },
};

export const FIXTURE_EDITORIAL_STORY: FixtureStory = {
  id: "ed-1",
  ownerKind: "site",
  title: "Reading the record from the water up",
  dek: "The site's own walkthrough of what the watershed lens turns up, in order.",
  author: "The record team",
  updated: "Reviewed monthly",
  doc: {
    version: "1.0.0",
    blocks: [
      h(2, "Start with the thesis"),
      p(
        "The watershed lens holds that hyperscale compute lands where it can pull power and water. Lima is the worked example.",
      ),
      cite("chapter:network:h1-water-power"),
      h(3, "The withdrawal the file never names"),
      p("At the river's design low flow, the modeled draw is 24.3× the whole stream."),
      cite("figure:lima:dilution-curve"),
      note(
        "warning",
        "The intake of record is not named anywhere in the NPDES file. Treat the ratio as inference until it is.",
      ),
      cite("lead:lima:intake-not-named"),
      p("The concept doing the load-bearing work here is the 7Q10 baseline itself."),
      cite("concept:lima:7q10"),
      cite("dataset:lima:dilution-runs"),
      h(3, "Where the paper trail is thickest"),
      cite("exhibit:lima:opc-p317"),
      cite("teardown:lima:air-permit"),
      cite("document:lima:npdes-draft"),
      cite("place:lima:parcel-0100-03-002"),
      cite("person:lima:county-recorder"),
      note(
        "info",
        "This story is site-authored — it shares the exact same renderer as a reader Story. Only the byline differs.",
      ),
      cite("meeting:lima:exec-session-0527"),
    ],
  },
};
