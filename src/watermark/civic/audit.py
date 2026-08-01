"""Completeness audit: ingested minutes vs. the body's grounded meeting cadence.

Each registry entry carries the body's *standing* meeting schedule (e.g. American =
"2nd & last Monday"). This compares the dates we actually ingested (from the
meeting index) against the dates that cadence *should* have produced over the span
we cover, and reports the gaps — a concrete public-records-request worklist (which
body + which date to ask for) — plus the off-schedule "special" meetings we did get.

A flagged gap is a **candidate to verify**, not proof a meeting was withheld: a
cadence can change over the years, and a meeting can be cancelled. The audit says
"the schedule expected a meeting here and we don't have it," nothing more.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.civic.layout import meetings_dir
from watermark.civic.models import Subdivision
from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_ORDINALS: dict[str, int | str] = {
    "1st": 1,
    "first": 1,
    "2nd": 2,
    "second": 2,
    "3rd": 3,
    "third": 3,
    "4th": 4,
    "fourth": 4,
    "last": "last",
}
_ORDINAL_RE = re.compile(r"\b(1st|first|2nd|second|3rd|third|4th|fourth|last)\b", re.IGNORECASE)
_WEEKDAY_RE = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Cadence:
    """A parsed standing schedule: weekday(s) + which occurrences in the month.

    ``ordinals`` empty means **every** occurrence of those weekdays — a weekly board
    ("9:30 am Tuesday & Thursday"), not a monthly one.
    """

    weekdays: tuple[int, ...]  # Monday=0 .. Sunday=6
    ordinals: tuple[int | str, ...]  # e.g. (2, 4) or (2, "last") or (1,); () = weekly


def parse_cadence(schedule: str | None) -> Cadence | None:
    """Parse a standing schedule into a Cadence.

    Handles the monthly nth-weekday forms ("2nd & 4th Monday", "2nd & last Monday",
    "1st Tuesday") and the **weekly** form — one or more weekdays with no ordinal at
    all ("Regular Meeting: 9:30 am Tuesday & Thursday", Hancock County's board, #1839).
    A weekly board is the shape Lima's six bodies never had, so it used to parse to
    ``None`` and the audit reported no coverage at all for it.

    Returns ``None`` for an empty/irregular schedule (e.g. Lafayette's "1st Thursday
    after 1st Monday" — the "after" clause can't be a simple nth-weekday rule).
    """
    if not schedule or "after" in schedule.lower():
        return None
    wds = _WEEKDAY_RE.findall(schedule)
    ords = _ORDINAL_RE.findall(schedule)
    if not wds:
        return None
    seen_wd: list[int] = []
    for w in wds:
        day = _WEEKDAYS[w.lower()]
        if day not in seen_wd:
            seen_wd.append(day)
    seen: list[int | str] = []
    for o in ords:
        val = _ORDINALS[o.lower()]
        if val not in seen:
            seen.append(val)
    # An ordinal list is read as applying to the ONE weekday it qualifies; "2nd & 4th Monday"
    # names a single day. Multiple weekdays alongside ordinals is a shape no committed roster
    # uses and would be ambiguous ("1st Monday & 3rd Tuesday"), so keep the historical
    # single-weekday reading there rather than guessing a cross product.
    if seen:
        return Cadence(weekdays=(seen_wd[0],), ordinals=tuple(seen))
    return Cadence(weekdays=tuple(seen_wd), ordinals=())


def nth_weekday(year: int, month: int, weekday: int, n: int | str) -> date | None:
    """The ``n``-th ``weekday`` of a month (``n`` is 1-4 or "last"); ``None`` if absent."""
    days = [
        d
        for d in calendar.Calendar().itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    if n == "last":
        return days[-1] if days else None
    idx = int(n) - 1
    return days[idx] if 0 <= idx < len(days) else None


def expected_dates(cadence: Cadence, start: date, end: date) -> list[date]:
    """Every scheduled meeting date the cadence implies within ``[start, end]``.

    Ordinals apply to **every month in the span** — a month-range qualifier printed in the
    schedule text ("First Tuesday of the Month, 7:00 pm February-December") is not honoured, so
    a body that recesses is expected to have met in its recess month. With no ordinals the
    cadence is weekly: every occurrence of each named weekday in the span.
    """
    out: list[date] = []
    if not cadence.ordinals:
        d = start
        while d <= end:
            if d.weekday() in cadence.weekdays:
                out.append(d)
            d += timedelta(days=1)
        return out
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        for weekday in cadence.weekdays:
            for n in cadence.ordinals:
                d2 = nth_weekday(year, month, weekday, n)
                if d2 and start <= d2 <= end:
                    out.append(d2)
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return sorted(out)


class AuditReport(BaseModel):
    """Coverage of one body's ingested minutes against its standing cadence."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    schedule: str | None  # the verbatim cadence string
    parsed: bool  # whether the cadence was machine-parseable
    span_start: str | None
    span_end: str | None
    expected: int  # scheduled meetings in span
    present: int  # scheduled meetings we have
    coverage: float  # present / expected (0..1), 0.0 when expected==0
    missing: list[str]  # scheduled dates we DON'T have -> records-request worklist
    special: list[str]  # dates we have that are OFF the standing schedule


def audit_body(
    subdivision: Subdivision,
    *,
    settings: Settings | None = None,
    index_path: Path | None = None,
) -> AuditReport | None:
    """Audit one body's meeting index against its cadence; ``None`` if not ingested."""
    settings = settings or get_settings()
    index_path = index_path or (
        meetings_dir(settings.extracted_dir, subdivision.slug, settings) / "meeting-index.yaml"
    )
    if not index_path.exists():
        return None
    data = yaml.safe_load(index_path.read_text(encoding="utf-8")) or {}
    actual = sorted(
        {
            str(d.get("date_verified") or d.get("date_listing"))
            for d in data.get("documents", [])
            if isinstance(d, dict) and (d.get("date_verified") or d.get("date_listing"))
        }
    )
    cadence = parse_cadence(subdivision.meeting_schedule)
    # Skip impossible calendar dates (e.g. a Feb 30 from a malformed source link, #615): the
    # `_is_iso` regex admits them but `date.fromisoformat` would crash. A non-empty `actual`
    # can thus yield no usable dates — guard on `actual_dates`, not the raw strings.
    actual_dates = {d for a in actual if (d := _parse_iso(a)) is not None}
    if not actual_dates:
        return AuditReport(
            slug=subdivision.slug,
            schedule=subdivision.meeting_schedule,
            parsed=cadence is not None,
            span_start=None,
            span_end=None,
            expected=0,
            present=0,
            coverage=0.0,
            missing=[],
            special=[],
        )
    start, end = min(actual_dates), max(actual_dates)
    if cadence is None:
        return AuditReport(
            slug=subdivision.slug,
            schedule=subdivision.meeting_schedule,
            parsed=False,
            span_start=start.isoformat(),
            span_end=end.isoformat(),
            expected=0,
            present=0,
            coverage=0.0,
            missing=[],
            special=sorted(d.isoformat() for d in actual_dates),
        )
    expected = set(expected_dates(cadence, start, end))
    present = expected & actual_dates
    missing = expected - actual_dates
    special = actual_dates - expected
    return AuditReport(
        slug=subdivision.slug,
        schedule=subdivision.meeting_schedule,
        parsed=True,
        span_start=start.isoformat(),
        span_end=end.isoformat(),
        expected=len(expected),
        present=len(present),
        coverage=round(len(present) / len(expected), 3) if expected else 0.0,
        missing=sorted(d.isoformat() for d in missing),
        special=sorted(d.isoformat() for d in special),
    )


def _is_iso(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def _parse_iso(s: str) -> date | None:
    """Parse an ISO ``yyyy-mm-dd`` string, or ``None`` if it isn't a real calendar date.

    The ``_is_iso`` regex admits impossible dates (e.g. ``2024-02-30``) that crash
    ``date.fromisoformat``; this keeps the audit robust to a single bad source link (#615).
    """
    if not _is_iso(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def write_audit(report: AuditReport, out_path: Path) -> Path:
    """Write the completeness audit YAML (the records-request worklist)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"{report.slug} meeting-completeness audit",
            "slug": report.slug,
            "schedule": report.schedule,
            "method": "expected meeting dates from the standing cadence vs. ingested "
            "meeting-index dates, bounded to the ingested span. The cadence model reads "
            "weekday(s) + ordinal(s) only: ordinals are applied to EVERY month in the span "
            "and a schedule with no ordinal is read as weekly. A month-range qualifier in "
            "the schedule text (e.g. 'February-December') is NOT honoured, so a body that "
            "recesses is expected to have met in its recess month and `expected` overcounts "
            "there.",
            "caveat": "A missing date is a CANDIDATE to verify/request, not proof of "
            "withholding — cadences change and meetings get cancelled.",
            "span": [report.span_start, report.span_end],
            "expected": report.expected,
            "present": report.present,
            "coverage": report.coverage,
            "missing_count": len(report.missing),
            "special_count": len(report.special),
        },
        "missing": report.missing,  # records-request worklist
        "special_meetings": report.special,  # off-schedule sessions we did get
    }
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_path
