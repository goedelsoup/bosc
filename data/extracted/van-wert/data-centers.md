# Van Wert / Van Wert County, OH — Data-Center Activity Register

Discover-and-pin register for the Van Wert watershed point — the upper Maumee basin (Town Creek
→ Little Auglaize → Auglaize → Maumee). Status **as of 2026-07-02**. Tags are BOSC evidentiary
discipline: `[verified]` = cited public source (two+ independent or a primary instrument),
`[reference]` = single credible-media source, `[inference]`, `[open]`. **Nothing here is in the
BOSC corpus yet** — this records the *verified public record* and the specific primary instruments
to *pull*. Every figure is cited; none is fabricated.

> **Land committed (2026-07-31, #1403):** the campus geometry is now in the corpus —
> `data/reference/van-wert/parcel-assemblage.geojson` + `data/extracted/van-wert/bosc-site-footprint.yaml`,
> the **five Van Wert County parcels deeded to `QTS VAN WERT LLC`** in June 2026, **900.59 ac
> deeded / 901.502 ac planar**, contiguous. This activates the **places** readiness domain and
> closes the "deed grantee" `[open]` below; it also corrects the school-taxing-body line (the
> campus straddles **two** districts) and the SSURGO HSG on the profile (flat `D` → dual `C/D`).
> The **grantor** and the recorder instrument numbers stay `[open]` — the county's parcel layer
> carries neither, so the Marsh Foundation → Thor → QTS chain is still #1401's pull.
>
> **Water record committed (2026-08-01, #1406):** the municipal water instruments are now in the
> corpus — NPDES **2PD00006\*WD**, the modification that put the CSO Long Term Control Plan on a
> dated construction schedule effective 2026-07-01, plus its draft public notice
> (`data/documents/oepa/van-wert/`, extractions under `data/extracted/oepa/van-wert/`). The
> standing register is `data/extracted/van-wert/water-watch.yaml`. Its finding: **Van Wert drinks
> Town Creek and discharges to Town Creek**, on one NHDPlus flowline, with the five CSO outfalls
> in between — see the water section below.
>
> **Profile pin (2026-07-13, #1402):** the campus below is now registered as a SITE-PLAN-grounded
> `SiteFacility` on the Van Wert `SiteProfile` (the #1327 Urbana precedent) — the 500 MW is carried
> as a `[reference]` bracket (never a disclosure; QTS declines to state capacity), with closed-loop-dry
> cooling and the ~$10B investment. This activates the **facility** readiness domain (the
> `economics-demand-pressure` feed; `tier` backdrop → case). The pin cites this public record; the
> grounding *instruments* (ordinances, hearing record, deeds, OPSB LON) remain the ingest job of #1401.

## Disambiguation guardrail

The confirmed project is the **Van Wert Mega Site**, City of Van Wert / Van Wert County, OH —
the ~1,500-acre Marsh Foundation industrial site north of U.S. Route 30. Van Wert County drains
to the Maumee (Lake Erie basin), distinct from the Great Miami / Scioto data-center clusters.
`[verified]`

## 1 — QTS "Van Wert Mega Site" campus

- **Operator / end user:** QTS Data Centers (legal entity QTS Realty Trust, LLC; Overland Park,
  KS), Blackstone-owned since its 2021 take-private. Publicly named as the end user late
  May–June 2026. `[verified]` Source: q.com/data-centers/van-wert; DCD; VW Independent.
- **Land developer:** Thor Equities Group, via its data-center division Form8tion ("Form8tion
  Van Wert"). `[verified]` Source: GlobeNewswire (Aug 19, 2025); citybiz; DCD.
- **Seller:** The Marsh Foundation (local non-profit; owner of the Mega Site). `[verified]`
- **Project codename:** none disclosed. `[open]`
- **Deed grantee / shell LLC:** **`QTS VAN WERT LLC`** — the operator holds title directly, on all
  five campus parcels. `[verified]` (#1403; Van Wert County Auditor CAMA, read 2026-07-31.) The
  intermediate Thor SPE **VAN WERT EAST OWNER LLC**, which held the 221.15-ac anchor as recently as
  a 2026-07-10 probe, is gone from the county roll; a countywide owner scan returns **zero** parcels
  for `THOR`, `FORM8TION`, `VAN WERT EAST` or `EQUITIES`, so no surviving nominee holding exists.
  The **grantor**, the recorder instrument numbers and the deed book/page stay `[open]` — the
  county's parcel layer carries none of them; pull the Van Wert County Recorder deeds.
- **Location:** Van Wert Mega Site — north of U.S. Route 30, between Stripe Road and Mendon Road
  (broader Mega Site bounded by Hwy 30, Gilliland Rd, Marsh Rd, US-224). `[verified]`
- **Acreage (evolving):** Thor's initial acquisition ~221 acres (Aug 2025); ~962 acres annexed by
  the City May 11, 2026; QTS campus footprint quoted at 902 acres, up to seven buildings.
  `[verified]` (221 ac = phase-1 land buy; 902/962 ac = full campus/annexation.)
- **Acreage, now instrument-grounded (#1403):** the committed holding is **900.59 ac deeded /
  901.502 ac planar** across five contiguous parcels — `17-034718.0000` (362.23 ac),
  `.0100` (221.15, the anchor), `.0200` (157.84), `12-034459.0000` (128.13),
  `33-047500.0000` (31.24). `[verified]` That meets the quoted **902 ac** to **0.16%** — the first
  independent confirmation of the operator's own figure — but falls **61.4 ac (6.4%) short** of the
  **~962 ac annexed**. That gap is `[open]`: road right-of-way inside the annexed area and non-QTS
  parcels inside the annexation description are both live explanations and neither is established,
  because the ordinances' legal descriptions are not in the corpus.
- **Consideration (#1403):** four parcels (679.44 ac) conveyed **2026-06-16** at a recorded
  **$39,117,825**, the anchor **2026-06-18** at **$110,575,000** — exactly **$500,000 × its 221.15
  CAMA acres**, and a **10.6×** step over the ~$47,000/ac Thor paid ten months earlier. All warranty
  deeds. `[verified]` The four same-day parcels share one date and one amount, the signature of a
  single multi-parcel deed, so that figure is **not summed** across them and the campus's total
  consideration stays `[open]`.
- **Zoning:** annexed and zoned I-2 General Industrial with conditional data-center use (City
  Council, May 11, 2026). `[verified]`
- **Investment:** ~$10 billion total capital investment (QTS). `[verified]` Source: q.com; all
  outlets. (An early Feb 2025 report cited "$2B" before the scope grew.)
- **Power draw (MW):** up to 500 MW (Thor/Form8tion figure at land acquisition). `[reference]` —
  QTS's own page declines to confirm MW ("we don't disclose specific power capacity").
- **Power utility:** AEP Ohio (American Electric Power / Ohio Power Co). QTS states it will fund
  100% of the grid/energy infrastructure upgrades "at no cost to existing ratepayers." `[verified]`
- **Jobs:** >1,500 construction over the 5–6 year build (local building-trades unions);
  ~200 permanent full-time (q.com official; local coverage says 200–250). `[verified]`/`[reference]`.

### Financial / tax instruments

- **Projected local tax revenue:** ~$200 million — reported both as "over 20 years" (announcement)
  and "over 15 years" (March 2026 local piece); horizon ambiguous. `[reference]`
- **CRA / TIF / PILOT / enterprise-zone specifics:** not publicly disclosed with dollar figures or
  terms. Van Wert County is entirely within an Enterprise Zone (up to 100% real-property abatement
  for up to 15 years) and has CRA authority, but no executed abatement/PILOT ordinance with
  rates/years was found. `[open]` — pull the Van Wert City Council / County Commissioners
  economic-development agreements.
- **School taxing bodies — the campus straddles TWO districts** (#1403, correcting the earlier
  single-district `[reference]`): **772.46 ac Lincolnview** Local School District (the four
  Ridge/Hoaglin parcels) and **128.13 ac Van Wert City** School District (`12-034459.0000`).
  `[verified]` — two independent lines for the Lincolnview four (the auditor's own district name
  carries the "(LV)" suffix, and the county SchoolDistrict layer returns Lincolnview at each
  parcel's interior point); for `33-047500.0000` only the spatial join is available. Vantage Career
  Center is also a taxing body. A CRA school-compensation agreement for a project of this payroll
  size would therefore have to reach **both** boards, not one. The auditor also has all five
  parcels in Van Wert **Corporation** tax districts (12, 17, 33), consistent with the annexation,
  while the county's district *polygon* layer still shows townships — a currency gap in the
  polygons, not a contradiction.
- **Developer-funded infrastructure (not a tax instrument):** ~$25 million for Bonnewitz Crossing
  (N. Washington St. to Mendon Rd.) and Mendon Road overpass improvements — developer-funded.
  `[reference]`
- **Legal counsel retained by City/County:** Vorys Sater Seymour and Pease LLP; Bricker Graydon
  LLP. `[reference]`

### Water / hydrology hook

- **Water source:** City of Van Wert municipal water — the City approved the initial closed-loop
  fill; QTS says it is still "in discussions to identify the best solutions." `[verified]`/`[open]`
  Source: vanwert.org/water-treatment; q.com.
- **Cooling:** closed-loop (Danfoss-patented equipment); ongoing consumption small. Operational
  draw ≈ 660,000 gallons/yr (single local timeline source); QTS characterizes ongoing use as
  "about what 4 households use per month." `[reference]`
- **Cooling-cycling reconciliation (B2, #1682):** the A3 harness
  (`watermark cooling-reconcile`) tested the closed-loop-dry claim against the record. With no
  metered makeup (the Ohio DNR withdrawal registry has no Van Wert County pull built) and no
  facility-own blowdown (OHD000001 is a draft permit, unlinked to the facility by name), the
  outcome is a **`gap`** — the pin stays `closed_loop_dry` / `[reference]`, **not** upgraded to
  `document`-grade. The disclosed ~660,000 gal figure is a single-source self-report (not a
  metered instrument, so it cannot corroborate the operator's own claim), and the same number is
  framed both as an *annual* operational draw and a *one-time* initial fill — that fill-vs-annual
  ambiguity is the unresolved **#1409** discrepancy, quantified here, not settled. The initial-fill
  volume + a metered water-service use are sharpened into a C2 records request (#1688 / #1409). See
  `data/reference/oepa/cooling-reconciliation.yaml`. `[open]`
- **Wastewater path / NPDES:** not disclosed for the facility; no facility-specific NPDES number
  found. `[open]`
- **Receiving water:** Van Wert's stream is Town Creek → Middle Creek → Little Auglaize River →
  Auglaize River → Maumee River (Lake Erie basin). HUC-12: Lower Town Creek (04100007 08 04);
  Ohio EPA river code 04-143. `[verified]` Source: Ohio EPA permit 2PD00006*WD fact sheet,
  composite sheets 49 and 52 (`data/documents/oepa/van-wert/2PD00006.f8aaad0a.pdf`).
  (The stream network above corrects an earlier line that omitted Middle Creek.)
- **The City drinks the creek it discharges to — one reach, three claims on it** (#1406). Van Wert
  City is the **only surface-water public water system in Van Wert County** (PWS **OH8100611**,
  community system, primary source `SW`, 10,846 served, active — EPA SDWIS via ECHO, extract
  2026-07-09) `[verified]`, and the City's own utilities page says outright that "the water that
  the people of Van Wert use and drink comes from Town Creek" `[reference]`. Snapped to NHDPlus v2
  through USGS NLDI on 2026-08-01, the **water plant, the city's second NPDES point and the WWTP
  outfall all fall on one 17.05 km flowline (COMID 15653063)** running south → north, with the
  **five CSO outfalls in between** (Wall St., First & Monroe, Main St., Central, Keplar — all
  discharging to Town Creek, coordinates in Part II.C of the permit). `[verified]` The intake side
  is therefore **upstream** of the CSOs and the outfall — nobody drinks this plant's effluent —
  but every claim on the creek's flow is a claim on the same water in sequence. `[inference]`
  And the buffer is thin: the City's reservoirs hold **1.01 billion gallons**, while the creek's
  recorded annual yield since 1951 runs from **180 million gallons to 1.26 billion** — a 7× spread,
  with the worst year delivering under a fifth of storage. `[reference]` Standing watch, with the
  compliance record and every open thread: `data/extracted/van-wert/water-watch.yaml`.
- **The municipal wastewater permit is under a CSO construction schedule as of 2026-07-01**
  (#1406). NPDES **2PD00006\*WD** (modification of the \*VD renewal; action 2026-05-18, Public
  Notice 221593, comment closed 2026-06-24, entered the Director's Journal 2026-06-30, effective
  2026-07-01, expires 2030-05-31) rewrote Part I.C around the CSO **Long Term Control Plan
  Compliance Assistance Plan** — the 2022 Completion Evaluation Report having found the 1999
  plan's ≤4-events-per-typical-year goal **not attained**. Four control projects (Blaine St.
  interceptor, **Town Creek siphon**, Bonnewitz pump-station weir, raising the CSO 010 weir six
  inches) are now dated obligations: **begin construction by 2026-08-01**, operational by
  2027-01-01, 24-month post-construction monitoring 2027-03 → 2029-03, completion evaluation
  2029-06-01. `[verified]` Whether construction actually began by that first date is `[open]` —
  and the same permittee's CSO Event Report, O&M Report and Combined Sewer Report schedule events
  have been recorded by ECHO as "unachieved and not reported" **continuously since early 2024**,
  with **zero formal enforcement actions and $0 in penalties**. `[verified]` (ECHO DFR OH0027910,
  read 2026-08-01, ICIS-NPDES extract 2026-07-24; **12 of the 13 quarters ECHO displays** carry a
  violation, the exception being 2023-Q4 — *not* "12 of 12", which is what the pre-ingest research
  had.)
- **Maumee TMDL phosphorus:** the plant carries an individual wasteload allocation of **1,000 kg
  total phosphorus for the critical season (March–July)** under the September 2023 Maumee
  Watershed Nutrient TMDL, and Part II.AE routes compliance to "the Maumee Watershed Total
  Phosphorus NPDES General Permit" — **the permit prints no general-permit number**, so binding
  that to the corpus's `OHP000001` is our identification, not the instrument's. `[verified]` Held
  at its own 15 kg/day monthly-average loading limit across the 153-day season the individual
  permit would allow 2,295 kg — **2.30× the allocation** — which is why the condition defers to
  the general permit and carries a reopener. `[inference]` The same permit's Part II.AE names the
  covered facility "**Defiance** Van Wert WWTP", boilerplate carried over from another permittee
  and printed verbatim in an issued instrument. `[verified]`

### Hydrology screen

- **Receiving water:** Town Creek / Little Auglaize (the Van Wert WWTP receiving reach is
  OH0027910 → Town Creek RM 13.87; design flow 4.0 MGD, peak hydraulic capacity 8.0 MGD;
  **outfall 001 at 40.8882410 N, -84.58437518 W** — permit 2PD00006\*WD and its draft public
  notice, #1406; see the Van Wert `SiteProfile`). `[verified]`
- **Nearest mainstem gage:** USGS 04186500 (Auglaize River near Fort Jennings) — on the Auglaize
  mainstem, **not** Town Creek/Little Auglaize; a Town Creek 7Q10 needs separate derivation.
  `[reference]`/`[open]`
- **Abstraction vs. flow:** the facility's specific discharge point / receiving water and a Town
  Creek 7Q10 are not disclosed (closed-loop + still-negotiated water/sewer). `[open]` — no
  assimilative screen possible until the outfall and a low-flow denominator are pinned.
- **Site drainage — Town Creek is NOT where most of this campus drains** (#1403). Intersecting the
  committed boundary with the Van Wert County GIS `Watersheds` layer splits the 901.5 planar acres
  **North Spice Run 371.54 ac (41.2%), Marsh Ditch 347.43 ac (38.5%), Van Wert Corp Ditch 1024
  102.81 ac (11.4%), Town Creek 61.88 ac (6.9%)**; 17.8 ac (2.0%) fall outside the layer.
  `[verified]` as the county's own mapping. All four are **petitioned county ditches** with their
  own numbers (North Spice Run #1966, Marsh Ditch #1592, Town Creek #1391, Ditch 1024), which makes
  the **Van Wert County Engineer / ditch-maintenance record** the instrument for the campus
  stormwater path. The site profile's `corridor_name` and `abstraction_gage` model Town Creek as
  the receiving reach, and Town Creek takes under 7% of the campus — the downstream routing of the
  other three into the Little Auglaize → Auglaize → Maumee is `[inference]` pending an NHD/NLDI
  trace and is a live lead, not a settled path.

### Regulatory record (status as of 2026-07-02)

- **Annexation + zoning:** ~962 ac annexed + I-2 industrial zoning + conditional data-center use,
  approved as emergency ordinances (waiving three readings), 6–0, May 11, 2026. `[verified]`
- **Timeline:** groundbreaking Q4 2026 (planned); first building operational Q1 2029; full buildout
  ~2032. `[reference]`
- **Ohio EPA air PTI (emergency generators):** `[open]` — QTS says generators are emergency backup
  only, tested monthly; no facility-specific PTI number found. Emergency generators <500 hr/yr may
  fall under permit-by-rule; otherwise a PTI/PTIO is required. Instrument to pull: OEPA air permits
  DB / eDoc, Van Wert County, entity "QTS" / "Form8tion" / shell LLC.
- **NPDES / stormwater:** Ohio EPA draft general NPDES permit for data centers is **OHD000001**
  (draft; public hearing/comment close Dec 17, 2025 — covers non-contact cooling water, cooling-
  tower/boiler blowdown, low-volume wastewater, industrial stormwater). Not yet linked to the Van
  Wert facility by name. `[verified]` Source: Ohio EPA; Bricker.

### Opposition / litigation

- **Local opposition:** at the May 11, 2026 Council meeting, 40–50 residents attended and a majority
  raised concerns (water levels, electricity, noise, light pollution); some demanded a moratorium or
  full three readings. Council passed the enabling ordinances anyway (as emergencies). `[verified]`
- **Statewide:** a citizen effort is gathering signatures for a constitutional amendment to prohibit
  data centers consuming >25 MW; lawmakers heard data-center opposition (June 3, 2026) but
  enacted no moratorium. `[reference]` (advocacy).
- **Litigation:** none specific to the Van Wert project found. `[open]`

## 2 — No other confirmed Van Wert County activity pinned yet

No second data-center operator or land assembly in Van Wert County is confirmed to the pinning
standard as of 2026-07-02. `[open]` — re-sweep on the next pass.

## Instruments to pull (priority order)

1. **Van Wert County Recorder** — the **grantor** side and the instrument numbers. The Auditor half
   of this item is **done** (#1403): grantee, parcel IDs, acreage, prices and transfer dates are
   committed from the CAMA. What the auditor layer cannot give is the grantor, the deed book/page
   and the legal description, so the Marsh Foundation → Thor/Form8tion (Aug 2025) → QTS (Jun 2026)
   chain still needs the recorded instruments. Add the county Engineer's **survey records** named on
   the parcels — `VW-SD522-1`, `VW-SD522-2`, `VW-SD522-523`, `VW-SD524` — which are the splits that
   carved the campus out of the Marsh tract.
2. **Van Wert City Council / County Commissioners** — executed CRA / PILOT / TIF ordinance(s) with
   %/term, plus the Lincolnview + Vantage school-compensation agreements.
3. **OEPA air PTI** — emergency generator bank PTI(s) for the Mega Site (NWDO, Van Wert County).
4. **Ohio EPA / EPA ECHO** — any facility NPDES coverage / notice-of-intent under OHD000001, and
   a Town Creek / Little Auglaize 7Q10. The **municipal** half of this item is **done** (#1406):
   permit 2PD00006\*WD is committed, the outfall is coordinate-pinned, and the compliance record
   is dated and regenerable in `data/extracted/van-wert/water-watch.yaml`. What that register
   leaves open — the raw-water intake's own location, the CSO volumes, a measured critical-season
   phosphorus load, and the two uncommitted water-plant permits (OHG8P0006, OH0135569) — is
   itemized there under `instruments_to_pull`.
5. **City of Van Wert water/sewer** — the closed-loop fill volume and any water/sewer service
   agreement (the peak-withdrawal figure to screen against Town Creek). Sharpened by #1406: the
   creek's own recorded annual yield ranges 180 MG–1.26 BG since 1951, so the screen a service
   agreement needs is against a **dry year**, not an average one.

## Sources

- QTS (official): [q.com/data-centers/van-wert](https://q.com/data-centers/van-wert/)
- Hometown Stations ($10B announcement): [van-wert-announces-10-billion-qts-data-center-campus-investment](https://www.hometownstations.com/news/van_wert_county/van-wert-announces-10-billion-qts-data-center-campus-investment/article_18b9e9fc-010b-4353-95c0-4ed96293c1ed.html)
- Data Center Dynamics (QTS end user): [qts-behind-van-wert-ohio-mega-site-acquisition-announces-10-billion-data-center-campus](https://www.datacenterdynamics.com/en/news/qts-behind-van-wert-ohio-mega-site-acquisition-announces-10-billion-data-center-campus/)
- VW Independent (end user): [2026/05/29/qts-data-centers-is-the-end-user-for-vw-data-center](https://thevwindependent.com/news/2026/05/29/qts-data-centers-is-the-end-user-for-vw-data-center/)
- VW Independent (council approval): [2026/05/11/council-unanimously-approves-data-center-legislation](https://thevwindependent.com/news/2026/05/11/council-unanimously-approves-data-center-legislation/)
- VW Independent (timeline): [2026/05/29/data-center-construction-operations-timeline-shared](https://thevwindependent.com/news/2026/05/29/data-center-construction-operations-timeline-shared/)
- VW Independent (opposition): [2026/06/03/lawmakers-hear-data-center-opposition](https://thevwindependent.com/news/2026/06/03/lawmakers-hear-data-center-opposition/)
- Thor Equities (GlobeNewswire, land buy): [thor-equities-group-expands-portfolio](https://www.globenewswire.com/news-release/2025/08/19/3135865/0/en/Thor-Equities-Group-Expands-Portfolio-with-Key-Acquisition-in-North-America-s-Leading-Data-Center-Corridor.html)
- Ohio EPA (data-center general permit): [wastewater-discharges-from-data-centers--general-permit](https://epa.ohio.gov/divisions-and-offices/surface-water/permitting/wastewater-discharges-from-data-centers--general-permit)
- Bricker (draft NPDES OHD000001): [ohio-epa-issues-draft-general-npdes-permit-for-data-centers](https://www.bricker.com/insights/publications/ohio-epa-issues-draft-general-npdes-permit-for-data-centers)
- City of Van Wert water: [vanwert.org/water-treatment](https://vanwert.org/water-treatment/)
- Ohio EPA HUC-12 (Lower Town Creek–Lower Little Auglaize): [nps report PDF](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/nps/Lower%20Town%20Creek-Lower%20Little%20Auglaize%20River_Ver1.0_10-31-2023.pdf)
- Ohio EPA NPDES 2PD00006 (the DAM slot; now serves the \*WD modification): [2PD00006.pdf](https://dam.assets.ohio.gov/image/upload/epa.ohio.gov/Portals/35/permits/doc/2PD00006.pdf)
- EPA ECHO Detailed Facility Report, Van Wert WWTP: [OH0027910](https://echodata.epa.gov/echo/dfr_rest_services.get_dfr?p_id=OH0027910&output=JSON)
- EPA "How's My Waterway", Lower Town Creek: [OH041000070804](https://mywaterway.epa.gov/waterbody-report/21OHIO/OH041000070804)
- Stop Ohio Data Centers (advocacy, leads only): [stopohiodatacenters.org/data-center-water-usage-ohio](https://stopohiodatacenters.org/data-center-water-usage-ohio)
