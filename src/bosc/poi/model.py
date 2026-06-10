"""Point-of-interest (place) models — the validated frontmatter of a POI profile.

A POI is the **place** peer of a person profile ([`bosc.people`](../people.py)): a
markdown file under ``data/poi/<slug>.md`` opened by a YAML frontmatter header, cited to
the corpus and **depth-marked**. The place-specific enrichment is geometry (geocoding);
the deepest depth rung, ``watched``, is what feeds imagery tracking (`bosc.gis`). See
[`docs/poi-subsystem.md`](../../../docs/poi-subsystem.md).

``extra="forbid"`` everywhere so a typo'd key is a loud error, not a silent drop. The
depth/kind ladders are ``Literal`` so an out-of-vocabulary value fails validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The research-depth ladder (human-set except the mechanical mention -> located advance).
Depth = Literal["mention", "located", "characterized", "watched"]
# Place taxonomy; drives the geocoder and whether the POI is a single place or a group.
Kind = Literal["parcel", "facility", "address", "feature", "jurisdiction", "composite"]

Bbox = tuple[float, float, float, float]  # WGS84 (minx, miny, maxx, maxy)


class POILocation(BaseModel):
    """Where the POI is, and how we know — tagged for provenance, never fabricated."""

    model_config = ConfigDict(extra="forbid")

    method: str | None = None  # parcel-cama | census-geocode | gnis | echo | curated
    confidence: str | None = None  # high | medium | low
    asof: str | None = None
    bbox: Bbox | None = None  # the tracking AOI (footprint bbox, or a buffered point)


class POITrack(BaseModel):
    """Imagery-tracking config — present only at ``depth: watched``."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    collections: list[str] = Field(default_factory=list)
    since: str | None = None  # baseline date for the time series


class SurfaceForm(BaseModel):
    """One corpus alias of this place + how it resolved — the dedup audit trail."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["parcel-id", "address", "coord", "name", "gnis"]
    value: str
    citation: str | None = None
    resolved_parcel: str | None = None


class POIRelationship(BaseModel):
    """A typed link from this place into the entity graph (e.g. owner -> an org)."""

    model_config = ConfigDict(extra="forbid")

    role: str
    entity: str


class POIFrontmatter(BaseModel):
    """The validated frontmatter header of a ``data/poi/<slug>.md`` profile."""

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str | None = None  # defaults to the file stem
    kind: Kind = "parcel"
    depth: Depth = "mention"
    parcels: list[str] = Field(default_factory=list)  # canonical anchor(s)
    members: list[str] = Field(default_factory=list)  # composites: member POI slugs
    location: POILocation | None = None
    track: POITrack | None = None
    surface_forms: list[SurfaceForm] = Field(default_factory=list)
    relationships: list[POIRelationship] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)  # required for evidence; repo refs
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


@dataclass
class POIProfile:
    """A parsed POI profile: validated frontmatter + the markdown body."""

    path: Path
    slug: str
    front: POIFrontmatter
    body: str

    @property
    def name(self) -> str:
        return self.front.name

    @property
    def kind(self) -> str:
        return self.front.kind

    @property
    def depth(self) -> str:
        return self.front.depth

    @property
    def bbox(self) -> Bbox | None:
        return self.front.location.bbox if self.front.location else None

    @property
    def tracked(self) -> bool:
        """Whether this POI feeds imagery tracking (``watched`` + ``track.enabled``)."""
        return self.front.depth == "watched" and bool(self.front.track and self.front.track.enabled)


class POICandidate(BaseModel):
    """A place reference discovered in the corpus, pre-resolution.

    The output of the ``discover`` stage: a raw locator (a parcel id, an address, or a
    corpus-verified facility/business ``feature`` name) with the corpus citations where
    it appears and whether the store already covers it. A candidate is a *lead to resolve
    and curate*, never an automatic POI.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["parcel-id", "address", "feature"]
    value: str  # a representative verbatim form
    normalized: str  # coverage/dedup key (digits-only parcel; upper-cased address; name key)
    occurrences: int  # total mentions across the corpus
    citations: list[str] = Field(default_factory=list)  # repo-relative source paths
    covered: bool = False  # already represented by a POI in the store
