# WPAFB groundwater — reference corroboration & dated negatives

Companion to the two ingested primary records ([SSA designation](ssa-53fr15876.epa.yaml),
[CERCLA FFA](cercla-ffa-1991.epa.yaml)): the external authoritative datasets that corroborate
the plume-on-sole-source-aquifer story, and the sourced negatives that bound what is *not* on
the record. Pointers, not committed datasets — the USGS model/data archives are downloadable
but not vendored here.

## USGS reference datasets — `[reference]`

### USGS SIR 2023-5017 — PFAS in GM-BVA groundwater, 2019–20

- **Title:** *Per- and polyfluoroalkyl substances in groundwater from the Great Miami
  buried-valley aquifer, southwestern Ohio, 2019–20.* Published **2023-03-17**.
- **Producer:** U.S. Geological Survey, in cooperation with the **Miami Conservancy District**
  (Dayton, Ohio).
- **Design:** 23 wells (22 sampled) across the GM-BVA; total depths 21–101 ft; 24 PFAS
  analyzed by two isotope-dilution adaptations of EPA Method 537.1.
- **Key finding:** PFOS of **1.9 ng/L** at well CL-275 and PFOA of **2.1 ng/L** at well
  BU-1106 exceeded the EPA June-2022 interim health-advisory guidances (by ~9,500% and
  ~52,500% respectively — the advisories were sub-ng/L). Confirms PFAS is present in the
  sole-source aquifer at the regional scale, independent of the WPAFB CERCLA record.
- **URL:** <https://pubs.usgs.gov/publication/sir20235017/full>

### USGS SIR 2021-5115 — GM-BVA groundwater-flow model near WPAFB

- **Title:** *Update of the groundwater flow model for the Great Miami buried-valley aquifer
  in the vicinity of Wright-Patterson Air Force Base near Dayton, Ohio.* Author **Alexander D.
  Riddle**, published **November 2021**.
- **Model:** steady-state, three-dimensional, three-layer MODFLOW model covering ~**241 sq mi**
  in Montgomery, Greene, and Clark Counties; recalibrated to October 2018 conditions;
  **228 pumped wells** simulated. Glacial sands and gravels in a buried bedrock valley yield up
  to 2,000 gpm; the shale bedrock is poorly permeable.
- **Relevance:** the plume-migration / well-field-capture setting for the WPAFB TCE/PFAS plume —
  the quantitative model behind "the buried-valley supply is the water story."
- **URL:** <https://pubs.usgs.gov/publication/sir20215115>

## Dated negatives (sourced absences, not gaps)

- **No ATSDR PFAS exposure assessment for WPAFB/Dayton** (checked 2026-07-10 and re-checked
  2026-07-14 against the ATSDR PFAS exposure-assessment site). WPAFB is **not** among the ten
  communities in ATSDR's PFAS Exposure Assessment program (the 2018 NDAA cohort). `[verified-negative]`
  - Nuance: ATSDR *does* hold two older, site-specific WPAFB products — a **Public Health
    Assessment (November 1999)** and a **Health Consultation on methane migration at Landfills
    8 & 10 (1990)** — both predating the PFAS issue. So the accurate statement is: no
    **PFAS-specific** ATSDR exposure assessment or health consultation exists, not that ATSDR
    has never assessed the base.

## Deferred / verification-task items (not ingested here)

- The **2024-12-16 EPA environmental-indicator revocation letter** (human-health + groundwater-
  migration no longer "under control") lives in the AFCEC/EPA Administrative Record; it is the
  compliance/standing-watch pull, not this record-ingest.
- **WPAFB PFAS NPDWR notification (2025-01-24)** for PWS OH2903412 (Area A) / OH2903312 (Area B)
  is robots-blocked (HTTP 403) — a manual pull.
- OEPA NPDES fact sheets (receiving water + passby) for OH0024881 / OH0049646 are the #464/#463
  verification/screen task.
