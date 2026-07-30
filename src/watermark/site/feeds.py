"""The content-bundle contract — typed models for every feed the frontend reads.

These Pydantic models *are* the contract (issue #53, Tier 1). Each ``export_X`` in
the ``watermark.site.*`` modules returns one of these, and :mod:`watermark.site.export` writes
them under ``data/site/bundle/`` with a ``manifest.json`` and a JSON Schema per feed
(generated from these models, so schema and code never drift).

Two primitives carry provenance into every figure-bearing feed (issue #60), so a
consumer can render ``[verified] cite p.X`` or an approximate ``~`` value purely from
the bundle — no re-deriving:

* :class:`Citation` — where a value came from. Its ``source_kind`` maps onto the
  dossier's evidence discipline exactly as :class:`watermark.hydrology.model.ProvenancedValue`
  does (``document``/``connector`` → ``verified``; ``assumption``/``derived`` →
  ``inference``); ``verified`` is a derived boolean the frontend reads directly.
* :class:`Figure` — a number that preserves the ``~`` approximate marker as *data*
  (``approximate: true``), not as formatted text.

The already-provenanced feeds (rsei, lei, economics-baseline, hydrology-scenarios)
export their existing :mod:`watermark` Pydantic models unchanged — they already satisfy the
#60 discipline through ``ProvenancedValue`` / an inventory ``meta.source`` — so this
module only models the feeds whose renderers worked off dataclasses or raw dicts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field

from watermark.provenance import Confidence as Confidence
from watermark.provenance import EvidenceRegister, source_is_verified
from watermark.provenance import SourceKind as SourceKind
from watermark.site.readiness import State, Tier  # the readiness vocabulary SSOT (#1220)
from watermark.sites import (
    CoolingModelType,
    DcEndUse,
    FacilityKind,
    FacilityLifecycle,
)  # the facility vocab (#1628 / #1664)

# --- bundle contract version ---------------------------------------------------
# Bumped per the back-compat policy in data/site/bundle/README.md: PATCH for additive
# optional fields, MINOR for new feeds, MAJOR for a breaking field change/removal.
# 1.1.0: added the `concepts` feed (issue #68, the wiki concept-glossary store).
# 1.2.0: source-document rendering (epic #274) — `DocumentItem` gains real
#   `media_type`/`render_class` (#275), `RecordItem` gains the `source_doc_*` join (#276).
# 1.3.0: `DocumentItem` gains `published` — the default-deny public allowlist flag (#280).
# 1.4.0: adds the `network` object feed — the cross-site basin synthesis (watermark.network; #308/#323).
# 1.5.0: adds the `hypotheses` + `hypothesis-assessments` feeds — the boom-origin lenses and their
#   (site x hypothesis) evidence cells (watermark.hypotheses; #308). The directory reads these instead of
#   the formerly-hardcoded LENSES/LENS_DATA, so each cell now ships with a Citation.
# 1.6.0: adds the `catalog` feed — the published data catalog (watermark.catalog projected to
#   CatalogItem + the reconcile observed snapshot; epic #631 Phase 3 / #659).
# 1.6.1: the manifest gains `site` — the network-site slug a bundle is for, so it self-identifies
#   (per-site bundle scoping; #762).
# 1.7.0: adds the per-site `leads` feed — the open-leads board read from a committed per-site store
#   (`data/site/leads.yaml`, slug-scoped), so a peer carries its own leads, not Lima's (#796).
# 1.8.0: adds the optional `ask-embeddings` feed — all-MiniLM-L6-v2 document vectors for hybrid
#   BM25 + vector retrieval (#329); absent when `watermark export --no-embeddings` is used.
# 1.9.0: `hydrology-scenarios` rows gain `cooling_model` (top-level, on the scenario, and on its
#   basis) plus the basis honesty flags `method_disclosed` / `is_bracketed` and the hybrid
#   `seasonal_months` — the cooling-model typology (epic #1060). An `unknown` model means the
#   method is undisclosed: render the bracketed range, never a single headline (#1057).
# 1.10.0: keep annual time series (issue #1111). `economics-baseline` trend points (`YearTotal`)
#   gain `establishments` and now span a decade (QCEW 2014-2024, not two years); adds the
#   `consumer-energy` feed — the EIA state price/sales dataset with each series' full annual
#   history (`points`) plus its latest cited value, so the site can chart price trends.
# 1.11.0: adds the `catalog-index` object feed — the hydrated catalog of addressable "grabbable"
#   atoms (handle grammar `<kind>:<site>:<local_id>`) the user-authored Stories write/read paths
#   resolve against, plus `catalog_version` for handle-drift revalidation (epic #1090 / #1093).
# 1.12.0: adds the `economics-demand-pressure` object feed (#1105) — the facility demand→consumer-
#   price-pressure sensitivity (`FacilityDemandPressure`): households-equivalent, demand share, and
#   the STYLIZED price-pressure band, each a `ProvenancedValue`. Facility-gated — absent for a thin
#   site with no documented facility (mirrors `derive_demand_pressure`'s own gate).
# 1.13.0: adds the `routed-hydrograph` object feed (#1184) — the loop's design-storm hydrograph
#   routed down the cited confluence graph via Muskingum-Cunge (`RoutedHydrographNetwork`): the
#   routed vs. naive-summed outlet hydrograph series, the peak `attenuation_pct` + `lag_hr`, the
#   per-reach attenuation/lag table, and the `site` label. Absent when the topology or reach
#   table is missing.
# 1.14.0: the cooling `basis` (`CoolingBasis`, embedded in `hydrology-scenarios`) gains the optional
#   `makeup_high` ProvenancedValue — the campus intake at the upper consumptive bound (#1153), read
#   by refill instead of back-calculating consumptive_high/consumptive_fraction across incompatible
#   per-archetype bases. Additive/optional: absent (null) for the fraction-uncertainty archetypes.
# 1.15.0: `economics-baseline` surfaces QCEW wages (#1109) — the county total and each sector gain
#   `avg_annual_pay` (USD/year) and `avg_weekly_wage` (USD/week) `ProvenancedValue`s (already in the
#   fetched CSV, previously dropped). Optional/backward-compatible: a suppressed or zero-wage slice
#   omits the field rather than asserting a fabricated $0.
# 1.16.0: adds the `energy-burden` object feed (#1110) — median household income (Census B19013)
#   with derived electricity / gas / combined household energy burden (% of income), a fully
#   `[derived]` consumer-impact metric alongside `consumer-energy`. Present only where the site's
#   committed baseline carries income; absent (section degrades) otherwise.
# 1.17.0: the manifest gains the `readiness` block (#1220/#1222) — the standing domain-activation
#   readiness (`SiteReadiness`): the five domains' `absent|seeded|live` states plus the derived
#   `tier` (`stub|backdrop|case|reference`), recomputed at every export from feed counts + the
#   profile (watermark.site.readiness). The frontend reads it instead of re-deriving section gating.
# 1.18.0: adds the air-quality & backup-generation dispatch feeds (epic #1172, #1181) —
#   `air-scenarios` (Tier-0 emissions scenarios + synthetic-minor NSR cap check, #1177) and
#   `air-dispersion` (Tier-1 AERMOD concentration screen vs NAAQS, event-anchored, #1182).
#   Dispersion is facility+permit-gated (absent → section locks); dispersion runs carry
#   `available=False` when the AERMOD binary/met is absent (deck + NAAQS basis real, no
#   fabricated concentration). Both reuse the domain models (watermark.air), like hydrology-scenarios.
# 1.19.0: adds the `air-dispersion-field` collection feed (epic #1237 / #1232) — the gridded AERMOD
#   concentration surface per pollutant (`DispersionField`) the deck.gl FieldLayer renders: the
#   receptor grid reshaped into per-averaging-period `values[]`, the model-grid→lon/lat `geo_ref`
#   corner box, per-period NAAQS lines, and a fixed `provenance: assumption` marker (the CBI-redacted
#   stack ⇒ [inference]). Reference-site gated; `available=False` with empty `values` when the AERMOD
#   binary/met is absent (geometry real, no fabricated concentration).
# 1.20.0: adds the `reach-network` object feed (epic #1237 / #1235) — the real river-centerline
#   geometry (`ReachNetwork`) the deck.gl FlowLayer particle-advection viz advects over: one
#   downstream-oriented `ReachLine` (lon/lat polyline) per model reach node, keyed by `node_id`
#   so the frontend joins flow magnitude (routed-hydrograph) + deficit (hydrology-scenarios) by
#   node. Geometry is verbatim NHDPlus via USGS NLDI (watermark.hydrology.reach_geometry),
#   committed under data/reference/hydrology/reaches/. Reference-site gated like routed-hydrograph;
#   absent when the committed centerline file is missing (nothing invented).
# 1.21.0: adds the `greenops` object feed (#1076/#1084) — Watermark's own compute footprint
#   (`GreenopsReport`): the usage → electricity → water derivation, with headline stats,
#   compute-by-function / AI-by-task / monthly-electricity / water breakdowns, and a methodology
#   block, every figure a `ProvenancedValue` tagged reference/derived/assumption (never verified —
#   our own consumption is modeled, not metered). Global like `network`: emitted into every
#   bundle identically from the committed data/reference/greenops/footprint.yaml (a modeled
#   placeholder when that artifact is absent, so the feed is never skipped).
# 1.22.0: adds the `water-seasonal-field` object feed (epic #1237 / #1236) — the seasonal
#   evaporation / net-atmospheric-withdrawal climograph the deck.gl FieldLayer renders as a
#   cartesian month-axis strip (Phase 2, water). The field scalar is net atmospheric withdrawal
#   (reference ET0 - precip, mm/day, from the cited NASA POWER normals + FAO-56 ET0); the deficit
#   boundary (net=0) is the threshold isopleth. The per-month low-flow `multiple` rides along for
#   the SSR table/probe and is [inference] (it screens the modeled buildout draw). Reference-site
#   gated; `available=False` with empty `months` when the climate/scenario inputs are absent.
# 1.23.0: adds an optional quantitative range to `ProvenancedValue` (#760) — `low`/`high`
#   absolute bounds around the central `value`, distinct from the qualitative `confidence`.
#   A measured/derived estimate whose honest representation is a band ("226 ± ~35 ac") now
#   carries the spread as data rather than prose in the citation, so the bundle/frontend and
#   the uncertainty engine (#271) consume it uniformly. Both bounds optional (a document-
#   verbatim figure stays a single value); back-compatible — every feed embedding a
#   `ProvenancedValue` gains the two nullable fields.
# 1.24.0: adds the `contacts` collection feed — the curated per-site directory of human contact
#   points (petitioners, organizers, officials, community groups, outlets) a reader can reach.
#   Slug-scoped committed YAML (`data/site/contacts.yaml`, sibling reads its own `<slug>/`),
#   modeled like `leads` (#796): every contact names a real `source` (no fabricated people, per
#   the data-discipline rules) and carries only *public* routing (`links`) — private hand-off
#   addresses stay server-side. The spine the petition-connect + bulletin surfaces reference;
#   absent → the feed is skipped and the section degrades. Back-compatible (additive feed +
#   the `contact` catalog kind).
# 1.25.0: adds the `facts` collection feed — the normalized `(subject, predicate, value, unit,
#   status, evidence)` projection over the bundle's already-provenanced numeric facts (#1587,
#   epic #1579 Phase 3). A `catalog-index`-style post-pass (`watermark.site.facts`): it mints no
#   values and copies no payloads, it re-keys each `ProvenancedValue` already in the economics /
#   greenops / hydrology / air feeds (plus the derived facility `PowerBasis`) into one flat,
#   queryable table so a fact question is a tiny retrieval + arithmetic, not a whole-record pull.
#   `status` is the evidence-discipline tag derived from each value's `source_kind`
#   (`watermark.provenance.evidence_tag`: document/connector→verified, reference→reference,
#   assumption/derived→inference; `open` is reserved for unquantified facts). `evidence` reuses
#   the shared provenance shape but `page` stays null where the source `ProvenancedValue` carries
#   none — never invented (chain of custody). Powers the `get_facts` MCP tool. `rsei`/`records`
#   projection + `aggregate_facts` (#1588) are deferred follow-ups. Back-compatible (an additive
#   collection feed; registered in the `catalog` like any dataset, no new catalog-index kind).
# 1.26.0: adds the `passages` collection feed + its `passage-embeddings` companion — the page-level
#   excerpt index the `search_passages` MCP tool returns instead of a whole extracted record (#1589,
#   epic #1579 Phase 3). `passages` carries one `PassageItem` per text-bearing page of a *published*
#   source PDF (scoped to the default-deny publish allowlist #280, so no non-published source text
#   ships): `document_id` joins to the `documents` feed / `get_document` by `DocumentItem.rel`, `page`
#   is the 1-indexed printed page, `text` is the pypdf text-layer extraction verbatim (garbled OCR for
#   scans — a locator, never a transcription; image-only pages are omitted). `passage-embeddings` is
#   the all-MiniLM-L6-v2 vector companion (the same 384-dim space as `ask-embeddings`) for the hybrid
#   BM25+vector search; like `ask-embeddings` both feeds are always emitted (empty when the source PDFs
#   are absent / `--no-embeddings`) so the schema set stays stable. Not cataloged (a retrieval index,
#   like `ask-embeddings`). Back-compatible (two additive feeds, no changed shapes).
# 1.27.0: adds the `open-questions` collection feed (#1568, epic #1560 workstream B) — the aggregated
#   still-open threads of the corpus, each with provenance. A post-pass projection
#   (`watermark.site.open_questions`) over the just-assembled `leads` + `hypothesis-assessments` feeds:
#   every `[open]`-tagged lead (wired to the `lead:kind:question` / `lead:status:unanswered` label
#   vocabulary) + every `[open]`-tagged hypothesis cell, ported from yidam's `open-questions` model
#   (open ⇔ the `[open]` tag). Skipped for a site with no open threads, so `hasFeed("open-questions")`
#   is false and the section degrades rather than shipping an empty list. Not cataloged (a derived
#   view — the underlying leads are already cataloged). Back-compatible (one additive feed).
# 1.27.1: `DocumentItem` gains optional version/duplicate-cluster metadata — `duplicate_cluster`,
#   `canonical_document_id`, `version`, `supersedes` (#1590, epic #1579 Phase 3), projected from the
#   curated custody manifest (`data/site/document-versions.yaml`) by watermark.site.docversions so
#   retrieval can collapse a filing's versions to the canonical one while retaining a superseded
#   version's distinct evidence (`deduplicate` / `version_policy` args on search_corpus/passages).
#   Additive/optional — absent for a document with no declared cluster (PATCH, back-compatible).
# 1.28.0: adds the `corpus-index` collection feed (#1573, epic #1560 workstream C) — the at-a-glance
#   map of the yidam corpus mirror, one `CorpusNodeItem` per projected node with its display `kind`,
#   in/out degree, line count, and freshness (last commit of the committed source it derives from).
#   A post-pass over the just-built `Mirror` (`watermark.site.corpus_index`): `links_in`/`links_out`
#   are the resolved edge counts, `lines` replicates `write_mirror`'s serialization for parity with
#   `yidam corpus-index`, and `updated` is the newest git commit date over the node's backing corpus
#   file(s) (null when a node is aggregated/code-derived — never fabricated). Always emitted (every
#   site's mirror has ≥1 node), so the schema set stays stable. Not cataloged (a derived view of the
#   corpus, like `open-questions`). Back-compatible (one additive feed).
# 1.29.0: the manifest gains an optional `exports` block (#1574, epic #1560 workstream D1) — the
#   graph exports (RDF Turtle + JSON-LD, GraphML) of the corpus mirror (#1561), rendered by
#   `watermark.site.graph_exports` and written under the bundle's `exports/` as downloadable
#   research artifacts (the wiki graph page links them). Each `ExportRef` names a file, its media
#   type, format, and node/edge counts. Additive/optional — absent when the mirror wasn't
#   projected for this bundle (a redirected/test export); the frontend degrades to no downloads
#   (one additive manifest field, no changed feed shapes, back-compatible).
# 1.30.0: adds the `corpus-nodes` retrieval feed (#1575, epic #1560 workstream D2) — the searchable
#   substrate behind the wiki "ask this concept" affordance. A second post-pass over the same
#   `Mirror` the `corpus-index` map is built from (`watermark.site.corpus_nodes`), but carrying each
#   node's *searchable text* (`text`, the one canonical `node_text` the semantic index also embeds,
#   so the lexical and vector surfaces tokenize the same content), its evidence tag when it bears one
#   (`evidence`), its page key (`ref`, a concept slug today), and its undirected 1-hop adjacency
#   (`neighbors`) so the frontend can scope client-side lexical retrieval to one concept's corpus
#   neighborhood — no server, offline. Always emitted (the mirror is never empty), so the schema set
#   stays stable. Not cataloged (a derived retrieval index, like `corpus-index`/`open-questions`).
#   Back-compatible (one additive feed).
# 1.30.1: the `rsei` feed (the `RseiInventory` model) gains a per-facility `top_water_chemicals`
#   array — each facility's cumulative pounds released *to water* by chemical (the media-3 breakdown,
#   reconciling to `pounds_by_media["water"]`), the input the chemical-specific toxic screen reads
#   (WS-07 / #1607). Additive/optional (absent facilities default to `[]`), so an existing rsei.json
#   without it stays valid — PATCH, back-compatible.
# 1.30.2: each `hydrology-scenarios` `AssimilativeCheck` gains `effluent_credited_ratio` +
#   `effluent_credited_flag`, and its long-reserved `upstream_returns` field is now *computed*
#   (WS-15 / #1615): the permitted effluent already in the reach (Σ other WWTPs sharing the
#   receiving water) credited into a second, effluent-credited dilution ratio, presented alongside
#   the conservative cited-7Q10-only `dilution_ratio` (unchanged). Additive/optional (all three are
#   null when a plant is alone on its stream), so an existing feed row stays valid — PATCH,
#   back-compatible.
# 1.30.3: each `routed-hydrograph` reach (the `ReachRouting` model) gains `subreaches` + `courant`
#   — the sub-reach discretization the Muskingum-Cunge routing ran at (WS-09 / #1609): the reach is
#   split into `subreaches` Courant≈1 steps routed in series (curing the coarse-single-step
#   coefficient blow-up the old output clamp masked), and `courant` (c·Δt/Δx, ≈ 1) is the routing
#   validity flag. Additive with defaults (`subreaches=1`, `courant=0.0`), so an existing
#   routed-hydrograph.json without them stays valid — PATCH, back-compatible.
# 1.31.0: adds the `facility` collection feed (#1628, epic #1626 F2) — the machine-readable
#   projection of the now multi-facility `SiteProfile.facilities`: one `FacilityItem` per disclosed
#   campus carrying its lifecycle `status`, structured `operator` / `end_use`, IT-load bracket,
#   site-plan disclosure, cooling archetype, and resolved geometry link. The manifest gains an
#   optional `facility` summary block (`FacilitySummary`: the primary campus's status + the facility
#   count) the frontend reads for the per-site status badge (retiring the hardcoded TS
#   `FACILITY_STATUS` dict), and the `network` feed's `NodeActivity` gains `facility_status` /
#   `operator` / `end_use` / `facility_count`. Facility-gated (feed skipped, block absent for a
#   facility-less site). One new feed → MINOR, back-compatible (the manifest block + activity fields
#   are optional, so a pre-1.31 bundle degrades to `investigation`).
# 1.32.0: the `defense-contractors` feed's `DefenseContractorItem` gains a resolved federal-dollar
#   join (#1662, ME-C): each seed prime carries the USASpending awards its matched corpus entities
#   resolve to (`awards` — `ContractorAward` with `total_obligations`, `nexus`, a defense-vs-civilian
#   `defense_share`, the trailing `annual_obligations` flow, and the top `by_psc` / `by_naics`
#   category mix), plus a rolled-up `total_obligations` scalar + strongest `nexus`. The federal
#   dollars already reached the entity graph; this joins them to the feed that names the contractor.
#   Additive/optional (a contractor with no matched award keeps empty `awards` / null totals), so a
#   pre-1.32 defense-contractors.json stays valid — MINOR, back-compatible.
# 1.32.1: each `hydrology-scenarios` `ScenarioResult` gains three optional provenanced fields
#   (#1633, epic #1626 F7) — `receiving_summer_30q10` + `receiving_1q10` (the cited seasonal design
#   low flows) and `campus_routed_discharge` (the demand node's own routed industrial discharge,
#   Lima's FM-2). They surface figures already grounded in the balance / low-flow table so the
#   frontend dilution model reads them per-site instead of hardcoding Lima's floors + FM-2 constant.
#   All three default null (a scenario without them stays valid) — PATCH, back-compatible.
# 1.33.0: the `economics-baseline` feed is made honest about the federal / military employment the
#   county QCEW cannot see (#1661, ME-B). `IndustryEmployment.latest` gains `government` — the
#   federal/state/local ownership slices (QCEW own 1/2/3, agglvl 71) the private-ownership sector
#   mix structurally cannot show, closing the total-vs-sectors reconciliation (at a federal enclave
#   the federal row is the county's largest employer yet carries no NAICS sector). `EconomicBaseline`
#   gains `unit_caveat` (the county-straddle caveat promoted from prose `note` to a structured field)
#   and `coverage_note` (a standing caveat documenting the excluded uniformed active-duty military).
#   All additive/optional (government defaults `[]`, unit_caveat null, coverage_note a model default),
#   so a pre-1.33 economics-baseline.json stays valid — MINOR, back-compatible.
# 1.33.1: each `hydrology-scenarios` `AssimilativeCheck` gains the acute pair `acute_low_flow` +
#   `acute_dilution_ratio` + `acute_flag` (WS-08 / #1608). The screen matches the design flow to
#   the criterion type — chronic aquatic-life dilution at the cited 7Q10 (`dilution_ratio`,
#   unchanged) and **acute** at the cited **1Q10** — because banding an acute limit with the
#   chronic design flow understates the constraint (a standard reviewer objection). All three are
#   null when the fact sheet omits the 1Q10; a cited 1Q10 = 0 cfs (a stream that runs dry at design
#   low flow) yields a 0:1 acute ratio (no acute capacity). Additive/optional, so an existing
#   hydrology-scenarios.json row stays valid — PATCH, back-compatible.
# 1.34.0: the `records` feed's closed RecordGroup enum gains two genres (#1746, epic #1744;
#   fulfills the Findlay TAXONOMY-GRANTS lead): `enforcement` (an `order` payload block —
#   consent decrees, OEPA Director's Final Findings & Orders, closure/extension letters) and
#   `finance` (an `award` block — WPCLF/OWDA loans, principal-forgiveness awards, federal
#   grants). Until now these genres had no honest bucket and were filed under `permits-epa`
#   with a disclosed TAXONOMY NOTE. Enum growth is additive for feed READERS (a pre-1.34
#   records.json remains valid) but a pre-1.34 records.schema.json rejects the new group
#   values — MINOR, back-compatible for data, schema refresh required.
# 1.35.0: adds the `grid` object feed (#1642, GP-E E1) — the per-site **grid backdrop**
#   (`watermark.grid.model.GridProfile`): the cited electric-service chain (serving utility,
#   holding company, balancing authority, wholesale RTO, retail regulator — each a `CitedFact`),
#   the EIA-861 utility annual profile (retail sales / customers / average price), the EIA-930
#   balancing-authority annual load, and, where a campus is disclosed, the `load_share` block
#   expressing its draw as a share of the utility / BA / state denominators. This was the richest
#   per-site grid artifact in the repo and it reached only a CLI-produced reference file
#   (`SiteProfile.grid_relpath`), never the bundle — so the presentation tier had no feed carrying
#   the grid backdrop and filled the vacuum with hand-copied Lima constants (`gridLoad.ts`'s
#   `AEP_OHIO_RETAIL_GWH` / `OHIO_RETAIL_GWH`), a second uncontrolled copy of the EIA
#   denominators. Grid identity joins the **backdrop floor** (`watermark.site.readiness`): it
#   describes the *place*, not the campus, so a facility-less peer carries it with `load_share`
#   null rather than nothing at all. Exported as its own already-provenanced Pydantic model like
#   `rsei` / `economics-baseline` (`ProvenancedValue` + `CitedFact` carry the #60 discipline), so
#   no new model is defined here. One new feed → MINOR, back-compatible (a reader that doesn't
#   know `grid` is unaffected; a pre-1.35 bundle simply has no grid backdrop to render).
# 1.36.0: the `defense-contractors` feed carries its evidence discipline in the type system
#   instead of in prose (#1663, ME-D). `DefenseContractorItem` gains `tag` + `tag_basis` — the
#   register of the item's corridor-presence claim (`open` when nothing matched, `inference` for a
#   bare owner/party name-pattern hit, `verified` only when a UEI-pinned award's curated `nexus`
#   corroborates it), retiring the page's "leads, not verdicts" callout as the *only* carrier of
#   that caveat. `ScanParcel` gains the pair the old scan conflated: `record_tag` for the GIS
#   columns themselves (verbatim from the county service → `verified`) and
#   `attribution` / `attribution_tag` / `attribution_basis` for what the scan claims the parcel IS
#   — at Lima, the `[inference]` JSMC identification that previously existed only as a free-text
#   prefix inside `meta.army_controlled_note`. The attribution text + register are sourced from the
#   site profile's `GisDefenseMeta` (never parsed out of the note), so a peer states its own.
#   All six fields carry defaults, so a pre-1.36 defense-contractors.json stays valid — MINOR,
#   back-compatible.
# 1.37.0: adds the `drawdown` object feed (groundwater well-drawdown thread) — the reference
#   site's Theis cone-of-depression screen (`watermark.hydrology.drawdown.DrawdownResult`) over the
#   ODNR well-log census + the literature aquifer parameters. Carries the `[inference]` apex
#   drawdown (a transmissivity-bracketed `ProvenancedValue`), the radius of influence, the count of
#   domestic census wells within it, the cone profile for the AquiferSection figure, and the
#   hypothetical-pumping scenario + caveats. Its headline is the inverse finding: a hyperscale
#   groundwater stress DEWATERS the low-transmissivity limestone aquifer — corroborating the
#   campus's reliance on municipal surface water. Reference-gated by construction (only a site with
#   a committed well-log census + a resolvable cooling basis produces it; `load_drawdown` returns
#   `None` otherwise → feed skipped), and exported as its own already-provenanced model like `grid`
#   / `rsei`, so no new model is defined here. One new feed → MINOR, back-compatible (a reader that
#   doesn't know `drawdown` is unaffected; a pre-1.37 bundle simply has no cone to render).
# 1.38.0: adds the `dewatering` object feed + the `geo/dewatering` map layer — the DOCUMENTED peer
#   of `drawdown`. Where `drawdown` screens a single HYPOTHETICAL cooling-makeup well, `dewatering`
#   models the real, documented wellfield the developer installed to lower the water table for site
#   grading (`watermark.hydrology.dewatering.DewateringImpact`): 44 [verified] ODNR well-log/sealing
#   records as a superposition of Cooper-Jacob cones, evaluated at each nearby domestic census well.
#   Carries the per-well cones (transmissivity-bracketed T + radius of influence), the domestic
#   census wells inside the composite cone with their [inference] superimposed drawdown, the field
#   capacity / operating window / `as_of` snapshot date, and caveats. The wells/rates/dates are
#   [verified]; every drawdown is [inference], bracketed. The `geo/dewatering` layer projects the
#   same wellfield onto the deck.gl map (well points sized by radius of influence + the impacted
#   domestic wells), reusing the shared `geo.schema.json`. Site-gated by construction (only a site
#   with a committed `SiteProfile.dewatering_wellfield_relpath` produces them; both self-skip
#   elsewhere), and the object feed is exported as its own already-provenanced model like `grid` /
#   `drawdown`, so no new model is defined here. One object feed + one geo layer → MINOR,
#   back-compatible (a pre-1.38 bundle simply has no wellfield to render).
# 1.39.0: the `dewatering` feed gains two optional fields answering "where did the pumped water go?"
#   — `discharge_screen` and `reservoir_recharge` (`watermark.hydrology.dewatering_discharge`). The
#   discharge screen compares the USGS reach gain between the bracketing gages (Ottawa @ Lima 128 sq
#   mi → near Kalida 350 sq mi) over the documented pumping window vs. a prior-year baseline,
#   restricted to baseflow days, against the expected ~7.6 cfs discharge — its honest headline a
#   NEGATIVE result (`outcome: not_separable`): the signal is swamped by the 222 sq mi of incremental
#   drainage, and the upstream low-flow floor is unchanged, so the surface record can neither confirm
#   nor exclude the discharge (the NPDES authorization is the `[open]` owed record). The reservoir
#   read characterizes the Auglaize supply gage's recharge conditions over the same window. Gage
#   discharge is `[verified]` USGS daily values; every attribution is `[inference]`. Both are read
#   from the committed `dewatering-discharge.yaml` report (regenerated by `watermark
#   dewatering-discharge --write`), so the export stays offline/deterministic. Two additive optional
#   fields on an existing model → MINOR, back-compatible (a pre-1.39 bundle carries a cone with no
#   discharge screen; a reader that doesn't know the fields is unaffected).
# 1.40.0: the `dewatering` feed's impacted wells become vulnerability-aware + directional (the "why
#   does a shallow dry well slip past us?" thread). Each `ImpactedWell` gains `available_column_ft`
#   (the well's own buffer before going dry = total depth - static level), `column_consumed_frac`,
#   and `goes_dry` — because a very shallow well is dewatered by a decline a deep one shrugs off, so
#   the flat >1 ft threshold under- and over-states real risk; the screen now also admits a well the
#   drawdown would push past its OWN column even below 1 ft. And `DewateringImpact` gains a
#   `hydraulic_gradient` (regional water-table gradient fit from census head `dem_elev - static`) +
#   a per-well `gradient_position` (up/down/cross-gradient) — the groundwater analog of the discharge
#   screen's upstream/downstream, since a radial cone is direction-blind but a down-gradient well sees
#   the field ~upstream of it. All `[inference]`. Additive optional fields on an existing model →
#   MINOR, back-compatible (a pre-1.40 reader is unaffected).
# 1.41.0: adds the `thermal` object feed (#1719, epic #1715 Phase 4) — the receiving-water
#   temperature-rise / CWA §316(a) screen (`watermark.hydrology.thermal.ThermalDischargeInventory`),
#   the **third cooling axis**. The platform already published cooling *volume*
#   (`hydrology-scenarios`) and discharge *chemistry* (the toxics screen); the discharge's *heat*
#   reached only a committed reference file. Each row is one facility's heat load read against the
#   reach's Ohio numeric temperature criterion (OAC 3745-1-35 Table 35-11, by geographic zone) at
#   the cited design low flows: the fully-mixed ΔT and mixed temperature, the reach's thermal
#   assimilative capacity, the Great Lakes RIS tolerances the mixed temperature crosses, and the
#   OAC 3745-1-06 (O)(5) closed-cycle-blowdown exemption. Rows carry `kind` — a `data_center` row's
#   heat load is MODELLED from the disclosed IT load (`[inference]`, with its three heat-partition
#   `scenarios` and the derived-vs-observed `calibration`), a `permitted_discharger` row's is the
#   permittee's own ECHO-DMR reported effluent temperature x flow (`[verified]`, with the `dmr`
#   block naming the permit's numeric limit or its absence). Never conflate them: read `kind`
#   before quoting a number. Site-gated by the artifact's own `meta.site`, so a peer cannot inherit
#   the reference site's corridor; exported as its own already-provenanced model like `grid` /
#   `drawdown` / `dewatering`, so no new model is defined here. One new feed → MINOR,
#   back-compatible (a pre-1.41 bundle simply has no thermal screen to render).
# 1.42.0: the federal-enclave seam (#1664, epic #1659 ME-E) — two new feeds and one additive
#   field. `enclave` (object) publishes a federal installation's OWN land / water / wastewater /
#   power / toxics: the DoD MIRTA boundary measured against the acreage its grounding record
#   states, its EPA SDWIS community water systems, its EPA ECHO NPDES discharges, an `[open]`
#   electrical load, and — the point of the cluster — its own EPA RSEI/TRI row together with the
#   plain statement of why the site's county backdrop cannot contain it (a straddling enclave
#   reports TRI from the county the profile did NOT pick as its economic unit) and why even that
#   row cannot carry the CERCLA mass. `geo/enclave` publishes the boundary as a map layer and is
#   the second geometry signal the `places` domain activates on, so a site that will never have a
#   county CAMA parcel is no longer structurally locked out of the domain. `FacilityItem` gains
#   `kind` (`data_center` | `federal_installation`, defaulting to the former, so every existing
#   row is unchanged) — a consumer must branch on it rather than read a `federal_installation`'s
#   absent IT load as an undisclosed campus MW. Two new feeds + an optional field → MINOR,
#   back-compatible (a pre-1.42 bundle simply has no enclave to render).
# 1.43.0: the economic argument as disciplined scenario bands (#1665, epic #1659 ME-F) — one
#   new feed. `economics-scenarios` (object) publishes what lived only in prose and in a
#   hardcoded frontend array: the discrete what-if `profiles` (building share x jobs, each
#   priced for forgone property tax / un-abated tax kept / sales-tax exemption / net subsidy /
#   per-job), the ledger `lines` as bands over those corners, the `load_per_job` ratio (the
#   §3 "subsidizes load, not employment" magnitude), the `withheld` inputs that keep the bands
#   wide with the record that would collapse each, the modeling `constants` as cited
#   `ProvenancedValue`s, and the cited industry `axes` (the GovCloud authorized-region premium,
#   the DCTE / AI-rack refresh curve, jobs-per-MW, the subsidy-per-job benchmark) each carrying
#   every published source pooled into it. The DISCIPLINE is in the type system, not the prose:
#   a band refuses `low == high`, and every axis / line / withheld input refuses the `verified`
#   tag and any confidence above `low` — a scenario structurally cannot serialize as an
#   assertion, and the GovCloud profile is a labeled counterfactual, explicitly not a defense
#   finding. INSTRUMENT-gated on `SiteProfile.abatement_parameters_relpath`, so a peer with no
#   abatement agreement on the record simply has no feed and its report locks rather than being
#   priced off another county's mills. One new feed → MINOR, back-compatible (a pre-1.43 bundle
#   simply has no scenario bands to render).
# 1.44.0: the impact study as a typed bundle artifact (#1804, epic #1803 P1) — one new feed.
#   `impact-study` (collection) ships the missing-impact-study's data spine: one row per study
#   chapter, keyed `(chapter, facility_key)`, each carrying the chapter's verdict
#   (`data | partial | gap | na` — row counts + content probes, never presence alone), its
#   headline `stats` (each wearing a `verified | inference | open` evidence tag), its gap
#   findings (the fixed three-line grammar: the requirement, the absence, the ask), the
#   MUST-render caveats, and the strictly-curated `lead_ids` joins onto the site's own leads
#   board. A pure post-pass PROJECTION over the feeds already assembled (`watermark.site.
#   impact_study`, the `open-questions` pattern): it mints no claims and reads no corpus —
#   the same sources the frontend's TS composers read, which it replaces row-for-row (the
#   frontend prefers a shipped row wholesale; a parity suite over every committed bundle
#   pins the two derivations equal, so the cutover cannot silently change a published
#   verdict). Emitted for every site — a facility-less site's project-dependent chapters
#   read `na` (watch state), never `gap`. One new feed → MINOR, back-compatible (a pre-1.44
#   bundle simply composes chapter models at the frontend build instead).
# 1.45.0: the cooling-cycling reconciliation reaches the bundle (#1805, epic #1803 P2) — one
#   new feed. `cooling-reconciliation` (object) ships THE SITE'S OWN candidate row(s) of the
#   committed claim-vs-record water account (`data/reference/oepa/cooling-reconciliation.yaml`,
#   epic #1676: the A3 harness, the A4 secondary corroborators, the B1-B3 provenance slots) —
#   claim (archetype + source + citation), the predicted account at screening grade, the
#   documented / reserved / disclosed slots kept structurally distinct, outcome
#   (`discrepancy | corroborated | reservation_conflict | gap`) + tag + finding, the
#   records-sought lead, and the corroborator stances — validated back through the producer's
#   own `ReconciliationRecord` model and shipped verbatim, so the feed is byte-consistent with
#   the reference artifact by construction. The harness's discipline rules ride the feed as
#   MUST-render `caveats` (a ceiling is not an instrument; a self-report never upgrades the
#   source; corroborators never change the outcome; a back-solved CoC is a bracket). Site-gated
#   on the rows' own `site` key and self-skipped when the site has no row (#1364), and the
#   Intel positive-control row (`is_control`) is excluded explicitly — a calibration vector
#   never ships as site data, even on a `new-albany` bundle. One new feed → MINOR,
#   back-compatible (a pre-1.45 bundle simply renders the water chapter without the
#   reconciliation block).
CONTRACT_VERSION = "1.45.0"

# SourceKind / Confidence now live in watermark.provenance (shared with watermark.hypotheses +
# hydrology.ProvenancedValue, #605); re-exported here so importers of watermark.site.feeds are
# unchanged.
RecordGroup = Literal[
    "deeds",
    "enforcement",
    "finance",
    "permits-epa",
    "permits-idem",
    "permits-npdes",
    "permits-sos",
    "plans",
    "opc",
]
# What the frontend document viewer dispatches on — derived from the *real* file
# (extension + content sniff), never from hand-authored genre metadata (epic #274).
RenderClass = Literal["image", "text", "html", "pdf", "office", "other"]


# --- shared provenance primitives (issue #60) ---------------------------------
class Citation(BaseModel):
    """Structured provenance for a feed item or a single figure.

    Mirrors :class:`watermark.hydrology.model.ProvenancedValue`'s evidence discipline so the
    whole bundle speaks one provenance language: ``source_kind`` says where the value
    came from, ``source`` is the citable artifact (a repo-relative ``data/`` path, an
    external dataset label, a permit/instrument number), ``page`` locates it within a
    multi-page source, and ``verified`` is derived so a consumer never re-computes it.
    """

    model_config = ConfigDict(extra="forbid")

    source: str | None = None  # repo-relative artifact path, dataset label, or doc id
    source_kind: SourceKind = "document"
    page: int | None = None  # 1-based page within the source, if applicable
    confidence: Confidence = "medium"
    note: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        """True when grounded in a record or a live gauge (``[verified]`` in prose)."""
        return source_is_verified(self.source_kind)


class Figure(BaseModel):
    """A number that keeps the ``~`` approximate marker as data, not formatted text.

    ``approximate`` is the transcription ``~`` lifted out of the YAML string so a
    consumer renders the tilde from the bundle; ``citation`` ties the figure to its
    source page/file. Dollar totals are high-confidence (``approximate=False``);
    transcribed quantities marked ``~`` in the source set ``approximate=True``.
    """

    model_config = ConfigDict(extra="forbid")

    value: float | int | None = None
    approximate: bool = False
    unit: str | None = None
    citation: Citation | None = None


# --- facts feed (#1587) --------------------------------------------------------
# The evidence-discipline vocabulary a normalized fact renders as: the three tags a
# `source_kind` maps to (`watermark.provenance.evidence_tag`), plus `open` for an asserted-
# but-unquantified fact (a known predicate with no value yet — a lead). A projection over the
# provenanced feeds yields only verified/inference/reference; `open` rides along for the
# readiness/leads tie-in (deferred). Aliased to the shared `watermark.provenance.EvidenceRegister`
# (#1663) rather than re-spelled, so the vocabulary can't drift from the peer that
# `watermark.connectors.gis_schema` — which can't import this heavy module — speaks.
FactStatus = EvidenceRegister


class FactEvidence(BaseModel):
    """Where a normalized fact came from — the `Citation` shape, projected from a value's
    provenance.

    A `ProvenancedValue` (the carrier of every typed numeric fact — economics, greenops,
    hydrology, air, facility power) records provenance as a single free-text ``citation``
    with **no structured page**, so a projected fact keeps that text verbatim in
    ``citation`` and lifts a repo-relative artifact path into ``source`` only when the text
    *is* one. ``page`` is populated **only** where the source genuinely carries one and is
    **never invented** — the chain-of-custody discipline (root CLAUDE.md): a value with no
    page yields ``page=null``, honestly.
    """

    model_config = ConfigDict(extra="forbid")

    source: str | None = None  # repo-relative artifact path / dataset label / doc id, when known
    source_kind: SourceKind = "document"
    page: int | None = None  # 1-based page, only where the source carries it — never fabricated
    citation: str | None = None  # the ProvenancedValue free-text citation, verbatim
    confidence: Confidence = "medium"
    asof: str | None = None  # ISO date/datetime for a live (connector) value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        """True when grounded in a record or a live gauge (``[verified]`` in prose)."""
        return source_is_verified(self.source_kind)


class FactItem(BaseModel):
    """One normalized ``(subject, predicate, value, unit, status, evidence)`` fact.

    The `facts` feed is a projection (`watermark.site.facts`), not a new extraction: every row
    re-keys a `ProvenancedValue` the bundle already ships (or the derived facility
    `PowerBasis`) into a flat, queryable tuple, so ``get_facts`` answers a fact question with a
    tiny retrieval instead of a whole-record pull. ``subject`` is a stable ``<kind>:<id>`` key
    (mirroring the catalog handle grammar) with a human ``subject_label``; ``predicate`` is a
    normalized snake_case field name; ``status`` is the evidence-discipline tag
    (`watermark.provenance.evidence_tag`) derived from the value's ``source_kind``; ``feed``
    names the source bundle feed the fact was projected from (a pointer, not a copy).
    """

    model_config = ConfigDict(extra="forbid")

    subject: str  # canonical key, e.g. "facility:lima", "county:39003", "naics:39003:62"
    subject_label: str  # human display, e.g. "Allen County, Ohio"
    subject_kind: str  # site | county | state | facility | sector | hydrology-scenario | ...
    predicate: str  # normalized snake_case field name, e.g. "genset_count", "demand_share_pct"
    value: float | int | None = None  # None ⇒ an asserted-but-unquantified fact (status=open)
    unit: str | None = None
    status: FactStatus
    approximate: bool = False  # the transcription `~` marker, as data
    low: float | None = None  # quantitative uncertainty band (#760), carried through
    high: float | None = None
    evidence: FactEvidence
    feed: str  # the source bundle feed this fact was projected from


# --- facility feed (#1628) -----------------------------------------------------
class FacilityItem(BaseModel):
    """One disclosed data-center campus — the machine-readable projection of a
    :class:`watermark.sites.SiteFacility` (#1628, epic #1626 F2).

    A site holds N of these (``is_primary`` marks the modeled campus that drives the water/power/air
    math). Each carries the structured facts the model now holds instead of freetext comments: the
    lifecycle ``status``, the ``operator`` / ``end_use`` (each with its citation), the IT-load bracket
    (``None`` when the load is entirely ``[open]`` — a rezoning-only campus), the site-plan
    disclosure, the cooling archetype, and the resolved geometry link (facility-level, or inherited
    from the site). Nothing here is re-keyed by hand — it is projected from the validated model, so a
    provenance travels with its value across the seam.
    """

    model_config = ConfigDict(extra="forbid")

    key: str  # the facility's stable slug (unique within a site)
    name: str  # display identity, e.g. "Shawnee Energy Campus"
    is_primary: bool  # the first/modeled campus (drives the water/power/air math)
    status: FacilityLifecycle  # investigation | confirmed | construction | live
    # What KIND of facility this row is (#1664). Every row before the enclave seam was a
    # `data_center`, which is the default, so this discriminates rather than reclassifies. A
    # `federal_installation` row carries none of the data-center columns below (they are forbidden
    # at the model level, not merely absent) — its land/water/wastewater/toxics live in the
    # `enclave` feed. A consumer must branch on this rather than reading an all-null IT load as
    # "a campus that hasn't disclosed its MW yet".
    kind: FacilityKind = FacilityKind.DATA_CENTER
    operator: str | None = None
    operator_citation: str | None = None
    end_use: DcEndUse | None = None  # None ⇒ end use is [open] (never asserted — Lima's question)
    end_use_citation: str | None = None
    facility_type: str | None = None  # the freetext site-plan type, retained alongside end_use
    it_load_mw: float | None = None  # central IT load; None ⇒ load entirely [open]
    it_load_low_mw: float | None = None
    it_load_high_mw: float | None = None
    # The two IT-load groundings are kept DISTINCT (not coalesced) so a consumer can tell a
    # permit-grounded load (Lima/Fort Wayne — the [verified] backup → N+1 inference) from a
    # non-permit screening/derivation bracket (Urbana — [inference]) structurally, not by parsing
    # prose (#1697 discipline; #1628 review). Exactly one is set on a disclosed load; both None on
    # an [open] load. `air_permit_relpath` is the committed extraction the permit basis points at.
    air_permit_citation: str | None = None
    air_permit_relpath: str | None = None
    it_load_citation: str | None = None  # a NON-permit derivation basis (screening bracket)
    gross_floor_area_sqft: int | None = None
    disclosed_investment_usd: float | None = None
    disclosure_citation: str | None = None
    cooling_model: CoolingModelType
    # The provenance CLASS of the cooling archetype — `assumption` (asserted, e.g. Lima's
    # evaporative tower) vs `reference`/`document` (disclosed) — so the evidence grammar has a typed
    # field to key on instead of regexing the citation (#1628 review).
    cooling_model_source: Literal["document", "connector", "reference", "assumption"]
    cooling_model_citation: str
    parcels_relpath: str | None = (
        None  # resolved geometry link (only when the artifact exists on disk)
    )
    footprint_relpath: str | None = None


class FacilitySummary(BaseModel):
    """The manifest's compact **facility** block (#1628) — the primary campus's lifecycle status +
    the facility count.

    The cheap per-slug source the frontend reads for the site's facility-status badge (retiring the
    hardcoded ``FACILITY_STATUS`` dict in ``web/packages/core/src/sites.ts``), mirroring how the
    ``readiness`` block is read. Absent (``Manifest.facility is None``) for a facility-less site, so
    the reader defaults to ``investigation``.
    """

    model_config = ConfigDict(extra="forbid")

    status: FacilityLifecycle  # the PRIMARY campus's lifecycle stage — drives the site badge
    count: int  # number of disclosed facilities on the site
    primary_name: str
    primary_operator: str | None = None
    primary_end_use: DcEndUse | None = None


# --- records feed --------------------------------------------------------------
class RecordItem(BaseModel):
    """One committed extraction, contractor-/genre-agnostic (mirrors records.py).

    ``fields`` is the raw payload block verbatim (so the ``~`` marker survives in any
    transcribed scalar); ``approximate_paths`` lists the dotted field paths whose value
    carried that marker, and ``citation`` is the structured provenance footer.
    """

    model_config = ConfigDict(extra="forbid")

    rel: str  # path relative to data/extracted — the stable record id
    group: RecordGroup
    title: str
    confidence: str | None = None
    warnings: list[str] = Field(default_factory=list)
    fields: dict[str, Any] = Field(default_factory=dict)
    approximate_paths: list[str] = Field(default_factory=list)
    citation: Citation
    # The real source document this record was read from (epic #274 / #276), joined
    # against the documents catalog so a stale/removed source_path yields ``None``
    # (no broken link) rather than a 404. Connector-only records carry ``None``.
    source_doc_rel: str | None = None  # the source file's data/documents rel
    source_doc_render_class: RenderClass | None = None  # from the documents feed (#275)
    source_doc_published: bool = False  # cleared for public serving (allowlist, #280)


# --- timeline feed -------------------------------------------------------------
class TimelineEntry(BaseModel):
    """One dated event, traceable to the extraction(s) that supplied it."""

    model_config = ConfigDict(extra="forbid")

    date: str  # as transcribed (ISO where legible; "" when undated)
    category: str
    title: str
    ref: str = ""  # logical id (instrument / permit no) for cross-doc dedup
    parties: list[str] = Field(default_factory=list)
    detail: str = ""
    source: str  # primary extraction path, relative to data/extracted
    also_sources: list[str] = Field(default_factory=list)
    citation: Citation


# --- entities + relationships feeds -------------------------------------------
class EntityNode(BaseModel):
    """A resolved party in the entity graph, keyed by its canonical name."""

    model_config = ConfigDict(extra="forbid")

    key: str  # canonical, normalized key — the cross-feed reference id
    display: str
    kind: str
    classification: str
    relation_class: str | None = None
    relation_basis: str | None = None
    variants: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    roles: dict[str, int] = Field(default_factory=dict)
    parcels: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    lei: str | None = None
    uei: str | None = None
    federal_obligations: float | None = None


class RelationshipEdge(BaseModel):
    """A directed edge between two entity keys, traceable to one document."""

    model_config = ConfigDict(extra="forbid")

    src: str  # source entity key (resolves into the entities feed)
    rel: str
    dst: str  # destination entity key (resolves into the entities feed)
    date: str = ""
    ref: str = ""
    source: str = ""
    relation_class: str | None = None
    relation_basis: str | None = None


# --- people feed ---------------------------------------------------------------
class PersonItem(BaseModel):
    """A curated individual profile (only expanded-research ones are published)."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    entity_key: str | None = None  # resolves into the entities feed
    aliases: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    summary: str | None = None
    expanded: bool = False
    tags: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    body: str = ""


# --- places feed ---------------------------------------------------------------
class PlaceLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str | None = None
    confidence: str | None = None
    asof: str | None = None
    bbox: list[float] | None = None  # [minx, miny, maxx, maxy], WGS84


class PlaceTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    collections: list[str] = Field(default_factory=list)
    since: str | None = None


class PlaceRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    entity: str  # resolves into the entities feed


class PlaceItem(BaseModel):
    """A curated place (POI) profile — the place peer of a person profile."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    name: str
    kind: str
    depth: str
    parcels: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)  # composite member slugs
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    location: PlaceLocation | None = None
    track: PlaceTrack | None = None
    relationships: list[PlaceRelationship] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    body: str = ""


# --- candidates + defense-contractors feeds -----------------------------------
class CandidateItem(BaseModel):
    """A demand-fit cloud-consumer candidate (curated, not corpus-derived)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tier: int
    kind: str
    sector: str | None = None
    location: str | None = None
    workload_classes: list[str] = Field(default_factory=list)
    confirmed_cloud_relationship: str | None = None
    speculative: bool = False
    basis: str | None = None
    entity_key: str | None = None  # resolves into the entities feed when matched


class ScanParcel(BaseModel):
    """A parcel row from the defense-land GIS scan (extra GIS columns allowed).

    Two registers travel with one row, and conflating them is the failure this model exists to
    prevent (#1663, ME-D). The GIS columns — owner, situs, acres, value — are verbatim from the
    county's public parcel service, so ``record_tag`` is ``verified``. What the scan *claims the
    parcel is* — a named prime's holding, the Joint Systems Manufacturing Center — is an analyst
    reading over those columns, carried in ``attribution`` and tagged separately by
    ``attribution_tag``. Before this, the ``[inference]`` marker on the JSMC identification lived
    only as a free-text prefix inside the scan's ``meta.army_controlled_note`` prose, so a consumer
    could not tell a verified ownership row from an inferred attribution without parsing English.
    """

    model_config = ConfigDict(extra="allow")

    # The register of the row's OWN columns (owner/situs/acres/value). `verified` for a live
    # ArcGIS pull; a site that vendors a downloaded parcel extract instead sets `reference`.
    record_tag: FactStatus = "verified"
    # What the scan claims this parcel IS, and the register of that claim — never derived by
    # regexing `attribution_basis` for a `[tag]` prefix. `attribution` is null on a row the scan
    # merely lists (it asserts nothing beyond the ownership already in `record_tag`).
    attribution: str | None = None
    attribution_tag: FactStatus = "inference"
    attribution_basis: str | None = None  # why that register — the reasoning, per row


class FederalAnnualFlow(BaseModel):
    """One federal fiscal year's prime-award obligations (the annual flow, #1662)."""

    model_config = ConfigDict(extra="forbid")

    fiscal_year: int
    obligations: float


class FederalCategory(BaseModel):
    """One PSC/NAICS category's share of a recipient's federal obligations (#1662)."""

    model_config = ConfigDict(extra="forbid")

    code: str
    name: str
    obligations: float


class ContractorAward(BaseModel):
    """A USASpending federal-award record joined to a matched corpus entity (#1662, ME-C).

    The dollars are verbatim from ``data/reference/usaspending/[<slug>/]awards.yaml``; the join
    key is the entity node's ``uei`` (stamped by the same watchlist), so the feed's federal totals
    reconcile with the entity graph rather than re-deriving them.
    """

    model_config = ConfigDict(extra="forbid")

    entity_key: str  # the matched graph node this award resolves through
    recipient_name: str
    uei: str
    total_obligations: float  # all-time prime-award obligations (USD)
    nexus: str  # verified | context | open — how the recipient ties to the corridor
    defense_share: float | None = None  # DoD-family / all-agency obligations, 0..1
    annual_obligations: list[FederalAnnualFlow] = Field(default_factory=list)
    by_psc: list[FederalCategory] = Field(default_factory=list)
    by_naics: list[FederalCategory] = Field(default_factory=list)


class DefenseContractorItem(BaseModel):
    """A seed prime defense contractor + the corpus entities its patterns matched.

    When a matched entity resolves to a USASpending recipient, its awards are stamped here (#1662):
    ``awards`` carries the per-entity federal records, and ``total_obligations`` / ``nexus`` roll
    them up (the summed dollars + the strongest nexus). A contractor with no matched award keeps
    an empty ``awards`` and null totals.

    ``tag`` types the discipline the page previously carried only as a prose callout (#1663, ME-D):
    it is the register of the item's **corridor-presence claim**, not of the seed row (the seed list
    is curated, and a prime that matched nothing still ships so the search is visible). A bare
    ``matched_entities`` hit is a case-insensitive substring match on a party name — a lead, so
    ``inference``; a match corroborated by a UEI-pinned award whose curated ``nexus`` is
    ``verified`` earns ``verified``; nothing matched leaves the question standing, so ``open``.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    note: str | None = None
    patterns: list[str] = Field(default_factory=list)
    matched_entities: list[str] = Field(default_factory=list)  # entity keys
    awards: list[ContractorAward] = Field(default_factory=list)
    total_obligations: float | None = None  # Σ distinct matched awards (USD); null if none
    nexus: str | None = None  # strongest matched nexus (verified > context > open); null if none
    tag: FactStatus = "open"  # register of the corridor-presence claim (#1663)
    tag_basis: str | None = None  # why that register — what carried (or failed to carry) it


class DefenseFeed(BaseModel):
    """The defense-contractors feed: the seed list + the parcel-scan findings."""

    model_config = ConfigDict(extra="forbid")

    contractors: list[DefenseContractorItem] = Field(default_factory=list)
    prime_owned: list[ScanParcel] = Field(default_factory=list)
    army_controlled: list[ScanParcel] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)


# --- meetings feed -------------------------------------------------------------
class MeetingItem(BaseModel):
    """One corridor-relevant subdivision meeting summary (grounded, no inference)."""

    model_config = ConfigDict(extra="forbid")

    slug: str  # the subdivision body (e.g. "lacrpc", "lima")
    date: str | None = None
    kind: str | None = None
    summary: str = ""
    corridor_relevance: str = ""
    decisions: list[str] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    parcels: list[str] = Field(default_factory=list)
    dollar_figures: list[str] = Field(default_factory=list)
    hits: list[str] = Field(default_factory=list)
    citation: Citation


# --- documents + exhibits feeds -----------------------------------------------
class DocumentItem(BaseModel):
    """One source document in the catalog, addressed by its corpus path."""

    model_config = ConfigDict(extra="forbid")

    rel: str  # path relative to data/documents — the as-received chain-of-custody name
    name: str
    size_bytes: int
    suffix: str  # the file extension, lower-cased and de-dotted (the as-received signal)
    # The renderable type, derived from the *real* file (extension + a content sniff of
    # the leading bytes), not from hand-authored metadata (epic #274 / #275).
    media_type: str  # MIME, e.g. application/pdf, image/jpeg, text/html
    render_class: RenderClass  # what the viewer dispatches on
    # Cleared for *public* serving by the default-deny allowlist (#280); dev/preview
    # serve everything regardless. The /api/doc Function enforces the same flag.
    published: bool
    available: bool  # locally present (not an unresolved Git-LFS pointer)
    download_url: str | None = None
    # Version / duplicate-cluster metadata (#1590, epic #1579 Phase 3), projected from the
    # curated custody manifest (`data/site/document-versions.yaml`, watermark.site.docversions)
    # so retrieval can collapse a filing's versions to the authoritative one without losing the
    # evidence a superseded version carries (e.g. a draft's CBI-unredacted figure). All optional
    # and absent for a document with no declared cluster.
    duplicate_cluster: str | None = None  # stable cluster id, e.g. "oepa:2PH00006"
    canonical_document_id: str | None = None  # canonical member's rel (self if this is canonical)
    version: str | None = None  # "final" | "draft" | "fact_sheet" | "duplicate" | "v2" | …
    supersedes: list[str] = Field(default_factory=list)  # rels superseded (canonical member only)


class DocumentCollectionItem(BaseModel):
    """A first-level collection under data/documents and its catalogued entries."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    description: str = ""
    entries: list[DocumentItem] = Field(default_factory=list)


class ExhibitItem(BaseModel):
    """A curated, published exhibit — a source PDF or a page-range slice of a bundle."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    title: str
    caption: str = ""
    source: str  # path relative to data/documents
    pages: str | None = None  # "317-327" (0-based inclusive) or None for the whole file
    available: bool


# --- leads feed (issue #796) --------------------------------------------------
# The four lead kinds, the lead lifecycle status, and the evidence tag — the data vocabulary the
# frontend's leads board renders (presentation labels stay frontend-side). A lead is *unverified
# inference until a source corroborates it*, so the tag is only ever `open` (a documented gap) or
# `inference` (a labeled reading), never `verified`.
LeadKind = Literal["signal", "question", "redaction", "claim"]
LeadStatus = Literal["low", "unanswered", "withheld", "review"]
LeadTag = Literal["open", "inference"]


class LeadItem(BaseModel):
    """One open lead — a gap we're chasing on a site, each tracing to a real committed source.

    The per-site peer of Lima's curated leads board: read from `data/site/leads.yaml` (slug-scoped),
    so a sibling site carries its own leads, not Lima's (#796). No fabricated contributors or
    timestamps — every lead names where the gap is recorded.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable local id; mirrors the PRR item / source where apt
    kind: LeadKind
    status: LeadStatus
    tag: LeadTag
    title: str
    detail: str
    source: str  # the real citation — where this gap is recorded
    issue: int | None = (
        None  # a linked watermark-directory/the-watermark-directory tracking issue, when one exists
    )
    note: str | None = None  # a short standing note, used sparingly + truthfully


# --- open-questions feed (issue #1568, epic #1560 workstream B) ----------------
# Where a still-open question was aggregated from: the per-site `leads` board, or an `[open]`-tagged
# cell of the boom-origin hypothesis matrix. Ports yidam's `open-questions` model (a node is open
# when it carries the `[open]` tag) — see `watermark.site.corpus_mirror.render_open_questions`.
OpenQuestionOrigin = Literal["lead", "hypothesis"]


class OpenQuestionItem(BaseModel):
    """One unanswered question in the corpus — an `[open]`-tagged lead or hypothesis cell.

    The `open-questions` feed is a **projection** (`watermark.site.open_questions`), not a new
    extraction: it aggregates every still-open thread the bundle already ships — the `[open]`-tagged
    rows of the `leads` feed (the per-site board, wired to the `lead:kind:question` /
    `lead:status:unanswered` label vocabulary) and the `[open]`-tagged cells of the
    `hypothesis-assessments` matrix (a documented gap under a boom-origin lens) — into one flat,
    provenanced list. It ports yidam's `open-questions` model: a node is open when it carries the
    `[open]` tag (`claim_tag == "open"`), so an `[inference]`-tagged lead (a labeled reading, not a
    gap) is deliberately excluded, exactly as `render_open_questions` excludes it.

    Every row names a real ``source`` — the citation where the gap is recorded (a lead's source, or
    the hypothesis cell's committed matrix file). The lead-derived fields (``kind``/``status``/
    ``issue``) are present only for ``origin == "lead"``; the hypothesis-derived fields
    (``hypothesis``/``hypothesis_label``/``signal``) only for ``origin == "hypothesis"``.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable id: the lead id, or `hyp:<hypothesis>:<site>` for a matrix cell
    origin: OpenQuestionOrigin
    question: str  # the open question — the lead title, or a synthesized cell prompt
    detail: str  # one honest paragraph of context (never fabricated)
    source: str  # the real provenance citation — where this gap is recorded
    # lead-derived context (present when origin == "lead") — the lead:kind:* / lead:status:* vocab.
    kind: LeadKind | None = None
    status: LeadStatus | None = None
    issue: int | None = None  # a linked tracking issue, when the lead names one
    # hypothesis-derived context (present when origin == "hypothesis").
    hypothesis: str | None = None  # the lens id ("water" | "defense" | "surveillance")
    hypothesis_label: str | None = None  # the human lens label, e.g. "H1 Water & Coercion"
    signal: str | None = None  # the cell's signal strength ("anchor"|"strong"|"moderate"|"watch")


# --- impact-study feed (issue #1804, epic #1803) --------------------------------
# The study's verdict vocabulary and the FigureStat evidence subset. These mirror
# `web/packages/core/src/study.ts` (`ChapterStatus`, `FigureStatData.evidence`) — the frontend
# prefers a shipped `impact-study` row WHOLESALE over its TS composers, so the serialized shapes
# below are pinned by the frontend's own guardrail + parity suites and must not drift.
StudyChapterStatus = Literal["data", "partial", "gap", "na"]
StudyEvidence = Literal["verified", "inference", "open"]
StudyBasis = Literal["grounded", "modeled"]


class StudyStat(BaseModel):
    """One headline figure of a study chapter — the `FigureStatData` shape, exported.

    Every figure wears a real evidence tag (`verified | inference | open` — the FigureStat
    contract admits no `reference`; reference-register context rides in `sub`/caveats). The
    field names are already the frontend's — no aliasing needed.
    """

    model_config = ConfigDict(extra="forbid")

    label: str
    value: str  # pre-formatted display string (ranges, brackets) — the JS formatting, mirrored
    unit: str | None = None
    evidence: StudyEvidence
    basis: StudyBasis | None = None
    sub: str | None = None
    source: str | None = None
    warn: bool | None = None  # tri-state: absent (not a screened figure) vs. explicit pass/fail


class StudyGap(BaseModel):
    """A gap rendered as a FINDING — the panel's fixed three-line grammar.

    ``missing_record`` is a noun phrase completing "Computing it requires ___" (the frontend
    guardrails reject sentence-form copy). ``lead_ids`` are the strictly-curated joins onto the
    site's own leads board — never a fuzzy keyword match. Serializes camelCase to match the
    `StudyGapFinding` interface the frontend renders verbatim.
    """

    model_config = ConfigDict(extra="forbid")

    would_screen: str = Field(serialization_alias="wouldScreen")
    missing_record: str = Field(serialization_alias="missingRecord")
    producer: str | None = None
    lead_ids: list[str] | None = Field(default=None, serialization_alias="leadIds")


class StudyChapterModel(BaseModel):
    """One chapter's plain-JSON model — the exact shape every study surface renders.

    The Python realization of the frontend's `StudyChapterModel` (the seam #1795 reserved):
    `studyChapterModel` returns a shipped row's ``model`` untransformed, so this serializes
    with the interface's own camelCase keys.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    facility_key: str | None = Field(default=None, serialization_alias="facilityKey")
    status: StudyChapterStatus
    status_reasons: list[str] = Field(default_factory=list, serialization_alias="statusReasons")
    stats: list[StudyStat] = Field(default_factory=list)
    gaps: list[StudyGap] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class ImpactStudyItem(BaseModel):
    """One `impact-study` feed row — a chapter's model, keyed ``(chapter, facility_key)``.

    A projection (`watermark.site.impact_study`) over the bundle's own assembled feeds — the
    missing-impact-study epic's data spine, computed at export instead of at the frontend
    build. ``facility_key`` is the resolved primary campus (null for a facility-less site's
    site-level study — the frontend matches the pair exactly, so null never wildcards onto a
    campus's rows). ``lead_ids`` are the chapter-level curated joins (the annex "residual
    asks" register — distinct from the per-gap joins inside the model).
    """

    model_config = ConfigDict(extra="forbid")

    chapter: str
    facility_key: str | None = None
    lead_ids: list[str] = Field(default_factory=list)
    model: StudyChapterModel


# --- corpus-index feed (issue #1573, epic #1560 workstream C) ------------------
# One row per node of the yidam corpus mirror (`watermark.site.corpus_mirror`): the at-a-glance map
# of the whole corpus. `kind` is the BOSC display kind (site/entity/person/concept/hypothesis/lead/
# open-question/relation) refined from the node's `class` + meta — the yidam `class` alone folds
# entities, people, and the site anchor all into `artifact`, so the finer `kind` is what a reader
# scans by. Ports the columns of `yidam corpus-index` (class, label, links-out, lines) and adds the
# in-degree and freshness the issue calls for.
CorpusNodeKind = Literal[
    "site",
    "entity",
    "person",
    "concept",
    "hypothesis",
    "lead",
    "open-question",
    "relation",
    "node",
]


class CorpusNodeItem(BaseModel):
    """One node of the corpus mirror — a browsable row for the wiki node-index page.

    The `corpus-index` feed is a **post-pass projection** (`watermark.site.corpus_index`), not a new
    extraction: it re-reads the just-built :class:`~watermark.site.corpus_mirror.Mirror` (which is
    itself a projection of the committed corpus) into a flat, sortable table. `node_class` is the
    yidam class (`artifact`/`concept`/`hypothesis`/`question`/`relation`); `kind` is the finer BOSC
    display kind derived from the node's meta. `links_out` is the node's own outgoing-edge count and
    `links_in` the number of other nodes that point at it (both resolved within the mirror). `lines`
    replicates the serialized node's line count exactly as `yidam corpus-index` reports it. `updated`
    is the newest commit date (ISO-8601 date) over the committed source file(s) the node derives from
    — null for an aggregated or code-derived node with no single backing file (never fabricated).
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # the yidam node id — `<class>/<name>`
    node_class: str  # the yidam class — artifact | concept | hypothesis | question | relation
    kind: CorpusNodeKind  # the BOSC display kind refined from meta
    label: str
    scope: str | None = None  # "site" | "network" (from the node's meta.scope), when known
    links_out: int  # outgoing edges (this node → others)
    links_in: int  # incoming edges (others → this node), resolved within the mirror
    lines: int  # serialized-node line count (parity with `yidam corpus-index`)
    updated: str | None = None  # ISO date of the newest commit touching the node's source(s)


# --- corpus-nodes retrieval feed (issue #1575, epic #1560 workstream D2) -------
# The searchable substrate behind the wiki "ask this concept" affordance: the same yidam mirror the
# `corpus-index` map projects, but carrying each node's *searchable text* + evidence tag + 1-hop
# adjacency, so a concept page can run client-side lexical retrieval scoped to its own corpus
# neighborhood (offline, no server — the D3 spike's verdict, #1576). A retrieval index, not a
# browsable table: a post-pass over the `Mirror` (`watermark.site.corpus_nodes`), never re-extracted.
class CorpusRetrievalNodeItem(BaseModel):
    """One corpus-mirror node as a client-side retrieval unit.

    `text` is the one canonical `node_text` derivation the semantic index also embeds
    (`watermark.site.corpus_mirror.node_text`) — label · description · class · salient meta — so the
    lexical (`corpus-nodes`) and vector (`yidam_index`) surfaces tokenize the *same* content and never
    drift. `kind` is the same BOSC display kind as `corpus-index`. `evidence` is the node's claim tag
    when it carries one (`[open]` leads/questions, `[inference]` readings) and null otherwise — a
    structural node (a concept, a resolved entity) asserts no evidence tag, so the evidence palette is
    never spent on it. `ref` is the node's wiki page key — the concept slug for a `concept` node
    (its slug↔node join key + route param), null for kinds without a dedicated page today.
    `neighbors` is the node's undirected 1-hop adjacency (out-links plus in-links, resolved within
    the mirror), the graph the frontend walks to build a concept's neighborhood.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # the yidam node id — `<class>/<name>`
    kind: CorpusNodeKind  # the BOSC display kind (same mapping as `corpus-index`)
    label: str
    text: str  # searchable blob — the canonical `node_text` (reconciled with the vector index)
    evidence: FactStatus | None = None  # the node's claim tag when it bears one, else null
    ref: str | None = None  # wiki page key — concept slug today (slug↔node join), else null
    neighbors: list[str] = []  # undirected 1-hop neighbor ids, for neighborhood scoping


# --- contacts feed ------------------------------------------------------------
# The kinds of human contact point a site carries. `petitioner` and `organizer` are the ones the
# petition-connect + bulletin surfaces route to; `official`/`group`/`outlet` round out the directory.
ContactKind = Literal["petitioner", "organizer", "official", "group", "outlet"]


class ContactLink(BaseModel):
    """One *public* way to reach or read about a contact — a petition page, website, or social.

    Public routing only: private hand-off addresses (where a petition-connect is delivered) never
    enter the bundle; they live server-side (Phase 2). A bare label + URL, no provenance of its own
    (the parent :class:`ContactItem` carries the ``source``).
    """

    model_config = ConfigDict(extra="forbid")

    label: str  # short human label ("petition", "website", "Facebook")
    # Validated http(s) URL: malformed or non-http(s) values (e.g. `javascript:`) are rejected at
    # load time, so a curated link can never reach the frontend as an unsafe `href`. Serializes to a
    # plain string in the bundle (`model_dump(mode="json")`), so the feed's wire shape is unchanged.
    url: HttpUrl


class ContactItem(BaseModel):
    """One curated site-level contact point — a petitioner, organizer, official, group, or outlet.

    The per-site directory a reader can act on: read from `data/site/contacts.yaml` (slug-scoped),
    so a sibling site carries its own contacts, not Lima's (mirrors `leads`, #796). Every contact
    names a real committed ``source`` — no fabricated people, per the data-discipline rules — and
    exposes only *public* routing via ``links``; private hand-off addresses stay server-side.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable local id (kebab slug), the catalog handle's local_id
    kind: ContactKind
    name: str
    org: str | None = None  # affiliated organization, when distinct from the name
    role: str | None = None  # title / relationship ("lead organizer", "county commissioner")
    summary: str  # what they work on / the cause — one honest sentence
    links: list[ContactLink] = Field(default_factory=list)
    place: str | None = None  # where they're based, when documented
    source: str  # the real citation — where this contact is documented
    tags: list[str] = Field(default_factory=list)
    issue: int | None = None  # a linked tracking issue, when one exists


# --- concepts feed (issue #68) ------------------------------------------------
class ConceptItem(BaseModel):
    """One glossary concept from the wiki concept store (``data/concepts/*.md``).

    The lightweight peer of a person profile: a frontmatter header (identity +
    cross-links) plus a hand-written markdown body. ``related`` holds the slugs of
    sibling concepts; the frontend additionally resolves inline ``[[wiki links]]``
    in the body against the concepts, entities, and people feeds.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str  # the stable concept id (file stem)
    title: str
    kind: str = "concept"  # concept | term | method
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    related: list[str] = Field(default_factory=list)  # sibling concept slugs
    body: str = ""


# --- data catalog feed (epic #631, Phase 3 / #659) ----------------------------
class CatalogStorageFile(BaseModel):
    """One committed file belonging to a catalogued dataset (a published storage row)."""

    model_config = ConfigDict(extra="forbid")

    relpath: str  # relative to data/, ``{site}`` template kept verbatim for slug-scoped sets
    media_type: str
    lfs: bool = False


class CatalogObserved(BaseModel):
    """The reconcile snapshot's observed half for a dataset (``data/catalog/_observed.yaml``)."""

    model_config = ConfigDict(extra="forbid")

    exists: bool
    sha256: str | None = None
    size_bytes: int = 0
    lfs_materialized: bool = True
    file_count: int = 0
    stale: bool = False
    asof: str | None = None


class CatalogItem(BaseModel):
    """One dataset in the published data catalog — the bundle projection of a ``CatalogEntry``.

    The presentation peer of :class:`watermark.catalog.CatalogEntry`: the declared facts (producer,
    license, access tier, refresh, the per-site ``site_scope`` axis, storage) joined to the
    observed snapshot (:class:`CatalogObserved`). ``citation`` carries the producer as the
    bundle's shared provenance shape so the catalog speaks the same language as every other feed.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    scope: str  # documents | extracted | reference | derived | bundle | people | hypotheses | poi
    collection: str  # the first dir under the scope (e.g. "echo"), or the scope when flat
    status: str  # needs-review | reviewed | deprecated
    producer_kind: str  # connector | derived | vendored | manual | extracted
    command: str | None = None  # the `watermark <cmd>` regenerator
    connector_ref: str | None = None
    source: str  # human upstream label
    external_url: str | None = None
    license: str | None = None
    access_tier: str  # public | keyed | throttled
    site_scope: str  # lima-legacy | slug-scoped | basin-shared
    cadence: str  # daily | weekly | monthly | quarterly | annual | on-demand | static
    ttl_days: int | None = None
    last_refreshed: str | None = None
    tags: list[str] = Field(default_factory=list)
    storage: list[CatalogStorageFile] = Field(default_factory=list)
    observed: CatalogObserved | None = None  # None until `watermark catalog reconcile` has run
    citation: Citation


# --- typed GeoJSON feeds (issue #61) ------------------------------------------
class GeoProperties(BaseModel):
    """Layer metadata carried on every feature (extra popup fields allowed)."""

    model_config = ConfigDict(extra="allow")

    layer: str
    label: str | None = None
    color: str | None = None  # the legend swatch the renderer uses
    role: str | None = None  # geometry role: area | line | point


class GeoFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Feature"] = "Feature"
    geometry: dict[str, Any]  # WGS84 verbatim, display-only (no reprojection)
    properties: GeoProperties


class GeoFeatureCollection(BaseModel):
    """One typed GeoJSON layer feed for DeckGL (a valid FeatureCollection + ``feed``)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["FeatureCollection"] = "FeatureCollection"
    feed: str  # the feed/layer name (campus, jsmc, corridor, femaflood, rsei, ...)
    meta: dict[str, Any] = Field(default_factory=dict)
    features: list[GeoFeature] = Field(default_factory=list)


# --- ask-embeddings feed (issue #329) -----------------------------------------
class AskEmbeddingEntry(BaseModel):
    """One precomputed all-MiniLM-L6-v2 embedding for an ask-index unit (#329).

    Stored in the bundle as ``ask-embeddings.json`` and served as a static asset
    so the /api/ask Worker can embed the query at runtime and compute cosine
    similarity without an additional Python/Node dependency.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    """Stable id matching the corresponding AskUnit, ``{feed}:{local_id}``."""
    embedding: list[float]
    """384-dimensional L2-normalised float vector (all-MiniLM-L6-v2)."""


# --- passages feed (issue #1589, epic #1579 Phase 3) --------------------------
class PassageItem(BaseModel):
    """One page-level passage from a *published* source PDF — a page-cited excerpt (#1589).

    The unit the ``search_passages`` MCP tool returns instead of a whole extracted record: one
    relevant permit page shouldn't require pulling the full extraction. Scoped to the default-deny
    public-publish allowlist (#280) so no non-published source text ever ships in the bundle.

    ``document_id`` is the source document's ``DocumentItem.rel`` (path relative to
    ``data/documents``) — the join key to the ``documents`` feed and ``get_document``. ``text`` is
    the pypdf text-layer extraction verbatim; for a scanned document it is garbled OCR (per the root
    CLAUDE.md, never trust its digits), so treat it as a **locator** for the cited page, not a
    transcription. Image-only pages (no text layer) carry no excerpt and are omitted from the feed.
    """

    model_config = ConfigDict(extra="forbid")

    id: str  # stable passage id — ``{document_id}#p{page}``
    document_id: str  # DocumentItem.rel — path relative to data/documents (the join key)
    collection: str  # first path segment of document_id (e.g. "oepa") — the collection axis
    title: str  # the source document's catalog name, for display
    page: int  # 1-indexed printed page number (matches DocumentEntry provenance)
    # Sub-page heading when known; page chunks carry none today. Required-but-nullable (the builder
    # always emits it, `null` for unknown) so the feed contract matches the web `PassageRow` shape.
    section: str | None
    text: str  # the page's text-layer extraction (capped), verbatim


class PassageEmbeddingEntry(BaseModel):
    """One precomputed all-MiniLM-L6-v2 embedding for a :class:`PassageItem` (#1589).

    The passage-level peer of :class:`AskEmbeddingEntry`: stored as ``passage-embeddings.json`` and
    served as a static asset so the ``search_passages`` Worker can embed the query at runtime (the
    same 384-dim space) and compute cosine similarity for the hybrid BM25+vector rank. Absent
    entries degrade the tool to BM25-only, so a partial index is fine.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    """Stable id matching the corresponding :class:`PassageItem`, ``{document_id}#p{page}``."""
    embedding: list[float]
    """384-dimensional L2-normalised float vector (all-MiniLM-L6-v2)."""


# --- hydrated catalog index feed (epic #1090 / #1093) -------------------------
# The closed catalog kind set — the shared vocabulary of both tiers. The Python builder emits only
# the feed-backed kinds; the Astro overlay (`web/packages/core/src/catalog.ts`) adds the web-only ones
# (teardown/doc/chapter/figure). Typing `kind` as this Literal makes the generated
# `catalog-index.schema.json` carry a `kind` enum, which the frontend parity-tests against so the
# two tiers' kind sets can't silently drift (`watermark.site.catalog_index.CATALOG_KINDS`).
CatalogKind = Literal[
    "record",
    "timeline",
    "entity",
    "person",
    "place",
    "meeting",
    "exhibit",
    "concept",
    "lead",
    "contact",
    "dataset",
    "teardown",
    "doc",
    "chapter",
    "figure",
]


class CatalogAtom(BaseModel):
    """One addressable, "grabbable" atom in the hydrated catalog (#1093).

    A *pointer*, not a copy: ``feed`` + ``local_id`` name the live bundle row this handle
    resolves against at render time, so a user Story can cite a record without ever forking it
    (chain of custody). ``handle`` is the canonical address ``<kind>:<site>:<local_id>``, where
    ``local_id`` reuses the source feed's **existing** stable key (``rel``/``key``/``slug``/
    ``id``/``ref``) — no new ids are minted.
    """

    model_config = ConfigDict(extra="forbid")

    handle: str  # canonical address: <kind>:<site>:<local_id>
    kind: CatalogKind  # one of the closed catalog kinds (record, entity, timeline, meeting, ...)
    site: str  # the network-site slug this atom belongs to
    local_id: str  # the source feed's existing stable key
    title: str  # human-readable label for the grab UI
    feed: str  # the source feed name this atom resolves into (pointer, not copy)


class CatalogIndex(BaseModel):
    """The hydrated catalog — the addressable atom index the Story write/read paths consume (#1093).

    Emitted as an object feed carrying two version stamps: ``catalog_version`` (a content hash over
    the atom set, so #1099 can detect when a user Story's handles may have drifted) and the source
    ``contract_version``. The Python tier emits the feed-backed kinds here; the Astro build overlays
    the web-only kinds (``teardown``/``doc``/``chapter``/``figure``) at render time, so the resolver
    sees one merged catalog.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    catalog_version: str  # sha256 over the sorted atom handles — stable across identical corpora
    contract_version: str  # the bundle contract these atoms were indexed under
    atoms: list[CatalogAtom] = Field(default_factory=list)


# --- air dispersion field (GPU field/flow viz, epic #1237 / #1232) ------------------------
# A gridded AERMOD concentration surface for one pollutant — the deck.gl FieldLayer reads it
# (epic #1237). Distinct from the `air-dispersion` NAAQS *screen* feed (peak-vs-standard, per
# period): this is the full receptor grid reshaped into per-period `values[]` arrays plus the
# model-grid→lon/lat `geo_ref` the frontend georeferences the field with.


class DispersionGrid(BaseModel):
    """The receptor-grid geometry in AERMOD model metres (source at the origin, X=east, Y=north).

    ``x0_m``/``y0_m`` are the SW corner; ``nx``/``ny`` the counts; ``dx_m``/``dy_m`` the spacing.
    A period's ``values[]`` is row-major over this grid — ``values[iy * nx + ix]`` — so the
    frontend can index it without carrying per-cell coordinates.
    """

    model_config = ConfigDict(extra="forbid")

    nx: int = Field(ge=1)
    ny: int = Field(ge=1)
    dx_m: float = Field(gt=0)
    dy_m: float = Field(gt=0)
    x0_m: float  # SW-corner easting, relative to the source at (0, 0)
    y0_m: float  # SW-corner northing


class DispersionGeoRef(BaseModel):
    """The model grid's WGS84 corner box — how the frontend places the field on the map.

    The source sits at ``(source_lon, source_lat)``; ``sw``/``ne`` bound the axis-aligned grid
    (a deck.gl ``[west, south, east, north]`` box). Derived by a local flat-earth projection of
    the metre grid about the source, so it inherits the field's ``assumption`` provenance.
    """

    model_config = ConfigDict(extra="forbid")

    crs: str = "WGS84 (EPSG:4326)"
    source_lon: float
    source_lat: float
    sw_lon: float
    sw_lat: float
    ne_lon: float
    ne_lat: float


class DispersionPeriodField(BaseModel):
    """One averaging period's gridded concentration surface + its NAAQS reference line."""

    model_config = ConfigDict(extra="forbid")

    averaging_period: str  # the AERMOD AVE token: "1", "8", "24", "ANNUAL", ...
    values: list[float | None] = Field(default_factory=list)  # µg/m³, row-major; null = no receptor
    max_conc_ug_m3: float | None = None  # peak over the grid, when receptors are present
    naaqs_ug_m3: float | None = None  # the standard for this (pollutant, period), when one exists
    exceeds_naaqs: bool = False  # peak > standard (screening only — a flag, not a violation)


class DispersionField(BaseModel):
    """A gridded AERMOD dispersion surface for one pollutant — the #1232 deliverable.

    ``provenance`` is fixed to ``assumption``: the Lima permit redacts the genset stack geometry
    as CBI, so every modeled concentration inherits that assumed input and the frontend must
    render it ``[inference]``, never ``[verified]``. ``available`` is False (with empty ``values``)
    when the AERMOD binary/met is absent — the grid geometry, ``geo_ref`` and NAAQS lines still
    resolve, but no concentration is fabricated (the same honest degrade as ``air-dispersion``).
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    pollutant: str
    unit: str = "ug/m3"
    provenance: Literal["assumption"] = (
        "assumption"  # CBI-redacted stack ⇒ [inference], not [verified]
    )
    available: bool = False
    grid: DispersionGrid
    geo_ref: DispersionGeoRef
    periods: list[DispersionPeriodField] = Field(default_factory=list)
    stack_is_assumption: bool = True
    engine_version: str = ""
    caveats: list[str] = Field(default_factory=list)
    note: str = ""

    @classmethod
    def from_receptors(
        cls,
        *,
        site: str,
        pollutant: str,
        grid: DispersionGrid,
        geo_ref: DispersionGeoRef,
        period_receptors: dict[str, list[tuple[float, float, float]]],
        naaqs: dict[str, float | None],
        available: bool,
        unit: str = "ug/m3",
        stack_is_assumption: bool = True,
        engine_version: str = "",
        caveats: list[str] | None = None,
        note: str = "",
    ) -> DispersionField:
        """Reshape per-period ``(x_m, y_m, conc)`` receptors onto ``grid`` → a ``DispersionField``.

        Each period in ``period_receptors`` becomes a :class:`DispersionPeriodField` whose
        ``values[]`` is the row-major grid (null where no receptor landed — e.g. the source cell).
        ``naaqs`` supplies the per-period standard (µg/m³, or ``None`` where none is defined). An
        empty ``period_receptors`` (the binary/met-absent degrade) yields periods with empty
        ``values`` — the geometry is real, nothing is invented.
        """
        cells = grid.nx * grid.ny
        periods: list[DispersionPeriodField] = []
        for ave in period_receptors:
            recs = period_receptors[ave]
            values: list[float | None] = [None] * cells if recs else []
            peak: float | None = None
            for x_m, y_m, conc in recs:
                ix = round((x_m - grid.x0_m) / grid.dx_m)
                iy = round((y_m - grid.y0_m) / grid.dy_m)
                if 0 <= ix < grid.nx and 0 <= iy < grid.ny:
                    values[iy * grid.nx + ix] = conc
                    peak = conc if peak is None else max(peak, conc)
            std = naaqs.get(ave)
            periods.append(
                DispersionPeriodField(
                    averaging_period=ave,
                    values=values,
                    max_conc_ug_m3=peak,
                    naaqs_ug_m3=std,
                    exceeds_naaqs=bool(std is not None and peak is not None and peak > std),
                )
            )
        return cls(
            site=site,
            pollutant=pollutant,
            unit=unit,
            available=available,
            grid=grid,
            geo_ref=geo_ref,
            periods=periods,
            stack_is_assumption=stack_is_assumption,
            engine_version=engine_version,
            caveats=caveats or [],
            note=note,
        )


# --- reach-network centerlines (GPU flow viz, epic #1237 / #1235) --------------------------
# The real river-centerline geometry the deck.gl FlowLayer advects particles over. The model
# reaches (network.yaml / reaches.yaml) carry no coordinates, so this is verbatim NHDPlus via
# USGS NLDI (watermark.hydrology.reach_geometry), committed under data/reference/hydrology/reaches/.
# Keyed by `node_id`, so the frontend joins each reach's flow magnitude (from routed-hydrograph)
# and deficit state (from hydrology-scenarios) without re-carrying those numbers here.


class ReachLine(BaseModel):
    """One reach node's river centerline — a downstream-oriented (lon, lat) polyline."""

    model_config = ConfigDict(extra="forbid")

    node_id: str  # the network.yaml node id (join key)
    name: str
    receiving_water: str | None = None
    downstream: str | None = None  # the node this reach drains into (None at the outlet)
    length_km: float
    coordinates: list[tuple[float, float]]  # (lon, lat), ordered head → downstream


class ReachNetwork(BaseModel):
    """The reach network's river-centerline geometry for the FlowLayer viz (#1235)."""

    model_config = ConfigDict(extra="forbid")

    site: str
    crs: str = "WGS84 (EPSG:4326)"
    reaches: list[ReachLine] = Field(default_factory=list)
    note: str = ""
    caveats: list[str] = Field(default_factory=list)


# --- water seasonal evaporation / net-atmospheric-withdrawal field (epic #1237 / #1236) ----
# The seasonal climograph the deck.gl FieldLayer renders as a cartesian month-axis strip (Phase-2
# water). The field scalar is net atmospheric withdrawal (reference ET0 - precip, mm/day) from the
# cited NASA POWER normals + FAO-56 ET0; the deficit boundary (net=0) is the load-bearing threshold
# isopleth. Distinct from `hydrology-scenarios` (the annual water balance): this is the month-by-
# month seasonal read `watermark.hydrology.scenario.evaluate_seasonal` produces.


class SeasonalMonthCell(BaseModel):
    """One month of the seasonal climograph: the climate drivers + the low-flow screen.

    ``net_atmospheric_mm_day`` (ET0 - precip) is the field scalar the FieldLayer ramps; a positive
    value is a growing-season deficit (ET exceeds precipitation, so no rainfall buffer).
    ``multiple`` is the draw read against ``low_flow_cfs`` (the cited seasonal floor — 30Q10 summer
    in the growing season, else the annual 7Q10); it rests on the *modeled* buildout draw, so the
    frontend renders it ``[inference]``, never a measured withdrawal.
    """

    model_config = ConfigDict(extra="forbid")

    month: str  # JAN..DEC
    growing_season: bool  # ET0 > precip this month
    et0_mm_day: float
    precip_mm_day: float
    net_atmospheric_mm_day: float  # ET0 - precip — the field scalar
    low_flow_cfs: float  # the cited design low flow applied this month
    low_flow_basis: str  # "30Q10 summer" | "7Q10 annual"
    consumptive_cfs: float  # this month's net consumptive draw (month-varying for hybrid)
    multiple: float | None  # draw / low_flow (None when the floor is 0)


class SeasonalField(BaseModel):
    """The seasonal evaporation / net-atmospheric-withdrawal climograph — the #1236 deliverable.

    A month-axis climograph the deck.gl FieldLayer renders as a cartesian strip (epic #1237, Phase
    2). The field scalar is net atmospheric withdrawal (reference ET0 - precip, mm/day): a one-hue
    bone->forest->ink ramp, with the deficit boundary (net=0) as the threshold isopleth — the
    growing-season edge, where ET starts to exceed precipitation. ``provenance`` is fixed to
    ``reference``: the climograph is the cited NASA POWER normals + FAO-56 ET0. The per-month
    ``multiple`` overlays the *modeled* buildout consumptive draw against the cited seasonal low
    flow, so that read is ``[inference]`` — surfaced in the SSR table/probe, never baked into the
    mm/day raster scalar. ``available`` is False (empty ``months``) when the climate/ET inputs or
    the buildout scenario are absent — the thresholds still resolve, nothing is fabricated.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    scenario: str
    cooling_model: str | None = None
    unit: str = "mm/day"  # the field scalar's unit (net atmospheric withdrawal)
    # The climograph is cited climate normals; the per-month `multiple` alone is [inference].
    provenance: Literal["reference"] = "reference"
    available: bool = False
    consumptive_cfs: float | None = None  # the headline draw screened (cfs)
    annual_7q10_cfs: float | None = None
    summer_30q10_cfs: float | None = None
    one_q10_cfs: float | None = None  # absolute design low flow (often 0)
    annual_multiple: float | None = None  # draw / annual 7Q10
    summer_multiple: float | None = None  # draw / summer 30Q10 — the seasonal headline
    growing_season_months: list[str] = Field(default_factory=list)
    months: list[SeasonalMonthCell] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    note: str = ""


# --- manifest ------------------------------------------------------------------
FeedKind = Literal["collection", "object", "geojson"]


class FeedRef(BaseModel):
    """One entry in the manifest's feed index — what it is and how to read it."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    path: str  # relative to the bundle root, e.g. "feeds/records.json"
    media_type: str  # application/json | application/geo+json | application/x-ndjson
    schema_ref: str = Field(serialization_alias="schema", validation_alias="schema")
    kind: FeedKind
    count: int  # rows (collection), features (geojson), or 1 (object)


ExportFormat = Literal["turtle", "jsonld", "graphml"]


class ExportRef(BaseModel):
    """One entry in the manifest's graph-**exports** index (#1574) — a downloadable serialization
    of the corpus mirror (:mod:`watermark.site.graph_exports`), not a typed feed.

    Distinct from :class:`FeedRef`: an export is an interchange artifact (RDF / GraphML) for
    external graph tools, keyed by ``format`` rather than storage ``kind``, carrying the graph's
    node/edge counts. The wiki graph page reads this list to render the download links.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    path: str  # relative to the bundle root, e.g. "exports/corpus.ttl"
    media_type: str  # text/turtle | application/ld+json | application/graphml+xml
    format: ExportFormat
    node_count: int  # mirror nodes serialized
    edge_count: int  # resolved (non-dangling) links serialized


class DomainReadiness(BaseModel):
    """Per-domain activation state (#1220): each of the five domains is ``absent|seeded|live``.

    Computed at export from feed counts + the ``SiteProfile`` by :mod:`watermark.site.readiness`
    (the SSOT for the predicates); this is only the wire shape. The ``State``/``Domain``
    vocabulary lives there so the schema and the computation can never drift.
    """

    model_config = ConfigDict(extra="forbid")

    backdrop: State
    facility: State
    places: State
    record: State
    story: State


class SiteReadiness(BaseModel):
    """The manifest's standing **readiness** block (#1220 / #1222): the per-domain states plus
    the tier :func:`watermark.site.readiness.site_tier` derives from them.

    Recomputed at every ``watermark export``, so it rises when a source lands and falls when one
    dries up — a standing property, not an onboard-time snapshot. The frontend
    (``web/packages/core/src/readiness.ts``) reads this instead of re-deriving section gating from raw
    feed counts (#1223).
    """

    model_config = ConfigDict(extra="forbid")

    tier: Tier
    domains: DomainReadiness


class Manifest(BaseModel):
    """The bundle index: version, provenance of the generation, and the feed list."""

    model_config = ConfigDict(extra="forbid")

    site: str  # the network-site slug this bundle is for (#762) — so a bundle self-identifies
    bundle_version: str  # the data generation's version (bumped on every export)
    contract_version: str  # the schema/contract version these feeds conform to
    generated_at: str  # ISO-8601 UTC
    feed_count: int
    row_total: int  # sum of feed counts — a quick internal-consistency check
    readiness: SiteReadiness  # standing domain-activation readiness (#1220) — tier + per-domain
    # The primary facility's lifecycle status + facility count (#1628) — the per-slug source the
    # frontend badge reads. Optional so a pre-1.31 bundle (or a facility-less site) degrades to
    # `investigation` rather than crashing.
    facility: FacilitySummary | None = None
    feeds: list[FeedRef] = Field(default_factory=list)
    # Downloadable graph exports of the corpus mirror (#1574) — RDF/GraphML interchange artifacts,
    # present on a canonical `watermark export` (absent for a redirected/test bundle). Optional so a
    # pre-1.28 bundle without the block still validates.
    exports: list[ExportRef] = Field(default_factory=list)
