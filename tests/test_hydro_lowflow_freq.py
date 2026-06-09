"""Low-flow frequency analysis: frequency math, climatic-year minima, and the
committed-artifact regression that pins the case's headline 7Q10 (hermetic)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from bosc.config import Settings
from bosc.hydrology import lowflow_frequency as lf
from bosc.hydrology.connectors.nwis import DailyDischargeSeries, fetch_daily_discharge

# ------------------------------------------------------------------------ probit


@pytest.mark.parametrize(
    ("p", "expected"),
    [(0.5, 0.0), (0.975, 1.959964), (0.025, -1.959964), (0.1, -1.281552), (0.9, 1.281552)],
)
def test_probit_matches_known_normal_deviates(p: float, expected: float) -> None:
    assert lf._probit(p) == pytest.approx(expected, abs=1e-4)


def test_probit_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        lf._probit(0.0)
    with pytest.raises(ValueError):
        lf._probit(1.0)


# --------------------------------------------------------------------------- LP3


def test_lp3_median_of_zero_skew_series_is_geometric_mean() -> None:
    # log10-symmetric minima => skew ~ 0 => the p=0.5 quantile is the geometric mean.
    minima = [10**x for x in (-1.0, -0.5, 0.0, 0.5, 1.0)]  # logs symmetric about 0
    q, skew, zero_fraction = lf._lp3_low_quantile(minima, 0.5)
    assert zero_fraction == 0.0
    assert abs(skew) < 1e-6
    assert q == pytest.approx(1.0, rel=1e-6)  # 10 ** mean(log10) = 10**0 = 1


def test_lp3_is_monotone_in_nonexceedance_probability() -> None:
    minima = [0.2, 0.4, 0.6, 0.9, 1.3, 2.0, 2.8, 4.1, 6.0, 9.0]
    q10 = lf._lp3_low_quantile(minima, 0.10)[0]
    q50 = lf._lp3_low_quantile(minima, 0.50)[0]
    q90 = lf._lp3_low_quantile(minima, 0.90)[0]
    assert q10 < q50 < q90


def test_lp3_conditional_zero_handling() -> None:
    # 2 dry years of 12 => p0 = 1/6. Below p0 the quantile is exactly 0; above it, > 0.
    minima = [0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    q_low, _, p0 = lf._lp3_low_quantile(minima, 0.10)
    assert p0 == pytest.approx(1 / 6)
    assert q_low == 0.0  # 0.10 <= p0
    q_hi, _, _ = lf._lp3_low_quantile(minima, 0.30)
    assert q_hi > 0.0  # 0.30 > p0


def test_low_flow_quantiles_wraps_both_estimates() -> None:
    minima = [0.2, 0.4, 0.6, 0.9, 1.3, 2.0, 2.8, 4.1, 6.0, 9.0]
    lp3, weibull, _skew, zero_fraction = lf.low_flow_quantiles(minima, nonexceedance_prob=0.10)
    assert lp3 > 0.0 and weibull > 0.0
    assert zero_fraction == 0.0


# ---------------------------------------------------------------- annual minima


def _full_year_series(low_dips: dict[str, float]) -> DailyDischargeSeries:
    """A full climatic year 2015 (Apr 2015 to Mar 2016) at flow 100, with named dips."""
    by_date: dict[str, float] = {}
    d = date(2015, 4, 1)
    end = date(2016, 3, 31)
    while d <= end:
        by_date[d.isoformat()] = 100.0
        d += timedelta(days=1)
    by_date.update(low_dips)
    items = sorted(by_date.items())
    return DailyDischargeSeries(
        site_no="TEST",
        name="Synthetic",
        unit="ft3/s",
        dates=[k for k, _ in items],
        values_cfs=[v for _, v in items],
    )


def test_annual_minima_grouping_window_and_completeness() -> None:
    # A contiguous 7-day dip to 5.0 in Aug 2015, plus a single 3.0 day in Feb 2016.
    dips = {f"2015-08-{day:02d}": 5.0 for day in range(10, 17)}  # 7 consecutive days
    dips["2016-02-15"] = 3.0  # Jan-Mar => belongs to climatic year 2015
    series = _full_year_series(dips)

    one = lf.annual_nday_minima(series, 1)
    seven = lf.annual_nday_minima(series, 7)

    assert [m.climatic_year for m in one] == [2015]  # Feb 2016 folds into cy2015
    assert one[0].complete is True  # a full year of daily values
    # 1-day min is the isolated Feb low; 7-day min is the contiguous Aug dip.
    assert one[0].min_cfs == pytest.approx(3.0)
    assert seven[0].min_cfs == pytest.approx(5.0)


def test_annual_minima_excludes_short_years() -> None:
    # Only a handful of days => not "complete", excluded from any fit.
    series = DailyDischargeSeries(
        site_no="TEST",
        name="Synthetic",
        unit="ft3/s",
        dates=["2015-07-01", "2015-07-02", "2015-07-03"],
        values_cfs=[9.0, 8.0, 7.0],
    )
    minima = lf.annual_nday_minima(series, 1)
    assert minima and all(m.complete is False for m in minima)


# ----------------------------------------------------------------- connector


def test_fetch_daily_discharge_parses_fixture(hydro_settings: Settings) -> None:
    series = fetch_daily_discharge(
        "04187100", start_date="2021-06-01", end_date="2021-08-31", settings=hydro_settings
    )
    assert len(series) == 92
    assert series.site_no == "04187100"
    assert "Ottawa River at Lima" in series.name
    assert series.dates == sorted(series.dates)  # ascending
    assert series.dates[0] == "2021-06-01" and series.dates[-1] == "2021-08-31"
    assert all(v >= 0 for v in series.values_cfs)


# --------------------------------------------------- committed-artifact regression


def test_committed_low_flow_frequency_reproduces_cited_7q10(hydro_settings: Settings) -> None:
    lff = lf.load_low_flow_frequency(settings=hydro_settings)
    assert lff is not None, "data/reference/hydrology/low-flow-frequency.yaml must be committed"
    assert lff.site_no == "04187100"

    seven = lff.stat("7Q10")
    assert seven is not None
    # The computed 7Q10 lands on the cited regulatory 0.2 cfs (within the screening band).
    assert seven.lp3_cfs.value == pytest.approx(0.24, abs=0.05)
    assert seven.cited_cfs is not None and seven.cited_cfs.value == pytest.approx(0.2)
    assert seven.corroborates is True
    # Every cited statistic corroborates (1Q10 = 0 dry, 30Q10 ~ summer floor).
    assert all(s.corroborates for s in lff.statistics if s.cited_cfs is not None)


def test_recompute_from_committed_minima_is_deterministic(hydro_settings: Settings) -> None:
    lff = lf.load_low_flow_frequency(settings=hydro_settings)
    assert lff is not None
    m7 = [m.min_cfs for m in lff.minima_for(7) if m.complete]
    lp3, _weibull, _skew, _zero = lf.low_flow_quantiles(m7, nonexceedance_prob=0.10)
    # Recomputing from the committed per-year minima yields the stored statistic.
    seven = lff.stat("7Q10")
    assert seven is not None
    assert lp3 == pytest.approx(seven.lp3_cfs.value, abs=1e-3)


def test_computed_low_flow_is_derived_not_document(hydro_settings: Settings) -> None:
    # The computed figure must never masquerade as the cited regulatory statistic.
    lff = lf.load_low_flow_frequency(settings=hydro_settings)
    assert lff is not None
    for s in lff.statistics:
        assert s.lp3_cfs.source == "derived" and not s.lp3_cfs.verified
        assert s.weibull_cfs.source == "derived"
        if s.cited_cfs is not None:
            assert s.cited_cfs.source == "document" and s.cited_cfs.verified


def test_one_q10_is_zero_for_intermittent_mainstem(hydro_settings: Settings) -> None:
    lff = lf.load_low_flow_frequency(settings=hydro_settings)
    assert lff is not None
    one = lff.stat("1Q10")
    assert one is not None
    assert one.lp3_cfs.value == 0.0  # the Ottawa mainstem runs dry at design low flow
    assert one.zero_fraction > 0.0


def test_findings_flag_corroboration(hydro_settings: Settings) -> None:
    lff = lf.load_low_flow_frequency(settings=hydro_settings)
    assert lff is not None
    findings = lf.low_flow_frequency_findings(lff)
    assert findings, "expected one finding per cited statistic"
    assert all(f.ok for f in findings)
    assert any("7Q10" in f.subject for f in findings)
