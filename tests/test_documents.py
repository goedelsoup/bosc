"""Tests for document-level extraction (deeds, NPDES permits)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from bosc.agent.extractor import StructuredExtractor
from bosc.config import Settings
from bosc.models import Deed, DeedExtraction, NpdesExtraction, NpdesPermit
from bosc.pipeline.extract import (
    extract_deed,
    extract_document,
    extract_npdes,
    save_doc_extraction,
)
from bosc.pipeline.ingest import SourceDocument


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


def test_extract_npdes_attaches_provenance() -> None:
    permit = NpdesPermit(permit_no="2PH00006*LD", facility_name="American II WWTP")
    extraction = extract_npdes(_doc(), extractor=_FakeExtractor(permit), pdf=_FakePdf(pages=30))  # type: ignore[arg-type]
    assert isinstance(extraction, NpdesExtraction)
    assert extraction.permit.permit_no == "2PH00006*LD"
    assert extraction.pages_read == list(range(6))  # text_pages=6 dominates the 1 image page


def test_extract_document_dispatch_and_unknown() -> None:
    permit = NpdesPermit(permit_no="X")
    ex = extract_document(_doc(), kind="npdes", extractor=_FakeExtractor(permit), pdf=_FakePdf())  # type: ignore[arg-type]
    assert isinstance(ex, NpdesExtraction)
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
