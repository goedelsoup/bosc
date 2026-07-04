"""Assimilative-dilution + low-flow-frequency models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.models._core import ProvenancedValue

Flag = Literal["ok", "tight", "violation"]


class AssimilativeCheck(BaseModel):
    """Low-flow dilution of one discharge into its receiving water.

    The dilution ratio is ``design_low_flow / discharge`` — parts of receiving-water low
    flow per part of effluent. ``upstream_returns`` is a **reserved** field for crediting
    an upstream WWTP's effluent return to the low-flow denominator; it is not yet computed,
    is always ``None`` today, and the ratio does **not** credit it. A screening heuristic
    flags the result; it is **not** a permit determination.
    """

    model_config = ConfigDict(extra="forbid")

    receiving_water: str
    discharger: str
    design_low_flow: ProvenancedValue  # the 7Q10 (cited)
    discharge: ProvenancedValue
    # Reserved: not yet credited into `dilution_ratio` (see the hydrology review). Kept on
    # the model (defaulted None) so the committed bundle contract stays stable.
    upstream_returns: ProvenancedValue | None = None
    dilution_ratio: float
    flag: Flag
    detail: str


# Screening thresholds on the dilution ratio (stream low-flow : effluent).
# Below 1, the effluent dominates the stream at design low flow — effectively
# undiluted. These are coarse screening bands, not regulatory mixing-zone rules.
DILUTION_VIOLATION = 1.0
DILUTION_TIGHT = 10.0


class AnnualMinimum(BaseModel):
    """One climatic year's minimum n-day average discharge at a gage.

    The climatic year (Apr 1 to Mar 31) brackets the late-summer low-flow season
    so a single drought is never split across two years. ``complete`` records
    whether the year carried enough daily values to enter the frequency fit — the
    exclusion is auditable, never silent.
    """

    model_config = ConfigDict(extra="forbid")

    climatic_year: int  # the Apr 1 start year
    nday: int
    min_cfs: float
    valid_days: int
    complete: bool


class LowFlowStatistic(BaseModel):
    """A computed n-day, T-year low-flow frequency statistic (e.g. the 7Q10).

    Two independent estimates bracket the value: a parametric **log-Pearson III**
    fit (the USGS-standard distribution, by method of moments on the log of the
    annual minima, with a conditional-probability adjustment when some years run
    dry) and a non-parametric **Weibull** plotting-position interpolation. Both are
    ``derived`` — a screening corroboration of the cited regulatory figure, never a
    substitute for it (see :mod:`watermark.hydrology.lowflow`).
    """

    model_config = ConfigDict(extra="forbid")

    label: str  # "7Q10"
    nday: int
    return_period_yr: int  # 10
    nonexceedance_prob: float  # 0.10 (= 1 / return_period_yr)
    n_years: int  # complete climatic years in the fit
    lp3_cfs: ProvenancedValue  # derived, log-Pearson III
    weibull_cfs: ProvenancedValue  # derived, empirical plotting position
    log_skew: float  # skew of log10(annual minima), the LP3 shape
    zero_fraction: float  # fraction of minima that are zero (dry years)
    cited_cfs: ProvenancedValue | None = None  # the cited regulatory value, if any
    cited_basis: str | None = None  # what the cited value represents (e.g. "summer 30Q10")
    corroborates: bool | None = None  # LP3 within the screening band of the cited value


class LowFlowFrequency(BaseModel):
    """Independent low-flow frequency analysis of one USGS gage's daily record.

    Reproduces the design low flows (1Q10 / 7Q10 / 30Q10) from the raw USGS daily
    discharge — the statistic Ohio EPA cites from a fact sheet but never shows its
    work for. A second, self-standing line of evidence under the assimilative
    screen: when the computed 7Q10 lands on the cited value, the "effluent is
    undiluted at design low flow" finding no longer rests on a single number.
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    site_name: str
    receiving_water: str | None = None
    period_start: str  # ISO date of the first daily value used
    period_end: str
    record_days: int  # valid daily values in the record
    complete_years: int  # climatic years that entered the fit
    completeness_threshold_days: int
    statistics: list[LowFlowStatistic]
    annual_minima: list[AnnualMinimum]  # the auditable per-year series (1/7/30-day)
    method: str
    note: str = ""

    def stat(self, label: str) -> LowFlowStatistic | None:
        return next((s for s in self.statistics if s.label == label), None)

    def minima_for(self, nday: int) -> list[AnnualMinimum]:
        return [m for m in self.annual_minima if m.nday == nday]
