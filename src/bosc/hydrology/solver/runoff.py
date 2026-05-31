"""SCS dimensionless unit hydrograph + convolution.

Turns a design-storm depth + curve number + basin parameters into a runoff
hydrograph:

    Tp = dt/2 + 0.6 * Tc           time to peak (hr)
    Qp = 484 * A / Tp              UH peak (cfs per inch of excess; A in sq mi)

The dimensionless SCS unit hydrograph (q/Qp vs t/Tp) is scaled by ``(Tp, Qp)`` and
convolved with the incremental excess rainfall. The 484 peak factor makes the
hydrograph conserve volume (total flow volume == excess depth over the area).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from bosc.hydrology.model import Hydrograph
from bosc.hydrology.solver.curve_number import excess_rainfall
from bosc.hydrology.solver.rainfall import scs_type_ii_hyetograph

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


def _unit_hydrograph(area_sqmi: float, tc_hr: float, dt_hr: float) -> NDArray[np.float64]:
    """UH ordinates (cfs per inch of excess) at ``dt_hr`` spacing."""
    tp = dt_hr / 2.0 + 0.6 * tc_hr
    qp = 484.0 * area_sqmi / tp
    n = int(np.ceil(5.0 * tp / dt_hr)) + 1  # the dimensionless curve tails out by t/Tp=5
    t = np.arange(n, dtype=np.float64) * dt_hr
    return qp * np.interp(t / tp, _T_OVER_TP, _Q_OVER_QP)


def simulate_runoff(
    *,
    area_acres: float,
    curve_number: float,
    tc_hr: float,
    storm_depth_in: float,
    dt_hr: float = 0.1,
    duration_hr: float = 24.0,
) -> Hydrograph:
    """Run the Tier-0 SCS chain for one footprint and one design storm."""
    area_sqmi = area_acres / 640.0
    _, cumulative, _ = scs_type_ii_hyetograph(storm_depth_in, dt_hr=dt_hr, duration_hr=duration_hr)
    cum_excess = excess_rainfall(cumulative, curve_number)
    inc_excess = np.diff(cum_excess, prepend=0.0)  # inches per step
    uh = _unit_hydrograph(area_sqmi, tc_hr, dt_hr)

    flows = np.convolve(inc_excess, uh)[: len(inc_excess)]
    times = np.arange(1, len(flows) + 1, dtype=np.float64) * dt_hr
    volume_acft = float(flows.sum() * dt_hr * _SEC_PER_HR / _SQFT_PER_ACRE)
    peak_idx = int(np.argmax(flows))

    return Hydrograph(
        times_hr=[round(t, 4) for t in times.tolist()],
        flows_cfs=[round(q, 4) for q in flows.tolist()],
        peak_cfs=round(float(flows[peak_idx]), 3),
        time_to_peak_hr=round(float(times[peak_idx]), 3),
        volume_acft=round(volume_acft, 3),
        runoff_depth_in=round(float(cum_excess[-1]), 4),
        curve_number=round(curve_number, 1),
    )
