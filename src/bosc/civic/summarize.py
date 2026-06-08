"""Summarize the corridor-relevant subdivision meetings: what was actually decided.

The index tells us a meeting *mentions* the data-center project; this runs the
analyze stage over those meetings' text to extract **what happened** — the motions,
votes, parties, parcels, and dollar figures, plus a grounded note on how the meeting
connects to the corridor. Output: ``meeting-summaries.yaml`` per body, the reviewed
artifact that turns the index from an inventory into evidence.

Grounded by construction: the model is forced to populate a Pydantic schema and
instructed to record only what the minutes text states — no inference, no outside
knowledge. The extractor client is injectable, so the orchestration is unit-tested
without network/keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.agent.extractor import StructuredExtractor
from bosc.civic.indexer import extract_text
from bosc.civic.keywords import CORRIDOR_SUBJECTS
from bosc.civic.models import Subdivision
from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

_MAX_CHARS = 24_000  # bound the text sent per meeting (minutes are short, but cap cost)

_INSTRUCTIONS = (
    "You are reading the minutes/agenda of an Allen County, Ohio township or village "
    "meeting. It was flagged because its text references the data-center corridor "
    "project (codename Project BOSC / Bistrozzi LLC / a hyperscale data center, "
    "possibly Google). Extract ONLY what the document text actually states — do not "
    "infer, speculate, or add outside knowledge; if a field has nothing, return an "
    "empty list. Quote names and dollar figures as written.\n"
    "- summary: 2-4 neutral sentences on the corridor-relevant business only.\n"
    "- corridor_relevance: one sentence on how this meeting connects to the project, "
    "grounded strictly in the text.\n"
    "- decisions: motions, votes, resolutions, approvals/denials as stated.\n"
    "- parties: named people, firms, applicants, agencies.\n"
    "- parcels: parcel numbers or addresses mentioned.\n"
    "- dollar_figures: dollar amounts as written."
)


class MeetingSummary(BaseModel):
    """What a corridor-relevant meeting decided — grounded in the minutes text."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    corridor_relevance: str
    decisions: list[str]
    parties: list[str]
    parcels: list[str]
    dollar_figures: list[str]


class SummaryEntry(BaseModel):
    """A meeting summary plus its index provenance."""

    model_config = ConfigDict(extra="forbid")

    date: str | None
    kind: str
    filename: str
    hits: list[str]
    summary: MeetingSummary


class SummaryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    entries: list[SummaryEntry]
    skipped: list[str]  # filenames skipped (no extractable text)


def summarize_meeting(text: str, *, extractor: StructuredExtractor) -> MeetingSummary:
    """Extract the structured summary of one meeting's text."""
    return extractor.extract_from_text(
        MeetingSummary, instructions=_INSTRUCTIONS, text=text[:_MAX_CHARS]
    )


def summarize_corridor_meetings(
    subdivision: Subdivision,
    *,
    settings: Settings | None = None,
    extractor: StructuredExtractor | None = None,
    docs_dir: Path | None = None,
    index_path: Path | None = None,
    limit: int | None = None,
    ocr: bool = True,
) -> SummaryReport:
    """Summarize every corridor-relevant meeting in a body's index.

    Selects meetings whose ``hits`` name a project-specific subject
    (``CORRIDOR_SUBJECTS``), re-extracts each file's text (OCR'ing scans by default),
    and runs the structured summary. A file with no extractable text is recorded in
    ``skipped`` rather than summarized from nothing.
    """
    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings)
    base = settings.extracted_dir / subdivision.slug / "meetings"
    index_path = index_path or (base / "meeting-index.yaml")
    docs_dir = docs_dir or (settings.documents_dir / subdivision.slug / "meetings")
    data = yaml.safe_load(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    docs = [
        d
        for d in (data or {}).get("documents", [])
        if isinstance(d, dict) and any(h in CORRIDOR_SUBJECTS for h in d.get("hits", []))
    ]
    if limit is not None:
        docs = docs[:limit]

    entries: list[SummaryEntry] = []
    skipped: list[str] = []
    for d in docs:
        filename = str(d.get("filename", ""))
        path = docs_dir / filename
        text, method = extract_text(path, ocr=ocr) if path.exists() else ("", "none")
        if method == "none" or not text:
            skipped.append(filename)
            continue
        entries.append(
            SummaryEntry(
                date=d.get("date_verified") or d.get("date_listing"),
                kind=str(d.get("kind", "other")),
                filename=filename,
                hits=[str(h) for h in d.get("hits", [])],
                summary=summarize_meeting(text, extractor=extractor),
            )
        )
    log.info(
        "civic.summarize", slug=subdivision.slug, summarized=len(entries), skipped=len(skipped)
    )
    return SummaryReport(slug=subdivision.slug, entries=entries, skipped=skipped)


def write_summaries(report: SummaryReport, out_path: Path) -> Path:
    """Write the meeting-summaries YAML (reviewed corridor-evidence artifact)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc: dict[str, Any] = {
        "meta": {
            "subject": f"{report.slug} corridor meeting summaries",
            "slug": report.slug,
            "method": "structured extraction (forced tool use) over the meeting text; "
            "model records only what the minutes state — no inference.",
            "summarized": len(report.entries),
            "skipped_no_text": report.skipped,
        },
        "meetings": [
            {
                "date": e.date,
                "kind": e.kind,
                "filename": e.filename,
                "hits": e.hits,
                **e.summary.model_dump(),
            }
            for e in sorted(report.entries, key=lambda e: e.date or "")
        ],
    }
    out_path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out_path
