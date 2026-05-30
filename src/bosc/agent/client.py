"""The Claude-driven research agent.

A thin wrapper over the Claude Agent SDK that wires in BOSC's in-process tools,
applies project defaults from :mod:`bosc.config`, and exposes a simple
``await agent.run(prompt) -> str`` surface plus a streaming variant.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    query,
)

from bosc.agent import tools
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

DEFAULT_SYSTEM_PROMPT = """\
You are the Project BOSC research agent. You investigate public-records source
material about the privately funded BOSC roadwork program and its engineering
cost estimates. Be precise and cite source pages/files. When numbers are
involved, prefer the deterministic BOSC tools (reconcile_summary, read_extraction)
over estimating in your head. Distinguish high-confidence figures from
approximate (~) transcriptions. Never fabricate line items or sources.
"""


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
    ) -> None:
        self.settings = settings or get_settings()
        self.model = model or self.settings.model
        self.system_prompt = system_prompt
        self.max_turns = max_turns or self.settings.max_turns
        self.enable_tools = enable_tools

    def _options(self) -> ClaudeAgentOptions:
        kwargs: dict[str, object] = {
            "model": self.model,
            "system_prompt": self.system_prompt,
            "max_turns": self.max_turns,
        }
        if self.enable_tools:
            kwargs["mcp_servers"] = {tools.SERVER_NAME: tools.build_server()}
            kwargs["allowed_tools"] = tools.ALLOWED_TOOL_NAMES
        return ClaudeAgentOptions(**kwargs)  # type: ignore[arg-type]

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield assistant text blocks as they arrive."""
        async for message in query(prompt=prompt, options=self._options()):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        yield block.text

    async def run(self, prompt: str) -> str:
        """Run a single research turn and return the concatenated final text."""
        log.info("agent.run", model=self.model, tools=self.enable_tools)
        parts = [chunk async for chunk in self.stream(prompt)]
        return "\n".join(parts).strip()
