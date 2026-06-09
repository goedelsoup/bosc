"""Independent low-flow frequency analysis from the USGS daily-discharge record.

:mod:`bosc.hydrology.lowflow` carries the **cited** regulatory 7Q10 — read off an
Ohio EPA NPDES fact sheet, ``source=document``. This module does the thing the fact
sheet asserts but never shows: it *computes* the design low flows (1Q10 / 7Q10 /
30Q10) from the raw USGS daily-mean discharge and reports how close the computation
lands to the cited value. The computed figures are ``derived`` — a screening
corroboration, **never** a substitute for the cited statistic (root CLAUDE.md: "the
cited regulatory 7Q10 lives in lowflow.py; the NWIS observed minimum only
sanity-checks it").

Method (the standard low-flow frequency recipe, pure-numpy-free so it stays
auditable):

1. **Annual n-day minima.** Group the daily record by *climatic year* (Apr 1 to
   Mar 31, so a late-summer drought is never split) and take each year's minimum
   n-day trailing-average flow. Years without enough daily values are flagged
   ``complete=False`` and excluded from the fit — the exclusion is recorded, never
   silent.
2. **Log-Pearson Type III** (the USGS-standard distribution) by method of moments
   on ``log10`` of the annual minima, with the Wilson-Hilferty frequency factor.
   The 10-year low flow is the value at non-exceedance probability ``1/10 = 0.10``.
3. **Conditional-probability adjustment** for dry years: if a fraction ``p0`` of
   the minima are zero, the quantile below ``p0`` is simply ``0``; above it the fit
   runs on the non-zero minima at the conditional probability ``(p - p0)/(1 - p0)``.
4. A non-parametric **Weibull** plotting-position interpolation brackets the LP3
   estimate as a distribution-free check.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology import lowflow
from bosc.hydrology.connectors.nwis import DailyDischargeSeries, fetch_daily_discharge
from bosc.hydrology.model import (
    AnnualMinimum,
    HydroFinding,
    LowFlowFrequency,
    LowFlowStatistic,
    ProvenancedValue,
)
from bosc.logging import get_logger

log = get_logger(__name__)

_FILENAME = "low-flow-frequency.yaml"
# The n-day averaging windows and the return period of the design low flow.
DEFAULT_NDAYS = (1, 7, 30)
DEFAULT_RETURN_PERIOD_YR = 10
# A climatic year needs at least this many daily values to enter the fit.
DEFAULT_COMPLETENESS_DAYS = 350
# Screening band: the computed LP3 "corroborates" the cited value within a factor
# of two — genuinely strong agreement for a statistic with wide confidence bounds.
_CORROB_LOW = 0.5
_CORROB_HIGH = 2.0

_METHOD = (
    "climatic-year (Apr-Mar) annual n-day minima; log-Pearson III "
    "(method of moments, Wilson-Hilferty frequency factor) bracketed by Weibull "
    "plotting position; conditional-probability adjustment for zero-flow years"
)


# --------------------------------------------------------------------------- math


def _probit(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation, ~1e-9 abs).

    Avoids a scipy dependency; accurate enough for a screening frequency factor.
    """
    if not 0.0 < p < 1.0:
        raise ValueError(f"probit requires 0 < p < 1, got {p}")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    p_low = 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= 1.0 - p_low:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def _lp3_low_quantile(minima: list[float], p: float) -> tuple[float, float, float]:
    """Log-Pearson III low-flow quantile at non-exceedance probability ``p``.

    Returns ``(quantile_cfs, log_skew, zero_fraction)``. Handles dry years via the
    conditional-probability adjustment: the quantile in the zero-flow mass is 0.
    """
    n = len(minima)
    if n == 0:
        return math.nan, math.nan, math.nan
    nonzero = [m for m in minima if m > 0.0]
    zero_fraction = (n - len(nonzero)) / n
    if p <= zero_fraction:
        # The p-quantile falls inside the zero-flow probability mass.
        return 0.0, math.nan, zero_fraction
    p_cond = (p - zero_fraction) / (1.0 - zero_fraction)
    x = [math.log10(m) for m in nonzero]
    k = len(x)
    mean = sum(x) / k
    var = sum((xi - mean) ** 2 for xi in x) / (k - 1) if k > 1 else 0.0
    sd = math.sqrt(var)
    if k > 2 and sd > 0.0:
        skew = (k / ((k - 1) * (k - 2))) * sum((xi - mean) ** 3 for xi in x) / sd**3
    else:
        skew = 0.0
    z = _probit(p_cond)
    if abs(skew) < 1e-6:
        factor = z
    else:
        # Wilson-Hilferty approximation of the Pearson III frequency factor.
        factor = (2.0 / skew) * ((1.0 + skew * z / 6.0 - skew * skew / 36.0) ** 3 - 1.0)
    return 10.0 ** (mean + factor * sd), skew, zero_fraction


def _weibull_low_quantile(minima: list[float], p: float) -> float:
    """Weibull plotting-position low-flow quantile at non-exceedance probability ``p``."""
    s = sorted(minima)
    n = len(s)
    if n == 0:
        return math.nan
    positions = [(i + 1) / (n + 1) for i in range(n)]
    if p <= positions[0]:
        return s[0]
    if p >= positions[-1]:
        return s[-1]
    for i in range(n - 1):
        if positions[i] <= p <= positions[i + 1]:
            frac = (p - positions[i]) / (positions[i + 1] - positions[i])
            return s[i] + frac * (s[i + 1] - s[i])
    return s[-1]


def low_flow_quantiles(
    minima: list[float], *, nonexceedance_prob: float
) -> tuple[float, float, float, float]:
    """``(lp3, weibull, log_skew, zero_fraction)`` for a set of annual minima.

    The public seam the report/tests use to recompute a quantile from the committed
    per-year minima without re-fetching the gage record.
    """
    lp3, skew, zero_fraction = _lp3_low_quantile(minima, nonexceedance_prob)
    weibull = _weibull_low_quantile(minima, nonexceedance_prob)
    return lp3, weibull, skew, zero_fraction


# ----------------------------------------------------------------------- minima


def _climatic_year(d: date) -> int:
    """Climatic year starting Apr 1: Apr-Dec map to ``year``, Jan-Mar to ``year-1``."""
    return d.year if d.month >= 4 else d.year - 1


def annual_nday_minima(
    series: DailyDischargeSeries,
    nday: int,
    *,
    completeness_days: int = DEFAULT_COMPLETENESS_DAYS,
) -> list[AnnualMinimum]:
    """Per-climatic-year minimum n-day trailing-average discharge.

    A window counts only when it spans ``nday`` *consecutive* calendar days (no
    internal gap). ``complete`` marks years carrying ``>= completeness_days`` daily
    values; only those should enter a frequency fit.
    """
    by_date: dict[date, float] = {date.fromisoformat(d): v for d, v in series.points()}
    days = sorted(by_date)
    valid_by_year: dict[int, int] = defaultdict(int)
    for d in days:
        valid_by_year[_climatic_year(d)] += 1

    min_by_year: dict[int, float] = {}
    window: list[date] = []
    for d in days:
        window.append(d)
        window = [w for w in window if (d - w).days < nday]
        if len(window) == nday and (window[-1] - window[0]).days == nday - 1:
            mean = sum(by_date[w] for w in window) / nday
            cy = _climatic_year(d)
            min_by_year[cy] = min(min_by_year.get(cy, math.inf), mean)

    out = [
        AnnualMinimum(
            climatic_year=cy,
            nday=nday,
            min_cfs=round(value, 4),
            valid_days=valid_by_year[cy],
            complete=valid_by_year[cy] >= completeness_days,
        )
        for cy, value in sorted(min_by_year.items())
    ]
    return out


# ------------------------------------------------------------------ orchestration


def _cited_for(
    nday: int, receiving_water: str | None, *, settings: Settings
) -> tuple[ProvenancedValue | None, str | None]:
    """The cited regulatory value (and its basis) to corroborate an ``nday`` stat against."""
    if receiving_water is None:
        return None, None
    if nday == 7:
        return lowflow.low_flow_for(receiving_water, settings=settings), "7Q10"
    ctx = lowflow.low_flow_context(receiving_water, settings=settings)
    if nday == 1 and ctx.get("one_q10_cfs") is not None:
        return (
            ProvenancedValue.from_document(
                float(ctx["one_q10_cfs"]), "cfs", f"cited 1Q10 for {receiving_water}"
            ),
            "1Q10",
        )
    if nday == 30 and ctx.get("thirty_q10_summer_cfs") is not None:
        return (
            ProvenancedValue.from_document(
                float(ctx["thirty_q10_summer_cfs"]),
                "cfs",
                f"cited summer 30Q10 for {receiving_water}",
            ),
            "summer 30Q10",
        )
    return None, None


def _corroborates(computed: float, cited: ProvenancedValue | None) -> bool | None:
    """Does the computed LP3 land within the screening band of the cited value?"""
    if cited is None or math.isnan(computed):
        return None
    if cited.value == 0.0:
        return computed == 0.0
    ratio = computed / cited.value
    return _CORROB_LOW <= ratio <= _CORROB_HIGH


def _statistic(
    minima: list[AnnualMinimum],
    *,
    nday: int,
    return_period_yr: int,
    site_no: str,
    receiving_water: str | None,
    period: str,
    settings: Settings,
) -> LowFlowStatistic:
    complete = [m.min_cfs for m in minima if m.complete]
    p = 1.0 / return_period_yr
    lp3, weibull, skew, zero_fraction = low_flow_quantiles(complete, nonexceedance_prob=p)
    label = f"{nday}Q{return_period_yr}"
    cited, basis = _cited_for(nday, receiving_water, settings=settings)
    return LowFlowStatistic(
        label=label,
        nday=nday,
        return_period_yr=return_period_yr,
        nonexceedance_prob=p,
        n_years=len(complete),
        lp3_cfs=ProvenancedValue.derived(
            round(lp3, 4),
            "cfs",
            citation=f"log-Pearson III on {len(complete)} climatic-year {nday}-day minima, NWIS {site_no} {period}",
        ),
        weibull_cfs=ProvenancedValue.derived(
            round(weibull, 4),
            "cfs",
            citation=f"Weibull plotting position, {len(complete)} climatic-year {nday}-day minima, NWIS {site_no}",
        ),
        log_skew=round(skew, 4) if not math.isnan(skew) else 0.0,
        zero_fraction=round(zero_fraction, 4) if not math.isnan(zero_fraction) else 0.0,
        cited_cfs=cited,
        cited_basis=basis,
        corroborates=_corroborates(lp3, cited),
    )


def compute_low_flow_frequency(
    *,
    site_no: str,
    receiving_water: str | None = None,
    start_date: str = "1980-01-01",
    end_date: str = "2024-12-31",
    ndays: tuple[int, ...] = DEFAULT_NDAYS,
    return_period_yr: int = DEFAULT_RETURN_PERIOD_YR,
    completeness_days: int = DEFAULT_COMPLETENESS_DAYS,
    settings: Settings | None = None,
) -> LowFlowFrequency:
    """Compute the 1Q10 / 7Q10 / 30Q10 for one gage from its daily-discharge record."""
    settings = settings or get_settings()
    series = fetch_daily_discharge(
        site_no, start_date=start_date, end_date=end_date, settings=settings
    )
    if not series.dates:
        raise ValueError(f"NWIS {site_no}: empty daily record for {start_date}..{end_date}")

    period = f"{series.dates[0]}—{series.dates[-1]}"
    all_minima: list[AnnualMinimum] = []
    statistics: list[LowFlowStatistic] = []
    complete_years = 0
    for nday in ndays:
        minima = annual_nday_minima(series, nday, completeness_days=completeness_days)
        all_minima.extend(minima)
        complete_years = max(complete_years, sum(1 for m in minima if m.complete))
        statistics.append(
            _statistic(
                minima,
                nday=nday,
                return_period_yr=return_period_yr,
                site_no=site_no,
                receiving_water=receiving_water,
                period=period,
                settings=settings,
            )
        )

    lff = LowFlowFrequency(
        site_no=series.site_no,
        site_name=series.name,
        receiving_water=receiving_water,
        period_start=series.dates[0],
        period_end=series.dates[-1],
        record_days=len(series),
        complete_years=complete_years,
        completeness_threshold_days=completeness_days,
        statistics=statistics,
        annual_minima=all_minima,
        method=_METHOD,
    )
    seven_q10 = lff.stat(f"7Q{return_period_yr}")
    log.info(
        "hydro.lowflow_frequency",
        site=site_no,
        complete_years=complete_years,
        seven_q10_lp3=seven_q10.lp3_cfs.value if seven_q10 is not None else None,
    )
    return lff


# --------------------------------------------------------------------- findings


def low_flow_frequency_findings(lff: LowFlowFrequency) -> list[HydroFinding]:
    """One finding per cited statistic: does the computed value corroborate it?"""
    findings: list[HydroFinding] = []
    for s in lff.statistics:
        if s.cited_cfs is None:
            continue
        ok = bool(s.corroborates)
        findings.append(
            HydroFinding(
                subject=f"{lff.site_name} {s.label}",
                check="lowflow-corroboration",
                ok=ok,
                detail=(
                    f"computed {s.lp3_cfs.value:g} cfs (LP3) / {s.weibull_cfs.value:g} (Weibull) "
                    f"vs cited {s.cited_basis} {s.cited_cfs.value:g} cfs over "
                    f"{s.n_years} climatic years — "
                    f"{'corroborates' if ok else 'diverges from'} the cited value"
                ),
            )
        )
    return findings


# ------------------------------------------------------------------- persistence


def _reference_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / _FILENAME


def write_low_flow_frequency(lff: LowFlowFrequency, *, settings: Settings | None = None) -> Path:
    """Persist a low-flow frequency analysis to the committed reference YAML."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"Independent low-flow frequency analysis — {lff.site_name}",
            "source": f"USGS NWIS daily-values service, gage {lff.site_no}",
            "method": lff.method,
            "discipline": (
                "Computed (derived) corroboration of the cited regulatory 7Q10 in "
                "low-flow-7q10.yaml — not a substitute for the cited statistic."
            ),
        },
        "frequency": lff.model_dump(mode="json"),
    }
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    return path


def load_low_flow_frequency(*, settings: Settings | None = None) -> LowFlowFrequency | None:
    """Load the committed low-flow frequency analysis, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = data.get("frequency")
    if not block:
        return None
    return LowFlowFrequency.model_validate(block)
