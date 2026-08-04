"""Core provenance + water-balance models for the Tier-0 hydrology subsystem.

The cornerstone is :class:`ProvenancedValue`: every number that enters the water
balance carries where it came from, so a result is self-auditing. The ``source``
tag maps onto the dossier's evidence discipline:

    document, connector  ->  [verified]   (read from a record or a live gauge)
    assumption, derived  ->  [inference]  (asserted, or computed from the above)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from watermark.provenance import SourceKind as SourceKind
from watermark.provenance import source_is_verified

NodeRole = Literal["abstraction", "demand", "wwtp", "receiving"]


def _resolve_bounds(
    value: float,
    low: float | None,
    high: float | None,
    plus_minus: float | None,
    rel_uncertainty: float | None,
) -> tuple[float | None, float | None]:
    """Reduce the three range spellings to a single absolute ``(low, high)`` pair.

    A caller gives **at most one** of: explicit ``low``/``high`` absolute bounds, a
    symmetric ``plus_minus`` spread, or a ``rel_uncertainty`` fraction (± that share of
    ``value``). The stored form is always absolute bounds — the shape the uncertainty
    engine (#271) consumes — so the convenience spellings are computed here, never kept.
    """
    forms = [
        ("low/high", low is not None or high is not None),
        ("plus_minus", plus_minus is not None),
        ("rel_uncertainty", rel_uncertainty is not None),
    ]
    if sum(1 for _, present in forms if present) > 1:
        given = ", ".join(name for name, present in forms if present)
        raise ValueError(f"give at most one range spelling; got {given}")
    if plus_minus is not None:
        if plus_minus < 0:
            raise ValueError(f"plus_minus must be non-negative, got {plus_minus}")
        return value - plus_minus, value + plus_minus
    if rel_uncertainty is not None:
        if rel_uncertainty < 0:
            raise ValueError(f"rel_uncertainty must be non-negative, got {rel_uncertainty}")
        spread = abs(value) * rel_uncertainty
        return value - spread, value + spread
    return low, high


class ProvenancedValue(BaseModel):
    """A single numeric quantity tagged with its provenance.

    Construct via the classmethods (:meth:`from_document`, :meth:`from_connector`,
    :meth:`assume`, :meth:`derived`) so the ``source`` tag is never forgotten.

    A **measured or derived estimate** may also carry a quantitative uncertainty range
    (#760): optional absolute ``low``/``high`` bounds around the central ``value``,
    *orthogonal* to the qualitative ``confidence`` enum. The convention: a document- or
    connector-verbatim figure is a single value (no band); an estimate whose honest
    representation is "226 ± ~35 ac" carries ``low``/``high`` so downstream consumers
    (the bundle, the frontend, the Monte-Carlo engine #271) see the spread as data, not
    prose buried in the citation. The estimate constructors (:meth:`derived`,
    :meth:`assume`, :meth:`from_reference`) take the range inline; :meth:`with_range`
    attaches one to any value (e.g. a document-anchored central with a derived band).
    """

    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str  # "cfs" | "MGD" | "sqmi" | "acre" | "in" | ...
    source: SourceKind
    citation: str | None = None  # rel_path, geojson feature id, NWIS site, or rationale
    confidence: Literal["high", "medium", "low"] = "medium"
    asof: str | None = None  # ISO datetime, for connector (live) values
    # Quantitative uncertainty band (#760), distinct from the qualitative `confidence`.
    # Absolute bounds, either/both optional; `low <= value <= high` where present.
    low: float | None = None
    high: float | None = None

    @model_validator(mode="after")
    def _check_range(self) -> ProvenancedValue:
        if self.low is not None and self.low > self.value:
            raise ValueError(f"range low {self.low} exceeds value {self.value}")
        if self.high is not None and self.high < self.value:
            raise ValueError(f"range high {self.high} is below value {self.value}")
        return self

    @property
    def has_range(self) -> bool:
        """True when a quantitative uncertainty band is attached (either bound present)."""
        return self.low is not None or self.high is not None

    @property
    def low_or_value(self) -> float:
        """The lower bound, or the central ``value`` when no low bound is set."""
        return self.value if self.low is None else self.low

    @property
    def high_or_value(self) -> float:
        """The upper bound, or the central ``value`` when no high bound is set."""
        return self.value if self.high is None else self.high

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
    def from_reference(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "medium",
        asof: str | None = None,
        low: float | None = None,
        high: float | None = None,
        plus_minus: float | None = None,
        rel_uncertainty: float | None = None,
    ) -> ProvenancedValue:
        """A value from committed authoritative external reference data.

        Distinct from a record about *this* facility (``document``) and from an
        asserted modeling input (``assumption``): a published spec / table vendored
        under ``data/reference`` (e.g. an accelerator datasheet). Cite the file. May
        carry a range (see the class docstring) when the reference states a band, and
        an optional ``asof`` when the reference figure is anchored to a dated instrument
        (e.g. an agreement's effective date).
        """
        lo, hi = _resolve_bounds(value, low, high, plus_minus, rel_uncertainty)
        return cls(
            value=value,
            unit=unit,
            source="reference",
            citation=citation,
            confidence=confidence,
            asof=asof,
            low=lo,
            high=hi,
        )

    @classmethod
    def assume(
        cls,
        value: float,
        unit: str,
        why: str,
        *,
        confidence: Literal["high", "medium", "low"] = "low",
        low: float | None = None,
        high: float | None = None,
        plus_minus: float | None = None,
        rel_uncertainty: float | None = None,
    ) -> ProvenancedValue:
        """An asserted value not derivable from any record (state the rationale).

        Takes an optional range (see the class docstring) — a banded assumption (e.g. a
        PUE assumed to lie in 1.2-1.43) is a single central value carrying its spread.
        """
        lo, hi = _resolve_bounds(value, low, high, plus_minus, rel_uncertainty)
        return cls(
            value=value,
            unit=unit,
            source="assumption",
            citation=why,
            confidence=confidence,
            low=lo,
            high=hi,
        )

    @classmethod
    def derived(
        cls,
        value: float,
        unit: str,
        citation: str,
        *,
        confidence: Literal["high", "medium", "low"] = "medium",
        asof: str | None = None,
        low: float | None = None,
        high: float | None = None,
        plus_minus: float | None = None,
        rel_uncertainty: float | None = None,
    ) -> ProvenancedValue:
        """A value computed from other provenanced inputs (cite the derivation).

        Takes an optional range (see the class docstring): a derived estimate whose
        method carries uncertainty (e.g. a raster-segmented area ±20%) is the natural
        home of the range shape. ``asof`` dates a derivation whose *inputs* are dated —
        a statistic reduced from a live gauge window is only true as of that window, and
        omitting the date was how a replayed fixture read as current (WS-21, #1621).
        """
        lo, hi = _resolve_bounds(value, low, high, plus_minus, rel_uncertainty)
        return cls(
            value=value,
            unit=unit,
            source="derived",
            citation=citation,
            confidence=confidence,
            asof=asof,
            low=lo,
            high=hi,
        )

    def with_range(
        self,
        *,
        low: float | None = None,
        high: float | None = None,
        plus_minus: float | None = None,
        rel_uncertainty: float | None = None,
    ) -> ProvenancedValue:
        """A copy of this value with a quantitative uncertainty band attached.

        The escape hatch for a ``document``/``connector`` central that legitimately
        carries a band (a measured figure with method/instrument uncertainty, e.g. a
        document-anchored IT load with a derived N+1 bracket) — the verbatim
        constructors stay range-free so a plain figure never sprouts a spurious band.
        """
        lo, hi = _resolve_bounds(self.value, low, high, plus_minus, rel_uncertainty)
        # Rebuild through validation — model_copy(update=...) would bypass _check_range and
        # let an invalid low>value / high<value band reach the copy.
        return self.model_validate({**self.model_dump(), "low": lo, "high": hi})

    @property
    def verified(self) -> bool:
        """True when the value is grounded in a record or a live gauge.

        ``reference`` (a vendored published spec) is authoritative but is *not* a
        record about this facility, so it is not "verified" in the dossier sense.
        """
        return source_is_verified(self.source)

    def __str__(self) -> str:
        tag = {
            "document": "doc",
            "connector": "live",
            "reference": "ref",
            "assumption": "assume",
            "derived": "calc",
        }[self.source]
        core = f"{self.value:,.2f}"
        if self.has_range:
            lo = "?" if self.low is None else f"{self.low:,.2f}"
            hi = "?" if self.high is None else f"{self.high:,.2f}"
            core += f" ({lo}-{hi})"
        return f"{core} {self.unit} [{tag}]"


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
    """One node's known flow terms — an *inventory*, not a closed per-node balance.

    Terms are optional and a node carries only what's known/relevant: an abstraction
    node has ``inflow`` (live river-flow context, not a metered withdrawal); a WWTP node
    has ``return_flow``; the campus demand node has ``return_flow`` + ``consumptive_use``.
    No assembled node carries every term — the intake *withdrawal* that would tie
    source -> use -> discharge into a closed per-node loop is not quantified in the corpus
    — so this model does **not** assert ``inflow + stormwater = return + consumptive`` and
    must not be read as a self-closing balance. The genuine, order-invariant
    mass-conservation check runs downstream on the accumulated network:
    :attr:`RoutedNetwork.closes`, which routes these ``return_flow`` terms through the
    cited confluence graph and is exercised in the tests. All flows are in **cfs**.
    ``stormwater`` is the Increment-2 seam: a cited zero today, filled by the SCS-CN
    solver later.
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
    """The assembled source -> use -> WWTP -> receiving loop as a per-node flow *inventory*.

    Each :class:`WaterBalanceNode` carries only its known terms (see that class); no node
    carries the full ``inflow``/``return``/``consumptive`` set, so this container is an
    inventory of grounded discharges, not a self-closing balance. Mass conservation is
    checked downstream, where these ``return_flow`` terms are routed through the cited
    confluence graph: :attr:`RoutedNetwork.closes` (built by
    :func:`watermark.hydrology.network.route_network`, surfaced as the
    ``mass-balance-closes`` finding, and exercised in the tests).

    A per-node ``closes()`` once lived here; it was vacuous — it ``continue``\\ d on every
    node because none held both ``inflow`` and ``return_flow``, so it returned ``True``
    unconditionally and could never fail — and was removed (WS-05, #1605) in favor of the
    routed check. Don't reintroduce a self-test that cannot fail.
    """

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
