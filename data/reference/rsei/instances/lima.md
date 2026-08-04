---
site: lima
title: RSEI at Lima — Allen County, OH (FIPS 39003)
---

Lima's copy of the [RSEI inventory](../README.md): `reference/rsei/inventory.yaml` (the
reference build keeps the un-slugged path) reduced to **Allen County, OH — FIPS 39003**,
**49 facilities**. Every figure below was summed from RSEI rows by `watermark rsei` —
nothing here is fabricated, inferred, or estimated by BOSC.

## The toxic-discharge screen

The county's three largest water dischargers — **INEOS Nitriles, Lima Refining, PCS
Nitrogen** — cluster on the **Ottawa River at Lima**, whose cited 7Q10 is **0.2 cfs
(1Q10 = 0)**. Their releases screen at ~51 / 131 / 263 mg/L at design low flow: the
largest toxic load in the county meets the smallest assimilative capacity in it.

Of the 49 facilities, **13** release toxics to water and are placed on a receiving stream
by `watermark toxics`. Only Lima Refining's receiving water is independently ECHO-cited
(`OH0002623 → Ottawa River`); the other two are **corridor inferences** — inside the
profile's `toxic_corridor_bbox`, tagged `source: assumption`, and never presented as
cited. See the [receiving-water ladder](../README.md#toxic-discharge-screen-toxic-discharge-screenyaml)
for how that tag is assigned.

## Corridor relevance

- **U.S. ARMY JSMC / GENERAL DYNAMICS LAND SYSTEMS** is Allen County's **#4** RSEI Score
  (~3.05 M, 98% cancer-driven, mostly nickel compounds), independently corroborating the
  GDLS-at-JSMC reading in the [defense-contractor scan](../../allen-gis/README.md).
- The per-facility **water** pounds bucket ties into the
  [hydrology](../../../../docs/HYDROLOGY.md) thread and the screen above; receiving-water
  joins run against the [Maumee NPDES inventory](../../echo/README.md).
- The facility parents resolve against the [corridor LEI watchlist](../../gleif/README.md)
  — Cenovus for Lima Refining, General Dynamics for GDLS.

## Caveats specific to this instance

- **9 of the 49** Allen County facilities report pounds with a zero Score
  (`meta.scored_facility_count: 40`): they released only non-modeled media/chemicals in
  the modeled years. That is faithful to the data, not a gap.
- The county's latest reporting facility carries `last_year: 2022`, the v2.3.12 archive's
  own ceiling — so this instance is not vintage-truncated the way the network-wide
  re-pull note describes.
