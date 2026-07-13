"""Tests for the corpus retrieval store: embeddings, store, ingestion (#807-#809).

Hermetic — no network, no model downloads. The SentenceTransformersProvider is
tested via a mock; the store is tested with a real LanceDB tmp dir using a
stub provider that emits deterministic vectors.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from watermark.config import Settings
from watermark.retrieval.embeddings import (
    EmbeddingProvider,
    SentenceTransformersProvider,
    get_provider,
)
from watermark.retrieval.ingestion import (
    _split_text,
    iter_extracted_chunks,
    iter_reference_chunks,
)
from watermark.retrieval.store import Chunk, CorpusStore, SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _VectorProvider(EmbeddingProvider):
    """Deterministic stub: hashlib-based fixed-dimension vectors, no model load.

    Uses hashlib.md5 (not Python's randomized hash()) so vectors are stable
    across processes regardless of PYTHONHASHSEED, and byte values ensure no
    zero vector is produced for ordinary text.
    """

    DIM = 8

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib

        out: list[list[float]] = []
        for text in texts:
            digest = hashlib.md5(text.encode()).digest()
            v = [b / 255.0 for b in digest[: self.DIM]]
            norm = sum(x**2 for x in v) ** 0.5 or 1.0
            out.append([x / norm for x in v])
        return out

    @property
    def dimension(self) -> int:
        return self.DIM


def _tmp_store(tmp_path: Path) -> CorpusStore:
    return CorpusStore(tmp_path / "lancedb", _VectorProvider())


def _chunk(
    chunk_id: str = "c::0",
    text: str = "hello world",
    site: str = "lima",
    collection: str = "aedg",
    doc_kind: str = "extracted",
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        site=site,
        collection=collection,
        doc_kind=doc_kind,
        source_path="aedg/foo.yaml",
        page=-1,
        provenance={"file": "foo.yaml"},
    )


# ---------------------------------------------------------------------------
# #807 — EmbeddingProvider contract
# ---------------------------------------------------------------------------


def test_embedding_provider_abc() -> None:
    with pytest.raises(TypeError):
        EmbeddingProvider()  # type: ignore[abstract]


def test_sentence_transformers_provider_lazy_load() -> None:
    """Provider does not import sentence_transformers until embed() is called."""
    provider = SentenceTransformersProvider("all-MiniLM-L6-v2")
    assert provider._model is None


def test_sentence_transformers_provider_embed() -> None:
    """embed() returns one vector per text; dimensions match."""
    fake_model = MagicMock()
    import numpy as np

    fake_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    fake_model.get_sentence_embedding_dimension.return_value = 3

    provider = SentenceTransformersProvider("test-model")
    provider._model = fake_model

    result = provider.embed(["foo", "bar"])
    assert len(result) == 2
    assert len(result[0]) == 3
    assert abs(result[0][0] - 0.1) < 1e-6


def test_sentence_transformers_provider_dimension() -> None:
    fake_model = MagicMock()
    fake_model.get_sentence_embedding_dimension.return_value = 384
    provider = SentenceTransformersProvider()
    provider._model = fake_model
    assert provider.dimension == 384


def test_get_provider_sentence_transformers() -> None:
    settings = Settings(embedding_provider="sentence_transformers", embedding_model="test")
    provider = get_provider(settings)
    assert isinstance(provider, SentenceTransformersProvider)
    assert provider._model_name == "test"


def test_get_provider_unknown() -> None:
    settings = Settings(embedding_provider="openai")
    with pytest.raises(ValueError, match="unknown embedding provider"):
        get_provider(settings)


# ---------------------------------------------------------------------------
# #808 — CorpusStore
# ---------------------------------------------------------------------------


def test_store_not_exists_before_build(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    assert not store.exists


def test_store_rebuild(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    chunks = [_chunk("a::0", "alpha"), _chunk("b::0", "beta")]
    store.rebuild(chunks)
    assert store.exists


def test_store_query_returns_results(tmp_path: Path) -> None:
    stored_text = "water quality discharge permit"
    store = _tmp_store(tmp_path)
    store.rebuild([_chunk("a::0", stored_text)])
    # Query with the exact stored text so the hash-based stub produces the
    # same vector — guarantees cosine distance = 0 regardless of hash seed.
    results = store.query(stored_text)
    assert isinstance(results, list)
    assert len(results) >= 1
    r = results[0]
    assert isinstance(r, SearchResult)
    assert r.chunk_id == "a::0"
    assert 0.0 <= r.score <= 1.0


def test_store_query_empty_when_not_built(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    assert store.query("anything") == []


def test_store_query_site_filter(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    store.rebuild(
        [
            _chunk("lima::0", "NPDES permit", site="lima"),
            _chunk("fw::0", "NPDES permit", site="fort-wayne"),
        ]
    )
    results = store.query("NPDES", site="lima")
    assert all(r.site == "lima" for r in results)


def test_store_update_site_replaces_only_that_site(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    store.rebuild(
        [
            _chunk("lima::0", "Lima content", site="lima"),
            _chunk("fw::0", "Fort Wayne content", site="fort-wayne"),
        ]
    )
    store.update_site("fort-wayne", [_chunk("fw::1", "Updated FW", site="fort-wayne")])
    fw_results = store.query("Fort Wayne Updated", site="fort-wayne", limit=5)
    # old fw::0 chunk should be gone
    ids = {r.chunk_id for r in fw_results}
    assert "fw::0" not in ids
    # lima should be unaffected
    lima_results = store.query("Lima content", site="lima", limit=5)
    assert any(r.chunk_id == "lima::0" for r in lima_results)


def test_store_provenance_roundtrip(tmp_path: Path) -> None:
    prov = {"file": "test.yaml", "page": 3}
    c = _chunk("p::0")
    c.provenance = prov
    store = _tmp_store(tmp_path)
    store.rebuild([c])
    results = store.query("hello world")
    assert results[0].provenance == prov


def test_store_update_site_creates_table_when_missing(tmp_path: Path) -> None:
    store = _tmp_store(tmp_path)
    assert not store.exists
    store.update_site("lima", [_chunk("a::0")])
    assert store.exists


# ---------------------------------------------------------------------------
# #809 — Ingestion helpers
# ---------------------------------------------------------------------------


def test_split_text_short() -> None:
    assert _split_text("hello") == ["hello"]


def test_split_text_long() -> None:
    big = ("paragraph\n\n" * 200).strip()
    parts = _split_text(big, max_chars=500)
    assert len(parts) > 1
    for p in parts:
        assert len(p) <= 600  # small overage for paragraph boundary


def test_iter_reference_chunks_missing_dir(tmp_path: Path) -> None:
    chunks = list(iter_reference_chunks(tmp_path / "nonexistent"))
    assert chunks == []


def test_iter_reference_chunks_markdown(tmp_path: Path) -> None:
    ref = tmp_path / "hydrology"
    ref.mkdir()
    (ref / "README.md").write_text("# Title\n\nContent here.", encoding="utf-8")
    chunks = list(iter_reference_chunks(tmp_path))
    assert len(chunks) >= 1
    assert chunks[0].doc_kind == "reference"
    assert chunks[0].site == ""


def test_iter_reference_chunks_csv(tmp_path: Path) -> None:
    ref = tmp_path / "echo"
    ref.mkdir()
    (ref / "facilities.csv").write_text(
        "FacilityName,NPDES,State\nAmazon AWS,OH0123,OH\nMeta,OH0456,OH",
        encoding="utf-8",
    )
    chunks = list(iter_reference_chunks(tmp_path))
    # One chunk per data row (not the header)
    assert len(chunks) == 2
    assert "FacilityName" in chunks[0].text
    assert "Amazon AWS" in chunks[0].text


def test_iter_extracted_chunks_empty_dir(tmp_path: Path) -> None:
    chunks = list(iter_extracted_chunks(tmp_path, site="lima"))
    assert chunks == []


def test_iter_extracted_chunks_lima(tmp_path: Path) -> None:
    (tmp_path / "aedg").mkdir()
    (tmp_path / "aedg" / "foo.yaml").write_text("key: value\n", encoding="utf-8")
    chunks = list(iter_extracted_chunks(tmp_path, site="lima"))
    assert len(chunks) >= 1
    assert chunks[0].site == "lima"
    assert chunks[0].doc_kind == "extracted"


def test_iter_extracted_chunks_non_lima(tmp_path: Path) -> None:
    (tmp_path / "fort-wayne" / "idem").mkdir(parents=True)
    (tmp_path / "fort-wayne" / "idem" / "permit.yaml").write_text(
        "permit: NPDES\n", encoding="utf-8"
    )
    chunks = list(iter_extracted_chunks(tmp_path, site="fort-wayne"))
    assert all(c.site == "fort-wayne" for c in chunks)


def test_iter_extracted_chunks_non_lima_missing(tmp_path: Path) -> None:
    chunks = list(iter_extracted_chunks(tmp_path, site="fort-wayne"))
    assert chunks == []


def test_iter_extracted_chunks_honors_corpus_scope(tmp_path: Path) -> None:
    """#1504: a peer whose records live under a collection prefix (Fort Wayne's
    ``idem/fort-wayne``) is indexed too, not just its bare ``<slug>/`` subdir — and it never
    picks up another site's slug subtree or Lima's un-slugged collections.
    """
    # Fort Wayne's registered scope is ("fort-wayne", "idem/fort-wayne").
    (tmp_path / "fort-wayne").mkdir()
    (tmp_path / "fort-wayne" / "wwtp.yaml").write_text("permit: DMR\n", encoding="utf-8")
    (tmp_path / "idem" / "fort-wayne").mkdir(parents=True)
    (tmp_path / "idem" / "fort-wayne" / "wqc.yaml").write_text("permit: WQC\n", encoding="utf-8")
    # Out-of-scope neighbours: another peer's subtree and a Lima-only collection.
    (tmp_path / "troy-piqua").mkdir()
    (tmp_path / "troy-piqua" / "dmr.yaml").write_text("permit: other\n", encoding="utf-8")
    (tmp_path / "recorder").mkdir()
    (tmp_path / "recorder" / "deed.yaml").write_text("deed: {}\n", encoding="utf-8")

    chunks = list(iter_extracted_chunks(tmp_path, site="fort-wayne"))
    sources = {c.source_path for c in chunks}
    assert sources == {"fort-wayne/wwtp.yaml", "idem/fort-wayne/wqc.yaml"}
    assert all(c.site == "fort-wayne" for c in chunks)


def test_iter_extracted_chunks_lima_indexes_whole_tree(tmp_path: Path) -> None:
    """Lima (the reference build, scope ``None``) still indexes every subtree, including the
    collection-prefixed peer records — the pre-existing whole-tree behavior (#1505).
    """
    (tmp_path / "recorder").mkdir()
    (tmp_path / "recorder" / "deed.yaml").write_text("deed: {}\n", encoding="utf-8")
    (tmp_path / "idem" / "fort-wayne").mkdir(parents=True)
    (tmp_path / "idem" / "fort-wayne" / "wqc.yaml").write_text("permit: WQC\n", encoding="utf-8")

    chunks = list(iter_extracted_chunks(tmp_path, site="lima"))
    sources = {c.source_path for c in chunks}
    assert sources == {"recorder/deed.yaml", "idem/fort-wayne/wqc.yaml"}
    assert all(c.site == "lima" for c in chunks)


# ---------------------------------------------------------------------------
# #808 — Settings wiring
# ---------------------------------------------------------------------------


def test_settings_lancedb_dir() -> None:
    s = Settings(data_dir=Path("/tmp/testdata"))
    assert s.lancedb_dir == Path("/tmp/testdata/cache/lancedb")


def test_settings_embedding_defaults() -> None:
    s = Settings()
    assert s.embedding_provider == "sentence_transformers"
    assert s.embedding_model == "all-MiniLM-L6-v2"
