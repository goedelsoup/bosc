# `data/hypotheses/` — the (site × hypothesis) evidence store

This is the committed, reviewed assessment store for the boom-origin **hypotheses**.
It is the backend peer of the frontend directory: the same
cells the `/directory` page renders, now carried as data with provenance.

- Layout: `data/hypotheses/<hypothesis-id>/<site-slug>.yaml`, one **evidence cell** per
  `(site × hypothesis)`. Schema: `watermark.hypotheses.HypothesisAssessment`.
- Hypotheses are registered in `watermark.hypotheses.HYPOTHESES` (ported from
  `web/src/lib/directory.ts`). The three IDs are `water` (H1), `defense` (H2),
  `surveillance` (H3).
- Each cell carries a `signal` (anchor/strong/moderate/watch), an evidentiary `tag`
  (`verified` / `inference` / `open`), the hypothesis's `group` + `fields`, and ≥1
  `citation` (required for any non-`open` cell — the upgrade over the old hardcoded TS).
- **`signal` ≠ `tag`.** `signal` is how loud the nexus is; `tag` is whether the cell's
  facts are documented or inferred. A federal nexus is a *signal*, not a verdict.
- **`sub_thesis`** (optional) classifies what *kind of claim* the cell is making — the
  investigative frame, orthogonal to signal and tag. Vocabulary (#905):

  | value | what it captures |
  |-------|-----------------|
  | `coercion` | A regulatory/structural mechanism that compels locality acceptance |
  | `end-use` | What the compute is actually for (application class) |
  | `capture` | Economic/political capture: subsidies, CRA/PILOT, abatements |
  | `opacity` | Concealment: shell LLCs, redacted records, beneficial-ownership gaps |
  | `nexus` | The specific institutional/regulatory framework enabling the site |

  Rendered as a `· [tag]` suffix on the primary field in the directory scorecard.
- These are partly **our own inferences** (tagged as such), so this is a new tree — not
  `data/reference/` (authoritative outside data only).
- A cell is hand-authored here, or **promoted** from a research run
  (`watermark research run --recipe hypothesis-assessment --hypothesis <id>`, which proposes
  candidates under `data/research/<run>/assessments/` for review — onboard-style: it
  proposes, it never promotes).
- Lint before committing: `watermark hypotheses check`.

`water/` (H1) carries no cells: the reference hypothesis is rendered from the site registry +
basin network (by drainage), not from per-site assessment cells.
