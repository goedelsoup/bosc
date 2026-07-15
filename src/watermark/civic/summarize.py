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

from watermark.agent.extractor import StructuredExtractor
from watermark.civic.indexer import extract_text
from watermark.civic.keywords import is_corridor_relevant
from watermark.civic.layout import meetings_dir
from watermark.civic.models import Subdivision
from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.pipeline.corpus import iter_meeting_artifacts, relpath_in_scope
from watermark.sites import CorpusScopeArg, active_profile

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

    Selects meetings whose ``hits`` name one of the active site's corridor subjects
    (``SiteProfile.corridor_subjects``, #1523 — Lima's BOSC set by default, empty for a
    peer that hasn't declared its own), re-extracts each file's text (OCR'ing scans by
    default), and runs the structured summary. A file with no extractable text is
    recorded in ``skipped`` rather than summarized from nothing.
    """
    settings = settings or get_settings()
    extractor = extractor or StructuredExtractor(settings=settings)
    subjects = active_profile(settings).corridor_subjects
    base = meetings_dir(settings.extracted_dir, subdivision.slug, settings)
    index_path = index_path or (base / "meeting-index.yaml")
    docs_dir = docs_dir or meetings_dir(settings.documents_dir, subdivision.slug, settings)
    data = yaml.safe_load(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    docs = [
        d
        for d in (data or {}).get("documents", [])
        if isinstance(d, dict) and is_corridor_relevant(d.get("hits", []), subjects)
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


def load_committed_summaries(
    settings: Settings | None = None,
    *,
    scope: CorpusScopeArg = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Read every committed ``meeting-summaries.yaml`` across both site layouts (#1522).

    Returns ``(slug, meeting)`` pairs across all bodies, sorted by ``(slug, date)``;
    each ``meeting`` is the flat committed shape written by :func:`write_summaries`
    (``date``/``kind``/``filename``/``hits`` + the :class:`MeetingSummary` fields).
    Shared by the timeline (event-detail enrichment) and the site meetings page so
    neither re-parses the artifact independently.

    Reads both Lima's flat ``<body>/meetings/`` and a peer's nested ``<site>/<body>/meetings/``
    (:func:`~watermark.pipeline.corpus.iter_meeting_artifacts`). ``scope`` is the active site's
    corpus prefixes (#762): each summaries file is gated on its real path through
    ``relpath_in_scope``, so a non-Lima site's meetings feed carries only its own bodies and Lima's
    whole-tree-minus-peers scope excludes every nested peer tree. ``None`` reads every body.
    """
    settings = settings or get_settings()
    extracted = settings.extracted_dir
    out: list[tuple[str, dict[str, Any]]] = []
    for path in iter_meeting_artifacts(extracted, "meeting-summaries.yaml"):
        if not relpath_in_scope(path.relative_to(extracted).as_posix(), scope):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        slug = str(data.get("meta", {}).get("slug", path.parent.parent.name))
        meetings = [m for m in data.get("meetings", []) if isinstance(m, dict)]
        meetings.sort(key=lambda m: str(m.get("date") or ""))
        out.extend((slug, m) for m in meetings)
    return out


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
