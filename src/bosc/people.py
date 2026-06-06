"""Per-individual profile store — the curated detail layer of the entity graph.

Each meaningful individual gets a markdown file under ``data/people/<slug>.md``
opened by a YAML **frontmatter** header. The header carries identity, linkage to
the resolved entity graph (``entity_key``), and the ``expanded_research`` flag that
gates whether the person is published to the site; the markdown body below it is
hand-written research prose.

This is the seam for the entity graph's eventual detail store: a profile links to a
graph entity by ``entity_key`` (its canonical normalized name, see
:func:`bosc.pipeline.entities.normalize_name`), so the generated entity graph can
deep-link to the human-authored dossier and vice-versa.

Frontmatter is parsed with the standard library + ``pyyaml`` (no extra dependency).
A malformed profile is logged and skipped rather than aborting a load — the store
is curated by hand, so one bad file shouldn't take down the site build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from bosc.logging import get_logger
from bosc.pipeline.entities import normalize_name

log = get_logger(__name__)

_FM_DELIM = "---"


class PersonFrontmatter(BaseModel):
    """The validated frontmatter header of a person profile.

    ``extra="forbid"`` so a typo'd key is a loud error, not a silently dropped
    field. Everything but ``name`` is optional; list fields default to empty.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    slug: str | None = None  # defaults to the file stem
    entity_key: str | None = None  # canonical graph key; defaults to normalize_name(name)
    aliases: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    affiliations: list[str] = Field(default_factory=list)
    summary: str | None = None
    # The gate: only profiles with expanded_research == True are rendered on the site.
    expanded_research: bool = False
    sources: list[str] = Field(default_factory=list)  # repo-relative paths / citations
    tags: list[str] = Field(default_factory=list)


@dataclass
class PersonProfile:
    """A parsed person profile: validated frontmatter + the markdown body."""

    path: Path
    slug: str
    front: PersonFrontmatter
    body: str

    @property
    def name(self) -> str:
        return self.front.name

    @property
    def expanded(self) -> bool:
        """Whether this individual gets expanded research and is published to the site."""
        return self.front.expanded_research

    @property
    def entity_key(self) -> str:
        """Canonical entity-graph key this profile links to."""
        return self.front.entity_key or normalize_name(self.front.name)


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split a frontmatter document into ``(yaml_header, body)``.

    The file must open with a ``---`` line; the header runs until the next ``---``
    line on its own. Raises ``ValueError`` if either delimiter is missing.
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


def parse_profile(path: Path) -> PersonProfile:
    """Parse and validate one ``<slug>.md`` profile."""
    header, body = split_frontmatter(path.read_text(encoding="utf-8"))
    data = yaml.safe_load(header) or {}
    front = PersonFrontmatter.model_validate(data)
    slug = front.slug or path.stem
    return PersonProfile(path=path, slug=slug, front=front, body=body)


def load_people(people_dir: Path) -> list[PersonProfile]:
    """Load every ``*.md`` profile under ``people_dir`` (README excluded), sorted by name.

    A profile that fails to parse/validate is logged and skipped.
    """
    if not people_dir.is_dir():
        return []
    profiles: list[PersonProfile] = []
    for path in sorted(people_dir.glob("*.md")):
        if path.name.upper() == "README.MD":
            continue
        try:
            profiles.append(parse_profile(path))
        except Exception as exc:  # one malformed profile must not kill the load
            log.warning("people.parse_failed", path=str(path), error=str(exc).splitlines()[0])
    profiles.sort(key=lambda p: p.name.upper())
    return profiles
