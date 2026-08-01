"""Generic records-page fetcher: scrape document links off a body's minutes page.

The WordPress / Wix / Revize / static-HTML bodies don't share a platform API — they
just put `<a>` links to PDF/DOC files on a "minutes" (or "agendas") page. This
fetcher pulls that page through the shared connector cache and turns every
document-file link into a ``MeetingDoc``, parsing the meeting date out of the link
text or filename and classifying minutes vs. agenda from the same.

It is deliberately conservative: it reports only links that actually point at a
document file, passes titles/URLs through verbatim, and parses a date only when one
is unambiguously present (else ``date: null``). A page that lists nothing as a file
link (an embedded viewer, a JS-loaded list) yields an honest empty result — never a
fabricated entry.
"""

from __future__ import annotations

import html as _html
import re
from datetime import date as _date
from typing import cast
from urllib.parse import unquote, urljoin

from watermark.civic._http import get_page
from watermark.civic.models import MeetingDoc, Subdivision
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

_ANCHOR = re.compile(
    r"""<a\b[^>]*\bhref=["']([^"']+)["'][^>]*>(.*?)</a>""", re.IGNORECASE | re.DOTALL
)
_TAG = re.compile(r"<[^>]+>")
# A document-file link: an extension before the query/fragment/end of the href.
_DOC_EXT = re.compile(r"\.(?:pdf|docx?|xlsx?|rtf)(?=[?#]|$)", re.IGNORECASE)

_MONTHS = {
    m: i
    for i, m in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1
    )
}
# 1-6-26 | 01/02/2026 | 1.2.2024  (M D Y, US order — the township filename convention)
_NUMERIC_DATE = re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b")
# 2026-01-06 (ISO)
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
# January 6, 2026 | Jan 6 2026
_NAMED_DATE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")


def _valid(year: int, month: int, day: int) -> str | None:
    """ISO ``yyyy-mm-dd``, or ``None`` if the components aren't a real calendar date.

    Validates via :class:`datetime.date` so an impossible date (e.g. Feb 30) returns ``None``
    rather than a string that later crashes ``date.fromisoformat`` in the corpus audit (#615).
    """
    if not (1900 <= year <= 2100):
        return None
    try:
        return _date(year, month, day).isoformat()
    except ValueError:
        return None


def parse_date(text: str) -> str | None:
    """First unambiguous date in ``text`` as ISO ``yyyy-mm-dd``, else ``None``.

    Handles the township conventions: ``1-6-26`` / ``01/02/2026`` / ``1.2.2024``
    (US month-day order; 2-digit years are 2000s), ISO, and ``January 6, 2026``.
    """
    if m := _ISO_DATE.search(text):
        return _valid(int(m[1]), int(m[2]), int(m[3]))
    if m := _NAMED_DATE.search(text):
        month = _MONTHS.get(m[1][:3].lower())
        return _valid(int(m[3]), month, int(m[2])) if month else None
    if m := _NUMERIC_DATE.search(text):
        year = int(m[3])
        year += 2000 if year < 100 else 0
        return _valid(year, int(m[1]), int(m[2]))
    return None


def _classify_kind(haystack: str) -> str:
    low = haystack.lower()
    if "agenda" in low:
        return "agenda"
    if re.search(r"minute|\bmins?\b|\brom\b", low):  # "ROM" = record of minutes
        return "minutes"
    if "packet" in low:
        return "packet"
    # Allen County's A######/M###### (MMDDYY) filename convention: the county
    # commissioners link an agenda as the bare meeting date ("June 9, 2026") with the
    # kind carried only by the file basename. Read it as a last resort — after the
    # title/keyword checks — and anchor to the path separator + the suffix/extension
    # so it can't catch a township's bare-date "2.6.2024.pdf" (no A/M letter prefix).
    if re.search(r"/a\d{5,7}[-.]", low):
        return "agenda"
    if re.search(r"/m\d{5,7}[-.]", low):
        return "minutes"
    return "other"


def _date_signal(title: str, href: str) -> str:
    """The text a meeting date may honestly be read from: the link text + the file's own name.

    Deliberately NOT the whole href. A CMS puts its own bookkeeping in the path — WordPress
    files everything under ``/wp-content/uploads/<YYYY>/<MM>/`` — and that prefix reads as a
    date to :func:`parse_date`. On a body whose filenames are bare US dates the two collide
    and the *upload* month wins: Allen Township's ``/uploads/2026/05/01-06-2026.pdf`` matched
    ``05/01-06`` and dated a January-2026 meeting to **2006-05-01**, inventing a decade of
    chronology for a page that only holds 2024-2026 (#1839, the first peer to hit it — Lima's
    WordPress bodies all carry ISO or named dates and were never miscounted).

    The upload path is when the clerk uploaded the file, never when the body met, so it is not
    a date source at all. Only the last path segment (with its query, which is where Wix hangs
    the friendly ``?dn=`` download name) is kept. A body that encodes the meeting date *only*
    in its upload path now yields ``date: null`` — an honest omission over an invented date.
    """
    basename = unquote(_html.unescape(href)).rsplit("/", 1)[-1]
    return f"{title} {basename}"


def extract_documents(html: str, *, base_url: str, slug: str) -> list[MeetingDoc]:
    """Every document-file link on a records page, as ``MeetingDoc``s (deduped by URL)."""
    docs: list[MeetingDoc] = []
    seen: set[str] = set()
    for href, inner in _ANCHOR.findall(html):
        if not _DOC_EXT.search(href):
            continue
        url = urljoin(base_url, _html.unescape(href))
        if url in seen:
            continue
        seen.add(url)
        title = re.sub(r"\s+", " ", _html.unescape(_TAG.sub("", inner))).strip()
        # The friendly download name (Wix `?dn=…`) and filename carry date/kind too;
        # percent-decode so "%20Minutes"/"%20ROM" read as words for classification.
        signal = f"{title} {unquote(_html.unescape(href))}"
        docs.append(
            MeetingDoc(
                slug=slug,
                body=None,  # single-body records page; the subdivision is the body
                kind=_classify_kind(signal),
                title=title or None,
                # Kind reads the whole href (its `/m######-` convention is anchored on the
                # path separator); the DATE must not — see _date_signal.
                date=parse_date(_date_signal(title, href)),
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
    """Fetch + scrape a body's records page into MeetingDocs.

    ``url`` overrides the page; otherwise the registry's ``publishing.records_url``
    (falling back to ``website``) is used.
    """
    settings = settings or get_settings()
    target = url or subdivision.publishing.records_url or subdivision.publishing.website
    if not target:
        raise ValueError(f"{subdivision.slug}: no records page URL on record")
    page = get_page(target, connector="subdivision_records", settings=settings)
    final_url = cast("str", page.get("final_url", target))
    docs = extract_documents(
        cast("str", page.get("html", "")), base_url=final_url, slug=subdivision.slug
    )
    log.info("civic.generic.fetch", slug=subdivision.slug, docs=len(docs), page=final_url)
    return docs
