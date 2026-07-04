"""Build EPA AERMOD ``aermod.inp`` control + source decks from our data.

AERMOD reads a fixed five-pathway control file (``CO`` control, ``SO`` sources, ``RE``
receptors, ``ME`` meteorology, ``OU`` output). :func:`build_aermod_inp` assembles the
full deck; the per-pathway helpers are exposed for unit-testing each section.

The source deck is built from two things: the site's per-engine emission rate (permit-
certified lb/hr → g/s, grounded) and the per-unit **stack geometry**. The geometry is an
``assumption`` for Lima — the permit redacts engine specs as CBI — so
:func:`assumed_stack_params` documents its screening basis explicitly. Nothing here is
hardcoded to a site: the caller threads in the rate and (optionally) real stack data.
"""

from __future__ import annotations

from watermark.air.aermod.model import (
    AermodControl,
    AermodSource,
    GensetStackParams,
    ReceptorGrid,
    lb_per_hr_to_g_per_s,
)
from watermark.air.model import Pollutant
from watermark.hydrology.model import ProvenancedValue

# Our Pollutant labels -> the AERMOD POLLUTID token. AERMOD has no VOC species, so VOC
# maps to the generic OTHER (no built-in decay/chemistry assumptions apply either way).
_AERMOD_POLLUTID: dict[Pollutant, str] = {
    "NOx": "NOX",
    "CO": "CO",
    "PM10": "PM10",
    "PM2.5": "PM25",
    "SO2": "SO2",
    "VOC": "OTHER",
}


# Site-agnostic default rationale for the screening stack geometry. Callers with a
# site-specific reason (e.g. that site's permit redacts engine specs as CBI) pass their
# own ``why`` so the assumption is never misattributed to another site's permit.
_STACK_ASSUMPTION_WHY = (
    "typical large (~2.75 MW) stationary CI diesel genset exhaust — a screening assumption "
    "used where the engine make/model/size is not in the record (e.g. redacted as CBI); "
    "supersede with manufacturer stack data when disclosed (#1180)"
)


def assumed_stack_params(*, why: str | None = None) -> GensetStackParams:
    """Screening stack geometry for a ~2.75 MW stationary diesel genset — **all assumption**.

    Used where no certified stack dimensions exist in the record (for Lima, the permit
    redacts engine make/model/size as CBI). These are typical published values for a large
    stationary CI diesel engine exhaust, tagged ``assumption`` — a stated modeling input,
    **never** presented as a permit fact. ``why`` overrides the site-agnostic default
    rationale with a site-specific citation (so a non-Lima run isn't tagged with Lima's
    permit); a site with disclosed manufacturer data builds a ``document``-tagged
    :class:`GensetStackParams` instead (the #1180 seam).
    """
    why = why or _STACK_ASSUMPTION_WHY
    return GensetStackParams(
        height_m=ProvenancedValue.assume(10.0, "m", why=why),
        diameter_m=ProvenancedValue.assume(0.6, "m", why=why),
        exit_velocity_ms=ProvenancedValue.assume(40.0, "m/s", why=why),
        exit_temp_k=ProvenancedValue.assume(720.0, "K", why=why),
    )


def genset_point_source(
    *,
    src_id: str,
    pollutant: Pollutant,
    per_engine_lb_per_hr: float,
    rate_citation: str,
    stack: GensetStackParams | None = None,
    x_m: float = 0.0,
    y_m: float = 0.0,
    base_elev_m: float = 0.0,
) -> AermodSource:
    """One genset as an AERMOD point source: certified rate (lb/hr→g/s) + stack geometry.

    ``per_engine_lb_per_hr`` is the permit-certified per-engine rate (see
    :func:`watermark.air.emissions.permit_factors`); it is converted to g/s and tagged
    ``derived`` (from a documented rate). ``stack`` defaults to :func:`assumed_stack_params`.
    """
    stack = stack or assumed_stack_params()
    g_s = lb_per_hr_to_g_per_s(per_engine_lb_per_hr)
    return AermodSource(
        src_id=src_id,
        pollutant=pollutant,
        x_m=x_m,
        y_m=y_m,
        base_elev_m=base_elev_m,
        emission_g_s=ProvenancedValue.derived(
            round(g_s, 6),
            "g/s",
            citation=f"{per_engine_lb_per_hr:g} lb/hr x {round(lb_per_hr_to_g_per_s(1.0), 6)} "
            f"g/s-per-lb/hr ({rate_citation})",
        ),
        stack=stack,
    )


def _pollutid(pollutant: Pollutant) -> str:
    return _AERMOD_POLLUTID[pollutant]


def control_pathway(control: AermodControl) -> str:
    """The ``CO`` (control) pathway: model options, averaging, pollutant, run flag.

    The averaging periods are validated at the model boundary (:class:`AermodControl`'s
    ``AveragePeriod`` literal), so no re-check is needed here.
    """
    modelopt = "DFAULT CONC" if control.regulatory_default else "CONC"
    lines = [
        "CO STARTING",
        f"CO TITLEONE  {control.title}",
        f"CO MODELOPT  {modelopt} {control.terrain}",
        f"CO AVERTIME  {' '.join(control.averaging_periods)}",
        f"CO POLLUTID  {_pollutid(control.pollutant)}",
    ]
    if control.flagpole_height_m is not None:
        lines.append(f"CO FLAGPOLE  {control.flagpole_height_m:g}")
    lines += ["CO RUNORNOT  RUN", "CO FINISHED"]
    return "\n".join(lines)


def source_pathway(sources: list[AermodSource]) -> str:
    """The ``SO`` (source) pathway: one ``POINT`` per genset + a single ``SRCGROUP ALL``."""
    if not sources:
        raise ValueError("AERMOD source pathway needs at least one source")
    lines = ["SO STARTING"]
    for s in sources:
        lines.append(f"SO LOCATION  {s.src_id}  POINT  {s.x_m:g} {s.y_m:g} {s.base_elev_m:g}")
    for s in sources:
        st = s.stack
        # SRCPARAM: emission rate (g/s), release height (m), exit temp (K), exit velocity
        # (m/s), inside diameter (m) — the AERMOD point-source parameter order.
        lines.append(
            f"SO SRCPARAM  {s.src_id}  {s.emission_g_s.value:g} "
            f"{st.height_m.value:g} {st.exit_temp_k.value:g} "
            f"{st.exit_velocity_ms.value:g} {st.diameter_m.value:g}"
        )
    lines.append("SO SRCGROUP  ALL")
    lines.append("SO FINISHED")
    return "\n".join(lines)


def receptor_pathway(grid: ReceptorGrid) -> str:
    """The ``RE`` (receptor) pathway: a uniform Cartesian ``GRIDCART`` network."""
    return "\n".join(
        [
            "RE STARTING",
            f"RE GRIDCART {grid.net_id} STA",
            f"RE GRIDCART {grid.net_id} XYINC "
            f"{grid.x0_m:g} {grid.nx} {grid.dx_m:g} {grid.y0_m:g} {grid.ny} {grid.dy_m:g}",
            f"RE GRIDCART {grid.net_id} END",
            "RE FINISHED",
        ]
    )


def meteorology_pathway(
    *,
    surface_file: str,
    profile_file: str,
    surface_station_id: str,
    upper_air_station_id: str,
    data_year: int,
    base_elev_m: float,
) -> str:
    """The ``ME`` (meteorology) pathway pointing at AERMET-processed surface/profile files.

    The files themselves come from AERMET (#1179, deferred); a committed **canned** pair
    drives the minimal acceptance run. ``SURFDATA``/``UAIRDATA`` echo the station ids/year
    the AERMET run declared (AERMOD cross-checks them against the file headers).
    """
    return "\n".join(
        [
            "ME STARTING",
            f"ME SURFFILE  {surface_file}",
            f"ME PROFFILE  {profile_file}",
            f"ME SURFDATA  {surface_station_id} {data_year}",
            f"ME UAIRDATA  {upper_air_station_id} {data_year}",
            f"ME PROFBASE  {base_elev_m:g} METERS",
            "ME FINISHED",
        ]
    )


def output_pathway(control: AermodControl, *, plotfiles: dict[str, str] | None = None) -> str:
    """The ``OU`` (output) pathway: max-value tables + one machine-readable ``PLOTFILE``/ave.

    ``plotfiles`` maps an averaging-period token to an output filename; each is emitted as
    ``OU PLOTFILE <ave> ALL FIRST <file>`` — the stable, columnar format
    :func:`watermark.air.aermod.engine.parse_plotfile` reads. Defaults to one plotfile per
    averaging period, named ``<ave>.plt``.
    """
    if plotfiles is None:
        plotfiles = {ave: f"{ave.lower()}.plt" for ave in control.averaging_periods}
    lines = [
        "OU STARTING",
        "OU RECTABLE  ALLAVE  FIRST",
        "OU MAXTABLE  ALLAVE  10",
    ]
    for ave, path in plotfiles.items():
        lines.append(f"OU PLOTFILE  {ave} ALL FIRST  {path}")
    lines.append("OU FINISHED")
    return "\n".join(lines)


def build_aermod_inp(
    *,
    control: AermodControl,
    sources: list[AermodSource],
    grid: ReceptorGrid,
    surface_file: str,
    profile_file: str,
    surface_station_id: str = "00000",
    upper_air_station_id: str = "00000",
    data_year: int = 2020,
    plotfiles: dict[str, str] | None = None,
) -> str:
    """Assemble a complete ``aermod.inp`` deck from typed inputs.

    The base elevation of the ``ME PROFBASE`` is taken from the first source's stack base.
    """
    base_elev = sources[0].base_elev_m if sources else 0.0
    return (
        "\n".join(
            [
                control_pathway(control),
                "",
                source_pathway(sources),
                "",
                receptor_pathway(grid),
                "",
                meteorology_pathway(
                    surface_file=surface_file,
                    profile_file=profile_file,
                    surface_station_id=surface_station_id,
                    upper_air_station_id=upper_air_station_id,
                    data_year=data_year,
                    base_elev_m=base_elev,
                ),
                "",
                output_pathway(control, plotfiles=plotfiles),
            ]
        )
        + "\n"
    )
