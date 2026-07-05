# National Ambient Air Quality Standards (NAAQS)

The federal criteria-pollutant concentration limits the **Tier-1 AERMOD dispersion
screen** compares modeled ground-level concentrations against (epic #1172, #1182). Read by
`watermark.air.aermod.dispersion`; regenerable — every value is transcribed from the cited
EPA / CFR source, nothing is fabricated.

## Files

| File | What | Source |
|---|---|---|
| `naaqs.yaml` | The primary (health-based) NAAQS for the criteria pollutants the genset model emits, one row per (pollutant, averaging period), in µg/m³. | 40 CFR Part 50 / [EPA NAAQS Table](https://www.epa.gov/criteria-air-pollutants/naaqs-table). `source: reference`. |

## Discipline

- **Screening, not a compliance demonstration.** The dispersion screen models a *single*
  source with *no* monitored background concentration. A modeled peak below the standard is
  reassuring; a peak above it flags the need for a full NAAQS demonstration (background +
  cumulative sources + any permitted tiering), **not** an automatic violation. The screen
  says so in its caveats.
- **`reference`, never `verified`.** These are published federal standards — a prior the
  modeled concentration is held against, not a fact about the site. Surfaced as
  `ProvenancedValue` they are tagged `reference`.
- **NOx is screened as NO2.** AERMOD models NOx as NO2 under a full-conversion screening
  assumption, so the NOx rows carry the NO2 standards.
- **VOC has no NAAQS** (an ozone precursor, not a directly-modeled criteria pollutant) and is
  intentionally absent — a VOC dispersion run produces concentrations but no NAAQS comparison.
- **Keep it current.** The annual PM2.5 primary standard was lowered from 12.0 to 9.0 µg/m³
  by the 2024 reconsideration final rule (89 FR 16202); re-transcribe from the cited source if
  EPA revises a standard.
