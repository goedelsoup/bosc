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
  - **Read-side resolves per active site (#424/#1504).** The extraction-reading tools
    (`list_extractions`, `read_extraction`, `program_overview`, `reconcile_*`) resolve the
    **active site's own** corpus via `_site_extracted_files` — the whole `data/extracted/` tree
    **minus every registered peer's subtree** (#1505) for the corpus home (`_CORPUS_HOME` = Lima),
    else the files in the site's `effective_corpus_scope`
    (the *same* `relpath_in_scope` predicate the export/retrieval paths use, so collection-prefixed
    records like `idem/fort-wayne/` and `oepa/urbana/` are seen, not just the bare `<slug>/` subdir).
    So a per-site run reads its own record, never another site's, and `_scoped(...)` labels whose
    corpus it is (naming the scope prefixes). Paths are shown/accepted relative to `data/extracted/`. `entities` and `timeline` also resolve
    per active site via `load_corpus(settings)` — for non-Lima sites they return that site's
    own committed extractions (empty if none, not Lima's cross-site record). The hydrology
    `list_documents` is also per-site scoped (#899): off the corpus home it filters
    `data/documents/` to paths containing the active site slug (e.g.
    `data/documents/idem/fort-wayne/`); with no matching docs it returns a helpful empty
    message rather than a `_reference_only` notice. `storm_plan_inventory` (#901) resolves via
    `active_profile(settings).storm_inventory_relpath` — `None` for sites without a committed plan;
    `sanitary_basis` (#901) resolves `data/reference/hydrology/<site>/sanitary-basis.yaml` — `None`
    for sites without a committed basis. `hydrology_balance` (#829) runs per-site for any site
    that has committed its own WWTP graph (`data/reference/<slug>/watch-items.geojson`) — else
    the `_reference_only(...)` notice (which would otherwise silently serve Lima's periplus
    graph); it site-scopes routing (`load_routing` reads `reference/hydrology/<slug>/routing.yaml`)
    and only carries a data-center campus node where a `bosc-fm2` discharge is committed. The
    remaining Lima-specific hydrology tools (`stormwater_runoff`, `hydrology_scenario`,
    `tier1_swmm`) still return a `_reference_only(...)` notice off-home — tracked in #900.
- `yidam_tools.py` — a **second** in-process SDK MCP server (`yidam`, namespace
  `mcp__yidam__*`), BOSC's Python realization of `yidam serve --mcp` (#1563). It serves the
  **yidam corpus mirror** (`watermark.site.corpus_mirror`, Epic #1560) — the committed corpus
  projected into `yidam://corpus/<class>/<name>` nodes — so the agent can `list` / `read` /
  `query` (keyword) / `semantic_search` (vector) nodes and run `open_questions` over the
  projected method-layer graph (entities, relationships, concepts, people, leads, hypotheses,
  `[open]` claims). It builds the mirror **in-memory** for the active site (offline read of
  committed corpus, cached per turn) rather than reading the git-ignored `.yidam/corpus/` tree,
  so it never depends on a prior `export`. `semantic_search` (#1564) queries the LanceDB vector
  index (`watermark.site.yidam_index`, `.yidam/index/`) — built by `watermark corpus-mirror
  --index` and lazily by this server on first use — over the **same** all-MiniLM-L6-v2 backend
  as the `/ask` embeddings + `retrieve_corpus` (`watermark.retrieval.get_provider`), so it is
  reconciled with them, not a competing index.
  The SDK's in-process server exposes **tools only** (no MCP resources), so the
  `yidam://corpus/*` "resources" are delivered as list/read tools (nodes still carry the URI).
  Wired into `client.py` via `enable_yidam` (default on, rides on `enable_tools`).
- Models come from `get_settings()` (`WATERMARK_MODEL` for research, `WATERMARK_EXTRACT_MODEL`
  for bulk extraction) — never hardcode a model id here.
- Figures come from the rendered **image**, not the OCR text layer; the extractor
  passes OCR text only as a hint.
