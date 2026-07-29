"""NRCS Type-II 24-hour design rainfall distribution, at the published 6-minute resolution.

Given a total storm depth (inches), produce the cumulative and incremental hyetograph at a
chosen time step. Allen County, OH falls in the NRCS **Type II** rainfall region.

**Why this is built, not tabulated (WS-10 / #1610).** A Type-II curve stored at 1-hour
resolution and linearly interpolated onto a 0.1-hr grid smears the central burst into a
constant hourly intensity: the whole 11->12 hr increment (0.428 of the 24-hr depth) arrives as
one flat rate, and the sub-hourly intensities that drive a short-Tc catchment's peak are
understated ~3x. The distribution is therefore constructed here at the NRCS-native 0.1-hr
(6-minute) step by the **WinTR-20 algorithm published in NEH-630 Ch. 4, section 630.0407**
("Development of 24-Hour Rainfall Distribution From 5-Minute Through 24-Hour Rainfall Values"),
driven by the duration ratios *embedded in the standard Type II distribution* (NEH-630 Ch. 4,
figure 4-46, column 3). The construction is verified two ways in the tests: against the
handbook's own worked example (Columbus, OH, 25-yr — figures 4-63 through 4-69, reproduced to
within its published rounding), and against the legacy hourly Type-II table, which it matches
away from the central burst it exists to resolve.

**Caveat carried forward.** NEH-630 Ch. 4 (630.0403 B(8)) concludes that the legacy Type I/IA/
II/III distributions "be discontinued in areas covered by NOAA Atlas 14 data" — the Type II's
embedded 60-min/24-hr ratio is 0.454, while this corridor's own committed Atlas-14 point data
(``atlas14-corridor-ddf.yaml``: 25-yr 60-min 2.17 in / 24-hr 4.25 in) gives 0.51. Type II still
under-states the local burst; :func:`build_distribution` is the seam a site-specific Atlas-14
ratio set plugs into. Tracked as an open follow-up, not silently applied here.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

# Ratios of shorter-duration to 24-hour precipitation *embedded in* the standard NRCS Type II
# distribution — USDA NRCS, National Engineering Handbook Part 630, Ch. 4 "Storm Rainfall Depth
# and Distribution" (210-630-H, Amend. 88, Aug 2019), figure 4-46 column 3 ("Type II ratio").
# Keyed by duration in hours. These ratios *define* the curve: the construction below places
# each one as a nested block centred on hour 12.
_TYPE_II_DURATION_RATIOS: dict[float, float] = {
    5.0 / 60.0: 0.114,
    10.0 / 60.0: 0.201,
    15.0 / 60.0: 0.270,
    30.0 / 60.0: 0.380,
    1.0: 0.454,
    2.0: 0.538,
    3.0: 0.595,
    6.0: 0.707,
    12.0: 0.841,
}

# The construction's native grid: a 24-hour storm at a 0.1-hr (6-minute) step. 6 minutes is the
# finest interval the NRCS procedure resolves (step 8 places the maximum 6-minute block at
# 12.0-12.1 hr), so a caller asking for a finer dt gets that block spread at constant intensity
# — real sub-6-minute structure is not in the published distribution and is not invented here.
_DIST_DT_HR = 0.1
_DIST_DURATION_HR = 24.0
_DIST_N = round(_DIST_DURATION_HR / _DIST_DT_HR) + 1  # 241 ordinates, t = 0.0 .. 24.0


def build_distribution(duration_ratios: dict[float, float]) -> NDArray[np.float64]:
    """Cumulative rain ratios at 0.1-hr steps (241 ordinates, 0.0 -> 1.0) for a ratio set.

    Implements NEH-630 Ch. 4 section 630.0407 B steps 2-8 verbatim. ``duration_ratios`` maps a
    duration in hours to its depth as a fraction of the 24-hour depth, and must carry the ten
    NRCS durations (5, 10, 15, 30 min; 1, 2, 3, 6, 12 hr — the 24-hr ratio is 1.0 by
    definition). The result is symmetric about hour 12 except for the single maximum 6-minute
    block, which step 8 places at 12.0-12.1 hr.
    """
    missing = {5 / 60, 10 / 60, 15 / 60, 30 / 60, 1.0, 2.0, 3.0, 6.0, 12.0} - set(duration_ratios)
    if missing:
        raise ValueError(f"rainfall distribution needs ratios for durations (hr) {sorted(missing)}")

    # Step 2 — preliminary cumulative rain ratios (CRR) at the anchor times. Each duration's
    # block is centred on hour 12, so the curve at the block's leading edge is 0.5 - ratio/2.
    def lead(duration_hr: float) -> float:
        return 0.5 - duration_ratios[duration_hr] / 2.0

    crr_6, crr_9 = lead(12.0), lead(6.0)
    crr_105, crr_11, crr_115 = lead(3.0), lead(2.0), lead(1.0)
    crr_1175, crr_11875 = lead(0.5), lead(0.25)
    crr_119167 = lead(10.0 / 60.0)  # 11 hr 55 min — the leading edge of the 10-minute block

    crr = np.zeros(_DIST_N, dtype=np.float64)
    t = np.arange(_DIST_N, dtype=np.float64) * _DIST_DT_HR

    # Step 3 — 0.0 to 9.0 hr: CRR(t) = a*t^2 + b*t (eq. 4-1).
    a = (2.0 / 3.0 * crr_9 - crr_6) / 18.0
    b = (crr_6 - 36.0 * a) / 6.0
    seg = t <= 9.0
    crr[seg] = a * t[seg] ** 2 + b * t[seg]

    # Step 4 — 9.0 to 10.5 hr: CRR(t) = a2*t^2 + b2*t (eq. 4-2).
    a2 = (9.0 / 10.5 * crr_105 - crr_9) / 13.5
    b2 = (crr_9 - 81.0 * a2) / 9.0
    seg = (t > 9.0) & (t <= 10.5)
    crr[seg] = a2 * t[seg] ** 2 + b2 * t[seg]

    # Step 5 — 10.5 to 11.5 hr: CRR(t) = a3*t^2 + b3*t + c3 (eq. 4-3), fitted through the
    # 10.5 / 11.0 / 11.5 anchors. (The handbook prints c3's leading term as a bare "11"; it is
    # CRR(11) — the printed worked example only reproduces with CRR(11), which is how it is
    # written here and what the regression test against figure 4-67 confirms.)
    a3 = 2.0 * (crr_115 - 2.0 * crr_11 + crr_105)
    b3 = crr_115 - crr_105 - 22.0 * a3
    c3 = crr_11 - 121.0 * a3 - 11.0 * b3
    seg = (t > 10.5) & (t <= 11.5)
    crr[seg] = a3 * t[seg] ** 2 + b3 * t[seg] + c3

    # Step 6 — 11.6 to 11.9 hr: intensity-damped blend onto the 30/15/10-minute anchors, so the
    # rise into the burst stays smooth instead of stepping at each anchor.
    intensity_115 = (crr[115] - crr[114]) / _DIST_DT_HR
    factor_116 = min(-0.867 * intensity_115 + 0.4337, 0.399)
    factor_117 = min(-0.4917 * intensity_115 + 0.8182, 0.799)
    crr[116] = crr_115 + factor_116 * (crr_1175 - crr_115)
    crr[117] = crr_115 + factor_117 * (crr_1175 - crr_115)
    crr[118] = crr_1175 + (11.8 - 11.75) / (11.875 - 11.75) * (crr_11875 - crr_1175)
    t_119167 = 11.0 + 55.0 / 60.0
    crr[119] = crr_11875 + (11.9 - 11.875) / (t_119167 - 11.875) * (crr_119167 - crr_11875)

    # Step 7 — 12.1 to 24.0 hr by symmetry about hour 12: CRR(12 + k) = 1 - CRR(12 - k).
    crr[121:] = 1.0 - crr[119::-1]

    # Step 8 — the 12.0 ordinate carries the maximum 6-minute block, interpolated between the
    # 5- and 10-minute ratios, so the distribution's peak intensity is the published one.
    ratio_5, ratio_10 = duration_ratios[5.0 / 60.0], duration_ratios[10.0 / 60.0]
    crr[120] = crr[121] - (ratio_5 + 0.2 * (ratio_10 - ratio_5))

    if not bool(np.all(np.diff(crr) >= -1e-12)):
        raise ValueError(
            "constructed rainfall distribution is not monotonic — the duration ratios are "
            "inconsistent (a shorter duration must never carry more depth than a longer one)"
        )
    return crr


@lru_cache(maxsize=4)
def _type_ii_cumulative() -> NDArray[np.float64]:
    """The standard Type-II curve at 0.1-hr steps (cached; the ratio table is a constant)."""
    curve = build_distribution(_TYPE_II_DURATION_RATIOS)
    curve.setflags(write=False)
    return curve


def scs_type_ii_hyetograph(
    depth_in: float,
    *,
    dt_hr: float = 0.1,
    duration_hr: float = 24.0,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Return ``(times, cumulative_in, incremental_in)`` for a Type-II storm.

    ``times`` are the right edges of each step (length ``duration_hr/dt_hr``). The cumulative
    depth ends exactly at ``depth_in``; the incremental series sums to ``depth_in``
    (mass-conserving regardless of ``dt_hr``). A ``duration_hr`` other than 24 rescales the
    24-hour shape onto that duration.

    ``dt_hr`` at or below the distribution's native 0.1 hr resolves the published central burst;
    a coarser step averages over it, and (as with any design-storm model) understates the peak
    intensity a short-Tc catchment responds to.
    """
    if depth_in < 0:
        raise ValueError("storm depth must be non-negative")
    n = round(duration_hr / dt_hr)
    times = np.arange(1, n + 1, dtype=np.float64) * dt_hr
    curve = _type_ii_cumulative()
    dist_times = np.arange(_DIST_N, dtype=np.float64) * _DIST_DT_HR
    # Interpolate the cumulative fraction onto our time grid, scaled to the 24h distribution.
    frac = np.interp(times / duration_hr * _DIST_DURATION_HR, dist_times, curve)
    cumulative = frac * depth_in
    incremental = np.diff(cumulative, prepend=0.0)
    return times, cumulative, incremental
