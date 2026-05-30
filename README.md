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
uv run bosc ask "Which roundabout has the largest design fee, and why?"
```

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

- `data/documents/**` — raw source material (scans/PDFs). **Versioned**, with
  large binaries (`*.pdf`, images) stored via **Git LFS** (see `.gitattributes`).
  Treated as immutable inputs.
- `data/extracted/**` — reviewed structured extractions. **Committed.** This is
  the durable research artifact and what the tests run against.
- `data/cache/`, `data/scratch/` — regenerable working files. Git-ignored.

Cloning requires Git LFS (`git lfs install`) to pull the full source documents;
without it you get lightweight pointer files.

See [data/README.md](data/README.md) for the extraction conventions (including
the `~approximate` marker for uncertain scan transcriptions).

## Layout

```
src/bosc/
  config.py        # settings (env + .env), data paths
  logging.py       # structlog setup
  models.py        # typed OPC extraction models (+ approx-number coercion)
  cli.py           # `bosc` Typer CLI
  agent/
    client.py      # ResearchAgent — Claude Agent SDK wrapper
    tools.py       # in-process MCP tools over the pipeline
  pipeline/
    ingest.py  extract.py  analyze.py
tests/
```
