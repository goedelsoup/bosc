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

These are checked-in build artifacts — regenerate, don't hand-edit. To refresh one site:

```
watermark --site <slug> export --no-embeddings --out web/sites/<slug>
rm -rf web/sites/<slug>/schemas   # the contract schemas live once at data/site/bundle/schemas/
# Drop the heavy retrieval-index feeds — the lean committed bundle omits them (see below):
python - "$slug" <<'PY'
import json, sys, pathlib
d = pathlib.Path("web/sites") / sys.argv[1]
for f in ("passages", "passage-embeddings"):
    (d / "feeds" / f"{f}.ndjson").unlink(missing_ok=True)
m = json.loads((d / "manifest.json").read_text())
m["feeds"] = [x for x in m["feeds"] if x["name"] not in ("passages", "passage-embeddings")]
m["feed_count"], m["row_total"] = len(m["feeds"]), sum(x["count"] for x in m["feeds"])
(d / "manifest.json").write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
PY
```

Notes on what's committed here vs. a raw export:

- **No `schemas/`** — the site-agnostic JSON Schemas + `manifest.schema.json` are the shared
  contract and live once at `data/site/bundle/schemas/`; duplicating them per site (×23) is
  pure bloat and the frontend never reads them at build time.
- **`ask-embeddings.json` is present but empty** — exported with `--no-embeddings` to keep the
  tree offline and lean (no ~80 MB model download). Hybrid retrieval degrades to BM25-only over
  these committed bundles; the live per-site exports carry the real vectors.
- **No `passages` / `passage-embeddings` feeds** — the page-level retrieval indexes (#1589) are
  large (Lima's `passages.ndjson` is ~3.7 MB, LFS-resolved-PDF dependent) and every committed
  bundle omits them. A raw export always emits both, so the regen step above drops the files
  **and** their manifest entries; the frontend degrades to declaring-absent (`hasFeed` → `[]`),
  and if the manifest declared them without the files the static build would `ENOENT`.

## Drift guard

`tests/test_site_bundle.py` asserts the committed lima/fort-wayne/urbana bundles still track
their `watermark … export` contract (matching `contract_version` + `site`, every committed feed
still produced by the exporter, internally consistent counts). Refresh the affected site(s) on
drift.
