"""Route design-storm hydrographs down the cited confluence graph (#1184).

The time-varying counterpart to :mod:`watermark.hydrology.network` (which routes the loop
as a *steady-state scalar* low-flow mass balance). This gives the Muskingum-Cunge primitive
in :mod:`watermark.hydrology.solver.routing` its production caller: it generates an SCS
design-storm runoff hydrograph at each contributing subcatchment, routes each one downstream
through its trapezoidal reach — attenuating and lagging the peak — and superposes them at
confluences, so the outlet peak is the *routed* peak, **not the arithmetic sum** of the
tributary peaks.

It reads two committed, provenance-tagged inputs:

* the magnitude-free confluence topology (``network.yaml`` -> :func:`network.load_topology`),
* the reach geometry + contributing subcatchments (``reaches.yaml`` -> :func:`load_reaches`).

The headline is the routed outlet hydrograph vs. the naive **summed** hydrograph (the local
subcatchment inflows superposed with no channel routing): ``peak_attenuation_pct`` and
``lag_hr`` quantify what routing buys over the sum. Tier-0 screening — not HEC-HMS/HEC-RAS.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

import numpy as np
import yaml
from numpy.typing import NDArray

from watermark.config import Settings, get_settings
from watermark.hydrology import network, stormwater
from watermark.hydrology.model import (
    HydroFinding,
    NetworkNode,
    Reach,
    ReachRouting,
    ReachTable,
    RoutedHydrographNetwork,
)
from watermark.hydrology.solver.routing import route_reach
from watermark.hydrology.solver.runoff import simulate_runoff
from watermark.logging import get_logger

log = get_logger(__name__)

_DEFAULT_DT_HR = 0.1
_DEFAULT_DURATION_HR = 24.0
# Extra zero-padded tail (hr) so a reach's lag never clips the routed peak off the horizon.
_ROUTING_HEADROOM_HR = 24.0


def _reaches_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "reaches.yaml"


def load_reaches(*, settings: Settings | None = None) -> ReachTable | None:
    """Load the committed reach geometry + subcatchments, or ``None`` if the file is absent."""
    settings = settings or get_settings()
    path = _reaches_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ReachTable.model_validate(
        {"catchments": data.get("catchments") or {}, "reaches": data.get("reaches") or {}}
    )


class _ReachGeometry(TypedDict, total=False):
    """The trapezoid overrides a reach may carry (a precise kwargs type so unpacking into
    ``route_reach`` can't be confused with its ``subreaches`` control knob)."""

    bottom_width_ft: float
    side_slope_z: float
    manning_n: float


def _geometry_kwargs(reach: Reach) -> _ReachGeometry:
    """The optional trapezoid overrides present on a reach (the rest fall back to ``route``)."""
    kw: _ReachGeometry = {}
    if reach.bottom_width_ft is not None:
        kw["bottom_width_ft"] = reach.bottom_width_ft.value
    if reach.side_slope_z is not None:
        kw["side_slope_z"] = reach.side_slope_z.value
    if reach.manning_n is not None:
        kw["manning_n"] = reach.manning_n.value
    return kw


def _peak(series: NDArray[np.float64], times: NDArray[np.float64]) -> tuple[float, float]:
    """``(peak_cfs, time_to_peak_hr)`` of a hydrograph series (``(0.0, 0.0)`` if empty/flat)."""
    if series.size == 0 or float(series.max()) <= 0.0:
        return 0.0, 0.0
    idx = int(np.argmax(series))
    return float(series[idx]), float(times[idx])


def route_storm_network(
    nodes: list[NetworkNode],
    table: ReachTable,
    *,
    return_period_yr: int,
    storm_depth_in: float,
    site_label: str = "",
    dt_hr: float = _DEFAULT_DT_HR,
    duration_hr: float = _DEFAULT_DURATION_HR,
) -> RoutedHydrographNetwork:
    """Route one design storm's hydrographs down the topology and superpose at confluences (pure).

    ``nodes`` is the cited confluence graph; ``table`` supplies each contributing node's
    subcatchment and each reach's channel geometry. ``site_label`` names the loop for the
    finding/CLI headline (e.g. the active site's place); it is carried on the result. All series
    share one time grid (padded with a routing-headroom tail so a lagged peak is never clipped).
    Returns the routed outlet hydrograph, the naive summed (un-routed) hydrograph, and per-reach
    attenuation/lag.
    """
    warnings: list[str] = []

    # 1. Local design-storm inflow at each contributing (catchment) node, on a shared horizon.
    local: dict[str, NDArray[np.float64]] = {}
    base_len = 0
    for node in nodes:
        catch = table.catchments.get(node.id)
        if catch is None:
            continue
        hg = simulate_runoff(
            area_acres=catch.area_acres.value,
            curve_number=catch.curve_number.value,
            tc_hr=catch.tc_hr.value,
            storm_depth_in=storm_depth_in,
            dt_hr=dt_hr,
            duration_hr=duration_hr,
        )
        local[node.id] = np.asarray(hg.flows_cfs, dtype=np.float64)
        base_len = max(base_len, local[node.id].size)

    # Report typo'd reaches.yaml keys (both blocks) instead of silently ignoring them: a
    # catchment/reach keyed to a non-existent node contributes nothing and is a data error.
    node_ids = {n.id for n in nodes}
    for cid in table.catchments:
        if cid not in node_ids:
            warnings.append(f"reaches.yaml catchment {cid!r} is not a node in network.yaml")
    for rid in table.reaches:
        if rid not in node_ids:
            warnings.append(f"reaches.yaml reach {rid!r} is not a node in network.yaml")

    if base_len == 0:
        warnings.append("no contributing subcatchments resolved; nothing to route")
        return _empty_network(return_period_yr, storm_depth_in, dt_hr, warnings)

    horizon = base_len + round(_ROUTING_HEADROOM_HR / dt_hr)
    times = np.arange(1, horizon + 1, dtype=np.float64) * dt_hr
    local = {nid: _pad(series, horizon) for nid, series in local.items()}

    # 2. Accumulate downstream: each node's inflow = its local runoff + its upstream reaches'
    #    routed outflow; route that inflow through the node's own reach to its downstream node.
    upstream: dict[str, list[str]] = {n.id: [] for n in nodes}
    for n in nodes:
        if n.downstream is not None and n.downstream in upstream:
            upstream[n.downstream].append(n.id)

    order = network.toposort(nodes)  # computed once; reused for the outlet fallback below
    node_inflow: dict[str, NDArray[np.float64]] = {}
    node_outflow: dict[str, NDArray[np.float64]] = {}
    reach_results: list[ReachRouting] = []
    for node in order:
        inflow = np.zeros(horizon, dtype=np.float64)
        for u in upstream[node.id]:
            inflow = inflow + node_outflow[u]
        if node.id in local:
            inflow = inflow + local[node.id]
        node_inflow[node.id] = inflow

        reach = table.reaches.get(node.id)
        if reach is None:
            node_outflow[node.id] = inflow  # pass-through (outfall at a confluence, or the outlet)
            if node.downstream is not None and node.kind not in ("outfall", "outlet"):
                warnings.append(f"node {node.id!r} has no reach geometry; routed as pass-through")
            continue
        rr = route_reach(
            inflow,
            length_ft=reach.length_ft.value,
            slope=reach.slope.value,
            dt_hr=dt_hr,
            **_geometry_kwargs(reach),
        )
        outflow = rr.outflow_cfs
        node_outflow[node.id] = outflow
        in_peak, in_ttp = _peak(inflow, times)
        out_peak, out_ttp = _peak(outflow, times)
        reach_results.append(
            ReachRouting(
                node_id=node.id,
                name=node.name,
                length_ft=reach.length_ft.value,
                slope=reach.slope.value,
                inflow_peak_cfs=round(in_peak, 3),
                inflow_time_to_peak_hr=round(in_ttp, 3),
                outflow_peak_cfs=round(out_peak, 3),
                outflow_time_to_peak_hr=round(out_ttp, 3),
                attenuation_pct=round(100.0 * (in_peak - out_peak) / in_peak, 2)
                if in_peak
                else 0.0,
                lag_hr=round(out_ttp - in_ttp, 3),
                subreaches=rr.subreaches,
                courant=round(rr.courant, 3),
            )
        )
        # Validity flag (WS-09 / #1609): a reach shorter than one c·Δt step can't be subdivided
        # to Courant≈1 (n stays 1, Cr>1), so its single Muskingum step is under-resolved in time
        # — routed as near-translation, not a numerical failure, but flagged as soft.
        if rr.subreaches == 1 and rr.courant > 2.0:
            warnings.append(
                f"reach {node.id!r} is short relative to the routing step (Courant "
                f"{rr.courant:.2f}); routed as a single near-translation step, soft — a "
                "finer dt would resolve it"
            )

    # 3. Routed outlet hydrograph vs. the naive summed (un-routed) local inflows.
    outlet_id = next((n.id for n in nodes if n.kind == "outlet"), None)
    if outlet_id is None:
        warnings.append("no outlet node in topology; using the last toposorted node as the outlet")
        outlet_id = order[-1].id
    routed = node_inflow[outlet_id]
    summed = np.zeros(horizon, dtype=np.float64)
    for series in local.values():
        summed = summed + series

    routed_peak, routed_ttp = _peak(routed, times)
    summed_peak, summed_ttp = _peak(summed, times)
    atten = round(100.0 * (summed_peak - routed_peak) / summed_peak, 2) if summed_peak else 0.0

    rn = RoutedHydrographNetwork(
        site=site_label,
        return_period_yr=return_period_yr,
        storm_depth_in=round(storm_depth_in, 3),
        dt_hr=dt_hr,
        times_hr=[round(t, 4) for t in times.tolist()],
        outlet_hydrograph_cfs=[round(q, 3) for q in routed.tolist()],
        summed_hydrograph_cfs=[round(q, 3) for q in summed.tolist()],
        routed_peak_cfs=round(routed_peak, 3),
        summed_peak_cfs=round(summed_peak, 3),
        peak_attenuation_pct=atten,
        routed_time_to_peak_hr=round(routed_ttp, 3),
        summed_time_to_peak_hr=round(summed_ttp, 3),
        lag_hr=round(routed_ttp - summed_ttp, 3),
        reaches=reach_results,
        warnings=warnings,
    )
    log.info(
        "hydro.hydrograph_route",
        return_period=return_period_yr,
        routed_peak=rn.routed_peak_cfs,
        summed_peak=rn.summed_peak_cfs,
        attenuation_pct=rn.peak_attenuation_pct,
        lag_hr=rn.lag_hr,
    )
    return rn


def _pad(series: NDArray[np.float64], length: int) -> NDArray[np.float64]:
    """Right-pad a hydrograph series with trailing zeros (its flow has returned to baseline)."""
    if series.size >= length:
        return series[:length]
    out = np.zeros(length, dtype=np.float64)
    out[: series.size] = series
    return out


def _empty_network(
    return_period_yr: int, storm_depth_in: float, dt_hr: float, warnings: list[str]
) -> RoutedHydrographNetwork:
    return RoutedHydrographNetwork(
        return_period_yr=return_period_yr,
        storm_depth_in=round(storm_depth_in, 3),
        dt_hr=dt_hr,
        times_hr=[],
        outlet_hydrograph_cfs=[],
        summed_hydrograph_cfs=[],
        routed_peak_cfs=0.0,
        summed_peak_cfs=0.0,
        peak_attenuation_pct=0.0,
        routed_time_to_peak_hr=0.0,
        summed_time_to_peak_hr=0.0,
        lag_hr=0.0,
        reaches=[],
        warnings=warnings,
    )


def build_routed_hydrograph(
    *,
    return_period_yr: int = 25,
    settings: Settings | None = None,
    live: bool = False,
) -> RoutedHydrographNetwork | None:
    """Route the committed loop for one design storm (the offline/hermetic feed producer).

    Loads the cited topology + reach table, resolves the design-storm depth via the
    offline-aware :func:`watermark.hydrology.stormwater._resolve_storm` (same NOAA Atlas-14
    corridor-point depth the campus storm chain uses), and routes. Returns ``None`` if either
    committed input is absent, so ``watermark export`` skips the feed rather than fabricating one.
    """
    from watermark.sites import active_profile

    settings = settings or get_settings()
    nodes = network.load_topology(settings=settings)
    table = load_reaches(settings=settings)
    if not nodes or table is None:
        log.info("hydro.hydrograph_route.absent", nodes=len(nodes), reaches=table is not None)
        return None
    storm = stormwater._resolve_storm(return_period_yr, settings=settings, live=live)
    return route_storm_network(
        nodes,
        table,
        return_period_yr=return_period_yr,
        storm_depth_in=storm.depth.value,
        site_label=active_profile(settings).place,
    )


_ARTIFACT_REL = ("reference", "hydrology", "routed-hydrograph.yaml")


def write_routed_hydrograph(
    rn: RoutedHydrographNetwork, *, settings: Settings | None = None
) -> Path:
    """Persist the inspectable routed-hydrograph summary and return its path.

    Writes the headline + per-reach attenuation/lag table, but **omits the two long
    per-timestep series** (they'd be ~1500 lines of derived numbers) — those ship in the site
    bundle's ``routed-hydrograph`` feed, and the whole result regenerates deterministically
    offline via ``watermark basin-route``. A committed reference doc, not a typed pipeline input.
    """
    settings = settings or get_settings()
    path = settings.data_dir.joinpath(*_ARTIFACT_REL)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = rn.model_dump(exclude={"times_hr", "outlet_hydrograph_cfs", "summed_hydrograph_cfs"})
    doc["series_note"] = (
        f"{len(rn.times_hr)} timesteps at dt={rn.dt_hr} hr omitted here; the full outlet + "
        "summed series ship in the site bundle's routed-hydrograph feed. Regenerate with "
        "`watermark basin-route --write`."
    )
    path.write_text(
        yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    log.info("hydro.hydrograph_route.wrote", path=str(path))
    return path


def hydrograph_findings(rn: RoutedHydrographNetwork) -> list[HydroFinding]:
    """The routing headline as an evidence-tagged finding: attenuation + lag over the naive sum."""
    if not rn.reaches:
        return []
    loop = f"{rn.site} loop" if rn.site else "The loop"
    return [
        HydroFinding(
            subject=f"{loop} design-storm peak at the outlet",
            check="routed-vs-summed-peak",
            ok=rn.peak_attenuation_pct >= 0.0,
            detail=(
                f"routing the {rn.return_period_yr}-yr storm down the cited confluence graph "
                f"attenuates the outlet peak from Σ{rn.summed_peak_cfs:,.0f} cfs (naive sum of "
                f"subcatchment hydrographs) to {rn.routed_peak_cfs:,.0f} cfs "
                f"({rn.peak_attenuation_pct:g}% lower) and lags it {rn.lag_hr:g} hr — "
                "the peak a downstream reach sees is attenuated and delayed, not summed"
            ),
        )
    ]
