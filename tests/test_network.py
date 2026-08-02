"""The BOSC network synthesis (watermark.network): the watershed points as one connected basin.

Hermetic — builds the cross-site comparison from committed reference data only (topology +
each node's economy/grid/toxics artifacts + the low-flow screen). No network, no fixtures.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.network import BasinNetwork, build_basin_network, write_basin_network

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def net() -> BasinNetwork:
    return build_basin_network(
        settings=Settings(data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True)
    )


def _node(net: BasinNetwork, slug: str):  # type: ignore[no-untyped-def]
    return next(n for n in net.nodes if n.slug == slug)


def test_shared_basin_and_node_count(net: BasinNetwork) -> None:
    assert net.sink == "Lake Erie"
    assert "TMDL" in net.shared_constraint
    # Every registered, topology-listed site is a node.
    assert {n.slug for n in net.nodes} == {
        "lima",
        "fort-wayne",
        "defiance",
        "toledo",
        "van-wert",
        "findlay",
        "ottawa",
        "bryan",
    }


def test_topology_drains_downstream_to_the_sink(net: BasinNetwork) -> None:
    # Defiance is the confluence collector; Toledo the outlet; everything routes through them.
    assert _node(net, "toledo").downstream == "Lake Erie"
    assert _node(net, "defiance").downstream == "toledo"
    for slug in ("lima", "van-wert", "findlay", "ottawa", "bryan", "fort-wayne"):
        assert _node(net, slug).downstream == "defiance", slug
    # Subtrees derived from the drainage path.
    assert _node(net, "bryan").subtree == "Tiffin"
    assert _node(net, "lima").subtree == "Auglaize"
    assert _node(net, "ottawa").subtree == "Auglaize"  # Blanchard -> Auglaize
    assert _node(net, "toledo").subtree == "Maumee mainstem"


def test_display_order_is_upstream_to_downstream(net: BasinNetwork) -> None:
    order = [n.slug for n in net.nodes]
    # The lower-Maumee collectors come last, Defiance before Toledo.
    assert order[-2:] == ["defiance", "toledo"]
    # Fort Wayne (upper mainstem) sits after the tributary subtrees, before the collectors.
    assert order.index("bryan") < order.index("fort-wayne") < order.index("defiance")


def test_subtree_generalizes_across_basins() -> None:
    """#610: the subtree is derived from the drainage path, not a Maumee-only literal table.

    A cross-basin (Miami / Scioto) node buckets into its OWN basin's grouping instead of
    silently falling through to ``Maumee mainstem``; the Maumee labels are unchanged.
    """
    from watermark.network import _subtree

    # Maumee — exactly as before.
    assert _subtree(["Ottawa River", "Auglaize River", "Maumee River"]) == "Auglaize"
    assert _subtree(["Town Creek", "Little Auglaize River", "Auglaize River", "Maumee River"]) == (
        "Auglaize"
    )
    assert _subtree(["Prairie Creek", "Tiffin River", "Maumee River"]) == "Tiffin"
    assert _subtree(["Maumee River"]) == "Maumee mainstem"
    # Great Miami basin — its own grouping, never "Maumee mainstem".
    assert _subtree(["Mad River", "Great Miami River"]) == "Mad"
    assert _subtree(["Great Miami River"]) == "Great Miami mainstem"
    # Scioto basin.
    assert _subtree(["Olentangy River", "Scioto River"]) == "Olentangy"
    assert _subtree(["Scioto River"]) == "Scioto mainstem"


def test_screen_is_one_dimension_honestly_sparse(net: BasinNetwork) -> None:
    # Lima (violation), Defiance (tight), Van Wert (violation) and — since #1460 — Findlay
    # (violation) are cleanly screenable.
    lima = _node(net, "lima").screen
    assert lima.status == "screened" and lima.flag == "violation" and lima.dilution_ratio < 0.1
    defiance = _node(net, "defiance").screen
    assert defiance.status == "screened" and defiance.flag == "tight"
    assert 4.0 < (defiance.dilution_ratio or 0) < 9.0
    van_wert = _node(net, "van-wert").screen
    assert van_wert.status == "screened" and van_wert.flag == "violation"
    assert (van_wert.dilution_ratio or 0) < 0.05  # 0.026:1 — 39x effluent dominance
    # Findlay became screenable when the curated overlay gave OH0025135 the receiving water its
    # own NPDES fact sheet names (#1460, closing #352), and #1458 then re-based it: the screen no
    # longer runs on the DERIVED 8.67 cfs at USGS 04189000 (a regulated gage sitting DOWNSTREAM of
    # this plant's own outfall — its own effluent was in its own denominator) but on the 0.21 cfs
    # Ohio EPA states AT the outfall, reached through the permit-scoped `permits:` index. Same
    # violation band, ~41x tighter in the ratio (the denominators are 8.67 / 0.21 = 41x apart —
    # about 1.6 orders of magnitude); pin the source, not just the number.
    findlay = _node(net, "findlay").screen
    assert findlay.status == "screened" and findlay.flag == "violation"
    assert (findlay.dilution_ratio or 0) == pytest.approx(0.009, abs=0.001)  # 0.21 / 23.208
    assert "cited AT THIS OUTFALL" in findlay.detail and "0.21 cfs" in findlay.detail
    # The rest are reported unscreened, with the reason (omit, don't guess) — the data gap.
    screened = [n for n in net.nodes if n.screen.status == "screened"]
    assert len(screened) == 4
    assert _node(net, "bryan").screen.status == "no_7q10"  # ungaged Prairie Creek
    assert _node(net, "toledo").screen.status == "no_receiving_water"  # null in ECHO


def test_economy_shape_is_universal(net: BasinNetwork) -> None:
    # Every node is a manufacturing-concentrated, information-sector-absent county.
    for n in net.nodes:
        assert n.economy.manufacturing_lq is not None and n.economy.manufacturing_lq > 1.0, n.slug
        assert n.economy.information_lq is not None and n.economy.information_lq < 1.0, n.slug
        assert n.economy.population and n.economy.population > 0, n.slug


def test_grid_carries_the_serving_utility(net: BasinNetwork) -> None:
    lima = _node(net, "lima").grid
    assert "AEP Ohio" in (lima.utility or "") and "PUCO" in (lima.retail_regulator or "")
    # Bryan is the network's municipal node — home-rule regulator, AMP/PJM, cheapest bundled price.
    bryan = _node(net, "bryan").grid
    assert "municipal" in (bryan.holding_company or "").lower()
    assert "home rule" in (bryan.retail_regulator or "").lower()
    # FirstEnergy/ATSI for the lower-mainstem nodes (non-AEP).
    assert "FirstEnergy" in (_node(net, "defiance").grid.holding_company or "")


def test_toxics_present(net: BasinNetwork) -> None:
    for n in net.nodes:
        assert n.toxics.facility_count and n.toxics.facility_count > 0, n.slug


def test_disclosed_facilities_are_lima_fort_wayne_van_wert_and_findlay(net: BasinNetwork) -> None:
    # Lima (OEPA Air PTI) and Fort Wayne (IDEM Title V air permit, #360) are AIR-PERMIT-grounded
    # facilities; Van Wert (the QTS Mega Site, #1402) is SITE-PLAN-grounded (the #1327 Urbana
    # precedent) — its 500 MW is a [reference] bracket, not an air-permit disclosure. Findlay (the
    # One Power "Findlay Megawatt Hub" / MARA 150 MW take-or-pay, #1459) is SEC-INSTRUMENT-grounded
    # — its MW is a [verified] disclosure. Every other Maumee node carries the grid backdrop
    # without a campus load.
    disclosed = {n.slug for n in net.nodes if n.activity.has_disclosed_facility}
    assert disclosed == {"lima", "fort-wayne", "van-wert", "findlay"}
    for slug in disclosed:
        node = _node(net, slug)
        assert node.activity.it_load_mw and node.activity.it_load_mw > 0


def test_write_round_trips(tmp_path: Path, net: BasinNetwork) -> None:
    import yaml

    out = write_basin_network(net, settings=Settings(data_dir=tmp_path))
    assert out.exists()
    reloaded = BasinNetwork.model_validate(yaml.safe_load(out.read_text(encoding="utf-8")))
    assert len(reloaded.nodes) == len(net.nodes)
    assert reloaded.sink == net.sink
