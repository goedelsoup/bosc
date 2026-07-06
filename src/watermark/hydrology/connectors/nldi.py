"""USGS NLDI — NHDPlus flowline (river-centerline) geometry connector.

Pulls **real river-centerline geometry** from the USGS **Network-Linked Data Index**
(NLDI), the navigation service over the NHDPlus flowline network. Two operations, both
returning WGS84 GeoJSON verbatim (no reprojection/simplification):

* :func:`snap_point` — snap a WGS84 point to the NHDPlus flowline it lands on, returning
  that flowline's ``comid`` (the network handle everything else keys on). Drives the
  tributary anchors (a WWTP outfall's coordinate → the creek it discharges to).
* :func:`navigate_flowlines` — from a gage (``USGS-<site_no>``) or a bare ``comid``,
  navigate the network in a direction (``UM`` upstream-main, ``DM`` downstream-main,
  ``UT`` upstream-with-tributaries, ``DD`` downstream-diversions) up to ``distance_km``,
  returning the ordered NHDPlus flowline segments as ``Flowline`` records.

This is the honest geometry source behind ``watermark reaches`` (the reach-network the
GPU FlowLayer viz, epic #1237 / #1235, advects over): the model reaches in
``network.yaml``/``reaches.yaml`` carry only topology + channel length/slope — no
coordinates — so the centerline geometry comes from NHDPlus, not invented. Reuses the
shared hydrology connector cache/offline/fixture machinery; synchronous (``httpx``).
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

# NLDI navigation modes (over the NHDPlus network): upstream-main / downstream-main /
# upstream-with-tributaries / downstream-with-diversions. Only these four are valid.
_NAV_MODES = frozenset({"UM", "DM", "UT", "DD"})


class NldiError(RuntimeError):
    """The NLDI service returned an error / an unusable (non-flowline) response."""


class Flowline(BaseModel):
    """One NHDPlus flowline segment — a river-centerline polyline, WGS84 verbatim."""

    model_config = ConfigDict(extra="forbid")

    comid: int  # the NHDPlus catchment/flowline id
    coordinates: list[tuple[float, float]]  # [(lon, lat), ...], verbatim from NHDPlus


def _iter_lines(geometry: dict[str, Any]) -> list[list[tuple[float, float]]]:
    """The LineString parts of a GeoJSON geometry as ``[(lon, lat), ...]`` lists."""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in coords]]
    if gtype == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in part] for part in coords]
    return []


def snap_point(lon: float, lat: float, *, settings: Settings | None = None) -> int | None:
    """The NHDPlus ``comid`` of the flowline the WGS84 point ``(lon, lat)`` snaps to.

    Returns ``None`` when NLDI can't place the point on the network (e.g. off-network).
    Replayed from cache/fixture when offline; an offline miss raises ``HydroOfflineError``.
    """
    settings = settings or get_settings()
    # NLDI wants a WKT POINT in the `coords` query param.
    query = {"coords": f"POINT({round(lon, 6)} {round(lat, 6)})"}

    def fetch() -> Any:
        log.info("nldi.snap", lon=lon, lat=lat)
        resp = httpx.get(
            f"{settings.nldi_base_url}/linked-data/comid/position",
            params=query,
            timeout=settings.hydro_request_timeout_s,
        )
        resp.raise_for_status()
        return resp.json()

    payload = cast(
        "dict[str, Any]", cached_get("nldi", {"snap": query["coords"]}, fetch, settings=settings)
    )
    if isinstance(payload, dict) and "error" in payload:
        raise NldiError(f"NLDI error snapping ({lon}, {lat}): {payload['error']}")
    features = (payload or {}).get("features") or []
    if not features:
        return None
    props = features[0].get("properties") or {}
    comid = props.get("comid") or props.get("identifier")
    return int(comid) if comid is not None else None


def navigate_flowlines(
    source: str,
    mode: str,
    *,
    distance_km: float,
    settings: Settings | None = None,
) -> list[Flowline]:
    """The NHDPlus flowlines reachable from ``source`` in ``mode`` within ``distance_km``.

    ``source`` is either a gage feature id (``"USGS-04187100"``) or a bare NHDPlus
    ``comid`` (``"15653137"``). ``mode`` is one of ``UM``/``DM``/``UT``/``DD``. Each
    returned :class:`Flowline` is one network segment; the caller stitches them into an
    ordered reach polyline (:mod:`watermark.hydrology.reach_geometry`). Geometry is WGS84,
    carried verbatim. Replayed from cache/fixture when offline.
    """
    settings = settings or get_settings()
    if mode not in _NAV_MODES:
        raise ValueError(
            f"unsupported NLDI nav mode {mode!r}; expected one of {sorted(_NAV_MODES)}"
        )
    # A gage id routes through /nwissite/<id>; a bare comid through /comid/<id>.
    src = source.strip()
    base = "nwissite" if src.upper().startswith("USGS-") else "comid"
    path = f"{settings.nldi_base_url}/linked-data/{base}/{src}/navigation/{mode}/flowlines"
    query = {"distance": f"{distance_km:g}"}
    key_params = {"src": f"{base}:{src}", "mode": mode, "distance": query["distance"]}

    def fetch() -> Any:
        log.info("nldi.navigate", source=src, mode=mode, distance_km=distance_km)
        resp = httpx.get(path, params=query, timeout=settings.hydro_request_timeout_s)
        resp.raise_for_status()
        return resp.json()

    payload = cast("dict[str, Any]", cached_get("nldi", key_params, fetch, settings=settings))
    if isinstance(payload, dict) and "error" in payload:
        raise NldiError(f"NLDI error navigating {src} {mode}: {payload['error']}")

    out: list[Flowline] = []
    for feat in (payload or {}).get("features") or []:
        props = feat.get("properties") or {}
        comid = props.get("nhdplus_comid") or props.get("comid")
        geometry = feat.get("geometry")
        if comid is None or not geometry:
            continue
        for part in _iter_lines(geometry):
            if part:
                out.append(Flowline(comid=int(comid), coordinates=part))
    return out
