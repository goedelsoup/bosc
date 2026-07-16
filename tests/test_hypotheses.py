"""Tests for the boom-origin hypothesis axis (the third axis: site x hypothesis).

The registry is ported from ``web/packages/core/src/directory.ts`` (LENSES + LENS_DATA); the
port-parity test below is the zero-drift contract — if a cell's signal/group/field was
mistranscribed when it moved into ``data/hypotheses/``, this fails before the frontend
cutover (Phase 2) can render the wrong thing.
"""

from __future__ import annotations

import textwrap

from watermark.config import Settings
from watermark.hypotheses import (
    HYPOTHESES,
    Citation,
    Hypothesis,
    HypothesisAssessment,
    assessment_path,
    assessments_for,
    get_hypothesis,
    lint_assessments,
    load_assessments,
)

# The canonical LENS_DATA cells (signal/group + the per-hypothesis fields), transcribed
# from directory.ts. The committed YAML store must reproduce these exactly.
_EXPECTED = {
    ("defense", "lima"): (
        "anchor",
        "arsenal",
        {"nexus": "Lima Army Tank Plant (JSMC)", "linkage": "Co-located · Allen Co."},
    ),
    ("defense", "springfield"): (
        "moderate",
        "arsenal",
        {"nexus": "Springfield-Beckley ANGB", "linkage": "Adjacent · NASIC nearby"},
    ),
    ("defense", "wpafb"): (
        "strong",
        "arsenal",
        {"nexus": "Wright-Patterson AFB", "linkage": "Adjacent · Mad R. terminus"},
    ),
    ("defense", "new-albany"): (
        "moderate",
        "federal",
        {"nexus": "CHIPS semiconductor megasite", "linkage": "Federal program"},
    ),
    ("defense", "columbus"): (
        "moderate",
        "federal",
        {"nexus": "DLA Land & Maritime", "linkage": "Supply chain"},
    ),
    ("defense", "lordstown"): (
        "watch",
        "supply",
        {"nexus": "Defense-battery corridor", "linkage": "Supply chain (signal)"},
    ),
    ("surveillance", "lima"): (
        "anchor",
        "onrecord",
        {"operator": "Shawnee Energy Campus", "capital": "CRA #548-25 · 15 yr / 75%"},
    ),
    ("surveillance", "hamilton-middletown"): (
        "watch",
        "subsidy",
        {"operator": "—", "capital": "Municipal power + CRA (signal)"},
    ),
    ("surveillance", "new-albany"): (
        "moderate",
        "onrecord",
        {"operator": "Hyperscaler cluster (inferred)", "capital": "JobsOhio · TIF (inference)"},
    ),
    ("surveillance", "columbus"): (
        "watch",
        "subsidy",
        {"operator": "—", "capital": "Enterprise-zone abatement (signal)"},
    ),
    ("water", "lima"): (
        "watch",
        "coercion",
        {
            "wwtp": "Allen County Sanitary District (FM-1: American Bath / American II; FM-2: City of Lima)"
        },
    ),
    ("surveillance", "fort-wayne"): (
        "moderate",
        "onrecord",
        {
            "operator": "Hatchworks LLC (Google shell — Mountain View CA mailing, Zodiac parcels)",
            "capital": "—",
            "end_use": "consumer_surveillance [inference]",
        },
    ),
}


def test_registry_has_three_hypotheses() -> None:
    assert list(HYPOTHESES) == ["water", "defense", "surveillance"]
    assert [h.number for h in HYPOTHESES.values()] == ["H1", "H2", "H3"]
    assert HYPOTHESES["water"].status == "reference"
    assert HYPOTHESES["defense"].status == "emerging"
    assert HYPOTHESES["surveillance"].status == "emerging"


def test_hypothesis_is_frozen() -> None:
    import pytest

    with pytest.raises(Exception):  # noqa: B017 — pydantic frozen raises ValidationError
        HYPOTHESES["defense"].name = "mutated"  # type: ignore[misc]


def test_get_hypothesis() -> None:
    assert get_hypothesis("defense").number == "H2"


def test_hypothesis_fields_and_groups() -> None:
    assert HYPOTHESES["defense"].fields == ("nexus", "linkage")
    assert HYPOTHESES["defense"].groups == ("arsenal", "federal", "supply", "watch")
    assert HYPOTHESES["surveillance"].fields == ("operator", "capital", "end_use")
    # H1 CWA coercion cells use wwtp + gap; the basin network provides the rest.
    assert HYPOTHESES["water"].fields == ("wwtp", "gap")
    assert HYPOTHESES["water"].groups == ("coercion",)


def test_committed_store_loads_and_matches_lens_data() -> None:
    """Port-parity: the committed cells reproduce directory.ts LENS_DATA exactly."""
    cells = {(c.hypothesis, c.site): c for c in load_assessments()}
    assert set(cells) == set(_EXPECTED)
    for key, (signal, group, fields) in _EXPECTED.items():
        cell = cells[key]
        assert cell.signal == signal, key
        assert cell.group == group, key
        assert cell.fields == fields, key


def test_assessments_for_filters_by_hypothesis() -> None:
    assert {c.site for c in assessments_for("defense")} == {
        "lima",
        "springfield",
        "wpafb",
        "new-albany",
        "columbus",
        "lordstown",
    }
    assert {c.site for c in assessments_for("surveillance")} == {
        "lima",
        "hamilton-middletown",
        "new-albany",
        "columbus",
        "fort-wayne",
    }
    assert {c.site for c in assessments_for("water")} == {"lima"}


def test_committed_store_lint_has_no_hard_findings() -> None:
    """The real store lints clean except for the soft 'untracked-site' notes."""
    hard = [f for f in lint_assessments() if f.kind != "untracked-site"]
    assert hard == []


def test_non_open_cell_requires_a_citation() -> None:
    """Every verified/inference cell carries provenance — the upgrade over LENS_DATA."""
    for c in load_assessments():
        if c.tag != "open":
            assert c.citations, (c.hypothesis, c.site)


def test_citation_verified_is_derived() -> None:
    assert Citation(source_kind="document").verified is True
    assert Citation(source_kind="connector").verified is True
    assert Citation(source_kind="reference").verified is False
    assert Citation(source_kind="assumption").verified is False


def test_lint_catches_malformed_cells(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(data_dir=tmp_path)
    root = settings.hypotheses_dir
    # unknown hypothesis
    (root / "ghost").mkdir(parents=True)
    (root / "ghost" / "lima.yaml").write_text(
        textwrap.dedent(
            """\
            site: lima
            hypothesis: ghost
            tag: open
            """
        ),
        encoding="utf-8",
    )
    # bad group + bad field + missing citation (tag verified, no citations)
    (root / "defense").mkdir(parents=True)
    (root / "defense" / "lima.yaml").write_text(
        textwrap.dedent(
            """\
            site: lima
            hypothesis: defense
            signal: anchor
            tag: verified
            group: not-a-group
            fields:
              made_up: x
            citations: []
            """
        ),
        encoding="utf-8",
    )
    kinds = {f.kind for f in lint_assessments(settings=settings)}
    assert "unknown-hypothesis" in kinds
    assert "bad-group" in kinds
    assert "bad-field" in kinds
    assert "missing-citation" in kinds


def test_load_empty_when_no_store(tmp_path) -> None:  # type: ignore[no-untyped-def]
    assert load_assessments(settings=Settings(data_dir=tmp_path)) == []


def test_assessment_path() -> None:
    settings = Settings(data_dir=__import__("pathlib").Path("/tmp/x"))
    assert (
        assessment_path("defense", "lima", settings=settings)
        == settings.hypotheses_dir / "defense" / "lima.yaml"
    )


def test_assessment_model_validates_from_yaml_shape() -> None:
    """A cell parses from the on-disk YAML shape (no derived `verified` key present)."""
    raw = {
        "site": "lima",
        "hypothesis": "defense",
        "signal": "anchor",
        "tag": "verified",
        "group": "arsenal",
        "fields": {"nexus": "X", "linkage": "Y"},
        "citations": [{"source": "docs/defense-nexus.md", "source_kind": "reference"}],
    }
    cell = HypothesisAssessment.model_validate(raw)
    assert cell.fields == {"nexus": "X", "linkage": "Y"}
    assert cell.citations[0].verified is False  # 'reference' is not [verified]
    # The derived `verified` is exported (for the bundle) but isn't an input field.
    assert cell.citations[0].model_dump()["verified"] is False


def test_sub_thesis_roundtrips_through_model() -> None:
    """sub_thesis is optional, validated against the known vocabulary, and absent by default."""
    base = {
        "site": "lima",
        "hypothesis": "surveillance",
        "signal": "anchor",
        "tag": "verified",
        "group": "onrecord",
        "fields": {"operator": "X", "capital": "Y"},
        "citations": [],
    }
    cell_none = HypothesisAssessment.model_validate(base)
    assert cell_none.sub_thesis is None

    cell_capture = HypothesisAssessment.model_validate({**base, "sub_thesis": "capture"})
    assert cell_capture.sub_thesis == "capture"

    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HypothesisAssessment.model_validate({**base, "sub_thesis": "unknown-tag"})


def test_hypothesis_model_rejects_extra() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Hypothesis(id="x", number="H9", name="x", claim="x", thesis="x", status="emerging", bogus=1)  # type: ignore[call-arg]
