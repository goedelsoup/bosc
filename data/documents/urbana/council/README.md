# urbana/council/ — City of Urbana legislative record (incentive instruments)

The City of Urbana's own legislative record for the **Urbana Technology Hub** data-center
project (site: urbana) — the ordinances, packets, approved minutes, and public notice that
carry the project's **incentive and development instruments**. Ingested for #1354 (sub-issue
of #1263), which asked for the CRA / development agreement and the state incentive record.

At the 2026-06-28 corpus freeze the City's legislative documents were recorded as unreachable
from this build environment (`data/extracted/urbana/datacenter-facility.md` §7). **They are
reachable now** — `www.urbanaohio.com` serves the packets and approved minutes as static PDF
uploads, with no portal, session, or search gate.

## Source

All files retrieved 2026-08-01 from `https://www.urbanaohio.com/uploads/1/2/4/6/124631710/`,
linked from [`/city-council-agenda-packet.html`](https://www.urbanaohio.com/city-council-agenda-packet.html)
and [`/city-council-minutes.html`](https://www.urbanaohio.com/city-council-minutes.html).
As-received names, SHA-256, page counts, and how each date was content-verified are in
[`filename-map.yaml`](filename-map.yaml).

| File | What it carries |
|---|---|
| `2024-11-19_regular_meeting_packet.pdf` | **Ord. 4612-24** + **Exhibit A: the Pre-Annexation Agreement** with Urbana0624C, LLC — the City's only contract with the developer |
| `2024-12-17_approved_city_council_meeting_minutes.pdf` | Ord. 4612-24 passed **5-0**; Ord. 4613-24 (statement of services) and 4614-24 (land use / zoning buffers) passed **5-0** |
| `2025-10-21_approved_city_council_meeting_minutes.pdf` | The R.C. 3735.66 **public hearing** on CRA #2; Ord. 4631-25 second reading |
| `2025-11-04_regular_meeting_packet.pdf` | **Ord. 4631-25** full text + Exhibits A-1 / B / C (the CRA #2 boundary) |
| `2025-11-04_approved_city_council_meeting_minutes.pdf` | Ord. 4631-25 passed **5-2** |
| `data_center_timeline_public_notice_2.26.26.docx.pdf` | The City's own response and timeline — states there are **no CRA agreements** and no contracts other than the pre-annexation agreement |
| `project_overview_-_urbana_technolody_hub.pdf` | The developer disclosure the City posted: 460k sq ft, the 65/55 dB offer, and the tax-revenue figures |

Two are **scanned with no text layer** (the two meeting packets, and the project overview);
they were read by 200 DPI render + OCR. The public-notice PDF is a `.docx` export and has a
native text layer.

## Reviewed extraction

The structured read lives with the Urbana site synthesis, not here:

- [`data/extracted/urbana/incentive-instruments.yaml`](../../../extracted/urbana/incentive-instruments.yaml)
- [`data/extracted/urbana/incentive-instruments.md`](../../../extracted/urbana/incentive-instruments.md)

## Known gaps

- **The executed Pre-Annexation Agreement is not in corpus.** What is ingested is the *draft*
  attached as Exhibit A to Ord. 4612-24, which the ordinance authorizes the Director of
  Administration to enter into "in general accordance with" — the signed, dated counterpart
  (and its Exhibits B & C legal descriptions) has not been produced. `[open]`
- **No CRA Agreement exists to ingest.** R.C. 3735.671 requires a written agreement, Council
  approval, and an ODOD-assigned CRA number before any exemption; none had come before Council
  through the 2026-08-04 agenda. The 65 dB / 55 dB noise limits live only in the developer's
  project overview as terms *offered* for such an agreement.
- **The CRA Application** (the form on file with the Clerk of Council, required by Ord. 4631-25
  §Five before any agreement is negotiated) has not been requested or produced. `[open]`
- **Ohio Secretary of State** business filings for `Urbana0624C, LLC` are unreachable from this
  environment (`businesssearch.ohiosos.gov` → HTTP 403), so the entity's registered agent and
  members are `[open]` — the City's identification of it as "Highland" is the City's own.
- **Ohio Department of Development** is unreachable (`development.ohio.gov` → HTTP 404 for all
  paths), so the ODOD CRA registry and its R.C. 3735.672 annual reports could not be pulled.
- The **2026-02-17 council packet** (the meeting the project overview appears to accompany) and
  the Feb-2026 **site-plan application** are not ingested.
