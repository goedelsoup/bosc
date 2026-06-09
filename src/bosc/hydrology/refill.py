"""Refill adequacy: can high-flow pumping keep Lima's reservoirs full against demand?

The storage budget (:mod:`bosc.hydrology.supply`) shows the campus draw against the *stock*
of ~15 BG. This module closes the loop on the *flow*: the reservoirs are off-stream, filled
by pumping from the Auglaize and Ottawa **only when the rivers run high**, so the question is
whether that refill keeps up — especially through a drought.

Two answers, from the gauged daily record:

* **Normal years — trivially adequate.** The combined mean flow of the two rivers is many
  times the city+campus demand, so in an average year there is far more water to pump than to
  treat (``annual_supply_multiple``).
* **Drought — the binding case.** Both rivers fall below demand for long stretches (the Ottawa
  reaches 0 cfs; the Auglaize near Lima sits below the city+campus draw ~a quarter of the
  time), and the system lives off storage. The **sequent-peak (Rippl) storage requirement** —
  the maximum cumulative deficit of (demand - pumpable inflow) over the record — is the active
  storage the worst historical drawdown calls on. Compared to the real ~14.4 BG it shows how
  much margin the campus eats, and the residual risk is a drought worse than the gauged record.

A *derived* screening analysis. The committed artifact
(``data/reference/hydrology/refill-adequacy.yaml``) is regenerated from the live USGS record by
``bosc refill --write`` and read offline by :func:`load_refill_adequacy`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors.nwis import fetch_daily_discharge
from bosc.hydrology.cooling import derive_cooling_basis
from bosc.hydrology.model import (
    DroughtDrawdown,
    HydroFinding,
    RefillAdequacy,
    RiverFlowStat,
)
from bosc.hydrology.supply import campus_budget_from_cooling, load_supply
from bosc.hydrology.units import cfs_to_mgd, mgd_to_cfs
from bosc.logging import get_logger

log = get_logger(__name__)

# The long-record discharge gages for Lima's two supply rivers. 04185750 (Auglaize near Lima)
# carries no daily-discharge record, so the Auglaize is gauged at Fort Jennings (04186500,
# 1921-present) — DOWNSTREAM of Lima's intakes with more drainage area, so it OVERSTATES the
# flow at the intake (an optimistic refill bound, flagged in the caveats).
DEFAULT_AUGLAIZE_SITE = "04186500"
DEFAULT_OTTAWA_SITE = "04187100"
# Screening minimum bypass left in-stream (not pumped to storage). Ottawa = its cited 7Q10;
# the Auglaize has no cited 7Q10 in the corpus, so a small assumption near its 99% exceedance.
DEFAULT_PASSBY_AUGLAIZE_CFS = 2.5
DEFAULT_PASSBY_OTTAWA_CFS = 0.2
_START, _END = "1980-01-01", "2024-12-31"
_DAYS_PER_YEAR = 365.0
_FILENAME = "refill-adequacy.yaml"
_METHOD = (
    "sequent-peak (Rippl) storage requirement on aligned daily NWIS discharge, passby-adjusted"
)


def _exceedance(asc: list[float], frac: float) -> float:
    """Flow exceeded ``frac`` of the days (e.g. 0.90 -> the low p90 flow), from an ascending list."""
    if not asc:
        return 0.0
    idx = int((1.0 - frac) * len(asc))
    return asc[min(max(idx, 0), len(asc) - 1)]


def _sequent_peak(available_mgd: list[float], demand_mgd: float) -> tuple[float, int, int]:
    """Rippl storage requirement: max cumulative deficit of (demand - inflow), and its spell.

    Returns ``(required_storage_mg, worst_spell_start_index, worst_spell_days)``. A pure
    accumulator over the daily series — no network, no reservoir geometry.
    """
    required = 0.0
    running = 0.0
    cur_start = 0
    cur_len = 0
    worst_start = 0
    worst_len = 0
    for i, avail in enumerate(available_mgd):
        net = demand_mgd - avail  # >0 draws storage down
        if net > 0:
            if running == 0.0:
                cur_start = i
                cur_len = 0
            running += net
            cur_len += 1
            if running > required:
                required = running
                worst_start = cur_start
                worst_len = cur_len
        else:
            running += net  # surplus refills
            if running <= 0.0:
                running = 0.0
                cur_len = 0
    return required, worst_start, worst_len


def _river_stat(
    site_no: str,
    site_name: str,
    river: str,
    points: list[tuple[str, float]],
    *,
    passby_cfs: float,
    demand_cfs: float,
    note: str,
) -> RiverFlowStat:
    asc = sorted(v for _, v in points)
    n = len(asc)
    below = sum(1 for v in asc if v < demand_cfs)
    return RiverFlowStat(
        site_no=site_no,
        site_name=site_name,
        river=river,
        period_start=points[0][0],
        period_end=points[-1][0],
        record_days=n,
        mean_cfs=round(sum(asc) / n, 1) if n else 0.0,
        median_cfs=round(_exceedance(asc, 0.5), 1),
        min_cfs=round(asc[0], 2) if n else 0.0,
        p90_cfs=round(_exceedance(asc, 0.90), 1),
        p95_cfs=round(_exceedance(asc, 0.95), 1),
        p99_cfs=round(_exceedance(asc, 0.99), 2),
        passby_cfs=passby_cfs,
        pct_days_below_demand=round(100.0 * below / n, 1) if n else None,
        note=note,
    )


def compute_refill_adequacy(
    *,
    auglaize_site: str = DEFAULT_AUGLAIZE_SITE,
    ottawa_site: str = DEFAULT_OTTAWA_SITE,
    start_date: str = _START,
    end_date: str = _END,
    passby_auglaize_cfs: float = DEFAULT_PASSBY_AUGLAIZE_CFS,
    passby_ottawa_cfs: float = DEFAULT_PASSBY_OTTAWA_CFS,
    settings: Settings | None = None,
) -> RefillAdequacy:
    """Compute the refill adequacy / drought storage-requirement from the live gage records.

    The networked regeneration path (``bosc refill --write``). Pulls both rivers' daily
    discharge, characterizes each, and runs the sequent-peak storage requirement for the
    baseline-city / +campus / +campus-high demand scenarios against the committed storage.
    """
    settings = settings or get_settings()
    supply = load_supply(settings=settings)
    if supply is None:
        raise ValueError("water-supply.yaml absent — cannot scale refill against storage")

    budget = campus_budget_from_cooling(supply)
    basis = derive_cooling_basis()
    municipal = supply.current_production.value
    gross = budget.gross_production_mgd
    makeup_high = (
        basis.consumptive_high.value / basis.consumptive_fraction.value
        if basis.consumptive_fraction.value
        else basis.makeup_demand.value
    )
    gross_high = round(municipal + makeup_high, 2)
    demand_scenarios = [
        ("baseline city", round(municipal, 2)),
        ("+campus (central)", round(gross, 2)),
        ("+campus (high bound)", gross_high),
    ]
    demand_cfs = mgd_to_cfs(gross)
    capacity = supply.total_storage_mg

    aug = fetch_daily_discharge(
        auglaize_site, start_date=start_date, end_date=end_date, settings=settings
    )
    ott = fetch_daily_discharge(
        ottawa_site, start_date=start_date, end_date=end_date, settings=settings
    )
    aug_pts, ott_pts = aug.points(), ott.points()
    if not aug_pts or not ott_pts:
        raise ValueError("empty daily record for a supply gage")

    rivers = [
        _river_stat(
            aug.site_no,
            aug.name,
            "Auglaize River",
            aug_pts,
            passby_cfs=passby_auglaize_cfs,
            demand_cfs=demand_cfs,
            note=(
                "gauged at Fort Jennings, DOWNSTREAM of Lima's Auglaize intakes with more "
                "drainage area — overstates the flow at the intake (optimistic refill)"
            ),
        ),
        _river_stat(
            ott.site_no,
            ott.name,
            "Ottawa River",
            ott_pts,
            passby_cfs=passby_ottawa_cfs,
            demand_cfs=demand_cfs,
            note="net of Lima's upstream Ottawa intakes; reaches 0 cfs in drought",
        ),
    ]

    # Align both records on common dates for the combined sequent-peak.
    aug_by_date = dict(aug_pts)
    ott_by_date = dict(ott_pts)
    dates = sorted(set(aug_by_date) & set(ott_by_date))
    available_mgd = [
        cfs_to_mgd(
            max(0.0, aug_by_date[d] - passby_auglaize_cfs)
            + max(0.0, ott_by_date[d] - passby_ottawa_cfs)
        )
        for d in dates
    ]
    combined_mean_cfs = (
        round(sum(aug_by_date[d] + ott_by_date[d] for d in dates) / len(dates), 1) if dates else 0.0
    )

    scenarios: list[DroughtDrawdown] = []
    for label, demand in demand_scenarios:
        required, w_start, w_len = _sequent_peak(available_mgd, demand)
        scenarios.append(
            DroughtDrawdown(
                label=label,
                demand_mgd=demand,
                required_storage_mg=round(required, 1),
                pct_of_capacity=round(100.0 * required / capacity, 1) if capacity else 0.0,
                worst_spell_start=dates[w_start] if dates else None,
                worst_spell_days=w_len,
                survives=required < capacity,
            )
        )

    annual_demand_mg = round(gross * _DAYS_PER_YEAR, 0)
    combined_mean_mgd = cfs_to_mgd(combined_mean_cfs)
    ra = RefillAdequacy(
        period_start=dates[0] if dates else start_date,
        period_end=dates[-1] if dates else end_date,
        aligned_days=len(dates),
        storage_capacity_mg=capacity,
        combined_mean_cfs=combined_mean_cfs,
        annual_demand_mg=annual_demand_mg,
        annual_supply_multiple=round(combined_mean_mgd / gross, 1) if gross else 0.0,
        rivers=rivers,
        scenarios=scenarios,
        method=_METHOD,
        warnings=[],
        caveats=[
            "Auglaize gauged at Fort Jennings (downstream, larger drainage area) — overstates "
            "intake flow, so the storage requirement is an UNDER-estimate (optimistic).",
            "Pure sequent-peak captures all surplus above passby (no pump-rate cap) — also "
            "optimistic; a real pump-capacity limit would raise the storage requirement.",
            "Passby flows are screening assumptions (Ottawa = cited 7Q10 0.2 cfs; Auglaize 2.5 "
            "cfs, no cited 7Q10); reservoir evaporation is not subtracted.",
            "The binding drought is the worst in the GAUGED record — a longer/deeper drought "
            "than ~1988-2024 would call on more storage than shown.",
        ],
    )
    log.info(
        "hydro.refill",
        aligned_days=ra.aligned_days,
        supply_multiple=ra.annual_supply_multiple,
        baseline_pct=scenarios[0].pct_of_capacity,
        campus_pct=scenarios[1].pct_of_capacity,
    )
    return ra


def refill_findings(ra: RefillAdequacy) -> list[HydroFinding]:
    """Findings: normal-year adequacy, drought survival, and the campus's erosion of margin."""
    findings: list[HydroFinding] = [
        HydroFinding(
            subject="normal-year refill",
            check="refill-annual-surplus",
            ok=ra.annual_supply_multiple > 1.0,
            detail=(
                f"the two rivers' combined mean flow is {ra.combined_mean_cfs:g} cfs — "
                f"~{ra.annual_supply_multiple:g}x the city+campus demand; in an average year "
                "there is far more water to pump than to treat, so refill is amply adequate."
            ),
        )
    ]
    base = ra.scenario("baseline city")
    campus = ra.scenario("+campus (central)")
    high = ra.scenario("+campus (high bound)")
    if base is not None and campus is not None:
        findings.append(
            HydroFinding(
                subject="worst-drought storage requirement",
                check="refill-drought-drawdown",
                ok=campus.survives,
                detail=(
                    f"the worst gauged drawdown (~{campus.worst_spell_days}d from "
                    f"{campus.worst_spell_start}) calls on {campus.required_storage_mg:,.0f} MG "
                    f"with the campus ({campus.pct_of_capacity:g}% of the "
                    f"{ra.storage_capacity_mg:,.0f} MG storage) vs {base.required_storage_mg:,.0f} "
                    f"MG city-only ({base.pct_of_capacity:g}%) — "
                    f"{'survives with margin' if campus.survives else 'EXCEEDS storage'}."
                ),
            )
        )
        eroded = round(campus.required_storage_mg - base.required_storage_mg, 0)
        findings.append(
            HydroFinding(
                subject="campus erosion of the drought buffer",
                check="refill-margin-erosion",
                ok=True,
                detail=(
                    f"the campus adds {eroded:,.0f} MG to the worst-drought storage call "
                    f"({base.pct_of_capacity:g}% -> {campus.pct_of_capacity:g}% of capacity) and "
                    f"lengthens the binding drawdown {base.worst_spell_days} -> "
                    f"{campus.worst_spell_days} days."
                ),
            )
        )
    if high is not None:
        findings.append(
            HydroFinding(
                subject="extended-drought sensitivity",
                check="refill-extended-drought",
                ok=high.survives,
                detail=(
                    f"at the high cooling bound ({high.demand_mgd:g} MGD) the worst gauged drought "
                    f"calls on {high.pct_of_capacity:g}% of storage; a drought longer or deeper "
                    "than the 1988-2024 record is the residual exposure this screen cannot bound."
                ),
            )
        )
    return findings


def _reference_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / _FILENAME


def write_refill_adequacy(ra: RefillAdequacy, *, settings: Settings | None = None) -> Path:
    """Persist the refill adequacy analysis to the committed reference YAML."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": "Refill adequacy / drought storage requirement — Lima reservoir system",
            "source": (
                f"USGS NWIS daily discharge: Auglaize {DEFAULT_AUGLAIZE_SITE} (Fort Jennings) + "
                f"Ottawa {DEFAULT_OTTAWA_SITE} (Lima); storage from water-supply.yaml"
            ),
            "method": ra.method,
            "discipline": (
                "Derived screening: sequent-peak storage requirement vs committed reservoir "
                "storage. Refill is amply adequate in normal years; the binding case is the "
                "worst gauged drought, and the residual risk is a drought beyond the record."
            ),
        },
        "refill": ra.model_dump(mode="json"),
    }
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    log.info("hydro.refill.wrote", path=str(path))
    return path


def load_refill_adequacy(*, settings: Settings | None = None) -> RefillAdequacy | None:
    """Load the committed refill adequacy analysis, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    payload = data.get("refill")
    if not payload:
        return None
    return RefillAdequacy.model_validate(payload)
