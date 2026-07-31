"""Native text reads of the corpus' Office/browser formats (#1757).

Hermetic: every fixture is synthesized in ``tmp_path`` (a real OOXML zip, a real openpyxl
workbook, real cp1252 bytes) — no committed binaries, no LibreOffice, no network.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from watermark.documents.office import (
    detect_suffix,
    docx_text,
    html_text,
    is_lfs_pointer,
    plain_text,
    read_native_text,
    xlsx_text,
)

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _docx(path: Path, body: str) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", body)
    return path


# --- .docx ---------------------------------------------------------------------------------------
def test_docx_text_joins_runs_within_a_paragraph_and_splits_on_paragraphs(tmp_path: Path) -> None:
    # Word splits a sentence across runs mid-word; joining runs with a separator would inject
    # spaces the document doesn't have, so runs concatenate and only <w:p> makes a break.
    path = _docx(
        tmp_path / "a.docx",
        "<w:p><w:t>Findings and </w:t><w:t>Orders</w:t></w:p>"
        "<w:p><w:t>SSO closure &amp; report</w:t></w:p>",
    )
    assert docx_text(path) == "Findings and Orders\nSSO closure & report"


def test_docx_text_drops_empty_paragraphs(tmp_path: Path) -> None:
    path = _docx(
        tmp_path / "a.docx", "<w:p><w:t>One</w:t></w:p><w:p></w:p><w:p><w:t>Two</w:t></w:p>"
    )
    assert docx_text(path) == "One\nTwo"


def test_docx_text_on_a_non_zip_is_a_gap_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip at all")
    assert docx_text(path) == ""


# --- .xlsx ---------------------------------------------------------------------------------------
def test_xlsx_text_renders_every_sheet_with_tabs_and_iso_dates(tmp_path: Path) -> None:
    import datetime

    import openpyxl

    book = openpyxl.Workbook()
    first = book.active
    first.title = "1-APPL. INFO."
    first.append(["APPLICANT:", "Allen County Commissioners"])
    first.append([None, None])  # an all-blank row is dropped, not rendered as bare tabs
    first.append(["Submitted", datetime.datetime(2008, 5, 6)])
    second = book.create_sheet("2-SCHED.")
    second.append(["Design", 200000])
    book.save(tmp_path / "wb.xlsx")

    text = xlsx_text(tmp_path / "wb.xlsx")
    assert text.splitlines() == [
        "### 1-APPL. INFO.",
        "APPLICANT:\tAllen County Commissioners",
        "Submitted\t2008-05-06",
        "",
        "### 2-SCHED.",
        "Design\t200000",
    ]


def test_xlsx_text_on_a_non_workbook_is_a_gap_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "broken.xlsx"
    path.write_bytes(b"PK\x03\x04 truncated")
    assert xlsx_text(path) == ""


# --- .htm / .html --------------------------------------------------------------------------------
def test_html_text_drops_style_script_and_conditional_comments(tmp_path: Path) -> None:
    path = tmp_path / "email.htm"
    path.write_text(
        "<html><head><style>p.MsoNormal {margin:0in;}</style>"
        "<!--[if gte mso 9]><xml>junk</xml><![endif]--></head>"
        "<body><p>Subject: Bath Trunk Sizing</p><p>Guys&mdash;</p>"
        "<script>var x = 1;</script></body></html>",
        encoding="utf-8",
    )
    text = html_text(path)
    assert "MsoNormal" not in text
    assert "var x" not in text
    assert "junk" not in text
    assert "Subject: Bath Trunk Sizing" in text
    assert "Guys—" in text


def test_html_text_honours_a_declared_windows_1252_charset(tmp_path: Path) -> None:
    # Word's "web page" export declares cp1252; its non-breaking spaces and em dashes are single
    # bytes that are invalid UTF-8, so guessing utf-8 would litter the text with U+FFFD.
    path = tmp_path / "word.htm"
    path.write_bytes(
        b'<html><head><meta http-equiv=Content-Type content="text/html; charset=windows-1252">'
        b"</head><body><p>From:\xa0Mike\x97URS</p></body></html>"
    )
    text = html_text(path)
    assert "�" not in text
    assert "Mike—URS" in text


def test_html_text_block_closers_become_line_breaks(tmp_path: Path) -> None:
    path = tmp_path / "b.htm"
    path.write_text("<div>One</div><div>Two</div>", encoding="utf-8")
    assert html_text(path) == "One\nTwo"


# --- decoding ------------------------------------------------------------------------------------
def test_plain_text_falls_back_to_cp1252_for_undecodable_bytes(tmp_path: Path) -> None:
    path = tmp_path / "legacy.txt"
    path.write_bytes(b"Ottawa River \x96 7Q10 \x93low flow\x94")
    # cp1252 0x96/0x93/0x94 are en-dash and curly quotes — written as escapes so the assertion
    # can't be "fixed" by an editor normalising the very punctuation it is about.
    assert plain_text(path) == "Ottawa River \u2013 7Q10 \u201clow flow\u201d"


def test_plain_text_prefers_utf8_when_it_decodes(tmp_path: Path) -> None:
    path = tmp_path / "modern.txt"
    path.write_text("Auglaize — 0.614 ratio", encoding="utf-8")
    assert plain_text(path) == "Auglaize — 0.614 ratio"


# --- format detection ----------------------------------------------------------------------------
def test_detect_suffix_uses_the_extension_when_there_is_one(tmp_path: Path) -> None:
    path = tmp_path / "Order.DOC"
    path.write_bytes(_OLE2)
    assert detect_suffix(path) == ".doc"


def test_detect_suffix_sniffs_an_extensionless_pdf(tmp_path: Path) -> None:
    # Three files in the sanitary production arrived with no extension and are never renamed
    # (chain of custody), so the format has to come from the bytes.
    path = tmp_path / "Flow Calculations American-Bath feb 6, 2008"
    path.write_bytes(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    assert detect_suffix(path) == ".pdf"


def test_detect_suffix_tells_an_ole2_workbook_from_an_ole2_document(tmp_path: Path) -> None:
    doc = tmp_path / "Revised Change Order"
    doc.write_bytes(_OLE2 + b"\x00" * 64 + "WordDocument".encode("utf-16-le"))
    assert detect_suffix(doc) == ".doc"

    xls = tmp_path / "Amort"
    xls.write_bytes(_OLE2 + b"\x00" * 64 + "Workbook".encode("utf-16-le"))
    assert detect_suffix(xls) == ".xls"


def test_detect_suffix_tells_an_extensionless_workbook_zip_from_a_document_zip(
    tmp_path: Path,
) -> None:
    # .docx and .xlsx are both zips with the same magic; the OOXML part names decide, so a
    # suffix-less workbook isn't handed to the docx reader (which would find no body and
    # report an empty read).
    book = tmp_path / "Amort"
    with zipfile.ZipFile(book, "w") as z:
        z.writestr("xl/workbook.xml", "<workbook/>")
    assert detect_suffix(book) == ".xlsx"

    doc = tmp_path / "Memo"
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/document.xml", "<w:p/>")
    assert detect_suffix(doc) == ".docx"


def test_detect_suffix_falls_back_to_docx_for_a_truncated_zip(tmp_path: Path) -> None:
    path = tmp_path / "Truncated"
    path.write_bytes(b"PK\x03\x04 not really an archive")
    assert detect_suffix(path) == ".docx"  # read as a gap downstream, not a crash


def test_detect_suffix_is_empty_for_an_unidentifiable_extensionless_file(tmp_path: Path) -> None:
    path = tmp_path / "mystery"
    path.write_bytes(b"\x01\x02\x03\x04")
    assert detect_suffix(path) == ""


# --- LFS pointers --------------------------------------------------------------------------------
def test_is_lfs_pointer_recognises_an_unresolved_pointer(tmp_path: Path) -> None:
    path = tmp_path / "big.docx"
    path.write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 12\n", encoding="utf-8"
    )
    assert is_lfs_pointer(path)


def test_read_native_text_declines_an_lfs_pointer_rather_than_transcribing_it(
    tmp_path: Path,
) -> None:
    # The pointer stub is valid text; indexing it would put "git-lfs.github.com" in the corpus.
    path = tmp_path / "minutes.docx"
    path.write_text(
        "version https://git-lfs.github.com/spec/v1\noid sha256:abc\n", encoding="utf-8"
    )
    assert read_native_text(path) == ("", "none")


# --- the dispatcher ------------------------------------------------------------------------------
def test_read_native_text_reports_the_reader_that_produced_the_text(tmp_path: Path) -> None:
    txt = tmp_path / "notes.txt"
    txt.write_text("Shawnee II DFFO extension", encoding="utf-8")
    assert read_native_text(txt) == ("Shawnee II DFFO extension", "txt")

    doc = _docx(tmp_path / "a.docx", "<w:p><w:t>Hume Road</w:t></w:p>")
    assert read_native_text(doc) == ("Hume Road", "docx")


def test_read_native_text_declines_a_legacy_binary(tmp_path: Path) -> None:
    # .doc has no in-process reader; it is served by a committed sidecar instead.
    path = tmp_path / "letter.doc"
    path.write_bytes(_OLE2)
    assert read_native_text(path) == ("", "none")


def test_read_native_text_reports_none_when_the_document_is_empty(tmp_path: Path) -> None:
    path = _docx(tmp_path / "blank.docx", "<w:p></w:p>")
    assert read_native_text(path) == ("", "none")
