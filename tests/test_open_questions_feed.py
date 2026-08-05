"""Tests for the aggregated ``open-questions`` feed (#1568).

The projector tests are pure (no corpus load) — they pin the ``[open]``-tag filter (an
``[inference]`` lead is excluded), the lead → question carry-through of the
``lead:kind:*`` / ``lead:status:*`` vocabulary, the hypothesis-cell prompt/provenance grammar,
and the leads-before-hypotheses ordering + dedup. One integration test exports a real Lima
bundle and asserts the feed emits, every question carries provenance, and the two origins
resolve.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from watermark.site.open_questions import (
    _hypothesis_labels,
    _hypothesis_questions,
    _project_hypothesis_cells,
    _project_leads,
    build_open_questions,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

_CV = "2.0.0"

# A hypotheses feed's rows (id → number/name/question), as they appear in an assembled bundle.
# `question` arrived at contract 1.52.0 (#1917); `_HYPS_PRE_152` is the same feed without it,
# which is what a bundle exported before the bump still carries.
_HYPS = [
    {
        "id": "water",
        "number": "H1",
        "name": "Water & Coercion",
        "question": "Is a town's acceptance compelled by its own Clean Water Act exposure?",
    },
    {
        "id": "surveillance",
        "number": "H3",
        "name": "Consumer Surveillance",
        "question": "What for?",
    },
]
_HYPS_PRE_152 = [{k: v for k, v in h.items() if k != "question"} for h in _HYPS]


def _lead(id_: str, tag: str, **extra: Any) -> dict[str, Any]:
    """A serialized LeadItem row, as it appears in an assembled `leads` feed."""
    return {
        "id": id_,
        "kind": "question",
        "status": "unanswered",
        "tag": tag,
        "title": f"{id_} title",
        "detail": f"{id_} detail",
        "source": f"data/site/{id_}.yaml",
        "issue": None,
        "note": None,
        **extra,
    }


def _cell(hypothesis: str, site: str, tag: str, **extra: Any) -> dict[str, Any]:
    """A serialized HypothesisAssessment row, as it appears in an assembled feed."""
    return {
        "site": site,
        "hypothesis": hypothesis,
        "signal": "watch",
        "tag": tag,
        "sub_thesis": None,
        "group": None,
        "fields": {},
        "citations": [],
        **extra,
    }


# --- the [open]-tag filter on leads --------------------------------------------------------
def test_open_tagged_leads_included_inference_excluded() -> None:
    rows = [
        _lead("OPEN-1", "open"),
        _lead("INFER-1", "inference"),  # a labeled reading, not a gap — excluded
        _lead("OPEN-2", "open", kind="redaction", status="withheld", issue=42),
    ]
    qs = _project_leads(rows)
    assert [q.id for q in qs] == ["OPEN-1", "OPEN-2"]
    assert all(q.origin == "lead" for q in qs)
    # the lead:kind:* / lead:status:* vocabulary is carried through verbatim
    assert (qs[1].kind, qs[1].status, qs[1].issue) == ("redaction", "withheld", 42)


def test_lead_detail_collapsed_to_one_line() -> None:
    q = _project_leads([_lead("X", "open", detail="line one\n  line two\n\tline three")])[0]
    assert q.detail == "line one line two line three"
    assert q.question == "X title"
    assert q.source == "data/site/X.yaml"


# --- the [open]-tag filter + grammar on hypothesis cells -----------------------------------
def test_hypothesis_cells_open_only_with_provenance_and_label() -> None:
    rows = [
        _cell("water", "lima", "open", fields={"wwtp": "American Bath"}),
        _cell("water", "lima", "verified"),  # a documented cell — not an open thread
    ]
    qs = _project_hypothesis_cells(rows, _hypothesis_labels(_HYPS), _hypothesis_questions(_HYPS))
    assert len(qs) == 1
    q = qs[0]
    assert q.id == "hyp:water:lima"
    assert q.origin == "hypothesis"
    assert q.question == "Open thread — H1 Water & Coercion @ lima"
    assert q.hypothesis == "water" and q.hypothesis_label == "H1 Water & Coercion"
    assert q.signal == "watch"
    # provenance = the committed matrix file, never a fabricated citation (open cells have none)
    assert q.source == "data/hypotheses/water/lima.yaml"
    assert "American Bath" in q.detail and "No documented nexus yet" in q.detail
    # The thread states the hypothesis's ROOT question (#1917) — before it, this projection turned
    # cells into question threads under a hypothesis that never said what it was asking.
    assert "The hypothesis asks: Is a town's acceptance compelled" in q.detail


def test_hypothesis_label_falls_back_to_id_when_unknown() -> None:
    qs = _project_hypothesis_cells(
        [_cell("mystery", "lima", "open")], _hypothesis_labels(_HYPS), _hypothesis_questions(_HYPS)
    )
    assert qs[0].hypothesis_label == "mystery"
    assert qs[0].question == "Open thread — mystery @ lima"
    # No root question for an unregistered hypothesis — the detail simply omits the line rather
    # than printing "The hypothesis asks:" with nothing after it.
    assert "The hypothesis asks" not in qs[0].detail


def test_root_question_is_omitted_on_a_pre_1_52_bundle() -> None:
    """A bundle exported before the field existed still projects, without a blank question.

    The frontend builds against whatever `web/sites/` carries, so the degrade has to be real:
    the key is absent, not empty, and the thread reads exactly as it did before #1917.
    """
    qs = _project_hypothesis_cells(
        [_cell("water", "lima", "open")],
        _hypothesis_labels(_HYPS_PRE_152),
        _hypothesis_questions(_HYPS_PRE_152),
    )
    assert qs[0].hypothesis_label == "H1 Water & Coercion"
    assert "The hypothesis asks" not in qs[0].detail


# --- aggregation: ordering, dedup, absent feeds --------------------------------------------
def test_leads_precede_hypotheses_and_absent_feeds_are_safe() -> None:
    payloads = {
        "leads": [_lead("L1", "open"), _lead("L2", "inference")],
        "hypothesis-assessments": [_cell("water", "lima", "open")],
        "hypotheses": _HYPS,
    }
    qs = build_open_questions(payloads)
    assert [q.origin for q in qs] == ["lead", "hypothesis"]  # leads first, then matrix threads
    assert [q.id for q in qs] == ["L1", "hyp:water:lima"]
    # missing feeds never crash — an empty mapping yields no questions
    assert build_open_questions({}) == []
    assert build_open_questions({"leads": []}) == []


def test_dedup_on_id() -> None:
    payloads = {"leads": [_lead("DUP", "open"), _lead("DUP", "open")]}
    qs = build_open_questions(payloads)
    assert [q.id for q in qs] == ["DUP"]


# --- integration: a real Lima bundle -------------------------------------------------------
# `lima_bundle` is conftest's session-wide, cross-worker export (#1773) — this module reads one
# feed off it, so it must never pay for an export of its own.
def _open_questions(bundle: Path) -> list[dict[str, Any]]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    ref = next(f for f in manifest["feeds"] if f["name"] == "open-questions")
    assert ref["kind"] == "collection"
    return json.loads((bundle / ref["path"]).read_text(encoding="utf-8"))


def test_feed_emitted_at_contract_version(lima_bundle: Path) -> None:
    manifest = json.loads((lima_bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["contract_version"] == _CV
    questions = _open_questions(lima_bundle)
    assert len(questions) > 0


def test_every_question_carries_provenance(lima_bundle: Path) -> None:
    questions = _open_questions(lima_bundle)
    # "with provenance" (the issue's Done): every open question names a real source.
    assert all(q["source"] for q in questions)
    assert all(q["question"] and q["detail"] for q in questions)


def test_both_origins_resolve_with_their_own_fields(lima_bundle: Path) -> None:
    questions = _open_questions(lima_bundle)
    leads = [q for q in questions if q["origin"] == "lead"]
    hyps = [q for q in questions if q["origin"] == "hypothesis"]
    assert leads and hyps  # Lima carries both an open board and open matrix threads
    # a lead question surfaces the lead:status vocabulary; a hypothesis question its label
    assert all(q["status"] is not None for q in leads)
    assert all(q["hypothesis_label"] and q["source"].startswith("data/hypotheses/") for q in hyps)
    # no [inference] leads leaked in (the tag filter held over the real board)
    assert len({q["id"] for q in questions}) == len(questions)
