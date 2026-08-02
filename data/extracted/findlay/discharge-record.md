# Findlay's discharge record — the issued NPDES permit, its modification, and the TMDL chain

**Site:** Findlay, OH (Hancock County) · **Issue:** 1460 · **Ingested:** 2026-07-31
**Instruments:** Ohio EPA NPDES `2PD00008` (application `OH0025135`) · Maumee Watershed Nutrient
TMDL Appendix 4 · Maumee Watershed Total Phosphorus general permit `OHP000001` · the 2024 TMDL
Biennial Report · Ohio EPA's January 2026 List of Variances

All figures below are `[verified]` from the instruments named beside them. These are digitally
generated Ohio EPA PDFs, so the quoted text is each document's own embedded text layer, not an OCR
guess of a scan.

## The plant

The City of Findlay Water Pollution Control Center — the fact sheet writes WPCC, the permit and
the TMDL write WPCF — sits at 1201 South River Road and discharges through a single final outfall,
`2PD00008001`, to the **Blanchard River at River Mile 56.42**. Ohio EPA river code 04-160,
hydrologic unit 04100008-03-04, Hancock County, Eastern Corn Belt Plains. The segment is designated
Warmwater Habitat, Agricultural Water Supply, Industrial Water Supply and Primary Contact
Recreation.

Constructed 1988, last upgraded 2001. Average design flow **15 MGD**, peak hydraulic capacity
**40 MGD**. It serves Findlay, the villages of Arcadia and Van Buren, and parts of Hancock County
through an oxidation ditch, secondary clarification, ferric-chloride precipitation, UV disinfection
and post aeration. Sludge is aerobically digested, belt-press dewatered, and landfilled. Estimated
infiltration/inflow is 1.6 MGD. Ohio EPA records no effluent limit violations in the previous five
years.

The collection system is 93% separate and 7% combined, with **ten authorized combined sewer
overflows** — eight to the Blanchard, and two (`010` Hancock and Bank Street, `013` East Sandusky
and Blanchard Street) to **Eagle Creek**, the same Eagle Creek the flood-mitigation program is
building a dry storage basin on. Ten sanitary sewer overflows are separately monitored. The
pretreatment program covers **eight significant industrial users**, five of them categorical,
discharging 0.428 MGD.

## The number that matters: there is no dilution

Table 12 of the fact sheet gives the design low flows **at the outfall**, from USGS gages 04188300
and 04189000:

| Statistic | Value (cfs) |
|---|---|
| 1Q10, annual | 0.17 |
| **7Q10, annual** | **0.21** |
| 30Q10, summer | 0.31 |
| 30Q10, winter | 1.24 |
| 90Q10, annual | 0.32 |
| Harmonic mean, annual | 1.84 |
| Findlay WPCC average design flow | **23.208** |

The plant's design flow is roughly **110 times** the river's annual 7Q10. Ohio EPA does the
arithmetic itself on page 13:

> Acute Dilution Ratio = (1Q10 + WWTP flow rate) / WWTP flow rate = (0.17 cfs + 23.2 cfs) / 23.2 cfs
> = **1.0**

A ratio of 1.0 is the floor of the calculation. It means that at design flow, below River Mile
56.42, the Blanchard River *is* the effluent. The acute wasteload allocation that follows is
expressed as 30 percent mortality in 100 percent effluent.

**This is now the low flow the network carries for Findlay** (issue 1458, reconciled 2026-08-02).
It used to screen at **0.37:1** dilution against a *derived* 8.67 cfs — an LP3 fit at gage
04189000, i.e. effluent 2.68× the low flow — and the reconciliation retired that denominator for
this plant on two grounds neither number could be argued out of (both ratios below are stated
low-flow-to-effluent, the `dilution_ratio` convention: smaller is worse):

- **The gage sits below this outfall.** USGS 04189000 is at 41.05589 / −83.68799, ~1.1 mi WNW of
  outfall 2PD00008001 at 41.049722 / −83.667778, on a reach the Blanchard runs westward; Straub
  (2001) places it "2.0 mi west of Findlay, 3.0 mi downstream from Eagle Creek." So the flow that
  denominator measured already contained the discharge it was being used to screen.
- **The gage is regulated.** Straub's REMARKS for the station, verbatim: "Water is diverted
  upstream from station into Findlay Reservoir. Storage in Findlay Reservoir used for water supply
  of city of Findlay, and is available for low-flow augmentation. All water returns to stream
  upstream from station."

Where the Blanchard is *unregulated*, USGS publishes a 7Q10 of **0.03 cfs** (04188337, below Mt.
Blanchard, WY2008–2020) and **0 cfs** for its Eagle Creek tributary (04188496). The 0.21 cfs Ohio
EPA computed at RM 56.42 is consistent with that; the 8.67 was never the river's own low flow.
The screen now reads **0.009:1** — ~41× tighter than the 0.37:1 it replaced, effluent 110× the
low flow rather than 2.68× — and the comparison artifact
(`data/reference/network/findlay-ottawa-comparison.yaml`) is re-based on each plant's own fact
sheet. Sources: `data/reference/usgs/low-flow/` (bytes + traps),
`data/reference/hydrology/mainstem-gages.yaml` (the reviewed reads).

Populating `_FINDLAY.plant_receiving` with the cited receiving water, the outfall river mile and the
Table 12 low flows is what closes **issue 352**, together with the ECHO correction below.

## What ECHO did not have

EPA ECHO returned `receiving_water: null` for `OH0025135` — the largest POTW in the Blanchard
subbasin and the third-largest grouped-load phosphorus discharger in the Maumee watershed. While
that field was null the plant fell out of every receiving-water screen. Three independent Ohio EPA
instruments name the water outright:

1. the fact sheet, p. 7 — *"Findlay WPCC discharges to Blanchard River at River Mile 56.42"*;
2. general permit `OHP000001` Part I.C.1 — *"City of Findlay WPCF | OH0025135 | 2PD00008 |
   Blanchard River"*;
3. the January 2026 List of Variances — affected water body *"Blanchard River"*.

The correction is declared in the committed curation overlay
(`data/reference/echo/curation/maumee-wwtp.receiving-water.yaml`) and re-applied on every
`watermark npdes --basin maumee` pull, so a refresh can never silently revert it. The re-pull that
applied it produced no other change to the basin inventory.

## The permit in force, and what its modification actually did

The permit history has three legs, and the Ohio EPA DAM currently serves only two of them.

| Leg | Instrument | Dates |
|---|---|---|
| Renewal fact sheet | `2PD00008*UD`, Public Notice 205259 | noticed 2024-08-09, comments closed 2024-09-08 |
| Renewal as issued | `2PD00008*UD` | effective **2024-11-01**, expires **2029-10-31** |
| Modification | `2PD00008*VD`, Public Notice 216133 | issued 2025-11-07, noticed 2025-11-14, comments closed 2025-12-14, effective **2026-02-01**, expires 2029-10-31 |

The middle row is the gap. The DAM's `permits/doc/2PD00008.pdf` slot now serves the **modification
package** — Director John Logue's transmittal letter, the modified permit, and the modification's
own eight-page fact sheet — so the corpus holds the `*UD` fact sheet but not the `*UD` permit as
issued. Its term is recorded from the January 2026 variance list, which prints
`2PD00008*UD | 001 | 11/1/2024 | 10/31/2029` outright. Obtaining the as-issued `*UD` bytes is lead
`UD-ISSUANCE-BYTES`.

The modification's entire substance is a date, moved twice:

> 1. Page 14 - Part I, C, Schedule of Compliance, change the milestone summary report for the
>    Municipal CSO Schedule event code 34099 Due Date to **November 1, 2026**.
> 2. Page 15 - Part I, C, 2, Long-Term Control Plan (LTCP) Addendum section (b.), change the
>    language to **No later than November 1, 2026**.

Nothing else moved. The limits, the mercury variance and the low-flow basis are untouched.

That deadline has a history. Findlay's 1998 CSO Long-Term Control Plan did not attain its designated
level of control of four overflows per typical year; a 2018 evaluation report found that twelve of
the CSO outfalls no longer had combined sewer upstream and were in substance sanitary sewer
overflows; an updated integrated plan — inflow-and-infiltration reduction, raised CSO weirs, upsized
pipe, a new 5 MGD lift station, equalization basins — was submitted 2020-01-31 and approved
2021-07-08; and the City then asked for more time to evaluate its treatment system and develop a new
plan. **2026-11-01** is where that request landed. Lead `CSO-LTCP-2026-11-01`.

The sibling milestone is quieter and arrives first: event code **52599, due 2026-05-01**, requires
the City to evaluate whether local industrial-user limits for total phosphorus would make
substantial progress toward a monthly average effluent concentration of **0.5 mg/L** — half the
permit's own limit — or to submit evidence that they would not.

## The mercury variance

Findlay's permit has carried a mercury variance since a 2010 modification, renewed in the 2024
action under OAC 3745-1-38(H). The water-quality-based limit it departs from is **1.3 ng/L**. The
variance-based monthly average is **3.3 ng/L**, with a daily maximum of 1700 ng/L, and a standing
condition that the **annual** average stay at or below **12 ng/L**. Ohio EPA records the effluent
falling from 8.5 ng/L when the variance issued to 2.2 ng/L now, and the Pollutant Minimization
Program continues.

The January 2026 statewide variance list carries a Modified Allowable Ambient Concentration of
**3.29 ng/L** for this outfall. That is an *in-stream* concentration, and the 3.3 ng/L is an
*effluent* limit — two different quantities that coincide here to within a rounding step. That
coincidence is what an acute dilution ratio of 1.0 means when you write it out.

Whole effluent toxicity went the other way. No toxicity was detected in the reporting period,
reasonable potential was not demonstrated, and the final effluent limits for *Ceriodaphnia dubia*
were removed. Table 14 now lists all four WET endpoints — acute and chronic *C. dubia* and
*Pimephales promelas* — as **monitoring only**. Annual chronic testing with determination of acute
endpoints is retained.

## Phosphorus: two instruments, one number, and a bubble

The permit's own total-phosphorus limit is **1.0 mg/L** (30-day average) and 56.8 kg/day, daily
maximum 1.5 mg/L and 85.2 kg/day. Its stated basis is `PTS` — Phosphorus Treatment Standards,
OAC 3745-33-06(C). That is a **technology** standard. It is not the TMDL.

The TMDL reaches this plant through a different instrument. The Maumee Watershed Nutrient TMDL,
approved by US EPA on 2023-09-28, assigns Findlay WPCF a spring-season (March-July) wasteload
allocation of **3.2 metric tons** of total phosphorus (Appendix 4, Table A4.1), plus a separate
**0.016 MT** for its combined sewer overflows (Table A4.3) — the third-largest CSO allocation in the
basin, behind Toledo and Lima. General permit `OHP000001`, effective 2023-11-01 over 39 facilities,
restates the same allocation as a **3,200 kg** seasonal Individual Load Limit (Part IV.A.1) and is
the instrument that makes it enforceable.

Table A4.5 of the same appendix prints what the plant actually discharged:

| | 2008 | WLA | 2017 | 2018 | 2019 | 2020 | 2021 |
|---|---|---|---|---|---|---|---|
| Findlay WPCF (MT spring TP) | 4.4 | **3.2** | 4.8 | 5.5 | 5.3 | 5.5 | 5.4 |

Every reported year is above the allocation, by 50 to 72 percent. Among the basin's five largest
grouped-load POTWs, Findlay is the only one over in every year on the record.

And it is not, on this record, a violation of anything. `OHP000001` Part IV.C.3:

> For any given season, individual permittees are in violation of their Individual Load Limit **only
> if**: a. The Cumulative Load exceeds the Cumulative Load Limit **and**; b. The permittee's
> Individual Load exceeds their respective Individual Load Limit.

Compliance is evaluated at the group first. The 2024 Biennial Report gives the group's first
reported season: **43,304 kg-TP against a 64,170 kg cap**, 20,866 kg of headroom. So long as the
bubble holds, an individual plant running half again over its own allocation is in compliance by the
permit's own terms. The Director *may* re-evaluate an over-limit permittee's eligibility on review
of each Season Report (Part IV.C.4), and an exceedance by a permittee found ineligible becomes a
violation regardless of the group (Part IV.C.5) — but neither is automatic.

What the corpus cannot say is whether Findlay is still over. The TMDL's per-facility record stops at
2021 and the Biennial Report publishes only the group total. The document that would answer it is
the plant's own annual Season Report under Part IV.D, due each September 1 and carrying "the
calculated Individual Load and a brief assessment comparing the Individual Load to the permittee's
Individual Load Limit." Those are not in the corpus. Lead `TP-SEASON-REPORTS`.

## Committed artifacts

| Record | Instrument |
|---|---|
| [`oepa/findlay/2PD00008.fs.npdes.yaml`](../oepa/findlay/2PD00008.fs.npdes.yaml) | The `*UD` renewal fact sheet — receiving water, Table 12, dilution, mercury, WET, Table 14 |
| [`oepa/findlay/2PD00008.npdes.yaml`](../oepa/findlay/2PD00008.npdes.yaml) | The `*VD` modification package as issued — the schedule, the full station inventory, the attached fact sheet |
| [`oepa/findlay/2PD00008.1abaf306.npdes.yaml`](../oepa/findlay/2PD00008.1abaf306.npdes.yaml) | The `*VD` draft public notice (PN 216133) |
| [`findlay/tmdl/maumee-tp-wla-2PD00008.epa.yaml`](tmdl/maumee-tp-wla-2PD00008.epa.yaml) | The allocation chain — TMDL row, general-permit limit, compliance rule, 2024 group performance |

Source documents: [`data/documents/oepa/findlay/`](../../documents/oepa/findlay/) (permit, fact
sheet, modification notice), [`data/documents/oepa/`](../../documents/oepa/) (`OHP000001.pdf`,
`OHP000001_FS.pdf`, `Jan_2026_List_of_Variances.pdf`),
[`data/documents/maumee-tmdl/`](../../documents/maumee-tmdl/) (Appendix 4, the 2024 Biennial
Report).

## Open threads

- `CSO-LTCP-2026-11-01` — the LTCP addendum deadline, and whether it moves again.
- `TP-SEASON-REPORTS` — the plant's own phosphorus loads since 2021.
- `UD-ISSUANCE-BYTES` — the as-issued `*UD` permit, which the DAM no longer serves.
- `MERCURY-VARIANCE-RENEWAL` — the annual 12 ng/L condition.
- Issue **1458** — the derived-vs-cited low-flow reconciliation. This record supplies the cited
  side; it does not resolve the conflict.
