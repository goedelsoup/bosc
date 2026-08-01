# The normalized `facts` feed + `get_facts` — design (#1587)

> Spike + feat. Phase 3 of the MCP corpus-retrieval epic (#1579). Status: **implemented** on
> this branch — the `facts` feed (`watermark.site.facts`) + the `get_facts` MCP tool. The §10
> decisions are resolved (v1 covers all exported `ProvenancedValue` feeds + `PowerBasis`).

## 1. The problem

The public MCP server does **item-level** retrieval: one `search_corpus` hit returns the
matched unit's whole flattened blob (a full normalized record). A fact question therefore
pulls ~18–24k tokens for what should be a sub-1.5k-token answer.

`get_facts` turns a fact question into a **tiny retrieval + arithmetic**:

```text
get_facts(subject="Project BOSC", predicate=["genset_count", "genset_rating"])
   → genset_count  = 114   (count)   [verified] air-permit
   → genset_rating = 2.75  (MW each) [verified] air-permit
   → caller computes 114 × 2.75 = 313.5 MW
```

instead of injecting the whole facility record to recover two numbers.

## 2. What exists today (the reason this is a spike, not a wiring job)

The corpus already tags every number with provenance — but through **two different
carriers**, and they diverge on exactly the axis a normalized fact needs (a structured
document + page vs. free text):

| carrier | where | shape | `page`? |
|---|---|---|---|
| **`ProvenancedValue`** | `watermark.hydrology.models._core` (shared) | `value, unit, source: SourceKind, citation: str \| None, confidence, asof, low/high` | **no** — `citation` is one free-text string |
| **`feeds.Citation`** | `watermark.site.feeds` | `source, source_kind, page: int \| None, pages: list[int] \| None, confidence, note, verified` | **yes** (typed) |

Every **typed numeric fact** in the bundle (economics, greenops, hydrology, air, facility
power) is a `ProvenancedValue` — clean `value`/`unit`/`source`, but a **free-text citation
with no page**. The structured, page-bearing `Citation` is used only by the record/document
side (`records`, `hypotheses`, `exhibits`). `records` used to write the page into the free-text
`note` rather than the typed `page` field; #1584 fixed that, so a record now carries a real
1-based `page` (and a `pages` span) — but the `ProvenancedValue` side is unchanged, and that
asymmetry is what the rest of this document is about. `feeds.Figure` (`{value,
approximate, unit, citation}`) is the closest existing shape to the target, but it is a
**latent, never-constructed** model.

So `(subject, predicate, value, unit, status)` and page-level evidence **do not co-exist in
any one source today.** That is the core finding.

### Inventory — provenanced numeric facts by feed

Exported bundle feeds whose fields are `ProvenancedValue`:

| feed | builder | subject (identity present?) | notable facts (unit) |
|---|---|---|---|
| `economics-baseline` | `economics.export_economics` | **county** `fips`/`area_name`; sectors keyed by `naics` ✓ | `total_employment` (jobs), `establishments`, `avg_annual_pay` (USD/yr), `avg_weekly_wage`, per-sector `annual_avg_employment`/`location_quotient`, `median_household_income` (USD) |
| `consumer-energy` | `economics.export_consumer_energy` | **state/area**, series keyed by `series_id/fuel/metric` ✓ | latest `price` (¢/kWh, $/Mcf), `sales` (M kWh) |
| `economics-demand-pressure` | `economics.export_demand_pressure` | **facility × state** (facility id *implicit* — per-slug) | `facility_draw_mw`, `demand_share_pct`, `households_equivalent`, `price_pressure_pct_low/high` |
| `energy-burden` | `economics.export_energy_burden` | **household in area** (area ✓) | `electricity_burden_pct`, `gas_burden_pct`, `combined_burden_pct`, annual costs (USD) |
| `greenops` | `greenops.export_greenops` | **the platform** (global singleton, no site) | headline compute/electricity/water/**carbon**; `EnergyBreakdown.infrastructure/inference` (MWh, #1643 — model inference is in the energy chain, not scoped out); `CarbonAccount` location-based (ours and the provider's) + market-based + grid intensity; `WaterDraw.direct/indirect/budget_cap` (gal, tenant-attributed — the cooling is our provider's, apportioned by billed IT-kWh); never `[verified]` by rule |
| `hydrology-scenarios` | `_load_scenarios` | **receiving water + campus node** (`receiving_water_name`, `Node.id/role`) ✓ | `consumptive_loss` (cfs), `receiving_7q10` (cfs), `cooling_demand` (MGD), basis `it_load`/`wue`/`makeup_demand` |
| `air-scenarios` | `_load_air_scenarios` | **genset fleet** (facility id *implicit*), per `pollutant` | `engine_mw` (MW), `runtime_hours` (hr/yr), `PollutantTonnage.tpy` |

Two headline feeds carry facts **without** `ProvenancedValue`:

- **`rsei`** — bare `float`s (`score`, `pounds`, …); provenance is out-of-band in
  `RseiInventory.meta.source` + module caveats. Subject is strongly identified
  (`facility_id`, `npdes_permit`, `naics`, `fips`). A projection would synthesize per-fact
  provenance from the shared `meta`.
- **`records.fields`** — the raw extraction payloads, **untyped** `dict[str, Any]` with the
  `~` marker as a string (OPC cost estimates, deed amounts, permit limits). Structured
  `Citation` (with a real 1-based `page`/`pages` since #1584), but no predicate normalization.

### The motivating example is not in the bundle yet

`get_facts(subject="Project BOSC", predicate=["genset_count","genset_rating"])` — the
issue's own example — draws on `PowerBasis` (`facility.power.derive_power_basis`):
`genset_count`, `genset_rating`, `it_load`, `pue`, `facility_draw`, `backup_power`, all
`ProvenancedValue` with **structured `document` citations** (the air-permit). But
`PowerBasis` is **derived on the fly, never exported as a feed** (only `economics-demand-
pressure` and cooling consume it). To answer the issue's own example, v1 must project facts
from `derive_power_basis(settings)` in addition to the exported feeds. This is a small,
contained reach into an existing derivation and dovetails with the facility-modeling epic
(#1626, "MW math hand-duplicated / severed at feeds.ts").

## 3. Decision: projection, not new extraction

**The `facts` feed is a normalization pass over facts the corpus already carries** — not a
new extraction pipeline. Precedent: `catalog-index` (#1093) is exactly this shape — a cheap
post-pass over the already-assembled feeds (`build_catalog_index(rows_by_feed, …)`),
minting no new ids, copying no payloads, pointing back at each source row. `facts` is the
`catalog-index` pattern applied to the numeric layer.

New extraction (parsing figures out of untyped `records.fields`, or OCR'ing pages for
predicates) is a separate epic and out of the spike's scope. Rationale: (a) the spike's
"Done" is a *design doc + feed + tool*, not a pipeline; (b) fabricating facts from garbled
OCR digits violates the data-discipline rules ("never trust its digits"); (c) the
`ProvenancedValue` feeds already give clean `value`/`unit`/`status` with zero invention.

## 4. The `FactItem` model

Added to `watermark.site.feeds` (the contract SSOT); schema generated from it.

```python
FactStatus = Literal["verified", "inference", "reference", "open"]

class FactEvidence(BaseModel):          # a thin alias over the shared provenance shape
    model_config = ConfigDict(extra="forbid")
    source: str | None = None           # repo-relative artifact path / dataset label / doc id
    source_kind: SourceKind             # document|connector|reference|assumption|derived
    page: int | None = None             # populated only where genuinely known — never invented
    citation: str | None = None         # the ProvenancedValue free-text citation, verbatim
    confidence: Confidence = "medium"
    asof: str | None = None
    @computed_field verified -> bool     # = source_is_verified(source_kind)

class FactItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str                        # canonical key, e.g. "site:lima", "county:39003",
                                        #   "facility:lima", "naics:39003:62"
    subject_label: str                  # human display, e.g. "Allen County, Ohio"
    subject_kind: str                   # site|county|state|facility|watershed|sector|platform|…
    predicate: str                      # normalized snake_case, e.g. "genset_count"
    value: float | int | None           # None ⇒ an asserted-but-unquantified fact (status=open)
    unit: str | None = None
    status: FactStatus
    approximate: bool = False           # the ~ marker (records / Figure), as data
    low: float | None = None            # uncertainty band (#760), carried through
    high: float | None = None
    evidence: FactEvidence
    feed: str                           # provenance-of-the-projection: the source bundle feed
```

Design notes:

- **`evidence` reuses the bundle's one provenance language.** It is the `Citation` shape
  with the `ProvenancedValue` free-text string kept verbatim in `citation`, `page`
  populated only where a structured page genuinely exists (records; a permit page). It is
  **never fabricated** — a `ProvenancedValue` with no page yields `page=null`, honestly.
- **`feed`** makes every fact traceable back to the row it was projected from (the
  `catalog-index` "pointer, not copy" discipline), and is what `get_facts` /
  `aggregate_facts` filter on for the `fact_category` axis (#1827 — see §5).
- **`low`/`high`** carry the existing uncertainty band so a bracketed estimate stays a band.

## 5. Subject & predicate grammar

**Subject = a structured key + a display label + a kind** (mirrors the `catalog-index`
handle grammar `<kind>:<site>:<local_id>` rather than inventing a new one):

| subject_kind | key example | source |
|---|---|---|
| `site` | `site:lima` | the active slug (whole-site facts) |
| `facility` | `facility:lima` | `SiteProfile.facility` / `PowerBasis` |
| `county` | `county:39003` | economics `fips` |
| `state` | `state:oh` | consumer-energy `area` |
| `sector` | `naics:39003:62` | economics per-NAICS sector |
| `watershed` | `reach:<node_id>` | hydrology `Node.id` / `receiving_water_name` |
| `platform` | `platform:bosc` | greenops (global) |

`get_facts(subject=…)` matches **flexibly** — case-insensitive over `subject`,
`subject_label`, and the key's `local_id` — so the issue's `subject="Project BOSC"` resolves
without the caller knowing the key grammar. Granularity rides on the **subject** (the
sector, the node, the pollutant), keeping **predicate** a small, clean vocabulary of
snake_case field names (`genset_count`, `total_employment`, `consumptive_loss`,
`demand_share_pct`, …), which is what the caller filters on.

### Fact categories — the grouping over `feed` (#1827)

`FactItem.feed` **is** the category axis, so `get_facts` / `aggregate_facts` expose it two
ways: `feed` takes one exact source (or a list), and `fact_category` takes a named grouping
over them. The vocabulary lives in **one** place —
`web/packages/core/src/factCategories.ts` — which both the tool schema and the handlers read,
so the enum and the filter cannot drift.

| category | feeds | what it answers |
|---|---|---|
| `economics` | `economics-baseline` | the county labor market and household income the facility lands in |
| `energy` | `consumer-energy`, `energy-burden`, `economics-demand-pressure` | what power costs the public here, and what a new load does to that |
| `facility-power` | `facility-power` | what the facility itself draws (gensets, IT load, PUE) |
| `water` | `hydrology-scenarios` | the cooling water balance against the receiving stream |
| `air` | `air-scenarios` | the genset fleet's modeled annual emissions |
| `platform` | `greenops` | Watermark/BOSC's **own** compute/carbon/water footprint |

A grouping is an **editorial claim** — it asserts that two feeds answer the same *kind* of
question — so two calls are written down rather than inferred from feed names:

- **`economics-demand-pressure` is filed under `energy`, not `economics`.** Its predicates are
  grid quantities (`demand_share_pct`, `load_factor`, `state_retail_sales_gwh`,
  `price_pressure_pct_low/high`): it measures the facility's load against the state retail
  market and the ratepayer pressure that follows. The feed's *name* is economics; its
  *content* is the electricity market, and a caller asking for `economics` wants the
  labor-market baseline.
- **`facility-power` is not part of `energy`.** `energy` is what power costs the public;
  `facility-power` is what the facility draws — a different subject (`facility:<site>`, not
  the ratepayer) and a different evidence posture (mostly `[inference]`, derived off a
  disclosed backup fleet). Merging them would return a document-anchored retail price beside
  a derived draw as though they answered the same question.

The grouping is a **partition** (every feed belongs to exactly one category), and
`factCategories.test.ts` sweeps the committed per-site bundles to keep it total as the Python
projectors grow — a new `feed=` literal in `watermark.site.facts` fails there, named, rather
than at runtime.

**A constraint that names nothing real fails loudly.** An unknown `fact_category`, an unknown
`feed`, or a `fact_category`/`feed` pair that can't both hold each return an error row
carrying the vocabulary — never an empty result set, which would be indistinguishable from
"the corpus has no such facts" for a question the corpus can plainly answer. This is why the
axis is **not** a `search_corpus` facet (#1691 proposed it there): the `facts` feed is not in
the ask index, so the constraint would have filtered on a field no unit carries.

## 6. Status → the evidence vocabulary

`status` is derived from `source_kind` via the existing `source_is_verified` discipline — no
new judgement:

| `source_kind` | `status` | tag |
|---|---|---|
| `document`, `connector` | `verified` | `[verified]` |
| `reference` | `reference` | `[reference]` |
| `assumption`, `derived` | `inference` | `[inference]` |
| — (value is `None`) | `open` | `[open]` |

`open` is reserved for an asserted-but-unquantified fact (a known predicate with no value —
a lead). v1 projection over `ProvenancedValue`s yields only verified/inference/reference;
`open` is in the schema for the leads/needs tie-in (deferred, §9).

## 7. v1 sources (and what's deferred)

**v1 projects from** (recommended — see the open decision below):

1. All exported `ProvenancedValue` object feeds: `economics-baseline`, `consumer-energy`,
   `economics-demand-pressure`, `energy-burden`, `greenops`, `hydrology-scenarios`,
   `air-scenarios`.
2. **`PowerBasis`** via `derive_power_basis(settings)` — to serve the issue's own
   generator/IT-load/draw example, the highest-value facility facts (facility-gated:
   absent for a thin site, exactly like `demand-pressure`).

**Deferred to a follow-up** (documented, not silently dropped):

- **`rsei`** — bare floats + out-of-band `meta`; a projection must synthesize per-fact
  provenance. Mechanical but distinct; fold in once the shape is proven.
- **`records.fields`** — untyped payloads need per-`RecordGroup` predicate rules (OPC
  totals, deed amounts, permit limits). Highest fabrication risk; needs its own care.
- **`aggregate_facts`** (#1588) — server-side sum/count/group over the same feed. `get_facts`
  ships the tuples; `aggregate_facts` is the arithmetic tier on top. **Done** — see
  [aggregate-facts.md](aggregate-facts.md).
- **The leads/`open` tie-in** — surfacing readiness "needs" as `open` facts.

Each projector is a small pure function `fn(feed_row_or_model) -> list[FactItem]`, so adding
a source later is one function + a registry row (the `_SPECS`/`_collect_feeds` idiom).

## 8. Build wiring

`facts` is a **post-pass**, like `catalog-index` — it needs the assembled feeds in hand.

- **`feeds.py`**: add `FactItem` + `FactEvidence`; bump `CONTRACT_VERSION` `1.24.0 → 1.25.0`
  (MINOR — a new feed) with a changelog stanza.
- **`site/facts.py`** (new): `build_facts(rows_by_feed, *, settings) -> list[FactItem]`, a
  registry of per-source projectors. Object feeds are re-read from the assembled payloads
  (`_collection_rows` peer for objects) or the in-memory models; `PowerBasis` is derived.
- **`export.py`**: append `_facts_feed(feeds, settings)` right after `_catalog_index_feed`
  (both are normalization passes over the just-assembled feeds).
- **Contract touchpoints** (per the "adding a feed" discipline): generated
  `schemas/facts.schema.json`; the README feed table; `manifest.example.json`; the committed
  `web/sites/<slug>/` bundles (regenerated); the web `contract_version` test fixtures.
- **Catalog**: `facts` becomes a `dataset`-kind catalog atom; run `catalog reconcile` +
  `audit --apply` after regen.

## 9. The `get_facts` MCP tool

Follows the **existing governed-envelope convention** (`get_document`'s sibling) — text
content carrying `{ results, token_estimate, truncated, next_cursor }`. **Note:** issue
#1577 (`structuredContent`/output schemas) is *not* on this branch; `get_facts` does not
introduce it.

- **`web/packages/core/src/feeds.ts`**: a `FactItem` TS interface.
- **`web/src/pages/feeds/facts.json.ts`**: static emitter (`loadFeed("facts")`), mirroring
  `records.json.ts`.
- **`web/packages/core/src/mcpTools.ts`**: a `MCP_TOOLS` entry:

  ```text
  get_facts — retrieve normalized (subject, predicate, value, unit, status) facts.
    subject             flexible match over subject/label/key (e.g. "Project BOSC", "Allen County")
    predicate           string | string[] — filter to these predicates
    status              filter by verified|inference|reference|open
    fact_category       economics|energy|facility-power|water|air|platform (#1827, §5)
    feed                string | string[] — one exact source feed instead of a grouping
    include_evidence    bool (default false) — attach the evidence block (source/page/citation)
    site, intent, max_results, max_tokens, cursor   (shared governance knobs)
  ```

  Default (`include_evidence=false`) returns compact `{subject, predicate, value, unit,
  status}` tuples — the sub-1.5k-token answer. `include_evidence=true` attaches
  `evidence{source, source_kind, page, citation, verified}` per fact.

- **`web/functions/api/_lib/mcpTools/bundleReaders.ts`**: `handleGetFacts(params,
  requestUrl)` — resolve the `fact_category`/`feed` gate (`resolveFeedGate`, shared with
  `handleAggregateFacts`), `fetchFeed<FactItem[]>("facts")`, filter by
  category/subject/predicate/status, strip `evidence` unless requested, paginate via
  `govern(...)`.
- **`mcpDispatch.ts`**: import + `case "get_facts":`.
- **Resources**: add `facts` to `READABLE_FEEDS` + a `FEED_DESCRIPTIONS` entry.
- **Tests**: a `handleGetFacts` block mirroring `handleGetDocument` (filter, projection,
  `include_evidence`, budget shed); Python `tests/test_facts_feed.py` (projection
  correctness, no-fabrication, schema validation, subject/predicate coverage).

## 10. Decisions (resolved)

1. **v1 source coverage** — *all exported `ProvenancedValue` feeds plus `PowerBasis`* (§7).
   `rsei` (bare floats + out-of-band `meta`) and `records.fields` (untyped payloads) are
   deferred follow-ups; each is one projector function when picked up.
2. **`PowerBasis` reach** — **in**. The facility power facts (the issue's own
   `genset_count × genset_rating` example) are projected directly from
   `derive_power_basis(settings)` even though `PowerBasis` is not an exported feed, so the
   motivating example resolves in v1. Facility-gated, exactly like `economics-demand-pressure`.

Everything else (projection over extraction, `FactItem` shape, subject/predicate grammar,
status mapping, the page-honesty constraint, the governed-envelope tool) is settled by the
existing patterns and the data-discipline rules.
