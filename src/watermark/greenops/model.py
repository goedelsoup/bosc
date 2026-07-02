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

from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.model import ProvenancedValue


class GreenopsPeriod(BaseModel):
    """The reporting window a report covers (the usage report is trailing-12-months)."""

    model_config = ConfigDict(extra="forbid")

    label: str  # "Jul 2025-Jun 2026" (display)
    start: str  # ISO year-month, "2025-07"
    end: str  # ISO year-month, "2026-06"
    kind: str = "trailing_12_months"


def period_from_window(starting_at: str, ending_at: str) -> GreenopsPeriod:
    """Build the report window label from RFC 3339 bounds (``ending_at`` exclusive).

    Shared by the per-source connectors (#1078/#1079) so every report labels the same
    window the same way.
    """
    start = datetime.fromisoformat(starting_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ending_at.replace("Z", "+00:00")) - timedelta(days=1)
    return GreenopsPeriod(
        label=f"{start:%b %Y}-{end:%b %Y}",
        start=f"{start:%Y-%m}",
        end=f"{end:%Y-%m}",
    )


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


# --- AWS connector payloads (#1079) --------------------------------------------------------
# The reduced shapes of the two AWS pulls: Cost Explorer (dollars + usage, by service +
# usage type, folded into the platform-function taxonomy) and the Sustainability API
# (the Customer Carbon Footprint Tool's successor — emissions totals used to calibrate
# the derived electricity figure in footprint.py, #1083).


class AwsUsageLine(BaseModel):
    """One Cost Explorer group — a (service, usage type) pair summed over the window.

    ``usage_amount``/``usage_unit`` carry CE's ``UsageQuantity`` metric verbatim; the unit
    varies by usage type (hours, GB-months, requests, …) and is only meaningful within a
    single line — never sum amounts across lines.
    """

    model_config = ConfigDict(extra="forbid")

    service: str  # CE SERVICE dimension value, e.g. "Amazon Simple Storage Service"
    usage_type: str  # CE USAGE_TYPE dimension value, e.g. "TimedStorage-ByteHrs"
    function: str  # the platform-function bucket this service maps to
    cost: ProvenancedValue  # USD, reference
    usage_amount: float
    usage_unit: str


class AwsFunctionCost(BaseModel):
    """Cost Explorer dollars folded into one platform-function bucket.

    The taxonomy (hosting / ingestion / search / ai_inference / storage, plus the ``other``
    catch-all) is our classification of AWS's service dimension — the dollars stay
    ``reference`` (a billing export), the mapping is declared in the connector and every
    unmapped service lands in ``other``, never dropped.
    """

    model_config = ConfigDict(extra="forbid")

    function: str  # "hosting" | "ingestion" | "search" | "ai_inference" | "storage" | "other"
    label: str  # "Hosting", "AI inference", …
    cost: ProvenancedValue  # USD, reference
    services: list[str]  # the CE services folded in, ranked by cost desc


class AwsCostReport(BaseModel):
    """The reduced AWS Cost Explorer pull over the window (``ce:GetCostAndUsage``).

    ``by_function`` is ranked by cost, descending; ``lines`` keeps the full
    (service, usage type) detail the fold came from. Every figure is ``reference``.
    """

    model_config = ConfigDict(extra="forbid")

    period: GreenopsPeriod
    total_cost: ProvenancedValue  # USD across every service
    by_function: list[AwsFunctionCost]
    lines: list[AwsUsageLine]
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values = [self.total_cost]
        values += [f.cost for f in self.by_function]
        values += [line.cost for line in self.lines]
        return values


class AwsCarbonMonth(BaseModel):
    """One month of AWS-estimated emissions (both GHG-Protocol methods), in MTCO2e."""

    model_config = ConfigDict(extra="forbid")

    month: str  # ISO year-month, "2025-07"
    mbm_emissions: ProvenancedValue  # market-based method, MTCO2e
    lbm_emissions: ProvenancedValue  # location-based method, MTCO2e


class AwsCarbonReport(BaseModel):
    """The reduced AWS Sustainability pull (``sustainability:GetEstimatedCarbonEmissions``).

    The Customer Carbon Footprint Tool's successor (CCFT retired 2026-06-30). AWS reports
    emissions only — **no electricity/kWh figure exists**, so the derived electricity
    number is calibrated against ``lbm_total`` via grid intensity in ``footprint.py``
    (#1082/#1083), never read from here. Emissions data lags roughly three months behind
    the calendar; ``monthly`` simply ends at AWS's latest published month.
    """

    model_config = ConfigDict(extra="forbid")

    period: GreenopsPeriod
    mbm_total: ProvenancedValue  # market-based method total, MTCO2e
    lbm_total: ProvenancedValue  # location-based method total, MTCO2e
    monthly: list[AwsCarbonMonth]
    model_version: str  # AWS's emissions-model version, e.g. "v3.0.0"
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values = [self.mbm_total, self.lbm_total]
        for m in self.monthly:
            values += [m.mbm_emissions, m.lbm_emissions]
        return values


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
