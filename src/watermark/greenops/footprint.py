"""GreenOps footprint assembly — usage → electricity → water derivation (#1076).

STUB (this issue is the scaffold, #1077). The real derivation — lifting the per-source
connector pulls (AWS billing/CCFT, Anthropic usage, GitHub Actions, eGRID) into a
:class:`~watermark.greenops.model.GreenopsReport` via published WUE / carbon-intensity
factor tables — lands in #1083. Until then, :func:`placeholder_report` returns a fully
modeled ``assumption`` report so the page (and the bundle feed, #1084) degrade gracefully
rather than fake a metered figure.

Every value here is ``ProvenancedValue.assume(...)``: an un-wired source is a stated
modeling input, never a ``[verified]`` fact about our own consumption.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.greenops.model import (
    AiByTask,
    ComputeByFunction,
    ElectricitySeries,
    GreenopsPeriod,
    GreenopsReport,
    HeadlineFigure,
    MethodologyItem,
    NamedQuantity,
    WaterDraw,
)
from watermark.hydrology.model import ProvenancedValue

# The rationale stamped on every placeholder figure — so a reader (and the frontend)
# can tell a modeled seed from a wired source at a glance.
_PLACEHOLDER = "modeled placeholder pending the wired source (#1078-#1083)"


def _assume(value: float, unit: str) -> ProvenancedValue:
    return ProvenancedValue.assume(value, unit, _PLACEHOLDER)


def placeholder_report() -> GreenopsReport:
    """A fully modeled (``assumption``) footprint report — the un-wired-source fallback.

    Mirrors the shape and rough magnitudes the sustainability page renders, but every
    figure is a stated placeholder, not a source pull. Replaced source-by-source as the
    connectors (#1078-#1082) and the derivation (#1083) land.
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
