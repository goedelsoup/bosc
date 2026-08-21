"""Unit tests for watermark.oepa.portal — the eDocument portal sweep.

All tests are offline: they parse the committed results-page fixture or build the search
form in memory, and never touch the network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from watermark.oepa.portal import (
    PortalDoc,
    _hidden_fields,
    _parse_rows,
    _search_form,
    _split_entity_and_doc_type,
    permit_crosswalk,
    search_portal,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "oepa" / "portal-champaign-npdes-results.html"


@pytest.fixture(scope="module")
def page() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def docs(page: str) -> list[PortalDoc]:
    return _parse_rows(page)


# ---------------------------------------------------------------------------
# _hidden_fields
# ---------------------------------------------------------------------------


def test_hidden_fields_scrapes_all_three_postback_tokens(page: str) -> None:
    fields = _hidden_fields(page)
    assert set(fields) == {"__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"}
    assert fields["__VIEWSTATEGENERATOR"] == "A3C4E1F9"


def test_hidden_fields_on_a_page_without_them_is_empty() -> None:
    assert _hidden_fields("<html><body>no form here</body></html>") == {}


# ---------------------------------------------------------------------------
# _split_entity_and_doc_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("left", "entity", "doc_type"),
    [
        ("URBANA WPCF - Report", "URBANA WPCF", "Report"),
        # The doc type is compound and its qualifier must not be read as the type.
        ("NORTH LEWISBURG WWTP - Permit - Long Term", "NORTH LEWISBURG WWTP", "Permit - Long Term"),
        (
            "HICKORY GROVE MOBILE HOME COMMUNITY - Permit - Intermediate",
            "HICKORY GROVE MOBILE HOME COMMUNITY",
            "Permit - Intermediate",
        ),
        # The *entity* carries the separator, not the doc type.
        (
            "SYNAGRO - THOMAS SITE - Inspection or Compliance Review",
            "SYNAGRO - THOMAS SITE",
            "Inspection or Compliance Review",
        ),
        ("MINGO FARMS LLC - DFFO - DFFO", "MINGO FARMS LLC", "DFFO - DFFO"),
        # Nothing to split.
        ("URBANA WPCF", "URBANA WPCF", None),
    ],
)
def test_split_entity_and_doc_type(left: str, entity: str, doc_type: str | None) -> None:
    assert _split_entity_and_doc_type(left) == (entity, doc_type)


# ---------------------------------------------------------------------------
# _parse_rows
# ---------------------------------------------------------------------------


def test_parses_every_result_row(docs: list[PortalDoc]) -> None:
    assert len(docs) == 8


def test_every_row_carries_the_searched_facets(docs: list[PortalDoc]) -> None:
    assert {d.county for d in docs} == {"CHAMPAIGN"}
    assert {d.program for d in docs} == {"NPDES"}


def test_docid_and_url_come_from_the_href(docs: list[PortalDoc]) -> None:
    first = docs[0]
    assert first.docid == "4237221"
    assert first.url.endswith("ViewDocument.aspx?docid=4237221")


def test_entity_name_may_contain_the_field_separator(docs: list[PortalDoc]) -> None:
    synagro = next(d for d in docs if d.docid == "4196954")
    assert synagro.entity == "SYNAGRO - THOMAS SITE"
    assert synagro.doc_type == "Inspection or Compliance Review"


def test_wwtp_row_yields_the_state_permit_id(docs: list[PortalDoc]) -> None:
    """The whole point of the sweep: entity name -> Ohio state permit number."""
    urbana = next(d for d in docs if d.entity == "URBANA WPCF")
    assert urbana.permit_id == "1PD00011"
    assert urbana.doc_date == "8/20/2026"


@pytest.mark.parametrize(
    ("docid", "description"),
    [
        ("4223262", None),  # tail has no description segment at all
        ("4237221", None),  # tail has a single empty description segment
        ("4207377", "INSPECTION"),
        ("4151713", "CORRESPONDENCE"),  # trailing empty padding segments dropped
        ("4119376", "PTF285192904"),  # leading empty padding segments dropped
    ],
)
def test_description_ignores_empty_padding_segments(
    docs: list[PortalDoc], docid: str, description: str | None
) -> None:
    assert next(d for d in docs if d.docid == docid).description == description


def test_rows_without_a_docid_are_skipped() -> None:
    assert _parse_rows("<tr><td>1</td><td></td><td><a>NO LINK HERE</a></td></tr>") == []


def test_row_without_a_parseable_date_is_skipped() -> None:
    row = (
        '<tr><td>1</td><td></td><td><a href="ViewDocument.aspx?docid=99">'
        "ACME - Report - not-a-date - NPDES - ALLEN - 1PD00001 - 99</a></td></tr>"
    )
    assert _parse_rows(row) == []


# ---------------------------------------------------------------------------
# is_permit_id / permit_crosswalk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("permit_id", ["1PD00011", "1GRN00923", "2PE00000"])
def test_permit_shaped_ids(permit_id: str) -> None:
    assert _doc(permit_id=permit_id).is_permit_id


@pytest.mark.parametrize("permit_id", ["", "OH0021806", "NEO01", "1PD0001"])
def test_non_permit_shaped_ids(permit_id: str) -> None:
    assert not _doc(permit_id=permit_id).is_permit_id


def test_crosswalk_keeps_one_entity_per_permit_and_drops_unshaped(
    docs: list[PortalDoc],
) -> None:
    crosswalk = permit_crosswalk(docs)
    assert crosswalk["1PD00011"] == "URBANA WPCF"
    # 1PB00037 appears on two rows (an inspection and an NOV) and collapses to one entry.
    assert crosswalk["1PB00037"] == "MECHANICSBURG WWTP"
    assert len(crosswalk) == 7


def test_crosswalk_drops_rows_whose_secondary_id_is_not_a_permit() -> None:
    assert permit_crosswalk([_doc(permit_id="OH0021806")]) == {}


# ---------------------------------------------------------------------------
# _search_form
# ---------------------------------------------------------------------------


def test_populated_criterion_rows_are_anded_and_empty_ones_are_not() -> None:
    """Regression: ``And`` on an *empty* row makes the portal discard every criterion.

    A CHAMPAIGN/NPDES sweep built that way came back with Franklin County 401-wetlands
    rows — an unfiltered result page that silently reads as a successful search.
    """
    form = _search_form({}, county="CHAMPAIGN", program="NPDES", entity="", permit_id="")
    p = "ctl00$search$KeywordPanel1$"
    assert form[p + "ddlConn_-1_1_104_1"] == "And"  # county — populated
    assert form[p + "ddlConn_-1_1_109_1"] == "And"  # program — populated
    assert form[p + "ddlConn_-1_1_106_1"] == "Or"  # entity — empty
    assert form[p + "ddlConn_-1_1_111_1"] == "Or"  # secondary id — empty
    assert form[p + "ddlConn_-1_1_121_1"] == "Or"  # permit number — empty


def test_doc_type_is_never_sent_as_a_real_id() -> None:
    """The doc-type select is postback-activated; a real id on the search 500s."""
    form = _search_form({}, county="ALLEN", program="NPDES", entity="", permit_id="")
    assert form["ctl00$search$ddlDocType"] == "-1"


def test_hidden_tokens_are_carried_into_the_form() -> None:
    form = _search_form(
        {"__VIEWSTATE": "abc"}, county="ALLEN", program="NPDES", entity="", permit_id=""
    )
    assert form["__VIEWSTATE"] == "abc"
    assert form["ctl00$search$btnSearch"] == "Search"


# ---------------------------------------------------------------------------
# search_portal
# ---------------------------------------------------------------------------


def test_search_portal_requires_a_criterion() -> None:
    with pytest.raises(ValueError, match="county, entity or permit_id"):
        search_portal(settings=object(), county="", entity="", permit_id="")  # type: ignore[arg-type]


def test_permits_only_filters_client_side(
    monkeypatch: pytest.MonkeyPatch, docs: list[PortalDoc]
) -> None:
    """The sweep is always all-types; ``permits_only`` narrows the parsed rows."""
    payload = {"rows": [d.model_dump() for d in docs], "total_pages": 3, "truncated": False}
    monkeypatch.setattr("watermark.oepa.portal.cached_get", lambda *a, **k: payload)

    every = search_portal(settings=_settings(), county="CHAMPAIGN")
    permits = search_portal(settings=_settings(), county="CHAMPAIGN", permits_only=True)

    assert len(every) == 8
    assert {d.doc_type for d in permits} == {
        "Permit - Short Term",
        "Permit - Long Term",
        "Permit - Intermediate",
    }


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _doc(**overrides: Any) -> PortalDoc:
    base = {
        "docid": "1",
        "entity": "ACME",
        "doc_type": "Permit",
        "doc_date": "1/1/2026",
        "program": "NPDES",
        "county": "ALLEN",
        "permit_id": "1PD00001",
        "description": None,
        "url": "https://example.invalid/1",
    }
    return PortalDoc.model_validate(base | overrides)


def _settings() -> Any:
    from watermark.config import Settings

    return Settings(civic_offline=True)


# ---------------------------------------------------------------------------
# _is_truncated / PortalSweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "truncated", "why"),
    [
        ({"served": 1355, "pages_walked": 3, "last_page": 3, "total_pages": 3}, False, "complete"),
        # The portal caps one query at 2000 rows; a full 4th page is only 200 rows.
        ({"served": 2000, "pages_walked": 4, "last_page": 4, "total_pages": 4}, True, "capped"),
        # Pages overlap, so breaking on a no-new-rows page means rows were MISSED.
        ({"served": 1800, "pages_walked": 3, "last_page": 4, "total_pages": 4}, True, "early"),
        ({"served": 100, "pages_walked": 1, "last_page": 40, "total_pages": 91}, True, "budget"),
    ],
)
def test_is_truncated(kwargs: dict[str, int], truncated: bool, why: str) -> None:
    from watermark.oepa.portal import _is_truncated

    assert _is_truncated(**kwargs) is truncated, why


def test_sweep_reports_coverage_not_just_rows(
    monkeypatch: pytest.MonkeyPatch, docs: list[PortalDoc]
) -> None:
    from watermark.oepa.portal import sweep_portal

    payload = {
        "rows": [d.model_dump() for d in docs],
        "total_pages": 4,
        "pages_walked": 4,
        "rows_served": 2000,
        "truncated": True,
    }
    monkeypatch.setattr("watermark.oepa.portal.cached_get", lambda *a, **k: payload)
    sweep = sweep_portal(settings=_settings(), county="FRANKLIN")

    assert sweep.truncated is True
    assert sweep.rows_served == 2000
    # The row list alone would read as a clean 8-document result.
    assert len(sweep.docs) == 8


def test_search_portal_returns_only_the_rows(
    monkeypatch: pytest.MonkeyPatch, docs: list[PortalDoc]
) -> None:
    payload = {"rows": [d.model_dump() for d in docs], "total_pages": 1, "truncated": False}
    monkeypatch.setattr("watermark.oepa.portal.cached_get", lambda *a, **k: payload)
    assert [d.docid for d in search_portal(settings=_settings(), county="CHAMPAIGN")] == [
        d.docid for d in docs
    ]
