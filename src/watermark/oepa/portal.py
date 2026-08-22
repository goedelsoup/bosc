"""Ohio EPA eDocument portal — county x program document sweep.

The portal at ``edocpub.epa.ohio.gov`` is the only route that serves Ohio's **state**
permit numbers (``1PD00011``).  ECHO knows a facility by its *federal* NPDES id
(``OH0021806``) and by name, but the DAM permit URL
(:func:`watermark.oepa.fetch.dam_url`) is keyed by the state number — so without this
module a site's WWTP permit can only be found by keyword luck.  A county x ``NPDES``
sweep surfaces the county's water permits, which *is* the federal->state crosswalk:
match the ECHO facility name against :attr:`PortalDoc.entity` and read
:attr:`PortalDoc.permit_id`.  (How completely it surfaces them is the caveat below.)

Mechanics (ASP.NET WebForms, no auth, no rate limit observed):

1. ``GET`` the home page and scrape ``__VIEWSTATE`` / ``__VIEWSTATEGENERATOR`` /
   ``__EVENTVALIDATION``.
2. ``POST`` the search back to the same URL.  County (``…_104_1``) and Program
   (``…_109_1``) are **plain selects**, so a name-independent sweep is possible; the
   row connector must be flipped to ``And`` or the two criteria are OR-ed.
3. ``POST`` again against the *results* ViewState to raise the page size to 600 and to
   walk pages.  The pager exists only on the results page — sending it with the initial
   search returns HTTP 500.

A permit-number lookup must go through the **Secondary ID** criterion row; the row the
portal labels "Package/Permit Number" indexes nothing and answers every query with an
empty 200 (:data:`_DECOY_PERMIT_FIELD`).  That is the difference between "this permit has
no documents" and "we asked the wrong column", and the portal will not tell you which.

A county-wide sweep is **best-effort, not an enumeration**: the portal caps any one query
at :data:`_RESULT_CAP` rows and its pages overlap, so a large county returns fewer distinct
documents than it holds.  :func:`sweep_portal` reports that as :attr:`PortalSweep.truncated`.  To resolve
a specific facility's permit, search by ``entity`` — a narrow query stays under the cap.

Every result row collapses its fields into one ``" - "``-joined string, and **both** the
entity name (``SUTPHEN CORPORATION - URBANA``) and the doc type (``Permit - Short Term``)
may themselves contain that separator.  :func:`_parse_rows` therefore anchors on the
**doc date**, the one unambiguously-shaped field, and reads the fixed-offset columns to
its right.
"""

from __future__ import annotations

import html as _html
import re
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from pydantic import BaseModel, ConfigDict

from watermark.civic._http import BROWSER_HEADERS
from watermark.config import Settings
from watermark.connectors import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

PORTAL_URL = "https://edocpub.epa.ohio.gov/publicportal/edochome.aspx"
VIEW_DOCUMENT_URL = "https://edocpub.epa.ohio.gov/publicportal/ViewDocument.aspx?docid={docid}"

# Permits are slow-moving; a week-long cache keeps a repeat sweep off the network.
_PORTAL_CACHE_TTL_HOURS = 168

# The largest page size the results pager offers (10/20/30/50/100/250/600).
_MAX_PAGE_SIZE = 600

# A 600-row POST routinely takes over a minute, so the shared 30s civic timeout is a floor
# this connector has to raise; it is used as a minimum, not an override.
_MIN_REQUEST_TIMEOUT_S = 180.0

# Refuse to walk a pathological result set; a county x program sweep is ~3 pages.
_MAX_PAGES = 40

# The portal serves at most this many rows for any one query, whatever the pager claims:
# a 4-page result set ends in a 200-row page (600 + 600 + 600 + 200).  Worse, the pages
# OVERLAP -- consecutive pages re-serve docids seen on earlier ones (a GREENE x NPDES walk
# returned 600/600/600/200 rows but only 1665 distinct docids), so the underlying result
# order is not a stable partition and paging cannot fully enumerate a large county.
# Both facts are reported as ``truncated``; narrow with ``entity`` rather than trusting a
# big-county sweep to be complete.
_RESULT_CAP = 2000

# Doc type is filtered *client-side*: ``ctl00$search$ddlDocType`` is a postback-activated
# control, and sending a real id with the initial search returns HTTP 500 (only the
# "-1" all-types default is postable). Every permit row's doc type starts "Permit"
# ("Permit", "Permit - Short Term", "Permit - Long Term", "Permit - Intermediate").
_PERMIT_DOC_TYPE_PREFIX = "Permit"

_FIELD_PREFIX = "ctl00$search$KeywordPanel1$"
_COUNTY_FIELD = "ddlValue_-1_1_104_1"
_ENTITY_FIELD = "txtValue_-1_1_106_1"
_PROGRAM_FIELD = "ddlValue_-1_1_109_1"
# The permit number lives in **Secondary ID** (``…_111_1``), not in the row labelled
# "Package/Permit Number" (``…_121_1``).  That row is postable and indexes nothing: every
# value returns a well-formed 200 with zero rows, including permit numbers the portal has
# just served in its own results column.  Searching ``2GC08747`` there returns nothing
# while the same string in Secondary ID returns the permit's eight documents.
_SECONDARY_FIELD = "txtValue_-1_1_111_1"
_DECOY_PERMIT_FIELD = "txtValue_-1_1_121_1"

_PAGE_NUM_FIELD = "ctl00$results$DocHitList$DocHitList_CurrentPageNum"
_PAGE_SIZE_FIELD = "ctl00$results$DocHitList$DocHitList_CurrentPageSize"

_HIDDEN_FIELDS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")

_DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_ANCHOR_TEXT_RE = re.compile(r"<a[^>]*>([^<]*)</a>", re.S)
_DOCID_RE = re.compile(r"docid=(\d+)")
_TOTAL_PAGES_RE = re.compile(r"of (\d+)&nbsp;")

# An Ohio permit number: district digit, 2-3 letter type, 5 digits (``1PD00011``,
# ``1GRN00923``). Kept permissive — the field is reported verbatim either way.
PERMIT_ID_RE = re.compile(r"^\d[A-Z]{2,3}\d{5}$")


class PortalDoc(BaseModel):
    """One document row from the eDocument portal results table."""

    model_config = ConfigDict(extra="forbid")

    docid: str
    entity: str
    doc_type: str | None
    doc_date: str
    program: str
    county: str
    permit_id: str
    description: str | None
    url: str

    @property
    def is_permit_id(self) -> bool:
        """Whether ``permit_id`` has the shape of an Ohio state permit number."""
        return bool(PERMIT_ID_RE.match(self.permit_id))


class PortalSweep(BaseModel):
    """One portal query's rows plus the coverage facts needed to read them honestly."""

    model_config = ConfigDict(extra="forbid")

    docs: list[PortalDoc]
    total_pages: int
    pages_walked: int
    rows_served: int
    truncated: bool
    """True when this query hit the portal's row cap, ran out of page budget, or stopped
    on an overlapping page — i.e. the rows are a floor, not the full result set."""


def _hidden_fields(page: str) -> dict[str, str]:
    """Scrape the ASP.NET postback tokens out of a rendered page."""
    fields: dict[str, str] = {}
    for name in _HIDDEN_FIELDS:
        m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', page)
        if m:
            fields[name] = _html.unescape(m.group(1))
    return fields


def _split_entity_and_doc_type(left: str) -> tuple[str, str | None]:
    """Split the pre-date segments into entity name and doc type.

    Both halves may contain the ``" - "`` separator, so this cannot be done by position.
    The doc type is the *last* segment, plus a preceding segment when it is one of the
    portal's compound permit qualifiers (``Permit - Short Term``, ``DFFO - DFFO``).
    """
    segs = left.split(" - ")
    if len(segs) < 2:
        return left, None
    qualifiers = {"Short Term", "Long Term", "Intermediate", "DFFO"}
    if len(segs) >= 3 and segs[-1] in qualifiers:
        return " - ".join(segs[:-2]), f"{segs[-2]} - {segs[-1]}"
    return " - ".join(segs[:-1]), segs[-1]


def _parse_rows(page: str) -> list[PortalDoc]:
    """Extract every result row from a portal results page.

    Anchors on the doc date rather than counting segments from either end: the entity
    name and the doc type both admit the ``" - "`` separator, but exactly one field
    matches ``M/D/YYYY``, and the columns to its right are fixed-offset.
    """
    docs: list[PortalDoc] = []
    for row in _ROW_RE.findall(page):
        id_match = _DOCID_RE.search(row)
        if not id_match:
            continue
        cells = _CELL_RE.findall(row)
        if len(cells) < 3:
            continue
        text_match = _ANCHOR_TEXT_RE.search(cells[2])
        if not text_match:
            continue
        segs = [_html.unescape(s).strip() for s in text_match.group(1).split(" - ")]
        date_i = next((i for i, s in enumerate(segs) if _DATE_RE.match(s)), None)
        # Need program, county and secondary-id to the right of the date.
        if date_i is None or date_i + 3 >= len(segs):
            continue
        entity, doc_type = _split_entity_and_doc_type(" - ".join(segs[:date_i]))
        # Everything between the secondary id and the trailing docid echo is description,
        # padded with a variable number of empty segments ("1PY00002 -  -  -  - PTF285…").
        # Keep the segments that carry text; the padding is layout, not data.
        description = " - ".join(s for s in segs[date_i + 4 : -1] if s) or None
        docid = id_match.group(1)
        docs.append(
            PortalDoc(
                docid=docid,
                entity=entity,
                doc_type=doc_type,
                doc_date=segs[date_i],
                program=segs[date_i + 1],
                county=segs[date_i + 2],
                permit_id=segs[date_i + 3],
                description=description,
                url=VIEW_DOCUMENT_URL.format(docid=docid),
            )
        )
    return docs


def _search_form(
    hidden: dict[str, str],
    *,
    county: str,
    program: str,
    entity: str,
    permit_id: str,
) -> dict[str, str]:
    """Build the initial search POST body.

    Every criterion row is posted, empty or not, but a row's connector must be left at
    the page default ``Or`` unless the row actually carries a value: setting ``And`` on
    an *empty* row makes the portal discard the whole criteria set and return an
    unfiltered result page (observed: a CHAMPAIGN/NPDES sweep coming back with Franklin
    County 401-wetlands rows).  Only populated rows are joined with ``And``.

    ``permit_id`` is posted to **Secondary ID**, not to the row labelled "Package/Permit
    Number" — see :data:`_DECOY_PERMIT_FIELD`.
    """
    rows = (
        ("104_1", _COUNTY_FIELD, county),
        ("106_1", _ENTITY_FIELD, entity),
        ("109_1", _PROGRAM_FIELD, program),
        ("111_1", _SECONDARY_FIELD, permit_id),
        ("121_1", _DECOY_PERMIT_FIELD, ""),
    )
    form = dict(hidden)
    for suffix, field, value in rows:
        form[_FIELD_PREFIX + field] = value
        form[_FIELD_PREFIX + f"ddlOp_-1_1_{suffix}"] = "Equal"
        form[_FIELD_PREFIX + f"ddlConn_-1_1_{suffix}"] = "And" if value else "Or"
    form.update(
        {
            _FIELD_PREFIX + "txtFrom": "",
            _FIELD_PREFIX + "txtTo": "",
            "ctl00$search$txtFullText": "",
            "ctl00$search$ddlDocType": "-1",
            "ctl00$search$btnSearch": "Search",
        }
    )
    return form


def _is_truncated(*, served: int, pages_walked: int, last_page: int, total_pages: int) -> bool:
    """Whether a completed walk is an undercount of the portal's real result set.

    Three independent ways that happens, none visible in the row count alone:

    * **capped** — the portal refuses to serve more than :data:`_RESULT_CAP` rows for one
      query, and a 4-page set ends in a short 200-row page.
    * **stopped early** — the walk broke before the last reported page because a page
      returned nothing new; the pages overlap, so this means rows were missed, not that
      the set was exhausted.
    * **over page budget** — the result set claims more pages than :data:`_MAX_PAGES`.
    """
    return served >= _RESULT_CAP or pages_walked < last_page or total_pages > _MAX_PAGES


def _live_search(
    *,
    county: str,
    program: str,
    entity: str,
    permit_id: str,
    timeout_s: float,
) -> dict[str, Any]:
    """Run the full search + paging flow and return raw row dicts."""
    with httpx.Client(headers=BROWSER_HEADERS, timeout=timeout_s, follow_redirects=True) as client:
        home = client.get(PORTAL_URL)
        home.raise_for_status()
        form = _search_form(
            _hidden_fields(home.text),
            county=county,
            program=program,
            entity=entity,
            permit_id=permit_id,
        )
        results = client.post(PORTAL_URL, data=form)
        results.raise_for_status()

        # The pager lives only on the results page; widen it before walking.
        wide = dict(_hidden_fields(results.text))
        wide.update(
            {
                "__EVENTTARGET": _PAGE_SIZE_FIELD,
                "__EVENTARGUMENT": "",
                _PAGE_NUM_FIELD: "1",
                _PAGE_SIZE_FIELD: str(_MAX_PAGE_SIZE),
            }
        )
        page = client.post(PORTAL_URL, data=wide)
        page.raise_for_status()

        rows = _parse_rows(page.text)
        seen = {d.docid for d in rows}
        served = len(rows)
        total_match = _TOTAL_PAGES_RE.search(page.text)
        total_pages = int(total_match.group(1)) if total_match else 1
        last_page = min(total_pages, _MAX_PAGES)
        pages_walked = 1

        for page_num in range(2, last_page + 1):
            nxt = dict(_hidden_fields(page.text))
            nxt.update(
                {
                    "__EVENTTARGET": _PAGE_NUM_FIELD,
                    "__EVENTARGUMENT": "",
                    _PAGE_NUM_FIELD: str(page_num),
                    _PAGE_SIZE_FIELD: str(_MAX_PAGE_SIZE),
                }
            )
            page = client.post(PORTAL_URL, data=nxt)
            page.raise_for_status()
            parsed = _parse_rows(page.text)
            pages_walked = page_num
            served += len(parsed)
            fresh = [d for d in parsed if d.docid not in seen]
            # The pager stops advancing at the end of the capped set and re-serves the
            # last page forever; without this the walk would spin to _MAX_PAGES.
            if not fresh:
                break
            seen.update(d.docid for d in fresh)
            rows.extend(fresh)

    return {
        "rows": [d.model_dump() for d in rows],
        "total_pages": total_pages,
        "pages_walked": pages_walked,
        "rows_served": served,
        "truncated": _is_truncated(
            served=served,
            pages_walked=pages_walked,
            last_page=last_page,
            total_pages=total_pages,
        ),
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def sweep_portal(
    *,
    settings: Settings,
    county: str = "",
    program: str = "NPDES",
    entity: str = "",
    permit_id: str = "",
    permits_only: bool = False,
) -> PortalSweep:
    """Search the eDocument portal and return the matching rows with their coverage facts.

    ``county`` and ``program`` are portal vocabulary (``"CHAMPAIGN"``, ``"NPDES"``) and
    are intersected.  ``entity`` matches the Entity Name field; ``permit_id`` matches the
    **Secondary ID** field, which is where the portal indexes the state permit number —
    the row labelled "Package/Permit Number" matches nothing at all
    (:data:`_DECOY_PERMIT_FIELD`).  Both text fields take a bare term as a *prefix* match
    and support ``*`` wildcards — ``"*XENIA*"`` is the contains-search, and is the way to
    resolve one facility without a county-wide (and possibly ``truncated``) sweep.  The
    field operator is Equal/Not-Equal only; there is no "contains" operator.  ``permits_only`` keeps just the ``Permit*`` doc types —
    a **client-side** filter, because the portal's own doc-type select cannot be set on
    the initial search (see :data:`_PERMIT_DOC_TYPE_PREFIX`).

    The sweep itself is always all-types, so one cached pull backs every filtered view.
    Results are cached for a week and replayed from a committed fixture when
    ``settings.civic_offline`` is set.
    """
    if not any((county, entity, permit_id)):
        raise ValueError("sweep_portal needs at least one of county, entity or permit_id")

    params = {
        "county": county,
        "program": program,
        "entity": entity,
        "permit_id": permit_id,
    }

    def fetch() -> Any:
        return _live_search(
            county=county,
            program=program,
            entity=entity,
            permit_id=permit_id,
            timeout_s=max(settings.civic_request_timeout_s, _MIN_REQUEST_TIMEOUT_S),
        )

    payload = cast(
        "dict[str, Any]",
        cached_get(
            "oepa_portal",
            params,
            fetch,
            cache_dir=settings.civic_cache_dir,
            offline=settings.civic_offline,
            fixtures_dir=settings.civic_fixtures_dir,
            ttl_hours=_PORTAL_CACHE_TTL_HOURS,
        ),
    )

    docs = [PortalDoc.model_validate(r) for r in payload.get("rows", [])]
    if permits_only:
        docs = [d for d in docs if d.doc_type and d.doc_type.startswith(_PERMIT_DOC_TYPE_PREFIX)]
    if payload.get("truncated"):
        # Never let a capped walk read as a complete sweep.
        log.warning(
            "oepa.portal.truncated",
            county=county,
            program=program,
            entity=entity,
            total_pages=payload.get("total_pages"),
            pages_walked=payload.get("pages_walked"),
            rows_served=payload.get("rows_served"),
            distinct=len(docs),
            note=(
                f"portal caps a result set at {_RESULT_CAP} rows and re-serves overlapping "
                "pages; narrow the query (entity=) instead of trusting this sweep as complete"
            ),
        )
    log.info(
        "oepa.portal.search",
        county=county,
        program=program,
        entity=entity,
        permits_only=permits_only,
        docs=len(docs),
    )
    return PortalSweep(
        docs=docs,
        total_pages=int(payload.get("total_pages", 1)),
        pages_walked=int(payload.get("pages_walked", 1)),
        rows_served=int(payload.get("rows_served", len(docs))),
        truncated=bool(payload.get("truncated", False)),
    )


def search_portal(
    *,
    settings: Settings,
    county: str = "",
    program: str = "NPDES",
    entity: str = "",
    permit_id: str = "",
    permits_only: bool = False,
) -> list[PortalDoc]:
    """Return just the rows from :func:`sweep_portal`.

    Convenience for callers that have already accepted the coverage caveat; anything that
    reports results to a human should use :func:`sweep_portal` and surface ``truncated``.
    """
    return sweep_portal(
        settings=settings,
        county=county,
        program=program,
        entity=entity,
        permit_id=permit_id,
        permits_only=permits_only,
    ).docs


def permit_crosswalk(docs: list[PortalDoc]) -> dict[str, str]:
    """Reduce portal rows to ``{state permit id: entity name}``.

    Rows whose secondary-id field is not permit-shaped are dropped; the first entity
    seen for an id wins.
    """
    crosswalk: dict[str, str] = {}
    for d in docs:
        if d.is_permit_id:
            crosswalk.setdefault(d.permit_id, d.entity)
    return crosswalk
