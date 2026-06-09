"""Tier-1 SWMM: .inp builders (always) + engine runs (skipped if SWMM unavailable)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bosc.config import Settings
from bosc.hydrology.swmm import engine, inp

_SWMM = engine.swmm_available()
_needs_swmm = pytest.mark.skipif(not _SWMM, reason="SWMM engine (pyswmm) not loadable here")


# --- .inp builders: no engine needed ---


def test_stormwater_inp_has_required_sections() -> None:
    text, outfall, _orifice, _storage = inp.stormwater_inp(
        area_acres=100.0, pct_imperv=90.0, depth_in=4.0
    )
    for section in (
        "[SUBCATCHMENTS]",
        "[INFILTRATION]",
        "[OUTFALLS]",
        "[RAINGAGES]",
        "[TIMESERIES]",
    ):
        assert section in text
    assert outfall in text
    # No detention requested -> no storage/orifice sections.
    assert "[STORAGE]" not in text


def test_stormwater_inp_with_detention_adds_storage_and_orifice() -> None:
    det = inp.DetentionGeom(basin_area_ft2=50_000.0, max_depth_ft=10.0, orifice_diam_ft=2.0)
    text, _outfall, orifice, storage = inp.stormwater_inp(
        area_acres=100.0, pct_imperv=90.0, depth_in=4.0, detention=det
    )
    assert "[STORAGE]" in text and "[ORIFICES]" in text and "[XSECTIONS]" in text
    assert storage in text and orifice in text


def test_sanitary_inp_has_dwf_and_rdii() -> None:
    text, wwtp = inp.sanitary_inp(base_mgd=2.5, sewershed_acres=300.0, rdii_r=0.05, depth_in=4.0)
    assert "[DWF]" in text and "[RDII]" in text and "[HYDROGRAPHS]" in text
    assert wwtp in text


def test_hyetograph_timeseries_conserves_depth() -> None:
    # Sum of (intensity * dt) over the lines should recover the storm depth.
    dt = 0.1
    lines = inp._hyetograph_lines("TS1", 4.0, dt)
    total = sum(float(ln.split()[-1]) * dt for ln in lines)
    assert total == pytest.approx(4.0, abs=1e-6)


# --- engine runs ---


@_needs_swmm
def test_engine_runs_minimal_storm() -> None:
    text, outfall, _o, _s = inp.stormwater_inp(area_acres=50.0, pct_imperv=80.0, depth_in=3.0)
    res = engine.simulate(text, nodes=[outfall])
    assert res.available
    assert res.node_peak_cfs[outfall] > 0
    assert abs(res.continuity_error_pct) < 5.0  # mass-balance sane


@_needs_swmm
def test_detention_attenuates_peak() -> None:
    common = {"area_acres": 100.0, "pct_imperv": 90.0, "depth_in": 4.0}
    undet, out, _o, _s = inp.stormwater_inp(**common)
    free_peak = engine.simulate(undet, nodes=[out]).node_peak_cfs[out]
    det = inp.DetentionGeom(
        basin_area_ft2=100 * 43560 * 0.05, max_depth_ft=12.0, orifice_diam_ft=1.5
    )
    dtext, out, _orf, sto = inp.stormwater_inp(detention=det, **common)
    res = engine.simulate(dtext, nodes=[out], storages=[sto])
    assert res.node_peak_cfs[out] < free_peak  # the basin attenuates
    assert res.storage_peak_acft[sto] > 0


@_needs_swmm
def test_run_tier1_sizes_detention_and_flags_surcharge() -> None:
    from bosc.hydrology.tier1 import run_tier1

    settings = Settings(
        data_dir=Path(__file__).resolve().parents[1] / "data",
        hydro_offline=True,
        hydro_fixtures_dir=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "hydrology",
    )
    result = run_tier1(return_period_yr=25, settings=settings, live=True)
    assert result.available
    d = result.detention
    assert d is not None
    # Paving raises the peak; the sized basin holds the release near the pre-dev rate.
    assert d.post_peak_cfs > d.pre_peak_cfs
    assert d.controlled_peak_cfs == pytest.approx(d.pre_peak_cfs, rel=0.15)
    assert d.required_storage_acft > 0
    # The committed-deck capture: four decks with the engine version recorded.
    assert result.engine.startswith("pyswmm")
    assert {d.name for d in result.decks} == {"pre", "post", "detention", "sanitary"}
    assert all(d.inp_text and d.reports_node for d in result.decks)
    # The surcharge is routing-aware: only campus receivers are judged (no Shawnee II).
    assert "Shawnee II" not in {s.plant for s in result.surcharge}
    assert all(s.forcemain == "FM-1" for s in result.surcharge)
    # The documented small plants are surcharged by the wet-weather peak.
    assert any(s.exceeds for s in result.surcharge)
    am2 = next(s for s in result.surcharge if "American II" in s.plant)
    assert am2.capacity.source == "document" and am2.wet_weather_peak.source == "derived"
    # Grounded sanitary basis: per-plant headroom (peak - avg) drives the comparison.
    assert result.sanitary_basis is not None
    assert am2.avg_design_flow is not None and am2.avg_design_flow.source == "document"
    assert am2.peaking_factor is not None and am2.peaking_factor.source == "derived"
    assert am2.headroom_mgd == pytest.approx(
        am2.capacity.value - am2.avg_design_flow.value, abs=0.01
    )
    # The regulatory SSO-mandate context surfaces as a finding.
    from bosc.hydrology.tier1 import tier1_findings

    assert any(f.check == "sso-mandate" for f in tier1_findings(result))
