# van-wert/council/ — City of Van Wert legislative record (Mega Site annexation + zoning)

The City of Van Wert's own legislative record for the **QTS Van Wert Mega Site** — the three
emergency ordinances passed 2026-05-11 that annexed and rezoned the campus, the statutory public
hearing of 2026-05-04 they rest on, and the 2026-04-27 meeting that ordered them. Ingested for
#1401 (sub-issue of #1267), which asked for the primary-instrument set behind a register that
until now cited press coverage.

Before this, the Van Wert corpus held the *water* instruments (`oepa/van-wert/`, #1406) and the
*land* geometry (`reference/van-wert/parcel-assemblage.geojson`, #1403) but no City legislation.
The campus's legal existence — the annexation, the zoning classification, and the code amendment
that made a data center a permitted use in Van Wert at all — was carried entirely on newspaper
citations.

## Source

All files retrieved 2026-08-03 from `https://vanwert.org/wp-content/uploads/`, a plain WordPress
upload tree behind [`/meeting-minutes/`](https://vanwert.org/meeting-minutes/) and
[`/ordinances/`](https://vanwert.org/ordinances/). No portal, session, or search gate.

**The `/ordinances/` page is a rolling window, not an archive** — on 2026-08-03 it listed only
eight June/July 2026 items and nothing from May. The May ordinances were found through the site's
open WordPress REST media index (`/wp-json/wp/v2/media?search=26-05&per_page=100`), which
enumerates the whole upload archive with dates, titles and URLs and needs no auth. Use that route
for any Van Wert legislation older than the current window.

As-received names, SHA-256, page counts, upload timestamps and how each date was content-verified
are in [`filename-map.yaml`](filename-map.yaml).

| File | What it carries |
|---|---|
| `4.27.26.pdf` | The motion that **ordered** the three ordinances — as a *Type 2* annexation, with **Roberts abstaining**; Safety-Service Director Fleming on the record that the City **could not** supply fill water |
| `5.4.26-Public-Hearing-1.pdf` | The certified public-hearing record: the **four petition parcel numbers**, AEP Ohio's testimony, the City's own **660,000-gallon** fill disclosure, and 88 pages of written comment |
| `26-05-028-draft-ordinance.pdf` | **Ord. 26-05-028** body — annexation of **901.698 ± ac** from Hoaglin, Pleasant and Ridge Townships, resting on **pre-annexation agreements from 2014 and 2016** |
| `26-05-028.pdf` | Its Exhibits A and B — the metes-and-bounds (Parcel One 776.565 ac + Parcel Two 125.133 ac) and the plat |
| `26-05-029-draft-ordinance.pdf` | **Ord. 26-05-029** body — the Planning Commission → County RPC → Council chain that produced it |
| `26-05-029.pdf` | Its **Exhibit A**: the text that first defined *Data Center* in the Van Wert code, made it a permitted I-2 use, and confined power plants and substations to I-2 |
| `26-05-030-draft-ordinance.pdf` | **Ord. 26-05-030** body — the §150.12(C) conditional zoning petition, filed 2026-03-09 |
| `26-05-030.pdf` | Its Exhibits A/B/C, including **Exhibit C — the entire set of conditions**: a landscape mound, and nothing else |
| `5.11.26.pdf` | The **passage record** — all three suspended the rules and passed on first and final reading as emergencies, with **no numeric tally recorded** |
| `5.27.26.pdf` | *(#1407)* The AEP franchise term **cut from 50 years to 10**, and the Safety-Service Director's statement that the Haviland power-line upgrade **"was not related to the Data Center"** |
| `6.8.26.pdf` | *(#1407)* The **Ohio Power franchise passed** (an extension of a **1975** ordinance), and the motion that ordered a private-well ordinance because it was unclear whether **industrial areas** were covered |
| `26-06-034-DRAFT.pdf` | *(#1407)* **Ord. 26-06-034** — new §150.41 "Private Wells". Its Exhibit A makes new wells a **conditional** use in every zoning class; it does **not** prohibit them, and contains no grandfather clause or geothermal exception |
| `7.13.26.pdf` | *(#1407)* **The incentive statement** — VWAED's Executive Director "is concluding incentives and development agreements for the data center and hopes to have those done by the next council meeting" |

## Custody caveats

0. **The minutes are signed; the ordinances are not.** The approval page of each set of minutes
   carries wet-ink Clerk and Council-President signatures over a **typed** "Approved on: <date>"
   (verified visually at 300 DPI on `7.13.26.pdf` p. 7 — never read a Van Wert approval date from
   OCR alone; see the `5.11.26.pdf` note in `filename-map.yaml` for why).
1. **No ordinance file here is signed or certified.** All six were uploaded 2026-05-07 17:10 UTC,
   four days before the vote, and each prints an unfilled `Passed this ___ day of ___, 2026`.
   Passage is evidenced by the approved minutes, not by the ordinance PDFs. Certified copies are a
   records request to the Clerk of Council.
2. **Two ordinance variants exist per ordinance and they differ.** The `-draft-ordinance.pdf`
   files carry a *President Pro Tempore / Acting Mayor* signature block; the bare `NNN.pdf` files
   carry the standard *President of Council / Mayor* block and the exhibits. Both were posted the
   same minute. The 2026-05-11 minutes explain the pro-tem block — Mayor Markward had a prior
   excused absence, so Council President Eikenbary acted as Mayor and Hurless as President Pro
   Tempore — but *why the City posted both* is `[open]`.
3. **`26-05-028.pdf` has no ordinance body**, only Exhibits A and B. Its body is the companion
   `-draft-ordinance.pdf`.
4. **The record names two things it does not contain**: the written comments "retained in the
   Clerk's official file" and the hearing's audio/video recording "maintained as part of the
   official record by the Clerk of Council." Both are records requests.

## The second retrieval (2026-08-05, #1407)

Four more documents, same route, covering the council record forward from the Mega Site vote:
2026-05-27, 2026-06-08 and 2026-07-13, plus the one ordinance in that window that touches the
campus's water question. The incentive/water-service search they belong to is
[`data/extracted/van-wert/incentive-water-instruments.yaml`](../../../extracted/van-wert/incentive-water-instruments.yaml).

**The gap in that set is the 2026-06-22 meeting.** The City's own media index carries an
attachment row for it and the file 404s — the row outlived the upload. It is the one council
meeting between the well motion and the incentive report whose minutes could not be read.

Excluded on purpose from that window, with reasons in `filename-map.yaml`: the 2027 tax budget
(`25-06-028` / `26-06-033`), a CSO supplemental appropriation (`26-05-032`), the Butterfly Meadows
solar lease (`26-06-035` — an energy instrument, flagged for the grid line of work), a
tree-commission repeal, door-to-door sales, a handicap parking space, a smoking prohibition, and
the `26-07-039` annexation of 49.682 ac (including an Ohio Power parcel) that the Law Director
explained on the record as a sanitary equalization basin, not the Mega Site.

## What is NOT here

`26-04-026.pdf` (CRA with True North Partners Holdings, LLC) and `26-04-027` (CRA with Cool
Machines Holdings, Inc) were passed the same night as emergencies and are **not** Mega Site
instruments — a $14M building at 205 Bonnewitz Crossing and a separate manufacturer. Checked and
excluded on purpose; see `filename-map.yaml`.

The extraction is [`data/extracted/van-wert/mega-site-instruments.yaml`](../../../extracted/van-wert/mega-site-instruments.yaml)
and its digest [`mega-site-instruments.md`](../../../extracted/van-wert/mega-site-instruments.md).
