"""Plain-text reads of the corpus' Office/browser source formats (#1757).

The batch-3 sanitary production (epic #1744) is the corpus' first large tranche of **native**
departmental files — Word, Excel, and Word-exported HTML rather than scans. This module is the
read side of making them searchable: pure, dependency-light text extraction for the formats that
can be read **in process**, with no external converter.

Two families, split by whether the bytes are readable without a converter:

* **Native** (:data:`NATIVE_TEXT_SUFFIXES`) — ``.txt`` / ``.htm`` / ``.html`` / ``.docx`` /
  ``.xlsx``. Read here, at index time, straight from the source bytes. Nothing is committed.
* **Legacy binary** (:data:`SIDECAR_SOURCE_SUFFIXES`) — ``.doc`` / ``.dot`` / ``.xls`` / ``.rtf``.
  OLE2/RTF containers with no in-process reader; they go through the committed text sidecars
  (:mod:`watermark.text_sidecars`), which this module does **not** produce.

**Read-only, like the rest of the package** — nothing here writes to ``data/documents/**``.

Extraction is deliberately structural, not semantic: a ``.docx`` is its ``<w:t>`` runs, an
``.xlsx`` is its cells joined by tabs, an ``.htm`` is its markup with the tags removed. That is
enough to retrieve on and to cite a file by, and it never invents content the bytes don't carry.
An unreadable file yields ``""`` — a *visible* gap the caller reports, never an exception.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
import zipfile
from pathlib import Path

# Formats read in process, straight from the source bytes (no converter, nothing committed).
NATIVE_TEXT_SUFFIXES = frozenset({".txt", ".htm", ".html", ".docx", ".xlsx"})

# Legacy binary formats with no in-process reader — served by a committed text sidecar
# (watermark.text_sidecars). Split by which LibreOffice application owns the format, because
# the two take different conversion routes (Writer → text; Calc → xlsx → xlsx_text).
WRITER_SUFFIXES = frozenset({".doc", ".dot", ".rtf"})
CALC_SUFFIXES = frozenset({".xls"})
SIDECAR_SOURCE_SUFFIXES = WRITER_SUFFIXES | CALC_SUFFIXES

# A Git-LFS pointer is a ~130-byte text stub standing in for the real bytes on a clone that
# never ran `git lfs pull`. Converting or parsing one yields the pointer's own text, so every
# reader here has to recognise it and decline (the corpus' binaries are all LFS-tracked).
_LFS_POINTER_MAGIC = b"version https://git-lfs.github.com/spec/v1"

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_PDF_MAGIC = b"%PDF"
_ZIP_MAGIC = b"PK\x03\x04"

# OLE2 directory-entry names are UTF-16LE. A Word document owns a "WordDocument" stream, an
# Excel workbook a "Workbook" (or, pre-95, "Book") stream — enough to tell the two apart when
# the file arrived with no extension at all (chain of custody: never rename a source file).
_OLE2_WORKBOOK_MARKERS = (
    "Workbook".encode("utf-16-le"),
    "Book".encode("utf-16-le"),
)
_OLE2_SNIFF_BYTES = 4 * 1024 * 1024

# A ``.docx`` visible-text run: ``<w:t>`` or ``<w:t xml:space="preserve">``, and nothing whose
# name merely STARTS with those bytes. The separator after ``w:t`` is what does the work — an
# element name continues with a name character, an attribute list begins with whitespace.
_W_RUN = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)

# A spreadsheet's used range can be inflated by stray formatting; bound the read so one
# pathological sheet can't stall an index rebuild. Truncation is marked in the output, not silent.
_MAX_SHEET_ROWS = 10_000


def is_lfs_pointer(path: Path) -> bool:
    """Whether *path* is an unresolved Git-LFS pointer rather than the real bytes."""
    try:
        with path.open("rb") as fh:
            return fh.read(len(_LFS_POINTER_MAGIC)) == _LFS_POINTER_MAGIC
    except OSError:
        return False


def _sniff_zip_suffix(path: Path) -> str:
    """``.xlsx`` when an extensionless OOXML zip is a workbook, else ``.docx``.

    Both formats are zips with the same magic, so the part name decides: a workbook keeps its
    sheets under ``xl/``, a document its body under ``word/``. An unreadable archive falls back
    to ``.docx`` — :func:`docx_text` reports it as an empty read, which is the same visible gap
    any other broken container produces.
    """
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
    except (zipfile.BadZipFile, OSError):
        return ".docx"
    return ".xlsx" if any(n.startswith("xl/") for n in names) else ".docx"


def detect_suffix(path: Path) -> str:
    """The effective lower-case format suffix for *path*.

    Normally just its extension. Three files in the sanitary production arrived with **no**
    extension and are kept that way (chain of custody), so a suffix-less file is sniffed from its
    magic bytes instead: ``%PDF`` → ``.pdf``; a zip → the OOXML kind its parts name
    (:func:`_sniff_zip_suffix`); an OLE2 container → ``.xls`` when it carries a workbook stream,
    else ``.doc``. Returns ``""`` when the format can't be identified.
    """
    suffix = path.suffix.lower()
    if suffix:
        return suffix
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
            if head.startswith(_PDF_MAGIC):
                return ".pdf"
            if head.startswith(_ZIP_MAGIC):
                return _sniff_zip_suffix(path)
            if not head.startswith(_OLE2_MAGIC):
                return ""
            body = head + fh.read(_OLE2_SNIFF_BYTES)
    except OSError:
        return ""
    if any(marker in body for marker in _OLE2_WORKBOOK_MARKERS):
        return ".xls"
    return ".doc"


# Text arriving from a county file server predates UTF-8 by two decades: a third of the sanitary
# production's .txt/.htm files are cp1252 (Word's "Western European" default), where a curly quote
# or a non-breaking space is one byte that UTF-8 can't decode. Guessing utf-8 turns those into
# replacement-character noise mid-sentence, so decode by evidence instead.
_CHARSET_DECL = re.compile(rb"""charset=["']?([A-Za-z0-9_-]+)""", re.IGNORECASE)
_CHARSET_SNIFF_BYTES = 4096
_FALLBACK_ENCODING = "cp1252"  # a superset of latin-1: decodes any byte, never raises


def _decode(raw: bytes, *, declared: str | None = None) -> str:
    """Decode *raw* by evidence: a declared charset, then a BOM, then UTF-8, then cp1252.

    UTF-8 is self-validating — a byte string that decodes strictly is almost never accidentally
    valid — so trying it before the cp1252 fallback identifies modern files correctly without a
    charset library. The fallback cannot fail, so this always returns text.
    """
    for encoding in (declared, "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else None, "utf-8"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode(_FALLBACK_ENCODING, errors="replace")


def _declared_charset(raw: bytes) -> str | None:
    """The charset an HTML document declares in its head, if any."""
    match = _CHARSET_DECL.search(raw[:_CHARSET_SNIFF_BYTES])
    return match.group(1).decode("ascii", "ignore") if match else None


def plain_text(path: Path) -> str:
    """Read a plain-text source, decoded by evidence (:func:`_decode`). Unreadable → ``""``."""
    try:
        return _decode(path.read_bytes())
    except OSError:
        return ""


def docx_text(path: Path) -> str:
    """The visible text of a ``.docx`` (an OOXML zip), paragraph by paragraph.

    ``word/document.xml`` holds the body; ``<w:t>`` elements are the visible runs and ``<w:p>``
    the paragraph boundaries, so joining runs within a paragraph and paragraphs with newlines
    preserves the block structure the chunker splits on. A file that isn't a readable zip (a
    Git-LFS pointer, a truncated copy) yields ``""``.

    ⚠️ The run pattern must not treat ``w:t`` as a *prefix*. WordprocessingML is full of elements
    that begin with those bytes — ``w:tab``, ``w:tabs``, ``w:tbl``, ``w:tblPr``, ``w:tc``,
    ``w:tcPr``, ``w:tr`` — so a ``<w:t[^>]*>`` open pattern matches ``<w:tabs>`` and then runs
    non-greedily to the *next* ``</w:t>``, splicing every tab stop and table property in between
    into the document's text. Measured on one committed Lima Planning Commission minute
    (``_05242023-811.docx``): 29,409 "characters" of which 12,441 were markup. The damage was
    bounded only by the paragraph split, which is why it read as plausible text rather than
    obvious garbage.
    """
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    paragraphs = [
        _html.unescape("".join(_W_RUN.findall(block))).strip() for block in re.split(r"</w:p>", xml)
    ]
    return "\n".join(p for p in paragraphs if p)


def _cell(value: object) -> str:
    """One spreadsheet cell as text — dates as ISO, blanks as empty."""
    if value is None:
        return ""
    if isinstance(value, _dt.datetime):
        return value.date().isoformat() if value.time() == _dt.time.min else value.isoformat(" ")
    if isinstance(value, _dt.date):
        return value.isoformat()
    return str(value)


def xlsx_text(path: Path) -> str:
    """An ``.xlsx`` workbook as tab-separated text, one ``### <sheet>`` block per worksheet.

    Cached values are read (``data_only=True``) rather than formulas — a spreadsheet's *numbers*
    are what a records question is about. All-blank rows are dropped so a sparse sheet doesn't
    become a wall of tabs. This is also the renderer behind the ``.xls`` sidecar, so legacy and
    modern workbooks land in the same shape.
    """
    import openpyxl

    try:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:  # a pointer, a corrupt zip, an unsupported variant — a gap, not a crash
        return ""
    try:
        blocks: list[str] = []
        for sheet in book.worksheets:
            lines: list[str] = []
            truncated = False
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_idx >= _MAX_SHEET_ROWS:
                    truncated = True
                    break
                cells = [_cell(v) for v in row]
                if any(c.strip() for c in cells):
                    lines.append("\t".join(cells).rstrip("\t"))
            if truncated:
                lines.append(f"[truncated at {_MAX_SHEET_ROWS} rows]")
            if lines:
                blocks.append(f"### {sheet.title}\n" + "\n".join(lines))
        return "\n\n".join(blocks)
    finally:
        book.close()


_HTML_DROP_BLOCKS = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_BLOCK_END = re.compile(
    r"</(p|div|tr|li|h[1-6]|table|blockquote)\s*>|<br\s*/?>", re.IGNORECASE
)
_HTML_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")


def html_text(path: Path) -> str:
    """The visible text of an ``.htm``/``.html`` file, tags removed.

    The production's HTML is Word's "web page" export of email threads, which carries kilobytes
    of MSO stylesheet inside ``<style>`` blocks and conditional comments — dropped first, so the
    text is the message and not the boilerplate. Block-level closers become newlines, which keeps
    the paragraph boundaries the chunker splits on. Word declares its own ``charset`` in the head
    (usually ``windows-1252``); that declaration is honoured over any guess.
    """
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    raw = _decode(data, declared=_declared_charset(data))
    if not raw:
        return ""
    raw = _HTML_DROP_BLOCKS.sub(" ", raw)
    raw = _HTML_COMMENT.sub(" ", raw)
    raw = _HTML_BLOCK_END.sub("\n", raw)
    text = _html.unescape(_HTML_TAG.sub(" ", raw))
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return _BLANK_RUN.sub("\n\n", "\n".join(lines)).strip()


def read_native_text(path: Path, *, suffix: str | None = None) -> tuple[str, str]:
    """``(text, method)`` for a natively readable source; ``("", "none")`` when it isn't one.

    ``method`` names the reader that produced the text (``txt`` / ``html`` / ``docx`` / ``xlsx``)
    so a caller can record *how* a file became searchable, and is ``none`` whenever the text came
    out empty — an image-only export or an unresolved LFS pointer is a reported gap, not a silent
    one. Pass ``suffix`` to reuse an already-computed :func:`detect_suffix`.
    """
    effective = suffix if suffix is not None else detect_suffix(path)
    if effective not in NATIVE_TEXT_SUFFIXES or is_lfs_pointer(path):
        return ("", "none")
    if effective == ".txt":
        text, method = plain_text(path), "txt"
    elif effective in {".htm", ".html"}:
        text, method = html_text(path), "html"
    elif effective == ".docx":
        text, method = docx_text(path), "docx"
    else:
        text, method = xlsx_text(path), "xlsx"
    text = text.strip()
    return (text, method if text else "none")
