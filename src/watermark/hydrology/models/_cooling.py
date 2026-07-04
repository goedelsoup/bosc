"""Cooling-basis + scenario models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.models._core import ProvenancedValue, WaterBalance
from watermark.hydrology.models._lowflow import AssimilativeCheck
from watermark.sites import CoolingModelType


class CoolingBasis(BaseModel):
    """A sourced cooling-water design basis for one cooling archetype.

    Derived by the archetype's spec in :data:`watermark.hydrology.cooling_models.COOLING_MODELS`
    (#1053): ``cooling_model`` records *which world* produced these numbers. Fields
    irrelevant to a given archetype (e.g. ``cycles_of_concentration`` for
    ``closed_loop_dry``) are ``None`` — never faked. For the ``unknown`` archetype the
    low/high pair is a **bracket across candidate archetypes** (``is_bracketed=True``,
    ``method_disclosed=False``), not an estimate.
    """

    model_config = ConfigDict(extra="forbid")

    # Which archetype's math produced this basis. Defaults to the evaporative tower only
    # so committed pre-taxonomy artifacts (all Lima, all evaporative) still parse; every
    # spec sets it explicitly — selection never falls through to this default (#1054).
    cooling_model: CoolingModelType = CoolingModelType.EVAPORATIVE_TOWER
    it_load: ProvenancedValue  # MW (from the air-permit genset count; 0 for `off`)
    wue: ProvenancedValue | None = None  # L/kWh, consumptive water per IT energy (wet modes)
    cycles_of_concentration: ProvenancedValue | None = None  # cooling-tower CoC (tower modes)
    consumptive_fraction: ProvenancedValue  # evaporated share of the intake
    makeup_demand: ProvenancedValue  # MGD, the cooling intake / withdrawal
    consumptive_low: ProvenancedValue  # MGD, low bound
    consumptive_high: ProvenancedValue  # MGD, upper bound
    method: str = "power x WUE (central); blowdown x cycles (upper bound)"
    method_disclosed: bool = True  # False = archetype not on record (`unknown`)
    is_bracketed: bool = False  # True = low/high span candidate archetypes, no single estimate
    # hybrid_adiabatic (#1058): the months with evaporative assist (ET0 > precip); the
    # consumptive draw is ~0 outside them. None for the constant-draw archetypes.
    seasonal_months: list[str] | None = None

    def headline_consumptive(self) -> ProvenancedValue | None:
        """The single central consumptive draw (MGD), or ``None`` for a bracketed basis.

        For a disclosed archetype this is the central (power x WUE) estimate —
        ``consumptive_low``, the low end of the two-method [power, blowdown] bracket, and
        equal to ``makeup_demand x consumptive_fraction`` for the wet modes. For the
        ``unknown`` archetype (``is_bracketed``) there is **no single headline**: callers
        must present ``consumptive_low``..``consumptive_high`` as a range and lock the
        headline (CLAUDE.md: never a single headline for an undisclosed method). Enforce
        the guard here, in the data tier, not only in the presentation tier.
        """
        return None if self.is_bracketed else self.consumptive_low

    def headline_makeup(self) -> ProvenancedValue | None:
        """The single central makeup / intake (MGD), or ``None`` for a bracketed basis.

        Same honesty guard as :meth:`headline_consumptive`: an ``unknown`` archetype
        carries the evaporative upper-bound *envelope* in ``makeup_demand`` for plumbing
        completeness, but it is not an estimate — callers must not publish it as a headline.
        """
        return None if self.is_bracketed else self.makeup_demand


class Scenario(BaseModel):
    """A what-if over the municipal loop, parameterized by the cooling knob.

    The data-center campus draws cooling water from the same Ottawa/Auglaize supply
    the WWTPs discharge to; the evaporated (consumptive) fraction is a net loss to
    the basin. The knobs default to the sourced :class:`CoolingBasis` but remain
    overridable — this is a sensitivity, not a forecast.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    # Which cooling world the knobs assume (#1056). None only for a pre-taxonomy artifact
    # or a bare-override sensitivity with no archetype semantics.
    cooling_model: CoolingModelType | None = None
    cooling_demand: ProvenancedValue  # campus cooling intake (MGD)
    consumptive_fraction: ProvenancedValue  # fraction evaporated (0..1)
    basis: CoolingBasis | None = None  # the sourced derivation, when used


class ScenarioResult(BaseModel):
    """A scenario evaluated against the water balance + cited low flows."""

    model_config = ConfigDict(extra="forbid")

    scenario: Scenario
    # Surfaced from scenario.cooling_model so the bundle feed reads it top-level (#1059).
    cooling_model: CoolingModelType | None = None
    consumptive_loss: ProvenancedValue  # net basin loss (cfs), derived from the knobs
    receiving_7q10: ProvenancedValue | None = None  # per-site receiving-water low flow (#900)
    receiving_live: ProvenancedValue | None = None  # live receiving-water streamflow, for context
    receiving_water_name: str | None = None  # which receiving water the 7Q10 is for (#900)
    balance: WaterBalance
    assimilative: list[AssimilativeCheck]


class ScenarioDiff(BaseModel):
    """Baseline vs buildout: the net new consumptive draw and its low-flow scale."""

    model_config = ConfigDict(extra="forbid")

    baseline: str
    scenario: str
    consumptive_increase_cfs: float
    receiving_water_name: str | None = None  # per-site receiving water (#900)
    receiving_7q10_cfs: float | None = None  # per-site cited/derived 7Q10 (#900)
    multiple_of_7q10: float | None = None


class MonthlyWithdrawal(BaseModel):
    """One month: the cooling draw vs the season-appropriate cited low flow.

    For the constant-draw archetypes the consumptive draw is the same year-round; what
    changes by month is the receiving stream's *available* low flow and whether rainfall
    offsets atmospheric demand. A ``hybrid_adiabatic`` facility's draw is itself
    month-varying (#1058): the warm-season assist rate in ET0 > precip months, ~0
    otherwise. In the growing season the draw is read against the cited summer design
    low flow (30Q10), not the annual 7Q10 — and arrives when reference ET exceeds
    precip, so there is no rainfall buffer.
    """

    model_config = ConfigDict(extra="forbid")

    month: str  # JAN..DEC
    growing_season: bool  # ET0 > precip this month
    et0_mm_day: float
    precip_mm_day: float
    net_atmospheric_mm_day: float  # ET0 - precip (positive = deficit, no rainfall buffer)
    low_flow_cfs: float  # the cited design low flow applied this month
    low_flow_basis: str  # "30Q10 summer" | "7Q10 annual"
    consumptive_cfs: float  # this month's net consumptive draw (month-varying for hybrid)
    multiple: float | None  # consumptive / low_flow (None when the floor is 0)


class SeasonalWithdrawal(BaseModel):
    """The cooling draw screened month-by-month against the Ottawa's seasonal low flow.

    Bridges the climate baseline (reference ET vs precip) and the cooling scenario: the
    annual-7Q10 multiple understates the growing-season pinch, when the river sits at its
    summer design low flow *and* ET exceeds precip. All low-flow figures are cited
    (`data/reference/hydrology/low-flow-7q10.yaml`); no monthly statistic is fabricated.
    """

    model_config = ConfigDict(extra="forbid")

    scenario: str
    # The archetype the draw assumes (#1058); None for a bare-override sensitivity.
    cooling_model: CoolingModelType | None = None
    # The headline rate: the constant draw, or for hybrid the warm-season assist rate.
    consumptive_cfs: float
    months: list[MonthlyWithdrawal]
    growing_season_months: list[str]
    annual_7q10_cfs: float
    summer_30q10_cfs: float | None = None
    one_q10_cfs: float | None = None  # absolute design low flow (often 0)
    annual_multiple: float | None = None  # draw / annual 7Q10
    summer_multiple: float | None = None  # draw / summer 30Q10 — the seasonal headline
