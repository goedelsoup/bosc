"""Orchestrate one automated-research run.

Two stages, reusing both surfaces of :mod:`watermark.agent`:

  1. **Investigate** — the open-ended :class:`~watermark.agent.client.ResearchAgent`
     (Agent SDK) explores the topic with the read-only BOSC tools and returns
     citation-grounded findings.
  2. **Distill** — the deterministic :class:`~watermark.agent.extractor.StructuredExtractor`
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
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError

from watermark.agent.client import AgentResult, ResearchAgent
from watermark.agent.extractor import ExtractionError, StructuredExtractor
from watermark.config import Settings, get_settings
from watermark.hypotheses import HYPOTHESES, HypothesisAssessment
from watermark.logging import get_logger
from watermark.research.models import (
    RUNTIME_LABELS,
    AssessmentDraft,
    IssueProposal,
    ProposalDrafts,
    ResearchRunManifest,
    RunProvenance,
)

log = get_logger(__name__)

# Bound the findings text handed to the distiller (cost guard; reports are short).
_MAX_FINDINGS_CHARS = 60_000

# Token budget for the proposal-distillation response. The default extractor budget (4096)
# can truncate a rich findings pass — several detailed proposals, sometimes emitted as a
# single stringified JSON array (a forced-tool-use quirk ProposalDrafts coerces) — leaving
# invalid JSON. Give it generous headroom so the array always completes (Sonnet allows far more).
_DISTILL_MAX_TOKENS = 16384

# The distillation occasionally fails on a model quirk (the proposals array emitted as a
# truncated/malformed JSON *string* that won't parse). It's the run's final step — the costly
# findings pass already succeeded — so re-roll the deterministic extractor a few times rather
# than lose the whole run; a fresh draw almost always returns a clean native array.
_DISTILL_ATTEMPTS = 3

_T = TypeVar("_T")


def _distill_with_retry(op: Callable[[], _T], *, event: str, fail_msg: str) -> _T:
    """Re-roll a forced-tool-use distillation on a model quirk, up to ``_DISTILL_ATTEMPTS``.

    Shared by :func:`distill_proposals` + :func:`_distill_assessment`: each failed draw
    (``ValidationError`` / ``ExtractionError`` — a stringified field, an off-taxonomy value)
    is logged and re-rolled; on exhaustion the last model error is re-raised explicitly (not
    ``assert``, which ``python -O`` strips into a confusing ``raise None`` — #617).
    """
    last_err: Exception | None = None
    for attempt in range(1, _DISTILL_ATTEMPTS + 1):
        try:
            return op()
        except (ValidationError, ExtractionError) as exc:  # model quirk; re-roll the draw
            last_err = exc
            log.warning(event, attempt=attempt, max=_DISTILL_ATTEMPTS, error=str(exc)[:160])
    if last_err is None:  # unreachable: every failed attempt records last_err
        raise RuntimeError(fail_msg)
    raise last_err


_RESEARCH_PROMPT = """\
Investigate this topic over the Project BOSC corpus using the read-only BOSC tools
(timeline, entities, program_overview, read_extraction, reconcile_*, the hydrology
tools, etc.).

Before synthesizing findings, call list_site_issues(state="all") to load the existing
issue backlog for this site. Use it to avoid re-proposing already-tracked findings:
cite the existing issue number if you encounter terrain that is already covered, and
prefer filling gaps in the backlog over re-covering resolved terrain.

Produce a thorough, citation-grounded findings report: state what the evidence shows
and cite source pages/files; distinguish high-confidence figures from approximate (~)
transcriptions; never fabricate sources or line items (prefer omission over invention).
Then call out concrete, actionable follow-up investigations worth tracking as issues —
corpus gaps, unverified claims, reconciliation discrepancies, or new extraction targets.

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
If the findings reference an existing tracked issue number for a finding, do NOT
propose it again — omit it from the list entirely.
If the findings surface no actionable follow-ups, return an empty list.

IMPORTANT: Call the tool with a native JSON array for the proposals field — not a
JSON-encoded string. Each proposal must be a plain JSON object (not escaped or quoted).

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
    (:data:`~watermark.research.models.RUNTIME_LABELS`) and a stable dedupe key in code so
    those are never subject to model whim.
    """
    instructions = _DISTILL_INSTRUCTIONS.format(topic=topic, max_proposals=max_proposals)
    text = findings[:_MAX_FINDINGS_CHARS]
    distill_system = (
        "You are a structured-data extractor. Always fill tool parameters with native JSON "
        "values: arrays as JSON arrays, objects as JSON objects — never as JSON-encoded strings. "
        'String fields may contain quotes; escape them properly as \\" in the JSON.'
    )
    drafts = _distill_with_retry(
        lambda: extractor.extract_from_text(
            ProposalDrafts, instructions=instructions, text=text, system=distill_system
        ),
        event="research.distill.retry",
        fail_msg="proposal distillation failed with no recorded error",
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


# --- the prompt scaffold for the hypothesis-assessment recipe ------------------------------
_ASSESS_PROMPT = """\
Assess one watershed-point site against one hypothesis about the origin of the Ohio
data-center boom, using only the read-only BOSC tools over this site's committed record.

Hypothesis {number} — {name}: {claim}
What would support or strengthen it:
{predicted}

Site under assessment: {site}

Gather the evidence for and against this hypothesis at {site}. Cite sources (pages/files);
distinguish documented facts from inferred connections; never fabricate a nexus, an operator,
or a figure (prefer "not found" over invention). A federal/operator nexus is a SIGNAL, not a
verdict. Conclude with the site's signal strength, whether the cell is documented or inferred,
the taxonomy group, and the per-field facts this hypothesis tracks ({fields}).
"""

_ASSESS_DISTILL_INSTRUCTIONS = """\
Convert the findings into ONE structured (site x hypothesis) evidence cell for {site} under
hypothesis {number} ({name}). Use ONLY the findings text — add no outside knowledge.
- signal: one of [{signals}] (strength of the nexus), or omit if nothing was found.
- tag: 'verified' (a documented fact backs it), 'inference' (an inferred connection), or
  'open' (a question, nothing documented yet).
- group: one of [{groups}], or omit.
- fields: a map with keys among [{fields}] — the concrete facts ("—" where unknown).
- citations: one per fact — source (a data/ path, permit/instrument id, or doc), source_kind
  (document/connector/reference/assumption/derived), confidence. Any non-'open' cell MUST
  carry at least one citation.
- rationale: one sentence on the evidentiary basis.
"""


def _distill_assessment(
    findings: str,
    *,
    hypothesis_id: str,
    site: str,
    instructions: str,
    extractor: StructuredExtractor,
) -> HypothesisAssessment:
    """Distill findings into one normalized ``(site x hypothesis)`` cell (forced tool use).

    Re-rolls the deterministic extractor on the forced-tool-use quirk (same guard as
    :func:`distill_proposals`); normalization validates ``signal``/``tag``/``group`` against
    the hypothesis taxonomy, so a bad draw is caught and retried rather than silently kept.
    """
    hyp = HYPOTHESES[hypothesis_id]
    text = findings[:_MAX_FINDINGS_CHARS]

    def _assess() -> HypothesisAssessment:
        draft: AssessmentDraft = extractor.extract_from_text(
            AssessmentDraft, instructions=instructions, text=text
        )
        return HypothesisAssessment(
            site=site,
            hypothesis=hyp.id,
            signal=draft.signal or None,  # "" -> None
            tag=draft.tag,  # validated against the EvidenceTag literal here
            group=draft.group or None,
            fields={k: v for k, v in draft.fields.items() if k in hyp.fields},
            citations=draft.citations,
        )

    return _distill_with_retry(
        _assess, event="research.assess.retry", fail_msg="assessment failed with no recorded error"
    )


# --- recipes: a research-agent kind is a prompt + a distillation, registered here ----------
class ResearchRecipe:
    """A research-agent kind: the prompt it investigates with, and how it distills findings.

    Building a new research agent is *registering a recipe*, not rewriting the orchestration:
    :func:`run_research` is recipe-driven and defaults to :data:`ISSUE_PROPOSAL_RECIPE` (the
    original behavior, unchanged). A recipe varies the investigate prompt, the agent skills,
    and the distillation target/normalization; the read-only tools and the provenance plumbing
    are shared. ``distill`` returns ``(issue proposals, assessment cells)`` — a recipe fills one.
    """

    name: str = "research"
    skills: tuple[str, ...] | None = None

    def validate_ctx(self, ctx: dict[str, Any]) -> None:
        """Raise if the run ``context`` lacks what the recipe needs (default: nothing)."""

    def build_prompt(self, *, topic: str, ctx: dict[str, Any]) -> str:
        raise NotImplementedError

    def distill(
        self,
        findings: str,
        *,
        topic: str,
        ctx: dict[str, Any],
        extractor: StructuredExtractor,
        max_proposals: int,
    ) -> tuple[list[IssueProposal], list[HypothesisAssessment]]:
        raise NotImplementedError


class _IssueProposalRecipe(ResearchRecipe):
    """The original run: investigate a free-text topic, distill GitHub issue proposals."""

    name = "issue-proposal"

    def build_prompt(self, *, topic: str, ctx: dict[str, Any]) -> str:
        return _RESEARCH_PROMPT.format(topic=topic)

    def distill(
        self,
        findings: str,
        *,
        topic: str,
        ctx: dict[str, Any],
        extractor: StructuredExtractor,
        max_proposals: int,
    ) -> tuple[list[IssueProposal], list[HypothesisAssessment]]:
        proposals = distill_proposals(
            findings, topic=topic, extractor=extractor, max_proposals=max_proposals
        )
        return proposals, []


class _HypothesisAssessmentRecipe(ResearchRecipe):
    """Assess the active ``--site`` against one boom-origin hypothesis; distill a cell.

    Output is *proposed*, not promoted: the candidate cell is written under the run's
    ``assessments/`` dir for review — graduating it into ``data/hypotheses/`` is a manual
    edit (mirrors ``watermark onboard``, which proposes but never promotes).
    """

    name = "hypothesis-assessment"

    def validate_ctx(self, ctx: dict[str, Any]) -> None:
        hid = ctx.get("hypothesis")
        if hid not in HYPOTHESES:
            raise ValueError(
                f"recipe {self.name!r} needs context['hypothesis'] in {sorted(HYPOTHESES)}; "
                f"got {hid!r}"
            )
        if not ctx.get("site"):
            raise ValueError(f"recipe {self.name!r} needs context['site'] (the active --site)")

    def build_prompt(self, *, topic: str, ctx: dict[str, Any]) -> str:
        hyp = HYPOTHESES[ctx["hypothesis"]]
        return _ASSESS_PROMPT.format(
            number=hyp.number,
            name=hyp.name,
            claim=hyp.claim,
            site=ctx["site"],
            fields=", ".join(hyp.fields) or "(none)",
            predicted="\n".join(f"- {p}" for p in hyp.predicted_evidence),
        )

    def distill(
        self,
        findings: str,
        *,
        topic: str,
        ctx: dict[str, Any],
        extractor: StructuredExtractor,
        max_proposals: int,
    ) -> tuple[list[IssueProposal], list[HypothesisAssessment]]:
        hyp = HYPOTHESES[ctx["hypothesis"]]
        instructions = _ASSESS_DISTILL_INSTRUCTIONS.format(
            site=ctx["site"],
            number=hyp.number,
            name=hyp.name,
            signals=", ".join(hyp.signals),
            groups=", ".join(hyp.groups) or "(none)",
            fields=", ".join(hyp.fields) or "(none)",
        )
        cell = _distill_assessment(
            findings,
            hypothesis_id=hyp.id,
            site=ctx["site"],
            instructions=instructions,
            extractor=extractor,
        )
        return [], [cell]


_ONBOARD_PROMPT = """\
You are setting up a new watershed-point site ({site}) on the BOSC research platform.
Use the read-only BOSC tools to assess the site's current state against the Lima reference
build and produce a structured onboarding review.

Start by calling list_site_issues(state="all") to load the existing issue backlog for
{site}. Use it to avoid re-filing leads that are already tracked: cite the existing
issue number when you encounter terrain already in the backlog, and use the lead queue
to calibrate where the gaps actually are before diving into each area.

For each substantive comparison step:
- Call retrieve_corpus with a focused semantic query and site="lima" to pull relevant Lima
  precedents instead of loading Lima's full corpus.
- If retrieve_corpus returns source-document context that has no corresponding entry in
  data/extracted/ for this site, call report_novel_finding to file it as a triage lead and
  move on — do not pursue it inline.

Cover the following areas for {site}:
1. NPDES / permit profile: call discover_oepa_permits to find what's on the OEPA DAM
   for this site, then call fetch_oepa_permit for each 'new' result to download it.
   Note which permits were already committed vs newly fetched vs still missing.
2. Grid / utility profile: EIA-861, BA interchange, LMP zone — what's present, what's missing.
3. Hydrology: NWIS gauges configured, 7Q10 / water-balance status.
4. GIS: parcel / zoning connectors wired; footprint geometry present.
5. Extracted corpus: what's been extracted vs what source documents exist.
6. Hypothesis assessments: which cells are populated vs open.
7. Data-center activity sweep: run search_web with I-75/rail-corridor data-center queries for
   {site}. Use the data-center-sweep skill methodology: disambiguation guardrail first, then
   source-priority order (city council resolutions → county recorder → Ohio SOS → OEPA →
   ECHO → trade press). For any active project, call fetch_url on the primary city/council
   resolution source to confirm operator, location, water draw, and tax instruments. Check
   RSEI county inventory and ECHO NPDES for NAICS 518210 entries; record a negative result
   explicitly if no project is found. Tag every claim with the BOSC evidence vocabulary:
   [verified] for cited primary-source instruments, [inference] for arithmetic, [open] for
   unconfirmed items. Do not bridge Lima/Allen County entities onto {site}.

End with a prioritized checklist of blocking gaps (items that must be resolved before the
site can be promoted to selectable) and non-blocking gaps (good follow-up leads).
Cite sources (connector outputs, committed files, GH issues) throughout. Do not fabricate
status — prefer "not found" over invented figures.
"""


class _SiteOnboardRecipe(ResearchRecipe):
    """Retrieval-augmented site-setup review: assess a new site against the Lima baseline.

    Uses retrieve_corpus for cross-site comparison (low token cost) and
    report_novel_finding to file novel source context as triage leads rather than
    chasing unapproved research lines.
    """

    name = "site-onboard"

    def validate_ctx(self, ctx: dict[str, Any]) -> None:
        if not ctx.get("site"):
            raise ValueError(f"recipe {self.name!r} needs context['site'] (the active --site slug)")

    def build_prompt(self, *, topic: str, ctx: dict[str, Any]) -> str:
        return _ONBOARD_PROMPT.format(site=ctx["site"])

    def distill(
        self,
        findings: str,
        *,
        topic: str,
        ctx: dict[str, Any],
        extractor: StructuredExtractor,
        max_proposals: int,
    ) -> tuple[list[IssueProposal], list[HypothesisAssessment]]:
        proposals = distill_proposals(
            findings, topic=topic, extractor=extractor, max_proposals=max_proposals
        )
        return proposals, []


ISSUE_PROPOSAL_RECIPE = _IssueProposalRecipe()
HYPOTHESIS_ASSESSMENT_RECIPE = _HypothesisAssessmentRecipe()
SITE_ONBOARD_RECIPE = _SiteOnboardRecipe()
RECIPES: dict[str, ResearchRecipe] = {
    ISSUE_PROPOSAL_RECIPE.name: ISSUE_PROPOSAL_RECIPE,
    HYPOTHESIS_ASSESSMENT_RECIPE.name: HYPOTHESIS_ASSESSMENT_RECIPE,
    SITE_ONBOARD_RECIPE.name: SITE_ONBOARD_RECIPE,
}


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
    recipe: ResearchRecipe | None = None,
    context: dict[str, Any] | None = None,
) -> ResearchRunManifest:
    """Run one investigation and return its manifest (does not persist).

    ``recipe`` selects the research-agent kind (default :data:`ISSUE_PROPOSAL_RECIPE`);
    ``context`` carries recipe inputs (e.g. ``{"hypothesis": ..., "site": ...}`` for the
    hypothesis-assessment recipe). ``generated_at`` is supplied by the caller (an ISO-8601
    stamp) so runs stay deterministic; the agent/extractor are injectable for testability.
    """
    settings = settings or get_settings()
    recipe = recipe or ISSUE_PROPOSAL_RECIPE
    ctx = dict(context or {})
    recipe.validate_ctx(ctx)
    max_turns = max_turns or settings.research_max_turns
    max_proposals = max_proposals if max_proposals is not None else settings.research_max_proposals
    agent = agent or ResearchAgent(
        settings=settings,
        max_turns=max_turns,
        enable_tools=enable_tools,
        skills=list(recipe.skills) if recipe.skills is not None else None,
    )
    extractor = extractor or StructuredExtractor(settings=settings, max_tokens=_DISTILL_MAX_TOKENS)

    result: AgentResult = await agent.converse(
        recipe.build_prompt(topic=topic, ctx=ctx), on_text=on_text
    )
    proposals, assessments = recipe.distill(
        result.text, topic=topic, ctx=ctx, extractor=extractor, max_proposals=max_proposals
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
        recipe=recipe.name,
        proposals=len(proposals),
        assessments=len(assessments),
        turns=result.num_turns,
        cost_usd=result.cost_usd,
    )
    return ResearchRunManifest(
        provenance=provenance,
        findings=result.text,
        proposals=proposals,
        assessments=assessments,
    )


def _assessment_doc(cell: HypothesisAssessment) -> dict[str, Any]:
    """A candidate cell as committed YAML — the ``verified`` computed field excluded so the
    file re-validates as a :class:`HypothesisAssessment` (a reviewer can move it straight into
    ``data/hypotheses/``)."""
    return cell.model_dump(mode="json", exclude={"citations": {"__all__": {"verified"}}})


def _manifest_doc(manifest: ResearchRunManifest) -> dict[str, Any]:
    """The committed ``manifest.yaml`` shape: meta/provenance + the recipe's output."""
    p = manifest.provenance
    doc: dict[str, Any] = {
        "meta": {
            "topic": p.topic,
            "model": p.model,
            "generated_at": p.generated_at,
            "method": (
                "open-ended research agent over the read-only BOSC tools, then "
                "structured distillation (forced tool use). Read-only on data/documents/**."
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
    if manifest.assessments:
        # A summary index; the full candidate cells live as files under assessments/ (write_run).
        doc["assessments"] = [
            {
                "site": a.site,
                "hypothesis": a.hypothesis,
                "signal": a.signal,
                "tag": a.tag,
                "group": a.group,
                "file": f"assessments/{a.hypothesis}-{a.site}.yaml",
            }
            for a in manifest.assessments
        ]
    return doc


def _findings_markdown(manifest: ResearchRunManifest) -> str:
    """The human-readable ``findings.md``: YAML frontmatter + the agent's report."""
    p = manifest.provenance
    cost = "~" if p.cost_usd is None else f"{p.cost_usd:.4f}"
    tools_list = "\n".join(f"  - {t}" for t in p.tools_used) if p.tools_used else "  []"
    frontmatter = (
        "---\n"
        f"topic: {p.topic}\n"
        f"model: {p.model}\n"
        f"generated: {p.generated_at}\n"
        f"turns: {p.num_turns}\n"
        f"turns_cap: {p.max_turns}\n"
        f"cost_usd: {cost}\n"
        f"proposals: {len(manifest.proposals)}\n"
        f"tools:\n{tools_list}\n"
        "---\n\n"
    )
    return frontmatter + manifest.findings.strip() + "\n"


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

    # Same-day reruns share a run_slug (<topic>-<date>), so a second run silently
    # clobbers the first's outputs. Keep overwriting (idempotent reruns are useful) but
    # warn, so a clobber is never silent (#617).
    if (out_dir / "findings.md").exists():
        log.warning("research.run.overwrite", out_dir=str(out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "findings.md").write_text(_findings_markdown(manifest), encoding="utf-8")
    (out_dir / "manifest.yaml").write_text(
        yaml.safe_dump(_manifest_doc(manifest), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    # Candidate (site x hypothesis) cells — proposed for review, each a ready-to-promote
    # data/hypotheses/ file. Promotion (moving it into data/hypotheses/) stays a manual edit.
    if manifest.assessments:
        adir = out_dir / "assessments"
        adir.mkdir(parents=True, exist_ok=True)
        for a in manifest.assessments:
            (adir / f"{a.hypothesis}-{a.site}.yaml").write_text(
                yaml.safe_dump(_assessment_doc(a), sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
    log.info(
        "research.write",
        out_dir=str(out_dir),
        proposals=len(manifest.proposals),
        assessments=len(manifest.assessments),
    )
    return out_dir


def load_manifest(run_dir: Path) -> ResearchRunManifest:
    """Reconstruct a manifest from a written run dir (the inverse of :func:`write_run`).

    Reads ``manifest.yaml`` (provenance + proposals); ``findings`` is read back from
    ``findings.md`` when present. Used by ``watermark research publish`` so the workflow can
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
    adir = run_dir / "assessments"
    assessments = (
        [
            HypothesisAssessment.model_validate(yaml.safe_load(p.read_text(encoding="utf-8")))
            for p in sorted(adir.glob("*.yaml"))
        ]
        if adir.is_dir()
        else []
    )
    return ResearchRunManifest(
        provenance=provenance, findings=findings, proposals=proposals, assessments=assessments
    )
