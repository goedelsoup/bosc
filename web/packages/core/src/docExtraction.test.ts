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
  // 115 -> 129 (#2078): the permit lifecycle — 2PE00000*MD/*ND/*OD/*PD across issued permits, draft
  // public notices and the 2023 fact sheet, plus seven permit ACTIONS and the 2022 renewal
  // application. Existing genres (`npdes`, `epa`); no contract change.
  // 129 -> 138 (#2079): the nine paragraph-33 semiannual progress reports, under the
  // `compliance-report` genre added for them. They are the decree's own measuring instrument.
  // 138 -> 155 (#2080): the tranche completes — 15 correspondence items, a mercury variance
  // application, three engineering drawings/reports, and City Ordinance 155-13 (hand-authored;
  // `resolution` has no extractor). Every Lima WWTP document that CAN be extracted now is.
  // ⚠️ 155 -> 153 (#2085), AND THE TWO ARE NOT UNREAD. Both are still committed, still extracted,
  // still catalogued; they are simply not LIMA's. Ohio EPA's portal indexes by permit, and the
  // 2PE00000 sweep returned two other facilities' records — a Mansfield WWTP letter carrying
  // Lima's permit number in its own reference block (`edoc-3063821`) and a Henry County spill
  // report naming no permit at all (`edoc-3296496`). `data/extracted` mirrors an immutable
  // `data/documents`, so neither byte moved: `data/corpus-attribution.yaml` re-attributes them at
  // the read layer, the letter into Mansfield's corpus scope and the IPIR into no registered
  // site's. This denominator counts what LIMA's bundle publishes, so it falls by two — a
  // correction, not a regression. The percentage is unchanged at 4.6%.
  // 3,348 -> 3,350 and 153 -> 154 (#2088): the two Bistrozzi eDocuments of the BOSC-1A sanitary
  // PTI Rev. 1. ⚠️ THE DENOMINATOR GAINS TWO AND THE NUMERATOR ONLY ONE, and that asymmetry is
  // real rather than a missed extraction — see the `counts.permits` note below. Two further eDocs
  // of the same permit action (`4230061`, `4230062`) are deliberately NOT committed on Git-LFS
  // budget and are recorded by sha256 in the shelf's `filename-map.yaml`.
  // 3,350 -> 3,362 and 154 -> 155 (#2089): the twelve eDocuments of the 2DP00130 / APP285104563
  // indirect-discharge application package (BISTROZZI LLC / "Project BOSC" to the American-Bath
  // POTW), shelved under `oepa/lima/`. ⚠️ THE PORTAL SERVES 23 ROWS AND THE DENOMINATOR MOVES BY
  // TWELVE: the package is the same bundle filed three times and resolves to 16 distinct
  // documents, of which eleven are exact byte-duplicates (7) or text-identical re-submissions
  // whose PDF bytes differ (4). All 23 docids are accounted for by sha256 in
  // `data/documents/oepa/lima/2dp00130-app285104563-manifest.yaml` — complete coverage, not a
  // deferral. ⚠️ THE NUMERATOR MOVES BY ONE, AND THAT IS A DECISION RATHER THAN A GAP: only the
  // application form has a fitting genre (`npdes`). The two sampling reports were read and left
  // UNEXTRACTED because no genre fits an Indirect Discharge Permit Sampling Report and their
  // Group A results table is blank, so a model fitted to them would bake in the wrong shape; the
  // four vendor SDSs, two lab certificates, flow schematic and site-plan exhibit are not agency
  // instruments and have no genre either. Their content lives in the reviewed artifact
  // `data/extracted/oepa/lima/2dp00130-surrogate-characterization.yaml`, which is deliberately
  // shaped so `corpus._classify` DECLINES it — it is a reading, not a record, and must never
  // count here.
  it("extracts 158 of 3,394 documents — 4.7% of the corpus", () => {
    const entries = documents.flatMap((c) => c.entries);
    // 3,362 -> 3,382 (City of Lima PRR, #1536): the twenty committed files of the City's first
    // public-records production, under `legal/prr-mandamus/prr-production-2026-08-{22,24}-lima/`.
    // Twenty-two were DELIVERED; the issued permit and the July 2026 NOV are byte-identical to
    // records already held from Ohio EPA and were not re-committed (pinned by sha256 in the
    // production's custody manifest).
    // The extracted count is UNCHANGED at 155, and honestly so: the join is per-`rel`, and the
    // City-of-Lima production's five extractions are production-level (a bench series, a
    // notification pair, an application, a letter series, an agreement) rather than one artifact
    // per source file. Those twenty documents are read and analysed; they are not per-document
    // joined, so they raise the denominator only.
    // 155 -> 157: two reads of documents the corpus already held. `maumee-tmdl/Appendix-4` (the
    // Maumee TMDL's individual NPDES wasteload allocations, extracted for Lima's own rows — it was
    // already read for FINDLAY's, but Findlay's artifact is outside Lima's scope) and
    // `oepa/lima/edoc-4116228.pdf` (the county Sanitary Engineer's discharge authorization).
    // 157 -> 158 (the §401 backfill): `permits/bosc-401-certifications.epa.yaml`, the read of the
    // two Project BOSC water-quality certifications. ⚠️ ONE extraction against TWELVE new
    // documents — it is a permit-sequence read across both certifications, not one artifact per
    // exhibit, so it joins on the withdrawal email alone and the other eleven raise only the
    // denominator. That is why the corpus moves by 12 and the numerator by 1.
    // ⚠️ The denominator does NOT move for the eleven text sidecars added under
    // `lima/meetings-text/` and `lacrpc/meetings-text/`: a `-text` tree is derived content and
    // `watermark.site.documents` excludes it by `in_sidecar_tree`.
    // 3,382 -> 3,394 (the §401 backfill): twelve documents from the two Project BOSC water-quality
    // certifications that the *BOSC* portal sweep listed in August and nobody had fetched. The
    // sweep named 18 rows; they are 12 distinct byte-streams, and the six duplicate docids are
    // recorded in the shelf's filename-map rather than committed twice.
    expect(entries.length).toBe(3394);
    expect(countExtracted(entries, index)).toBe(158);
  });

  it("is near-complete on the small instrument collections, and thin across the big holdings", () => {
    const counts = Object.fromEntries(
      documents.map((c) => [c.slug, [countExtracted(c.entries, index), c.entries.length]]),
    );
    // The instrument collections — small, and read.
    // permits +2 (the two USACE wetland determination forms), recorder +1 (the R.C. 1311.04
    // Notice of Commencement), plans +1 (the SWP3, re-keyed `record:` -> `plan:`) — all #1993.
    // permits [28, 35] -> [29, 37] (#2088). ⚠️ +2 DOCUMENTS BUT ONLY +1 EXTRACTED, and BOTH are in
    // fact extracted — `4230060.epa.yaml` and `4230068.sanitary.yaml` are committed and catalogued.
    // The join counts what publishes into the RECORDS feed, and the engineering read's payload
    // block `record:` is UNCLAIMED in `_BLOCK_TO_GROUP` (src/watermark/site/records.py), so a
    // `kind=sanitary`/`engineering` artifact reaches no record group. This is PRE-EXISTING and
    // corpus-wide, not introduced here: the three `oepa/lima/edoc-18403xx.engineering.yaml` reads
    // are invisible to this join for the same reason. Giving `record:` a group is a taxonomy
    // decision of the kind the comments in that file take deliberately, and it is NOT made here.
    // permits [29, 37] -> [30, 49]: twelve §401 documents in, one extraction out. The read covers
    // all twelve — the delineation sheet, the Waters-of-the-US table, both ODNR letters and the
    // withdrawal email — but the join is per `source_path`, and that names only `4011312.pdf`, the
    // 2026-02-18 withdrawal. The other eleven are `companion_sources`: read, cited, not joined.
    expect(counts.permits).toEqual([30, 49]);
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
    expect(counts.legal).toEqual([15, 1756]);
    expect(counts.commissioners).toEqual([0, 995]);
    // `oepa` now belongs here: held, and largely READ. 98 of 111 is 88.3% — well above
    // `legal`'s 0.9% and `commissioners`' zero, and well below the instrument collections it used
    // to sit with. The gap is the ingestion backlog this pull created, and it should RISE as
    // extraction proceeds — 11 -> 12 at #2075 (the consent decree), 12 -> 28 at its follow-on
    // (the enforcement tranche, 1994-2026), 28 -> 58 at #2077 (the 30 inspections), 58 -> 72 at
    // #2078 (the permit lifecycle), 72 -> 81 at #2079 (the progress reports), 81 -> 98 at #2080
    // (the tail). THE LIMA WWTP TRANCHE IS COMPLETE: 90 of the 93 committed documents are read and
    // the other 3 are byte-identical duplicates declared in document-versions.yaml that must never
    // be extracted. The 13 that keep this off 111 are the pre-existing oepa/ documents outside this
    // pull, not a remainder of it.
    // 98 -> 96 (#2085): the two misfiled documents leave Lima's scope for the sites they are
    // actually about (Mansfield) or for none at all (Henry County). The denominator stays 111 —
    // the DOCUMENTS are still held here, because the shelf still records what the agency served.
    // That the two numbers now move independently is the whole point: custody is not attribution.
    // ⚠️ The remaining 92 do NOT map 22-to-`order` as this comment once said. The portal's
    // "Judicial Order" doc type is a FILING DRAWER, not a genre: of its 12 rows exactly ONE is an
    // order (the decree), NINE are paragraph-33 semiannual progress reports filed under it, and TWO
    // are City of Lima letters. A progress report reports AGAINST obligations rather than imposing
    // them, so `--kind order` would have produced eleven wrong artifacts and ten near-duplicate
    // "decrees". Read a document before assuming its doc type is its genre.
    // oepa 96 -> 97 extracted of 111 -> 123 (#2089): the 2DP00130 application package. The gap
    // widens on purpose — see the note above the previous test for why eleven of these twelve
    // documents have no extraction and should not.
    // oepa 97 -> 98: `2dp00130-conveyance-and-authorization.yaml` reads THREE of the package's
    // remaining documents — the authorization letter, the flow schematic and the utility site plan
    // — but the join is per `source_path`, so it moves the count by one. The other two are named
    // in the artifact's `sources:` list and are read, not joined; the same asymmetry the City-of-
    // Lima production note describes above. Eleven-of-twelve is now ten-of-twelve unread.
    expect(counts.oepa).toEqual([98, 123]);
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
    // 120 -> 134 (#2078): the permit lifecycle, into the existing `permits-npdes`/`permits-epa`.
    // 134 -> 143 (#2079): the nine progress reports, into the NEW `compliance-reports` group.
    // 143 -> 160 (#2080): the tail — correspondence into `enforcement`, the ordinance into
    // `local-legislation`, the drawings into their own groups. No contract change.
    // 160 -> 158 (#2085): the two Ohio EPA misfilings re-attributed away from Lima. Mansfield's
    // own bundle gains one of them, which is where the record was always supposed to be.
    // 158 -> 159 (#2088): `permits/4230060.epa.yaml`, which publishes into `permits-epa` as an
    // agency ACTION. Its companion `4230068.sanitary.yaml` does NOT appear, because `record:`
    // claims no group — the same gap noted on `counts.permits` above. One document, one record.
    // 159 -> 160 (#2089): `oepa/lima/edoc-4116201.npdes.yaml`, the indirect-discharge
    // application form, which publishes into `permits-npdes`. One record from twelve committed
    // documents, for the reason given above.
    // 160 -> 163: the TMDL allocation record, the 2DP00130 conveyance record and the BOSC §401
    // certification record — all three `permits-epa`, all three naming their source document.
    expect(records.length).toBe(163);
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
    // 153 -> 154 (#2088): `4230060.epa.yaml` names its source document and so gains an index
    // entry. `4230068.sanitary.yaml` names one too, but never becomes a record at all (`record:`
    // claims no group), so it cannot reach this index — which is why the join moves by one while
    // the corpus moves by two.
    // 154 -> 155 (#2089): `oepa/lima/edoc-4116201.npdes.yaml` names its source document and so
    // gains an index entry. Here the join and the record move together — unlike #2088, this
    // extraction both becomes a record and names its source. The other eleven committed
    // documents of the package have no extraction at all and so reach neither side.
    // 155 -> 158: all three new records — the TMDL allocation, the 2DP00130 conveyance and the
    // BOSC §401 certifications — name a source document, so the join and the record move together
    // — as at #2089 and unlike #2088.
    expect(index.size).toBe(158);
  });
});
