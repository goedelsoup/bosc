"""SCS solver invariants — the physics that must hold regardless of inputs."""

from __future__ import annotations

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
from watermark.hydrology.solver.rainfall import scs_type_ii_hyetograph
from watermark.hydrology.solver.runoff import simulate_runoff


def test_hyetograph_conserves_mass() -> None:
    _, cumulative, incremental = scs_type_ii_hyetograph(4.0, dt_hr=0.1)
    assert cumulative[-1] == pytest.approx(4.0)
    assert float(incremental.sum()) == pytest.approx(4.0)
    assert np.all(np.diff(cumulative) >= -1e-9)  # monotonic non-decreasing


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
