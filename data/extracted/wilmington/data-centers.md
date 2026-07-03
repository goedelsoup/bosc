# Wilmington / Clinton Co., OH — Data-Center Activity Register

Discover-and-pin register for the Wilmington watershed point — the **Little Miami**'s single-tenant
**Wilmington Air Park (ILN)** corridor (ex-DHL super-hub → Amazon Air / ATSG cargo). Status **as of
2026-07-03**. Tags are BOSC evidentiary discipline: `[verified]` = cited primary/government source,
`[reported]` = credible secondary, `[reference]`, `[inference]`, `[open]`.

**This is a scaffold, not a completed sweep (#519), and it doubles as the load-driver verification
record (#891).** The web / permit / interconnection pass is **to-run**; every open item names the
primary instrument to pull. **Nothing here is fabricated.** A flat no-activity outcome is a valid,
citable result — not a failure.

## Discipline guardrail

Do **not** bridge the **Lima/Allen County Bistrozzi land-assembly graph** onto Wilmington/Clinton —
there is no evidentiary link. Every data-center entity in the corpus graph (Bistrozzi shells,
Amazon.com Services LLC, Google, Turner Construction, EMH&T/Vorys/WSGR) resolves **exclusively** to
Allen County parcels and bodies. Any Clinton County assembly is a **separate register**.

## Disambiguation guardrail

Confirm every entry is physically in **Clinton County, OH** (FIPS 39027) — the Wilmington situs.
Do not confuse **Wilmington, OH** with Wilmington DE / NC. The Air Park is **ILN** (Airborne /
Wilmington Air Park), not ILM (Wilmington NC) or Wilmington DE.

## 1 — Baseline: the corpus is empty and the employment mix is a *cargo*, not a *compute*, signal `[verified]`

- `[verified]` **Zero Wilmington / Clinton-County data-center primary documents are in the BOSC
  corpus** as of 2026-06-22 (self-research first pass, #247) — the corpus is entirely Lima/Allen
  County. This is a flat no-data finding, **not** evidence that none is proposed. `facility=None`.
- `[verified]` **No NAICS 518210 (data processing / hosting) facility** appears in the Clinton
  County RSEI toxics inventory (`reference/rsei/wilmington/inventory.yaml`, 21 facilities / 13
  scored). The inventory is entirely **metal-fab / auto-parts / foundry**: Stanley Works (332111),
  Ahresty Wilmington (331523), American Showa (336330), Kautex Textron, Blanchester Foundry
  (331511), UFP Blanchester (321114).
- `[verified]` The dominant economic signature is **Transportation & Warehousing (NAICS 48–49) LQ
  5.75** — the Air Park cargo hub (BLS QCEW 2023, area 39027, `reference/economics/wilmington/
  baseline.yaml`), **not** an IT-hosting cluster. Information (NAICS 51) sits at LQ 1.57 (577 jobs)
  but carries **no** identified data-processing establishment — the elevation is not a compute
  cluster on the record. `[verified]`

So the prior is **flat no data-center activity**; a sited campus would be a genuine discovery.
Commit a **dated, sourced flat no-activity finding** if the web/permit pass confirms nothing.

## 2 — The Air Park single-tenant thread (comparator, not a data center) `[reference]`

The **Wilmington Air Park (ILN)** is the "place shaped by one tenant" comparator — an ex-DHL super
hub now anchored by **Amazon Air** operated through **Air Transport Services Group (ATSG)** and its
ABX Air / ATI subsidiaries. `[reference]` It is a **cargo-aviation** footprint and an **Amazon**
footprint to set against the Lima Amazon **data-center** tenant — a useful contrast, **not** a data
center. Its power/water draw is a large-load anchor worth tracking (§3), but no compute facility is
on record. Verify tenancy against the Clinton County Port Authority / air-cargo record before any
figure is used; until then this stays `[reference]`.

## 3 — Load-driver verification (#891): no driver in the corpus; leads to pull `[open]`

The #891 premise is that onboarding must confirm a real large-load driver before deep profile work.
The corpus confirms **none is currently recorded**. The site keeps a plausible anchor (the Air Park),
so it is **not** reclassified inventory-only here — but the following external triggers are
**unchecked** and each must be queried and its outcome (confirmed driver / plausible lead / no
evidence) recorded before Wilmington is promoted:

### Instruments to pull (priority order)

1. **JobsOhio / Clinton County economic-development announcements** — any new large-load or campus
   incentive tied to Wilmington / the Air Park. `[open]`
2. **AES Ohio (Dayton Power & Light, #4922) / PJM DAY-zone large-load interconnection queue** — a
   >100 MW tap is the earliest hard signal of a compute or industrial load. (Grid identity is
   pinned: `reference/eia/wilmington/grid-profile.yaml` — DP&L / AES Ohio, PJM DAY zone.) `[open]`
3. **Ohio EPA eSuite / Air Division** — new-source air PTI (emergency-generator banks are the
   primary air trigger for a data center) for large industrial loads in Clinton County. `[open]`
4. **Ohio EPA / EPA ECHO NPDES** — new individual NPDES or data-center stormwater coverage under the
   draft general permit **OHD000001** on Todd Fork / Lytle Creek / the Little Miami. (Basin-screen
   ran 7/129 dischargers; WWTP receiving water already pinned — see the low-flow screen.) `[open]`
5. **Clinton County recorder / auditor + Ohio SOS** — large contiguous industrial assembly near the
   Air Park / I-71 corridor; nominee-LLC formations. Keep any find a **separate register**, never
   bridged to the Lima/Allen graph. `[open]`
6. **Clinton County Port Authority / Wilmington Air Park redevelopment filings** — the ex-DHL hub
   redevelopment record, where any co-located compute build would surface first. `[open]`

**Outcome as of 2026-07-03:** driver **not confirmed**; corpus records **zero**; the six instruments
above are the to-run pass. If all return negative, record a dated flat no-activity finding and hold
Wilmington at registry/inventory status (it is already non-`selectable` in `web/src/lib/sites.ts`).

## 4 — Hydrology hook (for any sited facility) `[open]`

Any sited Air Park / Clinton County facility discharges to **Todd Fork → Little Miami** (or Lytle
Creek → Todd Fork for the municipal path). Todd Fork is **ungaged**; the at-site 7Q10 is derived by a
**drainage-area-ratio interpolation** between the Milford (03245500) and Oldtown (03240000) brackets
— see `data/extracted/wilmington/low-flow-screen.md` (#516). The Little Miami is a **National & State
Scenic River** (anti-degradation overlay). Fill the water-draw figures from the primary instrument
only; leave `[open]` until disclosed. Do not invent a withdrawal figure.

## Sources

- Clinton County RSEI toxics inventory (in-corpus): `data/reference/rsei/wilmington/inventory.yaml`
- Clinton County economics baseline (in-corpus, BLS QCEW): `data/reference/economics/wilmington/baseline.yaml`
- Grid identity (DP&L / AES Ohio, PJM DAY zone): `data/reference/eia/wilmington/grid-profile.yaml`
- Ungaged Todd Fork low-flow screen (#516): `data/extracted/wilmington/low-flow-screen.md`
- Wilmington onboarding self-research pass (the zero-record + Air Park finding):
  `data/research/onboard-wilmington-*/` (see `data/extracted/wilmington/ONBOARDING.md`)
- Ohio EPA (data-center general permit OHD000001): <https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit>
