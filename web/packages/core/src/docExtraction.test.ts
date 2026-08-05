import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  countExtracted,
  extractionIndex,
  extractionMark,
  extractionStatus,
  extractionStatusesIn,
  extractionSummary,
  RECORD_ROUTE_BASE,
} from "./docExtraction";
import type { DocumentCollectionItem, DocumentEntry, RecordItem } from "./feeds";

const HERE = fileURLToPath(new URL(".", import.meta.url));

function limaFeed<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(HERE, `../../../sites/lima/feeds/${name}.json`), "utf-8")) as T;
}

const record = (over: Partial<RecordItem> = {}): RecordItem =>
  ({
    rel: "permits/4132514.epa.yaml",
    group: "permits-epa",
    title: "PTI 4132514",
    source_doc_rel: "permits/4132514.pdf",
    ...over,
  }) as RecordItem;

const entry = (rel: string): DocumentEntry => ({ rel, name: rel.split("/").pop() }) as DocumentEntry;

describe("extractionIndex", () => {
  it("keys records by the document they were read from", () => {
    const index = extractionIndex([record()]);
    expect([...index.keys()]).toEqual(["permits/4132514.pdf"]);
    expect(index.get("permits/4132514.pdf")).toEqual([
      {
        rel: "permits/4132514.epa.yaml",
        group: "permits-epa",
        title: "PTI 4132514",
        href: "/site/records/permits-epa/permits-4132514-epa-yaml/",
      },
    ]);
  });

  it("skips a record with no source document — a connector pull belongs to no file", () => {
    expect(extractionIndex([record({ source_doc_rel: null })]).size).toBe(0);
    expect(extractionIndex([record({ source_doc_rel: undefined })]).size).toBe(0);
  });

  it("collects every record read from the same document, in feed order", () => {
    const index = extractionIndex([
      record({ rel: "aedg/opc.a.yaml", source_doc_rel: "aedg/bundle.pdf" }),
      record({ rel: "aedg/opc.b.yaml", source_doc_rel: "aedg/bundle.pdf" }),
    ]);
    expect(index.get("aedg/bundle.pdf")?.map((r) => r.rel)).toEqual(["aedg/opc.a.yaml", "aedg/opc.b.yaml"]);
  });

  it("mints hrefs under the base the catalog asset trims off", () => {
    const refs = extractionIndex([record()]).get("permits/4132514.pdf") ?? [];
    expect(refs.map((r) => r.href.startsWith(RECORD_ROUTE_BASE))).toEqual([true]);
  });
});

describe("extractionStatus / countExtracted / extractionStatusesIn", () => {
  const index = extractionIndex([record()]);
  const entries = [entry("permits/4132514.pdf"), entry("permits/unread.pdf")];

  it("classifies a document by whether the join names it", () => {
    expect(extractionStatus("permits/4132514.pdf", index)).toBe("extracted");
    expect(extractionStatus("permits/unread.pdf", index)).toBe("catalogued");
  });

  it("counts the extracted half of a listing", () => {
    expect(countExtracted(entries, index)).toBe(1);
    expect(countExtracted([], index)).toBe(0);
  });

  it("offers a facet only where both states are present", () => {
    expect(extractionStatusesIn(entries, index)).toEqual(["extracted", "catalogued"]);
    // `commissioners`: 995 files, none extracted — one option would select everything.
    expect(extractionStatusesIn([entry("commissioners/a.pdf")], index)).toEqual(["catalogued"]);
    expect(extractionStatusesIn([entry("permits/4132514.pdf")], index)).toEqual(["extracted"]);
    expect(extractionStatusesIn([], index)).toEqual([]);
  });
});

describe("extractionMark", () => {
  it("links a single extraction straight at its record", () => {
    const refs = extractionIndex([record()]).get("permits/4132514.pdf");
    expect(extractionMark("permits/4132514.pdf", refs)).toEqual({
      status: "extracted",
      label: "extracted",
      href: "/site/records/permits-epa/permits-4132514-epa-yaml/",
    });
  });

  it("sends a multi-record document to its own page rather than picking one record", () => {
    const refs = extractionIndex([
      record({ rel: "aedg/opc.a.yaml", source_doc_rel: "aedg/bundle.pdf" }),
      record({ rel: "aedg/opc.b.yaml", source_doc_rel: "aedg/bundle.pdf" }),
    ]).get("aedg/bundle.pdf");
    const mark = extractionMark("aedg/bundle.pdf", refs);
    expect(mark.status).toBe("extracted");
    expect(mark.label).toBe("extracted · 2 records");
    expect(mark.href).toMatch(/^\/doc\/[0-9a-z]+\/$/);
  });

  it("has nothing to open for a catalogued-only document", () => {
    expect(extractionMark("commissioners/a.pdf", undefined)).toEqual({
      status: "catalogued",
      label: "not extracted",
      href: null,
    });
    expect(extractionMark("commissioners/a.pdf", []).href).toBeNull();
  });
});

describe("extractionSummary", () => {
  it("reads as a ratio, grouped", () => {
    expect(extractionSummary(26, 35)).toBe("26 of 35 extracted");
    expect(extractionSummary(8, 1732)).toBe("8 of 1,732 extracted");
    expect(extractionSummary(0, 995)).toBe("0 of 995 extracted");
  });
});

// The acceptance assertion (#1898): the counts the landings print are the join, measured on the
// committed bundle. If a re-export moves them, this fails loudly rather than the site quietly
// reporting a stale rate — and the per-collection split IS the finding, so it is pinned per
// collection and not just in total.
describe("the join, against the committed Lima bundle", () => {
  const records = limaFeed<RecordItem[]>("records");
  const documents = limaFeed<DocumentCollectionItem[]>("documents");
  const index = extractionIndex(records);

  it("resolves every source document — no record cites a file outside the catalog", () => {
    const catalogued = new Set(documents.flatMap((c) => c.entries.map((e) => e.rel)));
    const dangling = [...index.keys()].filter((rel) => !catalogued.has(rel));
    expect(dangling).toEqual([]);
  });

  it("extracts 52 of 3,250 documents — 1.6% of the corpus", () => {
    const entries = documents.flatMap((c) => c.entries);
    expect(entries.length).toBe(3250);
    expect(countExtracted(entries, index)).toBe(52);
  });

  it("is near-complete on the instrument collections and absent from the two biggest", () => {
    const counts = Object.fromEntries(
      documents.map((c) => [c.slug, [countExtracted(c.entries, index), c.entries.length]]),
    );
    // The instrument collections — small, and read.
    expect(counts.permits).toEqual([26, 35]);
    expect(counts.oepa).toEqual([11, 18]);
    expect(counts.recorder).toEqual([6, 7]);
    expect(counts.plans).toEqual([1, 4]);
    // The two productions that are 84% of the catalog — held, and essentially unread.
    expect(counts.legal).toEqual([8, 1732]);
    expect(counts.commissioners).toEqual([0, 995]);
  });

  it("counts distinct documents, not records — 5 records name no source file", () => {
    // 56 -> 57 at contract 1.53.0 (#1438). The new `local-legislation` genre claims a `resolution:`
    // payload block, and Lima's corpus already held one that nothing had ever claimed: Allen County
    // Resolution #494-25, the Commissioners' own authorization of the CRA school-district notice to
    // Elida and Apollo Career Center. It was a real, cited, recorder-stamped extraction that the
    // records taxonomy had no bucket for — the same failure mode #1724 fixed for Urbana, found here
    // by a genre added for another site entirely.
    expect(records.length).toBe(57);
    // 4 -> 5 with it, and this one is NOT a connector-sourced record: it carries its source under
    // `provenance.source_path`, an envelope shape `_source_ref` does not resolve (it reads a
    // top-level `source_path` or a `source.file`). So the document join is lost even though the
    // PDF is catalogued. Pre-existing and out of scope here; the count is pinned so a later fix to
    // `_source_ref` shows up as a deliberate change rather than drift.
    expect(records.filter((r) => !r.source_doc_rel).length).toBe(5);
    // Still 52 distinct source documents — the new record adds no join, which is the point above.
    expect(index.size).toBe(52);
  });
});
