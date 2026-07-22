"""Data-driven discharge routing for the Lima loop.

Loads ``data/reference/hydrology/routing.yaml`` into a :class:`RoutingTable`. Two
flows are modeled (see the YAML header):

* ``wwtp_receiving`` — which receiving stream each county WWTP discharges to (the
  assimilative-screen denominator). This replaces the dict that used to be
  hardcoded in :mod:`watermark.hydrology.balance`.
* ``bosc_routing`` — where the BOSC campus sends its own wastewater, by forcemain.
  Every route carries a ``status`` of ``confirmed`` (document/plan-cited) or
  ``theorized`` (an unconfirmed lead). **Only confirmed routes feed the balance**;
  the theorized "FM-3 to Shawnee II" lead is surfaced as a caveat and held out, so
  "Shawnee II has no known routing" is structural rather than assumed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.sites import is_reference_site

RouteStatus = Literal["confirmed", "theorized"]
Confidence = Literal["high", "medium", "low"]


class Route(BaseModel):
    """One WWTP -> receiving-stream route, with the plant's permitted design flow."""

    model_config = ConfigDict(extra="forbid")

    receiving_water: str | None = None
    # Permitted average design flow (MGD) — the structured, document-cited discharge
    # magnitude the assimilative screen uses (WS-22, issue 1622). ``None`` ⇒ the balance
    # falls back to the first ``N MGD`` token in the watch-items summary prose.
    design_flow_mgd: float | None = None
    status: RouteStatus = "confirmed"
    confidence: Confidence = "high"
    citation: str | None = None


class BoscRoute(BaseModel):
    """Where the BOSC campus sends wastewater, via one forcemain, to one or more receivers."""

    model_config = ConfigDict(extra="forbid")

    via: str  # forcemain id (bosc-fm1, bosc-fm2, theorized-fm3-shawnee-ii)
    to: list[str]  # receiver node ids
    # Permitted industrial discharge (MGD) carried by this forcemain, when documented —
    # the structured source the campus node reads for its FM discharge (WS-22, issue 1622).
    design_flow_mgd: float | None = None
    status: RouteStatus
    confidence: Confidence = "medium"
    citation: str | None = None


class RoutingTable(BaseModel):
    """The committed routing for the loop: WWTP->stream + BOSC->WWTP forcemains."""

    model_config = ConfigDict(extra="forbid")

    wwtp_receiving: dict[str, Route] = {}
    bosc_routing: list[BoscRoute] = []

    def receiving_for(self, node_id: str) -> tuple[str | None, str]:
        """``(receiving_water, citation)`` for a WWTP node, or ``(None, "")`` if unrouted."""
        route = self.wwtp_receiving.get(node_id)
        if route is None:
            return None, ""
        return route.receiving_water, (route.citation or "")

    def design_flow_for(self, node_id: str) -> float | None:
        """The WWTP's permitted design flow (MGD), or ``None`` if not curated here.

        ``None`` ⇒ the balance falls back to parsing the watch-items summary prose. This is
        the structured analog of the ECHO ``design_flow_mgd`` column (WS-22, issue 1622)."""
        route = self.wwtp_receiving.get(node_id)
        return route.design_flow_mgd if route is not None else None

    def forcemain_design_flow(self, via: str) -> float | None:
        """The industrial discharge (MGD) documented for a campus forcemain, or ``None``."""
        for route in self.bosc_routing:
            if route.via == via and route.design_flow_mgd is not None:
                return route.design_flow_mgd
        return None

    def confirmed_bosc_routes(self) -> list[BoscRoute]:
        return [r for r in self.bosc_routing if r.status == "confirmed"]

    def theorized_bosc_routes(self) -> list[BoscRoute]:
        return [r for r in self.bosc_routing if r.status == "theorized"]

    def campus_receivers(self) -> dict[str, str]:
        """Map each *confirmed* campus-receiver node id to the forcemain that reaches it.

        e.g. ``{"watch-lima-fm2-terminus": "bosc-fm2",
        "watch-american-bath-wwtp": "bosc-fm1", "watch-american-ii-wwtp": "bosc-fm1"}``.
        Plants absent from this map (Shawnee II — FM-3 theorized) receive no campus flow.
        """
        out: dict[str, str] = {}
        for route in self.confirmed_bosc_routes():
            for node_id in route.to:
                out.setdefault(node_id, route.via)
        return out


def _routing_path(settings: Settings) -> Path:
    """The active site's discharge-routing table.

    The reference build (Lima) reads the flat ``reference/hydrology/routing.yaml`` (its
    forcemain / WWTP→stream graph); a sibling site reads its own
    ``reference/hydrology/<slug>/routing.yaml`` and never inherits Lima's BOSC forcemain
    routes (#829). Absent ⇒ :func:`load_routing` returns ``None`` and the balance falls
    back to the profile ``plant_receiving`` for receiving-water resolution.
    """
    base = settings.data_dir / "reference" / "hydrology"
    if is_reference_site(settings.site):
        return base / "routing.yaml"
    return base / settings.site / "routing.yaml"


def load_routing(*, settings: Settings | None = None) -> RoutingTable | None:
    """Load the active site's committed routing table, or ``None`` if the file is absent."""
    settings = settings or get_settings()
    path = _routing_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RoutingTable(
        wwtp_receiving={
            str(k): Route.model_validate(v) for k, v in (data.get("wwtp_receiving") or {}).items()
        },
        bosc_routing=[BoscRoute.model_validate(r) for r in (data.get("bosc_routing") or [])],
    )
