"""SCS solver invariants — the physics that must hold regardless of inputs."""

from __future__ import annotations

import math

import numpy as np
import pytest

from watermark.config import Settings
from watermark.hydrology.solver import routing
from watermark.hydrology.solver.curve_number import (
    adjust_amc,
    cn_for,
    composite_cn,
    excess_rainfall,
    storage_s,
    weighted_excess_rainfall,
)
from watermark.hydrology.solver.rainfall import (
    _TYPE_II_DURATION_RATIOS,
    build_distribution,
    scs_type_ii_hyetograph,
)
from watermark.hydrology.solver.runoff import (
    _CFS_HR_PER_IN_SQMI,
    gamma_shape_for,
    simulate_runoff,
    unit_duration_hr,
)

# --------------------------------------------------------------------------------------
# WS-10 / #1610 — design-storm peak fidelity: the rainfall distribution's own references.
# --------------------------------------------------------------------------------------

# NEH-630 Ch. 4 figure 4-63: the 25-yr duration ratios for Columbus, OH (WSO Airport), the
# handbook's worked example for the 630.0407 construction :func:`build_distribution` implements.
_NRCS_EXAMPLE_RATIOS: dict[float, float] = {
    5 / 60: 0.1464,
    10 / 60: 0.2252,
    15 / 60: 0.2770,
    30 / 60: 0.3919,
    1.0: 0.5068,
    2.0: 0.6014,
    3.0: 0.6396,
    6.0: 0.7568,
    12.0: 0.8784,
}
# The cumulative rain ratios the handbook prints for that example (figures 4-65 through 4-69,
# plus the step-8 value at hour 12), sampled across every segment of the construction.
_NRCS_EXAMPLE_CRR: dict[float, float] = {
    1.0: 0.0045,
    6.0: 0.0608,
    9.0: 0.1216,
    10.0: 0.1594,
    10.5: 0.1802,
    10.6: 0.1818,
    11.0: 0.1993,
    11.4: 0.2349,
    11.5: 0.2466,
    11.6: 0.2657,
    11.7: 0.2903,
    11.8: 0.3270,
    11.9: 0.3770,
    12.0: 0.46081,
    12.1: 0.6230,
    12.5: 0.7534,
    13.0: 0.8007,
    15.0: 0.8784,
    18.0: 0.9392,
    20.0: 0.9685,
    24.0: 1.0000,
}

# The legacy 1-hour Type-II table this module used before #1610 (NRCS Type II, hours 0..24).
# Kept as the shape anchor: the reconstruction must reproduce it everywhere EXCEPT the central
# burst, which is precisely the hour an hourly table cannot resolve.
_LEGACY_HOURLY_TYPE_II: tuple[float, ...] = (
    0.000, 0.011, 0.022, 0.035, 0.048, 0.063, 0.080, 0.098, 0.120, 0.147, 0.181, 0.235,
    0.663, 0.772, 0.820, 0.850, 0.880, 0.898, 0.912, 0.926, 0.938, 0.948, 0.958, 0.974, 1.000,
)  # fmt: skip

# NEH-630 Table 16-1 (abridged) — the tabulated dimensionless unit hydrograph, q/Qp vs t/Tp.
# The analytic gamma form the solver now uses must track it; the table's own area implies a peak
# factor of ~476 rather than 484, which is why the tolerance below is a few percent and not zero.
_NEH_TABLE_16_1: tuple[tuple[float, float], ...] = (
    (0.0, 0.0), (0.1, 0.015), (0.2, 0.075), (0.3, 0.16), (0.4, 0.28), (0.5, 0.43), (0.6, 0.60),
    (0.7, 0.77), (0.8, 0.89), (0.9, 0.97), (1.0, 1.0), (1.1, 0.98), (1.2, 0.92), (1.3, 0.84),
    (1.4, 0.75), (1.5, 0.66), (1.6, 0.56), (1.8, 0.42), (2.0, 0.32), (2.2, 0.24), (2.4, 0.18),
    (2.6, 0.13), (2.8, 0.098), (3.0, 0.075), (3.5, 0.036), (4.0, 0.018), (4.5, 0.009),
)  # fmt: skip


def test_distribution_reproduces_the_nrcs_worked_example() -> None:
    # The construction is NEH-630 Ch. 4 section 630.0407; the handbook prints its own worked
    # result for Columbus, OH. Reproducing that table to its published rounding is what makes
    # this an implementation of a cited method rather than a curve we drew.
    crr = build_distribution(_NRCS_EXAMPLE_RATIOS)
    for hour, expected in _NRCS_EXAMPLE_CRR.items():
        assert crr[round(hour * 10)] == pytest.approx(expected, abs=1e-4), f"hour {hour}"
    assert crr[0] == 0.0 and crr[-1] == pytest.approx(1.0)
    assert np.all(np.diff(crr) >= -1e-12)


def test_type_ii_carries_its_published_duration_ratios() -> None:
    # The point of building the curve from NEH-630 fig. 4-46's embedded ratios: the maximum
    # nested window of each duration comes back out at the published depth. The legacy hourly
    # table cannot — its 1-hour burst is 0.428 of the storm against a published 0.454.
    crr = build_distribution(_TYPE_II_DURATION_RATIOS)
    legacy = np.interp(np.arange(241) * 0.1, np.arange(25.0), _LEGACY_HOURLY_TYPE_II)

    def max_window(curve: np.ndarray, hours: float) -> float:
        n = round(hours * 10)
        return float(np.max(curve[n:] - curve[:-n]))

    for duration in (1.0, 2.0, 3.0, 6.0, 12.0):
        assert max_window(crr, duration) == pytest.approx(
            _TYPE_II_DURATION_RATIOS[duration], abs=5e-4
        ), f"{duration} hr"
    assert max_window(legacy, 1.0) == pytest.approx(0.428, abs=1e-3)  # the understated burst


def test_type_ii_matches_the_legacy_hourly_table_away_from_the_burst() -> None:
    # Fidelity check in the other direction: the reconstruction is the SAME distribution, so it
    # must track the legacy hourly ordinates everywhere the hourly table was able to resolve.
    crr = build_distribution(_TYPE_II_DURATION_RATIOS)
    for hour, legacy in enumerate(_LEGACY_HOURLY_TYPE_II):
        if hour == 12:  # the central-burst ordinate an hourly table necessarily misplaces
            continue
        assert crr[hour * 10] == pytest.approx(legacy, abs=0.025), f"hour {hour}"


def test_fine_hyetograph_resolves_the_central_burst() -> None:
    # The bias this fixes: a 1-hour table interpolated to 0.1 hr spreads the central burst as a
    # constant hourly intensity, understating the sub-hourly intensity a short-Tc catchment
    # responds to by ~3x.
    _, _, incremental = scs_type_ii_hyetograph(4.0, dt_hr=0.1)
    peak_intensity = float(incremental.max()) / 0.1
    legacy_hourly_intensity = 0.428 * 4.0  # the legacy table's whole hour-11->12 block, in/hr
    assert peak_intensity / legacy_hourly_intensity == pytest.approx(3.07, abs=0.1)


def test_hyetograph_below_six_minutes_spreads_rather_than_invents_intensity() -> None:
    # 6 minutes is the finest interval the published NRCS construction resolves. A finer step
    # must spread that block at constant intensity — never manufacture a sharper one.
    _, _, coarse = scs_type_ii_hyetograph(4.0, dt_hr=0.1)
    _, _, fine = scs_type_ii_hyetograph(4.0, dt_hr=0.025)
    assert float(fine.sum()) == pytest.approx(4.0)
    assert float(fine.max()) / 0.025 == pytest.approx(float(coarse.max()) / 0.1, rel=1e-9)


def test_hyetograph_conserves_mass() -> None:
    _, cumulative, incremental = scs_type_ii_hyetograph(4.0, dt_hr=0.1)
    assert cumulative[-1] == pytest.approx(4.0)
    assert float(incremental.sum()) == pytest.approx(4.0)
    assert np.all(np.diff(cumulative) >= -1e-9)  # monotonic non-decreasing


def test_distribution_rejects_an_incomplete_ratio_set() -> None:
    with pytest.raises(ValueError, match="needs ratios for durations"):
        build_distribution({1.0: 0.454, 24.0: 1.0})


# --------------------------------------------------------------------------------------
# WS-10 / #1610 — the peak factor sets the SHAPE, and the SCS unit-duration rule.
# --------------------------------------------------------------------------------------


def test_gamma_unit_hydrograph_tracks_the_tabulated_neh_curve() -> None:
    # The analytic form the solver builds at the standard 484 must be the NEH Table 16-1 curve.
    m = gamma_shape_for(484.0)
    assert m == pytest.approx(3.70, abs=0.01)
    x = np.array([t for t, _ in _NEH_TABLE_16_1])
    tabulated = np.array([q for _, q in _NEH_TABLE_16_1])
    gamma = x**m * np.exp(m * (1.0 - x))
    assert float(np.max(np.abs(gamma - tabulated))) < 0.07
    assert gamma[x == 1.0] == pytest.approx(1.0)  # the peak is at t = Tp by construction


def test_peak_factor_conserves_volume_at_every_value(hydro_settings: Settings) -> None:
    # The defect this closes: rescaling ONE fixed dimensionless shape by a different peak factor
    # silently drops (or invents) runoff volume — a "flat basin" 300 would lose 38% of it. The
    # shape is solved from the factor instead, so volume reconciles with depth at any value.
    common = {
        "area_acres": 200.0,
        "curve_number": 88.0,
        "tc_hr": 0.75,
        "storm_depth_in": 4.0,
        "settings": hydro_settings,  # hermetic: the Ia ratio resolves off the fixture, not ambient
    }
    for factor in (200.0, 300.0, 484.0, 600.0):
        h = simulate_runoff(**common, peak_factor=factor)
        # abs=1e-3: volume_acft is stored to 3 decimals, which is the only slack here.
        assert h.volume_acft == pytest.approx(h.runoff_depth_in / 12.0 * 200.0, abs=1e-3), factor


def test_peak_factor_and_its_shape_are_locked_together() -> None:
    # 645.33 cfs-hr is one inch over one square mile; the peak factor is that constant divided by
    # the area under the dimensionless curve, which is what makes the two inseparable.
    for factor in (100.0, 300.0, 484.0, 600.0):
        m = gamma_shape_for(factor)
        x = np.linspace(0.0, 400.0, 4_000_001)
        with np.errstate(divide="ignore"):
            curve = np.where(x > 0, np.exp(m * np.log(np.where(x > 0, x, 1.0)) + m * (1 - x)), 0.0)
        assert _CFS_HR_PER_IN_SQMI / float(np.trapezoid(curve, x)) == pytest.approx(
            factor, rel=1e-4
        )
    # A flatter factor spreads the same volume over a longer base, so its peak is lower.
    assert gamma_shape_for(300.0) < gamma_shape_for(484.0) < gamma_shape_for(600.0)


def test_unit_duration_obeys_the_scs_rule_and_divides_the_requested_step() -> None:
    # D <= 0.133*Tc (NEH-630 Ch. 16), and D must stay an exact sub-multiple of the caller's step
    # so a network routing several catchments on one grid is never handed off-grid samples.
    for tc in (0.1, 0.2, 0.35, 0.6, 0.75, 1.0, 2.0, 8.0):
        d = unit_duration_hr(tc, 0.1)
        assert d <= 0.133 * tc + 1e-12 or d == 0.1
        assert d <= 0.1
        assert round(0.1 / d, 9) == round(round(0.1 / d), 9)  # 0.1 / D is an integer
    assert unit_duration_hr(1.0, 0.1) == 0.1  # Tc >= 0.75 hr: the rule is already satisfied
    assert unit_duration_hr(0.2, 0.1) == pytest.approx(0.025)  # a small paved catchment refines


def test_short_tc_catchment_peaks_higher_under_the_unit_duration_rule(
    hydro_settings: Settings,
) -> None:
    # The bias the rule removes: pinning the unit duration at the 0.1-hr output step broadens the
    # unit hydrograph for a small paved catchment (Tp = D/2 + 0.6*Tc), flattening its peak.
    common = {
        "area_acres": 3.0,
        "curve_number": 98.0,
        "storm_depth_in": 4.25,
        "settings": hydro_settings,  # hermetic: peak factor + Ia resolve off the fixture
    }
    refined = simulate_runoff(**common, tc_hr=0.2)
    # dt_hr is the EXACT computed step; times_hr is rounded for display, so assert on dt_hr.
    assert refined.dt_hr == pytest.approx(unit_duration_hr(0.2, 0.1))
    assert refined.dt_hr < 0.1  # the returned series lands on the refined grid
    # A long-Tc basin is untouched — the sub-hourly burst never reaches its peak.
    slow = simulate_runoff(**common, tc_hr=8.0)
    assert slow.dt_hr == pytest.approx(0.1)


def test_hydrograph_carries_the_exact_step_not_the_rounded_display_time(
    hydro_settings: Settings,
) -> None:
    # Tc 0.3 hr refines the unit duration to 0.1/3 = 0.0333... — a step `times_hr` (rounded to 4
    # decimals for display) cannot represent. A caller re-deriving the step from times_hr[0] would
    # inherit that rounding into its padding length, Courant number and routed lag, so the exact
    # value is carried on the hydrograph instead.
    h = simulate_runoff(
        area_acres=3.0,
        curve_number=98.0,
        tc_hr=0.3,
        storm_depth_in=4.25,
        settings=hydro_settings,
    )
    assert h.dt_hr == pytest.approx(0.1 / 3, rel=1e-12)  # exact, unrounded
    assert h.times_hr[0] != pytest.approx(h.dt_hr, rel=1e-12)  # display value HAS lost precision


def test_excess_matches_closed_form() -> None:
    cn = 85.0
    p = 4.0
    s = storage_s(cn)
    ia = 0.2 * s
    expected = (p - ia) ** 2 / (p - ia + s)
    _, cumulative, _ = scs_type_ii_hyetograph(p, dt_hr=0.1)
    cum_excess = excess_rainfall(cumulative, cn)
    assert float(cum_excess[-1]) == pytest.approx(expected, rel=1e-6)


def test_excess_zero_below_initial_abstraction() -> None:
    cn = 70.0  # S=4.29, Ia=0.857 in; a 0.5 in storm yields no runoff
    _, cumulative, _ = scs_type_ii_hyetograph(0.5, dt_hr=0.5)
    assert float(excess_rainfall(cumulative, cn)[-1]) == 0.0


def test_amc_adjustment_direction() -> None:
    cn_ii = 80.0
    assert adjust_amc(cn_ii, "I") < cn_ii < adjust_amc(cn_ii, "III")
    assert adjust_amc(cn_ii, "II") == cn_ii


def test_composite_cn_area_weighted() -> None:
    assert composite_cn([(50.0, 80.0), (50.0, 90.0)]) == pytest.approx(85.0)
    assert composite_cn([]) == 70.0  # documented fallback


def test_weighted_excess_exceeds_composite_cn_excess() -> None:
    # #1611 / TR-55: run each cover's CN separately and area-weight the runoff DEPTHS, rather
    # than applying one composite CN. Because runoff is convex in CN (Jensen), the weighted
    # depth is >= the composite-CN depth, strictly so when the covers differ — the runoff a
    # composite CN under-predicts once the impervious share passes ~30%.
    _, cumulative, _ = scs_type_ii_hyetograph(2.5, dt_hr=0.1)
    parts = [(115.0, 98.0), (225.0, 68.0)]  # ~34% impervious, wide CN spread
    weighted = weighted_excess_rainfall(cumulative, parts)
    lumped = excess_rainfall(cumulative, composite_cn(parts))
    assert float(weighted[-1]) > float(lumped[-1])
    # A single cover reduces exactly to the plain CN equation (nothing to weight).
    solo = weighted_excess_rainfall(cumulative, [(200.0, 85.0)])
    assert np.allclose(solo, excess_rainfall(cumulative, 85.0))
    # Degenerate zero-area parts fall back to the documented bare CN-70 series.
    degenerate = weighted_excess_rainfall(cumulative, [(0.0, 90.0)])
    assert np.allclose(degenerate, excess_rainfall(cumulative, 70.0))


def test_weighted_runoff_raises_depth_volume_and_frequent_peak() -> None:
    # The pipeline-level effect of the weighted-runoff method: more runoff depth and volume
    # (the detention-deficit signal), and a higher peak for a small/frequent storm.
    parts = [(115.0, 98.0), (225.0, 68.0)]
    composite = composite_cn(parts)
    common = {"area_acres": 340.0, "tc_hr": 0.6, "storm_depth_in": 2.5, "dt_hr": 0.1}
    weighted = simulate_runoff(cn_parts=parts, **common)
    lumped = simulate_runoff(curve_number=composite, **common)
    assert weighted.runoff_method == "weighted_runoff"
    assert lumped.runoff_method == "composite_cn"
    assert weighted.runoff_depth_in > lumped.runoff_depth_in
    assert weighted.volume_acft > lumped.volume_acft
    assert weighted.peak_cfs > lumped.peak_cfs
    # The reported CN stays the area-weighted composite (a summary descriptor, not storm-derived).
    assert weighted.curve_number == pytest.approx(composite, abs=0.1)


def test_weighted_runoff_understatement_largest_for_frequent_storms() -> None:
    # The compositing understatement in runoff DEPTH is largest for small/frequent storms — the
    # impervious fraction runs off while the pervious fraction still abstracts — and narrows as
    # the storm grows. This is why TR-55 separates high-impervious footprints; the frequent,
    # channel-forming storms are where the erosion signal is most understated.
    parts = [(115.0, 98.0), (225.0, 65.0)]
    composite = composite_cn(parts)

    def depth_gap(depth_in: float) -> float:
        common = {"area_acres": 340.0, "tc_hr": 0.6, "storm_depth_in": depth_in}
        return (
            simulate_runoff(cn_parts=parts, **common).runoff_depth_in
            - simulate_runoff(curve_number=composite, **common).runoff_depth_in
        )

    assert depth_gap(1.5) > depth_gap(6.0) > 0


def test_simulate_runoff_requires_exactly_one_cn_input() -> None:
    common = {"area_acres": 100.0, "tc_hr": 0.6, "storm_depth_in": 4.0}
    with pytest.raises(ValueError, match="exactly one"):
        simulate_runoff(**common)  # neither curve_number nor cn_parts
    with pytest.raises(ValueError, match="exactly one"):
        simulate_runoff(curve_number=80.0, cn_parts=[(100.0, 80.0)], **common)  # both


def test_cn_lookup_from_cited_table() -> None:
    s = Settings()
    assert cn_for("cropland", "C", settings=s) == pytest.approx(85.0)
    assert cn_for(24, "C", settings=s) == pytest.approx(94.0)  # developed, high intensity
    assert cn_for("developed_campus", "C", settings=s) > cn_for("cropland", "C", settings=s)


def test_runoff_volume_conserves() -> None:
    # Total hydrograph volume (ac-ft) must equal runoff depth over the area.
    h = simulate_runoff(
        area_acres=200.0, curve_number=88.0, tc_hr=0.75, storm_depth_in=4.0, dt_hr=0.05
    )
    expected_acft = h.runoff_depth_in / 12.0 * 200.0
    # Keeping the full convolution recession tail makes reported volume reconcile with
    # reported depth; residual gap is UH-ordinate discretization, not tail truncation.
    assert h.volume_acft == pytest.approx(expected_acft, rel=0.02)
    # Guard against re-truncating to the input length: the recession tail runs past the
    # 24 hr storm, so the hydrograph must be longer than the hyetograph it convolved.
    assert h.times_hr[-1] > 24.0


def test_higher_cn_yields_higher_peak() -> None:
    common = {"area_acres": 100.0, "tc_hr": 0.75, "storm_depth_in": 4.0, "dt_hr": 0.1}
    low = simulate_runoff(curve_number=78.0, **common)
    high = simulate_runoff(curve_number=95.0, **common)
    assert high.peak_cfs > low.peak_cfs
    assert high.volume_acft > low.volume_acft


def test_runoff_amc_iii_raises_peak_and_records_condition() -> None:
    # A wet-antecedent (AMC-III) run adjusts the AMC-II CN upward, so the same storm
    # yields a higher peak, and the hydrograph records the condition it ran under.
    common = {"area_acres": 200.0, "curve_number": 80.0, "tc_hr": 0.75, "storm_depth_in": 4.0}
    avg = simulate_runoff(**common)
    wet = simulate_runoff(**common, amc="III")
    assert avg.amc == "II"  # default is average antecedent moisture
    assert wet.amc == "III"
    assert wet.curve_number > avg.curve_number == 80.0  # AMC-II passes the CN through
    assert wet.peak_cfs > avg.peak_cfs


def test_muskingum_coefficients_sum_to_one() -> None:
    c1, c2, c3 = routing.muskingum_coeffs(
        500.0,
        length_ft=5000.0,
        slope=0.002,
        manning_n=0.04,
        bottom_width_ft=10.0,
        side_slope_z=2.0,
        dt_hr=0.1,
    )
    assert c1 + c2 + c3 == pytest.approx(1.0, abs=1e-9)


def test_routing_attenuates_and_lags_peak() -> None:
    inflow = np.array([0, 10, 50, 120, 200, 120, 50, 10, 0, 0, 0, 0], dtype=np.float64)
    out = routing.route(inflow, length_ft=8000.0, slope=0.001, dt_hr=0.1)
    assert out.max() <= inflow.max() + 1e-6  # never amplifies
    assert int(out.argmax()) >= int(inflow.argmax())  # peak no earlier


def _storm_inflow() -> np.ndarray:
    """A design-storm-shaped inflow with a long zero tail (room for the routed peak to land)."""
    hg = simulate_runoff(
        area_acres=30000, curve_number=80, tc_hr=6.0, storm_depth_in=4.25, dt_hr=0.1
    )
    return np.concatenate([np.asarray(hg.flows_cfs, dtype=np.float64), np.zeros(300)])


def test_long_reach_is_subdivided_to_courant_near_one() -> None:
    # WS-09 / #1609: a long reach (routing the whole 82k-ft length as ONE Muskingum step drives
    # c1 strongly negative) is split into n sub-reaches so the grid Courant number lands near 1.
    inflow = _storm_inflow()
    rr = routing.route_reach(inflow, length_ft=82000.0, slope=0.001, dt_hr=0.1)
    assert rr.subreaches > 1  # not routed as a single coarse step
    assert 0.9 <= rr.courant <= 1.5  # Courant ≈ 1 by construction (the validity flag)
    assert rr.dx_ft == pytest.approx(82000.0 / rr.subreaches)


def test_subdivided_muskingum_coefficients_are_all_nonnegative() -> None:
    # The point of subdivision: at Courant ≈ 1 with X∈[0,½] every coefficient is non-negative,
    # so the routed hydrograph is a convex combination — no leading-limb oscillation for the
    # output clamp to mask. The single coarse step drives c1 negative; the sub-reach step does not.
    q_ref = float(_storm_inflow().max())
    geom = {"slope": 0.001, "manning_n": 0.04, "bottom_width_ft": 10.0, "side_slope_z": 2.0}
    single = routing.muskingum_coeffs(q_ref, length_ft=82000.0, dt_hr=0.1, **geom)
    assert single[0] < 0  # the coarse whole-reach step: c1 < 0 (the masked pathology)
    n = routing.subreach_count(q_ref, length_ft=82000.0, dt_hr=0.1, **geom)
    dx = 82000.0 / n
    sub = routing.muskingum_coeffs(q_ref, length_ft=dx, dt_hr=0.1, **geom)
    assert all(c >= 0 for c in sub), sub  # every sub-reach coefficient is non-negative
    assert sum(sub) == pytest.approx(1.0, abs=1e-9)


def test_routed_peak_is_grid_independent() -> None:
    # Halving Δx (doubling the sub-reach count) must barely move the outlet peak — the routed
    # peak is a physical quantity, not a grid artifact. The single coarse step, by contrast, is
    # meaningfully off. (Cunge's method matches physical diffusion at any Δx, so refining converges.)
    inflow = _storm_inflow()
    auto = routing.route_reach(inflow, length_ft=82000.0, slope=0.001, dt_hr=0.1)
    finer = routing.route_reach(
        inflow, length_ft=82000.0, slope=0.001, dt_hr=0.1, subreaches=auto.subreaches * 2
    )
    single = routing.route_reach(inflow, length_ft=82000.0, slope=0.001, dt_hr=0.1, subreaches=1)
    rel = abs(finer.outflow_cfs.max() - auto.outflow_cfs.max()) / auto.outflow_cfs.max()
    assert rel < 0.03, f"outlet peak moved {rel:.1%} on halving Δx — not grid-independent"
    # The un-subdivided single step is the outlier the subdivision fixes.
    assert abs(single.outflow_cfs.max() - auto.outflow_cfs.max()) / auto.outflow_cfs.max() > rel


def test_subreach_count_is_bounded_for_a_pathological_reach() -> None:
    # WS-09 / #1609: a very slow/flat reach (tiny celerity from a near-zero slope) would ask for
    # an unbounded ⌈L/(c·Δt)⌉; the count is capped at _MAX_SUBREACHES so routing can't explode
    # into a runaway number of O(series) passes. A normal reach stays far below the cap.
    geom = {"slope": 1e-6, "manning_n": 0.04, "bottom_width_ft": 10.0, "side_slope_z": 2.0}
    n = routing.subreach_count(500.0, length_ft=200_000.0, dt_hr=0.1, **geom)
    assert n == routing._MAX_SUBREACHES  # capped (the uncapped ⌈L/(c·Δt)⌉ is far larger)
    # route_reach honors the cap through its real entry point (q_ref = the inflow peak).
    inflow = np.array([0, 100, 300, 500, 300, 100, 0, 0, 0, 0], dtype=np.float64)
    assert routing.route_reach(inflow, length_ft=200_000.0, dt_hr=0.1, **geom).subreaches == n
    # A committed-scale reach is nowhere near the cap.
    normal = routing.subreach_count(
        12000.0, length_ft=82000.0, dt_hr=0.1, **(geom | {"slope": 0.001})
    )
    assert 1 < normal < routing._MAX_SUBREACHES


def test_route_reach_passthrough_on_zero_inflow() -> None:
    # A dry reach (no peak to derive celerity from) passes through: one sub-reach, zero Courant.
    rr = routing.route_reach(np.zeros(50), length_ft=1000.0, slope=0.001)
    assert rr.subreaches == 1 and rr.courant == 0.0
    assert np.array_equal(rr.outflow_cfs, np.zeros(50))


def test_normal_flow_hydraulics_are_manning_consistent() -> None:
    # WS-12 / #1612: the conveyance screen's uniform-flow primitive. Manning must reproduce the
    # discharge it was solved for, and the reported velocity/shear must follow from that section.
    geom = {"bottom_width_ft": 10.0, "side_slope_z": 2.0, "slope": 0.002, "manning_n": 0.04}
    flow = routing.normal_flow(580.0, **geom)
    q_back = (
        (1.49 / geom["manning_n"])
        * flow.area_sqft
        * flow.hydraulic_radius_ft ** (2.0 / 3.0)
        * math.sqrt(geom["slope"])
    )
    assert q_back == pytest.approx(580.0, rel=1e-3)
    assert flow.velocity_fps == pytest.approx(580.0 / flow.area_sqft)
    assert flow.shear_stress_psf == pytest.approx(62.4 * flow.hydraulic_radius_ft * geom["slope"])
    # It shares normal_depth with the routing parameters, so the two never disagree on stage.
    assert flow.depth_ft == pytest.approx(routing.normal_depth(580.0, **geom))
    # Monotone in discharge — depth, velocity and boundary shear all rise with flow.
    bigger = routing.normal_flow(1000.0, **geom)
    assert bigger.depth_ft > flow.depth_ft
    assert bigger.velocity_fps > flow.velocity_fps
    assert bigger.shear_stress_psf > flow.shear_stress_psf
    # A dry channel is an all-zero state, not a degenerate depth.
    dry = routing.normal_flow(0.0, **geom)
    assert (dry.depth_ft, dry.velocity_fps, dry.shear_stress_psf) == (0.0, 0.0, 0.0)


def test_routing_default_section_constants_are_the_exported_ones() -> None:
    # The conveyance screen must report the SAME trapezoid the routing ran on, so the defaults
    # are named constants rather than repeated literals in each signature.
    assert (routing.DEFAULT_BOTTOM_WIDTH_FT, routing.DEFAULT_SIDE_SLOPE_Z) == (10.0, 2.0)
    inflow = np.array([0, 10, 50, 120, 200, 120, 50, 10, 0, 0, 0, 0], dtype=np.float64)
    explicit = routing.route_reach(
        inflow,
        length_ft=8000.0,
        slope=0.001,
        bottom_width_ft=routing.DEFAULT_BOTTOM_WIDTH_FT,
        side_slope_z=routing.DEFAULT_SIDE_SLOPE_Z,
    )
    assert np.array_equal(
        routing.route_reach(inflow, length_ft=8000.0, slope=0.001).outflow_cfs,
        explicit.outflow_cfs,
    )
