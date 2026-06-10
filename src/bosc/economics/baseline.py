"""Assemble the localized economic baseline and persist it as committed reference.

``build_baseline`` pulls BLS QCEW for a set of years (live or offline-from-fixture),
keeps the latest year's full sector mix and a total-employment trend across years.
``write_baseline`` dumps it to ``data/reference/economics/baseline.yaml`` (regenerable
via ``bosc economics``); ``load_baseline`` reads that committed artifact for the site
build, so the site never needs a live pull.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from bosc.config import Settings, get_settings
from bosc.connectors import OfflineError
from bosc.economics.connectors.census import CensusError, fetch_population_series
from bosc.economics.connectors.qcew import fetch_county_industries
from bosc.economics.model import EconomicBaseline, PopulationSeries, YearTotal
from bosc.logging import get_logger

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
    industries = [
        fetch_county_industries(year=y, fips=settings.econ_fips, settings=settings) for y in years
    ]
    latest = industries[-1]
    trend = [YearTotal(year=ie.year, total_employment=ie.total_employment) for ie in industries]
    population = _maybe_population(settings)
    log.info(
        "econ.baseline", years=years, sectors=len(latest.sectors), population=population is not None
    )
    pop_note = (
        "Population from US Census ACS 5-year (B01003)."
        if population is not None
        else "Population-over-time needs a Census key (BOSC_CENSUS_API_KEY)."
    )
    return EconomicBaseline(
        fips=latest.fips,
        area_name=latest.area_name,
        latest=latest,
        trend=trend,
        population=population,
        note=(
            "Employment from BLS QCEW (keyless open data). Location quotient = county "
            "sector share / national share (export-orientation; the county-level proxy "
            f"for an import/export ratio). {pop_note}"
        ),
    )


def _reference_path(reference_dir: Path) -> Path:
    return reference_dir / "economics" / "baseline.yaml"


def write_baseline(baseline: EconomicBaseline, *, settings: Settings | None = None) -> str:
    """Persist the baseline as committed reference YAML; return the path."""
    settings = settings or get_settings()
    path = _reference_path(settings.reference_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(baseline.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("econ.baseline.wrote", path=str(path))
    return str(path)


def load_baseline(reference_dir: Path) -> EconomicBaseline | None:
    """Read the committed baseline YAML, or ``None`` if absent (site page then skipped)."""
    path = _reference_path(reference_dir)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return EconomicBaseline.model_validate(data)
