"""Merge resolved candidates into deduplicated place groups — the dedup orchestration.

Resolve each discovered candidate, then **block by canonical parcel**: surface forms
that resolve to the same ``PARCEL_NO`` unify into one :class:`MergeGroup`. The auto/human
gate follows the merge-strictness decision —

* ``covered``    — the parcel is already a POI in the store;
* ``auto``       — the parcel identity is fixed by an **exact parcel-id** (promotable);
* ``review``     — the parcel rests only on a (fuzzy) geocode → a human must confirm;
* ``unresolved`` — no parcel resolved (geocode-only / failed).

The grouped members are the ``surface_forms`` audit trail that P3 curate writes into POIs.
Atomic merge keeps distinct parcels distinct (a campus is 10 parcels → 10 groups); a
*composite* unifies them by hand (curate), not here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors.allen_gis import Parcel
from bosc.poi.discover import covered_parcels, discover_candidates
from bosc.poi.model import POICandidate
from bosc.poi.resolve import Resolution, resolve_candidate

MergeStatus = Literal["covered", "auto", "review", "unresolved"]
_STATUS_ORDER = {"auto": 0, "review": 1, "unresolved": 2, "covered": 3}

Item = tuple[POICandidate, Resolution]


class MergeMember(BaseModel):
    """One surface form in a group, with the provenance of how it resolved."""

    model_config = ConfigDict(extra="forbid")

    kind: str  # parcel-id | address | coord
    value: str
    citations: list[str]
    method: str
    confidence: str
    auto_mergeable: bool


class MergeGroup(BaseModel):
    """The surface forms that resolve to one canonical parcel, plus the merge verdict."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = None  # the blocking key: parcel_no, else a gnis-/geo- fallback
    parcel_no: str | None  # the parcel number (None for a non-parcel feature/unresolved)
    parcel: Parcel | None
    members: list[MergeMember]
    has_exact_id: bool  # >=1 exact parcel-id member (fixes the identity)
    covered: bool  # already a POI in the store
    status: MergeStatus


def merge_resolutions(items: list[Item], *, settings: Settings | None = None) -> list[MergeGroup]:
    """Block already-resolved ``(candidate, resolution)`` pairs into :class:`MergeGroup`s.

    Pure grouping — no network — so the dedup logic is testable on synthetic resolutions.
    """
    settings = settings or get_settings()
    covered = covered_parcels(settings=settings)

    blocks: dict[str | None, list[Item]] = {}
    for cand, res in items:
        blocks.setdefault(res.key, []).append((cand, res))  # parcel_no, else fallback key

    groups: list[MergeGroup] = []
    for key, pairs in blocks.items():
        members = [
            MergeMember(
                kind=c.kind,
                value=c.value,
                citations=c.citations,
                method=r.method,
                confidence=r.confidence,
                auto_mergeable=r.auto_mergeable,
            )
            for c, r in pairs
        ]
        has_exact_id = any(m.kind == "parcel-id" and m.auto_mergeable for m in members)
        parcel = next((r.parcel for _, r in pairs if r.parcel is not None), None)
        parcel_no = next((r.parcel_no for _, r in pairs if r.parcel_no is not None), None)
        is_covered = parcel_no is not None and parcel_no in covered
        status: MergeStatus = (
            "unresolved"
            if key is None
            else "covered"
            if is_covered
            else "auto"
            if has_exact_id
            else "review"  # a geocoded/GNIS proposal — confirm before merging
        )
        groups.append(
            MergeGroup(
                key=key,
                parcel_no=parcel_no,
                parcel=parcel,
                members=members,
                has_exact_id=has_exact_id,
                covered=is_covered,
                status=status,
            )
        )
    groups.sort(key=lambda g: (_STATUS_ORDER[g.status], -len(g.members), g.key or ""))
    return groups


def merge_candidates(
    candidates: list[POICandidate], *, settings: Settings | None = None
) -> list[MergeGroup]:
    """Resolve each candidate (network) then merge — the full per-candidate path."""
    settings = settings or get_settings()
    items = [(c, resolve_candidate(c, settings=settings)) for c in candidates]
    return merge_resolutions(items, settings=settings)


def merge_corpus(
    *, parcel_ids_only: bool = True, settings: Settings | None = None
) -> list[MergeGroup]:
    """Discover the corpus, then merge. Parcel-ids only by default (the reliable anchor;
    including addresses/feature-names geocodes/GNIS-resolves every one — slower, fuzzier).
    """
    settings = settings or get_settings()
    # Skip the entity-graph name pass when we only want parcel-ids (the lean default).
    cands = discover_candidates(settings=settings, names=not parcel_ids_only)
    if parcel_ids_only:
        cands = [c for c in cands if c.kind == "parcel-id"]
    return merge_candidates(cands, settings=settings)
