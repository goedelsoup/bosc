# CLAUDE.md — guidance for agents working in this repo

Project BOSC is an **agentic research platform** that deconstructs public-records
source documents (degraded scans, OCR PDFs) into reviewed structured data and
runs Claude-driven analysis over it. Spun out from Periplus.

## Architecture

Three-stage pipeline under `src/bosc/pipeline/`: **ingest → extract → analyze**.
The `src/bosc/agent/` layer wraps the Claude Agent SDK and exposes in-process
tools so the agent inspects real data. Entry point is the `bosc` Typer CLI
(`src/bosc/cli.py`).

## Conventions

- **Tooling:** mise manages the toolchain (Python 3.11, uv, node, git-lfs);
  `Brewfile` is the fallback. uv for envs/deps, ruff for lint+format, mypy
  `strict`, pytest. Run `mise run check` before declaring done.
- **Python 3.11+**, `from __future__ import annotations` at the top of modules.
- **Config:** never read `os.environ` directly — go through `bosc.config.get_settings()`.
  Settings are `BOSC_`-prefixed; the model default is `claude-opus-4-8`, bulk
  extraction uses `claude-sonnet-4-6`.
- **Models:** structured extractions are validated with the Pydantic models in
  `bosc.models`. Scan transcriptions may be **approximate**, written `~12345`
  in YAML; `ApproxInt`/`_coerce_number` handle that — preserve the marker in
  source data, don't silently drop it.

## Data discipline (important)

- `data/documents/**` is raw, immutable, and **versioned via Git LFS** for large
  binaries (see `.gitattributes`). Add new scan/PDF types to LFS tracking.
- `data/extracted/**` is the committed, reviewed artifact and what tests run on.
- When transcribing figures: dollar totals/subtotals are high-confidence; mark
  uncertain quantities `~`. **Never fabricate line items or sources.** Prefer
  omission over invention. Cite source page/file.

## What "extract" must achieve

The reference target is `data/extracted/roundabouts.*.opc.yaml`: the six Tetra
Tech OPC estimates at 0-based PDF pages **317 (summary), 318-327 (detail)** of
`data/documents/aedg/PRR-01-bundle.ocr.pdf` (printed sheets `pdf_page` 318-328).

The extract stage is **implemented as a hybrid read** (`bosc.pipeline.extract`):
OCR text layer (pypdf, hint only) + 300 DPI render (pypdfium2) → forced-tool-use
vision extraction (`bosc.agent.extractor.StructuredExtractor`) → Pydantic-
validated `EstimateExtraction` with provenance (`PageExtraction`). The OCR text
layer is badly garbled (e.g. `$109,307.69` → `$108.307.89`); **never trust its
digits — figures come from the image.** New extraction work should produce
faithful, reconcilable data, and `bosc reconcile` should pass (or surface a real
discrepancy worth flagging to the County Engineer).

`bosc extract --detail` extracts full per-section line items (`DetailExtraction`,
`LineItem`) and is checked with `analyze.reconcile_detail` (each section's line
items must roll up to its subtotal). `Number` (`models._coerce_number_keep`)
preserves int-vs-float for quantities/rates and tolerates the `~` marker.
