"""Read-only access to a PDF's text layer and rendered page images.

Two backends, chosen for permissive licenses (this is a proprietary project):

* **pypdf** (BSD) — extract the embedded OCR text layer. Cheap, but on degraded
  scans the *digits* are unreliable; treat the text as a structural hint only.
* **pypdfium2** (Apache/BSD, Google PDFium) — render a page to a raster image at
  a chosen DPI, for authoritative *visual* reading by a vision model.

Pages are addressed by 0-based index. The cost sheets' printed ``pdf_page`` is
1-based, so ``pdf_page == index + 1``.
"""

from __future__ import annotations

import io
from pathlib import Path
from types import TracebackType

import pypdf
import pypdfium2 as pdfium

# The reference extractions were read at 300 DPI; match that by default.
DEFAULT_DPI = 300
_PDF_NATIVE_DPI = 72.0


class PdfDocument:
    """Lazily-opened, read-only handle to a PDF for text and image access."""

    def __init__(self, path: str | Path, *, dpi: int = DEFAULT_DPI) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.dpi = dpi
        self._reader: pypdf.PdfReader | None = None
        self._pdfium: pdfium.PdfDocument | None = None

    # -- lazy backends ------------------------------------------------------
    @property
    def _pypdf(self) -> pypdf.PdfReader:
        if self._reader is None:
            self._reader = pypdf.PdfReader(str(self.path))
        return self._reader

    @property
    def _render(self) -> pdfium.PdfDocument:
        if self._pdfium is None:
            self._pdfium = pdfium.PdfDocument(str(self.path))
        return self._pdfium

    # -- access -------------------------------------------------------------
    @property
    def page_count(self) -> int:
        return len(self._pypdf.pages)

    def _check_index(self, index: int) -> None:
        if not 0 <= index < self.page_count:
            raise IndexError(f"page index {index} out of range (0..{self.page_count - 1})")

    def page_text(self, index: int) -> str:
        """Return the embedded OCR text for a page (may be empty/garbled)."""
        self._check_index(index)
        return self._pypdf.pages[index].extract_text() or ""

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        """Render a page to PNG bytes at ``dpi`` (default :data:`DEFAULT_DPI`)."""
        self._check_index(index)
        scale = (dpi or self.dpi) / _PDF_NATIVE_DPI
        bitmap = self._render[index].render(scale=scale)
        image = bitmap.to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    # -- lifecycle ----------------------------------------------------------
    def close(self) -> None:
        if self._pdfium is not None:
            self._pdfium.close()
            self._pdfium = None
        self._reader = None

    def __enter__(self) -> PdfDocument:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
