"""Tests for the page-level ``passages`` feed (#1589, epic #1579 Phase 3).

The builder tests are pure (no corpus load) — they pin the publish-allowlist scope (only
``published`` PDFs are indexed, so no non-published source text ever ships), the page-cite grammar
(``{document_id}#p{page}``, 1-indexed), the image-only-page skip, graceful degradation when a
source PDF can't be opened, and the broken-``ToUnicode`` OCR fallback (#1966). One integration test
exports a real Lima bundle and asserts both the ``passages`` and ``passage-embeddings`` feeds emit
against their schemas at the right contract.

The OCR fallback is exercised through the injected :data:`~watermark.site.passages.OcrPage` seam, so
the suite never shells out to tesseract (same discipline as ``test_civic_indexer``); the fixture PDF
it runs against is generated, not committed — a hand-assembled page whose ``ToUnicode`` CMap is
shifted down by ``0x1D``, which reproduces the real permits' damage byte-for-byte.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from watermark.civic.indexer import OcrUnavailableError
from watermark.config import Settings
from watermark.site.feeds import PassageItem
from watermark.site.passages import (
    PassageExtraction,
    _published_pdf_entries,
    _repair_surrogate_pairs,
    artifact_path,
    build_passages,
    has_broken_text_layer,
    load_committed_passages,
    write_committed_passages,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "2.2.0"

# The exact bytes `July 1, 2026` decodes to through a ToUnicode CMap shifted down by 0x1D — the
# start date of van-wert's final effluent limitations as pypdf reads it out of
# `data/documents/oepa/van-wert/2PD00006.f8aaad0a.pdf` (#1966).
_BROKEN_JULY = "-XO\\\x03\x14\x0f\x03\x15\x13\x15\x19"


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


def _broken_tounicode(pages: list[str], shift: int) -> bytes:
    """A ``ToUnicode`` CMap that maps every code used to ``code - shift`` — the real defect (#1966).

    A subset font whose CMap maps character codes to raw *glyph indices* is exactly this: an offset
    table. Codes that land below 0x20 decode to C0 control bytes (the detectable half of the damage)
    and the rest decode to other printable characters (the silent half).
    """
    codes = sorted({ord(c) for text in pages for c in text})
    entries = "".join(f"<{c:02X}> <{c - shift:04X}>\n" for c in codes)
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CMapName /Shifted def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{len(codes)} beginbfchar\n{entries}endbfchar\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode()


def _surrogate_tounicode(pages: list[str], chars: str) -> bytes:
    """A ``ToUnicode`` CMap that splits a surrogate pair across TWO ``bfchar`` entries.

    This is the real defect in ``oepa/lima/edoc-4175534.pdf`` p.15, and it is NOT the obvious
    one. A four-byte destination (``<D835DC45>``) is a *legitimate* way to write U+1D445 and
    pypdf combines it correctly — a fixture built that way reproduces nothing. The damaged font
    instead maps two different character codes to the two HALVES::

        <80> -> <D835>      (high surrogate, alone)
        <81> -> <DC45>      (low surrogate, alone)

    pypdf decodes each entry independently, so the halves only look like a pair once
    concatenated. Each is a lone surrogate: representable in a Python ``str``, not encodable to
    UTF-8, and therefore invisible until serialization — which is how one page of one document
    killed the entire 261-document ``watermark passages`` write.

    Generated rather than committed, for the same reason as :func:`_broken_tounicode`: it
    reproduces the real bytes exactly instead of a hand-typed approximation of them.
    """
    high, low = chars[0], chars[1]
    codes = sorted({ord(c) for text in pages for c in text})
    halves = {ord(high): "D835", ord(low): "DC45"}
    entries = "".join(f"<{c:02X}> <{halves.get(c, f'{c:04X}')}>\n" for c in codes)
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        "/CMapName /Surrogate def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{len(codes)} beginbfchar\n{entries}endbfchar\n"
        "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend"
    ).encode()


def _write_text_pdf(
    path: Path,
    pages: list[str],
    *,
    unicode_shift: int | None = None,
    surrogate_chars: str | None = None,
) -> None:
    """Hand-assemble a minimal multi-page PDF whose pages carry a real text layer.

    ``unicode_shift`` attaches a deliberately broken ``ToUnicode`` CMap (see
    :func:`_broken_tounicode`), so the text layer decodes shifted down by that many code points.
    """
    objs: list[bytes] = []

    def obj(body: bytes) -> int:
        objs.append(body)
        return len(objs)

    page_ids: list[int] = []
    if unicode_shift is None and surrogate_chars is None:
        font_id = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    else:
        cmap = (
            _surrogate_tounicode(pages, surrogate_chars)
            if surrogate_chars is not None
            else _broken_tounicode(pages, unicode_shift or 0)
        )
        cmap_id = obj(b"<< /Length %d >>\nstream\n%b\nendstream" % (len(cmap), cmap))
        font_id = obj(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode %d 0 R >>" % cmap_id
        )
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


def test_surrogate_pairs_are_recombined_not_dropped() -> None:
    """A UTF-16 pair denotes one real character and must survive as that character.

    Some ``ToUnicode`` CMaps encode astral characters as surrogate pairs and pypdf yields the
    halves separately. Lima's WWTP capacity report (``oepa/lima/edoc-4175534.pdf`` p.15) writes
    its removal-efficiency formula in a mathematical-italic font, so ``U+D835 U+DC45`` arrives
    where the document prints ``U+1D445``.
    """
    assert _repair_surrogate_pairs("x\U0001d445y") == "x\U0001d445y"
    assert _repair_surrogate_pairs("R\ud835\udc45 = 1") == "R\U0001d445 = 1"


def test_an_orphan_surrogate_is_removed_without_a_replacement_char() -> None:
    """Regression: an unpaired surrogate must not become U+FFFD.

    Round-tripping the whole string through ``errors="replace"`` is the obvious repair and the
    wrong one — it swaps the orphan for a visible U+FFFD, which is a silent edit to quoted
    public-record text and precisely what :func:`_repair_cp1252_punctuation` refuses to do.
    A half-surrogate denotes nothing, so removal is the only honest outcome.
    """
    assert _repair_surrogate_pairs("a\ud800b") == "ab"
    assert _repair_surrogate_pairs("a\udc45b") == "ab"
    assert "\ufffd" not in _repair_surrogate_pairs("a\ud800b")


def test_clean_text_is_returned_unchanged() -> None:
    assert (
        _repair_surrogate_pairs("plain ASCII \u2014 and a dash") == "plain ASCII \u2014 and a dash"
    )


def test_every_emitted_passage_encodes_to_utf8(tmp_path: Path) -> None:
    """The invariant the crash violated: a passage must survive serialization.

    A lone surrogate is representable in a Python ``str`` and NOT encodable to UTF-8, so it
    passes every text-level check and then kills the write. ``watermark passages`` died on one
    page of one document out of 261 with a ``PydanticSerializationError``, after doing the work.
    """
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/math.pdf", ["removal efficiency RI"], surrogate_chars="RI")
    passages = build_passages(_collection([_doc("oepa/math.pdf", published=True)]), docs)
    assert passages, "the fixture must produce a passage, not an empty read"
    for item in passages:
        item.text.encode("utf-8")  # must not raise
        assert not any(0xD800 <= ord(c) <= 0xDFFF for c in item.text)
    # Encodability alone would also hold if the repair simply DELETED both halves, which is a
    # silent edit to quoted text rather than a repair. Assert the character the document
    # actually prints survives.
    assert any("\U0001d445" in item.text for item in passages)


def test_published_pdf_entries_filters_correctly() -> None:
    feed = _collection(
        [
            _doc("a.pdf", published=True, name="A"),
            _doc("b.pdf", published=False),
            _doc("c.html", published=True, render_class="html"),
        ]
    )
    assert _published_pdf_entries(feed) == [("a.pdf", "A")]


# --- the broken-ToUnicode OCR fallback (#1966) ---------------------------------------------
def _broken_doc(tmp_path: Path) -> tuple[Path, list[dict[str, Any]]]:
    """A published PDF whose page 1 has a shifted CMap and whose page 2 is clean."""
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/shifted.pdf", ["July 1, 2026"], unicode_shift=0x1D)
    _write_text_pdf(docs / "oepa/clean.pdf", ["July 1, 2026"])
    return docs, _collection(
        [_doc("oepa/shifted.pdf", published=True), _doc("oepa/clean.pdf", published=True)]
    )


def test_shifted_cmap_reproduces_the_real_damage(tmp_path: Path) -> None:
    """The fixture is a regression fixture only if it decodes to what the real permits decode to:
    `July 1, 2026` → `-XO\\` plus C0 control bytes, every code shifted down by 0x1D. The detector
    fires on it and not on the same string read through an intact font."""
    import pypdf

    docs, _ = _broken_doc(tmp_path)
    broken = pypdf.PdfReader(str(docs / "oepa/shifted.pdf"), strict=False).pages[0].extract_text()
    clean = pypdf.PdfReader(str(docs / "oepa/clean.pdf"), strict=False).pages[0].extract_text()
    assert _BROKEN_JULY in broken
    assert has_broken_text_layer(broken)
    assert "July 1, 2026" in clean
    assert not has_broken_text_layer(clean)


def test_broken_page_falls_back_to_ocr(tmp_path: Path) -> None:
    """A page whose text layer trips the detector is re-read WHOLE by OCR and says so; a clean page
    in the same run keeps its text layer untouched."""
    docs, feed = _broken_doc(tmp_path)
    calls: list[tuple[str, int]] = []

    def fake_ocr(path: Path, index: int) -> str:
        calls.append((path.name, index))
        return "During the period beginning July 1, 2026,\x0c"  # tesseract ends a page with \x0c

    passages = build_passages(feed, docs, ocr_page=fake_ocr)
    by_doc = {p.document_id: p for p in passages}
    assert calls == [("shifted.pdf", 0)], "only the damaged page is re-read"
    repaired = by_doc["oepa/shifted.pdf"]
    assert repaired.method == "ocr"
    assert "July 1, 2026" in repaired.text
    # The whole page is replaced — no shifted remnant survives, and the form feed tesseract appends
    # is stripped so the OCR read can't trip the detector it was called in to clear.
    assert "-XO\\" not in repaired.text
    assert not has_broken_text_layer(repaired.text)
    assert by_doc["oepa/clean.pdf"].method == "pdf_text"


def test_ocr_unavailable_degrades_to_the_readable_remainder(tmp_path: Path) -> None:
    """No tesseract → the page is kept, not dropped, but says its read is damaged and ships the
    readable remainder with the undecodable bytes gone. The binary is probed once per run, not once
    per damaged page."""
    docs = tmp_path / "documents"
    _write_text_pdf(docs / "oepa/shifted.pdf", ["July 1, 2026", "July 2, 2026"], unicode_shift=0x1D)
    feed = _collection([_doc("oepa/shifted.pdf", published=True)])
    calls = 0

    def unavailable(path: Path, index: int) -> str:
        nonlocal calls
        calls += 1
        raise OcrUnavailableError("the tesseract binary is not on PATH")

    passages = build_passages(feed, docs, ocr_page=unavailable)  # must not raise
    assert calls == 1
    assert [p.page for p in passages] == [1, 2]
    assert {p.method for p in passages} == {"pdf_text_damaged"}
    assert not any(has_broken_text_layer(p.text) for p in passages)
    assert "-XO\\" in passages[0].text  # the silently-shifted half survives; hence the marker


def test_unrenderable_page_is_kept_as_a_damaged_locator(tmp_path: Path) -> None:
    """A page OCR can't read — wilmington's `1MP00060.pdf` p. 127 renders blank — is not dropped: a
    partial locator beats a hole in the index, and `pdf_text_damaged` is what says not to quote
    it."""
    docs, feed = _broken_doc(tmp_path)

    def blank(path: Path, index: int) -> str:
        return "   "

    passages = build_passages(feed, docs, ocr_page=blank)
    shifted = next(p for p in passages if p.document_id == "oepa/shifted.pdf")
    assert shifted.method == "pdf_text_damaged"
    assert not has_broken_text_layer(shifted.text)


def test_ocr_fallback_can_be_disabled(tmp_path: Path) -> None:
    """`ocr_page=None` is the text-layer-only read — still scrubbed and still flagged, because the
    page is damaged whether or not anyone tried to repair it."""
    docs, feed = _broken_doc(tmp_path)
    passages = build_passages(feed, docs, ocr_page=None)
    by_doc = {p.document_id: p for p in passages}
    assert by_doc["oepa/shifted.pdf"].method == "pdf_text_damaged"
    assert by_doc["oepa/clean.pdf"].method == "pdf_text"


# --- the committed artifact's standing guarantees (#1966) -----------------------------------
def _committed() -> list[PassageItem]:
    settings = Settings(data_dir=REPO_ROOT / "data")
    passages = load_committed_passages(settings)
    assert passages, f"committed artifact missing: {artifact_path(settings)}"
    return passages


def test_committed_artifact_ships_no_control_bytes() -> None:
    """The emit invariant, checked on the real artifact: `data/site/passages.ndjson` is what every
    bundle's `passages` feed is filtered from, so a control byte here reaches the public feed."""
    broken = [p.id for p in _committed() if has_broken_text_layer(p.text)]
    assert not broken, f"{len(broken)} passage(s) carry control bytes, e.g. {broken[:3]}"


def test_committed_artifact_reads_the_van_wert_effluent_dates() -> None:
    """The reported defect itself (#1966). Part I.A of van-wert's `*WD` modification opens with the
    date its final effluent limitations begin; through the permit's broken CMap that date extracted
    as `-XO\\` plus control bytes, which is unfindable by anyone searching for it."""
    page3 = next(p for p in _committed() if p.id == "oepa/van-wert/2PD00006.f8aaad0a.pdf#p3")
    assert page3.method == "ocr"
    assert "July 1, 2026" in page3.text
    assert _BROKEN_JULY not in page3.text


def test_committed_artifact_repairs_all_but_the_unrenderable_page() -> None:
    """A regen without tesseract turns every repaired page back into a damaged one — which is a
    silent revert of this fix, so it is pinned. The one exception is wilmington `1MP00060.pdf`
    p. 127, which pdfium renders as a blank raster: there is nothing for OCR to read."""
    by_method: dict[str, list[str]] = {}
    for p in _committed():
        by_method.setdefault(p.method, []).append(p.id)
    assert len(by_method.get("ocr", [])) >= 49
    assert by_method.get("pdf_text_damaged", []) == ["oepa/wilmington/1MP00060.pdf#p127"]


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
    write_committed_passages(
        PassageExtraction(items=items, published_pdfs=["oepa/p.pdf"]), settings
    )
    artifact = tmp_path / "site" / "passages.ndjson"
    assert artifact.is_file()
    assert load_committed_passages(settings) == items
    assert json.loads(artifact.read_text(encoding="utf-8"))["method"] == "pdf_text"
    # The sidecar lands beside it, recording the set this run covered (#2025) — so the index can
    # never again be a file with no account of what it describes.
    meta = json.loads((tmp_path / "site" / "passages.meta.json").read_text(encoding="utf-8"))
    assert meta == {
        "published_pdfs": ["oepa/p.pdf"],
        "documents_with_passages": 1,
        "passage_count": 1,
    }


def test_pre_1_54_artifact_still_loads(tmp_path: Path) -> None:
    """`method` is defaulted, not required, so a passages.ndjson written before contract 1.54.0
    (no `method` key) still reads — the export degrades to "text layer" rather than failing."""
    settings = Settings(data_dir=tmp_path)
    artifact = artifact_path(settings)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "id": "oepa/p.pdf#p1",
                "document_id": "oepa/p.pdf",
                "collection": "oepa",
                "title": "p.pdf",
                "page": 1,
                "section": None,
                "text": "effluent limit",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert [p.method for p in load_committed_passages(settings)] == ["pdf_text"]


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


# --- index freshness (#2025) --------------------------------------------------------------------
# The shared `data/site/passages.ndjson` has no per-site regeneration and no freshness check, which
# makes it the worst case of the committed-artifact lag this epic is about: #2023 cleared eight
# `oepa/` documents already inside a cleared boundary, and they sat unindexed until an unrelated
# site was rebuilt. These drive the check against a synthetic sidecar — the predicate is a set
# comparison, so it needs no PDFs and no extraction.


def _seed_index(tmp_path: Path, built_from: list[str]) -> Settings:
    """A data_dir whose passages sidecar claims it was built from `built_from`."""
    site = tmp_path / "site"
    site.mkdir(parents=True, exist_ok=True)
    (site / "passages.meta.json").write_text(
        json.dumps(
            {"published_pdfs": built_from, "documents_with_passages": 0, "passage_count": 0}
        ),
        encoding="utf-8",
    )
    return Settings(data_dir=tmp_path)


def test_an_index_with_no_sidecar_cannot_be_trusted(tmp_path: Path) -> None:
    """An index that carries no record of what it covers is a finding, not a pass.

    The alternative — assuming an undocumented index is current — is exactly the assumption that
    let the shared artifact drift for eight days across three PRs.
    """
    from watermark.site.passages import check_index_freshness

    (tmp_path / "site").mkdir(parents=True)
    (findings,) = check_index_freshness(Settings(data_dir=tmp_path))
    assert findings.kind == "no-meta"


def test_a_document_cleared_since_the_build_is_reported(tmp_path: Path, monkeypatch: Any) -> None:
    """The #2023 shape: a document enters the cleared set and is never offered to the extractor."""
    from watermark.site import passages as passages_mod

    settings = _seed_index(tmp_path, ["oepa/a.pdf"])
    monkeypatch.setattr(
        passages_mod, "published_pdf_rels", lambda _s: ["oepa/a.pdf", "oepa/newly-cleared.pdf"]
    )
    (finding,) = passages_mod.check_index_freshness(settings)
    assert finding.kind == "newly-published"
    assert finding.subject == "oepa/newly-cleared.pdf"


def test_a_document_withdrawn_since_the_build_is_reported(tmp_path: Path, monkeypatch: Any) -> None:
    """The other direction: the index retains page text for a document the publish policy no
    longer clears. The per-site feed filters it out at export, so it is not a live leak — but a
    committed artifact outliving its clearance is worth naming. Zero occurrences today; this is
    the guard, not a report."""
    from watermark.site import passages as passages_mod

    settings = _seed_index(tmp_path, ["oepa/a.pdf", "oepa/withheld.pdf"])
    monkeypatch.setattr(passages_mod, "published_pdf_rels", lambda _s: ["oepa/a.pdf"])
    (finding,) = passages_mod.check_index_freshness(settings)
    assert finding.kind == "no-longer-published"
    assert finding.subject == "oepa/withheld.pdf"


def test_an_unchanged_published_set_is_current(tmp_path: Path, monkeypatch: Any) -> None:
    """Coverage is deliberately NOT the predicate. 63 of the 261 published PDFs carry no passage
    and none is an unresolved LFS pointer — they are image-only scans with a zero-length text
    layer, so "published but carrying no passage" would be 63 standing findings forever. What is
    exact is whether the cleared SET has moved."""
    from watermark.site import passages as passages_mod

    settings = _seed_index(tmp_path, ["oepa/a.pdf", "oepa/b.pdf"])
    monkeypatch.setattr(passages_mod, "published_pdf_rels", lambda _s: ["oepa/b.pdf", "oepa/a.pdf"])
    assert passages_mod.check_index_freshness(settings) == []


def test_the_committed_index_is_current() -> None:
    """The real artifact must cover the real published corpus — the end-to-end guard.

    Cheap enough for the suite: it resolves the publish policy and reads the document catalog,
    opening no PDF. The rebuild it recommends is the expensive half, and only runs when this fails.
    """
    from watermark.site.passages import check_index_freshness

    findings = check_index_freshness(Settings(data_dir=REPO_ROOT / "data"))
    assert findings == [], (
        "the committed passage index no longer covers the published corpus — "
        f"run `git lfs pull && watermark passages`: {[str(f) for f in findings]}"
    )
