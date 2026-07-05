"""Reach-network centerline assembly — stitch NHDPlus flowlines into per-reach polylines.

The model reaches in ``network.yaml`` / ``reaches.yaml`` carry topology + channel
length/slope only — no coordinates. This module turns the **real** NHDPlus flowline
geometry from the NLDI connector (:mod:`watermark.hydrology.connectors.nldi`) into one
ordered, downstream-oriented centerline per reach node, so the geometry is sourced (real
river lines), never invented. The geometry primitives (``chain_flowlines``,
``cut_by_fractions``, …) are pure; :func:`assemble_reach_network` drives the fixture-backed
NLDI connector per the committed ``reach-nav.yaml`` plan, so it stays offline-testable.

Discipline (Tier-0 screening): the *geometry* is verbatim NHDPlus. The only modeling
choice is where one mainstem is **cut** into its named model reaches — done by the
reaches' own stated length **ratios** (a proportional cut of the real arc length),
recorded as such, not as a claim about NHDPlus segment boundaries.
"""

from __future__ import annotations

import json
import math
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors import nldi
from watermark.hydrology.hydrograph_routing import load_reaches
from watermark.hydrology.network import load_topology
from watermark.logging import get_logger

log = get_logger(__name__)

Point = tuple[float, float]  # (lon, lat), WGS84

# Endpoint-match tolerance when chaining flowline segments — NHDPlus vertices are shared
# exactly at confluences, so ~1e-4° (~11 m) comfortably joins them without bridging a gap.
_CHAIN_EPS_DEG = 1e-4


class ReachCenterline(BaseModel):
    """One reach node's river-centerline polyline, ordered head → downstream."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    name: str
    receiving_water: str | None
    downstream: str | None  # the node this reach drains into (or None at the outlet)
    coordinates: list[Point]  # (lon, lat), ordered downstream
    length_km: float


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance between two ``(lon, lat)`` points, in kilometres."""
    r = 6371.0088
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def polyline_length_km(coords: list[Point]) -> float:
    """Arc length of a ``(lon, lat)`` polyline, in kilometres."""
    return sum(haversine_km(a, b) for a, b in pairwise(coords))


def _dist2(a: Point, b: Point) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def chain_flowlines(lines: list[list[Point]], *, eps_deg: float = _CHAIN_EPS_DEG) -> list[Point]:
    """Greedily stitch a set of flowline segments into one ordered polyline.

    Connects segments by matching near-equal endpoints (any of the four orientations),
    growing a single path. Segments that never connect (a disjoint tributary mixed in) are
    dropped — the caller navigates one path at a time, so a well-formed group chains whole.
    Order within the result is geometric, not yet downstream — call :func:`orient_downstream`.
    """
    remaining = [list(seg) for seg in lines if seg]
    if not remaining:
        return []
    path = remaining.pop(0)
    eps2 = eps_deg * eps_deg
    progress = True
    while remaining and progress:
        progress = False
        for i, seg in enumerate(remaining):
            if _dist2(path[-1], seg[0]) <= eps2:
                path = path + seg[1:]
            elif _dist2(path[-1], seg[-1]) <= eps2:
                path = path + seg[-2::-1]
            elif _dist2(path[0], seg[-1]) <= eps2:
                path = seg[:-1] + path
            elif _dist2(path[0], seg[0]) <= eps2:
                path = seg[:0:-1] + path
            else:
                continue
            remaining.pop(i)
            progress = True
            break
    return path


def split_at_point(coords: list[Point], point: Point) -> tuple[list[Point], list[Point]]:
    """Split a polyline at the vertex nearest ``point`` into ``(before, after)``.

    The split vertex is shared by both halves (so they stay contiguous). Used to cut the
    mainstem at the real gage location: everything upstream of the gage vs. the assimilative
    reach below it. Degenerate splits (point at an end) return one empty half.
    """
    if len(coords) < 2:
        return coords, []
    idx = min(range(len(coords)), key=lambda i: _dist2(coords[i], point))
    return coords[: idx + 1], coords[idx:]


def orient_downstream(coords: list[Point], anchor: Point) -> list[Point]:
    """Orient a polyline so its **last** vertex is the one nearest ``anchor`` (the outlet).

    Particles advect from ``coords[0]`` → ``coords[-1]``; the downstream anchor (the reach's
    confluence / the network outlet) pins that direction, so flow always runs downhill.
    """
    if len(coords) < 2:
        return coords
    if _dist2(coords[0], anchor) < _dist2(coords[-1], anchor):
        return coords[::-1]
    return coords


def cut_by_fractions(coords: list[Point], fractions: list[float]) -> list[list[Point]]:
    """Split a polyline into consecutive sub-polylines by cumulative arc-length fractions.

    ``fractions`` are the share of total length for each piece, in order (they need not sum
    to exactly 1 — they're normalized). A new vertex is interpolated at each internal cut so
    the pieces tile the line exactly and share the boundary vertex (contiguous advection).
    Returns one polyline per fraction; empty fractions yield 2-point degenerate stubs skipped
    by the caller. With a single fraction, returns ``[coords]`` unchanged.
    """
    if len(coords) < 2 or len(fractions) <= 1:
        return [coords]
    total = polyline_length_km(coords)
    norm = sum(fractions) or 1.0
    # Cumulative cut distances (exclude the final endpoint; the last piece takes the remainder).
    targets: list[float] = []
    acc = 0.0
    for f in fractions[:-1]:
        acc += (f / norm) * total
        targets.append(acc)

    pieces: list[list[Point]] = []
    current: list[Point] = [coords[0]]
    ti = 0
    run = 0.0  # arc length walked so far
    for a, b in pairwise(coords):
        seg = haversine_km(a, b)
        # Emit as many cuts as fall within this segment.
        while ti < len(targets) and run + seg >= targets[ti] and seg > 0:
            t = (targets[ti] - run) / seg
            cut: Point = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            current.append(cut)
            pieces.append(current)
            current = [cut]
            ti += 1
        current.append(b)
        run += seg
    pieces.append(current)
    # Guard: pad with empties if the line was too short to reach every cut.
    while len(pieces) < len(fractions):
        pieces.append([])
    return pieces


# --- Navigation plan + assembly (reads reach-nav.yaml, drives the NLDI connector) ---------


class MainstemNav(BaseModel):
    """The mainstem navigation: one gage-anchored line cut into its named model reaches."""

    model_config = ConfigDict(extra="forbid")

    gage: str  # NLDI feature id, e.g. "USGS-04187100"
    gage_point: tuple[float, float]  # (lon, lat) — the head/reach split anchor
    upstream_km: float
    downstream_km: float = 0.0
    above_gage: list[str]  # reach node_ids above the gage, cut by their length ratios
    below_gage: str  # the single assimilative reach node_id below the gage


class TributaryNav(BaseModel):
    """One tributary: snap the WWTP outfall, navigate up (head) + down (confluence)."""

    model_config = ConfigDict(extra="forbid")

    head: str  # the headwater reach node_id
    confluence: str  # the lower reach node_id (to the Ottawa confluence)
    anchor: tuple[float, float]  # (lon, lat) of the WWTP outfall to snap
    upstream_km: float
    downstream_km: float


class ReachNavPlan(BaseModel):
    """The committed reach-network navigation plan (``reach-nav.yaml``)."""

    model_config = ConfigDict(extra="ignore")

    outlet_anchor: tuple[float, float]
    mainstem: MainstemNav
    tributaries: list[TributaryNav] = []


def _nav_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "reach-nav.yaml"


def load_nav_plan(*, settings: Settings | None = None) -> ReachNavPlan | None:
    """Load the committed reach-nav plan, or ``None`` when the file is absent."""
    settings = settings or get_settings()
    path = _nav_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ReachNavPlan.model_validate(data)


def _gather(calls: list[list[nldi.Flowline]]) -> list[list[Point]]:
    """Flatten NLDI nav results into one coordinate list per ``comid`` (deduped).

    UM and DM navigations both include the source flowline, so a shared ``comid`` would
    otherwise be chained twice into a doubled-back path — dedup keeps each segment once.
    """
    by_comid: dict[int, list[Point]] = {}
    for result in calls:
        for fl in result:
            by_comid.setdefault(fl.comid, fl.coordinates)
    return list(by_comid.values())


def _centerline(node_id: str, coords: list[Point], nodes: dict[str, Any]) -> ReachCenterline:
    node = nodes.get(node_id)
    return ReachCenterline(
        node_id=node_id,
        name=getattr(node, "name", node_id),
        receiving_water=getattr(node, "receiving_water", None),
        downstream=getattr(node, "downstream", None),
        coordinates=coords,
        length_km=round(polyline_length_km(coords), 3),
    )


def assemble_reach_network(
    *, settings: Settings | None = None
) -> tuple[list[ReachCenterline], list[str]]:
    """Navigate + stitch the reach-network centerlines per the committed nav plan.

    Reads ``reach-nav.yaml`` (the anchors + cut order), ``network.yaml`` (node names /
    downstream / receiving water) and ``reaches.yaml`` (the length ratios), drives the NLDI
    connector for the real NHDPlus geometry, and returns one :class:`ReachCenterline` per
    reach node that resolves to a line, plus warnings for any that don't. Offline-safe:
    every NLDI call is replayed from the committed fixture.
    """
    settings = settings or get_settings()
    warnings: list[str] = []
    plan = load_nav_plan(settings=settings)
    if plan is None:
        return [], ["reach-nav.yaml absent — no reach-network geometry"]
    nodes = {n.id: n for n in load_topology(settings=settings)}
    reach_table = load_reaches(settings=settings)
    if reach_table is None:
        return [], ["reaches.yaml absent — cannot cut mainstem into model reaches"]
    lengths = {rid: r.length_ft.value for rid, r in reach_table.reaches.items()}
    anchor: Point = tuple(plan.outlet_anchor)  # type: ignore[assignment]
    out: list[ReachCenterline] = []

    # Mainstem: one line head → outlet, split at the real gage point. Above the gage is cut
    # into its model reaches by length ratio; below is the single assimilative reach.
    ms = plan.mainstem
    calls = [nldi.navigate_flowlines(ms.gage, "UM", distance_km=ms.upstream_km, settings=settings)]
    if ms.downstream_km > 0:
        calls.append(
            nldi.navigate_flowlines(ms.gage, "DM", distance_km=ms.downstream_km, settings=settings)
        )
    full = orient_downstream(chain_flowlines(_gather(calls)), anchor)
    if len(full) < 2:
        warnings.append(f"mainstem from {ms.gage} returned no usable geometry")
    else:
        above, below = split_at_point(full, tuple(ms.gage_point))  # type: ignore[arg-type]
        fracs = [lengths.get(r, 1.0) for r in ms.above_gage]
        for rid, piece in zip(ms.above_gage, cut_by_fractions(above, fracs), strict=False):
            if len(piece) < 2:
                warnings.append(f"reach {rid!r} got no geometry from the mainstem cut")
                continue
            out.append(_centerline(rid, piece, nodes))
        if len(below) >= 2:
            out.append(_centerline(ms.below_gage, below, nodes))
        else:
            warnings.append(f"reach {ms.below_gage!r} (below gage) got no geometry")

    # Tributaries: snap the outfall, navigate up+down → one line cut head : confluence.
    for trib in plan.tributaries:
        comid = nldi.snap_point(trib.anchor[0], trib.anchor[1], settings=settings)
        if comid is None:
            warnings.append(f"tributary {trib.head!r}: NLDI could not snap {trib.anchor}")
            continue
        cid = str(comid)
        tcalls = [
            nldi.navigate_flowlines(cid, "UM", distance_km=trib.upstream_km, settings=settings),
            nldi.navigate_flowlines(cid, "DM", distance_km=trib.downstream_km, settings=settings),
        ]
        line = orient_downstream(chain_flowlines(_gather(tcalls)), anchor)
        if len(line) < 2:
            warnings.append(f"tributary {trib.head!r}: no usable geometry from comid {cid}")
            continue
        head_len = lengths.get(trib.head, 1.0)
        conf_len = lengths.get(trib.confluence, 1.0)
        head_piece, conf_piece = cut_by_fractions(line, [head_len, conf_len])
        if len(head_piece) >= 2:
            out.append(_centerline(trib.head, head_piece, nodes))
        if len(conf_piece) >= 2:
            out.append(_centerline(trib.confluence, conf_piece, nodes))

    return out, warnings


def reach_network_geojson(centerlines: list[ReachCenterline]) -> dict[str, Any]:
    """The reach-network centerlines as a committed-reference GeoJSON FeatureCollection."""
    features = [
        {
            "type": "Feature",
            "properties": {
                "node_id": c.node_id,
                "name": c.name,
                "receiving_water": c.receiving_water,
                "downstream": c.downstream,
                "length_km": c.length_km,
            },
            "geometry": {"type": "LineString", "coordinates": [list(p) for p in c.coordinates]},
        }
        for c in centerlines
    ]
    return {
        "type": "FeatureCollection",
        "meta": {
            "subject": "Reach-network river centerlines (NHDPlus via USGS NLDI)",
            "source": (
                "USGS NLDI navigation over the NHDPlus flowline network; stitched + cut per "
                "reach by watermark.hydrology.reach_geometry. Geometry verbatim (WGS84)."
            ),
            "crs": "WGS84 (EPSG:4326)",
            "caveats": [
                "Centerline geometry is real NHDPlus, display-only — no reprojection/simplification.",
                "Mainstem/tributary reach boundaries are a proportional cut by reaches.yaml lengths.",
                "Tier-0 screening geometry for the FlowLayer viz; not a calibrated hydraulic network.",
            ],
        },
        "features": features,
    }


def write_reach_network(centerlines: list[ReachCenterline], out_path: Path) -> Path:
    """Write the reach-network centerlines to ``out_path`` as GeoJSON; return the path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = reach_network_geojson(centerlines)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
