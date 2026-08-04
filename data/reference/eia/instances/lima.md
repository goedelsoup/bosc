---
site: lima
title: Grid & consumer energy at Lima — AEP Ohio, PJM, Allen County, OH
---

Lima's copy of the [EIA grid & consumer-energy dataset](../README.md): the un-slugged
`reference/eia/consumer-energy.yaml` + `grid-profile.yaml`, resolved to **Ohio** and to the
Lima campus's serving utility. The method is the README's; what it resolved to here is
below.

## The serving utility is corpus-grounded, not asserted

The relator
[data appendix](../../../extracted/legal/select-committee-2026/relator-testimony/bosc-data-appendix-2026-06-01.md)
references the **AEP Ohio tariff** for this campus's 25 MW threshold; the Allen County
commissioners' minutes reference local AEP service (Res #974-25). The retail
service-territory boundary is **formally confirmed** against the EIA-861 service-territory
file / PUCO map — named as the confirmation source (`confidence: high`).

**RTO = PJM** follows and is authoritative: AEP Ohio is a PJM transmission zone,
FERC-jurisdictional.

## The three load denominators (#94/#120)

| denominator | value | source |
|---|---|---|
| AEP Ohio retail sales | ~48,653 GWh | EIA-861 per-utility "Sales to Ultimate Customers" (2024 vintage) |
| AEP Ohio customers | ~1.53 M | same |
| PJM annual demand | ~815,056 GWh | EIA-930 daily-demand sum (Eastern tz), `fetch_ba_annual_load` |
| Ohio state retail | see `consumer-energy.yaml` | shared with the consumer-price series (#91) |

AEP Ohio reports in a **restructured split** — Bundled (SSO) + Delivery (shopping). Retail
sales and customers are the sum; the average price is the **bundled (full-service)
revenue/sales**, because delivery-only rows exclude generation and a blended price would
understate the all-in cost.

## Consumer series

Ohio residential electricity price (`ELEC.PRICE.OH-RES.A`), Ohio residential natural gas
(`NG.N3010OH3.A`), and Ohio total retail sales (`ELEC.SALES.OH-ALL.A`) — the state market
the campus load is sized against, and the household prices the ratepayer read is built on.
The campus itself buys at wholesale/industrial rates; the residential price is the
consumer-impact reference, never the campus's own bill.
