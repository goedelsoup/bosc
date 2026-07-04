# GreenOps — carbon-intensity & water factor tables

The `reference` factor tables the footprint derivation (#1083) multiplies our electricity
figure by, so the electricity → CO2e / source-mix / water conversion reads authoritative
published factors rather than a hand-maintained constant. Every figure here is
`source: reference` — an authoritative published factor, **not** a metered fact about our
own consumption. Nothing here is `verified`; the derivation that applies these stays
`derived`, and PUE / utilization / which-subregion-a-workload-runs-in remain stated
`assumption`s upstream.

## EPA eGRID subregion factors (`egrid-<year>.yaml`, #1082)

- **Source:** EPA Emissions & Generation Resource Integrated Database (eGRID), the annual
  subregion file (`SRL<yy>` sheet). Regenerate with `watermark greenops egrid --write`
  (public workbook, no API key). The raw ~20 MB xlsx caches under
  `data/cache/greenops/egrid/` (git-ignored); only the reduced subregion rows are
  committed.
- **Vintage:** set by `WATERMARK_EGRID_YEAR` / `egrid_data_url` (default eGRID2023). A new
  vintage is a config change: bump the year and point the URL at that release's workbook.
- **Fields** (selected by field code from the sheet's own header row, never by index):
  `SRC2ERTA` — annual CO2-equivalent total output emission rate (lb/MWh, the
  electricity→CO2e factor); `SRTRPR` — total-renewables generation share; the `SR*PR`
  columns — the per-fuel generation mix. The renewable grouping
  (hydro/biomass/wind/solar/geothermal) is our declared classification, cross-checked
  against eGRID's own `SRTRPR` total.

## WUE benchmarks (`wue-benchmarks.yaml`, #1082)

- **Source:** hand-curated Water Usage Effectiveness benchmarks (liters of water per kWh)
  from published data-center water studies (EPRI, Uptime Institute) plus the upstream
  water-for-electricity intensity (NREL / EPRI). Not a live pull — an in-code canonical
  emitted by `watermark greenops egrid --write`, so it stays regenerable and schema-checked.
- **Bases:** `site` WUE is direct on-site cooling water; `source` WUE is the water consumed
  upstream to generate the electricity drawn. The two are on different bases and must never
  be summed across bases or compared. Representative rows are marked low-confidence.
