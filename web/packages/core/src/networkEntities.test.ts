import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, afterEach, describe, expect, it, vi } from "vitest";
import type { EntityNode, PersonItem, RelationshipEdge } from "./feeds";

// The network union behind the wiki's entity pages (#1906). The finding: `getStaticPaths` in
// `pages/wiki/**` runs outside `runWithSite`, so the whole network-global wiki was minted from the
// reference bundle and a party carried only by a peer had no page anywhere. These drive the union
// and, more to the point, the MERGE RULE — which is the part that can go wrong quietly: an entity
// page that silently drops one site's reading of a party is the same class of bug as #1886.

const tmpDirs: string[] = [];

function node(key: string, over: Partial<EntityNode> = {}): EntityNode {
  return {
    key,
    display: key,
    kind: "corporate",
    classification: "corporate_domestic",
    variants: [],
    signals: [],
    roles: {},
    parcels: [],
    addresses: [],
    sources: [],
    ...over,
  };
}

function edge(over: Partial<RelationshipEdge> & Pick<RelationshipEdge, "src" | "dst">): RelationshipEdge {
  return { rel: "owns", date: "", ref: "", source: "recorder/x.yaml", ...over };
}

function manifest(feeds: Record<string, unknown>, slug: string): object {
  const entries = Object.entries(feeds);
  return {
    site: slug,
    bundle_version: "test",
    contract_version: "2.0.0",
    generated_at: "2026-01-01T00:00:00Z",
    feed_count: entries.length,
    row_total: 0,
    feeds: entries.map(([name]) => ({
      name,
      path: `${name}.json`,
      media_type: "application/json",
      schema: "s",
      kind: "collection",
      count: Array.isArray(feeds[name]) ? (feeds[name] as unknown[]).length : 0,
    })),
  };
}

/** A parent dir holding one bundle per slug under `<parent>/<slug>/`. */
function makeBundles(bySlug: Record<string, Record<string, unknown>>): string {
  const parent = mkdtempSync(join(tmpdir(), "bosc-network-entities-"));
  tmpDirs.push(parent);
  for (const [slug, feeds] of Object.entries(bySlug)) {
    const dir = join(parent, slug);
    mkdirSync(dir, { recursive: true });
    writeFileSync(join(dir, "manifest.json"), JSON.stringify(manifest(feeds, slug)));
    for (const [name, rows] of Object.entries(feeds)) {
      writeFileSync(join(dir, `${name}.json`), JSON.stringify(rows));
    }
  }
  return parent;
}

// The union reader and the bundle module must come from ONE reset boundary so they share a single
// AsyncLocalStorage — the same discipline `wikiScope.test.ts` uses.
async function load(dir: string) {
  process.env.WATERMARK_BUNDLE_DIR = dir;
  vi.resetModules();
  return {
    net: await import("./networkEntities"),
    links: await import("./entityLinks"),
  };
}

afterEach(() => {
  delete process.env.WATERMARK_BUNDLE_DIR;
});
afterAll(() => {
  for (const d of tmpDirs) rmSync(d, { recursive: true, force: true });
});

describe("wikiSites — which builds the wiki unions over", () => {
  it("takes the selectable sites that have a bundle, in registry order", async () => {
    const { net } = await load(
      makeBundles({
        lima: { entities: [] },
        "fort-wayne": { entities: [] },
        // Registered but NOT selectable: it emits no page tree, so nothing can link into it.
        wilmington: { entities: [node("RLR INVESTMENTS")] },
      }),
    );
    expect(net.wikiSites()).toEqual(["lima", "fort-wayne"]);
  });

  it("degrades over a selectable slug with no committed bundle rather than throwing", async () => {
    // A site promoted in the registry before its bundle is exported must not take the wiki down.
    const { net } = await load(makeBundles({ lima: { entities: [node("A")] } }));
    expect(net.wikiSites()).toEqual(["lima"]);
    expect(net.networkEntities().map((e) => e.key)).toEqual(["A"]);
  });
});

describe("networkEntities — the union", () => {
  it("gives a peer-only party a page, which is the whole finding", async () => {
    const { net, links } = await load(
      makeBundles({
        lima: { entities: [node("AMAZON COM SERVICES")] },
        "fort-wayne": {
          entities: [node("DANA LIGHT AXLE PRODUCTS"), node("project-zodiac-campus")],
        },
      }),
    );
    expect(net.networkEntities().map((e) => e.slug)).toEqual([
      "amazon-com-services",
      "dana-light-axle-products",
      "project-zodiac-campus",
    ]);
    // …and the link guard agrees, so a page that names the party can actually link it.
    expect(links.entityHref("project-zodiac-campus")).toBe("/wiki/entities/project-zodiac-campus/");
  });

  it("merges a party on more than one watershed point into ONE page carrying both", async () => {
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("GENERAL DYNAMICS")] },
        "fort-wayne": { entities: [node("GENERAL DYNAMICS")] },
      }),
    );
    const all = net.networkEntities();
    expect(all).toHaveLength(1);
    expect(all[0].sites).toEqual(["lima", "fort-wayne"]);
    expect(all[0].readings.map((r) => r.site)).toEqual(["lima", "fort-wayne"]);
  });

  it("orders precedence by the registry, not by which feed was read first", async () => {
    // The object key order below puts the peer first on purpose: iteration order must not decide
    // whose reading is primary.
    const { net } = await load(
      makeBundles({
        "fort-wayne": { entities: [node("X", { display: "Peer reading" })] },
        lima: { entities: [node("X", { display: "Reference reading" })] },
      }),
    );
    const [x] = net.networkEntities();
    expect(x.sites[0]).toBe("lima");
    expect(x.node.display).toBe("Reference reading");
  });
});

describe("the merge rule", () => {
  it("unions the set-valued fields and drops nothing a site contributed", async () => {
    const { net } = await load(
      makeBundles({
        lima: {
          entities: [
            node("GD", {
              variants: ["GENERAL DYNAMICS CORPORATION"],
              sources: ["data/reference/gleif/lei-records.yaml"],
              parcels: ["P-1"],
              addresses: ["1 A St"],
              signals: ["defense"],
            }),
          ],
        },
        "fort-wayne": {
          entities: [
            node("GD", {
              variants: ["GENERAL DYNAMICS CORPORATION", "GD Corp"],
              sources: ["data/extracted/fort-wayne/x.yaml"],
              parcels: ["P-2"],
              addresses: [],
              signals: ["defense", "federal"],
            }),
          ],
        },
      }),
    );
    const [gd] = net.networkEntities();
    expect(gd.node.variants).toEqual(["GENERAL DYNAMICS CORPORATION", "GD Corp"]);
    expect(gd.node.sources).toEqual([
      "data/reference/gleif/lei-records.yaml",
      "data/extracted/fort-wayne/x.yaml",
    ]);
    expect(gd.node.parcels).toEqual(["P-1", "P-2"]);
    expect(gd.node.signals).toEqual(["defense", "federal"]);
  });

  it("does NOT sum role counts across sites", async () => {
    // The failure this forbids: one network-global reference source (GLEIF, USAspending) is read
    // into every site's graph, so `jsmc_operator: 1` appears once per selectable bundle off ONE
    // document. Summing would report four operator roles where the record asserts one.
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("GDLS", { roles: { jsmc_operator: 1 } })] },
        "fort-wayne": { entities: [node("GDLS", { roles: { jsmc_operator: 1 } })] },
        urbana: { entities: [node("GDLS", { roles: { jsmc_operator: 1 } })] },
      }),
    );
    const [gdls] = net.networkEntities();
    expect(gdls.node.roles).toEqual({ jsmc_operator: 1 });
    expect(gdls.readings.map((r) => r.roleTotal)).toEqual([1, 1, 1]);
  });

  it("takes the first STATED registry identifier — an absence is not a competing value", async () => {
    const { net } = await load(
      makeBundles({
        // The reference bundle has joined the GLEIF/USAspending inventories; the peer has not.
        lima: { entities: [node("A", { uei: null, federal_obligations: null })] },
        "fort-wayne": { entities: [node("A", { uei: "VF58HFRNGEL8", federal_obligations: 42 })] },
      }),
    );
    const [a] = net.networkEntities();
    expect(a.node.uei).toBe("VF58HFRNGEL8");
    expect(a.node.federal_obligations).toBe(42);
    expect(a.disagreements).toEqual([]);
  });

  it("records a real disagreement instead of silently picking one reading", async () => {
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("A", { classification: "corporate_parent" })] },
        "fort-wayne": { entities: [node("A", { classification: "industrial_facility" })] },
      }),
    );
    const [a] = net.networkEntities();
    expect(a.node.classification).toBe("corporate_parent"); // the primary supplies the headline…
    expect(a.disagreements).toEqual([
      {
        field: "classification",
        readings: [
          { site: "lima", value: "corporate_parent" },
          { site: "fort-wayne", value: "industrial_facility" },
        ],
      },
    ]);
  });

  it("refuses to merge two distinct keys that resolve to one route", async () => {
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("GENERAL DYNAMICS")] },
        "fort-wayne": { entities: [node("General, Dynamics")] },
      }),
    );
    expect(() => net.networkEntities()).toThrow(/same wiki route/);
  });
});

describe("networkEdges — the unioned graph", () => {
  it("is one edge when two sites carry the same assertion, tagged with both", async () => {
    const { net } = await load(
      makeBundles({
        lima: { relationships: [edge({ src: "A", dst: "B" })] },
        "fort-wayne": { relationships: [edge({ src: "A", dst: "B" })] },
      }),
    );
    expect(net.networkEdges()).toEqual([
      { edge: edge({ src: "A", dst: "B" }), sites: ["lima", "fort-wayne"] },
    ]);
  });

  it("keeps two edges when the sites read a different source or date", async () => {
    const { net } = await load(
      makeBundles({
        lima: { relationships: [edge({ src: "A", dst: "B", source: "recorder/x.yaml" })] },
        "fort-wayne": { relationships: [edge({ src: "A", dst: "B", source: "oepa/y.yaml" })] },
      }),
    );
    const edges = net.networkEdges();
    expect(edges).toHaveLength(2);
    expect(edges.map((e) => e.sites)).toEqual([["lima"], ["fort-wayne"]]);
  });

  it("partitions a party's edges over the whole network, not one site's slice", async () => {
    const { net } = await load(
      makeBundles({
        lima: { relationships: [edge({ src: "A", dst: "B" })] },
        "fort-wayne": { relationships: [edge({ src: "C", dst: "A" })] },
      }),
    );
    const { outgoing, incoming } = net.networkEdgesFor("A");
    expect(outgoing.map((e) => e.edge.dst)).toEqual(["B"]);
    expect(incoming.map((e) => e.edge.src)).toEqual(["C"]);
  });
});

describe("entityProfiles — a per-site profile keeps its curating site", () => {
  it("links the site whose record curates the person, not the ambient one", async () => {
    const person = (slug: string, entity_key: string): PersonItem => ({
      slug,
      name: slug,
      entity_key,
      aliases: [],
      roles: [],
      affiliations: [],
      expanded: true,
      tags: [],
      sources: [],
      body: "",
    });
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("A")], people: [person("ann", "A")] },
        "fort-wayne": { entities: [node("A")], people: [person("bo", "A")] },
      }),
    );
    expect(net.entityProfiles("A")).toEqual([
      { site: "lima", person: person("ann", "A") },
      { site: "fort-wayne", person: person("bo", "A") },
    ]);
  });
});

describe("entityBacklinks — each rail resolved against the build that publishes its target", () => {
  const question = (id: string, text: string) => ({
    id,
    origin: "lead" as const,
    question: text,
    detail: "",
    source: "data/site/leads.yaml",
  });

  it("deep-links a peer's open thread to that peer's OWN leads board", async () => {
    // The wiki board renders the canonical build's rows plus the network matrix's cells (#1569).
    // A peer's lead is not on it, so pointing there would be a 404 with a good snippet — the
    // failure #1890 refused to ship. The peer's leads board anchors by lead id, so that is the
    // addressable destination.
    const { net } = await load(
      makeBundles({
        lima: {
          entities: [node("PROJECT ZODIAC")],
          "open-questions": [question("LIMA-1", "What does PROJECT ZODIAC intend to build")],
        },
        "fort-wayne": {
          entities: [node("PROJECT ZODIAC")],
          "open-questions": [question("FW-1", "Who is behind PROJECT ZODIAC in Fort Wayne")],
        },
      }),
    );
    const [zodiac] = net.networkEntities();
    const urls = net.entityBacklinks(zodiac).openQuestions;
    expect(urls).toEqual([
      expect.objectContaining({ id: "LIMA-1", site: "lima", url: "/wiki/open-questions/#lima-1" }),
      expect.objectContaining({
        id: "FW-1",
        site: "fort-wayne",
        url: "/network/fort-wayne/leads#FW-1",
      }),
    ]);
  });

  it("reads the hypothesis matrix from the canonical build, which hosts every site's cell", async () => {
    // NOT a per-site union, and the asymmetry is the reason: the reference build carries a cell for
    // every watershed point (`is_reference_site`, the network-global-host role) while a peer
    // carries only its own row. Unioning per site would give a peer-only party a backlink the
    // hypothesis page — which reads the same canonical matrix for its "Entities it bears on" rail —
    // could not return, and would read the thinner haystack besides.
    const hypothesis = {
      id: "surveillance",
      number: "H3",
      name: "Consumer Surveillance",
      claim: "c",
      thesis: "t",
      status: "emerging",
      signals: [],
      groups: [],
      fields: [],
      related_docs: [],
      predicted_evidence: [],
    };
    const cell = (site: string, note: string) => ({
      site,
      hypothesis: "surveillance",
      tag: "open",
      fields: { operator: note },
      citations: [],
    });
    const { net } = await load(
      makeBundles({
        lima: {
          entities: [node("AMAZON COM SERVICES")],
          hypotheses: [hypothesis],
          // The network's matrix: the cell naming the peer's party lives HERE.
          "hypothesis-assessments": [cell("fort-wayne", "DANA LIGHT AXLE PRODUCTS")],
        },
        "fort-wayne": {
          entities: [node("DANA LIGHT AXLE PRODUCTS")],
          hypotheses: [hypothesis],
          "hypothesis-assessments": [],
        },
      }),
    );
    const dana = net.networkEntities().find((e) => e.key === "DANA LIGHT AXLE PRODUCTS");
    expect(net.entityBacklinks(dana!).hypotheses.map((h) => h.id)).toEqual(["surveillance"]);
  });

  it("raises a peer-only party's threads at all — the rail used to read one bundle", async () => {
    const { net } = await load(
      makeBundles({
        lima: { entities: [node("AMAZON COM SERVICES")] },
        "fort-wayne": {
          entities: [node("DANA LIGHT AXLE PRODUCTS")],
          "open-questions": [question("FW-2", "Is DANA LIGHT AXLE PRODUCTS still operating")],
        },
      }),
    );
    const dana = net.networkEntities().find((e) => e.key === "DANA LIGHT AXLE PRODUCTS");
    expect(net.entityBacklinks(dana!).openQuestions.map((q) => q.id)).toEqual(["FW-2"]);
  });
});
