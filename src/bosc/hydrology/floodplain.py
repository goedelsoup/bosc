"""Campus footprint vs the FEMA floodplain — a committed, dossier-ready finding.

The stormwater analysis cares whether the data-center footprint sits in (or beside)
the FEMA Special Flood Hazard Area. That is a *spatial* question against the DFIRM
floodzone layer (:mod:`bosc.hydrology.connectors.lima_gis`), so — like the live GIS
pulls — the answer is computed once and committed to
``data/reference/hydrology/campus-floodzone.yaml``; the dossier reads that file so
``render_report`` stays offline-deterministic.

Mirrors :mod:`bosc.hydrology.maumee`: a committed, cited finding is the grounded
source; the renderer never hits the network.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings

if TYPE_CHECKING:
    from bosc.hydrology.connectors.lima_gis import FloodZone


def _label(fld_zone: str | None, subtype: str | None) -> str:
    """A compact zone label, e.g. ``AE`` or ``AE (FLOODWAY)``."""
    z = (fld_zone or "?").strip()
    sub = (subtype or "").strip()
    return f"{z} ({sub})" if sub else z


class CampusFloodzone(BaseModel):
    """Whether the recorded campus parcels lie in — or near — the FEMA floodplain."""

    model_config = ConfigDict(extra="forbid")

    footprint: str
    in_parcels_zones: list[str]  # distinct SFHA zones intersecting the parcels (empty = none)
    nearby_buffer_m: int
    nearby_zones: list[str]  # distinct SFHA zones within the buffer of the parcels
    firm: str  # the FEMA DFIRM / FIS citation
    citation: str

    @property
    def in_floodplain(self) -> bool:
        return bool(self.in_parcels_zones)


def _reference_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "campus-floodzone.yaml"


def load_campus_floodzone(*, settings: Settings | None = None) -> CampusFloodzone | None:
    """Load the committed campus-floodzone finding, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CampusFloodzone.model_validate(data)


class WwtpFloodzone(BaseModel):
    """A WWTP discharge point's FEMA flood exposure (point-in-polygon + buffered)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    npdes: str
    receiving_water: str | None = None
    lat: float
    lon: float
    in_sfha_zones: list[str]  # SFHA zones at the facility point (empty = not in SFHA)
    zones_by_buffer: dict[int, list[str]]  # buffer metres -> distinct SFHA zone labels

    @property
    def in_sfha(self) -> bool:
        return bool(self.in_sfha_zones)

    def nearest_buffer(self, *, contains: str = "") -> int | None:
        """Smallest buffer (m) at which a zone (optionally matching ``contains``) appears."""
        for b in sorted(self.zones_by_buffer):
            if any(contains.upper() in z.upper() for z in self.zones_by_buffer[b]):
                return b
        return None


class WwtpFloodzones(BaseModel):
    """The committed WWTP-outfall flood-exposure finding."""

    model_config = ConfigDict(extra="forbid")

    note: str
    citation: str
    plants: list[WwtpFloodzone]


def load_wwtp_floodzones(*, settings: Settings | None = None) -> WwtpFloodzones | None:
    """Load the committed WWTP-outfall flood-exposure finding, or ``None`` if absent."""
    settings = settings or get_settings()
    path = settings.data_dir / "reference" / "hydrology" / "wwtp-floodzone.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plants = [
        WwtpFloodzone(
            name=p["name"],
            npdes=p["npdes"],
            receiving_water=p.get("receiving_water"),
            lat=float(p["lat"]),
            lon=float(p["lon"]),
            in_sfha_zones=list(p.get("in_sfha_zones") or []),
            zones_by_buffer={int(k): list(v) for k, v in (p.get("zones_by_buffer") or {}).items()},
        )
        for p in (data.get("plants") or [])
    ]
    return WwtpFloodzones(
        note=data.get("note", ""), citation=data.get("citation", ""), plants=plants
    )


def write_campus_floodzone(
    in_parcels: list[FloodZone],
    nearby: list[FloodZone],
    *,
    buffer_m: int,
    footprint: str,
    settings: Settings | None = None,
) -> Path:
    """Write the campus floodplain-proximity finding from connector results."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)

    def zones(fzs: list[FloodZone]) -> list[str]:
        return sorted({_label(f.fld_zone, f.zone_subtype) for f in fzs})

    firm = next((f.source_cit for f in (*in_parcels, *nearby) if f.source_cit), "FEMA DFIRM 39003C")
    doc: dict[str, Any] = {
        "footprint": footprint,
        "in_parcels_zones": zones(in_parcels),
        "nearby_buffer_m": buffer_m,
        "nearby_zones": zones(nearby),
        "firm": str(firm),
        "citation": (
            "City of Lima GIS Floodzone layer (FEMA DFIRM panel 39003C) "
            "intersected with the recorded Bistrozzi parcel footprints "
            "(data/reference/periplus/bosc-parcels.geojson). source: connector."
        ),
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
