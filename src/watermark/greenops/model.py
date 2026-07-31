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

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.connectors import CacheOrigin
from watermark.hydrology.model import ProvenancedValue

SourceBasis = Literal["illustrative", "measured"]
"""Whether a usage export describes *real* consumption or is a shaped sample (#1643/F3).

``measured`` — the export came from a live provider pull (or its cache entry): the numbers
are this organization's actual billed usage over the window. ``illustrative`` — the export
was replayed from a committed fixture, so its magnitudes are a **sample**, correct in shape
and internally consistent but not a real footprint.

**It is stamped from the fetch path, never by hand** (:data:`watermark.connectors.CacheOrigin`),
and defaults to ``illustrative``: an artifact that does not say where it came from is not
allowed to read as a real pull. :meth:`GreenopsReport.assert_no_verified`'s sibling discipline —
a report is ``measured`` only when every wired source is, so one sample export keeps the whole
report (and the ``/about/sustainability`` banner) honest.
"""


def basis_for_origin(origin: CacheOrigin) -> SourceBasis:
    """Map the rung that served a connector payload onto the export's :data:`SourceBasis`.

    A committed **fixture** replay is a sample (``illustrative``); a **live** fetch and the
    **cache** entry it wrote are the organization's real usage (``measured``). Keeping this
    one-liner in the model (rather than inline in each connector) is what makes the four
    exports agree on the rule.
    """
    return "illustrative" if origin == "fixture" else "measured"


def combine_basis(bases: Iterable[SourceBasis]) -> SourceBasis:
    """The basis of a report assembled from several exports: ``measured`` only if all are.

    An empty iterable (nothing wired) is ``illustrative`` — a report with no source behind it
    is the least measured thing there is.
    """
    seen = list(bases)
    return "measured" if seen and all(b == "measured" for b in seen) else "illustrative"


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
    """Water attributable to our draw, on the **source** basis, against the internal budget cap.

    **The boundary is tenancy, not ownership** (#1643/F4). We operate no data center: the
    cooling water in ``direct`` is drawn by *our cloud provider's* facility, apportioned to us
    by the kWh we bill. Calling it "our direct on-site cooling" claimed a facility we do not
    have; it is **tenant-attributed facility cooling**, and the field name is kept only for
    feed stability.

    **The two components compose; they are not two bases summed.** ``direct`` is site-basis
    cooling water per kWh of *IT* load; ``indirect`` is the *upstream increment* — water
    consumed generating the electricity delivered to the whole facility (IT x PUE). Site WUE
    plus that increment **is** the source WUE by definition (The Green Grid WP#35), so
    :attr:`total` is a well-formed source-basis figure. What must never be summed is a
    site-basis WUE and an already-source-basis WUE; the benchmark table marks the increment
    ``basis="upstream"`` precisely so the derivation cannot pick a source-basis row here.
    """

    model_config = ConfigDict(extra="forbid")

    unit: str = "gal"
    direct: ProvenancedValue  # tenant-attributed provider facility cooling (site WUE x IT kWh)
    indirect: ProvenancedValue  # upstream generation increment (EWIF x facility kWh)
    budget_cap: ProvenancedValue  # the internal annual budget the gauge reads against

    @property
    def total(self) -> float:
        """Source-basis total: facility cooling + the upstream generation increment."""
        return self.direct.value + self.indirect.value


class CarbonAccount(BaseModel):
    """The report's CO2e figures — the thing eGRID exists to produce (#1643/F1).

    Carbon was previously computed only to build a prose reconciliation sentence, so a
    sustainability page reported every dimension *except* the one its factor table is for.
    This is the first-class account.

    **Dual reporting is the GHG-Protocol Scope-2 convention, and the two are not
    interchangeable.** ``location_based`` prices electricity at the *physical grid's* average
    intensity (our eGRID subregion factor) — what the grid actually emitted to serve us.
    ``market_based`` prices it at the *contractual* intensity the supplier claims (PPAs,
    RECs) — what our provider reports after procurement. A market-based figure is always the
    smaller and is never a substitute for the location-based one; both are published.

    ``derived_location_based`` is *our* model (electricity x the eGRID rate);
    ``provider_location_based`` / ``market_based`` are the provider's own estimate over its
    whole service surface. They differ by scope, which is why ``reconciliation`` states the
    ratio in prose rather than picking a winner.
    """

    model_config = ConfigDict(extra="forbid")

    unit: str = "MTCO2e"
    derived_location_based: ProvenancedValue  # our electricity x eGRID subregion rate
    provider_location_based: ProvenancedValue | None = None  # AWS's own LBM total
    market_based: ProvenancedValue | None = None  # AWS's own MBM total (contractual)
    intensity: ProvenancedValue | None = None  # the eGRID rate applied, lb CO2e/MWh
    subregion: str | None = None  # the eGRID subregion the rate came from, e.g. "SRVC"
    reconciliation: str = ""  # why our model and the provider's estimate differ

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the account, for provenance auditing."""
        maybe = [self.provider_location_based, self.market_based, self.intensity]
        return [self.derived_location_based, *(v for v in maybe if v is not None)]


class EnergyBreakdown(BaseModel):
    """Electricity split by **scope of the workload**, not by function (#1643/F2).

    The vCPU chain models the infrastructure we rent (instances + CI runners). Model
    inference runs on the provider's accelerators and appears on no bill of ours as energy —
    only as tokens. Scoping it out entirely made the electricity, carbon and water headlines
    structurally unable to represent a Claude-driven platform's real footprint, so it is
    folded in here as its own component and reported separately rather than hidden inside
    the infrastructure number.

    Both components carry the same unit as :class:`ElectricitySeries`; ``inference`` is a
    banded assumption (see :class:`InferenceEnergyTable`) and stays visibly low-confidence.
    """

    model_config = ConfigDict(extra="forbid")

    unit: str = "MWh"
    infrastructure: ProvenancedValue  # vCPU-hrs x W/vCPU x PUE (instances + CI runners)
    inference: ProvenancedValue  # tokens x Wh/1k-tokens x PUE, by model class


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
    basis: SourceBasis = "illustrative"  # live pull vs replayed sample (#1643/F3)
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
    basis: SourceBasis = "illustrative"  # live pull vs replayed sample (#1643/F3)
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values = [self.mbm_total, self.lbm_total]
        for m in self.monthly:
            values += [m.mbm_emissions, m.lbm_emissions]
        return values


# --- GitHub Actions/storage billing (#1081) ------------------------------------------------
# The reduced shape of the enhanced-billing usage pull
# (/organizations/{org}/settings/billing/usage): per-day line items with a product, SKU,
# quantity + unit, and net dollars, summed over the window and folded into a small category
# taxonomy (ci_compute = Actions minutes, storage = Git LFS / Packages / shared storage,
# other = everything else). The Actions minutes are the metered CI-compute input the
# footprint derivation (#1083) turns into vCPU-hrs (the runner SKU sets the core count);
# storage GB-hours are the corpus-at-rest input. Every figure is `reference` — a billing
# export, not a metered fact about our own consumption.


class GithubUsageLine(BaseModel):
    """One GitHub billing usage line — a (product, sku, unit_type) summed over the window.

    ``quantity`` carries the API's ``quantity`` metric verbatim; its unit is ``unit_type``
    (Minutes, GigabyteHours, …) and is only meaningful within a single line — never sum
    amounts across lines of differing units.
    """

    model_config = ConfigDict(extra="forbid")

    product: str  # billing product, e.g. "Actions", "Git LFS", "Packages", "Shared Storage"
    sku: str  # billing SKU, e.g. "Actions Linux", "Actions macOS", "Git LFS Data"
    unit_type: str  # "Minutes" | "GigabyteHours" | ...
    category: Literal["ci_compute", "storage", "other"]  # our taxonomy bucket
    quantity: float  # summed usage in unit_type
    cost: ProvenancedValue  # net USD, reference


class GithubRunnerMinutes(BaseModel):
    """Actions minutes for one runner SKU — the CI-compute → vCPU-hrs split hangs off the SKU.

    The runner SKU (Linux / Windows / macOS, and the multi-core variants) sets the core
    count the derivation multiplies minutes by, so the by-runner split is what the footprint
    (#1083) needs; the minutes themselves stay a ``reference`` billing figure.
    """

    model_config = ConfigDict(extra="forbid")

    sku: str  # "Actions Linux", "Actions Windows", "Actions macOS", "Actions Linux 4-core", …
    label: str  # display name (the SKU as billed)
    minutes: ProvenancedValue  # minutes, reference
    cost: ProvenancedValue  # net USD, reference


class GithubStorageProduct(BaseModel):
    """Storage usage for one (product, unit) — Git LFS / Packages / Actions / shared storage.

    Grouped by ``(product, unit_type)`` so incompatible units (GB-hours vs GB) are never
    summed together; the derivation reads the GB-hours lines as the corpus-at-rest input.
    """

    model_config = ConfigDict(extra="forbid")

    product: str  # "Git LFS", "Packages", "Actions", "Shared Storage", …
    label: str  # display name (the product as billed)
    unit_type: str  # "GigabyteHours" | "Gigabytes" | …
    quantity: ProvenancedValue  # in unit_type, reference
    cost: ProvenancedValue  # net USD, reference


class GithubUsageReport(BaseModel):
    """The reduced GitHub enhanced-billing usage pull over the window.

    ``total_minutes`` is every Actions minute (CI compute); ``by_runner`` splits it by runner
    SKU (ranked by minutes, desc). ``storage`` keeps the storage products (ranked by cost,
    desc); ``lines`` keeps the full (product, sku, unit) detail the folds came from. Every
    figure is ``reference`` — a billing export, not a metered fact.
    """

    model_config = ConfigDict(extra="forbid")

    period: GreenopsPeriod
    total_minutes: ProvenancedValue  # Actions minutes across every runner, reference
    total_cost: ProvenancedValue  # net USD across every product, reference
    by_runner: list[GithubRunnerMinutes]  # ranked by minutes desc
    storage: list[GithubStorageProduct]  # ranked by cost desc
    lines: list[GithubUsageLine]  # full detail, ranked by cost desc
    basis: SourceBasis = "illustrative"  # live pull vs replayed sample (#1643/F3)
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values = [self.total_minutes, self.total_cost]
        for r in self.by_runner:
            values += [r.minutes, r.cost]
        for s in self.storage:
            values += [s.quantity, s.cost]
        values += [line.cost for line in self.lines]
        return values


# --- eGRID factors + WUE benchmarks (#1082) ------------------------------------------------
# The reference factor tables the derivation (#1083) applies: EPA eGRID subregion
# carbon-intensity (lb CO2e/MWh) + generation mix, pulled by the egrid connector, and the
# hand-curated WUE (Water Usage Effectiveness) benchmark table (EPRI / Uptime Institute).
# Every figure is `reference` — an authoritative published factor, NEVER a metered fact
# about our own consumption. The derivation multiplies electricity by these; PUE /
# utilization / which-subregion remain stated `assumption`s upstream.


class EgridResourceShare(BaseModel):
    """One fuel's share of an eGRID subregion's generation mix (resource mix, percent)."""

    model_config = ConfigDict(extra="forbid")

    fuel: str  # "coal" | "gas" | "nuclear" | "hydro" | "wind" | "solar" | ...
    label: str  # "Coal", "Natural gas", "Nuclear", ...
    percent: float  # generation share 0-100 (eGRID reports a 0-1 fraction, scaled x100 here)
    renewable: bool  # our declared classification (hydro/biomass/wind/solar/geothermal)


class EgridSubregion(BaseModel):
    """One eGRID subregion's carbon-intensity + generation-mix factors.

    ``co2e_rate`` is the annual CO2-equivalent total output emission rate (SRC2ERTA,
    lb/MWh) — the electricity→CO2e factor; ``renewable_pct`` is eGRID's total-renewables
    share (SRTRPR). ``resource_mix`` keeps the per-fuel breakdown (fuels with a nonzero
    share, ranked desc). Both provenanced figures are ``reference``.
    """

    model_config = ConfigDict(extra="forbid")

    code: str  # eGRID subregion acronym, e.g. "RFCW"
    name: str  # eGRID subregion name, e.g. "RFC West"
    co2e_rate: ProvenancedValue  # lb CO2e/MWh, reference
    renewable_pct: ProvenancedValue  # % of generation from renewables, reference
    resource_mix: list[EgridResourceShare]  # ranked by share desc

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the subregion, for provenance auditing."""
        return [self.co2e_rate, self.renewable_pct]


class EgridFactors(BaseModel):
    """The reduced EPA eGRID subregion factor table (the connector's ``--write`` artifact).

    Every subregion in the published vintage, so the derivation can apportion electricity
    by whichever subregion a workload runs in. Values are read **by field code** (SUBRGN,
    SRNAME, SRC2ERTA, SRTRPR, the SR*PR mix columns) from the workbook's own header row,
    never by index. Every figure is ``reference``.
    """

    model_config = ConfigDict(extra="forbid")

    year: int  # eGRID data year, e.g. 2023
    vintage: str  # release label, e.g. "eGRID2023"
    source_url: str  # the workbook the factors were pulled from
    subregions: list[EgridSubregion]  # ranked by code
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the table, for provenance auditing."""
        return [v for sr in self.subregions for v in sr.all_values()]

    def by_code(self) -> dict[str, EgridSubregion]:
        """Subregions keyed by acronym, for the derivation's lookup by region."""
        return {sr.code: sr for sr in self.subregions}


class WueBenchmark(BaseModel):
    """One Water Usage Effectiveness benchmark — liters of water per kWh, for a facility type.

    ``basis`` is a three-way distinction, and conflating the last two is what let the old
    derivation sum figures its own docstring forbade summing (#1643/F4):

    - ``site`` — facility cooling water only, per kWh of **IT** load.
    - ``upstream`` — the *increment* consumed generating the electricity delivered, per kWh
      of **facility** load. Not a WUE on its own; it is the term you add to a site WUE.
    - ``source`` — an already-complete site + upstream figure.

    ``site`` + ``upstream`` compose into a source-basis total (The Green Grid WP#35). A
    ``site`` and a ``source`` row must never be summed — that double-counts cooling. The
    figure is ``reference`` (a published benchmark), never a metered fact about our cooling.
    """

    model_config = ConfigDict(extra="forbid")

    facility_type: str  # "hyperscale_evaporative" | "closed_loop_airside" | "grid_upstream" | ...
    label: str  # "Hyperscale, evaporative cooling", ...
    wue: ProvenancedValue  # L/kWh, reference
    basis: Literal["site", "upstream", "source"]
    note: str = ""


class WueTable(BaseModel):
    """The committed WUE benchmark table (EPRI / Uptime Institute), tagged ``reference``.

    Hand-curated from published data-center water benchmarks (site WUE) plus the upstream
    water-for-electricity intensity (source WUE) — not a live pull. The derivation (#1083)
    multiplies the electricity figure by the site + source benchmarks for the modeled
    facility type; every figure here stays ``reference``, never ``verified``.
    """

    model_config = ConfigDict(extra="forbid")

    vintage: str  # "EPRI 2024 / Uptime Institute 2023"
    benchmarks: list[WueBenchmark]
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the table, for provenance auditing."""
        return [b.wue for b in self.benchmarks]


# --- LLM inference energy coefficients (#1643/F2) -------------------------------------------
# The factor table that puts model inference into the energy chain. Unlike eGRID this is not a
# pull — no provider publishes a per-token energy figure for its hosted models — so it is a
# hand-curated `reference` table of *published third-party measurements*, each with a dated
# citation and an explicit band. The published per-query figures span an order of magnitude;
# the band is how that spread stays visible instead of hiding behind a point estimate.


class InferenceEnergyBenchmark(BaseModel):
    """Energy per 1,000 tokens for one class of hosted model, as a banded published estimate.

    ``wh_per_1k_tokens`` carries the central estimate **and** a ``low``/``high`` band (#760);
    a consumer that drops the band is overstating what is known. ``basis`` names which tokens
    the coefficient is priced against — decode (output) dominates inference energy, so a
    coefficient measured per *output* token cannot be applied to an input+output total.
    """

    model_config = ConfigDict(extra="forbid")

    model_class: str  # "frontier" | "mid_tier" | "small"
    label: str  # "Frontier (Opus-class)", ...
    wh_per_1k_tokens: ProvenancedValue  # Wh per 1,000 tokens of `basis`, reference, banded
    basis: Literal["output_tokens", "total_tokens"]
    note: str = ""


class InferenceEnergyTable(BaseModel):
    """The committed per-token inference-energy table the derivation applies (#1643/F2).

    Hand-curated from published inference-energy measurements, transcribed with source and
    date. Every figure is ``reference`` — a published third-party estimate, never a metered
    fact about our own inference (no provider exposes one). ``models`` maps a provider model
    id onto a ``model_class``; an id not in the map falls to ``default_class``, so a new model
    is priced conservatively rather than silently dropped from the energy chain.
    """

    model_config = ConfigDict(extra="forbid")

    vintage: str  # "Epoch AI 2025-02 / Jegham et al. 2025-05 / Google 2025-08"
    benchmarks: list[InferenceEnergyBenchmark]
    models: dict[str, str] = {}  # provider model id -> model_class
    default_class: str = "frontier"  # the conservative fallback for an unmapped model id
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the table, for provenance auditing."""
        return [b.wh_per_1k_tokens for b in self.benchmarks]

    def by_class(self) -> dict[str, InferenceEnergyBenchmark]:
        """Benchmarks keyed by model class, for the derivation's lookup."""
        return {b.model_class: b for b in self.benchmarks}

    def benchmark_for(self, model_id: str) -> InferenceEnergyBenchmark | None:
        """The benchmark for a provider model id via ``models`` → ``default_class``.

        Matches the longest declared id prefix, so ``claude-opus-4-8-20260115`` resolves
        through the ``claude-opus-4-8`` entry without the map chasing point releases.
        """
        by_class = self.by_class()
        matches = [k for k in self.models if model_id.startswith(k)]
        if matches:
            key = max(matches, key=len)
            found = by_class.get(self.models[key])
            if found is not None:
                return found
        return by_class.get(self.default_class)


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
    energy: EnergyBreakdown | None = None  # infrastructure vs inference (#1643/F2)
    carbon: CarbonAccount | None = None  # the CO2e account (#1643/F1)
    water: WaterDraw
    methodology: list[MethodologyItem]
    sources: list[str] = []  # display source-line credits ("EPA eGRID … 2025", …)
    # Whether the usage exports behind these figures are a real pull or a shaped sample
    # (#1643/F3). Composed from the source exports by the derivation, never hand-set; an
    # artifact that omits it reads as `illustrative`, which is the honest default.
    basis: SourceBasis = "illustrative"
    note: str = ""

    def all_values(self) -> list[ProvenancedValue]:
        """Every :class:`ProvenancedValue` in the report, for provenance auditing."""
        values: list[ProvenancedValue] = [h.value for h in self.headline]
        values += [f.value for f in self.compute_by_function.functions]
        values += [t.value for t in self.ai_by_task.tasks]
        values += [m.value for m in self.electricity.monthly]
        values += [self.electricity.grid, self.electricity.renewable]
        if self.energy is not None:
            values += [self.energy.infrastructure, self.energy.inference]
        if self.carbon is not None:
            values += self.carbon.all_values()
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
