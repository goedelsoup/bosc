# Lima data-center campus — federal-authorization instrument search (H2)

**Issue:** #1480 (sub-issue of #1261) · **As of:** 2026-07-15
**Outcome:** **documented negative search on every instrument path** — no facility-naming
federal-authorization instrument (FedRAMP / DoD IL / GSA-DoD award / cloud-region
designation) ties the Lima campus, its owner-of-record shell (**Bistrozzi LLC** /
**Bistrozzi Addition LLC**), or the campus address to a federal workload. The **H2 defense
nexus stays an `[inference]`** (proximity, not connection); the `H2-AUTH` authorization
question stays **undisclosed** — and this search establishes it is undisclosed *by the
structure of the record*, not merely un-looked-for.

This closes the #1480 acceptance path by the outcome the issue anticipated (cf. Urbana
#1353): *"a confirmed negative … is itself a useful, citable finding, not a non-result."*
Four instrument paths were searched against primary/authoritative surfaces; none surfaced a
facility-scoped authorization. Re-run when a disclosure trigger fires (§6).

The single sharpest structural finding is in §2: a Google federal authorization **attaches
to the cloud service, not to a street address**, so even a fully-authorized federal workload
running at Lima would leave **no facility-naming public instrument to find**. The negative is
therefore expected, and it does not lower the ceiling on the question — it maps where the
ceiling is.

---

## 1. USASpending / SAM.gov — the owner-of-record shell has **no federal footprint** `[verified]`

The campus is a composite of **10 Bistrozzi LLC parcels**
(`data/entities/poi/data-center-campus.md`); the assembling entity registered in Ohio as
**Bistrozzi Addition LLC**, a **foreign (Delaware) LLC**, organizer **Scott J. Ziance**
(Vorys), registered agent CT Corporation
(`data/extracted/permits/sos-bistrozzi-addition-llc-2026-04-08.sos.yaml`). A federal award
to that entity — a GSA/DoD contract, a cooperative agreement, any prime obligation — would
name it on USASpending. It does not.

Queried the **USASpending.gov API** (`api.usaspending.gov`, U.S. Treasury; the same public
surface `watermark usaspending` resolves against) directly, 2026-07-15:

| Query | Endpoint | Result |
|---|---|---|
| recipient keyword `Bistrozzi` | `POST /api/v2/recipient/` | HTTP 200 · **0 recipients** |
| recipient keyword `Bistrozzi Addition` | `POST /api/v2/recipient/` | HTTP 200 · **0 recipients** |
| award recipient text `Bistrozzi` | `POST /api/v2/search/spending_by_award/` | HTTP 200 · **0 awards** |

Neither shell exists as a USASpending recipient and neither holds any federal prime award.
`[verified: USASpending.gov API, retrieved 2026-07-15]` This is consistent with Bistrozzi
being an economic-development land-holding SPE (Vorys / Ziance is the corridor's abatement
counsel, `data/entities/people/scott-ziance.md`), **not** a federal contractor. A real-estate
holding shell with no federal awards has no reason to hold a SAM.gov entity registration
either (SAM registration is a precondition of *receiving* awards, which it does not).

**Path result:** no GSA/DoD award, cooperative agreement, or SAM.gov recipient record names
the campus owner. The corridor's only *verified* federal-award recipient remains **General
Dynamics Land Systems** — the JSMC operator (§4), which is the arsenal, not the campus.
`[verified: data/entities/profiles/usaspending-watchlist.yaml]`

---

## 2. FedRAMP Marketplace — the authorization is **service-scoped, names no facility** `[verified]`

The `H2-AUTH` predicted evidence is "a documented authorization posture (FedRAMP / DoD IL
clearance level)." Searched the **FedRAMP Marketplace** for a Google product listing that
names a Lima / Allen County / Ohio facility, address, or region. The relevant listing —
**"Google Services (Google Cloud Platform Products and underlying Infrastructure)"**
([FR1805751477](https://www.fedramp.gov/marketplace/products/FR1805751477/)) — is:

- **Impact level:** High · **Status:** FedRAMP Certified (2019-12-04, Rev5) · Agency path ·
  26 authorizations · 424 reuses. `[reference: FedRAMP Marketplace, retrieved 2026-07-15]`
- **Scope:** the **cloud service offering itself** — "GCP Products and underlying
  Infrastructure" — **not** a named physical facility. The listing **names no data-center
  facility, street address, city, or region**, Lima or otherwise. `[verified: same]`

This is the structural point, and it is decisive for the whole search. Google's public-sector
compliance is delivered through **Assured Workloads**, which — in Google's own words —
**"does not rely on physical infrastructure distinct from Google's public cloud data centers.
Instead, it delivers a Software Defined Community Cloud"**
`[reference:` [cloud.google.com/blog … FedRAMP High on 100 additional services](https://cloud.google.com/blog/topics/public-sector/google-cloud-achieves-fedramp-high-authorization-on-100-additional-services)`]`.
A FedRAMP / DoD-IL authorization in this model attaches to the *software boundary and the set
of regions*, **not to a building**. So a facility-naming FedRAMP instrument for Lima **cannot
exist by construction** — not because Lima is un-authorized, but because the authorization
grammar has no "facility" object to bind to an address. **The absence of a Lima FedRAMP
instrument is therefore evidence of nothing** about whether federal workloads could ever run
there — it is exactly what an authorized *or* unauthorized Lima facility would both look like.

**Path result:** no facility-naming FedRAMP authorization exists for the Lima campus, and
the record's structure means none would even if the campus hosted federal workloads. The
`H2-AUTH` question is **not answerable** from the FedRAMP Marketplace in either direction.

---

## 3. DoD Impact Level + public-sector cloud-region announcement — **capability, not a Lima fact** `[reference]`/`[open]`

DoD impact-level authorizations were searched for a Lima-specific disclosure. What the record
shows is a **capability Google holds network-wide**, never pinned to this facility:

- Google Cloud holds a **DISA Provisional Authorization at IL2 / IL4 / IL5**; **Google
  Distributed Cloud (air-gapped appliance) holds IL6**. `[reference:` [Google Cloud DISA
  compliance](https://cloud.google.com/security/compliance/disa)`,` [GDC IL6](https://cloud.google.com/blog/topics/public-sector/google-distributed-cloud-gdc-gdc-air-gapped-appliance-achieve-dod-impact-level-6-il6-authorization)`]`
- **No** source ties any IL authorization to the Lima campus. IL authorizations, like
  FedRAMP, scope to the service/region, not the building. This restates — and now sources —
  the point already in `docs/defense-nexus.md`: the IL credential "is a capability Google
  holds everywhere it operates, not a fact about Lima." `[open]`
- **No public-sector cloud-region / Assured-Workloads announcement names Lima or Ohio** as a
  government region. Searched Google Cloud region/Assured-Workloads announcements 2026-07-15;
  none references the Lima build. `[verified: negative — Google Cloud region announcements]`

Independently, the *public* framing of the Lima build is **commercial**: Google's $500 M,
~200-acre American/Sugar-Creek-township project is described as supporting "personal
electronics, hospitals, and businesses," ~50 jobs — no federal, defense, or classified
purpose disclosed. `[reference:`
[hometownstations.com](https://www.hometownstations.com/news/allen_county/google-revealed-as-company-behind-500-million-data-center-project-in-lima-area/article_7fa7f0c1-88c1-4d79-86ca-630d942787e6.html)`,`
[DCD](https://www.datacenterdynamics.com/en/news/google-confirmed-as-company-behind-500m-data-center-in-lima-ohio/)`]`

**Path result:** the DoD-IL posture is a service-level capability, not a Lima disclosure; no
region announcement names Lima. The authorization posture stays **undisclosed** — searched,
not found, and structurally unbindable to the address (§2).

---

## 4. JSMC co-location — **coincidental geography, no documented supply/authorization link** `[inference]`

The `H2-AUTH` lead's second half asks whether the **Joint Systems Manufacturing Center**
(Lima Army Tank Plant) co-location is a demonstrated relationship or shared geography. This
search confirms the reading already argued in `docs/defense-nexus.md`:

- The JSMC is **~5.5 mi south** of the campus (nearest parcel edges), a government-owned,
  **General Dynamics Land Systems**-operated (GOCO) plant currently building **M1A1 Abrams**
  (including for Ukraine). `[verified: data/reference/allen-gis/parcels.defense.yaml;
  reference:` [TACOM JSMC-Lima](https://tacom.army.mil/jsmc-lima)`,`
  [Lima Army Tank Plant (Wikipedia)](https://en.wikipedia.org/wiki/Lima_Army_Tank_Plant)`]`
- **Nothing** in the public record — no contract, filing, deed, or dated communication —
  ties the Google campus, Bistrozzi, or a defense workload to the JSMC or to GDLS. A
  Google↔JSMC/GDLS **data-center supply-chain contract search returned nothing**.
  `[verified: negative — SAM.gov/USASpending/news, 2026-07-15]`
- This is corroborated on the County side by the standing **"no records"** response to the
  PRR item seeking County↔DoD/GDIT/GDLS communications on the corridor
  (`data/extracted/legal/prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml`,
  item 2). One avenue confirmed shut; the link neither established nor disproven.

**Path result:** the co-location is **geography, not a demonstrated relationship**. Per the
method (adjacency + capability + a market segment = an *inferred* connection, never a
finding), the nexus stays `[inference]`; the search declines to force it into a link —
exactly the outcome Urbana #1353 reached and held.

---

## 5. Conflation guard — read before quoting any "federal Google" fact ⚠️

Automated summaries blur Google's **network-wide** federal capabilities into **site-specific**
Lima claims. None of the following is a fact *about Lima*:

- **IL2/IL4/IL5/IL6, FedRAMP High** — capabilities of the Google Cloud **service**, held
  everywhere Google operates. Not a Lima authorization (§2–3).
- **Project Dazzler (Scioto County)** — the one place a `google.com` applicant email attaches
  to Google in the corpus is a **separate** project, **not** the Lima corridor campus
  (`data/entities/profiles/usaspending-watchlist.yaml`, Google `nexus: open`).
- **The "Google" attribution to the Lima campus itself** rests on the AEDG release + press
  (`[reference]`), not yet a primary corpus instrument; the end-user attribution is tracked
  as `open` in the watchlist. This search does **not** upgrade it.
- **General Dynamics federal awards** are the **arsenal's** (JSMC/GDLS), not the campus's
  (§1, §4).

---

## 6. Disciplined outcome + re-verify triggers

- The **H2 defense nexus stays `[inference]`** (proximity, not connection) and the **`H2-AUTH`
  authorization posture stays undisclosed / `[open]`**. **No federal link was fabricated** to
  close the question, and **no inference was silently dropped** — it is now investigated and
  bounded.
- The `data/hypotheses/defense/lima.yaml` cell keeps its **`signal: anchor`, `tag: verified`**
  (the *geography* is verified); a citation records this negative authorization search so the
  cell is no longer un-investigated on the posture.
- The `H2-AUTH` lead is updated to cite this artifact — a **documented negative**, not an open
  un-run search.

**Re-run this search when:**

- a **GSA/DoD contract award or cooperative agreement** naming Bistrozzi LLC / Bistrozzi
  Addition LLC / Google at the campus address posts to USASpending / SAM.gov;
- a **FedRAMP Marketplace** or **DISA IL** listing begins naming a facility/region that can be
  resolved to Lima / Allen County (a change in Google's disclosure grammar);
- a **Google Cloud region / Assured-Workloads / public-sector** announcement names the Lima
  build as a government or federally-scoped region;
- the **AEDG release** (or any primary instrument) lands in the corpus and resolves the campus
  end-user attribution — at which point re-run §1 against the *named* operator.

Any of these **replaces the `[inference]`/`[open]` posture with the disclosed instrument** and
updates `H2-AUTH`, the `defense/lima.yaml` cell, and `docs/defense-nexus.md` together.

## Sources

- USASpending.gov API (`api.usaspending.gov`), U.S. Treasury — recipient + award search, `Bistrozzi` / `Bistrozzi Addition`, retrieved 2026-07-15 (0 results)
- FedRAMP Marketplace, "Google Services (GCP Products and underlying Infrastructure)" FR1805751477 — <https://www.fedramp.gov/marketplace/products/FR1805751477/>
- Google Cloud, "FedRAMP High authorization on 100 additional services" (Assured Workloads = Software Defined Community Cloud, no distinct physical infrastructure) — <https://cloud.google.com/blog/topics/public-sector/google-cloud-achieves-fedramp-high-authorization-on-100-additional-services>
- Google Cloud DISA compliance (IL2/IL4/IL5 PA) — <https://cloud.google.com/security/compliance/disa>
- Google Distributed Cloud air-gapped appliance, DoD IL6 — <https://cloud.google.com/blog/topics/public-sector/google-distributed-cloud-gdc-gdc-air-gapped-appliance-achieve-dod-impact-level-6-il6-authorization>
- US Army TACOM, JSMC-Lima — <https://tacom.army.mil/jsmc-lima>; Lima Army Tank Plant — <https://en.wikipedia.org/wiki/Lima_Army_Tank_Plant>
- Google confirmed behind $500M Lima data center (commercial framing) — hometownstations.com; DataCenterDynamics
- Corpus cross-refs: `data/entities/poi/data-center-campus.md`; `data/extracted/permits/sos-bistrozzi-addition-llc-2026-04-08.sos.yaml`; `data/entities/profiles/usaspending-watchlist.yaml`; `data/extracted/legal/prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml` (item 2); `docs/defense-nexus.md`
