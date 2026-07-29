"""SCS dimensionless unit hydrograph + convolution.

Turns a design-storm depth + curve number + basin parameters into a runoff
hydrograph:

    D  = min(dt, 0.133 * Tc)       unit-rainfall duration (hr) — see below
    Tp = D/2 + 0.6 * Tc            time to peak (hr)
    Qp = peak_factor * A / Tp      UH peak (cfs per inch of excess; A in sq mi)

The dimensionless SCS unit hydrograph (q/Qp vs t/Tp) is scaled by ``(Tp, Qp)`` and convolved
with the incremental excess rainfall.

**The peak factor sets the shape, not just the height (WS-10 / #1610).** The 484 convention is
not a free multiplier: it is fixed by the standard dimensionless UH shape, through the identity
``volume = Qp * Tp * K`` where ``K`` is the area under the dimensionless curve. One inch of
excess over one square mile is 645.33 cfs-hr, so a peak factor and its shape are locked together
by ``peak_factor = 645.33 / K``. Rescaling a *fixed* shape by a different peak factor therefore
violates mass conservation (a "flat basin" factor of 300 would drop 38% of the runoff volume on
the floor). The dimensionless curve is accordingly built here in its NEH-630 Ch. 16 gamma form,

    q/Qp = (t/Tp)^m * exp(m * (1 - t/Tp)),

with the shape parameter ``m`` solved from the requested peak factor so ``K(m) = 645.33 /
peak_factor`` — m = 3.70 reproduces the standard 484 curve, m = 1.51 the flat-basin 300, m =
5.60 the steep-basin 600. Volume is conserved for every peak factor by construction.

The peak factor resolves, in precedence order: an explicit ``peak_factor=`` argument, then the
active site profile's ``uh_peak_factor``, then the cited Tier-0 constant in
``tier0-parameters.yaml`` (484) — see :mod:`watermark.hydrology.solver.parameters`.

**The unit-rainfall duration is not the output time step.** SCS requires ``D <= 0.133 * Tc``;
pinning ``D`` at the 0.1-hr output step broadens the unit hydrograph (and so understates the
peak) for any catchment with ``Tc < 0.75 hr`` — which is every small paved one. ``D`` is
therefore refined to an integer sub-multiple of the requested ``dt_hr`` that satisfies the rule,
and the returned series lands on that finer grid (``dt_hr`` still divides it exactly, so a
caller's own grid is preserved).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from watermark.config import Settings
from watermark.hydrology.model import Hydrograph
from watermark.hydrology.solver.curve_number import (
    adjust_amc,
    composite_cn,
    excess_rainfall,
    weighted_excess_rainfall,
)
from watermark.hydrology.solver.parameters import peak_factor as _peak_factor
from watermark.hydrology.solver.parameters import round_sig
from watermark.hydrology.solver.rainfall import scs_type_ii_hyetograph

_SQFT_PER_ACRE = 43560.0
_SEC_PER_HR = 3600.0
_FT_PER_MILE = 5280.0
# One inch of runoff over one square mile, in cfs-hr — the constant that ties the SCS peak
# factor to its dimensionless shape (645.33 = 5280^2 / 12 / 3600).
_CFS_HR_PER_IN_SQMI = _FT_PER_MILE**2 / 12.0 / _SEC_PER_HR

# SCS unit-rainfall-duration rule: the excess-rainfall increment convolved with the UH must not
# exceed 0.133 * Tc (NEH-630 Ch. 16 / TR-55), or the unit hydrograph is broadened and the peak
# understated. 0.133 ~ Tp/(2*... ) is the handbook's rounded 2/15 of the time of concentration.
_UNIT_DURATION_FRACTION_OF_TC = 0.133
# Truncation of the gamma tail: enough ordinates to carry this share of the UH volume. The
# ordinates are then renormalised to the exact volume, so the residue is a <0.1% uniform scale.
_UH_VOLUME_CAPTURED = 0.999
_UH_MAX_T_OVER_TP = 100.0  # hard guard for very low peak factors (long, flat recessions)


def _gamma_volume_ratio(m: float) -> float:
    """``K(m)`` — the area under ``(t/Tp)^m * exp(m*(1 - t/Tp))``, integrated over ``t/Tp``."""
    return math.exp(m + math.lgamma(m + 1.0) - (m + 1.0) * math.log(m))


@lru_cache(maxsize=32)
def gamma_shape_for(peak_factor: float) -> float:
    """The gamma UH shape parameter ``m`` whose dimensionless area conserves volume.

    Solves ``645.33 / K(m) = peak_factor`` by bisection. ``K`` is strictly decreasing in ``m``,
    so the root is unique; the bracket spans peak factors of roughly 25 (m -> 0) to 3,000.
    """
    if not math.isfinite(peak_factor) or peak_factor <= 0:
        raise ValueError(f"peak factor must be finite and positive, got {peak_factor!r}")
    lo, hi = 1e-4, 200.0
    if (
        not _CFS_HR_PER_IN_SQMI / _gamma_volume_ratio(lo)
        <= peak_factor
        <= (_CFS_HR_PER_IN_SQMI / _gamma_volume_ratio(hi))
    ):
        raise ValueError(
            f"peak factor {peak_factor} is outside the representable SCS range "
            f"({_CFS_HR_PER_IN_SQMI / _gamma_volume_ratio(lo):.0f}"
            f"-{_CFS_HR_PER_IN_SQMI / _gamma_volume_ratio(hi):.0f})"
        )
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _CFS_HR_PER_IN_SQMI / _gamma_volume_ratio(mid) < peak_factor:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def unit_duration_hr(tc_hr: float, dt_hr: float) -> float:
    """The SCS unit-rainfall duration ``D`` for a catchment, as a sub-multiple of ``dt_hr``.

    ``D <= 0.133 * Tc`` is the SCS rule; ``D`` is additionally snapped to ``dt_hr / k`` for
    integer ``k`` so the requested output grid stays a subset of the computed one (a caller
    routing several catchments on one shared grid is never handed off-grid samples).
    """
    if tc_hr <= 0 or dt_hr <= 0:
        raise ValueError("time of concentration and time step must both be positive")
    required = _UNIT_DURATION_FRACTION_OF_TC * tc_hr
    if required >= dt_hr:
        return dt_hr
    return dt_hr / math.ceil(dt_hr / required)


def _unit_hydrograph(
    area_sqmi: float, tc_hr: float, d_hr: float, *, peak_factor: float
) -> NDArray[np.float64]:
    """UH ordinates (cfs per inch of excess) at ``d_hr`` spacing, for unit duration ``d_hr``.

    The ordinates are renormalised so ``sum(uh) * d_hr`` is exactly the volume of one inch of
    excess over ``area_sqmi`` — discretisation and tail truncation therefore cannot leak runoff
    volume out of the convolution.
    """
    tp = d_hr / 2.0 + 0.6 * tc_hr
    m = gamma_shape_for(peak_factor)
    x_step = d_hr / tp
    n = int(np.ceil(_UH_MAX_T_OVER_TP / x_step)) + 1
    x = np.arange(n, dtype=np.float64) * x_step
    with np.errstate(divide="ignore", invalid="ignore"):
        shape = np.where(
            x > 0.0, np.exp(m * np.log(np.where(x > 0.0, x, 1.0)) + m * (1.0 - x)), 0.0
        )
    # Trim the tail once it carries the target share of the volume (the ordinates decay
    # exponentially, so this is a handful of Tp for any usable peak factor).
    keep = int(np.searchsorted(np.cumsum(shape), _UH_VOLUME_CAPTURED * shape.sum())) + 1
    shape = shape[: max(keep, 2)]
    volume = _CFS_HR_PER_IN_SQMI * area_sqmi  # cfs-hr per inch of excess
    total = float(shape.sum()) * d_hr
    if total <= 0.0:  # pragma: no cover — guarded by the peak-factor bracket above
        raise ValueError("degenerate unit hydrograph (zero volume)")
    return shape * (volume / total)


def simulate_runoff(
    *,
    area_acres: float,
    curve_number: float | None = None,
    tc_hr: float,
    storm_depth_in: float,
    amc: str = "II",
    cn_parts: list[tuple[float, float]] | None = None,
    dt_hr: float = 0.1,
    duration_hr: float = 24.0,
    peak_factor: float | None = None,
    settings: Settings | None = None,
) -> Hydrograph:
    """Run the Tier-0 SCS chain for one footprint and one design storm.

    Provide **exactly one** cover input. ``curve_number`` is one tabulated AMC-II value for a
    homogeneous footprint. ``cn_parts`` is a list of ``(area, cn)`` covers for a *mixed*
    footprint: the excess rainfall is then computed by the TR-55 weighted-runoff method (each
    cover's CN run separately, runoff depths area-weighted; :func:`weighted_excess_rainfall`),
    which does not under-predict runoff the way a single composite CN does once the impervious
    share passes ~30%. Either way the reported ``curve_number`` is the (composite) CN and the
    hydrograph records the ``runoff_method`` used.

    ``amc`` selects the antecedent condition the storm falls on — ``"III"`` (wet, prior rain has
    saturated the ground) raises the effective CN and yields the conservative upper-bound peak,
    ``"I"`` (dry) lowers it. The returned hydrograph records both the effective ``curve_number``
    and the ``amc`` it was run under, so a reader can tell whether a reported peak is
    wet-antecedent.

    ``peak_factor`` (the SCS UH peak factor) defaults to the active site profile's
    ``uh_peak_factor`` and then to the cited ``tier0-parameters.yaml`` value (484); pass it to
    override for a calibrated basin. It sets the dimensionless UH's *shape*, not just its
    height, so volume is conserved at any value (see the module docstring). The reported
    ``peak_cfs`` is stored to 2 significant figures — a Tier-0 screen's inputs are ~2 sig figs,
    so a finer stored peak would read as false confidence — while the full
    ``flows_cfs``/``times_hr`` series keeps its precision (it feeds the volume and any
    downstream routing).

    ``dt_hr`` is the *requested* output step. The SCS unit-rainfall duration rule
    (``D <= 0.133 * Tc``) refines it to ``dt_hr / k`` for a short-Tc catchment, and the returned
    series lands on that finer grid — ``dt_hr`` still divides it exactly. Use
    :func:`unit_duration_hr` to compute the grid a call will land on.
    """
    if (curve_number is None) == (cn_parts is None):
        raise ValueError("simulate_runoff needs exactly one of curve_number or cn_parts")
    pf = peak_factor if peak_factor is not None else _peak_factor(settings=settings)
    area_sqmi = area_acres / 640.0
    # The unit-rainfall duration doubles as the computation step: the excess-rainfall increments
    # convolved with the UH are by definition D-hour increments.
    dt_hr = unit_duration_hr(tc_hr, dt_hr)
    _, cumulative, _ = scs_type_ii_hyetograph(storm_depth_in, dt_hr=dt_hr, duration_hr=duration_hr)
    runoff_method: Literal["composite_cn", "weighted_runoff"]
    if cn_parts is not None:
        # AMC adjusts each cover's own CN before the depths are combined (a per-cover soil
        # property), so the wet/dry bound is applied to the honest weighted-runoff depth.
        adjusted = [(area, adjust_amc(cn, amc)) for area, cn in cn_parts]
        cum_excess = weighted_excess_rainfall(cumulative, adjusted, settings=settings)
        effective_cn = composite_cn(adjusted)  # composite, reported as a summary descriptor
        runoff_method = "weighted_runoff"
    else:
        assert curve_number is not None  # narrowed by the exactly-one guard above
        effective_cn = adjust_amc(curve_number, amc)
        cum_excess = excess_rainfall(cumulative, effective_cn, settings=settings)
        runoff_method = "composite_cn"
    inc_excess = np.diff(cum_excess, prepend=0.0)  # inches per step
    uh = _unit_hydrograph(area_sqmi, tc_hr, dt_hr, peak_factor=pf)

    # Keep the full convolution (len(inc_excess)+len(uh)-1 samples): truncating to the
    # input length would drop the recession tail after the last rainfall increment,
    # so flows.sum() (and thus volume_acft) would understate the reported runoff depth.
    flows = np.convolve(inc_excess, uh)
    times = np.arange(1, len(flows) + 1, dtype=np.float64) * dt_hr
    volume_acft = float(flows.sum() * dt_hr * _SEC_PER_HR / _SQFT_PER_ACRE)
    peak_idx = int(np.argmax(flows))

    return Hydrograph(
        times_hr=[round(t, 4) for t in times.tolist()],
        flows_cfs=[round(q, 4) for q in flows.tolist()],
        peak_cfs=round_sig(float(flows[peak_idx])),  # 2 sig figs — Tier-0 inputs are ~2 sf
        time_to_peak_hr=round(float(times[peak_idx]), 3),
        volume_acft=round(volume_acft, 3),
        runoff_depth_in=round(float(cum_excess[-1]), 4),
        curve_number=round(effective_cn, 1),
        tc_hr=round(tc_hr, 3),
        dt_hr=dt_hr,  # the exact unit duration, UNROUNDED — times_hr is rounded for display
        amc=amc,  # str param, validated against the Hydrograph Literal at construction
        runoff_method=runoff_method,
    )
