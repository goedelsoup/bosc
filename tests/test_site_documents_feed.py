"""Feed-level tests for source-document rendering (epic #274, phase A).

A1 (#275): ``media_type`` / ``render_class`` are derived from the *real* file — a
content sniff of the leading bytes, trusted over the extension on disagreement, with an
office override table. A2 (#276): a record joins to its real source document only when
that document is actually catalogued (a stale ``source_path`` yields no link).
"""

from __future__ import annotations

from pathlib import Path

from watermark.site.documents import (
    PublishAllowlist,
    _document_stat,
    _lfs_pointer_size,
    build_doc_index,
    build_documents,
    export_documents,
    load_publish_allowlist,
)
from watermark.site.records import _normalize_source_rel, export_records


def _entries(documents_dir: Path) -> dict[str, tuple[str, str, bool]]:
    """rel -> (media_type, render_class, available) for a built catalog."""
    result = build_documents(documents_dir)
    return {
        e.rel: (e.media_type, e.render_class, e.available)
        for c in result.collections
        for e in c.entries
    }


def test_render_class_sniff_overrides_a_mislabeled_extension(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    # A PDF mislabeled .txt — the sniff must win (degraded/mislabeled corpus files).
    (docs / "recorder").mkdir(parents=True)
    (docs / "recorder" / "scan.txt").write_bytes(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    (docs / "recorder" / "photo.bin").write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")
    (docs / "recorder" / "real.txt").write_text("plain notes", encoding="utf-8")

    got = _entries(docs)
    assert got["recorder/scan.txt"][:2] == ("application/pdf", "pdf")
    assert got["recorder/photo.bin"][:2] == ("image/jpeg", "image")
    assert got["recorder/real.txt"][:2] == ("text/plain", "text")


def test_file_directly_under_documents_dir_is_not_a_single_file_collection(
    tmp_path: Path,
) -> None:
    """#617: a file dropped directly under documents_dir has no collection — it must be
    skipped, not turned into a single-file 'collection' named after the file."""
    docs = tmp_path / "documents"
    (docs / "recorder").mkdir(parents=True)
    (docs / "recorder" / "deed.pdf").write_bytes(b"%PDF-1.5\n")
    (docs / "stray.pdf").write_bytes(b"%PDF-1.5\n")  # no collection subdir

    result = build_documents(docs)
    slugs = {c.slug for c in result.collections}
    assert slugs == {"recorder"}
    assert "stray" not in slugs
    assert "stray.pdf" not in slugs


def test_office_override_table(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    (docs / "plans").mkdir(parents=True)
    # Office files are zip/OLE containers — no positive sniff, so the extension governs.
    (docs / "plans" / "drawing.odg").write_bytes(b"PK\x03\x04zipzip")
    (docs / "plans" / "report.docx").write_bytes(b"PK\x03\x04zipzip")
    (docs / "plans" / "legacy.doc").write_bytes(b"\xd0\xcf\x11\xe0OLE")

    got = _entries(docs)
    assert got["plans/drawing.odg"][1] == "office"
    assert got["plans/report.docx"][1] == "office"
    assert got["plans/legacy.doc"][1] == "office"
    assert got["plans/drawing.odg"][0] == "application/vnd.oasis.opendocument.graphics"


def test_lfs_pointer_is_available_with_size_from_the_pointer(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    (docs / "aedg").mkdir(parents=True)
    # An unpulled Git-LFS pointer stands in for bytes that live in LFS/R2 and are served
    # from the object store, not the build tree (#1347) — so the doc is *available*, with
    # the true size read from the pointer text. Sniffing the pointer text would mis-class
    # it, so the real extension governs the render class instead.
    pointer = "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 143327\n"
    (docs / "aedg" / "PRR.pdf").write_text(pointer, encoding="utf-8")

    entry = next(
        e for c in build_documents(docs).collections for e in c.entries if e.rel == "aedg/PRR.pdf"
    )
    assert (entry.media_type, entry.render_class) == ("application/pdf", "pdf")
    assert entry.available is True
    assert entry.size_bytes == 143327  # from the pointer, not the ~130-byte pointer file


def test_lfs_pointer_size_parses_and_rejects_non_pointers() -> None:
    assert _lfs_pointer_size(b"version https://git-lfs.github.com/spec/v1\nsize 42\n") == 42
    assert _lfs_pointer_size(b"%PDF-1.7\n...real bytes...") is None
    # Malformed size line -> not a usable pointer size.
    assert _lfs_pointer_size(b"version https://git-lfs.github.com/spec/v1\nsize nope\n") is None


def test_document_stat_missing_file_is_absent(tmp_path: Path) -> None:
    size, available, is_pointer = _document_stat(tmp_path / "nope.pdf")
    assert (size, available, is_pointer) == (0, False, False)


def test_normalize_source_rel_shapes() -> None:
    # Absolute machine path with the legacy shawnee-smart-systems prefix.
    abs_path = (
        "/Users/cparent/Code/shawnee-smart-systems/bosc/data/documents/"
        "recorder/bistrozzi-deeds/202508130008300.pdf"
    )
    assert _normalize_source_rel(abs_path) == "recorder/bistrozzi-deeds/202508130008300.pdf"
    # Repo-relative, both with and without the data/ prefix.
    assert _normalize_source_rel("data/documents/aedg/PRR-01-bundle.ocr.pdf") == (
        "aedg/PRR-01-bundle.ocr.pdf"
    )
    assert _normalize_source_rel("documents/plans/bistrozzi-plans/LMA1A.odg") == (
        "plans/bistrozzi-plans/LMA1A.odg"
    )
    # A directory reference and a non-corpus path resolve to nothing.
    assert _normalize_source_rel("data/documents/aedg/data-center-updates/") is None
    assert _normalize_source_rel("/tmp/somewhere/else.pdf") is None
    assert _normalize_source_rel(None) is None


def test_export_records_joins_to_the_real_source_document(tmp_path: Path) -> None:
    extracted = tmp_path / "extracted"
    (extracted / "recorder").mkdir(parents=True)
    (extracted / "permits").mkdir(parents=True)
    # A deed with an absolute source_path that resolves to a catalogued file.
    (extracted / "recorder" / "a.deed.yaml").write_text(
        "deed:\n  instrument_no: '202508130008300'\n"
        "source_path: /Users/x/shawnee-smart-systems/bosc/data/documents/"
        "recorder/bistrozzi-deeds/202508130008300.pdf\n",
        encoding="utf-8",
    )
    # A record whose source_path points at a file NOT in the catalog -> no link.
    (extracted / "permits" / "b.epa.yaml").write_text(
        "action:\n  permit_no: X\nsource_path: data/documents/permits/missing/ghost.pdf\n",
        encoding="utf-8",
    )
    # A connector-only record with no source_path at all.
    (extracted / "permits" / "c.permit.yaml").write_text(
        "permit:\n  permit_no: 2PH00006\n", encoding="utf-8"
    )

    doc_index = {"recorder/bistrozzi-deeds/202508130008300.pdf": ("pdf", True)}
    by_rel = {r.rel: r for r in export_records(extracted, doc_index=doc_index)}

    joined = by_rel["recorder/a.deed.yaml"]
    assert joined.source_doc_rel == "recorder/bistrozzi-deeds/202508130008300.pdf"
    assert joined.source_doc_render_class == "pdf"
    assert joined.source_doc_published is True

    for rel in ("permits/b.epa.yaml", "permits/c.permit.yaml"):
        rec = by_rel[rel]
        assert rec.source_doc_rel is None
        assert rec.source_doc_render_class is None
        assert rec.source_doc_published is False


def test_publish_allowlist_is_default_deny_plus_exhibits(tmp_path: Path) -> None:
    # Missing file -> nothing public EXCEPT the auto-included exhibits (default-deny).
    al = load_publish_allowlist(tmp_path / "nope.yaml", exhibit_sources=["aedg/exhibit.pdf"])
    assert al.is_published("aedg/exhibit.pdf")  # exhibit auto-included
    assert not al.is_published("recorder/secret.pdf")

    allow = tmp_path / "published-documents.yaml"
    allow.write_text(
        "collections:\n  - aedg\nglobs:\n  - 'permits/*/*.pdf'\ndocuments:\n  - recorder/one.pdf\n",
        encoding="utf-8",
    )
    al2 = load_publish_allowlist(allow, exhibit_sources=["legal/x.pdf"])
    assert al2.is_published("aedg/anything.pdf")  # whole collection
    assert al2.is_published("permits/bistrozzi-permits/4132514.pdf")  # glob
    assert al2.is_published("recorder/one.pdf")  # exact
    assert al2.is_published("legal/x.pdf")  # exhibit auto-included
    assert not al2.is_published("recorder/two.pdf")  # default-deny


def test_publishable_exhibit_sources_excludes_sliced_bundles() -> None:
    # A page-sliced exhibit publishes only its derivative slice — its full source bundle
    # must NOT be auto-included in the allowlist (else /api/doc would republish the whole
    # document the slice was carved out of). Whole-file exhibits still auto-include. #1301
    from watermark.site.exhibits import publishable_exhibit_sources
    from watermark.site.feeds import ExhibitItem

    whole = ExhibitItem(slug="nda", title="NDA", source="legal/nda.pdf", available=True)
    sliced = ExhibitItem(
        slug="opc",
        title="OPC",
        source="aedg/PRR-01-bundle.ocr.pdf",
        pages="317-327",
        available=True,
    )
    sources = publishable_exhibit_sources([whole, sliced])
    assert sources == ["legal/nda.pdf"]
    assert "aedg/PRR-01-bundle.ocr.pdf" not in sources


def test_build_doc_index_reads_published_from_entries(tmp_path: Path) -> None:
    docs = tmp_path / "documents"
    (docs / "aedg").mkdir(parents=True)
    (docs / "aedg" / "a.pdf").write_bytes(b"%PDF-1.4")
    (docs / "aedg" / "b.html").write_text("<html></html>", encoding="utf-8")
    allowlist = PublishAllowlist(documents=frozenset({"aedg/a.pdf"}))
    collections = export_documents(docs, allowlist=allowlist)
    index = build_doc_index(collections)
    assert index["aedg/a.pdf"] == ("pdf", True)
    assert index["aedg/b.html"] == ("html", False)
