"""Ohio LSC Status Report of Legislation connector.

Pulls the per-General-Assembly **Status Report of Legislation** published by the
Ohio Legislative Service Commission at ``statusreport.lsc.ohio.gov``. For a given
GA (e.g. the 136th) the site offers the whole report as a single authoritative
spreadsheet — ``/<ga>/files/<ga>th-ga-status-report.xlsx`` — which is the source
of truth here. The browseable HTML index only carries number/sponsor/title; the
xlsx carries the legislative-milestone columns (chamber-by-chamber introduction,
committee assignment/report, third-consideration passage, conference, concurrence,
governor action, effective date) and the running "Note" of recent action.

This is **not** a hydrology source, but it reuses the connector machinery —
:func:`_cache.cached_get` (on-disk cache + TTL + offline/committed-fixture
fallback) — so a rerun never re-fetches and tests stay hermetic. The xlsx is
parsed to a plain JSON payload (the cached/fixture artifact is readable JSON, not
a binary workbook); values are passed through **verbatim** from the workbook —
this module never fabricates or normalizes away a date, sponsor, or status.

The workbook is parsed with the standard library (``zipfile`` + ``ElementTree``)
to avoid an openpyxl dependency. Synchronous (``httpx``) to match BOSC's pipeline.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

import httpx
import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_str
from watermark.hydrology.connectors._cache import cached_get
from watermark.logging import get_logger

log = get_logger(__name__)

_SS_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Column letter -> field, by position in the LSC workbook (verified against the
# 136th GA report). Two sponsor columns (C/D) share the merged "Primary Sponsor(s)"
# header; F-I are the House milestone block, J-M the Senate block.
_COLUMNS: dict[str, str] = {
    "A": "bill_type",  # "H. B.", "S. B.", "H. R.", "S. C. R.", ...
    "B": "number",
    "C": "sponsor_1",
    "D": "sponsor_2",
    "E": "short_title",
    "F": "house_introduced",
    "G": "house_cmte_assigned",
    "H": "house_cmte_reported",
    "I": "house_passed_3rd",
    "J": "senate_introduced",
    "K": "senate_cmte_assigned",
    "L": "senate_cmte_reported",
    "M": "senate_passed_3rd",
    "N": "to_conf_cmte",
    "O": "concurrence",
    "P": "gov_action",
    "Q": "effective_date",
    "R": "note",
}

# High-confidence row-2 header tokens (case-insensitive substring) used to VALIDATE the
# positional letter map above before trusting it (WS-25 / #1625). The letter map is only valid
# while the workbook keeps its column layout; if the LSC re-orders/inserts a column, binding by
# A1 letter would silently mislabel every field. Only a few near-certain anchors are checked so a
# benign header re-wording warns (loud, auditable) rather than hard-failing the pull.
_HEADER_ANCHORS: dict[str, str] = {
    "C": "sponsor",  # merged "Primary Sponsor(s)" header (C/D)
    "E": "title",  # short-title column
    "R": "note",  # trailing running-note column
}


class ChamberProgress(BaseModel):
    """One chamber's milestone dates/codes, verbatim from the workbook.

    Each field is the raw cell text (e.g. ``"1/23/2025"``, a committee code like
    ``"H. PS"``, or a date with a trailing chamber marker). ``None`` means the
    cell was empty — never an inferred default.
    """

    model_config = ConfigDict(extra="forbid")

    introduced: str | None = None
    cmte_assigned: str | None = None
    cmte_reported: str | None = None
    passed_3rd: str | None = None


class Bill(BaseModel):
    """One measure (bill/resolution) and its status across both chambers."""

    model_config = ConfigDict(extra="forbid")

    identifier: str  # normalized, e.g. "HB 1", "SCR 12"
    bill_type: str | None  # raw type as published, e.g. "H. B."
    number: str | None
    sponsors: list[str]  # primary sponsor(s), in workbook order
    short_title: str | None
    house: ChamberProgress
    senate: ChamberProgress
    to_conf_cmte: str | None = None
    concurrence: str | None = None
    gov_action: str | None = None
    effective_date: str | None = None
    note: str | None = None

    @classmethod
    def from_row(cls, row: dict[str, str | None]) -> Bill:
        bill_type = to_str(row.get("bill_type"))
        number = to_str(row.get("number"))
        sponsors = [s for s in (to_str(row.get("sponsor_1")), to_str(row.get("sponsor_2"))) if s]
        return cls(
            identifier=_identifier(bill_type, number),
            bill_type=bill_type,
            number=number,
            sponsors=sponsors,
            short_title=to_str(row.get("short_title")),
            house=ChamberProgress(
                introduced=to_str(row.get("house_introduced")),
                cmte_assigned=to_str(row.get("house_cmte_assigned")),
                cmte_reported=to_str(row.get("house_cmte_reported")),
                passed_3rd=to_str(row.get("house_passed_3rd")),
            ),
            senate=ChamberProgress(
                introduced=to_str(row.get("senate_introduced")),
                cmte_assigned=to_str(row.get("senate_cmte_assigned")),
                cmte_reported=to_str(row.get("senate_cmte_reported")),
                passed_3rd=to_str(row.get("senate_passed_3rd")),
            ),
            to_conf_cmte=to_str(row.get("to_conf_cmte")),
            concurrence=to_str(row.get("concurrence")),
            gov_action=to_str(row.get("gov_action")),
            effective_date=to_str(row.get("effective_date")),
            note=to_str(row.get("note")),
        )


class StatusReport(BaseModel):
    """The full status report for one General Assembly."""

    model_config = ConfigDict(extra="forbid")

    ga: str
    as_of: str | None  # the workbook's "Reflects legislative action through ..." note
    source_url: str
    bills: list[Bill]


def _identifier(bill_type: str | None, number: str | None) -> str:
    """Normalize ``("H. B.", "1") -> "HB 1"``; falls back gracefully if either is missing."""
    abbr = "".join(ch for ch in (bill_type or "") if ch.isalnum())
    num = (number or "").strip()
    return f"{abbr} {num}".strip()


def _ordinal_suffix(ga: str) -> str:
    """English ordinal suffix for a GA number string ("136" -> "th", "133" -> "rd")."""
    try:
        n = int(ga)
    except ValueError:
        return "th"
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _xlsx_url(settings: Settings, ga: str) -> str:
    return f"{settings.lsc_base_url}/{ga}/files/{ga}{_ordinal_suffix(ga)}-ga-status-report.xlsx"


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    """Resolved text of one cell: shared-string, inline string, or literal value."""
    t = cell.get("t")
    if t == "s":  # shared string, value is the index
        v = cell.find(_SS_NS + "v")
        if v is not None and v.text is not None:
            return shared[int(v.text)]
        return ""
    if t == "inlineStr":
        is_el = cell.find(_SS_NS + "is")
        return (
            "".join(node.text or "" for node in is_el.iter(_SS_NS + "t"))
            if is_el is not None
            else ""
        )
    v = cell.find(_SS_NS + "v")
    return v.text or "" if v is not None else ""


def _col_letter(ref: str) -> str:
    """Column letters from an A1-style cell ref ("AB12" -> "AB")."""
    return "".join(ch for ch in ref if ch.isalpha())


def _header_mismatches(header_cells: dict[str, str]) -> list[str]:
    """Anchor columns whose row-2 header doesn't carry the expected token (WS-25 / #1625).

    Returns a human-readable mismatch per :data:`_HEADER_ANCHORS` anchor that fails, so the
    caller can surface a column-layout shift before the letter map (:data:`_COLUMNS`) mislabels
    every field. An empty list means the checked headers line up with the map.
    """
    out: list[str] = []
    for col, token in _HEADER_ANCHORS.items():
        label = (header_cells.get(col) or "").strip().lower()
        if token not in label:
            out.append(f"col {col}: expected header ~{token!r}, got {header_cells.get(col)!r}")
    return out


def parse_workbook(content: bytes) -> dict[str, Any]:
    """Parse an LSC status-report .xlsx into a JSON-serializable payload.

    Returns ``{"as_of": str|None, "rows": [{field: value, ...}, ...]}`` where each
    row's keys are the named fields from :data:`_COLUMNS` and values are the raw
    cell text. Row 1 is the "Reflects legislative action through ..." note; row 2
    is the header; data rows follow.
    """
    with zipfile.ZipFile(BytesIO(content)) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in si.iter(_SS_NS + "t")) for si in ss_root]
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    data = sheet.find(_SS_NS + "sheetData")
    rows = list(data.findall(_SS_NS + "row")) if data is not None else []

    as_of: str | None = None
    parsed: list[dict[str, str | None]] = []
    for row in rows:
        cells = {
            _col_letter(c.get("r", "")): _cell_text(c, shared).strip()
            for c in row.findall(_SS_NS + "c")
        }
        rownum = row.get("r")
        if rownum == "1":  # banner: "Reflects legislative action through MM/DD/YYYY"
            as_of = next((v for v in cells.values() if v), None)
            continue
        if rownum == "2":  # header row — validate the letter map before trusting it (WS-25)
            mismatches = _header_mismatches(cells)
            if mismatches:
                log.warning("lsc.header_layout_drift", mismatches=mismatches, header=cells)
            continue
        if not any(cells.values()):
            continue
        record = {field: (cells.get(col) or None) for col, field in _COLUMNS.items()}
        parsed.append(record)

    return {"as_of": as_of, "rows": parsed}


def fetch_status_report(ga: str | None = None, *, settings: Settings | None = None) -> StatusReport:
    """Fetch (or replay from cache/fixture) the LSC status report for a GA.

    ``ga`` defaults to ``settings.lsc_default_ga``. The workbook is downloaded once
    and cached as parsed JSON; offline runs serve the cache or a committed fixture.
    """
    settings = settings or get_settings()
    ga = ga or settings.lsc_default_ga
    url = _xlsx_url(settings, ga)
    params = {"_source": "lsc-status-xlsx", "ga": ga}

    def fetch() -> Any:
        log.info("lsc.fetch", ga=ga, url=url)
        resp = httpx.get(url, timeout=settings.hydro_request_timeout_s, follow_redirects=True)
        resp.raise_for_status()
        return parse_workbook(resp.content)

    payload = cast("dict[str, Any]", cached_get("lsc", params, fetch, settings=settings))
    bills = [Bill.from_row(row) for row in payload.get("rows", [])]
    return StatusReport(ga=ga, as_of=payload.get("as_of"), source_url=url, bills=bills)


# --- Reference dataset assembly --------------------------------------------


def _bill_record(bill: Bill) -> dict[str, Any]:
    """One bill as a YAML-ready mapping; ``None`` is a genuine empty cell."""
    return {
        "identifier": bill.identifier,
        "bill_type": bill.bill_type,
        "number": bill.number,
        "sponsors": bill.sponsors,
        "short_title": bill.short_title,
        "house": bill.house.model_dump(),
        "senate": bill.senate.model_dump(),
        "to_conf_cmte": bill.to_conf_cmte,
        "concurrence": bill.concurrence,
        "gov_action": bill.gov_action,
        "effective_date": bill.effective_date,
        "note": bill.note,
    }


def _type_counts(bills: list[Bill]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bill in bills:
        key = (bill.bill_type or "?").strip()
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def write_status_report(report: StatusReport, out_dir: Path) -> Path:
    """Write the status report as one YAML file with a ``meta:`` provenance block.

    Deterministic — the only date in the output is the workbook's own ``as_of``, so
    re-running ``watermark lsc`` for an unchanged report regenerates identical bytes.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"status-report.{report.ga}.yaml"
    doc = {
        "meta": {
            "subject": f"Ohio {report.ga}th GA — Status Report of Legislation",
            "source": "Ohio Legislative Service Commission (LSC) — statusreport.lsc.ohio.gov",
            "source_url": report.source_url,
            "as_of": report.as_of,
            "count": len(report.bills),
            "type_counts": _type_counts(report.bills),
            "caveats": [
                "Values are verbatim from the LSC status-report workbook; nothing is inferred.",
                "Dates/codes are kept as published (raw strings), including any chamber markers.",
                "Only the primary sponsor(s) are reported (the workbook's two sponsor columns).",
            ],
        },
        "bills": [_bill_record(b) for b in report.bills],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
