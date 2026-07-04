"""Assemble the municipal water-balance loop from cited records + live gauges.

The spine is the four county/Lima WWTP discharges (document-sourced design flows
from ``watch-items.geojson``), each routed to its cited receiving water. The
forcing function — the BOSC data-center campus — contributes its documented FM-2
discharge plus a *derived* consumptive cooling loss (the sourced power-based central
from ``watermark.hydrology.cooling``). The abstraction end is grounded with *live* NWIS
river flow when available.

Everything the headline assimilative check depends on (WWTP discharge -> named
receiving water) is ``document``-sourced; the abstraction/demand context is clearly
``connector``/``assumption``-tagged so it never masquerades as fact.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors.nwis import DISCHARGE_CFS, fetch_streamflow
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.model import Node, ProvenancedValue, WaterBalance, WaterBalanceNode
from watermark.hydrology.routing import RoutingTable, load_routing
from watermark.hydrology.units import mgd_to_cfs
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# The per-plant fallback receiving waters (from the active SiteProfile.plant_receiving,
# sourced from the Ohio EPA NPDES fact sheets in our corpus) and the abstraction/dilution
# gauge (SiteProfile.abstraction_gage) are per-site. The fallback is consulted only when
# data/reference/hydrology/routing.yaml is absent, so the balance never breaks during rollout.

_MGD_RE = re.compile(r"(\d+(?:\.\d+)?)\s*MGD", re.IGNORECASE)


def _features(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", []) if isinstance(data, dict) else []


def _default_watch_items(settings: Settings) -> Path:
    # Per-site override: data/reference/<slug>/watch-items.geojson takes precedence so
    # non-Lima sites can carry their own WWTP/infrastructure geometry without touching
    # the frozen Lima periplus import.
    site_path = settings.data_dir / "reference" / settings.site / "watch-items.geojson"
    if site_path.exists():
        return site_path
    return settings.data_dir / "reference" / "periplus" / "watch-items.geojson"


def _design_mgd(summary: str) -> tuple[float | None, bool]:
    """First design flow (MGD) stated in a summary; flag if more than one (expansion)."""
    found = [float(m) for m in _MGD_RE.findall(summary)]
    if not found:
        return None, False
    return found[0], len(found) > 1


def _receiving_for(
    fid: str, routing: RoutingTable | None, *, settings: Settings
) -> tuple[str | None, str]:
    """Resolve a WWTP's receiving water from the routing table, falling back to the profile."""
    if routing is not None and fid in routing.wwtp_receiving:
        return routing.receiving_for(fid)
    return active_profile(settings).plant_receiving.get(fid, (None, ""))


def _surface_bosc_routing(routing: RoutingTable | None, warnings: list[str]) -> None:
    """Record where BOSC's wastewater goes — and flag theorized routes as excluded.

    Encodes the standing requirement: BOSC output is routed to Lima (FM-2) and the
    American plants (FM-1) only; Shawnee II's FM-3 is theorized and held out of the
    balance, so its lack of a known route is explicit rather than silently assumed.
    """
    if routing is None:
        return
    for route in routing.confirmed_bosc_routes():
        log.info("hydro.bosc_routing.confirmed", via=route.via, to=route.to)
    for route in routing.theorized_bosc_routes():
        warnings.append(
            f"BOSC routing via {route.via} to {', '.join(route.to)} is THEORIZED "
            "(unconfirmed) — excluded from the balance; Shawnee II has no known BOSC routing."
        )


def _wwtp_nodes(
    path: Path, warnings: list[str], routing: RoutingTable | None, *, settings: Settings
) -> list[WaterBalanceNode]:
    nodes: list[WaterBalanceNode] = []
    for feat in _features(path):
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        fid = str(props.get("id", ""))
        title = str(props.get("title", ""))
        is_wwtp = props.get("status") == "bosc_fm1_receiver" or title.endswith("WWTP")
        if not is_wwtp or geom.get("type") != "Point":
            continue

        receiving, recv_cite = _receiving_for(fid, routing, settings=settings)
        mgd, expanding = _design_mgd(str(props.get("summary", "")))
        lon, lat = geom["coordinates"][0], geom["coordinates"][1]
        node = Node(
            id=fid or title,
            name=title,
            role="wwtp",
            receiving_water=receiving,
            lat=float(lat),
            lon=float(lon),
        )
        return_flow = None
        if mgd is not None:
            return_flow = ProvenancedValue.from_document(
                mgd_to_cfs(mgd),
                "cfs",
                citation=f"{fid} ({mgd} MGD design)",
            )
            if expanding:
                warnings.append(
                    f"{title}: summary states a flow expansion; used the first value ({mgd} MGD)."
                )
        else:
            warnings.append(f"{title}: no design flow found in watch-items summary.")
        if receiving is None:
            warnings.append(
                f"{title}: receiving water not mapped; assimilative check will skip it."
            )
        else:
            log.info("hydro.wwtp", plant=title, receiving=receiving, citation=recv_cite)
        nodes.append(WaterBalanceNode(node=node, return_flow=return_flow))
    return nodes


def _campus_node(path: Path, warnings: list[str], *, settings: Settings) -> WaterBalanceNode:
    """The BOSC data-center campus: documented FM-2 discharge + a derived cooling loss."""
    fm2_mgd: float | None = None
    for feat in _features(path):
        props = feat.get("properties") or {}
        if props.get("id") == "bosc-fm2":
            fm2_mgd, _ = _design_mgd(str(props.get("summary", "")))
            break

    return_flow = None
    if fm2_mgd is not None:
        return_flow = ProvenancedValue.from_document(
            mgd_to_cfs(fm2_mgd),
            "cfs",
            citation=f"bosc-fm2 ({fm2_mgd} MGD industrial discharge to Lima)",
        )
    else:
        warnings.append("BOSC campus: FM-2 discharge not found in watch-items.")

    # Cooling consumptive loss isn't metered, but the design basis is now sourced:
    # derive_cooling_basis() brackets the evaporative consumptive draw from the disclosed
    # air-permit power figure (x WUE) and the documented FM-2 blowdown. Carry the
    # central (power x WUE) estimate as the campus's projected consumptive (net basin)
    # loss — `derived`, not a 0 placeholder. The scenario layer (`watermark scenario`)
    # re-derives baseline-vs-buildout and can override via `--cooling-demand`.
    basis = derive_cooling_basis(settings)
    low, high = basis.consumptive_low.value, basis.consumptive_high.value
    node = Node(id="bosc-campus", name="BOSC data-center campus", role="demand")

    # Honesty guard (CLAUDE.md): an undisclosed cooling method is a bracket, never a
    # single headline. `headline_consumptive()` returns None for the `unknown` archetype
    # — carry no scalar consumptive into the balance and let the presentation tier render
    # the range, rather than leaking the evaporative envelope as a headline.
    headline = basis.headline_consumptive()
    if headline is None:
        warnings.append(
            f"BOSC campus cooling method is undisclosed ({basis.cooling_model.value}): "
            f"consumptive is a bracket ({low:g}-{high:g} MGD), not a single estimate — no "
            "headline consumptive is carried into the balance; the range is rendered instead."
        )
        return WaterBalanceNode(node=node, return_flow=return_flow, consumptive_use=None)

    loss_cfs = mgd_to_cfs(headline.value)
    wue_txt = f" x {basis.wue.value:g} L/kWh" if basis.wue is not None else ""
    consumptive = ProvenancedValue.derived(
        round(loss_cfs, 3),
        "cfs",
        citation=(
            f"derived cooling basis ({basis.cooling_model.value}): {headline.value:g} MGD "
            f"central consumptive (range {low:g}-{high:g} MGD), {basis.it_load.value:g} MW "
            f"IT{wue_txt} — see watermark.hydrology.cooling"
        ),
    )
    warnings.append(
        f"BOSC campus consumptive cooling is a derived central estimate (~{loss_cfs:.1f} cfs; "
        f"{low:g}-{high:g} MGD evaporative range) from the air-permit power figure x WUE — not "
        f"a metered or permitted value."
    )
    return WaterBalanceNode(node=node, return_flow=return_flow, consumptive_use=consumptive)


def _abstraction_node(settings: Settings, warnings: list[str]) -> WaterBalanceNode | None:
    """The municipal WTP intake reach, grounded with live streamflow when available.

    Per-site (#1159): the intake node identity (id/name/river) and the abstraction gage come
    from the active ``SiteProfile``. A site with no configured intake node
    (``abstraction_node_id`` empty) yields ``None`` — the balance omits the abstraction reach
    rather than labeling another site's gage as Lima's WTP.
    """
    prof = active_profile(settings)
    if not prof.abstraction_node_id:
        warnings.append(
            f"no abstraction node configured for site {settings.site!r}; "
            "the water balance omits the intake reach."
        )
        return None
    node = Node(
        id=prof.abstraction_node_id,
        name=prof.abstraction_node_name,
        role="abstraction",
        receiving_water=prof.abstraction_river or None,
    )
    inflow: ProvenancedValue | None = None
    try:
        readings = fetch_streamflow(sites=[prof.abstraction_gage], settings=settings)
        flow = next(
            (r for r in readings if r.parameter_cd == DISCHARGE_CFS and r.value is not None),
            None,
        )
        if flow is not None and flow.value is not None:
            inflow = ProvenancedValue.from_connector(
                flow.value, "cfs", citation=f"NWIS {flow.site_no} ({flow.name})", asof=flow.datetime
            )
    except Exception as exc:
        warnings.append(
            f"live {prof.abstraction_river or 'river'} streamflow unavailable: {type(exc).__name__}"
        )
    warnings.append(
        f"{prof.abstraction_node_name} withdrawal rate is not documented; "
        "abstraction shown as river-flow context only."
    )
    return WaterBalanceNode(node=node, inflow=inflow)


def build_water_balance(
    *,
    settings: Settings | None = None,
    watch_items_path: Path | None = None,
    live: bool = True,
) -> WaterBalance:
    """Assemble the source -> use -> WWTP -> receiving loop.

    ``live=False`` skips the NWIS abstraction grounding (a pure document/assumption
    balance); ``live=True`` adds the gauge reading (offline-aware via the cache).
    """
    settings = settings or get_settings()
    path = watch_items_path or _default_watch_items(settings)
    warnings: list[str] = []

    routing = load_routing(settings=settings)
    nodes = _wwtp_nodes(path, warnings, routing, settings=settings)
    _surface_bosc_routing(routing, warnings)
    nodes.append(_campus_node(path, warnings, settings=settings))
    if live:
        abstraction = _abstraction_node(settings, warnings)
        if abstraction is not None:
            nodes.append(abstraction)

    log.info("hydro.balance", nodes=len(nodes), wwtp=sum(1 for n in nodes if n.node.role == "wwtp"))
    return WaterBalance(nodes=nodes, warnings=warnings)
