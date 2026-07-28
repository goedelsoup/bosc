"""Dewatering discharge-signal screen -- can the wellfield's discharge be seen in the river?

The construction-dewatering wellfield (:mod:`watermark.hydrology.dewatering`) pumped up to ~4.9 MGD
(~7.6 cfs) of groundwater to grade the campus. That water had to go somewhere -- typically a
permitted construction-dewatering discharge to a receiving water. This module screens the USGS gage
record for that discharge two ways, over the DOCUMENTED pumping window vs. a prior-year baseline:

1. **Reach gain.** The gain between an UPSTREAM gage (Ottawa @ Lima, 128 sq mi) and a DOWNSTREAM one
   (Ottawa near Kalida, 350 sq mi) carries any point input to the reach. Restricted to baseflow
   (recession) days so storm runoff doesn't mask a small steady input, and expressed as a
   drainage-area-ratio residual (downstream - DA_ratio * upstream) so the incremental drainage's
   own baseflow is netted out.
2. **Upstream low-flow floor.** A sustained discharge to the Ottawa *above* the Lima gage would prop
   up that gage's recession floor; if the floor is unchanged, that argues against such a discharge.

The honest result at Lima is a NEGATIVE screen: the ~7.6 cfs candidate is swamped by the ~222 sq mi
of incremental drainage between the gages (baseflow gain ~40 cfs), and the upstream gage still
recedes to ~3 cfs during the window. So the surface-water record can neither confirm nor exclude the
discharge; the construction-dewatering NPDES authorization (its rate + receiving water) is the
``[open]`` owed record. Gage discharge is ``[verified]`` USGS daily values, but every reach-gain
ATTRIBUTION is a screen -- ``[inference]``, never a metered discharge.

A companion read characterizes RESERVOIR RECHARGE over the same window: Lima's off-stream reservoirs
refill by pumping from the Auglaize at high flow, so the primary supply gage's flow regime (median +
days above the pumping passby) says whether the pumping window was itself a good recharge period.
"""

from __future__ import annotations

import statistics
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors.nwis import DailyDischargeSeries, fetch_daily_discharge
from watermark.hydrology.model import HydroFinding, ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile
from watermark.sites._model import DischargeReach

log = get_logger(__name__)

# 1 million gallons/day = 1.54723 cubic feet/second.
CFS_PER_MGD = 1.54723
# Baseflow (recession) days: the driest quartile of upstream flow in each period -- when the reach
# gain is baseflow + any point input, with minimal storm-runoff masking.
_BASEFLOW_QUANTILE = 0.25
# A discharge is only called "separable" when an elevation of at least half the field capacity (and
# never less than this floor) shows in the residual gain or the low-flow floor -- below that it is
# lost in the reach's natural variability.
_SEPARABLE_FLOOR_CFS = 2.0


# --- models -----------------------------------------------------------------------------


class ReachWindow(BaseModel):
    """One period's baseflow reach statistics (upstream + downstream aligned by date)."""

    model_config = ConfigDict(extra="forbid")

    label: str  # "dewatering" | "baseline"
    start: str  # ISO
    end: str  # ISO
    n_days: int
    upstream_median_cfs: float
    upstream_min_cfs: float
    baseflow_days: int
    baseflow_gain_median_cfs: float  # median (downstream - upstream) on baseflow days
    baseflow_resid_median_cfs: float  # median (downstream - DA_ratio * upstream) on baseflow days
    provisional_fraction: float  # share of NWIS provisional (P) days across the two gages


class DischargeScreen(BaseModel):
    """Whether the dewatering discharge is separable in the gage record (all ``[inference]``)."""

    model_config = ConfigDict(extra="forbid")

    upstream_gage: str
    upstream_name: str
    downstream_gage: str
    downstream_name: str
    incremental_da_sqmi: float  # downstream DA - upstream DA (the drainage that swamps the signal)
    expected_discharge_cfs: ProvenancedValue  # field capacity, bracket [0, capacity]
    window: ReachWindow
    baseline: ReachWindow
    baseflow_gain_delta_cfs: float  # window - baseline (raw gain)
    baseflow_resid_delta_cfs: float  # window - baseline (DA-ratio residual)
    upstream_floor_delta_cfs: float  # window upstream min - baseline upstream min
    separable: bool
    outcome: Literal["not_separable", "elevated_gain", "elevated_floor"]
    tag: str = "inference"
    note: str
    caveats: list[str] = []


class ReservoirRecharge(BaseModel):
    """The primary supply gage's flow regime over the window -- reservoir-recharge context."""

    model_config = ConfigDict(extra="forbid")

    gage: str
    gage_name: str
    passby_cfs: float  # the pumping passby minimum (below it the reservoirs cannot refill)
    window_median_cfs: float
    baseline_median_cfs: float
    window_refill_days: int  # days above passby (pumpable to refill) in the window
    baseline_refill_days: int
    window_days: int
    baseline_days: int
    tag: str = "inference"
    note: str
    caveats: list[str] = []


# --- helpers ----------------------------------------------------------------------------


def _median(xs: list[float]) -> float:
    return float(statistics.median(xs)) if xs else 0.0


def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        return 0.0
    idx = min(len(sorted_xs) - 1, int(q * len(sorted_xs)))
    return sorted_xs[idx]


def _shift_year(iso: str, delta: int) -> str:
    """Shift an ISO date by ``delta`` years, clamping Feb 29 to Feb 28."""
    d = date.fromisoformat(iso)
    try:
        return d.replace(year=d.year + delta).isoformat()
    except ValueError:  # Feb 29 in a non-leap target year
        return d.replace(year=d.year + delta, day=28).isoformat()


def _dewatering_window(settings: Settings) -> tuple[str, str] | None:
    """The documented pumping window (first completion -> last sealing) from the wellfield."""
    from watermark.hydrology.dewatering import load_dewatering_wells  # lazy: avoid an import cycle

    wells = load_dewatering_wells(settings=settings)
    starts = sorted(w.completion_date for w in wells if w.completion_date)
    ends = sorted(w.sealed_date for w in wells if w.sealed_date)
    if not starts or not ends:
        return None
    return starts[0], ends[-1]


def _window_stats(
    label: str,
    start: str,
    end: str,
    upstream: DailyDischargeSeries,
    downstream: DailyDischargeSeries,
    *,
    da_ratio: float,
) -> ReachWindow:
    """Baseflow gain / DA-residual for one period, aligning the two gages by calendar date."""
    up = dict(upstream.points())
    dn = dict(downstream.points())
    dates = sorted(set(up) & set(dn))
    lows = [up[d] for d in dates]
    highs = [dn[d] for d in dates]
    thr = _quantile(sorted(lows), _BASEFLOW_QUANTILE)
    gains = [hi - lo for lo, hi in zip(lows, highs, strict=True) if lo <= thr]
    resids = [hi - da_ratio * lo for lo, hi in zip(lows, highs, strict=True) if lo <= thr]
    return ReachWindow(
        label=label,
        start=start,
        end=end,
        n_days=len(dates),
        upstream_median_cfs=round(_median(lows), 1),
        upstream_min_cfs=round(min(lows), 1) if lows else 0.0,
        baseflow_days=len(gains),
        baseflow_gain_median_cfs=round(_median(gains), 1),
        baseflow_resid_median_cfs=round(_median(resids), 1),
        provisional_fraction=round(
            (upstream.provisional_fraction + downstream.provisional_fraction) / 2.0, 2
        ),
    )


# --- compute ----------------------------------------------------------------------------


def compute_discharge_screen(
    reach: DischargeReach,
    upstream_window: DailyDischargeSeries,
    downstream_window: DailyDischargeSeries,
    upstream_baseline: DailyDischargeSeries,
    downstream_baseline: DailyDischargeSeries,
    *,
    capacity_mgd: float,
    window: tuple[str, str],
    baseline: tuple[str, str],
) -> DischargeScreen:
    """Screen the reach gain (window vs baseline) against the expected dewatering discharge."""
    da_ratio = reach.downstream_da_sqmi / reach.upstream_da_sqmi
    win = _window_stats(
        "dewatering", window[0], window[1], upstream_window, downstream_window, da_ratio=da_ratio
    )
    base = _window_stats(
        "baseline",
        baseline[0],
        baseline[1],
        upstream_baseline,
        downstream_baseline,
        da_ratio=da_ratio,
    )

    expected = round(capacity_mgd * CFS_PER_MGD, 1)
    gain_delta = round(win.baseflow_gain_median_cfs - base.baseflow_gain_median_cfs, 1)
    resid_delta = round(win.baseflow_resid_median_cfs - base.baseflow_resid_median_cfs, 1)
    floor_delta = round(win.upstream_min_cfs - base.upstream_min_cfs, 1)

    threshold = max(_SEPARABLE_FLOOR_CFS, 0.5 * expected)
    if resid_delta >= threshold:
        outcome: Literal["not_separable", "elevated_gain", "elevated_floor"] = "elevated_gain"
    elif floor_delta >= threshold:
        outcome = "elevated_floor"
    else:
        outcome = "not_separable"
    separable = outcome != "not_separable"

    incremental = round(reach.downstream_da_sqmi - reach.upstream_da_sqmi, 0)
    note = _screen_note(reach, outcome, expected, resid_delta, floor_delta, incremental)
    caveats = [
        "Gage discharge is [verified] USGS daily values; the reach-gain ATTRIBUTION to dewatering "
        "is [inference] -- a screen, never a metered discharge.",
        f"The {incremental:g} sq mi of incremental drainage between the gages produces a baseflow "
        f"gain of ~{base.baseflow_gain_median_cfs:g} cfs, so a ~{expected:g} cfs point source sits "
        "inside the reach's natural variability.",
        "The discharge point + rate are not on record (the construction-dewatering NPDES "
        "authorization is an [open] owed record), so 'to this reach' is itself an assumption -- the "
        "water may have gone to a storm sewer, infiltration, or another receiving water.",
    ]
    if win.provisional_fraction > 0 or base.provisional_fraction > 0:
        caveats.append(
            "Recent water-years are NWIS provisional (unreviewed); the screen is directional only."
        )

    return DischargeScreen(
        upstream_gage=reach.upstream_gage,
        upstream_name=reach.upstream_name,
        downstream_gage=reach.downstream_gage,
        downstream_name=reach.downstream_name,
        incremental_da_sqmi=incremental,
        expected_discharge_cfs=ProvenancedValue.derived(
            expected,
            "cfs",
            f"Dewatering field capacity {capacity_mgd:g} MGD x {CFS_PER_MGD} cfs/MGD [inference]; "
            "an upper bound (staged installs/sealings + unknown routing) -> bracket [0, capacity].",
            low=0.0,
            high=expected,
        ),
        window=win,
        baseline=base,
        baseflow_gain_delta_cfs=gain_delta,
        baseflow_resid_delta_cfs=resid_delta,
        upstream_floor_delta_cfs=floor_delta,
        separable=separable,
        outcome=outcome,
        note=note,
        caveats=caveats,
    )


def _screen_note(
    reach: DischargeReach,
    outcome: str,
    expected: float,
    resid_delta: float,
    floor_delta: float,
    incremental: float,
) -> str:
    if outcome == "elevated_gain":
        return (
            f"The {reach.upstream_name} -> {reach.downstream_name} baseflow reach gain runs "
            f"{resid_delta:g} cfs higher during the dewatering window than the prior-year baseline "
            f"-- consistent with a ~{expected:g} cfs discharge to the reach, though not proof of one."
        )
    if outcome == "elevated_floor":
        return (
            f"The upstream {reach.upstream_name} low-flow floor sits {floor_delta:g} cfs higher "
            "during the window -- consistent with a sustained discharge to the Ottawa above the gage."
        )
    return (
        f"NOT SEPARABLE: the dewatering discharge (up to ~{expected:g} cfs) does not register in the "
        f"{reach.upstream_name} -> {reach.downstream_name} reach. The baseflow reach gain is "
        f"{resid_delta:+g} cfs vs the prior-year baseline and the upstream low-flow floor "
        f"{floor_delta:+g} cfs -- both within noise, swamped by the {incremental:g} sq mi of "
        "incremental drainage. The surface-water record can neither confirm nor exclude the "
        "discharge; its rate + receiving water are the [open] owed record."
    )


def load_discharge_screen(*, settings: Settings | None = None) -> DischargeScreen | None:
    """Screen the active site's dewatering discharge against its bracketing gage reach."""
    settings = settings or get_settings()
    reach = active_profile(settings).dewatering_discharge_reach
    if reach is None:
        return None
    span = _dewatering_window(settings)
    if span is None:
        return None
    from watermark.hydrology.dewatering import load_dewatering_wells  # lazy: avoid an import cycle

    win_start, win_end = span
    base_start, base_end = _shift_year(win_start, -1), _shift_year(win_end, -1)
    wells = load_dewatering_wells(settings=settings)
    capacity_mgd = round(sum(w.test_rate_gpm or 0.0 for w in wells) * 1440.0 / 1e6, 2)

    def dv(site: str, start: str, end: str) -> DailyDischargeSeries:
        return fetch_daily_discharge(site, start_date=start, end_date=end, settings=settings)

    try:
        up_w = dv(reach.upstream_gage, win_start, win_end)
        dn_w = dv(reach.downstream_gage, win_start, win_end)
        up_b = dv(reach.upstream_gage, base_start, base_end)
        dn_b = dv(reach.downstream_gage, base_start, base_end)
    except ValueError as exc:  # a gage with no DV over a window -> no screen, not a crash
        log.warning("dewatering_discharge.no_dv", error=str(exc).splitlines()[0])
        return None
    return compute_discharge_screen(
        reach,
        up_w,
        dn_w,
        up_b,
        dn_b,
        capacity_mgd=capacity_mgd,
        window=(win_start, win_end),
        baseline=(base_start, base_end),
    )


def load_reservoir_recharge(*, settings: Settings | None = None) -> ReservoirRecharge | None:
    """Characterize reservoir-recharge conditions (primary supply gage) over the pumping window."""
    settings = settings or get_settings()
    profile = active_profile(settings)
    gage = profile.supply_gage_primary
    if not gage or gage == "TODO":
        return None
    span = _dewatering_window(settings)
    if span is None:
        return None
    win_start, win_end = span
    base_start, base_end = _shift_year(win_start, -1), _shift_year(win_end, -1)
    passby = float(profile.passby_primary_cfs)

    def dv(start: str, end: str) -> DailyDischargeSeries:
        return fetch_daily_discharge(gage, start_date=start, end_date=end, settings=settings)

    try:
        win = dv(win_start, win_end)
        base = dv(base_start, base_end)
    except ValueError as exc:
        log.warning("dewatering_discharge.reservoir.no_dv", error=str(exc).splitlines()[0])
        return None
    win_q = [q for _, q in win.points()]
    base_q = [q for _, q in base.points()]
    win_refill = sum(1 for q in win_q if q > passby)
    base_refill = sum(1 for q in base_q if q > passby)
    return ReservoirRecharge(
        gage=win.site_no,
        gage_name=win.name,
        passby_cfs=round(passby, 1),
        window_median_cfs=round(_median(win_q), 1),
        baseline_median_cfs=round(_median(base_q), 1),
        window_refill_days=win_refill,
        baseline_refill_days=base_refill,
        window_days=len(win_q),
        baseline_days=len(base_q),
        note=(
            f"Over the pumping window the {win.name} ran a median {round(_median(win_q)):g} cfs with "
            f"{win_refill} of {len(win_q)} days above the {round(passby):g} cfs pumping passby "
            f"(vs {base_refill} of {len(base_q)} the prior year) -- the days Lima could pump the "
            "off-stream reservoirs full. Recharge context, not a dewatering effect: the reservoirs "
            "refill from the rivers at high flow, independent of the campus grading."
        ),
        caveats=[
            "Supply-gage flow is [verified] USGS daily values; the refill-day count is [inference] "
            "(the pumping passby is the modeling minimum, not a metered diversion schedule).",
        ],
    )


# --- findings ---------------------------------------------------------------------------


class DewateringDischargeReport(BaseModel):
    """The committed 'where did the water go?' report -- the reach screen + recharge context.

    A snapshot over a FIXED historical window, so it is committed as a regenerable reference
    artifact (like ``low-flow-7q10.derived.yaml``) rather than pulled live at export: the content
    bundle reads it offline and deterministically, and CI never touches the network. Regenerate with
    ``watermark dewatering-discharge --write``.
    """

    model_config = ConfigDict(extra="forbid")

    as_of: str  # ISO snapshot date (the ODNR records-pull date the wellfield window is keyed to)
    screen: DischargeScreen | None = None
    reservoir_recharge: ReservoirRecharge | None = None


def build_discharge_report(
    *, as_of: str, settings: Settings | None = None
) -> DewateringDischargeReport | None:
    """Assemble the discharge screen + reservoir-recharge read (pulls the gage record LIVE)."""
    settings = settings or get_settings()
    screen = load_discharge_screen(settings=settings)
    recharge = load_reservoir_recharge(settings=settings)
    if screen is None and recharge is None:
        return None
    return DewateringDischargeReport(as_of=as_of, screen=screen, reservoir_recharge=recharge)


def discharge_report_path(settings: Settings) -> Path | None:
    """The active site's committed discharge-report YAML, or ``None`` if it has none."""
    relpath = active_profile(settings).dewatering_discharge_relpath
    return settings.data_dir / relpath if relpath else None


def write_discharge_report(report: DewateringDischargeReport, out_path: Path) -> Path:
    """Write the report as a byte-stable committed YAML (deterministic re-runs)."""
    payload = {
        "meta": {
            "subject": "Dewatering discharge-signal screen + reservoir-recharge context",
            "source": "USGS NWIS daily values (discharge, 00060) [verified]; screen [inference]",
            "as_of": report.as_of,
            "units": "cfs; drainage area sq mi",
        },
        **report.model_dump(mode="json"),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out_path


def read_discharge_report(*, settings: Settings | None = None) -> DewateringDischargeReport | None:
    """Read the active site's committed discharge report (offline, no network)."""
    settings = settings or get_settings()
    path = discharge_report_path(settings)
    if path is None or not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.pop("meta", None)
    return DewateringDischargeReport.model_validate(data)


def discharge_screen_findings(screen: DischargeScreen) -> list[HydroFinding]:
    """Narrate the discharge screen in the hydrology finding idiom."""
    subject = f"{screen.upstream_name} -> {screen.downstream_name} reach"
    return [
        HydroFinding(
            subject=subject,
            check="dewatering-discharge-signal",
            ok=True,  # a surfaced screen, not a pass/fail
            detail=screen.note,
        )
    ]


def reservoir_recharge_findings(recharge: ReservoirRecharge) -> list[HydroFinding]:
    """Narrate the reservoir-recharge context in the hydrology finding idiom."""
    return [
        HydroFinding(
            subject=f"{recharge.gage_name} supply",
            check="dewatering-reservoir-recharge",
            ok=True,
            detail=recharge.note,
        )
    ]
