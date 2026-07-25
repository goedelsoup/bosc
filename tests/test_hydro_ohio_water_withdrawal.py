"""Ohio DNR WWFRP water-withdrawal connector — offline fixture replay (hermetic).

The makeup-side source for the cooling-water account (#1677 / epic #1676). Everything
here replays the committed Allen County (Lima) fixture; nothing touches the network.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.connectors._cache import cache_key
from watermark.hydrology.connectors import ohio_water_withdrawal as oww
from watermark.hydrology.connectors._cache import HydroOfflineError


def test_fetch_county_registry(hydro_settings: Settings) -> None:
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    assert reg.county == "Allen"
    assert reg.state == "OH"
    assert reg.since_year == 2015
    assert reg.source_url.endswith("/FeatureServer/0")
    assert len(reg.facilities) == 33
    # Facilities come back registration-number sorted.
    regs = [f.registration_number for f in reg.facilities]
    assert regs == sorted(regs)


def test_registry_fields_verbatim(hydro_settings: Settings) -> None:
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    by = {f.registration_number: f for f in reg.facilities}

    refinery = by["00386"]
    assert refinery.name == "LIMA REFINING COMPANY"
    assert refinery.primary_use_type == "Industry"
    assert refinery.status == "Active"
    assert refinery.county == "ALLEN"
    assert refinery.latitude is not None and refinery.longitude is not None
    # An epoch-ms registration date is rendered as an ISO calendar date, not raw millis.
    assert refinery.registration_date is not None
    assert len(refinery.registration_date) == 10 and refinery.registration_date[4] == "-"


def test_ground_vs_surface_series_are_distinct(hydro_settings: Settings) -> None:
    """Regression guard for the layer-in-cache-key fix.

    A ground-water-only registrant (Lima Refining) must carry a ground-water series and an
    *empty* surface-water one; a surface-water-only registrant (Lima City PWS-Auglaize) the
    reverse. If the three totals-table queries collided on one cache key (the layer lives in
    the URL, not the query string), every facility would show the same table's rows.
    """
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    by = {f.registration_number: f for f in reg.facilities}

    refinery = by["00386"]  # ground water only
    assert refinery.ground_water and not refinery.surface_water

    pws = by["01320"]  # Lima City PWS-Auglaize — surface water only
    assert pws.surface_water and not pws.ground_water


def test_layer_is_part_of_the_cache_key() -> None:
    """The bug the test above guards, at the cache-key layer: same query, different table."""
    base = {
        "where": "RegistrationNumber IN ('00386') AND Year >= 2015",
        "outFields": "*",
        "resultOffset": 0,
        "resultRecordCount": 2000,
    }
    assert cache_key({"layer": oww.OHIO_WWFRP_SW_TABLE, **base}) != cache_key(
        {"layer": oww.OHIO_WWFRP_GW_TABLE, **base}
    )


def test_withdrawal_amounts_and_mean_daily(hydro_settings: Settings) -> None:
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    by = {f.registration_number: f for f in reg.facilities}

    pws = by["01320"]  # Lima City PWS-Auglaize
    twenty24 = next(a for a in pws.surface_water if a.year == 2024)
    assert twenty24.total_mg == pytest.approx(6113.0)
    # 12 monthly values, keyed uppercase; a blank month is a genuine None, not 0.
    assert set(twenty24.monthly_mg) == {
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    }
    # Million gallons / days-in-year -> MGD (2024 is a leap year: 366 days).
    assert pws.mean_daily_withdrawal_mgd(2024) == pytest.approx(6113.0 / 366, rel=1e-6)
    # Default year is the most recent reported year.
    assert pws.mean_daily_withdrawal_mgd() == pws.mean_daily_withdrawal_mgd(
        max(pws.reported_years())
    )


def test_return_can_exceed_withdrawal_and_is_preserved(hydro_settings: Settings) -> None:
    """The return>withdrawal anomaly is kept verbatim — the connector never reconciles it away."""
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    pcs = next(f for f in reg.facilities if f.registration_number == "01769")  # PCS Nitrogen
    withdrawn = pcs.withdrawal_total_mg(2024)
    returned = pcs.return_total_mg(2024)
    assert withdrawn == pytest.approx(1128.67)
    assert returned == pytest.approx(1236.42)
    assert returned > withdrawn  # a real DNR-record anomaly, left for the A3 reconciliation


def test_makeup_feeds_it_load_inversion(hydro_settings: Settings) -> None:
    """The #1677 seam: a reported withdrawal feeds it_load_mw_from_once_through_withdrawal.

    Round-trip a facility's reported MGD through the once-through inversion and back through
    the forward derivation — this guards the shared unit chain the two functions ride.
    """
    from watermark.hydrology.cooling_models import (
        CoolingParams,
        _derive_once_through,
        it_load_mw_from_once_through_withdrawal,
    )

    reg = oww.fetch_county("Allen", settings=hydro_settings)
    pcs = next(f for f in reg.facilities if f.registration_number == "01769")
    mgd = pcs.mean_daily_withdrawal_mgd(2024)
    assert mgd is not None and mgd > 0

    mw = oww.implied_it_load_mw(mgd)
    # The wrapper is exactly the cooling-model inversion — no drift.
    assert mw == pytest.approx(it_load_mw_from_once_through_withdrawal(mgd))

    # Forward once-through derivation from that IT load reproduces the withdrawal
    # (makeup_demand is rounded to 2 dp in the derivation, so compare at that grain).
    basis = _derive_once_through(None, CoolingParams(it_load_mw=mw), hydro_settings)
    assert basis.makeup_demand.value == pytest.approx(mgd, abs=0.01)


def test_fetch_facility_by_registration_number(hydro_settings: Settings) -> None:
    fac = oww.fetch_facility("00386", settings=hydro_settings)
    assert fac is not None
    assert fac.name == "LIMA REFINING COMPANY"
    assert fac.ground_water  # series attached


def test_offline_unknown_county_raises(hydro_settings: Settings) -> None:
    # No committed fixture for a county nobody pulled -> an actionable offline miss.
    with pytest.raises(HydroOfflineError):
        oww.fetch_county("Cuyahoga", settings=hydro_settings)


def test_write_registry_is_deterministic(hydro_settings: Settings, tmp_path) -> None:
    reg = oww.fetch_county("Allen", settings=hydro_settings)
    first = oww.write_registry(reg, tmp_path / "a")
    second = oww.write_registry(reg, tmp_path / "b")
    assert first.read_bytes() == second.read_bytes()
    assert first.name == "allen.yaml"


def test_county_slug() -> None:
    assert oww.county_slug("Allen") == "allen"
    assert oww.county_slug("Allen County, OH") == "allen"
    assert oww.county_slug("Van Wert County, OH") == "van-wert"


def test_days_in_year() -> None:
    assert oww._days_in_year(2024) == 366  # leap
    assert oww._days_in_year(2023) == 365
    assert oww._days_in_year(2000) == 366  # divisible by 400
    assert oww._days_in_year(1900) == 365  # divisible by 100, not 400
