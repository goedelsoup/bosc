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
from watermark.economics.connectors.census import CensusError, fetch_population_series
from watermark.economics.connectors.qcew import fetch_county_industries
from watermark.economics.model import EconomicBaseline, PopulationSeries, YearTotal
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# QCEW annual averages; latest two-ish points give a recent employment trend.
_DEFAULT_YEARS = [2018, 2023]
# Census ACS5 population points — a longer span (the county's slow decline).
_POP_YEARS = [2010, 2015, 2020, 2023]


def _maybe_population(settings: Settings) -> PopulationSeries | None:
    """ACS5 population series when a Census key (live) or a committed fixture is available.

    Returns ``None`` rather than raising when no key is set and no fixture exists, so
    the baseline degrades gracefully (the gap is documented, not fabricated).
    """
    if not settings.census_api_key and not settings.econ_offline:
        return None
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
    if population is None:
        # No Census key and no fixture — preserve the existing committed population rather
        # than overwriting it with null. A re-run without a key must not drop real data.
        existing = load_baseline(settings)
        if existing is not None and existing.population is not None:
            population = existing.population
            log.info("econ.population.preserved", fips=settings.econ_fips)
    # Authoritative per-county label from the Census ACS NAME (e.g. "Hancock County, Ohio");
    # falls back to the active profile's county when no Census key/fixture is available.
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
    trend = [YearTotal(year=ie.year, total_employment=ie.total_employment) for ie in industries]
    log.info(
        "econ.baseline", years=years, sectors=len(latest.sectors), population=population is not None
    )
    pop_note = (
        "Population from US Census ACS 5-year (B01003)."
        if population is not None
        else "Population-over-time needs a Census key (WATERMARK_CENSUS_API_KEY)."
    )
    # An optional per-site economic-unit caveat (e.g. WPAFB's Greene/Montgomery straddle) — the
    # site's own note, surfaced so a reader of this single-county baseline isn't misled.
    unit_note = active_profile(settings).econ_unit_note
    return EconomicBaseline(
        fips=latest.fips,
        area_name=area_name,
        latest=latest,
        trend=trend,
        population=population,
        note=(
            "Employment from BLS QCEW (keyless open data). Location quotient = county "
            "sector share / national share (export-orientation; the county-level proxy "
            f"for an import/export ratio). {pop_note}" + (f" {unit_note}" if unit_note else "")
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
