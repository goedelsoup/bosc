"""SCS dimensionless unit hydrograph + convolution.

Turns a design-storm depth + curve number + basin parameters into a runoff
hydrograph:

    Tp = dt/2 + 0.6 * Tc           time to peak (hr)
    Qp = peak_factor * A / Tp      UH peak (cfs per inch of excess; A in sq mi)

The dimensionless SCS unit hydrograph (q/Qp vs t/Tp) is scaled by ``(Tp, Qp)`` and
convolved with the incremental excess rainfall. The peak factor (484 by convention) makes
the hydrograph conserve volume (total flow volume == excess depth over the area). It is the
cited Tier-0 constant in ``tier0-parameters.yaml``
(:mod:`watermark.hydrology.solver.parameters`), overridable per call via ``peak_factor=``.
"""

from __future__ import annotations

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

# Dimensionless SCS unit hydrograph: t/Tp -> q/Qp (NEH-630 Table 16-1, abridged).
_T_OVER_TP: tuple[float, ...] = (
    0.0,
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.4,
    1.5,
    1.6,
    1.8,
    2.0,
    2.2,
    2.4,
    2.6,
    2.8,
    3.0,
    3.5,
    4.0,
    4.5,
    5.0,
)
_Q_OVER_QP: tuple[float, ...] = (
    0.0,
    0.015,
    0.075,
    0.16,
    0.28,
    0.43,
    0.60,
    0.77,
    0.89,
    0.97,
    1.0,
    0.98,
    0.92,
    0.84,
    0.75,
    0.66,
    0.56,
    0.42,
    0.32,
    0.24,
    0.18,
    0.13,
    0.098,
    0.075,
    0.036,
    0.018,
    0.009,
    0.004,
)

_SQFT_PER_ACRE = 43560.0
_SEC_PER_HR = 3600.0


def _unit_hydrograph(
    area_sqmi: float, tc_hr: float, dt_hr: float, *, peak_factor: float
) -> NDArray[np.float64]:
    """UH ordinates (cfs per inch of excess) at ``dt_hr`` spacing."""
    tp = dt_hr / 2.0 + 0.6 * tc_hr
    qp = peak_factor * area_sqmi / tp
    n = int(np.ceil(5.0 * tp / dt_hr)) + 1  # the dimensionless curve tails out by t/Tp=5
    t = np.arange(n, dtype=np.float64) * dt_hr
    return qp * np.interp(t / tp, _T_OVER_TP, _Q_OVER_QP)


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

    ``peak_factor`` (the SCS UH peak factor) defaults to the cited ``tier0-parameters.yaml``
    value (484); pass it to override for a calibrated basin. The reported ``peak_cfs`` is stored
    to 2 significant figures — a Tier-0 screen's inputs are ~2 sig figs, so a finer stored peak
    would read as false confidence — while the full ``flows_cfs``/``times_hr`` series keeps its
    precision (it feeds the volume and any downstream routing).
    """
    if (curve_number is None) == (cn_parts is None):
        raise ValueError("simulate_runoff needs exactly one of curve_number or cn_parts")
    pf = peak_factor if peak_factor is not None else _peak_factor(settings=settings)
    area_sqmi = area_acres / 640.0
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
        amc=amc,  # str param, validated against the Hydrograph Literal at construction
        runoff_method=runoff_method,
    )
