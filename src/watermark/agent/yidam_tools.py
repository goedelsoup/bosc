"""The yidam corpus mirror, served to the research agent as an in-process MCP backend (#1563).

This is BOSC's Python realization of ``yidam serve --mcp`` (Epic #1560, workstream E, E3):
it exposes the projected yidam corpus mirror — the ``yidam://corpus/<class>/<name>`` nodes
built by :mod:`watermark.site.corpus_mirror` (#1561/#1562) — to the in-app
:class:`~watermark.agent.client.ResearchAgent` so the agent can browse and query the
method-layer graph (entities, relationships, wiki concepts, profiled people, the leads board,
the boom-origin hypotheses, and the ``[open]`` claims) instead of re-deriving it from raw
extractions. It closes the deferred "method-layer → in-app research agent" wiring.

**Why a second server, and why tools (not MCP resources).** The agent wires in-process SDK
MCP servers via :func:`claude_agent_sdk.create_sdk_mcp_server`, which registers **tools only**
— it has no resource surface, and the Agent SDK's ``query()`` loop does not auto-attach MCP
resources to the model the way it does tools. So the ``yidam://corpus/*`` "resources" the
issue names are delivered as list/read **tools** (nodes are still addressed by their
``yidam://corpus/<class>/<name>`` URI), alongside the ``open_questions`` and ``query`` tools.
This is a dedicated ``yidam`` server so its namespace (``mcp__yidam__*``) stays distinct from
the ``watermark`` extraction/hydrology tools in :mod:`watermark.agent.tools`.

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

import re
from typing import Any

import yaml
from claude_agent_sdk import create_sdk_mcp_server, tool

from watermark.agent.tracing import traced_tool
from watermark.config import Settings, get_settings
from watermark.site.corpus_mirror import CLASSES, Mirror, MirrorNode, build_mirror

YIDAM_SERVER_NAME = "yidam"

# The URI scheme a mirror node is addressed by — `yidam://corpus/<class>/<name>` (what a real
# `yidam serve --mcp` would expose as a resource). read/query accept the bare `<class>/<name>`
# id or this full URI interchangeably.
URI_SCHEME = "yidam://corpus/"

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
    """Drop the cached mirrors — call between sites/corpus edits (used by the tests)."""
    _MIRROR_CACHE.clear()


# --- pure serving over an in-memory Mirror (independently testable) --------------------------
def node_uri(node: MirrorNode) -> str:
    """The node's ``yidam://corpus/<class>/<name>`` URI."""
    return f"{URI_SCHEME}{node.id}"


def normalize_id(raw: str) -> str:
    """Accept a ``yidam://corpus/<class>/<name>`` URI, a bare ``<class>/<name>`` id, or a
    ``<name>.yml`` file path and reduce it to the canonical ``<class>/<name>`` id (or bare name)."""
    s = (raw or "").strip()
    if s.startswith(URI_SCHEME):
        s = s[len(URI_SCHEME) :]
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


def _haystack(node: MirrorNode) -> str:
    """The searchable text for a node — label, description, name, and its projected meta."""
    return " ".join((node.label, node.description, node.name, str(node.meta))).lower()


def query_nodes(
    mirror: Mirror, query: str, *, node_class: str | None = None, limit: int = 20
) -> list[MirrorNode]:
    """Rank nodes by a case-insensitive term match over label > description/name > meta.

    A whitespace-tokenized ``query``; label hits weigh most, then name/description, then the
    projected provenance meta. Empty/zero-score nodes are dropped; ties break on ``id``.
    """
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
    return [node for _, node in scored[: max(1, limit)]]


def open_question_nodes(mirror: Mirror) -> list[MirrorNode]:
    """The still-open nodes — the in-memory peer of ``render_open_questions``.

    Faithful to :func:`watermark.site.corpus_mirror.render_open_questions`: a node is open when
    its ``label`` starts with ``?``, it carries ``claim_tag: open`` (BOSC's structured ``[open]``
    marker on leads + open hypothesis cells), or its serialized node text contains ``[open]``.
    """
    out: list[MirrorNode] = []
    for node in mirror.nodes:
        if node.label.startswith("?") or node.meta.get("claim_tag") == "open":
            out.append(node)
            continue
        text = yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True)
        if "[open]" in text:
            out.append(node)
    return out


# --- rendering (node → the text a tool returns) ---------------------------------------------
def _render_node(node: MirrorNode) -> str:
    """One node as its ``yidam://corpus/...`` header + the exact YAML the mirror writes to disk."""
    body = yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True).rstrip()
    return f"# {node_uri(node)}\n{body}"


def _render_index(nodes: list[MirrorNode], *, site: str) -> str:
    """The list view — nodes grouped by class, one ``uri  label`` line each."""
    if not nodes:
        return f"No corpus nodes for site '{site}'."
    lines = [f"yidam corpus mirror — site '{site}' — {len(nodes)} node(s):"]
    for cls in CLASSES:
        in_class = [n for n in nodes if n.node_class == cls]
        if not in_class:
            continue
        lines.append(f"\n## {cls} ({len(in_class)})")
        lines.extend(f"- {node_uri(n)}  —  {n.label}" for n in in_class)
    return "\n".join(lines)


# --- tools ----------------------------------------------------------------------------------
@tool(
    "yidam_list_nodes",
    "List the active site's yidam corpus mirror nodes (the yidam://corpus/<class>/<name> "
    f"graph projected from the BOSC corpus), grouped by class ({_CLASS_LIST}). Pass node_class "
    "to list just one kind. Read a node's full detail with yidam_read_node.",
    {
        "type": "object",
        "properties": {
            "node_class": {
                "type": "string",
                "description": f"Optional: restrict to one class ({_CLASS_LIST}).",
            },
        },
        "required": [],
    },
)
@traced_tool
async def yidam_list_nodes(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    mirror = _mirror(settings)
    node_class = (args or {}).get("node_class") or None
    if node_class is not None and node_class not in CLASSES:
        return _text(f"Unknown node_class '{node_class}'. Valid: {_CLASS_LIST}.")
    nodes = list_nodes(mirror, node_class=node_class)
    return _text(_render_index(nodes, site=mirror.site))


@tool(
    "yidam_read_node",
    "Read one yidam corpus node by id or URI (e.g. 'artifact/site-lima' or "
    "'yidam://corpus/hypothesis/water'). Returns the node's label, description, projected "
    "BOSC provenance (site/scope/claim_tag/source/…), and its outgoing links.",
    {"id": str},
)
@traced_tool
async def yidam_read_node(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    mirror = _mirror(settings)
    node_id = (args or {}).get("id", "")
    node = find_node(mirror, node_id)
    if node is None:
        return _text(f"No corpus node: {node_id!r}. Use yidam_list_nodes to see valid ids.")
    return _text(_render_node(node))


@tool(
    "yidam_query",
    "Search the active site's yidam corpus mirror by keyword — ranks nodes by matches over "
    "label, description, and projected provenance. Optional node_class filter "
    f"({_CLASS_LIST}) and limit (default 20). Read a hit with yidam_read_node.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Keyword(s) to match against nodes."},
            "node_class": {
                "type": "string",
                "description": f"Optional: restrict to one class ({_CLASS_LIST}).",
            },
            "limit": {"type": "integer", "description": "Max hits to return (default 20)."},
        },
        "required": ["query"],
    },
)
@traced_tool
async def yidam_query(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    mirror = _mirror(settings)
    args = args or {}
    query = str(args.get("query", "")).strip()
    if not query:
        return _text("Pass a non-empty 'query'.")
    node_class = args.get("node_class") or None
    if node_class is not None and node_class not in CLASSES:
        return _text(f"Unknown node_class '{node_class}'. Valid: {_CLASS_LIST}.")
    limit = int(args.get("limit") or 20)
    hits = query_nodes(mirror, query, node_class=node_class, limit=limit)
    if not hits:
        return _text(f"No corpus nodes match {query!r}.")
    lines = [f"{len(hits)} match(es) for {query!r}:"]
    for node in hits:
        detail = f"  — {node.description}" if node.description else ""
        lines.append(f"- {node_uri(node)}  [{node.node_class}]  {node.label}{detail}")
    return _text("\n".join(lines))


@tool(
    "yidam_open_questions",
    "List the active site's open threads from the corpus mirror — the leads board and the "
    "[open]-tagged hypothesis claims (nodes with no documented nexus yet). The yidam "
    "open-questions report, run against the live mirror.",
    {},
)
@traced_tool
async def yidam_open_questions(_args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    mirror = _mirror(settings)
    nodes = open_question_nodes(mirror)
    if not nodes:
        return _text(f"No open questions for site '{mirror.site}'.")
    lines = [f"{len(nodes)} open question(s) for site '{mirror.site}':"]
    lines.extend(f"- {node.label}  ({node_uri(node)})" for node in nodes)
    return _text("\n".join(lines))


ALL_TOOLS = [
    yidam_list_nodes,
    yidam_read_node,
    yidam_query,
    yidam_open_questions,
]
ALLOWED_TOOL_NAMES = [f"mcp__{YIDAM_SERVER_NAME}__{t.name}" for t in ALL_TOOLS]


def build_server() -> Any:
    """Create the in-process SDK MCP server serving the yidam corpus mirror to the agent."""
    return create_sdk_mcp_server(name=YIDAM_SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)
