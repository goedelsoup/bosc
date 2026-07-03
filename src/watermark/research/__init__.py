"""Automated-research runs: investigate a topic, distill issue proposals.

The agentic-research subsystem behind ``watermark research run`` and the research GitHub
App (Epic 5). A run investigates a topic over the corpus using the existing
:class:`~watermark.agent.client.ResearchAgent` (read-only on ``data/documents/**``) and
emits a reviewable issue-proposal manifest plus prose findings; :mod:`~watermark.research.publish`
turns a written run into a deduped publish plan (issues + PR body) for the workflow.
"""

from __future__ import annotations

from watermark.research.models import IssueProposal, ResearchRunManifest, RunProvenance
from watermark.research.publish import (
    DEDUPE_MARKER,
    PlannedIssue,
    PublishPlan,
    build_plan,
    existing_keys,
    marker,
)
from watermark.research.run import (
    HYPOTHESIS_ASSESSMENT_RECIPE,
    ISSUE_PROPOSAL_RECIPE,
    RECIPES,
    SITE_ONBOARD_RECIPE,
    ResearchRecipe,
    distill_proposals,
    load_manifest,
    run_research,
    run_slug,
    slug,
    write_run,
)

__all__ = [
    "DEDUPE_MARKER",
    "HYPOTHESIS_ASSESSMENT_RECIPE",
    "ISSUE_PROPOSAL_RECIPE",
    "RECIPES",
    "SITE_ONBOARD_RECIPE",
    "IssueProposal",
    "PlannedIssue",
    "PublishPlan",
    "ResearchRecipe",
    "ResearchRunManifest",
    "RunProvenance",
    "build_plan",
    "distill_proposals",
    "existing_keys",
    "load_manifest",
    "marker",
    "run_research",
    "run_slug",
    "slug",
    "write_run",
]
