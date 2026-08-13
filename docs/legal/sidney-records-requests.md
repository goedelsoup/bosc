# Sidney — drafted R.C. 149.43 requests (AWS campus, 2388 W. Millcreek Rd)

Work product for issue [#1998](https://github.com/watermark-directory/the-watermark-directory/issues/1998),
epic #1275. **Drafts, not sent** — nothing here is a record, and nothing here has been transmitted.
Each ask below is the municipal half of the instruments-to-pull list in
[`data/extracted/sidney/data-centers.md`](../../data/extracted/sidney/data-centers.md); the state
and federal routes are scriptable and are handled by the standing watch instead
([`regulatory-watch.yaml`](../../data/extracted/sidney/regulatory-watch.yaml)).

## Before sending — three things this record already tells you to expect

1. **A five-business-day delay is contractual, not statutory.** CRA Agreement §32 and Development
   Agreement §8.17 oblige the City, on receiving a request touching the company's "Confidential
   Information", to notify the company, give it a copy of the request, and allow it at least five
   business days to negotiate a response or "pursue, at its sole cost and expense, legal remedies
   to stop the City's release". Neither clause enlarges any R.C. 149.43 exemption — it is delay
   layered on the statute — but it is why a response may not be prompt. `[verified]` #1380.
2. **R.C. 149.433 will be asserted over engineering detail**, and is already asserted three ways at
   this site: handwritten beside the City's redactions, blacking out Exhibit D edge to edge, and
   pre-printed on every sheet of the sewer plan set. ⚠️ But Ohio EPA **published that plan set
   anyway**, unredacted (#1998) — so the marking is a submitter's claim, not an agency
   determination, and a 149.433 stamp is not by itself a reason to stop asking.
3. **Frame to the instrument or the approval, not to the drawing.** `[inference]` The redactions
   that have actually occurred fell on line sizes, manhole counts and a water-service exhibit. An
   ask for *the approval and its conditions* has cleared where an ask for *the drawing* would meet
   the exemption.

**Ohio practice notes.** R.C. 149.43(B)(1) requires records "promptly" for inspection and copies
within a reasonable period. A requester need not put a request in writing, need not identify
themselves and need not state a purpose — R.C. 149.43(B)(4)-(5) — and an agency may not condition
production on any of those. If a request is denied in whole or part, R.C. 149.43(B)(3) requires the
public office to provide an explanation **with legal authority**; ask for that in writing, since it
is what a later R.C. 149.43(C) action is built on. Keep each request narrow and separately
numbered so a partial denial is legible as a partial denial.

---

## ✅ Requests 1 and 2 are ANSWERED — do not send them

The City's legislative portal `sidneycityoh.documents-on-demand.com` was **never blocked**. It was
recorded across this record as Cloudflare-challenged; the 403 is an **HTTP/2 fingerprint block**,
and the identical request over HTTP/1.1 returns 200 with a browsable JSON tree. #1999 corrected the
diagnosis; **#1998 acted on it, on 2026-08-13, and both asks were satisfied in minutes.**

| was request | what was pulled instead |
|---|---|
| 1 · minutes for the three vote dates | `City Council Minutes September 08, 2025.pdf`, `… October 27, 2025.pdf`, `… April 27, 2026.pdf` |
| 2 · Resolution 69-25 | `69-25 - Amending Resolution 84-22 - Expanding CRA Boundaries.pdf` — **and** `84-22`, the act that actually established the CRA |

All six are committed under `data/documents/sidney/council/` with sha256 and content-verified dates
in [`filename-map.yaml`](../../data/documents/sidney/council/filename-map.yaml).

**What the minutes settled.** Every one of the six votes now has its mover, second and result: five
passed unanimously and **Res. 82-25 passed 5–2**, with Councilmember Thurber and Vice Mayor Wagner
voting no. It is the only item across the three meetings the clerk journalled by name.

**Ask 1's part 2 is NOT answered and is still worth sending** — see request 1b below. The portal
carries minutes, not audio.

> **The generalisable lesson.** This record recorded "blocked" for this host in five artifacts and
> in these two drafted requests before anyone retried the request over HTTP/1.1. **A 403 to a
> scripted client may be a protocol-fingerprint block, not a policy.** Retry before recording a
> route negative — and before spending a public body's time on a request for a record it already
> publishes. The Shelby County Recorder and PUCO DIS were re-tested the same day under the same
> hypothesis and are genuinely blocked over both protocols; those negatives are dated in
> `data/extracted/sidney/regulatory-watch.yaml` → `route_retests`.

## 1b · City Clerk — meeting audio for the three vote dates

**To:** Clerk of Council, City of Sidney, 201 W. Poplar St., Sidney, OH 45365

> Under R.C. 149.43, I request any audio or video recording the City maintains of the regular
> meetings of Sidney City Council held on **2025-09-08**, **2025-10-27** and **2026-04-27**,
> including any recording of a committee or work session held on the same dates, in the electronic
> format in which it is maintained.

**Why this one still matters.** The approved minutes are now in the corpus and they record what was
decided — but they **name no member of the public**. On 2026-04-27 they say only that "a number of
people present raised questions and concerns" about pretreatment standards, monitoring, tap-in
costs, billing against the capacity reserve and fines, and that "those from the public speaking"
raised noise, vibration, power supply, environmental and health impacts and the city's financial
condition. No speaker, no group, no count. The audio is the remaining route by which any person
outside City government enters this site's record (#1947), and it is not on the portal.

**Also retrievable without a request, and not yet pulled:** the minutes of **2022-10-10** (Res.
84-22) and **2026-02-23** (Res. 14-26, the consolidation plat). Same portal; it holds Council
minutes back to **1857** and resolutions back to **1976**.

## 3 · Community Development — the site plan as approved

**To:** Community Development Director, City of Sidney

> Under R.C. 149.43, I request the **approved site plan** for the data-center campus at 2388 W.
> Millcreek Road / 1151 S. Vandemark Road, together with the staff approval, any conditions of
> approval, and the application and any completeness or review correspondence.

**Why.** Site-plan approval is administrative under Zoning Code §1115.09, so it surfaces as a staff
action with no agenda item — there is no minutes trail to find it in. The Development Agreement
confirms one is in the approval loop (§3.6.1; §5.4 site-plan fee under Codified Ordinances
§1309.11). This is the only route to a **building count** and the campus's gross floor area, which
AWS has never disclosed and which is why the IT load is an investment-scaled screening bracket
rather than a floor-area screen.

## 4 · Wastewater / Public Works — the significant-industrial-user permit

**To:** City of Sidney Public Works / Wastewater Superintendent

> Under R.C. 149.43, I request the **industrial user permit, significant industrial user permit, or
> pretreatment permit** issued to Amazon Data Services, Inc. or Amazon Web Services, Inc. for the
> facility at 2388 W. Millcreek Road, together with any pretreatment agreement, any baseline
> monitoring report submitted by that user, and any self-monitoring or discharge reports it has
> filed to date.

**Why.** This is the only instrument that separates this campus's wastewater from the WWTP's
totals. The service agreement fixes a **reserved** ceiling of 390,493 gpd (5.60% of the 7 MGD
plant); the SIU permit and its monitoring are what would show **actual** load against it — the
reserved-vs-metered distinction the cooling-model bracket turns on.

## 5 · Engineering — the grading plan and storm water report

**To:** City Engineer, City of Sidney

> Under R.C. 149.43, I request the **grading plan** and the **storm water report** on file with the
> Engineering Department for the grading permit issued for the AWS Data Center site at 2388 W.
> Millcreek Road (permit signed 2026-05-15), together with any approval, conditions or review
> correspondence.

**Why.** Both are recited on the face of the grading permit, so their existence is established by
an instrument already in the corpus. ⚠️ Expect R.C. 149.433 over parts of the drawings; ask for the
**approval and its conditions** even if the drawing itself is withheld, and request the written
explanation with legal authority that R.C. 149.43(B)(3) requires for any partial denial.

## 6 · City Clerk — annexation / rezoning for the campus parcel

**To:** Clerk of Council (same address)

> Under R.C. 149.43, I request any **ordinance or resolution annexing, rezoning or establishing the
> zoning classification of** Shelby County parcel **26-03-201-002** (formerly parcels 26-03-126-001,
> -226-001, -201-001, -251-001 and -251-002), together with the staff report and the Planning
> Commission recommendation for each.

**Why.** The City's own published GIS cannot answer the zoning question: the zoning layer
(`SidneyGIS_AllLayers/270`, adopted 2016) and the annexation layer (stopping at Ord. A-3145,
2023-08-28) both miss the campus's interior point, while the auditor's TY2025 tax district `01`
("CLINTON TWP SIDNEY CORP") says it **is** in the city. That is a currency gap in the published
layers, not unzoned land (#1379) — the ordinance is what closes it.

## 7 · City Clerk — the unredacted Development Agreement exhibits

**To:** Clerk of Council (same address)

> Under R.C. 149.43, I request the **unredacted** Development Agreement between the City of Sidney
> and Amazon (authorized by Resolution 27-26), including **Exhibit D**. If any portion is withheld,
> please provide the written explanation with legal authority required by R.C. 149.43(B)(3),
> identifying the specific exemption claimed for each withheld portion.

**Why.** The published copy blacks out sewer line size, manhole count and linear footage, the water
service line size and location, and the whole of Exhibit D — with `ORC 149.433` written by hand
beside each. The ask here is deliberately for the **explanation** as much as the record: a
149.433 claim is the submitter's, and the agency owes its own reasoning.

---

## Recording the responses

A response — including a denial — is evidence. Shelve the produced bytes under
`data/documents/sidney/<collection>/` with a `filename-map.yaml` entry, and record a **dated
per-route negative** for anything refused or unanswered, the way the standing watch records its
blocked routes. A denial with its cited authority is a finding in its own right, and is what an
R.C. 149.43(C) action would be built from.
