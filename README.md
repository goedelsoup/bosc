# Watermark

> **A PUBLIC RECORD OF THE BUILD-OUT** · `watermark.directory`

**The build-out, on the public record.** Watermark is an agentic research
platform that assembles the paper trail behind a contested hyperscale
data-center build-out — the deeds, permits, cost estimates, and meeting minutes
the developers didn't write — and turns it into browsable, citable, structured
evidence.

It reads what's on the page. Degraded scans, OCR'd permits, recorder filings,
and county minutes are deconstructed into reviewed structured data, and Claude
runs analysis across the result. Land is moving and shells are forming; the
record was often made thin on purpose. This is the tool that reassembles it.

The subject is a network of **watershed-point sites** across the Ohio River
basin — each a point where compute meets ground, water, and power. **Lima, OH**
(American Sugar Creek, Allen County) is the live reference build; 22 more sites
are registered and coming online as contributions land.

---

## The discipline

The corpus is **litigation evidence**, and it is treated that way. Nothing is
guessed. Nothing is invented. Every figure either reads off a scanned page or
returns from an official database, and it carries its source.

The reading model is doctrinal — **source → structured read → meaning →
verify.** Nothing is asserted that can't be traced back a step. Every claim in
the extracted data carries an evidence tag:

| Tag | Means |
|---|---|
| `[verified]` | Reads off a source document or an authoritative database. |
| `[inference]` | A reasoned read the record supports but does not state outright — *a lead, not a verdict.* |
| `[reference]` | From a secondary/public-domain source (books, surveys), never promoted to verified. |
| `[open]` | An unanswered question, a gap, or withheld material — named, not hidden. |

Numbers are sacred. Uncertain scan transcriptions are written `~12345` and stay
that way — the marker is research metadata, never silently dropped. Precision
*is* the message: a figure that exact — `$14,223,081`, `pp. 317–328`, `0.2 cfs`
— is the tell.

---

## What it does

### Document pipeline

Three stages under [`src/watermark/pipeline/`](src/watermark/pipeline/):

```
ingest  →  extract  →  analyze
```

**`watermark ingest`** — walks [`data/documents/`](data/documents/),
inventories source files by collection (`aedg/`, `oepa/`, `recorder/`, …),
emits a manifest.

**`watermark extract <doc_id> --kind <kind> --pdf-page <N>`** — a hybrid vision
read. The OCR text layer (pypdf) is a hint only; its digits are unreliable on
degraded scans (`$109,307.69` comes through as `$108.307.89`). A 300 DPI render
(pypdfium2) goes to a forced-tool-use Claude call that reads every figure off
the *image*, resolved against an auto-detected format `Profile`. The output is a
Pydantic-validated, contractor-agnostic `Estimate` — dynamic `sections` and
`markups`, construction subtotal, total — written to
[`data/extracted/`](data/extracted/). `--detail` adds per-section line items
(item, description, quantity, unit, rate, extended amount), cross-checked against
section subtotals on the way in. Adding a contractor is a `Profile` registration,
not a model change.

**`watermark reconcile`** — a deterministic arithmetic check: section roll-ups,
markup rates, totals. It surfaces transcription errors and budgeting
discrepancies with no model call at all.

### Research agent

**`watermark research run`** drives a Claude Agent SDK loop over the extracted
corpus, backed by **25 in-process MCP tools** that expose real committed data —
the agent inspects the record, it does not invent it:

| Tool group | Tools |
|---|---|
| Corpus | `list_documents`, `list_extractions`, `read_extraction`, `retrieve_corpus` |
| Estimates | `reconcile_summary`, `reconcile_estimate`, `program_overview` |
| Record | `timeline`, `entities` |
| Hydrology | `hydrology_balance`, `stormwater_runoff`, `hydrology_scenario`, `storm_plan_inventory`, `sanitary_basis`, `tier1_swmm` |
| Web | `search_web`, `fetch_url` |
| OEPA | `discover_oepa_permits`, `fetch_oepa_permit` |
| Findings & issues | `report_novel_finding`, `list_site_issues`, `comment_on_pr`, `add_label`, `remove_label`, `set_issue_state` |

Tools resolve per the active `--site`. Off the Lima reference build they serve
the active site's own corpus or return an honest "not yet available" notice —
they never silently fall through to Lima's data.

**`watermark research run --recipe site-onboard`** is a structured first pass
that directs the agent across six coverage areas: NPDES/permit profile,
GIS/parcels, water-grid data, facility/RSEI toxics, economic ledger, and
hypothesis assessment. It discovers and fetches new OEPA DAM permit PDFs on its
own. **`watermark research publish`** promotes findings to GitHub issues under a
`kind/area/status` label taxonomy.

### Hydrology and water balance

[`src/watermark/hydrology/`](src/watermark/hydrology/) runs water-balance and
stormwater models of the municipal loop. Connectors pull **live public data**:

| Source | What |
|---|---|
| USGS NWIS | Streamflow, 7Q10 low-flow |
| NOAA Atlas-14 | Rainfall frequency (DDF curves) |
| EPA ECHO | NPDES permit inventory, DMRs |
| NASA POWER | Surface met data for ET calculation |
| EIA-861 | Utility service territory and sales |
| PJM | LMP, interchange, generation |

Every connector reads through an on-disk cache with a TTL and a committed-fixture
fallback, so `mise run test` never touches the network.

### Reference datasets

[`data/reference/`](data/reference/) holds authoritative external data —
committed, regenerable from a `watermark` subcommand, and documented with source
and gaps in a per-folder `README.md`:

- `echo/` — EPA ECHO NPDES discharger inventory (Maumee basin)
- `hydrology/` — USGS flow and NOAA rainfall reference values
- `rsei/` — EPA RSEI facility toxics scores
- `economics/`, `eia/` — utility baselines, USASpending federal outlays
- `periplus/` — parcel geometry, road-corridor GIS

### The site network

**23 sites registered across 7 basins.** Lima is the live reference; the rest
are registered profiles at varying readiness — *registered is not live.*

| Basin | Sites |
|---|---|
| Maumee | **Lima**, Findlay, Fort Wayne, Van Wert, Toledo, Defiance, Bryan, Ottawa |
| Great Miami | Urbana, Springfield, Wright-Patterson AFB, Hamilton·Middletown, Troy·Piqua, Sidney, Greenville |
| Little Miami | Xenia, Wilmington |
| Scioto | New Albany, Columbus, Piketon |
| Muskingum | Coshocton |
| Sandusky | Sandusky |
| Ohio Brush Creek | West Union |

Each site is a `SiteProfile` in
[`watermark.sites.SITES`](src/watermark/sites/) carrying every per-site knob
(USGS gages, county FIPS, GIS URLs, EIA utility number, output relpaths). The
frontend registry mirrors it in [`web/src/lib/sites.ts`](web/src/lib/sites.ts).
Onboard a new site with `watermark onboard <slug>` (runbook:
[docs/onboarding.md](docs/onboarding.md)). Promotion to `selectable` in the
frontend stays a manual, parity-gated edit — a thin site **degrades, it doesn't
break**: sections lock and surface a needs board rather than faking a value.

### Public site

The site builds in two tiers. The **data tier** ([`watermark.site`](src/watermark/site/),
`watermark export`) emits a typed content bundle — JSON feeds plus a
`manifest.json` stamped with `CONTRACT_VERSION` (currently **1.15.0**) — from the
extracted corpus. The **presentation tier** ([`web/`](web/)) is an Astro + MDX
static site that reads that bundle at build time; deck.gl map and graph views are
the only React islands, and charts are a hand-rolled SVG library. The frontend
classifies each section `available | locked` from feed counts in the manifest,
so a thin site degrades gracefully. **Cloudflare Pages** hosts it, with Pages
Functions (`/api/submit`, `/api/ask`) deploying alongside. See
[web/README.md](web/README.md).

---

## Data layout

```
data/
  documents/    Raw originals, exactly as received — never edited (Git LFS for PDFs/scans)
                  aedg/          engineering cost estimates
                  oepa/<site>/   Ohio EPA NPDES permits & fact sheets
                  recorder/      property deeds & recorder filings
                  commissioners/ county commission minutes
                  idem/<site>/   Indiana IDEM permit docs
                  legal/         web captures & legal exhibits
  extracted/    Reviewed, structured YAML — the committed, durable artifact
  reference/    Authoritative external datasets (each with a README + source)
  entities/     Resolved people & points-of-interest graph
  hypotheses/   Per-site hypothesis store (boom-origin × site)
  research/     Agent finding manifests and leads (data/research/<site>/)
  site/         Export feeds and bundle (data/site/bundle/ — built by watermark export)
  cache/        Regenerable API responses — git-ignored
```

`data/documents/**` is **immutable, chain-of-custody source** — never alter a
byte, never rename a malformed filename in place (record the canonical name in an
alias manifest instead). Large binaries are **versioned via Git LFS**; cloning
requires `git lfs install` for the full documents, otherwise you get lightweight
pointer files.

---

## Quickstart

```bash
mise install          # Python 3.11, uv, node 24, git-lfs
mise run setup        # uv sync --extra dev + git lfs install
cp .env.example .env  # set ANTHROPIC_API_KEY

watermark ingest
watermark reconcile roundabouts.summary.opc.yaml     # no API key needed
watermark --site lima research run --recipe site-onboard
```

The reference extraction target is the six Tetra Tech OPC estimates at pp.
317–328 of `data/documents/aedg/PRR-01-bundle.ocr.pdf`
([`data/extracted/aedg/roundabouts.*.opc.yaml`](data/extracted/aedg/)).
`mise run check` is the gate to run before declaring done
(`mise run //web:check` for `web/` changes, `mise run ci` for both).

See [DEVELOPMENT.md](DEVELOPMENT.md) for the full task reference and
[CONTRIBUTING.md](CONTRIBUTING.md) for data conventions and the contribution
workflow.

---

## Design

Watermark has a house **documentary design system** — bone paper, one forest
signal, square corners, no shadows, Archivo for prose and IBM Plex Mono for
every load-bearing figure. Indigo encodes data; the evidence palette only ever
encodes evidence (verified → forest, inference → amber, open → muted, scope-gap →
oxblood, key figure → highlight). The wordmark's one green period is the whole
system in a single mark. The full system and tokens live in [`design/`](design/),
mirrored from the Watermark Design System.

> The voice, everywhere: plain, exact, quietly serious. It never sells and never
> spins — it earns trust by showing its work. We treat every submission as a
> **lead, not a verdict.**

---

## Naming

The platform is **Watermark**; `watermark` is the only installed command. **BOSC**
is the project codename and survives only as vocabulary — the `/bosc` site
re-root for the Lima reference build, the repo name, `bosc-`-prefixed
Lima-specific filenames — never as an executable. Spun out from Periplus.
