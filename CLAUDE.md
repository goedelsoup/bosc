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
NPDES inventory; columns are selected by ECHO **ObjectName**, never by index). A regenerated
dataset is **never** hand-edited — the next pull reverts it. A reviewed, document-cited
correction goes in a committed **overlay** the connector merges on every pull
(`echo_curation.py` / `data/reference/echo/curation/`, #1698), and a correction that stops
reconciling against upstream **refuses the write** instead of overriding it silently.

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
open-questions over the projected graph. **#1564 (E4)** added a LanceDB **vector index**
over the mirror (`watermark.site.yidam_index`, `.yidam/index/` — `watermark corpus-mirror
--index`, lazily rebuilt by the MCP server) powering a `semantic_search` tool; it reuses the
**same** all-MiniLM-L6-v2 backend as the `/ask` embeddings (`watermark.retrieval.get_provider`),
so it is *reconciled* with them, not a competing index (the `/ask` feed stays canonical for
`/api/ask`). The skills are usable by repo-working agents now.

**The yidam split — projection is ours, reports are upstream's.** BOSC is a *non-vendoring*
derived repo: no `yidam/` · `sadhana/` · `samudaya/` overlay, no vendored prelude. It owns the
**projection** (`watermark.site.corpus_mirror` — sites, leads, hypotheses, the claim vocabulary;
pure Python, so `watermark export` still runs offline with no Rust). It does **not** own the four
corpus **reports** over that mirror (`graph-check` · `lint` · `corpus-index` · `open-questions`) —
those come from the real `yidam` binary via `watermark.site.yidam_cli`, which parses
`--format json` (the RFC-0016 Phase 0 envelope: `format_version`, a `yidam` build block, and a
per-violation `in_baseline` flag). **Never re-implement a yidam report in Python.** BOSC did,
for the sound reason that the binary once required the whole native ML stack; RFC-0003's default
build retired that (no protoc, no lancedb, ~1 min to compile) and the replica was deleted
because it had silently drifted: over the same mirror the replica reported 20 open
questions where the binary saw 2, and nothing could detect the gap.

- **Install:** `mise run yidam-build` — clones the pinned commit and installs to **`.yidam/bin/`**,
  upstream's convention (its own `mise.yidam.toml` and the VS Code extension both resolve that
  path as "this repository's own build"), never the shared `~/.cargo/bin`, which any other yidam
  checkout silently overwrites. mise puts it on `PATH`. Rust is scoped to that task, not a
  repo-wide `[tools]` entry. The build is the **default feature set** plus `.yidam.toml`'s
  `[build] features` — *not* `--no-default-features --features reports`, which upstream now
  names as a mistake (`reports` gates nothing, and the flag drops `tonpa`, `vault-s3` and
  `export-graph`).
- **Run:** `mise run yidam-reports`. Locally the binary is *optional* — `watermark corpus-mirror`
  projects and says so when it cannot report. CI installs it and **gates** (the `corpus` job).
- **The pin is `.yidam.toml`**, on upstream's schema (`origin`/`commit`/`template`/`committed`;
  the old `cli`/`cli_ref` names are dead and fail `yidam-build`), currently **`cli/v0.8.0`**.
  `mise run yidam-vendor-status` reports drift — a report, never a gate.
- ⚠️ **`[build] features` is the one part of that file BOSC writes, and it is load-bearing.**
  It declares what this repo's gates need beyond the released default set — today
  `export-graph`, which makes `export --format rdf` available. Its absence is **silent**: the
  RDF half of the #2053 conformance check *skips* on a binary that cannot answer, so a build
  without the feature does not fail, it stops checking. Through `cli/v0.7.0` the released
  binary carried no `export-graph`, so adopting upstream's download channel would have deleted
  half that gate unnoticed; reported from here and fixed in v0.8.0 (goedelsoup/yidam#532), which
  put it in `default` **and** added this table. It is redundant at the current pin and written
  anyway — it costs nothing until it would cost a capability. Both `mise run yidam-build` and
  the CI `corpus` job read it, so the feature set is stated in exactly one place.
- **`lint` gates against `.yidam/lint-baseline.yml`**, the one committed file under `.yidam/`
  (the rest is regenerable and ignored). It enumerates accepted inherited debt so only a
  *regression* fails; `orphan-in` is `info` upstream and never gates. Re-bless deliberately
  (`yidam lint --bless`) and review the diff, like an extraction.
- **The corpus bytes live in a yidam artifact vault** (epic #2141, RFC-0023): one content-addressed
  store, `.yidam/config.toml`'s lone `[vault.default]`, holding 3,662 files at 3,186 distinct
  addresses. The load-bearing equivalence is that **a Git-LFS oid IS the sha256 of the content**,
  so `data/*/*/vault.yaml` (`watermark documents manifest`) is derivable without materializing
  3.5 GiB — which is what lets the record be written and checked on an `lfs: false` checkout.
  `watermark documents hydrate` restores bytes into the working tree.
  ⚠️ **BOSC declines `yidam vault materialize`, and this is the one upstream capability it
  refuses.** That command writes `.yidam/vault/<entry-slug>/<slug>-<hash8>.<ext-from-media_type>`,
  which is right for its question — give a person a real file to open — and wrong here, where the
  **filename is evidence**: three sources carry no extension and several carry upper-case ones
  because a received name is never "fixed". Measured on `cli/v0.8.0`, `1-12-26 minutes.docx`
  materialized as `multi-527ba1ba.bin`. So `hydrate` places files under their as-received names,
  and **refuses to overwrite anything that disagrees with the record** — a tool that settled a
  divergence by writing over it would destroy the evidence there was one.
  ⚠️ **`VAULTED_SUFFIXES` is the definition of what belongs in the vault, and `.gitattributes` is
  its second copy only until #2147 deletes those lines.** A test proves the two agree while git can
  still answer. `check` reads the filesystem *and* Git-LFS for the same reason: an LFS-only
  inventory does not degrade at the untrack, it **inverts** — `tracked - recorded` goes empty and
  the gate reports a clean corpus because nobody was asked.
- **The graph exports (`graph_exports.py`) are the one surviving renderer replica**, and they
  stay: `web/sites/<slug>/exports/` is committed, so sourcing them from the binary would put Rust
  back in the export path. Their fidelity is enforced instead — CI runs the real binary over the
  same mirror and compares structurally (#2053). **Never "fix" a divergence by changing the
  expectation**; the renderers must agree, or the difference must be a deliberate, recorded
  decision. Re-measured at the `cli/v0.8.0` re-pin: RDF subject IRIs, the `yidam:` predicate
  vocabulary, and GraphML nodes / edges / key schema are all identical to the previous pin's.
- **The MCP surface implements the frozen tool contract** (RFC-0005) at **0.12.0**, vendored as
  `src/watermark/agent/mcp_contract.json` and re-vendored with `mise run yidam-contract-sync`
  (which also vendors `commit_vocabulary.json`, the closed commit list `check_subject` serves);
  CI proves both copies match the pin. Tool names, descriptions and schemas come **from that
  file** — never hand-written, and the served list is **derived** from it, so a tool added
  upstream is an `ImportError` rather than a tool that quietly does not exist. BOSC serves 12 of
  13 and declines only `dependencies` (it pins no tonpa dependency). See
  `src/watermark/agent/CLAUDE.md`.
- **The mirror's classes declare a contract** (#2132): each `<class>.ont.yml` names the
  properties its instances carry and the relationships it licenses, `edge_policy: exhaustive`,
  with the genuinely optional properties in `.yidam/corpus/universal.yml`. Declared as data in
  `corpus_mirror.ONTOLOGY` and rendered from there, so the MCP tools read the same object the
  binary reads a rendering of. **An instance's provenance nests under `properties:`** — yidam
  reads properties from that mapping and nowhere else, and the bare top-level keys this
  projection wrote until #2132 were invisible to the whole ontology layer. Four
  `missing-property` warnings are deliberate and documented in the declaration; every other
  ontology check reports zero, and now that means something.
  ⚠️ **Declare every relationship the projection CAN author, not just the ones it did.** Two of
  them (`concept -in-corpus->`, `relation -in-site->`) are fallback links no instance writes
  against today's corpus, so a vocabulary read off the emitted mirror looks complete and is not
  — and under `exhaustive` the first isolated glossary term or unresolved entity key is an
  **ERROR**, not a warning. Such an edge is marked `fallback=True` (a fact about the projection,
  never rendered into the YAML), which is what keeps "declared for a path not yet taken" apart
  from "the ontology reached past its corpus". `test_every_relationship_the_projection_can_author_is_licensed`
  reads the relationship literals out of the **source** for exactly this reason.
- **The mirror carries a catalog, and a record class (#2134).** `.yidam/catalog/` is projected
  from BOSC's own `data/catalog/**` (199 reviewed `CatalogEntry` records) by
  `watermark.site.corpus_catalog`; `.yidam/corpus/record/` is one node per committed extraction
  in the site's scope (`watermark.site.corpus_records`). Together they make **`verified-unsourced`
  answerable**: a node cites a source by linking to `../../catalog/<slug>.md`, and a `[verified]`
  claim with no such link is a standing the corpus cannot demonstrate. Before this the mirror
  held **zero** `[verified]` claims while `data/extracted/**` held 2,145, so the check returned
  early at zero — the same false green #2132 was filed to end.
  ⚠️ **`rests-on` is deliberately undeclared in every `<class>.ont.yml`.** yidam's
  `unlicensed-edge` / `edge-target-class` walk `instance_links`, which pairs a link with the
  *node* it resolves to; a catalog entry is a **file**, so citations are invisible to the class
  contract and fully visible to `linked_paths` (what the evidence checks read). That split is
  what lets an `exhaustive` edge policy coexist with citing sources. Declaring it would need a
  `target:` class, and an empty target licenses every class for every edge.
  ⚠️ **A record carries its claim profile, not its prose** — `claim_standings` (one bracketed
  token per standing, so yidam counts the record once) plus `claim_counts` (the true totals).
  Excerpting the assertion a tag belongs to is an editorial act with no mechanical answer, and
  the flattering direction is exactly what the check exists to catch. `README.md` /
  `ONBOARDING.md` / `COMPLETENESS.md` are **not records**: they carry tag legends, which would
  manufacture six ungrounded `[verified]` claims out of prose about filing.
- ⚠️ **The five baselined `broken-prose-link` findings are LINK_MAP pages — do not "fix" them.**
  `entities.md`, `candidates.md`, `gis-map.md` and `economics-baseline.md` (×2) are legacy
  generated pages that no longer exist as files; `@watermark/core`'s `rehype-doc-links.ts`
  rewrites them to their new-IA routes at build time, matching by basename so a wrong-depth
  `../economics-baseline.md` resolves too. They are dead only as raw files, which is the
  documented cost of keeping the `docs/**` source canonical. Repointing them at real files
  would break the rewrite and lose the route. Everything else that check found was genuine rot
  and is fixed.
- **`broken-prose-link` walks `docs/**`, not just the corpus.** Its baselined findings include
  15 in `docs/reference/periplus/` — a **frozen, unmodified import**, which must not be edited
  to satisfy a linter.

## Conventions

- **Tooling & CI (full task reference + CI rationale: [DEVELOPMENT.md](DEVELOPMENT.md)):**
  mise manages the toolchain (Python 3.11, uv, ruff, mypy `strict`, pytest, node 24;
  `Brewfile` fallback) as a **monorepo** — backend tasks at the repo root, `web/` tasks
  namespaced `//web:*`, and a bare task name runs the project you're standing in.
  **`mise run check` is the gate to run before declaring done** (`mise run //web:check` for
  `web/` changes; `mise run ci` for both). `markdown` (`pnpm exec markdownlint-cli2`) is a
  **separate required CI check** on any `.md` edit — run it locally (common failures
  `MD032` missing-blank-before-list, `MD012` consecutive-blanks; config + excludes in
  `.markdownlint-cli2.yaml`). That root config **ignores `web/**`** — the Astro tree has its
  own config + task (`web/.markdownlint-cli2.yaml`, `mise run //web:markdown`, also folded
  into `//web:check` and the CI `markdown` job), so a `web/**/*.md` edit is linted there, not
  by the root run. Same rules; `.mdx` is linted by neither (Biome + `astro check` own it).
  CI (`.github/workflows/ci.yml`) gates its two halves at the
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
  **A site's facility is not always a data center** (#1664): `SiteFacility.kind` also admits a
  `federal_installation` (WPAFB), which carries a `FederalInstallation` block and has the
  IT-load / genset / cooling dimensions **forbidden at the type level** so a base can't be sized
  as a campus. Anything that models a campus reads the narrower `SiteProfile.campus`, not
  `.facility`. Its land comes from the DoD **MIRTA** register (`watermark.connectors.federal`)
  because a federal enclave is off the county tax rolls and will never appear in a CAMA parcel
  layer, and its toxics row is reduced against **its own reporting county**, which for a
  straddling base is not the site's `rsei_fips` — `watermark enclave` writes the committed set,
  `watermark.enclave` assembles it, and every documented figure is *projected* from the enclave's
  grounding record rather than re-keyed into the profile.
  Onboard a registered site with `watermark onboard <slug>` (`watermark.onboard`; runbook
  `docs/onboarding.md`): it scaffolds the per-site data dirs, runs the portable reach
  connectors (per-site point outputs are slug-scoped so Lima is never clobbered; basin-level
  outputs stay shared), and prints a **blocking review checklist** — promotion to
  `live`/`selectable` in `data/sites.yaml` (then `watermark sites sync`) stays a manual,
  parity-gated edit.
  **Registered ≠ selectable, and a thin peer is still engageable** (#781/#782): a
  non-reference `/network/<site>` page **degrades, doesn't break**. Readiness is **domain
  activation, not Lima-shape-matching** (#1220): a site is defined by the **domains that
  actually have a story there**, not by its deficits against Lima's taxonomy. It is computed
  **in Python at export** (`watermark.site.readiness`) and written into `manifest.json` as a
  `readiness` block — the five domains (**backdrop, facility, places, record, inquiry**), each
  `absent | seeded | live`, plus a derived **tier** (`stub → backdrop → case → reference`). It
  is a **standing property recomputed at every `watermark export`**: it rises when a source
  lands and falls when one dries up — never an onboard-time snapshot. The **floor is always
  pulled** (backdrop = the coordinate/FIPS/state-keyed connectors — economics-baseline,
  consumer-energy, RSEI); **above the floor triggers on evidence, never scaffolds** (facility on
  a disclosed permit + its feed, places on committed campus/footprint **or federal-enclave**
  geometry, record on extracted `records`/`documents`, inquiry on the site's own **`impact-study`
  verdicts**). **`inquiry` was `story` until #1971 (epic #1968), and the rename is the point:** its
  predicate was a registered MDX walk + a leads feed — the only domain whose signal was *authored
  prose* — so van-wert read `absent` while carrying three merged investigations, and findlay read
  `live` for a walk that was `comingSoon` and could not be opened. It now asks whether the site's
  study **answers**: a substantive chapter count **and** at least one of the two corpus-keyed
  chapters (`assembly`/`governance`) substantive, because most chapters derive from connector pulls
  and a count alone lets a zero-record site out-score a worked corpus. **The tier is derived from
  the four record-bearing domains only** — `inquiry` is reported and never gates, so a walk is no
  longer the price of a site's tier and a guided walk is never a "need" on a peer's board. Lima's
  `project-bosc` is the network's ONE surviving walk, kept as a method demo, not a per-site
  obligation. The frontend
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

- `data/documents/**` is raw, immutable, and **held in a yidam artifact vault, not in git**
  (#2147). Nothing under it that matches `VAULTED_SUFFIXES` is tracked or committed: the bytes are
  content-addressed in R2 and the repository holds the *record* of them in
  `data/*/*/vault.yaml`. `watermark documents hydrate` fills a working tree; `git lfs pull` does
  nothing here any more.
  ⚠️ **A new source type goes in the collection manifest, not in LFS tracking.** Add its suffix to
  `watermark.documents.vault.VAULTED_SUFFIXES`, regenerate the `.gitignore` block, then
  `watermark documents manifest` — in that order, because a suffix the ignore block does not name
  gets **committed as a source byte no manifest records**, which is the one state the vault exists
  to make impossible. `watermark documents manifest --check` catches it wherever the bytes are.
  The `history/` sub-tree is for secondary/reference sources (public-domain books,
  surveys) and nests **by site** (`history/allen-oh/`, `history/allen-in/`, …) so
  books for different watershed points don't collide. All claims from `history/`
  sources are tagged `[reference]`, never `[verified]`.
  A directory named `<dir>-text/` is the one derived thing that tree admits (#1757): committed
  **text sidecars** for the legacy binaries (`.doc/.dot/.xls/.rtf`) in its `<dir>/` sibling,
  which have no in-process reader and would otherwise be unsearchable. They mirror the source
  layout, keep the source's full name plus `.txt`, and are pinned to their source's sha256 by a
  `text-sidecars.yaml` manifest — `watermark text-sidecars <dir>` regenerates, `--check` reports
  drift. **Never hand-edit one** (the next run reverts it) and **never cite one**: the sidecar is
  a reading aid, the source is the record. Everything else (`.txt/.htm/.docx/.xlsx`) is read in
  process by `watermark.documents.office`; no sidecar exists for a format that can be read.
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
When the source is filed under a **site** subdirectory of that collection
(`oepa/van-wert/`), the extraction must keep it: `<collection>/<slug>/` *is* the site
attribution the corpus scope reads (#1405 — `watermark.sites._eponymous_prefixes`), so
an extraction shelved flat lands in Lima's reference record instead of its own site's,
and that site's record domain can never rise from permit ingest. Other sub-nesting
(`permits/bistrozzi-permits/` → `permits/`) carries no such meaning and need not mirror.

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
