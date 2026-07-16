"""The yidam corpus-mirror vector index (Epic #1560, E4 · #1564).

``watermark corpus-mirror --index`` embeds the projected mirror nodes into a LanceDB index
(``yidam embed`` + ``yidam index-build``) reused by ``yidam serve --mcp`` for semantic search.
These tests are hermetic: a deterministic bag-of-words :class:`EmbeddingProvider` stub stands in
for all-MiniLM-L6-v2 (no model download, no network) and drives a real LanceDB temp dir — the
same pattern as ``test_retrieval.py`` — so cosine ranking is exercised without the real model.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import watermark.retrieval.embeddings as retrieval_embeddings
from watermark.config import Settings
from watermark.retrieval.embeddings import EmbeddingProvider
from watermark.site import yidam_index
from watermark.site.corpus_mirror import Mirror, MirrorLink, MirrorNode
from watermark.site.yidam_index import (
    YidamVectorIndex,
    build_yidam_index,
    default_index_dir,
    node_text,
    node_uri,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class _BagProvider(EmbeddingProvider):
    """Deterministic bag-of-words vectors — cosine tracks token overlap, no model load.

    Each token hashes (md5, so it is stable across processes/``PYTHONHASHSEED``) to a bucket;
    the vector counts tokens per bucket. Two texts sharing distinctive terms land close under
    cosine, so a query ranks the node whose text it overlaps — a realistic stand-in for a real
    sentence embedder, but fully deterministic.
    """

    DIM = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.DIM
            for tok in re.findall(r"[a-z0-9]+", text.lower()):
                bucket = int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.DIM
                vec[bucket] += 1.0
            out.append(vec)  # LanceDB's cosine metric normalizes; magnitude is irrelevant
        return out

    @property
    def dimension(self) -> int:
        return self.DIM


def _mirror() -> Mirror:
    """A small, connected mirror spanning three classes with distinctive vocabulary."""
    anchor = MirrorNode(
        "artifact",
        "site-demo",
        label="Demo",
        description="A demo watershed-point site.",
        meta={"site": "demo", "scope": "site", "kind": "site"},
        links=[MirrorLink("../hypothesis/water.yml", "assessed-under")],
    )
    hyp = MirrorNode(
        "hypothesis",
        "water",
        label="H1 · Water",
        description="The data-center boom is fundamentally a water story about the basin.",
        meta={"site": "demo", "scope": "network", "number": "H1"},
        links=[MirrorLink("../artifact/site-demo.yml", "assessed-at")],
    )
    lead = MirrorNode(
        "question",
        "lead-cooling",
        label="Cooling-water intake for the campus",
        description="Investigate the cooling water intake source and volume for the campus.",
        meta={"site": "demo", "claim_tag": "open", "lead_kind": "water"},
        links=[MirrorLink("../artifact/site-demo.yml", "on-site")],
    )
    grid = MirrorNode(
        "question",
        "lead-substation",
        label="Substation interconnection queue",
        description="Trace the electrical substation transmission interconnection request.",
        meta={"site": "demo", "claim_tag": "open", "lead_kind": "grid"},
        links=[MirrorLink("../artifact/site-demo.yml", "on-site")],
    )
    return Mirror(site="demo", nodes=[anchor, hyp, lead, grid])


# --- text projection ------------------------------------------------------------------------
def test_node_text_captures_label_description_class_and_salient_meta() -> None:
    node = MirrorNode(
        "artifact",
        "person-jane",
        label="Jane Roe",
        description="County commissioner.",
        meta={
            "kind": "person",
            "roles": ["chair", "trustee"],
            "site": "demo",  # structural noise — excluded from the semantic text
            "scope": "site",  # ditto
        },
    )
    text = node_text(node)
    assert "Jane Roe" in text and "County commissioner." in text
    assert "artifact" in text  # the class is part of the text unit
    assert "chair" in text and "trustee" in text  # salient meta (roles) kept
    assert "scope" not in text and "· site ·" not in text  # structural provenance dropped


def test_node_uri_matches_the_mirror_addressing() -> None:
    assert node_uri("hypothesis/water") == "yidam://corpus/hypothesis/water"


def test_default_index_dir_is_under_the_git_ignored_yidam_tree(tmp_path: Path) -> None:
    settings = Settings(site="lima", data_dir=tmp_path / "data")
    assert default_index_dir(settings) == tmp_path / ".yidam" / "index"


# --- build + query (real LanceDB temp dir, stub provider) -----------------------------------
def test_build_and_query_ranks_the_matching_node_first(tmp_path: Path) -> None:
    index = YidamVectorIndex(tmp_path / "index", _BagProvider())
    assert index.build(_mirror()) == 4
    assert index.exists

    hits = index.query("cooling water intake", limit=4)
    assert hits, "a query overlapping a node's text should return hits"
    assert hits[0].node_id == "question/lead-cooling"
    assert hits[0].uri == "yidam://corpus/question/lead-cooling"
    assert 0.0 <= hits[0].score <= 1.0
    # The grid lead shares no cooling/water vocabulary → it ranks below the water nodes.
    assert hits[0].score >= next(h.score for h in hits if h.node_id == "question/lead-substation")


def test_query_filters_by_node_class(tmp_path: Path) -> None:
    index = YidamVectorIndex(tmp_path / "index", _BagProvider())
    index.build(_mirror())
    hits = index.query("water", node_class="question", limit=10)
    assert hits and all(h.node_class == "question" for h in hits)
    # The `hypothesis/water` node (best keyword match) is excluded by the class filter.
    assert all(h.node_id != "hypothesis/water" for h in hits)


def test_query_on_unbuilt_index_or_empty_query_returns_nothing(tmp_path: Path) -> None:
    index = YidamVectorIndex(tmp_path / "index", _BagProvider())
    assert not index.exists
    assert index.query("cooling") == []  # unbuilt table
    index.build(_mirror())
    assert index.query("   ") == []  # empty query
    assert index.query("cooling", limit=0) == []  # non-positive limit


def test_build_overwrites_and_is_idempotent(tmp_path: Path) -> None:
    index = YidamVectorIndex(tmp_path / "index", _BagProvider())
    index.build(_mirror())
    # A second build over the same mirror overwrites, not appends — count stays stable.
    assert index.build(_mirror()) == 4
    hits = index.query("cooling water intake", limit=50)
    assert len({h.node_id for h in hits}) == len(hits)  # no duplicate rows


def test_build_skips_an_empty_mirror(tmp_path: Path) -> None:
    index = YidamVectorIndex(tmp_path / "index", _BagProvider())
    assert index.build(Mirror(site="demo", nodes=[])) == 0
    assert not index.exists


# --- reconciliation with the /ask embeddings ------------------------------------------------
def test_index_shares_the_exact_ask_embeddings_provider_factory() -> None:
    # The reconciliation guarantee, enforced structurally: the yidam index resolves its backend
    # through the very same `get_provider` the /ask embeddings + the retrieval store use. Same
    # factory ⇒ same model + dimension + vector space ⇒ the indexes cannot drift model-to-model.
    assert yidam_index.get_provider is retrieval_embeddings.get_provider


def test_build_yidam_index_orchestrates_mirror_and_provider(
    tmp_path: Path, monkeypatch: object
) -> None:
    calls = {"n": 0}
    stub = _BagProvider()

    def _fake_get_provider(_settings: object) -> _BagProvider:
        calls["n"] += 1
        return stub

    monkeypatch.setattr(yidam_index, "get_provider", _fake_get_provider)  # type: ignore[attr-defined]
    settings = Settings(site="lima", data_dir=tmp_path / "data")
    built = build_yidam_index(settings, mirror=_mirror(), index_dir=tmp_path / "index")

    assert calls["n"] == 1  # resolved the shared provider when none was passed
    assert built.site == "demo"
    assert built.nodes == 4
    assert built.dimension == stub.dimension
    assert built.index_dir == tmp_path / "index"
    # The written index is queryable with the same provider (round-trips through LanceDB).
    assert YidamVectorIndex(tmp_path / "index", stub).query("substation", limit=1)[
        0
    ].node_class == ("question")
