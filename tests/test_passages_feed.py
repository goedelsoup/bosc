"""Tests for the page-level ``passages`` feed (#1589, epic #1579 Phase 3).

The builder tests are pure (no corpus load) — they pin the publish-allowlist scope (only
``published`` PDFs are indexed, so no non-published source text ever ships), the page-cite grammar
(``{document_id}#p{page}``, 1-indexed), the image-only-page skip, and graceful degradation when a
source PDF can't be opened. One integration test exports a real Lima bundle and asserts both the
``passages`` and ``passage-embeddings`` feeds emit against their schemas at the right contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watermark.config import Settings
from watermark.site.feeds import PassageItem
from watermark.site.passages import (
    _published_pdf_entries,
    build_passages,
    load_committed_passages,
    write_committed_passages,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "1.42.0"


def _doc(
    rel: str, *, published: bool, render_class: str = "pdf", name: str | None = None
) -> dict[str, Any]:
    return {
        "rel": rel,
        "name": name or rel.rsplit("/", 1)[-1],
        "render_class": render_class,
        "published": published,
    }


def _collection(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"slug": "c", "title": "C", "entries": entries}]


def _write_text_pdf(path: Path, pages: list[str]) -> None:
    """Hand-assemble a minimal multi-page PDF whose pages carry a real text layer."""
    objs: list[bytes] = []

    def obj(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    page_ids: list[int] = []
    font_id = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # Reserve the Pages node id (filled after pages exist).
    pages_id = obj(b"")
    for text in pages:
        stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()
        cid = obj(b"<< /Length %d >>\nstream\n%b\nendstream" % (len(stream), stream))
        pid = obj(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 200 200] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
            % (pages_id, font_id, cid)
        )
        page_ids.append(pid)
    kids = b" ".join(b"%d 0 R" % pid for pid in page_ids)
    objs[pages_id - 1] = b"<< /Type /Pages /Count %d /Kids [%b] >>" % (len(page_ids), kids)
    catalog_id = obj(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

    out = bytearray(b"%PDF-1.7\n")
    offsets: list[int] = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%b\nendobj\n" % (i, body)
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        catalog_id,
        xref_pos,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


# --- publish-allowlist scope ---------------------------------------------------------------
def test_only_published_pdfs_are_indexed(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/pub.pdf", ["hello world"])
    _write_text_pdf(docs / "private/secret.pdf", ["classified page"])
    feed = _collection(
        [
            _doc("oepa/pub.pdf", published=True),
            _doc("private/secret.pdf", published=False),  # default-deny — must not leak
        ]
    )
    passages = build_passages(feed, docs)
    assert [p.document_id for p in passages] == ["oepa/pub.pdf"]
    assert all("classified" not in p.text for p in passages)


def test_non_pdf_published_entries_are_skipped(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/pub.pdf", ["a page"])
    feed = _collection(
        [
            _doc("oepa/pub.pdf", published=True),
            _doc("aedg/page.html", published=True, render_class="html"),  # not a PDF
        ]
    )
    passages = build_passages(feed, docs)
    assert {p.document_id for p in passages} == {"oepa/pub.pdf"}


# --- page-cite grammar + text extraction ---------------------------------------------------
def test_page_cite_grammar_is_one_indexed(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/permit.pdf", ["first page text", "second page text"])
    passages = build_passages(_collection([_doc("oepa/permit.pdf", published=True)]), docs)
    assert [(p.id, p.page) for p in passages] == [
        ("oepa/permit.pdf#p1", 1),
        ("oepa/permit.pdf#p2", 2),
    ]
    assert passages[0].collection == "oepa"
    assert passages[0].document_id == "oepa/permit.pdf"
    assert "first page" in passages[0].text


def test_empty_pages_are_omitted(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    # Page 2 has no text layer (image-only) — it should carry no passage, and page 3 keeps p.3.
    _write_text_pdf(docs / "oepa/mixed.pdf", ["page one", "", "page three"])
    passages = build_passages(_collection([_doc("oepa/mixed.pdf", published=True)]), docs)
    assert [p.page for p in passages] == [1, 3]


def test_unreadable_pdf_degrades(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    # A Git-LFS pointer stands in for an unresolved binary — pypdf can't open it.
    (docs / "oepa").mkdir(parents=True)
    (docs / "oepa/pointer.pdf").write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:deadbeef\nsize 123\n"
    )
    _write_text_pdf(docs / "oepa/real.pdf", ["real content"])
    feed = _collection(
        [_doc("oepa/pointer.pdf", published=True), _doc("oepa/real.pdf", published=True)]
    )
    passages = build_passages(feed, docs)  # must not raise
    assert {p.document_id for p in passages} == {"oepa/real.pdf"}


def test_published_pdf_entries_filters_correctly() -> None:
    feed = _collection(
        [
            _doc("a.pdf", published=True, name="A"),
            _doc("b.pdf", published=False),
            _doc("c.html", published=True, render_class="html"),
        ]
    )
    assert _published_pdf_entries(feed) == [("a.pdf", "A")]


# --- the committed artifact ----------------------------------------------------------------
def test_committed_passages_round_trip(tmp_path: Path) -> None:
    """`write_committed_passages` → `load_committed_passages` preserves the rows; a missing artifact
    reads as empty (the LFS-free build degrades to no passages rather than failing)."""
    settings = Settings(data_dir=tmp_path)
    assert load_committed_passages(settings) == []  # absent → empty
    items = [
        PassageItem(
            id="oepa/p.pdf#p1",
            document_id="oepa/p.pdf",
            collection="oepa",
            title="p.pdf",
            page=1,
            section=None,
            text="effluent limit",
        )
    ]
    write_committed_passages(items, settings)
    assert (tmp_path / "site" / "passages.ndjson").is_file()
    assert load_committed_passages(settings) == items


# --- integration: the real Lima export -----------------------------------------------------
# `lima_bundle` / `site_bundle` are conftest's session-wide, cross-worker exports (#1773). The
# shared export always passes `skip_embeddings=True`, which is what the empty-`passage-embeddings`
# assertion below reads.
def _feed_ref(bundle: Path, name: str) -> dict[str, Any]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    ref = next((f for f in manifest["feeds"] if f["name"] == name), None)
    assert ref is not None, f"reference build must emit the {name} feed"
    return ref


def test_reference_export_emits_passages_and_embeddings_feeds(lima_bundle: Path) -> None:
    """Lima's published PDFs (the OEPA collection + the PRR bundle) feed `passages`;
    `passage-embeddings` is emitted (empty here — skip_embeddings) so the schema is stable. Both are
    always-emitted retrieval-index feeds (like `ask-embeddings`). The export reads the committed
    `data/site/passages.ndjson` artifact (not the LFS PDFs), so this holds without a git-lfs pull."""
    passages_ref = _feed_ref(lima_bundle, "passages")
    assert passages_ref["count"] > 0, "committed passages artifact should yield Lima passages"
    rows = [
        json.loads(line)
        for line in (lima_bundle / passages_ref["path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == passages_ref["count"]
    # Every passage traces to a published PDF document_id and carries a 1-indexed page.
    for r in rows[:50]:
        assert r["id"] == f"{r['document_id']}#p{r['page']}"
        assert r["page"] >= 1
        assert r["text"].strip()
    # Filter invariant: every passage's document is a *published PDF* in this bundle's documents
    # feed — the export filters the global artifact to the site's published set (no leak of
    # non-published or peer-scoped source text).
    docs_ref = _feed_ref(lima_bundle, "documents")
    published_pdf_rels = {
        e["rel"]
        for coll in json.loads((lima_bundle / docs_ref["path"]).read_text(encoding="utf-8"))
        for e in coll["entries"]
        if e["published"] and e["render_class"] == "pdf"
    }
    assert {r["document_id"] for r in rows} <= published_pdf_rels
    # passage-embeddings is present (schema-stable), empty under skip_embeddings.
    emb_ref = _feed_ref(lima_bundle, "passage-embeddings")
    assert emb_ref["count"] == 0


def test_sibling_site_has_no_published_pdf_passages(site_bundle: Callable[[str], Path]) -> None:
    """A peer with no published documents of its own still emits the feed (schema-stable), empty —
    the global allowlist is Lima-anchored, so a sibling's passages set degrades cleanly."""
    ref = _feed_ref(site_bundle("fort-wayne"), "passages")
    assert ref["count"] == 0
