"""SCS solver invariants — the physics that must hold regardless of inputs."""

from __future__ import annotations

import numpy as np
import pytest

from bosc.config import Settings
from bosc.hydrology.solver import routing
from bosc.hydrology.solver.curve_number import (
    adjust_amc,
    cn_for,
    composite_cn,
    excess_rainfall,
    storage_s,
)
from bosc.hydrology.solver.rainfall import scs_type_ii_hyetograph
from bosc.hydrology.solver.runoff import simulate_runoff


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
    assert h.volume_acft == pytest.approx(expected_acft, rel=0.03)  # UH-tail truncation tol


def test_higher_cn_yields_higher_peak() -> None:
    common = {"area_acres": 100.0, "tc_hr": 0.75, "storm_depth_in": 4.0, "dt_hr": 0.1}
    low = simulate_runoff(curve_number=78.0, **common)
    high = simulate_runoff(curve_number=95.0, **common)
    assert high.peak_cfs > low.peak_cfs
    assert high.volume_acft > low.volume_acft


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
