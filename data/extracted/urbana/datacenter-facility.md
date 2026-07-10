# Urbana data-center facility — the "Urbana Technology Hub" (Thor Equities)

Resolves **#1327** (the `facility` readiness domain) and the corpus's central `[open]` question —
*is Highland55 a data center, and who is "Vance Brands"?* — **which is now answered: it is a data
center.** Tags follow the project vocabulary (`[verified]` = primary/press/government source;
`[reference]` = authoritative outside data / public disclosure; `[inference]`; `[open]`).

This is external public-record discovery layered on the ingested Highland55 permit corpus
(`data/documents/permits/highland55/`, the §401 WQC / Corps JD instruments) and the land-assembly
deed record ([`land-assembly.yaml`](land-assembly.yaml), #1328). **The naming site-plan/permit
instrument itself is not in corpus** — the City of Urbana planning documents were not reachable to
ingest from this build env (only vetted connector hosts resolve; cf. the #1328 limitation on the
Champaign Recorder / Ohio SoS). So the *end-use* is `[reference]` (public disclosure), not yet
`[verified]` — see §7.

## 1. The facility `[reference]`

| Field | Value |
|---|---|
| Name | **Urbana Technology Hub** (data-center campus) |
| Location | Corner of **SR-55 & US-68**, Urbana Township, Champaign County, OH |
| Developer | **Thor Equities** (via its **Form8tion** unit) — **Urbana Owner I LLC** + **Highland55 Investments LLC** |
| Scale | **460,000 sq ft**, single-story, ~40 ft tall (disclosed site plan) |
| Investment | **~$1 billion** disclosed |
| Cooling | **Closed-loop** — water use "comparable to a standard office building" (see §5) |
| Serving utility | **AES Ohio (Dayton Power & Light)** — confirms the profile's `[verified]` serving utility (EIA-861 #4922 / DP&L, PJM **DAY** zone) |
| Jobs | 30–80 permanent operations; 1,000+ construction |
| Incentives | CRA agreement offered (noise limits 65 dB day / 55 dB night); ~$6M/yr combined city + school tax |
| Power (MW) | **NOT disclosed** — a floor-area screening bracket only; the interconnection/air-permit load stays `[open]` (see §4) |
| Named tenant/operator | none yet `[open]` |

## 2. Disclosure timeline `[reference]`

- **Feb 2026** — the data-center plan is **disclosed at a City of Urbana meeting** and in the
  **site-plan application** (Urbana Daily Citizen, "Data center plans revealed at city meeting",
  2026-02-18). This resolves the corpus's `[open]` end-use question.
- **H2 2025 – 2026** — the ~230-ac land assembly recorded to the Champaign County auditor (four
  parcels, three Thor single-purpose entities) — the register + LLC graph are in
  [`land-assembly.yaml`](land-assembly.yaml) / [`highland55-findings.md`](highland55-findings.md).
- Litigation **Thor v. Urbana** — the federal case (S.D. Ohio **3:26-cv-00196-MJN-CHG**, filed
  2026-06-19) is now **in corpus** as a filed primary instrument
  ([`litigation-thor-v-urbana.md`](litigation-thor-v-urbana.md), #1329). Thor **alleges** the
  Project is a data center; as a party's pleading this is `[reference]` (attributed), not
  independent verification of the end-use. The complaint also **recites** an ordinance record
  (`[reference]`) — the City amended M-1 to permit data centers on this land (Ord. 4621-25)
  specifically for the Project, then moved to reverse it — which frames the entitlement *dispute*
  as over a data center. The underlying ordinances are not attached to Doc #1 (Exhibits 1–9 are
  separate ECF filings) and stay `[open]` (#1359). The companion Champaign County Common Pleas
  administrative appeal remains `[open]`.

## 3. Land assembly `[verified]` (deed record) — see §land-assembly

The recorded ownership assemblage behind the campus is sourced to the Champaign County auditor CAMA
(deed Official-Record book/page for each parcel); full register in
[`land-assembly.yaml`](land-assembly.yaml). Grantee / deed / consideration / date are `[verified]`;
grantors are `[reference]` corroborated `[inference]` by the acreage/price math.

## 4. Power / grid — MW load `[open]`

- **The campus's own MW load is NOT publicly disclosed.** The disclosure states the end user pays
  all grid/transmission upgrades, but names no capacity figure and no named tenant/operator. `[open]`
- Serving utility **AES Ohio (DP&L)** confirms the profile's `[verified]` serving utility (EIA-861
  #4922, PJM DAY zone). `[reference]`
- The MW load, the **PJM interconnection queue position**, and any **air permit** for emergency
  gensets are the tracked `[open]` sub-leads (parent epic #1263). Per data discipline (never
  fabricate a figure), the profile carries **no disclosed genset fleet** and **no air permit** —
  the air-dispatch model refuses cleanly for this site.

> **Negative-search result (#1353, 2026-07-10).** Both facility-naming power/emissions instruments
> were searched; **neither surfaced a load or a genset fleet for this campus**, so the MW stays
> `[open]` and the screening bracket is **retained** (full record:
> [`facility-power-instrument-search.md`](facility-power-instrument-search.md)):
>
> - **PJM.** AES Ohio's disclosed "Dayton" TEAC large-load *customer requests* name **Piqua,
>   Adams County, Marysville, Tipp City, Jeffersonville, Wilmington** — **none Champaign County /
>   Urbana**; the only Champaign-County PJM-queue item is **Woodstock Solar (AE2-342)**, a
>   withdrawn 40 MW solar generator, unrelated. `[verified]`
> - **OEPA air.** US-EPA ECHO **ICIS-AIR** shows **no campus air permit** at the SR-55/US-68 site —
>   the 7 air sources near Urbana are all pre-existing industry (City landfill, Hall printing,
>   Heritage/Westville grain, JMC/Ultra-Met metal, Bundy). Expected for a greenfield whose
>   construction opens 2026-06-01. `[verified]`
> - **⚠️ Conflation guard.** The **100 MW→1.3 GW** AES Ohio ramp is the **Adams County** (Stuart
>   substation) request, and the **~500 MW** figure is Thor's **Van Wert County** campus — **neither
>   is Urbana.** Urbana's own disclosure states no MW; baxtel lists no capacity for it.

### The IT-load screening bracket `[inference]` — read this before quoting a MW figure

Because the domain must activate to `live` (#1327) but the load is undisclosed, `SiteProfile.facility`
carries an **IT-load SCREENING bracket — explicitly `[inference]`, never a disclosure**:

- **35 MW low / ~70 MW central / 115 MW high**, from the disclosed **460,000 sq ft gross floor area
  × a whole-building IT power-density band of 75–250 W/sq ft** (a *stated screening assumption*).
- The single-story ~40 ft form factor and the disclosed **closed-loop dry cooling** ("water use
  comparable to a standard office building", §5) argue against the max-density liquid-AI archetype,
  so the band is deliberately bounded **well below** GB200-class rack densities.
- This bracket exists only to size the order-of-magnitude demand-pressure sensitivity
  (`economics-demand-pressure`); it is **not** a load disclosure and must be **replaced** the moment a
  PJM interconnection application or an air permit surfaces the real load. See the `it_load_citation`
  on `_URBANA.facility`.

## 5. Cooling / water — the key finding `[reference]`

The developer disclosed **closed-loop cooling** with water use **"comparable to a standard office
building."** Carried on the profile as `cooling_model = CLOSED_LOOP_DRY` (`source="reference"`). This
**undercuts the Mad River buried-valley water-abstraction thesis**: the headline concern for a data
center on a US-EPA sole-source aquifer is consumptive cooling withdrawal, and the disclosed design is
low-water. This stays `[reference]` (public disclosure) until an ingested mechanical/plumbing permit
takes it to `[verified]`.

## 6. What `SiteProfile.facility` now carries (#1327)

`_URBANA.facility` is a **site-plan-grounded** `SiteFacility` (contrast Lima / Fort Wayne, which are
air-permit-grounded): it records the disclosed non-power attributes (`facility_type`,
`gross_floor_area_sqft`, `disclosed_investment_usd`, `disclosure_citation`, `cooling_model`) and an
`[inference]` IT-load bracket (`it_load_citation`), with **`genset_count` / `genset_mw` /
`air_permit_citation` left `None`** (no disclosed generation, no air permit). This flips the `facility`
readiness domain from `absent` → **`live`** (the `economics-demand-pressure` feed is present), and
`facilityStatus("urbana")` from `investigation` → `confirmed`.

## 7. Open leads / extraction targets

The end-use stays **`[reference]`** — the #1353 search for a facility-naming *primary* instrument
(PJM interconnection / OEPA air permit) came back **negative** (§4), so nothing surfaced to take it
to `[verified]`. It flips the moment any lead below resolves.

- `[open]` **The MW load** and the **PJM interconnection queue position** — searched negative
  2026-07-10 (§4); the screening bracket is retained until a later AES Ohio TEAC / PJM large-load
  filing names an Urbana-area substation, then replaces it.
- `[open]` **An OEPA air PTIO** (emergency engines) — searched negative on ECHO ICIS-AIR
  2026-07-10 (§4); re-check when the greenfield reaches construction. Populates
  `genset_count`/`genset_mw`/`air_permit_citation` and activates the air-dispatch model.
- `[open]` **The Feb-2026 site-plan application** (and any building/zoning permit) — the primary
  instrument that *names* the facility type; ingest to `data/documents/**/urbana/` when reachable to
  take the end-use `[reference]` → `[verified]`.
- `[open]` **Named tenant/operator** — "Vance Brands" appears in the Corps JD filings but is not
  resolved to a data-center operator; neither the PJM nor the air search named an operator (#1353).
- `[open]` The **CRA/PILOT agreement** and the **development agreement** — incentive instruments.
