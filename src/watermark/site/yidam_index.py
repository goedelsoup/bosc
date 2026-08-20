"""A vector index over the yidam corpus mirror (Epic #1560, workstream E, E4 · #1564).

``watermark corpus-mirror`` projects the committed BOSC corpus into yidam nodes
(:mod:`watermark.site.corpus_mirror`); this module embeds those nodes and builds a
**LanceDB vector index** over them — BOSC's realization of ``yidam embed`` + ``yidam
index-build``. The index powers semantic search over the method-layer graph, served to the
research agent through ``yidam serve --mcp`` (:mod:`watermark.agent.yidam_tools`).

**Reconciled with the ``/ask`` embeddings, not a competing index.** This index reuses the
*same* embedding backend as every other BOSC vector surface —
:func:`watermark.retrieval.embeddings.get_provider` (default ``all-MiniLM-L6-v2``, 384-dim) —
so query and document vectors share one semantic space. It does **not** touch, and is not read
by, the public ``/ask`` path: the three vector surfaces stay deliberately distinct in *what*
they index, while sharing *how* they embed (so nothing drifts model-to-model):

============================  =====================================  =========================
surface                       indexes                                serves
============================  =====================================  =========================
``ask-embeddings`` feed       the build-time **bundle feeds**         public ``/api/ask`` (canon)
(:mod:`watermark.site.embeddings`)
``data/cache/lancedb/``       the raw **corpus chunks**               agent ``retrieve_corpus``
(:mod:`watermark.retrieval`)
``.yidam/index/`` (this)      the projected **mirror nodes**          agent ``yidam serve --mcp``
============================  =====================================  =========================

**Additive + regenerable.** The index is a git-ignored artifact under ``.yidam/index/``
(alongside the mirror's ``.yidam/corpus/`` and reports' ``.yidam/reports/``), rebuilt from the
mirror by ``watermark corpus-mirror --index`` and lazily by the MCP server on first semantic
search — so ``yidam serve --mcp`` never depends on a prior CLI run. The committed corpus stays
the source of truth; this index, like the mirror, is never one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.retrieval.embeddings import EmbeddingProvider, get_provider
from watermark.site.corpus_mirror import CLASSES, Mirror, build_mirror, node_text

log = get_logger(__name__)

_TABLE = "yidam_nodes"
_BATCH = 256  # rows per embedding call (matches watermark.retrieval.store)

# The URI a mirror node is addressed by — kept in sync with watermark.agent.yidam_tools so a
# semantic hit renders/resolves identically to a keyword one (`yidam://corpus/<class>/<name>`).
_URI_SCHEME = "yidam://corpus/"


def node_uri(node_id: str) -> str:
    """The ``yidam://corpus/<class>/<name>`` URI for a node id."""
    return f"{_URI_SCHEME}{node_id}"


@dataclass
class YidamHit:
    """One ranked node from a semantic query over the index."""

    node_id: str  # the canonical `<class>/<name>` id
    node_class: str
    name: str
    label: str
    description: str
    score: float  # cosine similarity (higher = more relevant), clamped to [0, 1]

    @property
    def uri(self) -> str:
        return node_uri(self.node_id)


def default_index_dir(settings: Settings | None = None) -> Path:
    """The index's default location — ``<repo-root>/.yidam/index`` (git-ignored, regenerable)."""
    settings = settings or get_settings()
    return settings.data_dir.parent / ".yidam" / "index"


class YidamVectorIndex:
    """A LanceDB table of embedded mirror nodes — build from a :class:`Mirror`, then query.

    Structurally the mirror-node peer of :class:`watermark.retrieval.store.CorpusStore`: one
    table, rebuild-only (no partial edits), cosine similarity. Kept separate because it indexes
    the projected method-layer graph (entities/relationships/concepts/…), not raw corpus chunks.
    """

    def __init__(self, index_dir: Path, provider: EmbeddingProvider) -> None:
        self._index_dir = index_dir
        self._provider = provider
        self._db: Any = None

    def _connect(self) -> Any:
        if self._db is None:
            import lancedb

            self._index_dir.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self._index_dir))
        return self._db

    def _table_names(self) -> list[str]:
        resp = self._connect().list_tables()
        # LanceDB 0.17+ returns a ListTablesResponse with .tables; older versions a plain list.
        return list(resp.tables) if hasattr(resp, "tables") else list(resp)

    @property
    def exists(self) -> bool:
        """True when the index has been built (the LanceDB table is present)."""
        try:
            return _TABLE in self._table_names()
        except Exception:
            return False

    def _embed_batched(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _BATCH):
            vectors.extend(self._provider.embed(texts[i : i + _BATCH]))
        return vectors

    def build(self, mirror: Mirror) -> int:
        """Embed every mirror node and (over)write the index table. Returns the node count.

        A full rebuild — the mirror is small and always regenerated whole, so there is no
        incremental-update path (unlike the per-site corpus store). An empty mirror is a no-op.
        """
        nodes = mirror.nodes
        if not nodes:
            log.info("yidam_index.skip", reason="empty mirror", site=mirror.site)
            return 0
        vectors = self._embed_batched([node_text(n) for n in nodes])
        records = [
            {
                "node_id": n.id,
                "node_class": n.node_class,
                "name": n.name,
                "label": n.label,
                "description": n.description,
                "uri": node_uri(n.id),
                "site": str(n.meta.get("site") or mirror.site),
                "scope": str(n.meta.get("scope") or ""),
                "claim_tag": str(n.meta.get("claim_tag") or "").strip().strip("[]").lower(),
                "text": node_text(n),
                "vector": v,
            }
            for n, v in zip(nodes, vectors, strict=True)
        ]
        self._connect().create_table(_TABLE, records, mode="overwrite")
        log.info(
            "yidam_index.built",
            site=mirror.site,
            nodes=len(nodes),
            dim=len(vectors[0]) if vectors else 0,
            dir=str(self._index_dir),
        )
        return len(nodes)

    def query(
        self, query_text: str, *, node_class: str | None = None, limit: int = 10
    ) -> list[YidamHit]:
        """Semantic search over the index — the *limit* nodes closest to *query_text*.

        Empty query, unbuilt index, or non-positive *limit* all return no hits.
        """
        if limit <= 0 or not query_text.strip() or not self.exists:
            return []
        table = self._connect().open_table(_TABLE)
        vector = self._provider.embed([query_text])[0]
        q = table.search(vector).metric("cosine").limit(limit)
        if node_class is not None:
            escaped = node_class.replace("'", "''")
            q = q.where(f"node_class = '{escaped}'")
        rows: list[dict[str, Any]] = q.to_list()
        return [
            YidamHit(
                node_id=str(r["node_id"]),
                node_class=str(r["node_class"]),
                name=str(r["name"]),
                label=str(r["label"]),
                description=str(r.get("description") or ""),
                score=min(1.0, max(0.0, 1.0 - float(r.get("_distance", 0.0)))),
            )
            for r in rows
        ]


@dataclass
class YidamIndexBuild:
    """The outcome of one ``watermark corpus-mirror --index`` / lazy MCP index build."""

    site: str
    index_dir: Path
    nodes: int
    dimension: int


def build_yidam_index(
    settings: Settings | None = None,
    *,
    mirror: Mirror | None = None,
    provider: EmbeddingProvider | None = None,
    index_dir: Path | None = None,
) -> YidamIndexBuild:
    """Build the LanceDB vector index over the active site's corpus mirror.

    ``yidam embed`` + ``yidam index-build`` fused: project the mirror (if not supplied), embed
    every node with the shared :func:`~watermark.retrieval.embeddings.get_provider` backend
    (reconciled with the ``/ask`` embeddings — same model, same 384-dim space), and write the
    ``.yidam/index/`` table. Offline by construction (the mirror is a pure read of committed
    data); the only network touch is the one-time embedding-model download.
    """
    settings = settings or get_settings()
    mirror = mirror if mirror is not None else build_mirror(settings)
    provider = provider or get_provider(settings)
    index_dir = index_dir or default_index_dir(settings)

    index = YidamVectorIndex(index_dir, provider)
    nodes = index.build(mirror)
    return YidamIndexBuild(
        site=mirror.site,
        index_dir=index_dir,
        nodes=nodes,
        dimension=provider.dimension,
    )


# Re-exported so callers can validate/round-trip a node_class without importing corpus_mirror.
__all__ = [
    "CLASSES",
    "YidamHit",
    "YidamIndexBuild",
    "YidamVectorIndex",
    "build_yidam_index",
    "default_index_dir",
    "node_text",
    "node_uri",
]
