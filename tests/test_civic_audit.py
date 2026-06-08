"""Completeness audit: cadence parsing, expected-date generation, gap detection."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from bosc.civic.audit import (
    Cadence,
    audit_body,
    expected_dates,
    nth_weekday,
    parse_cadence,
    write_audit,
)
from bosc.civic.models import Subdivision
from bosc.config import Settings


def test_parse_cadence() -> None:
    assert parse_cadence("2nd & 4th Monday, 7:00 PM") == Cadence(0, (2, 4))
    assert parse_cadence("2nd & last Monday, 7:30 PM") == Cadence(0, (2, "last"))
    assert parse_cadence("1st Tuesday, 7:30 PM") == Cadence(1, (1,))
    assert parse_cadence("2nd Tuesday, 8:00 PM") == Cadence(1, (2,))
    # Irregular ("after" clause) and empty -> not machine-parseable.
    assert parse_cadence("1st Thursday after 1st Monday, 7:30 PM (Community Building)") is None
    assert parse_cadence(None) is None
    assert parse_cadence("when needed") is None


def test_nth_weekday() -> None:
    # Jan 2026: Mondays are the 5th, 12th, 19th, 26th.
    assert nth_weekday(2026, 1, 0, 2) == date(2026, 1, 12)
    assert nth_weekday(2026, 1, 0, "last") == date(2026, 1, 26)
    assert nth_weekday(2026, 1, 0, 5) is None  # no 5th Monday


def test_expected_dates_in_span() -> None:
    cadence = Cadence(0, (2, 4))  # 2nd & 4th Monday
    got = expected_dates(cadence, date(2026, 1, 1), date(2026, 2, 28))
    assert got == [date(2026, 1, 12), date(2026, 1, 26), date(2026, 2, 9), date(2026, 2, 23)]


def _seed_index(tmp: Path, slug: str, dates: list[str]) -> Settings:
    settings = Settings(data_dir=tmp)
    docs = [
        {"kind": "minutes", "body": None, "date_verified": d, "date_listing": d, "hits": []}
        for d in dates
    ]
    out = settings.extracted_dir / slug / "meetings" / "meeting-index.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump({"meta": {"slug": slug}, "documents": docs}), encoding="utf-8")
    return settings


def _body(slug: str, schedule: str) -> Subdivision:
    return Subdivision(slug=slug, name=slug.title(), type="township", meeting_schedule=schedule)


def test_audit_body_flags_missing_and_special(tmp_path: Path) -> None:
    # Have the 2nd Monday of Jan + an off-schedule 20th + the 4th Monday of Feb.
    settings = _seed_index(tmp_path, "x-township", ["2026-01-12", "2026-01-20", "2026-02-23"])
    report = audit_body(_body("x-township", "2nd & 4th Monday, 7:00 PM"), settings=settings)
    assert report is not None and report.parsed
    assert report.span_start == "2026-01-12" and report.span_end == "2026-02-23"
    # Expected in span: Jan12, Jan26, Feb9, Feb23. We have Jan12 + Feb23.
    assert report.expected == 4
    assert report.present == 2
    assert report.coverage == 0.5
    assert report.missing == ["2026-01-26", "2026-02-09"]  # the records-request worklist
    assert report.special == ["2026-01-20"]  # off-schedule session


def test_audit_body_none_when_not_ingested(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    assert audit_body(_body("y-township", "1st Tuesday"), settings=settings) is None


def test_audit_irregular_schedule_lists_specials_only(tmp_path: Path) -> None:
    settings = _seed_index(tmp_path, "z-village", ["2026-01-08", "2026-02-12"])
    report = audit_body(_body("z-village", "1st Thursday after 1st Monday"), settings=settings)
    assert report is not None and not report.parsed
    assert report.expected == 0
    assert report.special == ["2026-01-08", "2026-02-12"]


def test_write_audit_shape(tmp_path: Path) -> None:
    settings = _seed_index(tmp_path, "x-township", ["2026-01-12", "2026-02-23"])
    report = audit_body(_body("x-township", "2nd & 4th Monday"), settings=settings)
    assert report is not None
    out = write_audit(report, tmp_path / "completeness-audit.yaml")
    doc = yaml.safe_load(out.read_text())
    assert doc["meta"]["slug"] == "x-township"
    assert "CANDIDATE" in doc["meta"]["caveat"]
    assert doc["missing"] == report.missing
