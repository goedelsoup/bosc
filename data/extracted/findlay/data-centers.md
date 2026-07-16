# Findlay / Hancock County, OH — Data-Center Activity Register

Discover-and-pin register for the Findlay onboarding — the **I-75 corridor** sweep required by
#1459 (epic #1265). Status **as of 2026-07-16** (research refresh 2026-07-10). Tags are BOSC
evidentiary discipline: `[verified]` = cited public source, `[inference]`, `[open]`, `[reference]`.
Unlike a pure discover-and-pin sweep, this one has an **affirmative, doubly-sourced finding**: a
disclosed, operating large-load facility whose MW is verified from both sides via SEC instruments
(entry 1). Every figure is cited; none is fabricated. Do not bridge the Lima/Allen County graph
onto Hancock County — there is no evidentiary link.

## Disambiguation guardrail

Findlay is **not** an affirmative-negative county (contrast Ottawa #1423). Every entry below is
confirmed as genuinely Hancock County, OH.

⚠️ **The critical guard: MARA Holdings, Inc. ≠ Marathon Petroleum Corp.** Two unrelated companies,
both attachable to the string "Marathon … Findlay, Ohio":

- **MARA Holdings, Inc.** (NASDAQ: **MARA**) — a bitcoin-mining company, formerly **Marathon
  Digital Holdings**. It is the 150 MW take-or-pay customer of the One Power hub (entry 1).
  `[verified]`
- **Marathon Petroleum Corp** (NYSE: **MPC**) — the petroleum refiner **headquartered in Findlay,
  OH**, and a Hancock-County NPDES/air permittee. It has **no** relationship to the data-center
  activity here. `[reference]`

Never merge these two entities in the EntityGraph. Add an explicit disambiguation note to both
entity records. The name collision ("Marathon … Findlay") is exactly the trap this guard exists
to catch.

## 1 — MARA Holdings at the One Power "Findlay Megawatt Hub" (MWHub 01)

The one confirmed operating large-load facility in the county. Verified from **both sides** — the
host's SEC filing and the customer's own release.

- **Host / operator:** One Power Co (privately held; CEO Jereme Kent). `[verified]`
  Source: One Power Co Form S-1/A, EDGAR CIK 2039139.
- **Anchor customer:** MARA Holdings, Inc. (NASDAQ: MARA; ex-Marathon Digital Holdings) — bitcoin
  mining. `[verified]` Source: One Power S-1/A + MARA 2024-11-11 release.
- **Facility name:** MWHub 01, the "Findlay Megawatt Hub." `[verified]`
- **Location:** ~170-acre campus in Allen Township, Hancock County — I-75 at TR 215 / CR 99.
  `[verified]` Source: One Power S-1/A.
- **Capacity:** "Current Capacity 30 MW, Planned Maximum 150 MW, Status: **Operating**." First
  energized 2023 with "the first fully digital substation in the United States." `[verified]`
  Source: One Power S-1/A.
- **Contract:** MARA leases **150 MW for 15 years, take-or-pay** — payment "due regardless of
  whether or not the customer elects to purchase power." `[verified]` Source: One Power S-1/A.
- **Customer corroboration:** MARA's 2024-11-11 release describes "a **150-megawatt operation in
  Findlay, Ohio**, which already has **30 megawatts of capacity**," part of ~372 MW across three
  Ohio sites, with full energization **intended by end-2025**. `[verified]`
  Source: [ir.mara.com/news-events/press-releases/detail/1375](https://ir.mara.com/news-events/press-releases/detail/1375/).
- **Current energization status (as of 2026):** `[open — MARA 10-K / operations updates]` — the
  30→150 MW build-out timeline was "intended by end-2025"; whether the full 150 MW is energized
  today is not confirmed in the sources reviewed. This is the standing open check.
- **`SiteFacility` populated (#1459):** `it_load_mw = 150` (contracted take-or-pay, `[verified]`),
  `it_load_low_mw = 30` (currently energized, `[verified]`), `it_load_high_mw = 150`. The MW here
  is a **disclosure**, not a screening bracket — contrast the site-plan-grounded Urbana (#1327) /
  Sidney (#1378) / Van Wert (#1402) facilities whose loads are inferred. `cooling_model = UNKNOWN`
  (MARA's Findlay cooling design is not on the record). `genset_count/genset_mw/air_permit` stay
  `None` (no air permit found — see Regulatory record). See `_FINDLAY` in
  `src/watermark/sites/_profiles.py`.

### Corporate chain

- **One Power Co** — IPO Form S-1 filed **2025-01-23**; **withdrawn (Form RW) 2025-05-09**; Form D
  private placement **2025-07-23** (EDGAR CIK 2039139; DRS 2024-11-12). September 2025
  reorganization / layoffs + a lender workout. `[reference]`
- **OnSite Partners acquired One Power Company** — announced **2026-02-16**. OnSite is owned by
  funds advised by **Basalt Infrastructure Partners**. `[verified]`
  Source: [onsitepartners.com/news/onsite-partners-acquires-one-power-company](https://onsitepartners.com/news/onsite-partners-acquires-one-power-company-to-expand-distributed-generation-portfolio/).
- **OnSite + AEP + Basalt** data-center-power collaboration (Bloom fuel cells) — announced
  **2025-06-12**. `[verified]`
  Source: [onsitepartners.com/news/onsite-partners-aep-and-basalt-infrastructure-partners-collaborate](https://onsitepartners.com/news/onsite-partners-aep-and-basalt-infrastructure-partners-collaborate-to-bring-power-solutions-to-data-centers/).

### Land assembly

- 110 ac @ **$5.9M closed 2026-03-05** (North Findlay Industrial Park) + 40 ac in 2025 + the 74-ac
  wind campus. `[open — Hancock County Recorder pull]` — grantee vehicle / parcel IDs pending the
  epic #1265 recorder/places sub-issue.
- **Hyperscale end-use for the land assembly is press speculation only** (`[reference]`, The Ohio
  Register) — **no operator, no instrument.** It stays **out of this register's numbered entries**
  and out of the `SiteFacility`: the disclosed facility (entry 1) is the MARA compute load, not a
  speculated hyperscale campus.

### Water / hydrology hook

- **Cooling design:** `[open]` — MARA has not stated the Findlay cooling design. The One Power hub
  is a behind-the-meter natural-gas-generation compute campus; bitcoin-mining loads span
  air-cooled, immersion, and hydro-cooled designs. `cooling_model` stays `UNKNOWN` (bracketed
  range, never the evaporative default).
- **Max withdrawal / consumption:** `[open]` — no disclosed water-service agreement or withdrawal
  figure for the hub (contrast Sidney's Res 26-26 1.0 MGD ceiling). No figure invented.
- **Receiving water (context):** the Blanchard River near Findlay — 7Q10 derived 8.67 cfs (USGS
  04189000; `low-flow-7q10.derived.yaml`, #414). `[verified]` The reconciliation of that
  denominator is the epic #1265 hydrology sub-issue's target, not this facility issue's.

### Hydrology screen

`[open]` — no disclosed water draw for the MARA operation, so no assimilative screen is run. Leave
open until a water-service agreement, an NPDES industrial permit, or a cooling spec discloses a
figure. Do not invent one.

### Regulatory record (status as of 2026-07-16)

- **Ohio EPA air PTI (generator banks):** `[open]` — **no One Power / MARA generator-bank PTI
  found at web level.** The behind-the-meter natural-gas generation implies air permitting, but no
  instrument was reachable. Instrument to pull: OEPA Air Pollution Control / NWDO **eSuite**,
  search "One Power," "MARA," "Marathon Digital," Hancock County / Allen Township, 2023–2026.
- **Construction-stormwater NOI:** `[open]` — a NOI for the 110-ac North Findlay parcel is
  expected but not confirmed. Instrument to pull: OEPA Division of Surface Water CGP NOI.
- **OHD000001** (the statewide **draft data-center-discharge general permit**; comments closed
  **2026-01-16**): `[open]` — the docket should be scanned for Findlay-area commenters. Instrument
  to pull: the OHD000001 comment record.
  Source (hearing slides): [dam.assets.ohio.gov … OHD_DataCenter_PP-FINAL-PresentationFull-Slides](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/Data_Centers/OHD_DataCenter_PP-FINAL-PresentationFull-Slides-Correct.pdf).
- **Ohio SOS entity registrations:** One Power Co, MARA Holdings, Inc. `[open]` — not pulled.

## 2 — Watch surface (in-county, no instrument yet)

- **+300 MW made available in 2024** via a One Power "standalone interconnection site" expansion
  (S-1/A) — **no named customer.** `[open]` The interconnection instrument (PUCO / PJM / AEP) is
  the epic #1265 grid sub-issue's target. **Not** in the `SiteFacility` basis.
- **Tall Timbers West** and **Findlay International Park** — industrial-park capacity to watch; no
  disclosed data-center tenant. `[open]`

## 3 — Corridor context (adjacent counties, out of scope for this site)

Context only — these are **not** Hancock County entries and are **not** in scope for the Findlay
node (the disambiguation guardrail: adjacent-county projects are context, not entries):

- **Meta "Project Accordion" ($800M+)** — Bowling Green / Wood County (the Bowling Green node,
  epic #1433). `[reference]`
- **Shawnee Township 18-month data-center moratorium** — Allen County (the Lima node's county).
  `[reference]`

## 4 — Negative checks (per-source)

- **stopohiodatacenters.org:** no Hancock County entry as of the 2026-07-10 sweep. `[verified]`
- **EPA ECHO / NPDES:** no NAICS 518210 or data-center-type NPDES permittee in the committed
  Maumee NPDES inventory (0 matches). `[verified]`
  Source: `data/reference/echo/maumee-wwtp.all-npdes.yaml`.
- **RSEI TRI inventory (Hancock County, v234, 29 facilities):** no NAICS 518210 entry; no
  data-center SIC. `[verified]` Source: `data/reference/rsei/findlay/inventory.yaml` (FIPS 39063).
- **OEPA air PTI web search:** no One Power / MARA generator-bank PTI reachable at web level
  (see Regulatory record). `[verified — negative]`

A negative check tagged `[verified]` is a result, not a gap — it protects the record.

## Instruments to pull (priority order)

1. **One Power Co Form S-1/A** (EDGAR CIK 2039139) — the primary disclosure of the hub capacity +
   the MARA take-or-pay contract (already cited; ingest for the corpus).
2. **MARA Holdings 10-K / operations updates** — resolve the 2026 energization status `[open]`.
3. **Hancock County Recorder** — deed(s) for the 110-ac (2026-03-05, $5.9M) + 40-ac + 74-ac
   parcels: grantee vehicle, parcel IDs, acreage (epic #1265 places sub-issue).
4. **OEPA Air PTI** (NWDO eSuite) — One Power / MARA generator-bank permit(s), Allen Township.
5. **OEPA CGP stormwater NOI** — the North Findlay Industrial Park construction coverage.
6. **OHD000001 comment docket** — scan for Findlay-area commenters.
7. **PJM / PUCO / AEP interconnection** — the +300 MW standalone-interconnection instrument (epic
   #1265 grid sub-issue).
8. **Ohio SOS** — One Power Co and MARA Holdings, Inc. registrations.

## Sources

- One Power Co Form S-1/A (EDGAR CIK 2039139): [sec.gov/Archives/edgar/data/2039139/…/onepowercompany-sx1a.htm](https://www.sec.gov/Archives/edgar/data/2039139/000162828025002278/onepowercompany-sx1a.htm)
- MARA release, 2024-11-11: [ir.mara.com/news-events/press-releases/detail/1375](https://ir.mara.com/news-events/press-releases/detail/1375/)
- OnSite acquires One Power (2026-02-16): [onsitepartners.com/news/onsite-partners-acquires-one-power-company](https://onsitepartners.com/news/onsite-partners-acquires-one-power-company-to-expand-distributed-generation-portfolio/)
- OnSite + AEP + Basalt (2025-06-12): [onsitepartners.com/news/onsite-partners-aep-and-basalt-infrastructure-partners-collaborate](https://onsitepartners.com/news/onsite-partners-aep-and-basalt-infrastructure-partners-collaborate-to-bring-power-solutions-to-data-centers/)
- The Ohio Register (2026-03-25, land assembly + speculation, use for leads not primary facts): [theohioregister.com/findlay-hiding-looming-data-center-project](https://www.theohioregister.com/findlay-hiding-looming-data-center-project/)
- Baxtel MARA listing (secondary): [baxtel.com/data-centers/mara-holdings](https://baxtel.com/data-centers/mara-holdings)
- OHD000001 hearing slides (OEPA): [dam.assets.ohio.gov … OHD_DataCenter_PP-FINAL-PresentationFull-Slides](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/Data_Centers/OHD_DataCenter_PP-FINAL-PresentationFull-Slides-Correct.pdf)
