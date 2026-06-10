"""Automated-research runs: orchestration, distillation, manifest persistence.

Hermetic — the Agent SDK ``query`` is monkeypatched and the distiller uses a fake
Anthropic client (the same pattern as ``test_agent`` / ``test_civic_summarize``), so
nothing here hits the network or needs API keys.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from bosc.agent import client as client_mod
from bosc.agent.extractor import StructuredExtractor
from bosc.config import Settings
from bosc.research import (
    IssueProposal,
    ResearchRunManifest,
    RunProvenance,
    build_plan,
    existing_keys,
    load_manifest,
    marker,
    run_research,
    run_slug,
    write_run,
)
from bosc.research.run import distill_proposals

_DRAFTS = {
    "proposals": [
        {
            "title": "Verify the Diller roundabout contingency rate",
            "body": "Summary lists 25% but the detail pages imply 20%. Acceptance: reconcile.",
            "rationale": "A discrepancy that moves the program total.",
            "labels": ["extraction"],
        },
        {
            "title": "Extract the missing OPC detail page 327",
            "body": "Page 327 is unextracted. Acceptance: a validated Estimate for it.",
            "rationale": "A corpus gap.",
            "labels": [],
        },
    ]
}


class _FakeMessages:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def create(self, **_: Any) -> Any:
        block = type(
            "B", (), {"type": "tool_use", "name": "record_extraction", "input": self._payload}
        )
        return type("M", (), {"content": [block()]})()


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.messages = _FakeMessages(payload)


def _extractor(payload: dict[str, Any] | None = None) -> StructuredExtractor:
    return StructuredExtractor(client=_FakeClient(payload or _DRAFTS), settings=Settings())


async def _fake_query(*, prompt: str, options: Any):  # type: ignore[no-untyped-def]
    yield AssistantMessage(
        content=[TextBlock(text="The Diller estimate uses a 25% contingency. ")], model="m"
    )
    yield AssistantMessage(
        content=[ToolUseBlock(id="t1", name="mcp__bosc__program_overview", input={})], model="m"
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=3,
        session_id="s",
        total_cost_usd=0.0321,
        result="Findings: the Diller estimate uses a 25% contingency.",
    )


# --- distillation ----------------------------------------------------------
def test_distill_normalizes_labels_and_dedupe_key() -> None:
    proposals = distill_proposals(
        "some findings", topic="contingency", extractor=_extractor(), max_proposals=5
    )
    assert len(proposals) == 2
    first = proposals[0]
    # process labels are prepended in code; the topical suggestion is preserved, deduped.
    assert first.labels == ["agent-proposed", "needs-triage", "extraction"]
    assert first.dedupe_key == "verify-the-diller-roundabout-contingency-rate"


def test_distill_respects_max_proposals() -> None:
    proposals = distill_proposals("f", topic="t", extractor=_extractor(), max_proposals=1)
    assert len(proposals) == 1


# --- orchestration ---------------------------------------------------------
def test_run_research_builds_manifest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "query", _fake_query)
    manifest = asyncio.run(
        run_research(
            "Diller contingency",
            generated_at="2026-06-10T12:00:00+00:00",
            settings=Settings(),
            extractor=_extractor(),
            max_proposals=5,
        )
    )
    prov = manifest.provenance
    assert prov.topic == "Diller contingency"
    assert prov.tools_used == ["mcp__bosc__program_overview"]
    assert prov.num_turns == 3
    assert prov.cost_usd == 0.0321
    assert prov.max_turns == Settings().research_max_turns  # taken from the agent
    assert "25% contingency" in manifest.findings
    assert len(manifest.proposals) == 2
    assert manifest.proposals[0].labels[:2] == ["agent-proposed", "needs-triage"]


# --- persistence -----------------------------------------------------------
def test_write_run_persists_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "query", _fake_query)
    manifest = asyncio.run(
        run_research(
            "Diller contingency",
            generated_at="2026-06-10T12:00:00+00:00",
            settings=Settings(),
            extractor=_extractor(),
            max_proposals=5,
        )
    )
    out = write_run(manifest, tmp_path / "run", settings=Settings(data_dir=tmp_path / "data"))

    findings = (out / "findings.md").read_text(encoding="utf-8")
    assert "Research run: Diller contingency" in findings
    assert "25% contingency" in findings

    doc = yaml.safe_load((out / "manifest.yaml").read_text(encoding="utf-8"))
    assert doc["meta"]["topic"] == "Diller contingency"
    assert doc["meta"]["findings"] == "findings.md"
    assert doc["meta"]["provenance"]["num_turns"] == 3
    first = doc["proposals"][0]
    assert first["dedupe_key"] == "verify-the-diller-roundabout-contingency-rate"
    assert "agent-proposed" in first["labels"]


def test_write_run_refuses_corpus_path() -> None:
    settings = Settings()
    empty = ResearchRunManifest(
        provenance=RunProvenance(topic="t", model="m", generated_at="2026-06-10T00:00:00+00:00"),
        findings="x",
        proposals=[],
    )
    with pytest.raises(ValueError, match="immutable corpus"):
        write_run(empty, settings.documents_dir / "sneaky", settings=settings)


# --- slug ------------------------------------------------------------------
def test_run_slug_is_deterministic() -> None:
    assert (
        run_slug("Diller Contingency Rate!", "2026-06-10T12:00:00+00:00")
        == "diller-contingency-rate-2026-06-10"
    )


# --- dedupe / publish plan -------------------------------------------------
def _manifest() -> ResearchRunManifest:
    return ResearchRunManifest(
        provenance=RunProvenance(
            topic="Diller contingency",
            model="claude-opus-4-8",
            generated_at="2026-06-10T12:00:00+00:00",
            tools_used=["mcp__bosc__program_overview"],
            num_turns=3,
            max_turns=30,
            cost_usd=0.0321,
        ),
        findings="Findings body.",
        proposals=[
            IssueProposal(
                title="Verify the Diller roundabout contingency rate",
                body="Reconcile 25% vs 20%.",
                labels=["agent-proposed", "needs-triage", "extraction"],
                rationale="Moves the total.",
                dedupe_key="verify-the-diller-roundabout-contingency-rate",
            ),
            IssueProposal(
                title="Extract the missing OPC detail page 327",
                body="Page 327 is unextracted.",
                labels=["agent-proposed", "needs-triage"],
                rationale="Corpus gap.",
                dedupe_key="extract-the-missing-opc-detail-page-327",
            ),
        ],
    )


def test_existing_keys_reads_marker_and_title_fallback() -> None:
    keys = existing_keys(
        [
            {"number": 1, "title": "Anything at all", "body": f"x {marker('keyed-by-marker')} y"},
            {"number": 2, "title": "Extract the missing OPC detail page 327", "body": "no marker"},
        ]
    )
    assert "keyed-by-marker" in keys  # from the embedded marker
    assert "extract-the-missing-opc-detail-page-327" in keys  # from the title slug
    assert "anything-at-all" in keys


def test_build_plan_dedupes_and_embeds_marker() -> None:
    # An open issue already covers proposal #2 (by title slug).
    existing = [{"number": 9, "title": "Extract the missing OPC detail page 327", "body": ""}]
    plan = build_plan(_manifest(), existing=existing, run_ref="data/research/run-1")

    assert plan.pr_title == "research: Diller contingency"
    assert "$0.0321" in plan.pr_body  # provenance + cost embedded (#79 PR template)
    assert "1 opened" in plan.pr_body and "1 skipped" in plan.pr_body
    assert plan.duplicates == ["extract-the-missing-opc-detail-page-327"]
    assert [i.dedupe_key for i in plan.issues] == ["verify-the-diller-roundabout-contingency-rate"]
    # The opened issue's body carries the dedupe marker so a later run won't re-propose.
    assert marker("verify-the-diller-roundabout-contingency-rate") in plan.issues[0].body
    assert "data/research/run-1" in plan.issues[0].body


def test_build_plan_skips_same_run_collision() -> None:
    m = _manifest()
    m.proposals[1].dedupe_key = m.proposals[0].dedupe_key  # force a within-run collision
    plan = build_plan(m, existing=[], run_ref="data/research/run-2")
    assert len(plan.issues) == 1
    assert plan.duplicates == [m.proposals[0].dedupe_key]


def test_load_manifest_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "query", _fake_query)
    manifest = asyncio.run(
        run_research(
            "Diller contingency",
            generated_at="2026-06-10T12:00:00+00:00",
            settings=Settings(),
            extractor=_extractor(),
            max_proposals=5,
        )
    )
    out = write_run(manifest, tmp_path / "run", settings=Settings(data_dir=tmp_path / "data"))
    loaded = load_manifest(out)
    assert loaded.provenance.topic == "Diller contingency"
    assert loaded.provenance.num_turns == 3
    assert loaded.provenance.cost_usd == 0.0321
    assert [p.dedupe_key for p in loaded.proposals] == [p.dedupe_key for p in manifest.proposals]
