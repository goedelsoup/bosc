"""SCS Type-II 24-hour design rainfall distribution.

Given a total storm depth (inches), produce the cumulative and incremental
hyetograph at a chosen time step. Allen County, OH falls in the SCS **Type II**
rainfall region. The cumulative-fraction table is the standard NRCS Type II 24-hr
distribution (NEH-630 / TR-55); intermediate times are linearly interpolated.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Cumulative fraction P(t)/P(24h) of the NRCS Type II 24-hour storm, hour 0..24.
# The steep rise around hour 12 is the Type II central burst.
_TYPE_II_HOURS: tuple[float, ...] = tuple(float(h) for h in range(25))
_TYPE_II_CUM: tuple[float, ...] = (
    0.000,
    0.011,
    0.022,
    0.035,
    0.048,
    0.063,
    0.080,
    0.098,
    0.120,
    0.147,
    0.181,
    0.235,
    0.663,
    0.772,
    0.820,
    0.850,
    0.880,
    0.898,
    0.912,
    0.926,
    0.938,
    0.948,
    0.958,
    0.974,
    1.000,
)


def scs_type_ii_hyetograph(
    depth_in: float,
    *,
    dt_hr: float = 0.1,
    duration_hr: float = 24.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(times, cumulative_in, incremental_in)`` for a Type-II storm.

    ``times`` are the right edges of each step (length ``duration_hr/dt_hr``).
    The cumulative depth ends exactly at ``depth_in``; the incremental series sums
    to ``depth_in`` (mass-conserving regardless of ``dt_hr``).
    """
    if depth_in < 0:
        raise ValueError("storm depth must be non-negative")
    n = round(duration_hr / dt_hr)
    times = np.arange(1, n + 1, dtype=np.float64) * dt_hr
    # Interpolate the cumulative fraction onto our time grid, scaled to the 24h table.
    frac = np.interp(times / duration_hr * 24.0, _TYPE_II_HOURS, _TYPE_II_CUM)
    cumulative = frac * depth_in
    incremental = np.diff(cumulative, prepend=0.0)
    return times, cumulative, incremental
