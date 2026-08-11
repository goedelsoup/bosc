"""Baseline vs data-center-buildout scenarios over the municipal water loop.

The dominant uncertainty in the loop is the campus's *consumptive* cooling demand —
evaporated water that never returns to the Ottawa/Auglaize basin. This module makes
that the knob: a :class:`Scenario` carries a cooling intake and a consumptive
fraction (both assumptions), and :func:`evaluate` computes the net basin loss and
sets it on the campus node's ``consumptive_use`` seam. :func:`diff` reports the new
draw against the **cited Ottawa 7Q10** (0.2 cfs) — the scale that makes the point:
at design low flow the river already nearly dries, so any material cooling draw is a
large multiple of what the Ottawa carries.

Results persist to ``data/scenarios/*.scenario.yaml`` — committed, reviewed, and
self-auditing (every number keeps its provenance tag).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.assimilative import check_assimilative
from watermark.hydrology.balance import (
    CAMPUS_COOLING_DERIVED_WARNING_PREFIX,
    build_water_balance,
)
from watermark.hydrology.connectors.nwis import DISCHARGE_CFS, fetch_streamflow
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.lowflow import (
    _normalize,
    low_flow_context,
    low_flow_for,
    seasonal_low_flows,
    summer_season_months,
)
from watermark.hydrology.model import (
    CoolingBasis,
    MonthlyWithdrawal,
    ProvenancedValue,
    Scenario,
    ScenarioDiff,
    ScenarioResult,
    SeasonalWithdrawal,
)
from watermark.hydrology.solver.parameters import round_sig
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger
from watermark.sites import CoolingModelType, active_profile, site_scoped_path

log = get_logger(__name__)


def baseline_scenario() -> Scenario:
    """The current system: no incremental cooling draw."""
    return Scenario(
        name="baseline",
        description="Current municipal loop, no data-center cooling draw.",
        cooling_model=CoolingModelType.OFF,
        cooling_demand=ProvenancedValue.assume(0.0, "MGD", why="baseline: no campus cooling load"),
        consumptive_fraction=ProvenancedValue.assume(0.0, "fraction", why="baseline"),
    )


def _ratio(value: float) -> float:
    """A low-flow multiple, rounded so a real ratio never publishes as zero (#1995).

    The convention is one decimal, which is right for the multiples this network was built on —
    Lima's cooling draw is a sizeable fraction of the Ottawa's 7Q10. Sidney is three orders of
    magnitude the other way (a contracted 0.0146 cfs against a 24.0 cfs reach), and one decimal
    rounds that to ``0.0``: a screen that reads as *no draw at all* rather than as a very small
    one, which is a different claim and the wrong one. Anything that would vanish keeps two
    significant figures instead; every value at the old scale is unchanged, so no committed
    artifact moves.
    """
    rounded = round(value, 1)
    return rounded if rounded else round_sig(value, 2)


def _stated_cooling_account(
    settings: Settings | None,
) -> tuple[ProvenancedValue, ProvenancedValue | None] | None:
    """The active facility's STATED cooling water account, if the record carries one (#1995).

    Returns ``(makeup, consumptive_fraction | None)`` — both ``document``-provenanced and
    carrying the facility's own citation — or ``None`` when nothing is stated.

    The fraction comes back only when the record states **both** sides of the account, because
    it is the *difference* that is the consumption: makeup less what returns to the sewer as
    blowdown. With a stated makeup and no stated blowdown the fraction is left to the archetype,
    which pairs a ``document`` intake with an ``assumption`` fraction — legible from the source
    tags, and better than inventing a return the record does not describe.
    """
    facility = active_profile(settings or get_settings()).facility
    if facility is None or facility.makeup_mgd is None or facility.makeup_citation is None:
        return None
    makeup = ProvenancedValue.from_document(facility.makeup_mgd, "MGD", facility.makeup_citation)
    # A return larger than the intake would make the consumed share NEGATIVE and publish it as
    # `derived` — a campus putting water back into the basin. `SiteFacility` refuses that pair at
    # construction, so this is the belt to that suspender: fall back to the archetype rather than
    # compute a fraction from an account that does not balance.
    if (
        facility.blowdown_mgd is None
        or facility.makeup_mgd <= 0
        or facility.blowdown_mgd > facility.makeup_mgd
    ):
        return makeup, None
    frac = ProvenancedValue.derived(
        (facility.makeup_mgd - facility.blowdown_mgd) / facility.makeup_mgd,
        "fraction",
        citation=(
            f"consumption is the difference between the stated makeup ({facility.makeup_mgd:g} "
            f"MGD) and the stated return ({facility.blowdown_mgd:g} MGD), both on the record — "
            f"see the makeup citation. NOT a cooling-model efficiency: it says what this "
            f"account returns, not how the heat is rejected."
        ),
    )
    return makeup, frac


def buildout_scenario(
    *,
    cooling_demand_mgd: float | None = None,
    consumptive_fraction: float | None = None,
    cooling_model: CoolingModelType | str | None = None,
    basis: CoolingBasis | None = None,
    settings: Settings | None = None,
) -> Scenario:
    """Data-center buildout with the site facility's cooling-archetype consumptive draw.

    Resolution order for the intake, most-grounded first (#1995):

    1. an explicit ``cooling_demand_mgd`` — a sensitivity sweep, tagged an assumption;
    2. the facility's **stated** ``makeup_mgd`` — a contracted or permitted withdrawal on the
       record, tagged ``document`` with its own citation;
    3. the sourced :class:`CoolingBasis` derived for the facility's ``cooling_model`` (#1056).

    Rung 2 is the one that is new, and it exists because Sidney inverts the network's usual
    shape: a campus that discloses no MW and no floor area, on top of an executed municipal
    service agreement that states the gallons outright. Deriving its water from the
    investment-scaled IT-load screen would stack an ``[inference]`` on an ``[inference]`` when
    the number is simply on the record. A stated quantity beating a derivation is the ordinary
    rule; what this adds is that the resulting scenario CARRIES that provenance, so the
    committed artifact cites the instrument rather than reading as a scenario knob someone typed.

    ``cooling_model`` overrides the archetype for sensitivity runs, and **a sweep suspends rung
    2**: the stated account describes the design the facility actually contracted for, so asking
    "what if this were an evaporative tower?" and then answering with the real account's gallons
    would model neither. An explicit archetype therefore falls through to its own derived demand.
    Without one, the derived basis is still built and still rides on ``Scenario.basis`` when a
    stated makeup wins — it becomes the cross-check rather than the source, which is the
    comparison a reader most wants (Sidney's contracted 0.0126 MGD against a 0-4.03 MGD envelope).
    """
    basis = basis or derive_cooling_basis(settings, cooling_model=cooling_model)
    stated = None if cooling_model is not None else _stated_cooling_account(settings)
    if cooling_demand_mgd is not None:
        cooling_demand = ProvenancedValue.assume(
            cooling_demand_mgd, "MGD", why="campus cooling intake — scenario override"
        )
    elif stated is not None:
        cooling_demand = stated[0]
    else:
        # Honesty guard (CLAUDE.md): a bracketed (undisclosed-method) basis carries the
        # evaporative envelope in `makeup_demand` for plumbing completeness, but it is not
        # an estimate — don't default the scenario knob to it. Require an explicit demand.
        makeup_pv = basis.headline_makeup()
        if makeup_pv is None:
            raise ValueError(
                f"cooling basis for {basis.cooling_model.value} is bracketed (undisclosed "
                "method) — pass an explicit cooling_demand_mgd for the sensitivity instead of "
                "defaulting to the bracket envelope"
            )
        cooling_demand = makeup_pv
    if consumptive_fraction is not None:
        frac = ProvenancedValue.assume(
            consumptive_fraction, "fraction", why="consumptive fraction — scenario override"
        )
    elif stated is not None and stated[1] is not None:
        frac = stated[1]
    else:
        frac = basis.consumptive_fraction
    return Scenario(
        name="buildout",
        description=(
            f"Data-center campus cooling draw ({basis.cooling_model.value}) on the "
            "municipal supply."
        ),
        cooling_model=basis.cooling_model,
        cooling_demand=cooling_demand,
        consumptive_fraction=frac,
        basis=basis,
    )


def evaluate(
    scenario: Scenario,
    *,
    settings: Settings | None = None,
    live: bool = True,
) -> ScenarioResult:
    """Evaluate a scenario: net consumptive loss, modified balance, low-flow context."""
    settings = settings or get_settings()
    loss_cfs = mgd_to_cfs(scenario.cooling_demand.value * scenario.consumptive_fraction.value)
    consumptive = ProvenancedValue.derived(
        loss_cfs,
        "cfs",
        citation=(
            f"{scenario.cooling_demand.value:g} MGD x {scenario.consumptive_fraction.value:g} "
            f"consumptive (scenario {scenario.name})"
        ),
    )

    balance = build_water_balance(settings=settings, live=live)
    campus = balance.node("bosc-campus")
    if campus is not None:
        campus.consumptive_use = consumptive
        # A no-cooling scenario (baseline) zeroes the campus draw, so the balance's derived
        # cooling caveat — a buildout-only figure — doesn't apply here; drop it.
        if scenario.cooling_model is CoolingModelType.OFF:
            balance.warnings[:] = [
                w
                for w in balance.warnings
                if not w.startswith(CAMPUS_COOLING_DERIVED_WARNING_PREFIX)
            ]

    profile = active_profile(settings)
    # The NAME is the site's display prose; the KEY is the cited reach it screens against, and on
    # a river carrying more than one cited reach they are not the same string (#1995) — see
    # `SiteProfile.receiving_low_flow_key`. Look up on the key, report under the name.
    receiving_water = profile.receiving_water_name
    low_flow_key = profile.receiving_low_flow_key or receiving_water
    receiving_7q10 = low_flow_for(low_flow_key, settings=settings)
    summer_30q10, one_q10 = seasonal_low_flows(low_flow_key, settings=settings)
    receiving_live = _receiving_live(settings=settings, live=live)

    # The campus's own routed industrial discharge (Lima's FM-2), read portably off the demand
    # node's return flow — the same grounded figure the balance already carries (#1633).
    demand = next(iter(balance.by_role("demand")), None)
    campus_routed_discharge = demand.return_flow if demand is not None else None

    return ScenarioResult(
        scenario=scenario,
        cooling_model=scenario.cooling_model,
        consumptive_loss=consumptive,
        receiving_7q10=receiving_7q10,
        receiving_summer_30q10=summer_30q10,
        receiving_1q10=one_q10,
        receiving_live=receiving_live,
        receiving_water_name=receiving_water,
        campus_routed_discharge=campus_routed_discharge,
        balance=balance,
        assimilative=check_assimilative(balance),
    )


def _receiving_live(*, settings: Settings, live: bool) -> ProvenancedValue | None:
    if not live:
        return None
    profile = active_profile(settings)
    try:
        readings = fetch_streamflow(sites=[profile.abstraction_gage], settings=settings)
    except Exception as exc:
        log.info("hydro.scenario.no_live", error=type(exc).__name__)
        return None
    flow = next(
        (r for r in readings if r.parameter_cd == DISCHARGE_CFS and r.value is not None), None
    )
    if flow is None:
        return None
    # Dated and down-weighted by the reading itself: a provisional ("P") real-time reading
    # is unreviewed and subject to revision (#1602), and a reading replayed past the IV
    # service's freshness window is not the current flow (#1621) — so neither enters the
    # scenario as an authoritative live flow.
    pv = flow.as_provenanced("cfs")
    if pv is None:
        return None

    # A site's abstraction gage is not always ON its receiving water, and where it is not, this
    # reading is a DIFFERENT waterbody's flow (#886). Wilmington is the case: its receiving water
    # is Lytle Creek (DA 9.0 mi², 7Q10 0.0068 cfs) but the nearest ACTIVE discharge gage is the
    # Little Miami at Milford, DA 1,203 mi² — 133x the drainage area, reading hundreds of cfs.
    # Presented as "Lytle Creek live flow" that is not context, it is a contradiction of the
    # screen sitting three lines above it. The value is real and stays; what it measures is
    # stated on it, so no consumer can attribute it to the receiving water by default.
    water = _normalize(profile.receiving_water_name or "")
    if water and water not in (flow.name or "").lower():
        pv = pv.model_copy(
            update={
                "citation": (
                    f"{pv.citation} — NOT a reading of {profile.receiving_water_name}: this "
                    "site's nearest active discharge gage is on a different waterbody, so treat "
                    "this as regional context only, never as the receiving reach's own flow"
                )
            }
        )
    return pv


def diff(baseline: ScenarioResult, scenario: ScenarioResult) -> ScenarioDiff:
    """Net new consumptive draw and its scale against the per-site receiving-water 7Q10."""
    increase = scenario.consumptive_loss.value - baseline.consumptive_loss.value
    q7 = scenario.receiving_7q10.value if scenario.receiving_7q10 else None
    multiple = (increase / q7) if (q7 and q7 > 0) else None
    return ScenarioDiff(
        baseline=baseline.scenario.name,
        scenario=scenario.scenario.name,
        consumptive_increase_cfs=round(increase, 3),
        receiving_water_name=scenario.receiving_water_name,
        receiving_7q10_cfs=q7,
        multiple_of_7q10=_ratio(multiple) if multiple is not None else None,
    )


def evaluate_seasonal(
    consumptive_cfs: float,
    *,
    receiving_water: str | None = None,
    scenario_name: str = "buildout",
    settings: Settings | None = None,
    basis: CoolingBasis | None = None,
) -> SeasonalWithdrawal | None:
    """Screen the consumptive draw against the receiving water's *seasonal* low flow.

    Two distinct seasons drive this screen, kept separate (#1624):

    * The **regulatory summer season** — a fixed permit calendar window (Ohio EPA: May 1-
      Oct 31, cited via :func:`watermark.hydrology.lowflow.summer_season_months`) — SELECTS
      the design low flow: the cited **summer 30Q10** in-season, the annual **7Q10**
      otherwise. All low-flow figures are cited; nothing is interpolated to a per-month
      statistic we do not have.
    * The **climatic growing season** — the months where reference ET0 exceeds precipitation
      (committed NASA POWER normals + FAO-56 ET0) — is reported only as a diagnostic
      (``growing_season`` per month, ``growing_season_months``); it does **not** select the
      design low flow. Earlier this heuristic *was* the switch, which could apply the summer
      statistic in the wrong months (a dry warm April, a wet July).

    For a ``hybrid_adiabatic`` ``basis`` (#1058) the draw itself is **month-varying**: the
    warm-season (assist) rate — ``basis.consumptive_high`` — applies in the ET0 > precip
    months and ~0 elsewhere, instead of smearing an annual average across the year. That
    assist is a physical response to atmospheric demand, so it stays keyed on the *growing*
    season, not the regulatory window. Constant-draw archetypes ignore ``basis`` and use
    ``consumptive_cfs`` as is. Returns ``None`` if the climate/ET inputs are absent.
    """
    settings = settings or get_settings()
    from watermark.hydrology import climate, et

    hybrid = basis is not None and basis.cooling_model == CoolingModelType.HYBRID_ADIABATIC
    # The warm-season assist rate; the seasonal headline for a hybrid facility.
    warm_cfs = mgd_to_cfs(basis.consumptive_high.value) if (hybrid and basis) else consumptive_cfs

    prof = active_profile(settings)
    rw = receiving_water or prof.receiving_low_flow_key or prof.receiving_water_name
    clim = climate.load_climatology(settings=settings)
    precip = clim.get("PRECTOTCORR") if clim is not None else None
    if clim is None or precip is None:
        return None
    et0 = et.penman_monteith_et0(clim)

    q7 = low_flow_for(rw, settings=settings)
    ctx = low_flow_context(rw, settings=settings)
    annual_7q10 = q7.value if q7 is not None else None
    if annual_7q10 is None:
        return None
    summer_30q10 = ctx.get("thirty_q10_summer_cfs")
    one_q10 = ctx.get("one_q10_cfs")
    # The regulatory summer window (cited permit calendar, Ohio EPA May-Oct) — selects the
    # design low flow. NOT the ET0 > precip growing season, which is only a diagnostic (#1624).
    summer_months = set(summer_season_months(settings=settings))

    months: list[MonthlyWithdrawal] = []
    growing: list[str] = []
    for m in et._MONTHS:
        e = et0.monthly_mm_day[m]
        p = precip.monthly[m]
        net = round(e - p, 3)
        # Climatic growing season (diagnostic only): the months reference ET exceeds rainfall.
        is_growing = net > 0
        if is_growing:
            growing.append(m)
        # The design low flow is selected by the REGULATORY summer season (the permit's fixed
        # calendar window), not the climatic growing season (#1624). They coincide for Lima but
        # need not: a wet July stays a summer-30Q10 month; a dry warm April stays a 7Q10 month.
        if m in summer_months and summer_30q10 is not None:
            floor, floor_basis = summer_30q10, "30Q10 summer"
        else:
            floor, floor_basis = annual_7q10, "7Q10 annual"
        # Hybrid (#1058): the evaporative assist is a physical response to atmospheric demand,
        # so it runs in the ET0 > precip (growing-season) months — independent of the floor switch.
        month_cfs = (warm_cfs if is_growing else 0.0) if hybrid else consumptive_cfs
        # Same precision rule as the annual/summer multiples below — a month's draw is the same
        # quantity at the same scale, so it must not vanish where they survive (#1995).
        multiple = _ratio(month_cfs / floor) if floor and floor > 0 else None
        months.append(
            MonthlyWithdrawal(
                month=m,
                growing_season=is_growing,
                et0_mm_day=round(e, 2),
                precip_mm_day=round(p, 2),
                net_atmospheric_mm_day=net,
                low_flow_cfs=floor,
                low_flow_basis=floor_basis,
                consumptive_cfs=round(month_cfs, 3),
                multiple=multiple,
            )
        )

    # For a hybrid the annual multiple reads the annual-average draw (assist months
    # only); the summer multiple reads the concentrated warm-season rate.
    annual_cfs = warm_cfs * len(growing) / 12.0 if hybrid else consumptive_cfs
    return SeasonalWithdrawal(
        scenario=scenario_name,
        cooling_model=basis.cooling_model if basis is not None else None,
        consumptive_cfs=round(warm_cfs if hybrid else consumptive_cfs, 3),
        months=months,
        growing_season_months=growing,
        annual_7q10_cfs=annual_7q10,
        summer_30q10_cfs=summer_30q10,
        one_q10_cfs=one_q10,
        annual_multiple=_ratio(annual_cfs / annual_7q10) if annual_7q10 > 0 else None,
        summer_multiple=(
            _ratio((warm_cfs if hybrid else consumptive_cfs) / summer_30q10)
            if summer_30q10 and summer_30q10 > 0
            else None
        ),
    )


def scenarios_dir(settings: Settings | None = None) -> Path:
    """The active site's hydrology-scenario store — the ONE definition, read *and* written.

    Lima (the reference layout) keeps the flat committed ``data/scenarios/``; every peer gets
    ``data/scenarios/<slug>/``, the same ``site_scoped_path`` rule the rest of the per-site
    curated stores follow (#762).

    This function exists because the reader and the writer used to compute the location
    **independently and disagree** (#1995). ``watermark.site.export._load_scenarios`` already
    read the slug subdir, while :func:`write_scenario` wrote the bare ``settings.scenarios_dir``
    — so ``watermark --site <peer> scenario --write`` did two wrong things at once: it
    OVERWROTE Lima's committed ``buildout.scenario.yaml`` (the artifact Lima's cooling figures
    are regression-locked against), and the peer that ran it still exported an empty
    ``hydrology-scenarios`` feed, because its own reader was looking somewhere else. That is
    why no peer site has ever carried the feed.

    Note the sibling convention deliberately NOT changed here: air scenarios
    (:func:`watermark.air.scenario.write_scenario`) live flat with a ``<slug>.air-`` filename
    PREFIX, and their reader (``_load_air_scenarios``) and ``watermark.ledger`` both glob that
    prefix off the same flat dir. Reader and writer already agree there, so it is correct as it
    stands — two conventions, each internally consistent, is not the bug; one convention split
    across a reader and a writer was.
    """
    settings = settings or get_settings()
    return site_scoped_path(settings.data_dir / "scenarios", settings.site, is_dir=True)


def write_scenario(result: ScenarioResult, *, settings: Settings | None = None) -> str:
    """Persist a scenario result as a committed, self-auditing YAML artifact."""
    settings = settings or get_settings()
    out_dir = scenarios_dir(settings)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.scenario.name}.scenario.yaml"
    # mode="json" so CoolingModelType serializes as its value (safe_dump rejects enums).
    path.write_text(
        yaml.safe_dump(result.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("hydro.scenario.wrote", path=str(path))
    return str(path)
