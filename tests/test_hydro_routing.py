"""Data-driven discharge routing: the committed table loads, and Shawnee II's BOSC
route is theorized (held out of the balance) while the American/Lima routes are
confirmed — encoding 'BOSC output to Lima + American only; Shawnee II unrouted'.
"""

from __future__ import annotations

from watermark.config import Settings
from watermark.hydrology.balance import build_water_balance
from watermark.hydrology.routing import load_routing


def test_routing_table_loads(hydro_settings: Settings) -> None:
    routing = load_routing(settings=hydro_settings)
    assert routing is not None, "committed routing.yaml should load"
    # WWTP -> stream routes match the cited fact sheets.
    assert routing.receiving_for("watch-american-ii-wwtp")[0] == "Dug Run"
    assert routing.receiving_for("watch-shawnee-ii-wwtp")[0] == "Ottawa River"
    # Unknown node -> no route, never invented.
    assert routing.receiving_for("nope") == (None, "")


def test_routing_table_carries_structured_design_flows(hydro_settings: Settings) -> None:
    """WS-22 (issue 1622): design flows are a structured, document-cited field on the routing
    table — the analog of the ECHO design_flow_mgd column — not a first-match regex over prose."""
    routing = load_routing(settings=hydro_settings)
    assert routing is not None
    # Each accessor returns (design flow MGD, its authoritative NPDES citation) so the value's
    # real source travels with it into the evidence record, not a generic watch-item id.
    assert routing.design_flow_for("watch-american-ii-wwtp") == (
        1.2,
        "Ohio EPA fact sheet 2PH00006 (American II WWTP)",
    )
    mgd, cite = routing.design_flow_for("watch-american-bath-wwtp")
    assert mgd == 1.5 and "2PH00007" in (cite or "")
    # Shawnee II's summary states an expansion (2.0 -> 3.0 MGD); the structured value pins the
    # post-expansion design flow rather than depending on which prose token the regex catches.
    mgd, cite = routing.design_flow_for("watch-shawnee-ii-wwtp")
    assert mgd == 3.0 and "2PK00002" in (cite or "")
    mgd, cite = routing.design_flow_for("watch-lima-wwtp")
    assert mgd == 18.5 and "2PE00000" in (cite or "")
    # The campus forcemain's industrial discharge is structured too (read by the campus node).
    mgd, cite = routing.forcemain_design_flow("bosc-fm2")
    assert mgd == 2.5 and "FM-2" in (cite or "")
    # Unknown ids -> no invented flow, and no dangling citation.
    assert routing.design_flow_for("nope") == (None, None)
    assert routing.forcemain_design_flow("bosc-fm1") == (None, None)  # no flow curated for FM-1


def test_bosc_routing_confirmed_vs_theorized(hydro_settings: Settings) -> None:
    routing = load_routing(settings=hydro_settings)
    assert routing is not None
    confirmed_targets = {t for r in routing.confirmed_bosc_routes() for t in r.to}
    theorized_targets = {t for r in routing.theorized_bosc_routes() for t in r.to}
    # BOSC output is confirmed to Lima (FM-2) and the American plants (FM-1).
    assert "watch-lima-fm2-terminus" in confirmed_targets
    assert "watch-american-ii-wwtp" in confirmed_targets
    # Shawnee II is theorized only — not a confirmed BOSC receiver.
    assert "watch-shawnee-ii-wwtp" in theorized_targets
    assert "watch-shawnee-ii-wwtp" not in confirmed_targets


def test_campus_receivers_maps_node_to_forcemain(hydro_settings: Settings) -> None:
    routing = load_routing(settings=hydro_settings)
    assert routing is not None
    receivers = routing.campus_receivers()
    # FM-2 -> Lima; FM-1 -> American Bath + American II; Shawnee II is not a receiver.
    assert receivers["watch-lima-fm2-terminus"] == "bosc-fm2"
    assert receivers["watch-american-ii-wwtp"] == "bosc-fm1"
    assert receivers["watch-american-bath-wwtp"] == "bosc-fm1"
    assert "watch-shawnee-ii-wwtp" not in receivers


def test_balance_surfaces_theorized_shawnee_routing(hydro_settings: Settings) -> None:
    """The balance must flag Shawnee II's theorized BOSC routing as excluded."""
    balance = build_water_balance(settings=hydro_settings, live=False)
    joined = " ".join(balance.warnings).lower()
    assert "theorized" in joined and "shawnee" in joined
    # The WWTP receiving-water routing still resolves (no regression).
    receiving = {
        n.node.name: n.node.receiving_water for n in balance.nodes if n.node.role == "wwtp"
    }
    assert any(v == "Ottawa River" for v in receiving.values())
