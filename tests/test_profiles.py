"""Tests for the format-profile registry, detection, and prompt building."""

from __future__ import annotations

import pytest

from bosc import profiles


def test_registry_has_builtin_profiles() -> None:
    ids = {p.id for p in profiles.all_profiles()}
    assert {"tetratech", "generic"} <= ids
    assert profiles.get("tetratech").display_name == "Tetra Tech"


def test_get_unknown_profile_raises() -> None:
    with pytest.raises(KeyError):
        profiles.get("nope")


def test_detect_from_ocr_text() -> None:
    # Even garbled OCR usually carries the contractor name / document title.
    text = "...TETRA TECH...\nOPINION OF PROBABLE PROJECT COST\nCole Street/Diller"
    assert profiles.detect(text) is profiles.TETRATECH


def test_detect_returns_none_when_no_match() -> None:
    assert profiles.detect("a generic cost estimate with no telltale keywords") is None


def test_resolve_prefers_explicit_then_detect_then_generic() -> None:
    assert profiles.resolve("tetratech", "") is profiles.TETRATECH  # explicit wins
    assert profiles.resolve("auto", "tetra tech opinion of probable") is profiles.TETRATECH
    assert profiles.resolve("auto", "no telltale keywords here") is profiles.GENERIC_OPC


def test_prompt_includes_format_specifics() -> None:
    summary = profiles.TETRATECH.prompt(detail=False)
    assert "Tetra Tech" in summary
    assert "ROADWAY" in summary  # expected-section vocabulary
    assert "extract EVERY line item" not in summary  # summary mode: subtotals only

    detail = profiles.TETRATECH.prompt(detail=True)
    assert "extract EVERY line item" in detail
    assert "ODOT" in detail  # item-number scheme
