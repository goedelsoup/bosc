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

## Conventions

Figures (design flow, limits, dates) come from the document image/text, never
inferred. Each file's `meta` block records the source PDF, pages read, and a
confidence note. `null` means the document stated no value — not an estimate.
