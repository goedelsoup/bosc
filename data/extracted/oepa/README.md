# Ohio EPA NPDES permit extractions

Reviewed structured reads (`*.npdes.yaml`) of the Ohio EPA NPDES permit documents
under [`data/documents/oepa/`](../../documents/oepa/README.md). One file per source
PDF, mirroring the source filename.

## Coverage

Three document types — issued **permit**, **fact sheet**, and draft public notice
(`draft-pn`) — across permits `2PH00006` (American II), `2PH00007` (American/Bath),
and `2PK00002` (Shawnee II).

`2PE00000.npdes.yaml` covers the **City of Lima WWTP** renewal permit
(`2PE00000*OD`, application `OH0026069`) — the municipal receiving plant, outfall
`2PE00000001` to the **Ottawa River at River Mile 37.6**, average design flow
**18.5 MGD** (peak 70 MGD). A text-layer read of a digital PDF (no OCR). Its reported
effluent record lives alongside as `lima-wwtp-OH0026069.dmr.yaml` (an EPA ECHO DMR
pull, not a permit extraction — see below).

`2DP00130.npdes.yaml` covers an **indirect discharge** (pretreatment) permit —
BISTROZZI LLC's "Bosc" data center discharging non-contact cooling water to the
American–Bath POTW — so its `receiving_water` is the POTW and `stream_network` is
`null` (no surface-water body).

`lima-wwtp-OH0026069.dmr.yaml` is **not** a permit extraction: it is the reported
effluent record (Discharge Monitoring Reports) for the Lima WWTP pulled from EPA ECHO
(`watermark dmr OH0026069`) — actual flow vs. the 18.5 MGD design, the CSO/bypass
outfall count, and every ECHO-flagged effluent exceedance (2023-01..2026-06). Reported
values are verbatim from the permittee's submissions; regenerable via the command in
its `meta.regenerate`.

## Site sub-collections

Permits belonging to a **non-Lima network site** live in a slug sub-directory —
`troy-piqua/`, `findlay/` — and that path is named in the site's
`SiteProfile.corpus_relpaths`, which both puts the permit in that site's own record
feed and subtracts it from Lima's reference-build scope (#1505). Note that
`watermark extract --write` always lands a document-level extraction in the *first-level*
collection (`_collection_dir` mirrors `rel.parts[0]` only), so moving a site's artifact
into its sub-directory is a reviewed step after extraction, not something the pipeline does.

### `findlay/` — City of Findlay WPCC, permit `2PD00008` (issue 1460)

Three reads of one permit's paper trail, and they are not interchangeable:

| File | Instrument |
|---|---|
| `2PD00008.fs.npdes.yaml` | The **`*UD` renewal fact sheet** (PN 205259, noticed 2024-08-09) — the anchor. River Mile 56.42, Table 12 low flows (annual 7Q10 **0.21 cfs**), the **1.0** acute dilution ratio, the renewed mercury variance, WET reduced to monitoring only, and Table 14's final limits. |
| `2PD00008.npdes.yaml` | The **`*VD` modification package as issued** (effective 2026-02-01) — a composite PDF whose one substantive act is moving the CSO Schedule event 34099 and the LTCP Addendum to 2026-11-01. Carries the full station inventory (1 final outfall, 10 SSOs, 10 CSOs) and the modification's own attached fact sheet. |
| `2PD00008.1abaf306.npdes.yaml` | The **`*VD` draft public notice** (PN 216133, effective date "PROPOSED"). Its filename carries a content-hash infix because Ohio EPA serves it from a different DAM path under the same basename as the issued permit. |

Two things to carry when quoting these. First, the DAM's `permits/doc/` slot serves the
**modified** package, not the 2024 `*UD` renewal it modified, so the `*UD` permit as issued
is not among the committed bytes; its term (effective 2024-11-01, expires 2029-10-31) is
recorded from Ohio EPA's January 2026 variance list instead. Second, each file's `permit:`
block is the pipeline's own six-page read and everything after it is a **reviewed
augmentation** transcribed page-by-page from the same PDF, with the page cited on each block.
Where review superseded an extractor warning, the original is kept as `superseded_warnings`
rather than deleted.

Narrative: [`data/extracted/findlay/discharge-record.md`](../findlay/discharge-record.md).
The TMDL allocation chain that reaches this plant is a separate record,
[`findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml`](../findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml).

## Conventions

Figures (design flow, limits, dates) come from the document image/text, never
inferred. Each file's `meta` block records the source PDF, pages read, and a
confidence note. `null` means the document stated no value — not an estimate.
