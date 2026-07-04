"""Assemble the localized economic baseline and persist it as committed reference.

``build_baseline`` pulls BLS QCEW for a set of years (live or offline-from-fixture),
keeps the latest year's full sector mix and a total-employment trend across years.
``write_baseline`` dumps it to ``data/reference/economics/baseline.yaml`` (regenerable
via ``watermark economics``); ``load_baseline`` reads that committed artifact for the site
build, so the site never needs a live pull.
"""

from __future__ import annotations

import httpx
import yaml

from watermark.config import Settings, get_settings
from watermark.connectors import OfflineError
from watermark.economics.connectors.census import (
    CensusError,
    fetch_median_household_income,
    fetch_population_series,
)
from watermark.economics.connectors.qcew import fetch_county_industries
from watermark.economics.model import EconomicBaseline, PopulationSeries, YearTotal
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# QCEW annual averages across a ~decade so the trend line is real, not two points
# (issue #1111). 2014 is the earliest year the open-data CSV API serves; the latest
# published annual is 2024. A committed fixture per year keeps offline rebuilds hermetic.
_DEFAULT_YEARS = list(range(2014, 2025))
# Census ACS5 population points — a longer span (the county's slow decline).
_POP_YEARS = [2010, 2015, 2020, 2023]
# Census ACS5 median household income (B19013, #1110) — the latest 5-year vintage.
_INCOME_YEAR = max(_POP_YEARS)


def _maybe_income(settings: Settings) -> ProvenancedValue | None:
    """ACS5 median household income (B19013), best-effort — mirrors :func:`_maybe_population`.

    A live fetch (cache miss) needs ``WATERMARK_CENSUS_API_KEY``; a warm cache/fixture is
    served keyless. Returns ``None`` rather than raising when it can't be satisfied, so the
    baseline (and the derived energy burden) degrade gracefully instead of fabricating income.
    """
    try:
        return fetch_median_household_income(
            year=_INCOME_YEAR, fips=settings.econ_fips, settings=settings
        )
    except (OfflineError, httpx.HTTPError, CensusError) as exc:
        log.warning("econ.income.skipped", error=str(exc).splitlines()[0])
        return None


def _maybe_population(settings: Settings) -> PopulationSeries | None:
    """ACS5 population series, best-effort.

    Always attempts the pull so a warm cache or committed fixture is served without a key
    (it's excluded from the cache key) — a keyless re-run keeps a previously-fetched series
    instead of discarding it. A live fetch (cache miss) requires ``WATERMARK_CENSUS_API_KEY``
    and otherwise fails fast; either way the pull returns ``None`` rather than raising when
    it can't be satisfied (offline miss, missing key, HTTP/Census error), so the baseline
    degrades gracefully (the gap is documented, not fabricated).
    """
    try:
        return fetch_population_series(years=_POP_YEARS, fips=settings.econ_fips, settings=settings)
    except (OfflineError, httpx.HTTPError, CensusError) as exc:
        log.warning("econ.population.skipped", error=str(exc).splitlines()[0])
        return None


def build_baseline(
    *,
    years: list[int] | None = None,
    settings: Settings | None = None,
) -> EconomicBaseline:
    """Pull QCEW for ``years`` and assemble the latest sector mix + employment trend."""
    settings = settings or get_settings()
    years = sorted(years or _DEFAULT_YEARS)
    population = _maybe_population(settings)
    income = _maybe_income(settings)
    population_preserved = False
    income_preserved = False
    if population is None or income is None:
        # A live ACS5 pull couldn't be satisfied (offline miss / missing key / HTTP / Census
        # error) and nothing warm in the cache — preserve the existing committed value rather
        # than overwriting it with null. A failed re-run must not drop real data. Track what's
        # carried over (possibly stale) for an honest note.
        existing = load_baseline(settings)
        if population is None and existing is not None and existing.population is not None:
            population = existing.population
            population_preserved = True
            log.info("econ.population.preserved", fips=settings.econ_fips)
        if income is None and existing is not None and existing.median_household_income is not None:
            income = existing.median_household_income
            income_preserved = True
            log.info("econ.income.preserved", fips=settings.econ_fips)
    # Authoritative per-county label from the Census ACS NAME (e.g. "Hancock County, Ohio");
    # falls back to the active profile's county when the population series is unavailable.
    area_name = (
        population.area_name if population is not None else active_profile(settings).county_name
    )
    industries = [
        fetch_county_industries(
            year=y, fips=settings.econ_fips, area_name=area_name, settings=settings
        )
        for y in years
    ]
    latest = industries[-1]
    trend = [
        YearTotal(
            year=ie.year,
            total_employment=ie.total_employment,
            establishments=ie.establishments,
        )
        for ie in industries
    ]
    log.info(
        "econ.baseline", years=years, sectors=len(latest.sectors), population=population is not None
    )
    if population is None:
        pop_note = (
            "Population-over-time unavailable (no cached/committed ACS5 series and the "
            "live pull could not be reached)."
        )
    elif population_preserved:
        pop_note = (
            "Population carried from the previously committed US Census ACS 5-year "
            "(B01003) baseline — this run's live pull was unavailable, so it may be stale."
        )
    else:
        pop_note = "Population from US Census ACS 5-year (B01003)."
    if income is None:
        income_note = (
            "Median household income unavailable (no cached/committed ACS5 B19013 and the "
            "live pull could not be reached)."
        )
    elif income_preserved:
        income_note = (
            "Median household income carried from the previously committed US Census ACS "
            "5-year (B19013) — this run's live pull was unavailable, so it may be stale."
        )
    else:
        income_note = f"Median household income from US Census ACS 5-year (B19013, {_INCOME_YEAR})."
    # An optional per-site economic-unit caveat (e.g. WPAFB's Greene/Montgomery straddle) — the
    # site's own note, surfaced so a reader of this single-county baseline isn't misled.
    unit_note = active_profile(settings).econ_unit_note
    return EconomicBaseline(
        fips=latest.fips,
        area_name=area_name,
        latest=latest,
        trend=trend,
        population=population,
        median_household_income=income,
        note=(
            "Employment from BLS QCEW (keyless open data). Location quotient = county "
            "sector share / national share (export-orientation; the county-level proxy "
            f"for an import/export ratio). {pop_note} {income_note}"
            + (f" {unit_note}" if unit_note else "")
        ),
    )


def write_baseline(baseline: EconomicBaseline, *, settings: Settings | None = None) -> str:
    """Persist the baseline as committed reference YAML; return the path.

    Per-site (#326 econ): writes the active site's ``baseline_relpath`` (Lima = the legacy
    un-slugged path; a new site slug-scopes it so onboarding never clobbers Lima). The reader
    (``load_baseline``) resolves the same per-site path.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).baseline_relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(baseline.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("econ.baseline.wrote", path=str(path))
    return str(path)


def load_baseline(settings: Settings | None = None) -> EconomicBaseline | None:
    """Read the committed baseline YAML for the active site, or ``None`` if absent.

    Per-site (#606): resolves ``baseline_relpath`` off the active profile so a non-Lima
    export reads its own committed baseline, not Lima's. Absent → the site page is skipped.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).baseline_relpath
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return EconomicBaseline.model_validate(data)
