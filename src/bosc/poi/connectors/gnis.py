"""USGS GNIS — named feature → point (the non-parcel branch of the resolve funnel).

For places the parcel funnel can't anchor (rivers, water bodies, landforms), GNIS gives
a **stable identity** (`gaz_id`) plus a representative point. Queries the USGS National
Map *geonames* ArcGIS service (`settings.gnis_url`) — free, no key, US public domain —
across the configured layers (default hydrographic: Streams, Other Hydrographic). Reuses
the shared connector cache against the POI cache root; fields are read by name. The
service repeats a feature across counties, so the first match (deduped on `gaz_id`) wins.
"""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.connectors import cached_get
from bosc.logging import get_logger

log = get_logger(__name__)

_CONNECTOR = "gnis"


class GnisFeature(BaseModel):
    """One GNIS named feature: its stable id, class, county, and a representative point."""

    model_config = ConfigDict(extra="forbid")

    gnis_id: int
    name: str
    feature_class: str | None
    county: str | None
    state: str | None
    lon: float
    lat: float
    source: str = "USGS GNIS (National Map geonames)"

    @property
    def key(self) -> str:
        """The canonical identity key for a non-parcel place (stable across re-pulls)."""
        return f"gnis-{self.gnis_id}"


def find_feature(
    name: str,
    *,
    state: str | None = None,
    layers: list[int] | None = None,
    settings: Settings | None = None,
) -> GnisFeature | None:
    """The first GNIS feature named ``name`` in ``state`` across the configured layers."""
    settings = settings or get_settings()
    state = state or settings.gnis_default_state
    layers = layers if layers is not None else list(settings.gnis_layers)
    safe = name.replace("'", "''")

    for layer in layers:
        params = {"layer": layer, "name": name, "state": state}

        def fetch(layer: int = layer) -> Any:
            log.info("gnis.fetch", name=name, state=state, layer=layer)
            resp = httpx.get(
                f"{settings.gnis_url}/{layer}/query",
                params={
                    "where": f"gaz_name='{safe}' AND state_alpha='{state}'",
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "json",
                },
                timeout=settings.poi_request_timeout_s,
            )
            resp.raise_for_status()
            return resp.json()

        payload = cast(
            "dict[str, Any]",
            cached_get(
                _CONNECTOR,
                params,
                fetch,
                cache_dir=settings.poi_cache_dir,
                offline=settings.poi_offline,
                fixtures_dir=settings.poi_fixtures_dir,
            ),
        )
        feature = _parse(payload, name=name, state=state)
        if feature is not None:
            return feature
    return None


def _parse(payload: dict[str, Any], *, name: str, state: str) -> GnisFeature | None:
    features = payload.get("features") or []
    if not features:
        return None
    attrs = features[0].get("attributes") or {}
    point = _rep_point(features[0].get("geometry") or {})
    gid = attrs.get("gaz_id")
    if point is None or gid is None:
        return None
    return GnisFeature(
        gnis_id=int(gid),
        name=str(attrs.get("gaz_name") or name),
        feature_class=_s(attrs.get("gaz_featureclass")),
        county=_s(attrs.get("county_name")),
        state=_s(attrs.get("state_alpha")) or state,
        lon=point[0],
        lat=point[1],
    )


def _rep_point(geom: dict[str, Any]) -> tuple[float, float] | None:
    """A single representative (lon, lat) from any Esri geometry (point / multipoint / …)."""
    if geom.get("x") is not None and geom.get("y") is not None:
        return (float(geom["x"]), float(geom["y"]))
    for key in ("points",):
        seq = geom.get(key)
        if seq:
            return (float(seq[0][0]), float(seq[0][1]))
    for key in ("paths", "rings"):
        seq = geom.get(key)
        if seq and seq[0]:
            return (float(seq[0][0][0]), float(seq[0][0][1]))
    return None


def _s(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
