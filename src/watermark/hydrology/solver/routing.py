"""Muskingum-Cunge channel routing (constant-parameter, Tier-0).

Library primitive: this routes a *time-varying* hydrograph, unlike the steady-state
mass balance in :mod:`watermark.hydrology.network`. Its production caller is
:mod:`watermark.hydrology.hydrograph_routing` (the ``/basin`` view — route storm hydrographs
down the cited confluence graph so a downstream peak is attenuated and lagged, not summed).
(The AMC-III adjuster from the sibling cleanup #1160 *is* wired in, via
``solver.runoff.simulate_runoff``.)

Routes an inflow hydrograph down a trapezoidal reach, attenuating and lagging the
peak. Parameters are derived once at a reference discharge (the inflow peak):

    normal depth via Manning (Newton-Raphson, trapezoid)
    celerity  c = (5/3) * V          (kinematic wave, wide-channel — see below)
    storage   K = Δx / c
    weighting X = 0.5 * (1 - Q / (c * S0 * Tw * Δx))   clamped to [0, 0.5]

then the standard Muskingum coefficients c1+c2+c3 = 1.

**Sub-reach subdivision (WS-09 / #1609).** ``Δx`` is a *sub-reach* step, **not** the whole
reach length. Routing a 15k-30k ft reach as one coarse Muskingum step drives the leading
coefficient ``c1 = (Δt - 2KX)/denom`` strongly negative (the 82k ft Lima Ottawa reach hit
``c1 ≈ -0.75``), which produces a spurious leading-limb dip/oscillation that the old output
clamp merely masked. Standard practice (Ponce 1989; NRCS) subdivides each reach into
``n ≈ ⌈L/(c·Δt)⌉`` sub-reaches so the grid **Courant number** ``Cr = c·Δt/Δx ≈ 1`` and routes
them in series. At ``Cr ≈ 1`` with ``X ∈ [0, ½]`` all three coefficients are non-negative, so
the routed hydrograph is a genuine convex combination (no oscillation to clamp) and the routed
peak is **grid-independent** — halving Δx moves the outlet peak by well under a percent. Each
reach records its ``Cr`` as a validity flag.

**Celerity assumption (WS-25).** The exact kinematic-wave celerity is ``c = dQ/dA = (dQ/dy)/T``
(``T`` the top width) for the *actual* section. ``c = (5/3)·V`` is its **wide-channel limit** —
exact for a wide rectangular section (where ``dQ/dA → (5/3)·V``), and an **over-estimate** for the
narrow trapezoidal default (10 ft bottom, 2:1 sides) because wetted-perimeter growth with depth
holds the true ``dQ/dy`` below the wide-channel value. For that default section the exact
Manning ``dQ/dA`` runs ~**15-20 % below** ``(5/3)·V`` across the loop's depth/slope range (deeper
flow → larger gap), so the wide-channel form over-states celerity by ~1/0.82 ≈ 20 % there.

This is a **stated Tier-0 assumption**, not a calibrated value, and it is kept deliberately: the
routed peak is **grid-independent** by construction (the Courant≈1 sub-reach subdivision below),
so the celerity choice moves the sub-reach *count* and the reach travel time ``K = Δx/c`` — not
the qualitative attenuation the ``/basin`` screen reads — and a ~20 % celerity bias is well
inside the Tier-0 screening band. Computing ``dQ/dA`` numerically per reach is the exact upgrade
(it lengthens ``K`` on narrow reaches); it is not wired in here so the committed
``routed-hydrograph`` reference/feed stays stable. A wide mainstem — where the assumption
*holds* — should override the channel geometry in ``reaches.yaml``.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np
from numpy.typing import NDArray

from watermark.config import Settings
from watermark.hydrology.solver.parameters import default_manning_n

_SECONDS_PER_HOUR = 3600.0
# Compute guard (WS-09 / #1609): a very slow / flat reach (tiny celerity from a low slope or a
# data-entry error) makes dx_per_step -> 0, so the Courant≈1 count ⌈L/(c·Δt)⌉ would explode and
# each sub-reach is an O(len(series)) routing pass. Cap it far above any real reach (the committed
# loop needs ≤ ~19); when the cap bites, the recorded Courant number drops below 1 to reveal it.
_MAX_SUBREACHES = 1000


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


def reach_kinematics(
    q_ref: float,
    *,
    slope: float,
    manning_n: float,
    bottom_width_ft: float,
    side_slope_z: float,
) -> tuple[float, float]:
    """``(celerity_ft_s, top_width_ft)`` at the reference discharge (wide-channel kinematic wave).

    ``celerity = (5/3)·V`` is the wide-channel limit of the exact kinematic celerity ``c = dQ/dA``
    (exact for a wide rectangular section, ~15-20 % over the true ``dQ/dA`` for the narrow
    trapezoidal default) — a stated Tier-0 assumption, quantified in the module docstring. ``0.0``
    celerity signals a degenerate reach (no flow / no area) that the callers pass through unrouted.
    """
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
    return (5.0 / 3.0) * velocity, top_width


def subreach_count(
    q_ref: float,
    *,
    length_ft: float,
    slope: float,
    manning_n: float,
    bottom_width_ft: float,
    side_slope_z: float,
    dt_hr: float,
) -> int:
    """Number of series sub-reaches ``n ≈ ⌈L/(c·Δt)⌉`` so each step has Courant ``c·Δt/Δx ≈ 1``.

    Routing the whole reach as one coarse Muskingum step drives ``c1`` negative (WS-09 / #1609);
    splitting it into ``n`` Courant≈1 steps and routing them in series keeps every coefficient
    non-negative and makes the routed peak grid-independent. A degenerate (zero-celerity) reach
    returns ``1`` (the callers pass it through unrouted); the count is bounded by
    ``_MAX_SUBREACHES`` so a pathologically slow/flat reach can't explode into an unbounded
    number of O(series) routing passes.
    """
    celerity, _ = reach_kinematics(
        q_ref,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
    )
    dx_per_step = celerity * dt_hr * _SECONDS_PER_HOUR  # ft a kinematic wave travels in one Δt
    if dx_per_step <= 0 or length_ft <= 0:
        return 1
    return max(1, min(_MAX_SUBREACHES, math.ceil(length_ft / dx_per_step)))


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
    """Muskingum-Cunge ``(c1, c2, c3)`` for a single step of ``length_ft``. Sum to 1.

    ``length_ft`` here is the *sub-reach* step Δx (see :func:`route_reach`), not the whole reach;
    ``X`` and ``K`` are formed at that Δx so a Courant≈1 step yields non-negative coefficients.
    """
    celerity, top_width = reach_kinematics(
        q_ref,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
    )
    if celerity <= 0:
        return 1.0, 0.0, 0.0  # degenerate: pass-through
    k_hr = (length_ft / celerity) / _SECONDS_PER_HOUR
    x = 0.5 * (1.0 - q_ref / (celerity * slope * top_width * length_ft))
    x = min(0.5, max(0.0, x))
    denom = 2.0 * k_hr * (1.0 - x) + dt_hr
    c1 = (dt_hr - 2.0 * k_hr * x) / denom
    c2 = (dt_hr + 2.0 * k_hr * x) / denom
    c3 = (2.0 * k_hr * (1.0 - x) - dt_hr) / denom
    return c1, c2, c3


class RoutedReach(NamedTuple):
    """A routed reach outflow plus the sub-reach discretization that produced it (WS-09 / #1609).

    ``courant`` is the grid Courant number ``c·Δt/Δx`` at the sub-reach scale — the routing
    validity flag: ``≈ 1`` by construction, so the Muskingum coefficients stay non-negative and
    the routed peak is grid-independent.
    """

    outflow_cfs: NDArray[np.float64]
    subreaches: int
    dx_ft: float
    celerity_ft_s: float
    courant: float


def _step(inflow: NDArray[np.float64], c1: float, c2: float, c3: float) -> NDArray[np.float64]:
    """One Muskingum step through a single sub-reach."""
    out = np.zeros_like(inflow)
    out[0] = inflow[0]
    for i in range(1, len(inflow)):
        # With a Courant≈1 sub-reach and X∈[0,½] all coefficients are non-negative, so this is a
        # convex combination and stays ≥ 0 on its own; the max() is floating-point insurance (and
        # the safety net when a caller forces a single coarse step), no longer an oscillation mask.
        out[i] = max(0.0, c1 * inflow[i] + c2 * inflow[i - 1] + c3 * out[i - 1])
    return out


def route_reach(
    inflow_cfs: NDArray[np.float64],
    *,
    length_ft: float,
    slope: float,
    manning_n: float | None = None,
    bottom_width_ft: float = 10.0,
    side_slope_z: float = 2.0,
    dt_hr: float = 0.1,
    subreaches: int | None = None,
    settings: Settings | None = None,
) -> RoutedReach:
    """Route an inflow hydrograph through a reach, subdividing into Courant≈1 sub-reaches.

    The reach is split into ``n`` equal sub-reaches (``n`` auto-selected for Courant ≈ 1, or
    forced via ``subreaches`` — used by the grid-independence test), one set of constant
    Muskingum coefficients is formed at the reference discharge (the inflow peak) and the
    sub-reach step Δx, and the hydrograph is routed through the ``n`` sub-reaches in series.
    Returns the outflow series alongside the discretization (``subreaches``, ``dx_ft``,
    ``celerity_ft_s``, ``courant``) so the caller can record the routing's validity.

    ``manning_n`` defaults to the cited natural-channel value in ``tier0-parameters.yaml``
    (0.04) when a reach sets none; ``reaches.yaml`` overrides it per reach.
    """
    if manning_n is None:
        manning_n = default_manning_n(settings=settings)
    q_ref = float(inflow_cfs.max()) if inflow_cfs.size else 0.0
    if q_ref <= 0:
        return RoutedReach(inflow_cfs.copy(), 1, length_ft, 0.0, 0.0)

    celerity, _ = reach_kinematics(
        q_ref,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
    )
    n = (
        subreaches
        if subreaches is not None
        else subreach_count(
            q_ref,
            length_ft=length_ft,
            slope=slope,
            manning_n=manning_n,
            bottom_width_ft=bottom_width_ft,
            side_slope_z=side_slope_z,
            dt_hr=dt_hr,
        )
    )
    n = max(1, n)
    dx = length_ft / n
    c1, c2, c3 = muskingum_coeffs(
        q_ref,
        length_ft=dx,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
        dt_hr=dt_hr,
    )
    courant = (celerity * dt_hr * _SECONDS_PER_HOUR / dx) if dx > 0 else 0.0

    out = inflow_cfs.astype(np.float64, copy=True)
    for _ in range(n):
        out = _step(out, c1, c2, c3)
    return RoutedReach(out, n, dx, celerity, courant)


def route(
    inflow_cfs: NDArray[np.float64],
    *,
    length_ft: float,
    slope: float,
    manning_n: float | None = None,
    bottom_width_ft: float = 10.0,
    side_slope_z: float = 2.0,
    dt_hr: float = 0.1,
    settings: Settings | None = None,
) -> NDArray[np.float64]:
    """Route an inflow hydrograph through a reach; returns the outflow series.

    Thin wrapper over :func:`route_reach` (Courant≈1 sub-reach subdivision) that drops the
    discretization diagnostics — kept for callers that only need the routed series. ``manning_n``
    defaults to the cited ``tier0-parameters.yaml`` value (``reaches.yaml`` overrides per reach).
    """
    return route_reach(
        inflow_cfs,
        length_ft=length_ft,
        slope=slope,
        manning_n=manning_n,
        bottom_width_ft=bottom_width_ft,
        side_slope_z=side_slope_z,
        dt_hr=dt_hr,
        settings=settings,
    ).outflow_cfs
