"""Groundwater-drawdown (cone-of-depression) screen -- the ``[inference]`` scenario layer.

The analytical top of the groundwater stack: given the aquifer parameters
(:mod:`watermark.hydrology.aquifer`, an ``[inference]`` transmissivity BRACKET) and a
**pumping stress** ``Q``, the Theis solution gives the drawdown cone a well field of that
size would impose -- the quantitative form of the residents' "area well concerns."

**This is a scenario, not a documented mechanism -- and it is framed that way.** The record
shows the data-center campus draws treated **municipal** water (Lima's surface-water
reservoirs), and no on-site production wells or groundwater-withdrawal permit are on record
(the withdrawal registration is an ``[open]`` owed record). So ``Q`` here is a hypothetical
-- "*if* a load of this size pumped locally from the aquifer" -- tagged ``assumption`` /
``[inference]`` and always **bracketed**, never a headline. Its strongest use is the inverse
finding: pumping a hyperscale makeup load from the low-transmissivity fractured-limestone
aquifer drives drawdown **past the saturated thickness** -- the aquifer physically *cannot*
supply it, which is exactly why the campus is on municipal water. The screen surfaces that
as a ``dewatering`` outcome rather than an implausible number.

Theis (fully confined, fully penetrating, constant ``Q``):
``s(r, t) = Q / (4*pi*T) * W(u)``, ``u = r^2 * S / (4*T*t)``, ``W(u) = E1(u)`` (the
exponential integral, via a dependency-free Abramowitz & Stegun approximation).
The radius of influence is the Cooper-Jacob zero-drawdown intercept
``r0 = sqrt(2.25 * T * t / S)``.
"""

from __future__ import annotations

from math import exp, sqrt
from math import log as ln

from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology._geo import haversine_ft
from watermark.hydrology.aquifer import AquiferParameters
from watermark.hydrology.connectors import ohio_waterwells as oww
from watermark.hydrology.model import HydroFinding, ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

# Unit conversions.
_FT3_PER_GAL = 1.0 / 7.480519480519  # ft^3 per US gallon
_FT3_DAY_PER_MGD = 1_000_000.0 * _FT3_PER_GAL  # ~133,680.6 ft^3/day per MGD
_FT_PER_MILE = 5280.0

# Default pumping-well radius (ft) at which the peak (cone-apex) drawdown is reported. Theis
# diverges as r -> 0, so a physical borehole radius is used, not 0.
_WELL_RADIUS_FT = 0.5
# Drawdown (ft) below which a domestic well is treated as effectively unaffected.
_AFFECTED_THRESHOLD_FT = 1.0


def mgd_to_ft3_day(mgd: float) -> float:
    """Million gallons/day -> cubic feet/day."""
    return mgd * _FT3_DAY_PER_MGD


def well_function(u: float) -> float:
    """The Theis well function ``W(u) = E1(u)`` (exponential integral), dependency-free.

    Abramowitz & Stegun (1964) rational approximations 5.1.53 (``0 < u <= 1``, error < 2e-7)
    and 5.1.56 (``u > 1``, error < 5e-5) — no scipy dependency for one exponential integral.
    """
    if u <= 0:
        return 0.0
    if u <= 1.0:
        # A&S 5.1.53: E1(u) = -ln(u) + sum(a_k u^k)
        a = (-0.57721566, 0.99999193, -0.24991055, 0.05519968, -0.00976004, 0.00107857)
        return -ln(u) + a[0] + u * (a[1] + u * (a[2] + u * (a[3] + u * (a[4] + u * a[5]))))
    # A&S 5.1.56: E1(u) = e^-u/u * (u^2 + a1 u + a2) / (u^2 + b1 u + b2)
    a1, a2, b1, b2 = 2.334733, 0.250621, 3.330657, 1.681534
    return (exp(-u) / u) * (u * u + a1 * u + a2) / (u * u + b1 * u + b2)


def theis_drawdown(
    q_ft3_day: float, t_ft2_day: float, storativity: float, r_ft: float, t_days: float
) -> float:
    """Theis confined-aquifer drawdown (ft) at radius ``r_ft`` after ``t_days`` of pumping."""
    if t_ft2_day <= 0 or storativity <= 0 or r_ft <= 0 or t_days <= 0 or q_ft3_day <= 0:
        return 0.0
    u = (r_ft * r_ft * storativity) / (4.0 * t_ft2_day * t_days)
    return q_ft3_day / (4.0 * 3.141592653589793 * t_ft2_day) * well_function(u)


def radius_of_influence_ft(t_ft2_day: float, storativity: float, t_days: float) -> float:
    """Cooper-Jacob zero-drawdown intercept r0 = sqrt(2.25*T*t/S) (ft)."""
    if t_ft2_day <= 0 or storativity <= 0 or t_days <= 0:
        return 0.0
    return sqrt(2.25 * t_ft2_day * t_days / storativity)


def cooper_jacob_drawdown(
    q_ft3_day: float, t_ft2_day: float, storativity: float, r_ft: float, t_days: float
) -> float:
    """Cooper-Jacob (late-time Theis) drawdown (ft): ``s = Q/(4*pi*T) * ln(2.25*T*t/(r^2*S))``.

    The log-linear approximation of Theis. Unlike the full Theis solution it reaches **exactly
    zero** at the radius of influence ``r0 = sqrt(2.25*T*t/S)`` (the argument of the log is 1
    there) and is floored at 0 beyond it — so it is the right form for the **cone profile**,
    which must decline to zero at ``r0``. The apex headline stays on the full Theis solution.
    """
    if t_ft2_day <= 0 or storativity <= 0 or r_ft <= 0 or t_days <= 0 or q_ft3_day <= 0:
        return 0.0
    arg = 2.25 * t_ft2_day * t_days / (r_ft * r_ft * storativity)
    if arg <= 1.0:  # at or beyond the radius of influence
        return 0.0
    return q_ft3_day / (4.0 * 3.141592653589793 * t_ft2_day) * ln(arg)


# --- models -----------------------------------------------------------------------------


class DrawdownScenario(BaseModel):
    """A hypothetical pumping stress on the aquifer (never a documented withdrawal)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    pumping_mgd: ProvenancedValue  # Q, [inference]/assumption, may carry a low/high band
    duration_days: float
    aquifer_material: str  # which material's T/S the cone runs on (default: the dominant)
    note: str


class DrawdownPoint(BaseModel):
    """One (radius, drawdown) sample of the cone profile, for the AquiferSection figure."""

    model_config = ConfigDict(extra="forbid")

    radius_ft: float
    drawdown_ft: float


class DrawdownResult(BaseModel):
    """A screening drawdown cone for one scenario x aquifer material (all ``[inference]``)."""

    model_config = ConfigDict(extra="forbid")

    county: str
    scenario: DrawdownScenario
    material: str
    confinement: str
    transmissivity_ft2_day: ProvenancedValue  # the bracket the cone runs on
    storativity: ProvenancedValue
    saturated_thickness_ft: float | None
    # Cone-apex drawdown at the pumping well (capped at saturated thickness when it dewaters).
    drawdown_at_well_ft: ProvenancedValue
    radius_of_influence_ft: ProvenancedValue
    # Whether the central-T cone exceeds the saturated thickness (aquifer cannot sustain Q).
    dewaters: bool
    sustainable: bool
    affected_domestic_wells: int | None  # census domestic wells within the influence radius
    profile: list[DrawdownPoint]
    tag: str = "inference"
    caveats: list[str] = []


# --- scenarios --------------------------------------------------------------------------


def cooling_makeup_scenario(
    params: AquiferParameters,
    *,
    makeup_mgd: float,
    low_mgd: float | None,
    high_mgd: float | None,
    duration_days: float = 365.0,
    material: str | None = None,
    makeup_basis: str | None = None,
) -> DrawdownScenario:
    """The headline hypothetical: the campus cooling makeup, *as if* pumped from groundwater.

    ``makeup_mgd`` (+ any ``low_mgd``/``high_mgd`` band) is the caller-supplied pumping stress —
    resolved from the ACTIVE SITE's cooling basis by :func:`site_cooling_makeup_scenario`, never
    baked in here, so no site's figure leaks into another's and no uncertainty band is fabricated.
    The campus actually draws this as treated municipal (surface) water -- the note records that
    this is a hypothetical groundwater stress, not a documented withdrawal.

    ``makeup_basis`` names WHERE the stress came from and defaults to Lima's committed buildout
    scenario, which is where it came from for the only site that had one when this was written.
    A caller resolving the makeup some other way must say so (#1997): the citation is the reader's
    only route back to the figure, and one that points at a committed artifact holding a
    *different* number is worse than no citation at all.
    """
    dom = params.dominant()
    mat = (material or (dom.material if dom else "LIMESTONE")).upper()
    basis = (
        makeup_basis
        or "Campus cooling makeup (buildout central, data/scenarios/buildout.scenario.yaml)"
    )
    pumping = ProvenancedValue.assume(
        # NOT rounded (#1997): a stated makeup is traceable to the instrument that states it, and
        # `round(x, 3)` published Sidney's contracted 0.0126 MGD as 0.013 — a figure its own
        # citation does not contain. Rounding is a display concern; the value keeps its precision.
        makeup_mgd,
        "MGD",
        f"{basis} framed as a HYPOTHETICAL groundwater pumping stress. The campus draws municipal "
        "SURFACE water; no on-site production well or withdrawal permit is on record ([open]).",
        low=low_mgd,
        high=high_mgd,
    )
    return DrawdownScenario(
        name="cooling-makeup-if-groundwater",
        pumping_mgd=pumping,
        duration_days=duration_days,
        aquifer_material=mat,
        note=(
            "Hypothetical: what a well field supplying the campus cooling makeup would do to the "
            f"{mat} aquifer. Bounds the 'area well concerns'; not a documented groundwater use."
        ),
    )


def site_cooling_makeup_scenario(
    params: AquiferParameters,
    *,
    settings: Settings | None = None,
    makeup_mgd: float | None = None,
    material: str | None = None,
) -> DrawdownScenario:
    """The cooling-makeup scenario for the ACTIVE SITE (makeup from its cooling basis, or override).

    Resolves the campus cooling makeup (MGD + any committed uncertainty band), most-grounded
    first, mirroring :func:`watermark.hydrology.scenario.buildout_scenario` (#1995/#1997):

    1. an explicit ``makeup_mgd`` — a sensitivity sweep, no band;
    2. the facility's **stated** makeup, where the record carries one;
    3. the active site's :func:`~watermark.hydrology.cooling.derive_cooling_basis` demand.

    Rung 2 matters here for the same reason it mattered there, and the consequence is larger.
    Where the cooling method is undisclosed, ``makeup_demand`` holds the evaporative UPPER-BOUND
    ENVELOPE, which the basis itself tags ``assumption`` and labels "NOT an estimate" — and
    ``headline_makeup()`` returns ``None`` precisely so a caller cannot publish it as one. This
    function read straight past that guard. At Sidney that meant screening a 3.59 MGD stress
    (which dewaters the aquifer, 116 ft of apex drawdown) against a campus whose CONTRACTED
    makeup is 0.0126 MGD — 285x smaller, on the record, and drawn from municipal surface water.
    A stated quantity beats an envelope; the envelope is the sweep, not the site.
    """
    settings = settings or get_settings()
    if makeup_mgd is not None:
        return cooling_makeup_scenario(
            params,
            makeup_mgd=makeup_mgd,
            low_mgd=None,
            high_mgd=None,
            material=material,
            makeup_basis="Cooling makeup supplied as an explicit sensitivity override",
        )
    from watermark.hydrology.cooling import derive_cooling_basis
    from watermark.hydrology.scenario import _stated_cooling_account

    stated = _stated_cooling_account(settings)
    if stated is not None:
        makeup = stated[0]
        basis = f"Campus cooling makeup, STATED on the record — {makeup.citation}"
    else:
        makeup = derive_cooling_basis(settings).makeup_demand
        basis = f"Campus cooling makeup ({makeup.source}) — {makeup.citation}"
    return cooling_makeup_scenario(
        params,
        makeup_mgd=makeup.value,
        low_mgd=makeup.low,
        high_mgd=makeup.high,
        material=material,
        makeup_basis=basis,
    )


# --- compute ----------------------------------------------------------------------------


def _count_affected_domestic(
    inventory: oww.WaterWellInventory, *, lat: float, lon: float, radius_ft: float
) -> int:
    """Domestic census wells within ``radius_ft`` of the campus point (with coordinates)."""
    n = 0
    for w in inventory.wells:
        if (w.well_use or "").strip().upper() != "DOMESTIC":
            continue
        if w.latitude is None or w.longitude is None:
            continue
        if haversine_ft(lat, lon, w.latitude, w.longitude) <= radius_ft:
            n += 1
    return n


def compute_drawdown(
    params: AquiferParameters,
    scenario: DrawdownScenario,
    *,
    inventory: oww.WaterWellInventory | None = None,
    campus_lat: float | None = None,
    campus_lon: float | None = None,
    well_radius_ft: float = _WELL_RADIUS_FT,
    threshold_ft: float = _AFFECTED_THRESHOLD_FT,
) -> DrawdownResult:
    """Screen the Theis cone for one scenario against one aquifer material's parameters."""
    # The scenario always names a concrete material (defaulted to the dominant one upstream in
    # cooling_makeup_scenario), so an unresolved name is a real error — never silently substitute
    # the dominant material's parameters for the one the caller asked for.
    material = params.material(scenario.aquifer_material)
    if material is None:
        raise ValueError(
            f"aquifer material {scenario.aquifer_material!r} is not present in {params.county} "
            f"(present: {[m.material for m in params.materials]})"
        )

    t_pv = material.transmissivity_ft2_day
    if t_pv is None:
        raise ValueError(
            f"material {material.material} has no transmissivity (no saturated thickness)"
        )
    s_val = material.storativity.value
    b = material.saturated_thickness_ft.value if material.saturated_thickness_ft else None

    q_central = mgd_to_ft3_day(scenario.pumping_mgd.value)
    q_low = mgd_to_ft3_day(scenario.pumping_mgd.low_or_value)
    q_high = mgd_to_ft3_day(scenario.pumping_mgd.high_or_value)
    t_days = scenario.duration_days

    # Drawdown at the well apex. s scales like Q/T: the DEEPEST cone pairs the highest Q with
    # the lowest T; the shallowest pairs the lowest Q with the highest T.
    def apex(q: float, t: float) -> float:
        return theis_drawdown(q, t, s_val, well_radius_ft, t_days)

    s_central = apex(q_central, t_pv.value)
    s_deep = apex(q_high, t_pv.low_or_value)
    s_shallow = apex(q_low, t_pv.high_or_value)

    # Dewatering is the CENTRAL-T verdict -- what this field has always said it was ("Whether the
    # central-T cone exceeds the saturated thickness"), and what the computation now does (#1997).
    # It was keyed on the bracket's DEEP end (highest Q, lowest transmissivity), which flags
    # true for almost any rate in a low-transmissivity aquifer: at Sidney a 0.0126 MGD contracted
    # makeup published `dewaters: true` on a central cone of 8.6 ft against 116 ft of saturated
    # thickness. A boolean named `dewaters` is read categorically by any consumer that does not
    # also read the prose beside it, so it has to carry the central case.
    #
    # Lima's finding is unaffected and that is the check on this change: its central cone reaches
    # the thickness on its own (the cap below binds at the central value), so "pumping a
    # hyperscale load from this aquifer dewaters it" still stands where it was earned.
    dewaters = b is not None and s_central >= b
    # The deep end is retained as a BOUNDED caveat rather than a verdict: still worth reporting
    # for a screen that exists to bound the "area well concerns", never a claim about the aquifer.
    deep_end_dewaters = b is not None and s_deep > b and not dewaters

    # Report capped at the saturated thickness: past b the analytical value is unphysical
    # (the aquifer is dewatered), so cap and flag rather than print an impossible number.
    def cap(s: float) -> float:
        return round(min(s, b), 1) if b is not None else round(s, 1)

    drawdown_pv = ProvenancedValue.derived(
        cap(s_central),
        "ft",
        (
            f"Theis cone apex (r={well_radius_ft} ft, t={t_days:g} d) on the {material.material} "
            f"aquifer, Q={scenario.pumping_mgd.value:g} MGD [inference]. "
            + (
                "CAPPED at the saturated thickness -- the central cone reaches it, i.e. the "
                "aquifer DEWATERS and cannot sustain this rate."
                if dewaters
                else (
                    "Bracket spans the transmissivity range; its HIGH end is capped at the "
                    "saturated thickness -- the low-transmissivity end reaches it while the "
                    "central estimate does not, which bounds the concern rather than settling it."
                    if deep_end_dewaters
                    else "Bracket spans the transmissivity range."
                )
            )
        ),
        low=cap(min(s_shallow, s_deep)),
        high=cap(max(s_shallow, s_deep)),
    )

    r0_central = radius_of_influence_ft(t_pv.value, s_val, t_days)
    r0_pv = ProvenancedValue.derived(
        round(r0_central, 0),
        "ft",
        f"Cooper-Jacob r0 = sqrt(2.25*T*t/S) on the {material.material} aquifer [inference].",
        low=round(radius_of_influence_ft(t_pv.low_or_value, s_val, t_days), 0),
        high=round(radius_of_influence_ft(t_pv.high_or_value, s_val, t_days), 0),
    )

    affected: int | None = None
    if inventory is not None and campus_lat is not None and campus_lon is not None:
        affected = _count_affected_domestic(
            inventory, lat=campus_lat, lon=campus_lon, radius_ft=r0_central
        )

    # A coarse cone profile for the AquiferSection figure (apex -> radius of influence). Uses
    # Cooper-Jacob so the cone DECLINES with radius and reaches ~0 at r0 (the full Theis solution
    # stays finite there, which would render as a flat, uninformative line); the saturated-
    # thickness cap then bites only in the near field, where the local drawdown exceeds it.
    profile: list[DrawdownPoint] = []
    steps = 24
    for i in range(steps + 1):
        frac = i / steps
        r = well_radius_ft + frac * max(r0_central - well_radius_ft, 0.0)
        s = cooper_jacob_drawdown(q_central, t_pv.value, s_val, max(r, well_radius_ft), t_days)
        profile.append(DrawdownPoint(radius_ft=round(r, 1), drawdown_ft=cap(s)))

    caveats = [
        "Hypothetical pumping stress: the campus draws municipal SURFACE water; no groundwater "
        "withdrawal is on record. Q is [inference], the cone is a screen, never a headline.",
        "Theis assumes a confined, homogeneous, fully-penetrating aquifer at constant Q -- a "
        "screening idealization, not a calibrated model.",
        *params.caveats,
    ]
    if dewaters:
        caveats.insert(
            1,
            "The CENTRAL cone reaches the saturated thickness: the local aquifer CANNOT sustain "
            "this rate -- corroborating the campus's reliance on municipal surface water.",
        )
    elif deep_end_dewaters:
        # The bounded form of the same observation (#1997): worth reporting, because bounding the
        # "area well concerns" is what this screen is for — but it is a statement about the
        # bracket's pessimistic end, not about the aquifer, and it must not read as one.
        caveats.insert(
            1,
            "The low-transmissivity end of the bracket reaches the saturated thickness while the "
            "central estimate stays well below it. That BOUNDS the concern; it does not establish "
            "that the aquifer cannot sustain this rate, and `dewaters` is false accordingly.",
        )

    return DrawdownResult(
        county=params.county,
        scenario=scenario,
        material=material.material,
        confinement=material.confinement,
        transmissivity_ft2_day=t_pv,
        storativity=material.storativity,
        saturated_thickness_ft=b,
        drawdown_at_well_ft=drawdown_pv,
        radius_of_influence_ft=r0_pv,
        dewaters=dewaters,
        sustainable=not dewaters,
        affected_domestic_wells=affected,
        profile=profile,
        caveats=caveats,
    )


def load_drawdown(
    *, scenario: DrawdownScenario | None = None, settings: Settings | None = None
) -> DrawdownResult | None:
    """Screen the active site's aquifer + census against a scenario (default: cooling makeup)."""
    settings = settings or get_settings()
    from watermark.hydrology.aquifer import load_aquifer_parameters
    from watermark.sites import active_profile

    params = load_aquifer_parameters(settings=settings)
    if params is None:
        return None
    profile = active_profile(settings)
    slug = oww.county_slug(profile.county_name)
    path = settings.data_dir / "reference" / "ohio-waterwells" / f"{slug}.csv"
    inventory = oww.read_inventory(path, settings=settings) if path.is_file() else None
    scen = scenario or site_cooling_makeup_scenario(params, settings=settings)
    return compute_drawdown(
        params,
        scen,
        inventory=inventory,
        campus_lat=profile.design_lat,
        campus_lon=profile.design_lon,
    )


# --- findings ---------------------------------------------------------------------------


def drawdown_findings(result: DrawdownResult) -> list[HydroFinding]:
    """Narrate the drawdown screen in the hydrology finding idiom."""
    subject = f"{result.county} {result.material} aquifer"
    s = result.drawdown_at_well_ft
    out = [
        HydroFinding(
            subject=subject,
            check="drawdown-aquifer-capacity",
            ok=result.sustainable,
            detail=(
                (
                    f"Hypothetical {result.scenario.pumping_mgd.value:g} MGD groundwater pumping "
                    f"DEWATERS the aquifer: the CENTRAL cone reaches the "
                    f"{result.saturated_thickness_ft:g} ft saturated thickness (bracket "
                    f"{s.low_or_value:g}-{s.high_or_value:g}) -- it cannot sustain this rate. "
                    "The campus is on municipal surface water; no on-site production well is on "
                    "record."
                )
                if result.dewaters
                else (
                    f"Apex drawdown {s.value:g} ft (bracket {s.low_or_value:g}-{s.high_or_value:g}) "
                    f"for a hypothetical {result.scenario.pumping_mgd.value:g} MGD stress."
                )
            ),
        )
    ]
    if result.affected_domestic_wells is not None:
        r0 = result.radius_of_influence_ft
        out.append(
            HydroFinding(
                subject=subject,
                check="drawdown-affected-wells",
                ok=True,
                detail=(
                    f"{result.affected_domestic_wells} domestic census wells fall within the "
                    f"{r0.value:g} ft ([inference]) radius of influence of the campus point -- the "
                    "population a well field of this size could measurably draw down."
                ),
            )
        )
    return out
