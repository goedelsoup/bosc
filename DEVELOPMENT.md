# Development

## Toolchain

Managed by [mise](https://mise.jdx.dev/) (Python 3.11, uv, node 24, git-lfs).
`brew bundle` is the fallback (`Brewfile` lists the same tools).

```bash
mise install          # provision pinned tools
mise run setup        # uv sync --extra dev + git lfs install
cp .env.example .env  # set ANTHROPIC_API_KEY (+ WATERMARK_SITE if needed)
```

The repo is a **mise monorepo**: the backend (repo root) and `web/` each
have their own task set. A bare task name runs the project you are standing in;
`//web:<task>` targets the web project from anywhere.

## Task reference

### Backend

```bash
mise run check    # gate: ruff + format-check + markdown + mypy strict + pytest
mise run test     # pytest only
mise run lint     # ruff check
mise run types    # mypy
mise run fmt      # ruff format (auto-fix)
mise run export   # run watermark export → data/site/bundle/
mise run dev -- … # run the watermark CLI
```

### Frontend (Astro)

```bash
mise run //web:check      # gate: Biome + astro check + vitest + build + links
mise run //web:dev        # astro dev server  → http://localhost:4321
mise run //web:test       # vitest only
mise run //web:lint       # biome ci
mise run //web:fmt        # biome format (auto-fix)
mise run //web:build      # static build  → web/dist/
mise run //web:dev:stack  # wrangler + mocked externals (Pages Functions)
```

### Whole-repo

```bash
mise run ci           # runs both check gates
mise tasks --all      # list every task
```

### Data tasks

```bash
mise run oepa-permit <permit_id> <site>   # fetch → ingest → extract → catalog sync
```

After adding or editing an extraction, sync the data catalog (see
[CONTRIBUTING.md → Adding extractions](CONTRIBUTING.md#adding-extractions)):

```bash
watermark catalog reconcile      # refresh _observed.yaml
watermark catalog audit --apply  # apply inferred fields
watermark catalog check          # gate — must pass before committing
```

## CI

`.github/workflows/ci.yml` uses a `changes` job to gate the two halves:

- **Python `check` job** (ruff/format/mypy/pytest) — runs when `src/`, `tests/`,
  `data/`, `pyproject.toml`, `uv.lock`, or `mise.toml` changed.
- **Astro `web` job** — runs when `web/` changed.
- Either `mise.toml` or `ci.yml` edit triggers both.

`check` is the one **required** status check on `main`. Filtering is at the job
level (skipped job = success), not the workflow trigger level (path-filtered
workflow = stuck pending). Don't add a top-level `paths:` to `ci.yml`.

Markdown is a **separate required CI check**: any PR that adds or edits `.md`
files runs `pnpm exec markdownlint-cli2`. Config in `.markdownlint-cli2.yaml`;
generated docs are excluded. Run it locally before pushing.

## Settings

Never read `os.environ` directly — use `watermark.config.get_settings()`.
Settings are `WATERMARK_`-prefixed. Key ones:

| Env var | Default | What |
|---|---|---|
| `WATERMARK_SITE` | `lima` | Active site slug |
| `ANTHROPIC_API_KEY` | — | Required for agent/extract |
| `WATERMARK_MODEL` | `claude-opus-4-8` | Research agent model |
| `WATERMARK_EXTRACT_MODEL` | `claude-sonnet-4-6` | Bulk extraction model |
| `WATERMARK_DATA_DIR` | `data/` | Root data directory |

The `--site` flag on the root CLI writes `WATERMARK_SITE` to the env before the
first `get_settings()` call — that is the one sanctioned `os.environ` write.

## Testing

Tests are hermetic — no network. Hydrology/connector tests use the `hydro_settings`
fixture (`conftest.py`, `hydro_offline=True`, `hydro_fixtures_dir` →
`tests/fixtures/hydrology/`). A new connector needs a committed fixture; an
offline cache miss raises `HydroOfflineError` naming the key to record.

`test_extracted_yaml_valid.py` validates every committed extraction against
`watermark.models`. Adding extractions means keeping them schema-valid.

Tests run against committed `data/extracted/` (the reviewed artifact), not raw
`data/documents/`. If a live connector run populates `data/cache/` before a test
run it can pollute offline tests; remove `data/cache/{hydrology,economics}` if
tests fail spuriously after a live pull.

## Modules

```
src/watermark/
  cli/            Typer CLI — root app + one module per subcommand group
  config.py       Settings (WATERMARK_* env) and data-dir helpers
  models.py       Pydantic models for all extracted data shapes
  profiles.py     Per-contractor document-format profiles (OPC, NPDES, …)
  sites/          SiteProfile registry + per-site path helpers
  agent/          Claude Agent SDK wrapper (research agent + in-process tools)
  pipeline/       ingest / extract / analyze + cross-document assembly
  hydrology/      Water-balance + stormwater models; USGS/NOAA/EPA connectors
  oepa/           Ohio EPA DAM discovery and permit fetch
  gis/            Parcel/zoning GIS connectors (ArcGIS REST, OGRIP)
  grid/           EIA-861, PJM LMP/interchange, federal generation
  economics/      EIA utility baseline, RSEI toxics, USASpending
  site/           Data-tier export (watermark export → content bundle)
  research/       Agent recipe runner and finding publisher
  catalog*.py     Data catalog registry and CI check
```

## Adding a site

1. `watermark sites new <slug>` — prints a paste-ready `SiteProfile` stub.
2. Fill every field from a cited source; `watermark onboard <slug> --check`
   flags unfilled placeholders.
3. Register in `web/packages/core/src/sites.ts` with `status: "open"`,
   `selectable: false`.
4. `watermark onboard <slug>` — scaffolds per-site data dirs, runs portable
   reach connectors, prints the blocking review checklist.
5. Promotion to `selectable: true` is a manual, parity-gated edit after the
   checklist clears.

See [docs/onboarding.md](docs/onboarding.md) for the full runbook.

## Frontend

The frontend is a self-contained Node project. It builds offline against
`web/sample-bundle/` (no Python, no LFS, no API keys). See
[web/README.md](web/README.md) for the Pages Functions (submit/ask/doc)
local testing approach, the wrangler dev stack, and the Cloudflare deployment.
