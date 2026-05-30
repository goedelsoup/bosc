"""Tests for the OPC data models, exercised against the real extraction."""

from __future__ import annotations

from pathlib import Path

from bosc.models import OPCSummary, _coerce_number


def test_coerce_number_handles_approx_and_separators() -> None:
    assert _coerce_number("~307043") == 307043
    assert _coerce_number("1,535,218") == 1535218
    assert _coerce_number("$50000") == 50000
    assert _coerce_number(120000) == 120000
    assert _coerce_number(None) is None


def test_loads_real_summary(summary_path: Path) -> None:
    summary = OPCSummary.from_yaml(summary_path)
    # Six sub-estimates: four roundabouts + two corridors.
    assert len(summary.sub_estimates) == 6
    names = {se.name for se in summary.sub_estimates}
    assert "Cole Street / Diller Road Roundabout" in names


def test_program_headline_total_matches_meta(summary_path: Path) -> None:
    summary = OPCSummary.from_yaml(summary_path)
    stated = summary.meta.summary_construction_total
    assert stated is not None
    # The meta headline equals the sum of the six summary-sheet line costs,
    # which are post-contingency *totals* — so it reconciles with grand_total(),
    # not the sum of construction subtotals. Within 1%.
    assert abs(summary.grand_total() - stated) <= round(stated * 0.01)
    # And the two are genuinely different figures (contingency makes up the gap).
    assert summary.construction_total() < stated


def test_diller_total_is_corrected_figure(summary_path: Path) -> None:
    summary = OPCSummary.from_yaml(summary_path)
    diller = next(se for se in summary.sub_estimates if "Diller" in se.name)
    # OCR-corrected: 1.535M, not 4.535M (see reconciliation notes).
    assert diller.total == 1535218
