"""Tests for document-level extraction (deeds, NPDES permits)."""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from PIL import Image

from watermark.agent.extractor import ExtractionError, StructuredExtractor
from watermark.config import Settings
from watermark.documents import IMAGE_SUFFIXES, read_image_png
from watermark.models import (
    BusinessFiling,
    Deed,
    DeedExtraction,
    EpaExtraction,
    EpaPermitAction,
    NoticeExtraction,
    NoticeOfCommencement,
    NpdesExtraction,
    NpdesPermit,
    SosExtraction,
)
from watermark.pipeline.extract import (
    extract_deed,
    extract_document,
    extract_epa,
    extract_notice,
    extract_npdes,
    extract_sos,
    save_doc_extraction,
)
from watermark.pipeline.ingest import SOURCE_SUFFIXES, SourceDocument


# --- fakes -----------------------------------------------------------------
class _Block:
    def __init__(self, type: str, name: str | None = None, input: Any = None) -> None:
        self.type, self.name, self.input = type, name, input


class _FakeClient:
    def __init__(self, blocks: list[_Block]) -> None:
        self.capture: dict[str, Any] = {}
        outer = self

        class _Messages:
            def create(self, **kwargs: Any) -> Any:
                outer.capture = kwargs
                return SimpleNamespace(content=blocks)

        self.messages = _Messages()


class _FakePdf:
    def __init__(self, pages: int = 3) -> None:
        self._n = pages

    @property
    def page_count(self) -> int:
        return self._n

    def page_text(self, index: int) -> str:
        return f"text {index}"

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        return b"\x89PNG-fake"

    def close(self) -> None:  # pragma: no cover
        pass


class _FakeExtractor:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def extract(
        self,
        target: Any,
        *,
        instructions: str,
        images: list[bytes] | None = None,
        image_png: bytes | None = None,
        context_text: str = "",
    ) -> Any:
        self.calls.append({"images": images, "context": context_text})
        return self.result


def _doc(name: str = "PRR.pdf") -> SourceDocument:
    return SourceDocument(
        path=Path(f"/data/documents/recorder/{name}"),
        doc_id="abc-1234",
        suffix=".pdf",
        size_bytes=10,
        collection="recorder",
    )


# --- models ----------------------------------------------------------------
def test_deed_consideration_coercion() -> None:
    d = Deed(consideration="$1,250,000", grantees=["Tilted Gate LLC"])
    assert d.consideration == 1250000
    assert d.confidence == "medium"  # default from the _Extracted mixin


def test_str_list_fields_tolerate_a_bare_string() -> None:
    # The LLM sometimes returns a list field as a single string; wrap, don't fail.
    d = Deed(grantors="Lone Grantor", warnings="one warning")
    assert d.grantors == ["Lone Grantor"]
    assert d.warnings == ["one warning"]
    assert Deed(grantors="").grantors == []  # empty string -> empty list


def test_npdes_basic_model() -> None:
    p = NpdesPermit(
        permit_no="2PH00006*LD", facility_name="American II WWTP", receiving_water="Pike Run"
    )
    assert p.permit_no == "2PH00006*LD"
    assert p.warnings == []


# --- extractor multi-image -------------------------------------------------
def test_extractor_sends_multiple_images() -> None:
    client = _FakeClient([_Block("tool_use", "record_extraction", {"instrument_type": "Deed"})])
    StructuredExtractor(client=client).extract(
        Deed, instructions="read", images=[b"a", b"b", b"c"], context_text="ctx"
    )
    content = client.capture["messages"][0]["content"]
    assert sum(1 for c in content if c["type"] == "image") == 3
    assert content[-1]["type"] == "text" and "read" in content[-1]["text"]


def test_extractor_flags_max_tokens_truncation() -> None:
    # A max_tokens stop with no tool call raises a distinct, actionable error rather
    # than the opaque "did not call tool" (#613).
    from watermark.agent.extractor import _first_tool_input

    msg = SimpleNamespace(content=[_Block("text")], stop_reason="max_tokens")
    with pytest.raises(ExtractionError, match="max_tokens"):
        _first_tool_input(msg, "record_extraction")
    # A non-truncation non-call still raises, now naming the stop_reason.
    msg2 = SimpleNamespace(content=[_Block("text")], stop_reason="end_turn")
    with pytest.raises(ExtractionError, match="end_turn"):
        _first_tool_input(msg2, "record_extraction")


# --- pipeline --------------------------------------------------------------
def test_extract_deed_attaches_provenance() -> None:
    deed = Deed(
        instrument_type="General Warranty Deed",
        instrument_no="202511180011830",
        grantees=["Anonymous LLC"],
        parcel_ids=["P1", "P2"],
    )
    extraction = extract_deed(_doc(), extractor=_FakeExtractor(deed), pdf=_FakePdf(pages=6))  # type: ignore[arg-type]
    assert isinstance(extraction, DeedExtraction)
    assert extraction.kind == "deed"
    assert extraction.deed.instrument_no == "202511180011830"
    assert extraction.pages_read == list(range(6))  # all 6 pages read
    assert extraction.image_pages_read == list(range(6))  # deed is vision-primary (#613)


def test_extract_npdes_attaches_provenance() -> None:
    permit = NpdesPermit(permit_no="2PH00006*LD", facility_name="American II WWTP")
    extraction = extract_npdes(_doc(), extractor=_FakeExtractor(permit), pdf=_FakePdf(pages=30))  # type: ignore[arg-type]
    assert isinstance(extraction, NpdesExtraction)
    assert extraction.permit.permit_no == "2PH00006*LD"
    assert extraction.pages_read == list(range(6))  # text_pages=6 dominates the 1 image page
    # …but only page 0 was rendered as an image and sent to the model (#613).
    assert extraction.image_pages_read == [0]


def test_extract_sos_attaches_provenance() -> None:
    filing = BusinessFiling(
        entity_name="Tilted Gate LLC",
        entity_type="foreign LLC",
        jurisdiction="Delaware",
        registered_agent="Corporation Service Company",
        organizer="Michael Montfort",
    )
    extraction = extract_sos(_doc(), extractor=_FakeExtractor(filing), pdf=_FakePdf(pages=4))  # type: ignore[arg-type]
    assert isinstance(extraction, SosExtraction)
    assert extraction.kind == "sos"
    assert extraction.filing.jurisdiction == "Delaware"
    assert extraction.pages_read == list(range(4))


def test_extract_epa_attaches_provenance() -> None:
    action = EpaPermitAction(
        agency="Ohio EPA",
        program="Surface Water Permit-to-Install",
        permit_no="DSWPTI-260294",
        action="approved",
        action_date="2026-04-07",
        applicant="Bistrozzi LLC",
        project_name="BOSC-1A",
        contact_name="Scott Ziance",
        contact_firm="Vorys",
    )
    extraction = extract_epa(_doc(), extractor=_FakeExtractor(action), pdf=_FakePdf(pages=5))  # type: ignore[arg-type]
    assert isinstance(extraction, EpaExtraction)
    assert extraction.kind == "epa"
    assert extraction.action.permit_no == "DSWPTI-260294"
    assert extraction.pages_read == list(range(3))  # text_pages=3 dominates the 1 image page


def test_extract_notice_attaches_provenance() -> None:
    notice = NoticeOfCommencement(
        project_name="Project BOSC",
        building_footprint_sf=283497,
        parcel_ids=["36-1200-03-001.000"],
        original_contractors=["Turner Construction Company"],
        contract_execution_date="2025-05-15",
        instrument_no="202606250006699",
    )
    doc = _doc()
    extractor = _FakeExtractor(notice)
    extraction = extract_notice(doc, extractor=extractor, pdf=_FakePdf(pages=21))  # type: ignore[arg-type]
    assert isinstance(extraction, NoticeExtraction)
    assert extraction.kind == "notice"
    assert extraction.doc_id == doc.doc_id
    assert extraction.source_path == str(doc.path)
    assert extraction.dpi == 200  # _NOTICE_DPI; doc is a PDF, not a raster source
    assert extraction.notice.building_footprint_sf == 283497
    assert extraction.notice.contract_execution_date == "2025-05-15"
    # notice is vision-primary but reads only its own substantive pages, not an
    # attached exhibit re-recording prior deeds (#1491) — text_pages=2 dominates
    # the 21-page source.
    assert extraction.pages_read == [0, 1]
    assert extraction.image_pages_read == [0, 1]
    # The extractor received exactly the first 2 pages' text/images (#613: an
    # honest image_pages_read means the model only ever saw what's recorded there).
    assert len(extractor.calls) == 1
    assert extractor.calls[0]["images"] == [b"\x89PNG-fake", b"\x89PNG-fake"]
    assert extractor.calls[0]["context"] == "text 0\n\ntext 1"


def test_extract_document_dispatch_and_unknown() -> None:
    permit = NpdesPermit(permit_no="X")
    ex = extract_document(_doc(), kind="npdes", extractor=_FakeExtractor(permit), pdf=_FakePdf())  # type: ignore[arg-type]
    assert isinstance(ex, NpdesExtraction)
    filing = BusinessFiling(entity_name="Acme LLC")
    sos = extract_document(
        _doc(), kind="sos", extractor=_FakeExtractor(filing), pdf=_FakePdf(pages=4)
    )  # type: ignore[arg-type]
    assert isinstance(sos, SosExtraction)
    with pytest.raises(ValueError, match="unknown document kind"):
        extract_document(_doc(), kind="invoice")


def test_save_doc_extraction_filename(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    extraction = NpdesExtraction(
        doc_id="d",
        source_path="/x/oepa-2PH00006-american-ii-permit.pdf",
        kind="npdes",
        dpi=150,
        permit=NpdesPermit(permit_no="2PH00006"),
    )
    path = save_doc_extraction(extraction, settings=settings)
    # Source lives outside data/documents -> lands at the extracted root.
    assert path.parent == settings.extracted_dir
    assert path.name == "oepa-2PH00006-american-ii-permit.npdes.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["permit"]["permit_no"] == "2PH00006"


def test_save_doc_extraction_mirrors_collection(tmp_path: Path) -> None:
    """A source under documents/<collection> lands under extracted/<collection>."""
    settings = Settings(data_dir=tmp_path)
    src = settings.documents_dir / "recorder" / "202511180011830-amazon-deed.pdf"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"%PDF-fake")
    extraction = DeedExtraction(
        doc_id="d",
        source_path=str(src),
        kind="deed",
        dpi=200,
        deed=Deed(instrument_no="202511180011830"),
    )
    path = save_doc_extraction(extraction, settings=settings)
    assert path.parent == settings.extracted_dir / "recorder"
    assert path.name == "202511180011830-amazon-deed.deed.yaml"


# --- raster image sources (#703) -------------------------------------------
def _img_doc(path: Path) -> SourceDocument:
    return SourceDocument(path=path, doc_id="img-1234", suffix=path.suffix.lower(), size_bytes=0)


def test_image_suffixes_are_admitted_to_the_extraction_inventory() -> None:
    # #619 dropped images from the inventory because no path existed; #703 re-admits them.
    assert IMAGE_SUFFIXES <= SOURCE_SUFFIXES
    assert {".png", ".jpg", ".jpeg", ".tif", ".tiff"} <= SOURCE_SUFFIXES
    assert _img_doc(Path("/x/scan.png")).is_image
    assert not _img_doc(Path("/x/scan.png")).is_pdf
    assert not _doc().is_image  # a .pdf is not an image


def test_read_image_png_reencodes_non_png_to_png(tmp_path: Path) -> None:
    # A .jpg / .tif source must come back as valid PNG bytes (the extractor pins image/png).
    for name, fmt in [("scan.jpg", "JPEG"), ("scan.tif", "TIFF")]:
        src = tmp_path / name
        Image.new("RGB", (8, 8), (200, 100, 50)).save(src, format=fmt)
        out = read_image_png(src)
        assert out[:8] == b"\x89PNG\r\n\x1a\n"  # PNG signature
        assert Image.open(io.BytesIO(out)).format == "PNG"


def test_read_image_png_flattens_cmyk_and_alpha(tmp_path: Path) -> None:
    # CMYK TIFF and RGBA PNG modes flatten to RGB rather than failing the PNG encode.
    cmyk = tmp_path / "cmyk.tif"
    Image.new("CMYK", (4, 4)).save(cmyk, format="TIFF")
    rgba = tmp_path / "alpha.png"
    Image.new("RGBA", (4, 4), (1, 2, 3, 128)).save(rgba, format="PNG")
    for src in (cmyk, rgba):
        assert Image.open(io.BytesIO(read_image_png(src))).mode == "RGB"


def test_extract_deed_from_image_source_sends_raw_image_no_text(tmp_path: Path) -> None:
    # The headline #703 path: a .png scan extracts through the same extract_deed as a PDF,
    # but with the single image and NO OCR text hint, and an honest dpi=0.
    src = tmp_path / "deed-scan.png"
    Image.new("RGB", (16, 16), (255, 255, 255)).save(src, format="PNG")
    deed = Deed(instrument_no="202511180011830", grantees=["Anonymous LLC"])
    extractor = _FakeExtractor(deed)
    extraction = extract_deed(_img_doc(src), extractor=extractor)  # type: ignore[arg-type]

    assert isinstance(extraction, DeedExtraction)
    assert extraction.deed.instrument_no == "202511180011830"
    assert extraction.pages_read == [0]
    assert extraction.image_pages_read == [0]
    assert extraction.dpi == 0  # a raster source isn't rendered at a DPI
    # the extractor saw exactly one image and no text hint
    (call,) = extractor.calls
    assert call["context"] == ""
    assert call["images"] is not None and len(call["images"]) == 1
    assert call["images"][0][:8] == b"\x89PNG\r\n\x1a\n"
