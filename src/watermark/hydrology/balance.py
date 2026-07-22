"""Assemble the municipal water-balance loop from cited records + live gauges.

The spine is the four county/Lima WWTP discharges — each plant's permitted design flow
read from the structured, document-cited ``design_flow_mgd`` in ``routing.yaml`` (the
``watch-items.geojson`` summary prose is only a logged fallback; WS-22, issue 1622) —
routed to its cited receiving water. The forcing function — the BOSC data-center campus —
contributes its documented FM-2 discharge plus a *derived* consumptive cooling loss (the
sourced power-based central from ``watermark.hydrology.cooling``). The abstraction end is
grounded with *live* NWIS river flow when available.

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
from watermark.sites import active_profile, is_reference_site

log = get_logger(__name__)

# The per-plant fallback receiving waters (from the active SiteProfile.plant_receiving,
# sourced from the Ohio EPA NPDES fact sheets in our corpus) and the abstraction/dilution
# gauge (SiteProfile.abstraction_gage) are per-site. The fallback is consulted only when
# data/reference/hydrology/routing.yaml is absent, so the balance never breaks during rollout.

# Fallback only: the first "N MGD" token in a feature summary. Load-bearing design flows
# are read from the structured `design_flow_mgd` in routing.yaml (WS-22, issue 1622); this
# regex over prose is a logged last resort for a site that hasn't curated the structured value.
# The optional leading "~" is captured so an approximate transcription (``~2.5 MGD``, the
# repo's approximate-number convention) keeps its provenance instead of being read as exact.
_MGD_RE = re.compile(r"(~)?\s*(\d+(?:\.\d+)?)\s*MGD", re.IGNORECASE)


def _features(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("features", []) if isinstance(data, dict) else []


def _site_watch_items_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / settings.site / "watch-items.geojson"


def has_site_watch_items(settings: Settings) -> bool:
    """True iff the active site has committed its own WWTP graph (``watch-items.geojson``).

    The balance falls back to Lima's periplus graph when a site has none
    (:func:`_default_watch_items`); the agent tool consults this to refuse rather than
    silently serve Lima's WWTPs for a site that hasn't committed its own (#829).
    """
    return _site_watch_items_path(settings).is_file()


def _default_watch_items(settings: Settings) -> Path:
    # Per-site override: data/reference/<slug>/watch-items.geojson takes precedence so
    # non-Lima sites can carry their own WWTP/infrastructure geometry without touching
    # the frozen Lima periplus import.
    site_path = _site_watch_items_path(settings)
    if site_path.exists():
        return site_path
    return settings.data_dir / "reference" / "periplus" / "watch-items.geojson"


def _design_mgd(
    structured: float | None, summary: str, *, subject: str
) -> tuple[float | None, bool, bool]:
    """Resolve a feature's design flow (MGD), preferring the structured, curated value.

    ``structured`` is the ``design_flow_mgd`` read from the routing table — the structured,
    document-cited source (the analog of the ECHO ``CWPTotalDesignFlowNmbr`` column). When it
    is present it wins and no prose heuristic runs. Only when it is absent do we fall back to
    the first ``N MGD`` token in the prose ``summary``, logging the fallback so a load-bearing
    number sourced by regex-over-prose is never silent.

    Returns ``(mgd, expanding, approximate)``: ``expanding`` (multiple MGD figures in the
    summary, e.g. an expansion) and ``approximate`` (the matched token carried the repo's
    ``~`` marker, so the value is a transcription estimate) are both fallback-only signals —
    a curated structured value is exact and non-expanding by construction.
    """
    if structured is not None:
        return structured, False, False
    matches = list(_MGD_RE.finditer(summary))
    if not matches:
        return None, False, False
    first = matches[0]
    approximate = bool(first.group(1))  # the "~" prefix, preserved rather than silently dropped
    mgd = float(first.group(2))
    log.info(
        "hydro.design_flow.regex_fallback",
        subject=subject,
        mgd=mgd,
        matches=len(matches),
        approximate=approximate,
    )
    return mgd, len(matches) > 1, approximate


def _design_flow_citation(base: str, structured_cite: str | None) -> str:
    """Compose the design-flow evidence citation.

    Appends the authoritative source — the routing table's Ohio EPA NPDES record — when the
    value came from the structured field, so the ``document`` evidence record names the real
    source instead of only the generic watch-item id (WS-22, issue 1622). A prose-fallback
    value (``structured_cite is None``) keeps just the watch-item base label.
    """
    return f"{base} — {structured_cite}" if structured_cite is not None else base


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
        structured_mgd, structured_cite = (
            routing.design_flow_for(fid) if routing is not None else (None, None)
        )
        mgd, expanding, approximate = _design_mgd(
            structured_mgd, str(props.get("summary", "")), subject=title or fid
        )
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
            marker = "~" if approximate else ""
            return_flow = ProvenancedValue.from_document(
                mgd_to_cfs(mgd),
                "cfs",
                citation=_design_flow_citation(
                    f"{fid} ({marker}{mgd} MGD design)", structured_cite
                ),
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


# The static prefix of the campus derived-cooling caveat. A no-cooling scenario (baseline)
# zeroes the campus draw, so the scenario layer drops this warning by prefix (`scenario.py`).
CAMPUS_COOLING_DERIVED_WARNING_PREFIX = (
    "BOSC campus consumptive cooling is a derived central estimate"
)


def _campus_node(
    path: Path, warnings: list[str], routing: RoutingTable | None, *, settings: Settings
) -> WaterBalanceNode | None:
    """The BOSC data-center campus: documented FM-2 discharge + a derived cooling loss.

    Gated on a committed campus-discharge feature (``bosc-fm2``) in the site's
    watch-items: a site that has not committed a data-center forcemain discharge carries
    no campus forcing node (``None``) rather than fabricating one from the facility alone
    (#829) — the balance stays the municipal WWTP loop + assimilative screen.
    """
    fm2_feat = next(
        (f for f in _features(path) if (f.get("properties") or {}).get("id") == "bosc-fm2"),
        None,
    )
    if fm2_feat is None:
        # The corpus home (Lima) is expected to model the BOSC campus discharge, so a
        # missing FM-2 feature is a data-integrity warning, not a silent drop; a peer that
        # models no BOSC campus simply carries no campus forcing node (#829).
        if is_reference_site(settings.site):
            warnings.append("BOSC campus: FM-2 discharge not found in watch-items.")
        return None
    structured_fm2, structured_fm2_cite = (
        routing.forcemain_design_flow("bosc-fm2") if routing is not None else (None, None)
    )
    fm2_mgd, _expanding, fm2_approx = _design_mgd(
        structured_fm2,
        str((fm2_feat.get("properties") or {}).get("summary", "")),
        subject="bosc-fm2",
    )

    return_flow = None
    if fm2_mgd is not None:
        marker = "~" if fm2_approx else ""
        return_flow = ProvenancedValue.from_document(
            mgd_to_cfs(fm2_mgd),
            "cfs",
            citation=_design_flow_citation(
                f"bosc-fm2 ({marker}{fm2_mgd} MGD industrial discharge to Lima)",
                structured_fm2_cite,
            ),
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
        f"{CAMPUS_COOLING_DERIVED_WARNING_PREFIX} (~{loss_cfs:.1f} cfs; "
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
            # A real-time IV reading NWIS flags provisional ("P") is unreviewed and subject
            # to revision — down-weight it so the balance never treats it as authoritative
            # as an approved value (#1602).
            inflow = ProvenancedValue.from_connector(
                flow.value,
                "cfs",
                citation=f"NWIS {flow.site_no} ({flow.name})",
                asof=flow.datetime,
                confidence="low" if flow.provisional else "high",
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
    campus = _campus_node(path, warnings, routing, settings=settings)
    if campus is not None:
        nodes.append(campus)
    if live:
        abstraction = _abstraction_node(settings, warnings)
        if abstraction is not None:
            nodes.append(abstraction)

    log.info("hydro.balance", nodes=len(nodes), wwtp=sum(1 for n in nodes if n.node.role == "wwtp"))
    return WaterBalance(nodes=nodes, warnings=warnings)
