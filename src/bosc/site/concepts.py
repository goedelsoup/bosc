"""The wiki concept-glossary store (issue #68).

A lightweight peer of the per-individual profile store (:mod:`bosc.people`): each
glossary concept is a markdown file under ``data/concepts/<slug>.md`` opened by a
YAML **frontmatter** header (title, kind, aliases, tags, summary, related slugs)
above a hand-written body. ``load_concepts`` parses+validates them (a malformed
file is logged and skipped, never aborting the build); ``export_concepts`` turns
them into the bundle's :class:`bosc.site.feeds.ConceptItem` feed.

The frontend (Epic #54, Section D) reads this feed, renders one page per concept,
and resolves inline ``[[wiki links]]`` in the body against the concepts, entities,
and people feeds — so a term defined here is reachable from anywhere it's named.
Frontmatter is parsed with the stdlib + ``pyyaml``; the ``---`` splitter is reused
from :mod:`bosc.people` so the two curated stores stay in lockstep.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bosc.logging import get_logger
from bosc.people import split_frontmatter
from bosc.site.feeds import ConceptItem

log = get_logger(__name__)


class ConceptFrontmatter(BaseModel):
    """The validated frontmatter header of a concept file.

    ``extra="forbid"`` so a typo'd key is a loud error, not a silently dropped
    field. Only ``title`` is required; ``slug`` defaults to the file stem.
    """

    model_config = ConfigDict(extra="forbid")

    title: str
    slug: str | None = None
    kind: str = "concept"  # concept | term | method
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    summary: str = ""
    related: list[str] = Field(default_factory=list)  # sibling concept slugs


def parse_concept(path: Path) -> ConceptItem:
    """Parse and validate one ``<slug>.md`` concept into its feed item."""
    header, body = split_frontmatter(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(header) or {}
    front = ConceptFrontmatter.model_validate(data)
    return ConceptItem(
        slug=front.slug or path.stem,
        title=front.title,
        kind=front.kind,
        aliases=front.aliases,
        tags=front.tags,
        summary=front.summary,
        related=front.related,
        body=body,
    )


def load_concepts(concepts_dir: Path) -> list[ConceptItem]:
    """Load every ``*.md`` concept under ``concepts_dir`` (README excluded), by title.

    A concept that fails to parse/validate is logged and skipped — the store is
    curated by hand, so one bad file shouldn't take down the site build.
    """
    if not concepts_dir.is_dir():
        return []
    concepts: list[ConceptItem] = []
    for path in sorted(concepts_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        try:
            concepts.append(parse_concept(path))
        except Exception as exc:  # one malformed concept must not kill the load
            log.warning("concepts.parse_failed", path=str(path), error=str(exc).splitlines()[0])
    concepts.sort(key=lambda c: c.title.upper())
    return concepts


def export_concepts(concepts: Sequence[ConceptItem]) -> list[ConceptItem]:
    """The concepts feed — already modelled as :class:`ConceptItem`, returned as-is."""
    return list(concepts)
