"""Corridor view — tie BOSC facilities/parcels/roadwork to corridor geography.

The frozen Periplus corridor geometry (`data/reference/periplus/corridor.geojson` study
area + `corridor-centerline.geojson` road/rail/transmission routes) was imported but
unused by any code. This module is the **spatial join**: it projects every BOSC watch
item (facilities + force mains) and recorded parcel onto that corridor geometry and
reports, per feature, whether it falls in the study area, its distance to the nearest
linear corridor route, the nearest route, and its station (chainage) along the primary
road centerline — the roadway the roundabouts OPC prices.

Pure and hermetic: shapely + pyproj over committed GeoJSON only (no network), mirroring
``bosc.hydrology.geo``. The corridor geometry is **external corroboration** (frozen from
the Periplus fork, per ``data/reference/periplus/README.md``), not a BOSC-produced
artifact — so the view cites it as a reference source and never edits it in place.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

_SQM_PER_ACRE = 4046.8564224
_PERIPLUS_REL = "data/reference/periplus"
# The linear corridor routes a feature is measured against (the study-area polygon, the
# Bistrozzi site polygon and the utilities point are context, not a centerline to clock).
_LINE_ROLES = ("road", "rail", "transmission")


class CorridorError(RuntimeError):
    """The corridor geometry is missing or empty — refuse to invent a corridor."""


class CorridorRoute(BaseModel):
    """One feature of the corridor centerline file (a route, the site, or a landmark)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    role: str  # road | rail | transmission | site | facility (verbatim from the source)
    geom_type: str
    length_m: float | None  # linear length for routes; None for points/polygons


class CorridorMember(BaseModel):
    """A BOSC feature located against the corridor — the spatial-join row."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: str  # facility | forcemain | parcel
    geom_type: str
    in_study_area: bool  # the geometry intersects the corridor study-area polygon
    distance_to_route_m: float  # to the nearest linear route (road/rail/transmission)
    nearest_route: str
    nearest_route_role: str
    station_m: float | None  # chainage along the primary road centerline (None if no road)
    source: str  # the GeoJSON the member came from


class CorridorView(BaseModel):
    """The corridor study area, its routes, and every BOSC feature joined to it."""

    model_config = ConfigDict(extra="forbid")

    study_area_acres: float
    routes: list[CorridorRoute] = Field(default_factory=list)
    members: list[CorridorMember] = Field(default_factory=list)
    source: str

    @property
    def in_corridor(self) -> list[CorridorMember]:
        """Members whose geometry falls within the corridor study area."""
        return [m for m in self.members if m.in_study_area]

    @property
    def road_length_m(self) -> float | None:
        """Total length of the road-role centerline route(s), in metres."""
        lengths = [r.length_m for r in self.routes if r.role == "road" and r.length_m]
        return round(sum(lengths), 1) if lengths else None


def _features(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return cast("list[dict[str, Any]]", data.get("features", []) if isinstance(data, dict) else [])


def build_corridor_view(*, settings: Settings | None = None) -> CorridorView:
    """Join BOSC facilities/parcels/force mains to the frozen Periplus corridor geometry.

    Reads the committed Periplus GeoJSON only; projects to UTM (``hydro_utm_epsg``) so
    distances and the station are in metres. Raises :class:`CorridorError` if the study
    area is missing — the corridor is never fabricated.
    """
    settings = settings or get_settings()
    ref = settings.reference_dir / "periplus"
    transform = Transformer.from_crs(4326, settings.hydro_utm_epsg, always_xy=True).transform

    def proj(geometry: dict[str, Any]) -> Any:
        return shapely_transform(transform, shape(geometry))

    corridor_feats = _features(ref / "corridor.geojson")
    if not corridor_feats:
        raise CorridorError(f"no corridor study-area geometry at {ref / 'corridor.geojson'}")
    study = proj(corridor_feats[0]["geometry"])
    study_acres = round(float(study.area) / _SQM_PER_ACRE, 1)

    # Corridor centerline routes: catalogue them all, but only the linear road/rail/
    # transmission routes are the geometry features are clocked against.
    routes: list[CorridorRoute] = []
    line_routes: list[tuple[str, str, Any]] = []  # (name, role, projected geom)
    road_lines: list[Any] = []
    for feat in _features(ref / "corridor-centerline.geojson"):
        geom = feat.get("geometry") or {}
        props = feat.get("properties") or {}
        gtype = str(geom.get("type") or "")
        role = str(props.get("role") or "")
        name = str(props.get("Name") or props.get("name") or "")
        pgeom = proj(geom)
        is_line = gtype in ("LineString", "MultiLineString")
        routes.append(
            CorridorRoute(
                name=name,
                role=role,
                geom_type=gtype,
                length_m=round(float(pgeom.length), 1) if is_line else None,
            )
        )
        if is_line and role in _LINE_ROLES:
            line_routes.append((name, role, pgeom))
            if role == "road":
                road_lines.append(pgeom)
    primary_road = max(road_lines, key=lambda g: float(g.length)) if road_lines else None

    def locate(
        mid: str, name: str, kind: str, geometry: dict[str, Any], source: str
    ) -> CorridorMember:
        mgeom = proj(geometry)
        gtype = str(geometry.get("type") or "")
        rep = mgeom if gtype == "Point" else mgeom.centroid
        dist, nr_name, nr_role = min(
            ((float(rg.distance(mgeom)), nm, rl) for nm, rl, rg in line_routes),
            default=(float("nan"), "", ""),
        )
        station = round(float(primary_road.project(rep)), 1) if primary_road is not None else None
        return CorridorMember(
            id=mid,
            name=name,
            kind=kind,
            geom_type=gtype,
            in_study_area=bool(study.intersects(mgeom)),
            distance_to_route_m=round(dist, 1),
            nearest_route=nr_name,
            nearest_route_role=nr_role,
            station_m=station,
            source=source,
        )

    members: list[CorridorMember] = []

    watch_src = f"{_PERIPLUS_REL}/watch-items.geojson"
    for feat in _features(ref / "watch-items.geojson"):
        geom = feat.get("geometry") or {}
        if not geom:
            continue
        props = feat.get("properties") or {}
        mid = str(props.get("id") or props.get("title") or "")
        name = str(props.get("title") or mid)
        kind = "forcemain" if geom.get("type") in ("LineString", "MultiLineString") else "facility"
        members.append(locate(mid, name, kind, geom, watch_src))

    parcels_path = ref / "bosc-parcels.geojson"
    if parcels_path.is_file():
        parcel_src = f"{_PERIPLUS_REL}/bosc-parcels.geojson"
        for feat in _features(parcels_path):
            geom = feat.get("geometry") or {}
            if not geom:
                continue
            props = feat.get("properties") or {}
            pid = str(props.get("parcel_id") or "")
            grantee = str(props.get("grantee") or "")
            name = f"{pid} ({grantee})" if grantee else pid
            members.append(locate(pid, name, "parcel", geom, parcel_src))

    # In the study area first, then closest-to-a-route, then by name — the worklist order.
    members.sort(key=lambda m: (not m.in_study_area, m.distance_to_route_m, m.name))
    log.info(
        "gis.corridor",
        study_acres=study_acres,
        members=len(members),
        in_corridor=sum(1 for m in members if m.in_study_area),
        routes=len(routes),
    )
    return CorridorView(
        study_area_acres=study_acres,
        routes=routes,
        members=members,
        source=(
            f"frozen Periplus corridor + centerline GeoJSON ({_PERIPLUS_REL}/) — "
            "external corroboration (do not edit in place)"
        ),
    )
