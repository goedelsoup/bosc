"""GreenOps footprint assembly — usage → electricity → CO2e → water (#1076, #1083, #1643).

The real derivation (this module) lifts the committed per-source connector artifacts
(AWS Cost Explorer + Sustainability/CCFT, GitHub Actions billing, Anthropic Admin usage)
and the ``reference`` factor tables (EPA eGRID subregion intensity/mix, WUE water
benchmarks) into a :class:`~watermark.greenops.model.GreenopsReport`:

    vCPU-hours      ─x(W/vCPU * PUE)→  infrastructure electricity (kWh)
    output tokens   ─x(Wh/1k * PUE) →  inference electricity (kWh)      ┐ both are our draw
    electricity     ─x(eGRID lb/MWh)→  CO2e / source mix   ↺ reconciled vs AWS's own estimate
    electricity     ─x(WUE L/kWh)  →   water (provider cooling + upstream generation)

**Scope, boundary, basis — the three things this chain gets asked to be honest about.**
Inference is *in* the energy chain (#1643/F2): a Claude-driven platform whose electricity
figure counts only rented vCPUs cannot describe itself. The cooling water is our *provider's*,
attributed to us by billed IT load (#1643/F4) — we operate no data center — and the site and
upstream terms compose into a source-basis total rather than being two bases summed. Carbon is
a published figure rather than a sentence (#1643/F1), reported location-based *and*
market-based, with each fleet priced at its own grid (#1643/F5).

**Every coefficient carries a band.** W/vCPU, PUE, the WUE rows and the per-token inference
coefficients each have dated citations and low/high bounds, propagated through the chain by
:class:`_Band`, so the published electricity / carbon / water figures show their spread.

**Illustrative vs measured** (#1643/F3): the report's ``basis`` is composed from the usage
exports' own, which the connectors stamp from the fetch path. Committed sample exports keep
the whole report ``illustrative`` and say so in the note and on the page.

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
from watermark.greenops.connectors.inference_energy import load_inference_energy
from watermark.greenops.model import (
    AiByTask,
    AwsCarbonReport,
    AwsCostReport,
    CarbonAccount,
    ComputeByFunction,
    EgridFactors,
    EgridSubregion,
    ElectricitySeries,
    EnergyBreakdown,
    GithubUsageReport,
    GreenopsPeriod,
    GreenopsReport,
    HeadlineFigure,
    InferenceEnergyTable,
    MethodologyItem,
    NamedQuantity,
    SourceBasis,
    WaterDraw,
    WueTable,
    combine_basis,
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
# figures' citations and the methodology block so a reader can see the lever. Each carries a
# BAND with dated citations (#1643/F5) — quoting a single scalar for a coefficient whose
# published range spans several-fold, on a model already known to sit ~3x below the provider's
# own estimate, presented false precision as a fact. The band propagates through the chain, so
# the published electricity / carbon / water figures each carry their own low/high.


@dataclass(frozen=True)
class _Band:
    """A positive quantity with a low/high bound, propagated through the derivation.

    Interval arithmetic over strictly non-negative monotone terms: the low bound of a product
    is the product of the low bounds. That is exact here because every factor in this chain
    (hours, watts, PUE, L/kWh, lb/MWh) is non-negative and every operation is multiply-or-add.
    """

    value: float
    low: float
    high: float

    def __mul__(self, other: _Band | float) -> _Band:
        if isinstance(other, _Band):
            return _Band(self.value * other.value, self.low * other.low, self.high * other.high)
        return _Band(self.value * other, self.low * other, self.high * other)

    def __add__(self, other: _Band) -> _Band:
        return _Band(self.value + other.value, self.low + other.low, self.high + other.high)

    def rounded(self, digits: int) -> _Band:
        return _Band(round(self.value, digits), round(self.low, digits), round(self.high, digits))


_ZERO_BAND = _Band(0.0, 0.0, 0.0)

_W_PER_VCPU = _Band(7.0, 2.1, 12.0)
"""Average operational power draw per *allocated* vCPU-hour, watts.

Folds typical utilization into one figure — a provisioned cloud vCPU draws power across the
hours it is billed, not only when pinned — and is a **whole-instance** coefficient, so it sits
deliberately above the CPU-package-only published ranges rather than inside them:

- **Low, 2.1 W** — Cloud Carbon Footprint's AWS coefficients (SPECpower-derived): 0.74 W/vCPU
  at 0% utilization to 3.5 W/vCPU at 100%, i.e. 2.12 W/vCPU at their 50% utilization fallback
  (cloudcarbonfootprint.org/docs/methodology, accessed 2026-07-31). CPU package only — it
  excludes DRAM, storage, network and chassis, which is why it is a floor and not a central
  estimate.
- **Central, 7.0 W** — a whole-instance figure. Teads Engineering, "Estimating AWS EC2
  Instances Power Consumption" (2021-03-25), measures ~5 W/vCPU for a c5.xlarge at 80%
  utilization via Intel RAPL (CPU package + DRAM), explicitly *not* counting storage,
  networking or chassis; 7 W adds that unmeasured platform overhead.
- **High, 12 W** — older/larger instance families whose platform overhead is a larger share.

The ~3x gap between this model's total and AWS's own all-service estimate is a SCOPE gap (we
model instance compute; AWS counts storage, transfer, managed services and idle capacity), not
a coefficient gap — raising this number would not close it.
"""

_PUE = _Band(1.2, 1.14, 1.56)
"""Power Usage Effectiveness of the hosting data centers (total facility power / IT power).

- **Low, 1.14** — AWS's published global average PUE for 2025 (1.15 in 2024),
  sustainability.aboutamazon.com/products-services/aws-cloud, accessed 2026-07-31.
- **Central, 1.2** — our stated pick, above AWS's own figure because CI runs on Azure and
  neither provider publishes a per-region PUE for the regions we actually land in.
- **High, 1.56** — Uptime Institute Global Data Center Survey 2024 industry average (flat for
  five consecutive years). Retained as the upper bound because a hyperscaler's *fleet* average
  is not a guarantee about any one facility.
"""

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
# We run no data center, so the cooling row is our PROVIDER's published figure, apportioned to
# us by billed IT-kWh — not an industry average standing in for a facility we don't have
# (#1643/F4). The two rows are on composable bases (`site` + `upstream`), never two WUEs summed.
_SITE_WUE_TYPE = "aws_published_site"  # provider facility cooling per IT-kWh, L/kWh
_UPSTREAM_WUE_TYPE = "grid_upstream"  # generation increment per facility-kWh, L/kWh

# Anthropic's inference serving region is not disclosed, so inference energy is attributed to
# the primary subregion rather than a fabricated one. Stated in the methodology, not hidden.
_INFERENCE_REGION_NOTE = (
    "the model provider does not disclose a serving region, so inference energy is attributed "
    "to the primary subregion"
)


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
    inference_energy: InferenceEnergyTable | None = None

    def usage_basis(self) -> SourceBasis:
        """The report's :data:`SourceBasis`, composed from the *usage* exports on disk.

        Only the usage exports vote — the eGRID/WUE/inference factor tables are published
        third-party references either way, so whether they came from a fixture says nothing
        about whether our consumption figures are real. Absent exports leave the report
        ``illustrative``, which is correct: nothing measured is behind it.
        """
        return combine_basis(
            src.basis
            for src in (self.aws_costs, self.aws_carbon, self.github, self.anthropic)
            if src is not None
        )


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
        inference_energy=_maybe(factors / "inference-energy.yaml", load_inference_energy),
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
    """The eGRID subregion the *primary* compute is modeled to run in (AWS us-east-1)."""
    if inputs.egrid is None:
        return None
    return inputs.egrid.by_code().get(settings.greenops_grid_subregion)


def _subregion_by_code(inputs: FootprintInputs, code: str) -> EgridSubregion | None:
    """One eGRID subregion by acronym, or ``None`` when the table is absent / lacks it."""
    if inputs.egrid is None:
        return None
    return inputs.egrid.by_code().get(code)


def _wue(inputs: FootprintInputs, facility_type: str, expect_basis: str) -> _Band | None:
    """The banded WUE benchmark (L/kWh) for a facility type, or ``None`` if absent.

    ``expect_basis`` is checked, not assumed: the whole point of the three-way basis
    (#1643/F4) is that picking a row on the wrong basis silently double-counts cooling, so a
    row whose basis has drifted is refused rather than applied.
    """
    if inputs.wue is None:
        return None
    for b in inputs.wue.benchmarks:
        if b.facility_type != facility_type:
            continue
        if b.basis != expect_basis:
            raise ValueError(
                f"WUE row {facility_type!r} is basis {b.basis!r}, expected {expect_basis!r}; "
                "summing across mismatched bases double-counts cooling water"
            )
        return _Band(b.wue.value, b.wue.low_or_value, b.wue.high_or_value)
    return None


# --- section builders (each self-degrading) ------------------------------------------------


@dataclass
class ComputeSplit:
    """The vCPU-hour read of the billing exports, kept split by the grid it ran on.

    ``by_subregion`` is what makes the carbon apportionment honest (#1643/F5): AWS instance
    hours and GitHub Actions minutes are two different fleets in two separately-configured
    eGRID subregions, and folding them into one total silently attributed CI to AWS's grid.
    """

    functions: list[NamedQuantity]  # ranked desc, for the by-function panel
    total_vcpu_hrs: float
    by_subregion: dict[str, float]  # eGRID subregion code -> vCPU-hrs
    wired: bool  # False when neither billing export is on disk


def _compute_by_function(inputs: FootprintInputs, settings: Settings) -> ComputeSplit:
    """vCPU-hours split by platform function *and* by the grid subregion each fleet runs on.

    AWS instance-hours land in ``greenops_grid_subregion``; GitHub Actions minutes land in
    ``greenops_ci_grid_subregion`` (hosted runners are Azure VMs). ``wired`` is False when
    neither source is on disk, so the caller can degrade the whole compute dimension.
    """
    wired = inputs.aws_costs is not None or inputs.github is not None
    by_fn: dict[str, tuple[str, float]] = {}  # function key → (label, vCPU-hrs)
    by_subregion: dict[str, float] = {}

    if inputs.aws_costs is not None:
        labels = {f.function: f.label for f in inputs.aws_costs.by_function}
        aws_hrs = 0.0
        for line in inputs.aws_costs.lines:
            if line.usage_unit != "Hrs":  # only instance-hours convert to vCPU-hrs
                continue
            vcpu_hrs = line.usage_amount * _vcpu_for_usage_type(line.usage_type)
            label = labels.get(line.function, line.function.replace("_", " ").title())
            prev = by_fn.get(line.function, (label, 0.0))
            by_fn[line.function] = (label, prev[1] + vcpu_hrs)
            aws_hrs += vcpu_hrs
        if aws_hrs:
            code = settings.greenops_grid_subregion
            by_subregion[code] = by_subregion.get(code, 0.0) + aws_hrs

    if inputs.github is not None:
        ci = sum(r.minutes.value / 60.0 * _runner_cores(r.sku) for r in inputs.github.by_runner)
        if ci:
            prev = by_fn.get("ci_cd", ("CI/CD", 0.0))
            by_fn["ci_cd"] = ("CI/CD", prev[1] + ci)
            code = settings.greenops_ci_grid_subregion
            by_subregion[code] = by_subregion.get(code, 0.0) + ci

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
    return ComputeSplit(
        functions=functions,
        total_vcpu_hrs=round(total, 1),
        by_subregion={k: round(v, 1) for k, v in by_subregion.items()},
        wired=wired,
    )


def _electricity_from_compute(total_vcpu_hrs: float) -> _Band:
    """Derived infrastructure electricity, MWh: vCPU-hrs x W/vCPU x PUE (Wh → MWh)."""
    return (_W_PER_VCPU * _PUE * total_vcpu_hrs) * (1.0 / 1_000_000.0)


def _inference_energy(inputs: FootprintInputs) -> tuple[_Band, str, list[str]]:
    """Electricity drawn generating our model output, MWh, banded — the omitted scope (F2).

    Returns ``(MWh band, citation, per-class notes)``. Priced per 1,000 **output** tokens
    against :class:`InferenceEnergyTable`, because decode dominates inference energy and
    prefill is far cheaper per token — pricing our 4.25M input tokens at the decode rate
    would have overstated this several-fold on a cache-heavy agentic workload.

    Each model's output tokens are priced at its own class's coefficient (an unmapped id falls
    to the table's conservative default), then multiplied by PUE: the anchoring measurement is
    accelerator+host, so facility overhead is ours to add. Degrades to a zero band — never a
    guess — when either the usage export or the coefficient table is absent.
    """
    if inputs.anthropic is None or inputs.inference_energy is None:
        return _ZERO_BAND, "", []

    table = inputs.inference_energy
    total_wh = _ZERO_BAND
    notes: list[str] = []
    priced_output = 0.0

    for entry in inputs.anthropic.by_model:
        bench = table.benchmark_for(entry.model)
        if bench is None:  # a table with no default class — price nothing, say nothing
            continue
        coeff = bench.wh_per_1k_tokens
        band = _Band(coeff.value, coeff.low_or_value, coeff.high_or_value)
        total_wh = total_wh + band * (entry.output_tokens / 1_000.0)
        priced_output += entry.output_tokens
        notes.append(
            f"{entry.model} ({entry.output_tokens:,} output tokens) at the "
            f"{bench.model_class} coefficient {coeff.value:g} Wh/1k "
            f"[{coeff.low_or_value:g}-{coeff.high_or_value:g}]"
        )

    # Output tokens the by-model split didn't account for (a model missing from the split, or
    # an export with no split at all) are priced at the default class rather than dropped —
    # silently omitting them would understate exactly the scope this fix exists to add.
    unpriced = max(0.0, inputs.anthropic.output_tokens.value - priced_output)
    if unpriced > 0:
        fallback = table.by_class().get(table.default_class)
        if fallback is not None:
            coeff = fallback.wh_per_1k_tokens
            band = _Band(coeff.value, coeff.low_or_value, coeff.high_or_value)
            total_wh = total_wh + band * (unpriced / 1_000.0)
            notes.append(
                f"{unpriced:,.0f} output tokens not in the by-model split, priced at the "
                f"default {table.default_class} coefficient"
            )

    mwh = (total_wh * _PUE) * (1.0 / 1_000_000.0)
    cite = (
        f"Anthropic output tokens x per-model-class Wh/1k output tokens ({table.vintage}) "
        f"x PUE {_PUE.value:g} — the published coefficients are accelerator+host, so facility "
        "overhead is added here"
    )
    return mwh, cite, notes


def _electricity_series(
    total_mwh_value: float,
    subregion: EgridSubregion | None,
    period: GreenopsPeriod,
    *,
    wired: bool,
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
        f"vCPU-hrs x {_W_PER_VCPU.value:g} W/vCPU x PUE {_PUE.value:g} (infrastructure) + "
        "model output tokens x Wh/1k output tokens x PUE (inference), distributed evenly "
        "across the window"
    )
    monthly = [
        NamedQuantity(
            label=m,
            value=ProvenancedValue.derived(
                round(total_mwh_value / 12.0, 4), "MWh", elec_cite, confidence="low"
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
            round(total_mwh_value * renewable_frac, 4), "MWh", mix_cite, confidence="low"
        )
        grid = ProvenancedValue.derived(
            round(total_mwh_value * (1.0 - renewable_frac), 4), "MWh", mix_cite, confidence="low"
        )
    else:
        renewable = _assume(0.0, "MWh")
        grid = _assume(round(total_mwh_value, 4), "MWh")
    return ElectricitySeries(monthly=monthly, grid=grid, renewable=renewable)


def _water(total_mwh: _Band, inputs: FootprintInputs, *, wired: bool) -> WaterDraw:
    """Water attributable to our draw, on the source basis (#1643/F4).

    Two composable terms, each applied to the load it is actually defined against — which is
    the fix, not a refinement:

    * **facility cooling** = our provider's published site WUE (L per **IT**-kWh) x IT-kWh.
      The old chain multiplied a per-IT-kWh benchmark by the PUE-inclusive facility total,
      overstating cooling by the full PUE factor; ``total_mwh / PUE`` divides it back out.
    * **upstream generation** = the water-for-electricity increment (L per **facility**-kWh)
      x the whole facility draw. This one *does* belong on the PUE-inclusive figure: the grid
      delivered every kWh the facility drew, overhead included.

    Their sum is a well-formed source-basis total (site + upstream **is** source WUE), not two
    bases summed — :func:`_wue` refuses a row whose basis would make it one.
    """
    facility_kwh = total_mwh * 1_000.0
    it_kwh = facility_kwh * (1.0 / _PUE.value)
    site_wue = _wue(inputs, _SITE_WUE_TYPE, "site") if wired else None
    upstream_wue = _wue(inputs, _UPSTREAM_WUE_TYPE, "upstream") if wired else None
    if site_wue is not None:
        gal = (it_kwh * site_wue * (1.0 / _L_PER_GAL)).rounded(1)
        direct = ProvenancedValue.derived(
            gal.value,
            "gal",
            f"IT-kWh (electricity / PUE {_PUE.value:g}) x {site_wue.value:g} L/kWh provider "
            "site WUE — cooling water drawn by our cloud provider's facility, attributed to "
            "us by billed IT load; we operate no data center. L → gal",
            confidence="low",
            low=gal.low,
            high=gal.high,
        )
    else:
        direct = _assume(0.0, "gal")
    if upstream_wue is not None:
        gal = (facility_kwh * upstream_wue * (1.0 / _L_PER_GAL)).rounded(1)
        indirect = ProvenancedValue.derived(
            gal.value,
            "gal",
            f"facility kWh x {upstream_wue.value:g} L/kWh upstream water-for-electricity "
            "increment (generation, per delivered kWh), L → gal",
            confidence="low",
            low=gal.low,
            high=gal.high,
        )
    else:
        indirect = _assume(0.0, "gal")
    budget = ProvenancedValue.assume(
        _WATER_BUDGET_GAL, "gal", "stated internal annual water-draw budget (a target, not metered)"
    )
    return WaterDraw(direct=direct, indirect=indirect, budget_cap=budget)


def _carbon_account(
    inputs: FootprintInputs,
    settings: Settings,
    by_subregion: dict[str, float],
    inference_mwh: _Band,
    infra_mwh: _Band,
) -> CarbonAccount | None:
    """The CO2e account — the figure eGRID exists to produce, now first-class (#1643/F1).

    Each fleet's electricity is priced at **its own** subregion's emission rate and summed, so
    CI running on a different grid is not attributed to AWS's. Inference rides on the primary
    subregion, with the reason stated rather than the attribution hidden.

    Returns ``None`` when no eGRID factors are on disk — a carbon figure with no intensity
    behind it would be an invention, so the account is absent and the section degrades.
    """
    if inputs.egrid is None:
        return None
    primary = _subregion(inputs, settings)
    total_hrs = sum(by_subregion.values())

    total_mt = _ZERO_BAND
    priced: list[str] = []
    for code, hrs in sorted(by_subregion.items()):
        sr = _subregion_by_code(inputs, code)
        if sr is None or not total_hrs:
            continue
        share = hrs / total_hrs
        mt = infra_mwh * share * (sr.co2e_rate.value * _LB_TO_MT)
        total_mt = total_mt + mt
        priced.append(f"{code} {sr.co2e_rate.value:g} lb/MWh ({share:.0%} of vCPU-hrs)")
    if primary is not None and inference_mwh.value:
        total_mt = total_mt + inference_mwh * (primary.co2e_rate.value * _LB_TO_MT)
        priced.append(f"inference at {primary.code} ({_INFERENCE_REGION_NOTE})")

    if not priced:  # factors present but nothing resolved to a subregion — say nothing
        return None

    rounded = total_mt.rounded(5)
    derived = ProvenancedValue.derived(
        rounded.value,
        "MTCO2e",
        "electricity x eGRID subregion CO2e output rate, apportioned by fleet: "
        + "; ".join(priced),
        confidence="low",
        low=rounded.low,
        high=rounded.high,
    )
    carbon = inputs.aws_carbon
    return CarbonAccount(
        derived_location_based=derived,
        provider_location_based=carbon.lbm_total if carbon is not None else None,
        market_based=carbon.mbm_total if carbon is not None else None,
        intensity=primary.co2e_rate if primary is not None else None,
        subregion=primary.code if primary is not None else None,
        reconciliation=_co2e_reconciliation(rounded.value, primary, carbon),
    )


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
    derived_mt: float, subregion: EgridSubregion | None, carbon: AwsCarbonReport | None
) -> str:
    """Reconcile *our* derived CO2e against the provider's own estimates, both methods (F1).

    Takes the already-apportioned derived total rather than recomputing it, so the prose and
    the published :class:`CarbonAccount` figure can never disagree. Names the ratio and why
    the two differ (we model instance compute + inference; AWS's estimate spans every service
    it bills us for), and reports market- **and** location-based side by side — a market-based
    total is a procurement claim, not a smaller version of the physical one. Degrades cleanly
    if a source is absent.
    """
    if subregion is None:
        return "eGRID factors absent — electricity → CO2e reconciliation skipped."
    rate = f"{subregion.co2e_rate.value:g} lb/MWh, {subregion.code}"
    if carbon is None:
        return (
            f"Derived ~{derived_mt:.4f} MTCO2e (electricity x {rate}); no AWS emissions total "
            "on disk to reconcile against."
        )
    aws_mt = carbon.lbm_total.value
    ratio = derived_mt / aws_mt if aws_mt else float("nan")
    return (
        f"Derived ~{derived_mt:.4f} MTCO2e (electricity x {rate}) vs AWS's own estimate — "
        f"{aws_mt:g} MTCO2e location-based, {carbon.mbm_total.value:g} MTCO2e market-based. "
        f"Ours is ~{ratio:.0%} of the location-based figure. They differ by scope: our model "
        "covers billed instance compute plus model inference, whereas AWS's estimate spans "
        "every service it bills (storage, transfer, managed-service and idle-capacity "
        "overhead) and none of our inference. The market-based figure is lower because it "
        "prices AWS's contracted renewable procurement, not the physical grid — it is "
        "reported alongside the location-based one, never instead of it."
    )


# --- the assembly --------------------------------------------------------------------------


def derive_footprint(settings: Settings | None = None) -> GreenopsReport:
    """Assemble the derived footprint report from the committed connector + factor artifacts.

    The usage → electricity → CO2e → water derivation (#1083, extended by #1643). Every wired
    figure is ``derived`` and every modeling lever an ``assumption``; a source not on disk
    degrades that dimension to a modeled assumption (nothing is fabricated or metered). The
    result validates against :class:`GreenopsReport` and passes
    :meth:`GreenopsReport.assert_no_verified`.

    The two energy scopes degrade **independently**: the infrastructure chain needs a billing
    export, the inference chain needs the Anthropic export plus the coefficient table, and
    either alone still produces electricity, carbon and water rather than zeroing the report.
    """
    settings = settings or get_settings()
    inputs = load_footprint_inputs(settings)
    period = _period_of(inputs)
    subregion = _subregion(inputs, settings)

    split = _compute_by_function(inputs, settings)
    compute_wired = split.wired
    infra_mwh = _electricity_from_compute(split.total_vcpu_hrs) if compute_wired else _ZERO_BAND
    inference_mwh, inference_cite, inference_notes = _inference_energy(inputs)
    # The two scopes are *both* our electricity — the vCPU chain models rented infrastructure,
    # the token chain models the inference that runs on the provider's accelerators. Scoping
    # the second out is what made the old headlines structurally unable to describe this
    # platform (#1643/F2); everything downstream (mix, carbon, water) reads this total.
    total_mwh = infra_mwh + inference_mwh
    energy_wired = compute_wired or bool(inference_mwh.value)

    if compute_wired:
        compute_value = ProvenancedValue.derived(
            split.total_vcpu_hrs,
            "vCPU-hrs",
            "AWS billed instance-hours x vCPU/instance + GitHub Actions minutes x runner cores",
            confidence="medium",
        )
    else:
        compute_value = _assume(0.0, "vCPU-hrs")

    if energy_wired:
        rounded_total = total_mwh.rounded(4)
        elec_value = ProvenancedValue.derived(
            rounded_total.value,
            "MWh",
            f"{split.total_vcpu_hrs:g} vCPU-hrs x {_W_PER_VCPU.value:g} W/vCPU x PUE "
            f"{_PUE.value:g} (infrastructure) + model inference energy; band from the "
            "coefficient ranges",
            confidence="low",
            low=rounded_total.low,
            high=rounded_total.high,
        )
    else:
        elec_value = _assume(0.0, "MWh")

    electricity = _electricity_series(total_mwh.value, subregion, period, wired=energy_wired)
    water = _water(total_mwh, inputs, wired=energy_wired)
    ai_headline, ai_by_task = _ai_section(inputs)
    carbon = _carbon_account(inputs, settings, split.by_subregion, inference_mwh, infra_mwh)
    reconciliation = (
        carbon.reconciliation
        if carbon is not None
        else _co2e_reconciliation(0.0, subregion, inputs.aws_carbon)
    )

    energy = None
    if energy_wired:
        infra_r = infra_mwh.rounded(4)
        infer_r = inference_mwh.rounded(4)
        energy = EnergyBreakdown(
            # Each scope carries its OWN provenance: an un-wired billing export must not ship a
            # `derived` zero, which would read as "we measured it and it was nothing".
            infrastructure=(
                ProvenancedValue.derived(
                    infra_r.value,
                    "MWh",
                    f"{split.total_vcpu_hrs:g} vCPU-hrs x {_W_PER_VCPU.value:g} W/vCPU x PUE "
                    f"{_PUE.value:g} (instances + CI runners)",
                    confidence="low",
                    low=infra_r.low,
                    high=infra_r.high,
                )
                if compute_wired
                else _assume(0.0, "MWh")
            ),
            inference=(
                ProvenancedValue.derived(
                    infer_r.value,
                    "MWh",
                    inference_cite
                    + (f" — {'; '.join(inference_notes)}" if inference_notes else ""),
                    confidence="low",
                    low=infer_r.low,
                    high=infer_r.high,
                )
                if inference_mwh.value
                else _assume(0.0, "MWh")
            ),
        )

    water_total = _Band(
        water.total,
        water.direct.low_or_value + water.indirect.low_or_value,
        water.direct.high_or_value + water.indirect.high_or_value,
    ).rounded(1)
    water_value = (
        ProvenancedValue.derived(
            water_total.value,
            "gal",
            "tenant-attributed provider facility cooling (site WUE x IT-kWh) + the upstream "
            "generation increment (x facility kWh) — a source-basis total, not two bases summed",
            confidence="low",
            low=water_total.low,
            high=water_total.high,
        )
        if water.direct.source == "derived"
        else _assume(water_total.value, "gal")
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
            sub="infrastructure + model inference, all regions",
            source_label="power-draw specs x PUE",
        ),
        HeadlineFigure(
            key="water",
            label="Water drawn",
            value=water_value,
            sub="provider cooling + generation upstream",
            source_label="WUE benchmarks",
        ),
    ]
    # The carbon headline (#1643/F1). eGRID's whole purpose is this number, and until now the
    # page reported every dimension except it. Appended rather than inserted so an existing
    # consumer keying on position is not silently re-pointed; absent when no factors resolve.
    if carbon is not None:
        headline.append(
            HeadlineFigure(
                key="carbon",
                label="Carbon emitted",
                value=carbon.derived_location_based,
                sub="location-based, our model"
                + (
                    f" · {carbon.market_based.value:g} market-based (AWS)"
                    if carbon.market_based is not None
                    else ""
                ),
                source_label=f"EPA eGRID {carbon.subregion or ''} intensity".strip(),
            )
        )

    regions = ", ".join(
        f"{code} ({hrs:,.0f} vCPU-hrs)" for code, hrs in sorted(split.by_subregion.items())
    )
    methodology = [
        MethodologyItem(
            title="Compute",
            body=(
                "AWS Cost Explorer instance-hours (by service, folded into platform functions) "
                "converted to vCPU-hours by instance size, plus GitHub Actions minutes converted "
                "by runner core count. We run no GPU instances: model inference happens on the "
                "provider's accelerators and appears on no bill of ours as energy, only as "
                "tokens — so it is priced separately below rather than counted here."
            ),
        ),
        MethodologyItem(
            title="Electricity & carbon",
            body=(
                f"Infrastructure: vCPU-hours x {_W_PER_VCPU.value:g} W per allocated vCPU "
                f"(range {_W_PER_VCPU.low:g}-{_W_PER_VCPU.high:g}, an average-operational "
                f"assumption folding utilization) x PUE {_PUE.value:g} (range "
                f"{_PUE.low:g}-{_PUE.high:g}). Inference: output tokens x a published "
                "per-model-class Wh/1k-output-token coefficient x PUE. Each fleet's "
                "electricity is priced at its own eGRID subregion's CO2e output rate"
                + (f" — {regions}" if regions else "")
                + f"; {_INFERENCE_REGION_NOTE}. Every headline figure carries the band its "
                f"coefficients imply. {reconciliation}"
            ),
        ),
        MethodologyItem(
            title="Water",
            body=(
                "We operate no data center. The cooling water below is our cloud provider's, "
                "attributed to us by billed IT load using its own published site WUE (liters "
                "per kWh of IT load — so the figure divides PUE back out rather than applying "
                "an IT-load benchmark to a facility-load number). Added to it is the upstream "
                "increment: the water consumed generating each kWh actually delivered to the "
                "facility. Site plus upstream is the source-basis total by definition; a "
                "site-basis and an already-source-basis benchmark are never summed, and the "
                "derivation refuses a benchmark row whose basis would make that happen."
            ),
        ),
        MethodologyItem(
            title="AI inferences",
            body=(
                "The Anthropic Admin API exposes token aggregates only, so the call count is "
                f"total tokens / {_AVG_TOKENS_PER_CALL:g} avg tokens/call (a stated assumption), "
                "and the by-task split is modeled until the per-task workspace keys (#1080) are "
                "named so the by-workspace usage can be labeled and metered by task. The energy "
                "those calls drew is priced against OUTPUT tokens, not this count and not the "
                "input+output total: decode dominates inference energy, prefill is far cheaper "
                "per token, and no provider publishes a per-token figure — so the coefficients "
                "are third-party published estimates, banded across roughly an order of "
                "magnitude because that is the spread of what has been measured."
            ),
        ),
    ]

    sources: list[str] = []
    if inputs.aws_costs is not None:
        sources.append(f"AWS Cost Explorer + Sustainability ({period.label})")
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
    if inputs.inference_energy is not None and inference_mwh.value:
        sources.append(f"inference-energy coefficients ({inputs.inference_energy.vintage})")

    degraded = [
        name
        for name, present in (
            ("AWS", inputs.aws_costs is not None),
            ("GitHub", inputs.github is not None),
            ("Anthropic", inputs.anthropic is not None),
            ("eGRID", inputs.egrid is not None),
            ("WUE", inputs.wue is not None),
            ("inference energy", inputs.inference_energy is not None),
        )
        if not present
    ]
    basis = inputs.usage_basis()
    note = (
        "Derived footprint (#1083): usage → electricity → CO2e → water from the committed "
        "connector exports and reference factor tables. Every conversion is `derived`; the "
        f"modeling levers (≈{_W_PER_VCPU.value:g} W/vCPU, PUE {_PUE.value:g}, eGRID subregions "
        f"{settings.greenops_grid_subregion} (cloud) / {settings.greenops_ci_grid_subregion} "
        f"(CI), {_AVG_TOKENS_PER_CALL:g} tokens/call, the per-token inference coefficients, "
        "the water budget) are stated `assumption`s. Nothing here is metered."
    )
    if basis == "illustrative":
        note += (
            " ILLUSTRATIVE: the usage exports behind these figures are committed samples, not a "
            "live provider pull, so the magnitudes are shaped like a real footprint but are not "
            "one. Wire the `watermark greenops <source> --write` pulls to flip this (#1643/F3)."
        )
    if degraded:
        note += f" Sources not wired (modeled assumption): {', '.join(degraded)}."

    report = GreenopsReport(
        period=period,
        headline=headline,
        compute_by_function=ComputeByFunction(functions=split.functions),
        ai_by_task=ai_by_task,
        electricity=electricity,
        energy=energy,
        carbon=carbon,
        water=water,
        methodology=methodology,
        sources=sources,
        basis=basis,
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
                sub="provider cooling + generation upstream",
                source_label="WUE benchmarks",
            ),
            HeadlineFigure(
                key="carbon",
                label="Carbon emitted",
                value=_assume(15.0, "MTCO2e"),
                sub="location-based, our model",
                source_label="EPA eGRID SRVC intensity",
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
        energy=EnergyBreakdown(
            infrastructure=_assume(24.5, "MWh"),
            inference=_assume(12.9, "MWh"),
        ),
        carbon=CarbonAccount(
            derived_location_based=_assume(15.0, "MTCO2e"),
            subregion="SRVC",
            reconciliation=(
                "Placeholder: no provider emissions export wired, so there is nothing to "
                "reconcile the modeled location-based figure against."
            ),
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
                    "Effectiveness (WUE) benchmarks — our provider's facility cooling, "
                    "attributed to us by billed IT load, plus the water consumed upstream to "
                    "generate the power delivered. We operate no data center."
                ),
            ),
        ],
        sources=[
            "cloud billing export FY26",
            "EPA eGRID subregion SRVC factors 2025",
            "EPRI / Uptime Institute WUE benchmarks 2024",
        ],
        basis="illustrative",
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
