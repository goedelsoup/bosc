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
    write_baseline,
)
from watermark.economics.connectors.census import (
    fetch_median_household_income,
    fetch_population_series,
)
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
    # Pay is never surfaced as a fabricated $0, and a zero-employment sector omits pay entirely
    # (QCEW can report a nonzero avg pay on an emp-0 "Unclassified" slice — "$X pay, 0 jobs").
    for s in ie.sectors:
        assert s.avg_annual_pay is None or s.avg_annual_pay.value > 0
        if s.annual_avg_employment.value == 0:
            assert s.avg_annual_pay is None and s.avg_weekly_wage is None


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


def test_qcew_sets_asof_to_data_year(econ_settings: Settings) -> None:
    """Connector values carry the annual-average year as ``asof`` (issue #1107), so a stale
    baseline is machine-flaggable rather than buried in citation prose."""
    ie = fetch_county_industries(year=2023, fips="39003", settings=econ_settings)
    assert ie.total_employment.asof == "2023"
    assert ie.establishments is not None and ie.establishments.asof == "2023"
    # Wages ride the same data year (issue #1109 + #1107).
    assert ie.avg_annual_pay is not None and ie.avg_annual_pay.asof == "2023"
    # Every sector value (employment, establishments, LQ) is tagged, not just the total.
    for s in ie.sectors:
        assert s.annual_avg_employment.asof == "2023"
        assert s.establishments is None or s.establishments.asof == "2023"
        assert s.location_quotient is None or s.location_quotient.asof == "2023"


def test_census_population_offline(econ_settings: Settings) -> None:
    series = fetch_population_series(years=[2010, 2023], fips="39003", settings=econ_settings)
    assert series.fips == "39003" and series.area_name == "Allen County, Ohio"
    assert [p.year for p in series.points] == [2010, 2023]
    assert all(p.population.verified for p in series.points)  # connector-sourced
    # Allen County's population declined over the span (the documented trend).
    assert series.points[-1].population.value < series.points[0].population.value
    # Each ACS5 point's ``asof`` is its data year (issue #1107).
    assert [p.population.asof for p in series.points] == ["2010", "2023"]


def test_census_median_income_offline(econ_settings: Settings) -> None:
    """The B19013 income pull (#1110) replays offline from its committed fixture, reads the
    value by name, and is connector-sourced with a citation naming the ACS variable."""
    inc = fetch_median_household_income(year=2023, fips="39003", settings=econ_settings)
    assert inc.unit == "USD/yr" and inc.verified  # connector-sourced
    assert 40_000 < inc.value < 100_000  # a sane county median household income
    assert "B19013" in (inc.citation or "") and "Allen County, Ohio" in (inc.citation or "")
    assert inc.asof == "2023"  # ACS vintage carried for staleness, like population (#1107)


def test_build_baseline_folds_median_income(econ_settings: Settings) -> None:
    """The baseline carries median household income (Census B19013) alongside population (#1110)."""
    baseline = build_baseline(years=[2018, 2023], settings=econ_settings)
    assert baseline.median_household_income is not None
    assert baseline.median_household_income.unit == "USD/yr"
    assert baseline.median_household_income.verified
    assert "B19013" in baseline.note


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
    # The committed baseline carries median household income (#1110) — the energy-burden input.
    assert baseline.median_household_income is not None
    assert baseline.median_household_income.value > 0


def test_build_baseline_preserves_population_on_keyless_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-run without a Census key must not drop a previously-committed population series
    (``baseline.py``: "A failed re-run must not drop real data"). When the live ACS5 pull
    can't be satisfied and nothing is warm in the cache, ``build_baseline`` carries the
    committed population over — marking the note as a (possibly stale) carry-forward — rather
    than overwriting the real series with ``null``.
    """
    settings = Settings(
        data_dir=tmp_path, econ_offline=True, econ_fixtures_dir=FIXTURES / "economics"
    )
    # First run: population folded in from the committed ACS5 fixtures, then committed to disk.
    first = build_baseline(years=[2018, 2023], settings=settings)
    assert first.population is not None
    write_baseline(first, settings=settings)

    # Re-run with the population pull unsatisfiable (keyless live miss / offline miss / Census
    # error) — the branch that must preserve the committed series rather than drop it.
    monkeypatch.setattr("watermark.economics.baseline._maybe_population", lambda _s: None)
    rerun = build_baseline(years=[2018, 2023], settings=settings)

    # The committed series is preserved verbatim — not dropped to ``None``, not fabricated.
    assert rerun.population == first.population
    # ...and the provenance note is honest that it's carried over (possibly stale), not fresh.
    assert "carried" in rerun.note.lower()


def test_non_lima_baseline_write_load_roundtrip(tmp_path: Path) -> None:
    """A non-Lima profile round-trips through its own slug-scoped baseline path (#326/#606):
    ``write_baseline`` lands under ``reference/economics/<slug>/baseline.yaml`` and
    ``load_baseline`` reads it back — without touching Lima's un-slugged legacy path.
    """
    # A valid baseline payload — the committed Lima model; its content is irrelevant to the
    # per-site path resolution this test exercises.
    payload = load_baseline(Settings(data_dir=REPO_ROOT / "data"))
    assert payload is not None

    findlay = Settings(data_dir=tmp_path, site="findlay")
    written = write_baseline(payload, settings=findlay)
    # Slug-scoped, not the Lima legacy path.
    assert written.endswith("reference/economics/findlay/baseline.yaml")
    assert (tmp_path / "reference" / "economics" / "findlay" / "baseline.yaml").is_file()
    # Lima's un-slugged path is never written (no clobber of the reference build).
    assert not (tmp_path / "reference" / "economics" / "baseline.yaml").exists()

    # Round-trips back through the findlay profile...
    assert load_baseline(findlay) == payload
    # ...and a Lima-profile read of the same data dir finds nothing (per-site path isolation).
    assert load_baseline(Settings(data_dir=tmp_path, site="lima")) is None
