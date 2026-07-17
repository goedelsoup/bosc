# The aggregated `open-questions` feed — design (#1568)

> feat. Workstream B of the yidam corpus epic (#1560); depends on the mirror (#1561/#1562).
> Status: **implemented** — the `open-questions` feed (`watermark.site.open_questions`,
> contract 1.27.0). Ports yidam's `open-questions` model into a typed bundle feed.

## 1. The problem

The corpus already holds its **unanswered** parts as first-class data, but across three stores:

- **`data/site/leads.yaml`** — the per-site open board (`watermark.site.leads`), each lead an
  `[open]` gap or an `[inference]` reading, keyed to the GitHub `lead:kind:*` / `lead:status:*`
  label vocabulary (`watermark.site.gh_leads`).
- **the hypothesis matrix** — the `(site × hypothesis)` evidence cells
  (`data/hypotheses/<hid>/<site>.yaml`, `watermark.hypotheses`), where an `[open]`-tagged cell
  is a documented gap: no nexus yet for this site under that boom-origin lens.
- **`[open]` claims** — the tag vocabulary itself (`docs/investigative-method`), which the two
  stores above carry structurally (a lead's `tag`, a cell's `tag`).

A reader — or the research agent — asking "what's still open here?" had to walk all three.
yidam already answers this over its projected corpus (`yidam open-questions`, replicated in
Python as `watermark.site.corpus_mirror.render_open_questions`): a node is open when it carries
the `[open]` tag. This feed brings that answer into the **content bundle** as a typed feed.

## 2. What it is

A **post-pass projection** — like `facts` (#1587) and `catalog-index` (#1093), it re-loads no
corpus, mints no claims, and copies no payloads it didn't already ship. It reads two
already-assembled feeds and aggregates their still-open rows into one flat, provenanced list:

```text
open-questions  ←  leads (tag == "open")  +  hypothesis-assessments (tag == "open")
                   (labelled via the hypotheses feed's lens rows)
```

The `[open]`-tag filter is the whole model: an `[inference]`-tagged lead is a *labeled reading*,
not a gap, so it is excluded — exactly as `render_open_questions` excludes it (`claim_tag ==
"open"`). One `OpenQuestionItem` per surviving row:

| field | leads origin | hypothesis origin |
|---|---|---|
| `id` | the lead id (`OEPA-2DP00130`) | `hyp:<hid>:<site>` (`hyp:water:lima`) |
| `origin` | `"lead"` | `"hypothesis"` |
| `question` | the lead `title` | `Open thread — <lens> @ <site>` |
| `detail` | the lead `detail`, one line | synthesized (`No documented nexus yet …`) |
| `source` | the lead `source` (the real citation) | `data/hypotheses/<hid>/<site>.yaml` |
| `kind` / `status` / `issue` | carried from the lead (`lead:kind:*` / `lead:status:*`) | `null` |
| `hypothesis` / `hypothesis_label` / `signal` | `null` | the lens id / label / cell signal |

Every row carries **provenance** (the issue's Done): a lead names where the gap is recorded; an
open cell has no `Citation` by rule (only an `open` cell may have none), so its `source` points
at the committed matrix file where the gap lives — never a fabricated citation (chain of
custody).

## 3. Scope + skip behaviour

Per-site scoped (#762): the projection runs over *this* bundle's committed `leads` +
`hypothesis-assessments` feeds, so a peer surfaces its own open threads, never Lima's. The feed
is **skipped** (dropped from the manifest, `hasFeed("open-questions")` false) for a site with no
open threads — the same convention as `leads`/`facts`, so the frontend degrades rather than
shipping an empty list. Across the committed network today: Lima 25 (22 leads + 3 matrix
threads), Findlay 6, Columbus / Hamilton-Middletown / Springfield 1 each; the rest carry none.

Not cataloged — a derived view whose underlying leads are already catalog atoms
(`catalog_index.py`), so it mints no new handles and `catalog_version` is unchanged (mirrors the
`facts` decision).

## 4. Deferred

- **Frontend surface.** This lands the data tier; a reader-facing open-questions board (and any
  `get_open_questions` MCP tool) is a follow-on — the feed is the contract those build on.
- **Non-tagged `[open]` prose.** Only the two structured stores are aggregated; `[open]` tags
  embedded in free-text record prose are out of scope (they carry no stable id or provenance
  anchor to project).
