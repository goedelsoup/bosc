"""Build the ``corpus-nodes`` feed (#1575, epic #1560 workstream D2) — the retrieval substrate.

The ``corpus-index`` feed (:mod:`watermark.site.corpus_index`) is the *browsable* map of the yidam
corpus mirror. This is its *searchable* peer: the same :class:`~watermark.site.corpus_mirror.Mirror`,
projected into one retrieval unit per node, carrying the node's searchable ``text``, its evidence
tag, its wiki page key, and its undirected 1-hop adjacency. It is the substrate behind the wiki
"ask this concept" affordance — a concept page loads it, walks the adjacency to scope to the
concept's neighborhood, and runs **client-side lexical retrieval** over that subset (offline, no
server). This is the D2 shape the D3 spike (#1576) settled on: retrieval, not generation.

Reconciled, not competing. ``text`` is the one canonical
:func:`~watermark.site.corpus_mirror.node_text` the semantic index
(:mod:`watermark.site.yidam_index`) also embeds, so the lexical and vector surfaces tokenize the
same content. ``kind`` reuses the exact display-kind mapping the ``corpus-index`` map derives, so a
node renders identically in the map and in an "ask" result. A post-pass over the just-built mirror —
never re-reads the corpus, never fabricates.
"""

from __future__ import annotations

from collections import defaultdict

from watermark.logging import get_logger
from watermark.site.corpus_index import _kind, _target_id
from watermark.site.corpus_mirror import Mirror, MirrorNode, node_text
from watermark.site.feeds import CorpusRetrievalNodeItem

log = get_logger(__name__)

# The claim-tag values that are real evidence tags (the `[verified]`/`[inference]`/`[reference]`/
# `[open]` grammar). A node whose meta carries none of these asserts no evidence — the palette is
# never spent on a purely structural node.
_EVIDENCE_TAGS = frozenset({"verified", "inference", "reference", "open"})


def _evidence(node: MirrorNode) -> str | None:
    """The node's evidence tag when it carries one (leads/open questions), else ``None``."""
    raw = str(node.meta.get("claim_tag") or "").strip().strip("[]").lower()
    return raw if raw in _EVIDENCE_TAGS else None


def _ref(node: MirrorNode) -> str | None:
    """The node's wiki page key — the concept slug for a concept node, else ``None``.

    A concept node is projected with a ``concept:<slug>`` source ref (the slug it maps 1:1 to its
    wiki page and its route param), so the slug↔node join the frontend needs is deterministic here.
    """
    if node.node_class == "concept":
        for ref in node.source_refs:
            if ref.startswith("concept:"):
                return ref[len("concept:") :]
    return None


def _undirected_adjacency(mirror: Mirror) -> dict[str, list[str]]:
    """``{node id: sorted neighbor ids}`` — every mirror link, resolved and made undirected.

    A neighborhood is a *connectivity* notion, not a direction one: a concept's neighborhood
    includes both the nodes it links to and the nodes that link to it. Links whose target is not a
    real mirror node (should not happen — every node emits ≥1 valid link) are dropped.
    """
    ids = {node.id for node in mirror.nodes}
    adj: dict[str, set[str]] = defaultdict(set)
    for node in mirror.nodes:
        for link in node.links:
            target = _target_id(node.node_class, link.target)
            if target in ids and target != node.id:
                adj[node.id].add(target)
                adj[target].add(node.id)
    return {node_id: sorted(neighbors) for node_id, neighbors in adj.items()}


def build_corpus_nodes(mirror: Mirror) -> list[CorpusRetrievalNodeItem]:
    """Project a :class:`Mirror` into the ``corpus-nodes`` retrieval feed rows (sorted by node id)."""
    adjacency = _undirected_adjacency(mirror)
    rows = [
        CorpusRetrievalNodeItem(
            id=node.id,
            kind=_kind(node),
            label=node.label,
            text=node_text(node),
            evidence=_evidence(node),
            ref=_ref(node),
            neighbors=adjacency.get(node.id, []),
        )
        for node in mirror.nodes
    ]
    rows.sort(key=lambda r: r.id)
    log.info("corpus_nodes.built", site=mirror.site, nodes=len(rows))
    return rows
