"""CivicPlus / CivicEngage "Agenda Center" fetcher.

An Agenda Center page (``/AgendaCenter``) groups meetings under per-body category
sections (``<h2>City Council Agendas and Minutes</h2>`` …) and links each document
as ``/AgendaCenter/ViewFile/{Agenda,Minutes}/_MMDDYYYY-<id>`` — the meeting date is
encoded right in the link tail. :func:`parse_agenda_center` turns that markup into
``MeetingDoc``s (one per document); :func:`fetch` pulls the page through the shared
connector cache and parses it.

Scope: this reads what the Agenda Center *index* surfaces (recent meetings per body
across the last few years, plus "Previous Versions" pointers). The full historical
archive is loaded by the site's ``POST /AgendaCenter/UpdateCategoryList`` per
(category, year) — a follow-on; :func:`fetch` logs how many docs it captured so the
index view is never mistaken for the complete record. Values are passed through
verbatim; no dates or titles are invented.
"""

from __future__ import annotations

import html as _html
import re
from typing import cast

from bosc.civic._http import get_page
from bosc.civic.models import MeetingDoc, Subdivision
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

# A category section header, e.g. "<h2 ...>City Council Agendas and Minutes</h2>".
_H2 = r"<h2[^>]*>(?P<h2>.*?)</h2>"
# A document link: /AgendaCenter/ViewFile/Agenda|Minutes/_MMDDYYYY-<id>, then its text.
_VF = (
    r'<a\b[^>]*\bhref="(?P<href>/AgendaCenter/ViewFile/(?P<kind>Agenda|Minutes)/'
    r'_(?P<date>\d{8})-(?P<id>\d+))"[^>]*>(?P<title>.*?)</a>'
)
_SCAN = re.compile(f"{_H2}|{_VF}", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
# Trailing "... Agendas and Minutes" / "Agendas & Minutes" / "- Agenda & Minutes"
# (the char class includes hyphen + en/em dash separators).
_CATEGORY_SUFFIX = re.compile(
    r"[\s\-\u2013\u2014]*agendas?\s*&?\s*(?:and\s*)?minutes?\s*$", re.IGNORECASE
)


def _clean(fragment: str) -> str:
    """Strip tags + entities + collapse whitespace from an HTML fragment."""
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub("", fragment))).strip()


def _body_name(h2_inner: str) -> str:
    """A category header to a body name (drop the trailing 'Agendas and Minutes')."""
    return _CATEGORY_SUFFIX.sub("", _clean(h2_inner)).strip() or _clean(h2_inner)


def _iso_date(mmddyyyy: str) -> str | None:
    """``05062024`` -> ``2024-05-06``; ``None`` if the components aren't a real date."""
    month, day, year = int(mmddyyyy[:2]), int(mmddyyyy[2:4]), int(mmddyyyy[4:])
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_agenda_center(html: str, *, base_url: str, slug: str) -> list[MeetingDoc]:
    """Parse an Agenda Center page (or UpdateCategoryList fragment) into MeetingDocs.

    One ``MeetingDoc`` per document link, attributed to the nearest preceding
    category header. De-duplicated by URL (the index repeats some links).
    """
    base = base_url.split("/AgendaCenter")[0] or base_url
    docs: list[MeetingDoc] = []
    seen: set[str] = set()
    current_body: str | None = None
    for m in _SCAN.finditer(html):
        if m.group("h2") is not None:
            current_body = _body_name(m.group("h2"))
            continue
        href = m.group("href")
        url = f"{base}{href}"
        if url in seen:
            continue
        seen.add(url)
        docs.append(
            MeetingDoc(
                slug=slug,
                body=current_body,
                kind=m.group("kind").lower(),  # "agenda" | "minutes"
                title=_clean(m.group("title")) or None,
                date=_iso_date(m.group("date")),
                url=url,
            )
        )
    return docs


def fetch(
    subdivision: Subdivision,
    *,
    url: str | None = None,
    settings: Settings | None = None,
) -> list[MeetingDoc]:
    """Fetch + parse a body's CivicPlus Agenda Center index into MeetingDocs.

    ``url`` overrides the Agenda Center URL; otherwise the registry's
    ``publishing.records_url`` (falling back to ``website``) is used.
    """
    settings = settings or get_settings()
    target = url or subdivision.publishing.records_url or subdivision.publishing.website
    if not target:
        raise ValueError(f"{subdivision.slug}: no Agenda Center URL on record")
    page = get_page(target, connector="civicplus", settings=settings)
    final_url = cast("str", page.get("final_url", target))
    docs = parse_agenda_center(
        cast("str", page.get("html", "")), base_url=final_url, slug=subdivision.slug
    )
    log.info(
        "civic.civicplus.fetch",
        slug=subdivision.slug,
        docs=len(docs),
        note="index view; full archive via UpdateCategoryList is a follow-on",
    )
    return docs
