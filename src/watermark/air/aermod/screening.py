"""Wire the Tier-0 emissions inventory into an AERMOD screening deck (#1178).

This is the seam between :mod:`watermark.air.emissions` (permit-certified per-engine rates)
and :mod:`watermark.air.aermod.inp` (the dispersion deck): :func:`build_screening_deck`
pulls the active site's per-engine ``lb/hr`` for a pollutant and emits a minimal single-
source, flat-terrain deck — the acceptance case. The stack geometry is the ``assumption``
default (the permit redacts engine specs as CBI); the emission rate is grounded.
"""

from __future__ import annotations

from watermark.air.aermod.inp import build_aermod_inp, genset_point_source
from watermark.air.aermod.model import AermodControl, AveragePeriod, ReceptorGrid
from watermark.air.emissions import load_emission_factors
from watermark.air.model import FactorBasis, LoadRegime, Pollutant
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)


def build_screening_deck(
    *,
    pollutant: Pollutant = "NOx",
    basis: FactorBasis = "permit",
    load_regime: LoadRegime = "load",
    averaging_periods: tuple[AveragePeriod, ...] = ("1", "ANNUAL"),
    grid_half_extent_m: float = 2500.0,
    grid_spacing_m: float = 100.0,
    surface_file: str = "canned.sfc",
    profile_file: str = "canned.pfl",
    settings: Settings | None = None,
) -> tuple[str, dict[str, str]] | None:
    """Build a single-source screening ``aermod.inp`` for the active site.

    Returns ``(inp_text, plotfiles)`` where ``plotfiles`` maps each averaging period to its
    ``OU PLOTFILE`` name, or ``None`` if the site has no documented facility (no fleet) or
    the requested pollutant isn't grounded on the chosen basis. Models **one** representative
    genset at the certified per-engine rate — flat terrain, canned met — the minimal
    end-to-end acceptance run.
    """
    settings = settings or get_settings()
    factors = load_emission_factors(basis=basis, load_regime=load_regime, settings=settings)
    if factors is None:
        log.info("aermod.screening.no_facility", site=settings.site)
        return None
    ef = factors.factor(pollutant)
    if ef is None:
        log.info("aermod.screening.pollutant_ungrounded", site=settings.site, pollutant=pollutant)
        return None

    source = genset_point_source(
        src_id="GEN1",
        pollutant=pollutant,
        per_engine_lb_per_hr=ef.per_engine_hour.value,
        rate_citation=f"{factors.basis} per-engine {pollutant} at {factors.load_regime} load",
    )
    control = AermodControl(
        title=f"Watermark AERMOD screening: {settings.site} {pollutant} ({factors.basis})",
        pollutant=pollutant,
        averaging_periods=averaging_periods,
        terrain="FLAT",
    )
    grid = ReceptorGrid.centered(half_extent_m=grid_half_extent_m, spacing_m=grid_spacing_m)
    plotfiles: dict[str, str] = {str(ave): f"{ave.lower()}.plt" for ave in averaging_periods}
    inp_text = build_aermod_inp(
        control=control,
        sources=[source],
        grid=grid,
        surface_file=surface_file,
        profile_file=profile_file,
        plotfiles=plotfiles,
    )
    return inp_text, plotfiles
