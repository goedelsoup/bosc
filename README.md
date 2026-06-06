# Project BOSC — Agentic Research Platform

A Python platform for **deconstructing public-records source documents** into
reviewed, structured, machine-checkable data — then running Claude-driven
agentic analysis over the result.

The driving example: the Project BOSC roadwork records (a privately funded
program with public-records exhibits), where degraded 300 DPI scans of
financial projections and engineering cost estimates must be read faithfully,
transcribed to structured YAML, and **reconciled arithmetically** so that
transcription errors and budgeting discrepancies surface automatically.

> Spun out from Periplus to keep BOSC's research, data, and tooling
> self-contained.

## In plain terms (for non-coders)

If you don't write software, here's the whole thing in a paragraph. This
repository is **two things in one box**:

1. **An archive of records.** The original public documents — scanned permits,
   engineering cost estimates, meeting minutes, deeds, saved web pages — live
   under [`data/documents/`](data/documents/), kept exactly as received and never
   edited. Careful typed-up versions of the numbers and facts inside them live
   under [`data/extracted/`](data/extracted/), in a structured, double-checkable
   form.
2. **A set of tools** (the code under [`src/`](src/bosc/)) that read those
   records, re-check the arithmetic, pull in supporting official datasets (for
   example the EPA's inventory of wastewater dischargers), and answer research
   questions about it all.

The rule that governs everything: **never invent a number or a source.** If a
figure can't be read off the page, or wasn't returned by an official database,
it's left blank and flagged — not guessed. Where a scanned number is hard to
read, it's marked approximate (`~`) rather than presented as exact.

You don't need to run any code to use the archive: browse
[`data/documents/`](data/documents/) for the originals and
[`data/extracted/`](data/extracted/) for the typed-up data. The
[Layout](#layout) section below is a plain-English map of where everything is.

## Pipeline

```
  data/documents/         data/extracted/
  (raw scans, PDFs)       (reviewed YAML)
        │                       │
        ▼                       ▼
   ┌─────────┐   ┌──────────┐   ┌──────────┐
   │ ingest  │──▶│ extract  │──▶│ analyze  │
   └─────────┘   └──────────┘   └──────────┘
   inventory     document →      reconcile +
   source docs   structured      agentic Q&A
                 data (agent)
```

| Stage | Module | What it does |
|-------|--------|--------------|
| **ingest** | `bosc.pipeline.ingest` | Walk `data/documents`, inventory source files into a manifest (`doc_id`, collection, size). No parsing. |
| **extract** | `bosc.pipeline.extract` | Drive the Claude agent to read a document and emit structured YAML; validate against `bosc.models`. The core deconstruction step. |
| **analyze** | `bosc.pipeline.analyze` | Deterministic reconciliation (section roll-ups, the 25% contingency, totals) **and** free-form agentic research questions. |

The **agent** layer (`bosc.agent`) wraps the [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview)
and exposes in-process tools (`reconcile_summary`, `read_extraction`,
`list_documents`, …) so the agent inspects real data instead of guessing.

## Quickstart

Toolchain is managed by [mise](https://mise.jdx.dev/) (Python 3.11, uv, node,
git-lfs). Without mise, `brew bundle` installs the same tools (see `Brewfile`).

```bash
mise install          # install pinned tools
mise run setup        # uv sync --extra dev + git lfs install + Claude Code CLI
cp .env.example .env  # add your ANTHROPIC_API_KEY

uv run bosc version
uv run bosc ingest                                   # inventory data/documents
uv run bosc reconcile roundabouts.summary.opc.yaml   # arithmetic checks (no API key needed)
uv run bosc extract <doc_id> --pdf-page 319 --write  # hybrid vision extraction of one sheet
uv run bosc ask "Which roundabout has the largest design fee, and why?"
```

### Extracting a cost sheet (hybrid read)

`bosc extract` reads one estimate page and writes a reviewed `*.opc.yaml`:

1. **OCR text layer** (pypdf) — a cheap structural hint; its digits are unreliable.
2. **300 DPI render** (pypdfium2) — the authoritative image.
3. **Profile resolve** — a format `Profile` is auto-detected from the OCR text
   (contractor name, document title) or set with `--profile`; it supplies the
   prompt vocabulary and markup convention.
4. **Vision read** — a Claude model (`BOSC_EXTRACT_MODEL`) is forced via tool use
   to populate a contractor-agnostic `Estimate` (a title + dynamic `sections`,
   each with line items and a subtotal + `markups` + construction subtotal +
   total), reading figures off the image and using the OCR text only as a hint.
   Pydantic-validated, tagged with `confidence`/`warnings`, and stamped with the
   `profile` used.

```bash
uv run bosc extract <doc_id> --pdf-page 319                 # auto-detect profile
uv run bosc extract <doc_id> --pdf-page 319 --profile tetratech --write
```

Pages are addressed by `--pdf-page` (1-based, the printed sheet number) or
`--page` (0-based PDF index). In the reference bundle the six estimates are
`--pdf-page 319..328`. After extraction, run `bosc reconcile` on the result to
catch transcription errors arithmetically.

**Generality.** Extraction dispatches by document `--kind` (`opc` today) and,
within OPC, by contractor **profile** (`bosc/profiles.py`). The `Estimate` model
and `analyze.reconcile_estimate` are format-agnostic — section taxonomy and
markup rate come from the data/profile, not hardcoded. Add a contractor by
registering a new `Profile`; no model changes.

**Summary vs. detail.** By default `extract` reads the section subtotals and
totals. Add `--detail` (`-d`) to extract the full per-section **line items**
(item number, description, quantity, unit, unit rate, extended amount) into a
`*.detail.opc.yaml`:

```bash
uv run bosc extract <doc_id> --pdf-page 319 --detail --write
```

Detail extractions are immediately checked **line-item → section subtotal**: the
extended amounts in each section must roll up to that section's subtotal, surfacing
a misread quantity or rate right away.

<details>
<summary>Without mise (Homebrew)</summary>

```bash
brew bundle                                  # python@3.11, uv, node, git-lfs
uv sync --extra dev && git lfs install --local
npm install -g @anthropic-ai/claude-code     # the Agent SDK drives this CLI
```
</details>

## Development

```bash
mise run check    # ruff check + ruff format --check + mypy + pytest
mise run fmt      # auto-fix lint + format
```

Or invoke the tools directly (`uv run ruff check .`, `uv run mypy`,
`uv run pytest`). Tests run offline against the committed extraction.

## Data policy

- `data/documents/**` — raw source material (scans/PDFs/web captures).
  **Versioned**, with large binaries (`*.pdf`, images) stored via **Git LFS**
  (see `.gitattributes`). Treated as immutable inputs — never edited.
- `data/extracted/**` — reviewed structured extractions of those documents.
  **Committed.** The durable research artifact and what the tests run against.
- `data/reference/**` — supporting datasets from *outside* sources (e.g. the EPA
  ECHO wastewater inventory, USGS/NOAA reference values, parcel geometry).
  **Committed**, and labeled with where each came from.
- `data/scenarios/**` — named what-if inputs for the water-balance model.
  **Committed.**
- `data/cache/` — regenerable downloads (e.g. saved API responses). Git-ignored.

Cloning requires Git LFS (`git lfs install`) to pull the full source documents;
without it you get lightweight pointer files.

See [data/README.md](data/README.md) for the extraction conventions (including
the `~approximate` marker for uncertain scan transcriptions).

## Layout

The repository has two halves: **`data/`** (the records and datasets) and
**`src/`** (the code that works on them). Everything else supports those.

### `data/` — the records and datasets

```
data/
  documents/    RAW originals, exactly as received — never edited:
                  recorder/      property deeds & recorder filings
                  oepa/          Ohio EPA NPDES permits & fact sheets
                  aedg/          engineering cost estimates (the scans we read)
                  commissioners/ county commission minutes & agendas
                  legal/         saved web pages & legal exhibits
                  permits/ plans/ regulatory/ sanitary/  supporting records
  extracted/    The same records, carefully typed up into structured,
                checkable form (YAML). The reviewed, durable artifact.
  reference/    Supporting datasets from outside sources:
                  echo/       EPA ECHO wastewater-discharger inventory (Maumee)
                  hydrology/  river-flow & rainfall reference values
                  periplus/   parcels, road-corridor geometry
  scenarios/    Named water-balance "what-if" inputs (baseline, buildout)
  cache/        Regenerable downloads (saved API responses). Not committed.
```

Each dataset folder has its own `README.md` explaining its source and columns —
for example [data/reference/echo/README.md](data/reference/echo/README.md)
documents the EPA wastewater inventory and its known gaps.

### `src/bosc/` — the code

```
src/bosc/
  cli.py          the `bosc` command — every task is a subcommand of it
  config.py       settings (env + .env) and where data lives
  models.py       the typed shapes that extracted data must fit
  profiles.py     per-contractor formats for reading cost estimates
  agent/          wraps Claude so it reads the real data instead of guessing
  documents/      opens PDFs and scanned engineering drawings
  pipeline/       the main stages run end to end:
                    ingest → extract → analyze, plus corpus, entities,
                    timeline, and hydrology assembly
  hydrology/      water-balance & stormwater modeling of the Lima water loop;
                    connectors/ pull live public data (USGS streamflow, NOAA
                    rainfall, EPA ECHO permits), with on-disk caching
  site/           builds the browsable web/ site from the corpus
tests/            offline tests (run against committed data + saved fixtures)
docs/             project notes; web/ + site/ hold the generated site
```

> **Reading the code as a non-coder:** start at the command you care about in
> `cli.py` (e.g. `bosc npdes` for the wastewater pull), then follow it into the
> matching module. Each file opens with a plain-language docstring saying what it
> does and why.
