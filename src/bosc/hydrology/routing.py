"""Data-driven discharge routing for the Lima loop.

Loads ``data/reference/hydrology/routing.yaml`` into a :class:`RoutingTable`. Two
flows are modeled (see the YAML header):

* ``wwtp_receiving`` — which receiving stream each county WWTP discharges to (the
  assimilative-screen denominator). This replaces the dict that used to be
  hardcoded in :mod:`bosc.hydrology.balance`.
* ``bosc_routing`` — where the BOSC campus sends its own wastewater, by forcemain.
  Every route carries a ``status`` of ``confirmed`` (document/plan-cited) or
  ``theorized`` (an unconfirmed lead). **Only confirmed routes feed the balance**;
  the theorized "FM-3 to Shawnee II" lead is surfaced as a caveat and held out, so
  "Shawnee II has no known routing" is structural rather than assumed.
"""

from __future__ import annotations

from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings

RouteStatus = Literal["confirmed", "theorized"]
Confidence = Literal["high", "medium", "low"]


class Route(BaseModel):
    """One WWTP -> receiving-stream route."""

    model_config = ConfigDict(extra="forbid")

    receiving_water: str | None = None
    status: RouteStatus = "confirmed"
    confidence: Confidence = "high"
    citation: str | None = None


class BoscRoute(BaseModel):
    """Where the BOSC campus sends wastewater, via one forcemain, to one or more receivers."""

    model_config = ConfigDict(extra="forbid")

    via: str  # forcemain id (bosc-fm1, bosc-fm2, theorized-fm3-shawnee-ii)
    to: list[str]  # receiver node ids
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


def load_routing(*, settings: Settings | None = None) -> RoutingTable | None:
    """Load the committed routing table, or ``None`` if the file is absent."""
    settings = settings or get_settings()
    path = settings.data_dir / "reference" / "hydrology" / "routing.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RoutingTable(
        wwtp_receiving={
            str(k): Route.model_validate(v) for k, v in (data.get("wwtp_receiving") or {}).items()
        },
        bosc_routing=[BoscRoute.model_validate(r) for r in (data.get("bosc_routing") or [])],
    )
