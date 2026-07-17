# `aggregate_facts` — deterministic server-side totals (#1588)

> Phase 3 of the MCP corpus-retrieval epic (#1579). Status: **implemented**. The arithmetic
> tier on top of the `facts` feed (#1587, [facts-feed.md](facts-feed.md)): `get_facts` ships
> the normalized tuples; `aggregate_facts` does the sum / count / mean / product the model
> would otherwise pull every row to compute.

## 1. The problem

`get_facts` already turns a fact question into a tiny retrieval — but a *total* still makes the
model pull every contributing row into its context and add them up itself. Two failures:

- **Cost.** Totalling employment across 20 NAICS sectors, or backup capacity across a fleet,
  drags 20+ tuples into context to recover one number.
- **Trust.** The arithmetic happens in the model, undocumented and non-reproducible. A wrong
  sum is invisible.

`aggregate_facts` moves the arithmetic to the server and hands back one grouped total with a
**human-readable derivation**, a **confidence**, a **caveat**, and the **`evidence_ids`** that
fed it:

```text
aggregate_facts({ metric: "backup_generation_capacity_mw", group_by: "project" })
   → { group: "facility:lima", value: 313.5, unit: "MW", derivation: "114 × 2.75 MW",
       status: "inference", confidence: "high", n: 2,
       caveat: "Emergency BACKUP generation … not primary/continuous generation. …",
       evidence_ids: ["facility:lima/genset_count", "facility:lima/genset_rating"] }
```

## 2. Generalizing `derive_power_basis`

The closest existing math is `watermark.facility.power.derive_power_basis`:
`backup_mw = genset_count × genset_rating` and `facility_draw = it_load × PUE`, with a
derivation string in the value's `citation`. But it runs off `SiteProfile.facility` constants,
not corpus facts, and the arithmetic is inline and single-purpose.

`aggregate_facts` lifts that arithmetic into a **data-driven recipe over the exported facts
feed**: `backup_generation_capacity_mw` reads the `genset_count` and `genset_rating` *facts*
(which #1587 already projected from the same `PowerBasis`) and multiplies them — the same
number, now one queryable surface, and reusable for any product/sum/count/mean the feed
supports. Because the engine is pure `@watermark/core` (`factAggregate.ts`), the Astro site can
import the exact same function, so the TS side of the MW math is computed once, not
hand-duplicated (dovetails with the facility-modeling epic #1626).

No new bundle feed and **no `CONTRACT_VERSION` bump**: the tool computes at request time over
the already-shipped `facts.json`.

## 3. The metric grammar

`metric` resolves in one of two ways (`resolveMetric`):

- **A registered recipe** (`FACT_METRICS` in `factAggregate.ts`) — the cross-predicate
  derivations that aren't a simple group sum:

  | key | op | inputs | unit | scope |
  |---|---|---|---|---|
  | `backup_generation_capacity_mw` | product | `genset_count` × `genset_rating` | MW | `facility` |
  | `facility_draw_mw` | product | `it_load` × `pue` | MW | `facility` |

- **The generic `<op>:<predicate>` grammar** — simple sum/count/mean of any single predicate,
  so the whole feed is aggregable without enumerating every predicate:
  `sum:annual_avg_employment`, `mean:avg_weekly_wage`, `count:genset_count`,
  `product:genset_count,genset_rating`, or the bare word `count` (count every matching fact).

Called with **no `metric`**, the tool lists the registered recipes (discovery).

## 4. Grouping

`group_by` partitions the total:

| value | dimension | example groups |
|---|---|---|
| `project` / `subject` (default) | the fact `subject` | one per facility / county / scenario |
| `kind` (`subject_kind`) | the subject kind | `facility`, `county`, `sector` |
| `feed` | the source bundle feed | `facility-power`, `economics-baseline` |
| `all` / `site` | one whole-site group | `site` |

A **product** is computed **per subject first** (each subject supplies one value per factor),
then rolled up to a coarser `group_by` by **summing** the per-subject products — so a
multi-facility site totals correctly. A subject missing a factor is omitted and flagged in the
`caveat`.

## 5. The evidentiary contract

Every result carries provenance, following the same discipline as the rest of the bundle:

- **`status`** is the **weakest** input status (`open` < `inference` < `reference` <
  `verified`) — an aggregate is only as strong as its weakest quantified fact. A **product is
  never reported stronger than `inference`**, matching `derive_power_basis` (whose
  `backup_power` / `facility_draw` are emitted `derived` even though the factors are
  document-anchored): arithmetic over facts is a derivation, not a document.
- **`confidence`** is the weakest input `evidence.confidence`.
- **`caveat`** prepends the recipe's standing note (e.g. "emergency BACKUP generation, not
  primary"), then flags modeled inputs and any omitted subjects. Never invented.
- **`evidence_ids`** are the `<subject>/<predicate>` handles of the facts summed — each
  re-fetchable through `get_facts(subject=…, predicate=…)`, so a total is always drillable back
  to its tuples.
- **`derivation`** is the literal arithmetic: `"114 × 2.75 MW"` for a single-subject product,
  `"12000 + 20000 = 32000 jobs"` for a sum (bounded to a few terms for a long list).

## 6. Wiring

- **`web/packages/core/src/factAggregate.ts`** — the pure engine: `FACT_METRICS`,
  `resolveMetric`, `aggregateFacts`, `listMetrics`, `parseGroupBy`. Unit-tested in
  `factAggregate.test.ts`.
- **`web/functions/api/_lib/mcpTools/bundleReaders.ts`** — `handleAggregateFacts`: fetch
  `facts.json`, filter by `subject`/`status`, call the engine, wrap in the governed
  `{ results, token_estimate, truncated, next_cursor }` envelope (shed order: `evidence_ids` →
  prose → never the value/unit/group).
- **`web/packages/core/src/mcpTools.ts`** — the `aggregate_facts` `MCP_TOOLS` schema.
- **`web/functions/api/_lib/mcpDispatch.ts`** — the `case "aggregate_facts"`.

It is a tool, not a feed, so there is no resource advertisement and no schema/manifest
touchpoint.

## 7. Deferred

- **Ad-hoc N-ary products beyond two factors** and unit inference for generic products (v1
  infers a unit only for single-predicate sum/mean; a registered product declares its unit).
- **`rsei` / `records.fields`** — once #1587's deferred projectors land those predicates in the
  facts feed, they aggregate here for free.
- **Weighted aggregations** (e.g. employment-weighted mean wage) — the v1 ops are unweighted.
