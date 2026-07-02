"""Typed models for Watermark's own compute footprint — the GreenOps report (#1076).

The self-reported footprint of running the platform, published to `/about/sustainability`
at the same evidence standard as the sites we track: every figure carries where it came
from via :class:`watermark.hydrology.model.ProvenancedValue` (the project-wide provenance
primitive), exactly like the hydrology and economics numbers. ``extra="forbid"``: these
are assembled by our own code.

**Discipline (important):** a footprint figure is *never* a metered fact about our own
consumption — a billing export is a ``reference``, a WUE/eGRID conversion is ``derived``,
and an un-wired source degrades to a modeled ``assumption``. Nothing here is
``connector``-``verified``; :func:`assert_no_verified` enforces that. The frontend reads
this shape as a global bundle feed (contract 1.9.0); the connectors that replace the
assumptions land in #1078-#1083.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.model import ProvenancedValue


class GreenopsPeriod(BaseModel):
    """The reporting window a report covers (the usage report is trailing-12-months)."""

    model_config = ConfigDict(extra="forbid")

    label: str  # "Jul 2025-Jun 2026" (display)
    start: str  # ISO year-month, "2025-07"
    end: str  # ISO year-month, "2026-06"
    kind: str = "trailing_12_months"


class HeadlineFigure(BaseModel):
    """One of the four report headline stats (compute / AI inferences / electricity / water).

    ``value`` carries the number, its native unit, and its provenance; ``sub`` and
    ``source_label`` are the display strings the FigureStat card renders (the split of
    what makes up the figure, and the human name of where it came from).
    """

    model_config = ConfigDict(extra="forbid")

    key: str  # "compute" | "ai_inferences" | "electricity" | "water"
    label: str  # "Compute"
    value: ProvenancedValue  # number + unit + source_kind
    sub: str  # "hosting, ingestion, search, AI"
    source_label: str  # "cloud billing export" (display; not the ProvenancedValue citation)


class NamedQuantity(BaseModel):
    """A labeled provenanced quantity — one bar / slice / month in a breakdown series."""

    model_config = ConfigDict(extra="forbid")

    label: str  # "Hosting", "Structured extraction", "Jul"
    value: ProvenancedValue


class ComputeByFunction(BaseModel):
    """Compute split by platform function (the ranked-bar panel), in vCPU-hours."""

    model_config = ConfigDict(extra="forbid")

    unit: str = "vCPU-hrs"
    functions: list[NamedQuantity]  # ranked desc by the builder


class AiByTask(BaseModel):
    """AI inference volume split by task type (the donut panel), in calls."""

    model_config = ConfigDict(extra="forbid")

    unit: str = "calls"
    tasks: list[NamedQuantity]


class ElectricitySeries(BaseModel):
    """Monthly electricity draw (the line panel) plus the grid/renewable source mix."""

    model_config = ConfigDict(extra="forbid")

    unit: str = "MWh"
    monthly: list[NamedQuantity]  # one point per month in the period
    grid: ProvenancedValue  # regional-mix grid draw over the period
    renewable: ProvenancedValue  # matched renewable (RECs) over the period


class WaterDraw(BaseModel):
    """Water draw split direct/indirect (the stacked bar) against the internal budget cap."""

    model_config = ConfigDict(extra="forbid")

    unit: str = "gal"
    direct: ProvenancedValue  # on-site cooling
    indirect: ProvenancedValue  # grid generation upstream
    budget_cap: ProvenancedValue  # the internal annual budget the gauge reads against

    @property
    def total(self) -> float:
        return self.direct.value + self.indirect.value


class MethodologyItem(BaseModel):
    """One derivation note (title + prose) under the methodology block."""

    model_config = ConfigDict(extra="forbid")

    title: str  # "Compute", "Electricity", "Water"
    body: str


class GreenopsReport(BaseModel):
    """The assembled compute-footprint report the sustainability page reads.

    Every numeric is a :class:`ProvenancedValue` carrying its ``source_kind``. A source
    that is not yet wired ships a modeled ``assumption`` placeholder (see
    :func:`watermark.greenops.footprint.placeholder_report`) so the page degrades
    gracefully rather than 500-ing or faking a ``connector`` value.
    """

    model_config = ConfigDict(extra="forbid")

    period: GreenopsPeriod
    headline: list[HeadlineFigure]
    compute_by_function: ComputeByFunction
    ai_by_task: AiByTask
    electricity: ElectricitySeries
    water: WaterDraw
    methodology: list[MethodologyItem]
    sources: list[str] = []  # display source-line credits ("EPA eGRID … 2025", …)
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values: list[ProvenancedValue] = [h.value for h in self.headline]
        values += [f.value for f in self.compute_by_function.functions]
        values += [t.value for t in self.ai_by_task.tasks]
        values += [m.value for m in self.electricity.monthly]
        values += [self.electricity.grid, self.electricity.renewable]
        values += [self.water.direct, self.water.indirect, self.water.budget_cap]
        return values

    def assert_no_verified(self) -> None:
        """Guard the core discipline: no footprint figure may claim to be ``[verified]``.

        Our own consumption is modeled, not metered — a billing export is ``reference``,
        a factor conversion is ``derived``, an un-wired source is ``assumption``. A
        ``document``/``connector`` (``verified``) source on any figure is a bug.
        """
        bad = [v for v in self.all_values() if v.verified]
        if bad:
            kinds = sorted({v.source for v in bad})
            raise ValueError(
                f"GreenopsReport carries {len(bad)} verified figure(s) ({kinds}); the platform's "
                "own footprint is modeled, not metered — use reference/derived/assumption only."
            )
