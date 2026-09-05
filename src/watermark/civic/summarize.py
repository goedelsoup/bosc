"""Summarize the corridor-relevant subdivision meetings: what was actually decided.

The index tells us a meeting *mentions* one of the active site's corridor subjects; this
runs the analyze stage over those meetings' text to extract **what happened** — the
motions, votes, parties, parcels, and dollar figures, plus a grounded note on how the
meeting connects to those subjects. Output: ``meeting-summaries.yaml`` per body, the
reviewed artifact that turns the index from an inventory into evidence.

Grounded by construction: the model is forced to populate a Pydantic schema and
instructed to record only what the minutes text states — no inference, no outside
knowledge. Both halves of that framing are **per site**: which meetings are selected
(``SiteProfile.corridor_subjects``, #1523) and what the model is told it is reading
(:func:`build_instructions`, #1839 — the county and the document's own hits, not Lima's
codenames). The extractor client is injectable, so the orchestration is unit-tested
without network/keys.
"""

from __future__ import annotations

from collections.abc import Collection
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


def build_instructions(county: str, hits: Collection[str]) -> str:
    """The extraction prompt for one meeting — per site, and naming that meeting's own hits.

    This prompt used to be hardcoded to Lima ("an Allen County, Ohio township or village",
    "codename Project BOSC / Bistrozzi LLC / a hyperscale data center, possibly Google") — the
    last Lima-locked seam in the loader, and a live one: told that Allen TOWNSHIP, HANCOCK
    County's minutes were Allen COUNTY BOSC minutes, the model dutifully explained that two
    Cooperative Economic Development Agreements were "a standard mechanism … in connection with
    large economic development projects such as a hyperscale data center" — a link those minutes
    never draw (#1839). So the county comes from the active profile and the flag is stated as
    what it literally is: this document's own index ``hits``.

    The closing rule on ``corridor_relevance`` is the guard against exactly that failure — a
    mention with no stated connection must be reported as a mention, not backfilled with a reason
    the minutes do not give.
    """
    named = ", ".join(sorted(hits)) or "(none recorded)"
    return (
        f"You are reading the minutes/agenda of a public meeting held by a political "
        f"subdivision of {county}. It was flagged because a keyword scan of its text matched "
        f"this site's corridor subjects: {named}. Extract ONLY what the document text actually "
        "states — do not infer, speculate, or add outside knowledge; if a field has nothing, "
        "return an empty list. Quote names and dollar figures as written.\n"
        "- summary: 2-4 neutral sentences on the corridor-relevant business only.\n"
        "- corridor_relevance: one sentence on how this meeting connects to those subjects, "
        "grounded strictly in the text. If the text does not connect them to anything beyond "
        "the mention itself, say that plainly — never supply a purpose, a project, or a party "
        "the minutes do not name.\n"
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


def summarize_meeting(
    text: str,
    *,
    extractor: StructuredExtractor,
    county: str,
    hits: Collection[str] = (),
) -> MeetingSummary:
    """Extract the structured summary of one meeting's text.

    ``county`` and ``hits`` build the per-site prompt (:func:`build_instructions`) — the
    subdivision's own county, and the corridor subjects this document actually matched.
    """
    return extractor.extract_from_text(
        MeetingSummary,
        instructions=build_instructions(county, hits),
        text=text[:_MAX_CHARS],
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
    profile = active_profile(settings)
    subjects = profile.corridor_subjects
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
        # ``documents_dir`` is what lets a legacy Office binary be read from its committed
        # ``-text`` sidecar. Omit it and every ``.doc`` agenda lands in ``skipped`` — which is
        # most of Lima's corridor-relevant meetings, the exact set this function exists to read.
        text, method = (
            extract_text(path, ocr=ocr, documents_dir=settings.documents_dir)
            if path.exists()
            else ("", "none")
        )
        if method == "none" or not text:
            skipped.append(filename)
            continue
        hits = [str(h) for h in d.get("hits", [])]
        entries.append(
            SummaryEntry(
                date=d.get("date_verified") or d.get("date_listing"),
                kind=str(d.get("kind", "other")),
                filename=filename,
                # The entry records EVERY hit — that's the index's finding, and the searchable
                # provenance. The PROMPT gets only the corridor subjects (#1839): it tells the
                # model "this site's corridor subjects: …", and a generic topic listed there is a
                # false statement the model then reasons from. It did: told `tax_abatement` was a
                # corridor subject, it wrote a sentence about a keyword that had matched
                # "asbestos abatement" in a demolition bid.
                hits=hits,
                summary=summarize_meeting(
                    text,
                    extractor=extractor,
                    county=profile.county_name,
                    hits=[h for h in hits if h in subjects],
                ),
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
