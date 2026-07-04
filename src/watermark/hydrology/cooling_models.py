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

# --- Lima-era module fallbacks (used only when a site has no SiteProfile.facility) -----
# These are the evaporative_tower defaults (#1055): disclosed / cited inputs for the
# reference build, kept as the last-resort fallback so the legacy call path is unchanged.
_GENSET_COUNT = 114
_GENSET_MW = 2.75  # ekW each, per the air permit
_BACKUP_MW = _GENSET_COUNT * _GENSET_MW  # ~313 MW
_IT_LOAD_MW = 275.0  # midpoint of the 250-300 MW estimate (IT ~= backup at N+1)
_AIR_PERMIT_CITE = (
    "OEPA Air PTI P0138965 (Facility 0302022054), committed "
    "data/extracted/permits/4132514.epa.yaml (final, 2026-05-28): "
    "114 hall gensets x 2.75 ekW = ~313 MW backup; IT ~250-300 MW (N+1). "
    "Per-engine ekW is from the draft public notice (3987141/3987144) — engine "
    "size is CBI-redacted in the final permit under a formal Ohio EPA trade-secret "
    "grant (OAC 3745-49-03, 2025-10-08; data/extracted/permits/3859883.epa.yaml), "
    "which also withholds cooling-system flowrates."
)

_WUE_L_PER_KWH = 1.8  # evaporative hyperscale; Google fleet avg ~1.1, evaporative higher
_WUE_CITE = "evaporative-cooled hyperscale WUE ~1.8 L/kWh (Google fleet avg ~1.1; 36 cooling towers on the air permit)"

_CYCLES = 5.0  # cooling-tower cycles of concentration (typical 4-6)
_CYCLES_CITE = "cooling-tower cycles of concentration ~5 (typical 4-6)"

_FM2_BLOWDOWN_MGD = 2.5  # documented FM-2 industrial discharge, as a blowdown upper bound
_FM2_CITE = (
    "bosc-fm2 2.5 MGD industrial discharge (CMAR RFQ §A.6), taken as cooling blowdown upper bound"
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
    "Diehl & Harris 2014, thermoelectric water-consumption coefficients)"
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


def _resolve_it_load(facility: SiteFacility | None, params: CoolingParams) -> tuple[float, str]:
    if params.it_load_mw is not None:
        it = params.it_load_mw
    elif facility is not None:
        it = facility.it_load_mw
    else:
        it = _IT_LOAD_MW
    cite = facility.air_permit_citation if facility else _AIR_PERMIT_CITE
    return it, cite


def _resolve_wue(facility: SiteFacility | None, params: CoolingParams) -> tuple[float, str]:
    if params.wue_l_per_kwh is not None:
        return params.wue_l_per_kwh, _WUE_CITE
    if facility is not None and facility.wue_l_per_kwh is not None:
        return facility.wue_l_per_kwh, facility.wue_citation or _WUE_CITE
    return _WUE_L_PER_KWH, _WUE_CITE


def _resolve_cycles(facility: SiteFacility | None, params: CoolingParams) -> tuple[float, str]:
    if params.cycles_of_concentration is not None:
        return params.cycles_of_concentration, _CYCLES_CITE
    if facility is not None and facility.cycles_of_concentration is not None:
        return facility.cycles_of_concentration, facility.cycles_citation or _CYCLES_CITE
    return _CYCLES, _CYCLES_CITE


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


# --- archetype derivations --------------------------------------------------------------


def _derive_off(
    facility: SiteFacility | None, params: CoolingParams, settings: Settings
) -> CoolingBasis:
    """No cooling-water load — every water quantity is an explicit zero, not an absence."""
    if facility is not None:
        it, it_cite = _resolve_it_load(facility, params)
        it_load = ProvenancedValue.from_document(it, "MW", citation=it_cite)
    else:
        it_load = ProvenancedValue.assume(
            0.0, "MW", why="no identified cooling-water facility (SiteProfile.facility is None)"
        )
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
    """
    it_load_mw, it_load_cite = _resolve_it_load(facility, params)
    wue_l_per_kwh, wue_cite = _resolve_wue(facility, params)
    cycles, cycles_cite = _resolve_cycles(facility, params)
    blowdown_mgd = params.blowdown_mgd
    if blowdown_mgd is None and facility is not None:
        blowdown_mgd = facility.blowdown_mgd
    blowdown_cite = (
        facility.blowdown_citation if (facility and facility.blowdown_citation) else _FM2_CITE
    )

    frac = (cycles - 1.0) / cycles  # evaporation / makeup
    consumptive_low = _consumptive_mgd_from_power(it_load_mw, wue_l_per_kwh)
    makeup = consumptive_low / frac if frac > 0 else consumptive_low
    if blowdown_mgd is not None:
        consumptive_high = blowdown_mgd * (cycles - 1.0)  # blowdown x (CoC-1) = evaporation
        high_cite = f"{blowdown_mgd:g} MGD blowdown x (CoC-1); {blowdown_cite}"
        # The blowdown method implies a genuinely larger intake: blowdown x CoC.
        makeup_high_cite = f"upper-bound intake = {high_cite} / evap fraction (blowdown x CoC)"
    else:
        # No disclosed discharge for this site — the power-method consumptive is the high bound,
        # and the intake at that bound is unchanged from the central power-method makeup.
        consumptive_high = consumptive_low
        high_cite = (
            f"{it_load_mw:g} MW x {wue_l_per_kwh:g} L/kWh (power x WUE; no disclosed blowdown)"
        )
        makeup_high_cite = (
            "upper-bound intake = central power-method makeup (no disclosed blowdown)"
        )

    if frac > 0:
        makeup_high_value = round(consumptive_high / frac, 2)
    else:
        # Degenerate CoC <= 1 (evap fraction non-positive): the value falls back to the
        # central makeup, so the citation must describe that, not the blowdown scaling.
        makeup_high_value = round(makeup, 2)
        makeup_high_cite = (
            "upper-bound intake = central makeup (CoC <= 1, evap fraction non-positive)"
        )

    return CoolingBasis(
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        it_load=ProvenancedValue.from_document(it_load_mw, "MW", citation=it_load_cite),
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
            citation=f"{it_load_mw:g} MW x {wue_l_per_kwh:g} L/kWh (power x WUE)",
        ),
        consumptive_high=ProvenancedValue.derived(
            round(consumptive_high, 2),
            "MGD",
            citation=high_cite,
        ),
    )


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
    """
    it_load_mw, it_load_cite = _resolve_it_load(facility, params)
    mult, mult_cite = _resolve_heat_reject_mult(facility, params)
    reject_mw = it_load_mw * mult
    # Rejected heat -> withdrawal through the single-source per-MW flow factor, so the forward
    # and its inverse (it_load_mw_from_once_through_withdrawal) can never drift.
    withdrawal_mgd = _mgd_from_liters_per_day(reject_mw * _OT_LPD_PER_MW)
    frac_central = (_OT_EVAP_FRAC_LOW + _OT_EVAP_FRAC_HIGH) / 2.0
    return CoolingBasis(
        cooling_model=CoolingModelType.ONCE_THROUGH,
        it_load=ProvenancedValue.from_document(it_load_mw, "MW", citation=it_load_cite),
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
        consumptive_low=ProvenancedValue.derived(
            round(withdrawal_mgd * _OT_EVAP_FRAC_LOW, 2),
            "MGD",
            citation=f"withdrawal x {_OT_EVAP_FRAC_LOW:g} forced evaporation; {_OT_EVAP_CITE}",
        ),
        consumptive_high=ProvenancedValue.derived(
            round(withdrawal_mgd * _OT_EVAP_FRAC_HIGH, 2),
            "MGD",
            citation=f"withdrawal x {_OT_EVAP_FRAC_HIGH:g} forced evaporation; {_OT_EVAP_CITE}",
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
    it_load_mw, it_load_cite = _resolve_it_load(facility, params)
    zero_cite = (
        "sealed closed loop, dry/air heat rejection: ~0 consumptive at screening grade "
        "(initial fill + minor leakage makeup only)"
    )
    return CoolingBasis(
        cooling_model=CoolingModelType.CLOSED_LOOP_DRY,
        it_load=ProvenancedValue.from_document(it_load_mw, "MW", citation=it_load_cite),
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
    months = [m for m in et._MONTHS if et0.monthly_mm_day[m] - precip.monthly[m] > 0]
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
    it_load_mw, it_load_cite = _resolve_it_load(facility, params)
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
        it_load=ProvenancedValue.from_document(it_load_mw, "MW", citation=it_load_cite),
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
