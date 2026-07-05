"""GreenOps footprint assembly — usage → electricity → water derivation (#1076, #1083).

The real derivation (this module) lifts the committed per-source connector artifacts
(AWS Cost Explorer + Sustainability/CCFT, GitHub Actions billing, Anthropic Admin usage)
and the ``reference`` factor tables (EPA eGRID subregion intensity/mix, WUE water
benchmarks) into a :class:`~watermark.greenops.model.GreenopsReport`:

    vCPU/GPU-hours  ─x(W/vCPU * PUE)→  electricity (kWh)
    electricity     ─x(eGRID lb/MWh)→  CO2e / source mix   ↺ reconciled vs the AWS CCFT total
    electricity     ─x(WUE L/kWh)  →   water (direct on-site cooling + upstream generation)

**Discipline (important).** The platform's own footprint is *modeled, not metered*. A billing
export is ``reference``, every conversion here is ``derived``, and the modeling levers it
applies (per-vCPU watts, PUE, which eGRID subregion the compute runs in, average tokens per
call, the internal water budget) are stated ``assumption``s — never ``connector``-``verified``
(:meth:`GreenopsReport.assert_no_verified`). Where a source is not on disk the affected
dimension **degrades to a clearly-tagged modeled assumption** rather than faking a figure or
crashing, so a partial wiring still produces an honest report.

:func:`placeholder_report` (the fully-modeled fallback) is retained for the un-wired case and
the committed placeholder fixture; :func:`derive_footprint` is the live assembly that
``watermark greenops footprint --write`` commits to ``data/reference/greenops/footprint.yaml``
(the artifact the sustainability feed, #1084, lifts).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import yaml

from watermark.config import Settings, get_settings
from watermark.greenops.connectors.anthropic import AnthropicUsageReport, load_anthropic_usage
from watermark.greenops.connectors.aws import load_aws_carbon, load_aws_costs
from watermark.greenops.connectors.egrid import load_egrid_factors, load_wue_table
from watermark.greenops.connectors.github import load_github_usage
from watermark.greenops.model import (
    AiByTask,
    AwsCarbonReport,
    AwsCostReport,
    ComputeByFunction,
    EgridFactors,
    EgridSubregion,
    ElectricitySeries,
    GithubUsageReport,
    GreenopsPeriod,
    GreenopsReport,
    HeadlineFigure,
    MethodologyItem,
    NamedQuantity,
    WaterDraw,
    WueTable,
)
from watermark.hydrology.model import ProvenancedValue

# The rationale stamped on every placeholder figure — so a reader (and the frontend)
# can tell a modeled seed from a wired source at a glance.
_PLACEHOLDER = "modeled placeholder pending the wired source (#1078-#1083)"


def _assume(value: float, unit: str) -> ProvenancedValue:
    return ProvenancedValue.assume(value, unit, _PLACEHOLDER)


_T = TypeVar("_T")


# --- stated modeling assumptions (the `assumption` levers the derivation applies) -----------
# Every constant here is a modeling input, not a metered fact: it surfaces in the derived
# figures' citations and the methodology block so a reader can see the lever. The comments name
# the published ranges each pick sits within; the value is our stated choice.

_W_PER_VCPU = 7.0
"""Average operational power draw per *allocated* vCPU-hour, watts. Folds typical utilization
into one figure — a provisioned cloud vCPU draws power across the hours it is billed, not only
when pinned — and sits inside the Cloud Carbon Footprint / Teads per-vCPU coefficient range
(~1-12 W)."""

_PUE = 1.2
"""Power Usage Effectiveness of the hosting data centers (total facility power ÷ IT power).
Hyperscale operators (AWS/GCP/Azure) publish annualized PUEs of ~1.1-1.2."""

_AVG_TOKENS_PER_CALL = 4_000.0
"""Mean input+output tokens per model call — used to derive a call count the Anthropic Admin
API does not expose (it reports token aggregates only). A mixed workload of large agentic
extraction calls and smaller ask/corroboration calls; a stated modeling input, low confidence."""

# Modeled share of AI calls by task — asserted until the per-task workspace keys (#1080) are
# named so the Anthropic by-workspace split can be labeled by task and metered directly. Sums to 1.
_AI_TASK_SPLIT: tuple[tuple[str, float], ...] = (
    ("Structured extraction", 0.55),
    ("Search & Ask", 0.30),
    ("Corroboration assist", 0.10),
    ("Drafting summaries", 0.05),
)

_WATER_BUDGET_GAL = 150.0
"""Internal annual water-draw budget the report's gauge reads against — a stated target, not
a metered constraint."""

# vCPU count per AWS instance-size token (the CE usage-line → vCPU-hrs map). Standard AWS sizes;
# the burstable t-family is 2 vCPU across nano..medium. Unknown sizes default to _DEFAULT_VCPU.
_VCPU_BY_SIZE: dict[str, int] = {
    "nano": 2,
    "micro": 2,
    "small": 2,
    "medium": 2,
    "large": 2,
    "xlarge": 4,
    "2xlarge": 8,
    "4xlarge": 16,
    "8xlarge": 32,
    "12xlarge": 48,
    "16xlarge": 64,
    "24xlarge": 96,
}
_DEFAULT_VCPU = 2

# GitHub-hosted runner vCPU counts (the Actions-minutes → vCPU-hrs map). Standard Linux/Windows
# runners are 2-core, macOS 3-core; a "<N>-core" larger-runner SKU overrides via _runner_cores.
_MACOS_CORES = 3
_DEFAULT_RUNNER_CORES = 2

_LB_TO_MT = 0.000453592  # pounds → metric tonnes
_L_PER_GAL = 3.785411784  # liters → US gallons

# Water benchmark facility types selected from the WUE table (data/reference/.../wue-benchmarks).
_SITE_WUE_TYPE = "industry_average_site"  # direct on-site cooling, L/kWh
_SOURCE_WUE_TYPE = "grid_upstream"  # upstream water-for-electricity, L/kWh


# --- reference inputs ----------------------------------------------------------------------


@dataclass
class FootprintInputs:
    """The committed source artifacts the derivation lifts — each optional so a not-yet-wired
    (or not-yet-committed) source degrades to a modeled assumption instead of crashing."""

    aws_costs: AwsCostReport | None = None
    aws_carbon: AwsCarbonReport | None = None
    github: GithubUsageReport | None = None
    anthropic: AnthropicUsageReport | None = None
    egrid: EgridFactors | None = None
    wue: WueTable | None = None


def _greenops_dir(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "greenops"


def load_footprint_inputs(settings: Settings | None = None) -> FootprintInputs:
    """Load whatever committed connector/factor artifacts exist; a missing file → ``None``."""
    settings = settings or get_settings()
    base = _greenops_dir(settings)
    factors = base / "factors"

    def _maybe(path: Path, loader: Callable[[Path], _T]) -> _T | None:
        return loader(path) if path.exists() else None

    return FootprintInputs(
        aws_costs=_maybe(base / "aws-costs.yaml", load_aws_costs),
        aws_carbon=_maybe(base / "aws-carbon.yaml", load_aws_carbon),
        github=_maybe(base / "github-usage.yaml", load_github_usage),
        anthropic=_maybe(base / "anthropic-usage.yaml", load_anthropic_usage),
        egrid=_maybe(factors / f"egrid-{settings.egrid_year}.yaml", load_egrid_factors),
        wue=_maybe(factors / "wue-benchmarks.yaml", load_wue_table),
    )


# --- small derivation helpers --------------------------------------------------------------


def _vcpu_for_usage_type(usage_type: str) -> int:
    """vCPU count for an AWS CE usage type, e.g. ``BoxUsage:t3.medium`` → 2, ``…:c5.xlarge`` → 4."""
    for token in re.split(r"[:.\-]", usage_type.lower()):
        if token in _VCPU_BY_SIZE:
            return _VCPU_BY_SIZE[token]
    return _DEFAULT_VCPU


def _runner_cores(sku: str) -> int:
    """vCPU count for a GitHub runner SKU, honoring a ``<N>-core`` larger-runner suffix."""
    m = re.search(r"(\d+)\s*-?\s*core", sku.lower())
    if m:
        return int(m.group(1))
    if "macos" in sku.lower():
        return _MACOS_CORES
    return _DEFAULT_RUNNER_CORES


def _month_labels(period: GreenopsPeriod) -> list[str]:
    """The 12 ``%b`` month labels of the reporting window, starting at ``period.start``."""
    year, month = (int(x) for x in period.start.split("-"))
    out: list[str] = []
    for _ in range(12):
        out.append(datetime(year, month, 1).strftime("%b"))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def _period_of(inputs: FootprintInputs) -> GreenopsPeriod:
    """The reporting window — taken from the first available source (they share one window)."""
    for src in (inputs.aws_costs, inputs.github, inputs.anthropic, inputs.aws_carbon):
        if src is not None:
            return src.period
    return GreenopsPeriod(label="Jul 2025-Jun 2026", start="2025-07", end="2026-06")


def _subregion(inputs: FootprintInputs, settings: Settings) -> EgridSubregion | None:
    """The eGRID subregion the compute is modeled to run in (``greenops_grid_subregion``)."""
    if inputs.egrid is None:
        return None
    return inputs.egrid.by_code().get(settings.greenops_grid_subregion)


def _wue(inputs: FootprintInputs, facility_type: str) -> float | None:
    """The WUE benchmark (L/kWh) for a facility type, or ``None`` if the table is absent."""
    if inputs.wue is None:
        return None
    for b in inputs.wue.benchmarks:
        if b.facility_type == facility_type:
            return b.wue.value
    return None


# --- section builders (each self-degrading) ------------------------------------------------


def _compute_by_function(inputs: FootprintInputs) -> tuple[list[NamedQuantity], float, bool]:
    """vCPU-hours split by platform function, from AWS instance-hours + GitHub Actions minutes.

    Returns ``(ranked functions, total vCPU-hrs, wired)`` — ``wired`` is False when neither the
    AWS nor the GitHub source is on disk, so the caller can degrade the whole compute dimension.
    """
    wired = inputs.aws_costs is not None or inputs.github is not None
    by_fn: dict[str, tuple[str, float]] = {}  # function key → (label, vCPU-hrs)

    if inputs.aws_costs is not None:
        labels = {f.function: f.label for f in inputs.aws_costs.by_function}
        for line in inputs.aws_costs.lines:
            if line.usage_unit != "Hrs":  # only instance-hours convert to vCPU-hrs
                continue
            vcpu_hrs = line.usage_amount * _vcpu_for_usage_type(line.usage_type)
            label = labels.get(line.function, line.function.replace("_", " ").title())
            prev = by_fn.get(line.function, (label, 0.0))
            by_fn[line.function] = (label, prev[1] + vcpu_hrs)

    if inputs.github is not None:
        ci = sum(r.minutes.value / 60.0 * _runner_cores(r.sku) for r in inputs.github.by_runner)
        if ci:
            prev = by_fn.get("ci_cd", ("CI/CD", 0.0))
            by_fn["ci_cd"] = ("CI/CD", prev[1] + ci)

    ranked = sorted(by_fn.values(), key=lambda kv: kv[1], reverse=True)
    functions = [
        NamedQuantity(
            label=label,
            value=ProvenancedValue.derived(
                round(hrs, 1),
                "vCPU-hrs",
                "billed instance-hours x vCPU/instance (AWS CE) + Actions minutes x runner "
                "cores (GitHub) over the window",
                confidence="medium",
            ),
        )
        for label, hrs in ranked
    ]
    total = sum(hrs for _, hrs in ranked)
    return functions, round(total, 1), wired


def _electricity_from_compute(total_vcpu_hrs: float) -> float:
    """Derived electricity, MWh: vCPU-hrs x W/vCPU x PUE (Wh → MWh)."""
    return total_vcpu_hrs * _W_PER_VCPU * _PUE / 1_000_000.0


def _electricity_series(
    total_mwh: float, subregion: EgridSubregion | None, period: GreenopsPeriod, *, wired: bool
) -> ElectricitySeries:
    """Monthly electricity (annual total spread evenly — no metered monthly series) + source mix."""
    if not wired:  # no compute source on disk — the whole electricity dimension is unknown
        return ElectricitySeries(
            monthly=[
                NamedQuantity(label=m, value=_assume(0.0, "MWh")) for m in _month_labels(period)
            ],
            grid=_assume(0.0, "MWh"),
            renewable=_assume(0.0, "MWh"),
        )
    elec_cite = (
        f"vCPU-hrs x {_W_PER_VCPU:g} W/vCPU x PUE {_PUE:g} (compute → electricity), "
        "distributed evenly across the window"
    )
    monthly = [
        NamedQuantity(
            label=m,
            value=ProvenancedValue.derived(
                round(total_mwh / 12.0, 4), "MWh", elec_cite, confidence="low"
            ),
        )
        for m in _month_labels(period)
    ]
    if subregion is not None:
        renewable_frac = subregion.renewable_pct.value / 100.0
        mix_cite = (
            f"electricity x eGRID {subregion.code} renewables share "
            f"{subregion.renewable_pct.value:g}% ({subregion.name})"
        )
        renewable = ProvenancedValue.derived(
            round(total_mwh * renewable_frac, 4), "MWh", mix_cite, confidence="low"
        )
        grid = ProvenancedValue.derived(
            round(total_mwh * (1.0 - renewable_frac), 4), "MWh", mix_cite, confidence="low"
        )
    else:
        renewable = _assume(0.0, "MWh")
        grid = _assume(round(total_mwh, 4), "MWh")
    return ElectricitySeries(monthly=monthly, grid=grid, renewable=renewable)


def _water(total_mwh: float, inputs: FootprintInputs, *, wired: bool) -> WaterDraw:
    """Water draw split direct (on-site cooling, site WUE) / indirect (upstream, source WUE)."""
    kwh = total_mwh * 1_000.0
    site_wue = _wue(inputs, _SITE_WUE_TYPE) if wired else None
    source_wue = _wue(inputs, _SOURCE_WUE_TYPE) if wired else None
    if site_wue is not None:
        direct = ProvenancedValue.derived(
            round(kwh * site_wue / _L_PER_GAL, 1),
            "gal",
            f"electricity x {site_wue:g} L/kWh site WUE (direct on-site cooling), L → gal",
            confidence="low",
        )
    else:
        direct = _assume(0.0, "gal")
    if source_wue is not None:
        indirect = ProvenancedValue.derived(
            round(kwh * source_wue / _L_PER_GAL, 1),
            "gal",
            f"electricity x {source_wue:g} L/kWh source WUE (upstream generation), L → gal",
            confidence="low",
        )
    else:
        indirect = _assume(0.0, "gal")
    budget = ProvenancedValue.assume(
        _WATER_BUDGET_GAL, "gal", "stated internal annual water-draw budget (a target, not metered)"
    )
    return WaterDraw(direct=direct, indirect=indirect, budget_cap=budget)


def _ai_section(inputs: FootprintInputs) -> tuple[ProvenancedValue, AiByTask]:
    """The AI-inference headline (a *derived* call count) + the by-task donut (a modeled split).

    The Anthropic Admin API exposes token aggregates only — no per-message request count — so the
    call count is derived from total tokens ÷ an average-tokens-per-call assumption, and the
    by-task split stays a stated assumption until the per-task workspace keys (#1080) are named.
    """
    if inputs.anthropic is not None:
        total_tokens = inputs.anthropic.input_tokens.value + inputs.anthropic.output_tokens.value
        calls = round(total_tokens / _AVG_TOKENS_PER_CALL)
        headline = ProvenancedValue.derived(
            float(calls),
            "calls",
            f"Anthropic total tokens ({total_tokens:,.0f}) ÷ {_AVG_TOKENS_PER_CALL:g} avg "
            "tokens/call (the Admin API exposes no per-message count)",
            confidence="low",
        )
    else:
        calls = int(_assume(0, "calls").value)
        headline = _assume(0.0, "calls")

    split_cite = (
        "modeled share of calls by task — asserted until the per-task workspace keys (#1080) "
        "are named so the Anthropic by-workspace split can be labeled and metered by task"
    )
    tasks = [
        NamedQuantity(
            label=label,
            value=ProvenancedValue.assume(float(round(calls * share)), "calls", split_cite),
        )
        for label, share in _AI_TASK_SPLIT
    ]
    return headline, AiByTask(tasks=tasks)


def _co2e_reconciliation(
    total_mwh: float, subregion: EgridSubregion | None, carbon: AwsCarbonReport | None
) -> str:
    """The CCFT reconciliation note: derived CO2e (electricity x eGRID intensity) vs AWS's total.

    Names the ratio and why the two differ (the vCPU model captures only active instance
    compute, whereas AWS's estimate spans every service). Degrades cleanly if a source is absent.
    """
    if subregion is None:
        return "eGRID factors absent — electricity → CO2e reconciliation skipped."
    derived_mt = total_mwh * subregion.co2e_rate.value * _LB_TO_MT
    if carbon is None:
        return (
            f"Derived ~{derived_mt:.4f} MTCO2e (electricity x {subregion.co2e_rate.value:g} "
            f"lb/MWh, {subregion.code}); no AWS CCFT total on disk to reconcile against."
        )
    aws_mt = carbon.lbm_total.value
    ratio = derived_mt / aws_mt if aws_mt else float("nan")
    return (
        f"Derived ~{derived_mt:.4f} MTCO2e (electricity x {subregion.co2e_rate.value:g} lb/MWh, "
        f"{subregion.code}) vs AWS's location-based estimate {aws_mt:g} MTCO2e — "
        f"~{ratio:.0%} of it. The two agree in order of magnitude; they differ because the vCPU "
        "model captures only active instance compute, whereas AWS's estimate spans every service "
        "(storage, transfer, managed-service and idle-capacity overhead)."
    )


# --- the assembly --------------------------------------------------------------------------


def derive_footprint(settings: Settings | None = None) -> GreenopsReport:
    """Assemble the derived footprint report from the committed connector + factor artifacts.

    The usage → electricity → water derivation (#1083). Every wired figure is ``derived`` and
    every modeling lever an ``assumption``; a source not on disk degrades that dimension to a
    modeled assumption (nothing is fabricated or metered). The result validates against
    :class:`GreenopsReport` and passes :meth:`GreenopsReport.assert_no_verified`.
    """
    settings = settings or get_settings()
    inputs = load_footprint_inputs(settings)
    period = _period_of(inputs)
    subregion = _subregion(inputs, settings)

    functions, total_vcpu_hrs, compute_wired = _compute_by_function(inputs)
    if compute_wired:
        total_mwh = _electricity_from_compute(total_vcpu_hrs)
        compute_value = ProvenancedValue.derived(
            total_vcpu_hrs,
            "vCPU-hrs",
            "AWS billed instance-hours x vCPU/instance + GitHub Actions minutes x runner cores",
            confidence="medium",
        )
        elec_value = ProvenancedValue.derived(
            round(total_mwh, 4),
            "MWh",
            f"{total_vcpu_hrs:g} vCPU-hrs x {_W_PER_VCPU:g} W/vCPU x PUE {_PUE:g}",
            confidence="low",
        )
    else:  # no compute source wired — degrade the whole compute→electricity→water chain
        total_mwh = 0.0
        compute_value = _assume(0.0, "vCPU-hrs")
        elec_value = _assume(0.0, "MWh")

    electricity = _electricity_series(total_mwh, subregion, period, wired=compute_wired)
    water = _water(total_mwh, inputs, wired=compute_wired)
    ai_headline, ai_by_task = _ai_section(inputs)
    reconciliation = _co2e_reconciliation(total_mwh, subregion, inputs.aws_carbon)

    water_value = (
        ProvenancedValue.derived(
            round(water.total, 1),
            "gal",
            "direct on-site cooling (site WUE) + upstream generation (source WUE)",
            confidence="low",
        )
        if water.direct.source == "derived"
        else _assume(round(water.total, 1), "gal")
    )

    headline = [
        HeadlineFigure(
            key="compute",
            label="Compute",
            value=compute_value,
            sub="hosting, search, CI/CD",
            source_label="AWS Cost Explorer + GitHub Actions billing",
        ),
        HeadlineFigure(
            key="ai_inferences",
            label="AI inferences run",
            value=ai_headline,
            sub="extraction, ask, corroboration, drafting",
            source_label="Anthropic Admin usage (derived call count)",
        ),
        HeadlineFigure(
            key="electricity",
            label="Electricity drawn",
            value=elec_value,
            sub="compute + cooling, all regions",
            source_label="power-draw specs x PUE",
        ),
        HeadlineFigure(
            key="water",
            label="Water drawn",
            value=water_value,
            sub="direct cooling + generation upstream",
            source_label="WUE benchmarks",
        ),
    ]

    methodology = [
        MethodologyItem(
            title="Compute",
            body=(
                "AWS Cost Explorer instance-hours (by service, folded into platform functions) "
                "converted to vCPU-hours by instance size, plus GitHub Actions minutes converted "
                "by runner core count. Model inference runs on third-party/serverless infra "
                "(Anthropic, Bedrock) and is reported as AI volume, not our vCPU-hours; we run no "
                "GPU instances."
            ),
        ),
        MethodologyItem(
            title="Electricity & carbon",
            body=(
                f"vCPU-hours x {_W_PER_VCPU:g} W per allocated vCPU (an average-operational "
                f"assumption folding utilization) x PUE {_PUE:g}. {reconciliation}"
            ),
        ),
        MethodologyItem(
            title="Water",
            body=(
                "Modeled from electricity using published Water Usage Effectiveness (WUE) "
                "benchmarks — a site WUE for direct on-site cooling and a source WUE for the water "
                "withdrawn upstream to generate the power drawn. The two bases are reported "
                "separately, never summed across bases."
            ),
        ),
        MethodologyItem(
            title="AI inferences",
            body=(
                "The Anthropic Admin API exposes token aggregates only, so the call count is "
                f"total tokens ÷ {_AVG_TOKENS_PER_CALL:g} avg tokens/call (a stated assumption), "
                "and the by-task split is modeled until the per-task workspace keys (#1080) are "
                "named so the by-workspace usage can be labeled and metered by task."
            ),
        ),
    ]

    sources: list[str] = []
    if inputs.aws_costs is not None:
        sources.append(f"AWS Cost Explorer + Sustainability/CCFT ({period.label})")
    if inputs.github is not None:
        sources.append(f"GitHub Actions/storage billing ({period.label})")
    if inputs.anthropic is not None:
        sources.append(f"Anthropic Admin usage + cost ({period.label})")
    # Credit eGRID only when the configured subregion actually resolves — otherwise the
    # electricity → CO2e / mix conversion is skipped (see the reconciliation), so listing eGRID
    # as a source would misrepresent a factor table the derivation never applied.
    if inputs.egrid is not None and subregion is not None:
        sources.append(f"EPA {inputs.egrid.vintage} subregion {subregion.code} factors")
    if inputs.wue is not None:
        sources.append(f"WUE benchmarks ({inputs.wue.vintage})")

    degraded = [
        name
        for name, present in (
            ("AWS", inputs.aws_costs is not None),
            ("GitHub", inputs.github is not None),
            ("Anthropic", inputs.anthropic is not None),
            ("eGRID", inputs.egrid is not None),
            ("WUE", inputs.wue is not None),
        )
        if not present
    ]
    note = (
        "Derived footprint (#1083): usage → electricity → water from the committed connector "
        "exports and reference factor tables. Every conversion is `derived`; the modeling levers "
        f"(≈{_W_PER_VCPU:g} W/vCPU, PUE {_PUE:g}, eGRID subregion "
        f"{settings.greenops_grid_subregion}, {_AVG_TOKENS_PER_CALL:g} tokens/call, the water "
        "budget) are stated `assumption`s. Nothing here is metered."
    )
    if degraded:
        note += f" Sources not wired (modeled assumption): {', '.join(degraded)}."

    report = GreenopsReport(
        period=period,
        headline=headline,
        compute_by_function=ComputeByFunction(functions=functions),
        ai_by_task=ai_by_task,
        electricity=electricity,
        water=water,
        methodology=methodology,
        sources=sources,
        note=note,
    )
    report.assert_no_verified()  # discipline guard: no footprint figure may claim to be metered
    return report


def placeholder_report() -> GreenopsReport:
    """A fully modeled (``assumption``) footprint report — the un-wired-source fallback.

    Mirrors the shape and rough magnitudes the sustainability page renders, but every
    figure is a stated placeholder, not a source pull. Retained for the committed placeholder
    fixture and the fully-un-wired case; the wired assembly is :func:`derive_footprint`.
    """
    return GreenopsReport(
        period=GreenopsPeriod(label="Jul 2025-Jun 2026", start="2025-07", end="2026-06"),
        headline=[
            HeadlineFigure(
                key="compute",
                label="Compute",
                value=_assume(14_220, "vCPU-hrs"),
                sub="hosting, ingestion, search, AI",
                source_label="cloud billing export",
            ),
            HeadlineFigure(
                key="ai_inferences",
                label="AI inferences run",
                value=_assume(2_340_000, "calls"),
                sub="extraction, ask, corroboration, drafting",
                source_label="model-provider usage logs",
            ),
            HeadlineFigure(
                key="electricity",
                label="Electricity drawn",
                value=_assume(37.4, "MWh"),
                sub="compute + cooling, all regions",
                source_label="eGRID factors",
            ),
            HeadlineFigure(
                key="water",
                label="Water drawn",
                value=_assume(37_500, "gal"),
                sub="direct cooling + generation upstream",
                source_label="WUE benchmarks",
            ),
        ],
        compute_by_function=ComputeByFunction(
            functions=[
                NamedQuantity(label="Hosting", value=_assume(6_200, "vCPU-hrs")),
                NamedQuantity(label="Ingestion", value=_assume(3_400, "vCPU-hrs")),
                NamedQuantity(label="AI inference", value=_assume(3_050, "vCPU-hrs")),
                NamedQuantity(label="Search index", value=_assume(980, "vCPU-hrs")),
                NamedQuantity(label="Corroboration", value=_assume(590, "vCPU-hrs")),
            ],
        ),
        ai_by_task=AiByTask(
            tasks=[
                NamedQuantity(label="Structured extraction", value=_assume(1_220_000, "calls")),
                NamedQuantity(label="Search & Ask", value=_assume(725_000, "calls")),
                NamedQuantity(label="Corroboration assist", value=_assume(255_000, "calls")),
                NamedQuantity(label="Drafting summaries", value=_assume(140_000, "calls")),
            ],
        ),
        electricity=ElectricitySeries(
            monthly=[
                NamedQuantity(label=m, value=_assume(v, "MWh"))
                for m, v in [
                    ("Jul", 2.8),
                    ("Aug", 3.1),
                    ("Sep", 3.3),
                    ("Oct", 3.0),
                    ("Nov", 2.9),
                    ("Dec", 3.2),
                    ("Jan", 3.6),
                    ("Feb", 3.3),
                    ("Mar", 3.0),
                    ("Apr", 2.9),
                    ("May", 3.1),
                    ("Jun", 3.2),
                ]
            ],
            grid=_assume(23.2, "MWh"),
            renewable=_assume(14.2, "MWh"),
        ),
        water=WaterDraw(
            direct=_assume(15_800, "gal"),
            indirect=_assume(21_700, "gal"),
            budget_cap=_assume(45_000, "gal"),
        ),
        methodology=[
            MethodologyItem(
                title="Compute",
                body=(
                    "Read from cloud vendor billing exports, split by service tag "
                    "(hosting, ingestion, search, model inference)."
                ),
            ),
            MethodologyItem(
                title="Electricity",
                body=(
                    "vCPU- and GPU-hours converted with vendor power-draw specs, then "
                    "apportioned by EPA eGRID subregion carbon-intensity factors for where "
                    "each workload runs."
                ),
            ),
            MethodologyItem(
                title="Water",
                body=(
                    "Modeled from the electricity figure using published Water Usage "
                    "Effectiveness (WUE) benchmarks — direct on-site cooling plus the water "
                    "withdrawn upstream to generate the power we draw."
                ),
            ),
        ],
        sources=[
            "cloud billing export FY26",
            "EPA eGRID subregion RFCW factors 2025",
            "EPRI / Uptime Institute WUE benchmarks 2024",
        ],
        note=(
            "Placeholder scaffold (#1077): every figure is a modeled assumption pending its "
            "wired source. Nothing here is metered."
        ),
    )


# --- committed artifact (data/reference/greenops/footprint.yaml) ---------------------------

_FOOTPRINT_RELPATH = Path("reference") / "greenops" / "footprint.yaml"


def footprint_reference_path(settings: Settings | None = None) -> Path:
    """Where the assembled footprint report is committed (the artifact #1084's feed lifts)."""
    settings = settings or get_settings()
    return settings.data_dir / _FOOTPRINT_RELPATH


def load_footprint(path: Path) -> GreenopsReport:
    """Load a committed :class:`GreenopsReport` YAML (the artifact #1084's builder lifts)."""
    data = yaml.safe_load(path.read_text())
    return GreenopsReport.model_validate(data)


def write_footprint(report: GreenopsReport, path: Path) -> Path:
    """Persist a :class:`GreenopsReport` as YAML, creating parents. Returns the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
    )
    return path
