"""Stage 3 — analyze.

Two complementary modes:

* :func:`reconcile` — deterministic arithmetic checks over a validated
  :class:`OPCSummary` (section sums, the 25% contingency, totals). Fast, cheap,
  and the first line of defense against transcription error.
* :func:`research_question` — hand a natural-language question to the Claude
  research agent with the structured data in context.
"""

from __future__ import annotations

from dataclasses import dataclass

from bosc.agent.client import ResearchAgent
from bosc.config import Settings, get_settings
from bosc.logging import get_logger
from bosc.models import OPCSummary, SubEstimate

log = get_logger(__name__)

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

    failures = [f for f in findings if not f.ok]
    log.info("analyze.reconciled", checks=len(findings), failures=len(failures))
    return findings


async def research_question(
    question: str,
    *,
    context: str = "",
    agent: ResearchAgent | None = None,
    settings: Settings | None = None,
) -> str:
    """Ask the research agent a free-form question, optionally with extra context."""
    settings = settings or get_settings()
    agent = agent or ResearchAgent(settings=settings)
    prompt = f"{context}\n\nQuestion: {question}" if context else question
    return await agent.run(prompt)
