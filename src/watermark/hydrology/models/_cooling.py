"""Cooling-basis + scenario models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, PrivateAttr

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
    # Single, uniform basis (#1153): evaporated share of ``makeup_demand`` (the intake),
    # for *every* archetype — ``makeup_demand`` is the intake in each (the tower's makeup,
    # the once-through withdrawal). So the central consumptive is ``makeup_demand x
    # consumptive_fraction`` universally; ``headline_consumptive()`` returns exactly that,
    # never ``consumptive_low`` (which is the range low, and only *coincides* with the
    # central for the tower/hybrid, not for once_through).
    consumptive_fraction: ProvenancedValue  # evaporated share of makeup_demand (the intake)
    makeup_demand: ProvenancedValue  # MGD, the cooling intake / withdrawal (central)
    consumptive_low: ProvenancedValue  # MGD, low bound of the consumptive range
    # MGD, upper bound of the consumptive range. WARNING for consumers: this is an
    # *independent* estimate on its own basis, NOT the evaporated share of ``makeup_demand``.
    # For ``evaporative_tower`` it is the blowdown-method evaporation (blowdown x (CoC-1)),
    # whose implied intake is the *larger* ``makeup_high`` (blowdown x CoC), not
    # ``makeup_demand`` (the power-method central intake). Pairing ``consumptive_high`` with
    # ``makeup_demand`` as one stream yields a >100% evaporative fraction (Lima: 10 vs 3.93
    # MGD) — divide by the matching intake via ``headline_makeup_high()`` instead (#1170).
    consumptive_high: ProvenancedValue
    # The intake at the upper consumptive bound (MGD). Larger than ``makeup_demand`` wherever the
    # upper bound is driven by a larger intake: the evaporative tower's blowdown-method bound
    # (blowdown x CoC) and once_through's HIGH-IT withdrawal (#1632 — the intake grows with the
    # disclosed MW range). Stays None for archetypes whose upper bound is not a larger intake
    # (dry/off), where ``headline_makeup_high()`` falls back to ``makeup_demand``. This is what
    # ``refill`` reads instead of dividing ``consumptive_high`` by ``consumptive_fraction``
    # (incompatible bases — #1153).
    makeup_high: ProvenancedValue | None = None
    method: str = "power x WUE (central); blowdown x cycles (upper bound)"
    method_disclosed: bool = True  # False = archetype not on record (`unknown`)
    is_bracketed: bool = False  # True = low/high span candidate archetypes, no single estimate
    # hybrid_adiabatic (#1058): the months with evaporative assist (ET0 > precip); the
    # consumptive draw is ~0 outside them. None for the constant-draw archetypes.
    seasonal_months: list[str] | None = None

    # WS-16 (#1616): True when the evaporative upper bound (``consumptive_high``) was limited
    # by the physical WUE ceiling rather than the blowdown method — set by
    # ``_derive_evaporative_tower``. Derivation-time metadata, deliberately NOT a serialized
    # field: it has no cross-tier (bundle/frontend) consumer — the cap's rationale already
    # travels in ``consumptive_high.citation`` — so keeping it off the model spares the
    # published bundle contract a version bump. Consumers that need it (the HYDROLOGY report
    # generator) read a freshly-derived in-process basis; a deserialized basis defaults False
    # (safe degradation — the "capped" annotation is omitted, the value stays correct).
    _consumptive_high_capped: bool = PrivateAttr(default=False)

    @property
    def consumptive_high_capped(self) -> bool:
        """True when ``consumptive_high`` was capped at the physical WUE ceiling (#1616)."""
        return self._consumptive_high_capped

    def headline_consumptive(self) -> ProvenancedValue | None:
        """The single central consumptive draw (MGD), or ``None`` for a bracketed basis.

        The archetype's **central** consumptive: ``makeup_demand x consumptive_fraction``,
        by construction, for every disclosed archetype (#1153). It coincides with
        ``consumptive_low`` for ``hybrid_adiabatic`` (where the range low *is* the
        annual-average power x WUE draw), but for the ``evaporative_tower`` and
        ``once_through`` the central sits **inside** the ``consumptive_low..consumptive_high``
        bracket: the tower low is now the LOW-IT power bound (power-side uncertainty, #1632)
        and the central is the CENTRAL-IT power x WUE; once_through's range combines the
        IT-load AND forced-evaporation-fraction uncertainty (low-IT withdrawal x 1% to high-IT
        withdrawal x 2%, around the central-IT withdrawal x 1.5%). Returning the product keeps
        ``balance`` (this headline) and
        ``scenario``/``supply`` (which both compute ``demand x fraction``) in agreement for
        every archetype.

        For the ``unknown`` archetype (``is_bracketed``) there is **no single headline**:
        callers must present ``consumptive_low``..``consumptive_high`` as a range and lock
        the headline (CLAUDE.md: never a single headline for an undisclosed method). Enforce
        the guard here, in the data tier, not only in the presentation tier.
        """
        if self.is_bracketed:
            return None
        return ProvenancedValue.derived(
            self.makeup_demand.value * self.consumptive_fraction.value,
            "MGD",
            citation=(
                f"central consumptive = {self.makeup_demand.value:g} MGD intake x "
                f"{self.consumptive_fraction.value:g} consumptive fraction "
                f"({self.consumptive_fraction.citation})"
            ),
            confidence=self.consumptive_low.confidence,
        )

    def headline_makeup(self) -> ProvenancedValue | None:
        """The single central makeup / intake (MGD), or ``None`` for a bracketed basis.

        Same honesty guard as :meth:`headline_consumptive`: an ``unknown`` archetype
        carries the evaporative upper-bound *envelope* in ``makeup_demand`` for plumbing
        completeness, but it is not an estimate — callers must not publish it as a headline.
        """
        return None if self.is_bracketed else self.makeup_demand

    def headline_makeup_high(self) -> ProvenancedValue | None:
        """The campus intake at the **upper** consumptive bound (MGD), or ``None`` if bracketed.

        The intake grows at the upper bound for the evaporative tower (the blowdown-method
        ``makeup_high`` = blowdown x CoC) and for once_through (the HIGH-IT withdrawal, #1632 —
        the intake scales with the disclosed MW range). For the archetypes whose upper bound is
        not a larger intake (dry/off) ``makeup_high`` is ``None`` and this falls back to
        ``makeup_demand``. ``refill`` reads this instead of back-calculating
        ``consumptive_high / consumptive_fraction`` — a division that is only valid when the
        bracket varies the method at a constant fraction, and produces a physically
        meaningless number otherwise (#1153).
        """
        if self.is_bracketed:
            return None
        return self.makeup_high or self.makeup_demand


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
    # Per-site seasonal design low flows, surfaced so the frontend reads them from the feed
    # instead of hardcoding Lima's floors (#1633). None when the cited table omits them.
    receiving_summer_30q10: ProvenancedValue | None = None  # growing-season 30Q10 (cfs)
    receiving_1q10: ProvenancedValue | None = None  # absolute driest-week 1Q10 (cfs, often 0)
    receiving_live: ProvenancedValue | None = None  # live receiving-water streamflow, for context
    receiving_water_name: str | None = None  # which receiving water the 7Q10 is for (#900)
    # The campus's own routed industrial discharge (cfs) — the demand node's return flow (Lima's
    # FM-2). Surfaced top-level (#1633) so the dilution model's effluent share is feed-sourced, not
    # a hardcoded constant; None for a scenario whose balance has no discharging demand node.
    campus_routed_discharge: ProvenancedValue | None = None
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
