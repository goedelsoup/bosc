"""Build EPA SWMM5 ``.inp`` models from our data.

Two models, both driven by the SCS Type-II design storm as a rainfall timeseries:

* :func:`stormwater_inp` — the campus subcatchment routed to an outfall, optionally
  through a detention basin (storage node + bottom orifice) for the post-development
  case. Sizing the orifice controls the released peak.
* :func:`sanitary_inp` — a sanitary junction carrying the dry-weather base flow plus
  rainfall-derived inflow & infiltration (RDII, an RTK unit hydrograph) to a WWTP
  outfall, for the wet-weather surcharge check.

Network and hydraulic parameters (widths, slopes, Manning's n, infiltration, RDII
R-T-K, basin geometry) are screening **assumptions** — we lack the as-built drainage
network. The footprint area and storm depth are document/connector-sourced.
"""

from __future__ import annotations

from dataclasses import dataclass

from watermark.hsg import is_dual_hsg, normalize_hsg
from watermark.hydrology import units
from watermark.hydrology.solver.rainfall import scs_type_ii_hyetograph

_SQFT_PER_ACRE = 43560.0


@dataclass(frozen=True)
class DetentionGeom:
    """Detention basin: a flat storage of ``area`` with a circular bottom orifice."""

    basin_area_ft2: float
    max_depth_ft: float
    orifice_diam_ft: float


def _hhmm(hours: float) -> str:
    total_min = round(hours * 60.0)
    return f"{total_min // 60:d}:{total_min % 60:02d}"


def _require_whole_minute_step(dt_hr: float) -> None:
    """Reject a time step SWMM's ``H:MM`` timestamps cannot express (see _hyetograph_lines)."""
    minutes = dt_hr * 60.0
    if dt_hr <= 0 or abs(minutes - round(minutes)) > 1e-9:
        raise ValueError(
            f"SWMM deck time step must be a positive whole number of minutes, got dt_hr={dt_hr!r} "
            f"({minutes:g} min) — SWMM timestamps are H:MM, so a fractional-minute step would "
            "collide successive rows onto the same label"
        )


def _hyetograph_lines(ts_name: str, depth_in: float, dt_hr: float) -> list[str]:
    """SWMM TIMESERIES lines of rainfall intensity (in/hr) for the design storm.

    Six decimals, not four: once the Type-II central burst is resolved at its published 6-minute
    intensity (#1610) rather than smeared across the hour, per-line rounding at 1e-4 in/hr leaks
    a visible fraction of the storm depth out of the deck.

    ``dt_hr`` must be a whole number of minutes. SWMM timestamps are ``H:MM``, so a fractional
    step (e.g. the 0.025 hr = 1.5 min the SCS unit-duration rule can produce for a fast catchment)
    would round successive rows onto colliding minute labels and silently mis-time the storm —
    a corrupt deck rather than a loud failure. Both public builders route through here.
    """
    _require_whole_minute_step(dt_hr)
    _, _, incremental = scs_type_ii_hyetograph(depth_in, dt_hr=dt_hr)
    lines = []
    for i, inc in enumerate(incremental.tolist()):
        intensity = inc / dt_hr  # in per hr over this interval
        lines.append(f"{ts_name}  {_hhmm(i * dt_hr)}  {intensity:.6f}")
    return lines


def _header(end_hr: float, dt_hr: float, *, infiltration: str = "HORTON") -> str:
    _require_whole_minute_step(dt_hr)  # the RAINGAGES interval is an H:MM label too
    rg_interval = _hhmm(dt_hr)
    return f"""[OPTIONS]
FLOW_UNITS           CFS
INFILTRATION         {infiltration}
FLOW_ROUTING         DYNWAVE
START_DATE           01/01/2026
START_TIME           00:00:00
END_DATE             01/0{1 + int(end_hr // 24)}/2026
END_TIME             {_hhmm(end_hr % 24)}:00
REPORT_STEP          00:05:00
WET_STEP             00:01:00
DRY_STEP             00:05:00
ROUTING_STEP         0:00:15
ALLOW_PONDING        YES

[EVAPORATION]
CONSTANT             0.0

[RAINGAGES]
RG1 INTENSITY {rg_interval} 1.0 TIMESERIES TS1
"""


# Horton infiltration by hydrologic soil group (max/min rate in/hr, decay 1/hr, dry
# days, max-vol). Assumption-grade screening values; the min (saturated) rate falls
# with the HSG. "C" keeps the legacy default string verbatim so existing decks are
# unchanged; a sourced HSG (watermark.hydrology.connectors.ssurgo) selects its infiltration.
_HORTON_BY_HSG = {
    "A": "3.0 0.45 4.0 7 0",
    "B": "3.0 0.30 4.0 7 0",
    "C": "3.0 0.1 4.0 7 0",
    "D": "3.0 0.05 4.0 7 0",
}


def _horton_for(hsg: str) -> str:
    """Horton infiltration string for a **resolved** single HSG; unrated falls back to "C".

    A dual group is refused, not sliced: ``B/D``'s two letters are the drained and undrained
    conditions of one soil, and their Horton rates differ 6-fold (0.30 vs 0.05 in/hr), so the
    deck's caller states the condition (:func:`watermark.hsg.resolve_hsg`) rather than
    inheriting the drained one by accident (WS-20 / #1620).
    """
    group = normalize_hsg(hsg)
    if is_dual_hsg(group):
        raise ValueError(
            f"SWMM infiltration needs a resolved hydrologic soil group, got the dual group "
            f"{hsg!r} — resolve it with watermark.hsg.resolve_hsg(group, condition) first"
        )
    return _HORTON_BY_HSG.get(group, _HORTON_BY_HSG["C"])


def stormwater_inp(
    *,
    area_acres: float,
    pct_imperv: float,
    depth_in: float,
    detention: DetentionGeom | None = None,
    dt_hr: float = 0.1,
    end_hr: float = 30.0,
    hsg: str = "C",
    pct_slope: float | None = None,
    s_perv_store_in: float = 0.05,
) -> tuple[str, str, str, str]:
    """Build a stormwater ``.inp``. Returns (text, outfall, orifice_link, storage_node).

    ``hsg`` selects the Horton infiltration (default "C" = the legacy assumption); pass a
    SSURGO-sourced group to ground the deck's soils — **resolved** to a single A-D letter for
    the scenario's drainage condition (``watermark.hsg.resolve_hsg``), since SSURGO's dual
    ratings carry two.

    ``pct_slope`` is the subcatchment surface slope (%). ``None`` keeps the generic ``1.0`` %
    screening default; pass a value derived from the graded rim relief (WS-25 / #1625) to ground
    it — a flat campus drains far slower than 1 % implies. ``s_perv_store_in`` is the pervious
    depression storage (in); the SWMM-manual range is ~0.1-0.3 in, so the ``0.05`` default is a
    conservative floor a grounded caller should raise (WS-25).
    """
    width = (area_acres * _SQFT_PER_ACRE) ** 0.5  # square-catchment width (ft)
    # Preserve the exact "1.0" literal for the generic default so an ungrounded deck is byte-stable.
    slope_str = "1.0" if pct_slope is None else f"{pct_slope:.3f}"
    outfall = "OUT1"
    storage = "DET"
    orifice = "OR1"
    drains_to = storage if detention else outfall

    inp = _header(end_hr, dt_hr)
    inp += f"""
[SUBCATCHMENTS]
S1 RG1 {drains_to} {area_acres:.2f} {pct_imperv:.1f} {width:.1f} {slope_str} 0

[SUBAREAS]
S1 0.015 0.10 0.05 {s_perv_store_in:g} 25 OUTLET

[INFILTRATION]
S1 {_horton_for(hsg)}

[OUTFALLS]
{outfall} 0 FREE NO
"""
    if detention:
        inp += f"""
[STORAGE]
{storage} 0 {detention.max_depth_ft:.1f} 0 FUNCTIONAL 0 0 {detention.basin_area_ft2:.1f}

[ORIFICES]
{orifice} {storage} {outfall} BOTTOM 0 0.65 NO

[XSECTIONS]
{orifice} CIRCULAR {detention.orifice_diam_ft:.3f} 0 0 0
"""
    inp += "\n[TIMESERIES]\n" + "\n".join(_hyetograph_lines("TS1", depth_in, dt_hr)) + "\n"
    inp += "\n[REPORT]\nINPUT NO\nNODES ALL\nLINKS ALL\n"
    return inp, outfall, orifice, storage


def sanitary_inp(
    *,
    base_mgd: float,
    sewershed_acres: float,
    rdii_r: float,
    depth_in: float,
    dt_hr: float = 0.1,
    end_hr: float = 36.0,
) -> tuple[str, str]:
    """Build a sanitary ``.inp`` with DWF + RDII. Returns (text, wwtp_outfall)."""
    base_cfs = units.mgd_to_cfs(base_mgd)
    wwtp = "WWTP"
    junction = "J1"

    inp = _header(end_hr, dt_hr)
    inp += f"""
[JUNCTIONS]
{junction} 0 10 0 0 0

[OUTFALLS]
{wwtp} 0 FREE NO

[CONDUITS]
C1 {junction} {wwtp} 200 0.013 0 0 0 0

[XSECTIONS]
C1 CIRCULAR 6.5 0 0 0

[DWF]
{junction} FLOW {base_cfs:.4f}

[HYDROGRAPHS]
UH1 RG1
UH1 All SHORT {rdii_r:.3f} 1.0 2.0
UH1 All MEDIUM {rdii_r / 2:.3f} 3.0 2.0

[RDII]
{junction} UH1 {sewershed_acres:.2f}
"""
    inp += "\n[TIMESERIES]\n" + "\n".join(_hyetograph_lines("TS1", depth_in, dt_hr)) + "\n"
    inp += "\n[REPORT]\nINPUT NO\nNODES ALL\nLINKS ALL\n"
    return inp, wwtp
