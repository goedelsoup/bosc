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

from watermark.agent import tools, yidam_tools
from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.tasks import PipelineTask

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
        enable_yidam: bool = True,
        skills: list[str] | None = None,
        task: PipelineTask | str = PipelineTask.ASK,
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.model
        self.system_prompt = system_prompt
        self.max_turns = max_turns or self.settings.max_turns
        self.enable_tools = enable_tools
        # #1563: also serve the yidam corpus mirror (yidam://corpus/*) as an MCP backend so the
        # agent can browse/query the projected method-layer graph. Rides on `enable_tools`.
        self.enable_yidam = enable_yidam
        self.skills = RESEARCH_SKILLS if skills is None else skills
        # The pipeline task this agent's calls are attributed to (#1080): selects the per-task
        # workspace key, routed into the Agent SDK subprocess via ClaudeAgentOptions.env below.
        # Normalize once so later `.value` access (the trace attribute in converse) is always
        # safe; an unknown task string falls back to the default rather than raising mid-turn.
        self.task: PipelineTask = PipelineTask.coerce(task, default=PipelineTask.ASK)

    def _allowed_tool_names(self) -> list[str]:
        """The BOSC tool allowlist for this agent: the extraction/hydrology tools, plus (by
        default) the yidam corpus-mirror backend (#1563). Empty when tools are disabled."""
        if not self.enable_tools:
            return []
        allowed = list(tools.ALLOWED_TOOL_NAMES)
        if self.enable_yidam:
            allowed += yidam_tools.ALLOWED_TOOL_NAMES
        return allowed

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
            # The BOSC extraction/hydrology tools, plus (by default) the yidam corpus-mirror
            # backend (#1563) as a second in-process server with its own `mcp__yidam__*`
            # namespace — the agent's window onto the projected method-layer graph.
            servers: dict[str, object] = {tools.SERVER_NAME: tools.build_server()}
            if self.enable_yidam:
                servers[yidam_tools.YIDAM_SERVER_NAME] = yidam_tools.build_server()
            kwargs["mcp_servers"] = servers
            kwargs["allowed_tools"] = self._allowed_tool_names()
        # Route this task's calls through its own workspace key (#1080). The SDK merges
        # `env` over the inherited process env, so we override only ANTHROPIC_API_KEY — and
        # only when a key actually resolves, leaving ambient auth untouched otherwise.
        task_key = self.settings.anthropic_key_for(self.task)
        if task_key:
            kwargs["env"] = {"ANTHROPIC_API_KEY": task_key}
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
            span.set_attribute("agent.task", self.task.value)
            span.set_attribute("agent.max_turns", self.max_turns)
            span.set_attribute("agent.tool_names", self._allowed_tool_names())
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
