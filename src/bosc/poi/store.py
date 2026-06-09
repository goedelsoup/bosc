"""Read/parse the ``data/poi/`` profile store.

Mirrors [`bosc.people`](../people.py): each ``<slug>.md`` opens with a ``---`` YAML
frontmatter block (validated by :class:`POIFrontmatter`) followed by hand-written
markdown. A malformed profile is logged and skipped rather than aborting the load — the
store is curated by hand. Parsed with the stdlib + ``pyyaml`` (no extra dependency).

The ``tracked_pois`` view is what `bosc.gis` consumes: POIs at ``depth: watched`` with
``track.enabled`` are the imagery tracking sites (replacing the old layer-grouping over
``gis-findings.geojson``).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bosc.config import Settings, get_settings
from bosc.logging import get_logger
from bosc.poi.model import POIFrontmatter, POIProfile

log = get_logger(__name__)

_FM_DELIM = "---"


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a frontmatter document into ``(yaml_header, body)``.

    The file must open with a ``---`` line; the header runs until the next ``---`` line
    on its own. Raises ``ValueError`` if either delimiter is missing. (Mirrors the
    splitter in :mod:`bosc.people` — kept local so the POI store stands alone.)
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FM_DELIM:
        raise ValueError("profile must open with a '---' frontmatter block")
    for i in range(1, len(lines)):
        if lines[i].strip() == _FM_DELIM:
            header = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :]).lstrip("\n")
            return header, body
    raise ValueError("unterminated '---' frontmatter block")


def parse_poi(path: Path) -> POIProfile:
    """Parse and validate one ``<slug>.md`` POI profile."""
    header, body = split_frontmatter(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(header) or {}
    front = POIFrontmatter.model_validate(data)
    slug = front.slug or path.stem
    return POIProfile(path=path, slug=slug, front=front, body=body)


def load_pois(*, settings: Settings | None = None) -> list[POIProfile]:
    """Load every ``*.md`` POI profile (README excluded), sorted by name.

    A profile that fails to parse/validate is logged and skipped.
    """
    settings = settings or get_settings()
    poi_dir = settings.poi_dir
    if not poi_dir.is_dir():
        return []
    profiles: list[POIProfile] = []
    for path in sorted(poi_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        try:
            profiles.append(parse_poi(path))
        except Exception as exc:  # one malformed profile must not kill the load
            log.warning("poi.parse_failed", path=str(path), error=str(exc).splitlines()[0])
    profiles.sort(key=lambda p: p.name.upper())
    return profiles


def load_poi(slug: str, *, settings: Settings | None = None) -> POIProfile | None:
    """One POI profile by slug, or ``None`` if absent."""
    return next((p for p in load_pois(settings=settings) if p.slug == slug), None)


def tracked_pois(*, settings: Settings | None = None) -> list[POIProfile]:
    """The POIs that feed imagery tracking (``depth: watched`` + ``track.enabled``)."""
    return [p for p in load_pois(settings=settings) if p.tracked]
