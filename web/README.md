# `frontend/` — the redesigned BOSC site (Astro + MDX)

Tier 2 of the two-tier site refactor ([Epic #54](https://github.com/watermark-directory/the-watermark-directory/issues/54)).
An in-repo [Astro](https://astro.build) + MDX app that reads the committed
**content bundle** (the typed JSON feeds the Python data tier emits, Epic #53)
at build time and renders the site as static HTML.

This is the **sole presentation tier** — the legacy Python SSG was retired at the parity
cutover. Production is **Cloudflare Pages**
([`pages.yml`](../.github/workflows/pages.yml) + [`wrangler.toml`](wrangler.toml), where
the [`functions/`](functions/) Pages Functions deploy too), **not** GitHub Pages — that
deploy was never flipped and Cloudflare supersedes it.

## Toolchain

Node is pinned via mise (`node = "24"` in [`mise.toml`](../mise.toml)); `mise install`
gets it. The package manager is **pnpm** (Epic #1549) — also mise-pinned (`npm:pnpm` in
the root `[tools]`) and matched by the `packageManager` field in the root `package.json`.
This app is one member of a repo-root **pnpm workspace**, so dependencies are locked in a
single [`pnpm-lock.yaml`](../pnpm-lock.yaml) at the repo root — use
`pnpm install --frozen-lockfile` for reproducible installs.

## Develop

```sh
cd web
pnpm install --frozen-lockfile   # or: pnpm install   (first time / after dep changes)
pnpm run dev       # dev server with HMR  → http://localhost:4321
pnpm run check     # astro check (types + template diagnostics)
pnpm run build     # static build         → dist/
pnpm run preview   # serve the built dist/ locally
```

This project is a mise monorepo subproject: from anywhere, `mise run //frontend:check`
runs the full gate (Biome + types + vitest + build + link check), `mise run //frontend:dev`
starts the dev server, and `mise run //frontend:<task>` reaches `test`/`lint`/`build`/`fmt`/
`preview`. Inside `frontend/`, a bare `mise run <task>` works too (see `frontend/mise.toml`).

In CI, the `frontend` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
does the same against the sample bundle (pure Node — no uv/LFS). It's path-filtered:
a `changes` gate runs it only when `frontend/` changed, so a backend-only PR skips
it (and a frontend-only PR skips the Python `check` job). Don't add a trigger-level
`paths:` filter to that workflow — `check` is a required status check, and skipping
the *workflow* would leave it stuck pending; skipping a *job* via the gate reports
success instead.

## Local dev & testing — the Pages Functions

`pnpm run dev` (astro) serves every **static** page but **not** the Cloudflare Pages
Functions in [`functions/`](functions/) — `/api/submit`, `/api/ask`, `/api/doc`. Those run
only on the Workers runtime. There are two ways to exercise them locally, and you usually
want the first:

**Tier A — automated route tests (offline, in CI).** `pnpm test` drives each handler
end-to-end with a faked `Env` + a stubbed `fetch` (`src/lib/{submit,ask,doc}Route.test.ts`
over the shared `src/lib/_routeHarness.ts`). No wrangler, no network, no real issues filed,
no Anthropic spend — and it gates every frontend PR. This is the safety net; reach for it
first when changing a Function.

**Tier B — the full interactive stack.** `mise run //frontend:dev:stack` builds the site and
serves it **with** the Functions via `wrangler pages dev`, so you can click through
submit/ask/doc in a browser (→ http://localhost:8788). It:

- creates `frontend/.dev.vars` from [`.dev.vars.example`](.dev.vars.example) on first run
  (with a throwaway App key) — kill switches on, **mocked externals by default**;
- builds with Cloudflare's always-pass **dummy Turnstile** keys so the widgets render;
- starts a local mock origin ([`scripts/dev-mocks.mjs`](scripts/dev-mocks.mjs)) that stands
  in for GitHub + Anthropic via the `GITHUB_API_BASE` / `ANTHROPIC_API_BASE` seam — so
  **submit files no real issue and ask spends no tokens**;
- binds local KV (rate-limit / budget / contact) and a local R2 simulator for `DOCS`.

`wrangler` is managed by **mise** (`frontend/mise.toml` `[tools]`, `npm:wrangler`), not an npm
dependency — so it's pinned + isolated without bloating `pnpm install` or the frontend CI job (which
uses `setup-node`, not mise). Run the stack via `mise run //frontend:dev:stack` (not a bare
`pnpm run dev:stack`) so wrangler is on `PATH`; its workerd binary downloads lazily on first run.
Turnstile verification still makes one real call to Cloudflare's siteverify (the dummy secret
always passes), so this needs network. For real end-to-end submit/ask instead of mocks, point
the `*_API_BASE` vars in `.dev.vars` at the real hosts and supply real creds.

**Serving real documents (`/api/doc`).** Before launch, `dev:stack` seeds the local R2 with the
**published** documents ([`scripts/seed-r2.mjs`](scripts/seed-r2.mjs)) — writing through
wrangler's own `getPlatformProxy()` into the *same* store `wrangler pages dev` reads (you can't
fill it with `wrangler r2 object put`). So PDFs/images load with **no Cloudflare creds and no
remote bucket**. It's incremental and LFS-aware; you need a real content bundle
(`WATERMARK_BUNDLE_DIR` or `watermark export`) and `git lfs pull` for the bytes. To serve more than the
published set, `pnpm run seed:r2 -- --collection <slug>` (or pass explicit rels) and restart the
stack. Skip seeding with `DEV_STACK_NO_SEED=1`. The doc-serving *logic* (gate, ranges,
content-type) is covered offline by `src/lib/docRoute.test.ts`.

## How the content bundle is resolved

`src/lib/bundle.ts` reads the bundle at build time. It picks the **first**
directory that contains a `manifest.json`:

1. **`$WATERMARK_BUNDLE_DIR`** — explicit override (absolute or relative to CWD).
2. **`../data/site/bundle`** — the real bundle, present after `watermark export`.
3. **`./sample-bundle`** — the committed minimal fixture (the default in a fresh
   checkout and in CI; see [`sample-bundle/README.md`](sample-bundle/README.md)).

So a plain `pnpm run build` works with zero Python (it uses the fixture). To build
the full site against real data:

```sh
watermark export                                   # → data/site/bundle/  (the loader then prefers it)
# or point anywhere:
WATERMARK_BUNDLE_DIR=/path/to/bundle pnpm run build
```

Read `manifest.json` first, then feeds it lists:

```ts
import { loadManifest, loadFeed } from "../lib/bundle";
const manifest = loadManifest();
const records = loadFeed<RecordItem[]>("records");
```

The bundle contract (manifest shape, feed list, schemas, provenance) is documented
in [`data/site/bundle/README.md`](../data/site/bundle/README.md).

## Information architecture — the BOSC network

The site is **one build** that hosts a *network* of watershed-point sites (the multi-site
pivot, [#308](https://github.com/watermark-directory/the-watermark-directory/issues/308)). Lima is the live reference
build; the basin sites come online incrementally. Two sources of truth: the sites registry
(`src/lib/sites.ts`) and the header IA (`src/lib/nav.ts` — the header tabs, the per-section
TOC rail, and the search index).

- **Lima's record content is physically re-rooted under `/bosc`** so future sites are clean
  siblings (`/gcp`, …). `/` redirects there (`public/_redirects`, a *temporary* 302 — the
  root will host network content once a second site lands). The topbar **project switcher**
  (a no-JS `<details>` on the brand mark) hops between sites, rendering each site's real
  `status`/`selectable` from the registry and the *current* site from the route
  (`siteForPath`). Only Lima is selectable today; the rest route to a coming-soon page
  (`/network/<slug>`).
- **Cross-cutting pages are network-global** at the root, shared across every site:
  `/about`, `/about-me`, `/wiki/*`, `/ask`, `/search`, `/network/*`, and the `/api/*` functions.

The four header tabs (the reconciled IA, design dictate 02 / [#307](https://github.com/watermark-directory/the-watermark-directory/issues/307)):

- **The BOSC site** (`/bosc/site/`) — documents, records, timeline, exhibits, people & places, legal
- **Watershed** (`/bosc/watershed/`) — hydrology, watershed map, imagery, RSEI/toxics
- **Wiki** (`/wiki/`) — entity & concept pages (global)
- **Docs** (`/bosc/docs/`) — the long-form essays + methodology

Home is the logo lockup (`/bosc`); the guided walk (`/bosc/start`) and **Ask** (`/ask`) are
topbar affordances, not tabs. The active tab is a white underline.

## Search

Dependency-free, zero-CDN. A build-time endpoint (`src/pages/search-index.json.ts` →
`/search-index.json`) emits one entry per section area and per bundle row — each carrying a
**kind** (Record / Entity / Concept / …), an optional mono **id**, and an **evidence tag**
where the row has a real signal (records, via their citation — no fabricated tags). The
matcher + the result **record-row grammar** (results grouped by section; each row is a kind
eyebrow · title · mono id · evidence dot · snippet) live in a shared engine
(`src/scripts/searchEngine.ts`) used by **both** the topbar dropdown (`src/scripts/search.ts`)
and the full results page (`/search`, `src/scripts/search-page.ts`) so the two never drift.
All-terms substring match, title hits first; `↵` opens `/search?q=…`. No lunr, no host.

## Charts

A hand-rolled SVG chart library (no charting dependency) in the record grammar
([#306](https://github.com/watermark-directory/the-watermark-directory/issues/306)): pure geometry builders in
`src/lib/charts.ts` (`buildVBars`/`buildHBars`/`buildLine`/`buildBullet`/`buildStacked`/
`buildDonut`/`buildSparkline`) feed seven SSR components in `src/components/charts/`. Two
palette rules: **indigo encodes data**; the **evidence palette** (`EVIDENCE_FILL` — green/
amber/grey) is spent *only* on encoding evidence. Real, no-fork uses are wired into records
(a by-group donut), reports (a discharge bullet), and the watershed hydrology screen (a
draw-vs-7Q10 bullet drawn from the scenarios feed).

## Interactive maps & the entity graph (deck.gl)

The map/graph visualizations (Epic #55) are **React islands** — the only React in
the app — mounted `client:only` so their JS (deck.gl + MapLibre, ~heavy) loads
**only** on those pages; the rest of the site stays zero-framework. Each island
has a **server-rendered no-JS fallback** (a legend + feature table, or the entity
list) that doubles as a plain data view.

- **Corridor map** (`/bosc/watershed/map`, [#71](https://github.com/watermark-directory/the-watermark-directory/issues/71)) — `src/components/islands/CorridorMap.tsx`, deck.gl `GeoJsonLayer`s over a MapLibre basemap with dated Esri Wayback aerials. Styled **entirely from the feed** (`color`/`role`/`radius`); the data is the geo feeds merged by the `/feeds/geo/corridor-map.geojson` endpoint.
- **Entity graph** (`/wiki/graph`, [#73](https://github.com/watermark-directory/the-watermark-directory/issues/73)) — `src/components/islands/EntityGraph.tsx`, a deck.gl `OrthographicView` over nodes/edges laid out at build time by `d3-force` (`/feeds/graph.json`, deterministic). Click a node → its wiki page; entity pages deep-link `/wiki/graph#<slug>` to focus a neighborhood.

The islands are build-verified (bundle, mount, endpoint fetch); a quick **browser
visual pass** is still worth doing (WebGL rendering isn't covered by `astro check`).
The watershed map (`/bosc/watershed/map`) and the before/during/after imagery slider
(`/bosc/watershed/imagery`, [#72](https://github.com/watermark-directory/the-watermark-directory/issues/72)) ship too —
`ImagerySlider.tsx` over the `geo/imagery` Wayback feed, against the committed
watershed-boundary + AOI geometry feeds.

## Narrative content (the `docs/` collection)

The project's prose (DOSSIER, methodology, HYDROLOGY, ECONOMICS, the bigger
picture, legal analyses…) is surfaced via an Astro **content collection** sourced
from the repo-root `docs/` **as-is** ([#69](https://github.com/watermark-directory/the-watermark-directory/issues/69)).

**Single-source decision:** `docs/` stays at the repo root and is **not** moved or
edited — it's also general repo documentation.
The frontend reads it with a `glob` loader over `../docs` (`src/content.config.ts`),
publishing only the curated set in `src/lib/narrative.ts`, rendered at `/bosc/docs/<slug>`.

Because the source links target the *legacy* `web/docs/` layout, a build-time
rehype plugin (`src/lib/rehype-doc-links.ts`) rewrites them without touching the
source: intra-narrative links → `/bosc/docs/<slug>`, known legacy pages → their new-IA
route (`src/lib/narrative.ts` `LINK_MAP`), and any other in-repo file (the corpus,
not-yet-migrated pages) → its GitHub source — so cross-links resolve in both tiers. Since
the re-root, the plugin **base-prefixes Lima routes with `/bosc`** (`limaBase` in
`astro.config.ts`), with a `GLOBAL_ROUTE` guard so network-global targets (`/wiki`, `/about`,
`/ask`) are *not* prefixed; `LINK_MAP` values stay un-prefixed so they don't double.

> Note: editing `astro.config.ts`-imported modules (the rehype plugin / its data) requires
> clearing **`node_modules/.astro`** (Astro caches markdown rehype output there — a stale
> cache silently survives a base/`LINK_MAP` change) and `node_modules/.vite` (the config
> bundle cache); a fresh `pnpm install --frozen-lockfile` in CI is unaffected.

## Evidence tags

`src/components/EvidenceTag.astro` renders the corpus's inline confidence markers
(`[verified]` / `[inference]` / `[open]` / `[filename]`) as tinted pills; derive
the kind from a citation with `evidenceKind()` in `src/lib/feeds.ts`.

## Layout

```
frontend/
  astro.config.ts      # MDX + React integrations; static output; rehype link
                       #   rewriter for the docs collection; site/base from env
  src/
    content.config.ts  # the docs/ narrative content collection (glob over ../docs)
    lib/
      bundle.ts          # build-time bundle reader (resolve dir, manifest, feeds, hasFeed)
      feeds.ts           # TS shapes for the feed rows + evidenceKind()
      nav.ts             # the 4-tab IA + section ids + per-section TOC (single source of truth)
      sites.ts           # the BOSC-network registry + siteForPath() (switcher source of truth)
      charts.ts          # pure SVG geometry builders for the chart library
      icons.ts           # the inline icon set (paired with Icon.astro)
      search.ts          # build-time search-index assembly over the bundle
      site.ts            # site constants + withBase() base-path helper
      narrative.ts       # which docs/ files are published + the legacy→IA link map
      rehype-doc-links.ts # build-time rewriter for in-repo links inside docs/ (base-aware)
      geo.ts / graph.ts  # build-time geo merge + deterministic d3-force graph layout
      geoStyle.ts        # client-safe geo types/colors (shared with the islands)
    components/          # Header (switcher + tabs + Ask + search), SectionToc rail, Logo/Icon
      charts/            # seven SSR chart primitives (bar/ranked/line/donut/bullet/stacked/spark)
      islands/           # CorridorMap + EntityGraph — the only React (deck.gl)
    layouts/Base.astro   # the app shell (header + TOC rail + content + footer)
    scripts/             # searchEngine.ts (shared) + search.ts/search-page.ts + toc.ts (no-dep)
    styles/site.css      # shell styling (indigo chrome, evidence pills, chart + search grammar)
    pages/
      index.astro         # the network root — redirects to the live site (/bosc)
      bosc/               # Lima's record content, re-rooted: site/ watershed/ docs/ reports/
                          #   timeline start submit walk (the four tabs + the walk spine)
      wiki/               # entities, concepts, the entity graph (network-global)
      network/            # the network hub + per-site coming-soon pages (/network/<slug>)
      about.mdx about-me.astro ask.astro search.astro   # network-global pages (root)
      search-index.json.ts ask-index.json.ts            # build-time client-index endpoints
      published-documents.json.ts robots.txt.ts
      feeds/              # build-time data endpoints (geojson, graph.json) for the islands
  functions/            # Cloudflare Pages Functions — /api/submit, /api/ask (see functions/README.md)
  public/_redirects     # Cloudflare 301/302s: / → /bosc (302) + old Lima URLs → /bosc/*
  sample-bundle/        # committed minimal bundle fixture (offline/CI build input)
```

## Status / roadmap

**Shipped — the two-tier site (Epic [#54](https://github.com/watermark-directory/the-watermark-directory/issues/54)) is
complete.** Scaffold + app shell, all the content sections (the corpus catalog/records/
timeline/exhibits/people/legal, the watershed water-balance + RSEI, the wiki entity/concept
pages + `[[wiki-link]]` resolver), the **deck.gl layer** (Epic #55 — corridor map #71 +
entity graph #73 + imagery slider #72), and the migrated narrative collection (#69).

**Shipped — the BOSC-network design refresh (Epic [#308](https://github.com/watermark-directory/the-watermark-directory/issues/308)).**
The multi-site pivot and chrome restyle: the sites registry + project switcher (#304) with
per-site coming-soon pages (#305); the chart library (#306); the icon/brand refresh (#309);
the four-tab IA reconciliation, the `/bosc` re-root + root globals, and the search
record-rows + the full `/search` page (#307); the switcher current-site fix (#316).

**Remaining:** flip the Pages deploy live to this app; build out the basin sites as the
network grows (Fort Wayne #235, Defiance #238,
Findlay #237, Toledo #236); and take the dark-until-enabled seams live (submit #241, ask
#302). The `/api/*` functions and the submit/ask pages ship behind kill switches until then.
