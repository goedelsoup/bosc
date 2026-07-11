# Grid reliability events (original records)

**Collection:** `grid/` · immutable source evidence

Primary-source records of bulk-power-system reliability events that bear on the
BOSC corridor's backup-generation question — i.e. events that force, or authorize,
"emergency" backup generators (the data-center diesel fleet under OEPA Air PTI
**P0138965**, `data/extracted/permits/4132514.epa.yaml`) into runtime. These give
the air-quality / dispatch modeling (Epic #1172) a real calibration target rather
than a pure hypothetical. Raw bytes are never edited; structured reads live in the
mirrored [`data/extracted/grid/`](../../extracted/grid/).

## Contents

### `pjm-202c-2026/` — PJM hot-weather FPA §202(c) emergency orders (June–July 2026)

Web-captured from **DOE CESER** ([2026 §202(c) orders](https://www.energy.gov/ceser/2026-doe-202c-orders))
and PJM. During the late-June/early-July 2026 PJM heat event, DOE issued two
Federal Power Act §202(c) emergency orders on PJM's application:

| File | Document | Issued |
|---|---|---|
| `doe-order-202-26-33.pdf` | DOE Order 202-26-33 — authorizes PJM to **direct backup generation** at data centers/large loads as last resort before/during an EEA 3 | 2026-06-30 |
| `doe-order-202-26-32.pdf` | DOE Order 202-26-32 — directs PJM to dispatch **specified generating units** | 2026-06-30 |
| `pjm-application-202-26-33.pdf` | PJM's underlying §202(c) request (letter to Secretary Wright) | 2026-06-27 |

Capture provenance (source URLs, SHA-256, byte sizes, content-verified dates) is in
[`pjm-202c-2026/filename-map.yaml`](pjm-202c-2026/filename-map.yaml). Order 202-26-33
is the one directly relevant to the corridor: it is the federal authorization for the
**reliability-triggered dispatch of data-center backup generation**.

**Scope caveat (chain of custody).** These are *region-wide* PJM orders. They do
**not** establish that the Bistrozzi P0138965 facility specifically ran its gensets —
that facility was permitted only 2026-05-28 and is still in construction. The
facility-level dispatch claim is tracked `[open]` in the extracted record, not
`[verified]`. See [`data/extracted/grid/pjm-202c-emergency-2026.event.yaml`](../../extracted/grid/pjm-202c-emergency-2026.event.yaml).

### `aep-lyka-2026/` — AEP Ohio "Lyka Transmission Project" (345kV substation + line, issue #1476)

Web-captured from **AEP Ohio's own project page**
([aeptransmission.com/ohio/Lyka](https://www.aeptransmission.com/ohio/Lyka/)) —
the first primary-utility-project-level grid instrument for the Lima campus (the
existing corpus's power story otherwise runs only through the OEPA air-permit
generator count, `data/extracted/permits/4132514.epa.yaml`). AEP Ohio proposes a
new **Lyka Substation** on a customer-owned parcel between N West St and N Cole
St, Sugar Creek Township, plus **~4 miles of new 345kV transmission line**.

| File | Document | Dated |
|---|---|---|
| `Lyka_ProjectFactsheet_V2.pdf` | Project fact sheet — scope, purpose, schedule (OPSB filing "Early 2027," in-service "Summer 2028") | 2026-04-08 |
| `Lyka_MapPoster2.pdf` | Study-area map — 45 numbered candidate line-route segments, no route finalized | undated (same capture) |

Capture provenance is in
[`aep-lyka-2026/filename-map.yaml`](aep-lyka-2026/filename-map.yaml). Structured
read: [`data/extracted/grid/aep-lyka-transmission-2026.project.yaml`](../../extracted/grid/aep-lyka-transmission-2026.project.yaml).

**Scope caveat (chain of custody).** As of the 2026-07-11 capture, **no OPSB case
number has been filed** — AEP's own schedule puts the regulatory filing at "Early
2027." A distinct, unrelated Ohio History Connection/SHPO consultation (OHPO
project ID `2026ALL68059`, "Lyka Station STATCOM Project," received 2026-04-08)
should not be conflated with the OPSB siting case itself. Neither AEP's project
page nor its fact sheet names a customer ("a commercial customer's facility");
the Google/Bistrozzi attribution in local press is tracked `[inference]`, not
`[verified]` — see the extracted record.
