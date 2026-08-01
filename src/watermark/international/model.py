"""The international data-center **candidates register** — a distinct artifact class (#1388/#1393,
epic #1387).

The domestic funnel is records-first: a council resolution, a deed, an NPDES permit prove a
project exists, and imagery only monitors what the record already pinned
(:class:`watermark.facility.candidate.DataCenterCandidate` is that funnel's structured record).
Abroad, that records channel mostly does not exist. This module is the other direction's
artifact: **open registers and, later, pixels are the discovery channel**, and what comes out is
explicitly a *candidate*, never a pinned facility.

Three properties are enforced here rather than left to reviewer discipline:

* **Nothing in this module can be ``[verified]``.** :attr:`Candidate.tag` is *derived* from
  :class:`DetectionBasis`, and no basis maps to ``verified``. A register agreeing with another
  register is ``[reference]``; a screen or a vision adjudication is ``[inference]``. Only an
  instrument about *this* facility could make it ``[verified]``, and by construction we hold none.
* **Operator attribution is cited or it is ``[open]``.** Coordinates are unambiguous;
  *attribution* is the risk (the epic's disambiguation analog). :class:`OperatorAttribution`
  refuses to carry a name without a citation, so "this is Google's" can never be asserted by a
  model default.
* **Negative results are results.** An AOI that was swept and yielded nothing is recorded as
  :class:`AoiResult` with its zero counts, not omitted — omission would read as "never looked".

This register is **never merged** with the domestic discover-and-pin registers, and it mints no
``SiteProfile``: a watershed-point site is a story-driven decision, not a detection.
"""

from __future__ import annotations

import math
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from watermark.provenance import EvidenceTag, evidence_tag

# The tag every entry in this register renders as — the three-tag subset that excludes
# ``verified``, plus ``open`` for an unattributed claim. Spelled out as a type so a reader of the
# feed contract can see the exclusion, not just read about it in prose.
CandidateTag = Literal["inference", "reference", "open"]


class PriorSource(StrEnum):
    """Where a prior observation came from — the internationalized source ladder (#1390).

    Each value is an *independent* channel: corroboration counts distinct sources, so two OSM
    nodes on the same campus are one source, while an OSM node plus a PeeringDB facility are two.
    """

    PEERINGDB = "peeringdb"
    OSM = "osm"
    OPERATOR_DISCLOSURE = "operator_disclosure"
    NATIONAL_REGISTRY = "national_registry"
    TRADE_PRESS = "trade_press"


class DetectionBasis(StrEnum):
    """What actually grounds a candidate — and therefore which tag it renders as.

    The ordering is the funnel's: ``priors_only`` is stage 1 (open registers), ``screened`` is
    stage 2 (footprint / substation-proximity / change detection, #1391), ``vision_adjudicated``
    is stage 3 (a ``FacilityDetection`` from adjudicated chips, #1392).

    The tag split is the load-bearing part. A ``priors_only`` entry is ``[reference]``: we are
    repeating what published registers say, and the honest citation is *to those registers*, not
    to a finding of ours. The moment we adjudicate anything ourselves — a screen or a vision
    read — the claim becomes **ours** and drops to ``[inference]``. It never rises: a detection
    is an inference about a place, and no amount of model confidence converts it into a record.
    """

    PRIORS_ONLY = "priors_only"
    SCREENED = "screened"
    VISION_ADJUDICATED = "vision_adjudicated"

    @property
    def tag(self) -> EvidenceTag:
        """This basis's evidence-discipline tag. Never ``verified`` — see the class docstring."""
        # `reference` for a published register we are relaying; `inference` (via the shared
        # `assumption`→inference mapping) for anything this platform adjudicated itself.
        return evidence_tag("reference" if self is DetectionBasis.PRIORS_ONLY else "assumption")


class CoolingType(StrEnum):
    """The cooling archetype a detection reads off the roof — the water thesis's foothold.

    Kept first-class per the epic's locked decision: the water question survives *inside* the
    detector as a field, not as the AOI selector. ``unknown`` is the honest default and the only
    value a ``priors_only`` entry can carry — no open register publishes cooling design.
    """

    EVAPORATIVE = "evaporative"  # cooling towers / wet plant — the water-intensive archetype
    DRY = "dry"  # air-cooled condensers / dry coolers
    CLOSED_LOOP = "closed_loop"  # sealed liquid loop, dry rejection
    HYBRID = "hybrid"  # adiabatic / switchable wet-dry
    SEAWATER = "seawater"  # once-through / district seawater cooling
    UNKNOWN = "unknown"


class Corroboration(StrEnum):
    """How many *independent* sources place a facility here."""

    SINGLE_SOURCE = "single_source"  # one register says so — a lead, not a corroborated candidate
    CORROBORATED = "corroborated"  # ≥2 independent sources agree on the location


def _slug(text: str, *, max_len: int = 72) -> str:
    """A stable, deterministic dedupe slug (local peer of ``facility.candidate._slug``)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "candidate"


class _DerivedFieldsAreRecomputed(BaseModel):
    """Base for the models that publish ``computed_field``s into the committed artifact.

    The derived values (``tag``, ``corroboration``, ``is_contested``, …) are serialized on
    purpose — the register YAML is read by people, and "corroboration: corroborated" beside the
    observations is worth more than making a reader count sources. But the models are
    ``extra="forbid"``, so a straight reload of what was written would fail on those very keys.

    They are therefore **dropped on input and recomputed**, which is also the right discipline:
    a derived field in a committed file is a rendering of the data, never an input to it. Someone
    who hand-edits ``tag: verified`` into the YAML changes nothing — the next load recomputes it
    from the basis, which is exactly what "nothing here can be [verified]" has to mean in
    practice.
    """

    @model_validator(mode="before")
    @classmethod
    def _drop_derived(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        derived = cls.model_computed_fields
        if not derived or not any(k in data for k in derived):
            return data
        return {k: v for k, v in data.items() if k not in derived}


class PriorObservation(BaseModel):
    """One open register's row about one location — the citable, re-pullable unit of evidence.

    Everything here is carried **verbatim from the register that published it**. ``operator`` is
    whatever that register states, un-normalized: collapsing "Equinix (Singapore) Pte Ltd" and
    "Equinix, Inc." would be *our* inference wearing the register's authority, and the whole point
    of keeping the raw rows is that a reader can see the two sources agree in their own words.

    ``license`` rides on every row rather than living only in the dataset README, so a downstream
    consumer of a single entry still knows the terms it is bound by (the #1390 license audit).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: PriorSource
    source_id: str  # the register's own stable key (PeeringDB fac id, OSM `node/123`)
    url: str  # the citable, re-pullable permalink for THIS row
    latitude: float
    longitude: float
    name: str | None = None
    operator: str | None = None  # verbatim; None when the register names none
    address: str | None = None
    country: str | None = None  # ISO 3166-1 alpha-2, as the register states it
    license: str  # the source's stated licence terms — travels with the row
    retrieved_at: str  # ISO date of the pull that produced this row
    # Register-specific capability signals, kept because they are the "capability first" driver
    # made concrete: a PeeringDB facility with networks and an exchange present is interconnected
    # infrastructure, not a name on a map. None where the register publishes no such count.
    network_count: int | None = None
    exchange_count: int | None = None


class CompetingClaim(BaseModel):
    """A *different* operator name, from a different source, for the same location."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: str
    citation: str
    source: PriorSource


def _same_operator(a: str, b: str) -> bool:
    """Whether two register spellings plausibly name the same operator.

    Deliberately conservative — containment after casefolding and stripping punctuation, so
    "Equinix, Inc." and "Equinix" agree while "Equinix, Inc." and "Axtel" do not. Anything
    cleverer (fuzzy ratios, corporate-family lookups) would start *resolving* disagreements, and
    a resolved disagreement is invisible; the whole point here is to keep it visible.
    """
    x, y = (re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip() for s in (a, b))
    return bool(x) and bool(y) and (x in y or y in x)


class OperatorAttribution(_DerivedFieldsAreRecomputed):
    """Who runs it — the field most likely to be wrong, so the one held hardest.

    A set ``operator`` MUST name the source that says so. There is no default that asserts a name,
    and no path that upgrades an attribution past ``[reference]``: an open register naming an
    operator is a published claim we are relaying, not a record we hold about the facility.

    When independent sources name **different** operators they land in :attr:`contested`, and the
    attribution reports itself as contested rather than quietly resolving to whichever source sits
    higher on the ladder. That silent resolution is a real hazard, not a hypothetical one: in the
    seeded register PeeringDB and OSM disagree about a Querétaro facility (Equinix vs. Axtel /
    Alestra) in a way that is probably an acquisition the two registers updated at different
    times — and "probably an acquisition" is precisely the kind of inference this platform does
    not get to make silently on a reader's behalf. Contested is **not** ``[open]``: the question
    was answered, twice, differently, and that is a more informative state than unanswered.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operator: str | None = None
    citation: str | None = None  # the URL / register row that states it
    source: PriorSource | None = None
    # Other cited names for the same place, from other sources. Never merged into `operator`.
    contested: list[CompetingClaim] = []

    @model_validator(mode="after")
    def _named_operators_are_cited(self) -> OperatorAttribution:
        if self.operator is None:
            if self.citation is not None or self.source is not None:
                raise ValueError(
                    "an open attribution (operator=None) carries no citation/source — the "
                    "question is unanswered, and a dangling citation implies it was answered"
                )
            if self.contested:
                raise ValueError(
                    "an open attribution cannot be contested — a competing claim IS a claim; "
                    "promote one to `operator` and leave the rest contesting it"
                )
        elif not self.citation or self.source is None:
            raise ValueError(
                f"attribution to {self.operator!r} needs both a citation and a source — "
                "operator attribution is cited or it is [open] (epic #1387)"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_contested(self) -> bool:
        """True when another source names a different operator for the same location."""
        return bool(self.contested)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tag(self) -> CandidateTag:
        """``[reference]`` when a source names the operator, ``[open]`` when none does.

        Contested does not change the tag — each competing name is still a cited published claim.
        What contested changes is whether a consumer may render the name *unqualified*, which is
        why :attr:`is_contested` is separate rather than folded in here.
        """
        return "open" if self.operator is None else "reference"


class Candidate(_DerivedFieldsAreRecomputed):
    """One international data-center candidate — a location, what grounds it, and who (if anyone
    citable) is said to run it.

    Deliberately *not* a :class:`~watermark.facility.candidate.DataCenterCandidate`: that model
    describes a project the domestic record already proved and carries the disclosed figures a
    promotion to a ``SiteFacility`` needs. This one describes a place open data points at. It
    holds no MW, no investment, no acreage — not because those are uninteresting but because
    nothing in this funnel can source them, and a field that exists invites a value that doesn't.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str  # stable dedupe identity, minted by `build_candidate`
    aoi: str  # the AOI slug this was found in (`aois.Aoi.slug`)
    country: str  # ISO 3166-1 alpha-2
    latitude: float
    longitude: float
    name: str | None = None  # the most complete name any source gives it
    attribution: OperatorAttribution = OperatorAttribution()
    basis: DetectionBasis = DetectionBasis.PRIORS_ONLY
    cooling: CoolingType = CoolingType.UNKNOWN
    observations: list[PriorObservation] = Field(min_length=1)
    # Imagery chain of custody: the STAC scene ids any adjudication read. Empty for every
    # `priors_only` entry — no pixels were looked at, which the basis already says.
    scene_ids: list[str] = []

    @model_validator(mode="after")
    def _adjudications_cite_their_scenes(self) -> Candidate:
        if self.basis is DetectionBasis.PRIORS_ONLY:
            if self.scene_ids:
                raise ValueError(
                    f"{self.key}: a priors-only candidate adjudicated no pixels, so it cannot "
                    "carry scene ids — set a detection basis if imagery was read"
                )
            if self.cooling is not CoolingType.UNKNOWN:
                raise ValueError(
                    f"{self.key}: cooling type is an imagery read; a priors-only candidate must "
                    "leave it `unknown` (no open register publishes cooling design)"
                )
        elif not self.scene_ids:
            raise ValueError(
                f"{self.key}: a {self.basis.value} candidate must record the scene ids it read, "
                "so every claim is re-pullable (epic #1387 chain of custody)"
            )
        return self

    # The three derived fields below are `computed_field`s, not plain properties, because the
    # bundle feed IS this model: a consumer that had to re-derive "is this corroborated" or "what
    # tag does this render as" from the raw observations would be re-implementing the discipline
    # on the far side of the contract, and the two copies would drift.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def sources(self) -> list[PriorSource]:
        """The distinct sources placing a facility here, in a stable order."""
        return sorted({o.source for o in self.observations})

    @computed_field  # type: ignore[prop-decorator]
    @property
    def corroboration(self) -> Corroboration:
        """Whether ≥2 *independent* sources agree — the seeded register's whole quality signal."""
        return Corroboration.CORROBORATED if len(self.sources) >= 2 else Corroboration.SINGLE_SOURCE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tag(self) -> EvidenceTag:
        """The evidence-discipline tag this candidate renders as. Never ``verified``."""
        return self.basis.tag


class AoiResult(_DerivedFieldsAreRecomputed):
    """One swept AOI's outcome — **including a null one**.

    A sweep that found nothing is a finding about that AOI, and the sweep skill requires it be
    recorded as such. Dropping empty AOIs would make the register read as though only the
    productive places had ever been looked at.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    slug: str
    label: str
    country: str
    bbox: tuple[float, float, float, float]  # (south, west, north, east), WGS84
    selection_basis: str  # why this AOI is in the sweep at all — stated, per the locked driver
    observations_by_source: dict[str, int] = {}  # raw prior rows pulled, per source
    candidate_count: int = 0
    corroborated_count: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_negative(self) -> bool:
        """True when the AOI was swept and produced no corroborated candidate."""
        return self.corroborated_count == 0


class SourceTerms(BaseModel):
    """One prior source's licence + attribution terms — the #1390 license audit, as data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: PriorSource
    label: str
    url: str
    license: str
    attribution: str  # the credit line a republisher owes
    notes: str | None = None


class CandidatesRegister(BaseModel):
    """The committed international candidates register.

    ``scope`` names which slice of the funnel produced it (``seeded`` for the priors-driven track,
    an AOI slug for a pilot discovery sweep) so the two never silently merge into one file whose
    entries have different provenance.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scope: str
    generated_at: str  # ISO date the assembly ran (caller-supplied; deterministic)
    corroboration_radius_m: float
    aois: list[AoiResult] = []
    sources: list[SourceTerms] = []
    candidates: list[Candidate] = []

    @property
    def corroborated(self) -> list[Candidate]:
        return [c for c in self.candidates if c.corroboration is Corroboration.CORROBORATED]

    @property
    def negative_aois(self) -> list[AoiResult]:
        return [a for a in self.aois if a.is_negative]


# --- geometry ------------------------------------------------------------------------------

# How close two registers must place a facility to be treated as describing the same one.
#
# A STATED SCREENING PARAMETER, not a measurement. The two priors geocode differently —
# PeeringDB carries a street address the operator supplied, OSM carries a node a mapper placed on
# (or near) the building — so exact agreement is not available and some tolerance is required.
# 250 m is roughly a large campus's own footprint: tight enough that two neighbouring facilities
# on the same industrial street stay distinct, loose enough to survive an address geocoded to a
# parcel centroid. Widening it would manufacture corroboration by merging distinct facilities,
# which is the failure mode that matters here.
CORROBORATION_RADIUS_M = 250.0

_EARTH_RADIUS_M = 6371008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def build_candidate(
    *,
    aoi: str,
    country: str,
    observations: list[PriorObservation],
    basis: DetectionBasis = DetectionBasis.PRIORS_ONLY,
    cooling: CoolingType = CoolingType.UNKNOWN,
    scene_ids: list[str] | None = None,
) -> Candidate:
    """Assemble a candidate from its corroborating observations.

    The derived fields are minted in code, never left to a caller (or a model) to supply: the
    position is the mean of the observations, the name is the longest one offered (the most
    specific), the dedupe key is a slug of that name plus the rounded position, and the
    attribution is taken from the **first source that names an operator**, in the ladder's own
    order — a self-maintained facility register outranks a crowd-sourced tag for *who runs it*,
    while neither outranks the other for *whether something is there*.

    The ladder picks which claim leads; it does **not** discard the others. Any source naming a
    materially different operator is kept as a :class:`CompetingClaim`, so a contested attribution
    reads as contested downstream instead of as a clean single answer.
    """
    if not observations:
        raise ValueError("a candidate needs at least one observation")
    lat = sum(o.latitude for o in observations) / len(observations)
    lon = sum(o.longitude for o in observations) / len(observations)
    names = [o.name for o in observations if o.name]
    name = max(names, key=len) if names else None

    stated = [o for o in observations if o.operator]
    stated.sort(key=lambda o: (_ATTRIBUTION_RANK.get(o.source, len(_ATTRIBUTION_LADDER)), o.url))
    attribution = OperatorAttribution()
    if stated and (lead := stated[0]).operator is not None:
        contested = [
            CompetingClaim(operator=o.operator, citation=o.url, source=o.source)
            for o in stated[1:]
            if o.operator is not None and not _same_operator(lead.operator, o.operator)
        ]
        attribution = OperatorAttribution(
            operator=lead.operator,
            citation=lead.url,
            source=lead.source,
            contested=contested,
        )

    return Candidate(
        key=_slug(f"{name or country}-{lat:.4f}-{lon:.4f}"),
        aoi=aoi,
        country=country,
        latitude=round(lat, 6),
        longitude=round(lon, 6),
        name=name,
        attribution=attribution,
        basis=basis,
        cooling=cooling,
        observations=sorted(observations, key=lambda o: (o.source.value, o.source_id)),
        scene_ids=sorted(scene_ids or []),
    )


# Whose statement of the operator we take when sources disagree, strongest first. PeeringDB
# facilities are maintained by the operators themselves against an interconnection database that
# would break if the name were wrong; an OSM `operator=` tag is a mapper's reading of a sign.
# Both are `[reference]` either way — this orders *whose words we quote*, not how much we believe.
_ATTRIBUTION_LADDER: tuple[PriorSource, ...] = (
    PriorSource.OPERATOR_DISCLOSURE,
    PriorSource.NATIONAL_REGISTRY,
    PriorSource.PEERINGDB,
    PriorSource.OSM,
    PriorSource.TRADE_PRESS,
)
_ATTRIBUTION_RANK = {source: i for i, source in enumerate(_ATTRIBUTION_LADDER)}
