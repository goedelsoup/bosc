"""Typed models for the Tier-0 hydrology subsystem.

Unlike the extraction models in :mod:`bosc.models` (``extra="allow"`` because the
LLM emits unanticipated keys), these are **computed by our own code**, so they use
``extra="forbid"`` to catch bugs early.

The cornerstone is :class:`ProvenancedValue`: every number that enters the water
balance carries where it came from, so a result is self-auditing. The ``source``
tag maps onto the dossier's evidence discipline:

    document, connector  ->  [verified]   (read from a record or a live gauge)
    assumption, derived  ->  [inference]  (asserted, or computed from the above)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

SourceKind = Literal["document", "connector", "assumption", "derived"]
NodeRole = Literal["abstraction", "demand", "wwtp", "receiving"]
Flag = Literal["ok", "tight", "violation"]


class ProvenancedValue(BaseModel):
    """A single numeric quantity tagged with its provenance.

    Construct via the classmethods (:meth:`from_document`, :meth:`from_connector`,
    :meth:`assume`, :meth:`derived`) so the ``source`` tag is never forgotten.
    """

    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str  # "cfs" | "MGD" | "sqmi" | "acre" | "in" | ...
    source: SourceKind
    citation: str | None = None  # rel_path, geojson feature id, NWIS site, or rationale
    confidence: Literal["high", "medium", "low"] = "medium"
    asof: str | None = None  # ISO datetime, for connector (live) values

    @classmethod
    def from_document(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> ProvenancedValue:
        """A value read from a source record (cite the file / feature id)."""
        return cls(
            value=value, unit=unit, source="document", citation=citation, confidence=confidence
        )

    @classmethod
    def from_connector(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        asof: str | None = None,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> ProvenancedValue:
        """A value fetched live from an external service (cite the site/endpoint)."""
        return cls(
            value=value,
            unit=unit,
            source="connector",
            citation=citation,
            confidence=confidence,
            asof=asof,
        )

    @classmethod
    def assume(
        cls,
        value: float,
        unit: str,
        why: str,
        *,
        confidence: Literal["high", "medium", "low"] = "low",
    ) -> ProvenancedValue:
        """An asserted value not derivable from any record (state the rationale)."""
        return cls(value=value, unit=unit, source="assumption", citation=why, confidence=confidence)

    @classmethod
    def derived(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "medium",
    ) -> ProvenancedValue:
        """A value computed from other provenanced inputs (cite the derivation)."""
        return cls(
            value=value, unit=unit, source="derived", citation=citation, confidence=confidence
        )

    @property
    def verified(self) -> bool:
        """True when the value is grounded in a record or a live gauge."""
        return self.source in ("document", "connector")

    def __str__(self) -> str:
        tag = {"document": "doc", "connector": "live", "assumption": "assume", "derived": "calc"}[
            self.source
        ]
        return f"{self.value:,.2f} {self.unit} [{tag}]"


class Node(BaseModel):
    """A point in the municipal water loop (a plant, a demand center, a stream)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    role: NodeRole
    receiving_water: str | None = None  # for wwtp nodes: where the discharge goes
    lat: float | None = None
    lon: float | None = None


class WaterBalanceNode(BaseModel):
    """One node's flow terms. Conservation: inflow + stormwater = return + consumptive.

    Terms are optional — a node carries only what's known/relevant (an abstraction
    node has ``inflow``; a demand node has ``consumptive_use`` + ``return_flow``).
    All flows are in **cfs**. ``stormwater`` is the Increment-2 seam: a cited zero
    today, filled by the SCS-CN solver later.
    """

    model_config = ConfigDict(extra="forbid")

    node: Node
    inflow: ProvenancedValue | None = None
    consumptive_use: ProvenancedValue | None = None
    return_flow: ProvenancedValue | None = None
    stormwater: ProvenancedValue | None = None

    def all_values(self) -> list[ProvenancedValue]:
        return [
            v for v in (self.inflow, self.consumptive_use, self.return_flow, self.stormwater) if v
        ]


class WaterBalance(BaseModel):
    """The assembled source -> use -> WWTP -> receiving loop."""

    model_config = ConfigDict(extra="forbid")

    nodes: list[WaterBalanceNode]
    tier: Literal["tier0"] = "tier0"
    warnings: list[str] = []

    def node(self, node_id: str) -> WaterBalanceNode | None:
        return next((n for n in self.nodes if n.node.id == node_id), None)

    def by_role(self, role: NodeRole) -> list[WaterBalanceNode]:
        return [n for n in self.nodes if n.node.role == role]

    def all_values(self) -> list[ProvenancedValue]:
        return [v for n in self.nodes for v in n.all_values()]

    def closes(self, *, rel_tol: float = 0.05) -> bool:
        """True if, where all terms are present, each node conserves mass within tol."""
        for n in self.nodes:
            if n.inflow is None or n.return_flow is None:
                continue
            storm = n.stormwater.value if n.stormwater else 0.0
            consume = n.consumptive_use.value if n.consumptive_use else 0.0
            lhs = n.inflow.value + storm
            rhs = n.return_flow.value + consume
            if abs(lhs - rhs) > max(0.01, abs(lhs) * rel_tol):
                return False
        return True


class AssimilativeCheck(BaseModel):
    """Low-flow dilution of one discharge into its receiving water.

    The dilution ratio is ``(design_low_flow + upstream_returns) / discharge``.
    A screening heuristic flags the result; it is **not** a permit determination.
    """

    model_config = ConfigDict(extra="forbid")

    receiving_water: str
    discharger: str
    design_low_flow: ProvenancedValue  # the 7Q10 (cited)
    discharge: ProvenancedValue
    upstream_returns: ProvenancedValue | None = None
    dilution_ratio: float
    flag: Flag
    detail: str


# Screening thresholds on the dilution ratio (stream low-flow : effluent).
# Below 1, the effluent dominates the stream at design low flow — effectively
# undiluted. These are coarse screening bands, not regulatory mixing-zone rules.
DILUTION_VIOLATION = 1.0
DILUTION_TIGHT = 10.0


class DesignStorm(BaseModel):
    """A design rainfall event (return period x duration -> depth)."""

    model_config = ConfigDict(extra="forbid")

    return_period_yr: int
    duration_hr: float
    depth: ProvenancedValue  # inches, source typically connector (NOAA Atlas-14)


class Hydrograph(BaseModel):
    """A Tier-0 runoff hydrograph (SCS unit-hydrograph convolution)."""

    model_config = ConfigDict(extra="forbid")

    times_hr: list[float]
    flows_cfs: list[float]
    peak_cfs: float
    time_to_peak_hr: float
    volume_acft: float
    runoff_depth_in: float
    curve_number: float
    tier: Literal["tier0"] = "tier0"


class StormRunoff(BaseModel):
    """Pre- vs post-development runoff for a design storm over one footprint.

    The headline stormwater impact: paving a pervious footprint raises the curve
    number, so the same storm yields a higher peak and more volume. The extra
    volume is the screening-grade detention deficit (the volume a basin must hold
    to keep post-development discharge at the pre-development rate).
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    area: ProvenancedValue  # acres
    hsg: ProvenancedValue  # hydrologic soil group as a coded value (A=1..D=4) + citation
    storm: DesignStorm
    pre: Hydrograph
    post: Hydrograph

    @property
    def peak_increase_cfs(self) -> float:
        return self.post.peak_cfs - self.pre.peak_cfs

    @property
    def volume_increase_acft(self) -> float:
        return self.post.volume_acft - self.pre.volume_acft


@dataclass(frozen=True)
class HydroFinding:
    """One hydrology observation. Mirrors :class:`bosc.pipeline.analyze.Finding`."""

    subject: str
    check: str
    ok: bool
    detail: str

    def __str__(self) -> str:
        mark = "OK " if self.ok else "XX "
        return f"{mark} [{self.check}] {self.subject}: {self.detail}"
