"""Tests for the structured extractor and the extract pipeline (generic OPC).

No network or API key: the Anthropic client and the PDF are replaced with fakes.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bosc.agent.extractor import ExtractionError, StructuredExtractor, _tool_schema
from bosc.config import Settings
from bosc.models import Estimate, PageExtraction
from bosc.pipeline.extract import extract_opc_page, extract_page, save_extraction
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
    def __init__(self, text: str = "Tetra Tech Opinion of Probable Project Cost") -> None:
        self.text = text
        self.closed = False

    def page_text(self, index: int) -> str:
        return self.text

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        return b"\x89PNG-fake"

    def close(self) -> None:
        self.closed = True


class _FakeExtractor:
    def __init__(self, estimate: Estimate) -> None:
        self.estimate = estimate
        self.calls: list[tuple[bytes | None, str]] = []

    def extract(
        self,
        target: Any,
        *,
        instructions: str,
        image_png: bytes | None = None,
        context_text: str = "",
    ) -> Estimate:
        self.calls.append((image_png, context_text))
        return self.estimate


def _estimate(**overrides: Any) -> Estimate:
    data: dict[str, Any] = {
        "name": "Cole/Diller Roundabout",
        "sections": [{"name": "ROADWAY", "subtotal": 109307, "line_items": []}],
        "construction_subtotal": 1228174,
        "markups": [{"label": "Contingency", "rate": 0.25, "amount": 307044}],
        "total": 1535218,
        "confidence": "high",
    }
    data.update(overrides)
    return Estimate.model_validate(data)


# --- StructuredExtractor ---------------------------------------------------
def test_extractor_validates_and_coerces_tool_input() -> None:
    tool_input = {
        "name": "Cole/Diller Roundabout",
        "construction_subtotal": "~1,228,174",  # approximate + separators
        "total": 1535218,
        "confidence": "high",
        "sections": [{"name": "ROADWAY", "subtotal": "~109,307"}],
    }
    client = _FakeClient([_Block("tool_use", "record_extraction", tool_input)])
    extractor = StructuredExtractor(client=client, model="test-model")

    result = extractor.extract(Estimate, instructions="GO", image_png=b"img", context_text="hint")

    assert result.name == "Cole/Diller Roundabout"
    assert result.construction_subtotal == 1228174  # coerced from "~1,228,174"
    assert result.section("roadway") is not None
    assert result.section("roadway").subtotal == 109307  # type: ignore[union-attr]


def test_extractor_builds_image_and_text_message() -> None:
    client = _FakeClient([_Block("tool_use", "record_extraction", {"name": "x"})])
    extractor = StructuredExtractor(client=client)
    extractor.extract(Estimate, instructions="READ THIS", image_png=b"img", context_text="garbled")

    content = client.capture["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert content[-1]["type"] == "text"
    assert "READ THIS" in content[-1]["text"]
    assert "UNRELIABLE" in content[-1]["text"] and "garbled" in content[-1]["text"]
    assert client.capture["tool_choice"] == {"type": "tool", "name": "record_extraction"}


def test_tool_schema_hides_pipeline_set_fields() -> None:
    props = _tool_schema(Estimate)["properties"]
    assert "profile" not in props  # set by the pipeline, not the model
    for field in ("name", "sections", "markups", "construction_subtotal", "total", "confidence"):
        assert field in props


def test_extractor_raises_when_no_tool_call() -> None:
    client = _FakeClient([_Block("text")])
    extractor = StructuredExtractor(client=client)
    with pytest.raises(ExtractionError):
        extractor.extract(Estimate, instructions="x")


# --- pipeline --------------------------------------------------------------
def _doc() -> SourceDocument:
    return SourceDocument(
        path=Path("/data/documents/aedg/PRR-01-bundle.ocr.pdf"),
        doc_id="PRR-01-bundle-abcd1234",
        suffix=".pdf",
        size_bytes=137_000_000,
        collection="aedg",
    )


def test_extract_opc_page_sets_profile_and_provenance() -> None:
    pdf, extractor = _FakePdf(), _FakeExtractor(_estimate())
    extraction = extract_opc_page(
        _doc(),
        318,
        profile="tetratech",
        extractor=extractor,
        pdf=pdf,  # type: ignore[arg-type]
    )
    assert extraction.page_index == 318
    assert extraction.pdf_page == 319  # 1-based printed sheet
    assert extraction.estimate.profile == "tetratech"  # stamped by the pipeline
    assert extraction.source_text_excerpt.startswith("Tetra Tech")
    assert pdf.closed is False  # injected pdf is not closed by the function


def test_extract_opc_page_auto_detects_profile() -> None:
    # OCR text mentioning the contractor drives auto-detection.
    pdf = _FakePdf(text="...TETRA TECH... opinion of probable project cost ...")
    extraction = extract_opc_page(
        _doc(),
        0,
        profile="auto",
        extractor=_FakeExtractor(_estimate()),
        pdf=pdf,  # type: ignore[arg-type]
    )
    assert extraction.estimate.profile == "tetratech"


def test_extract_page_dispatch_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="unknown document kind"):
        extract_page(_doc(), 0, kind="invoice")


def test_save_extraction_suffix_depends_on_line_items(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    summary = PageExtraction(
        doc_id="d", source_path="/x", page_index=0, pdf_page=1, dpi=300, estimate=_estimate()
    )
    detail = PageExtraction(
        doc_id="d",
        source_path="/x",
        page_index=0,
        pdf_page=1,
        dpi=300,
        estimate=_estimate(
            sections=[
                {
                    "name": "ROADWAY",
                    "subtotal": 100,
                    "line_items": [{"description": "x", "total_amount": 100}],
                }
            ]
        ),
    )
    assert save_extraction(summary, settings=settings).name.endswith(".p1.opc.yaml")
    assert save_extraction(detail, settings=settings).name.endswith(".p1.detail.opc.yaml")
