# Bowling Green · Middleton Twp (bowling-green) — energy / grid outputs

Per-site onboarding tree for the Bowling Green · Middleton Twp watershed point (basin: portage), scaffolded by `watermark onboard bowling-green` (#326). Values come from the portable onboard connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is fabricated; regenerate, don't hand-edit.

## Source

`watermark onboard bowling-green` over the Bowling Green · Middleton Twp `SiteProfile` — EIA-861 (utility retail) · EIA-930 (RTO demand/mix) · EIA v2 API (consumer energy prices).

### Non-EIA sources reaching `grid-profile.yaml` (#1440)

Every **figure** in `grid-profile.yaml` is connector-derived from the EIA sources above. Its `serving_utility.utility.citation` is the one hand-authored string in the file — it comes from `SiteProfile.serving_utility_citation`, is rewritten on every `watermark grid` run, and rests on records that are **not** EIA. Bowling Green is a **two-grid site**, so that citation carries a per-load split; its sources and confidence:

| claim | source | tag |
| --- | --- | --- |
| The **site's** utility is the City of Bowling Green municipal system, utility **`#2054`**, Municipal, BA=PJM | EIA-861 2024 Service_Territory / Sales_Ult_Cust (#1434) | `[verified]` |
| Wood County is inside **Toledo Edison's** tariffed territory (so the Meta campus is not on the muni) | The Toledo Edison Company, **P.U.C.O. No. 8, Original Sheet 3, Definition of Territory**, eff. 2026-03-01 — `data/documents/grid/bowling-green/TE-2026-Electric-Service.pdf` | `[verified]` |
| The campus's modelled grid draw is ~0 because it is served behind the meter | **Apollo OPSB 25-0973-EL-BLN, Condition 15** (bars interconnection with the PJM Transmission System) — `data/extracted/grid/bowling-green/apollo-power-generation-facility.yaml` | `[verified]` |
| The **Oppidan** colo is served by the municipal utility | City of Bowling Green electric-distribution GIS + the BG utilities director on the record — `data/extracted/grid/bowling-green/serving-utility.yaml` | `[inference]`, high confidence |
| Which utility is certified **at the parcel** — for either the Middleton Twp campus or the Woodbridge Business Park colo | not established; the PUCO county certified-territory map was not pulled | **`[open]`** |

A county is not a parcel: the tariff sheet establishes Toledo Edison's territory *includes territory in* Wood County, not that any given parcel sits in it. Full per-load determination at `data/extracted/grid/bowling-green/` (catalog `bowling-green-grid`).

## Known gaps & caveats

- Onboarding seed — **review every value against a cited source before promotion** (`web/src/lib/sites.ts` `status`/`selectable`, parity-gated).
- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated by the portable reach connectors — it needs a per-jurisdiction connector (see `docs/onboarding.md`).
- `grid-profile.yaml` is **connector-generated and `extra="forbid"`** — never hand-edit it. The only hand-authored input that reaches it is `SiteProfile.serving_utility_citation`; edit that and regenerate.
- `load_share.share_of_utility_pct` is struck against the **muni's** retail sales and is a **magnitude comparison**, not the campus's serving-utility ratio — the campus is on a different grid. A per-facility serving-utility denominator is an open model follow-up.

## Regenerate

`watermark onboard bowling-green`  (or the per-connector commands: `derive-low-flows`, `nasa-power --write`, etc.)
