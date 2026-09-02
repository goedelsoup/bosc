"""The yidam corpus mirror, served to the research agent as an in-process MCP backend (#1563).

This is BOSC's Python realization of ``yidam serve --mcp`` (Epic #1560, workstream E, E3):
it exposes the projected yidam corpus mirror — the ``yidam://corpus/<class>/<name>`` nodes
built by :mod:`watermark.site.corpus_mirror` (#1561/#1562) — to the in-app
:class:`~watermark.agent.client.ResearchAgent` so the agent can browse and query the
method-layer graph (entities, relationships, wiki concepts, profiled people, the leads board,
the boom-origin hypotheses, and the ``[open]`` claims) instead of re-deriving it from raw
extractions. It closes the deferred "method-layer → in-app research agent" wiring.

**This server implements the frozen MCP tool contract** (RFC-0005), vendored beside it as
``mcp_contract.json``. Names are bare — ``retrieve``, ``get_node``, ``list_nodes``,
``open_questions``, ``neighbors`` — because the server is already namespaced by its own name
in every client that mounts one (here: ``mcp__yidam__*``). Tool descriptions and input schemas
are read from that file rather than written here, so a tool added upstream and not added here
fails the conformance test instead of quietly not existing.

Before the freeze this server shared exactly **one name of five** with the Rust ``serve --mcp``
and the TypeScript tools: it prefixed everything ``yidam_``, split retrieval into a keyword tool
and a vector tool where the contract keeps one adaptive tool, returned a human YAML render where
the contract specifies a JSON node model, omitted the ``degraded`` flag entirely, and had no
``neighbors`` at all. An agent written against one server could not call another.

**Why tools and not MCP resources.** :func:`claude_agent_sdk.create_sdk_mcp_server` registers
**tools only** — there is no ``resources/*`` channel — so this server declares
``resources: false`` and serves ``list_nodes`` / ``get_node`` as its tool peers. That is the
contract's sanctioned shape for a tools-only server, and declaring it is what lets an agent read
the hole once instead of finding it through a tool-not-found error.

**What it serves.** The mirror is built **in-memory** for the active site via
:func:`watermark.site.corpus_mirror.build_mirror` — the same projection ``watermark
corpus-mirror`` / ``watermark export`` write to the git-ignored ``.yidam/corpus/`` tree, but
built fresh from the committed corpus so the backend never depends on a prior export having
run. It is an offline read of committed data (all entity-graph enrichments default off), so a
thin peer site still gets its always-present spine (the site anchor + the three network
hypotheses). The build is cached per ``(site, data_dir)`` so a multi-tool research turn
projects the corpus once.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from claude_agent_sdk import create_sdk_mcp_server, tool

from watermark.agent.tracing import traced_tool
from watermark.config import Settings, get_settings
from watermark.site.corpus_mirror import (
    CLASSES,
    Mirror,
    MirrorNode,
    build_mirror,
    resolve_link_target,
)
from watermark.site.yidam_index import YidamVectorIndex, default_index_dir, index_exists

YIDAM_SERVER_NAME = "yidam"

# The URI scheme a mirror node is addressed by — `yidam://corpus/<class>/<name>` (what a real
# `yidam serve --mcp` would expose as a resource). read/query accept the bare `<class>/<name>`
# id or this full URI interchangeably.
URI_SCHEME = "yidam://corpus/"

# The repo-relative root a node path is reported under (`.yidam/corpus/<class>/<name>.yml`).
_CORPUS_PREFIX = ".yidam/corpus/"

# Cap a single query's result window — the corpus is small (Lima ≈ 170 nodes), so this is a
# sanity bound on a caller-supplied `limit`, not a paging mechanism.
_MAX_QUERY_RESULTS = 100

_CLASS_LIST = "|".join(CLASSES)


def _text(payload: str) -> dict[str, Any]:
    """Wrap a string in the MCP tool-result content shape (matches ``watermark.agent.tools``)."""
    return {"content": [{"type": "text", "text": payload}]}


# --- the served mirror (built once per site, cached for the turn) ---------------------------
_MIRROR_CACHE: dict[tuple[str, str], Mirror] = {}


def _mirror(settings: Settings | None = None) -> Mirror:
    """The active site's corpus mirror, built (offline) once and cached per ``(site, data_dir)``."""
    settings = settings or get_settings()
    key = (settings.site, str(settings.data_dir))
    mirror = _MIRROR_CACHE.get(key)
    if mirror is None:
        mirror = build_mirror(settings)
        _MIRROR_CACHE[key] = mirror
    return mirror


def clear_mirror_cache() -> None:
    """Drop the cached mirrors + vector indexes — call between sites/corpus edits (the tests)."""
    _MIRROR_CACHE.clear()
    _INDEX_CACHE.clear()


# --- the served vector index (built/loaded once per site, cached for the turn) --------------
_INDEX_CACHE: dict[tuple[str, str], YidamVectorIndex] = {}


def _index(settings: Settings | None = None) -> YidamVectorIndex:
    """The active site's yidam vector index, opened once and cached per ``(site, data_dir)``.

    Lazily built from the in-memory mirror when the ``.yidam/index/`` table is absent, so
    ``yidam serve --mcp`` semantic search works even if ``watermark corpus-mirror --index``
    was never run. Reuses the shared embedding backend (:func:`get_provider`) so its vectors
    live in the same space as the ``/ask`` embeddings.
    """
    from watermark.retrieval.embeddings import get_provider

    settings = settings or get_settings()
    key = (settings.site, str(settings.data_dir))
    index = _INDEX_CACHE.get(key)
    if index is None:
        index = YidamVectorIndex(default_index_dir(settings), get_provider(settings))
        if not index.exists:
            index.build(_mirror(settings))
        _INDEX_CACHE[key] = index
    return index


# --- pure serving over an in-memory Mirror (independently testable) --------------------------
def node_uri(node: MirrorNode) -> str:
    """The node's ``yidam://corpus/<class>/<name>`` URI."""
    return f"{URI_SCHEME}{node.id}"


def normalize_id(raw: str) -> str:
    """Reduce any node reference to its canonical ``<class>/<name>`` id (or bare name).

    Accepts a ``yidam://corpus/<class>/<name>`` URI, a bare ``<class>/<name>`` id, a
    ``<name>.yml`` file path, or a **rendered relative link target** — a node's outgoing links
    serialize relative to its class dir, so a cross-class edge reads ``../<class>/<name>.yml``.
    Dropping the leading ``../`` traversal lets the agent follow a link straight into
    :func:`find_node`."""
    s = (raw or "").strip()
    if s.startswith(URI_SCHEME):
        s = s[len(URI_SCHEME) :]
    # A repository path — what `retrieve` and `open_questions` report as `path`. An id is
    # written by hand at least as often as it is copied, and an agent that read a path out of
    # one tool must be able to pass it to another.
    if s.startswith(_CORPUS_PREFIX):
        s = s[len(_CORPUS_PREFIX) :]
    while s.startswith("../"):
        s = s[len("../") :]
    s = s.strip("/")
    if s.endswith(".yml"):
        s = s[: -len(".yml")]
    return s


def find_node(mirror: Mirror, node_id: str) -> MirrorNode | None:
    """Resolve one node by ``<class>/<name>`` id / URI, falling back to a unique bare name."""
    want = normalize_id(node_id)
    for node in mirror.nodes:
        if node.id == want:
            return node
    by_name = [node for node in mirror.nodes if node.name == want]
    return by_name[0] if len(by_name) == 1 else None


def list_nodes(mirror: Mirror, *, node_class: str | None = None) -> list[MirrorNode]:
    """Every mirror node, optionally filtered to one class, in stable ``id`` order."""
    nodes = [n for n in mirror.nodes if node_class is None or n.node_class == node_class]
    return sorted(nodes, key=lambda n: n.id)


def query_nodes(
    mirror: Mirror, query: str, *, node_class: str | None = None, limit: int = 20
) -> list[MirrorNode]:
    """Rank nodes by a case-insensitive term match over label > description/name > meta.

    A whitespace-tokenized ``query``; label hits weigh most, then name/description, then the
    projected provenance meta. Empty/zero-score nodes are dropped; ties break on ``id``. A
    non-positive ``limit`` returns nothing; a positive one is capped at :data:`_MAX_QUERY_RESULTS`.
    """
    if limit <= 0:
        return []
    limit = min(limit, _MAX_QUERY_RESULTS)
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    if not terms:
        return []
    scored: list[tuple[int, MirrorNode]] = []
    for node in mirror.nodes:
        if node_class is not None and node.node_class != node_class:
            continue
        label = node.label.lower()
        name_desc = f"{node.name} {node.description}".lower()
        meta = str(node.meta).lower()
        score = 0
        for term in terms:
            if term in label:
                score += 3
            if term in name_desc:
                score += 2
            if term in meta:
                score += 1
        if score > 0:
            scored.append((score, node))
    scored.sort(key=lambda s: (-s[0], s[1].id))
    return [node for _, node in scored[:limit]]


def open_question_nodes(mirror: Mirror) -> list[MirrorNode]:
    """The still-open nodes — the in-memory peer of ``yidam open-questions``.

    **The predicate is frozen** (`mcp_contract.json`, `open_questions`), and at contract 0.12.0
    it is **three** arms: a node is open when its ``label`` starts with ``?``, when its body
    asserts an ``[open]`` claim, **or** when a property its class declared ``type: claim`` holds
    an open tag — in either spelling. No server may add a fourth, and none may add a blessed key
    name: matching a bare ``open`` under any key would make ``status: open`` on a ballot measure
    an open claim, and no corpus could opt out of that.

    **The third arm is the one BOSC reported.** It was two arms at the previous pin, and the
    mismatch — ``yidam open-questions`` reading a structured tag the MCP predicate forbade —
    was filed from here as `goedelsoup/yidam#127`. Upstream settled it by widening the contract
    rather than narrowing the CLI, and the note beside the arm names this corpus by measurement:
    *"the corpus that measured 26 open questions against this tool's 2, and reshaped its data to
    `[open]` to be seen at all."*

    The implementation below is unchanged and stays that way. BOSC's ``claim_tag`` is that
    property in substance, but ``_ont_yaml`` declares no properties, so a conforming read of the
    declaration finds nothing — and it does not need to, because
    :func:`watermark.site.corpus_mirror._claim_token` writes the bracketed token, which puts the
    tag in the serialized text where arm two reaches it. Two-arm and three-arm servers therefore
    return the identical set here, which is exactly what the contract says of a corpus that
    declares nothing. Measured across the re-pin: 31 nodes, before and after. #2132 declares the
    property and makes the third arm literal.
    """
    out: list[MirrorNode] = []
    for node in mirror.nodes:
        if node.label.startswith("?"):
            out.append(node)
            continue
        text = yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True)
        if "[open]" in text:
            out.append(node)
    return out


def node_edges(mirror: Mirror) -> list[tuple[str, str, str]]:
    """Every ``(from_id, to_id, relationship)`` in the mirror, targets resolved to node ids."""
    return [
        (node.id, resolve_link_target(node.node_class, link.target), link.relationship)
        for node in mirror.nodes
        for link in node.links
    ]


def neighbors_of(mirror: Mirror, node_id: str, depth: int = 1) -> list[dict[str, Any]]:
    """Nodes reachable from ``node_id`` within ``depth`` hops, following edges **both ways**.

    Breadth-first, so each node is reported once at its *shortest* hop, carrying the direction
    of the edge it was reached by. Undirected because half the interesting connections are
    inbound — it is the same reason the corpus has an ``orphan-in`` check at all, and a directed
    walk silently loses that half.
    """
    start = find_node(mirror, node_id)
    if start is None:
        return []
    by_id = {n.id: n for n in mirror.nodes}
    edges = node_edges(mirror)
    seen = {start.id}
    queue: list[tuple[str, int]] = [(start.id, 0)]
    found: list[dict[str, Any]] = []
    while queue:
        current, hop = queue.pop(0)
        if hop >= depth:
            continue
        step = [(to, rel, "out") for (frm, to, rel) in edges if frm == current]
        step += [(frm, rel, "in") for (frm, to, rel) in edges if to == current]
        for nxt, relationship, direction in step:
            if nxt in seen:
                continue
            seen.add(nxt)
            hit = by_id.get(nxt)
            found.append(
                {
                    "id": nxt,
                    "label": hit.label if hit else "",
                    "description": hit.description if hit else "",
                    "relationship": relationship,
                    "direction": direction,
                    "depth": hop + 1,
                }
            )
            queue.append((nxt, hop + 1))
    return found


# --- the frozen contract ---------------------------------------------------------------------
# Read from a vendored copy rather than restated in this file. The contract says why: *"This
# file is the only place the list lives; a harness that restates it is a second freeze, which is
# how three servers ended up sharing one name out of five capabilities."* Kept in sync with the
# pin by the CI corpus job, which diffs it against the yidam it checks out.
_CONTRACT: dict[str, Any] = json.loads(
    (Path(__file__).with_name("mcp_contract.json")).read_text(encoding="utf-8")
)


def contract() -> dict[str, Any]:
    """The frozen MCP tool contract (RFC-0005) this server implements."""
    return _CONTRACT


def _spec(name: str) -> dict[str, Any]:
    """One tool's frozen name, description and input schema."""
    for entry in _CONTRACT["tools"]:
        if entry["name"] == name:
            return dict(entry)
    raise KeyError(f"no tool {name!r} in the frozen contract")


def vector_ready(settings: Settings | None = None) -> bool:
    """Whether a built vector index is on disk for the active site.

    Deliberately does **not** build one. The old behaviour lazily embedded the whole mirror on
    first search, which meant an agent's first `retrieve` silently produced results from a space
    that had not existed a moment earlier — and, per RFC-0006, one whose weights differ from
    yidam's anyway. The contract's rule is the opposite: say `vector: false`, answer degraded,
    and let a human run `mise run corpus-vector-index` if they want the other arm.
    """
    settings = settings or get_settings()
    return index_exists(default_index_dir(settings))


# --- absence, rejection, and why a search was degraded ----------------------------------------
# Three fields the contract added at 0.4.0, and each answers a question the previous shape made
# unanswerable. They are constants rather than literals at each return so the vocabulary cannot
# drift between the arms — which is the whole complaint the fields were introduced to fix.

#: Why every `retrieve` on this server is degraded: the corpus has no vector index.
#:
#: `no_index`, deliberately, **not** `no_vector_support` — even though the light build this repo
#: pins genuinely cannot read one. The contract is explicit: *"the corpus is missing the
#: artefact, which is the repair either way, and pinning the nearer cause is what keeps this
#: case answerable identically by every build of every server."* Reporting the build's
#: limitation instead would make two repositories with the same repair look different.
_NO_INDEX = "no_index"


def _absent(code: str, instances: int) -> dict[str, Any]:
    """An empty answer that says which kind of nothing it is.

    ``instances`` is how many nodes were in scope for the search — the number that separates
    *"this corpus has nothing to say"* from *"this filter selected nothing to search"*.
    """
    return {"code": code, "instances": instances}


#: The capabilities that do not depend on runtime state, and so can be answered at import time.
#:
#: Kept separate from :func:`capabilities` deliberately: the served tool LIST is a function of
#: these alone (`retrieve` is core either way — `retrieve.vector` describes an index's state, not
#: whether the tool exists), and computing the list must not touch :func:`get_settings`. Doing so
#: at module scope poisons its ``lru_cache`` with the default site before the CLI's ``--site``
#: callback can set ``WATERMARK_SITE`` — which silently served one site's corpus under another
#: site's flag until it was caught.
_STATIC_CAPABILITIES: dict[str, Any] = {
    "graph": True,  # the mirror is a projected entity graph; edges are its point
    "phases": False,
    "sangha": False,
    "resources": False,
    # Backs the CLASS CONTRACT — what a class declares it may link to — and BOSC's does not
    # declare it. The mirror writes one `<class>.ont.yml` per class actually present, but each
    # is two lines (`class:` + `description:`): no `properties:`, no `edges:`. So the corpus
    # holds nodes and edges and an ontology that says nothing about either, which is precisely
    # the case the contract anticipates: *"it can back `graph` and not this. Optional is not
    # absent: such a server declares false and its cases are skipped rather than passed."*
    # Declaring true before `_ont_yaml` has something to say would pass 22 cases by accident.
    # #2132 is where this changes.
    "ontology": False,
    # `check_citation` resolves citations INTO a tonpa dependency — another corpus this one
    # pins and reads. BOSC pins none, so there is no far side for a span to have drifted from.
    "dependencies": False,
}


def capabilities(settings: Settings | None = None) -> dict[str, Any]:
    """What this server can actually back — filled honestly, not optimistically.

    `phases` and `sangha` read live `ma/*` / `rigpa/*` refs and elector positions from a working
    yidam repository; BOSC has neither, and no amount of projecting its corpus would produce
    them. `resources` is false because the Agent SDK's in-process servers expose **tools only**
    — there is no `resources/*` channel to serve the `yidam://` scheme over. Saying so is what
    lets an agent read the hole once instead of discovering it through a tool-not-found error on
    the call it cared about.
    """
    vector = vector_ready(settings)
    return {
        "contract": _CONTRACT["contract"],
        # The one dynamic entry: whether an index is built for the ACTIVE site, answered now
        # rather than at import. Never consulted to decide which tools are served.
        #
        # `reason` carries the same value `degraded_reason` will carry on every call, so a
        # client learns at connect time what it would otherwise learn one failed search later.
        # Null exactly when `vector` is true — the contract's rule, and the reason it is null
        # rather than absent is that a client testing the key must not have to distinguish
        # "not degraded" from "a server too old to say why".
        "retrieve": {"vector": vector, "reason": None if vector else _NO_INDEX},
        **_STATIC_CAPABILITIES,
    }


def served_tool_names() -> list[str]:
    """The contract tools this server backs: every ``core`` one, plus each declared capability.

    Derived from the contract rather than written beside it, so a tool added upstream and not
    added here fails the conformance test instead of quietly not existing.

    Takes no settings and must never need any: this runs at import time to build ``ALL_TOOLS``,
    and a :func:`get_settings` call here resolves — and caches — the wrong site.
    """
    caps = _STATIC_CAPABILITIES
    out = []
    for entry in _CONTRACT["tools"]:
        tier = entry.get("tier", "core")
        if tier == "core" or bool(caps.get(tier)):
            out.append(entry["name"])
    return out


def _json(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a contract response as the MCP text block, JSON-encoded.

    The envelope is the contract: a server returning its own YAML render hands every consumer a
    second format to parse, which is the drift the frozen list exists to stop.
    """
    return _text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False))


def _error(message: str) -> dict[str, Any]:
    """A tool-level failure the agent can read and react to."""
    return {"content": [{"type": "text", "text": message}], "isError": True}


def node_path(node_id: str) -> str:
    """The repository path a node id addresses — what `retrieve`/`open_questions` report."""
    return f".yidam/corpus/{node_id}.yml"


def _node_model(node: MirrorNode) -> dict[str, Any]:
    """One node in the unified model (RFC-0002).

    ``content`` carries the node's full YAML body — that is where BOSC's projected provenance
    (site / scope / claim_tag / source / issue / …) lives, and the contract reserves the field
    for exactly this. The typed fields beside it are the ones every server must agree on.
    """
    return {
        "id": node.id,
        "class": node.node_class,
        "label": node.label,
        "description": node.description,
        "content": yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True).rstrip(),
        "links": [
            {"target": link.target, "relationship": link.relationship} for link in node.links
        ],
    }


# --- tools (names, descriptions and schemas come from the contract) --------------------------
_RETRIEVE = _spec("retrieve")


@tool(_RETRIEVE["name"], _RETRIEVE["description"], _RETRIEVE["inputSchema"])
@traced_tool
async def retrieve(args: dict[str, Any]) -> dict[str, Any]:
    """One adaptive tool, not a split pair.

    Offering `query` and `semantic_search` as separate names made the caller decide which vector
    space it was in — the caller's least informed decision. `degraded` is present on **every**
    response; there is no third state.

    **Why, not only whether** (contract 0.4.0). `degraded_reason`, `rejected` and `absence` are
    required on every response too, and none of them is decoration: the bare boolean made a
    repository that never built an index and one whose index the binary cannot read look
    identical, and an empty `results` said nothing about whether the corpus was quiet, the query
    was empty, or the filter was wrong. Those have different repairs.

    A blank query is **not an error here** — it was, and the contract now says it is an
    `absence` with code ``query-no-terms``. That distinction is the tool's job: an agent that
    passed an empty string gets back the size of the corpus it failed to search, which is more
    useful than a refusal and is something it can act on.
    """
    args = args or {}
    query = str(args.get("query") or "").strip()
    k = max(1, int(args.get("k") or 5))
    node_class = args.get("class") or None

    settings = get_settings()
    mirror = _mirror(settings)

    # Resolved ONCE, before the early returns, and not restated in each arm. `degraded` is a
    # fact about this server's index, not about which branch answered — hardcoding it below
    # made the rejection and the blank-query arms report `no_index` on a site whose index IS
    # built, contradicting `capabilities()` in the same breath and telling the caller to build
    # an artefact it already has. The fixtures cannot catch that: they run on a corpus with no
    # index, where the wrong constant is accidentally right.
    vector = vector_ready(settings)
    reason = None if vector else _NO_INDEX

    # A class this corpus does not declare is REJECTED, not searched — a bad request, not an
    # empty result. BOSC can tell the difference because it knows its own class list, and the
    # two are different repairs: a rejection means fix the call, an absence means the corpus
    # has nothing. They are mutually exclusive; a rejection carries no absence and vice versa.
    if node_class is not None and node_class not in CLASSES:
        return _json(
            {
                "degraded": not vector,
                "degraded_reason": reason,
                "rejected": {
                    "code": "unknown-class",
                    "detail": f"unknown class {node_class!r}. Valid: {_CLASS_LIST}.",
                },
                "absence": None,
                "results": [],
            }
        )

    in_scope = sum(1 for n in mirror.nodes if node_class is None or n.node_class == node_class)
    if not query:
        return _json(
            {
                "degraded": not vector,
                "degraded_reason": reason,
                "rejected": None,
                "absence": _absent("query-no-terms", in_scope),
                "results": [],
            }
        )

    if vector:
        try:
            hits = _index(settings).query(query, limit=k, node_class=node_class)
            by_id = {n.id: n for n in mirror.nodes}
            results = [
                {
                    "path": node_path(hit.node_id),
                    "class": hit.node_class,
                    "label": hit.label,
                    "text": (
                        by_id[hit.node_id].description if hit.node_id in by_id else hit.description
                    ),
                    "score": round(float(hit.score), 6),
                }
                for hit in hits
            ]
            return _json(
                {
                    "degraded": False,
                    "degraded_reason": None,
                    "rejected": None,
                    "absence": None if results else _absent("no-term-match", in_scope),
                    "results": results,
                }
            )
        except Exception as exc:  # the index exists but would not answer — say so, do not guess
            log_hint = next(iter(str(exc).splitlines()), repr(exc))
            results = _keyword_results(mirror, query, k, node_class)
            return _json(
                {
                    "degraded": True,
                    "degraded_reason": _NO_INDEX,
                    "rejected": None,
                    "absence": None if results else _absent("no-term-match", in_scope),
                    "results": results,
                    "note": f"vector retrieval unavailable ({log_hint}); answered by keyword",
                }
            )

    results = _keyword_results(mirror, query, k, node_class)
    return _json(
        {
            "degraded": True,
            "degraded_reason": _NO_INDEX,
            "rejected": None,
            "absence": None if results else _absent("no-term-match", in_scope),
            "results": results,
        }
    )


def _keyword_results(
    mirror: Mirror, query: str, k: int, node_class: str | None
) -> list[dict[str, Any]]:
    """Keyword hits in the contract's result shape, scored 0..1 by term coverage."""
    terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]
    if not terms:
        return []
    scored: list[tuple[float, MirrorNode]] = []
    for node in mirror.nodes:
        if node_class is not None and node.node_class != node_class:
            continue
        haystack = f"{node.label} {node.description} {node.meta}".lower()
        hits = sum(1 for t in terms if t in haystack)
        if hits:
            scored.append((hits / len(terms), node))
    scored.sort(key=lambda s: (-s[0], s[1].id))
    return [
        {
            "path": node_path(node.id),
            "class": node.node_class,
            "label": node.label,
            "text": node.description,
            "score": round(score, 6),
        }
        for score, node in scored[:k]
    ]


_GET_NODE = _spec("get_node")


@tool(_GET_NODE["name"], _GET_NODE["description"], _GET_NODE["inputSchema"])
@traced_tool
async def get_node(args: dict[str, Any]) -> dict[str, Any]:
    node_id = str((args or {}).get("id") or "")
    if not node_id:
        return _error("missing required argument: id")
    node = find_node(_mirror(get_settings()), node_id)
    if node is None:
        return _error(f"node not found: {node_id}")
    return _json(_node_model(node))


_LIST_NODES = _spec("list_nodes")


@tool(_LIST_NODES["name"], _LIST_NODES["description"], _LIST_NODES["inputSchema"])
@traced_tool
async def list_nodes_tool(args: dict[str, Any]) -> dict[str, Any]:
    node_class = (args or {}).get("class") or None
    if node_class is not None and node_class not in CLASSES:
        return _error(f"unknown class {node_class!r}. Valid: {_CLASS_LIST}.")
    nodes = list_nodes(_mirror(get_settings()), node_class=node_class)
    return _json(
        {
            "nodes": [
                {
                    "id": n.id,
                    "class": n.node_class,
                    "label": n.label,
                    "description": n.description,
                }
                for n in nodes
            ]
        }
    )


_OPEN_QUESTIONS = _spec("open_questions")


@tool(_OPEN_QUESTIONS["name"], _OPEN_QUESTIONS["description"], _OPEN_QUESTIONS["inputSchema"])
@traced_tool
async def open_questions(_args: dict[str, Any]) -> dict[str, Any]:
    nodes = open_question_nodes(_mirror(get_settings()))
    return _json(
        {"open_questions": [{"id": n.id, "label": n.label, "path": node_path(n.id)} for n in nodes]}
    )


# --- the evidence vocabulary, and the claims made in it ---------------------------------------
# `claims`, `claim_tags` and `open_questions` all rest on one predicate, and the contract insists
# on that: *"the same predicate `status`, `open-questions` and `lint` use, and deliberately not
# the SDK's `extract_claims` — that is a line-oriented parser for the markdown node model, and
# over a YAML instance it reads `class: gage` as an untagged claim."*

#: The three standings, in the order the contract lists them. There is no fourth.
STANDINGS = ("verified", "inference", "open")

#: The bracketed form, which is the ONLY form scanned for in prose. A bare `open` in a sentence
#: is a word — matching it under any key would make `status: open` on a ballot measure a claim.
_TAG_IN_PROSE = re.compile(r"\[(" + "|".join(STANDINGS) + r")\]")

#: A fenced block is masked before scanning; inline code deliberately is NOT.
#:
#: The asymmetry is measured, not stylistic. The contract records that a server which filtered
#: backticked tags as mentions *"would understate a real corpus's open questions fivefold; that
#: rule was measured and thrown out."* Under-reporting `[open]` is promotion just as surely as
#: over-reporting `[verified]` — a corpus with its open questions silenced reads as settled.
_FENCED = re.compile(r"```.*?```", re.S)

#: A tag that is being TALKED ABOUT rather than asserted. Four shapes, each from the contract:
#: pluralised, named by the noun after it, the object of a past-tense reporting verb, or negated.
_MENTION_AFTER = re.compile(
    r"^(s\b|es\b|\s+(tag|tags|claim|claims|standing|standings|marker|markers|token|tokens)\b)",
    re.I,
)
_MENTION_BEFORE = re.compile(
    r"(?:\b(?:not|never|no|neither|nor|without)\s+"
    r"|\b(?:reported|marked|tagged|called|labelled|labeled|described|treated|read)\s+"
    r"(?:as\s+)?)$",
    re.I,
)

#: BOSC's own claim-carrying property.
#:
#: In substance this is the contract's third arm — *"a property the node's class declared
#: `type: claim`"* — and it is the arm upstream added in response to goedelsoup/yidam#127, filed
#: from here. In form it is not yet: `_ont_yaml` writes `class:` and `description:` and nothing
#: else, so no class DECLARES it and a conforming reader of the declaration would find nothing.
#: Serving it anyway is not widening the predicate — `_claim_token` writes the bracketed token,
#: so the tag is in the serialized text and the prose arm reaches it either way. Naming the
#: property here is what lets a claim carry the node's own description as its text rather than
#: the YAML line the tag happens to sit on. #2132 declares it and closes the gap.
_CLAIM_PROPERTY = "claim_tag"


def _standing_of(raw: Any) -> str | None:
    """The standing a claim-property value carries, in either spelling, or ``None``."""
    token = str(raw or "").strip().strip("[]").lower()
    return token if token in STANDINGS else None


def _prose_of(node: MirrorNode) -> list[str]:
    """The node's free-text fields — where a prose claim can live.

    Not the whole YAML dump. Scanning the serialization would attribute a claim to the
    `claim_tag:` key line, which is the node's standing rather than a sentence asserting
    anything, and would double-count it against the property arm below.
    """
    out = [node.description]
    out += [str(v) for k, v in node.meta.items() if k != _CLAIM_PROPERTY and isinstance(v, str)]
    return [t for t in out if t]


def _tagged_sentences(text: str) -> list[tuple[str, str]]:
    """``(standing, sentence)`` for each asserted claim in ``text``; mentions dropped."""
    masked = _FENCED.sub(" ", text)
    out: list[tuple[str, str]] = []
    for match in _TAG_IN_PROSE.finditer(masked):
        if _MENTION_AFTER.match(masked[match.end() :]):
            continue
        if _MENTION_BEFORE.search(masked[: match.start()]):
            continue
        # The claim is the sentence the tag sits in — "a node is 2-10 sentences; a claim is one".
        start = max(masked.rfind(". ", 0, match.start()) + 1, 0)
        end = masked.find(". ", match.end())
        sentence = masked[start : end + 1 if end != -1 else len(masked)].strip()
        out.append((match.group(1), sentence))
    return out


def _sources_of(node: MirrorNode) -> list[str]:
    """The node's cited sources, however the projection spelled them (`source` / `sources`)."""
    raw = node.meta.get("sources") or node.meta.get("source") or []
    return [str(r) for r in (raw if isinstance(raw, list) else [raw]) if r]


def node_claims(node: MirrorNode) -> list[dict[str, Any]]:
    """Every claim ``node`` asserts, in the contract's shape.

    **Serve the tag or serve nothing.** There is no untagged arm: an unmarked sentence is prose,
    and `get_node` is where prose lives. Inventing a fourth standing for it would turn every
    aside in the corpus into a weakly-evidenced claim.

    ``standing`` is the claim's OWN tag — never a minimum over the claims it rests on. No
    implementation computes that, and a field named for it would manufacture a tier nobody
    derived.
    """
    common = {
        "node": node.id,
        "class": node.node_class,
        "scope": node.meta.get("scope"),
        "sources": _sources_of(node),
    }
    out: list[dict[str, Any]] = []
    # The property arm contributes the node's own standing ONCE, and its text is the node's
    # description: the assertion the standing attaches to, not the key the tag was written on.
    if (standing := _standing_of(node.meta.get(_CLAIM_PROPERTY))) is not None:
        out.append({"text": node.description or node.label, "standing": standing, **common})
    for standing, sentence in _tagged_sentences(" ".join(_prose_of(node))):
        out.append({"text": sentence, "standing": standing, **common})
    return out


_CLAIMS = _spec("claims")


@tool(_CLAIMS["name"], _CLAIMS["description"], _CLAIMS["inputSchema"])
@traced_tool
async def claims(args: dict[str, Any]) -> dict[str, Any]:
    """Assertions, not documents — what the corpus takes as X, without its prose.

    `total` is the count **before** `k`, always. An agent told *here are 5 claims* and one told
    *here are 5 of 41* can take different next actions, and only the second can decide to ask
    for more.

    Local corpus only. A dependency's assertions are its corpus's; BOSC pins none, which is the
    same fact `capabilities()["dependencies"]` reports.
    """
    args = args or {}
    standing = args.get("standing") or None
    if standing is not None and standing not in STANDINGS:
        return _error(f"unknown standing {standing!r}. Valid: {', '.join(STANDINGS)}.")
    node_class = args.get("class") or None
    if node_class is not None and node_class not in CLASSES:
        return _error(f"unknown class {node_class!r}. Valid: {_CLASS_LIST}.")
    only_node = args.get("node") or None
    k = max(1, int(args.get("k") or 50))

    found: list[dict[str, Any]] = []
    for node in _mirror(get_settings()).nodes:
        if node_class is not None and node.node_class != node_class:
            continue
        if only_node is not None and node.id != normalize_id(str(only_node)):
            continue
        found += [c for c in node_claims(node) if standing is None or c["standing"] == standing]
    return _json({"claims": found[:k], "returned": len(found[:k]), "total": len(found)})


_CLAIM_TAGS = _spec("claim_tags")

#: What each standing means. BOSC's own evidentiary discipline, which is the same vocabulary —
#: `.claude/skills/evidentiary-discipline` is the prose this tool deliberately does not replace.
_TAG_MEANINGS = {
    "verified": (
        "Asserted on a source in the record: a document, a dataset, or a reading of one that "
        "another person could repeat. Cite it beside the tag."
    ),
    "inference": (
        "A reading the evidence supports but does not establish. The step from the record to "
        "the claim is the author's, and it must be visible as one."
    ),
    "open": (
        "A question the corpus has not answered. Tagging it is what keeps it countable — a "
        "corpus with its open questions silenced reads as settled."
    ),
}


@tool(_CLAIM_TAGS["name"], _CLAIM_TAGS["description"], _CLAIM_TAGS["inputSchema"])
@traced_tool
async def claim_tags(_args: dict[str, Any]) -> dict[str, Any]:
    """The three tags, what each means, and how each may be written.

    **The prose stays.** This carries the CONTENT, which is what makes the vocabulary cheap to
    obey; the REASONING lives in `.claude/skills/evidentiary-discipline` and upstream's
    `agent-conduct.md`, which is what makes it arguable and revisable. A server must not let
    this become the only statement of the rule.
    """
    return _json(
        {
            "tags": [
                {
                    "standing": standing,
                    # A property the class typed `claim` accepts the bare token; prose is
                    # scanned for the bracketed one only.
                    "in_prose": f"[{standing}]",
                    "in_property": standing,
                    "meaning": _TAG_MEANINGS[standing],
                }
                for standing in STANDINGS
            ],
            "note": (
                "Write the tag alone. `[verified — Pearl 2009]` matches nothing and counts as "
                "no claim at all: it looks tagged to a reader and reads as bare assertion to "
                "every tool. Write the tag and put the citation beside it."
            ),
        }
    )


# --- the closed commit vocabulary -------------------------------------------------------------
# Vendored beside the contract (`mise run yidam-contract-sync`) rather than shelled out to the
# binary, because this tool must answer with no yidam on PATH — which is how the research agent
# runs. Read from the file for the same reason the contract is: a list restated here would be a
# second freeze, and this one has three certified implementations upstream already.
_VOCABULARY: list[dict[str, str]] = json.loads(
    (Path(__file__).with_name("commit_vocabulary.json")).read_text(encoding="utf-8")
)["verbs"]
_KIND_OF = {entry["verb"]: entry["kind"] for entry in _VOCABULARY}

_CHECK_SUBJECT = _spec("check_subject")


@tool(_CHECK_SUBJECT["name"], _CHECK_SUBJECT["description"], _CHECK_SUBJECT["inputSchema"])
@traced_tool
async def check_subject(args: dict[str, Any]) -> dict[str, Any]:
    """Whether a commit subject is in the closed vocabulary — asked before the commit exists.

    **Total, and never an error.** An unrecognized verb is a finding in the payload, not a failed
    call: the gate reports it at `warn` because history cannot be rewritten to fix a verb, and a
    tool that failed harder than the gate would assert a verdict nobody agreed to — after which
    an agent learns to stop asking.

    **A note on this repository.** BOSC writes conventional commits, not this vocabulary, and
    says so where it declines upstream's commit-vocabulary CI. Serving the tool anyway is
    deliberate: the served list is DERIVED from the contract precisely so a tool added upstream
    cannot quietly not exist, and withholding a handler for a `core` tool would reintroduce the
    drift that mechanism was built to stop. What it answers is *"what would yidam file this
    as"*, which is true regardless of what this repository does with the answer. Whether
    `check_subject` belongs behind a capability of its own is a question for upstream, filed as
    one, not something to settle by omission here.
    """
    subject = str((args or {}).get("subject") or "")
    violations: list[dict[str, str]] = []

    # `verb` is EVERYTHING before the first `: `, which is why a conventional-commits `(scope)`
    # suffix costs twice: `vendor(yidam)` is in no list, AND classification falls through to
    # epistemic, filing an operational commit as a change in understanding.
    verb = subject.split(": ", 1)[0] if ": " in subject else ""
    recognized = verb in _KIND_OF
    # Operational is the explicit list; everything else classifies as epistemic. Total by
    # construction — every subject gets a kind, including ones predating the vocabulary.
    kind = _KIND_OF.get(verb, "epistemic")

    if not verb:
        violations.append(
            {
                "rule": "no-verb",
                "severity": "warn",
                "message": "no `verb: ` prefix — the subject names no act.",
            }
        )
    elif not recognized and re.match(r"^[^(\s]+\([^)]*\)$", verb):
        # Its own rule, not folded into `unrecognized-verb`: it has a known cause and a known
        # fix, and a caller told only `recognized: false` would go looking for a verb that is
        # already correct.
        violations.append(
            {
                "rule": "scope-suffix",
                "severity": "warn",
                "message": (
                    f"`{verb}` carries a conventional-commits scope suffix. The verb is "
                    f"everything before the first `: `, so drop the parenthesis: "
                    f"`{verb.split('(', 1)[0]}: …`."
                ),
            }
        )
    elif not recognized:
        violations.append(
            {
                "rule": "unrecognized-verb",
                "severity": "warn",
                "message": f"`{verb}` is not in the closed vocabulary.",
            }
        )

    return _json(
        {
            "text": subject,
            "verb": verb,
            "kind": kind,
            "recognized": recognized,
            "violations": violations,
            # The closed list travels WITH the verdict, so a caller that got it wrong can
            # correct without a second call — which is the whole point of asking beforehand.
            "vocabulary": _VOCABULARY,
        }
    )


_NEIGHBORS = _spec("neighbors")


@tool(_NEIGHBORS["name"], _NEIGHBORS["description"], _NEIGHBORS["inputSchema"])
@traced_tool
async def neighbors(args: dict[str, Any]) -> dict[str, Any]:
    args = args or {}
    node_id = str(args.get("id") or "")
    if not node_id:
        return _error("missing required argument: id")
    mirror = _mirror(get_settings())
    start = find_node(mirror, node_id)
    if start is None:
        return _error(f"node not found: {node_id}")
    depth = max(1, int(args.get("depth") or 1))
    return _json({"id": start.id, "neighbors": neighbors_of(mirror, start.id, depth)})


# The served list, in contract order. Assembled from `served_tool_names()` so a capability this
# server stops backing drops its tool rather than leaving one that answers wrongly.
_HANDLERS: dict[str, Any] = {
    "retrieve": retrieve,
    "get_node": get_node,
    "list_nodes": list_nodes_tool,
    "open_questions": open_questions,
    "claims": claims,
    "check_subject": check_subject,
    "claim_tags": claim_tags,
    "neighbors": neighbors,
}
ALL_TOOLS = [_HANDLERS[name] for name in served_tool_names()]
ALLOWED_TOOL_NAMES = [f"mcp__{YIDAM_SERVER_NAME}__{t.name}" for t in ALL_TOOLS]


def build_server() -> Any:
    """Create the in-process SDK MCP server serving the yidam corpus mirror to the agent."""
    return create_sdk_mcp_server(name=YIDAM_SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)
