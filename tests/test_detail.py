"""Tests for detail line-item extraction: models, reconciliation, pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bosc.config import Settings
from bosc.models import DetailExtraction, DetailPageExtraction, LineItem
from bosc.pipeline import analyze
from bosc.pipeline.extract import extract_detail_page, save_extraction
from bosc.pipeline.ingest import SourceDocument


def _diller_detail() -> DetailExtraction:
    return DetailExtraction(
        name="Cole/Diller Roundabout",
        construction_subtotal=1228174,
        total=1535218,
        section_subtotals={"roadway": 21500, "drainage": 120440},
        line_items={
            "roadway": [
                {
                    "item_no": "201E11000",
                    "description": "Clearing and grubbing",
                    "quantity": 1,
                    "unit": "LS",
                    "unit_amount": 20000,
                    "total_amount": 20000,
                },
                {
                    "item_no": "623E38500",
                    "description": "Monument assembly, Type C",
                    "quantity": 3,
                    "unit": "EACH",
                    "unit_amount": 500,
                    "total_amount": 1500,
                },
            ],
            "drainage": [
                # Approximate, from the degraded scan: ~ markers + separators.
                {
                    "item_no": "605E11111",
                    "description": '6" underdrains',
                    "quantity": "~2,044",
                    "unit": "FT",
                    "unit_amount": "10.0",
                    "total_amount": "~20,440",
                },
                {
                    "item_no": "custom_drain_ls",
                    "description": "Drainage improvements",
                    "quantity": 1,
                    "unit": "LS",
                    "unit_amount": 100000,
                    "total_amount": 100000,
                },
            ],
        },
    )


# --- models ----------------------------------------------------------------
def test_line_item_coercion_preserves_int_vs_float() -> None:
    item = LineItem(description="x", quantity="~2,044", unit_amount="10.0", total_amount="~20,440")
    assert item.quantity == 2044 and isinstance(item.quantity, int)
    assert item.unit_amount == 10.0 and isinstance(item.unit_amount, float)
    assert item.total_amount == 20440 and isinstance(item.total_amount, int)


def test_detail_extraction_sections_and_totals() -> None:
    detail = _diller_detail()
    sections = detail.line_items.sections()
    assert len(sections["roadway"]) == 2
    assert detail.section_item_total("roadway") == 21500.0
    assert detail.section_item_total("drainage") == 120440.0
    assert detail.section_item_total("pavement") == 0.0  # empty section


# --- reconciliation --------------------------------------------------------
def test_reconcile_detail_passes_when_items_match_subtotals() -> None:
    findings = analyze.reconcile_detail(_diller_detail())
    assert {f.check for f in findings} == {"line-item-rollup"}
    assert len(findings) == 2  # only roadway + drainage have items
    assert all(f.ok for f in findings)


def test_reconcile_detail_flags_mismatch() -> None:
    detail = _diller_detail()
    detail.section_subtotals.roadway = 99_999  # no longer equals the item sum
    findings = {f.subject: f for f in analyze.reconcile_detail(detail)}
    assert findings["Cole/Diller Roundabout:roadway"].ok is False
    assert findings["Cole/Diller Roundabout:drainage"].ok is True


# --- pipeline --------------------------------------------------------------
class _FakePdf:
    def page_text(self, index: int) -> str:
        return f"ocr {index}"

    def render_page_png(self, index: int, *, dpi: int | None = None) -> bytes:
        return b"\x89PNG-fake"

    def close(self) -> None:  # pragma: no cover - not called for injected pdf
        pass


class _FakeExtractor:
    def __init__(self, detail: DetailExtraction) -> None:
        self.detail = detail

    def extract(self, target: Any, **_: Any) -> DetailExtraction:
        return self.detail


def _doc() -> SourceDocument:
    return SourceDocument(
        path=Path("/data/documents/aedg/PRR-01-bundle.ocr.pdf"),
        doc_id="PRR-01-bundle-abcd1234",
        suffix=".pdf",
        size_bytes=137_000_000,
        collection="aedg",
    )


def test_extract_detail_page_returns_detail_page_extraction() -> None:
    extraction = extract_detail_page(
        _doc(),
        318,
        extractor=_FakeExtractor(_diller_detail()),
        pdf=_FakePdf(),  # type: ignore[arg-type]
    )
    assert isinstance(extraction, DetailPageExtraction)
    assert extraction.pdf_page == 319
    items = extraction.estimate.line_items.sections()
    assert len(items["drainage"]) == 2


def test_save_detail_extraction_writes_detail_suffix(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    extraction = DetailPageExtraction(
        doc_id="d",
        source_path="/x",
        page_index=318,
        pdf_page=319,
        dpi=300,
        estimate=_diller_detail(),
    )
    path = save_extraction(extraction, settings=settings)
    assert path.name == "cole-diller_roundabout.p319.detail.opc.yaml"
    data = yaml.safe_load(path.read_text())
    assert data["estimate"]["line_items"]["drainage"][0]["item_no"] == "605E11111"
