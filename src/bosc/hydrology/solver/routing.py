"""Muskingum-Cunge channel routing (constant-parameter, Tier-0).

Routes an inflow hydrograph down a trapezoidal reach, attenuating and lagging the
peak. Parameters are derived once at a reference discharge (the inflow peak):

    normal depth via Manning (Newton-Raphson, trapezoid)
    celerity  c = (5/3) * V          (kinematic wave)
    storage   K = L / c
    weighting X = 0.5 * (1 - Q / (c * S0 * Tw * L))   clamped to [0, 0.5]

then the standard Muskingum coefficients c1+c2+c3 = 1.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def normal_depth(
    q: float,
    *,
    bottom_width_ft: float,
    side_slope_z: float,
    slope: float,
    manning_n: float,
) -> float:
    """Solve Manning's equation for normal depth (ft) in a trapezoidal channel."""
    if q <= 0:
        return 0.0
    y = 1.0
    for _ in range(60):
        area = bottom_width_ft * y + side_slope_z * y * y
        perim = bottom_width_ft + 2.0 * y * np.hypot(1.0, side_slope_z)
        r = area / perim
        q_calc = (1.49 / manning_n) * area * r ** (2.0 / 3.0) * np.sqrt(slope)
        f = q_calc - q
        if abs(f) < 1e-4:
            break
        # numerical derivative
        dy = 1e-4
        a2 = bottom_width_ft * (y + dy) + side_slope_z * (y + dy) ** 2
        p2 = bottom_width_ft + 2.0 * (y + dy) * np.hypot(1.0, side_slope_z)
        q2 = (1.49 / manning_n) * a2 * (a2 / p2) ** (2.0 / 3.0) * np.sqrt(slope)
        dfdy = (q2 - q_calc) / dy
        if dfdy == 0:
            break
        y = max(1e-3, y - f / dfdy)
    return float(y)


def muskingum_coeffs(
    q_ref: float,
    *,
    length_ft: float,
    slope: float,
    manning_n: float,
    bottom_width_ft: float,
    side_slope_z: float,
    dt_hr: float,
) -> tuple[float, float, float]:
    """Muskingum-Cunge ``(c1, c2, c3)`` at a reference discharge. Sum to 1."""
    y = normal_depth(
        q_ref,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
        slope=slope,
        manning_n=manning_n,
    )
    area = bottom_width_ft * y + side_slope_z * y * y
    top_width = bottom_width_ft + 2.0 * side_slope_z * y
    velocity = q_ref / area if area > 0 else 0.0
    celerity = (5.0 / 3.0) * velocity
    if celerity <= 0:
        return 1.0, 0.0, 0.0  # degenerate: pass-through
    k_hr = (length_ft / celerity) / 3600.0
    x = 0.5 * (1.0 - q_ref / (celerity * slope * top_width * length_ft))
    x = min(0.5, max(0.0, x))
    denom = 2.0 * k_hr * (1.0 - x) + dt_hr
    c1 = (dt_hr - 2.0 * k_hr * x) / denom
    c2 = (dt_hr + 2.0 * k_hr * x) / denom
    c3 = (2.0 * k_hr * (1.0 - x) - dt_hr) / denom
    return c1, c2, c3


def route(
    inflow_cfs: NDArray[np.float64],
    *,
    length_ft: float,
    slope: float,
    manning_n: float = 0.04,
    bottom_width_ft: float = 10.0,
    side_slope_z: float = 2.0,
    dt_hr: float = 0.1,
) -> NDArray[np.float64]:
    """Route an inflow hydrograph through a reach; returns the outflow series."""
    q_ref = float(inflow_cfs.max()) if inflow_cfs.size else 0.0
    if q_ref <= 0:
        return inflow_cfs.copy()
    c1, c2, c3 = muskingum_coeffs(
        q_ref,
        length_ft=length_ft,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
        dt_hr=dt_hr,
    )
    out = np.zeros_like(inflow_cfs)
    out[0] = inflow_cfs[0]
    for i in range(1, len(inflow_cfs)):
        out[i] = max(0.0, c1 * inflow_cfs[i] + c2 * inflow_cfs[i - 1] + c3 * out[i - 1])
    return out
