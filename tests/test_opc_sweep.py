"""OPC page-sweep + summary assembly (#39).

`assemble_opc_summary` turns per-page Estimates into the legacy OPCSummary shape that
`analyze.reconcile` checks (so the hand-assembled summary becomes regenerable); the
`sweep_opc_pages` loop reuses one PDF + extractor across pages. The live vision
extraction is stubbed here (no PDF, no API) so the loop logic is tested offline.
"""

from __future__ import annotations

import pytest

from watermark.models import Estimate, EstimateSection, MarkupLine, PageExtraction
from watermark.pipeline import analyze
from watermark.pipeline import extract as extract_stage
from watermark.pipeline.ingest import SourceDocument


def _est(name: str, roadway: int, pavement: int) -> Estimate:
    """A synthetic, internally-consistent sub-estimate (sections sum, +25% = total)."""
    cs = roadway + pavement
    markup = round(cs * 0.25)
    return Estimate(
        name=name,
        profile="tetratech",
        sections=[
            EstimateSection(name="ROADWAY", subtotal=roadway),
            EstimateSection(name="PAVEMENT", subtotal=pavement),
        ],
        construction_subtotal=cs,
        markups=[MarkupLine(label="Contingency and Inflation", rate=0.25, amount=markup)],
        total=cs + markup,
    )


def test_assemble_opc_summary_reconciles() -> None:
    summary = extract_stage.assemble_opc_summary(
        [_est("RB1", 100_000, 200_000), _est("RB2", 50_000, 150_000)], pdf_pages=[318, 319]
    )
    assert len(summary.sub_estimates) == 2
    assert summary.sub_estimates[0].pdf_page == 318
    assert summary.sub_estimates[0].section_subtotals.total() == 300_000
    # Program headline = grand total of sub-estimate totals; the summary reconciles.
    assert summary.grand_total() == 375_000 + 250_000
    assert summary.meta.summary_construction_total == summary.grand_total()
    assert [f for f in analyze.reconcile(summary) if not f.ok] == []


def test_assemble_skips_incomplete_estimate_rather_than_fabricating() -> None:
    incomplete = Estimate(name="illegible", construction_subtotal=None, total=None)
    summary = extract_stage.assemble_opc_summary([_est("RB1", 1_000, 1_000), incomplete])
    assert [se.name for se in summary.sub_estimates] == ["RB1"]  # the incomplete one is dropped


def _doc() -> SourceDocument:
    from pathlib import Path

    return SourceDocument(path=Path("bundle.pdf"), doc_id="bundle", suffix=".pdf", size_bytes=1)


def test_sweep_reuses_one_pdf_and_loops_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"n": 0}

    class _FakePdf:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def close(self) -> None:
            closed["n"] += 1

    seen: list[int] = []

    def _fake_extract(doc: object, i: int, **kw: object) -> PageExtraction:
        seen.append(i)
        return PageExtraction(
            doc_id="d",
            source_path="p",
            page_index=i,
            pdf_page=i + 1,
            dpi=300,
            estimate=_est(f"RB{i}", i, i),
        )

    monkeypatch.setattr(extract_stage, "PdfDocument", _FakePdf)
    monkeypatch.setattr(extract_stage, "extract_opc_page", _fake_extract)

    sweep = extract_stage.sweep_opc_pages(_doc(), [318, 319, 320])
    assert seen == [318, 319, 320]
    assert [pe.pdf_page for pe in sweep.extractions] == [319, 320, 321]
    assert sweep.failed == [] and sweep.complete
    assert sweep.requested == [318, 319, 320]
    assert closed["n"] == 1  # the reused PDF is opened once and closed once


def test_sweep_skips_a_failing_page_without_aborting(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakePdf:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def close(self) -> None:
            pass

    def _fake_extract(doc: object, i: int, **kw: object) -> PageExtraction:
        if i == 319:
            raise RuntimeError("illegible page")
        return PageExtraction(
            doc_id="d",
            source_path="p",
            page_index=i,
            pdf_page=i + 1,
            dpi=300,
            estimate=_est("RB", i, i),
        )

    monkeypatch.setattr(extract_stage, "PdfDocument", _FakePdf)
    monkeypatch.setattr(extract_stage, "extract_opc_page", _fake_extract)

    sweep = extract_stage.sweep_opc_pages(_doc(), [318, 319, 320])
    assert [pe.page_index for pe in sweep.extractions] == [318, 320]  # bad page logged + skipped
    # ...but the drop is SURFACED, not swallowed — the failed index rides on the result (#1364).
    assert sweep.failed == [319]
    assert not sweep.complete


def test_sweep_survives_an_exception_with_an_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    # A raise with no message (`str(exc) == ""`) yields no lines — the skip-logging must fall back
    # to the repr, not index an empty list and abort the very sweep it exists to protect.
    class _FakePdf:
        def __init__(self, *a: object, **k: object) -> None:
            pass

        def close(self) -> None:
            pass

    def _fake_extract(doc: object, i: int, **kw: object) -> PageExtraction:
        if i == 319:
            raise ValueError  # no message → str(exc) == ""
        return PageExtraction(
            doc_id="d",
            source_path="p",
            page_index=i,
            pdf_page=i + 1,
            dpi=300,
            estimate=_est("RB", i, i),
        )

    monkeypatch.setattr(extract_stage, "PdfDocument", _FakePdf)
    monkeypatch.setattr(extract_stage, "extract_opc_page", _fake_extract)

    sweep = extract_stage.sweep_opc_pages(_doc(), [318, 319, 320])
    assert [pe.page_index for pe in sweep.extractions] == [318, 320]
    assert sweep.failed == [319]


def test_reconcile_flags_a_truncated_sweep_rather_than_passing_green() -> None:
    # A page silently dropping out of the sweep understates the program total by a whole estimate,
    # but the headline is derived from the survivors so the program-total check stays self-
    # consistent. The coverage cross-check (expected_count) turns that into a failing finding (#1364).
    ests = [_est("RB1", 100_000, 200_000), _est("RB2", 50_000, 150_000)]
    complete = extract_stage.assemble_opc_summary(ests, expected_count=2)
    assert [f for f in analyze.reconcile(complete) if not f.ok] == []

    truncated = extract_stage.assemble_opc_summary(ests[:1], expected_count=2)
    fails = [f for f in analyze.reconcile(truncated) if not f.ok]
    assert [f.check for f in fails] == ["coverage"]
    assert "1 of 2" in fails[0].detail

    # With no declared expectation the check is skipped (hand-authored summaries stay valid).
    assert [
        f for f in analyze.reconcile(extract_stage.assemble_opc_summary(ests[:1])) if not f.ok
    ] == []
