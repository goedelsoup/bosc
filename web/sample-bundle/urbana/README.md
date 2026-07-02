# `sample-bundle/urbana/` — Urbana offline fixture

A **minimal, trimmed snapshot** of the real Urbana content bundle
(`watermark --site urbana export` → `data/site/bundles/urbana/`), committed so
`npm run build` and offline UI work need zero Python or Git-LFS. It's a sibling of
`../lima/` and `../fort-wayne/`, keyed by registry slug like every other site
(`bundleFor("urbana")` in `src/lib/bundle.ts`).

Production regenerates the real bundle (`watermark export` in `.github/workflows/pages.yml`),
so this fixture is the **offline/CI stand-in only** — a few authentic rows per feed (real
shapes, not mocks). Schemas are **not** duplicated here (the manifest keeps its schema refs;
the canonical `schemas/*.schema.json` live under `data/site/bundle/`).

## An early, thin peer — Champaign County, OH

Urbana is a **queued** watershed point (Champaign County OH, FIPS 39021), sitting on the
**Mad River** in the Great Miami basin — the Wright-Patterson / Mad River corridor expansion
(#441/#797). It is registered but **not `selectable`**, so its `/network/urbana` page is the
readiness-degraded case (`web/src/lib/readiness.ts`): only the verified geography/gages are
set, and most sections lock. This fixture is the proof of that — every feed is **only
Urbana's** own record, and the platform doesn't fabricate to fill the gaps:

- `records`, `timeline`, `people`, `places`, `meetings`, `documents`, `exhibits`,
  `hydrology-scenarios`, `hypothesis-assessments`, `ask-embeddings` are **0 rows** — Urbana
  has no committed dated civic record, curated people/places/exhibits, per-site scenarios,
  assessed hypothesis cells, or an embedded ask index yet. On-thesis opacity, not a trim artifact.
- What *is* populated is the reconnaissance layer: `entities`/`relationships` (the corridor's
  own small graph, no Allen-County nodes), `defense-contractors`, `hypotheses` (open leads,
  not yet assessed), `leads` (the needs/leads board), `economics-baseline`, and `rsei` (Champaign
  County OH, FIPS 39021 — **not** Lima's or Fort Wayne's).
- `catalog` carries Urbana's `slug-scoped` datasets plus genuinely `basin-shared` ones, never
  Lima's `lima-legacy` rows. Urbana ships **no `geo`** feed — it has no committed campus assemblage.

`concepts` (the wiki glossary) and `network` (the basin synthesis) are network-global by
design and legitimately mention other sites — they are the same in every site's bundle.

## Refresh this fixture

After a contract change or new Urbana data (run from the repo root):

```sh
watermark --site urbana export --out /tmp/urbana-bundle
# then re-trim /tmp/urbana-bundle into this directory — a handful of rows per feed, dropping the
# generated schemas/ dir (catalog → ~a few dozen rows, rsei.facilities → ~4, hypotheses → ~3).
```

The drift guard `tests/test_site_bundle.py::test_urbana_sample_bundle_tracks_the_export_contract`
fails if this drifts from `watermark --site urbana export`, and
`test_default_scoped_sibling_bundle_carries_no_lima_corpus` asserts none of Lima's corpus leaks in.
