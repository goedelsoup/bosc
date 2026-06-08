"""Render committed subdivision corridor-meeting summaries as a site page.

Publishes the reviewed ``data/extracted/<slug>/meetings/meeting-summaries.yaml``
artifacts (built by ``bosc subdivisions summarize``) as one browsable page: for
each political subdivision, the meetings whose minutes/agendas name the corridor
project, with the grounded summary, decisions, parties, and dollar figures the
model read from the text. These same meetings appear on the [timeline] as
``subdivision_meeting`` events and their corridor actors in the [entity graph];
this page is the readable detail behind those.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

_INTRO = (
    "Reviewed summaries of the political-subdivision meetings whose minutes or "
    "agendas **name the corridor project** (Google / BOSC / Bistrozzi / data center). "
    "Each is a forced-tool-use extraction over the meeting text — the model records "
    "only what the minutes state, with no inference. Routine township business that a "
    "meeting also transacted stays in the per-body meeting index, off this page and "
    "off the timeline. Verify any figure against the cited source before quoting it."
)


def _esc(text: str) -> str:
    return " ".join(str(text).split()).strip()


def _body_name(slug: str) -> str:
    """Display name for a subdivision slug (``lacrpc`` keeps its acronym)."""
    return slug.upper() if slug.islower() and len(slug) <= 6 else slug.replace("-", " ").title()


def _render_meeting(meeting: dict[str, Any]) -> list[str]:
    date = _esc(meeting.get("date") or "undated")
    kind = _esc(meeting.get("kind") or "meeting")
    lines = [f"### {date} — {kind}", ""]
    relevance = _esc(meeting.get("corridor_relevance") or "")
    if relevance:
        lines += [f"> {relevance}", ""]
    summary = _esc(meeting.get("summary") or "")
    if summary:
        lines += [summary, ""]
    figures = [_esc(f) for f in meeting.get("dollar_figures", []) if _esc(f)]
    if figures:
        lines.append("**Dollar figures:** " + "; ".join(figures))
        lines.append("")
    decisions = [_esc(d) for d in meeting.get("decisions", []) if _esc(d)]
    if decisions:
        lines.append("**Decisions / motions:**")
        lines += [f"- {d}" for d in decisions]
        lines.append("")
    parties = [_esc(p) for p in meeting.get("parties", []) if _esc(p)]
    if parties:
        lines.append("**Parties:** " + "; ".join(parties))
        lines.append("")
    filename = _esc(meeting.get("filename") or "")
    if filename:
        lines += [f"*Source file: `{filename}`*", ""]
    return lines


def render_meetings(summaries: list[tuple[str, dict[str, Any]]]) -> str:
    """Render committed ``(slug, meeting)`` summary pairs to a markdown page."""
    lines = ["# Subdivision corridor meetings", "", _INTRO, ""]
    if not summaries:
        lines += ["", "*No corridor-relevant meeting summaries are committed yet.*", ""]
        return "\n".join(lines)

    by_body: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for slug, meeting in summaries:
        by_body[slug].append(meeting)

    total = len(summaries)
    lines.append(
        f"**{total}** summarized corridor meeting(s) across **{len(by_body)}** "
        "subdivision(s). They also appear on the [timeline](timeline.md) and their "
        "actors in the [entity graph](entities.md)."
    )
    lines.append("")
    for slug in sorted(by_body):
        meetings = by_body[slug]
        src = f"data/extracted/{slug}/meetings/meeting-summaries.yaml"
        lines.append(f"## {_body_name(slug)}")
        lines.append("")
        lines.append(f"{len(meetings)} meeting(s) · [raw summaries]({src})")
        lines.append("")
        for meeting in meetings:
            lines += _render_meeting(meeting)
    return "\n".join(lines).rstrip() + "\n"
