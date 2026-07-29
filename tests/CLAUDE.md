# CLAUDE.md — `tests`

Offline test suite. Defers to the root [`CLAUDE.md`](../CLAUDE.md).

- **Tests are hermetic — no network.** Hydrology/connector tests use the
  `hydro_settings` fixture in `conftest.py` (`hydro_offline=True`,
  `hydro_fixtures_dir` → [`tests/fixtures/hydrology/`](fixtures/README.md)). Inject
  that `Settings` rather than fighting `get_settings()`'s `lru_cache`.
- Tests run against **committed `data/extracted/**`** (the reviewed artifact) and
  committed fixtures — not against raw `data/documents/**` and not the live API.
- A new connector code path needs a committed fixture; an offline cache miss raises
  `HydroOfflineError` naming the key to record. Keep fixtures minimal; don't
  hand-edit recorded JSON.
- `test_extracted_yaml_valid.py` validates every committed extraction against
  `watermark.models` — adding extractions to the corpus means they must stay schema-valid.
- **Never call `export_bundle()` in a test.** A full export is the suite's most expensive
  operation (~14 s for Lima) and the suite once paid for 26 of them (#1773). Read the
  session-wide, cross-xdist-worker exports in `conftest.py` instead: `lima_bundle` (the
  reference build), `site_bundle("<slug>")` for a peer, `exported_bundle("<slug>")` when
  you need the `BundleResult` summary too. They always pass `skip_embeddings=True` — both
  embedding feeds are still emitted (empty), so the feed and schema sets are unchanged.
  Export directly *only* when the test needs a bundle the shared one can't be (a
  monkeypatched exporter, a deliberately degenerate feed) — and say so in the docstring.
- Run via `mise run check` (ruff + mypy strict + pytest) before declaring done.
