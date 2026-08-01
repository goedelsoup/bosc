"""Generic records-page fetcher: link extraction, date parsing, dispatch, replay."""

from __future__ import annotations

import pytest

from watermark.civic import load_registry
from watermark.civic.fetchers import FetcherNotImplementedError, fetch_meetings, generic
from watermark.config import Settings


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
        ("2-30-2024 Minutes", None),  # Feb 30 — impossible calendar date (#615)
        ("4-31-2024", None),  # Apr has 30 days
        ("2-29-2023", None),  # 2023 is not a leap year
        ("2-29-2024", "2024-02-29"),  # 2024 is a leap year
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


def test_generic_fetch_offline_replay(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    bath = reg.get("bath-township")  # platform wordpress
    assert bath is not None
    # Synthetic URL so a real local fetch can't mask the fixture.
    docs = generic.fetch(bath, url="https://bath.test/minutes/", settings=civic_settings)
    # Fixture: 3 distinct documents (one duplicate + one non-doc link dropped).
    assert len(docs) == 3
    kinds = sorted(d.kind for d in docs)
    assert kinds == ["agenda", "minutes", "other"]  # Minutes, Agenda, "Special Meeting"
    assert all(d.body is None for d in docs)  # single-body records page


def test_dispatch_routes_wordpress_to_generic(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    bath = reg.get("bath-township")
    assert bath is not None
    docs = fetch_meetings(bath, url="https://bath.test/minutes/", settings=civic_settings)
    assert len(docs) == 3


def test_dispatch_facebook_body_still_raises(civic_settings: Settings) -> None:
    reg = load_registry(civic_settings)
    richland = reg.get("richland-township")  # facebook, no records_url
    assert richland is not None
    with pytest.raises(FetcherNotImplementedError):
        fetch_meetings(richland, settings=civic_settings)


def test_wordpress_upload_path_is_not_read_as_the_meeting_date() -> None:
    """A CMS's ``/uploads/<YYYY>/<MM>/`` prefix must never supply a meeting date (#1839).

    Allen Township (Hancock County) is the first body in the network whose filenames are bare
    US dates sitting under WordPress's upload path. Scanning the whole href, ``05/01-06`` in
    ``/uploads/2026/05/01-06-2026.pdf`` matched first and dated a January-2026 meeting to
    **2006-05-01** — a decade of invented chronology for a page holding only 2024-2026. The date
    is read from the link text + the file's own basename; the upload path is when the clerk
    uploaded the file, never when the body met.
    """
    up = "https://allentwphancockoh.gov/wp-content/uploads"
    html = (
        f'<a href="{up}/2026/05/01-06-2026.pdf">Minutes</a>'  # was 2006-05-01
        f'<a href="{up}/2026/05/01-28-2026.pdf">Minutes</a>'  # was 2028-05-01
        f'<a href="{up}/2026/06/10-28-2025-Zoning-Amendment-Hearings.pdf">Minutes</a>'
        f'<a href="{up}/2026/05/04-01-2025-1.pdf">Minutes</a>'  # was 2001-05-04
    )
    docs = generic.extract_documents(html, base_url=f"{up}/", slug="allen-township")
    assert [d.date for d in docs] == ["2026-01-06", "2026-01-28", "2025-10-28", "2025-04-01"]
    assert all(d.kind == "minutes" for d in docs)


def test_date_from_upload_path_alone_is_omitted_not_invented() -> None:
    """A file whose only date is in the CMS upload path now yields ``date: None`` (#1839).

    Prefer omission over invention: the upload month is not the meeting date, and reporting it
    as one is worse than reporting nothing. The link text still wins when it carries a date.
    """
    up = "https://x.gov/wp-content/uploads/2026/05"
    docs = generic.extract_documents(
        f'<a href="{up}/board-packet.pdf">Packet</a>'
        f'<a href="{up}/board-packet-2.pdf">Packet for May 6, 2026</a>',
        base_url=f"{up}/",
        slug="x",
    )
    assert [d.date for d in docs] == [None, "2026-05-06"]


def test_kind_heuristic_still_reads_the_whole_href() -> None:
    """Narrowing the DATE signal must not narrow the KIND one (#1839).

    Allen County's ``A######``/``M######`` convention is anchored on the path separator, so
    ``_classify_kind`` keeps the full href even though ``parse_date`` no longer sees it.
    """
    up = "https://commissioners.allencountyohio.com/wp-content/uploads/2026/06"
    docs = generic.extract_documents(
        f'<a href="{up}/M060226.pdf">June 2, 2026</a>', base_url=f"{up}/", slug="commissioners"
    )
    assert [(d.kind, d.date) for d in docs] == [("minutes", "2026-06-02")]


def test_tax_abatement_does_not_match_an_asbestos_abatement_bid() -> None:
    """`tax_abatement` needs the tax sense (#1839).

    Hancock County's commissioners let 7 asbestos-abatement demolition bids through the old bare
    `abatement` pattern, tagging two 2026-04-16 records as tax-abatement business they never
    transacted. The named instruments (CRA/TIF/enterprise zone) still match on their own.
    """
    from watermark.civic.keywords import scan_text

    assert scan_text("PY24 Asbestos Abatement Hancock County Demolition Program") == []
    assert "tax_abatement" in scan_text("the tax abatement agreement was approved")
    assert "tax_abatement" in scan_text("Community Reinvestment Area (CRA) application")


def test_one_power_needs_the_facility_s_own_name_not_a_bare_unit() -> None:
    """`megawatt hub` alone is a unit plus a noun; the disclosed name carries its town (#1839)."""
    from watermark.civic.keywords import scan_text

    assert scan_text("a 150 megawatt hub is proposed") == []
    assert "one_power" in scan_text("the Findlay Megawatt Hub (MWHub 01)")
    assert "one_power" in scan_text("One Power Company filed a complaint")
