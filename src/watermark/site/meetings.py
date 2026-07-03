"""Export committed subdivision corridor-meeting summaries as typed feeds.

Publishes the reviewed ``data/extracted/<slug>/meetings/meeting-summaries.yaml``
artifacts (built by ``watermark subdivisions summarize``) as :class:`~watermark.site.feeds.MeetingItem`
feeds: for each political subdivision, the meetings whose minutes/agendas name the corridor
project, with the grounded summary, decisions, parties, and dollar figures the model read
from the text. (The legacy markdown ``render_meetings`` peer was removed at the SSG-cutover
cleanup, #603.)
"""

from __future__ import annotations

from typing import Any

from watermark.site.feeds import Citation, MeetingItem


def _str_list(value: Any) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def export_meetings(summaries: list[tuple[str, dict[str, Any]]]) -> list[MeetingItem]:
    """Export committed ``(slug, meeting)`` summary pairs as :class:`MeetingItem` items.

    Each meeting cites its source summaries
    artifact (``meeting['filename']`` when present, else the per-body summaries path).
    """
    items: list[MeetingItem] = []
    for slug, meeting in summaries:
        filename = (
            meeting.get("filename") or f"data/extracted/{slug}/meetings/meeting-summaries.yaml"
        )
        items.append(
            MeetingItem(
                slug=slug,
                date=meeting.get("date"),
                kind=meeting.get("kind"),
                summary=str(meeting.get("summary") or ""),
                corridor_relevance=str(meeting.get("corridor_relevance") or ""),
                decisions=_str_list(meeting.get("decisions")),
                parties=_str_list(meeting.get("parties")),
                parcels=_str_list(meeting.get("parcels")),
                dollar_figures=_str_list(meeting.get("dollar_figures")),
                hits=_str_list(meeting.get("hits")),
                citation=Citation(source=str(filename), source_kind="document"),
            )
        )
    return items
