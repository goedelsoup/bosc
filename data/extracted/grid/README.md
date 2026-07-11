# Grid reliability events (structured reads)

**Collection:** `grid/` · reviewed extractions of
[`data/documents/grid/`](../../documents/grid/)

Structured event and project records for bulk-power-system reliability events and
utility-siting projects relevant to the corridor's power story (Epic #1172; issue
#1476). Each record carries provenance tags (`[verified]` / `[reference]` /
`[inference]` / `[open]`) and cites the source file/page in the mirrored
`data/documents/grid/` collection.

## Contents

| File | Event / project |
|---|---|
| [`pjm-202c-emergency-2026.event.yaml`](pjm-202c-emergency-2026.event.yaml) | PJM hot-weather FPA §202(c) emergency (June–July 2026): DOE Orders 202-26-33 (data-center backup-generation dispatch authority) and 202-26-32 (specified-resources dispatch). |
| [`aep-lyka-transmission-2026.project.yaml`](aep-lyka-transmission-2026.project.yaml) | AEP Ohio "Lyka Transmission Project": 345kV substation + ~4mi line, Sugar Creek Township — no OPSB case filed yet (planned "Early 2027"); Google/Bistrozzi customer attribution `[inference]` only. |

**Discipline notes.**

- The PJM 2026 record establishes a `[verified]` region-wide authorization for
  reliability-triggered data-center backup dispatch, but tracks the Bistrozzi
  P0138965 facility's own genset runtime as `[open]` — that facility is
  pre-operational and no facility-level runtime record exists. No runtime hours are
  fabricated (omission over invention).
- The Lyka record establishes AEP Ohio's own project scope/schedule as
  `[verified]` (its own fact sheet), but tracks the Google/Bistrozzi customer
  attribution as `[inference]` only — AEP names no customer in any captured
  material; the identification rests on secondary local press. No customer or
  MW/interconnection figure is fabricated.
