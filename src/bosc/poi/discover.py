"""Discover place references in the committed corpus → POI candidates.

The first POI pipeline stage. Scan the reviewed corpus text for place references —
deed-format **parcel ids** (the canonical anchor) and **street addresses** — aggregate
them with the citations where they appear, and flag which the ``data/poi/`` store
already covers. Read-only and idempotent: it proposes a worklist; promoting a candidate
to a curated POI is a human step (``curate``). The parcel regex mirrors
``allen_gis._PARCEL_ID_RE``; a test cross-checks the two so they can't drift.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from bosc.config import Settings, get_settings
from bosc.hydrology.connectors.allen_gis import normalize_parcel_id
from bosc.poi.model import POICandidate
from bosc.poi.store import load_pois

# Deed-format Allen County parcel id (2-4-2-3.3) — mirrors allen_gis._PARCEL_ID_RE.
_PARCEL_RE = re.compile(r"\b\d{2}-\d{4}-\d{2}-\d{3}\.\d{3}\b")

# Conservative US street address: number + optional direction + 1-3 capitalized name
# words + a street-type suffix. A lead to verify, not a precise extractor.
_STREET_SUFFIX = (
    "St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Way|Ct|Court|"
    "Pike|Hwy|Highway|Pkwy|Parkway|Cir|Circle|Pl|Place|Ter|Terrace"
)
_ADDRESS_RE = re.compile(
    rf"\b\d{{1,6}}\s+(?:[NSEW]\.?\s+)?(?:[A-Z][A-Za-z'.-]+\s+){{1,3}}(?:{_STREET_SUFFIX})\b\.?"
)

_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".txt"}


def _default_roots(settings: Settings) -> list[Path]:
    """Committed text-corpus roots to scan (reviewed artifacts, not raw documents)."""
    data = settings.data_dir
    return [
        settings.extracted_dir,
        settings.people_dir,
        settings.entities_dir,
        data / "site",
        data / "scenarios",
    ]


def _iter_text_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in _TEXT_SUFFIXES:
            yield path


@dataclass
class _Acc:
    """Accumulator for one (kind, normalized) place reference across the corpus."""

    value: str
    count: int = 0
    files: set[str] = field(default_factory=set)


def covered_parcels(*, settings: Settings | None = None) -> set[str]:
    """Normalized parcel numbers already represented by a POI in the store."""
    settings = settings or get_settings()
    covered: set[str] = set()
    for poi in load_pois(settings=settings):
        for pid in poi.front.parcels:
            covered.add(normalize_parcel_id(pid))
        for sf in poi.front.surface_forms:
            if sf.type == "parcel-id":
                covered.add(normalize_parcel_id(sf.value))
            if sf.resolved_parcel:
                covered.add(normalize_parcel_id(sf.resolved_parcel))
    return covered


def discover_candidates(
    *, roots: list[Path] | None = None, settings: Settings | None = None
) -> list[POICandidate]:
    """Place references found in the corpus, with citations + store-coverage flags.

    Aggregated by ``(kind, normalized)`` and sorted kind → most-cited → key. Parcel-id
    candidates already in the store are marked ``covered`` (the uncovered ones are the
    records-worklist). Pass ``roots`` to scan a specific location (tests); ``settings``
    still drives store coverage.
    """
    settings = settings or get_settings()
    scan_roots = roots if roots is not None else _default_roots(settings)
    repo_root = settings.data_dir.parent

    hits: dict[tuple[str, str], _Acc] = {}

    def add(kind: str, raw: str, norm: str, path: Path) -> None:
        acc = hits.get((kind, norm))
        if acc is None:
            acc = hits[(kind, norm)] = _Acc(raw)
        acc.count += 1
        try:
            acc.files.add(str(path.relative_to(repo_root)))
        except ValueError:
            acc.files.add(str(path))

    for root in scan_roots:
        for path in _iter_text_files(root):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for m in _PARCEL_RE.finditer(text):
                add("parcel-id", m.group(0), normalize_parcel_id(m.group(0)), path)
            for m in _ADDRESS_RE.finditer(text):
                value = re.sub(r"\s+", " ", m.group(0)).strip(" .")
                add("address", value, value.upper(), path)

    covered = covered_parcels(settings=settings)
    candidates = [
        POICandidate(
            kind=kind,  # 'parcel-id' | 'address' by construction
            value=acc.value,
            normalized=norm,
            occurrences=acc.count,
            citations=sorted(acc.files),
            covered=(kind == "parcel-id" and norm in covered),
        )
        for (kind, norm), acc in hits.items()
    ]
    candidates.sort(key=lambda c: (c.kind, -c.occurrences, c.normalized))
    return candidates
