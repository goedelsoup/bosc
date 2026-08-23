import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  type CollectionSummary,
  DOCS_PER_PAGE,
  collectionLayout,
  containerOf,
  entriesFor,
  folderFacets,
  folderPathOf,
  pageCount,
  pageSegment,
  pageSlice,
  parsePageSegment,
  summarizeCollections,
} from "./docBrowse";
import type { DocumentCollectionItem, DocumentEntry } from "./feeds";

const HERE = fileURLToPath(new URL(".", import.meta.url));

function limaFeed(): DocumentCollectionItem[] {
  return JSON.parse(
    readFileSync(resolve(HERE, "../../../sites/lima/feeds/documents.json"), "utf-8"),
  ) as DocumentCollectionItem[];
}

const entry = (rel: string, size = 100): DocumentEntry =>
  ({ rel, name: rel.split("/").pop() ?? rel, size_bytes: size }) as DocumentEntry;

describe("containerOf", () => {
  it("is the second path segment", () => {
    expect(containerOf("legal/prr-mandamus/x/y.pdf")).toBe("prr-mandamus");
    expect(containerOf("commissioners/meetings/j.pdf")).toBe("meetings");
  });

  it("is null for a file sitting directly in its collection", () => {
    expect(containerOf("aedg/PRR-01-bundle.ocr.pdf")).toBeNull();
  });
});

describe("folderPathOf", () => {
  it("is the trail below the container, without the filename", () => {
    expect(folderPathOf("legal/prr-mandamus/9/SH & AB/Phase 1/cap.bmp")).toEqual(["9", "SH & AB", "Phase 1"]);
  });

  it("is empty for a file directly in its container or collection", () => {
    expect(folderPathOf("legal/prr-mandamus/notice.pdf")).toEqual([]);
    expect(folderPathOf("aedg/bundle.pdf")).toEqual([]);
  });
});

describe("pagination", () => {
  it("leaves page 1 as the bare landing", () => {
    expect(pageSegment(1)).toBeNull();
    expect(pageSegment(2)).toBe("page-2");
  });

  it("round-trips", () => {
    expect(parsePageSegment("page-7")).toBe(7);
    expect(parsePageSegment(pageSegment(42) ?? "")).toBe(42);
  });

  it("never reads a bare number as a page — the corpus has containers named 9, 11, 14, 15", () => {
    for (const segment of ["9", "11", "14", "15", "2"]) {
      expect(parsePageSegment(segment)).toBeNull();
    }
  });

  it("rejects page-1 and page-0, so a landing has exactly one address", () => {
    expect(parsePageSegment("page-1")).toBeNull();
    expect(parsePageSegment("page-0")).toBeNull();
  });

  it("gives an empty container a single page, not zero", () => {
    expect(pageCount(0)).toBe(1);
  });

  it("slices 1-based", () => {
    const items = [1, 2, 3, 4, 5];
    expect(pageSlice(items, 1, 2)).toEqual([1, 2]);
    expect(pageSlice(items, 3, 2)).toEqual([5]);
  });

  it("covers every item exactly once across its pages", () => {
    const items = Array.from({ length: 1619 }, (_, i) => i);
    const pages = pageCount(items.length);
    const seen = Array.from({ length: pages }, (_, i) => pageSlice(items, i + 1)).flat();
    expect(seen).toEqual(items);
  });
});

describe("summarizeCollections — against the committed Lima corpus", () => {
  const summaries = summarizeCollections(limaFeed());
  const bySlug = new Map(summaries.map((s) => [s.slug, s]));

  // 3,251 -> 3,254 (#2048): three H.B. 646 witness submissions added to
  // `legal/select-committee-2026/witnesses/`. They arrived inside an ADAMS COUNTY records
  // production but land in the LIMA bundle, and correctly so — `legal/` is network-global,
  // while the other 48 files of that production stay peer-scoped under `west-union/` and
  // `usace/west-union/` and are subtracted from the reference build's corpus scope.
  // 3,348 -> 3,350 (#2088): the two Bistrozzi eDocuments of the 2026-08-14 BOSC-1A sanitary PTI
  // Rev. 1 — `permits/bistrozzi-permits/4230060.pdf` (the issued DSWPTI-260597) and `4230068.pdf`
  // (its approved ePlan application). `permits/` is one of Lima's own prefixes, so they land here
  // directly. The same permit action served two MORE eDocs — `4230061` (23.95 MB site plan) and
  // `4230062` (14.45 MB sanitary plan & profile) — deliberately NOT committed on Git-LFS budget
  // and recorded by sha256 in `data/documents/permits/bistrozzi-permits/filename-map.yaml`.
  // Committing either moves this number again and SHOULD.
  it("summarizes all 21 collections", () => {
    expect(summaries).toHaveLength(21);
    expect(summaries.reduce((n, s) => n + s.count, 0)).toBe(3350);
  });

  it("finds the one production that is half the catalog", () => {
    const legal = bySlug.get("legal");
    if (!legal) throw new Error("legal collection missing");
    const prr = legal.containers[0];
    expect(prr.slug).toBe("prr-mandamus");
    expect(prr.count).toBe(1619);
    // The reason the container level exists at all: 238 folders, 10 levels below the container.
    expect(prr.folders).toBeGreaterThan(200);
    expect(prr.maxDepth).toBeGreaterThan(5);
  });

  it("orders containers by size so the front door leads with the substance", () => {
    for (const summary of summaries) {
      const counts = summary.containers.map((c) => c.count);
      expect(counts).toEqual([...counts].sort((a, b) => b - a));
    }
  });

  it("reports containers even for a tiny collection — the layout decides whether to route them", () => {
    const aedg = bySlug.get("aedg");
    if (!aedg) throw new Error("aedg collection missing");
    expect(aedg.count).toBe(5);
    expect(aedg.containers.map((c) => c.slug)).toEqual(["data-center-updates"]);
    expect(aedg.looseCount).toBe(1);
  });

  it("accounts for every entry as either loose or in a container", () => {
    for (const summary of summaries) {
      const inContainers = summary.containers.reduce((n, c) => n + c.count, 0);
      expect(inContainers + summary.looseCount).toBe(summary.count);
    }
  });

  it("counts non-routable entries rather than hiding them — a production stays complete", () => {
    expect(summaries.reduce((n, s) => n + s.nonRoutableCount, 0)).toBe(54);
  });

  it("carries the README provenance note the old index never rendered", () => {
    expect(summaries.filter((s) => s.description.length > 0).length).toBeGreaterThan(0);
  });
});

describe("collectionLayout — the container level is earned", () => {
  const summaries = summarizeCollections(limaFeed());
  const bySlug = new Map(summaries.map((s) => [s.slug, s]));

  it("routes containers only for the two collections a flat list can't hold", () => {
    const withContainers = summaries.filter((s) => collectionLayout(s) === "containers");
    expect(withContainers.map((s) => s.slug).sort()).toEqual(["commissioners", "legal"]);
  });

  it("keeps the other 19 collections flat", () => {
    expect(summaries.filter((s) => collectionLayout(s) === "flat")).toHaveLength(19);
  });

  it("lets a flat collection paginate rather than forcing a container hop", () => {
    // perry-township is 221 files in a single `meetings` directory: more than one page, but one
    // container is not navigation, so it stays flat and pages instead.
    const perry = bySlug.get("perry-township");
    if (!perry) throw new Error("perry-township collection missing");
    expect(perry.containers).toHaveLength(1);
    expect(collectionLayout(perry)).toBe("flat");
    expect(pageCount(perry.count)).toBe(2);
  });

  it("never sends a reader through a container hop to reach five files", () => {
    const aedg = bySlug.get("aedg");
    if (!aedg) throw new Error("aedg collection missing");
    expect(collectionLayout(aedg)).toBe("flat");
  });

  it("stays flat when a big collection has only one container — that is not navigation", () => {
    const oneBigContainer = {
      ...(bySlug.get("legal") as CollectionSummary),
      containers: [{ slug: "only", count: 900, bytes: 0, folders: 3, maxDepth: 2 }],
    };
    expect(collectionLayout(oneBigContainer)).toBe("flat");
  });
});

describe("page-weight budget", () => {
  it("splits the largest container so no listing carries more than DOCS_PER_PAGE rows", () => {
    const legal = summarizeCollections(limaFeed()).find((s) => s.slug === "legal");
    if (!legal) throw new Error("legal collection missing");
    expect(DOCS_PER_PAGE).toBe(150);
    expect(pageCount(legal.containers[0].count)).toBe(11);
  });

  it("keeps every listing's own content near 150 KB at ~1.0 KB per row", () => {
    // The chrome on top of this is not ours: every page in the build carries ~219 KB before a
    // row is rendered, 188 KB of which is the topbar site switcher (#1893). See DOCS_PER_PAGE.
    expect(DOCS_PER_PAGE * 1024).toBeLessThan(160 * 1024);
  });

  it("is a fraction of the 3,247 rows the single old index carried at ~2.0 MB", () => {
    expect(DOCS_PER_PAGE).toBeLessThan(3247 / 20);
  });
});

describe("entriesFor", () => {
  const collection: DocumentCollectionItem = {
    slug: "legal",
    title: "Legal",
    description: "",
    entries: [entry("legal/loose.pdf"), entry("legal/prr/a.pdf"), entry("legal/prr/deep/b.pdf")],
  };

  it("selects a container's entries at any depth beneath it", () => {
    expect(entriesFor(collection, "prr").map((e) => e.rel)).toEqual([
      "legal/prr/a.pdf",
      "legal/prr/deep/b.pdf",
    ]);
  });

  it("selects the loose files with a null container", () => {
    expect(entriesFor(collection, null).map((e) => e.rel)).toEqual(["legal/loose.pdf"]);
  });
});

describe("folderFacets", () => {
  it("materializes ancestors so the facet reads as a tree, not a list of leaves", () => {
    const facets = folderFacets([entry("c/box/a/b/deep.pdf")]);
    expect(facets.map((f) => f.path)).toEqual(["a", "a/b"]);
    expect(facets.map((f) => f.count)).toEqual([0, 1]);
    expect(facets.map((f) => f.depth)).toEqual([1, 2]);
  });

  it("ignores files that sit directly in the container", () => {
    expect(folderFacets([entry("c/box/flat.pdf")])).toEqual([]);
  });

  it("counts each folder's own files, leaving descendants to prefix matching", () => {
    const facets = folderFacets([
      entry("c/box/a/one.pdf"),
      entry("c/box/a/two.pdf"),
      entry("c/box/a/b/three.pdf"),
    ]);
    expect(facets).toEqual([
      { path: "a", name: "a", depth: 1, count: 2 },
      { path: "a/b", name: "b", depth: 2, count: 1 },
    ]);
  });

  it("covers the real production's folder tree", () => {
    const legal = limaFeed().find((c) => c.slug === "legal");
    if (!legal) throw new Error("legal collection missing");
    const facets = folderFacets(entriesFor(legal, "prr-mandamus"));
    expect(facets.length).toBeGreaterThan(200);
    // Every facet's parent is present — the invariant that makes indented rendering safe.
    const paths = new Set(facets.map((f) => f.path));
    for (const facet of facets) {
      if (facet.depth === 1) continue;
      expect(paths.has(facet.path.slice(0, facet.path.lastIndexOf("/")))).toBe(true);
    }
  });
});
