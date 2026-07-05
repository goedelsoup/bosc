"""Receptor-grid concentration run + NAAQS screen + event-anchored calibration (Tier-1, #1182).

The last mile of the AERMOD integration: take the Tier-0 emissions inventory into a modeled
ground-level **concentration** and compare it to the federal **NAAQS** (the criteria-pollutant
health standards). Two entry points:

- :func:`run_dispersion` — build the site's single-source screening deck
  (:mod:`watermark.air.aermod.screening`), run the located AERMOD binary against an
  operator-supplied canned met pair, and screen the peak concentration per averaging period
  against the NAAQS. Degrades to ``available=False`` (empty screens) when the binary or the
  canned met is absent — exactly as the engine does — so nothing here fabricates a
  concentration.
- :func:`run_calibration_dispersion` — the same run, but **anchored to the captured dispatch
  event** (#1174, via :mod:`watermark.air.calibration`): it models the permit **load**-point
  rate (a real authorized dispatch carries load, so the short-term 1-hr / 8-hr standards are
  the operative ones) and cites the event. The window is `[verified]`; whether *this* facility
  ran stays `[open]` — so the result reports concentrations against the standards **without**
  asserting the fleet actually produced them.

Discipline: this is a **screening** comparison — one source, no monitored background. A modeled
peak under the NAAQS is reassuring; a peak over it flags the need for a full demonstration, not
an automatic violation. The NAAQS themselves are a committed `reference` dataset
(``data/reference/air/naaqs/naaqs.yaml``), tagged `reference`, never `verified`.
"""

from __future__ import annotations

from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.air.aermod.engine import AermodResult
from watermark.air.aermod.engine import run as run_aermod
from watermark.air.aermod.inp import stack_params_from_profile
from watermark.air.aermod.model import AveragePeriod, GensetStackParams
from watermark.air.aermod.screening import build_screening_deck
from watermark.air.calibration import CapturedDispatchEvent, load_captured_event
from watermark.air.model import FactorBasis, LoadRegime, Pollutant
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

# The committed NAAQS reference dataset, relative to ``settings.reference_dir``.
_NAAQS_RELPATH = "air/naaqs/naaqs.yaml"


class NaaqsStandard(BaseModel):
    """One federal ambient standard: our pollutant, the NAAQS species, period, and limit."""

    model_config = ConfigDict(extra="forbid")

    pollutant: str  # our Pollutant label (NOx is screened as NO2)
    naaqs_species: str
    averaging_period: str  # AERMOD AVE token: "1", "8", "24", "ANNUAL", ...
    standard_ug_m3: float
    basis: str


class ConcentrationScreen(BaseModel):
    """A modeled peak concentration for one averaging period, screened against the NAAQS."""

    model_config = ConfigDict(extra="forbid")

    pollutant: str
    averaging_period: str
    max_conc_ug_m3: float  # AERMOD peak-receptor concentration
    naaqs_ug_m3: float | None = None  # the standard, when one exists for this period
    naaqs_species: str | None = None
    naaqs_basis: str | None = None
    pct_of_naaqs: float | None = None
    exceeds_naaqs: bool = False


class DispersionResult(BaseModel):
    """A screened AERMOD concentration run for one pollutant — the #1182 deliverable.

    ``available`` is False (with empty ``screens``) when the AERMOD binary or the canned met
    is absent: the deck + NAAQS table still resolve, but no concentration is fabricated. When
    ``event`` is set the run is the **event-anchored calibration** (the permit load-point rate,
    cited to the captured order); ``event`` is ``None`` for a plain screening run.
    """

    model_config = ConfigDict(extra="forbid")

    site: str
    pollutant: str
    factors_basis: FactorBasis
    load_regime: LoadRegime
    available: bool
    engine_version: str = ""
    source_emission_g_s: float | None = None
    stack: GensetStackParams | None = None
    stack_is_assumption: bool = True
    receptor_grid: dict[str, float] = {}
    averaging_periods: list[str] = []
    screens: list[ConcentrationScreen] = []
    any_naaqs_exceeded: bool = False
    exceeded: list[str] = []
    event: CapturedDispatchEvent | None = None
    caveats: list[str] = []
    note: str = ""


def load_naaqs(*, settings: Settings | None = None) -> list[NaaqsStandard]:
    """The committed NAAQS reference table (all pollutants / averaging periods)."""
    settings = settings or get_settings()
    path = settings.reference_dir / _NAAQS_RELPATH
    if not path.is_file():
        raise FileNotFoundError(f"NAAQS reference dataset missing: {path}")
    data = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    return [NaaqsStandard.model_validate(row) for row in data.get("standards", [])]


def naaqs_for(
    pollutant: Pollutant, averaging_period: str, *, settings: Settings | None = None
) -> NaaqsStandard | None:
    """The NAAQS for one (pollutant, averaging period), or ``None`` if none is defined."""
    for std in load_naaqs(settings=settings):
        if std.pollutant == pollutant and std.averaging_period == averaging_period:
            return std
    return None


def screen_concentrations(
    pollutant: Pollutant,
    max_conc: dict[str, float],
    *,
    settings: Settings | None = None,
) -> list[ConcentrationScreen]:
    """Screen modeled peak concentrations (per averaging period) against the NAAQS.

    ``max_conc`` maps an AERMOD averaging-period token to the peak-receptor concentration
    (µg/m³, e.g. :attr:`watermark.air.aermod.engine.AermodResult.max_conc`). A period with no
    matching NAAQS (e.g. a 1-hr run of a pollutant only capped annually) still reports its
    modeled peak, just with no comparison.
    """
    settings = settings or get_settings()
    table = {
        s.averaging_period: s for s in load_naaqs(settings=settings) if s.pollutant == pollutant
    }
    out: list[ConcentrationScreen] = []
    for ave, conc in max_conc.items():
        std = table.get(ave)
        pct = round(conc / std.standard_ug_m3 * 100.0, 1) if std else None
        out.append(
            ConcentrationScreen(
                pollutant=pollutant,
                averaging_period=ave,
                max_conc_ug_m3=round(conc, 5),
                naaqs_ug_m3=std.standard_ug_m3 if std else None,
                naaqs_species=std.naaqs_species if std else None,
                naaqs_basis=std.basis if std else None,
                pct_of_naaqs=pct,
                exceeds_naaqs=bool(std and conc > std.standard_ug_m3),
            )
        )
    return out


_SCREENING_CAVEAT = (
    "Screening comparison: a single modeled source with NO monitored background concentration "
    "and flat terrain + canned met. A peak below the NAAQS is reassuring; a peak above it flags "
    "the need for a full demonstration (background + cumulative sources), not an automatic "
    "violation."
)


def run_dispersion(
    *,
    pollutant: Pollutant = "NOx",
    basis: FactorBasis = "permit",
    load_regime: LoadRegime = "load",
    averaging_periods: tuple[AveragePeriod, ...] = ("1", "ANNUAL"),
    met_files: dict[str, str] | None = None,
    surface_file: str = "canned.sfc",
    profile_file: str = "canned.pfl",
    grid_half_extent_m: float = 2500.0,
    grid_spacing_m: float = 100.0,
    event: CapturedDispatchEvent | None = None,
    settings: Settings | None = None,
) -> DispersionResult | None:
    """Run the site's screening deck and screen the peak concentrations against the NAAQS.

    Returns ``None`` when the site has no documented facility or the pollutant isn't grounded
    on the chosen basis (nothing to model). When the AERMOD binary or the canned met is absent
    the result carries ``available=False`` and empty ``screens`` — the deck is real, the run
    isn't fabricated. ``met_files`` overrides the ``{surface_file, profile_file}`` contents; if
    omitted, the run is attempted with no met payload (which the absent binary short-circuits).
    """
    settings = settings or get_settings()
    built = build_screening_deck(
        pollutant=pollutant,
        basis=basis,
        load_regime=load_regime,
        averaging_periods=averaging_periods,
        grid_half_extent_m=grid_half_extent_m,
        grid_spacing_m=grid_spacing_m,
        surface_file=surface_file,
        profile_file=profile_file,
        settings=settings,
    )
    if built is None:
        log.info("aermod.dispersion.no_deck", site=settings.site, pollutant=pollutant)
        return None
    inp_text, plotfiles = built
    stack = stack_params_from_profile(settings)
    grid_meta = {"half_extent_m": grid_half_extent_m, "spacing_m": grid_spacing_m}

    caveats = [_SCREENING_CAVEAT]
    if stack.all_assumption:
        caveats.append(
            "Stack geometry is a screening assumption (engine specs not in the record) — the "
            "modeled concentration inherits that uncertainty; supersede with manufacturer stack "
            "data (SiteFacility.genset_stack_*)."
        )
    if event is not None:
        caveats.append(
            "Event-anchored: modeled at the permit LOAD-point rate a real authorized dispatch "
            f"carries, cited to {event.name}"
            + (f" (Order {event.order_id})" if event.order_id else "")
            + ". The authorization window is [verified]; whether this facility ran is [open] "
            "(facility_dispatch_confirmed="
            f"{event.facility_dispatch_confirmed}) — the concentrations are what such a dispatch "
            "would model, not a record that it occurred."
        )

    result: AermodResult = run_aermod(
        inp_text,
        met_files=met_files or {},
        plotfiles=plotfiles,
        pollutant=pollutant,
        settings=settings,
    )

    screens = (
        screen_concentrations(pollutant, result.max_conc, settings=settings)
        if result.available and result.max_conc
        else []
    )
    exceeded = [s.averaging_period for s in screens if s.exceeds_naaqs]

    note = result.note or (
        "AERMOD concentrations screened against the NAAQS."
        if screens
        else "Deck + NAAQS table resolved; AERMOD engine/met unavailable, so no modeled "
        "concentration (degraded, not fabricated)."
    )
    dr = DispersionResult(
        site=settings.site,
        pollutant=pollutant,
        factors_basis=basis,
        load_regime=load_regime,
        available=result.available and bool(result.max_conc),
        engine_version=result.engine_version,
        source_emission_g_s=_source_rate_g_s(inp_text),
        stack=stack,
        stack_is_assumption=stack.all_assumption,
        receptor_grid=grid_meta,
        averaging_periods=[str(a) for a in averaging_periods],
        screens=screens,
        any_naaqs_exceeded=bool(exceeded),
        exceeded=exceeded,
        event=event,
        caveats=caveats,
        note=note,
    )
    log.info(
        "aermod.dispersion.run",
        site=settings.site,
        pollutant=pollutant,
        available=dr.available,
        exceeded=exceeded,
        anchored=event is not None,
    )
    return dr


def run_calibration_dispersion(
    *,
    pollutant: Pollutant = "NOx",
    averaging_periods: tuple[AveragePeriod, ...] = ("1", "ANNUAL"),
    event_relpath: str | None = None,
    met_files: dict[str, str] | None = None,
    settings: Settings | None = None,
) -> DispersionResult | None:
    """The event-anchored calibration dispersion run (#1182).

    Loads the captured dispatch event (#1174) and runs the permit **load**-point dispersion,
    cited to that event. Falls back to a plain (unanchored) load-point screening run when no
    captured event is present, so a checkout without the event still produces a result. Returns
    ``None`` only when there's no facility / ungrounded pollutant.
    """
    settings = settings or get_settings()
    kwargs = {"event_relpath": event_relpath} if event_relpath is not None else {}
    event = load_captured_event(settings=settings, **kwargs)
    if event is None:
        log.info("aermod.dispersion.calibration.no_event", site=settings.site)
    return run_dispersion(
        pollutant=pollutant,
        basis="permit",
        load_regime="load",
        averaging_periods=averaging_periods,
        met_files=met_files,
        event=event,
        settings=settings,
    )


def _source_rate_g_s(inp_text: str) -> float | None:
    """Pull the single-source emission rate (g/s) back out of the deck's ``SO SRCPARAM`` line."""
    for line in inp_text.splitlines():
        if line.startswith("SO SRCPARAM"):
            parts = line.split()
            # SO SRCPARAM <id> <rate> <height> <temp> <velocity> <diameter>
            if len(parts) >= 4:
                try:
                    return float(parts[3])
                except ValueError:
                    return None
    return None
