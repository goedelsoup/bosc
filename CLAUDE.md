# CLAUDE.md — guidance for agents working in this repo

Project BOSC is an **agentic research platform** that deconstructs public-records
source documents (degraded scans, OCR PDFs) into reviewed structured data and
runs Claude-driven analysis over it. Spun out from Periplus.

## Architecture

Three-stage pipeline under `src/watermark/pipeline/`: **ingest → extract → analyze**.
The `src/watermark/agent/` layer wraps the Claude Agent SDK and exposes in-process
tools so the agent inspects real data. Entry point is the `watermark` Typer CLI
(the `src/watermark/cli/` package). **`watermark` is the only installed command**
(`[project.scripts]`); docs invoke `watermark <cmd>`. `BOSC`/`bosc` is the project
codename and survives only as vocabulary — the platform name, the `/bosc` Lima
site re-root, the `bosc` GitHub repo, and `bosc-`-prefixed Lima filenames — never
as an executable.

A second subsystem, `src/watermark/hydrology/`, runs water-balance / stormwater models
of the Lima municipal loop. `src/watermark/hydrology/connectors/` pulls **live public
data** (USGS NWIS, NOAA Atlas-14, EPA ECHO) through `_cache.cached_get` — on-disk
cache + TTL + offline/committed-fixture fallback, so tests never hit the network.
A new connector is a pure sync `fn(..., settings) -> pydantic` in that dir, with a
committed fixture under `tests/fixtures/hydrology/<connector>/`. External-data
pulls land as committed reference datasets under `data/reference/<source>/` and
are regenerable via a `watermark` subcommand (e.g. `watermark npdes` → the EPA ECHO Maumee
NPDES inventory; columns are selected by ECHO **ObjectName**, never by index).

The **public site** is built in two tiers. The Python data tier (`src/watermark/site/`)
emits a typed **content bundle** — JSON feeds + a manifest with a `CONTRACT_VERSION`,
Pydantic models in `watermark.site.feeds`, written by `watermark export`. The presentation tier lives
in **`web/`**: an Astro + MDX static site that reads that bundle at build time
(Epic #54). It's pure Node (pnpm, no uv/LFS) and builds against the committed
`web/sample-bundle/` fixture offline; deck.gl map/graph visualizations are the
only React islands. **`web/` is a pnpm workspace of focused packages, not one flat
package** (Epic #1549): the Astro app is **`@watermark/site`** (`web/` itself —
pages, layouts, residual components, plugins, config, middleware, content), depending on
**`@watermark/core`** (`web/packages/core` — DOM-free domain logic: feeds, catalog, sites,
nav, readiness, evidence, dilution, storyCompile, …), **`@watermark/charts`**
(`web/packages/charts` — the SVG chart geometry `charts.ts`), **`@watermark/viz`**
(`web/packages/viz` — the deck.gl/MapLibre React island cluster), and **`@watermark/functions`**
(`web/functions` — the Pages Functions; stays physically at the project root so Cloudflare
discovers them). Dependency order `core → {functions, charts, viz} → site`; the `@fn/*`
alias is retired (workspace packages resolve via `node_modules`) and the surviving `~/*`
is **site-internal only** (`web/src/*`). Each package owns its `tsconfig.json`; one
shared-root `web/vitest.config.ts` scopes each package's tests via `projects` (site / core /
charts / viz / functions — the Functions tests live under `web/functions/_test`). The
frontend is structured as **the BOSC network** (Epic #308):
one build hosting a network of watershed-point sites — Lima (the live reference build)
is physically re-rooted under **`/bosc`** so future sites are clean siblings, with
cross-cutting pages (about, wiki, ask, search, the `/network/*` hub) global at the root
and a topbar switcher (`@watermark/core`'s `sites.ts`) between them. Charts are a hand-rolled SVG
library (`@watermark/charts` + `web/src/components/charts/`) — indigo encodes data, the evidence
palette only encodes evidence. The legacy Python SSG was retired at the parity cutover —
the Astro `web/` is now the sole presentation tier. Production is
**Cloudflare Pages** (`.github/workflows/pages.yml` + `web/wrangler.toml`,
where the `web/functions/api/*` Pages Functions — `/api/submit`, `/api/ask` —
also deploy), **not** GitHub Pages: that deploy was never flipped and Cloudflare
supersedes it. See
`web/README.md` for the architecture; **don't edit `docs/**` to fix the new
site's cross-links** — they're rewritten at build time (`@watermark/core`'s `rehype-doc-links.ts`,
base-aware: Lima routes get the `/bosc` prefix, network-global ones don't), keeping the
`docs/**` source canonical. After a base/`LINK_MAP` change, clear
`node_modules/.astro` (Astro caches markdown rehype output there).

The **investigative-method layer** is the methodology the platform's analysis and
prose are held to: `.claude/skills/` carries six abstract, agent-discoverable
skills (evidentiary-discipline is the spine; the rest defer to it), and
`docs/investigative-method/` carries the candidate agent system prompt plus the
`ENRICHMENT.md` that binds those skills to this repo's artifacts (the `[verified]`/
`[inference]`/`[reference]`/`[open]` tag vocabulary, the `EntityGraph`,
`ProvenancedValue`, `docs/legal/`, the corpus audit). The in-app `watermark.agent`
research agent already loads the discipline system prompt + the read-only research
skill subset; **#1563 completed the method-layer → in-app-agent wiring** by serving
the **yidam corpus mirror** (Epic #1560 E1/E3 — the committed corpus projected into
`yidam://corpus/*` nodes by `watermark corpus-mirror`) to it as a second in-process
MCP backend (`watermark.agent.yidam_tools`, BOSC's Python realization of
`yidam serve --mcp`), so the agent can list / read / query those nodes and run
open-questions over the projected graph. The skills are usable by repo-working agents now.

## Conventions

- **Tooling & CI (full task reference + CI rationale: [DEVELOPMENT.md](DEVELOPMENT.md)):**
  mise manages the toolchain (Python 3.11, uv, ruff, mypy `strict`, pytest, node 24;
  `Brewfile` fallback) as a **monorepo** — backend tasks at the repo root, `web/` tasks
  namespaced `//web:*`, and a bare task name runs the project you're standing in.
  **`mise run check` is the gate to run before declaring done** (`mise run //web:check` for
  `web/` changes; `mise run ci` for both). `markdown` (`pnpm exec markdownlint-cli2`) is a
  **separate required CI check** on any `.md` edit — run it locally (common failures
  `MD032` missing-blank-before-list, `MD012` consecutive-blanks; config + excludes in
  `.markdownlint-cli2.yaml`). CI (`.github/workflows/ci.yml`) gates its two halves at the
  **job** level via a `changes` job, **not** a trigger-level `paths:` filter — a skipped
  job reports success and satisfies the required `check`, whereas a path-filtered-away
  workflow leaves it stuck "pending". **Don't add a top-level `paths:` to `ci.yml`.**
- **Python 3.11+**, `from __future__ import annotations` at the top of modules.
- **Config:** never read `os.environ` directly — go through `watermark.config.get_settings()`.
  Settings are `WATERMARK_`-prefixed; the model default is `claude-opus-4-8`, bulk
  extraction uses `claude-sonnet-4-6`.
- **Site axis (the BOSC network):** the platform hosts a network of watershed-point
  sites (Lima today; Fort Wayne/Defiance/… queued — #323/#308). Per-site values are
  **not** baked in: they live on a `SiteProfile` in `watermark.sites` (the Python peer of
  `web/packages/core/src/sites.ts`), selected by `WATERMARK_SITE` (`Settings.site`, default
  `lima`) or the global `watermark --site <slug>` flag. `Settings` fills the per-site config
  knobs (`PROFILE_SETTINGS_FIELDS`: `nwis_sites`, `rsei_fips`, `eia861_utility_number`,
  the GIS URLs, …) from the active profile unless a knob is set explicitly (env/`.env`/
  kwarg still win); deeper hydrology/grid/rsei constants read `watermark.sites.active_profile(settings)`.
  **Add a site by registering a profile in `watermark.sites.SITES`; never re-hardcode a
  Lima/Allen-County value.** Profile `*_relpath`s are relative to `settings.data_dir`,
  and `bosc-`-prefixed reference/extracted filenames are Lima-specific by convention — a
  new site supplies its own paths. (The `--site` callback writes `WATERMARK_SITE` to the env
  before the first `get_settings()`; that's the one sanctioned `os.environ` write.)
  Onboard a registered site with `watermark onboard <slug>` (`watermark.onboard`; runbook
  `docs/onboarding.md`): it scaffolds the per-site data dirs, runs the portable reach
  connectors (per-site point outputs are slug-scoped so Lima is never clobbered; basin-level
  outputs stay shared), and prints a **blocking review checklist** — promotion to
  `live`/`selectable` in `web/packages/core/src/sites.ts` stays a manual, parity-gated edit.
  **Registered ≠ selectable, and a thin peer is still engageable** (#781/#782): a
  non-reference `/network/<site>` page **degrades, doesn't break**. Readiness is **domain
  activation, not Lima-shape-matching** (#1220): a site is defined by the **domains that
  actually have a story there**, not by its deficits against Lima's taxonomy. It is computed
  **in Python at export** (`watermark.site.readiness`) and written into `manifest.json` as a
  `readiness` block — the five domains (**backdrop, facility, places, record, story**), each
  `absent | seeded | live`, plus a derived **tier** (`stub → backdrop → case → reference`). It
  is a **standing property recomputed at every `watermark export`**: it rises when a source
  lands and falls when one dries up — never an onboard-time snapshot. The **floor is always
  pulled** (backdrop = the coordinate/FIPS/state-keyed connectors — economics-baseline,
  consumer-energy, RSEI); **above the floor triggers on evidence, never scaffolds** (facility on
  a disclosed permit + its feed, places on committed campus/footprint geometry, record on
  extracted `records`/`documents`, story on a registered story + leads). The frontend
  (`web/packages/core/src/readiness.ts`) is a **thin reader** of the block: primary sections gate on their
  parent domain, leaf facets add a feed/registry check so an active domain never opens an empty
  page, and it surfaces a needs/leads board for the locked ones. `is_reference_site` survives
  **only** for the **network-global-host role** (routed-hydrograph, the hypothesis matrix, the
  catalog, concepts, the `docs/` long-form) — it is **not** a readiness backdoor: Lima renders
  as available because its manifest says every domain is `live`. Chrome is **two-tier by the
  current path** — site-level tabs when standing on a site (locked tabs render non-navigable),
  network tabs otherwise; a non-`selectable` site gets registry-only locked tabs. So **never
  fake a value to make a partial site look complete** — let it lock and ask for the source.
  Onboarding only needs the verifiable knobs; the page is useful before parity. (Leads are a
  per-site `leads` bundle feed, #796 — Lima's live in `data/site/leads.yaml`, a peer ships its own.)
- **Models:** structured extractions are validated with the Pydantic models in
  `watermark.models`. Scan transcriptions may be **approximate**, written `~12345`
  in YAML; `ApproxInt`/`_coerce_number` handle that — preserve the marker in
  source data, don't silently drop it.
- **CLI options:** a `typer.Option` default trips ruff `B008` when the parameter
  is annotated `Path` (but not for `bool`/`int`/`float`); type the option `str`
  and convert to `Path` in the body.

## Data discipline (important)

- `data/documents/**` is raw, immutable, and **versioned via Git LFS** for large
  binaries (see `.gitattributes`). Add new scan/PDF types to LFS tracking.
  The `history/` sub-tree is for secondary/reference sources (public-domain books,
  surveys) and nests **by site** (`history/allen-oh/`, `history/allen-in/`, …) so
  books for different watershed points don't collide. All claims from `history/`
  sources are tagged `[reference]`, never `[verified]`.
- `data/extracted/**` is the committed, reviewed artifact and what tests run on.
- `data/reference/**` is committed **authoritative data from outside sources**
  (EPA ECHO, USGS/NOAA, parcels). Each folder carries a `README.md` naming its
  source and gaps; raw API responses stay cached under `data/cache/` (git-ignored)
  so the committed CSV/YAML is regenerable.
- When transcribing figures: dollar totals/subtotals are high-confidence; mark
  uncertain quantities `~`. **Never fabricate line items or sources.** Prefer
  omission over invention. Cite source page/file.
- **Chain of custody — the corpus is litigation evidence.** Never alter a source
  byte under `data/documents/**`, and don't rename or "fix" malformed/typo'd
  source filenames in place: keep the as-received name and record the canonical
  name + a **content-verified** date (text layer or OCR, *not* the filename or
  outside knowledge) in a non-destructive alias manifest — see
  `data/extracted/commissioners/minutes/filename-map.yaml`. Removing a source
  file is only OK when it's a checksum-verified byte-identical duplicate — e.g. the
  commissioners' meeting record is now connector-sourced under
  `data/documents/commissioners/meetings/`, the legacy `minutes/raw/` tree retired
  under exactly this rule (`data/extracted/commissioners/meetings/cutover-reconciliation.yaml`).
  Captured
  third-party web evidence may embed secrets/tokens — that's evidence, not a leak
  to redact. The standing completeness audit is
  `data/extracted/legal/corpus-completeness-audit.md`.

## What "extract" must achieve

The reference target is `data/extracted/aedg/roundabouts.*.opc.yaml`: the six Tetra
Tech OPC estimates at 0-based PDF pages **317 (summary), 318-327 (detail)** of
`data/documents/aedg/PRR-01-bundle.ocr.pdf` (printed sheets `pdf_page` 318-328).
The extracted tree **mirrors `data/documents/` by collection** — an artifact lands
under the same first-level collection as its source (`recorder/`, `oepa/`, `aedg/`).

The extract stage is **implemented as a hybrid, profile-driven read**
(`watermark.pipeline.extract`): OCR text layer (pypdf, hint only) + 300 DPI render
(pypdfium2) → resolve a format `Profile` (`watermark.profiles`, auto-detected from the
OCR text or `--profile`) → forced-tool-use vision extraction
(`watermark.agent.extractor.StructuredExtractor`) → Pydantic-validated, contractor-
agnostic `Estimate` (dynamic `sections` + `markups`) with provenance
(`PageExtraction`). The OCR text layer is badly garbled (e.g. `$109,307.69` →
`$108.307.89`); **never trust its digits — figures come from the image.**

**Generality (important):** the extract entrypoint is not tied to one contractor.
`extract_page(doc, i, kind="opc", profile="auto", detail=...)` dispatches by
document kind, and within OPC by `Profile` (Tetra Tech is profile #1; `generic`
is the fallback). The `Estimate` model and `analyze.reconcile_estimate` are
format-agnostic — section taxonomy and markup rate come from the data/profile,
**not hardcoded**. Add a contractor by registering a `Profile`; don't add fixed
section fields. `watermark extract --detail` adds per-section `LineItem`s (rolled up
by `reconcile_estimate`). `Number` (`models._coerce_number_keep`) preserves
int-vs-float for quantities/rates and tolerates the `~` marker. `watermark reconcile`
(legacy `OPCSummary`, 25% convention) still covers the assembled summary artifact.
