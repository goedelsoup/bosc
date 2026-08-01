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
  from published data-center water studies (AWS's own published WUE, EPRI, Uptime Institute)
  plus the upstream water-for-electricity intensity (Macknick et al. 2012). Not a live pull —
  an in-code canonical emitted by `watermark greenops egrid --write`, so it stays regenerable
  and schema-checked. Every row carries a dated citation and a band (#1643/F5).
- **Bases — three, and the distinction is load-bearing:** `site` is facility cooling water
  per kWh of **IT** load; `upstream` is the increment consumed generating the electricity
  delivered to the **whole facility** (IT x PUE) — a term you *add* to a site WUE, not a WUE
  on its own; `source` is an already-complete site+upstream figure. Site + upstream compose
  into a source-basis total; site + source double-counts cooling and must never be summed.
- **Which row applies:** the derivation selects `aws_published_site`, because the platform
  runs no data center — the cooling water is AWS's, apportioned to us by billed IT-kWh
  (#1643/F4). `industry_average_site` is kept for comparison and deliberately not applied.

## Inference energy (`inference-energy.yaml`, #1643/F2)

- **Source:** hand-curated per-1,000-**output**-token energy coefficients by model class,
  from published third-party measurements (Epoch AI 2025-02, Jegham et al. 2025-05, Google
  2025-08). No provider publishes a per-token energy figure for its hosted models, so this
  is a `reference` table of outside estimates, never a metered fact. Emitted alongside the
  other factor tables by `watermark greenops egrid --write`.
- **Banded on purpose:** published estimates of the same quantity span roughly an order of
  magnitude, driven mostly by boundary — an accelerator-only figure excludes host CPU/DRAM,
  idle capacity and facility overhead, and Google's 2025-08 production measurement found the
  accelerator is only 58% of full-stack energy.
- **Basis:** output tokens. Decode dominates inference energy; prefill is far cheaper per
  token, so applying these to an input+output total would overstate a cache-heavy agentic
  workload several-fold. An unmapped model id is priced at `default_class`, never dropped.
