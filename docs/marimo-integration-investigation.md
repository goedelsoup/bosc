# marimo integration investigation

> **Outcome (superseded — decision record).** This evaluation recommended a partial,
> opt-in marimo **WASM** integration into the *legacy Python SSG*. That SSG was later
> retired (the Astro `web/` became the sole presentation tier), and the single
> proof-of-concept notebook (`notebooks/opc_scenario.py`) was **reimplemented as a native
> React island** rather than a WASM export — see
> `web/src/components/islands/OpcScenario.tsx` + `web/src/lib/opcScenario.ts`,
> live at `/bosc/reports/opc-scenario`. marimo was **not** adopted and the `notebooks/`
> directory was removed. This document is kept as the record of *why* — the
> `pyswmm`/`pypdfium2` WASM blockers, the ~27 MB per-notebook bundle, and the
> chain-of-custody fit — mirroring `docs/deckgl-spike.md`. The integration mechanics below
> (`watermark site build --notebooks`, `nav.yaml`, `web/` wrappers) describe the retired SSG and
> no longer exist; read them as history.

## Executive summary / recommendation

**Recommendation: integrate marimo, but partially and behind an opt-in build flag —
WASM-export only, for use cases (1) scenario demos and (2) lessons/tutorials. Do
*not* attempt use case (3) "open-ended exploration over the full BOSC dataset" as a
first step, and do not stand up a live marimo server.**

marimo's `marimo export html-wasm` produces a fully static, browser-only
(Pyodide/WASM) notebook that drops cleanly onto GitHub Pages — the same host the
BOSC site already targets. I installed marimo 0.23.9, built a real BOSC notebook
over the committed OPC estimate data, exported it to static WASM HTML, and served
it: the export succeeds, the bundled data file is reachable, and the runtime is
self-contained. So the *mechanism* fits.

The single biggest **blocker** is Pyodide package coverage for BOSC's own stack:
**`pyswmm` (the SWMM stormwater engine) and `pypdfium2` (the PDF renderer) have no
Pyodide/WASM builds and cannot load in the browser.** This kills "run the live
hydrology water-balance model in a WASM notebook" and "render a source PDF page in
the browser." The good news: `numpy`, `scipy`, `pandas`, `shapely`, `pyproj`,
`pydantic`, `httpx`, `pillow`, `networkx`, `matplotlib`, `pyyaml`, and `altair` are
all available in Pyodide, so the **entity graph, GIS geometry, OPC financials, and
EPA/GLEIF reference data are fully in-scope** for WASM notebooks. The hydrology
thread can participate only via **precomputed results** (export scenario outputs
from a real `watermark` run, then visualize them client-side) — which is the
marimo-recommended pattern for heavy/unsupported compute anyway, and is also the
right answer for the litigation **chain-of-custody** constraint (the browser
notebook reads bundled read-only artifacts; the authoritative model runs server-side
under `mise run check`).

The biggest **enabler** is that BOSC already commits its analysis inputs as small,
reviewed YAML/CSV/GeoJSON under `data/extracted` and `data/reference`. Those drop
straight into a notebook's `public/` folder and are read with `mo.notebook_location()`
— no server, no database, no network. That is exactly the shape Pyodide notebooks
want.

**Effort to a real first increment:** ~1 day for a single curated notebook plus an
opt-in `watermark site build --notebooks` step that shells `marimo export html-wasm` and
links the result from `nav.yaml`. **Maintenance cost** is real but bounded: marimo
is a new dev dependency, each notebook is a hand-curated page, and the WASM bundle is
~27 MB per notebook of frontend assets (the Python runtime/packages stream from a
CDN at page load, adding a multi-second cold start). It must stay *out* of
`mise run check`/mypy-strict/pytest — see §4.

---

## 1. Deployment-mode fit

### The two marimo modes vs the static host

| Mode | What it needs | Fits GitHub Pages? |
|---|---|---|
| `marimo export html-wasm … --mode run` | nothing — static HTML + JS + a CDN-loaded Pyodide runtime | **Yes.** Read-only "app": code locked/hidden, widgets live. |
| `marimo export html-wasm … --mode edit` | same static host | **Yes.** Same bundle, but the visitor can edit and re-run cells in their browser. |
| `marimo run notebook.py` / `marimo edit` (interactive server) | a live Python backend process (websocket) | **No.** Needs a hosted server; incompatible with a static Pages deploy and with the "site is an unlisted draft, manual deploy" posture. |

Verified flags (marimo 0.23.9, `marimo export html-wasm --help` / docs): `-o/--output`
(directory), `--mode {run,edit}`, `--show-code/--no-show-code`, `--watch/--no-watch`,
`--include-cloudflare`. The export **must be served over HTTP** — it will not run from
a `file://` URL, and the sibling `assets/` directory must be served next to
`index.html`. GitHub Pages satisfies both.

### Use-case → mode mapping

1. **Scenario demonstrations** → `--mode run`. A curated, locked notebook with
   sliders/dropdowns that recompute a result from bundled data (exactly the POC).
   Read-only is correct: it is a published exhibit, not a sandbox.
2. **Lessons / tutorials** → `--mode edit` for the "follow along and tinker"
   experience, or `--mode run` with `--show-code` for a read-the-code walkthrough.
   Either is static.
3. **Open-ended exploration** → wants `--mode edit` *and* the full dataset and full
   library stack in the browser. This is where WASM limits bite hardest (no pyswmm,
   no pypdfium2, 2 GB memory cap, the whole dataset would have to be bundled or
   fetched). Treat as a later, scoped goal, not part of the first integration.

### WASM limitations that matter here

**Pyodide package availability (verified against the Pyodide stable package list).**

| BOSC dependency | In Pyodide? | Notes |
|---|---|---|
| `numpy`, `scipy`, `pandas` | **Yes** | core scientific stack ships pre-built |
| `shapely`, `pyproj` | **Yes** | GEOS/libproj are compiled to WASM upstream |
| `pydantic` | **Yes** | the BOSC models validate in-browser |
| `httpx` | **Yes** | but see network note below |
| `pillow`, `networkx`, `matplotlib`, `pyyaml`, `altair` | **Yes** | graph + viz + config parsing all work |
| `markdown`, `jinja2` | **Yes** (pure-Python wheel via micropip) | |
| **`pyswmm`** | **No** | wraps the native SWMM C engine; no wasm32 wheel. **The water-balance/stormwater model cannot run in the browser.** |
| **`pypdfium2`** | **No** | ships a PDFium C++ binary; no wasm32 wheel. **Cannot render source PDF pages client-side.** |
| `polars` | via micropip | pure-Python/wasm wheel exists; not needed unless a notebook chooses it |
| `claude-agent-sdk`, `anthropic` | n/a | no agent calls belong in a public static notebook anyway |

Net: the *analysis-layer* deps load; the two *native-binary* deps (`pyswmm`,
`pypdfium2`) do not. This cleanly partitions what a WASM notebook can and cannot do.

**Network / filesystem.** Pyodide has no real filesystem and no raw sockets.
Python's built-in `open()` cannot read the bundled data once exported (the path
becomes a URL). The supported pattern, which the POC uses:

```python
data_url = str(mo.notebook_location() / "public" / "roundabouts.summary.opc.yaml")
import urllib.request
with urllib.request.urlopen(data_url) as fh:   # Pyodide routes urllib through fetch()
    doc = yaml.safe_load(fh.read())
```

`mo.notebook_location()` is the notebook directory locally and the deploy URL after
export, so one code path works in both. Anything in a `public/` folder next to the
notebook is copied into the export and served as a same-origin asset (no CORS issue).
`httpx`/`urllib` *can* reach out over the network, but only to CORS-permitting hosts —
so a notebook could fetch a `data/reference` CSV from the deployed site, but should
**not** be relied on to hit USGS/NOAA/EPA APIs live (those are what the server-side
`watermark.hydrology.connectors` are for; the browser would be blocked by CORS and would
also bypass the on-disk cache/fixture discipline).

**Bundle size / cold start.** The POC export is **~27 MB across 689 files** for a
single notebook — that is the marimo frontend (editor, CodeMirror language modes,
KaTeX, Mermaid, icons). It is shared chrome, not per-data weight, but it is heavy for
a docs site. On top of that, the Pyodide runtime and each scientific package stream
from a CDN on first load, so cold start is several seconds and depends on the
visitor's network. Implication: notebooks should be a small number of deliberate
pages, not sprinkled everywhere, and ideally lazy-loaded (linked, or iframed on
demand) rather than inlined into every page.

**Chain-of-custody (litigation evidence).** This is a constraint marimo handles well
*if used as designed*:

- A WASM notebook reads **bundled copies** of committed artifacts. It physically
  cannot mutate `data/documents/**` or `data/extracted/**` — there is no filesystem
  and the bundle is a copy. Good.
- The bundled copy must be a **build-time copy of a committed artifact**, never a
  hand-edited figure pasted into a notebook. The POC copies
  `data/extracted/aedg/roundabouts.summary.opc.yaml` verbatim into `notebooks/public/`.
  In a real integration, `build.py` should do that copy from the canonical source so
  the published data provably matches the corpus (don't let `public/` drift).
- Keep the *authoritative* hydrology/OPC computation server-side (under
  `mise run check`, validated by the Pydantic models). The browser notebook is a
  **viewer/illustrator over reviewed outputs**, not a second source of truth. This is
  also why "precompute heavy results, visualize in WASM" is the right architecture
  regardless of the pyswmm blocker.

---

## 2. Integration architecture

A concrete, convention-respecting design.

### Where notebooks live

```
notebooks/                         # new top-level dir, source of truth (committed)
  opc_scenario.py                  # a marimo notebook (= a plain .py file)
  public/                          # per-notebook bundled, read-only data
    roundabouts.summary.opc.yaml   # build-time copy of the committed artifact
```

marimo notebooks are ordinary Python files (`app = marimo.App()` with `@app.cell`
functions), so they version cleanly and diff sensibly — unlike `.ipynb` JSON.

### How the export gets invoked

Add an **opt-in** build step rather than changing the default pipeline. Two
equally-valid placements; prefer the CLI flag for discoverability:

- **CLI flag (recommended):** extend `site_build` in `src/watermark/cli.py` with
  `notebooks: bool = typer.Option(False, "--notebooks/--no-notebooks", …)`. When set,
  after `render_site(...)`, iterate `notebooks/*.py` and for each run
  `marimo export html-wasm <nb> -o site/notebooks/<slug> --mode run --no-show-code`.
  marimo is invoked as a subprocess (`subprocess.run([...])`), so it stays a
  dev/docs-only dependency and never imports into the typed codebase.
- **build.py hook:** a `build_notebooks(web, settings)` helper called only when the
  flag/CI input is set. Mirror the `data/extracted` copy-into-`public/` step here so
  the bundled data is provably the committed artifact.

A new module `src/watermark/site/notebooks.py` should own: resolving the notebook list,
copying canonical artifacts into each notebook's `public/`, shelling the export, and
**post-processing the bundle** (drop the stray sibling files the exporter copies — in
my run it copied `notebooks/`'s neighbors including a `CLAUDE.md` into the output; the
export grabs the whole notebook directory tree, so keep `notebooks/` clean or prune
after export).

The default `watermark site build` (and the CI/Pages workflow) stay exactly as they are
unless the flag is passed — zero risk to the current site.

### How exported HTML is embedded / linked

The marimo export is a **self-contained mini-site** (`index.html` + `assets/`) with
its own dark editor chrome — it will **not** inherit `site.css`/`extra.css`. Two
options:

- **Link as standalone pages (recommended):** add the export under
  `site/notebooks/<slug>/index.html` and add nav entries pointing at it. Clean, no
  CSS conflicts, lazy-loaded (the 27 MB only downloads when a visitor opens it).
  Because `nav.yaml` targets are `.md`→`.html`-rewritten, link to a notebook by
  generating a thin wrapper markdown page (e.g. `web/notebooks/opc.md`) whose body is
  a short intro + a link/iframe to `notebooks/opc/index.html`, *or* extend
  `_rewrite_target`/nav to allow a direct `…/index.html` target.
- **iframe inside a normal page:** wrap each notebook in a generated markdown page
  that embeds `<iframe src="notebooks/opc/index.html">`. Keeps the BOSC chrome around
  it; isolates the marimo CSS inside the frame. Slightly clunky sizing, but it
  preserves the site's look-and-feel on the surrounding page.

Either way `nav.yaml` gets a new section, e.g.:

```yaml
  - Notebooks:
      - OPC scenario explorer: notebooks/opc.md     # wrapper page → links/iframes the export
```

`templates/base.html` needs no change for the link approach (the standalone export
brings its own shell); for the iframe approach, nothing changes either since the
iframe sits inside normal rendered markdown. The site's CSS look-and-feel carries
over on the *wrapper/index* pages; inside the notebook itself it is marimo's theme
(acceptable, and visually signals "interactive tool").

### Convention compliance

- `notebooks/` is committed source of truth; the export lands under git-ignored
  `site/` (add `site/notebooks/` is already covered by the `/site/` ignore).
- The build step reads config via `get_settings()` (e.g. to locate the canonical
  `data/extracted` artifact to copy), never `os.environ`.
- CLI option typed as `bool` (no `Path`-in-`Option` B008 issue).
- marimo is added to the **`docs` optional group** (it powers `watermark site`,
  matching how markdown/jinja2 already live there), *not* core deps.

---

## 3. Alternatives / do-nothing

| Option | (1) Scenario demo | (2) Lessons | (3) Open exploration | Static-host fit | Verdict for BOSC |
|---|---|---|---|---|---|
| **Do nothing** (Markdown + existing Leaflet/Mermaid) | static charts/maps only — no recompute | read-only prose | none | perfect | Fine for narrative; **cannot** do "move a slider, see the total change." |
| **Jupyter + nbconvert (static HTML)** | renders *frozen* outputs; **no interactivity** | yes, as static pages | no | perfect | Good for baking a computed figure into a page; not for live widgets. |
| **JupyterLite / Pyodide directly** | yes (live, in-browser) | yes | **yes** — closest to "open IDE" | yes | Same Pyodide engine/limits as marimo; heavier full-IDE UI, `.ipynb` JSON diffs poorly, **no reactive dataflow** (must re-run cells manually). |
| **Quarto (+ quarto-pyodide)** | static by default; optional Pyodide cells | **excellent** for lessons/books | partial | yes | Strong authoring/lessons story, but it's a **second site generator** alongside the in-repo Python renderer — duplicates chrome/build and fights the "no MkDocs/theme, in-process renderer" decision (commit d44062a). |
| **Observable** | yes | yes | yes | yes (JS) | JavaScript, not Python — can't reuse BOSC's Pydantic models or the analysis code; wrong language for this codebase. |
| **Hosted marimo server** | yes, full power (pyswmm works!) | yes | **yes** | **no** — needs a running backend | Only path that runs the real hydrology model interactively, but breaks the static/unlisted-draft posture and adds ops/cost/attack-surface. Out of scope now. |
| **marimo WASM export** | **yes** (the POC) | yes (`--mode edit`) | partial (subject to pkg limits) | yes | **Best fit** for (1) and (2): Python, reuses the corpus, reactive, static. |

When marimo is *clearly right*: an interactive scenario page where a visitor adjusts
an assumption (contingency %, which intersections, a rainfall depth from precomputed
curves) and sees figures/charts recompute — in Python, over committed BOSC data, on a
static host. When it's *overkill*: a one-shot computed figure (use nbconvert or just
generate the chart in `build.py` and embed an image/Vega spec), or pure narrative
(plain markdown). When it's *the wrong tool*: anything needing the live SWMM engine,
PDF rendering, or real API pulls — that stays server-side.

---

## 4. Concrete recommendation + phased plan

**Integrate partially, WASM-only, opt-in.** Reasoning: it is the only option that is
(a) Python, so it reuses BOSC's models/data, (b) reactive, satisfying use cases (1)
and (2), and (c) static, preserving the GitHub-Pages + unlisted-draft + manual-deploy
posture and the chain-of-custody guarantee (browser reads read-only bundled copies).
Defer use case (3) and any live server.

### Phase 0 — POC (done in this investigation)

- `notebooks/opc_scenario.py` + `notebooks/public/roundabouts.summary.opc.yaml`.
- Verified: `marimo export html-wasm opc_scenario.py -o <out> --mode run` exits 0,
  bundles `public/`, serves over HTTP (index + data both 200). marimo not left in the
  synced env; nothing wired into the default build.

### Phase 1 — One real notebook, opt-in build step (~1 day)

- Add `marimo` to the `docs` optional group in `pyproject.toml`.
- Add `src/watermark/site/notebooks.py`: copy canonical artifact → `notebooks/<nb>/public/`,
  shell `marimo export html-wasm … --mode run`, prune stray sibling files from the
  output bundle.
- Add `--notebooks/--no-notebooks` to `watermark site build` (default off).
- Add a `Notebooks` section to `nav.yaml` and a thin wrapper markdown page that links
  (or iframes) the export.
- Add the flag to the Pages workflow as a `workflow_dispatch` input so deploy is a
  conscious choice.

### Phase 2 — Hydrology via precomputed results (~1–2 days)

- Add a `watermark` subcommand (or reuse an existing scenario run) that writes a small,
  committed **scenario-results** artifact under `data/extracted/.../scenario.*.yaml`
  from the *real* server-side model.
- A WASM notebook reads that artifact and lets visitors slide between precomputed
  cases / interpolate — no pyswmm in the browser. This is the canonical workaround and
  keeps the authoritative model under `mise run check`.

### Phase 3 — Lessons + (cautiously) exploration

- `--mode edit` tutorial notebooks (the `COURSE.md` material is a natural fit).
- Only then evaluate an "exploration" notebook over the entity graph (networkx +
  shapely are available), accepting bundle size and the package limits.

### Effort / risk / maintenance

- **Effort:** Phase 1 ~1 day; Phases 2–3 a few days each.
- **Risk:** marimo version churn (pin it); bundle bloat (one notebook ≈ 27 MB of
  frontend assets + CDN-streamed runtime → keep notebook count small, lazy-load);
  the exporter copying stray sibling files (prune step); CDN dependency for the
  Pyodide runtime (cold start, and a hard offline failure if the CDN is unreachable —
  self-hosting the runtime is possible but adds tens of MB).
- **Maintenance:** each notebook is hand-curated; bundled `public/` data must be
  regenerated from canonical artifacts on every build (don't let it drift — that's a
  chain-of-custody concern).

### Interaction with `mise run check` / mypy strict / tests

- The marimo notebooks are `.py` files with marimo-injected globals and cell wiring;
  they would **not** pass `ruff`/`mypy --strict` as written (and shouldn't be held to
  it — they're generated/authoring artifacts, like `web/`). **Exclude `notebooks/`
  from `ruff`, `mypy`, and `pytest`** (ruff `extend-exclude`, mypy `exclude`, pytest
  `norecursedirs`/no collection), the same way `web/` and `site/` are kept out.
- The **integration glue** (`src/watermark/site/notebooks.py`, the CLI flag) is normal
  typed code and *does* go through `mise run check` — it just shells out to marimo via
  `subprocess`, so marimo never needs to import or type-check inside the codebase.
- A lightweight test could assert the export command builds for one notebook in CI,
  but it's slow (downloads frontend assets) — better as a manual/opt-in check than a
  default `pytest` run.

---

## 5. Proof of concept (built and run)

**Files (left in the worktree, uncommitted, not wired into the build):**

- `notebooks/opc_scenario.py` — a marimo notebook over the OPC roundabout estimates.
- `notebooks/public/roundabouts.summary.opc.yaml` — a copy of the committed artifact
  `data/extracted/aedg/roundabouts.summary.opc.yaml`, bundled read-only.

**What the notebook does:** loads the six Tetra Tech sub-estimates from the bundled
YAML via `mo.notebook_location()` + `urllib`/`yaml` (the WASM-safe data path), exposes
a contingency-% slider and an intersections multiselect, and re-derives each total
from the high-confidence construction subtotal, showing a live program total and a
table comparing modeled vs source totals. It is explicitly read-only and carries the
evidence/confidence caveat in-page.

**Export command (verified):**

```bash
# from notebooks/
marimo export html-wasm opc_scenario.py -o ../site_wasm_poc --mode run
```

**Results:**

- Exit 0. Output: `index.html` + `assets/` (689 files, ~27 MB) + the bundled
  `public/roundabouts.summary.opc.yaml`.
- Served with `python -m http.server`: `index.html` → 200, bundled YAML → 200.
- `index.html` carries `data-marimo="true"`; the Pyodide runtime + Python packages
  (pyyaml here, a pure-Python wheel resolved by micropip) stream from a CDN at load.
- **Gotcha observed:** the exporter copied the notebook directory's sibling files
  (including a `CLAUDE.md`) into the output — a real integration must keep `notebooks/`
  clean or prune the bundle after export.

I could not headlessly execute the in-browser Python (that needs a real browser /
Pyodide session), but the export is structurally valid, self-contained, serves over
HTTP, and every library it imports (`yaml`) is Pyodide-resolvable — the same path the
marimo docs document for WASM data loading.

## Sources

- [marimo — WebAssembly HTML export](https://docs.marimo.io/guides/exporting/webassembly_html/)
- [marimo — WebAssembly notebooks (limitations)](https://docs.marimo.io/guides/wasm/)
- [marimo — CLI commands](https://docs.marimo.io/cli/)
- [marimo — self-host WASM notebooks](https://docs.marimo.io/guides/publishing/self_host_wasm/)
- [marimo issue #3194 — including data in WASM notebooks](https://github.com/marimo-team/marimo/issues/3194)
- [marimo issue #6719 — `mo.notebook_location()` path→URL after export](https://github.com/marimo-team/marimo/issues/6719)
- [Pyodide — packages built in Pyodide](https://pyodide.org/en/stable/usage/packages-in-pyodide.html)
- [JupyterLite](https://github.com/jupyterlite/jupyterlite) / [quarto-pyodide via Pyodide related projects](https://pyodide.org/en/stable/project/related-projects.html)
