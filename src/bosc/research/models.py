"""Typed models for automated-research runs.

A run investigates a topic over the corpus (read-only) and distills its findings
into a reviewable *issue-proposal manifest*: provenance + cost + a set of concrete,
actionable follow-up issues, each carrying a stable dedupe key. The manifest is the
machine-actionable artifact the research workflow (and a human reviewer) consume; the
prose findings live alongside it as ``findings.md``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Process labels every agent-proposed issue carries: provenance (``agent-proposed``)
# plus inert-until-triaged (``needs-triage``). These are the runtime labels managed in
# ``.github/config`` (Pulumi, Epic 5.4); a proposal stays inert until a maintainer
# triages it. They are added in code, never by the distillation model.
RUNTIME_LABELS: tuple[str, ...] = ("agent-proposed", "needs-triage")


class ProposalDraft(BaseModel):
    """One issue proposal as drafted by the distillation model (pre-normalization).

    The forced-tool-use schema the model fills. ``labels`` here are *topical*
    suggestions only (e.g. ``extraction``); the process labels are added downstream.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    rationale: str
    labels: list[str] = Field(default_factory=list)


class ProposalDrafts(BaseModel):
    """The distillation target: the full set of drafts from one findings pass."""

    model_config = ConfigDict(extra="forbid")

    proposals: list[ProposalDraft]


class IssueProposal(BaseModel):
    """A normalized, ready-to-open issue proposal (runtime labels + dedupe key)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    labels: list[str]
    rationale: str
    # Stable slug used to dedupe a proposal against existing open issues (Epic 5.5).
    dedupe_key: str


class RunProvenance(BaseModel):
    """How a run was produced — the audit trail embedded in the manifest."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    model: str
    generated_at: str  # ISO-8601; injected by the caller (keeps runs deterministic)
    tools_used: list[str] = Field(default_factory=list)
    num_turns: int = 0
    max_turns: int = 0
    cost_usd: float | None = None
    is_error: bool = False


class ResearchRunManifest(BaseModel):
    """A complete research run: provenance, prose findings, and issue proposals."""

    model_config = ConfigDict(extra="forbid")

    provenance: RunProvenance
    findings: str
    proposals: list[IssueProposal]
