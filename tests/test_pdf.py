"""Integration tests for PdfDocument against the real PRR bundle.

Skipped when the 137 MB source PDF is not materialized (e.g. a CI checkout with
only the Git LFS pointer present).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.documents import PdfDocument

REPO_ROOT = Path(__file__).resolve().parents[1]
PDF = REPO_ROOT / "data" / "documents" / "aedg" / "PRR-01-bundle.ocr.pdf"


def _real_pdf_available() -> bool:
    if not PDF.exists():
        return False
    with PDF.open("rb") as fh:  # don't read 137 MB — just the magic bytes
        return fh.read(8).startswith(b"%PDF")


pytestmark = pytest.mark.skipif(
    not _real_pdf_available(), reason="real PDF not materialized (LFS pointer only)"
)


def test_reads_page_count_and_text() -> None:
    with PdfDocument(PDF) as pdf:
        assert pdf.page_count == 328
        # 0-based page 318 == printed Diller sheet (pdf_page 319).
        assert "Diller" in pdf.page_text(318)


def test_renders_page_to_png() -> None:
    with PdfDocument(PDF) as pdf:
        png = pdf.render_page_png(318, dpi=72)  # low DPI keeps the test fast
        assert png.startswith(b"\x89PNG\r\n\x1a\n")


def test_out_of_range_page_raises() -> None:
    with PdfDocument(PDF) as pdf, pytest.raises(IndexError):
        pdf.page_text(99_999)
