"""Curated candidate-entity store (``data/entities/``).

These are hand-curated entities that are *not* derived from the document corpus
(the code-built graph in :mod:`bosc.pipeline.entities` covers corpus parties). The
first such inventory is the cloud-consumer candidates — corridor operations marked
on demand-fit only (workload class), explicitly **not** asserted customers or
parties connected to Project BOSC. Loaded with pyyaml + Pydantic; rendered to the
site by :mod:`bosc.site.candidates`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


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
    speculative: bool = False
    basis: str | None = None


class CandidateInventory(BaseModel):
    """A loaded ``data/entities/*.yaml`` inventory: provenance meta + entities."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = Field(default_factory=dict)
    entities: list[CandidateEntity] = Field(default_factory=list)


def load_inventory(path: Path) -> CandidateInventory:
    """Load and validate one candidate-entity inventory YAML file."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return CandidateInventory.model_validate(data)


def load_cloud_consumer_candidates(entities_dir: Path) -> CandidateInventory | None:
    """Load ``cloud-consumer-candidates.yaml`` if present, else ``None``."""
    path = entities_dir / "cloud-consumer-candidates.yaml"
    return load_inventory(path) if path.is_file() else None
