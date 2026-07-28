"""Groundwater-drawdown screen -- analytic sanity + the Allen dewatering outcome (hermetic).

Runs on the committed Allen census + literature aquifer table; no network. Guards the Theis
math, the scenario provenance discipline (Q is [inference], the cone is bracketed), and the
headline outcome: a hyperscale groundwater pumping stress dewaters the limestone aquifer.
"""

from __future__ import annotations

from math import isclose
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology import drawdown as dd
from watermark.hydrology.aquifer import compute_aquifer_parameters
from watermark.hydrology.connectors import ohio_waterwells as oww

REPO = Path(__file__).resolve().parents[1]
ALLEN_CSV = REPO / "data" / "reference" / "ohio-waterwells" / "allen.csv"


def _params(hydro_settings: Settings):
    inv = oww.read_inventory(ALLEN_CSV, settings=hydro_settings)
    return compute_aquifer_parameters(inv, settings=hydro_settings), inv


# --- pure analytic ----------------------------------------------------------------------


def test_mgd_conversion() -> None:
    assert isclose(dd.mgd_to_ft3_day(1.0), 133680.6, rel_tol=1e-4)


def test_well_function_matches_known_values() -> None:
    """W(u) = E1(u) against canonical tabulated exponential-integral values."""
    assert isclose(dd.well_function(0.1), 1.822924, rel_tol=1e-5)
    assert isclose(dd.well_function(1.0), 0.219384, rel_tol=1e-4)
    assert isclose(dd.well_function(2.0), 0.048901, rel_tol=1e-3)
    assert dd.well_function(0.0) == 0.0


def test_theis_matches_definition() -> None:
    """s = Q/(4*pi*T) * W(u), u = r^2 S / (4 T t)."""
    q, t, s, r, days = 100_000.0, 500.0, 1e-3, 100.0, 10.0
    u = (r * r * s) / (4.0 * t * days)
    expected = q / (4.0 * 3.141592653589793 * t) * dd.well_function(u)
    assert isclose(dd.theis_drawdown(q, t, s, r, days), expected, rel_tol=1e-12)


def test_theis_monotonic_in_radius_and_rate() -> None:
    kw = {"t_ft2_day": 500.0, "storativity": 1e-3, "t_days": 30.0}
    near = dd.theis_drawdown(100_000.0, r_ft=50.0, **kw)
    far = dd.theis_drawdown(100_000.0, r_ft=5000.0, **kw)
    assert near > far > 0  # drawdown decreases with distance
    more = dd.theis_drawdown(200_000.0, r_ft=50.0, **kw)
    assert more > near  # ... and increases with pumping rate


def test_theis_degenerate_inputs_are_zero() -> None:
    assert dd.theis_drawdown(0.0, 500.0, 1e-3, 100.0, 10.0) == 0.0
    assert dd.theis_drawdown(1e5, 500.0, 1e-3, 100.0, 0.0) == 0.0


def test_radius_of_influence_formula() -> None:
    t, s, days = 141.0, 5e-4, 365.0
    assert isclose(
        dd.radius_of_influence_ft(t, s, days), (2.25 * t * days / s) ** 0.5, rel_tol=1e-9
    )


# --- scenario provenance ----------------------------------------------------------------


def test_scenario_pumping_is_an_assumption_bracketed_when_given(hydro_settings: Settings) -> None:
    params, _ = _params(hydro_settings)
    scen = dd.cooling_makeup_scenario(params, makeup_mgd=3.92, low_mgd=2.6, high_mgd=5.2)
    q = scen.pumping_mgd
    assert q.source == "assumption"  # [inference], never documented
    assert q.has_range and q.low is not None and q.low <= q.value <= q.high  # band only when given
    assert "SURFACE water" in q.citation and "[open]" in q.citation


def test_site_scenario_resolves_makeup_from_cooling_basis(hydro_settings: Settings) -> None:
    """The site scenario pulls makeup from the active site's cooling basis — no baked-in value."""
    params, _ = _params(hydro_settings)
    q = dd.site_cooling_makeup_scenario(params, settings=hydro_settings).pumping_mgd
    assert q.value == 3.92 and q.source == "assumption"  # Lima's derived cooling makeup
    assert not q.has_range  # the committed makeup carries no uncertainty band (none fabricated)


# --- the Allen outcome ------------------------------------------------------------------


def test_allen_limestone_dewaters(hydro_settings: Settings) -> None:
    params, inv = _params(hydro_settings)
    r = dd.compute_drawdown(
        params,
        dd.site_cooling_makeup_scenario(params, settings=hydro_settings),
        inventory=inv,
        campus_lat=40.797,
        campus_lon=-84.123,
    )
    assert r.material == "LIMESTONE"
    assert r.dewaters is True and r.sustainable is False
    # Apex drawdown is CAPPED at the saturated thickness (not an unphysical number).
    assert r.drawdown_at_well_ft.value == r.saturated_thickness_ft
    assert r.drawdown_at_well_ft.source == "derived"
    assert r.tag == "inference"
    # The whole cone bracket stays at or below the saturated thickness.
    assert r.drawdown_at_well_ft.high_or_value <= r.saturated_thickness_ft
    # Domestic wells fall within a multi-thousand-foot radius of influence.
    assert r.affected_domestic_wells and r.affected_domestic_wells > 0
    assert r.radius_of_influence_ft.value > 1000


def test_affected_count_grows_with_radius(hydro_settings: Settings) -> None:
    _, inv = _params(hydro_settings)
    near = dd._count_affected_domestic(inv, lat=40.797, lon=-84.123, radius_ft=500.0)
    far = dd._count_affected_domestic(inv, lat=40.797, lon=-84.123, radius_ft=50_000.0)
    assert far >= near
    assert far > 0


def test_dewatering_finding_is_surfaced(hydro_settings: Settings) -> None:
    params, inv = _params(hydro_settings)
    r = dd.compute_drawdown(
        params,
        dd.site_cooling_makeup_scenario(params, settings=hydro_settings),
        inventory=inv,
        campus_lat=40.797,
        campus_lon=-84.123,
    )
    cap = next(f for f in dd.drawdown_findings(r) if f.check == "drawdown-aquifer-capacity")
    assert cap.ok is False  # cannot sustain
    assert "DEWATERS" in cap.detail and "municipal surface water" in cap.detail


def test_sustainable_scenario_does_not_dewater(hydro_settings: Settings) -> None:
    """A small stress on the high-transmissivity gravel aquifer yields a finite cone."""
    params, _ = _params(hydro_settings)
    scen = dd.cooling_makeup_scenario(
        params, makeup_mgd=0.05, low_mgd=0.02, high_mgd=0.1, material="GRAVEL"
    )
    r = dd.compute_drawdown(params, scen)
    assert r.material == "GRAVEL" and r.dewaters is False and r.sustainable is True
    assert 0.0 < r.drawdown_at_well_ft.value < (r.saturated_thickness_ft or 1e9)


def test_load_drawdown_via_active_profile(hydro_settings: Settings) -> None:
    r = dd.load_drawdown(settings=hydro_settings)
    assert r is not None and r.county == "Allen"
    assert r.dewaters is True  # Lima -> Allen limestone, cooling-makeup scenario
    assert len(r.profile) > 2  # a cone profile for the AquiferSection figure


def test_absent_material_raises_not_silent_dominant(hydro_settings: Settings) -> None:
    """A scenario naming an absent material raises -- never silently uses the dominant one."""
    params, _ = _params(hydro_settings)
    scen = dd.cooling_makeup_scenario(
        params, makeup_mgd=1.0, low_mgd=None, high_mgd=None, material="SANDSTONE"
    )
    with pytest.raises(ValueError, match="not present"):
        dd.compute_drawdown(params, scen)


def test_drawdown_cli_completes(hydro_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end CLI: the command runs to exit 0 with no formatting errors on both branches.

    (A ``saturated_thickness_ft is None`` result is unreachable via the API -- transmissivity and
    thickness are coupled in ``aquifer.py`` and ``compute_drawdown`` raises when T is None -- so the
    CLI's None guard is exercised by construction, not through a real screen. Both real branches --
    the site-default dewatering path and a sustainable override with a real thickness -- are run.)
    """
    from typer.testing import CliRunner

    import watermark.cli.hydrology as cli_hydro
    from watermark.cli import app

    monkeypatch.setattr(cli_hydro, "get_settings", lambda: hydro_settings)
    runner = CliRunner()
    dewater = runner.invoke(app, ["drawdown"])  # site cooling makeup -> Allen limestone dewaters
    assert dewater.exit_code == 0, dewater.output
    assert "DEWATERS" in dewater.output
    sustainable = runner.invoke(app, ["drawdown", "--makeup-mgd", "0.05", "--material", "GRAVEL"])
    assert sustainable.exit_code == 0, sustainable.output
