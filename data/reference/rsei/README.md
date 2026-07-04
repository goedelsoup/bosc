# Allen County RSEI toxic-release inventory (EPA RSEI Public Data Set)

Per-facility **Risk-Screening Environmental Indicators (RSEI)** results for **Allen
County, OH (FIPS 39003)**, reduced from EPA's RSEI Public Data Set. Every figure here
was summed from RSEI rows — nothing is fabricated, inferred, or estimated by BOSC.
Regenerate with `watermark rsei`.

## What RSEI is

RSEI is EPA's screening model over **Toxics Release Inventory (TRI)** reports. For
each reported release it combines the **pounds released**, the chemical's **toxicity
weight**, and (for the Score) **fate-and-transport + the surrounding population** into
two comparative measures:

- **RSEI Score** — modeled, population-weighted, *unitless*. Comparative **only**: it
  is **not** a risk estimate, a dose, or a concentration. Used to rank/triage.
- **RSEI Hazard** — pounds × toxicity weight, with **no** exposure/population term.
- **Cancer / Non-cancer Score** — the Score split by health endpoint (`CScore`/`NCScore`).

## Source

| | |
|---|---|
| Dataset | EPA RSEI Public Data Set — Public Release Data |
| Version | `v2312` — RSEI **v2.3.12** (March 2024; TRI reporting years 1988–2022) |
| Endpoint | `https://gaftp.epa.gov/rsei/Current_Version/V2312_RY2022/Public_Release_Data/RSEIv2312_Public_Release_Data.zip` |
| Format | one ~447 MB zip of per-table CSVs; the connector streams each table straight out of it (never extracts the ~1.2 GB `elements`) |
| License | U.S. Government work (public domain) |
| Docs | <https://www.epa.gov/rsei/ways-get-rsei-results> |

The prior `v234` release was distributed through the AWS Open Data bucket
`s3://epa-rsei-pds`; that bucket is **frozen** at `v234`/2016 and does not carry
v2.3.12, so the connector was re-pointed to EPA's `gaftp` Public Release Data (#1148).
The legacy per-table-gzip layout is still reachable via `rsei_distribution="s3_gz"`.

## How the inventory is built

RSEI is a relational dump. `watermark rsei` joins five tables and keeps only the rows that
roll up to a county-39003 facility:

```
elements   (ReleaseNumber)   -> Score, CScore, NCScore, Hazard, Population
  via release    (ReleaseNumber -> SubmissionNumber, Media, PoundsReleased)
  via submission (SubmissionNumber -> FacilityNumber, ChemicalNumber, SubmissionYear)
  via facility   (FacilityNumber -> name, coords, parent, NAICS1)
  via chemical   (ChemicalNumber -> name, CAS, ToxicityCategory)
```

- **Pounds** are summed from the reported `release` rows (`PoundsReleased`), bucketed
  by media via `media.csv` (`MediaCode`: 1 air, 3 water, 4 underground, 5 land,
  6 POTW, 7 offsite).
- **Score / Cancer / Non-cancer / Hazard** are summed from the modeled `elements`
  rows. `elements` carries `Hazard` directly — BOSC does not recompute it.
- Codes use the **primary reported** `NAICS1` field. v2.3.12 is NAICS-only — it dropped
  the `SIC1` and `NPDESPermit` facility columns v234 carried, so `sic` / `npdes_permit`
  are now always null. Text is Latin-1.

## Files

- `inventory.yaml` — provenance `meta` block + the 49 facilities, ranked by Score,
  each with cumulative Score/Cancer/Non-cancer/Hazard/pounds, a per-year series, a
  by-media pounds breakdown, and the top contributing chemicals.
- `toxic-discharge-screen.yaml` — the **toxic-load × assimilative-capacity screen**
  (`watermark toxics`): the 13 facilities that release toxics **to water**, placed on their
  receiving stream and read against the cited 7Q10 (see below).

## Toxic-discharge screen (`toxic-discharge-screen.yaml`)

`watermark toxics` extends the hydrology [low-flow assimilative screen](../../../docs/HYDROLOGY.md)
from the three municipal WWTPs to the **industrial** dischargers — the RSEI facilities
with water-media releases — using only committed artifacts (RSEI × ECHO × the cited
7Q10), no network.

- **Receiving water** is resolved on a ladder, never invented: ① a coordinate match to
  an EPA [ECHO](../echo/README.md) facility carrying a cited receiving water
  (`source: connector`); ② else membership in the **Ottawa River industrial corridor at
  Lima**, a coordinate-cluster *inference* (`source: assumption`, flagged `*` in the
  CLI); ③ else left null and reported `uncharacterized`.
- **Screening concentration** is a coarse `derived` order-of-magnitude value — annual
  reported water pounds, fully mixed at the receiving stream's 7Q10, no decay/mixing
  zone. It is a **screen**, not a permit determination or a measured concentration.
- **Flag bands** key on that concentration (the water pathway), *not* the total RSEI
  Score (which can be air-driven): `critical` ≥ 1 mg/L, `elevated` ≥ 0.01 mg/L.

The finding: the county's three largest water dischargers — **INEOS Nitriles, Lima
Refining, PCS Nitrogen** — cluster on the **Ottawa River at Lima**, whose cited 7Q10 is
**0.2 cfs (1Q10 = 0)**. Their releases screen at ~51 / 131 / 263 mg/L at design low
flow: the largest toxic load meets the smallest assimilative capacity. Only Lima
Refining's receiving water is independently ECHO-cited (`OH0002623 → Ottawa River`);
the other two are corridor inferences.

## Caveats / gaps

- A facility with reported **pounds but a zero Score** released only non-modeled
  media/chemicals in the modeled years — that is faithful to the data, not a gap
  (9 of 49 Allen County facilities).
- RSEI covers **TRI reporters only**. Small/unpermitted sources and non-TRI chemicals
  are out of scope by construction.
- The Score reflects the *modeling vintage* and population layer of `v2.3.12`; absolute
  values are comparable **within** this version, not across RSEI versions.
- The bulk archive (`RSEIv2312_Public_Release_Data.zip` ~447 MB; `elements` ~1.2 GB
  unzipped) is **not** committed — it caches under the git-ignored `data/cache/rsei/`
  and tables are streamed straight out of the zip. Only this curated YAML is committed.

## Corridor relevance

- **U.S. ARMY JSMC / GENERAL DYNAMICS LAND SYSTEMS** is Allen County's **#4** RSEI Score
  (~3.05 M, 98% cancer-driven, mostly nickel compounds), independently corroborating
  the GDLS-at-JSMC reading in the [defense-contractor scan](../allen-gis/README.md).
- The per-facility **water** pounds bucket ties into the
  [hydrology](../../../docs/HYDROLOGY.md) thread and the toxic-discharge screen above.
  (v2.3.12 no longer carries a facility `NPDESPermit`; receiving-water joins to the
  [Maumee NPDES inventory](../echo/README.md) now go through ECHO coordinate matches.)

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `rsei` — RSEI Toxic-Discharge Water Screen

Source: EPA RSEI (water-media releases) × EPA ECHO (receiving water) × Ohio EPA cited 7Q10 — a multi-source derivation · License: U.S. Government work (public domain) · Access: public · Site scope: basin-shared · Refresh: on-demand

Regenerate: `watermark rsei`

| file | type | lfs |
| --- | --- | --- |
| `reference/rsei/toxic-discharge-screen.yaml` | application/x-yaml | no |

### `rsei-inventory` — Allen County RSEI Toxic-Release Inventory (EPA RSEI Public Data Set v2.3.12)

Source: EPA RSEI Public Data Set v2.3.12 (EPA gaftp Public Release Data), version v2312 · License: U.S. Government work (public domain) · Access: public · Site scope: slug-scoped · Refresh: on-demand

Regenerate: `watermark rsei`

| file | type | lfs |
| --- | --- | --- |
| `reference/rsei/inventory.yaml` | application/x-yaml | no |
| `reference/rsei/{site}/inventory.yaml` | application/x-yaml | no |

<!-- catalog:end -->
