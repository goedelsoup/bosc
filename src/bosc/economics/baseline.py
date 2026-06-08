"""Assemble the localized economic baseline and persist it as committed reference.

``build_baseline`` pulls BLS QCEW for a set of years (live or offline-from-fixture),
keeps the latest year's full sector mix and a total-employment trend across years.
``write_baseline`` dumps it to ``data/reference/economics/baseline.yaml`` (regenerable
via ``bosc economics``); ``load_baseline`` reads that committed artifact for the site
build, so the site never needs a live pull.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bosc.config import Settings, get_settings
from bosc.economics.connectors.qcew import fetch_county_industries
from bosc.economics.model import EconomicBaseline, YearTotal
from bosc.logging import get_logger

log = get_logger(__name__)

# QCEW annual averages; latest two-ish points give a recent employment trend.
_DEFAULT_YEARS = [2018, 2023]


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
    log.info("econ.baseline", years=years, sectors=len(latest.sectors))
    return EconomicBaseline(
        fips=latest.fips,
        area_name=latest.area_name,
        latest=latest,
        trend=trend,
        population=None,  # requires a Census API key; see data/reference/economics/README.md
        note=(
            "Employment from BLS QCEW (keyless open data). Location quotient = county "
            "sector share / national share (export-orientation; the county-level proxy "
            "for an import/export ratio). Population-over-time needs a Census key."
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
