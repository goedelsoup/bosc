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
    iter_document_chunks,
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


def test_iter_extracted_chunks_lima_excludes_peer_subtrees(tmp_path: Path) -> None:
    """Lima (the reference build) indexes its own whole tree but now *subtracts* every registered
    peer's subtree (#1505): its un-slugged Allen-County collections are indexed, a peer's
    collection-prefixed record (``idem/fort-wayne/…``) or slug subtree (``troy-piqua/…``) is not —
    so a Piqua permit stops being double-indexed under Lima and rendering in Lima's record.
    """
    (tmp_path / "recorder").mkdir()
    (tmp_path / "recorder" / "deed.yaml").write_text("deed: {}\n", encoding="utf-8")
    (tmp_path / "oepa").mkdir()  # a Lima un-slugged collection — kept
    (tmp_path / "oepa" / "1PD00013.npdes.yaml").write_text("permit: lima\n", encoding="utf-8")
    (tmp_path / "idem" / "fort-wayne").mkdir(parents=True)  # a peer's jurisdiction prefix — dropped
    (tmp_path / "idem" / "fort-wayne" / "wqc.yaml").write_text("permit: WQC\n", encoding="utf-8")
    (tmp_path / "oepa" / "troy-piqua").mkdir()  # a peer under a Lima collection prefix — dropped
    (tmp_path / "oepa" / "troy-piqua" / "1PD00008.npdes.yaml").write_text(
        "permit: piqua\n", encoding="utf-8"
    )

    chunks = list(iter_extracted_chunks(tmp_path, site="lima"))
    sources = {c.source_path for c in chunks}
    assert sources == {"recorder/deed.yaml", "oepa/1PD00013.npdes.yaml"}
    assert all(c.site == "lima" for c in chunks)


# ---------------------------------------------------------------------------
# #1757 — native-format documents and their text sidecars
# ---------------------------------------------------------------------------


def _mini_corpus(tmp_path: Path) -> Path:
    """A documents tree carrying one of each route: PDF, native, and sidecar-backed."""
    import zipfile

    prod = tmp_path / "legal" / "production"
    prod.mkdir(parents=True)
    (prod / "notes.txt").write_text("Shawnee II DFFO extension letter", encoding="utf-8")
    (prod / "email.htm").write_text(
        "<html><head><style>p{margin:0}</style></head><body><p>Bath Trunk Sizing</p></body></html>",
        encoding="utf-8",
    )
    with zipfile.ZipFile(prod / "memo.docx", "w") as z:
        z.writestr("word/document.xml", "<w:p><w:t>Hume Road WPCLF</w:t></w:p>")
    (prod / "Letter to Chase.DOC").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")

    sidecars = tmp_path / "legal" / "production-text"
    sidecars.mkdir(parents=True)
    (sidecars / "Letter to Chase.DOC.txt").write_text("retainage account", encoding="utf-8")
    (sidecars / "text-sidecars.yaml").write_text("meta: {}\n", encoding="utf-8")
    (sidecars / "README.md").write_text("# derived", encoding="utf-8")
    return tmp_path


def test_iter_document_chunks_reads_the_native_office_and_browser_formats(tmp_path: Path) -> None:
    chunks = {c.source_path: c for c in iter_document_chunks(_mini_corpus(tmp_path))}

    assert chunks["legal/production/notes.txt"].provenance["text_source"] == "txt"
    assert chunks["legal/production/email.htm"].provenance["text_source"] == "html"
    assert "margin" not in chunks["legal/production/email.htm"].text
    assert chunks["legal/production/memo.docx"].text == "Hume Road WPCLF"
    # Un-paginated documents use the reference iterator's page convention.
    assert chunks["legal/production/notes.txt"].page == -1
    assert chunks["legal/production/notes.txt"].collection == "legal"


def test_iter_document_chunks_attributes_a_sidecar_to_the_record_it_transcribes(
    tmp_path: Path,
) -> None:
    # A citation has to name the .DOC — the .txt is a derived reading aid, and indexing it under
    # its own path would cite a file the county never produced.
    chunks = [
        c
        for c in iter_document_chunks(_mini_corpus(tmp_path))
        if c.provenance.get("text_source") == "sidecar"
    ]
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.source_path == "legal/production/Letter to Chase.DOC"
    assert chunk.provenance["sidecar"] == "legal/production-text/Letter to Chase.DOC.txt"
    assert chunk.provenance["filename"] == "Letter to Chase.DOC"
    assert chunk.collection == "legal"
    assert chunk.text == "retainage account"


def test_iter_document_chunks_does_not_index_a_sidecar_tree_under_its_own_path(
    tmp_path: Path,
) -> None:
    # The .txt must not appear twice — once as the record's text and once as a document of its
    # own — and the tree's manifest/README are not corpus text at all.
    sources = {c.source_path for c in iter_document_chunks(_mini_corpus(tmp_path))}
    assert not any(s.startswith("legal/production-text/") for s in sources)


def test_iter_document_chunks_routes_an_extensionless_pdf_by_its_magic_bytes(
    tmp_path: Path,
) -> None:
    import pypdf

    coll = tmp_path / "legal"
    coll.mkdir()
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with (coll / "Flow Calculations feb 6, 2008").open("wb") as fh:
        writer.write(fh)

    chunks = list(iter_document_chunks(tmp_path))
    assert [c.page for c in chunks] == [0]  # paginated, i.e. read as a PDF
    assert chunks[0].source_path == "legal/Flow Calculations feb 6, 2008"


def test_iter_document_chunks_survives_a_pdf_that_breaks_mid_traversal(tmp_path: Path) -> None:
    # reader.pages parses each page lazily, so a malformed PDF can raise partway through the
    # loop, not just in extract_text. One broken document must not abort the whole index build.
    coll = tmp_path / "legal"
    coll.mkdir()
    (coll / "broken.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")  # header only, no page tree
    (coll / "notes.txt").write_text("Shawnee II DFFO", encoding="utf-8")

    sources = {c.source_path for c in iter_document_chunks(tmp_path)}
    assert "legal/notes.txt" in sources  # the readable neighbour still lands


def test_iter_document_chunks_skips_formats_it_cannot_read(tmp_path: Path) -> None:
    coll = tmp_path / "legal"
    coll.mkdir()
    (coll / "scan.jpg").write_bytes(b"\xff\xd8\xff\xe0")
    (coll / "thumbs.db").write_bytes(b"\x00\x01")
    (coll / "filelist.xml").write_text("<xml/>", encoding="utf-8")  # a Word _files/ companion
    assert list(iter_document_chunks(tmp_path)) == []


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
