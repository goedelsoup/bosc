"""Tests for the structured extractor and the extract pipeline orchestration.

No network or API key: the Anthropic client and the PDF are replaced with fakes.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from bosc.agent.extractor import ExtractionError, StructuredExtractor
from bosc.config import Settings
from bosc.models import EstimateExtraction, PageExtraction
from bosc.pipeline.extract import extract_estimate_page, save_extraction
from bosc.pipeline.ingest import SourceDocument


# --- fakes -----------------------------------------------------------------
class _Block:
    def __init__(self, type: str, name: str | None = None, input: Any = None) -> None:
        self.type = type
        self.name = name
        self.input = input


class _FakeClient:
    """Stand-in for anthropic.Anthropic; records the last create() kwargs."""

    def __init__(self, blocks: list[_Block]) -> None:
        self.capture: dict[str, Any] = {}
        outer = self

        class _Messages:
            def create(self, **kwargs: Any) -> Any:
                outer.capture = kwargs
                return SimpleNamespace(content=blocks)

        self.messages = _Messages()


class _FakePdf:
    def __init__(self) -> None:
        self.closed = False

    def page_text(self, index: int) -> str:
        return f"OCR text for page {index}"

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        return b"\x89PNG-fake"

    def close(self) -> None:
        self.closed = True


class _FakeExtractor:
    def __init__(self, estimate: EstimateExtraction) -> None:
        self.estimate = estimate
        self.calls: list[tuple[bytes | None, str]] = []

    def extract(
        self,
        target: Any,
        *,
        instructions: str,
        image_png: bytes | None = None,
        context_text: str = "",
    ) -> EstimateExtraction:
        self.calls.append((image_png, context_text))
        return self.estimate


# --- StructuredExtractor ---------------------------------------------------
def test_extractor_validates_and_coerces_tool_input() -> None:
    tool_input = {
        "name": "Cole/Diller Roundabout",
        "construction_subtotal": "~1,228,174",  # approximate + separators
        "total": 1535218,
        "confidence": "high",
        "section_subtotals": {"roadway": 109307},
    }
    client = _FakeClient([_Block("tool_use", "record_extraction", tool_input)])
    extractor = StructuredExtractor(client=client, model="test-model")

    result = extractor.extract(
        EstimateExtraction, instructions="GO", image_png=b"img", context_text="ocr hint"
    )

    assert result.name == "Cole/Diller Roundabout"
    assert result.construction_subtotal == 1228174  # coerced from "~1,228,174"
    assert result.confidence == "high"
    assert result.section_subtotals.roadway == 109307


def test_extractor_builds_image_and_text_message() -> None:
    client = _FakeClient(
        [
            _Block(
                "tool_use",
                "record_extraction",
                {"name": "x", "construction_subtotal": 1, "total": 1},
            )
        ]
    )
    extractor = StructuredExtractor(client=client)
    extractor.extract(
        EstimateExtraction, instructions="READ THIS", image_png=b"img", context_text="garbled ocr"
    )

    content = client.capture["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[-1]["type"] == "text"
    assert "READ THIS" in content[-1]["text"]
    assert "UNRELIABLE" in content[-1]["text"] and "garbled ocr" in content[-1]["text"]
    assert client.capture["tool_choice"] == {"type": "tool", "name": "record_extraction"}


def test_extractor_raises_when_no_tool_call() -> None:
    client = _FakeClient([_Block("text")])
    extractor = StructuredExtractor(client=client)
    with pytest.raises(ExtractionError):
        extractor.extract(EstimateExtraction, instructions="x")


# --- pipeline orchestration ------------------------------------------------
def _doc() -> SourceDocument:
    return SourceDocument(
        path=Path("/data/documents/aedg/PRR-01-bundle.ocr.pdf"),
        doc_id="PRR-01-bundle-abcd1234",
        suffix=".pdf",
        size_bytes=137_000_000,
        collection="aedg",
    )


def test_extract_estimate_page_attaches_provenance() -> None:
    estimate = EstimateExtraction(
        name="Cole/Diller Roundabout",
        construction_subtotal=1228174,
        total=1535218,
        section_subtotals={"roadway": 109307},
        confidence="high",
    )
    pdf, extractor = _FakePdf(), _FakeExtractor(estimate)

    extraction = extract_estimate_page(_doc(), 318, extractor=extractor, pdf=pdf)  # type: ignore[arg-type]

    assert extraction.page_index == 318
    assert extraction.pdf_page == 319  # 1-based printed sheet
    assert extraction.estimate.name == "Cole/Diller Roundabout"
    assert extraction.source_text_excerpt == "OCR text for page 318"
    # Injected pdf must NOT be closed by the function (caller owns it).
    assert pdf.closed is False
    # The OCR text was passed to the extractor as a hint.
    assert extractor.calls[0][1] == "OCR text for page 318"


def test_save_extraction_writes_slugged_yaml(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    estimate = EstimateExtraction(
        name="Cole Street / West Street", construction_subtotal=1799687, total=2249609
    )
    extraction = PageExtraction(
        doc_id="d", source_path="/x", page_index=324, pdf_page=325, dpi=300, estimate=estimate
    )

    path = save_extraction(extraction, settings=settings)

    assert path.exists()
    assert path.name == "cole_street_-_west_street.p325.opc.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["pdf_page"] == 325
    assert data["estimate"]["name"] == "Cole Street / West Street"
