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
- **No `passages` / `passage-embeddings` feeds — except van-wert.** The page-level retrieval
  indexes (#1589) are large (Lima's `passages.ndjson` is ~3.7 MB, LFS-resolved-PDF dependent), so
  a raw export always emits both and the regen step above drops the files **and** their manifest
  entries; the frontend degrades to declaring-absent (`hasFeed` → `[]`), and if the manifest
  declared them without the files the static build would `ENOENT`.

  **`van-wert` is a deliberate exception** (#1963 / #1966) and ships its 243-row `passages.ndjson`
  committed. **Do not run the drop step on it** — a blanket regen loop that applies the snippet to
  every slug silently deletes committed retrieval evidence, which is how it bit #1969. Its
  `passage-embeddings.ndjson` is committed too but empty (the `--no-embeddings` artifact), so the
  manifest declares a 0-count feed against a 0-byte file, which is valid and must stay declared.

## Drift guard

`tests/test_site_bundle.py` guards these in two layers. Refresh the affected site(s) on drift.

- **Against a fresh export** — the committed lima / fort-wayne / urbana / wpafb bundles must
  still track their `watermark … export` (matching `contract_version` + `site`, every committed
  feed still produced by the exporter, an equal `readiness` block, internally consistent counts).
  Only these four are re-exported by the suite; a full-fleet export would be too slow to run per
  commit.
- **Against itself, for every committed bundle** — `readiness` is a *standing* property
  recomputed at every export, so a snapshot can over- or under-read its own evidence. Since
  `watermark.site.readiness.compute_readiness` is a pure function of `(profile, feed counts)` and
  a manifest carries both, every bundle here is checked for self-consistency with no export at
  all (#1770 — Urbana had shipped `record: live` over a zero-length `records` feed).
