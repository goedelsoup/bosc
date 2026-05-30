"""In-process tools exposed to the research agent via an SDK MCP server.

Each tool is a thin, deterministic adapter over the pipeline so the agent can
inspect real data instead of guessing. Tools return the standard MCP content
shape (``{"content": [{"type": "text", "text": ...}]}``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool

from bosc.config import get_settings
from bosc.models import OPCSummary
from bosc.pipeline import analyze, ingest

SERVER_NAME = "bosc"


def _text(payload: str) -> dict[str, Any]:
    """Wrap a string in the MCP tool-result content shape."""
    return {"content": [{"type": "text", "text": payload}]}


@tool("list_documents", "List ingested source documents and their collections.", {})
async def list_documents(_args: dict[str, Any]) -> dict[str, Any]:
    docs = ingest.discover()
    if not docs:
        return _text("No source documents found under data/documents.")
    lines = [
        f"- {d.doc_id}  [{d.collection or 'root'}]  {d.path.name}  ({d.size_bytes / 1e6:.1f} MB)"
        for d in docs
    ]
    return _text("\n".join(lines))


@tool("list_extractions", "List available structured extraction files.", {})
async def list_extractions(_args: dict[str, Any]) -> dict[str, Any]:
    extracted = get_settings().extracted_dir
    files = sorted(extracted.glob("*.yaml")) if extracted.exists() else []
    if not files:
        return _text("No extractions found under data/extracted.")
    return _text("\n".join(f"- {f.name}" for f in files))


@tool(
    "read_extraction",
    "Read the raw text of an extraction file under data/extracted by filename.",
    {"filename": str},
)
async def read_extraction(args: dict[str, Any]) -> dict[str, Any]:
    path = get_settings().extracted_dir / Path(args["filename"]).name
    if not path.exists():
        return _text(f"Not found: {path.name}")
    return _text(path.read_text(encoding="utf-8"))


@tool(
    "reconcile_summary",
    "Run deterministic arithmetic reconciliation over a *.summary.opc.yaml file.",
    {"filename": str},
)
async def reconcile_summary(args: dict[str, Any]) -> dict[str, Any]:
    path = get_settings().extracted_dir / Path(args["filename"]).name
    if not path.exists():
        return _text(f"Not found: {path.name}")
    summary = OPCSummary.from_yaml(path)
    findings = analyze.reconcile(summary)
    return _text("\n".join(str(f) for f in findings))


# All tools, and the in-process MCP server that hosts them.
ALL_TOOLS = [list_documents, list_extractions, read_extraction, reconcile_summary]
ALLOWED_TOOL_NAMES = [f"mcp__{SERVER_NAME}__{t.name}" for t in ALL_TOOLS]


def build_server() -> Any:
    """Create the in-process SDK MCP server hosting BOSC's tools."""
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)
