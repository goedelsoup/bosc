import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";

// Mirrors bundle.test.ts: askIndex.ts reads through bundle.ts, which memoizes the
// resolved dir + manifest at module scope, so each case points WATERMARK_BUNDLE_DIR at a
// fresh fixture and re-imports with a clean registry.
const tmpDirs: string[] = [];

function feedRef(name: string, path: string, count: number, kind = "collection"): object {
  return { name, path, media_type: "application/json", schema: "s", kind, count };
}

function makeBundle(feeds: object[], files: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), "bosc-ask-"));
  tmpDirs.push(dir);
  writeFileSync(
    join(dir, "manifest.json"),
    JSON.stringify({
      bundle_version: "test",
      contract_version: "1.1",
      generated_at: "2026-01-01T00:00:00Z",
      feed_count: feeds.length,
      row_total: 0,
      feeds,
    }),
  );
  for (const [name, body] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), body);
  }
  return dir;
}

async function loadAskIndex(dir: string): Promise<typeof import("./askIndex")> {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return import("./askIndex");
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

const RECORD = {
  rel: "aedg/roundabouts.summary.opc.yaml",
  group: "opc",
  title: "Roundabouts OPC — summary",
  confidence: "high",
  warnings: [],
  fields: { instrument_no: "12345", roadway_subtotal: "$1,200,000", nested: { skip: 1 } },
  approximate_paths: [],
  citation: {
    source: "data/documents/aedg/PRR-01-bundle.ocr.pdf",
    source_kind: "document",
    page: 318,
    confidence: "high",
    verified: true,
  },
};

const ENTITY = {
  key: "AMAZON COM SERVICES",
  display: "Amazon.com Services LLC",
  kind: "company",
  variants: ["AWS"],
  signals: [],
  roles: { buyer: 2 },
  parcels: [],
  addresses: [],
  sources: ["data/extracted/entities/graph.yaml"],
};

const TIMELINE = {
  date: "2019-03-01",
  category: "legal",
  title: "Confidentiality agreement signed",
  ref: "2019-nda",
  parties: ["City of Lima"],
  detail: "NDA covering the project",
  source: "data/extracted/legal/nda.yaml",
  also_sources: [],
};

describe("buildAskIndex", () => {
  it("emits one citation-keyed, deep-linked unit per record with its figures in text", async () => {
    const dir = makeBundle([feedRef("records", "feeds/records.json", 1)], {
      "feeds/records.json": JSON.stringify([RECORD]),
    });
    const m = await loadAskIndex(dir);
    const units = m.buildAskIndex();

    expect(units).toHaveLength(1);
    const u = units[0];
    expect(u.id).toBe("records:aedg/roundabouts.summary.opc.yaml");
    expect(u.url).toBe("/network/american-sugar-creek-allen-co/site/records/opc/");
    expect(u.source).toBe("data/documents/aedg/PRR-01-bundle.ocr.pdf");
    expect(u.page).toBe(318);
    expect(u.verified).toBe(true);
    // Scalar fields are flattened; nested objects are recursed so their leaf values are indexed.
    expect(u.text).toContain("instrument_no 12345");
    expect(u.text).toContain("roadway_subtotal");
    expect(u.text).toContain("skip 1"); // nested: { skip: 1 } — leaf included (#327)
  });

  it("synthesizes provenance for entities (source paths, not a Citation)", async () => {
    const dir = makeBundle([feedRef("entities", "feeds/entities.json", 1)], {
      "feeds/entities.json": JSON.stringify([ENTITY]),
    });
    const m = await loadAskIndex(dir);
    const [u] = m.buildAskIndex();
    expect(u.id).toBe("entities:AMAZON COM SERVICES");
    expect(u.url).toBe("/wiki/entities/amazon-com-services/");
    expect(u.source).toBe("data/extracted/entities/graph.yaml");
  });

  it("carries the source feed's structured date onto timeline units (#1580)", async () => {
    const dir = makeBundle([feedRef("timeline", "feeds/timeline.json", 1)], {
      "feeds/timeline.json": JSON.stringify([TIMELINE]),
    });
    const m = await loadAskIndex(dir);
    const [u] = m.buildAskIndex();
    expect(u.feed).toBe("timeline");
    expect(u.date).toBe("2019-03-01");
  });

  it("skips feeds absent from the manifest", async () => {
    const dir = makeBundle([], {});
    const m = await loadAskIndex(dir);
    expect(m.buildAskIndex()).toEqual([]);
  });

  // A timeline `ref` is a cross-doc dedup key by design — every event about one instrument
  // shares it — so two dated events under one permit collided on a single unit id. That id is
  // the join key `retrieval.ts` builds a Map from, and a Map keeps the LAST entry, so one event
  // was scored against the other's vector (#1422).
  it("disambiguates repeated unit ids, leaving the first occurrence untouched", async () => {
    const dir = makeBundle([feedRef("timeline", "feeds/timeline.json", 2)], {
      "feeds/timeline.json": JSON.stringify([
        { ...TIMELINE, date: "2024-12-17", ref: "2PD00028*PD", detail: "Public notice issued" },
        { ...TIMELINE, date: "2025-01-16", ref: "2PD00028*PD", detail: "Comment period ends" },
      ]),
    });
    const m = await loadAskIndex(dir);
    const units = m.buildAskIndex();
    expect(units.map((u: { id: string }) => u.id)).toEqual([
      "timeline:2PD00028*PD",
      "timeline:2PD00028*PD#2",
    ]);
    // Distinct ids must still carry distinct text, or the fix is cosmetic.
    expect(units[0].text).not.toBe(units[1].text);
  });
});

// The enrichment facets (#1691) — the ones #1582 refused to expose as filters because the index
// didn't carry them. Each is projected from a value the bundle ALREADY holds, so the tests here
// assert the *projection* (which feed field becomes which facet, and what stays absent); the
// matching semantics they're consumed under are `askFacets.test.ts`'s.
describe("buildAskIndex enrichment facets (#1691)", () => {
  const PERMIT_RECORD = {
    ...RECORD,
    rel: "oepa/2PH00006.npdes.yaml",
    group: "permits-npdes",
    fields: {
      permit_no: "2PH00006*LD",
      npdes_id: "OH0037338",
      agency: "Ohio EPA, Division of Surface Water",
      project_name: "Project Bosc Lvl 2 IWP",
    },
  };
  const FACILITY = {
    key: "project-bosc",
    name: "Project BOSC",
    is_primary: true,
    status: "construction",
    air_permit_relpath: "permits/4132514.epa.yaml",
  };

  it("projects a record's genre, permit ids, agency and project onto the unit", async () => {
    const dir = makeBundle(
      [feedRef("records", "feeds/records.json", 1), feedRef("facility", "feeds/facility.json", 1)],
      {
        "feeds/records.json": JSON.stringify([PERMIT_RECORD]),
        "feeds/facility.json": JSON.stringify([FACILITY]),
      },
    );
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    // `document_type` is the axis `feed` can't express — this unit's feed is "records".
    expect(u.feed).toBe("records");
    expect(u.document_type).toBe("permits-npdes");
    // Both identifiers, not just the first: the record is findable by state permit no AND NPDES id.
    expect(u.permit_numbers).toEqual(["2PH00006*LD", "OH0037338"]);
    // Verbatim — no taxonomy key is invented from the document's own words.
    expect(u.agency).toBe("Ohio EPA, Division of Surface Water");
    // "Project Bosc Lvl 2 IWP" resolves to the disclosed campus by segment prefix.
    expect(u.project).toBe("project-bosc");
  });

  it("attributes a record to the campus that cites it as its air permit, over any stated name", async () => {
    const dir = makeBundle(
      [feedRef("records", "feeds/records.json", 1), feedRef("facility", "feeds/facility.json", 1)],
      {
        "feeds/records.json": JSON.stringify([
          {
            ...RECORD,
            rel: "permits/4132514.epa.yaml",
            group: "permits-epa",
            fields: { project_name: "Bistrozzi LLC Allen County air pollution source" },
          },
        ]),
        "feeds/facility.json": JSON.stringify([FACILITY]),
      },
    );
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    expect(u.project).toBe("project-bosc");
  });

  it("keeps a named project the facility feed doesn't cover, as its own slug", async () => {
    const dir = makeBundle([feedRef("records", "feeds/records.json", 1)], {
      "feeds/records.json": JSON.stringify([
        { ...RECORD, rel: "oepa/dazzler.npdes.yaml", fields: { project_name: "Project Dazzler" } },
      ]),
    });
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    // No facility row to resolve against — but it is a real named project, so it stays findable.
    expect(u.project).toBe("project-dazzler");
  });

  it("omits a facet the feed has nothing to say about, rather than emitting an empty value", async () => {
    const dir = makeBundle([feedRef("records", "feeds/records.json", 1)], {
      "feeds/records.json": JSON.stringify([RECORD]), // fields carry no permit/agency/project
    });
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    expect(u.permit_numbers).toBeUndefined();
    expect(u.agency).toBeUndefined();
    expect(u.project).toBeUndefined();
    expect(u.entities).toBeUndefined();
  });

  it("takes a timeline entry's ref as its permit id and its category as the document type", async () => {
    const dir = makeBundle([feedRef("timeline", "feeds/timeline.json", 1)], {
      "feeds/timeline.json": JSON.stringify([
        { ...TIMELINE, ref: "2PH00006*LD", category: "epa_permit_action" },
      ]),
    });
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    expect(u.permit_numbers).toEqual(["2PH00006*LD"]);
    expect(u.document_type).toBe("epa_permit_action");
  });

  // The entity join is on the extraction PATH an entity was read from, which is the same string a
  // record is keyed by — an exact identifier match, never a name match.
  it("joins entities to the records and timeline entries they were read from", async () => {
    const dir = makeBundle(
      [
        feedRef("records", "feeds/records.json", 1),
        feedRef("timeline", "feeds/timeline.json", 1),
        feedRef("entities", "feeds/entities.json", 1),
      ],
      {
        "feeds/records.json": JSON.stringify([PERMIT_RECORD]),
        "feeds/timeline.json": JSON.stringify([TIMELINE]),
        "feeds/entities.json": JSON.stringify([
          { ...ENTITY, sources: ["oepa/2PH00006.npdes.yaml", "data/extracted/legal/nda.yaml"] },
        ]),
      },
    );
    const units = (await loadAskIndex(dir)).buildAskIndex();
    const byFeed = Object.fromEntries(units.map((u) => [u.feed, u]));
    expect(byFeed.records.entities).toEqual(["AMAZON COM SERVICES"]);
    expect(byFeed.timeline.entities).toEqual(["AMAZON COM SERVICES"]);
    // The party's own node is attributed to itself, so `filters.entity` returns it alongside the
    // filings rather than only the filings.
    expect(byFeed.entities.entities).toEqual(["AMAZON COM SERVICES"]);
  });

  it("resolves a place's party names to graph keys, keeping an unresolvable one as stated", async () => {
    const dir = makeBundle(
      [feedRef("places", "feeds/places.json", 1), feedRef("entities", "feeds/entities.json", 1)],
      {
        "feeds/places.json": JSON.stringify([
          {
            slug: "campus",
            name: "The campus",
            kind: "composite",
            depth: "site",
            parcels: [],
            members: [],
            aliases: [],
            tags: ["datacenter", "project-bosc"],
            relationships: [
              // Display name, not a key — resolved through the node's `display`.
              { role: "owner", entity: "Amazon.com Services LLC" },
              { role: "operator", entity: "Some Unmodeled Partner" },
            ],
            citations: [],
            body: "",
          },
        ]),
        "feeds/entities.json": JSON.stringify([ENTITY]),
      },
    );
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    expect(u.entities).toEqual(["AMAZON COM SERVICES", "Some Unmodeled Partner"]);
    // Only a tag naming a disclosed facility is a project — `datacenter` is vocabulary.
    expect(u.project).toBeUndefined(); // no facility feed in this bundle to resolve against
  });

  it("stamps the site's county from the registry, like `site`", async () => {
    const dir = makeBundle([feedRef("records", "feeds/records.json", 1)], {
      "feeds/records.json": JSON.stringify([RECORD]),
    });
    const [u] = (await loadAskIndex(dir)).buildAskIndex();
    expect(u.site).toBe("lima");
    expect(u.county).toBe("Allen County, OH");
  });
});
