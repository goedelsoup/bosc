# Corpus completeness audit — what source documents are missing

**Audited 2026-06-06.** Scope: every collection under [`data/documents/`](../../documents/) cross-referenced against the corpus's own declared expectations — the PRR production tracker, the minutes manifest, the PRR-01 bundle index, and the provenance citations inside [`data/extracted/`](../).

> Method: (1) **Substantive gaps** read from the county's own item-by-item response in [`bosc-prr-production-2026-06-05.response-index.yaml`](prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml) — i.e. records *requested and not produced*, not inference. (2) **Integrity gaps** computed by script: minutes/agenda filename parsing + pairing over `commissioners/minutes/raw/`, existence-checks of every `*.pdf` cited across `extracted/**`, and the PRR-01 bundle's `derived_files`. Ambiguous date-typo filenames were **not** auto-resolved (the heuristic produced impossible dates); they are listed for human verification. Minutes findings reflect the **2026-04-17 manifest snapshot**, not today.

## Headline

**The archive itself is in good shape; what's "missing" is mostly what the county hasn't produced.** Provenance is clean (94 distinct source PDFs cited across the extractions, 0 genuinely absent). The PRR production binaries are all present. The substantive holes are the records the county **deferred or withheld** — above all the entire **county-wastewater engineering universe (PRR items 5–15)** and the **item-4 cost-benefit analysis** — plus a modest set of corpus-hygiene issues in the minutes series (publication lag + ~12 malformed/misfiled filenames), none of which indicate lost evidence. A separate, newer thread (§2) tracks **watershed/conservation grant docs** worth digging up — the primary instruments behind a $650k Lost Creek (Maumee-headwater) ag-runoff grant whose SWCD summary is now in the corpus. A third thread (**§4**) flags the **OEPA air permit P0138965** — the secondhand-cited keystone behind the disclosed **313 MW** power figure, and the expected source of the **three-hall building footprint** — as not yet ingested.

---

## 1. Substantively missing — records the county has NOT produced

Declared in the county's first production tracker (cover letter 2026-06-05, Clerk of Board Brittany N. Woods). Of the 19-item request, these remain outstanding:

| Item(s) | Category | What's owed | County's stated posture |
|---|---|---|---|
| **5–15** | County wastewater works | BOSC pump-station/forcemain procurement; Shawnee II Phase 2; Shawnee Oaks / Hamlet of Hume sewering; permits **SWPTI-260294** & **DSW-6756**; **1996 CWA consent decree**; **Cridersville WWTP** records | **Produced 2026-06-12 (batch 2)** — BOSC CMAR chain (#469-25→#137-26→#378-26), data-center-flows TO5 (#679-24), Shawnee Oaks (#113-26/#136-26), Hume (#135-26), Shawnee II Phase 2 (#220-24/#937-23). **Outstanding = construction bids/award only** (the CMAR is still at pre-construction). The other named items are **already in-corpus**: permits **DSWPTI-260294** + **DSW-6756** ([`data/extracted/permits/`](../permits/) 4074527/4074529/4074551, approved 2026-04-07, BOSC-1A private sanitary sewer); the **1996 CWA consent decree** ([`regulatory/wastewater-enforcement-history.yaml`](../regulatory/wastewater-enforcement-history.yaml) — Civil Action 3:96 CV 7134, + source PDF); and **Cridersville WWTP** (NPDES **OH0020222**, 2.4 MGD → Little Ottawa, in the EPA ECHO inventory, now linked to the reroute economics in [`sanitary-economics.yaml`](../commissioners/sanitary-economics.yaml)). |
| **4** | Project BOSC | Cost-benefit analysis / projected tax-revenue impact / public-ROI inputs & assumptions | **Withheld** "being reviewed by our legal counsel for compliance with R.C. 149.43 and R.C. 9.66." Not produced. |
| **2** | Project BOSC | County ⇄ DoD / federal-contractor (GDIT, GDLS) comms re the American Twp facility / corridor | "No records"; county narrowed the ask. Deemed fulfilled. |
| **16** | Website | CMS audit trail / edit history for the Sanitary Engineering pages, 2025-01-01→ | "No records… do not manage the county website." **Contested** — WordPress revision history exists behind a 401 gate (see below). |
| **17** | Website | Internal comms re adding/removing BOSC / RFP / Bistrozzi / Shawnee II references on county sites | "No responsive records." |
| **18** | Address | Records indexed to **4110 N. Cole St., Lima** not caught by entity/project name | "No responsive records" (partial). |
| **19** | Engineer of record | County ⇄ **EMH&T** comms | None as to Commissioners; may supplement from Sanitary Eng. |

**The Category-B deferral — once the largest hole — was produced 2026-06-12** (batch 2; item-by-item in [`prr-mandamus/bosc-prr-production-2026-06-12.response-index.yaml`](prr-mandamus/bosc-prr-production-2026-06-12.response-index.yaml)). The production also resolved a corpus discrepancy: resolutions **#113-26 / #135-26 / #136-26** had been mislabeled "forcemain feasibility" — the primary records show #113-26 = Shawnee Oaks **engineering** (Access, $161k), #135-26 = Hamlet of Hume WPCLF ($2.0M), #136-26 = unincorporated Shawnee Twp / Shawnee Oaks WPCLF ($1.6M). These records tie to the OEPA **Shawnee II** permit `2PK00002` in [`data/extracted/oepa/`](../oepa/) and the ECHO discharger inventory in [`data/reference/echo/`](../../reference/echo/). They also yield the **data-center → WWTP keystone** (Task Order #5, #679-24 — a "Data Center Flows Treatment Evaluation" of the campus blowdown stream).

**Item 16 is "missing" by custody disclaimer, not non-existence.** The response index's own rebuttal shows the Sanitary pages' WordPress `modified` dates fall inside the requested window and the `/revisions` endpoint returns **HTTP 401 (gated, not 404)** — the version history exists; the county simply disclaims holding it. Custody sits with the host (AhelioTech / CorpComm-built site) — see [`allen-county-web-vendor-audit.md`](web-vendor-audit/allen-county-web-vendor-audit.md) and [`allen-county-level-sites.md`](web-vendor-audit/allen-county-level-sites.md).

*Universe note:* per the relator's 2026-06-03 narrowing email, any request item not listed was treated as withdrawn — so the "owed" set is bounded by these items. Production is rolling ("every Friday"). **Items 5–15 were produced in batch 2 (2026-06-12)**; **item 4** (cost-benefit, held under §9.66(D)) remains the one to watch.

---

## 2. Watershed / conservation grant docs — to dig up

A captured Allen SWCD project page entered the corpus 2026-06-06 as
[`watershed/osu-lima-ag-runoff.allenswcd.2026-06-06.pdf`](../../documents/watershed/osu-lima-ag-runoff.allenswcd.2026-06-06.pdf)
(extraction: [`watershed/osu-lima-ag-runoff-treatment.capture.yaml`](../watershed/osu-lima-ag-runoff-treatment.capture.yaml)).
It documents a **$650,000** ag-runoff retention/treatment grant (Project
`ALLENSWCD-FDFARM22`) on **Lost Creek HUC12 `041000070305`** — a Maumee headwater
2.7 mi east of I-75 — i.e. baseline nutrient-burden context for the hydrology
axis. The page is a **secondary SWCD summary**.

The project's **Lead PI, Dr. Vinayak S. Shedekar (OSU FABE)**, was identified from
the page; his **CV** ([`shedekar-cv.2025-09-28.pdf`](../../documents/watershed/shedekar-cv.2025-09-28.pdf),
provided 2026-06-06; bibliography at
[`../watershed/shedekar-vinayak.bibliography.md`](../watershed/shedekar-vinayak.bibliography.md))
**resolved the funding source**: Great Lakes Restoration Initiative (GLRI), subaward
through **Ohio EPA**, OSU portion **$327,450**, term **2023–2025** (CV grant #13) —
closing the prior `[open]`. The primary instruments still owed:

| Item | What's owed | Where to get it |
|---|---|---|
| **Grant agreement / award instrument** | The signed **GLRI / Ohio EPA** subaward itself — deliverables, match, reporting (program now known; instrument not in hand) | Ohio EPA GLRI subaward files; Allen SWCD; public-records request |
| **OSU application & conceptual design** | Engineering basis for the BMPs (berm/wetland/forebay/pump-vault; saturated buffer) | OSU FABE (Dr. V. Shedekar); Allen SWCD project file |
| **Load-reduction estimate table** | Referenced on the captured page ("provided in the table below") but **not transcribed** in the capture | Re-capture full page / SWCD project file |
| **OSU monitoring data** | Continuous flow + water-quality (3 sites, ISCO6712 samplers) — quantifies actual nutrient/flow reduction | OSU Overholt Drainage program |

These quantify the **existing** Maumee-headwater load and remediation spend the
corpus reasons against; the funding source is now verified, the rest not yet in
hand. Cross-ref the ECHO Maumee discharger inventory
([`../../reference/echo/`](../../reference/echo/)) and
[`../../../docs/HYDROLOGY.md`](../../../docs/HYDROLOGY.md).

---

## 3. Corpus-integrity gaps (minor)

### Commissioners minutes series — broadly complete
934 files in [`commissioners/minutes/raw/`](../../documents/commissioners/minutes/) spanning 2023–2026: **475 agendas (`A…`) / 453 minutes (`M…`)**, 468 distinct meeting-dates parsed. The 22-file agenda/minutes asymmetry is **mostly not real absence**:

- **Recent publication lag (not a gap):** 12 dates **2026-03-03 → 2026-04-20** have an agenda but no minutes — these are the most recent meetings relative to the 2026-04-17 manifest snapshot; minutes simply weren't posted yet.
- **Partial 2023 backfill (scope, not loss):** an 8-date cluster in **Dec 2023** (agendas, no minutes) sits in the partially-backfilled 2023 range (the corpus is pinned to 2024–2026).
- **Typo'd agendas masquerading as gaps:** several early-2024 "minutes, no agenda" dates *do* have an agenda under a malformed name — e.g. `A20524-Special.pdf` (2024-02-05), `A22124-Special-1.pdf` (2024-02-21), `A22824-Special.pdf` (2024-02-28).

### ~12 malformed / misfiled filenames (break automated indexing)
| Filename | Issue |
|---|---|
| `Govt.-Structure-Org-Chart-1.pdf` | **Not a meeting record** — reference handout misfiled in `minutes/raw/` |
| `Mayors-and-Zoning-Persons.pdf` | **Not a meeting record** — contact list misfiled |
| `Township-Trustees-Fiscal-Officers.pdf` | **Not a meeting record** — contact list misfiled |
| `CANCELLED-MEETING.pdf` | Cancelled-meeting placeholder (no date) |
| `Board-of-Commissioners-General-Session-September-9-2025-Meeting-Minutes.pdf` | Long-form name for the **2025-09-09 minutes** (should be `M090925.pdf`) |
| `ACC-M102423.pdf` | Stray `ACC-` prefix (minutes 2023-10-24) |
| `A0101024.pdf`, `A0404024.pdf`, `M0115226.pdf` | **7-digit date typos — ambiguous**; verify against the source before renaming |
| `A20524-Special.pdf`, `A22124-Special-1.pdf`, `A22824-Special.pdf` | 5-digit dates (leading zero dropped) |

### PRR-01 bundle derived files — not committed (low concern)
The [bundle index](../../documents/aedg/PRR-01-bundle.ocr.pdf.index.yaml) references seven `derived_files` (`Allen_County_PRR_searchable.pdf`, `..._full_text.txt`, `..._exhibit_index.txt`, `Allen_County_Project_Master_Table.md`, `BOSC_Tetra_Tech_OPC.yaml`, `BOSC_OPC_Detailed_Line_Items.yaml`). None are in `data/documents/aedg/` — but they are **regenerable derivatives** of `PRR-01-bundle.ocr.pdf`, which **is** present. Not lost source material.

### Sanitary as-built present but not yet extracted
*Added 2026-06-11 (issue #41).* [`sanitary/indianbrook-ps-asbuilt-2007.pdf`](../../documents/sanitary/indianbrook-ps-asbuilt-2007.pdf) — the 2007 Indian Brook pump-station as-built (4-page scan, **no text layer**) — is **present** in the corpus but **not yet grounded**: `data/extracted/sanitary/` carries no structured extraction, so the 8" forcemain / three-phase upgrade it documents is cited only secondhand (`data/reference/periplus/watch-items.geojson` "2007 as-built"; [`../../../docs/legal/mandamus-analysis.md`](../../../docs/legal/mandamus-analysis.md) §503). The discipline-agnostic `kind=engineering` / `kind=sanitary` extractor (`bosc.pipeline.extract.extract_engineering`) now exists; the structured `.sanitary.yaml` awaits a keyed vision pass (`ANTHROPIC_API_KEY`, tracked in #124). This is the one piece of sanitary as-built evidence that **is** in hand against the Category-B wastewater hole above (§1, items 5–15).

### Provenance — clean
Every `*.pdf` cited across `extracted/**` resolves to a real file under `data/documents/`. (Of 94 distinct cited names, the only 2 "unresolved" are false positives: a Google-Slides export title and a prose fragment, not file references.) The 5 PRR-production binaries named in the response index are all present in [`prr-production-2026-06-05/`](../../documents/legal/prr-mandamus/prr-production-2026-06-05/) — the index's "binaries to be added" note is stale.

---

## 4. Air permit (PTI P0138965) — the keystone power figure, cited secondhand

*Added 2026-06-09 (compute-capacity axis).* The Ohio EPA Air **Permit-to-Install P0138965** (Facility **0302022054**) is the **sole source** of the campus's disclosed electrical scale — **114 emergency generators × 2,750 ekW ≈ 313 MW backup → ~250–300 MW IT** (N+1). That figure anchors both the cooling-water balance ([`../../../docs/HYDROLOGY.md`](../../../docs/HYDROLOGY.md); `bosc.hydrology.cooling`) and the compute / AI-capacity derivation ([`../../../docs/COMPUTE.md`](../../../docs/COMPUTE.md); `bosc.facility`). **Yet the permit itself is not in the corpus** — the 313 MW / 114-genset figure enters only as a *secondhand citation* inside [`../commissioners/bosc-water-balance.analysis.md`](../commissioners/bosc-water-balance.analysis.md) and the [relator data appendix](select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md). No air-PTI PDF exists under [`data/documents/`](../../documents/): the permits folders hold §401 water-quality applications (not the air PTI), and the PRR-01 bundle is minutes + land/deed exhibits.

| What's owed | Why it matters | Where to get it |
|---|---|---|
| **Air PTI P0138965** (full permit + application) | Puts the **313 MW / ~275 MW IT** keystone on a **primary-source** footing — it currently carries a `[verified: document]` tag across the corpus *without the document committed* | Ohio EPA Division of Air Pollution Control (DAPC) public eDocument / eBusiness system, Facility ID **0302022054** |
| **Emission-unit layout / plot plan** | The 114 generators are grouped **by building**; the grouping is expected to show the **data-hall count (≈ three halls)** and a documented **building footprint** — which would re-ground the **footprint method (Method 3)** from "land × assumed coverage" to a real floor area, and let the genset-per-hall split cross-check per-hall power against the 275 MW total | Same permit (emission-unit table + any plot-plan attachment) |
| **Architectural site-plan sheets** (CI Design / WSP) | The committed plan set is a **single** grading & storm sheet (`1A-C-3104`) showing only ancillary **SSS/GPS** buildings on piers — the data-hall footprints sit on architectural sheets not in hand | EMH&T / CI Design plan set; PRR follow-up |

Until ingested, **Method 3 stays the flagged-weak land-area envelope** and the power figure rests on a secondhand citation. *(Lead: the three-hall footprint, noted by the relator from the air permit, is **recorded as a gap 2026-06-09**, not asserted — chain of custody requires it come from the document.)*

---

## Genuine-absence shortlist — **VERIFIED 2026-06-12** (#46)

All 8 low-confidence dates were checked against [commissioners.allencountyohio.com](https://commissioners.allencountyohio.com)
(year-specific minutes + agenda archives, raw-link inspection). **None is a corpus
capture lag** — our holdings already mirror what the county publishes. Outcomes are
recorded per-date in [`../commissioners/minutes/filename-map.yaml`](../commissioners/minutes/filename-map.yaml)
under `genuine_absence_verified:`. Summary:

- **Minutes present, no agenda → special-session structure (no separate agenda is ever published):**
  2023-03-22, 2023-06-21, 2025-08-13, 2025-11-14 — all confirmed "-Special Session"
  upstream. *(Correction: 2024-06-20, also on the old shortlist, is **not** special —
  the held `M062024.pdf` is a regular Thursday session; its agenda is genuinely
  absent upstream, the county never posted an `A062024`.)*
- **Agenda present, minutes never captured → genuine upstream absence (county never posted minutes):**
  2024-09-25 (Wed between regular Tue/Thu sessions), 2024-12-30 (year-end special
  session), 2025-12-30 (the county page's "December 30, 2025" minutes link is
  mislabeled — its href points to the Dec 23 file `M122325.pdf`; no real
  `M123025.pdf` exists upstream).

No corpus action required for any of the 8.

**Full civic cutover (2026-06-12, #133 follow-on):** the commissioners' entire meeting
record (Jan 2023–, 991 files) is now **connector-sourced** under
[`data/documents/commissioners/meetings/`](../../documents/commissioners/meetings/).
The legacy hand-assembled `minutes/raw/` tree (930 PDFs) was **retired** after every
file was verified **byte-identical** to its connector copy — the per-file record is
[`cutover-reconciliation.yaml`](../commissioners/meetings/cutover-reconciliation.yaml)
(930/930 matched, 0 retained). The download manifest + meeting index sit alongside it.
**OCR pass complete (2026-06-12, #135):** all 991 files text-extracted, **969/991 dates
content-verified** and **270 meetings flagged for corridor topics** (up from 497/91 when only
the agendas had a text layer). The "934 files in `minutes/raw/`" figures above describe the
pre-cutover 2026-04-17 snapshot.

---

## Cross-refs
- [`bosc-prr-production-2026-06-05.response-index.yaml`](prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml) — the production tracker §1 is read from
- [`bosc-prr-production-2026-06-05.analysis.md`](prr-mandamus/bosc-prr-production-2026-06-05.analysis.md) · [`../../../docs/legal/mandamus-analysis.md`](../../../docs/legal/mandamus-analysis.md)
- [`allen-county-web-vendor-audit.md`](web-vendor-audit/allen-county-web-vendor-audit.md) · [`allen-county-level-sites.md`](web-vendor-audit/allen-county-level-sites.md) — item-16 custody
- [`../oepa/`](../oepa/) (Shawnee II permit `2PK00002`) · [`../../reference/echo/`](../../reference/echo/) (Maumee discharger inventory) — Category-B wastewater ties
- [`../../../docs/COMPUTE.md`](../../../docs/COMPUTE.md) · [`../../reference/compute/README.md`](../../reference/compute/README.md) — the compute / AI-capacity derivation whose keystone (air permit P0138965) §4 tracks
