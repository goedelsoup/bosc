# `sites/` — the committed, per-site content bundles

Each subdirectory is one network site's **content bundle** — the committed input the Astro
build reads offline (CI, zero-Python). Unlike the old `sample-bundle/` fixtures (a hand-trimmed
Lima/Fort Wayne/Urbana subset), this tree holds a **full `watermark export` for every registered
site** in `watermark.sites.SITES`, so the whole BOSC network builds from committed data with no
Python step. The frontend resolves a site's bundle by registry slug (`bundleDir(slug)` in
`src/lib/bundle.ts`), so the directories are keyed the same way:

```
sites/
  lima/                 # the Lima reference site (WATERMARK_SITE default)
    manifest.json
    feeds/**
  fort-wayne/
  van-wert/
  …                     # one dir per slug in watermark.sites.SITES
```

## How the offline build finds these

`mise run //web:check` sets `WATERMARK_BUNDLE_DIR=sites` (and `WATERMARK_SKIP_EXPORT=1`), so
`bundle.ts` resolves `sites/<slug>/` instead of running the Python exporter. It's an explicit
opt-in, not a silent fallback. When a real, freshly generated bundle exists at
`../data/site/bundles/<slug>/` (the Vite plugin's `watermark --site <slug> export` output,
git-ignored), that takes precedence.

## Regenerating

These are checked-in build artifacts — regenerate, don't hand-edit:

```
watermark --site <slug> export --committed    # one site
watermark export --committed --all            # the whole network (~13 min)
```

`--committed` applies the lean trim below and writes into `web/sites/<slug>/`. The export lands
in a temp dir first and the committed tree is replaced only once it has succeeded, so a failed
run leaves the old bundle intact rather than half-overwriting it, and a feed the exporter no
longer produces is retired rather than left behind.

This used to be a hand-run shell + Python snippet, which is how the drop step deleted committed
retrieval evidence twice (#1969, #1993) — see the passages note below.

Notes on what's committed here vs. a raw export:

- **No `schemas/`** — the site-agnostic JSON Schemas + `manifest.schema.json` are the shared
  contract and live once at `data/site/bundle/schemas/`; duplicating them per site (×23) is
  pure bloat and the frontend never reads them at build time.
- **`ask-embeddings.json` is present but empty** — exported with `--no-embeddings` to keep the
  tree offline and lean (no ~80 MB model download). Hybrid retrieval degrades to BM25-only over
  these committed bundles; the live per-site exports carry the real vectors.
- **No `passages` / `passage-embeddings` feeds, unless a site commits them.** The page-level
  retrieval indexes (#1589) are large (Lima's `passages.ndjson` is ~3.7 MB, LFS-resolved-PDF
  dependent), so a raw export always emits both and the trim drops the files **and** their manifest
  entries; the frontend degrades to declaring-absent (`hasFeed` → `[]`), and if the manifest
  declared them without the files the static build would `ENOENT`.

  **Which sites keep them is derived, not listed.** `--committed` retains the retrieval feeds iff
  the site's own committed manifest already declares them, so the tree describes itself and there
  is no list to go stale. That matters: this README used to name the exception set in prose,
  noted that it "went stale within one issue of being written", and a blanket regen loop applying
  the old drop step to every slug silently deleted committed retrieval evidence — #1969, then
  #1993 again. To opt a site in for the first time, pass `--with-passages` once.

  Their `passage-embeddings.ndjson` are committed too but empty (the `--no-embeddings` artifact),
  so the manifest declares a 0-count feed against a 0-byte file, which is valid and must stay
  declared. To see the current set: `git ls-files 'sites/*/feeds/passages.ndjson' | cut -d/ -f2`.

## Drift guard

A committed bundle is a build artifact of the corpus that nothing recomputes, so it goes stale
silently — three times inside epic #1265 alone, each found mid-PR while doing something else
(#2025). Three layers, at different costs:

- **`watermark export --check [--all]`** — re-exports to a temp dir and compares the committed
  tree **byte for byte** (plus the manifest's own claims, ignoring `generated_at`). This is the
  only layer that sees a corrected figure *inside* a row: when it first ran, 23 of 26 bundles were
  publishing a stale size and sha256 for a shared dataset with every row count still equal. Too
  slow for a per-commit gate (~13 min for the fleet); run it before a release or on a schedule.
- **Against a fresh export, in the suite** (`tests/test_site_bundle.py`) — for the sites the
  suite already exports: matching `contract_version` + `site`, every committed feed still produced
  by the exporter, an equal `readiness` block, **equal per-feed row counts**, and internally
  consistent totals. Free (the export has already run) and it catches the severe shape — the
  corpus moving under a bundle. It deliberately stops short of bytes, which would make every
  corpus PR re-export the whole guarded set.
- **Against itself, for every committed bundle** — `readiness` is a *standing* property
  recomputed at every export, so a snapshot can over- or under-read its own evidence. Since
  `watermark.site.readiness.compute_readiness` is a pure function of `(profile, feed counts)` and
  a manifest carries both, every bundle here is checked for self-consistency with no export at
  all (#1770 — Urbana had shipped `record: live` over a zero-length `records` feed).
