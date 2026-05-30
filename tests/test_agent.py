"""Tests for the agent layer: in-process tools and result aggregation.

The Claude Agent SDK ``query`` is monkeypatched, so nothing here spawns the CLI
or hits the network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from bosc.agent import client as client_mod
from bosc.agent import tools
from bosc.agent.client import ResearchAgent
from bosc.config import Settings
from bosc.models import Estimate, PageExtraction
from bosc.pipeline.extract import save_extraction


# --- tools -----------------------------------------------------------------
async def test_program_overview_reads_committed_summary() -> None:
    out = await tools.program_overview.handler({})
    text = out["content"][0]["text"]
    assert "Program construction total" in text
    assert "Diller" in text  # one of the sub-estimates
    assert "checks pass" in text


async def test_reconcile_estimate_rejects_non_generated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    settings.extracted_dir.mkdir(parents=True)
    # A file not in the generated (top-level `estimate:`) shape.
    (settings.extracted_dir / "foo.opc.yaml").write_text("sub_estimates: []\n")
    monkeypatch.setattr(tools, "get_settings", lambda: settings)
    out = await tools.reconcile_estimate.handler({"filename": "foo.opc.yaml"})
    assert "not a generated estimate extraction" in out["content"][0]["text"]


async def test_reconcile_estimate_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path)
    monkeypatch.setattr(tools, "get_settings", lambda: settings)
    estimate = Estimate.model_validate(
        {
            "name": "Test Roundabout",
            "sections": [
                {
                    "name": "ROADWAY",
                    "subtotal": 21500,
                    "line_items": [
                        {"description": "a", "total_amount": 20000},
                        {"description": "b", "total_amount": 1500},
                    ],
                },
            ],
            "construction_subtotal": 21500,
            "markups": [{"label": "Contingency", "rate": 0.25, "amount": 5375}],
            "total": 26875,
        }
    )
    path = save_extraction(
        PageExtraction(
            doc_id="d", source_path="/x", page_index=0, pdf_page=1, dpi=300, estimate=estimate
        ),
        settings=settings,
    )
    out = await tools.reconcile_estimate.handler({"filename": path.name})
    text = out["content"][0]["text"]
    assert "line-item-rollup" in text
    assert "XX" not in text  # everything ties out


# --- ResearchAgent.converse ------------------------------------------------
async def _fake_query(*, prompt: str, options: Any):  # type: ignore[no-untyped-def]
    yield AssistantMessage(content=[TextBlock(text="Looking at the estimates. ")], model="m")
    yield AssistantMessage(
        content=[ToolUseBlock(id="t1", name="mcp__bosc__program_overview", input={})], model="m"
    )
    yield ResultMessage(
        subtype="success",
        duration_ms=10,
        duration_api_ms=8,
        is_error=False,
        num_turns=2,
        session_id="s",
        total_cost_usd=0.0123,
        result="The Diller roundabout.",
    )


async def test_converse_aggregates_answer_tools_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod, "query", _fake_query)
    agent = ResearchAgent()
    streamed: list[str] = []

    result = await agent.converse("which roundabout?", on_text=streamed.append)

    assert result.text == "The Diller roundabout."  # prefers ResultMessage.result
    assert result.tools_used == ["mcp__bosc__program_overview"]
    assert result.num_turns == 2
    assert result.cost_usd == 0.0123
    assert result.is_error is False
    assert "Looking at the estimates. " in "".join(streamed)  # streamed live
