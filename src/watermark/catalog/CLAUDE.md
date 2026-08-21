# CLAUDE.md — `watermark.catalog`

A metadata-driven registry over the committed data trees: what datasets exist, how each
is (re)produced, and whether what's on disk matches what's declared. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md) (its **Data discipline** section is the ground truth this
subsystem audits). Driven by `watermark catalog …` (`cli/catalog.py`).

- **Declared vs. observed is the spine.** *Declared* = one `CatalogEntry` YAML per dataset at
  `data/catalog/<scope>/<id>.yaml` (`__init__.py`); the loader hard-fails if the file's
  `scope`-dir and `id`-stem don't match the entry. *Observed* = `data/catalog/_observed.yaml`,
  the reconcile snapshot: per-entry existence, sha256, file count, LFS-materialization, `asof`,
  and staleness-vs-TTL. Every other command is a function of these two — nothing here fetches
  from the network.
- **A `slug-scoped` dataset is observed TWICE, and only one of them is a site's fact** (#2066).
  Its storage carries a `{site}` template, so it is a *different file per site*. The entry-level
  record is the **network-wide aggregate** over every site's copy — summed bytes, a hash of the
  whole set — and `check`/`diff`/`audit` read that. The per-site records live under
  `entries.<id>.sites.<slug>`, and **that** is what `watermark export` publishes into a site's
  `catalog.json`. A slug with no copy is ABSENT from the map and renders as `exists: false`.
  Publishing the aggregate instead is what made `parcel-assemblage` claim 531,148 bytes and 11
  files in mansfield's bundle for a 29,769-byte file, and `exists: true` in three bundles whose
  sites hold no such file at all — and, because the aggregate moves whenever *any* site's copy
  does, it kept `export --check --all` reporting 26 of 26 bundles drifted **on a clean tree**.
- **`resolve.py` is the one per-site rule**, shared by `reconcile` and `sites` so a site's
  observation and its presence answer the same question the same way. Two parts: what belongs to
  a site (the `{site}` expansions, plus — for the reference build alone — the un-slugged peers, as
  a **union**, since `hydrology-reaches` gives Lima both), and what counts as present (no declared
  *concrete* member absent, and ≥1 member found). The predicate is deliberately reconcile's own:
  a templated member's per-site absence is expected, never a gap — `rsei-inventory` templates a
  `{site}/enclave.yaml` only the one federal-enclave site can have, and an all-members rule read
  21 sites that hold their own inventory as missing it.
- **An entry declares the dataset's contract.** `id` (kebab slug, unique), `title`, `scope`
  (`documents`/`extracted`/`reference`/`derived`/`bundle`/…), a `producer` (how it regenerates:
  `kind` + a `watermark` `command` + `connector_ref` dotted module path + human `source`), `storage`
  items (relpath under `data_dir`, MIME, LFS flag, optional pinned `sha256`), a `refresh` block
  (cadence + `ttl_days` + `last_refreshed`), `site_scope` ownership (`slug-scoped` / `basin-shared`
  / `lima-legacy`), and `status` (`needs-review` → `reviewed`). Per-site storage relpaths carry a
  `{site}` template that reconcile expands; per-site absence is expected, not missing.
- **The producer graph is process order, not byte lineage (`dag.py`).** `depends_on` lists entry
  ids that must be produced first; `subgraph_order` does a postorder topo-sort (upstream first),
  and `check` hard-fails on unknown deps or cycles. `watermark catalog run <id>` (`runner.py`) plans
  the subgraph, skips fresh nodes (TTL), and executes each entry's `producer.command` as a
  subprocess — virtual nodes (no command) only order the graph.
- **The commands, by what they touch:**
  - `reconcile` (`reconcile.py`) — observe disk → write `_observed.yaml`. Observes only; never gates.
  - `diff` (`diff.py`) — committed `_observed.yaml` snapshot ↔ a fresh live reconcile: what content /
    membership / freshness moved (`added`/`removed`/`changed` per entry) since the last reconcile.
    The `git diff` analogue to reconcile's `git add`. Observes only, never gates, always exits 0 —
    distinct from `check` (declared ↔ disk).
  - `check` (`check.py`) — **the gate**: schema validity, missing/orphan files, staleness,
    checksum drift, render drift, audit drift, DAG integrity. LFS-aware (an unmaterialized pointer
    is not "missing"); staleness warns unless `--strict`.
  - `backfill` (`backfill.py`) — scaffold entries from committed `reference/` + `extracted/` data,
    grouping files into datasets and templating per-site paths. **Idempotent and prose-preserving**:
    it refreshes mechanical fields (`storage`, `producer`) but never overwrites reviewer-curated
    ones (`title`, `license`, `notes`, `depends_on`, `site_scope`); `reviewed` entries are untouched.
  - `render` (`render.py`) — inject a marker-delimited generated block into
    `data/reference/<collection>/README.md`. Additive + prose-preserving; opt-in (first render adds
    the marker), and `check` gates drift after.
  - `audit` (`audit.py`) — regenerate `data/catalog/COMPLETENESS.md` from catalog + the **committed**
    reconcile snapshot (deterministic, LFS-agnostic); `check` gates its drift.
  - `producer-check` (`producer.py`) — fail if a `connector_ref` module changed without its entry
    being touched (bypass with a `[catalog-waiver: …]` commit trailer).
  - `sites.py` — site-aware views (`site_view`, `readiness`) that answer per-site parity questions.
- **Invariants when adding a dataset.** File must sit at `data/catalog/<scope>/<id>.yaml` with
  matching `scope`/`id`; storage relpaths are relative to `settings.data_dir`; per-site outputs use
  `{site}`; a new entry starts `needs-review` and is promoted to `reviewed` by a human filling
  `license`/`access_tier`. Register a producer by its dotted `connector_ref`; don't invent a
  hand-maintained index — run `backfill` then curate. `check` is part of the `mise run check` gate,
  so a stale `COMPLETENESS.md` / `_observed.yaml` / rendered README will fail CI — regenerate them.
