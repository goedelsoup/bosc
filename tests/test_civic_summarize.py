"""Meeting summarization: corridor selection, grounded extraction, output shape.

Hermetic: a real StructuredExtractor with an injected fake Anthropic client (no
network/keys), so the forced-tool-use path runs without calling the API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from bosc.agent.extractor import StructuredExtractor
from bosc.civic.models import Subdivision
from bosc.civic.summarize import (
    MeetingSummary,
    summarize_corridor_meetings,
    summarize_meeting,
    write_summaries,
)
from bosc.config import Settings

_PAYLOAD = {
    "summary": "The board discussed the Bistrozzi data-center rezoning request.",
    "corridor_relevance": "Names the Bistrozzi LLC hyperscale data center.",
    "decisions": ["Motion to recommend rezoning passed 3-0"],
    "parties": ["Bistrozzi LLC", "Trustee Harmon"],
    "parcels": ["36-0100-03-002.000"],
    "dollar_figures": ["$5,000,000"],
}


class _FakeMessages:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def create(self, **_: Any) -> Any:
        self.calls += 1
        block = type(
            "B", (), {"type": "tool_use", "name": "record_extraction", "input": self._payload}
        )
        return type("M", (), {"content": [block()]})()


class _FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.messages = _FakeMessages(payload)


def _extractor(payload: dict[str, Any] | None = None) -> StructuredExtractor:
    return StructuredExtractor(client=_FakeClient(payload or _PAYLOAD), settings=Settings())


def _body(slug: str = "american-township") -> Subdivision:
    return Subdivision(slug=slug, name=slug.title(), type="township")


def test_summarize_meeting_returns_validated_summary() -> None:
    summary = summarize_meeting("Minutes: ... data center ...", extractor=_extractor())
    assert isinstance(summary, MeetingSummary)
    assert summary.decisions == ["Motion to recommend rezoning passed 3-0"]
    assert "data-center" in summary.summary


def _seed(tmp: Path, docs: list[dict[str, Any]], files: dict[str, str]) -> Settings:
    settings = Settings(data_dir=tmp)
    docs_dir = settings.documents_dir / "american-township" / "meetings"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name, html in files.items():
        (docs_dir / name).write_text(f"<html><body>{html}</body></html>", encoding="utf-8")
    idx = settings.extracted_dir / "american-township" / "meetings" / "meeting-index.yaml"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(
        yaml.safe_dump({"meta": {"slug": "american-township"}, "documents": docs}), "utf-8"
    )
    return settings


def test_summarize_selects_corridor_only_and_skips_textless(tmp_path: Path) -> None:
    docs = [
        {
            "filename": "a.html",
            "kind": "minutes",
            "date_verified": "2026-02-09",
            "hits": ["datacenter", "rezoning"],
        },
        {
            "filename": "b.html",
            "kind": "minutes",
            "date_verified": "2026-01-01",
            "hits": ["rezoning"],
        },  # generic only
        {
            "filename": "c.html",
            "kind": "minutes",
            "date_verified": "2026-03-01",
            "hits": ["google"],
        },  # file absent
    ]
    settings = _seed(
        tmp_path, docs, {"a.html": "data center rezoning discussion", "b.html": "road levy"}
    )
    report = summarize_corridor_meetings(_body(), settings=settings, extractor=_extractor())
    # Only the two corridor-hit docs are considered; b (generic) is excluded entirely.
    assert [e.filename for e in report.entries] == ["a.html"]
    assert report.skipped == ["c.html"]  # corridor-relevant but no extractable text


def test_summarize_respects_limit(tmp_path: Path) -> None:
    docs = [
        {
            "filename": f"m{i}.html",
            "kind": "minutes",
            "date_verified": f"2026-0{i}-01",
            "hits": ["datacenter"],
        }
        for i in range(1, 4)
    ]
    settings = _seed(tmp_path, docs, {f"m{i}.html": "data center" for i in range(1, 4)})
    report = summarize_corridor_meetings(
        _body(), settings=settings, extractor=_extractor(), limit=2
    )
    assert len(report.entries) == 2


def test_write_summaries_flattens_summary(tmp_path: Path) -> None:
    settings = _seed(
        tmp_path,
        [
            {
                "filename": "a.html",
                "kind": "minutes",
                "date_verified": "2026-02-09",
                "hits": ["datacenter"],
            }
        ],
        {"a.html": "data center"},
    )
    report = summarize_corridor_meetings(_body(), settings=settings, extractor=_extractor())
    out = write_summaries(report, tmp_path / "meeting-summaries.yaml")
    doc = yaml.safe_load(out.read_text())
    assert doc["meta"]["slug"] == "american-township"
    m = doc["meetings"][0]
    assert m["date"] == "2026-02-09"
    assert m["decisions"] == ["Motion to recommend rezoning passed 3-0"]
    assert m["parcels"] == ["36-0100-03-002.000"]
