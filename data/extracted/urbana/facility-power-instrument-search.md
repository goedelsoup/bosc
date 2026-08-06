# Urbana Technology Hub — facility-naming power/emissions instrument search

**Issue:** #1353 (sub-issue of #1263) · **As of:** 2026-07-10
**Outcome:** **documented negative search on both instrument paths** — the campus MW load
stays **undisclosed**; the `[inference]` screening bracket is **retained** (never fabricated);
the end-use tag stays **`[reference]`** (no facility-naming primary instrument surfaced).

This closes the #1353 acceptance path by the *explicitly-permitted* alternative: "the
`[inference]` 34.5/74.8/115 MW screening bracket … **explicitly retained with a documented
negative-search note** (never fabricate a figure)." Two primary-instrument paths were searched;
neither surfaced a load or a genset fleet for this campus. Re-run the two searches when a permit
or interconnection filing is expected to have posted (triggers in §5).

---

## 1. PJM interconnection queue / AES Ohio (Dayton) TEAC — **no Urbana request** `[verified]`

A generation or large-load interconnection request pinned to Champaign County / Urbana in the
**AES Ohio (DAY) zone** would name the MW and often the customer. Two authoritative surfaces were
searched:

### 1a. AES Ohio "Dayton" supplemental (TEAC) large-load customer requests

PJM **Transmission Expansion Advisory Committee — Dayton Supplemental Projects** (the AES Ohio
local-plan large-load filings) enumerate AES Ohio's disclosed data-center *customer requests* by
serving substation. The 2026-02-03 filing (and the surrounding cycle) name the following — **none
in Champaign County / Urbana / Urbana Township**:

| Serving substation | Location (county) | Disclosed load ramp (verbatim) |
|---|---|---|
| Eldean | **Piqua, OH** (Miami Co.) | 12/2027 45 MW · 12/2028 205 MW · 12/2029 440 MW · 12/2030 600 MW (+ a 365→600→870→1140 MW→1400 MW alt.) |
| Stuart | **Adams County, OH** | 11/2028 100 MW · 07/2029 400 MW · 10/2030 700 MW · 10/2031 1100 MW · 03/2032 **1300 MW** |
| Darby | **Marysville, OH** (Union Co.) | 5/2030 270 MW · 11/2031 540 MW · 5/2033 800 MW |
| Airport | **Tipp City, OH** (Miami Co.) | 03/2028 20 MW · 03/2029 160 MW · 03/2030 300 MW |
| Fayette | **Jeffersonville, OH** (Fayette Co.) | 35 MW (2026) · 480 MW (2028) · 1.5 GW (2031) |
| Clinton | **Wilmington, OH** (Clinton Co.) | 35 MW · 100 MW (2028) · 300 MW (2029) · 500 MW (2030) |

Source: PJM TEAC Dayton Supplemental Projects decks; corroborated by the
[PJM PC/TEAC Feb. 3 2026 brief](https://www.rtoinsider.com/125312-pjm-pc-teac-020326/).
The filings' own text names each request "in the vicinity of its **[substation]** substation in
**[city, county]**." **Urbana / Champaign County does not appear.** `[verified]`

> **Citation corrected 2026-08-06 (#1469).** This table originally cited the
> [20260203 deck](https://www.pjm.com/-/media/DotCom/committees-groups/committees/teac/2026/20260203/20260203-item-06---dayton-supplemental-projects.pdf)
> (item 06) as its single source, qualified only by the parenthetical "and the surrounding
> cycle". That deck contains **two** needs — Dayton-2025-007 (Eldean) and Dayton-2026-001
> (Stuart) — and does **not** contain the Fayette or Clinton rows. Those are in the
> [20260707 deck](https://www.pjm.com/-/media/DotCom/committees-groups/committees/teac/2026/20260707/20260707-item-11---dayton-supplemental-projects.pdf)
> (item 11), as Needs **Dayton-2025-001** and **Dayton-2025-002**, both first presented at
> the Need Meeting of 2025-02-04. The Feb, May and July 2026 decks are all committed at
> `data/documents/grid/wilmington/` with a capture manifest. **The table's figures are
> correct** — including, notably, both the Fayette/Jeffersonville 1.5 GW and the
> Clinton/Wilmington 500 MW, which this file had right while
> `data/extracted/wilmington/data-centers.md` carried the press misattribution of the 1.5 GW
> to Wilmington. Only the source attribution was wrong. The Darby and Airport rows are from
> neither committed deck and their filing is **not** re-established here — treat those two
> rows as uncited pending a read of the cycle that carries them.

### 1b. Interconnection queue (generation) — Champaign County

The only PJM interconnection-queue project in Champaign County, OH is **Woodstock Solar (AE2-342)**
— a **40 MW solar** generation request, **status withdrawn** — which is **not** the Urbana
Technology Hub and not a large-load request. Source:
[interconnection.fyi/project/pjm-ae2-342](https://www.interconnection.fyi/project/pjm-ae2-342).
`[verified]`

**Path result:** no Urbana large-load or generation interconnection request is on the PJM queue /
AES Ohio TEAC record as of 2026-07-10. This is *consistent* with the developer disclosing **no MW
figure** at the Feb-2026 City of Urbana meeting (§3) — the interconnection filing that would name
the load has not (yet) posted.

---

## 2. Ohio EPA air PTIO / US-EPA ECHO (ICIS-AIR) — **no campus air permit** `[verified]`

The OEPA connector is proven reachable (the `oepa/urbana/` NPDES tree, #1331), but the *air*
program is a separate database. An emergency-genset **Permit-to-Install-and-Operate (PTIO)** for
the campus would populate `genset_count` / `genset_mw` / `air_permit_citation` and activate the
air-dispatch model. Searched via US-EPA **ECHO air (ICIS-AIR/AFS)**, spatially, around the disclosed
site (Vance Brands parcel **40.0887 N, -83.7611 W**, SR-55 & US-68):

Bounding-box query `40.0887,-83.7611 → 40.16,-83.65` returns **7 air-program sources**, all
**pre-existing** industrial sources in/around Urbana city — **none is the campus, Thor, Highland55,
Urbana Owner, Vance Brands, or a data center**, and none sits at the SR-55/US-68 greenfield parcel:

| Facility (AIRName) | Address | NAICS | Programs |
|---|---|---|---|
| CITY OF URBANA | 1217 Children's Home Rd | 562212 (landfill) | SIP |
| THE HALL COMPANY | 420 E Water St | 323122 (printing support) | FESOP, SIP |
| HERITAGE COOPERATIVE | 304 Bloomfield Ave | 111150 (grain) | SIP |
| JMC METAL PROD. / JOHNSON INDS. | 605 Miami St | 332812 (metal coating) | SIP |
| RUSSELL T. BUNDY ASSOCIATES INC | 417 E Water St | 811310 | FESOP, SIP |
| ULTRA-MET MFG. CO. | 120 Fyffe St | 331491 | SIP |
| WESTVILLE GRAIN CO. | 1045 St. Rt. 560 | 311119 (grain) | SIP |

Source: US-EPA ECHO `air_rest_services` (`get_facilities` → `get_qid`), retrieved 2026-07-10; all
carry FIPS **39021** (Champaign County). A county-scoped ICIS-AIR query for a *new* large source at
the site returns none. `[verified]`

**Path result:** no air PTIO / air permit for the Urbana Technology Hub exists on the ECHO/ICIS-AIR
record as of 2026-07-10. This is expected for a greenfield campus whose construction window opens
**2026-06-01** (401 WQC, `highland55-findings.md`) — an emergency-genset PTIO, if the design has a
genset fleet at all, would typically be applied for at/near construction. The profile therefore
**carries no genset fleet and no air permit** (`genset_count` / `genset_mw` /
`air_permit_citation` = `None`) and the air-dispatch model refuses cleanly.

---

## 3. Cross-project conflation guard — **read before quoting any MW** ⚠️

Thor Equities / its **Form8tion** platform has **multiple** Ohio data-center projects, and AES
Ohio has **multiple** Dayton-zone large-load customers. Automated news/search summaries conflate
them. **None of the following belongs to Urbana:**

- **100 MW (2028) → 1.3 GW (03/2032)** — this is the **Adams County / Stuart substation** AES Ohio
  request (§1a), **not** Urbana. A news-summary layer mis-attributed it to Urbana during this
  search; it was rejected on the primary TEAC filing.
- **~500 MW** — this is Thor's **Van Wert County** campus (US-30, ~35 mi SE of Fort Wayne; ~900 ac,
  ~$10 B long-term; a QTS site sits ~2.5 mi away), **not** Urbana. (DCD; datacentermap "Form8tion
  Van Wert".)

Urbana's own disclosure (Urbana Daily Citizen 2026-02-18; Peak of Ohio; the Thor project info
sheet) gives **floor area (460,000 sq ft), ~$1 B, closed-loop cooling, 30–80 ops jobs, ~$5.8 M/yr
tax — and no MW.** baxtel, which lists power capacity when known, lists **none** for the Urbana
project. The Urbana campus MW load is genuinely **undisclosed**, not merely un-found.

---

## 4. "Vance Brands" tenant/operator — stays `[open]`

Neither the PJM nor the OEPA-air search named a tenant or operator. "Vance Brands" appears in the
Corps JD filings (`highland55-findings.md`) as a parcel/project name and resolves in the auditor
record to **Brand Investments LTD** (the grantor of the Vance Brands parcel) — **not** to a
data-center operator. No interconnection customer name and no air-permit applicant surfaced to
resolve it. The tenant/operator question remains `[open]` (#1263).

---

## 5. Disciplined outcome + re-verify triggers

- The **`[inference]` 34.5 / 74.8 / 115 MW screening bracket is RETAINED** (`_URBANA.facility.it_load_citation`),
  now annotated with this negative search. **No MW figure was fabricated** to close the load.
- The **end-use tag stays `[reference]`** (public disclosure) in `datacenter-facility.md` §7 and
  `highland55-findings.md` — no facility-naming primary instrument surfaced to take it to `[verified]`.
- `genset_count` / `genset_mw` / `air_permit_citation` stay **`None`**.
- `economics-demand-pressure` continues to run off the retained 74.8 MW central bracket (unchanged).

**Re-run this search when:**

- a later **PJM TEAC Dayton Supplemental** filing (AES Ohio local plan) posts — watch for a
  "customer request in the vicinity of [an Urbana-area] substation" or a Champaign-County entry;
- a **PJM new-services / large-load queue** position appears for the AES Ohio (DAY) zone at Urbana;
- an **OEPA air PTIO** (emergency engines) posts to ECHO/ICIS-AIR at the SR-55/US-68 parcel, or the
  City of Urbana **site-plan / building permit** becomes reachable to ingest.

Any of these **replaces the bracket with the disclosed load** and **flips the end-use
`[reference]` → `[verified]`** across the profile, `datacenter-facility.md` §7, and
`highland55-findings.md`.

## Sources

- PJM TEAC 2026-02-03 Dayton Supplemental Projects (item 06) — <https://www.pjm.com/-/media/DotCom/committees-groups/committees/teac/2026/20260203/20260203-item-06---dayton-supplemental-projects.pdf>
- PJM PC/TEAC brief, 2026-02-03 — <https://www.rtoinsider.com/125312-pjm-pc-teac-020326/>
- interconnection.fyi — Woodstock Solar (AE2-342), Champaign County, OH — <https://www.interconnection.fyi/project/pjm-ae2-342>
- US-EPA ECHO air (ICIS-AIR/AFS) `air_rest_services`, spatial query near 40.0887,-83.7611 — retrieved 2026-07-10
- Urbana Daily Citizen, "Data center plans revealed at city meeting," 2026-02-18 — <https://www.urbanacitizen.com/2026/02/18/data-center-plans-revealed-at-city-meeting/>
- Peak of Ohio, "Thor Equities highlights economic impact of proposed Urbana data center" — <https://www.peakofohio.com/local-news/thor-equities-highlights-economic-impact-of-proposed-urbana-data-center/>
- DataCenterDynamics / baxtel / datacentermap — Van Wert County (500 MW) vs. Urbana (no MW) disambiguation
