# Troy–Piqua / Miami County, OH — Data-Center Activity Register

Discover-and-pin register for the Troy–Piqua watershed point — the upper **Great Miami River**
corridor. Status **as of 2026-07-02; updated 2026-07-13** (#1482 facility, #1483 parcels, #1485
leads board, #1486 water & regulatory watch, #1487 governance & opposition watch). Tags are BOSC evidentiary discipline: `[verified]` =
on-record in a government/primary source (often two+), `[reported]` = credible secondary /
investigative journalism, not officially confirmed, `[reference]`, `[inference]`, `[open]`.
**Nothing here is in the BOSC corpus yet** — this records the *verified public record* and the
specific primary instruments to *pull*. Every figure is cited; none is fabricated.

## Disambiguation guardrail

The confirmed project is in the **City of Piqua**, Miami County, OH — upper Great Miami basin.
The developer of record is a shell (J5 LLC / Shaytura LLC); the reported hyperscaler backer
(Meta) is **not** officially confirmed and is tagged `[reported]`, never `[verified]`. `[verified]`

Two further disambiguation guards apply to the governance record (§ *Opposition / litigation*):

- **The City of Troy's Unified Development Code data-center provisions are a distinct thread** from
  Piqua's Project Klondike. Troy (the county seat, Piqua's downstream sister city) is writing
  data-center *siting rules* into a new UDC; that is regulatory pre-positioning, **not** a disclosed
  Troy data-center project. Do not conflate the two. `[open]` on whether any Troy project exists.
- **The statewide policy threads** (the data-center-ban ballot amendment, the OTCA sales-tax-exemption
  pause) are Ohio-wide context, not Piqua-specific instruments — filed here as context, never
  cross-referenced as a connection to J5/Klondike unless an instrument ties them.

## 1 — "Project Klondike" (Piqua I-75 Business Park data-center campus)

- **Developer of record:** J5 LLC, doing business as Shaytura LLC — stated on the City of Piqua's
  official project page ("securing site entitlements … to shield business plans from
  competitors"). `[verified]` Source: piquaoh.gov/1673.
- **Reported backer:** Meta Platforms (Facebook). `[reported]` — attribution originates with
  Hunterbrook's investigation, which traced J5 LLC's corporate filing to Meta's Menlo Park HQ
  address (1601 Willow Road). Meta has not publicly confirmed; the City cites an NDA and has not
  named the owner; DCD names only J5/Shaytura. **Do not assert Meta as verified.**
  - **Corporate-filing refresh (2026-07-11):** the prior Nevada-vs-Delaware ambiguity resolves as
    **Delaware-formed, Nevada-foreign-qualified** (not a contradiction — the two prior summaries
    were each describing a different filing layer). `[reported]` Manager named as **David Kling**
    (Meta's then-VP/Deputy General Counsel per a 2021 SEC filing). `[reported]` Signatory
    **Pamela Gregorski**, a Corporation Service Company (registered-agent vendor) manager who
    signs 78 OpenCorporates entities including 4 already-confirmed Meta data-center fronts
    elsewhere (Orla LLC/IN, Laidley LLC & Pelican Leap LLC/LA, Wurldwide LLC/TX) — this is
    **pattern evidence, not a Piqua-specific confirmation**. `[inference]` **Disambiguation guard:
    never merge the J5 LLC / Shaytura LLC entity record with a Meta entity in the graph** — the
    Meta attribution stays `[reported]` end-to-end, regardless of how strong this pattern reads.
  - **Prior-ownership lead (uncorroborated):** a single non-primary source (thislocallife.com)
    reports the land was first held by a "Piqua Land Company" tied to New Albany Company (NACO)
    before transfer to J5 LLC. `[reference]`, uncorroborated — a lead only, not independently
    confirmed; pending a primary deed-record check (Miami County Auditor/Recorder) — see
    Instruments to pull.
- **Project codename:** "Project Klondike" — `[reported]`, appears firmly in opposition coverage
  but not on the City page, DCD, or cleanview; origin (filing vs. community-coined) is `[open]`.
- **Location:** north of Farrington Road, east of Washington Road, in the Piqua I-75 Business &
  Industrial Park (near I-75 exit 78), City of Piqua. `[verified]` Source: piquaoh.gov; DCD.
- **Acreage — RESOLVED by the Miami County auditor pull (#1483, 2026-07-13).** The acreage gap was
  a **nested-scope** question, not a missing fourth parcel:
  - **Developer-owned campus = 607.842 ac** `[verified]` — the three parcels now deeded to **J5 LLC**
    (owner of record): `N44-101834` (359.475 ac, 2675 W Farrington Rd), `N44-101770` (245.367 ac,
    2305 Farrington Rd W), `N44-101846` (3.0 ac, N Washington Rd). Two of the three carry a
    **2025-12-24 conveyance for $62,234,725**; J5's auditor mailing is **52 E Gay St, Columbus OH**.
    This equals the "~607-ac phase-one" figure — it is the actual campus, committed as
    `data/reference/troy-piqua/parcel-assemblage.geojson`. Source: Miami County auditor CAMA
    (`parcel_joined` layer 0).
  - **+ adjacent J3 Development LLC** (`N44-101772`, 93.105 ac, 2332 W Farrington Rd) → 700.947 ac.
    Same `M40-WA022` auditor split lineage as the J5 parcels and physically adjacent, but a **different
    mailing** (Cincinnati, not J5's Columbus), so common control is `[inference]` — a **lead**, not
    committed to the assemblage. Worth confirming via OpenCorporates / a common registered agent.
  - **Full `M40-WA022` split-parent series = 963.794 ac** across 7 parcels `[verified lineage]` —
    262.847 ac stays farm-owned in Washington Twp (Hines, Holfinger ×2), never sold to the developer.
  - The City page's **~1,026-ac** figure = the cumulative **annexation record** (three tracts annexed
    2022–2025) and the **~1,200-ac** figure = the whole **I-75 Exit 78 Business & Industrial Park** —
    both LARGER scopes than the developer-owned campus. The campus (owner of record) is ~608 ac.
    `[verified]`/`[inference]` per the levels above; full reconciliation in
    `data/extracted/troy-piqua/bosc-site-footprint.yaml`.
- **Building program:** two buildings ~350,000 ft² each (~700,000 ft² total). `[verified]`
- **Investment:** "$1 billion plus" fixed-asset investment, plus ~$76M developer-funded utility
  infrastructure (water, wastewater, power, roads); projected >$180M community revenue over 30
  years. `[verified]` Source: piquaoh.gov; DCD.
- **Power draw (MW):** ~180 MW peak IT for the initial two buildings. `[reported]` — candidate-site
  trackers (ryangrissinger, cleanview, stopohiodatacenters); not on the City page or DCD
  ("capacity weren't shared"). Official MW is `[open]`.
- **Power utility (split by phase):** construction = Piqua Power System (municipal utility, an
  American Municipal Power member); long-term operations = **AES Ohio** (investor-owned).
  `[verified]` Source: piquaoh.gov. *Note: it is AES Ohio, NOT AEP Ohio.* Piqua runs its own
  municipal electric utility (Piqua Municipal Power System; EIA-861 utility #15095). `[verified]`
- **Jobs:** ~1,000+ average annual construction over 3–5 years; ~50+ permanent on-site (~$100,000+
  avg, ~$6M payroll); ~400+ contracted-services roles. `[verified]` Source: piquaoh.gov.

### Financial / tax instruments

- **Two stacked 100% exemptions:** 15-year, 100% CRA abatement on the improvements (buildings)
  valuation increase + 30-year, 100% real-property exemption via a TIF fund (land + buildings).
  `[verified]` Source: DCD; piquaoh.gov; Miami Valley Today.
- **PILOT:** ~$735,000 per building per year during the 15-year abatement (~$1.47M/yr for two
  buildings). `[verified]`
- **Instruments = CRA + TIF + Opportunity Zone;** no enterprise-zone abatement found. Land-value
  taxes are not abated; schools projected >$1M/yr additional. `[verified]` Source: MVT; piquaoh.gov.
- **Ohio data-center sales-tax exemption (OTCA, ORC 122.175):** `[open]` for this project — no
  primary record of an OTCA exemption granted (or applied for) by J5/Piqua. Governor DeWine directed
  a **pause on new OTCA data-center exemption approvals effective 2026-05-27**, pending the
  legislature's Joint Data Center Committee review; competing bills are unresolved — HB 975 (end the
  exemption 2026-10-01) vs. SB 374 (end 2027-10-01). `[reported]`. Do not assume an exemption exists.
  This is a **statewide** thread (context, not a J5 instrument); lead `OTCA-PAUSE` (#1487).
- **NDA:** the company "required a non-disclosure agreement" (City page) — but Miami Valley Today
  records commissioners saying they "never signed an NDA." The exact NDA signatory is contested.
  `[verified]`/contested.

### Water / hydrology hook

- **Contested draw figure (flag this tension):** the negotiated Water & Wastewater Agreement
  (effective Jan 23, 2026) reserves up to 500,000 GPD (Tier I) scaling to 2.0 MGD (Tier II / full
  operation) — ~30% of Piqua's ~6.75 MGD permitted intake; ~1.0 MGD wastewater reserved.
  `[verified]` Source: MVT; civiccapacity.com. **But** the City's public FAQ describes a
  closed-loop cooling system with only an "initial fill-up," occasional top-offs, and domestic-only
  ongoing use. `[verified]` These two framings conflict, and **neither has been reconciled against
  the executed agreement text** — the reserved figure and the closed-loop framing are each
  `[verified]` as *summaries*, but which one governs the consumptive-use screen is `[open]`. Pin to
  the instrument itself, not either summary. Tracked as standing lead `WATER-AGREEMENT` (#1486).
- **WWTP headroom vs. the reserved wastewater draw:** Piqua WWTP (Ohio EPA 1PD00008\*WD / NPDES
  OH0027049; renewal eff. 2022-09-01 – 2027-08-31) is design **8.7 MGD** with an actual mean flow of
  **~3.224 MGD** (37.1% of design, 2023 DMR). `[verified]` Source: `1PD00008.fs.npdes.yaml`;
  `wwtp-oh0027049.dmr.yaml`. The reserved ~1.0 MGD data-center wastewater is ~11.5% of design and
  sits within the ~63% unused headroom **on paper** — but whether it absorbs into existing headroom
  or implies a permit modification has **not** been checked against the fact sheet's WLA basis (the
  low-flow denominator). `[inference]`, unresolved: the committed fact-sheet extraction currently
  captures only the header pages, so the WLA table itself is a pull target. Lead `WWTP-WLA` (#1486).
- **Water source:** Piqua municipal water — City-owned surface-water plant ($55M, online 2018),
  ~7.0 MGD rated / ~6.7 MGD permitted, PWSID OH5501211; sources are the Great Miami River (~58%,
  intake at RM 118.5), Ernst gravel pit (~30%), Piqua Hydraulic canal (~12%). `[verified]`
- **Wastewater / receiving water:** Piqua WWTP (4.5 MGD secondary-treatment rating; **8.7 MGD
  hydraulic design flow** per the 2023 DMR — the two are different bases, not a contradiction, and
  the 8.7 MGD figure is the permit/WLA denominator used in the headroom bullet above) discharges to
  the Great Miami River at RM 114.3 under Ohio EPA NPDES permit 1PD00008 (2022 renewal fact sheet);
  data-center wastewater routes to the Piqua Municipal Wastewater System (new gravity sewers
  Washington→Farrington Rd). `[verified]` Source: Ohio EPA 1PD00008 fact sheet; DMR.
- **Data-center stormwater NPDES:** `[open]` — not found; Ohio EPA draft general permit **OHD000001**
  (statewide data-center wastewater discharge) is the likely vehicle. Its comment period closed
  2026-01-16 (hearing 2025-12-17); as of the 2026-07-11 refresh the Director's **final action was
  still pending** — not finalized, and no Piqua/J5-specific coverage found under it. `[reported]`/
  `[open]`. Once issued, confirm whether it covers this facility. Lead `OHD000001` (#1486).

### Hydrology screen

- **Receiving water:** Great Miami River, upper reach at Piqua (RM 114.3 outfall / RM 118.5
  intake). The basin-screen mainstem proxy is gage 03274000 (Great Miami River at Hamilton OH,
  mouth-ward). `[verified]`
- **Abstraction vs. flow:** the reserved up-to-2.0 MGD draw (3.1 cfs) is a real quantity to screen
  against the upper Great Miami low flow near Piqua; the closed-loop / domestic-only framing (if
  accurate) would make consumptive use far smaller. `[inference]` — the actual consumptive figure
  is undetermined until the agreement's true operating draw is pinned; **no assimilative
  conclusion drawn.** `[open]`

### Regulatory record (status as of 2026-07-02)

- **Approval:** Piqua City Commission 4–0 on November 3, 2025 (public hearing; passed as an
  emergency resolution waiving three readings). `[verified]` Supporting school-compensation / TIF
  agreements passed by Piqua City Schools & Upper Valley Career Center boards October 2025; all
  agreements executed January 23, 2026; a further resolution April 9, 2026. `[verified]`
- **Zoning/annexation:** the **cumulative annexation record** totals **~1,026 acres** annexed and
  zoned heavy-industrial 2022–2025 (Statler Farms annex Jun 8, 2022 / zone Sep 20, 2022; 329.824-ac
  parcel annex Sep 19, 2024 / zone Jan 28, 2025; 33-ac parcel annex Mar 13, 2025 / zone May 20,
  2025). `[verified]` Source: piquaoh.gov (project page; annexation/zoning timeline). This is a
  **larger scope than the developer-owned campus** (~607.8 ac, above) — the annexed land was
  re-platted and only part sold to J5 LLC; the ~1,200-ac City figure is the whole business park.
  The ~174-ac "gap" was a scope artifact, now resolved (see Acreage, above).
- **Operations target:** ~December 2029 per a candidate-site tracker. `[reported]` — not on the
  City page (which states no target).
- **Ohio EPA air PTI (backup generators):** `[open]`, confirmed-negative as of 2026-07-11 — a
  direct search of OEPA eSuite/DAPC for "J5 LLC" / "Shaytura LLC" / the Farrington Road address
  found no filing. A clean dated no, not a gap. Re-check on the next sweep; a filing could still land
  ahead of construction. Lead `AIR-PTI` (#1486).
- **NPDES stormwater construction permit:** `[open]` — no construction general-permit NOI /
  site-specific coverage found for the ~607.8-ac campus. A filing would be expected ahead of
  earthwork; stays tracked until found or a dated negative is recorded. Lead `CONSTRUCTION-SWPPP`
  (#1486).
- **Construction/permanent power vote (2026-07-07):** the Piqua Commission approved a
  construction-power agreement (city to supply up to 10 MW temporary power during construction,
  ~$5.13M infrastructure cost paid by J5 via escrow) and gave first reading to a 40-year AES Ohio
  franchise ordinance for permanent service — approved **3–1**, with **Commissioner Paul Simmons
  dissenting** (the first recorded Commission dissent on this project; the original November 2025
  approval was 4-0). `[verified]` Source: Dayton Daily News, "Piqua takes step toward powering
  planned data center," 2026-07-09. Confirms the power-utility split already on record above:
  Piqua Power System (AMP muni) for construction, AES Ohio for the 40-yr permanent term.

### Opposition / litigation

- **Organized opposition:** "Save Piqua" (leader Cree St. Meyer); "Stand With Piqua" rallies; a
  petition with ~2,500+ signatures (water, noise, light, electric costs, air quality, property
  values). `[verified]` Source: WHIO; Dayton247Now; MVT.
- **Litigation — no suit filed as of 2026-07-11.** Save Piqua retained counsel and is fundraising
  (~$300,000 GoFundMe) toward an injunction. `[reported]` Source: WHIO, 2026-06-02. **No lawsuit has
  been filed as of 2026-07-11** — an indirect check of the Miami County Case Search portal found no
  docket. `[open]` on any actual filing. *Next check:* re-query Miami County Case Search. If a suit
  lands, ingest the complaint and open a litigation register (as Urbana's Thor v. Urbana thread was).
  Lead `SAVE-PIQUA-SUIT` (#1487).
- **Moratorium:** demanded by organizers but no evidence the City adopted one. `[open]`/no.
- **Statewide ballot amendment — RESOLVED negative for 2026.** The proposed "Ohio Prohibition of Data
  Center Construction Amendment 2026" **did not qualify** for the 2026 ballot: Conserve Ohio had only
  ~73,031 of the required 413,488 signatures (44 of 88 counties, ~17%) by the 2026-07-01 deadline.
  Organizers publicly shifted to a **2027** attempt (signatures do not expire). `[reported]` Source:
  Ohio Capital Journal, 2026-06-19. *Next check:* the 2027 signature cycle. Statewide context — not a
  Piqua instrument. Lead `BALLOT-2027` (#1487).
- **Troy's (the city) Unified Development Code data-center provisions — a DISTINCT thread.** The City
  of Troy (county seat, downstream sister city) is separately writing data-center siting rules into a
  new UDC — a 10-acre minimum lot and a 1,000-ft setback from hospitals/schools/parks; a 2026-01-27
  public meeting drew 100+ opposed residents. `[reported]` Source: Troy Times Tribune, 2026-01-27.
  This is regulatory pre-positioning, **not** a disclosed Troy data-center project — do not conflate
  with Project Klondike (Piqua), same discipline as the Meta-attribution guard above. `[open]` on
  whether any actual Troy project sits behind it, and on the UDC adoption vote. *Next check:* Troy
  City Council UDC adoption. Lead `TROY-UDC` (#1487).
- **Advocacy sites (leads only, not verified):** stopohiodatacenters.org, piquadata.center,
  piquawatch.com, change.org petition, hntrbrk.com (investigative, higher credibility but not
  official). *One circulating "Epstein ties" piece is unverified — treat with strong skepticism.*

## 2 — No other confirmed Miami County activity pinned yet

Troy (the county seat's sister city, downstream on the Great Miami) has no confirmed data-center
campus pinned as of 2026-07-02. `[open]` — re-sweep on the next pass.

## 3 — What `SiteProfile.facility` now carries (#1482)

`_TROY_PIQUA.facility` is a **site-plan-grounded** `SiteFacility` (contrast Lima / Fort Wayne,
which are air-permit-grounded — same distinction the Urbana Technology Hub precedent, #1327,
established): it records the disclosed non-power attributes (`facility_type`,
`gross_floor_area_sqft=700000`, `disclosed_investment_usd`, `disclosure_citation`) and an
`[inference]` IT-load screening bracket (`it_load_citation`), with **`genset_count` / `genset_mw`
/ `air_permit_citation` left `None`** (no disclosed generation, confirmed-negative air-PTI
search). The bracket is **52.5 MW low / ~113.75 MW central / 175 MW high**, from the disclosed
700,000 sq ft gross floor area × the same 75–250 W/sq ft whole-building screening density band
Urbana uses — **not** bounded by a disclosed cooling design the way Urbana's is, because this
site's `cooling_model` stays `unknown` (the closed-loop-FAQ-vs-2.0-MGD-agreement conflict is
#1486's to resolve, not this one's). The ~180 MW candidate-tracker figure (§1, "Power draw") sits
just above (~3%) the top of this bracket — a `[reported]` cross-check only, never a disclosure.
This flips the `facility` readiness domain `absent` → `seeded`/`live` (once the
`economics-demand-pressure` feed is generated) and is recomputed at every `watermark export`.

## Standing watch & leads board

The open threads on this register are seeded to the site's leads board —
`data/site/troy-piqua/leads.yaml` (#1485) — so they surface in the bundle's `leads` feed and flip
the `story` readiness domain `absent → seeded` (troy-piqua is not yet in `STORY_SLUGS`; story
*registration* is a separate, later editorial call). Each lead is dated and sourced; nothing is
asserted above its tag. Next-check triggers:

| Lead | Thread | Next check |
| --- | --- | --- |
| `WATER-AGREEMENT` | 2.0 MGD reserve vs. closed-loop FAQ — unreconciled | pull the executed 2026-01-23 agreement text |
| `OHD000001` | statewide data-center NPDES general permit | Director's final action + Piqua/J5 coverage |
| `WWTP-WLA` | reserved 1.0 MGD wastewater vs. 1PD00008 headroom | extract the fact-sheet WLA table |
| `CONSTRUCTION-SWPPP` | construction-stormwater NOI | re-sweep OEPA eSuite before earthwork |
| `AIR-PTI` | backup-generator air PTI (confirmed-negative 2026-07-11) | re-run the eSuite/DAPC search |
| `SAVE-PIQUA-SUIT` | opposition litigation (no suit as of 2026-07-11) | re-query Miami County Case Search |
| `BALLOT-2027` | statewide ban amendment (failed 2026) | the 2027 signature cycle |
| `TROY-UDC` | Troy's UDC data-center provisions (distinct thread) | Troy City Council adoption vote |
| `OTCA-PAUSE` | statewide OTCA exemption pause | HB 975 vs. SB 374 resolution |
| `KLONDIKE-J5` | Meta backer — `[reported]`, not primary-confirmed | independent, non-Hunterbrook instrument |
| `KLONDIKE-J3` | adjacent J3 Development LLC common control (`[inference]`) | OpenCorporates / shared agent |
| `KLONDIKE-DEED` | recorder deed instrument numbers | Miami County Recorder pull |

## Instruments to pull (priority order)

1. **J5 LLC / Shaytura LLC corporate filing** — resolve the state of formation (Nevada vs.
   Delaware) and confirm the Menlo Park address (the Meta attribution's load-bearing document).
   **Update (2026-07-11):** the state-of-formation question resolves as Delaware-formed / Nevada-
   foreign-qualified (not a contradiction); a manager (David Kling) and registered-agent signatory
   (Pamela Gregorski, CSC) are named `[reported]`/`[inference]` (see §1, "Corporate-filing
   refresh"). The primary filing document itself is still not ingested into the corpus — that
   instrument, and independent (non-Hunterbrook) confirmation of the Meta linkage, stay the pull
   target.
2. **Piqua Land Company / New Albany Company (NACO) prior-ownership lead** — confirm or refute via
   the Miami County Auditor/Recorder deed chain (currently a single non-primary, uncorroborated
   source; see §1).
3. **Miami County Auditor / GIS — DONE (#1483, 2026-07-13).** Pulled the `parcel_joined` layer 0:
   the campus is the **3 J5 LLC parcels = 607.842 ac** (`N44-101834`/`N44-101770`/`N44-101846`),
   committed as `data/reference/troy-piqua/parcel-assemblage.geojson` with owner/acreage/transfer/
   split-lineage. The ~174-ac "gap" was a **nested-scope artifact** (campus ⊂ annexation record ⊂
   business park), not a fourth parcel (see Acreage). **Remaining `[open]`:** (a) confirm/refute the
   adjacent **J3 Development LLC** parcel (`N44-101772`, 93.1 ac) as a related SPE — same `M40-WA022`
   split lineage, different Cincinnati mailing; (b) pull the recorder **deed instrument numbers** for
   the J5 conveyances (the auditor shows sale date/amount but not the OR book/page or instrument #).
4. **City of Piqua** — the executed Water & Wastewater Agreement (Jan 23, 2026) to reconcile the
   2.0 MGD reservation vs. the closed-loop/domestic-only public messaging (#1486).
5. **OEPA air PTI** — re-check periodically for a backup generator PTI filing (SWDO, Miami County,
   entity "J5 LLC"); confirmed-negative as of 2026-07-11.
6. **Ohio EPA / EPA ECHO** — the Piqua WWTP NPDES 1PD00008 fact sheet (committed reference) and any
   data-center stormwater coverage under OHD000001.
7. **OTCA** — confirm whether any data-center sales-tax exemption was granted.

## Sources

- City of Piqua (project page, primary): [piquaoh.gov/1673/Data-Center-Project](https://www.piquaoh.gov/1673/Data-Center-Project)
- City of Piqua Power System: [piquaoh.gov/228/Power-System](https://www.piquaoh.gov/228/Power-System)
- City of Piqua Source Water Assessment (PWSID OH5501211): [2025 report PDF](https://www.piquaoh.gov/DocumentCenter/View/3012/2025-Source-Water-Assessment-Report-PDF)
- Ohio EPA (Piqua WWTP NPDES 1PD00008, Great Miami RM 114.3): [1PD00008 fact sheet PDF](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/1PD00008.fs.pdf)
- Ohio EPA (data-center general permit OHD000001): [wastewater-discharges-from-data-centers--general-permit](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit)
- Data Center Dynamics: [data-center-project-coming-to-piqua-ohio](https://www.datacenterdynamics.com/en/news/data-center-project-coming-to-piqua-ohio/)
- Miami Valley Today (commission plans): [piqua-commission-hears-plans-for-new-data-center](https://miamivalleytoday.com/piqua-commission-hears-plans-for-new-data-center/)
- CivicCapacity (water/wastewater agreement): [water-world-what-was-negotiated](https://www.civiccapacity.com/p/water-world-what-was-negoitated-between)
- WHIO (legal action): [community-group-planning-take-legal-action-over-piqua-data-center-plans](https://www.whio.com/news/local/community-group-planning-take-legal-action-over-piqua-data-center-plans/J2HTZOA2XZDFPBILJ646NNTTY4/)
- OpenEI (City of Piqua EIA utility ID 15095): [City_of_Piqua,_Ohio](https://openei.org/wiki/City_of_Piqua,_Ohio_(Utility_Company))
- Ryan Grissinger tracker (180 MW, ~Dec 2029): [OH-DC-0028](https://ryangrissinger.com/issues/data-centers/OH-DC-0028)
- Hunterbrook (Meta attribution, investigative): [hntrbrk.com/meta-data-centers](https://hntrbrk.com/meta-data-centers/)
- Stop Ohio Data Centers (advocacy, leads only): [stopohiodatacenters.org](https://stopohiodatacenters.org/)
- Dayton Daily News (2026-07-07 construction-power/franchise vote): "Piqua takes step toward
  powering planned data center" (2026-07-09)
- OpenCorporates (J5 LLC / Shaytura LLC entity filings; Pamela Gregorski registered-agent
  cross-reference) and Meta's 2021 SEC filing (David Kling, VP/Deputy General Counsel) —
  corporate-filing refresh, 2026-07-11
- thislocallife.com (Piqua Land Company / New Albany Company prior-ownership lead) — a single
  non-primary source, uncorroborated
