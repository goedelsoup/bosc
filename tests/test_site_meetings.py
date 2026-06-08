"""Site meetings page + the shared committed-summaries loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from bosc.civic.summarize import load_committed_summaries
from bosc.config import Settings
from bosc.site.meetings import render_meetings


def _seed(settings: Settings, slug: str, meetings: list[dict[str, object]]) -> None:
    p = settings.extracted_dir / slug / "meetings" / "meeting-summaries.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump({"meta": {"slug": slug}, "meetings": meetings}), encoding="utf-8")


def test_load_committed_summaries_groups_and_sorts(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    _seed(settings, "lacrpc", [{"date": "2026-04-23", "kind": "minutes", "filename": "b.pdf"}])
    _seed(
        settings,
        "american-township",
        [
            {"date": "2024-12-09", "kind": "minutes", "filename": "later.docx"},
            {"date": "2024-11-25", "kind": "minutes", "filename": "earlier.docx"},
        ],
    )
    loaded = load_committed_summaries(settings)
    assert len(loaded) == 3
    # Sorted by (slug, date): american-township earlier first, then later, then lacrpc.
    assert [m["filename"] for _, m in loaded] == ["earlier.docx", "later.docx", "b.pdf"]


def test_render_meetings_surfaces_grounded_detail() -> None:
    page = render_meetings(
        [
            (
                "lacrpc",
                {
                    "date": "2026-04-23",
                    "kind": "minutes",
                    "filename": "_04232026-272.pdf",
                    "corridor_relevance": "Presentation discussed project BOSC (Google data center).",
                    "summary": "Open discussion about data centers.",
                    "decisions": ["Motion to accept the DCC report; carried."],
                    "parties": ["Brad Baxter, Bath Township", "Elida Schools"],
                    "dollar_figures": ["$250,000 to Elida Schools", "$1.5 billion if all phases"],
                },
            )
        ]
    )
    assert "# Subdivision corridor meetings" in page
    assert "## LACRPC" in page  # short lowercase slug keeps its acronym
    assert "project BOSC (Google data center)" in page
    assert "$250,000 to Elida Schools; $1.5 billion if all phases" in page
    assert "- Motion to accept the DCC report; carried." in page
    assert "data/extracted/lacrpc/meetings/meeting-summaries.yaml" in page
    assert "[timeline](timeline.md)" in page and "[entity graph](entities.md)" in page


def test_render_meetings_empty_is_honest() -> None:
    page = render_meetings([])
    assert "No corridor-relevant meeting summaries are committed yet." in page
