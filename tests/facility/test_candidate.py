"""Structured data-center candidate record: schema discipline, prose→record distillation, the
committed backfill, and the promotion report (#1627, epic #1626 F1).

Hermetic — the distiller uses a fake Anthropic client (the ``test_research`` pattern), so nothing
here hits the network or needs API keys. The report/backfill tests read the committed
``data/extracted/**`` artifacts, like the rest of the offline suite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from watermark.agent.extractor import StructuredExtractor
from watermark.config import Settings, get_settings
from watermark.facility.candidate import (
    CandidateStatus,
    PromotionState,
    ProvenancedFigure,
    SiteCandidates,
    build_candidate,
    candidates_path,
    load_candidates,
    promotion_status,
    save_candidates,
)
from watermark.facility.sweep import (
    SWEEP_METHODOLOGY,
    build_sweep_prompt,
    distill_candidates,
)

# ---------------------------------------------------------------------------
# ProvenancedFigure — the provenance-carries-with-value discipline
# ---------------------------------------------------------------------------


def test_figure_preserves_value_type_and_maps_tags() -> None:
    mw = ProvenancedFigure(value=250, unit="MW", source_kind="reference", citation="Journal-News")
    water = ProvenancedFigure(value=15.8, unit="MGD", source_kind="connector", citation="DMR")
    assert isinstance(mw.value, int) and mw.tag == "reference"
    assert isinstance(water.value, float) and water.tag == "verified"  # connector -> [verified]
    derived = ProvenancedFigure(value=0.067, unit="cfs", source_kind="derived", citation="arith")
    assert derived.tag == "inference"


def test_open_figure_has_no_value_and_reads_open() -> None:
    fig = ProvenancedFigure(note="no air PTI found — pull OEPA eDoc")
    assert fig.value is None and fig.tag == "open"


def test_valued_figure_must_be_cited() -> None:
    with pytest.raises(ValidationError):
        ProvenancedFigure(value=100, unit="MW")  # no source_kind/citation
    with pytest.raises(ValidationError):
        ProvenancedFigure(value=100, unit="MW", source_kind="reference")  # no citation


def test_open_figure_forbids_dangling_provenance() -> None:
    with pytest.raises(ValidationError):
        ProvenancedFigure(source_kind="document", citation="x")  # provenance without a value


# ---------------------------------------------------------------------------
# DataCenterCandidate — dedup key + promotability
# ---------------------------------------------------------------------------

_OPERATOR = ProvenancedFigure(value="Prologis, Inc.", source_kind="reference", citation="DCD")


def test_build_candidate_mints_stable_key() -> None:
    c1 = build_candidate(project_name="Project Mila", operator=_OPERATOR)
    c2 = build_candidate(project_name="Project Mila", operator=_OPERATOR)
    assert c1.key == c2.key == "project-mila"
    # falls back to the operator name when there is no project name
    c3 = build_candidate(project_name=None, operator=_OPERATOR)
    assert c3.key == "prologis-inc"


def test_is_promotable_needs_a_facility_figure_but_not_verification() -> None:
    mw = ProvenancedFigure(value=250, unit="MW", source_kind="reference", citation="media")
    assert build_candidate(project_name="p", operator=_OPERATOR, it_load_mw=mw).is_promotable
    # a [reference] figure is still promotable (lands as an [inference] bracket, like Urbana)
    inv = ProvenancedFigure(value=1e9, unit="USD", source_kind="reference", citation="press")
    assert build_candidate(project_name="p", operator=_OPERATOR, investment_usd=inv).is_promotable


def test_is_not_promotable_without_facility_figures_or_when_dead() -> None:
    # only an [open] MW (no disclosed facility figure) -> not promotable
    openmw = ProvenancedFigure(note="MW not disclosed")
    assert not build_candidate(
        project_name="p", operator=_OPERATOR, it_load_mw=openmw
    ).is_promotable
    # withdrawn/rejected never promote, even with a figure
    mw = ProvenancedFigure(value=250, unit="MW", source_kind="reference", citation="media")
    dead = build_candidate(
        project_name="p", operator=_OPERATOR, it_load_mw=mw, status=CandidateStatus.REJECTED
    )
    assert not dead.is_promotable


# ---------------------------------------------------------------------------
# IO round-trip — including the [open]-figure edge
# ---------------------------------------------------------------------------


def test_save_load_round_trip_preserves_open_figures(tmp_path: Path) -> None:
    mw = ProvenancedFigure(value=250, unit="MW", source_kind="reference", citation="media")
    open_air = ProvenancedFigure(note="no PTI found")
    c = build_candidate(
        project_name="Project Mila",
        operator=_OPERATOR,
        it_load_mw=mw,
        air_permit=open_air,
        register_prose="## 1 — Prologis\n\nmulti\nline\nprose\n",
    )
    rec = SiteCandidates(
        site="x",
        generated_at="2026-07-20",
        source_register="extracted/x/data-centers.md",
        candidates=[c],
    )
    path = tmp_path / candidates_path(Settings(), "x").name
    save_candidates(rec, path)
    back = load_candidates(path)
    assert back == rec
    # the [open] figure survives as a value-less figure (not dropped entirely)
    assert back.candidates[0].air_permit is not None
    assert back.candidates[0].air_permit.tag == "open"
    # multi-line prose renders as a literal block for reviewability
    assert "register_prose: |" in path.read_text(encoding="utf-8")


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_candidates(tmp_path / "absent.yaml") is None


# ---------------------------------------------------------------------------
# distill_candidates — prose -> record, hermetic (fake client)
# ---------------------------------------------------------------------------

_DRAFT_PAYLOAD: dict[str, Any] = {
    "candidates": [
        {
            "project_name": "Project Mila",
            "operator": {"value": "Prologis, Inc.", "source_kind": "reference", "citation": "DCD"},
            "status": "approved",
            "location": "Trenton Industrial Park",
            "county": "Butler County, OH",
            "it_load_mw": {
                "value": 250,
                "unit": "MW",
                "source_kind": "reference",
                "citation": "Journal-News",
            },
            "investment_usd": {
                "value": 1000000000,
                "unit": "USD",
                "source_kind": "reference",
                "citation": "DCD",
            },
            "air_permit": {"note": "no Butler County PTI found"},
            "register_prose": "## 1 — Prologis Project Mila\n\n250 MW, ~$1B.\n",
        }
    ]
}


class _FakeMessages:
    def __init__(self, payload: dict[str, Any], tool_name: str) -> None:
        self._payload = payload
        self._tool_name = tool_name

    def create(self, **_: Any) -> Any:
        block = type("B", (), {"type": "tool_use", "name": self._tool_name, "input": self._payload})
        return type("M", (), {"content": [block()]})()


class _FakeClient:
    def __init__(self, payload: dict[str, Any], tool_name: str) -> None:
        self.messages = _FakeMessages(payload, tool_name)


def _extractor(payload: dict[str, Any]) -> StructuredExtractor:
    return StructuredExtractor(
        client=_FakeClient(payload, "record_data_center_candidates"), settings=Settings()
    )


def test_distill_round_trips_prose_into_a_validated_record() -> None:
    rec = distill_candidates(
        "# Register prose (ignored by the fake client)",
        site="hamilton-middletown",
        source_register="extracted/hamilton-middletown/data-centers.md",
        generated_at="2026-07-20",
        extractor=_extractor(_DRAFT_PAYLOAD),
    )
    assert rec.site == "hamilton-middletown"
    assert rec.source_register.endswith("data-centers.md")
    assert len(rec.candidates) == 1
    c = rec.candidates[0]
    assert c.key == "project-mila"  # minted in code, not by the model
    assert c.status == CandidateStatus.APPROVED
    assert c.it_load_mw is not None and c.it_load_mw.tag == "reference"
    assert c.air_permit is not None and c.air_permit.tag == "open"
    assert "Prologis Project Mila" in c.register_prose  # prose preserved as a field
    assert c.is_promotable


# ---------------------------------------------------------------------------
# The committed hamilton-middletown backfill (schema guard beyond parse-only)
# ---------------------------------------------------------------------------


def test_committed_backfill_validates_and_is_promotable() -> None:
    settings = get_settings()
    rec = load_candidates(candidates_path(settings, "hamilton-middletown"))
    assert rec is not None, "the hamilton-middletown backfill must be committed"
    assert rec.promotable, "Project Mila must be a promotable candidate"
    mila = rec.candidates[0]
    assert mila.key == "project-mila"
    # transcription discipline: the utility is a [verified] document (Duke's own filing);
    # the MW is [reference] (media); the air permit is [open] (no instrument pulled).
    assert mila.utility is not None and mila.utility.tag == "verified"
    assert mila.it_load_mw is not None and mila.it_load_mw.tag == "reference"
    assert mila.air_permit is not None and mila.air_permit.tag == "open"


# ---------------------------------------------------------------------------
# Promotion report — the explicit backlog board
# ---------------------------------------------------------------------------


def test_promotion_status_flags_backfilled_site_as_needs_promotion() -> None:
    row = promotion_status("hamilton-middletown")
    assert row.has_register and not row.has_facility
    assert row.promotable_count >= 1
    assert row.state == PromotionState.NEEDS_PROMOTION


def test_promotion_status_flags_undistilled_register_as_needs_distill() -> None:
    # columbus has a prose register but no candidate sidecar and facility=None.
    row = promotion_status("columbus")
    assert row.has_register and not row.has_facility
    assert row.candidate_count == 0
    assert row.state == PromotionState.NEEDS_DISTILL


def test_promotion_status_ok_when_a_facility_exists() -> None:
    # lima is the reference site — SiteProfile.facility is set, so it is not in the backlog.
    row = promotion_status("lima")
    assert row.has_facility and row.state == PromotionState.OK


# ---------------------------------------------------------------------------
# DRY: the single methodology source is embedded by both prompt paths
# ---------------------------------------------------------------------------


def test_sweep_methodology_is_the_single_source() -> None:
    from watermark.research.run import SITE_ONBOARD_RECIPE

    prompt = build_sweep_prompt(
        city="Lima", county="Allen County, OH", state="OH", site="lima", rsei_fips="39003"
    )
    onboard = SITE_ONBOARD_RECIPE.build_prompt(topic="", ctx={"site": "lima"})
    marker = "STEP 1 — DISAMBIGUATION GUARDRAIL"
    assert marker in SWEEP_METHODOLOGY
    assert marker in prompt and marker in onboard  # both embed the shared block
    assert "{sweep_methodology}" not in onboard and "{site}" not in onboard  # fully formatted
