"""The Claude-driven research agent.

A thin wrapper over the Claude Agent SDK that wires in BOSC's in-process tools,
applies project defaults from :mod:`watermark.config`, and exposes a simple
``await agent.run(prompt) -> str`` surface plus a streaming variant.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from importlib.resources import files

import opentelemetry.trace
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)
from opentelemetry.trace import StatusCode

from watermark.agent import tools
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)


@dataclass
class AgentResult:
    """The outcome of one research turn: the answer plus run metadata."""

    text: str
    tools_used: list[str] = field(default_factory=list)
    num_turns: int = 0
    cost_usd: float | None = None
    is_error: bool = False


# The agent's standing instructions are the investigative-method discipline prompt,
# shipped as a package asset so it loads from the wheel (the docs/ copy isn't packaged).
# Kept in sync with docs/investigative-method/SYSTEM_PROMPT.md by tests/test_agent.py.
DEFAULT_SYSTEM_PROMPT = (files("watermark.agent") / "system_prompt.md").read_text(encoding="utf-8")

# The skills (`.claude/skills/`) active for the read-only research surface (#247): the
# evidentiary spine plus the two analysis skills that fit a read-only corpus. The three
# authoring/legal/production skills are held back until the agent gains a drafting mode.
RESEARCH_SKILLS = [
    "evidentiary-discipline",
    "entity-and-document-deconstruction",
    "gis-and-siting-analysis",
    "data-center-sweep",
]


class ResearchAgent:
    """Reusable handle to a configured Claude research agent."""

    def __init__(
        self,
        *,
        model: str | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_turns: int | None = None,
        settings: Settings | None = None,
        enable_tools: bool = True,
        skills: list[str] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.model
        self.system_prompt = system_prompt
        self.max_turns = max_turns or self.settings.max_turns
        self.enable_tools = enable_tools
        self.skills = RESEARCH_SKILLS if skills is None else skills

    def _options(self) -> ClaudeAgentOptions:
        kwargs: dict[str, object] = {
            "model": self.model,
            "system_prompt": self.system_prompt,
            "max_turns": self.max_turns,
            # Headless: the BOSC tools are read-only, so auto-run them without prompts.
            "permission_mode": "bypassPermissions",
            # Load the investigative-method skills from `.claude/skills/` (#247). Setting
            # `skills` makes the SDK wire in the `Skill` tool + the project source itself, so
            # `allowed_tools` stays only the read-only BOSC tools; `setting_sources` is set
            # explicitly so the configuration is visible and testable.
            "skills": list(self.skills),
            "setting_sources": ["project"],
        }
        if self.enable_tools:
            kwargs["mcp_servers"] = {tools.SERVER_NAME: tools.build_server()}
            kwargs["allowed_tools"] = tools.ALLOWED_TOOL_NAMES
        return ClaudeAgentOptions(**kwargs)  # type: ignore[arg-type]

    async def converse(
        self, prompt: str, *, on_text: Callable[[str], None] | None = None
    ) -> AgentResult:
        """Run one turn, optionally streaming text via ``on_text``; return the result.

        Captures the final answer (the SDK ``ResultMessage`` if present, else the
        concatenated assistant text), which tools the agent invoked, and run cost.
        """
        tracer = opentelemetry.trace.get_tracer(__name__)
        with tracer.start_as_current_span("agent.research") as span:
            span.set_attribute("agent.model", self.model)
            span.set_attribute("agent.max_turns", self.max_turns)
            span.set_attribute(
                "agent.tool_names",
                list(tools.ALLOWED_TOOL_NAMES) if self.enable_tools else [],
            )
            log.info("agent.run", model=self.model, tools=self.enable_tools)
            parts: list[str] = []
            result = AgentResult(text="")
            async for message in query(prompt=prompt, options=self._options()):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            parts.append(block.text)
                            if on_text is not None:
                                on_text(block.text)
                        elif isinstance(block, ToolUseBlock):
                            result.tools_used.append(block.name)
                elif isinstance(message, ResultMessage):
                    result.num_turns = message.num_turns
                    result.cost_usd = message.total_cost_usd
                    result.is_error = message.is_error
                    if message.result:
                        result.text = message.result
            if not result.text:
                result.text = "\n".join(parts).strip()
            span.set_attribute("agent.turns", result.num_turns)
            if result.cost_usd is not None:
                span.set_attribute("agent.cost_usd", result.cost_usd)
            if result.is_error:
                span.set_status(StatusCode.ERROR)
            log.info(
                "agent.done",
                tools=len(result.tools_used),
                turns=result.num_turns,
                cost_usd=result.cost_usd,
            )
            return result

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield assistant text blocks as they arrive."""
        async for message in query(prompt=prompt, options=self._options()):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield block.text

    async def run(self, prompt: str) -> str:
        """Run a single research turn and return the final answer text."""
        return (await self.converse(prompt)).text
