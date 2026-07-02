# CLAUDE.md — `watermark.agent`

Wraps the Claude Agent SDK and the Anthropic Messages API. Defers to the root
[`CLAUDE.md`](../../../CLAUDE.md) for global rules.

- **Two distinct surfaces, don't conflate them:**
  - `client.py` — the open-ended **research agent** (Agent SDK). Use for free-form
    Q&A over already-extracted data.
  - `extractor.py` — a **single-shot, deterministic** structured extraction
    (Messages API + forced tool use + Pydantic validation). It is *not* the Agent
    SDK on purpose: that makes vision extraction predictable and unit-testable.
- `tools.py` — in-process tools exposed to the research agent via an SDK MCP server.
  Each tool is a **thin, deterministic adapter over the pipeline** (read real data,
  never fabricate) and must return the MCP shape
  `{"content": [{"type": "text", "text": ...}]}`.
  - **Read-side resolves per active site (#424).** The extraction-reading tools
    (`list_extractions`, `read_extraction`, `program_overview`, `reconcile_*`) resolve the
    **active site's own** corpus: the whole `data/extracted/` tree for the corpus home
    (`_CORPUS_HOME` = Lima), else that site's subtree (`data/extracted/<slug>/`) via
    `_site_extracted_root` — so a per-site run reads its own record, never another site's,
    and `_scoped(...)` labels whose corpus it is. `entities` and `timeline` also resolve
    per active site via `load_corpus(settings)` — for non-Lima sites they return that site's
    own committed extractions (empty if none, not Lima's cross-site record). The hydrology
    `list_documents` is also per-site scoped (#899): off the corpus home it filters
    `data/documents/` to paths containing the active site slug (e.g.
    `data/documents/idem/fort-wayne/`); with no matching docs it returns a helpful empty
    message rather than a `_reference_only` notice. `storm_plan_inventory` (#901) resolves via
    `active_profile(settings).storm_inventory_relpath` — `None` for sites without a committed plan;
    `sanitary_basis` (#901) resolves `data/reference/hydrology/<site>/sanitary-basis.yaml` — `None`
    for sites without a committed basis. The remaining Lima-specific hydrology tools
    (`hydrology_balance`, `stormwater_runoff`, `hydrology_scenario`, `tier1_swmm`) still return a
    `_reference_only(...)` notice off-home — tracked in #900.
- Models come from `get_settings()` (`WATERMARK_MODEL` for research, `WATERMARK_EXTRACT_MODEL`
  for bulk extraction) — never hardcode a model id here.
- Figures come from the rendered **image**, not the OCR text layer; the extractor
  passes OCR text only as a hint.
