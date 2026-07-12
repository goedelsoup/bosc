"""Read the Maumee-at-Waterville continuous monitor against the Napoleon spill timeline.

USGS **04193500** (Maumee River at Waterville OH) is the network's instrument on the
lower Maumee and the basin's derived 7Q10 reference. It ran through the whole
Napoleon / Huston Creek fertilizer spill (#1497), so this module reads its
instantaneous-value record across the event window and asks one question: **is any
signal attributable to the release, or merely coincident with the storm that failed
the containment dam?**

The record answers it with a travel-time argument, not a chemistry one — the gage has
**no ammonia or nitrate probe**. Turbidity, phycocyanin (fPC) and specific conductance
are optical/ionic *surrogates*; the reach's nitrogen signal must come from the OEPA /
Napoleon grab samples (the record sub-issue), never from this monitor. So every
attributed read here stays ``[inference]``:

* The loud signal — two turbidity spikes to ~324 / ~363 FNU on **Jul 10** — **pre-dates
  the overnight Jul 10 -> Jul 11 dam failure**, so at any positive travel time it cannot
  be the release plume. It is storm first-flush / resuspension from the same rain.
* Specific conductance *dropped* (storm dilution) on Jul 10 rather than bumping, so no
  dissolved-ion plume is visible in-window either; at the ~1-day travel time the
  dam-failure plume's leading edge only reaches Waterville at the very end of the record.
* The Jul 4-6 DO sag (to ~4.3 mg/L) tracks the low-flow / 35.5 deg-C heat window and
  *pre-dates* the dam failure — noted as thermal, not attributed to the spill.
* The Jul 5-6 discharge trough (~424 cfs, ~3.7x the derived 7Q10) means the initial
  spill week had a tight assimilative denominator — minimal dilution of any input.

A *derived* screening read. The committed artifact
(``data/reference/hydrology/toledo/waterville-spill-monitor-read.yaml``) is regenerated
from the live USGS record by ``watermark waterville-monitor --write`` and read offline by
:func:`load_monitor_read`. The raw event record is frozen as a committed IV fixture
(the IV service only retains ~120 days, so the fixture is its durable copy).
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.basin import load_derived_low_flows
from watermark.hydrology.connectors.nwis import (
    DISCHARGE_CFS,
    DISSOLVED_OXYGEN_MG_L,
    PHYCOCYANIN_UG_L,
    TURBIDITY_FNU,
    InstantaneousSeries,
    fetch_instantaneous_series,
)
from watermark.hydrology.models import (
    ContinuousMonitorRead,
    HydroFinding,
    MonitorSpike,
    ProvenancedValue,
)
from watermark.logging import get_logger

log = get_logger(__name__)

# The event window and the gage's parameter set (the committed IV fixture is this exact
# request). fPC is NWIS pcode 32319 (phycocyanin, ug/L) — NOT 32316, which is chlorophyll-a;
# #1498's brief cited 32316 in error. 00095 (specific conductance) is the ionic surrogate a
# dissolved-fertilizer plume would move; 00010 (water temp) is the DO sag's thermal driver.
SITE_NO = "04193500"
SITE_NAME = "Maumee River at Waterville OH"
WINDOW_START = "2026-07-01"
WINDOW_END = "2026-07-12"
WATER_TEMP_C = "00010"
SPECIFIC_CONDUCTANCE = "00095"
CHLOROPHYLL_A_UG_L = "32316"  # what #1498 mislabeled as fPC; kept so the mislabel is auditable
EVENT_PARAMS = (
    DISCHARGE_CFS,
    SPECIFIC_CONDUCTANCE,
    DISSOLVED_OXYGEN_MG_L,
    WATER_TEMP_C,
    TURBIDITY_FNU,
    CHLOROPHYLL_A_UG_L,
    PHYCOCYANIN_UG_L,
)

# The clock the plume starts from: the containment dam failed overnight Fri Jul 10 -> Sat
# Jul 11 under heavy rain ([verified], #1497). We start it at the midnight boundary — the
# earliest edge of the overnight window, i.e. the *most generous* (earliest) plume arrival.
RELEASE_START = "2026-07-11T00:00-04:00"

# Huston Creek mouth -> Waterville along the Maumee mainstem. Measured by NLDI upstream-main
# navigation from the 04193500 gage to the Maumee-at-Napoleon gage (04192550, 209 m off the
# nearest flowline vertex); the Huston Creek mouth sits within ~1-2 km of the Napoleon gage
# (Meyerholtz Park, west Napoleon), so the gage-to-gage distance is the reach proxy.
REACH_RIVER_KM = 41.9
REACH_CITATION = (
    "NLDI upstream-main navigation 04193500->04192550 (Maumee mainstem, sinuosity 1.16); "
    "Huston Creek mouth within ~1-2 km of the Napoleon gage"
)

# Mean advective velocity bracket at the Jul 11-12 storm flows (~2,500-3,700 cfs), from
# Manning normal-depth (watermark.hydrology.solver.routing) over a plausible lower-Maumee
# geometry range (width 350-550 ft, slope 1.0e-4..3.0e-4, n 0.030-0.040). Robust to the
# assumptions: ~1.2-1.8 ft/s. This is the *solute* (water-parcel) speed, not the faster
# flood-wave celerity.
VELOCITY_LOW_FPS = 1.2
VELOCITY_HIGH_FPS = 1.8
VELOCITY_CITATION = (
    "Manning normal-depth mean velocity at ~2,500-3,700 cfs over a lower-Maumee geometry "
    "range (W 350-550 ft, S 1e-4..3e-4, n 0.030-0.040); advective, not flood-wave celerity"
)

_FT_PER_KM = 3280.84
_FILENAME = "waterville-spill-monitor-read.yaml"
_TURBIDITY_SPIKE_FNU = 100.0  # an isolated transient well above the ~30 FNU baseline


def _reference_dir(settings: Settings) -> Path:
    """The per-site toledo hydrology reference dir (slug-scoped, #1220)."""
    return settings.data_dir / "reference" / "hydrology" / "toledo"


def _by_param(series: list[InstantaneousSeries]) -> dict[str, InstantaneousSeries]:
    return {s.parameter_cd: s for s in series}


def load_event_series(*, settings: Settings | None = None) -> list[InstantaneousSeries]:
    """The gage's instantaneous record for the event window (offline-replayed from fixture)."""
    settings = settings or get_settings()
    return fetch_instantaneous_series(
        SITE_NO,
        parameter_cds=EVENT_PARAMS,
        start_date=WINDOW_START,
        end_date=WINDOW_END,
        settings=settings,
    )


def _travel_hours(reach_km: float, velocity_fps: float) -> float:
    return reach_km * _FT_PER_KM / velocity_fps / 3600.0


def read_monitor(
    series: list[InstantaneousSeries],
    *,
    seven_q10: ProvenancedValue,
    reach_km: float = REACH_RIVER_KM,
    velocity_low_fps: float = VELOCITY_LOW_FPS,
    velocity_high_fps: float = VELOCITY_HIGH_FPS,
    release_start: str = RELEASE_START,
) -> ContinuousMonitorRead:
    """Read the continuous record into a structured, attribution-disciplined result.

    Observational fields are ``connector`` ``[verified]`` extrema of the record; the
    travel-time and attribution fields are ``derived`` ``[inference]``. The verdict is
    driven by whether the observed turbidity spikes pre-date ``release_start``: a spike
    earlier than the release cannot, at any positive travel time, be its plume.
    """
    by = _by_param(series)

    def extremum(param: str, want_max: bool) -> tuple[str, float]:
        pts = by[param].points()
        return (max if want_max else min)(pts, key=lambda p: p[1])

    # --- discharge & the assimilative denominator ---
    q_pts = by[DISCHARGE_CFS].points()
    q_min_t, q_min = min(q_pts, key=lambda p: p[1])
    q_peak_t, q_peak = max(q_pts, key=lambda p: p[1])
    q_unit = by[DISCHARGE_CFS].unit
    dilution = round(q_min / seven_q10.value, 2)

    # --- turbidity: baseline + isolated spikes ---
    turb = by[TURBIDITY_FNU]
    turb_pts = turb.points()
    baseline = round(statistics.median(v for _, v in turb_pts), 1)
    spikes = [
        MonitorSpike(timestamp=t, value=v, unit=turb.unit)
        for t, v in turb_pts
        if v >= _TURBIDITY_SPIKE_FNU
    ]

    # --- DO sag + its thermal driver ---
    do_t, do_v = extremum(DISSOLVED_OXYGEN_MG_L, want_max=False)
    temp_t, temp_v = extremum(WATER_TEMP_C, want_max=True)

    # --- specific conductance: storm dilution (min) vs low-flow concentration (max) ---
    cond = by[SPECIFIC_CONDUCTANCE]
    cond_min_t, cond_min = min(cond.points(), key=lambda p: p[1])
    cond_max_t, cond_max = max(cond.points(), key=lambda p: p[1])

    # --- phycocyanin: the true monthly high vs the value co-timed with the turbidity spike ---
    fpc = by[PHYCOCYANIN_UG_L]
    fpc_max_t, fpc_max = max(fpc.points(), key=lambda p: p[1])
    spike_day_noon = spikes[0].timestamp[:11] + "12:00:00.000-04:00" if spikes else None
    fpc_at_spike = next(
        ((t, v) for t, v in fpc.points() if t == spike_day_noon),
        (fpc_max_t, fpc_max),
    )

    # --- travel-time argument (advective) ---
    travel_high = _travel_hours(reach_km, velocity_low_fps)  # slow water -> long travel
    travel_low = _travel_hours(reach_km, velocity_high_fps)  # fast water -> short travel
    travel_mid = 0.5 * (travel_low + travel_high)

    latest_spike = max((s.timestamp for s in spikes), default="")
    spikes_precede = bool(spikes) and latest_spike < release_start
    if spikes_precede:
        attribution = (
            f"[inference] The turbidity spikes ({', '.join(f'{s.value:g} FNU @ {s.timestamp[:16]}' for s in spikes)}) "
            f"pre-date the overnight dam failure ({release_start[:10]}); at the ~{travel_low:.0f}-{travel_high:.0f} h "
            "reach travel time the release plume cannot reach Waterville until late Jul 11-Jul 12, "
            "so the spikes are storm first-flush / resuspension, NOT the release plume."
        )
    else:
        attribution = (
            "[inference] The observed spikes post-date the release, but optical/ionic surrogates "
            "are not a nitrogen measurement; plume attribution needs the OEPA/Napoleon grab samples."
        )

    caveats = [
        "Turbidity, fPC and specific conductance are optical/ionic SURROGATES; 04193500 has no "
        "ammonia or nitrate probe, so the reach's nitrogen signal must come from grab samples.",
        "#1498's brief cited pcode 32316 as fPC in error: 32316 is chlorophyll-a; phycocyanin is "
        "32319/32321. fPC was sub-bloom all month and its Jul-10 value is below its Jul-1/2 diel peaks.",
        "Reach geometry (width/slope/n) behind the velocity bracket is an assumption; the travel "
        "time is a range, and the attribution rests on the spike-vs-release ORDERING, not its width.",
        "The window ends Jul 12; the dam-failure plume's expected arrival lands at the very edge of "
        "the record, so an in-window absence of an ionic bump is 'not captured', not 'did not occur'.",
    ]

    def connector(value: float, unit: str, asof: str, note: str) -> ProvenancedValue:
        return ProvenancedValue.from_connector(
            value, unit, citation=f"NWIS {SITE_NO} {note}", asof=asof
        )

    return ContinuousMonitorRead(
        site_no=SITE_NO,
        site_name=SITE_NAME,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        discharge_min=connector(q_min, q_unit, q_min_t, "low-flow trough"),
        discharge_storm_peak=connector(q_peak, q_unit, q_peak_t, "storm peak"),
        seven_q10_cfs=seven_q10,
        low_flow_dilution_ratio=dilution,
        turbidity_baseline=ProvenancedValue.from_connector(
            baseline, turb.unit, citation=f"NWIS {SITE_NO} {TURBIDITY_FNU} median", asof=WINDOW_END
        ),
        turbidity_spikes=spikes,
        do_min=connector(do_v, by[DISSOLVED_OXYGEN_MG_L].unit, do_t, "DO sag (low-flow/thermal)"),
        water_temp_max=connector(temp_v, by[WATER_TEMP_C].unit, temp_t, "water-temp max"),
        conductance_storm_min=connector(cond_min, cond.unit, cond_min_t, "storm-dilution min"),
        conductance_low_flow_max=connector(cond_max, cond.unit, cond_max_t, "low-flow max"),
        phycocyanin_month_max=connector(fpc_max, fpc.unit, fpc_max_t, "fPC (32319) month max"),
        phycocyanin_at_turbidity_spike=connector(
            fpc_at_spike[1], fpc.unit, fpc_at_spike[0], "fPC (32319) at the turbidity spike"
        ),
        reach_river_km=ProvenancedValue.derived(reach_km, "km", citation=REACH_CITATION),
        plume_travel=ProvenancedValue.derived(
            round(travel_mid, 1),
            "hr",
            citation=VELOCITY_CITATION,
            low=round(travel_low, 1),
            high=round(travel_high, 1),
        ),
        release_start=release_start,
        spikes_precede_release=spikes_precede,
        attribution=attribution,
        caveats=caveats,
    )


def compute_monitor_read(*, settings: Settings | None = None) -> ContinuousMonitorRead:
    """Read the committed/live event record into a :class:`ContinuousMonitorRead`."""
    settings = settings or get_settings()
    series = load_event_series(settings=settings)
    seven_q10 = load_derived_low_flows(settings=settings).get("maumee river")
    if seven_q10 is None:
        raise ValueError(
            "no derived Maumee 7Q10 (run `watermark derive-low-flows`); needed as the dilution denominator"
        )
    return read_monitor(series, seven_q10=seven_q10)


def monitor_findings(read: ContinuousMonitorRead) -> list[HydroFinding]:
    """The headline findings, in the analyze-stage :class:`HydroFinding` shape."""
    spike_desc = ", ".join(
        f"{s.value:g} {s.unit} @ {s.timestamp[:16]}" for s in read.turbidity_spikes
    )
    return [
        HydroFinding(
            subject=read.site_name,
            check="attribution",
            ok=read.spikes_precede_release,
            detail=read.attribution,
        ),
        HydroFinding(
            subject=read.site_name,
            check="turbidity-spikes",
            ok=True,
            detail=f"baseline ~{read.turbidity_baseline.value:g} FNU; storm spikes {spike_desc}",
        ),
        HydroFinding(
            subject=read.site_name,
            check="low-flow-dilution",
            ok=read.low_flow_dilution_ratio >= 1.0,
            detail=(
                f"trough {read.discharge_min.value:g} cfs = {read.low_flow_dilution_ratio:g}x the "
                f"derived 7Q10 ({read.seven_q10_cfs.value:g} cfs) — tight initial-week denominator"
            ),
        ),
        HydroFinding(
            subject=read.site_name,
            check="do-sag-thermal",
            ok=True,
            detail=(
                f"DO sag {read.do_min.value:g} mg/L @ {(read.do_min.asof or '')[:10]} with water temp to "
                f"{read.water_temp_max.value:g} deg C — low-flow/thermal, PRE-dates the release"
            ),
        ),
    ]


def _pv_dict(pv: ProvenancedValue) -> dict[str, Any]:
    out: dict[str, Any] = {"value": pv.value, "unit": pv.unit, "source": pv.source}
    if pv.citation:
        out["citation"] = pv.citation
    if pv.asof:
        out["asof"] = pv.asof
    if pv.has_range:
        out["low"], out["high"] = pv.low, pv.high
    return out


def write_monitor_read(read: ContinuousMonitorRead, *, settings: Settings | None = None) -> Path:
    """Write the committed reference artifact; returns the path."""
    settings = settings or get_settings()
    path = _reference_dir(settings) / _FILENAME
    doc = {
        "meta": {
            "subject": "Maumee-at-Waterville (USGS 04193500) continuous monitor read vs the "
            "Napoleon / Huston Creek fertilizer spill (#1498, parent #1497)",
            "discipline": "Observational extrema are [verified] connector reads; the reach travel "
            "time and the plume-vs-first-flush attribution are [inference]. Optical/ionic "
            "surrogates are NOT a nitrogen measurement. Regenerate with "
            "`watermark waterville-monitor --write`.",
            "window": f"{read.window_start}..{read.window_end}",
            "raw_record_fixture": "tests/fixtures/hydrology/nwis/ (IV service retains only ~120 days)",
        },
        "site": {"site_no": read.site_no, "name": read.site_name},
        "discharge": {
            "low_flow_trough": _pv_dict(read.discharge_min),
            "storm_peak": _pv_dict(read.discharge_storm_peak),
            "derived_7q10": _pv_dict(read.seven_q10_cfs),
            "low_flow_dilution_ratio": read.low_flow_dilution_ratio,
        },
        "turbidity": {
            "baseline": _pv_dict(read.turbidity_baseline),
            "spikes": [
                {"timestamp": s.timestamp, "value": s.value, "unit": s.unit}
                for s in read.turbidity_spikes
            ],
        },
        "dissolved_oxygen": {
            "sag": _pv_dict(read.do_min),
            "water_temp_max": _pv_dict(read.water_temp_max),
        },
        "specific_conductance": {
            "storm_min": _pv_dict(read.conductance_storm_min),
            "low_flow_max": _pv_dict(read.conductance_low_flow_max),
        },
        "phycocyanin": {
            "month_max": _pv_dict(read.phycocyanin_month_max),
            "at_turbidity_spike": _pv_dict(read.phycocyanin_at_turbidity_spike),
        },
        "attribution": {
            "reach_river_km": _pv_dict(read.reach_river_km),
            "plume_travel_hours": _pv_dict(read.plume_travel),
            "release_start": read.release_start,
            "spikes_precede_release": read.spikes_precede_release,
            "verdict": read.attribution,
        },
        "caveats": read.caveats,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=100), encoding="utf-8")
    log.info("waterville_monitor.write", path=str(path))
    return path


def load_monitor_read(*, settings: Settings | None = None) -> ContinuousMonitorRead | None:
    """Reconstruct the read from the committed artifact (or ``None`` if absent)."""
    settings = settings or get_settings()
    path = _reference_dir(settings) / _FILENAME
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    def pv(d: dict[str, Any]) -> ProvenancedValue:
        return ProvenancedValue.model_validate(d)

    disc, turb = data["discharge"], data["turbidity"]
    do, cond = data["dissolved_oxygen"], data["specific_conductance"]
    fpc, attr = data["phycocyanin"], data["attribution"]
    return ContinuousMonitorRead(
        site_no=data["site"]["site_no"],
        site_name=data["site"]["name"],
        window_start=data["meta"]["window"].split("..")[0],
        window_end=data["meta"]["window"].split("..")[1],
        discharge_min=pv(disc["low_flow_trough"]),
        discharge_storm_peak=pv(disc["storm_peak"]),
        seven_q10_cfs=pv(disc["derived_7q10"]),
        low_flow_dilution_ratio=disc["low_flow_dilution_ratio"],
        turbidity_baseline=pv(turb["baseline"]),
        turbidity_spikes=[MonitorSpike.model_validate(s) for s in turb["spikes"]],
        do_min=pv(do["sag"]),
        water_temp_max=pv(do["water_temp_max"]),
        conductance_storm_min=pv(cond["storm_min"]),
        conductance_low_flow_max=pv(cond["low_flow_max"]),
        phycocyanin_month_max=pv(fpc["month_max"]),
        phycocyanin_at_turbidity_spike=pv(fpc["at_turbidity_spike"]),
        reach_river_km=pv(attr["reach_river_km"]),
        plume_travel=pv(attr["plume_travel_hours"]),
        release_start=attr["release_start"],
        spikes_precede_release=attr["spikes_precede_release"],
        attribution=attr["verdict"],
        caveats=data["caveats"],
    )
