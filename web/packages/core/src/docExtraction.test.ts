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

  // 52 -> 68 at contract 2.1.0 (#1993). The classifier recognized 137 of 263 committed
  // extractions and missed 126; eight new genres publish 32 of them, and Lima holds most.
  // 3,251 -> 3,254 (#2048): three H.B. 646 witness submissions added to
  // `legal/select-committee-2026/witnesses/`. They arrived inside an ADAMS COUNTY records
  // production but land in the LIMA bundle, and correctly so — `legal/` is network-global,
  // while the other 48 files of that production stay peer-scoped under `west-union/` and
  // `usace/west-union/` and are subtracted from the reference build's corpus scope.
  // 3,254 -> 3,348 (#2072 follow-on): 93 `oepa/lima/edoc-*.pdf` — the enforcement, inspection and
  // permit-action tranche of the City of Lima WWTP's NPDES record on permit 2PE00000 — plus
  // `plans/4091285.pdf`. The portal pull resolved 261 documents and all were fetched, but the
  // repository had exceeded its Git-LFS budget, so 168 (1.35 GB of routine reports, monitoring and
  // application packages) were deliberately NOT committed; every deferred docid is recorded in
  // `data/research/oepa-portal-2pe00000-2026-08-22/manifest.yaml` and is re-fetchable. The comment
  // here said 3,516 for one release — the count as if all 261 had landed — while the assertion
  // below said 3,348. The assertion was right.
  // 68 -> 69 (#2075): `oepa/lima/edoc-412983.order.yaml`, the 2015 federal consent decree. The
  // first of the 93 to be read, and the first `order`-genre extraction Lima has.
  // 69 -> 85 (#2075 follow-on): the enforcement tranche — the 1994 DFFO, the 2005 U.S. EPA
  // administrative order, the 2016 NOV/ROV/incident-report burst, two City letters, the 2026 NOV,
  // and one misfiled Mansfield letter. Sixteen documents, all `order`.
  // 85 -> 115 (#2077): the 30 Ohio EPA inspection letters, under the `inspection` genre added for
  // them. They are 30 CAPTURES of 18 distinct inspections — the portal serves most of this plant's
  // inspections twice, once with a text layer and once as a scan — so the extracted COUNT is
  // captures, not inspections, and the twelve twin pairs are clustered in document-versions.yaml.
  it("extracts 115 of 3,348 documents — 3.4% of the corpus", () => {
    const entries = documents.flatMap((c) => c.entries);
    expect(entries.length).toBe(3348);
    expect(countExtracted(entries, index)).toBe(115);
  });

  it("is near-complete on the small instrument collections, and thin across the big holdings", () => {
    const counts = Object.fromEntries(
      documents.map((c) => [c.slug, [countExtracted(c.entries, index), c.entries.length]]),
    );
    // The instrument collections — small, and read.
    // permits +2 (the two USACE wetland determination forms), recorder +1 (the R.C. 1311.04
    // Notice of Commencement), plans +1 (the SWP3, re-keyed `record:` -> `plan:`) — all #1993.
    expect(counts.permits).toEqual([28, 35]);
    expect(counts.recorder).toEqual([7, 7]);
    // plans 4 -> 5 (#2072 follow-on): `4091285.pdf`, the NOI completing the `2GC08747` set.
    expect(counts.plans).toEqual([2, 5]);
    // ⚠️ `oepa` MOVED CATEGORY and is asserted below with the holdings instead. It was [11, 18] —
    // small and mostly read, which is what "instrument collection" meant here. The Lima WWTP pull
    // took it to [11, 111]: the same eleven extractions against six times the documents. The
    // denominator changed what the collection IS, so leaving it in this group would have kept the
    // assertion passing while its sentence stopped being true.
    // The big holdings — held, and essentially unread. `legal` + `commissioners` were 84% of the
    // catalog against the old 3,254 denominator; at 3,348 the same 2,731 entries are 81.6%, and
    // `oepa` joins them below rather than the instruments above. `legal`
    // rose 8 -> 15 at #1993 (the CRA agreement, the NDA, the treatment agreement, the school-
    // district notice letters, both statewide bills). Denominator 1,733 -> 1,736 at #2048: the
    // three H.B. 646 witness submissions, which are held and unread like the rest of `legal`.
    expect(counts.legal).toEqual([15, 1736]);
    expect(counts.commissioners).toEqual([0, 995]);
    // `oepa` now belongs here: held, and read in good part. 58 of 111 is 52.3% — well above
    // `legal`'s 0.9% and `commissioners`' zero, and well below the instrument collections it used
    // to sit with. The gap is the ingestion backlog this pull created, and it should RISE as
    // extraction proceeds — 11 -> 12 at #2075 (the consent decree), 12 -> 28 at its follow-on
    // (the enforcement tranche, 1994-2026), 28 -> 58 at #2077 (the 30 inspections). The remaining
    // 46 are 36 permit actions, 9 paragraph-33 progress reports (no genre fits either yet), and
    // one byte-identical duplicate that must never be extracted.
    // ⚠️ The remaining 92 do NOT map 22-to-`order` as this comment once said. The portal's
    // "Judicial Order" doc type is a FILING DRAWER, not a genre: of its 12 rows exactly ONE is an
    // order (the decree), NINE are paragraph-33 semiannual progress reports filed under it, and TWO
    // are City of Lima letters. A progress report reports AGAINST obligations rather than imposing
    // them, so `--kind order` would have produced eleven wrong artifacts and ten near-duplicate
    // "decrees". Read a document before assuming its doc type is its genre.
    expect(counts.oepa).toEqual([58, 111]);
  });

  it("counts distinct documents, not records — 3 records name no source file", () => {
    // 56 -> 57 at contract 1.53.0 (#1438). The new `local-legislation` genre claims a `resolution:`
    // payload block, and Lima's corpus already held one that nothing had ever claimed: Allen County
    // Resolution #494-25, the Commissioners' own authorization of the CRA school-district notice to
    // Elida and Apollo Career Center. It was a real, cited, recorder-stamped extraction that the
    // records taxonomy had no bucket for — the same failure mode #1724 fixed for Urbana, found here
    // by a genre added for another site entirely.
    // 57 -> 73 at contract 2.1.0 (#1993), eight new genres across one classifier change.
    // 73 -> 74 (#2075): the Lima consent decree, which publishes into the `enforcement` group.
    // 74 -> 90 (#2075 follow-on): the sixteen-document enforcement tranche, same group.
    // 90 -> 120 (#2077): the 30 inspections, publishing into the NEW `inspections` group rather
    // than `enforcement` — an inspection imposes nothing, and contract 2.3.0 gives it its own.
    expect(records.length).toBe(120);
    // 5 -> 3, and this is the deliberate change the note below predicted. `_source_ref` now
    // resolves three further committed provenance shapes — `provenance.source_path` /
    // `provenance.sources`, the connector read's `meta.sources` (a dict of NAMED lists, so every
    // list is scanned and not just `primary`), and a top-level `sources:` list of instrument
    // blocks. Before #1993, 28 of the 32 records it publishes would have carried no join at all.
    // What remains is genuinely unjoinable: the two OPC artifacts and one FEMA obligation, none of
    // which names a single source document.
    expect(records.filter((r) => !r.source_doc_rel).length).toBe(3);
    // The joinable side of the same 73 -> 74 -> 90: every one of these names its source document,
    // so the index gains an entry each rather than joining the three that name none.
    expect(index.size).toBe(115);
  });
});
