"""Orchestrate one automated-research run.

Two stages, reusing both surfaces of :mod:`bosc.agent`:

  1. **Investigate** — the open-ended :class:`~bosc.agent.client.ResearchAgent`
     (Agent SDK) explores the topic with the read-only BOSC tools and returns
     citation-grounded findings.
  2. **Distill** — the deterministic :class:`~bosc.agent.extractor.StructuredExtractor`
     (forced tool use) converts those findings into a validated set of issue proposals.

The run is **read-only on the corpus**: the agent's tools only read, and persistence
(:func:`write_run`) writes solely under ``data/research/`` — it refuses to write under
``data/documents/``. Both the agent and the extractor are injectable, so the
orchestration is unit-tested without network or API keys.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from bosc.agent.client import AgentResult, ResearchAgent
from bosc.agent.extractor import StructuredExtractor
from bosc.config import Settings, get_settings
from bosc.logging import get_logger
from bosc.research.models import (
    RUNTIME_LABELS,
    IssueProposal,
    ProposalDrafts,
    ResearchRunManifest,
    RunProvenance,
)

log = get_logger(__name__)

# Bound the findings text handed to the distiller (cost guard; reports are short).
_MAX_FINDINGS_CHARS = 60_000

_RESEARCH_PROMPT = """\
Investigate this topic over the Project BOSC corpus using the read-only BOSC tools
(timeline, entities, program_overview, read_extraction, reconcile_*, the hydrology
tools, etc.). Produce a thorough, citation-grounded findings report: state what the
evidence shows and cite source pages/files; distinguish high-confidence figures from
approximate (~) transcriptions; never fabricate sources or line items (prefer omission
over invention). Then call out concrete, actionable follow-up investigations worth
tracking as issues — corpus gaps, unverified claims, reconciliation discrepancies, or
new extraction targets.

Topic: {topic}
"""

_DISTILL_INSTRUCTIONS = """\
You are converting a Project BOSC research agent's findings into concrete, actionable
GitHub issue proposals for follow-up investigation. Use ONLY the findings text below —
add no outside knowledge. Propose at most {max_proposals} issues, each a specific,
self-contained next step grounded in the findings (a corpus gap, an unverified claim to
check, a reconciliation discrepancy, or a new extraction target). For each proposal:
- title: a crisp, imperative one-line summary.
- body: context, the grounding from the findings (cite the sources the findings name),
  and a concrete acceptance criterion.
- rationale: one sentence on why this is worth doing.
- labels: optional *topical* labels only (e.g. extraction, hydrology, entities); omit
  the process labels, they are added automatically.
If the findings surface no actionable follow-ups, return an empty list.

Topic: {topic}
"""


def slug(text: str, *, max_len: int = 64) -> str:
    """A stable, filesystem- and search-friendly slug of ``text``.

    Also the basis of a proposal's ``dedupe_key``, so dedupe stays deterministic.
    """
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "research"


def run_slug(topic: str, generated_at: str) -> str:
    """Deterministic run-directory name: ``<topic-slug>-<date>``."""
    return f"{slug(topic, max_len=48)}-{generated_at[:10]}"


def distill_proposals(
    findings: str,
    *,
    topic: str,
    extractor: StructuredExtractor,
    max_proposals: int,
) -> list[IssueProposal]:
    """Distill findings text into normalized issue proposals (forced tool use).

    The model drafts topical proposals; we add the process labels
    (:data:`~bosc.research.models.RUNTIME_LABELS`) and a stable dedupe key in code so
    those are never subject to model whim.
    """
    drafts = extractor.extract_from_text(
        ProposalDrafts,
        instructions=_DISTILL_INSTRUCTIONS.format(topic=topic, max_proposals=max_proposals),
        text=findings[:_MAX_FINDINGS_CHARS],
    )
    proposals: list[IssueProposal] = []
    for d in drafts.proposals[:max_proposals]:
        labels = list(dict.fromkeys([*RUNTIME_LABELS, *d.labels]))
        proposals.append(
            IssueProposal(
                title=d.title,
                body=d.body,
                labels=labels,
                rationale=d.rationale,
                dedupe_key=slug(d.title),
            )
        )
    return proposals


async def run_research(
    topic: str,
    *,
    generated_at: str,
    settings: Settings | None = None,
    agent: ResearchAgent | None = None,
    extractor: StructuredExtractor | None = None,
    max_turns: int | None = None,
    max_proposals: int | None = None,
    enable_tools: bool = True,
    on_text: Callable[[str], None] | None = None,
) -> ResearchRunManifest:
    """Run one investigation and return its manifest (does not persist).

    ``generated_at`` is supplied by the caller (an ISO-8601 stamp) so runs stay
    deterministic and testable. The agent/extractor are injectable for the same reason.
    """
    settings = settings or get_settings()
    max_turns = max_turns or settings.research_max_turns
    max_proposals = max_proposals if max_proposals is not None else settings.research_max_proposals
    agent = agent or ResearchAgent(
        settings=settings, max_turns=max_turns, enable_tools=enable_tools
    )
    extractor = extractor or StructuredExtractor(settings=settings)

    result: AgentResult = await agent.converse(
        _RESEARCH_PROMPT.format(topic=topic), on_text=on_text
    )
    proposals = distill_proposals(
        result.text, topic=topic, extractor=extractor, max_proposals=max_proposals
    )
    provenance = RunProvenance(
        topic=topic,
        model=agent.model,
        generated_at=generated_at,
        tools_used=list(dict.fromkeys(result.tools_used)),
        num_turns=result.num_turns,
        max_turns=agent.max_turns,
        cost_usd=result.cost_usd,
        is_error=result.is_error,
    )
    log.info(
        "research.run",
        topic=topic,
        proposals=len(proposals),
        turns=result.num_turns,
        cost_usd=result.cost_usd,
    )
    return ResearchRunManifest(provenance=provenance, findings=result.text, proposals=proposals)


def _manifest_doc(manifest: ResearchRunManifest) -> dict[str, Any]:
    """The committed ``manifest.yaml`` shape: meta/provenance + the proposal list."""
    p = manifest.provenance
    return {
        "meta": {
            "topic": p.topic,
            "model": p.model,
            "generated_at": p.generated_at,
            "method": (
                "open-ended research agent over the read-only BOSC tools, then "
                "structured issue-proposal distillation (forced tool use). "
                "Read-only on data/documents/**."
            ),
            "provenance": {
                "tools_used": p.tools_used,
                "num_turns": p.num_turns,
                "max_turns": p.max_turns,
                "cost_usd": p.cost_usd,
                "is_error": p.is_error,
            },
            "findings": "findings.md",
        },
        "proposals": [
            {
                "title": pr.title,
                "dedupe_key": pr.dedupe_key,
                "labels": pr.labels,
                "rationale": pr.rationale,
                "body": pr.body,
            }
            for pr in manifest.proposals
        ],
    }


def _findings_markdown(manifest: ResearchRunManifest) -> str:
    """The human-readable ``findings.md``: a provenance header + the agent's report."""
    p = manifest.provenance
    cost = "—" if p.cost_usd is None else f"${p.cost_usd:.4f}"
    head = (
        f"# Research run: {p.topic}\n\n"
        f"- model: `{p.model}`\n"
        f"- generated: {p.generated_at}\n"
        f"- turns: {p.num_turns} (cap {p.max_turns}); cost: {cost}\n"
        f"- tools: {', '.join(p.tools_used) or '—'}\n"
        f"- proposals: {len(manifest.proposals)} (see `manifest.yaml`)\n\n"
        "---\n\n"
    )
    return head + manifest.findings.strip() + "\n"


def write_run(
    manifest: ResearchRunManifest, out_dir: Path, *, settings: Settings | None = None
) -> Path:
    """Persist a run: ``findings.md`` + ``manifest.yaml`` under ``out_dir``.

    Chain of custody: refuses to write under the immutable corpus
    (``data/documents/``). Returns ``out_dir``.
    """
    settings = settings or get_settings()
    resolved = out_dir.resolve()
    docs = settings.documents_dir.resolve()
    if resolved == docs or docs in resolved.parents:
        raise ValueError(f"refusing to write a research run under the immutable corpus: {out_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "findings.md").write_text(_findings_markdown(manifest), encoding="utf-8")
    (out_dir / "manifest.yaml").write_text(
        yaml.safe_dump(_manifest_doc(manifest), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("research.write", out_dir=str(out_dir), proposals=len(manifest.proposals))
    return out_dir


def load_manifest(run_dir: Path) -> ResearchRunManifest:
    """Reconstruct a manifest from a written run dir (the inverse of :func:`write_run`).

    Reads ``manifest.yaml`` (provenance + proposals); ``findings`` is read back from
    ``findings.md`` when present. Used by ``bosc research publish`` so the workflow can
    turn a run into a PR + issues without re-running the agent.
    """
    data = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8")) or {}
    meta = data.get("meta", {})
    prov = meta.get("provenance", {})
    provenance = RunProvenance(
        topic=meta.get("topic", ""),
        model=meta.get("model", ""),
        generated_at=meta.get("generated_at", ""),
        tools_used=list(prov.get("tools_used", [])),
        num_turns=int(prov.get("num_turns", 0)),
        max_turns=int(prov.get("max_turns", 0)),
        cost_usd=prov.get("cost_usd"),
        is_error=bool(prov.get("is_error", False)),
    )
    proposals = [IssueProposal.model_validate(p) for p in data.get("proposals", [])]
    findings_path = run_dir / "findings.md"
    findings = findings_path.read_text(encoding="utf-8") if findings_path.exists() else ""
    return ResearchRunManifest(provenance=provenance, findings=findings, proposals=proposals)
