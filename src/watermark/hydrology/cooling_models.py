"""Cooling-model taxonomy + registry — each archetype is its own water-math world.

Mirrors the format ``Profile`` registry idiom (:mod:`watermark.profiles`): register a
:class:`CoolingModelSpec` per archetype, don't hardcode one cooling technology into the
derivation (#1053). The enum itself (:class:`watermark.sites.CoolingModelType`) lives on
the site axis because the archetype is a per-site facility attribute
(``SiteFacility.cooling_model``) and ``watermark.config`` imports ``watermark.sites``.

The registry is keyed on **physical mechanism**, never on the industry's "open loop /
closed loop" labels — those are ambiguous in data-center usage ([reference]: EPA
WaterSense at Work §6 calls a recirculating wet tower an *open recirculating* system;
trade usage shortens that to "open loop", while "closed loop" names both sealed dry/air-
cooled circuits and, confusingly, tower condenser-water loops). Each spec documents its
open/closed alias for display; the engine dispatches on the enum only.

Every quantity a spec returns is a :class:`~watermark.hydrology.model.ProvenancedValue`;
fields irrelevant to an archetype are ``None``, never faked. The ``unknown`` archetype
(disclosed facility, undisclosed method) returns a **bracketed range** across candidate
archetypes — defaulting it to the water-intensive evaporative model would publish a
fabricated consumptive figure (#1057).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from watermark.config import Settings
from watermark.hydrology.model import CoolingBasis, ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import CoolingModelType, SiteFacility

log = get_logger(__name__)

_L_PER_GAL = 3.785411784

# --- Generic archetype defaults (used when a facility discloses no override) -------------
# These are ARCHETYPE reference values, not any one site's disclosure (#1634): a facility's
# own disclosed figures live on ``SiteProfile.facility`` and win here. Nothing site-specific
# belongs in this module — the genset/IT-load/permit/FM-2 constants that used to sit here
# were a second copy of Lima's ``SiteFacility``, so a site that disclosed none of them
# silently inherited Lima's basis. They are gone; the profile is the single source.
_WUE_L_PER_KWH = 1.8  # evaporative hyperscale; Google fleet avg ~1.1, evaporative higher
_WUE_CITE = (
    "evaporative-cooled hyperscale WUE ~1.8 L/kWh archetype default (Google fleet avg ~1.1, "
    "evaporative plants higher) — not a facility disclosure; a site that discloses its own "
    "WUE overrides this via SiteFacility.wue_l_per_kwh + wue_citation"
)

# The empirical ceiling on evaporative-hyperscale water-use effectiveness (WS-16, #1616). The
# blowdown-method upper bound (blowdown x (CoC-1)) is a valid *cooling* bound only if the
# disclosed discharge is pure cooling-tower blowdown. Cross-check the WUE it implies
# (consumptive / IT energy); when it exceeds this ceiling the discharge is physically
# unreachable for cooling alone — strong evidence it bundles non-cooling (process/sanitary)
# flow — so the cooling-only upper bound is capped here instead of publishing an unreachable
# evaporative loss. The ceiling is the top of the real evaporative range, not a thermodynamic
# limit; it is applied per :func:`_derive_evaporative_tower` and never drops below the
# facility's own central WUE (a plant may cite one above this generic ceiling).
_WUE_CEILING_L_PER_KWH = 2.2  # top of the ~1.8-2.2 L/kWh real evaporative-hyperscale range
_WUE_CEILING_CITE = (
    "evaporative-hyperscale WUE ceiling ~2.2 L/kWh (top of the ~1.8-2.2 L/kWh real-world "
    "evaporative range; Google fleet avg ~1.1) — a blowdown-implied cooling WUE above this "
    "indicates the disclosed discharge is not all cooling-tower blowdown"
)

_CYCLES = 5.0  # cooling-tower cycles of concentration (typical 4-6)
_CYCLES_CITE = "cooling-tower cycles of concentration ~5 (typical 4-6)"

# The blowdown cross-check's citation when the figure came from a sensitivity OVERRIDE rather
# than a facility disclosure — it names the override, never a documented discharge. (A
# disclosed blowdown always carries the facility's own ``blowdown_citation``.)
_BLOWDOWN_OVERRIDE_CITE = (
    "blowdown supplied as a sensitivity override (CoolingParams.blowdown_mgd) — not a "
    "disclosed discharge for this facility"
)
# Its peer for an IT load supplied the same way, with no facility disclosure behind it — it
# names the override, never another site's air permit.
_IT_LOAD_OVERRIDE_CITE = (
    "IT load supplied as a sensitivity override (CoolingParams.it_load_mw) — not a disclosed "
    "or derived load for this facility"
)

# --- once_through parameters ------------------------------------------------------------
_OT_DELTA_T_C = 10.0
_OT_DELTA_T_CITE = "once-through condenser temperature rise dT ~10 degC (typical 8-12 design)"
# L/day of once-through condenser flow per MW of rejected heat: kg/s per kW = 1/(c_p x dT),
# scaled kW->MW and s->day (kg ~= L for water). The forward flow and its inverse share this
# one factor so the unit chain can never drift between them.
_OT_LPD_PER_MW = 1_000.0 * 86_400.0 / (4.186 * _OT_DELTA_T_C)
# Heat *rejected* at the condenser is the IT (server) load plus the cooling-system work that
# moves it — pumps, chillers/compressors, fans — so the rejected-heat load driving the
# withdrawal is IT x an overhead multiplier, not bare IT (#1153). ~1.15 is a screening
# central; a chiller-heavy plant runs higher. Per-facility override via
# ``SiteFacility.heat_reject_multiplier`` / ``CoolingParams.heat_reject_multiplier``.
_OT_HEAT_REJECT_MULT = 1.15
_OT_HEAT_REJECT_CITE = (
    "condenser heat rejection = IT load x ~1.15 cooling overhead (heat rejected is server "
    "load + cooling-system work — pumps/chillers/fans; ~1.1-1.4 typical, chiller-heavy higher; "
    "per PUE/mechanical-load screening convention, e.g. ASHRAE Datacom / DOE DC energy guides)"
)
_OT_EVAP_FRAC_LOW = 0.01
_OT_EVAP_FRAC_HIGH = 0.02
_OT_EVAP_CITE = (
    "forced-evaporation share of a once-through withdrawal ~1-2% (USGS SIR 2014-5184, "
    "Diehl & Harris 2014, thermoelectric water-consumption coefficients). The band is a "
    f"fraction of *withdrawal*, so it is anchored to the assumed ~{_OT_DELTA_T_C:g} degC "
    "condenser dT (WS-25): the withdrawal scales inversely with dT for the same rejected heat, "
    "so a fixed %-of-withdrawal coefficient holds only at the dT it is defined at. The forced "
    "evaporation itself is driven by the rejected heat, not the intake volume — at a wider dT "
    "(smaller withdrawal) the same heat evaporates a larger *fraction* of it"
)

# --- hybrid_adiabatic parameters --------------------------------------------------------
# The fallback assist window when the site has no committed climatology: the temperate
# mid-latitude ET0 > precip season. A stated modeling assumption, replaced by the
# NASA POWER + FAO-56 determination whenever the climatology artifact exists.
_HYBRID_FALLBACK_MONTHS = ("MAY", "JUN", "JUL", "AUG", "SEP")
_HYBRID_FALLBACK_CITE = (
    "no committed climatology for this site — assumed May-Sep evaporative-assist window "
    "(temperate mid-latitude ET0 > precip season); regenerate with `watermark onboard`"
)


def _liters_per_day_from_mgd(mgd: float) -> float:
    """Volumetric flow: million gallons/day -> liters/day."""
    return mgd * 1_000_000.0 * _L_PER_GAL


def _mgd_from_liters_per_day(liters_per_day: float) -> float:
    """Volumetric flow: liters/day -> million gallons/day."""
    return liters_per_day / _L_PER_GAL / 1_000_000.0


def _consumptive_mgd_from_power(it_load_mw: float, wue_l_per_kwh: float) -> float:
    """Evaporative consumptive water (MGD) = IT energy x WUE."""
    liters_per_day = it_load_mw * 1_000.0 * 24.0 * wue_l_per_kwh  # kW x h/day x L/kWh
    return _mgd_from_liters_per_day(liters_per_day)


def _wue_from_consumptive_mgd(it_load_mw: float, consumptive_mgd: float) -> float:
    """Inverse of :func:`_consumptive_mgd_from_power`: the WUE (L/kWh) a consumptive draw implies.

    The evaporative tower uses this to cross-check a blowdown-method upper bound against the
    physical WUE ceiling (#1616): consumptive / IT energy = the implied water-use effectiveness.
    Returns 0 for a zero IT load (no energy denominator), so the caller's ceiling test is a
    no-op rather than a divide-by-zero.
    """
    energy_kwh_per_day = it_load_mw * 1_000.0 * 24.0  # kW x h/day
    if energy_kwh_per_day <= 0.0:
        return 0.0
    return _liters_per_day_from_mgd(consumptive_mgd) / energy_kwh_per_day


def it_load_mw_from_once_through_withdrawal(
    withdrawal_mgd: float, *, heat_reject_multiplier: float = _OT_HEAT_REJECT_MULT
) -> float:
    """Invert :func:`_derive_once_through`: withdrawal (MGD) -> IT load (MW).

    The once-through *consumptive* is only ~1-2% forced evaporation of the withdrawal, so
    it does not invert through a tower WUE. The withdrawal itself is the heat-rejection
    basis (``withdrawal = heat rejection / (rho x c x dT)``, heat rejection = IT x the
    cooling-overhead multiplier); this reverses that through the same :data:`_OT_LPD_PER_MW`
    factor **and** divides the ``heat_reject_multiplier`` back out (#1153), so a Method-2
    cross-check reconciles to the facility's own *IT* load — not the inflated rejected-heat
    load. Pass the facility's own multiplier when it overrides the ~1.15 default.
    """
    reject_mw = _liters_per_day_from_mgd(withdrawal_mgd) / _OT_LPD_PER_MW
    return reject_mw / heat_reject_multiplier


_MONTH_ORDER = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _window_label(months: list[str]) -> str:
    """A faithful label for an assist window: a span only when the months are contiguous.

    A climatology can return a gapped window (or one that wraps the year-end); collapsing
    it to ``first-last`` would misstate the assist months, so those list explicitly.
    """
    if not months:
        return "none"
    idx = [_MONTH_ORDER.index(m) for m in months]
    if idx == list(range(idx[0], idx[0] + len(idx))):
        return f"{months[0]}-{months[-1]}" if len(months) > 1 else months[0]
    return ", ".join(months)


def consumptive_range_label(basis: CoolingBasis) -> str:
    """The basis's consumptive figure for display: a single value when low == high.

    Shared by the CLI and the report renderer so a point estimate (e.g. closed_loop_dry's
    0 MGD) never prints as an awkward ``0-0 MGD`` range.
    """
    low, high = basis.consumptive_low, basis.consumptive_high
    if low.value == high.value:
        return f"{low.value:g} {low.unit}"
    return f"{low.value:g}-{high.value:g} {high.unit}"


@dataclass(frozen=True)
class CoolingParams:
    """Per-call overrides for a derivation (sensitivity sweeps).

    ``None`` means: resolve from the facility's disclosed override, else the archetype
    default. An explicit value wins over both and keeps the archetype's citation.
    """

    it_load_mw: float | None = None
    blowdown_mgd: float | None = None
    wue_l_per_kwh: float | None = None
    cycles_of_concentration: float | None = None
    heat_reject_multiplier: float | None = None


DeriveFn = Callable[[SiteFacility | None, CoolingParams, Settings], CoolingBasis]


@dataclass(frozen=True)
class CoolingModelSpec:
    """One cooling archetype: its identity, display alias, and derivation."""

    id: CoolingModelType
    display_name: str
    alias: str | None  # the ambiguous industry "open/closed loop" label, display-only
    mechanism: str  # one-line physical mechanism
    derive: DeriveFn


COOLING_MODELS: dict[CoolingModelType, CoolingModelSpec] = {}


def register(spec: CoolingModelSpec) -> CoolingModelSpec:
    COOLING_MODELS[spec.id] = spec
    return spec


def get(model: CoolingModelType | str) -> CoolingModelSpec:
    key = CoolingModelType(model)
    if key not in COOLING_MODELS:
        raise KeyError(f"unregistered cooling model {key!r}; known: {sorted(COOLING_MODELS)}")
    return COOLING_MODELS[key]


def resolve_cooling_model(
    facility: SiteFacility | None, *, override: CoolingModelType | str | None = None
) -> CoolingModelType:
    """The active archetype: explicit override > the facility's field > ``off`` (no facility).

    A facility that never set ``cooling_model`` carries the field default ``unknown`` —
    it must never silently inherit the water-intensive evaporative model (#1054).
    """
    if override is not None:
        return CoolingModelType(override)
    if facility is None:
        return CoolingModelType.OFF
    return facility.cooling_model


# --- shared input resolution ------------------------------------------------------------


def _resolve_it_load(
    facility: SiteFacility | None, params: CoolingParams
) -> tuple[float, float, float, str] | None:
    """The IT load's central value + its disclosed low/high range + the load-basis citation.

    The range is the **power-side uncertainty** the cooling-water bracket must reflect
    (#1632): an air-permit-grounded load is a bracket (N+1 backup ≈ IT — Lima 250-300),
    a floor-area screen is a density bracket. ``low``/``high`` fall back to ``central``
    for a point override (``CoolingParams.it_load_mw``), where there is no range to widen
    the water bracket with. The ``SiteFacility`` validator already enforces that the
    it-load triple is all-set or all-None.

    ``None`` when there is **no resolvable load** — no facility, or one whose load is
    entirely ``[open]`` (#1628). There is no module fallback to stand in: substituting one
    site's air-permit basis for another's silence is the leak this module refuses (#1634).
    ``derive_cooling_basis`` rejects that case for every archetype but ``off``, which
    reports an explicit zero instead.
    """
    if params.it_load_mw is not None:
        it = it_low = it_high = params.it_load_mw
    elif facility is not None and facility.it_load_mw is not None:
        it = facility.it_load_mw
        it_low = facility.it_load_low_mw if facility.it_load_low_mw is not None else it
        it_high = facility.it_load_high_mw if facility.it_load_high_mw is not None else it
    else:
        return None
    # A site-plan-grounded facility (Urbana) has no air permit; its IT load is a floor-area
    # screening bracket cited via ``it_load_citation``. A load supplied purely as an override
    # names the override as its basis — it is not this facility's disclosure.
    cite = (facility.air_permit_citation or facility.it_load_citation) if facility else None
    return it, it_low, it_high, cite or _IT_LOAD_OVERRIDE_CITE


def _require_it_load(
    facility: SiteFacility | None, params: CoolingParams
) -> tuple[float, float, float, str]:
    """:func:`_resolve_it_load` for the archetypes that cannot be derived without a load.

    ``derive_cooling_basis`` already refuses these upstream; this is the type-level guarantee
    for a spec invoked directly, and it names the same refusal rather than falling back.
    """
    resolved = _resolve_it_load(facility, params)
    if resolved is None:
        raise ValueError(
            "no resolvable IT load (no facility, or the facility's load is entirely [open]) — "
            "only `off` is derivable without one; another site's constants are never substituted"
        )
    return resolved


def _it_load_pv(it_load_mw: float, citation: str) -> ProvenancedValue:
    """The IT load as an ``[inference]`` (``derived``) — never ``[verified: document]`` (#1697).

    An air permit discloses the *backup* capacity (genset count x rating), not the IT
    load: the load is inferred from it (N+1 — IT ~= backup net of mechanical overhead) or
    from floor-area screening. So it is ``derived`` in every case, and the permit citation
    it carries is the derivation *basis*, not a disclosure of the load itself. The single
    home for this decision, so the five archetype derivations can't drift on it.
    """
    return ProvenancedValue.derived(it_load_mw, "MW", citation=citation)


def _resolve_wue(facility: SiteFacility | None, params: CoolingParams) -> tuple[float, str]:
    if params.wue_l_per_kwh is not None:
        return params.wue_l_per_kwh, _WUE_CITE
    if facility is not None and facility.wue_l_per_kwh is not None:
        return facility.wue_l_per_kwh, facility.wue_citation or _WUE_CITE
    return _WUE_L_PER_KWH, _WUE_CITE


def _resolve_cycles(facility: SiteFacility | None, params: CoolingParams) -> tuple[float, str]:
    if params.cycles_of_concentration is not None:
        cycles, cite = params.cycles_of_concentration, _CYCLES_CITE
    elif facility is not None and facility.cycles_of_concentration is not None:
        cycles, cite = facility.cycles_of_concentration, facility.cycles_citation or _CYCLES_CITE
    else:
        cycles, cite = _CYCLES, _CYCLES_CITE
    # Cycles of concentration is the makeup/blowdown ratio — physically always > 1. A
    # ``cycles <= 1`` override makes the evaporative fraction (CoC-1)/CoC zero or negative
    # (and CoC=0 divides by zero), silently yielding a non-physical basis. Reject it at the
    # source rather than propagating a bad ``frac`` through both tower and hybrid math (#1170).
    if cycles <= 1.0:
        raise ValueError(
            f"cycles of concentration must be > 1 (got {cycles:g}); CoC <= 1 gives a "
            "zero/negative evaporative fraction (CoC-1)/CoC — non-physical for a "
            f"recirculating tower. Check the cited override: {cite}"
        )
    return cycles, cite


def _resolve_heat_reject_mult(
    facility: SiteFacility | None, params: CoolingParams
) -> tuple[float, str]:
    if params.heat_reject_multiplier is not None:
        return params.heat_reject_multiplier, _OT_HEAT_REJECT_CITE
    if facility is not None and facility.heat_reject_multiplier is not None:
        return (
            facility.heat_reject_multiplier,
            facility.heat_reject_multiplier_citation or _OT_HEAT_REJECT_CITE,
        )
    return _OT_HEAT_REJECT_MULT, _OT_HEAT_REJECT_CITE


def reject_heat_load(
    facility: SiteFacility | None, params: CoolingParams | None = None
) -> ProvenancedValue | None:
    """The condenser heat-rejection load (MW), the heat-side peer of ``makeup_demand`` (#1717).

    Already computed inside :func:`_derive_once_through` (``reject_mw = IT x heat_reject_multiplier``)
    but discarded there after backing out a *water volume*; the thermal-discharge screen
    (:mod:`watermark.hydrology.thermal`) needs the heat load itself. Rejected heat is the IT
    (server) load **plus** the cooling-system work that moves it (~1.15 overhead), so it is
    defined for *every* archetype with a resolvable IT load — the tower rejects it to the
    atmosphere, once-through to the receiving water, a dry loop to the air — the split is the
    thermal screen's concern, not this accessor's.

    Carries the disclosed IT-load range (Lima 250-300 MW -> 287.5-345 MW rejected) as a
    quantitative band, and is an ``[inference]`` (``derived``) like the IT load it scales — the
    air permit discloses backup capacity, not the load, and never the heat rejection. Returns
    ``None`` when there is no resolvable *facility* IT load (``facility is None``, or a
    facility whose load is entirely ``[open]``) — mirroring the guard in
    :func:`watermark.hydrology.cooling.derive_cooling_basis`. A ``params.it_load_mw`` override
    (sensitivity runs) supplies the load and lifts the guard.
    """
    params = params or CoolingParams()
    resolved = _resolve_it_load(facility, params)
    if resolved is None:
        return None
    it, it_low, it_high, it_cite = resolved
    mult, mult_cite = _resolve_heat_reject_mult(facility, params)
    return ProvenancedValue.derived(
        round(it * mult, 1),
        "MW",
        citation=(
            f"condenser heat rejection = {it:g} MW IT x {mult:g} cooling overhead; "
            f"{it_cite}; {mult_cite}"
        ),
        low=round(it_low * mult, 1),
        high=round(it_high * mult, 1),
    )


# --- archetype derivations --------------------------------------------------------------


def _derive_off(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """No cooling-water load — every water quantity is an explicit zero, not an absence."""
    resolved = _resolve_it_load(facility, params)
    if resolved is not None:
        it, _it_low, _it_high, it_cite = resolved
        it_load = _it_load_pv(it, it_cite)
    else:
        # No facility at all, or one whose load is entirely [open] (#1628). Either way this
        # site has no IT figure of its own — report the absence, never another site's (#1634).
        why = (
            "no identified cooling-water facility (SiteProfile.facility is None)"
            if facility is None
            else "the disclosed facility's IT load is entirely [open] — no load figure on record"
        )
        it_load = ProvenancedValue.assume(0.0, "MW", why=why)
    zero_cite = "cooling model `off`: no cooling-water load"
    return CoolingBasis(
        cooling_model=CoolingModelType.OFF,
        it_load=it_load,
        consumptive_fraction=ProvenancedValue.derived(0.0, "fraction", citation=zero_cite),
        makeup_demand=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        consumptive_low=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        consumptive_high=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        method="no cooling-water load",
    )


def _derive_evaporative_tower(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """Recirculating wet tower (alias "open loop") — the two-method Lima bracket, verbatim.

    Top-down power x WUE (central) vs bottom-up blowdown x cycles-of-concentration
    (upper bound); consumptive fraction = (CoC-1)/CoC. This is the pre-taxonomy
    ``derive_cooling_basis`` math moved into its archetype (#1055) — Lima's committed
    figures are regression-locked against it.

    **The two methods are independent of each other, not of the water balance (#1634).**
    The blowdown the bottom-up bound rests on is the SAME documented discharge the balance
    carries as the campus ``return_flow`` (Lima: the ~2.5 MGD FM-2 industrial discharge —
    see :func:`watermark.hydrology.balance._campus_node`). It cross-checks the power basis,
    but an error in that one document moves the upper bound and the routed return flow
    together — never read the pair as two independent observations of the campus.
    """
    it_load_mw, it_load_low, it_load_high, it_load_cite = _require_it_load(facility, params)
    wue_l_per_kwh, wue_cite = _resolve_wue(facility, params)
    cycles, cycles_cite = _resolve_cycles(facility, params)
    blowdown_mgd = params.blowdown_mgd
    if blowdown_mgd is None and facility is not None:
        blowdown_mgd = facility.blowdown_mgd
    blowdown_cite = (
        facility.blowdown_citation
        if (facility and facility.blowdown_citation)
        else _BLOWDOWN_OVERRIDE_CITE  # an override, never another site's documented discharge
    )

    frac = (cycles - 1.0) / cycles  # evaporation / makeup
    # Central power x WUE — drives the central intake (makeup_demand) and the headline
    # consumptive. Kept on the CENTRAL IT load so the central figures stay stable while the
    # low/high bracket widens with the disclosed MW range (#1632).
    consumptive_central = _consumptive_mgd_from_power(it_load_mw, wue_l_per_kwh)
    makeup = consumptive_central / frac if frac > 0 else consumptive_central
    # Power-side uncertainty (#1632): the low bound is LOW IT x WUE, and the high bound is at
    # least HIGH IT x WUE — so the consumptive bracket reflects the disclosed MW range even
    # when no blowdown cross-check is on record (was: a degenerate low == high == central).
    consumptive_low = _consumptive_mgd_from_power(it_load_low, wue_l_per_kwh)
    consumptive_power_high = _consumptive_mgd_from_power(it_load_high, wue_l_per_kwh)
    low_cite = f"{it_load_low:g} MW (low IT) x {wue_l_per_kwh:g} L/kWh (power x WUE)"
    consumptive_high_capped = False  # WS-16 (#1616): set when the WUE-ceiling cap binds
    if blowdown_mgd is not None:
        blowdown_consumptive = blowdown_mgd * (cycles - 1.0)  # blowdown x (CoC-1) = evaporation
        # WS-16 (#1616): bound the blowdown method to a physical WUE ceiling. The disclosed
        # discharge is a valid *cooling* upper bound only if it is all cooling-tower blowdown;
        # cross-check the cooling WUE it implies against the empirical evaporative ceiling
        # (never below the facility's own central WUE, so the cap can't invert the low/high
        # bracket). The cross-check is at the HIGH IT load — the upper bound's energy
        # denominator (#1632) — so the cap co-scales with the disclosed MW range. Above the
        # ceiling the discharge is unreachable for cooling alone — it bundles non-cooling
        # (process/sanitary) flow — so cap the cooling-only bound to the ceiling.
        ceiling_wue = max(wue_l_per_kwh, _WUE_CEILING_L_PER_KWH)
        implied_wue = _wue_from_consumptive_mgd(it_load_high, blowdown_consumptive)
        if implied_wue > ceiling_wue:
            consumptive_high_capped = True
            consumptive_high = _consumptive_mgd_from_power(it_load_high, ceiling_wue)
            high_cite = (
                f"cooling upper bound capped at the WUE ceiling: {it_load_high:g} MW (high IT) x "
                f"{ceiling_wue:g} L/kWh = {consumptive_high:.2f} MGD. The disclosed "
                f"{blowdown_mgd:g} MGD blowdown x (CoC-1) = {blowdown_consumptive:g} MGD implies "
                f"~{implied_wue:.1f} L/kWh cooling WUE, above the ~{ceiling_wue:g} L/kWh ceiling, "
                f"so the {blowdown_mgd:g} MGD discharge is not all cooling blowdown (it bundles "
                f"process/sanitary flow) and cooling alone can't reach it. {_WUE_CEILING_CITE}; "
                f"{blowdown_cite}"
            )
            # Intake at the capped bound follows the evap fraction (consumptive / frac), NOT the
            # uncapped blowdown x CoC — that inflated intake belongs to the discarded raw figure.
            makeup_high_cite = (
                f"upper-bound intake = capped consumptive {consumptive_high:.2f} MGD / evap "
                "fraction (WUE-ceiling cap; disclosed blowdown bundles non-cooling flow)"
            )
        else:
            consumptive_high = blowdown_consumptive
            high_cite = f"{blowdown_mgd:g} MGD blowdown x (CoC-1); {blowdown_cite}"
            # The blowdown method implies a genuinely larger intake: makeup = blowdown x CoC
            # (= consumptive_high / evap fraction). State that derivation directly — reusing the
            # consumptive `(CoC-1)` citation here read as the makeup formula, which it is not.
            makeup_high_cite = (
                f"upper-bound intake = {blowdown_mgd:g} MGD blowdown x CoC({cycles:g}) = "
                f"{blowdown_mgd * cycles:g} MGD; {blowdown_cite}"
            )
        # The high-IT power method is a floor on the upper bound (#1632): a disclosed blowdown
        # below it must not shrink the bracket the MW range already opened. (Cannot fire when
        # capped: the cap is HIGH IT x ceiling_wue >= HIGH IT x WUE = the power high.)
        if consumptive_power_high > consumptive_high:
            consumptive_high = consumptive_power_high
            high_cite = (
                f"{it_load_high:g} MW (high IT) x {wue_l_per_kwh:g} L/kWh (power x WUE) — "
                "exceeds the disclosed-blowdown bound"
            )
            makeup_high_cite = "upper-bound intake = high-IT power-method makeup (power x WUE)"
    else:
        # No disclosed discharge for this site — the HIGH IT power method is the high bound,
        # and the intake at that bound follows the same evap fraction (#1632).
        consumptive_high = consumptive_power_high
        high_cite = (
            f"{it_load_high:g} MW (high IT) x {wue_l_per_kwh:g} L/kWh "
            "(power x WUE; no disclosed blowdown)"
        )
        makeup_high_cite = "upper-bound intake = high-IT power-method makeup (power x WUE)"

    if frac > 0:
        makeup_high_value = round(consumptive_high / frac, 2)
    else:
        # Degenerate CoC <= 1 (evap fraction non-positive): the value falls back to the
        # central makeup, so the citation must describe that, not the blowdown scaling.
        makeup_high_value = round(makeup, 2)
        makeup_high_cite = (
            "upper-bound intake = central makeup (CoC <= 1, evap fraction non-positive)"
        )

    basis = CoolingBasis(
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        it_load=_it_load_pv(it_load_mw, it_load_cite),
        wue=ProvenancedValue.assume(wue_l_per_kwh, "L/kWh", why=wue_cite),
        cycles_of_concentration=ProvenancedValue.assume(cycles, "ratio", why=cycles_cite),
        consumptive_fraction=ProvenancedValue.derived(
            round(frac, 3), "fraction", citation=f"(CoC-1)/CoC at CoC={cycles:g}"
        ),
        makeup_demand=ProvenancedValue.derived(
            round(makeup, 2),
            "MGD",
            citation=f"{it_load_mw:g} MW x {wue_l_per_kwh:g} L/kWh / evap fraction",
        ),
        # Intake at the upper consumptive bound. With disclosed blowdown this is a genuinely
        # larger withdrawal (blowdown x CoC = consumptive_high / (CoC-1)/CoC); with no disclosed
        # blowdown the high bound is the power method itself, so the intake is unchanged from
        # the central makeup (#1153). Either way `refill` reads this rather than dividing
        # consumptive_high by the fraction itself.
        makeup_high=ProvenancedValue.derived(
            makeup_high_value,
            "MGD",
            citation=makeup_high_cite,
        ),
        consumptive_low=ProvenancedValue.derived(
            round(consumptive_low, 2),
            "MGD",
            citation=low_cite,
        ),
        consumptive_high=ProvenancedValue.derived(
            round(consumptive_high, 2),
            "MGD",
            citation=high_cite,
        ),
    )
    # WS-16 (#1616): record whether the WUE-ceiling cap bound the upper estimate, so the
    # report generator reads an explicit flag instead of string-matching the citation.
    basis._consumptive_high_capped = consumptive_high_capped
    return basis


def _derive_once_through(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """Surface-water pass-through (alias "open once-through") — big withdrawal, small loss.

    Withdrawal = heat rejection / (rho x c x dT); nearly all of it returns warmer.
    Heat rejected at the condenser is the IT load **plus** cooling-system work, so the
    driving load is ``IT x heat_reject_multiplier`` (~1.15), not bare IT (#1153) — bare IT
    understates the withdrawal 10-40%. The consumptive share is the downstream forced
    evaporation induced by the thermal rise, ~1-2% of withdrawal (Diehl & Harris 2014).
    No tower, so no WUE/CoC.

    **dT coupling (WS-25).** The ~1-2% band is a fraction of *withdrawal*, and the withdrawal
    scales inversely with the condenser dT for a fixed rejected heat — so the coefficient is
    only dT-independent at the assumed ~10 degC dT it is defined at (:data:`_OT_DELTA_T_C`).
    Both the withdrawal and its forced-evaporation share are driven off that one dT here, so
    the coupling is internally consistent; a facility that discloses a different dT would need
    the coefficient re-anchored to its rejected heat rather than re-used verbatim.
    """
    it_load_mw, it_load_low, it_load_high, it_load_cite = _require_it_load(facility, params)
    mult, mult_cite = _resolve_heat_reject_mult(facility, params)
    reject_mw = it_load_mw * mult
    # Rejected heat -> withdrawal through the single-source per-MW flow factor, so the forward
    # and its inverse (it_load_mw_from_once_through_withdrawal) can never drift.
    withdrawal_mgd = _mgd_from_liters_per_day(reject_mw * _OT_LPD_PER_MW)
    # Power-side uncertainty (#1632): the withdrawal (and its forced-evaporation share) scale
    # with the IT load, so the low/high consumptive bounds use the LOW/HIGH IT withdrawals.
    # ``makeup_demand`` (the central withdrawal) is unchanged.
    withdrawal_low = _mgd_from_liters_per_day(it_load_low * mult * _OT_LPD_PER_MW)
    withdrawal_high = _mgd_from_liters_per_day(it_load_high * mult * _OT_LPD_PER_MW)
    frac_central = (_OT_EVAP_FRAC_LOW + _OT_EVAP_FRAC_HIGH) / 2.0
    return CoolingBasis(
        cooling_model=CoolingModelType.ONCE_THROUGH,
        it_load=_it_load_pv(it_load_mw, it_load_cite),
        consumptive_fraction=ProvenancedValue.assume(
            frac_central, "fraction", why=f"{_OT_EVAP_CITE} (central)"
        ),
        makeup_demand=ProvenancedValue.derived(
            round(withdrawal_mgd, 2),
            "MGD",
            citation=(
                f"{it_load_mw:g} MW IT x {mult:g} heat-rejection overhead = {reject_mw:g} MW "
                f"rejected / (rho x c x dT); {_OT_DELTA_T_CITE}; {mult_cite} — once-through "
                "withdrawal, nearly all returned"
            ),
        ),
        # The intake at the upper consumptive bound is the HIGH-IT withdrawal (#1632): since the
        # consumptive high uses the high-IT withdrawal, the intake it evaporates from grows with
        # the MW range too — so ``refill`` reads this, not the central ``makeup_demand``.
        makeup_high=ProvenancedValue.derived(
            round(withdrawal_high, 2),
            "MGD",
            citation=(
                f"high-IT ({it_load_high:g} MW) withdrawal = {it_load_high:g} MW x {mult:g} "
                f"heat-rejection overhead / (rho x c x dT) — the intake at the upper consumptive "
                f"bound; {_OT_DELTA_T_CITE}; {mult_cite}"
            ),
        ),
        consumptive_low=ProvenancedValue.derived(
            round(withdrawal_low * _OT_EVAP_FRAC_LOW, 2),
            "MGD",
            citation=(
                f"low-IT ({it_load_low:g} MW) withdrawal x {_OT_EVAP_FRAC_LOW:g} forced "
                f"evaporation; {_OT_EVAP_CITE}"
            ),
        ),
        consumptive_high=ProvenancedValue.derived(
            round(withdrawal_high * _OT_EVAP_FRAC_HIGH, 2),
            "MGD",
            citation=(
                f"high-IT ({it_load_high:g} MW) withdrawal x {_OT_EVAP_FRAC_HIGH:g} forced "
                f"evaporation; {_OT_EVAP_CITE}"
            ),
        ),
        method=(
            "once-through pass-through: withdrawal = heat rejection / (rho x c x dT), "
            "heat rejection = IT x cooling-overhead multiplier; "
            "consumptive = ~1-2% forced evaporation of the thermal rise"
        ),
    )


def _derive_closed_loop_dry(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """Sealed working fluid + dry/air heat rejection (alias "closed loop") — ~0 water.

    Consumptive use is ~0 at screening grade (initial fill plus minor leakage makeup);
    the trade-off is an **energy penalty** (higher fan load / PUE, worse hot-day
    performance), which is not a water quantity and is not fabricated into one. WUE and
    cycles-of-concentration do not apply — they stay ``None``, never faked.
    """
    # ~0 water: the power-side range (#1632) has no consumptive bracket to widen here.
    it_load_mw, _it_low, _it_high, it_load_cite = _require_it_load(facility, params)
    zero_cite = (
        "sealed closed loop, dry/air heat rejection: ~0 consumptive at screening grade "
        "(initial fill + minor leakage makeup only)"
    )
    return CoolingBasis(
        cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
        it_load=_it_load_pv(it_load_mw, it_load_cite),
        consumptive_fraction=ProvenancedValue.derived(0.0, "fraction", citation=zero_cite),
        makeup_demand=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        consumptive_low=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        consumptive_high=ProvenancedValue.derived(0.0, "MGD", citation=zero_cite),
        method=(
            "sealed fluid + dry/air rejection; ~0 consumptive water — the trade-off is an "
            "energy penalty (fan load / PUE), not a water quantity"
        ),
    )


def _assist_months(settings: Settings) -> tuple[list[str], str]:
    """The evaporative-assist window: months where ET0 > precip, from committed climatology.

    Falls back to the stated May-Sep assumption when the site has no climatology artifact
    — a modeling input, tagged as such in the citation it returns.
    """
    from watermark.hydrology import climate, et

    clim = climate.load_climatology(settings=settings)
    precip = clim.get("PRECTOTCORR") if clim is not None else None
    if clim is None or precip is None:
        return list(_HYBRID_FALLBACK_MONTHS), _HYBRID_FALLBACK_CITE
    et0 = et.penman_monteith_et0(clim)
    # Round the net-atmospheric deficit to 3 dp before the > 0 test so this assist window
    # and ``scenario.evaluate_seasonal``'s growing-season screen agree at the boundary — an
    # unrounded compare would flag a month with net in (0, 0.0005] as assist here but not
    # there, disagreeing on the derived annual average vs the seasonal screen (#1170).
    months = [m for m in et._MONTHS if round(et0.monthly_mm_day[m] - precip.monthly[m], 3) > 0]
    cite = (
        "assist window = ET0 > precip months from the committed NASA POWER normals "
        "+ FAO-56 ET0 (see hydrology climatology artifact)"
    )
    return months, cite


def _derive_hybrid_adiabatic(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """Dry cooling with seasonal evaporative (adiabatic) assist — month-varying draw.

    Tower-like (power x WUE) in the assist months where reference ET0 exceeds precip,
    ~0 consumptive otherwise (#1058). ``consumptive_high`` is the warm-season *rate*;
    ``consumptive_low`` / ``makeup_demand`` are the annual averages; ``seasonal_months``
    records the assist window so :func:`watermark.hydrology.scenario.evaluate_seasonal`
    can zero the winter months instead of smearing an annual average across the year.
    """
    # Deliberately not power-range-propagated (#1632): for hybrid, consumptive_low/high
    # encode SEASON (annual average vs the warm-season assist rate that
    # ``scenario.evaluate_seasonal`` reads as a point rate), not power-uncertainty bounds —
    # folding the IT-load range into consumptive_high would corrupt that seasonal rate.
    it_load_mw, _it_low, _it_high, it_load_cite = _require_it_load(facility, params)
    wue_l_per_kwh, wue_cite = _resolve_wue(facility, params)
    cycles, cycles_cite = _resolve_cycles(facility, params)
    months, window_cite = _assist_months(settings)
    frac_year = len(months) / 12.0

    frac = (cycles - 1.0) / cycles
    warm_consumptive = _consumptive_mgd_from_power(it_load_mw, wue_l_per_kwh)
    warm_makeup = warm_consumptive / frac if frac > 0 else warm_consumptive
    window = _window_label(months)
    # No assist window at all (ET0 never exceeds precip) ⇒ the facility runs dry
    # year-round — there is no "warm-season rate" to report as the high bound.
    if months:
        high_value = round(warm_consumptive, 2)
        high_cite = (
            f"warm-season (assist) rate: {it_load_mw:g} MW x {wue_l_per_kwh:g} L/kWh "
            "(power x WUE) — applies in the assist months, ~0 otherwise"
        )
    else:
        high_value = 0.0
        high_cite = (
            "no assist window — ET0 never exceeds precip in the climatology, so the "
            "facility runs dry year-round (~0 consumptive)"
        )

    return CoolingBasis(
        cooling_model=CoolingModelType.HYBRID_ADIABATIC,
        it_load=_it_load_pv(it_load_mw, it_load_cite),
        wue=ProvenancedValue.assume(
            wue_l_per_kwh, "L/kWh", why=f"warm-season (assist) WUE: {wue_cite}"
        ),
        cycles_of_concentration=ProvenancedValue.assume(
            cycles, "ratio", why=f"assist-mode {cycles_cite}"
        ),
        consumptive_fraction=ProvenancedValue.derived(
            round(frac, 3),
            "fraction",
            citation=f"(CoC-1)/CoC at CoC={cycles:g}, during assist months only",
        ),
        makeup_demand=ProvenancedValue.derived(
            round(warm_makeup * frac_year, 2),
            "MGD",
            citation=(
                f"annual average: warm-season makeup x {len(months)}/12 assist months "
                f"({window}); {window_cite}"
            ),
        ),
        consumptive_low=ProvenancedValue.derived(
            round(warm_consumptive * frac_year, 2),
            "MGD",
            citation=(
                f"annual average: {it_load_mw:g} MW x {wue_l_per_kwh:g} L/kWh x "
                f"{len(months)}/12 assist months ({window}); {window_cite}"
            ),
        ),
        consumptive_high=ProvenancedValue.derived(high_value, "MGD", citation=high_cite),
        method=(
            "dry cooling with seasonal evaporative (adiabatic) assist in ET0 > precip "
            "months; the consumptive draw is month-varying, ~0 outside the assist window"
        ),
        seasonal_months=months,
    )


def _derive_unknown(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """Disclosed facility, undisclosed cooling method — a bracket, never an estimate.

    The range spans the plausible candidate archetypes: ``closed_loop_dry`` as the lower
    bound and ``evaporative_tower`` as the upper (#1057). ``makeup_demand`` and
    ``consumptive_fraction`` carry the evaporative **upper-bound envelope** (tagged
    ``assumption``, low confidence) so downstream plumbing stays total — but
    ``is_bracketed=True`` / ``method_disclosed=False`` mark that no single figure is an
    estimate, and the presentation tier must render the range and lock the headline.
    """
    dry = _derive_closed_loop_dry(facility, params, settings)
    tower = _derive_evaporative_tower(facility, params, settings)
    return CoolingBasis(
        cooling_model=CoolingModelType.UNKNOWN,
        it_load=tower.it_load,
        consumptive_fraction=ProvenancedValue.assume(
            tower.consumptive_fraction.value,
            "fraction",
            why=(
                "cooling method undisclosed — evaporative (CoC-1)/CoC upper-bound envelope, "
                "NOT an estimate; the lower-bound archetype consumes ~0"
            ),
        ),
        makeup_demand=ProvenancedValue.assume(
            tower.makeup_demand.value,
            "MGD",
            why=(
                "cooling method undisclosed — evaporative upper-bound envelope "
                f"({tower.makeup_demand.citation}); NOT an estimate"
            ),
        ),
        consumptive_low=ProvenancedValue.derived(
            dry.consumptive_low.value,
            "MGD",
            citation=(
                "closed_loop_dry lower bound — cooling method undisclosed; "
                f"{dry.consumptive_low.citation}"
            ),
            confidence="low",
        ),
        consumptive_high=ProvenancedValue.derived(
            tower.consumptive_high.value,
            "MGD",
            citation=(
                "evaporative_tower upper bound — cooling method undisclosed; "
                f"{tower.consumptive_high.citation}"
            ),
            confidence="low",
        ),
        method=(
            "cooling method undisclosed — bracketed range: closed_loop_dry (low) to "
            "evaporative_tower (high); no single consumptive estimate exists"
        ),
        method_disclosed=False,
        is_bracketed=True,
    )


# --- the registry -----------------------------------------------------------------------

register(
    CoolingModelSpec(
        id=CoolingModelType.OFF,
        display_name="no cooling-water load",
        alias=None,
        mechanism="no cooling-water load (explicit zero, not an absence)",
        derive=_derive_off,
    )
)
register(
    CoolingModelSpec(
        id=CoolingModelType.EVAPORATIVE_TOWER,
        display_name="evaporative cooling tower",
        alias="open loop",
        mechanism="open recirculating wet tower: evaporation rejects heat; blowdown controls cycles",
        derive=_derive_evaporative_tower,
    )
)
register(
    CoolingModelSpec(
        id=CoolingModelType.ONCE_THROUGH,
        display_name="once-through surface water",
        alias="open once-through",
        mechanism="surface-water pass-through: large withdrawal, ~1-2% forced-evaporation loss",
        derive=_derive_once_through,
    )
)
register(
    CoolingModelSpec(
        id=CoolingModelType.CLOSED_LOOP_DRY,
        display_name="closed-loop dry (air-cooled)",
        alias="closed loop",
        mechanism="sealed working fluid + dry/air rejection: ~0 water, energy penalty instead",
        derive=_derive_closed_loop_dry,
    )
)
register(
    CoolingModelSpec(
        id=CoolingModelType.HYBRID_ADIABATIC,
        display_name="hybrid dry + adiabatic assist",
        alias=None,
        mechanism="dry cooling with seasonal evaporative assist in ET0 > precip months",
        derive=_derive_hybrid_adiabatic,
    )
)
register(
    CoolingModelSpec(
        id=CoolingModelType.UNKNOWN,
        display_name="undisclosed cooling method",
        alias=None,
        mechanism="facility disclosed, method not on record: bracketed range, never a headline",
        derive=_derive_unknown,
    )
)
