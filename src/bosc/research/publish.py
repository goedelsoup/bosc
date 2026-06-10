"""Turn a research run into a *publish plan*: which proposals become new issues
(deduped against the ones already open) and the PR body that frames the run.

Pure and I/O-free by design — GitHub reads (the existing-issues list) and writes
(``gh issue/pr create``, the branch push) happen in the ``research.yml`` workflow.
This module only *decides and renders*, so the dedupe and the PR/issue templating are
unit-tested without a network or a token.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from bosc.research.models import IssueProposal, ResearchRunManifest
from bosc.research.run import slug

# Embedded in every agent-opened issue body so a later run recognizes its own prior
# proposals even if the title was edited: ``<!-- research-dedupe: <key> -->``.
DEDUPE_MARKER = "research-dedupe"
_MARKER_RE = re.compile(rf"<!--\s*{DEDUPE_MARKER}:\s*([a-z0-9-]+)\s*-->")


def marker(key: str) -> str:
    """The HTML-comment dedupe marker embedded in an issue body."""
    return f"<!-- {DEDUPE_MARKER}: {key} -->"


def existing_keys(issues: Iterable[Mapping[str, Any]]) -> set[str]:
    """Dedupe keys already represented by the given issues.

    Reads the embedded body marker (authoritative) and also slugs the issue title as
    a fallback, so hand-filed issues and pre-marker proposals still dedupe. ``issues``
    is the parsed ``gh issue list --json number,title,body`` output.
    """
    keys: set[str] = set()
    for it in issues:
        m = _MARKER_RE.search(str(it.get("body") or ""))
        if m:
            keys.add(m.group(1))
        title = str(it.get("title") or "").strip()
        if title:
            keys.add(slug(title))
    return keys


class PlannedIssue(BaseModel):
    """One proposal resolved into a ready-to-open issue (body carries the marker)."""

    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    labels: list[str]
    dedupe_key: str


class PublishPlan(BaseModel):
    """The decision: issues to open, duplicates skipped, and the PR framing."""

    model_config = ConfigDict(extra="forbid")

    pr_title: str
    pr_body: str
    issues: list[PlannedIssue]
    duplicates: list[str]


def _issue_body(p: IssueProposal, *, run_ref: str) -> str:
    return (
        f"{p.body.strip()}\n\n"
        f"**Rationale:** {p.rationale}\n\n"
        "---\n"
        f"_Proposed by `bosc research run` ({run_ref}); inert until a maintainer "
        f"triages it._\n{marker(p.dedupe_key)}\n"
    )


def _pr_body(
    manifest: ResearchRunManifest,
    fresh: list[PlannedIssue],
    duplicates: list[str],
    *,
    run_ref: str,
) -> str:
    p = manifest.provenance
    cost = "—" if p.cost_usd is None else f"${p.cost_usd:.4f}"
    lines = [
        "## Automated research run",
        "",
        f"**Topic:** {p.topic}",
        "",
        "Produced by `bosc research run` — read-only over the corpus. This PR adds "
        "only `data/research/` artifacts (findings + issue-proposal manifest); it "
        "alters no source bytes under `data/documents/**`. A maintainer review is "
        "required — the research App cannot approve or merge its own PR.",
        "",
        "### Provenance",
        f"- model: `{p.model}`",
        f"- generated: {p.generated_at}",
        f"- turns: {p.num_turns} / cap {p.max_turns}",
        f"- tools: {', '.join(p.tools_used) or '—'}",
        f"- cost: {cost}",
        "",
        "### Proposed follow-up issues",
        f"- {len(fresh)} opened (labels: `agent-proposed`, `needs-triage`)",
        f"- {len(duplicates)} skipped as duplicates of open issues",
        "",
        f"See `{run_ref}/findings.md` and `{run_ref}/manifest.yaml`.",
    ]
    return "\n".join(lines) + "\n"


def build_plan(
    manifest: ResearchRunManifest, *, existing: Iterable[Mapping[str, Any]], run_ref: str
) -> PublishPlan:
    """Decide which proposals to open as issues and render the PR body.

    A proposal whose ``dedupe_key`` matches an existing open issue is skipped.
    ``run_ref`` is the run directory path (e.g. ``data/research/run-123``), embedded
    in the issue/PR bodies so a reviewer can find the artifacts.
    """
    keys = existing_keys(existing)
    fresh: list[PlannedIssue] = []
    duplicates: list[str] = []
    for proposal in manifest.proposals:
        if proposal.dedupe_key in keys:
            duplicates.append(proposal.dedupe_key)
            continue
        # Guard against two proposals in the *same* run colliding on a key.
        keys.add(proposal.dedupe_key)
        fresh.append(
            PlannedIssue(
                title=proposal.title,
                body=_issue_body(proposal, run_ref=run_ref),
                labels=proposal.labels,
                dedupe_key=proposal.dedupe_key,
            )
        )
    return PublishPlan(
        pr_title=f"research: {manifest.provenance.topic}",
        pr_body=_pr_body(manifest, fresh, duplicates, run_ref=run_ref),
        issues=fresh,
        duplicates=duplicates,
    )
