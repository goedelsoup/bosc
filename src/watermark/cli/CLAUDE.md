# CLAUDE.md — `watermark.cli`

The Typer command surface. Defers to the root [`CLAUDE.md`](../../../CLAUDE.md)
(its **CLI options** convention lives there).

- **Installed as `watermark`, spoken of as `bosc`.** The `[project.scripts]` entry point is
  `watermark = "watermark.cli:app"` (`pyproject.toml`) — the invocable command is `watermark`.
  `bosc` is the project codename and is used interchangeably throughout docstrings/docs; there
  is no separate `bosc` executable. The parenthetical "`src/watermark/cli.py`" in the root doc
  is now this **package** (`cli/__init__.py`), not a single file.
- **The app is assembled in `_base.py`, split from `__init__.py` on purpose.** `_base.py`
  defines the root `app = typer.Typer(...)`, the global `--site` `@app.callback`, and every
  sub-app (`sites_app`, `catalog_app`, `poi_app`, `imagery_app`, …) wired with `app.add_typer`.
  `__init__.py` then imports each command module so its `@app.command` / `@<sub>_app.command`
  decorators **run at import time and register** — there is no command registry; the decorators
  mutate the shared app instances. `__init__.py` re-exports `app`.
- **One module per command group**, plus root-level modules whose commands attach directly to
  `app` (no sub-app): `pipeline.py` (`version`, `onboard`, `ingest`, `extract`, `export`,
  `network`, …), `gis.py`, `grid.py` (grid + economics + federal-filings verbs), `hydrology.py`,
  `reference.py` (`npdes`, `dmr`, `nasa-power`, `rsei`, …), `retrieval.py` (`index`). Sub-app
  modules: `sites.py`, `catalog.py`, `hypotheses.py`, `research.py`, `objectstore.py`,
  `subdivisions.py`, `imagery.py`, `poi.py`, `leads.py`, `oepa.py`, `sweep.py`. A verb's
  implementation usually lives in the matching `watermark.<domain>` package — the CLI module is
  a **thin wrapper** (parse args → get settings → call the library → render).
- **`--site` is the one sanctioned `os.environ` write.** The `@app.callback` validates the slug
  against `watermark.sites.SITES` and writes `WATERMARK_SITE` to the env **before the first
  `get_settings()`** so the active `SiteProfile` is resolved. Everywhere else, go through
  `get_settings()` — never read `os.environ` directly.
- **Adding a subcommand.** A new root verb: add a `@app.command(name="…")` function to an
  existing root module (already imported, so it registers). A new **group**: create
  `cli/<group>.py`, define `<group>_app = typer.Typer(...)` + `app.add_typer(...)` in `_base.py`,
  add the module to the `__init__.py` import list, and hang `@<group>_app.command(...)` functions
  off it. In the body, get config via `get_settings()` (or the `offline_settings(subsystem)`
  helper); import shared names (`Settings`, `get_settings`, `console`, `wrote`, `SITES`, …) from
  `_base.py`, not their origins.
- **The B008 gotcha (root doc):** a `typer.Option` default on a parameter annotated `Path`
  trips ruff `B008`. Type the option **`str` and convert to `Path` in the body** (`bool`/`int`/
  `float` defaults are fine).
