"""Tests for the discipline-agnostic engineering-record extractor (kind=engineering /
sanitary) — issue #41.

The Indian Brook pump-station as-built is a text-layer-less scan, so the live read
needs the vision API; these tests stub the extractor (no PDF, no API) and pin the
*flexibility* of the layer: the same model carries any discipline, the two axes
(components + their specs; sheets + design parameters) flow through untouched, and
the `sanitary` alias only restamps the kind / output name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from watermark.models import (
    ComponentSpec,
    DesignFirm,
    EngineeringExtraction,
    EngineeringRecord,
    SheetRef,
    SpecItem,
)
from watermark.pipeline import extract as extract_stage
from watermark.pipeline.extract import extract_engineering, extract_sanitary
from watermark.pipeline.ingest import SourceDocument


class _FakePdf:
    def __init__(self, text: str = "", page_count: int = 4) -> None:
        self.text = text
        self.page_count = page_count
        self.closed = False

    def page_text(self, index: int) -> str:
        return self.text  # an as-built scan has no usable text layer

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        return b"PNG" + bytes([index])

    def close(self) -> None:
        self.closed = True


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
        self.calls.append({"target": target, "images": images, "instructions": instructions})
        return self.result


def _doc() -> SourceDocument:
    return SourceDocument(
        path=Path("/data/documents/sanitary/indianbrook-ps-asbuilt-2007.pdf"),
        doc_id="ib-1",
        suffix=".pdf",
        size_bytes=10,
        collection="sanitary",
    )


def _record() -> EngineeringRecord:
    """A sanitary pump-station as-built exercising both flexible axes."""
    return EngineeringRecord(
        facility_name="Indian Brook Pump Station",
        record_type="as-built",
        discipline="sanitary",
        record_date="2007-06-01",
        prepared_by=[DesignFirm(name="Acme Engineers", discipline="Civil")],
        sheets=[
            SheetRef(sheet_id="1 of 4", title="Cover & Index"),
            SheetRef(sheet_id="2 of 4", title="Pump Station Plan & Sections"),
        ],
        components=[
            ComponentSpec(
                name="forcemain",
                category="pipe",
                specs=[
                    SpecItem(parameter="diameter", value="8", unit="in"),
                    SpecItem(parameter="material", value="ductile iron"),
                ],
            ),
            ComponentSpec(
                name="Pump No. 1",
                category="pump",
                specs=[SpecItem(parameter="capacity", value="~150", unit="gpm")],
            ),
        ],
        design_parameters=[SpecItem(parameter="peak design flow", value="1.2", unit="MGD")],
        confidence="medium",
        warnings=["pump capacity read as approximate (~150 gpm)"],
    )


def test_extract_engineering_attaches_provenance_and_axes() -> None:
    pdf, extractor = _FakePdf(), _FakeExtractor(_record())
    extraction = extract_engineering(_doc(), extractor=extractor, pdf=pdf)  # type: ignore[arg-type]

    assert isinstance(extraction, EngineeringExtraction)
    assert extraction.kind == "engineering"
    # Both flexible axes survive the round-trip untouched.
    assert [c.name for c in extraction.record.components] == ["forcemain", "Pump No. 1"]
    assert extraction.record.components[0].specs[0].value == "8"
    assert [s.title for s in extraction.record.sheets] == [
        "Cover & Index",
        "Pump Station Plan & Sections",
    ]
    assert extraction.record.design_parameters[0].parameter == "peak design flow"
    # Image-first: every page of the scan is rendered and sent under the engineering prompt.
    assert extractor.calls[0]["target"] is EngineeringRecord
    assert len(extractor.calls[0]["images"]) == 4
    assert "ENGINEERING record" in extractor.calls[0]["instructions"]
    assert extraction.pages_read == [0, 1, 2, 3]


def test_sanitary_alias_only_restamps_kind() -> None:
    pdf, extractor = _FakePdf(), _FakeExtractor(_record())
    extraction = extract_sanitary(_doc(), extractor=extractor, pdf=pdf)  # type: ignore[arg-type]
    assert extraction.kind == "sanitary"  # drives the <stem>.sanitary.yaml output name
    assert extraction.record.discipline == "sanitary"


def test_approximate_marker_is_preserved_not_dropped() -> None:
    """The ~ approximate-read convention survives into the spec value (no silent round)."""
    pdf, extractor = _FakePdf(), _FakeExtractor(_record())
    extraction = extract_engineering(_doc(), extractor=extractor, pdf=pdf)  # type: ignore[arg-type]
    pump = next(c for c in extraction.record.components if c.category == "pump")
    assert pump.specs[0].value == "~150"


def test_engineering_and_sanitary_are_registered_doc_kinds() -> None:
    assert "engineering" in extract_stage.DOC_EXTRACTORS
    assert "sanitary" in extract_stage.DOC_EXTRACTORS


def test_extract_help_lists_every_registered_kind() -> None:
    """The ``--kind`` help is the only place a user learns which kinds exist.

    It had gone stale: ``order`` and ``award`` were registered by #1746 and never added,
    so the enforcement genre — consent decrees, DFFOs, NOVs — was reachable but
    undiscoverable, and the Lima WWTP judicial-order backlog looked like it needed a new
    model that already existed. A registry the docs don't list is a registry nobody uses.
    """
    from typer.testing import CliRunner

    from watermark.cli import app

    rendered = CliRunner().invoke(app, ["extract", "--help"], env={"COLUMNS": "200"}).output
    kinds = rendered.split("Document kind:", 1)[1]
    # The help text wraps, so normalise the box-drawing and whitespace away before matching.
    flat = " ".join(kinds.replace("│", " ").split())
    missing = [k for k in extract_stage.DOC_EXTRACTORS if k not in flat.split(".", 1)[0]]
    assert not missing, f"--kind help omits registered kinds: {missing}"
