# CLAUDE.md — `watermark.documents`

Read-only source-document access. Defers to the root [`CLAUDE.md`](../../../CLAUDE.md).

- **Read-only.** Nothing here writes to `data/documents/**` (immutable evidence). The one
  writer in the corpus tree is `watermark.text_sidecars`, and it writes only into a `-text`
  sibling directory — never a source byte, never inside an as-received tree.
- `pdf.py` — two licence-clean backends: **pypdf** (BSD) for the OCR text layer
  (cheap structural hint; digits unreliable on degraded scans) and **pypdfium2**
  (PDFium) to render a page raster at a DPI for authoritative vision reading. Pages
  are **0-based**; printed `pdf_page == index + 1`.
- `odg.py` — OpenDocument Drawing (a zip of XML). Here the relationship inverts:
  **text leads, the preview thumbnail hints** (the scan hybrid is the opposite).
  Reads are deliberately CRC-tolerant — engineering exports can exceed 70 MB and
  ship a bad CRC on `content.xml`; salvage what decompresses rather than failing.
- `office.py` — the corpus' **native** Office/browser formats (#1757), split by whether the
  bytes are readable without an external converter. **Native** (`NATIVE_TEXT_SUFFIXES`:
  `.txt/.htm/.html/.docx/.xlsx`) are read here, in process, at index time — a `.docx` is its
  `<w:t>` runs (concatenated within a `<w:p>`, so no phantom spaces), an `.xlsx` is its cells
  tab-joined per sheet, an `.htm` is its markup with `<style>`/`<script>`/comments dropped first
  (Word's "web page" export is mostly MSO stylesheet). **Legacy binary** (`.doc/.dot/.xls/.rtf`)
  have no in-process reader and are served by the committed sidecars in
  `watermark.text_sidecars` — this module never produces one. Two cross-cutting rules: text is
  decoded **by evidence** (declared charset → BOM → strict UTF-8 → cp1252; a third of the
  sanitary production's `.txt`/`.htm` is cp1252, and guessing UTF-8 shreds it), and
  `detect_suffix` sniffs magic bytes for the extensionless files the corpus keeps as-received.
  An unreadable file returns `""` — a gap the caller reports, never an exception.
- `image.py` — raster scans (`.png/.jpg/.tif`) with **no text layer** (#703):
  decode + re-encode to PNG (the extractor pins `image/png`) and hand the single
  image straight to the vision model, no OCR hint. The document *kind* dispatch is
  unchanged — an image source flows through the same `extract_<kind>` as a PDF; it's
  an alternate *source format*, not a new kind (`_read_doc` branches on `is_image`).
- New backends should stay permissively licensed (this is a proprietary project).
