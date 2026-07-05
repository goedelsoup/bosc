"""Reach-network centerline assembly — geometry primitives + offline NLDI integration.

The pure helpers are tested on synthetic polylines; the assembly is replayed from the
committed ``tests/fixtures/hydrology/nldi/`` fixtures (no network), asserting the seven Lima
reaches resolve into a connected, downstream-oriented network.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology import reach_geometry as rg

from .conftest import FIXTURES, REPO_ROOT


@pytest.fixture
def reach_settings(tmp_path: Path) -> Settings:
    """Offline hydrology settings with a sandboxed cache so only the fixtures are read."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        hydro_fixtures_dir=FIXTURES / "hydrology",
        hydro_cache_dir=tmp_path / "cache",
    )


# --- pure geometry ----------------------------------------------------------------------


def test_haversine_and_length() -> None:
    # ~1° of latitude ≈ 111 km.
    assert rg.haversine_km((0.0, 0.0), (0.0, 1.0)) == pytest.approx(111.19, abs=0.5)
    assert rg.polyline_length_km([(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]) == pytest.approx(
        222.4, abs=1
    )


def test_chain_flowlines_joins_end_to_end() -> None:
    a = [(0.0, 0.0), (1.0, 0.0)]
    b = [(1.0, 0.0), (2.0, 0.0)]
    assert rg.chain_flowlines([a, b]) == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]


def test_chain_flowlines_reorients_reversed_segment() -> None:
    a = [(0.0, 0.0), (1.0, 0.0)]
    b = [(2.0, 0.0), (1.0, 0.0)]  # shares the (1,0) endpoint but runs backwards
    assert rg.chain_flowlines([a, b]) == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]


def test_orient_downstream_puts_anchor_end_last() -> None:
    line = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    # anchor near the (0,0) end → the line is reversed so it *ends* there.
    assert rg.orient_downstream(line, (-0.1, 0.0))[-1] == (0.0, 0.0)
    # anchor near the (2,0) end → unchanged.
    assert rg.orient_downstream(line, (2.1, 0.0))[-1] == (2.0, 0.0)


def test_split_at_point_shares_the_boundary_vertex() -> None:
    line = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]
    before, after = rg.split_at_point(line, (2.0, 0.05))
    assert before[-1] == after[0] == (2.0, 0.0)
    assert before == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    assert after == [(2.0, 0.0), (3.0, 0.0)]


def test_cut_by_fractions_tiles_the_line_exactly() -> None:
    line = [(0.0, 0.0), (4.0, 0.0)]  # 4 units long
    pieces = rg.cut_by_fractions(line, [1.0, 1.0])  # halve it
    assert len(pieces) == 2
    assert pieces[0][0] == (0.0, 0.0)
    assert pieces[0][-1] == pieces[1][0]  # contiguous
    assert pieces[1][-1] == (4.0, 0.0)
    assert pieces[0][-1][0] == pytest.approx(2.0)  # cut at the midpoint


def test_cut_by_fractions_single_piece_is_identity() -> None:
    line = [(0.0, 0.0), (1.0, 0.0)]
    assert rg.cut_by_fractions(line, [1.0]) == [line]


# --- offline NLDI assembly --------------------------------------------------------------


def test_assemble_reach_network_resolves_the_lima_reaches(reach_settings: Settings) -> None:
    centerlines, warnings = rg.assemble_reach_network(settings=reach_settings)
    by_id = {c.node_id: c for c in centerlines}

    # All seven model reaches resolve to a line, no warnings.
    assert set(by_id) == {
        "ottawa-head",
        "lima-abstraction",
        "lima-reach",
        "dug-run-head",
        "dug-run-confluence",
        "pike-run-head",
        "pike-run-confluence",
    }
    assert warnings == []
    for c in centerlines:
        assert len(c.coordinates) >= 2
        assert c.length_km > 0


def test_mainstem_reaches_are_contiguous_head_to_outlet(reach_settings: Settings) -> None:
    by_id = {c.node_id: c for c in rg.assemble_reach_network(settings=reach_settings)[0]}
    chain = ["ottawa-head", "lima-abstraction", "lima-reach"]
    for upstream, downstream in pairwise(chain):
        # the end of one reach is the start of the next (shared cut vertex).
        assert by_id[upstream].coordinates[-1] == by_id[downstream].coordinates[0]


def test_tributary_confluences_meet_the_mainstem(reach_settings: Settings) -> None:
    by_id = {c.node_id: c for c in rg.assemble_reach_network(settings=reach_settings)[0]}
    lima_reach = by_id["lima-reach"].coordinates
    for trib in ("dug-run-confluence", "pike-run-confluence"):
        end = by_id[trib].coordinates[-1]
        nearest = min(rg.haversine_km(end, p) for p in lima_reach)
        assert nearest < 0.2  # the confluence lands on the assimilative reach (< 200 m)


def test_reach_network_geojson_shape(reach_settings: Settings) -> None:
    centerlines, _ = rg.assemble_reach_network(settings=reach_settings)
    doc = rg.reach_network_geojson(centerlines)
    assert doc["type"] == "FeatureCollection"
    assert len(doc["features"]) == len(centerlines)
    feat = doc["features"][0]
    assert feat["geometry"]["type"] == "LineString"
    assert set(feat["properties"]) == {
        "node_id",
        "name",
        "receiving_water",
        "downstream",
        "length_km",
    }
