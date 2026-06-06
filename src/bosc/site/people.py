"""Render the curated individual profiles as site pages.

Only profiles flagged ``expanded_research: true`` are published; the rest stay
tracked under ``data/people`` but off the site. Each published profile becomes
``web/people/<slug>.md`` — its hand-written body plus an identity block and a
provenance footer — linked from ``people/index.md`` and, where the ``entity_key``
matches, cross-linked from the entity graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bosc.people import PersonProfile
from bosc.pipeline.entities import EntityGraph

# Same evidence-discipline framing the entity graph uses: roles read from the
# record are leads, not verdicts about control or wrongdoing.
_PROFILE_NOTE = (
    '!!! note "What a profile is"\n'
    "    A profile collates how an individual appears across the public record and "
    "the research built on it. Roles and affiliations are read from cited sources; "
    "they are leads to verify, **not** accusations. Verify every claim against the "
    "cited source before quoting it."
)


@dataclass
class PersonPage:
    slug: str
    name: str
    summary: str
    roles: list[str]


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _source_link(source: str) -> str:
    """Link a repo-relative source to its mirrored copy (or render plain if external).

    Person pages live at ``web/people/<slug>.md``; the mirrored data tree sits at
    ``web/data/...``, so a ``data/...`` source is one directory up.
    """
    if source.startswith("data/") and not source.endswith("/"):
        return f"[`{_esc(source)}`](../{source})"
    return f"`{_esc(source)}`"


def _meta_block(profile: PersonProfile) -> list[str]:
    """The identity block rendered under the title (aliases, roles, affiliations)."""
    front = profile.front
    rows: list[tuple[str, str]] = []
    if front.aliases:
        rows.append(("Also known as", ", ".join(front.aliases)))
    if front.roles:
        rows.append(("Roles", ", ".join(front.roles)))
    if front.affiliations:
        rows.append(("Affiliations", ", ".join(front.affiliations)))
    if front.tags:
        rows.append(("Tags", ", ".join(f"`{t}`" for t in front.tags)))
    if not rows:
        return []
    lines = ["| | |", "|---|---|"]
    lines += [f"| **{label}** | {_esc(value)} |" for label, value in rows]
    lines.append("")
    return lines


def render_profile_page(profile: PersonProfile, *, egraph: EntityGraph | None = None) -> str:
    """Render one published profile to its markdown page."""
    front = profile.front
    lines = [f"# {front.name}", ""]
    if front.summary:
        lines += [f"*{front.summary}*", ""]
    lines.append(_PROFILE_NOTE)
    lines.append("")
    lines += _meta_block(profile)

    # Cross-link into the generated entity graph when this person resolved there.
    if egraph is not None and egraph.get(profile.entity_key) is not None:
        lines += [
            f"Appears in the [entity graph](../entities.md) as `{_esc(profile.entity_key)}`.",
            "",
        ]

    body = profile.body.strip()
    if body:
        lines += [body, ""]

    if front.sources:
        lines += ["## Sources", ""]
        lines += [f"- {_source_link(s)}" for s in front.sources]
        lines.append("")
    return "\n".join(lines)


def render_people_pages(
    people: list[PersonProfile],
    out_dir: Path,
    *,
    egraph: EntityGraph | None = None,
) -> list[PersonPage]:
    """Write a page for every ``expanded_research`` profile; return the published set.

    Profiles that are tracked but not expanded are intentionally skipped (no page).
    """
    published = [p for p in people if p.expanded]
    if not published:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    pages: list[PersonPage] = []
    for profile in published:
        (out_dir / f"{profile.slug}.md").write_text(
            render_profile_page(profile, egraph=egraph), encoding="utf-8"
        )
        pages.append(
            PersonPage(
                slug=profile.slug,
                name=profile.name,
                summary=profile.front.summary or "",
                roles=profile.front.roles,
            )
        )
    return pages


def render_people_index(pages: list[PersonPage], *, tracked: int) -> str:
    """Render ``people/index.md`` — the directory of published individuals."""
    published = len(pages)
    tracked_only = max(tracked - published, 0)
    lines = [
        "# Individuals",
        "",
        f"Curated profiles of key individuals in the corpus. **{published}** of "
        f"**{tracked}** tracked individuals have expanded research published here; "
        f"the remaining {tracked_only} are tracked privately and not yet published.",
        "",
        _PROFILE_NOTE,
        "",
    ]
    if not pages:
        lines += ["*No individuals are published yet.*", ""]
        return "\n".join(lines)
    lines += ["| Individual | Roles | Summary |", "|---|---|---|"]
    for page in sorted(pages, key=lambda p: p.name.upper()):
        roles = ", ".join(page.roles) or "—"
        lines.append(
            f"| [{_esc(page.name)}]({page.slug}.md) | {_esc(roles)} | {_esc(page.summary)} |"
        )
    lines.append("")
    return "\n".join(lines)
