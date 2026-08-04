import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { HypothesisAssessmentItem, HypothesisItem } from "./feeds";

// The hypothesis-node cross-linking machinery (#1570): the network-global hypothesis matrix,
// surfaced as wiki nodes cross-linked to the concepts/entities/open-questions each reading bears
// on. `hypothesisBacklinks` (concept/entity page → the readings that raise it) and
// `hypothesisRelatedNodes` (a reading → the nodes it names) are two directions of one prose match:
// a node name matched as a whole phrase against the hypothesis haystack (its reading + its cells'
// fields and citation notes, where the real operators and nexuses are actually named). Tested
// against a tmp bundle so the matching, the cell-fed haystack, and the gating are all exercised.

const tmpDirs: string[] = [];

function hyp(id: string, number: string, name: string, thesis: string): HypothesisItem {
  return {
    id,
    number,
    name,
    claim: `The ${number} reading.`,
    thesis,
    status: id === "water" ? "reference" : "emerging",
    signals: ["anchor", "strong", "moderate", "watch"],
    groups: [],
    fields: [],
    related_docs: [],
    predicted_evidence: [],
  };
}

function cell(
  site: string,
  hypothesis: string,
  fields: Record<string, string>,
  note?: string,
): HypothesisAssessmentItem {
  return {
    site,
    hypothesis,
    signal: "watch",
    tag: "open",
    fields,
    citations: note
      ? [{ source: `docs/${hypothesis}.md`, source_kind: "reference", note, verified: false }]
      : [],
  };
}

type Feeds = {
  hypotheses?: HypothesisItem[];
  "hypothesis-assessments"?: HypothesisAssessmentItem[];
  concepts?: unknown[];
  entities?: unknown[];
};

function makeBundle(slug: string, feeds: Feeds): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-hyp-"));
  tmpDirs.push(parent);
  const dir = join(parent, slug);
  mkdirSync(dir, { recursive: true });
  const entries = Object.entries(feeds).filter(([, rows]) => rows != null);
  const manifest = {
    bundle_version: "test",
    contract_version: "1.27",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: entries.length,
    row_total: entries.reduce((a, [, rows]) => a + (rows as unknown[]).length, 0),
    feeds: entries.map(([name, rows]) => ({
      name,
      path: `${name}.json`,
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: (rows as unknown[]).length,
    })),
  };
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest));
  for (const [name, rows] of entries) writeFileSync(join(dir, `${name}.json`), JSON.stringify(rows));
  return parent;
}

async function load(dir: string) {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  const bundle = await import("./bundle");
  const wiki = await import("./wiki");
  return { bundle, wiki };
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

const HYPS: HypothesisItem[] = [
  hyp(
    "water",
    "H1",
    "Water & Coercion",
    "Compute lands where it can pull power and water; the Clean Water Act and an NPDES permit are the backstop.",
  ),
  hyp(
    "defense",
    "H2",
    "Defense & Federal Enclave",
    "The build-out tracks arsenals, air bases, and federal research.",
  ),
];

// A defense cell whose only entity mention is in the citation note (never in the abstract thesis) —
// the case that proves cells feed the haystack.
const CELLS: HypothesisAssessmentItem[] = [
  cell(
    "wpafb",
    "defense",
    { nexus: "Wright-Patterson AFB", linkage: "Adjacent" },
    "Wright-Patterson AFB sits at the Mad River terminus, adjacent to the watershed point.",
  ),
  cell("lima", "water", { wwtp: "Allen County Sanitary District" }),
];

const CONCEPTS = [
  {
    slug: "clean-water-act",
    title: "Clean Water Act",
    kind: "concept",
    aliases: ["CWA"],
    tags: [],
    summary: "",
    related: [],
    body: "",
  },
  {
    slug: "npdes-permit",
    title: "NPDES permit",
    kind: "concept",
    aliases: [],
    tags: [],
    summary: "",
    related: [],
    body: "",
  },
  {
    slug: "gravel-pit",
    title: "Gravel pit",
    kind: "concept",
    aliases: [],
    tags: [],
    summary: "",
    related: [],
    body: "",
  },
];

const ENTITIES = [
  {
    key: "wright-patterson-afb",
    display: "Wright-Patterson AFB",
    variants: [],
    kind: "org",
    parcels: [],
    addresses: [],
    sources: [],
  },
  {
    key: "allen-county-sanitary-district",
    display: "Allen County Sanitary District",
    variants: [],
    kind: "org",
    parcels: [],
    addresses: [],
    sources: [],
  },
  {
    key: "acme-gravel",
    display: "Acme Gravel",
    variants: [],
    kind: "org",
    parcels: [],
    addresses: [],
    sources: [],
  },
];

describe("hypothesisBacklinks — a node's readings (#1570)", () => {
  const feeds: Feeds = { hypotheses: HYPS, "hypothesis-assessments": CELLS };

  it("matches a concept named in a reading's thesis prose, as a whole phrase", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", feeds));
    const hits = bundle.runWithSite("lima", () => wiki.hypothesisBacklinks(["Clean Water Act"]));
    expect(hits.map((h) => h.id)).toEqual(["water"]);
    expect(hits[0].number).toBe("H1");
    expect(hits[0].url).toBe("/wiki/hypotheses/water/");
    expect(hits[0].status).toBe("reference");
  });

  it("matches an entity named only in a cell's citation note (cells feed the haystack)", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", feeds));
    const hits = bundle.runWithSite("lima", () => wiki.hypothesisBacklinks(["Wright-Patterson AFB"]));
    expect(hits.map((h) => h.id)).toEqual(["defense"]);
  });

  it("holds the specificity floor — a ≥4-char token matches, a short initialism doesn't", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", feeds));
    // "NPDES" (5 chars) is in the water thesis and qualifies.
    const npdes = bundle.runWithSite("lima", () => wiki.hypothesisBacklinks(["NPDES"]));
    expect(npdes.map((h) => h.id)).toEqual(["water"]);
    // "CWA" (3 chars, single token) is below the floor — no accidental backlink even though the
    // string appears nowhere anyway; the guard is what keeps two-letter noise out.
    const cwa = bundle.runWithSite("lima", () => wiki.hypothesisBacklinks(["CWA"]));
    expect(cwa).toEqual([]);
  });

  it("returns nothing on a build without the hypothesis matrix", async () => {
    const { bundle, wiki } = await load(makeBundle("thin", { concepts: CONCEPTS }));
    const hits = bundle.runWithSite("thin", () => wiki.hypothesisBacklinks(["Clean Water Act"]));
    expect(hits).toEqual([]);
  });
});

describe("hypothesisRelatedNodes — a reading's nodes (#1570)", () => {
  const feeds: Feeds = {
    hypotheses: HYPS,
    "hypothesis-assessments": CELLS,
    concepts: CONCEPTS,
    entities: ENTITIES,
  };

  it("surfaces the concepts and entities a reading names, split by kind", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", feeds));
    const related = bundle.runWithSite("lima", () => wiki.hypothesisRelatedNodes(HYPS[0], CELLS));
    // Water thesis names the two concepts; the water cell's wwtp field names the sanitary district.
    expect(related.concepts.map((t) => t.label).sort()).toEqual(["Clean Water Act", "NPDES permit"]);
    expect(related.entities.map((t) => t.label)).toEqual(["Allen County Sanitary District"]);
    // The decoys (Gravel pit / Acme Gravel) are named nowhere in the reading.
    expect(related.concepts.some((t) => t.label === "Gravel pit")).toBe(false);
    expect(related.entities.some((t) => t.label === "Acme Gravel")).toBe(false);
  });

  it("resolves a reading's cell-named entity to the defense hypothesis", async () => {
    const { bundle, wiki } = await load(makeBundle("lima", feeds));
    const related = bundle.runWithSite("lima", () => wiki.hypothesisRelatedNodes(HYPS[1], CELLS));
    expect(related.entities.map((t) => t.label)).toEqual(["Wright-Patterson AFB"]);
  });

  it("dedupes a node by page URL when several of its names match", async () => {
    // Title + a distinct multi-word alias, both present in the thesis — two index keys, one URL.
    const concepts = [
      {
        slug: "cwa",
        title: "Clean Water Act",
        kind: "concept",
        aliases: ["Federal Water Pollution Control Act"],
        tags: [],
        summary: "",
        related: [],
        body: "",
      },
    ];
    const dupThesis =
      "The Clean Water Act, formally the Federal Water Pollution Control Act, is the backstop.";
    const dupHyp: HypothesisItem[] = [hyp("water", "H1", "Water & Coercion", dupThesis)];
    const { bundle, wiki } = await load(makeBundle("lima", { hypotheses: dupHyp, concepts }));
    const related = bundle.runWithSite("lima", () => wiki.hypothesisRelatedNodes(dupHyp[0], []));
    expect(related.concepts.filter((t) => t.label === "Clean Water Act")).toHaveLength(1);
  });
});

describe("hypothesisHref", () => {
  it("builds the wiki node-page url for a hypothesis id", async () => {
    const { wiki } = await load(makeBundle("lima", { hypotheses: HYPS }));
    expect(wiki.hypothesisHref("water")).toBe("/wiki/hypotheses/water/");
    expect(wiki.hypothesisHref("defense")).toBe("/wiki/hypotheses/defense/");
  });
});
