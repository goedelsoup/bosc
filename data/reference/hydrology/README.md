# Hydrology reference parameters

Committed reference inputs for the water-balance / stormwater model
(`watermark.hydrology`). These are **published reference values / standing assumptions**,
not document-derived figures — each is consumed as a tagged hydrology input
(`assumption`/`reference`), distinct from live connector pulls (USGS, NOAA, ECHO)
which are cached, not committed here.

## Files

| File | What | Source |
|---|---|---|
| `cn-lookup.yaml` | SCS Curve Numbers by NLCD land-cover class × hydrologic soil group (AMC-II), plus the dry/wet AMC adjustment forms. | USDA NRCS TR-55 Table 2-2, mapped to NLCD 2021 classes (same mapping Periplus used). |
| `tier0-parameters.yaml` | The load-bearing per-method Tier-0 solver + screening constants — the SCS UH **peak factor** (484), the **initial-abstraction ratio** (Ia = 0.2·S), the default channel **Manning n** (0.04), and the low-flow **dilution bands** (violation 1:1 / tight 10:1) — externalized from buried literals so each carries a citation and a per-call override seam (WS-23 / #1623). Read by `watermark.hydrology.solver.parameters`; the solver functions take `peak_factor=` / `ia_ratio=` / `manning_n=` / `bands=` to override, and `reaches.yaml` overrides Manning n per reach. Time-of-concentration endpoints are per-site on `SiteProfile`, not here. **Gaps:** the Ia ratio (λ=0.2) is contested — Hawkins et al. (2009) support λ≈0.05; the Manning n is a stated default, **not** a measured channel roughness; the dilution bands are heuristic screening thresholds, **not** regulatory mixing-zone rules; and none of these are **locally calibrated** for the Lima loop. `source: reference`/`assumption`. | NRCS NEH-630 Ch. 16 (peak factor) · TR-55 (Ia) · Chow 1959 Table 5-6 (Manning n) · screening conventions (dilution bands). |
| `low-flow-7q10.yaml` | Cited 7Q10 (7-day, 10-year) low-flow statistics for the receiving waters. An entry may declare `permits:` — the NPDES/Ohio EPA ids the value is **binding for** (#1458) — because Ohio EPA computes the design low flow *at the outfall*, so one river can carry several correct, non-interchangeable values (the Blanchard's 0.21 cfs at Findlay's RM 56.42 and 7.78 cfs at Ottawa's RM 22.1). The basin screen prefers a permit match over any name match; the routed-network solver never reads the permit index, because a reach is not a permit. | As cited; the regulatory statistic used by `watermark.hydrology.lowflow`. |
| `low-flow-frequency.yaml` | **Independently computed** 1Q10/7Q10/30Q10 for the Ottawa-at-Lima gage (NWIS 04187100) — log-Pearson III + Weibull on climatic-year n-day minima — with the per-year minima preserved for audit, read against the cited values above. The computed 7Q10 (≈0.24 cfs) reproduces the cited 0.2 cfs; the 1Q10 is 0 cfs (dry). `source: derived`. | USGS NWIS Daily Values service, pulled via `watermark lowflow-freq --write`; computed by `watermark.hydrology.lowflow_frequency`. A *corroboration* of the cited regulatory 7Q10, **not** a substitute. |
| `low-flow-7q10.derived.yaml` | **Derived** LP3 7Q10s for the major USGS-gaged mainstems across the network's basins — the denominators that extend the assimilative screen basin-wide (`watermark basin-screen`) beyond Lima's cited streams. `source: derived`; a screening proxy (the gage value, not the discharge reach), never a substitute for a cited regulatory 7Q10. Each entry may also carry the curated `note` and the cited `published` / `regulation` / `cross_check_gages` blocks copied forward from `mainstem-gages.yaml` (#1458, #1120) — this is the file the screen actually reads, so a reservation on the gage choice that stayed behind in the input would reach nobody the number reaches; and an entry may carry `basins`, restricting that denominator to the listed basins' inventories (set where the gage's conservatism argument is geographic, e.g. the Ohio River at Greenup — #1120). A screening denominator is therefore never read without the published statistic beside it; **`regulation.status: regulated` demotes the entry to `confidence: low`** — the Blanchard's 8.67 cfs is the worked example. Regenerate with `watermark derive-low-flows`. | USGS NWIS daily discharge → log-Pearson III (`watermark.hydrology.lowflow_frequency`); gages 04193500 / 04186500 / 04182000 / 04178000. |
| `mainstem-gages.yaml` | **Curated input** to the derived screen above: the major-network mainstem USGS gages (gage ID, ECHO receiving-water aliases, and the drainage-area rationale) plus the synthesized headwaters confluences (Fort Wayne), and — optionally per gage — the `note`, the `basins` scope, and the cited `published` / `regulation` / `cross_check_gages` annotations the derivation copies forward (#1458/#1120; author them **here**, never in the regenerated output). The auditable reference table `watermark derive-low-flows` reads to produce `low-flow-7q10.derived.yaml` — previously a ~150-line dict in `watermark.hydrology.basin`. `source`: curated reference (each gage verified to return a multi-decade NWIS daily-discharge record). **[open]** only the Blanchard is annotated so far; an un-annotated gage means "not yet read against the published record", never "unregulated". | Hand-curated from USGS NWIS station metadata; loaded by `watermark.hydrology.basin.load_mainstem_gages`. |
| `routing.yaml` | Discharge routing: which stream each WWTP discharges to (`wwtp_receiving`, the assimilative-screen denominator, externalized from `watermark.hydrology.balance`), and where the BOSC campus sends its own wastewater by forcemain (`bosc_routing`). Each route is `status: confirmed` (cited) or `theorized`. **BOSC output is confirmed to Lima (FM-2) + American Bath/II (FM-1); Shawnee II's FM-3 is theorized and excluded.** | Ohio EPA NPDES fact sheets + Periplus `watch-items.geojson`; loaded by `watermark.hydrology.routing`. |
| `network.yaml` | **Routed-network topology** — the directed confluence graph (headwaters → outfalls → confluences → the Lima assimilative reach → outlet) that turns the per-stream screen into a system mass balance. Carries no flow magnitudes (the solver reads each term from the cited 7Q10s, the document-cited discharges, and the scenario draw); only the confluence ORDER is a screening choice, so the order-invariant system totals (Σ natural ≈ 1.0 cfs vs Σ effluent ≈ 12.7 cfs) are robust. | `routing.yaml` (WWTP→stream, OEPA-cited) + `ottawa-lima-tmdl.yaml` (Dug Run / Pike Run are Ottawa tributaries); solved by `watermark.hydrology.network` (`watermark network`). |
| `reaches.yaml` | **Reach geometry + contributing subcatchments** for storm-hydrograph routing — the magnitude-bearing companion to `network.yaml`. Per contributing (headwater) node: the subcatchment `area_acres` / `curve_number` / `tc_hr` that generates a design-storm hydrograph; per node's downstream edge: the trapezoidal channel `length_ft` / `slope` / optional geometry the hydrograph is routed through. Every value carries its own provenance: Pike Run + Ottawa areas are `derived` from the committed WBD HU polygons, the Pike Run reach length via Hack's law on that area; CN/Tc, mainstem-reach splits, and all slopes are stated `assumption`s. | WBD HU12/HU10 polygons (`wbd/*.geojson`) for areas + Hack's-law lengths; the rest stated Tier-0 screening assumptions. Loaded by `watermark.hydrology.hydrograph_routing`. |
| `routed-hydrograph.yaml` | **Committed routed storm-hydrograph summary** (`source: derived`) — the 25-yr design storm routed down the `network.yaml` confluence graph via constant-parameter Muskingum-Cunge: the naive summed vs. routed outlet peak, the peak `attenuation_pct` and `lag_hr`, and the per-reach attenuation/lag table. The two long per-timestep series are omitted here (they ship in the site bundle's `routed-hydrograph` feed). Regenerate with `watermark basin-route --write`; the full result recomputes deterministically offline. | Computed by `watermark.hydrology.hydrograph_routing` from `network.yaml` + `reaches.yaml` + the cited NOAA Atlas-14 corridor depth (`watermark basin-route`). Tier-0 screening, not a calibrated HEC-RAS model. |
| `water-supply.yaml` | **Lima water-supply system** — the intake/storage/treatment half the routed network presumes. The five upground (off-stream) reservoirs (Lost Creek, Metzger, Ferguson → Ottawa-fed; Bresler, Williams → Auglaize-fed; ~14.4 BG, City states ~15 BG), the four pump stations (2 Auglaize, 2 Ottawa), and the plant capacity (30 MGD rated / ~15 MGD treated). The point it encodes: Lima's supply is **off-stream storage filled at high flow**, so withdrawal is decoupled from the 7Q10 — the low-flow constraint is reservoir **drawdown**, not intake depletion. Solved by `watermark.hydrology.supply` (`watermark supply`): drought-reserve drawdown, the campus's share of plant production, net basin loss. | City of Lima Utilities water-system page (limaohio.gov/249) for reservoirs/pump-stations/15 MGD; Vision 2040 (corpus) for 30 MGD rated; USGS 04185750 (Auglaize) + 04187100 (Ottawa). `source: document`. |
| `refill-adequacy.yaml` | **Reservoir refill adequacy / drought storage requirement** — the *flow* side of the supply budget. Can high-flow pumping from the Auglaize (USGS 04186500, Fort Jennings) + Ottawa (04187100) keep the ~14.4 BG storage filled against the city+campus demand? Two answers from the gauged daily record: normal-year supply is ~15x demand (refill trivially adequate), but the binding case is drought, scored by the **sequent-peak (Rippl) storage requirement** — the worst gauged drawdown (the 1999 event) needs 14% of storage city-only, 20% with the campus, 39% at the high cooling bound; all survive, but the campus eats the margin and a drought beyond the record is the residual risk. A compact reviewed summary (no raw daily series). `source: derived`. Regenerate with `watermark refill --write`; read offline by `watermark refill` / the dossier. | USGS NWIS daily discharge (04186500 + 04187100) + `water-supply.yaml` storage; computed by `watermark.hydrology.refill`. |
| `theories.yaml` | **Toggleable network theories** — unproven structural interventions overlaid on `network.yaml` and turned on per scenario by id (`watermark network --theory <id>`; `watermark theories` lists them). Each is a thin overlay that appends directed-inflow nodes (carrying their own `assumption` magnitude) and/or re-points an edge; it never edits the cited base graph, and ships `enabled: false` so the baseline runs with none. Two are defined: the **Cole/Beery 'waterfall' roundabout** (directed stormwater to Pike Run — its inject is now **derived** by `watermark.hydrology.roundabout` from the OPC-derived ~2.9-acre impervious catchment: only ~0.012 cfs mean-annual and **zero at design low flow**, so it cannot sustainably augment Pike Run; the flushing it offers is transient storm surges ~3–7 cfs — `watermark roundabout`) and the **FM-3 Shawnee II diverter** (campus wastewater rebalanced to Shawnee II — the held-out `theorized-fm3-shawnee-ii` lead; still an `assumption` knob). The roundabout inject is `source: derived`; the diverter is `source: assumption`. | Relator working theories; overlaid on `network.yaml` (cited topology) + `routing.yaml` (the FM-3 lead); the roundabout flow is derived from the Tetra Tech OPC quantities + Atlas-14/NASA-POWER rainfall. Applied by `watermark.hydrology.network.apply_theories`. |
| `lima/sanitary-basis.yaml` | Sanitary-flow basis parameters for the Lima loop (per-site; #901). | Reference basis. |
| `maumee-tmdl-wla.yaml` | Individual NPDES total-phosphorus wasteload allocations (spring-season + daily) for the Lima-loop facilities. | Transcribed verbatim from the final Maumee Watershed Nutrient TMDL, Appendix 4 (`data/documents/maumee-tmdl/`); `source: document`. |
| `maumee-tmdl-budget.yaml` | The watershed-level TMDL phosphorus budget (loading capacity) the WLAs sit inside: Table 1A (boundary + WLA + LA + MOS + AFG = 914.4 mt/spring), the ~40% reduction mandate (Annex 4 spring targets 860 mt TP / 186 mt DRP at Waterville; 2008 baseline 1,414.1 mt), and the tiny ~1.4–1.5 mt/spring future-growth allowance — the assimilative-capacity *ceiling*. | Transcribed verbatim from the final TMDL main report + US EPA Decision Document Att.1 (`data/documents/maumee-tmdl/`); `source: document`. |
| `ottawa-lima-tmdl.yaml` | The six near-field TMDLs (Appendix 5) — esp. the **Ottawa River (Lima Area) TMDL** (US EPA-approved 2014-04-15), the loop's own receiving water, whose impairment was "exacerbated by chronic low flow conditions" + its prior per-facility TP WLAs; plus the Tetra Tech WWTP P-removal cost evaluation (Appendix 6) framing. | Transcribed verbatim from the final TMDL Appendices 5 & 6 (`data/documents/maumee-tmdl/`); `source: document`. |
| `maumee-tmdl-responsiveness.yaml` | Digest of the TMDL Responsiveness Summary: the design-flow increases baked into the WLAs (**Shawnee #2 2.0→3.0 MGD**, Elida 0.5→0.8 MGD, Wapakoneta 4.0→6.0), the **new/expanding-discharger rule** (justify added load vs the limited AFG; install treatment to meet a 0.5 mg/L individual TP limit), local commenters (Lima Refinery, PCS Nitrogen, Village of Elida, AMWA), and the CAFO/nonpoint themes. | Transcribed verbatim from the TMDL Responsiveness Summary (`data/documents/maumee-tmdl/`); `source: document`. |
| `campus-floodzone.yaml` | Whether the recorded campus parcels sit in — or near — the FEMA Special Flood Hazard Area. | Spatial intersect of the Bistrozzi footprint with the FEMA DFIRM (panel 39003C) via the City of Lima GIS floodzone layer (`watermark floodzone --footprint`); `source: connector`. |
| `wwtp-floodzone.yaml` | FEMA flood exposure of the three county WWTP discharge points (point-in-polygon + 50/150/400 m buffers). | Facility coordinates from EPA ECHO (`data/reference/echo/`) tested against the FEMA DFIRM (panel 39003C); `source: connector`. ECHO coords are a proxy for the outfall. |
| `nasa-power-climatology.yaml` | Monthly + annual climate normals (corrected precip, temperature, humidity, wind, solar) at the Lima loop point — the long-run water-budget context for the design-storm analysis. | NASA POWER climatology point API (AWS Open Data `s3://nasa-power`), pulled via `watermark nasa-power --write`; `source: connector`. Climate *normals*, distinct from the NOAA Atlas-14 design-storm *extremes*. |
| `atlas14-corridor-ddf.yaml` | NOAA Atlas-14 depth-duration-frequency table (depths in inches) for the Cole St / Bluelick corridor centroid — the 60-min through 24-hr design storms at the 2/10/25/50/100-yr return periods. The regulatory design rainfall the OPC drainage scope must meet (`watermark drainage-audit`). | NOAA Atlas-14 PDS point query, pulled via `watermark drainage-audit --write-ddf`; `source: connector`. Design-storm *extremes*, distinct from the NASA POWER *normals*. |
| `bosc-stormwater-discharge.yaml` | **ASWCD-calibrated campus storm-discharge screen** (`source: derived`) — the post-development cover calibrated to the SWCD-declared footprint (only **~115 of ~340 ac** permanently impervious, so the post CN is an area-weighted *composite* ≈81, not the blanket near-impervious ≈92 the old default assumed — the as-permitted 25-yr peak bump is ~5× smaller), the single **60-inch** outfall's Manning full-flow capacity across a 0.3–1.0% slope band, and the design-storm peak vs **Dug Run**'s cited 7Q10 (~400× — a channel-stability/erosion signal). Regenerate with `watermark storm-discharge --write`; read offline by the dossier. | Computed by `watermark.hydrology.stormwater.screen_campus_discharge` from the document-cited footprint (`data/extracted/plans/bosc-site-footprint.yaml`, Allen SWCD PRR 2026-06-12), SSURGO HSG, NOAA Atlas-14 depths, and the cited Dug Run 7Q10 (`low-flow-7q10.yaml`). |
| `thermal-discharge-screen.yaml` | **Receiving-water thermal-discharge screen** (`source: derived`, epic #1715) — the heat-side peer of the toxics screen. Two kinds of row on the same reach, at the same cited design low flows, against the same Ohio daily-maximum temperature criterion: the campus's **modelled** condenser heat rejection (with its `once_through` / `evaporative_blowdown` / `conservative_bound` heat-partition scenarios, all three exceeding), and every NPDES permit on the Ottawa corridor screened on its **own reported** effluent temperature × flow. The findings it carries: the **Lima Refinery** (OH0002623) reports a **32.2 °C** peak daily-max effluent at ~3.7 MGD — 2.8 °C over the 29.4 °C criterion — from an outfall with **no numeric thermal limit**; **PCS Nitrogen** (OH0002615) likewise, monitor-only; at the 0.2 cfs 7Q10 the reach below either outfall *is* the effluent. The design ambient is the reach's own reported in-stream station (Lima WWTP outfall 901, 24.0 °C), which *lowers* the screened severity against the 27.8 °C reference design ambient. Regenerate with `watermark thermal --offline --write`. | Computed by `watermark.hydrology.thermal` from `cooling_models` (condenser rejection) × EPA ECHO DMR effluent temperature (parameters **00010** °C / **00011** °F) + flow (50050) × the cited design low flows (`low-flow-7q10.yaml`) × Ohio temperature criteria (`../wqs/ohio-temperature-criteria.yaml`) × Great Lakes RIS tolerances (`../thermal/`, EPA-833-F-23-007). A **screen**, not a CORMIX plume model or a permit determination. |
| `tier1-swmm.yaml` + `swmm/*.inp` | **Committed Tier-1 EPA-SWMM result** — detention sizing against the **as-permitted** footprint (post-dev peak ~436 cfs held to the ~169 cfs pre-dev rate by a ~20 ac-ft basin), the blanket-paved **full-buildout bound** alongside it (~657 cfs, ~45 ac-ft), and the sanitary wet-weather surcharge that overruns the receiving plant's documented headroom. The six input decks (`tier1-{pre,post,full-buildout,detention,detention-full-buildout,sanitary}.inp`) are committed with their sha256 recorded so the run is reproducible in EPA SWMM (chain of custody). `source: derived`. | EPA SWMM5 via pyswmm, run by `watermark.hydrology.tier1`, pulled via `watermark tier1 --write`. Footprint, its declared impervious acreage (which drives the as-permitted case's imperviousness, WS-14 / #1614), storm, and plant design flows are document/connector-sourced; the full-buildout 90% imperviousness, RDII R, and basin geometry are assumptions. Read engine-free by `load_tier1` so the dossier shows real numbers offline. |

## Caveats

These are inputs, not measurements. The `cn-lookup` AMC formulas note which form is
actually applied in code. The 7Q10 in `low-flow-7q10.yaml` is the **cited regulatory**
value. Two `derived` cross-checks corroborate it without replacing it: the USGS NWIS
instantaneous connector's observed minimum discharge, and the full low-flow frequency
analysis in `low-flow-frequency.yaml` (log-Pearson III on the multi-decade daily
record). When the assimilative screen divides by a 7Q10, it uses the cited document
value — the computed one only shows the cited value is reproducible from public data.

**One reach is the exception, and every consumer must read `source` rather than assume
`document`** (#886). Where a fact sheet has been read end to end and *demonstrably states no
design low flow at all*, `low-flow-7q10.yaml` may carry a `source: derived`,
`confidence: low` entry keyed to the **outfall reach**, with the deriving record's own period
named in its citation. Wilmington's `lytle creek` is the only such entry: Ohio EPA set that
permit's limits on BADCT plus a TMDL and never computed a low flow, so the choice there was
derived-vs-nothing — and on a reach that is 99.9% effluent, "nothing" renders as *unscreened*.
The exception's full conditions are in that file's header; it is not a licence to fill gaps
where the fact sheet simply has not been pulled, which still leaves a stream **omitted**.

<!-- catalog:begin (generated by `watermark catalog render`; do not edit inside) -->

**Cataloged datasets** — generated from `data/catalog/reference/`; run `watermark catalog render --apply` after editing an entry.

### `dewatering-discharge` — Dewatering Discharge-Signal Screen + Reservoir-Recharge Context (Derived)

Source: USGS NWIS daily discharge (00060) for the campus's bracketing gages (Ottawa @ Lima, near Kalida) + the primary supply gage (Auglaize @ Fort Jennings); the reach-gain screen is derived [inference] · License: U.S. Government work (USGS NWIS) · Access: public · Site scope: lima-legacy · Refresh: on-demand

Regenerate: `watermark dewatering-discharge --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/dewatering-discharge.yaml` | application/x-yaml | no |

### `hydrology` — Hydrology Reference Bundle (Water Balance · TMDL · Routing · Stormwater)

Source: Mixed-provenance hydrology working set — USGS NWIS, Ohio EPA TMDL documents, SSURGO/document-derived stormwater inputs, and BOSC-derived routing/water-supply artifacts (per-file provenance tagged) · License: Mixed (USGS public domain · Ohio public-record TMDL values · BOSC-derived); per-file provenance tagged · Access: public · Site scope: basin:maumee · Refresh: on-demand

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/aquifer-properties.yaml` | application/x-yaml | no |
| `reference/hydrology/bosc-stormwater-discharge.yaml` | application/x-yaml | no |
| `reference/hydrology/campus-floodzone.yaml` | application/x-yaml | no |
| `reference/hydrology/cn-lookup.yaml` | application/x-yaml | no |
| `reference/hydrology/low-flow-frequency.yaml` | application/x-yaml | no |
| `reference/hydrology/maumee-tmdl-budget.yaml` | application/x-yaml | no |
| `reference/hydrology/maumee-tmdl-responsiveness.yaml` | application/x-yaml | no |
| `reference/hydrology/maumee-tmdl-wla.yaml` | application/x-yaml | no |
| `reference/hydrology/network.yaml` | application/x-yaml | no |
| `reference/hydrology/ottawa-lima-tmdl.yaml` | application/x-yaml | no |
| `reference/hydrology/reaches.yaml` | application/x-yaml | no |
| `reference/hydrology/refill-adequacy.yaml` | application/x-yaml | no |
| `reference/hydrology/routed-hydrograph.yaml` | application/x-yaml | no |
| `reference/hydrology/lima/sanitary-basis.yaml` | application/x-yaml | no |
| `reference/hydrology/theories.yaml` | application/x-yaml | no |
| `reference/hydrology/thermal-discharge-screen.yaml` | application/x-yaml | no |
| `reference/hydrology/tier0-parameters.yaml` | application/x-yaml | no |
| `reference/hydrology/tier1-swmm.yaml` | application/x-yaml | no |
| `reference/hydrology/water-supply.yaml` | application/x-yaml | no |
| `reference/hydrology/wwtp-floodzone.yaml` | application/x-yaml | no |

### `hydrology-atlas14-corridor-ddf` — NOAA Atlas-14 Corridor Design-Storm Depths (Depth-Duration-Frequency)

Source: NOAA NWS HDSC Atlas-14 — precipitation-frequency point query (Partial-Duration Series, English depths) · License: U.S. Government work (public domain) · Access: public · Site scope: slug-scoped · Refresh: on-demand

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/atlas14-corridor-ddf.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/atlas14-corridor-ddf.yaml` | application/x-yaml | no |

### `hydrology-low-flow-7q10` — Receiving-Stream Design Low Flows (7Q10) — Cited + Derived

Source: Cited 7Q10s read from Ohio EPA NPDES fact sheets (document) + mainstem 7Q10s derived from USGS NWIS daily discharge via log-Pearson III · License: U.S. Government work (USGS-derived) + Ohio public record (cited fact-sheet values) · Access: public · Site scope: lima-legacy · Refresh: on-demand

Regenerate: `watermark derive-low-flows`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/low-flow-7q10.derived.yaml` | application/x-yaml | no |
| `reference/hydrology/low-flow-7q10.yaml` | application/x-yaml | no |
| `reference/hydrology/mainstem-gages.yaml` | application/x-yaml | no |

### `hydrology-nasa-power-climatology` — NASA POWER Climate Normals — site climatology

Source: NASA POWER (Prediction Of Worldwide Energy Resources) — climatology point REST API (satellite-derived monthly/annual normals) · License: U.S. Government work (public domain) · Access: public · Site scope: slug-scoped · Refresh: on-demand

Regenerate: `watermark nasa-power --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/nasa-power-climatology.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/nasa-power-climatology.yaml` | application/x-yaml | no |

### `hydrology-ohio-principal-streams` — Ohio Principal Streams & Drainage Areas (ODNR, Sherman 1925 / 1999 reprint)

Source: Ohio DNR, Division of Water — 'Principal Streams and Their Drainage Areas' (C.E. Sherman map, July 1925; reprinted 1999) · License: Ohio state-government work (public domain) · Access: public · Site scope: basin-shared · Refresh: static

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/ohio-principal-streams/principal-streams-and-drainage-areas.pdf` | application/pdf | yes |

### `hydrology-reaches` — Reach-network river centerlines — NHDPlus geometry (USGS NLDI)

Source: USGS NLDI navigation over the NHDPlus flowline network (per-site nav plans — Lima's mainstem gage 04187100 + WWTP snaps; Fort Wayne's three cited fork/mainstem gages; Sidney's mainstem + Loramie gages plus two campus-drainage snaps) · License: U.S. Government work (public domain) · Access: public · Site scope: slug-scoped · Refresh: on-demand

Regenerate: `watermark reaches --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/reach-nav.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/reach-nav.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/network.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/reaches.yaml` | application/x-yaml | no |
| `reference/hydrology/reaches/{site}.geojson` | application/geo+json | no |

### `hydrology-routing` — Per-Site Discharge Routing — WWTP receiving stream, permitted design flow, forcemains

Source: Hand-authored per-site routing table — each WWTP→stream route and its permitted average design flow transcribed from that plant's own Ohio EPA NPDES permit or fact sheet in the corpus and cited per route; Lima's BOSC forcemain graph additionally from the Periplus watch-items forcemain features · License: Public record (Ohio R.C. 149.43); BOSC-curated · Access: public · Site scope: slug-scoped · Refresh: on-demand

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/routing.yaml` | application/x-yaml | no |
| `reference/hydrology/{site}/routing.yaml` | application/x-yaml | no |

### `hydrology-swmm` — Tier-1 EPA SWMM5 Input Decks (Pre / As-Permitted / Full-Buildout / Detention / Sanitary)

Source: BOSC-generated EPA SWMM5 (.inp) model decks over the campus parcels + Atlas-14 design storm · License: BOSC work product (derived model decks; EPA SWMM engine is public-domain) · Access: public · Site scope: lima-legacy · Refresh: on-demand

Regenerate: `watermark tier1 --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/swmm/tier1-detention-full-buildout.inp` | application/octet-stream | no |
| `reference/hydrology/swmm/tier1-detention.inp` | application/octet-stream | no |
| `reference/hydrology/swmm/tier1-full-buildout.inp` | application/octet-stream | no |
| `reference/hydrology/swmm/tier1-post.inp` | application/octet-stream | no |
| `reference/hydrology/swmm/tier1-pre.inp` | application/octet-stream | no |
| `reference/hydrology/swmm/tier1-sanitary.inp` | application/octet-stream | no |

### `hydrology-toledo-waterville-spill-monitor-read` — Maumee-at-Waterville (04193500) Continuous-Monitor Read — Napoleon Spill

Source: USGS NWIS instantaneous-value record at 04193500 (Maumee River at Waterville OH) read against the Napoleon / Huston Creek fertilizer-spill timeline; travel time via NLDI + Manning · License: U.S. Government work (USGS-derived) · Access: public · Site scope: site:toledo · Refresh: on-demand

Regenerate: `watermark waterville-monitor --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/toledo/waterville-spill-monitor-read.yaml` | application/x-yaml | no |

### `hydrology-wbd` — USGS Watershed Boundary Dataset — Campus HUC Boundaries (HU10/HU12)

Source: USGS National Map Watershed Boundary Dataset (WBD) — ArcGIS REST MapServer HU sublayers · License: U.S. Government work (public domain) · Access: public · Site scope: lima-legacy · Refresh: on-demand

Regenerate: `watermark wbd --write`

| file | type | lfs |
| --- | --- | --- |
| `reference/hydrology/wbd/0410000704-middle-ottawa-river.geojson` | application/geo+json | no |
| `reference/hydrology/wbd/041000070404-pike-run.geojson` | application/geo+json | no |

<!-- catalog:end -->
