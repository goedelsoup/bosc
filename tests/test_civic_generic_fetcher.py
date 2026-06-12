"""Generic records-page fetcher: link extraction, date parsing, dispatch, replay."""

from __future__ import annotations

import pytest

from bosc.civic import load_registry
from bosc.civic.fetchers import FetcherNotImplementedError, fetch_meetings, generic
from bosc.config import Settings


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1-6-26 Minutes", "2026-01-06"),  # M-D-YY, township filename style
        ("01/02/2026", "2026-01-02"),  # M/D/YYYY
        ("1.2.2024.pdf", "2024-01-02"),  # M.D.YYYY (Revize filename)
        ("January 6, 2026", "2026-01-06"),  # named month
        ("Jan 6 2026", "2026-01-06"),
        ("2026-01-06 packet", "2026-01-06"),  # ISO wins
        ("no date here", None),
        ("13-40-2026", None),  # impossible month/day
    ],
)
def test_parse_date(text: str, expected: str | None) -> None:
    assert generic.parse_date(text) == expected


def test_extract_documents_kinds_dates_dedup_and_filtering() -> None:
    html = (
        '<a href="https://x.gov/wp-content/uploads/2026/01/1-6-26-Minutes.pdf">1-6-26 Minutes</a>'
        '<a href="https://x.gov/files/64b7b9.docx?dn=2-9-26%20ROM.docx">02-09-2026</a>'  # Wix-style
        '<a href="Documents/2.6.2024.pdf?t=20240101">2.6.2024.pdf</a>'  # Revize: rel + query
        '<a href="https://x.gov/2026-03-11-agenda.pdf">March 11 Agenda</a>'
        '<a href="/about">About us</a>'  # not a document -> skipped
        '<a href="https://x.gov/wp-content/uploads/2026/01/1-6-26-Minutes.pdf">dup</a>'  # deduped
    )
    docs = generic.extract_documents(html, base_url="https://x.gov/minutes/", slug="bath-township")
    assert [(d.kind, d.date) for d in docs] == [
        ("minutes", "2026-01-06"),
        ("minutes", "2026-02-09"),  # "ROM" in the ?dn= name classifies as minutes
        ("other", "2024-02-06"),  # bare date filename, no kind keyword
        ("agenda", "2026-03-11"),
    ]
    # Relative Revize link resolved against the page URL.
    assert docs[2].url == "https://x.gov/minutes/Documents/2.6.2024.pdf?t=20240101"


def test_classify_allen_county_filename_convention() -> None:
    """Allen County commissioners link agendas as a bare date; kind is in the A###### name.

    The county's agenda anchors carry no "agenda" word (just the meeting date), so the
    A######/M###### (MMDDYY) basename is the only kind signal — read after the keyword
    checks. A township's bare-date filename (no A/M letter prefix) still stays ``other``.
    """
    base = "https://commissioners.allencountyohio.com/meeting-agendas-2026/"
    up = "https://commissioners.allencountyohio.com/wp-content/uploads/2026/06"
    html = (
        f'<a href="{up}/A060926.pdf">June 9, 2026</a>'  # bare-date agenda
        f'<a href="{up}/A060126-Special.pdf">June 1, 2026-Special Session</a>'  # bare special
        f'<a href="{up}/M060226.pdf">Minutes of June 2, 2026</a>'  # keyword wins
        f'<a href="{up}/M060126-Special.pdf">June 1, 2026-Special Session</a>'  # bare special
        '<a href="https://x.gov/uploads/2.6.2024.pdf">2.6.2024</a>'  # township bare date
    )
    docs = generic.extract_documents(html, base_url=base, slug="commissioners")
    assert [(d.kind, d.date) for d in docs] == [
        ("agenda", "2026-06-09"),
        ("agenda", "2026-06-01"),
        ("minutes", "2026-06-02"),
        ("minutes", "2026-06-01"),
        ("other", "2024-02-06"),  # no A/M prefix — heuristic must not over-reach
    ]


def test_generic_fetch_offline_replay(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    bath = reg.get("bath-township")  # platform wordpress
    assert bath is not None
    # Synthetic URL so a real local fetch can't mask the fixture.
    docs = generic.fetch(bath, url="https://bath.test/minutes/", settings=hydro_settings)
    # Fixture: 3 distinct documents (one duplicate + one non-doc link dropped).
    assert len(docs) == 3
    kinds = sorted(d.kind for d in docs)
    assert kinds == ["agenda", "minutes", "other"]  # Minutes, Agenda, "Special Meeting"
    assert all(d.body is None for d in docs)  # single-body records page


def test_dispatch_routes_wordpress_to_generic(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    bath = reg.get("bath-township")
    assert bath is not None
    docs = fetch_meetings(bath, url="https://bath.test/minutes/", settings=hydro_settings)
    assert len(docs) == 3


def test_dispatch_facebook_body_still_raises(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    richland = reg.get("richland-township")  # facebook, no records_url
    assert richland is not None
    with pytest.raises(FetcherNotImplementedError):
        fetch_meetings(richland, settings=hydro_settings)
