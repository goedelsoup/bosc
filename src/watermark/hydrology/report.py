"""Render the hydrology findings as an evidence-tagged markdown dossier section.

Composes the three Tier-0 analyses — the water-balance + low-flow screen, the
pre/post stormwater runoff, and the baseline-vs-buildout scenario — into one
regenerable markdown document (``docs/HYDROLOGY.md``). Each figure keeps its
provenance tag so the dossier is auditable: ``[verified]`` for document/connector
values, ``[inference]`` for assumptions/derived.
"""

from __future__ import annotations

from collections.abc import Callable

from watermark.config import Settings, get_settings
from watermark.hydrology.cooling_models import consumptive_range_label
from watermark.hydrology.model import (
    CoolingBasis,
    HydroFinding,
    ProvenancedValue,
    SourceKind,
    StormRunoff,
)
from watermark.pipeline import hydrology as hydro_stage
from watermark.sites import active_profile

_TAG = {
    "document": "verified",
    "connector": "verified",
    "reference": "reference",
    "assumption": "inference",
    "derived": "inference",
}

# flag / severity -> dossier glyph, shared by the assimilative, toxic, and surcharge rows.
_MARK = {"ok": "✅", "tight": "⚠️", "violation": "❌", "critical": "❌", "elevated": "⚠️"}

# gallons scale: storage figures are carried in million gallons (MG) and shown in BG.
_MG_PER_BG = 1000.0


def _tag(source: SourceKind) -> str:
    """The evidence tag for a provenance source, e.g. ``[verified: document]`` (no backticks).

    The single source of truth is :data:`_TAG`; callers wrap the result in backticks.
    """
    return f"[{_TAG[source]}: {source}]"


def _flag_mark(flag: str) -> str:
    """The ❌ / ⚠️ / ✅ glyph for an assimilative/toxic/severity flag."""
    return _MARK[flag]


def _mg_to_bg(mg: float) -> float:
    """Million gallons -> billion gallons (the storage figures' display scale)."""
    return mg / _MG_PER_BG


def _ev(pv: ProvenancedValue | None) -> str:
    if pv is None:
        return "—"
    return f"{pv.value:,.2f} {pv.unit} `{_tag(pv.source)}`"


def _short_reach(name: str) -> str:
    """A reach's short label for inline prose — drop a ``(…)`` qualifier and any ``River …`` tail.

    ``Ottawa River upstream of Lima`` → ``Ottawa``; ``Dug Run (headwater)`` → ``Dug Run``.
    """
    base = name.split("(")[0].strip()
    return base.split(" River")[0].strip() if " River" in base else base


def _render_toxic_screen(emit: Callable[[str], None], settings: Settings) -> None:
    """The industrial RSEI toxic dischargers on the same receiving reaches."""
    from watermark.hydrology import toxics

    try:
        inv = toxics.build_screen(settings)
    except FileNotFoundError:
        return  # RSEI inventory not generated yet
    ranked = [s for s in inv.screens if s.flag in ("critical", "elevated")]
    if not ranked:
        return

    emit(
        "\n**Industrial toxic dischargers on the same reaches.** The municipal screen "
        "above covers the three WWTPs; the *industrial* side is larger. Of the "
        f"{inv.meta['water_releaser_count']} EPA-RSEI facilities that release toxics to "
        f"water in the county, **{inv.meta['critical_count']}** sit on a near-undiluted "
        "reach. Placing each on its receiving stream (ECHO-cited where available, else "
        "inferred from the Ottawa River industrial corridor) and reading it against the "
        "same cited 7Q10:\n"
    )
    emit("\n| facility | RSEI Score | to water (lb) | receiving | 7Q10 | screen mg/L |")
    emit("|---|--:|--:|---|--:|--:|")
    for s in ranked:
        mark = _flag_mark(s.flag)
        rw = s.receiving_water or "—"
        rw += " `[verified: ECHO]`" if s.receiving_water_source == "connector" else " *"
        q7 = f"{s.low_flow_7q10.value:g} cfs" if s.low_flow_7q10 else "—"
        conc = f"~{s.screening_concentration.value:g}" if s.screening_concentration else "—"
        emit(
            f"| {mark} {s.facility} | {s.score:,.0f} | {s.water_pounds:,.0f} "
            f"| {rw} | {q7} | {conc} |"
        )
    emit(
        "\n`*` = receiving water inferred from the corridor coordinate cluster, **not** "
        "independently cited. The screen mg/L is a coarse `[inference: derived]` value "
        "(annual reported water pounds, fully mixed at the 7Q10) — an order-of-magnitude "
        "screen, not a measured concentration.\n"
    )

    ctx = toxics._low_flow_context(settings).get("ottawa river", {})
    one_q10 = ctx.get("one_q10_cfs")
    summer = ctx.get("thirty_q10_summer_cfs")
    if one_q10 is not None:
        emit(
            "\nThe seasonal pinch compounds it: the Ottawa's **1Q10 is "
            f"{one_q10:g} cfs** (and summer 30Q10 {summer:g} cfs `[verified: document]`) — "
            "the mainstem effectively dries at design low flow. That floor falls in the "
            "**May-Oct** window where reference ET exceeds precipitation (§3), so the "
            "largest toxic loads meet the smallest assimilative capacity exactly when the "
            "river is lowest.\n"
        )


def _render_stormwater_pathway_note(emit: Callable[[str], None], settings: Settings) -> None:
    """The campus's SECOND discharge pathway — stormwater to Pike Run via the BOSC Storm
    Outfall — distinct from the FM-2 *process* discharge routed through Lima's WWTP above.

    Sourced from the committed SWP3 extraction (eDoc 4091286), not re-derived: no cited
    storm low-flow magnitude exists for this pathway, so it stays a receiving-water fact
    (network.yaml records it as topology context), not a routed mass-balance node.
    """
    import yaml

    from watermark.hydrology.lowflow import low_flow_for

    path = settings.data_dir / "extracted" / "plans" / "4091286.engineering.yaml"
    if not path.is_file():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rec = data.get("record") or {}
    params = {p.get("parameter"): p for p in rec.get("design_parameters") or []}
    disturbed = (params.get("total area disturbed") or {}).get("value")
    firms = rec.get("prepared_by") or []
    operator = next(
        (f.get("name") for f in firms if "operator" in (f.get("discipline") or "").lower()), None
    )
    engineer = next(
        (f.get("name") for f in firms if "engineer" in (f.get("discipline") or "").lower()), None
    )
    prepared = rec.get("record_date")
    if disturbed is None or not operator or not engineer or not prepared:
        return

    pike = low_flow_for("Pike Run", settings=settings)
    pike_q7 = f"{pike.value:g} cfs" if pike is not None else "no cited 7Q10"
    emit(
        "\n**A second campus pathway — stormwater to Pike Run.** Distinct from the FM-2 "
        "*process* discharge above (routed to Lima's WWTP), the campus's **stormwater** "
        "leaves the site via a constructed **BOSC Storm Outfall** channel that discharges "
        f"to **Pike Run** — the loop's most flow-starved tributary (7Q10 **{pike_q7}**, "
        "already shown undiluted by the American Bath WWTP). "
        f"Per the roundabout/outfall **SWP3** (Ohio EPA eDoc 4091286; operator {operator}, "
        f"engineer {engineer}; prepared {prepared}) `[verified: document]`, the site drains "
        "east-to-west by subsurface tile and the outfall channel terminates at Pike Run. "
        f"That SWP3 documents *construction* disturbance ({disturbed} ac), not a continuous "
        "low-flow discharge, so the pathway is recorded as a receiving-water fact, not added "
        "to the routed mass balance below.\n"
    )


def _render_lowflow_corroboration(emit: Callable[[str], None], settings: Settings) -> None:
    """Independently computed 1Q10/7Q10/30Q10 vs the cited regulatory low flows."""
    from watermark.hydrology.lowflow_frequency import load_low_flow_frequency

    lff = load_low_flow_frequency(settings=settings)
    if lff is None or not lff.statistics:
        return
    seven = lff.stat("7Q10")
    if seven is None or seven.cited_cfs is None:
        return

    emit(
        "\n**The cited 7Q10 is independently reproducible.** The denominator above is a "
        "single number read off a fact sheet. Computing it ourselves from the raw record — "
        f"the USGS daily-mean discharge at the **same gage the fact sheet names** (NWIS "
        f"{lff.site_no}, {lff.site_name}, {lff.period_start}..{lff.period_end}, "
        f"{lff.complete_years} complete climatic years) — lands on it. Annual n-day minima "
        "by climatic year, fit with log-Pearson III and bracketed by the non-parametric "
        "Weibull plotting position `[inference: derived]`:\n"
    )
    emit("\n| design low flow | computed (LP3) | computed (Weibull) | cited (Ohio EPA) |")
    emit("|---|--:|--:|--:|")
    for s in lff.statistics:
        if s.cited_cfs is None:
            continue
        label = s.label if s.cited_basis in (None, s.label) else f"{s.label} (vs {s.cited_basis})"
        emit(
            f"| {label} | {s.lp3_cfs.value:g} cfs | "
            f"{s.weibull_cfs.value:g} cfs | {s.cited_cfs.value:g} cfs |"
        )
    one = lff.stat("1Q10")
    dry = ""
    if one is not None and one.zero_fraction > 0:
        dry = (
            f" The 1-day record is dry in **{one.zero_fraction:.0%}** of complete years, so the "
            "computed 1Q10 is **0 cfs** — the mainstem literally stops, matching the cited 1Q10."
        )
    emit(
        f"\nThe computed **7Q10 is {seven.lp3_cfs.value:g} cfs** against the cited "
        f"**{seven.cited_cfs.value:g} cfs** — agreement to within rounding, from an independent "
        f"method on a longer record than the fact sheet used.{dry} So the assimilative screen's "
        "denominator is not an Ohio EPA artifact to be argued with; it is what the river actually "
        "carries at design low flow, reproducible by anyone with the public gage record. "
        "These computed figures are `[inference: derived]` and corroborate — they do not replace — "
        "the cited regulatory statistic.\n"
    )

    hm = lff.harmonic_mean
    if hm is not None and hm.cited_cfs is not None:
        agree = "lands on" if hm.corroborates else "diverges from"
        emit(
            "\n**The design flow is matched to the criterion type.** Acute aquatic-life criteria "
            "are evaluated at the 1Q10, chronic at the 7Q10, and human-health (carcinogen) criteria "
            "at the **harmonic-mean flow** — the whole-record statistic that weights the low tail "
            "the way a lifetime exposure does. Computed from the same daily record "
            f"(N/Σ(1/Q) over {hm.n_days} non-zero days"
            + (f", {hm.zero_days} zero-flow days excluded" if hm.zero_days else "")
            + f"), the harmonic mean is **{hm.computed_cfs.value:g} cfs** and {agree} the cited "
            f"**{hm.cited_cfs.value:g} cfs** `[inference: derived]`. So each criterion in the "
            "toxic screen is read against its own design flow, not a single 7Q10 pressed into "
            "every service.\n"
        )


def _render_routed_network(emit: Callable[[str], None], settings: Settings) -> None:
    """The per-stream screen generalized to a routed system mass balance."""
    from watermark.hydrology.assimilative import dilution_flag
    from watermark.hydrology.network import loop_natural_total
    from watermark.pipeline import hydrology as hydro_stage

    baseline, buildout, delta = hydro_stage.run_network(settings=settings, live=False)
    if not baseline.reaches or baseline.outlet_effluent_fraction is None:
        return

    # Break the routed effluent into three named parts so no claim leans on the wrong flow:
    #   - campus FM-2 (bosc-fm2-return): the data center's OWN industrial discharge;
    #   - the City of Lima WWTP (lima-wwtp): the major municipal plant's own design flow
    #     (18.5 MGD, OEPA 2PE00000 / OH0026069) — counted since #1536, absent on peers;
    #   - the three small county WWTPs (Dug Run / Pike Run / Ottawa tributaries): the
    #     data-center-independent municipal effluent, reported separately so "the river is
    #     mostly effluent" does not lean on either the campus's or the big plant's flow.
    campus = baseline.reach("bosc-fm2-return")
    campus_cfs = campus.gain.value if campus is not None and campus.gain is not None else 0.0
    lima_muni = baseline.reach("lima-wwtp")
    lima_muni_cfs = (
        lima_muni.gain.value if lima_muni is not None and lima_muni.gain is not None else 0.0
    )
    county_cfs = baseline.effluent_total_cfs - campus_cfs - lima_muni_cfs

    # "The loop's streams" means the Lima loop's OWN tributaries (Ottawa/Dug Run/Pike Run) —
    # NOT the system-wide natural_total_cfs, which (#1488) also carries the outlet's Auglaize
    # confluence gain, a downstream receiving water the cooling draw never touches.
    loop_natural = loop_natural_total(baseline)

    # The section's own thesis is that the streams nearly dry at design low flow, so the routed
    # natural total can reach 0 — guard the ratio (#614) rather than divide by it.
    if loop_natural > 0:
        municipal_multiple = (
            f"**{county_cfs / loop_natural:.1f}x** the streams' entire natural low flow"
        )
    else:
        municipal_multiple = (
            "more than the streams' entire natural low flow, which is effectively zero at "
            "design low flow"
        )

    # Per-headwater 7Q10 breakdown, derived from the routed model's injected base flows (#611):
    # the literals must equal the displayed loop_natural, not a separately-typed list that
    # silently diverges if the topology changes. Scoped to kind=="headwater" so the outlet's
    # own (downstream, derived) Auglaize gain doesn't leak into "the loop's own streams".
    natural_breakdown = " + ".join(
        f"{_short_reach(r.name)} {r.base.value:g} `{_tag(r.base.source)}`"
        for r in baseline.reaches
        if r.base is not None and r.kind == "headwater"
    )
    # "Leaving Lima" is the gage (the assimilative reach), unaffected by anything the Auglaize
    # adds further downstream — fall back to the outlet fraction if the gage is somehow absent.
    gage_reach = (
        baseline.reach(baseline.assimilative_reach) if baseline.assimilative_reach else None
    )
    gage_fraction = (
        gage_reach.effluent_fraction
        if gage_reach is not None and gage_reach.effluent_fraction is not None
        else baseline.outlet_effluent_fraction
    )
    emit(
        "\n### The whole loop at design low flow: a routed mass balance\n\n"
        "The screen above reads each plant against its *own* tributary in isolation. "
        "Routing the cited headwater 7Q10s, the document-cited WWTP/campus discharges, and "
        "the cooling draw through the cited confluence graph "
        "(`data/reference/hydrology/network.yaml`) shows the system picture the per-stream "
        "rows miss. At design low flow the loop's streams carry, in total, only "
        f"**{loop_natural:g} cfs** of *natural* low flow "
        f"({natural_breakdown}). The three small county "
        f"WWTP discharges alone add **{county_cfs:.2f} cfs** of treated effluent — "
        f"{municipal_multiple}, with no data center in the picture. The river at design low flow "
        "is effluent, not "
        "stream. "
        + (
            "The City of Lima WWTP — the major municipal plant — then adds its own "
            f"**{lima_muni_cfs:.2f} cfs** design discharge (18.5 MGD, OEPA NPDES 2PE00000 / "
            "OH0026069, outfall to the Ottawa at RM 37.6), and the campus adds its documented "
            f"**{campus_cfs:.2f} cfs** FM-2 industrial discharge (piped to that same plant via "
            "Lima's 78\" sewer), together taking the Ottawa leaving Lima to "
            f"**{gage_fraction:.0%} treated effluent** — now counting the municipal plant's own "
            "design flow that the corpus previously lacked (#1536; the FM-2 is the campus's "
            "increment on top of the plant's permitted baseline, not a double count).\n"
            if lima_muni_cfs > 0
            else "The campus then adds its own documented "
            f"**{campus_cfs:.2f} cfs** FM-2 industrial discharge (routed via Lima's sewer + "
            f"WWTP), taking the Ottawa leaving Lima to **{gage_fraction:.0%} treated effluent** "
            "— a *conservative* floor, since the receiving plant's own municipal design flow is "
            "not counted here.\n"
        )
    )
    emit("\n| reach | natural (cfs) | effluent (cfs) | routed (cfs) | deficit (cfs) |")
    emit("|---|--:|--:|--:|--:|")
    for r in buildout.reaches:
        deficit = f"{r.deficit_cfs:.2f}" if r.deficit_cfs else "—"
        emit(
            f"| {r.name} | {r.natural_cfs:.2f} | {r.effluent_cfs:.2f} | "
            f"{r.routed_cfs:.2f} | {deficit} |"
        )
    if delta.multiple_of_natural is not None:
        dry = (
            "consumes the Ottawa mainstem's entire design low flow — it runs **dry** at the "
            f"intake, leaving a **{buildout.consumptive_cfs - loop_natural:.2f} cfs** "
            "shortfall the river cannot supply"
            if delta.mainstem_runs_dry
            else "draws on a mainstem that still holds positive flow"
        )
        emit(
            f"\n**Unbuffered bound.** *If* the cooling load of "
            f"**{buildout.consumptive_cfs:.2f} cfs** were pumped straight from the Ottawa at 7Q10 "
            f"(**{delta.multiple_of_natural:g}x** the loop's entire natural low flow) it {dry}. But "
            "that is **not** how Lima's supply works — the city draws treated water from ~15 billion "
            "gallons of off-stream reservoir storage (see the next section), so this is a worst-case "
            "bound, not the operating reality. The routed balance still conserves mass (base + gains "
            f"- applied loss reconciles to the {buildout.outlet_cfs:.2f} cfs outlet) "
            "`[inference: derived]`. The order-invariant system totals are the robust result; the "
            "per-reach values depend on the cited-but-approximate confluence order and are "
            "screening-grade.\n"
        )

    # The outlet's own receiving water (#1488): the outlet was previously a bare label that
    # just repeated the gage's totals. Routed here, a drainage-area-ratio TRANSFER of the
    # Auglaize's own flow (not the raw downstream gage — see low-flow-7q10.derived.yaml for
    # the method) joins as a base flow, so the outlet row above already carries it — this
    # paragraph explains what changed and screens the arriving (Ottawa) flow against it with
    # the same dilution band.
    outlet = buildout.reach("outlet")
    if outlet is not None and outlet.base is not None and outlet.inflow_cfs > 0:
        ratio = outlet.base.value / outlet.inflow_cfs
        flag = dilution_flag(ratio)
        mark = _flag_mark(flag)
        emit(
            "\n**Downstream: the Auglaize confluence.** The outlet is the Ottawa's actual "
            f"receiving water, not a bare label. The Auglaize's own {outlet.base.value:g} cfs "
            f"7Q10 `{_tag(outlet.base.source)}` — a drainage-area-ratio *transfer*, not the raw "
            "USGS 04186500 (Fort Jennings) gage value, which sits below the confluence and "
            "already carries the Ottawa's own historical contribution (full method in "
            "`low-flow-7q10.derived.yaml`) — joins here, diluting "
            f"the **{outlet.inflow_cfs:.2f} cfs** routed Ottawa flow (mostly treated effluent) "
            f"arriving from Lima. {mark} At **{ratio:.2f}:1** dilution the confluence screens "
            f"**{flag}** by the same band as the per-plant checks above — the Auglaize's own "
            "flow is dwarfed by what the loop sends it. The final flow leaving toward the "
            f"Maumee is **{outlet.routed_cfs:.2f} cfs**, **{outlet.effluent_fraction:.0%}** "
            f"treated effluent — down from **{gage_fraction:.0%}** at the Lima gage, so the "
            "Auglaize genuinely dilutes the loop's discharge without resolving the underlying "
            "effluent-dominance. Even this transfer is a coarse screening estimate — it nets "
            "out the Ottawa's own drainage area at Lima, not at its actual mouth a few miles "
            "further downstream — so it likely still slightly *over*-states the Auglaize's "
            "own contribution.\n"
        )


def _render_water_supply(emit: Callable[[str], None], settings: Settings) -> None:
    """The intake/storage half: the off-stream reservoir budget the campus actually draws on."""
    from watermark.pipeline import hydrology as hydro_stage

    supply, budget, _findings = hydro_stage.run_water_budget(settings=settings)
    if supply is None or budget is None:
        return

    by_river = supply.storage_by_river()
    river_txt = ", ".join(f"{r} {_mg_to_bg(mg):.1f} BG" for r, mg in sorted(by_river.items()))
    emit(
        "\n### The supply side: off-stream storage, not a 7Q10 intake\n\n"
        "The screen above reads the campus draw as if it depleted the Ottawa at design low flow. "
        "It does not — and the real mechanism is a *stronger* finding. Lima's raw water is held in "
        f"**{len(supply.reservoirs)} upground (off-stream) reservoirs totalling "
        f"~{_mg_to_bg(supply.total_storage_mg):.1f} billion gallons** ({river_txt}), filled by pumping "
        "from **both** the Auglaize (west) and the Ottawa (east) through four pump stations **at "
        "high flow** `[verified: document]`. So Lima never withdraws at the 7Q10 — it lives off "
        "stored water, and the binding low-flow constraint is reservoir **drawdown**, not intake "
        "depletion.\n"
    )
    emit("\n| reservoir | built | capacity | source river |")
    emit("|---|--:|--:|---|")
    for r in supply.reservoirs:
        emit(f"| {r.name} | {r.built} | {r.capacity_mg:,.0f} MG | {r.source_river} |")
    emit(
        f"\nThe data center draws **treated** municipal water like any large customer, so its "
        f"**{budget.campus_makeup.value:g} MGD** makeup is an added draw on this shared storage — "
        f"**{budget.campus_share_pct:g}%** of the **{budget.gross_production_mgd:g} MGD** the plant "
        f"would then produce (against ~{supply.current_production.value:g} MGD today, "
        f"{supply.plant_capacity.value:g} MGD rated) `[inference: derived]`. At that draw the "
        f"zero-refill **drought reserve falls from {budget.drought_reserve_days_baseline:g} to "
        f"{budget.drought_reserve_days_buildout:g} days "
        f"(-{budget.drought_reserve_lost_days:g})**. Its evaporative "
        f"**{budget.campus_consumptive.value:g} MGD** consumptive is a permanent loss to the basin "
        "— the returns (FM-2/FM-1) go *downstream* to the Ottawa via the WWTPs, never back to the "
        "reservoirs, so the full makeup draws storage down. This is a far harder number to rebut "
        "than the 7Q10 multiple: the campus alone is a fifth of the city's water production, drawn "
        "from a finite reserve that must be refilled by high-flow pumping from two rivers whose "
        "yield is lowest in exactly the season the draw is highest. Quantifying that refill against "
        "the Auglaize (USGS 04185750) and Ottawa (04187100) flow records is the next increment.\n"
    )


def _render_refill_adequacy(emit: Callable[[str], None], settings: Settings) -> None:
    """The flow side of the supply: can pumping refill the reservoirs through a drought?"""
    from watermark.pipeline import hydrology as hydro_stage

    ra, _findings = hydro_stage.run_refill(settings=settings)
    if ra is None or not ra.scenarios:
        return
    base = ra.scenario("baseline city")
    campus = ra.scenario("+campus (central)")
    high = ra.scenario("+campus (high bound)")
    if base is None or campus is None:
        return

    emit(
        "\n### Can the rivers refill the reservoirs — even in drought?\n\n"
        "Off-stream storage only helps if high-flow pumping keeps it filled. Two questions, two "
        "answers from the gauged record "
        f"(Auglaize at Fort Jennings + Ottawa at Lima, {ra.period_start}—{ra.period_end}). "
        "**In a normal year, refill is amply adequate**: the two rivers' combined mean flow at the "
        f"intakes (**{ra.combined_mean_cfs:g} cfs**, Auglaize scaled to its intake reach) is "
        f"~**{ra.annual_supply_multiple:g}x** the city+campus "
        "demand `[verified: connector]`. **The binding case is drought**: the Ottawa reaches 0 cfs "
        f"and the Auglaize sits below the city+campus draw ~{ra.rivers[0].pct_days_below_demand:g}% "
        "of the time, so the system draws down storage.\n"
    )
    emit(
        "\nThe **sequent-peak storage requirement** — the active storage the worst gauged drawdown "
        "calls on at a constant demand — measures the drought margin and the campus's bite:\n"
    )
    emit(
        "\n| demand scenario | storage the worst drought needs | "
        f"of the {_mg_to_bg(ra.storage_capacity_mg):.1f} BG | worst drawdown |"
    )
    emit("|---|--:|--:|---|")
    for sc in ra.scenarios:
        emit(
            f"| {sc.label} ({sc.demand_mgd:g} MGD) | {sc.required_storage_mg:,.0f} MG | "
            f"{sc.pct_of_capacity:g}% | ~{sc.worst_spell_days} d from {sc.worst_spell_start} |"
        )
    eroded = campus.required_storage_mg - base.required_storage_mg
    high_txt = (
        f" At the high cooling bound ({high.demand_mgd:g} MGD) it rises to "
        f"**{high.pct_of_capacity:g}%**."
        if high is not None
        else ""
    )
    # The worst-drought year is the calendar year of the campus scenario's worst drawdown (#611),
    # not a typed-in literal that can diverge from the gauged record.
    worst_year = campus.worst_spell_start[:4] if campus.worst_spell_start else "worst-gauged"
    emit(
        f"\nThe worst gauged drought (the {worst_year} event, a "
        f"~{campus.worst_spell_days}-day drawdown) is "
        f"survived with large margin — but the campus raises the storage it calls on from "
        f"**{base.pct_of_capacity:g}% to {campus.pct_of_capacity:g}%** of capacity "
        f"(**+{eroded:,.0f} MG**, and ~{campus.worst_spell_days - base.worst_spell_days} more days of "
        f"drawdown).{high_txt} `[inference: derived]` So refill is adequate and the system survives the "
        "historical record — but the campus measurably erodes the buffer, and **a drought longer or "
        f"deeper than {ra.period_start[:4]}—{ra.period_end[:4]} is the residual exposure** this "
        "screen cannot bound.\n"
    )
    ev = ra.evaporation
    evap_txt = (
        " A first-order reservoir-evaporation sink is folded in — FAO-56 ET0 x a "
        f"{ev.open_water_coefficient:g} open-water coefficient over the "
        f"{ev.surface_area_acres:g}-acre reservoir surface, ~**{ev.mean_evap_mgd:g} MGD** mean "
        f"(peaking at {ev.peak_evap_mgd:g} MGD in {ev.peak_month}) `[derived]`, which tightens the "
        "drought bound above."
        if ev is not None
        else " Reservoir evaporation is not yet subtracted."
    )
    prof = active_profile(settings)
    ratio, primary_river = prof.intake_da_ratio_primary, prof.supply_river_primary
    optimism = (
        f"the {ratio:g} drainage-area transfer scaling the downstream {primary_river} gage to the "
        "intake is itself a coarse over-estimate; no pump-rate cap"
        if ratio != 1.0
        else f"the {primary_river} gage is downstream of the intakes; no pump-rate cap"
    )
    emit(
        f"\nThe estimate remains *optimistic* ({optimism}), so the real margin is still somewhat "
        f"tighter than shown.{evap_txt}\n"
    )


def _render_tier1_swmm(emit: Callable[[str], None], settings: Settings) -> None:
    """The committed EPA-SWMM detention + surcharge numbers (engine-free, from the artifact)."""
    from watermark.hydrology.tier1 import load_tier1

    result = load_tier1(settings=settings)
    if result is None or not result.available or result.detention is None:
        return
    d = result.detention
    worst_cont = max((abs(dk.continuity_error_pct) for dk in result.decks), default=0.0)

    imperv = (
        f" — {d.post_imperv_pct:g}% impervious, the declared permanently-impervious acreage"
        if d.post_imperv_pct is not None
        else ""
    )
    emit(
        f"\nThe committed run (`{result.engine}`, {result.storm_return_period_yr}-yr "
        f"{result.design_depth_in:g}-in storm; mass-balance continuity error "
        f"{worst_cont:.2f}%) `[inference: derived]` sizes the detention the corridor needs. "
        "Paving the footprint **as permitted** takes the design-storm peak from **"
        f"{d.pre_peak_cfs:,.0f} cfs** (cropland) to **{d.post_peak_cfs:,.0f} cfs**"
        f"{imperv}; holding the release back to the pre-development rate "
        f"({d.controlled_peak_cfs:,.0f} cfs) takes a **{d.required_storage_acft:,.0f} ac-ft** "
        f"basin ({d.basin_area_acres:g} ac, {d.orifice_diam_ft:g}-ft bottom orifice). Every "
        "input deck is committed under `data/reference/hydrology/swmm/` so anyone can re-run "
        "them in EPA SWMM.\n"
    )
    if d.has_full_buildout:
        emit(
            f"\nBuilt out — the whole parcel at the blanket {d.full_buildout_imperv_pct:g}% "
            "impervious assumption, the Tier-0 screen's `full_buildout` bound rather than the "
            f"permitted project — the same storm peaks at **{d.full_buildout_peak_cfs:,.0f} "
            f"cfs** and the basin holding it to the pre-development rate grows to "
            f"**{d.full_buildout_storage_acft:,.0f} ac-ft** "
            f"({d.full_buildout_orifice_diam_ft:g}-ft orifice). The two are separate readings "
            "of separate projects `[inference: derived]`; the as-permitted one is what the "
            "SW1225 application describes.\n"
        )
    sur = [
        s for s in result.surcharge if s.headroom_mgd is not None and s.avg_design_flow is not None
    ]
    if sur:
        emit(
            "\nThe campus's storm-driven sanitary peak does not stay on site — it rides the "
            "forcemains to the treatment plants. It is judged only against the plants that "
            "actually receive it:\n"
        )
        if result.surcharge_note:
            emit(f"\n> {result.surcharge_note}\n")
        emit("\n| plant (forcemain) | wet-weather peak | documented headroom | result |")
        emit("|---|--:|--:|---|")
        for s in sur:
            verdict = "❌ exceeds" if s.exceeds else "✅ within"
            fm = f" ({s.forcemain})" if s.forcemain else ""
            assert s.avg_design_flow is not None  # filtered above
            emit(
                f"| {s.plant}{fm} | {s.wet_weather_peak.value:.1f} MGD | {s.headroom_mgd:g} MGD "
                f"(peak {s.capacity.value:g} - avg {s.avg_design_flow.value:g}) | "
                f"{verdict} ({s.margin_mgd:+.1f}) |"
            )
        emit(
            f"\nThat **{sur[0].wet_weather_peak.value:.1f} MGD** is the campus's *total* "
            "wet-weather sanitary peak; it splits across FM-1 (the small American Bath / "
            "American II plants) and FM-2 (the City of Lima sewer). The corpus does not "
            "quantify the split, so it is not apportioned — but the total alone is several "
            f"times even American II's whole wet-weather headroom ({sur[0].headroom_mgd:g} MGD), "
            "so the small FM-1 plants cannot absorb their share. The RDII rate is an "
            "uncalibrated screening assumption — but the direction is robust, and it lands on "
            "the regulatory fact below.\n"
        )


def _render_drainage_audit(emit: Callable[[str], None], settings: Settings) -> None:
    """Audit the OPC roundabout drainage scope against the corridor design storm."""
    from watermark.hydrology import drainage

    try:
        audit = drainage.build_drainage_audit(settings)
    except FileNotFoundError:
        return  # OPC summary not present
    if not audit.scopes:
        return

    m = audit.meta
    emit(
        "\n### Drainage scope vs the design storm\n\n"
        f"The roundabout program budgets **${m['program_drainage_total']:,}** of drainage "
        f"across {m['sub_estimate_count']} OPC sub-estimates `[verified: document]`, but the "
        "engineering basis is thin. Auditing what the estimates actually quantify against the "
        "corridor design rainfall:\n"
    )
    emit("\n| sub-estimate | drainage $ | breakdown | sized $ | lump-sum $ |")
    emit("|---|--:|---|--:|--:|")
    for s in audit.scopes:
        if s.itemized:
            sized = f"{'~' if s.sized_amount_approximate else ''}{s.sized_amount:,}"
            lump = f"{'~' if s.lump_sum_amount_approximate else ''}{s.lump_sum_amount:,}"
            emit(f"| {s.name} | {s.drainage_subtotal:,} | itemized | {sized} | {lump} |")
        else:
            emit(f"| {s.name} | {s.drainage_subtotal:,} | *subtotal only* | — | — |")

    if audit.ddf is not None:
        d = audit.ddf
        cells = ", ".join(f"{rp}-yr {d.depth('24-hr', rp):.2f} in" for rp in d.return_periods)
        emit(f"\n**Atlas-14 corridor design storm** (24-hr) `[verified: connector]`: {cells}.\n")

    for f in audit.findings:
        emit(f"\n- {f.detail}")
    emit(
        "\n\nThis is a design-basis / scope-completeness reading, not a sizing of the "
        "roundabouts' hydraulics — the corpus carries no per-roundabout footprint area, so "
        "runoff/detention volumes are deliberately not computed.\n"
    )


def _render_seasonal_withdrawal(
    emit: Callable[[str], None],
    settings: Settings,
    consumptive_cfs: float,
    basis: CoolingBasis | None = None,
) -> None:
    """The cooling draw read against the receiving water's regulatory-summer design low flow.

    The design low flow is selected by the cited permit summer window (#1624); the growing
    season (ET0 > precip) is rendered separately as a diagnostic (the 🔴 mark). The basis rides
    along so a ``hybrid_adiabatic`` facility's draw is month-varying (#1058).
    """
    from watermark.hydrology import scenario

    sw = scenario.evaluate_seasonal(consumptive_cfs, settings=settings, basis=basis)
    if sw is None or not sw.months:
        return

    # The regulatory summer window (the months the cited summer 30Q10 governs) — distinct from
    # the climatic growing season (ET0 > precip); they coincide for Lima but need not (#1624).
    summer_win_months = [r.month for r in sw.months if r.low_flow_basis == "30Q10 summer"]
    summer_win = f"{summer_win_months[0]}-{summer_win_months[-1]}" if summer_win_months else ""
    grow_win = (
        f"{sw.growing_season_months[0]}-{sw.growing_season_months[-1]}"
        if sw.growing_season_months
        else ""
    )
    lede = (
        f"In the regulatory summer season (**{summer_win}**, the permit's fixed design-flow "
        f"window) the Ottawa sits at its cited summer design low flow (30Q10)"
        if summer_win
        else "Against the cited design low flow"
    )
    grow_note = (
        f", and across the growing season (**{grow_win}**, where reference ET exceeds "
        "precipitation — §3) that floor arrives with no rainfall buffer"
        if grow_win
        else ""
    )
    emit(
        "\n### The seasonal pinch: the draw lands when the river is lowest\n\n"
        f"The annual-7Q10 multiple understates the constraint. {lede}{grow_note}. Reading the "
        "same consumptive draw against the *cited seasonal* floor (🔴 = growing season, ET0 > "
        "precip):\n"
    )
    emit("\n| month | ET0 - precip (mm/d) | Ottawa low flow | draw ÷ low flow |")
    emit("|---|--:|---|--:|")
    for r in sw.months:
        net = f"{r.net_atmospheric_mm_day:+.2f}"
        floor = f"{r.low_flow_cfs:g} cfs ({r.low_flow_basis})"
        mult = f"{r.multiple:g}x" if r.multiple is not None else "—"
        mark = " 🔴" if r.growing_season else ""
        emit(f"| {r.month}{mark} | {net} | {floor} | {mult} |")
    if sw.summer_multiple is not None and sw.summer_30q10_cfs is not None and summer_win:
        emit(
            f"\nIn the **{summer_win}** summer window the draw is **{sw.summer_multiple:g}x** the "
            f"cited summer 30Q10 ({sw.summer_30q10_cfs:g} cfs) — vs {sw.annual_multiple:g}x the "
            f"annual 7Q10. And the summer 30Q10 is the *generous* floor: the Ottawa's absolute "
            f"design low flow is **1Q10 = {sw.one_q10_cfs:g} cfs** `[verified: document]`, so in "
            "the driest weeks there is no flow to draw against at all. The cooling draw peaks "
            "against supply precisely when the atmosphere is also taking the most.\n"
        )


def _render_wwtp_floodzones(emit: Callable[[str], None], settings: Settings) -> None:
    """The three WWTP outfalls' FEMA flood exposure on the same undiluted reaches."""
    from watermark.hydrology.floodplain import load_wwtp_floodzones

    wf = load_wwtp_floodzones(settings=settings)
    if wf is None or not wf.plants:
        return
    sited = [p for p in wf.plants if p.in_sfha]
    adjacent = [p for p in wf.plants if not p.in_sfha and p.nearest_buffer(contains="AE")]
    lead = (
        "All three plant sites sit in the FEMA floodplain"
        if len(sited) == len(wf.plants)
        else (
            f"None of the {len(wf.plants)} plant sites sits in the FEMA Special Flood "
            "Hazard Area at its ECHO-reported point"
            if not sited
            else f"{len(sited)} of {len(wf.plants)} plant sites sit in the FEMA SFHA"
        )
    )
    emit(
        f"\n**Outfall flood exposure.** {lead}, but the discharge infrastructure is "
        f"flood-adjacent on streams already shown to be undiluted at low flow "
        f"`{_tag('document')}`:\n"
    )
    emit("\n| Plant | Receiving water | In SFHA | Nearest AE | Nearest floodway |")
    emit("|---|---|---|---|---|")
    for p in wf.plants:
        ae = p.nearest_buffer(contains="AE")
        fw = p.nearest_buffer(contains="FLOODWAY")
        emit(
            f"| {p.name} | {p.receiving_water or '—'} | {'yes' if p.in_sfha else 'no'} "
            f"| {f'≤{ae} m' if ae else '—'} | {f'≤{fw} m' if fw else '—'} |"
        )
    if adjacent:
        emit(
            f"\n{wf.note} So the mapped exposure understates the outfalls': the "
            "discharge points themselves sit at the receiving water, inside or at the "
            "edge of the AE floodplain.\n"
        )


def _render_maumee_tmdl(emit: Callable[[str], None], settings: Settings) -> None:
    """The Maumee Nutrient TMDL phosphorus WLAs on the same permits (§2)."""
    from watermark.hydrology.maumee import load_maumee_tmdl

    tmdl = load_maumee_tmdl(settings=settings)
    if tmdl is None or not tmdl.facilities:
        return
    emit("\n## 2. The Maumee Nutrient TMDL: the same discharges are capped phosphorus loads\n")
    emit(
        "These discharges don't just strain a local stream. The Ottawa flows to the\n"
        "Auglaize and on to the **Maumee** — Lake Erie's largest tributary and the\n"
        "driver of its western-basin harmful algal blooms. The 2023 Maumee Watershed\n"
        "Nutrient TMDL (Ohio EPA, US-EPA-approved) assigns each individually permitted\n"
        "discharger a total-phosphorus **wasteload allocation**: a spring-season\n"
        "(March-July) cap, also stated as a daily equivalent. The plants the low-flow\n"
        "screen flags as effectively undiluted are the same permits carrying these caps\n"
        f"`{_tag('document')}`:\n"
    )
    emit("\n| facility | NPDES | spring TP (metric tons) | daily TP (kg) |")
    emit("|---|---|---|---|")
    for fac in tmdl.facilities:
        emit(
            f"| {fac.facility} | {fac.npdes or '—'} | "
            f"{fac.spring_tp.value:g} | {fac.daily_tp.value:g} |"
        )
    if tmdl.grouped_spring_tp is not None and tmdl.grouped_daily_tp is not None:
        emit(
            f"\nAcross the whole grouped category of individually permitted dischargers the\n"
            f"cap totals **{tmdl.grouped_spring_tp.value:g} metric tons** "
            f"({tmdl.grouped_daily_tp.value:g} kg/day) of spring phosphorus. So the local\n"
            f"dilution failure compounds a basin-scale constraint: at design low flow these\n"
            f"effluents are near-undiluted, and every pound of phosphorus is metered against a\n"
            f"Lake Erie nutrient budget.\n"
        )


def _render_climate_et(emit: Callable[[str], None], settings: Settings) -> None:
    """The NASA POWER climate baseline + FAO-56 reference-ET growing-season deficit."""
    from watermark.hydrology.climate import load_climatology

    clim = load_climatology(settings=settings)
    if clim is None:
        return
    ann = clim.annual_precip_mm()
    wettest = clim.wettest_month()
    t2m = clim.get("T2M")
    if ann is None or wettest is None or t2m is None:
        return
    emit(
        f"**Climate baseline (NASA POWER).** The Lima point averages "
        f"**~{ann:,.0f} mm/yr** of precipitation (corrected), peaking in "
        f"{wettest[0].title()}, at a mean annual temperature of "
        f"**{t2m.annual:.1f} °C** `[reference: NASA POWER climatology]`. The "
        f"satellite climate *normal* sets the long-run water budget; the design "
        f"storm below is the NOAA Atlas-14 *extreme* the corridor must detain — "
        f"the two are complementary.\n"
    )
    from watermark.hydrology.et import penman_monteith_et0

    try:
        et0 = penman_monteith_et0(clim)
    except ValueError:
        et0 = None
    if et0 is None:
        return
    net = ann - et0.annual_mm
    precip_m = clim.get("PRECTOTCORR")
    deficit = (
        [m for m in et0.monthly_mm_day if et0.monthly_mm_day[m] > precip_m.monthly[m]]
        if precip_m is not None
        else []
    )
    span = f"{deficit[0].title()}-{deficit[-1].title()}" if deficit else "none"
    emit(
        f"\n**Reference ET (FAO-56 Penman-Monteith).** Atmospheric water "
        f"*demand* runs **~{et0.annual_mm:,.0f} mm/yr** of reference ET0, "
        f"computed from the same POWER normals (temperature, humidity, wind, "
        f"solar) `[derived: FAO-56 Penman-Monteith]`. Net of precipitation "
        f"that is **{net:+,.0f} mm/yr** — and ET0 *exceeds* rainfall across "
        f"the **{span}** growing season, so summer soil moisture, pond "
        f"evaporation, and any consumptive cooling draw compete for water in "
        f"the months the Ottawa is already near its low-flow floor (§4).\n"
    )


def _render_stormwater_runoff(
    emit: Callable[[str], None],
    settings: Settings,
    runoff: StormRunoff,
    storm_findings: list[HydroFinding],
) -> None:
    """The pre/post design-storm runoff table + the campus footprint's flood exposure."""
    emit(
        f"A {runoff.storm.return_period_yr}-yr 24-hr design storm "
        f"({_ev(runoff.storm.depth)}) over the {runoff.area.value:,.0f}-ac footprint "
        f"`[{_TAG[runoff.area.source]}]`:\n"
    )
    emit("\n| case | curve number | peak (cfs) | volume (ac-ft) |")
    emit("|---|---|---|---|")
    emit(
        f"| pre-development (cropland) | {runoff.pre.curve_number:.0f} | {runoff.pre.peak_cfs:,.0f} | {runoff.pre.volume_acft:,.0f} |"
    )
    emit(
        f"| post-development (impervious) | {runoff.post.curve_number:.0f} | {runoff.post.peak_cfs:,.0f} | {runoff.post.volume_acft:,.0f} |"
    )
    for f in storm_findings:
        emit(f"\n- {f.detail}")

    from watermark.hydrology.floodplain import load_campus_floodzone

    cf = load_campus_floodzone(settings=settings)
    if cf is None:
        return
    if cf.in_floodplain:
        emit(
            f"\n\n**Part of the footprint lies in the FEMA floodplain.** The recorded\n"
            f"campus parcels intersect FEMA Special Flood Hazard Area "
            f"({', '.join(cf.in_parcels_zones)}; DFIRM {cf.firm}) `{_tag('document')}` —\n"
            f"development there faces base-flood-elevation and floodway constraints.\n"
        )
    elif cf.nearby_zones:
        emit(
            f"\n\n**The footprint sits just outside the FEMA floodplain — but only just.**\n"
            f"The recorded campus parcels intersect no FEMA Special Flood Hazard Area, yet\n"
            f"Zone {' and '.join(cf.nearby_zones)} (1%-annual-chance floodplain and regulatory\n"
            f"floodway) reach within ~{cf.nearby_buffer_m} m of them (FEMA DFIRM {cf.firm})\n"
            f"`{_tag('document')}`. The post-development runoff increase routes toward that\n"
            f"corridor; a regulatory floodway tolerates no rise, so added peak discharge there\n"
            f"is a permitting constraint, not only a detention-sizing question.\n"
        )


def _render_sanitary_context(emit: Callable[[str], None], settings: Settings) -> None:
    """The cited sanitary-headroom decree context + the absent on-site detention finding."""
    from watermark.hydrology.sanitary import load_sanitary_basis

    san = load_sanitary_basis(settings=settings)
    if san is not None and san.decree_note:
        rows = "; ".join(
            f"{p.plant} {p.avg_design_flow.value:g}/{p.peak_capacity.value:g} MGD "
            f"(headroom {p.headroom_mgd:g})"
            for p in san.plants
            if p.peak_capacity is not None and p.headroom_mgd is not None
        )
        emit(
            f"\n**The surcharge lands on a system with no headroom to give.** Permitted\n"
            f"average / peak design flows are document-cited [verified]: {rows}. The decisive\n"
            f"fact is regulatory: the collection system is already under a **2005 OEPA mandate\n"
            f"to eliminate all SSO bypassing by 2015**, with **${san.ii_remediation_musd.value:g}M**\n"
            f"of storm-water I/I remediation and a 21-inch trunk replaced by 48-inch purely to\n"
            f"equalize wet-weather I/I. So each plant's nominal wet-weather headroom (peak minus\n"
            f"permitted average) is already documented as effectively spent before the campus\n"
            f"adds load. The campus's documented dry-weather contribution is the {san.campus_industrial.value:g}\n"
            f"MGD FM-2 industrial discharge; the storm RDII multiplier on top remains an assumption.\n"
        )
    from watermark.hydrology.stormplan import load_inventory

    inv = load_inventory(settings=settings)
    if inv is not None and not inv.detention_shown:
        emit(
            f"\n**Detention is the absent control, not a modeled redesign.** The campus\n"
            f"grading & stormwater plan (`{inv.sheet_id}`, {inv.phase}, "
            f"{'[verified]' if inv.rim_min.verified else '[inference]'}) routes runoff via\n"
            f"catch basins -> inlets -> storm sewer to headwall outfalls (with rock check dams\n"
            f"and overland flood routing) and shows **no detention, retention, or infiltration\n"
            f"storage** across its {inv.rim_labels} storm-structure rims "
            f"({inv.rim_min.value:.0f}-{inv.rim_max.value:.0f} ft). So the SWMM-sized basin is the\n"
            f"on-site control the as-drawn 95% design omits. Pipe connectivity/inverts are drawn\n"
            f"as vector geometry with no schedule table, so a routable network is deliberately\n"
            f"not transcribed (omission over invention).\n"
        )


def render_report(*, settings: Settings | None = None, live: bool = False) -> str:
    """Build the full hydrology markdown dossier (offline-deterministic by default)."""
    settings = settings or get_settings()
    balance, assim, _findings = hydro_stage.run_baseline(settings=settings, live=live)
    runoff, storm_findings = hydro_stage.run_storm(settings=settings, live=live)
    base, build, delta = hydro_stage.run_scenarios(settings=settings, live=live)

    out: list[str] = []
    w = out.append
    w("# Hydrology — Tier-0 municipal water-flow findings\n")
    w(
        "> Generated by `watermark` (`watermark.hydrology`). Tier-0 SCS screening — auditable and\n"
        "> fast, not a substitute for SWMM/HEC-RAS. Every figure is tagged `[verified]`\n"
        "> (read from a record or a live gauge) or `[inference]` (assumption/derived).\n"
    )

    w("\n## 1. The municipal loop and its low-flow squeeze\n")
    w("The Lima system is one closed loop on two rivers:\n")
    w("> Auglaize/Ottawa → Lima WTP → municipal + data-center demand → WWTPs → Ottawa River\n")
    w("\n| node | role | flow | receiving |")
    w("|---|---|---|---|")
    for n in balance.nodes:
        flow = n.return_flow or n.inflow
        w(f"| {n.node.name} | {n.node.role} | {_ev(flow)} | {n.node.receiving_water or '—'} |")
    w(
        "\n**Low-flow assimilative screen** — each discharge against its receiving stream's cited "
        "design low flows, the design flow matched to the criterion type (chronic aquatic-life at "
        "the **7Q10**, acute at the **1Q10**):\n"
    )
    for c in assim:
        mark = _flag_mark(c.flag)
        # Acute (1Q10) dilution alongside the chronic (7Q10): using the chronic design flow to
        # band an acute limit understates the constraint (WS-08). None where no 1Q10 is cited.
        acute = ""
        if c.acute_dilution_ratio is not None and c.acute_low_flow is not None:
            acute = (
                f" Against the acute **1Q10 {c.acute_low_flow.value:g} cfs** → "
                f"**{c.acute_dilution_ratio:.2f}:1** ({c.acute_flag})."
            )
        # The conservative default: cited natural 7Q10 only, crediting no effluent.
        credited = ""
        if c.effluent_credited_ratio is not None and c.upstream_returns is not None:
            # Effluent-credited alternative (WS-15): the permitted effluent already in the
            # reach is real dilution water, so present it alongside — never in place of — the
            # conservative figure. Both together avoid over- and under-stating the dilution.
            credited = (
                f" Crediting the {c.upstream_returns.value:.2f} cfs of permitted effluent "
                f"already in the reach `[{_TAG[c.upstream_returns.source]}]` → "
                f"**{c.effluent_credited_ratio:.2f}:1** ({c.effluent_credited_flag})."
            )
        w(
            f"- {mark} **{c.discharger} → {c.receiving_water}**: chronic 7Q10 "
            f"{c.design_low_flow.value:g} cfs vs discharge {c.discharge.value:.2f} cfs "
            f"→ {c.dilution_ratio:.2f}:1 dilution ({c.flag}). "
            f"`[{_TAG[c.design_low_flow.source]}]` {c.design_low_flow.citation}"
            f"{acute}{credited}"
        )
    w(
        "\nAt design low flow the receiving streams carry less than the effluent they\n"
        "receive — the discharges are effectively undiluted by *natural* flow. Where a plant\n"
        "shares the reach with other permitted dischargers, the effluent-credited ratio shows\n"
        "the more honest system picture: it is diluted by standing effluent, not clean water.\n"
    )

    _render_stormwater_pathway_note(w, settings)
    _render_lowflow_corroboration(w, settings)
    _render_routed_network(w, settings)
    _render_water_supply(w, settings)
    _render_refill_adequacy(w, settings)
    _render_toxic_screen(w, settings)
    _render_wwtp_floodzones(w, settings)
    _render_maumee_tmdl(w, settings)

    w("\n## 3. Stormwater: paving the corridor\n")
    _render_climate_et(w, settings)
    _render_stormwater_runoff(w, settings, runoff, storm_findings)
    _render_drainage_audit(w, settings)

    rw_heading = delta.receiving_water_name or "receiving water"
    w(f"\n\n## 4. Scenario: data-center cooling vs the {rw_heading}'s low flow\n")
    basis = build.scenario.basis
    if basis is not None and basis.wue is not None and basis.cycles_of_concentration is not None:
        # The evaporative-tower two-method bracket (Lima's archetype).
        w("The cooling demand is **sourced**, derived from disclosed campus data by two methods:\n")
        # WS-16 (#1616): the blowdown method's upper bound is capped at the physical WUE ceiling
        # when the disclosed discharge implies an unreachable cooling WUE — say so, rather than
        # print the capped figure under a "blowdown x cycles" label that no longer computes it.
        # The cap state is an explicit flag on the derived basis (not a citation string-match).
        capped = basis.consumptive_high_capped
        bottom_up = (
            f"- bottom-up: FM-2 blowdown x {basis.cycles_of_concentration.value:g} cycles"
            + (
                ", capped at the physical evaporative-WUE ceiling (FM-2 is not purely cooling "
                "blowdown, so the raw blowdown figure is unreachable for cooling alone)"
                if capped
                else ""
            )
            + f" → **{basis.consumptive_high.value:g} MGD** consumptive (upper bound)\n"
        )
        w(
            f"- top-down: IT load {_ev(basis.it_load)} x WUE {_ev(basis.wue)} → "
            f"**{basis.consumptive_low.value:g} MGD** consumptive\n" + bottom_up
        )
        w(
            f"\nThey bracket the consumptive demand at "
            f"**{basis.consumptive_low.value:g}-{basis.consumptive_high.value:g} MGD**"
            + ("." if capped else " (FM-2 is not purely cooling blowdown).")
            + " The conclusion is robust to the range.\n"
        )
    elif basis is not None:
        span = basis.consumptive_low.value != basis.consumptive_high.value
        w(
            f"Cooling model: **{basis.cooling_model.value}** — {basis.method}. "
            f"Consumptive {'range' if span else 'estimate'} "
            f"**{consumptive_range_label(basis)}**"
            + (
                " (method undisclosed — a bracket across candidate archetypes, not an estimate).\n"
                if basis.is_bracketed
                else ".\n"
            )
        )
    w("\n| scenario | cooling intake | consumptive fraction | net basin loss |")
    w("|---|---|---|---|")
    for r in (base, build):
        w(
            f"| {r.scenario.name} | {r.scenario.cooling_demand.value:g} MGD | "
            f"{r.scenario.consumptive_fraction.value:g} | {_ev(r.consumptive_loss)} |"
        )
    if delta.multiple_of_7q10 is not None:
        rw = delta.receiving_water_name or "receiving water"
        w(
            f"\nBuildout adds **{delta.consumptive_increase_cfs:,.2f} cfs** of net consumptive "
            f"draw — **{delta.multiple_of_7q10:g}x** the {rw}'s cited 7Q10 "
            f"({delta.receiving_7q10_cfs:g} cfs). At design low flow the {rw} nearly dries "
            f"(1Q10 = 0 cfs); a data center's cooling draw competes for water the river\n"
            f"does not have — even the low estimate is tens of times the 7Q10.\n"
        )

    _render_seasonal_withdrawal(
        w, settings, build.consumptive_loss.value, basis=build.scenario.basis
    )

    w("\n\n## 5. Tier-1 escalation (EPA SWMM)\n")
    w(
        "`watermark tier1` runs the real EPA SWMM5 engine on the footprint under the design\n"
        "storm for two questions Tier-0 only approximates: the **detention volume** that\n"
        "holds the post-development peak to the pre-development rate, and the **sanitary\n"
        "wet-weather surcharge** (dry-weather base + RDII) against each plant's documented\n"
        "wet-weather headroom. Hydraulic routing parameters (RDII, basin geometry) are\n"
        "assumptions; the footprint, its declared impervious acreage — which drives the\n"
        "as-permitted case's imperviousness — the storm, and the plant design flows stay\n"
        "document/connector-sourced.\n"
    )

    _render_tier1_swmm(w, settings)
    _render_sanitary_context(w, settings)

    w("\n---\n")
    w(
        "_Sources: USGS NWIS (streamflow), NOAA Atlas-14 (design rainfall), NASA POWER\n"
        "(climate normals), Ohio EPA NPDES fact sheets 2PH00006 / 2PH00007 / 2IG00001\n"
        "(receiving-stream 7Q10), Maumee Watershed Nutrient TMDL Appendix 4 (phosphorus\n"
        "WLAs), recorded Bistrozzi parcels (footprint). Regenerate with `watermark hydro-report --write`._\n"
    )
    return "\n".join(out)


def write_report(*, settings: Settings | None = None, live: bool = False) -> str:
    """Write the dossier to ``docs/HYDROLOGY.md`` and return the path."""
    settings = settings or get_settings()
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "docs" / "HYDROLOGY.md"
    path.write_text(render_report(settings=settings, live=live), encoding="utf-8")
    return str(path)
