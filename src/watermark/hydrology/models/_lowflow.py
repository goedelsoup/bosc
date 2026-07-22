"""Assimilative-dilution + low-flow-frequency models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.models._core import ProvenancedValue

Flag = Literal["ok", "tight", "violation"]


class AssimilativeCheck(BaseModel):
    """Low-flow dilution of one discharge into its receiving water.

    Two dilution ratios are carried, and the honest picture is *both* (WS-15, #1615):

    * ``dilution_ratio`` (the **conservative default**) is ``design_low_flow / discharge``
      — parts of the receiving stream's cited natural low flow per part of effluent. It
      credits **no** upstream effluent; ``flag`` bands it.
    * ``effluent_credited_ratio`` is ``(design_low_flow + upstream_returns) / discharge``,
      crediting the permitted effluent **already in the reach** into the denominator, with
      ``effluent_credited_flag`` its band. It is ``None`` when there is no co-reach effluent
      to credit (the discharger is alone on its stream), so a tributary-only plant is
      untouched and stays at the conservative default.

    ``upstream_returns`` is that credited term: the summed **permitted design discharge of the
    other WWTP(s) sharing this receiving water** — the loop's own thesis is that the Ottawa
    *is* effluent at design low flow (93-98%), so a plant discharging into it is diluted by
    that standing effluent mass, not by the ~0.2 cfs of natural water. It is a screening
    co-reach sum (``derived``), not a longitudinal-position-resolved routing term; the routed
    accumulation lives in :class:`RoutedNetwork`. Both bands are heuristics, **not** permit
    determinations.
    """

    model_config = ConfigDict(extra="forbid")

    receiving_water: str
    discharger: str
    design_low_flow: ProvenancedValue  # the 7Q10 (cited)
    discharge: ProvenancedValue
    # Permitted effluent already in the reach (Σ other WWTPs on this receiving water), credited
    # into `effluent_credited_ratio`. None when the discharger is alone on its stream (WS-15).
    upstream_returns: ProvenancedValue | None = None
    dilution_ratio: float  # conservative: cited 7Q10 / discharge (no effluent credit)
    flag: Flag  # band on `dilution_ratio`
    # Effluent-credited: (7Q10 + upstream_returns) / discharge; None when nothing to credit.
    effluent_credited_ratio: float | None = None
    effluent_credited_flag: Flag | None = None
    detail: str


# Screening thresholds on the dilution ratio (stream low-flow : effluent).
# Below 1, the effluent dominates the stream at design low flow — effectively
# undiluted. These are coarse screening bands, not regulatory mixing-zone rules.
# The cited source of truth is `data/reference/hydrology/tier0-parameters.yaml`
# (`dilution.violation_ratio` / `dilution.tight_ratio`); `assimilative.dilution_flag`
# reads it (overridable via `bands=`), and a coupling test pins these constants to it.
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
