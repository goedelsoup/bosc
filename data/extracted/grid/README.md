# Grid reliability events (structured reads)

**Collection:** `grid/` · reviewed extractions of
[`data/documents/grid/`](../../documents/grid/)

Structured event records for bulk-power-system reliability events relevant to the
corridor's backup-generation question (Epic #1172). Each record carries provenance
tags (`[verified]` / `[reference]` / `[inference]` / `[open]`) and cites the source
file/page in the mirrored `data/documents/grid/` collection.

## Contents

| File | Event |
|---|---|
| [`pjm-202c-emergency-2026.event.yaml`](pjm-202c-emergency-2026.event.yaml) | PJM hot-weather FPA §202(c) emergency (June–July 2026): DOE Orders 202-26-33 (data-center backup-generation dispatch authority) and 202-26-32 (specified-resources dispatch). |

**Discipline note.** The 2026 record establishes a `[verified]` region-wide
authorization for reliability-triggered data-center backup dispatch, but tracks
the Bistrozzi P0138965 facility's own genset runtime as `[open]` — that facility is
pre-operational and no facility-level runtime record exists. No runtime hours are
fabricated (omission over invention).
