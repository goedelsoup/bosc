"""Stage 3 — analyze.

Two complementary modes:

* :func:`reconcile` — deterministic arithmetic checks over a validated
  :class:`OPCSummary` (section sums, the 25% contingency, totals). Fast, cheap,
  and the first line of defense against transcription error.
* :func:`research_question` — hand a natural-language question to the Claude
  research agent with the structured data in context.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import opentelemetry.trace

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.models import Estimate, OPCSummary, SubEstimate

if TYPE_CHECKING:
    # Imported lazily at call time to avoid a watermark.agent <-> watermark.pipeline cycle.
    from watermark.agent.client import ResearchAgent

log = get_logger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)

# Contingency + inflation rate applied to every construction subtotal.
CONTINGENCY_RATE = 0.25


@dataclass(frozen=True)
class Finding:
    """One reconciliation observation."""

    subject: str
    check: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        mark = "OK " if self.ok else "XX "
        return f"{mark} [{self.check}] {self.subject}: {self.detail}"


def _check_sub_estimate(se: SubEstimate) -> list[Finding]:
    findings: list[Finding] = []

    # 1. Section subtotals should roll up to the construction subtotal.
    section_sum = se.section_subtotals.total()
    findings.append(
        Finding(
            subject=se.name,
            check="section-rollup",
            ok=se.reconciles(),
            detail=f"sections sum {section_sum:,} vs construction_subtotal "
            f"{se.construction_subtotal:,} (delta {section_sum - se.construction_subtotal:,})",
        )
    )

    # 2. Contingency should be ~25% of the construction subtotal.
    expected_cont = round(se.construction_subtotal * CONTINGENCY_RATE)
    if se.contingency_inflation_25pct is not None:
        delta = se.contingency_inflation_25pct - expected_cont
        findings.append(
            Finding(
                subject=se.name,
                check="contingency-25pct",
                ok=abs(delta) <= max(2, round(expected_cont * 0.01)),
                detail=f"stated {se.contingency_inflation_25pct:,} vs expected "
                f"{expected_cont:,} (delta {delta:,})",
            )
        )

    # 3. construction_subtotal + contingency should equal total.
    implied_total = se.construction_subtotal + expected_cont
    findings.append(
        Finding(
            subject=se.name,
            check="total",
            ok=abs(implied_total - se.total) <= max(2, round(se.total * 0.01)),
            detail=f"subtotal+25% = {implied_total:,} vs stated total {se.total:,}",
        )
    )
    return findings


def reconcile(summary: OPCSummary) -> list[Finding]:
    """Run all deterministic arithmetic checks over a summary extraction."""
    findings: list[Finding] = []
    for se in summary.sub_estimates:
        findings.extend(_check_sub_estimate(se))

    # Cross-check the program-level headline total if the meta block has one.
    # NOTE: despite its name, meta.summary_construction_total holds the sum of
    # the six summary-sheet line costs, which are each sub-estimate's *total*
    # (post-25% contingency) — so it reconciles against grand_total(), not the
    # sum of construction subtotals. (See the reconciliation notes in the YAML.)
    stated = summary.meta.summary_construction_total
    if stated is not None:
        computed = summary.grand_total()
        findings.append(
            Finding(
                subject="PROGRAM",
                check="program-total",
                ok=abs(computed - stated) <= max(2, round(stated * 0.01)),
                detail=f"sum of sub-estimate totals {computed:,} vs meta headline "
                f"{stated:,} (delta {computed - stated:,})",
            )
        )

    # Coverage: the program-total check is self-consistent (the headline is derived from the
    # survivors), so it stays green even if a sub-estimate silently dropped out of the sweep. Cross-
    # check the assembled count against how many were expected so a truncated summary fails loudly
    # rather than under-reporting the program by a whole estimate (#1364).
    expected = summary.meta.expected_sub_estimates
    if expected is not None:
        assembled = len(summary.sub_estimates)
        findings.append(
            Finding(
                subject="PROGRAM",
                check="coverage",
                ok=assembled >= expected,
                detail=f"assembled {assembled} of {expected} expected sub-estimates"
                + (f" ({expected - assembled} dropped)" if assembled < expected else ""),
            )
        )

    failures = [f for f in findings if not f.ok]
    log.info("analyze.reconciled", checks=len(findings), failures=len(failures))
    return findings


def _approx_ok(value: float, expected: float, *, rel: float = 0.02) -> bool:
    return abs(value - expected) <= max(2, round(abs(expected) * rel))


def reconcile_estimate(estimate: Estimate) -> list[Finding]:
    """Markup-aware reconciliation of a single generic :class:`Estimate`.

    Checks, as far as the data allows (skipping missing figures):
      * line items roll up to each section subtotal (where items were extracted);
      * section subtotals roll up to the construction subtotal;
      * each percentage markup equals its rate times the construction subtotal;
      * construction subtotal + markups equals the total.

    Nothing here assumes a particular section taxonomy or markup rate.
    """
    with tracer.start_as_current_span("pipeline.analyze.reconcile") as span:
        span.set_attribute("pipeline.doc_id", estimate.name)
        span.set_attribute("pipeline.estimate_kind", estimate.profile or "generic")
        findings: list[Finding] = []
        name = estimate.name

        # 1. Line items -> section subtotal (only for sections with extracted items).
        for section in estimate.sections:
            if not section.line_items:
                continue
            if section.subtotal is None:
                findings.append(
                    Finding(
                        f"{name}:{section.key}",
                        "line-item-rollup",
                        False,
                        f"{len(section.line_items)} line items but no section subtotal",
                    )
                )
                continue
            items_sum = section.items_total()
            subtotal = float(section.subtotal)
            findings.append(
                Finding(
                    f"{name}:{section.key}",
                    "line-item-rollup",
                    _approx_ok(items_sum, subtotal),
                    f"items sum {items_sum:,.0f} vs subtotal {subtotal:,.0f} "
                    f"(delta {items_sum - subtotal:,.0f}, {len(section.line_items)} items)",
                )
            )

        construction_subtotal = estimate.construction_subtotal

        # 2. Section subtotals -> construction subtotal.
        if construction_subtotal is not None:
            sections_sum = estimate.sections_total()
            target = float(construction_subtotal)
            findings.append(
                Finding(
                    name,
                    "section-rollup",
                    _approx_ok(sections_sum, target),
                    f"sections sum {sections_sum:,.0f} vs construction_subtotal {target:,.0f} "
                    f"(delta {sections_sum - target:,.0f})",
                )
            )

        # 3. Each percentage markup should equal rate * construction subtotal.
        if isinstance(construction_subtotal, (int, float)):
            for markup in estimate.markups:
                if markup.rate is None or markup.amount is None:
                    continue
                expected = construction_subtotal * markup.rate
                stated = float(markup.amount)
                findings.append(
                    Finding(
                        f"{name}:{markup.label}",
                        "markup-rate",
                        _approx_ok(stated, expected),
                        f"stated {stated:,.0f} vs {markup.rate:.0%} of subtotal {expected:,.0f} "
                        f"(delta {stated - expected:,.0f})",
                    )
                )

        # 4. construction subtotal + markups -> total.
        if construction_subtotal is not None and estimate.total is not None:
            implied = float(construction_subtotal) + estimate.markups_total()
            total = float(estimate.total)
            findings.append(
                Finding(
                    name,
                    "total",
                    _approx_ok(implied, total),
                    f"subtotal+markups {implied:,.0f} vs total {total:,.0f} (delta {implied - total:,.0f})",
                )
            )

        failures = [f for f in findings if not f.ok]
        log.info("analyze.reconciled_estimate", checks=len(findings), failures=len(failures))
        return findings


# ---------------------------------------------------------------------------
# Self-correcting reconcile loop (issue #40).
#
# ``reconcile_estimate`` is a single deterministic pass that *emits* findings but
# acts on none. ``reconcile_with_repair`` closes that loop: when rollup checks fail
# and a re-extractor is supplied, it re-reads the offending sections (the live path
# is a higher-fidelity / second-Opus pass, injected by the caller) and reconciles
# again, up to ``max_rounds``. With no re-extractor it is a pure pass-through, so the
# known ROADWAY/PAVEMENT transcription gaps stay *characterized*, never silently
# rewritten — the committed reviewed artifact is left intact.
# ---------------------------------------------------------------------------

# A re-extractor takes the current estimate and its failing findings and returns an
# improved estimate (the live implementation re-reads the named sections at higher
# fidelity; tests inject a deterministic stub).
SectionReextractor = Callable[["Estimate", "list[Finding]"], "Estimate"]


def failing_section_keys(findings: list[Finding]) -> list[str]:
    """Distinct section keys implicated by failing rollup checks (order-stable).

    A failing ``line-item-rollup`` names its section in ``subject`` as ``name:key``;
    those keys are what a re-extractor should re-read. (A failing ``section-rollup`` is
    an estimate-level subtotal gap, not a single section — surfaced via the finding,
    not this list.)
    """
    keys: list[str] = []
    for f in findings:
        if not f.ok and f.check == "line-item-rollup":
            key = f.subject.rsplit(":", 1)[-1]
            if key not in keys:
                keys.append(key)
    return keys


@dataclass(frozen=True)
class RepairRound:
    """One pass of the repair loop: what was failing and which sections were re-read."""

    round: int
    failures_before: int
    sections: tuple[str, ...]


@dataclass(frozen=True)
class RepairResult:
    """The outcome of :func:`reconcile_with_repair`."""

    estimate: Estimate
    findings: list[Finding]
    rounds: list[RepairRound] = field(default_factory=list)

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]

    @property
    def converged(self) -> bool:
        """True if no checks fail after the loop."""
        return not self.failures


def reconcile_with_repair(
    estimate: Estimate,
    *,
    reextract: SectionReextractor | None = None,
    max_rounds: int = 2,
) -> RepairResult:
    """Reconcile, re-extracting offending sections on failure until clean or out of rounds.

    ``reextract`` is the (live or stubbed) section re-reader; when ``None`` this is a
    single deterministic pass that returns the failures as-is (characterize, don't
    rewrite). Each round re-extracts and re-reconciles; the loop stops as soon as no
    check fails. Returns the (possibly improved) estimate, the final findings, and a
    per-round audit trail.
    """
    current = estimate
    findings = reconcile_estimate(current)
    rounds: list[RepairRound] = []
    if reextract is None:
        return RepairResult(current, findings, rounds)

    for r in range(1, max_rounds + 1):
        failing = [f for f in findings if not f.ok]
        if not failing:
            break
        sections = failing_section_keys(failing)
        current = reextract(current, failing)
        findings = reconcile_estimate(current)
        rounds.append(RepairRound(round=r, failures_before=len(failing), sections=tuple(sections)))
        log.info(
            "analyze.repair_round",
            round=r,
            failures_before=len(failing),
            failures_after=len([f for f in findings if not f.ok]),
            sections=list(sections),
        )
    return RepairResult(current, findings, rounds)


async def research_question(
    question: str,
    *,
    context: str = "",
    agent: ResearchAgent | None = None,
    settings: Settings | None = None,
) -> str:
    """Ask the research agent a free-form question, optionally with extra context."""
    from watermark.agent.client import ResearchAgent

    settings = settings or get_settings()
    with tracer.start_as_current_span("pipeline.analyze.research") as span:
        span.set_attribute("pipeline.question", question[:80])
        agent = agent or ResearchAgent(settings=settings)
        prompt = f"{context}\n\nQuestion: {question}" if context else question
        return await agent.run(prompt)
