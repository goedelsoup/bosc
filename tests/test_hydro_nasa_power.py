"""NASA POWER climatology connector: offline fixture replay + parsing."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology.connectors import nasa_power
from watermark.hydrology.connectors._cache import HydroOfflineError


def test_climatology_offline(hydro_settings: Settings) -> None:
    clim = nasa_power.fetch_climatology(settings=hydro_settings)

    # Point + provenance.
    assert clim.latitude == pytest.approx(40.74, abs=0.01)
    assert clim.longitude == pytest.approx(-84.11, abs=0.01)
    assert clim.elevation_m is not None and clim.elevation_m > 0
    assert "POWER" in clim.source_title

    # Every requested parameter parsed with 12 monthly normals.
    names = {p.parameter for p in clim.parameters}
    assert {"PRECTOTCORR", "T2M", "ALLSKY_SFC_SW_DWN"} <= names
    precip = clim.get("PRECTOTCORR")
    assert precip is not None
    assert precip.units == "mm/day"
    assert len(precip.monthly) == 12
    assert all(v != -999.0 for v in precip.monthly.values())  # fill dropped

    # Derived helpers — annual depth and seasonality.
    ann = clim.annual_precip_mm()
    assert ann is not None and 800 < ann < 1200  # Lima ~1000 mm/yr
    assert clim.wettest_month() is not None
    assert clim.driest_month() is not None
    t2m = clim.get("T2M")
    assert t2m is not None and t2m.annual is not None and 5 < t2m.annual < 15


def test_offline_unfetched_point_raises(hydro_settings: Settings) -> None:
    with pytest.raises(HydroOfflineError):
        nasa_power.fetch_climatology(lon=0.0, lat=0.0, settings=hydro_settings)


def test_annual_precip_derived_from_monthly(hydro_settings: Settings) -> None:
    """Annual depth is the days-weighted monthly sum, not ANN x 365.25."""
    clim = nasa_power.fetch_climatology(settings=hydro_settings)
    precip = clim.get("PRECTOTCORR")
    assert precip is not None
    expected = sum(precip.monthly[m] * nasa_power._DAYS_IN_MONTH[m] for m in nasa_power._MONTHS)
    assert clim.annual_precip_mm() == pytest.approx(round(expected, 1))


def test_annual_precip_raises_on_ann_unit_drift(hydro_settings: Settings) -> None:
    """If POWER ships ANN as an annual total (not mm/day), the cross-check fails loud."""
    clim = nasa_power.fetch_climatology(settings=hydro_settings)
    precip = clim.get("PRECTOTCORR")
    assert precip is not None
    # Simulate ANN drifting to an annual total (~365x the mm/day rate).
    precip.annual = round(precip.annual * nasa_power._DAYS_PER_YEAR, 1)  # type: ignore[operator]
    with pytest.raises(nasa_power.NasaPowerUnitError):
        clim.annual_precip_mm()


def test_annual_precip_raises_on_monthly_unit_drift(hydro_settings: Settings) -> None:
    """WS-18 (#1618): the monthly block is assumed mm/day — a unit change fails loud."""
    clim = nasa_power.fetch_climatology(settings=hydro_settings)
    precip = clim.get("PRECTOTCORR")
    assert precip is not None
    precip.units = "in/day"  # POWER switching the monthly normal off mm/day
    with pytest.raises(nasa_power.NasaPowerUnitError, match=r"mm/day"):
        clim.annual_precip_mm()
