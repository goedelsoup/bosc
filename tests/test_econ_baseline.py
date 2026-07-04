"""Economics baseline: the QCEW connector replays offline fixtures, builds a sector
mix with location quotients, and an offline cache miss raises (no silent network).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors import OfflineError
from watermark.economics.baseline import (
    _POP_YEARS,
    _maybe_population,
    build_baseline,
    load_baseline,
)
from watermark.economics.connectors.census import fetch_population_series
from watermark.economics.connectors.qcew import (
    QcewError,
    _reduce_csv,
    fetch_county_industries,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def test_qcew_connector_offline(econ_settings: Settings) -> None:
    ie = fetch_county_industries(year=2023, fips="39003", settings=econ_settings)
    assert ie.year == 2023 and ie.fips == "39003"
    assert ie.total_employment.value > 0
    assert ie.total_employment.verified  # connector-sourced
    # Manufacturing is a real, dominant, export-oriented sector here.
    mfg = next(s for s in ie.sectors if s.naics == "31-33")
    assert mfg.location_quotient is not None and mfg.location_quotient.value > 1.5
    # Sectors are ranked by employment.
    emps = [s.annual_avg_employment.value for s in ie.sectors]
    assert emps == sorted(emps, reverse=True)


def test_qcew_surfaces_wages(econ_settings: Settings) -> None:
    """QCEW wages ride along on the county total and each sector (issue #1109), and a
    sector with no covered wages omits pay rather than asserting a fabricated $0."""
    ie = fetch_county_industries(year=2023, fips="39003", settings=econ_settings)
    # County-wide average pay (all ownerships) is surfaced and connector-sourced.
    assert ie.avg_annual_pay is not None
    assert ie.avg_annual_pay.value > 0 and ie.avg_annual_pay.unit == "USD/year"
    assert ie.avg_annual_pay.verified
    assert ie.avg_weekly_wage is not None and ie.avg_weekly_wage.unit == "USD/week"
    # A dominant sector carries per-sector pay.
    mfg = next(s for s in ie.sectors if s.naics == "31-33")
    assert mfg.avg_annual_pay is not None and mfg.avg_annual_pay.value > 0
    # Pay is never surfaced as a fabricated $0 — a suppressed/zero-wage slice is omitted.
    assert all(s.avg_annual_pay is None or s.avg_annual_pay.value > 0 for s in ie.sectors)


def test_reduce_csv_keeps_wage_columns() -> None:
    """`_reduce_csv` selects the wage columns by name, on both the total and sector rows."""
    csv = (
        "own_code,agglvl_code,industry_code,annual_avg_emplvl,annual_avg_estabs,"
        "avg_annual_pay,annual_avg_wkly_wage,lq_annual_avg_emplvl\n"
        "0,70,10,50000,2500,55000,1050,1.0\n"
        "5,74,31-33,8000,140,92000,1770,2.0\n"
    )
    reduced = _reduce_csv(csv)
    assert reduced["total"]["pay"] == 55000.0 and reduced["total"]["wkly"] == 1050.0
    assert reduced["sectors"][0]["pay"] == 92000.0 and reduced["sectors"][0]["wkly"] == 1770.0


def test_census_population_offline(econ_settings: Settings) -> None:
    series = fetch_population_series(years=[2010, 2023], fips="39003", settings=econ_settings)
    assert series.fips == "39003" and series.area_name == "Allen County, Ohio"
    assert [p.year for p in series.points] == [2010, 2023]
    assert all(p.population.verified for p in series.points)  # connector-sourced
    # Allen County's population declined over the span (the documented trend).
    assert series.points[-1].population.value < series.points[0].population.value


def test_build_baseline_trend(econ_settings: Settings) -> None:
    baseline = build_baseline(years=[2018, 2023], settings=econ_settings)
    assert [t.year for t in baseline.trend] == [2018, 2023]
    assert baseline.latest.year == 2023
    assert baseline.latest.sectors
    # Population is folded in from the committed ACS5 fixtures (offline).
    assert baseline.population is not None
    assert len(baseline.population.points) == 4


def test_build_baseline_default_span_is_a_decade_with_establishments(
    econ_settings: Settings,
) -> None:
    """The default span is a real ~decade trend (issue #1111), and each trend point carries
    QCEW establishments alongside employment — all served offline from committed fixtures."""
    baseline = build_baseline(settings=econ_settings)  # default years
    years = [t.year for t in baseline.trend]
    assert years == sorted(years) and len(years) >= 10  # a decade-plus, not two points
    assert baseline.latest.year == years[-1]
    # Establishments are carried on every trend point (not just the latest sector mix).
    assert all(t.establishments is not None and t.establishments.value > 0 for t in baseline.trend)


def test_offline_miss_raises(econ_settings: Settings) -> None:
    with pytest.raises(OfflineError):
        fetch_county_industries(year=1999, fips="39003", settings=econ_settings)


def test_keyless_live_serves_warm_census_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (#1108): a keyless *live* population pull still consults the on-disk cache.

    A live ACS5 fetch needs a key, but a warm cache hit doesn't (the key isn't part of the
    cache key). Priming the live cache and forbidding the network proves the keyless path is
    served from cache, not dropped to ``None``.
    """
    cache_dir = tmp_path / "cache" / "economics" / "census"
    cache_dir.mkdir(parents=True)
    now = datetime.now(UTC).isoformat()
    for fx in sorted((FIXTURES / "economics" / "census").glob("*.json")):
        record = json.loads(fx.read_text(encoding="utf-8"))
        record["fetched_at"] = now  # fresh, so live mode returns the cache hit without fetching
        (cache_dir / fx.name).write_text(json.dumps(record), encoding="utf-8")

    # Live mode, no key: any network attempt must fail the test.
    settings = Settings(data_dir=tmp_path, econ_offline=False, census_api_key="", econ_fips="39003")

    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("keyless live path must be served from the warm cache, not network")

    monkeypatch.setattr("watermark.economics.connectors.census.httpx.get", _no_network)

    series = _maybe_population(settings)
    assert series is not None
    assert [p.year for p in series.points] == _POP_YEARS


def test_keyless_live_cache_miss_fails_fast_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A keyless live fetch with a cold cache fails fast (no network), and the baseline
    degrades to ``None`` rather than attempting a keyless ACS5 request that would fail."""
    settings = Settings(data_dir=tmp_path, econ_offline=False, census_api_key="", econ_fips="39003")

    def _no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("keyless live fetch must fail fast before touching the network")

    monkeypatch.setattr("watermark.economics.connectors.census.httpx.get", _no_network)

    assert _maybe_population(settings) is None


def test_qcew_missing_county_total_raises_not_fabricates_zero(
    econ_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A payload without the county-total row (CSV drift / mistyped FIPS / empty upstream)
    must raise, not manufacture a `[verified]` zero-employment claim from missing data
    (issue #1102) — symmetric with the EIA connector's empty-payload guard."""
    from watermark.economics.connectors import qcew

    # `_reduce_csv` drops the total to `{}` when no all-ownership, all-industry row exists.
    reduced = _reduce_csv("own_code,agglvl_code,annual_avg_emplvl\n5,74,100\n")
    assert reduced["total"] == {}

    monkeypatch.setattr(qcew, "cached_get", lambda *a, **k: reduced)
    with pytest.raises(QcewError, match="no county-total employment row"):
        fetch_county_industries(year=2023, fips="39003", settings=econ_settings)


def test_committed_baseline_loads() -> None:
    """The committed reference YAML round-trips into the model (what the site reads)."""
    baseline = load_baseline(Settings(data_dir=REPO_ROOT / "data"))
    assert baseline is not None
    assert baseline.fips == "39003"
    assert baseline.latest.sectors
