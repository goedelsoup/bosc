"""FAO-56 Penman-Monteith reference ET0 from the committed NASA POWER climatology."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import climate, et
from watermark.hydrology.connectors.nasa_power import ClimatologyParameter, NasaPowerClimatology


def test_et0_from_committed_climatology() -> None:
    clim = climate.load_climatology(settings=Settings())
    assert clim is not None
    e = et.penman_monteith_et0(clim)

    assert e.method.startswith("FAO-56")
    assert len(e.monthly_mm_day) == 12
    # Lima (temperate continental): reference ET0 lands ~900-1200 mm/yr.
    assert 900 < e.annual_mm < 1200
    # Strong seasonality — summer demand far exceeds winter.
    assert e.monthly_mm_day["JUL"] > e.monthly_mm_day["JAN"]
    assert all(v >= 0 for v in e.monthly_mm_day.values())
    # Summer is a precipitation deficit (ET0 > rainfall) — the growing-season pinch.
    precip = clim.get("PRECTOTCORR")
    assert precip is not None
    assert e.monthly_mm_day["JUL"] > precip.monthly["JUL"]


def test_et0_uses_provided_lat_elevation() -> None:
    """Latitude/elevation overrides flow through (radiation depends on latitude)."""
    clim = climate.load_climatology(settings=Settings())
    assert clim is not None
    base = et.penman_monteith_et0(clim)
    # A much lower latitude raises extraterrestrial radiation -> higher ET0.
    tropical = et.penman_monteith_et0(clim, latitude=5.0)
    assert tropical.annual_mm > base.annual_mm


def test_et0_missing_parameter_raises() -> None:
    """A climatology without the radiation term can't yield ET0."""
    thin = NasaPowerClimatology(
        latitude=40.74,
        longitude=-84.11,
        elevation_m=276.0,
        source_title="thin",
        parameters=[
            ClimatologyParameter(
                parameter="T2M",
                units="C",
                longname="t",
                monthly=dict.fromkeys(et._MONTHS, 10.0),
                annual=10.0,
            )
        ],
    )
    with pytest.raises(ValueError, match=r"ALLSKY_SFC_SW_DWN|T2M_MAX|RH2M|WS2M"):
        et.penman_monteith_et0(thin)


def test_reservoir_evaporation_scales_with_area_and_matches_units() -> None:
    et0 = et.Et0Climatology(monthly_mm_day=dict.fromkeys(et._MONTHS, 5.0), annual_mm=1825.0)
    evap = et.reservoir_evaporation_mgd(et0, 1000.0)
    assert set(evap) == set(et._MONTHS)
    # 5 mm/day over 1000 acres = 5 * 1000 * 0.00106906 MG/day.
    assert evap["JUL"] == pytest.approx(5.0 * 1000.0 * 0.00106906, abs=1e-3)
    # Doubling the surface area doubles the loss (modulo 4-dp rounding).
    doubled = et.reservoir_evaporation_mgd(et0, 2000.0)
    assert doubled["JUL"] == pytest.approx(2 * evap["JUL"], abs=1e-3)
    # Days-weighted annual volume (flat 5 mm/day -> 365 * daily MGD).
    assert et.annual_evaporation_mg(evap) == pytest.approx(365 * evap["JAN"], abs=0.2)


def test_open_water_coefficient_scales_the_loss_above_grass_et0() -> None:
    # WS-17 (#1617): a >1 open-water coefficient lifts grass ET0 into the open-water band, so the
    # reservoir loss scales linearly with the coefficient (open water evaporates above grass ET0).
    et0 = et.Et0Climatology(monthly_mm_day=dict.fromkeys(et._MONTHS, 5.0), annual_mm=1825.0)
    grass = et.reservoir_evaporation_mgd(et0, 1000.0)  # coefficient 1.0
    open_water = et.reservoir_evaporation_mgd(et0, 1000.0, coefficient=1.15)
    assert open_water["JUL"] == pytest.approx(1.15 * grass["JUL"], abs=1e-3)
    assert open_water["JUL"] > grass["JUL"]
