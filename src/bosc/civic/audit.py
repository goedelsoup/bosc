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
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.civic.models import Subdivision
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

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
    """A parsed standing schedule: a weekday + which occurrences in the month."""

    weekday: int  # Monday=0 .. Sunday=6
    ordinals: tuple[int | str, ...]  # e.g. (2, 4) or (2, "last") or (1,)


def parse_cadence(schedule: str | None) -> Cadence | None:
    """Parse "2nd & 4th Monday" / "2nd & last Monday" / "1st Tuesday" into a Cadence.

    Returns ``None`` for an empty/irregular schedule (e.g. Lafayette's "1st Thursday
    after 1st Monday" — the "after" clause can't be a simple nth-weekday rule).
    """
    if not schedule or "after" in schedule.lower():
        return None
    wd = _WEEKDAY_RE.search(schedule)
    ords = _ORDINAL_RE.findall(schedule)
    if not wd or not ords:
        return None
    seen: list[int | str] = []
    for o in ords:
        val = _ORDINALS[o.lower()]
        if val not in seen:
            seen.append(val)
    return Cadence(weekday=_WEEKDAYS[wd.group(1).lower()], ordinals=tuple(seen))


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
    """Every scheduled meeting date the cadence implies within ``[start, end]``."""
    out: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        for n in cadence.ordinals:
            d = nth_weekday(year, month, cadence.weekday, n)
            if d and start <= d <= end:
                out.append(d)
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
        settings.extracted_dir / subdivision.slug / "meetings" / "meeting-index.yaml"
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
    if not actual:
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
    actual_dates = {date.fromisoformat(a) for a in actual if _is_iso(a)}
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


def write_audit(report: AuditReport, out_path: Path) -> Path:
    """Write the completeness audit YAML (the records-request worklist)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"{report.slug} meeting-completeness audit",
            "slug": report.slug,
            "schedule": report.schedule,
            "method": "expected meeting dates from the standing cadence vs. ingested "
            "meeting-index dates, bounded to the ingested span.",
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
