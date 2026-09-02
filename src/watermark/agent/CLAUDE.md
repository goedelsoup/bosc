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
  `mcp__yidam__*`), implementing the **frozen MCP tool contract** (RFC-0005), vendored beside it
  as `mcp_contract.json` (**contract 0.12.0**). The contract lists **13** tools across four
  tiers; BOSC serves **12** — the seven `core` ones (`retrieve` / `get_node` / `list_nodes` /
  `open_questions` / `claims` / `check_subject` / `claim_tags`), `neighbors` (`graph`), and
  `query` / `pack` / `estimate` / `licensed_edges` (`ontology`, since #2132). Descriptions and input schemas are **read from that file**, and the served list is
  **derived** from it by `served_tool_names()`, so a tool added upstream and not added here is
  an `ImportError` rather than a tool that quietly does not exist — which is exactly what the
  0.1.0 → 0.12.0 bump produced (#2127). **Never rename a tool or hand-write a schema here**;
  re-vendor with `mise run yidam-contract-sync` (CI proves the copy matches the pin — and the
  vendored `commit_vocabulary.json`, which is `check_subject`'s closed list, with it).

  **The one BOSC does not serve is declined honestly, not skipped.** `check_citation` is
  `dependencies`, and BOSC pins no tonpa dependency, so there is no far side for a citation to
  have drifted from. The contract's own words for that case: *"Optional is not absent: such a
  server declares false and its cases are skipped rather than passed."*

  **`ontology` is one capability for all four of its tools** — there is no way to serve
  `licensed_edges` and withhold `query`. #2132 flipped it to true by giving the ontology
  something to say: each class declares its properties and the relationships it licenses, with
  `edge_policy: exhaustive`, which is truthful because the mirror is **generated** — a
  relationship outside the declaration is a bug in `corpus_mirror`, not a coinage. The engine
  is `corpus_query.py`; this module keeps only the handlers. Three disciplines a shape-passing
  implementation gets wrong, each caught by an upstream case: a **rejection is an answer**, not
  an `isError`; an **absence is not a rejection** (`rejected` says the query is wrong,
  `absence` says the corpus is quiet, and at most one is non-null); and a **pack says why in
  its own `text`**, because a pack travels without the envelope and an empty one that explains
  nothing is a context window asserting the corpus has no view.

  Four rules the contract makes non-negotiable: `retrieve` is **one adaptive tool** carrying
  `degraded` on every response (never a keyword/vector pair — that makes the caller choose a
  vector space, its least informed decision), and since 0.4.0 carrying `degraded_reason`,
  `rejected` and `absence` with it — *why*, not only *whether*, because a bare boolean made a
  repo that never built an index and one whose binary cannot read its index look identical;
  `get_node` returns the **unified JSON model**, never a YAML render; the `open_questions`
  predicate is **frozen at three arms** (`?` label, `[open]` in the body, an open tag in a
  property the class declared `type: claim`) — no server may add a fourth, and the third arm is
  the one **this repository reported missing** (goedelsoup/yidam#127, settled by widening the
  contract); and `claims` **serves the tag or serves nothing** — there is no untagged arm, and
  `total` is always the count before `k`. `capabilities()` declares what BOSC backs (`graph`
  yes; `phases`/`sangha` no — they need a working yidam repo; `resources` no — SDK servers
  register tools only; `ontology`/`dependencies` no — see above). It serves
  the corpus mirror (`watermark.site.corpus_mirror`, Epic #1560) built **in-memory** for the
  active site (offline read of
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
