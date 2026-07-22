"""WS-23 / #1623: the cited Tier-0 solver constants + their per-call override seam.

The load-bearing physics/screening constants (SCS peak factor, initial-abstraction ratio,
default Manning n, dilution bands) are externalized to the cited reference layer
(`tier0-parameters.yaml`), read through `watermark.hydrology.solver.parameters`, and each
solver function exposes an override. These tests pin the reference values, prove the override
wins over the table, reject an invalid reference file, and lock the right-sized (2-sig-fig)
reported peak. Settings-backed calls take the hermetic `hydro_settings` fixture.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from watermark.config import Settings
from watermark.hydrology.models._lowflow import DILUTION_TIGHT, DILUTION_VIOLATION
from watermark.hydrology.solver import parameters as params
from watermark.hydrology.solver import routing
from watermark.hydrology.solver.curve_number import excess_rainfall
from watermark.hydrology.solver.rainfall import scs_type_ii_hyetograph
from watermark.hydrology.solver.runoff import simulate_runoff


def _committed_table(settings: Settings) -> dict:
    path = Path(settings.data_dir) / "reference" / "hydrology" / "tier0-parameters.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_params(root: Path, **overrides: float) -> Settings:
    """Write a tier0-parameters.yaml under ``root`` (a data_dir), overriding named values."""
    vals: dict[str, float] = {
        "peak_factor": 484,
        "ia": 0.2,
        "manning_n": 0.04,
        "violation": 1.0,
        "tight": 10.0,
    }
    vals.update(overrides)
    ref = root / "reference" / "hydrology"
    ref.mkdir(parents=True)
    (ref / "tier0-parameters.yaml").write_text(
        f"runoff:\n"
        f"  peak_factor: {{value: {vals['peak_factor']}}}\n"
        f"  initial_abstraction_ratio: {{value: {vals['ia']}}}\n"
        f"routing:\n"
        f"  manning_n: {{value: {vals['manning_n']}}}\n"
        f"dilution:\n"
        f"  violation_ratio: {{value: {vals['violation']}}}\n"
        f"  tight_ratio: {{value: {vals['tight']}}}\n",
        encoding="utf-8",
    )
    return Settings(data_dir=root)


def test_accessors_return_the_cited_reference_values(hydro_settings: Settings) -> None:
    assert params.peak_factor(settings=hydro_settings) == pytest.approx(484.0)
    assert params.initial_abstraction_ratio(settings=hydro_settings) == pytest.approx(0.2)
    assert params.default_manning_n(settings=hydro_settings) == pytest.approx(0.04)
    assert params.dilution_bands(settings=hydro_settings) == (
        pytest.approx(1.0),
        pytest.approx(10.0),
    )


def test_committed_yaml_is_coupled_to_the_in_code_defaults(hydro_settings: Settings) -> None:
    # The reference file is authoritative; the module defaults (missing-file fallback) and the
    # public DILUTION_* constants must not drift from it.
    table = _committed_table(hydro_settings)
    assert table["runoff"]["peak_factor"]["value"] == params._DEFAULT_PEAK_FACTOR
    assert table["runoff"]["initial_abstraction_ratio"]["value"] == params._DEFAULT_IA_RATIO
    assert table["routing"]["manning_n"]["value"] == params._DEFAULT_MANNING_N
    assert table["dilution"]["violation_ratio"]["value"] == params._DEFAULT_DILUTION_VIOLATION
    assert table["dilution"]["tight_ratio"]["value"] == params._DEFAULT_DILUTION_TIGHT
    # ...and the model-layer screening constants stay pinned to the same cited bands.
    assert table["dilution"]["violation_ratio"]["value"] == DILUTION_VIOLATION
    assert table["dilution"]["tight_ratio"]["value"] == DILUTION_TIGHT


def test_missing_reference_file_falls_back_to_the_cited_defaults(tmp_path: Path) -> None:
    # A data_dir without the file still runs a screen on the documented defaults (no crash).
    empty = Settings(data_dir=tmp_path)
    assert params.peak_factor(settings=empty) == params._DEFAULT_PEAK_FACTOR
    assert params.initial_abstraction_ratio(settings=empty) == params._DEFAULT_IA_RATIO
    assert params.default_manning_n(settings=empty) == params._DEFAULT_MANNING_N
    assert params.dilution_bands(settings=empty) == (
        params._DEFAULT_DILUTION_VIOLATION,
        params._DEFAULT_DILUTION_TIGHT,
    )


def test_present_but_invalid_reference_file_is_rejected(tmp_path: Path) -> None:
    # A present-but-invalid file must fail loudly (not silently accepted / cast) — only a MISSING
    # file falls back to the defaults. A negative roughness trips the Field bound; reversed bands
    # trip the model validator.
    neg = _write_params(tmp_path / "neg", manning_n=-0.04)
    with pytest.raises(ValidationError):
        params.default_manning_n(settings=neg)
    reversed_bands = _write_params(tmp_path / "rev", violation=10.0, tight=1.0)
    with pytest.raises(ValidationError):
        params.dilution_bands(settings=reversed_bands)


def test_round_sig_right_sizes_to_two_significant_figures() -> None:
    assert params.round_sig(578.83) == 580.0
    assert params.round_sig(0.012345) == 0.012
    assert params.round_sig(12.6) == 13.0
    assert params.round_sig(-249.4) == -250.0
    assert params.round_sig(0.0) == 0.0  # zero and non-finite pass through
    assert params.round_sig(3, sig=1) == 3.0


def test_ia_ratio_override_beats_the_table(hydro_settings: Settings) -> None:
    # A smaller initial-abstraction ratio (the Hawkins lambda=0.05 convention) abstracts less,
    # so the same storm yields MORE excess rainfall than the tabled lambda=0.2.
    _, cumulative, _ = scs_type_ii_hyetograph(2.0, dt_hr=0.1)
    default = float(excess_rainfall(cumulative, 80.0, settings=hydro_settings)[-1])
    low_ia = float(excess_rainfall(cumulative, 80.0, ia_ratio=0.05, settings=hydro_settings)[-1])
    assert low_ia > default > 0.0


def test_peak_factor_override_beats_the_table(hydro_settings: Settings) -> None:
    # The UH peak scales with the peak factor, so a larger factor raises the reported peak.
    common = {
        "area_acres": 200.0,
        "curve_number": 88.0,
        "tc_hr": 0.75,
        "storm_depth_in": 4.0,
        "settings": hydro_settings,
    }
    tabled = simulate_runoff(**common)
    steep = simulate_runoff(**common, peak_factor=600.0)
    flat = simulate_runoff(**common, peak_factor=300.0)
    assert flat.peak_cfs < tabled.peak_cfs < steep.peak_cfs


def test_manning_n_override_beats_the_table(hydro_settings: Settings) -> None:
    # A rougher channel (higher n) routes differently from the tabled 0.04 default.
    inflow = np.array([0, 10, 50, 120, 200, 120, 50, 10, 0, 0, 0, 0], dtype=np.float64)
    tabled = routing.route(
        inflow, length_ft=8000.0, slope=0.001, dt_hr=0.1, settings=hydro_settings
    )
    rough = routing.route(
        inflow, length_ft=8000.0, slope=0.001, dt_hr=0.1, manning_n=0.1, settings=hydro_settings
    )
    assert not np.allclose(tabled, rough)


def test_reported_peak_is_stored_to_two_significant_figures(hydro_settings: Settings) -> None:
    # The reported scalar peak is right-sized (a Tier-0 screen's inputs are ~2 sig figs); the
    # physics-bearing flows series keeps full precision (it feeds volume and downstream routing).
    h = simulate_runoff(
        area_acres=340.0, curve_number=86.0, tc_hr=0.6, storm_depth_in=4.5, settings=hydro_settings
    )
    assert h.peak_cfs == params.round_sig(h.peak_cfs)  # already 2 sig figs
    assert h.peak_cfs == pytest.approx(max(h.flows_cfs), rel=0.05)  # ~= the true series max (2 sf)
