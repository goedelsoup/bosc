"""Tests for the generic Estimate model and markup-aware reconciliation."""

from __future__ import annotations

from typing import Any

from bosc.models import Estimate, LineItem
from bosc.pipeline import analyze


def _diller() -> Estimate:
    """A small internally-consistent estimate (sections + markup tie out)."""
    data: dict[str, Any] = {
        "name": "Cole/Diller Roundabout",
        "sections": [
            {
                "name": "ROADWAY",
                "subtotal": 21500,
                "line_items": [
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
                        "description": "Monument assembly",
                        "quantity": 3,
                        "unit": "EACH",
                        "unit_amount": 500,
                        "total_amount": 1500,
                    },
                ],
            },
            {
                "name": "DRAINAGE",
                "subtotal": 120440,
                "line_items": [
                    {
                        "item_no": "605E11111",
                        "description": "underdrains",
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
            {"name": "WATER_WORK", "subtotal": 50000},  # subtotal-only (no items)
        ],
        "construction_subtotal": 191940,  # 21500 + 120440 + 50000
        "markups": [{"label": "Contingency and Inflation", "rate": 0.25, "amount": 47985}],
        "total": 239925,  # 191940 + 47985
    }
    return Estimate.model_validate(data)


# --- model -----------------------------------------------------------------
def test_line_item_coercion_preserves_int_vs_float() -> None:
    item = LineItem(description="x", quantity="~2,044", unit_amount="10.0", total_amount="~20,440")
    assert item.quantity == 2044 and isinstance(item.quantity, int)
    assert item.unit_amount == 10.0 and isinstance(item.unit_amount, float)
    assert item.total_amount == 20440 and isinstance(item.total_amount, int)


def test_estimate_helpers() -> None:
    est = _diller()
    assert est.section("roadway") is not None  # normalized-key lookup
    assert est.section("Roadway").items_total() == 21500.0  # type: ignore[union-attr]
    assert est.sections_total() == 191940.0
    assert est.markups_total() == 47985.0
    assert est.has_line_items() is True
    assert est.reconciles() is True


# --- reconciliation --------------------------------------------------------
def test_reconcile_estimate_all_checks_pass() -> None:
    findings = analyze.reconcile_estimate(_diller())
    checks = {f.check for f in findings}
    assert checks == {"line-item-rollup", "section-rollup", "markup-rate", "total"}
    # 2 sections with items + section-rollup + markup-rate + total = 5 findings.
    assert len(findings) == 5
    assert all(f.ok for f in findings), [str(f) for f in findings if not f.ok]


def test_reconcile_estimate_flags_section_mismatch() -> None:
    est = _diller()
    est.sections[0].subtotal = 99_999  # ROADWAY no longer matches its items
    findings = {f.subject: f for f in analyze.reconcile_estimate(est)}
    assert findings["Cole/Diller Roundabout:roadway"].ok is False


def test_reconcile_estimate_flags_bad_markup_rate() -> None:
    est = _diller()
    est.markups[0].amount = 10_000  # not 25% of the construction subtotal
    bad = [f for f in analyze.reconcile_estimate(est) if f.check == "markup-rate"]
    assert bad and bad[0].ok is False
