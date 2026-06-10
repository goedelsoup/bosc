"""Discover place references in the committed corpus → POI candidates.

The first POI pipeline stage. Scan the reviewed corpus text for place references —
deed-format **parcel ids** (the canonical anchor), **street addresses**, and
**facility / business names** — aggregate them with the citations where they appear,
and flag which the ``data/poi/`` store already covers. Read-only and idempotent: it
proposes a worklist; promoting a candidate to a curated POI is a human step (``curate``).

Each kind is divergence-guarded so the pass can't invent a place: the parcel regex
mirrors ``allen_gis._PARCEL_ID_RE`` (a test cross-checks the two), and the facility-name
vocabulary is the **entity graph's facility + corporate nodes** — discover only proposes
a name the entity resolver already resolved from the corpus. Name candidates are emitted
as ``feature`` so they flow through the resolve funnel's GNIS branch (``_resolve_feature``).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
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


def covered_names(*, settings: Settings | None = None) -> set[str]:
    """Normalized facility/business names already represented by a POI in the store.

    The coverage key is :func:`bosc.pipeline.entities.normalize_name` of the POI's name,
    aliases, and any ``name``/``gnis`` surface form — the same normalization the name
    pass keys candidates by, so an already-curated facility drops out of the worklist.
    """
    from bosc.pipeline.entities import normalize_name

    settings = settings or get_settings()
    covered: set[str] = set()
    for poi in load_pois(settings=settings):
        covered.add(normalize_name(poi.front.name))
        for alias in poi.front.aliases:
            covered.add(normalize_name(alias))
        for sf in poi.front.surface_forms:
            if sf.type in ("name", "gnis"):
                covered.add(normalize_name(sf.value))
    covered.discard("")
    return covered


def _no_names(_text: str) -> list[tuple[str, str]]:
    """The name matcher when name extraction is disabled — finds nothing."""
    return []


def _facility_name_matcher(settings: Settings) -> Callable[[str], list[tuple[str, str]]]:
    """A matcher over corpus-verified facility/business names → ``(display, norm)`` hits.

    The divergence guard: the vocabulary is the **entity graph's facility + corporate
    nodes**, so discover can only propose a name the entity resolver already resolved
    from the corpus — the name analog of the parcel regex mirroring ``allen_gis``. Every
    name variant becomes a boundary-guarded, whitespace-flexible literal (so a
    line-wrapped mention still matches); the longest name wins at a shared start. A match
    is mapped back to its entity by normalizing the matched text, so a hit always carries
    the entity's legible display name and its canonical dedup key.
    """
    from bosc.pipeline.entities import build_entity_graph, normalize_name

    graph = build_entity_graph(settings=settings)
    by_norm: dict[str, tuple[str, str]] = {}
    patterns: list[str] = []
    for ent in graph.entities.values():
        if ent.kind not in ("facility", "corporate"):
            continue
        display = ent.display
        norm = normalize_name(display)
        if not norm:
            continue
        for variant in ent.variants:
            value = variant.strip()
            if len(value) < 4:  # too short to match a name without risking noise
                continue
            by_norm.setdefault(normalize_name(value), (display, norm))
            tokens = [t for t in re.split(r"\s+", value) if t]
            if tokens:
                patterns.append(r"\s+".join(re.escape(t) for t in tokens))
    if not patterns:
        return _no_names

    patterns.sort(key=len, reverse=True)  # longest name wins at a shared start
    name_re = re.compile(rf"(?<![A-Za-z0-9])(?:{'|'.join(patterns)})(?![A-Za-z0-9])")

    def match(text: str) -> list[tuple[str, str]]:
        hits: list[tuple[str, str]] = []
        for m in name_re.finditer(text):
            hit = by_norm.get(normalize_name(m.group(0)))
            if hit is not None:
                hits.append(hit)
        return hits

    return match


def discover_candidates(
    *, roots: list[Path] | None = None, settings: Settings | None = None, names: bool = True
) -> list[POICandidate]:
    """Place references found in the corpus, with citations + store-coverage flags.

    Aggregated by ``(kind, normalized)`` and sorted kind → most-cited → key. Parcel-id
    candidates already in the store are marked ``covered`` (the uncovered ones are the
    records-worklist), as are facility-name candidates a POI already names. Pass ``roots``
    to scan a specific location (tests); ``settings`` still drives store coverage.

    ``names`` enables the facility/business-name pass (entity-graph guarded, emitted as
    ``feature`` candidates for the GNIS funnel); set it ``False`` to skip building the
    entity graph when only the parcel/address worklist is wanted (e.g. parcel-only merge).
    """
    settings = settings or get_settings()
    scan_roots = roots if roots is not None else _default_roots(settings)
    repo_root = settings.data_dir.parent
    match_names = _facility_name_matcher(settings) if names else _no_names

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
            for display, norm in match_names(text):
                add("feature", display, norm, path)

    covered_parc = covered_parcels(settings=settings)
    covered_nm = covered_names(settings=settings) if names else set[str]()
    candidates = [
        POICandidate(
            kind=kind,  # 'parcel-id' | 'address' | 'feature' by construction
            value=acc.value,
            normalized=norm,
            occurrences=acc.count,
            citations=sorted(acc.files),
            covered=(
                (kind == "parcel-id" and norm in covered_parc)
                or (kind == "feature" and norm in covered_nm)
            ),
        )
        for (kind, norm), acc in hits.items()
    ]
    candidates.sort(key=lambda c: (c.kind, -c.occurrences, c.normalized))
    return candidates
