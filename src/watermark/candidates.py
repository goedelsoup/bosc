"""Curated entity inputs (``data/entities/profiles/``).

These are hand-curated entity inputs that are *not* derived from the document
corpus (the code-built graph in :mod:`watermark.pipeline.entities` covers corpus
parties). Two inventories live under ``data/entities/profiles/``:

* ``cloud-consumer-candidates.yaml`` — corridor operations marked on demand-fit
  only (workload class), explicitly **not** asserted customers or parties
  connected to Project BOSC.
* ``defense-contractors.yaml`` — a seed list of DoD primes (name + match
  patterns) matched case-insensitively against the corpus entity graph and Allen
  County parcel owner names; a hit is a lead, not a classification or accusation.

Loaded with pyyaml + Pydantic; rendered to the site by :mod:`watermark.site.candidates`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings
from watermark.connectors.gis_schema import GisDefenseMeta
from watermark.sites import active_profile

# Curated inventories live under this subdirectory of ``settings.entities_dir``.
PROFILES_SUBDIR = "profiles"


class CandidateEntity(BaseModel):
    """One curated candidate entity (demand-fit only — not a customer/connection)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    tier: int
    kind: str  # corporate | government | ... (mirrors the entity-graph vocabulary)
    sector: str | None = None
    location: str | None = None
    workload_classes: list[str] = Field(default_factory=list)
    confirmed_cloud_relationship: str | None = None
    cloud_consumer_candidate: bool = True
    corridor_context: bool = False
    speculative: bool = False
    basis: str | None = None


class CandidateInventory(BaseModel):
    """A loaded ``data/entities/*.yaml`` inventory: provenance meta + entities."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = Field(default_factory=dict)
    entities: list[CandidateEntity] = Field(default_factory=list)


class DefenseContractor(BaseModel):
    """One DoD-prime seed entry: a display name plus owner-name match patterns."""

    model_config = ConfigDict(extra="forbid")

    name: str
    note: str | None = None
    patterns: list[str] = Field(default_factory=list)

    def matches(self, name: str) -> bool:
        """True if any pattern is a case-insensitive substring of ``name``."""
        up = name.upper()
        return any(p.upper() in up for p in self.patterns)


class DefenseContractorList(BaseModel):
    """The loaded ``defense-contractors.yaml`` seed list: provenance + primes."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = Field(default_factory=dict)
    defense_contractors: list[DefenseContractor] = Field(default_factory=list)

    def match(self, names: Iterable[str]) -> dict[str, list[str]]:
        """Map each contractor name to the input names it matches (substring).

        ``names`` is any iterable of strings (e.g. entity displays, parcel owner
        names). Only contractors with at least one hit appear in the result.
        """
        hits: dict[str, list[str]] = defaultdict(list)
        materialized = list(names)  # iterate the contractors against a stable list
        for dc in self.defense_contractors:
            for n in materialized:
                if dc.matches(n) and n not in hits[dc.name]:
                    hits[dc.name].append(n)
        return {k: v for k, v in hits.items() if v}


def load_inventory(path: Path) -> CandidateInventory:
    """Load and validate one candidate-entity inventory YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CandidateInventory.model_validate(data)


def _profiles_dir(entities_dir: Path) -> Path:
    """Resolve the curated-profiles directory, tolerating the pre-move layout."""
    nested = entities_dir / PROFILES_SUBDIR
    return nested if nested.is_dir() else entities_dir


def load_cloud_consumer_candidates(entities_dir: Path) -> CandidateInventory | None:
    """Load ``profiles/cloud-consumer-candidates.yaml`` if present, else ``None``."""
    path = _profiles_dir(entities_dir) / "cloud-consumer-candidates.yaml"
    return load_inventory(path) if path.is_file() else None


def load_defense_contractors(entities_dir: Path) -> DefenseContractorList | None:
    """Load ``profiles/defense-contractors.yaml`` if present, else ``None``."""
    path = _profiles_dir(entities_dir) / "defense-contractors.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return DefenseContractorList.model_validate(data)


class DefenseLandScan(BaseModel):
    """The committed Allen County defense-land scan (``parcels.defense.yaml``).

    Parcel rows are kept as loose dicts — they mirror the GIS connector's ``Parcel``
    dump plus, for ``prime_owned``, a ``matched_prime`` tag — so the site can render
    them without importing the connector layer.
    """

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = Field(default_factory=dict)
    prime_owned: list[dict[str, Any]] = Field(default_factory=list)
    army_controlled: list[dict[str, Any]] = Field(default_factory=list)


def load_defense_scan(settings: Settings) -> DefenseLandScan | None:
    """Load the active site's defense-land scan, if present.

    The parcel reference subfolder is the active profile's ``gis_parcel.reference_dir``
    (Lima = ``allen-gis``), so a non-Lima site reads its own ``parcels.defense.yaml``
    rather than Allen County's. Returns ``None`` when the site registers no parcel GIS
    schema or the scan file is absent.
    """
    prof = active_profile(settings)
    if prof.gis_parcel is None:
        return None
    path = settings.reference_dir / prof.gis_parcel.reference_dir / "parcels.defense.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return DefenseLandScan.model_validate(data)


def load_defense_meta(settings: Settings) -> GisDefenseMeta | None:
    """The active site's defense-scan provenance block, or ``None`` if it registers none.

    The scan YAML reproduces this block's *prose* into its ``meta``; the feed projection reads it
    here instead, because the typed enclave attribution + register (#1663) live on the profile —
    the single source — and are never parsed back out of the note's ``[inference]`` prefix.
    """
    prof = active_profile(settings)
    if prof.gis_parcel is None or prof.gis_parcel.defense is None:
        return None
    return prof.gis_parcel.defense.meta
