"""CivicPlus Agenda Center fetcher: parsing, dispatch, offline replay."""

from __future__ import annotations

import pytest

from bosc.civic import load_registry
from bosc.civic.fetchers import FetcherNotImplementedError, civicplus, fetch_meetings
from bosc.config import Settings


def test_parse_agenda_center_attributes_body_kind_date() -> None:
    html = (
        "<h2>City Council Agendas and Minutes</h2>"
        '<tr class="catAgendaRow"><strong aria-label="Agenda for May 6, 2024">May 6, 2024</strong>'
        '<a href="/AgendaCenter/ViewFile/Agenda/_05062024-853">Council Agenda</a>'
        '<a href="/AgendaCenter/ViewFile/Minutes/_05062024-853">Council Minutes</a></tr>'
        "<h2>City Planning Commission Agendas &amp; Minutes</h2>"
        '<a href="/AgendaCenter/ViewFile/Minutes/_03112024-848">PC Minutes</a>'
    )
    docs = civicplus.parse_agenda_center(
        html, base_url="https://www.limaohio.gov/AgendaCenter", slug="lima"
    )
    assert [(d.body, d.kind, d.date) for d in docs] == [
        ("City Council", "agenda", "2024-05-06"),
        ("City Council", "minutes", "2024-05-06"),
        ("City Planning Commission", "minutes", "2024-03-11"),
    ]
    # URLs are resolved against the site root, verbatim from the link tail.
    assert docs[0].url == "https://www.limaohio.gov/AgendaCenter/ViewFile/Agenda/_05062024-853"
    assert docs[0].slug == "lima"


def test_parse_agenda_center_dedupes_repeated_links() -> None:
    html = (
        "<h2>City Council Agendas and Minutes</h2>"
        '<a href="/AgendaCenter/ViewFile/Agenda/_05062024-853">x</a>'
        '<a href="/AgendaCenter/ViewFile/Agenda/_05062024-853">x (repeat)</a>'
    )
    docs = civicplus.parse_agenda_center(html, base_url="https://x.gov/AgendaCenter", slug="lima")
    assert len(docs) == 1


def test_iso_date_rejects_bad_components() -> None:
    assert civicplus._iso_date("05062024") == "2024-05-06"
    assert civicplus._iso_date("13012024") is None  # month 13
    assert civicplus._iso_date("00002024") is None


def test_fetch_offline_replay(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    lima = reg.get("lima")
    assert lima is not None
    # Synthetic URL so a real local `bosc subdivisions fetch lima` can't mask the fixture.
    docs = civicplus.fetch(lima, url="https://lima.test/AgendaCenter", settings=hydro_settings)
    # Fixture has 3 bodies, 5 documents (City Council: 2 agendas + 1 minutes).
    assert len(docs) == 5
    bodies = {d.body for d in docs}
    assert bodies == {"City Council", "City Planning Commission", "Land Bank Committee"}
    # The 2026 Land Bank agenda parsed despite no "Agendas and Minutes" suffix.
    land_bank = next(d for d in docs if d.body == "Land Bank Committee")
    assert land_bank.date == "2026-01-09"
    assert land_bank.kind == "agenda"


def test_dispatch_via_platform(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    lima = reg.get("lima")  # platform civicplus
    assert lima is not None
    docs = fetch_meetings(lima, url="https://lima.test/AgendaCenter", settings=hydro_settings)
    assert len(docs) == 5


def test_dispatch_unsupported_platform_raises(hydro_settings: Settings) -> None:
    reg = load_registry(hydro_settings)
    jackson = reg.get("jackson-township")  # request_only — no machine-readable records
    assert jackson is not None
    with pytest.raises(FetcherNotImplementedError):
        fetch_meetings(jackson, settings=hydro_settings)
