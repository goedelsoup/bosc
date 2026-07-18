"""Timeline assembly — merge dated events from every extraction into one order.

Phase C item 6. Each genre carries its own dates (a deed's recording date, an
NPDES permit's public-notice and comment-deadline dates, an OPC estimate's date);
this module pulls them into a single :class:`TimelineEvent` stream sorted into one
chronology, each event citing the artifact it came from.

Dates are transcribed from degraded scans, so parsing is lenient: a leading
``YYYY``, ``YYYY-MM``, or ``YYYY-MM-DD`` is enough to order on. Anything we can't
parse keeps its raw string and sinks to the end rather than being dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.pipeline.corpus import (
    Corpus,
    iter_meeting_artifacts,
    load_corpus,
    relpath_in_scope,
)
from watermark.sites import CorpusScope, active_profile, effective_corpus_scope

log = get_logger(__name__)

_DATE_RE = re.compile(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?")
# Sorts after any real date (year 9999) so undated events tail the chronology.
_UNDATED_KEY = (9999, 99, 99)


def _date_key(raw: str | None) -> tuple[int, int, int]:
    """A sortable ``(year, month, day)`` key from a loosely-formatted date."""
    if not raw:
        return _UNDATED_KEY
    match = _DATE_RE.search(raw)
    if not match:
        return _UNDATED_KEY
    year, month, day = match.groups()
    return (int(year), int(month or 0), int(day or 0))


@dataclass(frozen=True)
class TimelineEvent:
    """One dated event, traceable to the extraction(s) that supplied it."""

    date: str  # as transcribed (ISO where legible)
    category: str  # deed_recorded | npdes_public_notice | npdes_comment_deadline | opc_estimate
    title: str
    source: str  # primary extraction path, relative to data/extracted
    ref: str = ""  # logical id (instrument no / permit no) for cross-doc dedup
    parties: tuple[str, ...] = ()
    detail: str = ""
    also_sources: tuple[str, ...] = ()  # other artifacts reporting the same event

    @property
    def sort_key(self) -> tuple[tuple[int, int, int], str]:
        return (_date_key(self.date), self.category)


def _dedup(events: list[TimelineEvent]) -> list[TimelineEvent]:
    """Collapse the same real-world event reported by multiple artifacts.

    The corpus often holds several documents about one permit (permit + fact
    sheet + public notice), so an identical (ref, category, date) recurs. Keep
    the first, fold the rest's paths into ``also_sources``. Events with no ``ref``
    (nothing to key on) are passed through untouched.
    """
    seen: dict[tuple[str, str, tuple[int, int, int]], TimelineEvent] = {}
    out: list[TimelineEvent] = []
    for e in events:
        if not e.ref:
            out.append(e)
            continue
        key = (e.ref, e.category, _date_key(e.date))
        if key in seen:
            primary = seen[key]
            merged = replace(primary, also_sources=(*primary.also_sources, e.source))
            seen[key] = merged
            out[out.index(primary)] = merged
        else:
            seen[key] = e
            out.append(e)
    return out


def _deed_events(corpus: Corpus) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for rel, ex in corpus.deeds:
        d = ex.deed
        parties = tuple(d.grantors) + tuple(d.grantees)
        arrow = f"{', '.join(d.grantors) or '?'} → {', '.join(d.grantees) or '?'}"
        bits = [f"{len(d.parcel_ids)} parcel(s)"]
        if d.consideration is not None:
            bits.append(f"consideration {d.consideration:,}")
        events.append(
            TimelineEvent(
                date=d.recording_date or "",
                category="deed_recorded",
                title=f"{d.instrument_type or 'Deed'} {d.instrument_no or ''}: {arrow}".strip(),
                source=rel,
                ref=d.instrument_no or "",
                parties=parties,
                detail="; ".join(bits),
            )
        )
    return events


def _npdes_events(corpus: Corpus) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for rel, ex in corpus.permits:
        p = ex.permit
        parties = tuple(x for x in (p.applicant, p.facility_name) if x)
        label = f"NPDES {p.permit_no or '?'} ({p.facility_name or '?'})"
        if p.public_notice_date:
            events.append(
                TimelineEvent(
                    date=p.public_notice_date,
                    category="npdes_public_notice",
                    title=f"{label} — public notice",
                    source=rel,
                    ref=p.permit_no or "",
                    parties=parties,
                    detail=f"action {p.permit_action or '?'}; receiving {p.receiving_water or '?'}",
                )
            )
        if p.comment_period_end:
            events.append(
                TimelineEvent(
                    date=p.comment_period_end,
                    category="npdes_comment_deadline",
                    title=f"{label} — comment period ends",
                    source=rel,
                    ref=p.permit_no or "",
                    parties=parties,
                )
            )
    return events


def _epa_events(corpus: Corpus) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for rel, ex in corpus.actions:
        a = ex.action
        if not a.action_date:
            continue
        parties = tuple(x for x in (a.applicant, a.contact_name, a.contact_firm) if x)
        label = f"{a.program or 'EPA action'} {a.permit_no or ''}".strip()
        events.append(
            TimelineEvent(
                date=a.action_date,
                category="epa_permit_action",
                title=f"{label} — {a.action or 'correspondence'} ({a.project_name or '?'})",
                source=rel,
                ref=a.permit_no or "",
                parties=parties,
                detail=f"affected {a.affected_resource}" if a.affected_resource else "",
            )
        )
    return events


def _plan_events(corpus: Corpus) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for rel, ex in corpus.plans:
        p = ex.plan
        if not p.date:
            continue
        parties = tuple(fm.name for fm in p.prepared_by)
        label = (
            f"{p.discipline or 'Site plan'} ({p.phase})"
            if p.phase
            else (p.discipline or "Site plan")
        )
        events.append(
            TimelineEvent(
                date=p.date,
                category="site_plan",
                title=f"{label} — {p.project_name or '?'}",
                source=rel,
                ref=p.sheet_id or "",
                parties=parties,
            )
        )
    return events


def _opc_events(corpus: Corpus) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for rel, summary in corpus.summaries:
        meta = summary.meta
        if not meta.date:
            continue
        parties = tuple(x for x in (meta.estimator,) if x)
        events.append(
            TimelineEvent(
                date=meta.date,
                category="opc_estimate",
                title=f"OPC estimate: {meta.program or rel}",
                source=rel,
                parties=parties,
                detail=f"program total ~{summary.grand_total():,}" if summary.sub_estimates else "",
            )
        )
    return events


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a committed extraction YAML, or ``{}`` if absent/unreadable."""
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        log.warning("timeline.bad_yaml", path=str(path), error=str(exc).splitlines()[0])
        return {}
    return data if isinstance(data, dict) else {}


def _commissioners_events(
    settings: Settings, scope: CorpusScope | None = None
) -> list[TimelineEvent]:
    """Dated events from the committed commissioners extractions.

    These artifacts carry ``kind``s the corpus loader does not recognize (resolution
    ledgers, closed-session logs), so they are read directly here — the citable
    legislative spine of the project (NDA/CRA/RDA resolutions, the wastewater works,
    the codename-phase narrative, and the economic-development executive sessions).

    ``scope`` is the active site's corpus scope (#762): these read the extracted tree
    directly, so they are gated per-file like the corpus loader is — a sibling site
    (Fort Wayne) whose scope excludes ``commissioners/`` gets none of Lima's spine.
    """
    base = settings.extracted_dir / "commissioners"
    events: list[TimelineEvent] = []

    ledger_rel = "commissioners/bosc-resolution-ledger.yaml"
    ledger = (
        _load_yaml(base / "bosc-resolution-ledger.yaml")
        if relpath_in_scope(ledger_rel, scope)
        else {}
    )
    for key in ("resolutions", "adjacent_wastewater_resolutions"):
        for r in ledger.get(key, []):
            if not isinstance(r, dict) or not r.get("date"):
                continue
            res = str(r.get("res", "")).strip()
            title = str(r.get("title", "")).strip()
            events.append(
                TimelineEvent(
                    date=str(r["date"]),
                    category="county_resolution",
                    title=f"Res #{res}: {title}" if res else title,
                    source=ledger_rel,
                    ref=f"res-{res}" if res else "",
                    detail=str(r.get("thread", "")),
                )
            )
    for e in ledger.get("narrative_events", []):
        if not isinstance(e, dict) or not e.get("date"):
            continue
        events.append(
            TimelineEvent(
                date=str(e["date"]),
                category="county_event",
                title=str(e.get("event", "")).strip(),
                source=ledger_rel,
                detail=str(e.get("significance", "")),
            )
        )

    sessions_rel = "commissioners/closed-deliberation-and-corridor.yaml"
    closed = (
        _load_yaml(base / "closed-deliberation-and-corridor.yaml")
        if relpath_in_scope(sessions_rel, scope)
        else {}
    )
    for s in closed.get("econdev_and_property_sessions", []):
        if not isinstance(s, dict) or not s.get("date"):
            continue
        code = str(s.get("code", "")).strip()
        purpose = re.sub(r"\s+", " ", str(s.get("purpose", ""))).strip()
        events.append(
            TimelineEvent(
                date=str(s["date"]),
                category="executive_session",
                title=f"Executive session {code} — {purpose[:90]}".rstrip(" —"),
                source=sessions_rel,
                ref=f"exec-{s['date']}-{code}",
            )
        )
    return events


def _zoning_events(settings: Settings, scope: CorpusScope | None = None) -> list[TimelineEvent]:
    """The single American Township zoning **text amendment** that carried the data-center basis.

    Lima-specific (``lacrpc/``) and gated on the active site's scope (#762): a sibling
    site whose scope excludes ``lacrpc/`` gets nothing here.

    The resolution PDF lists five trustee re-adoptions but has **no change-log**, so the source
    artifact does not — and must not — claim which one introduced the Data Center / Hyperscale
    definitions + M-2 conditional use (11.2.4). Emitting one ``zoning_amendment`` event per
    re-adoption stamped *every* date (three of them pre-dating the project) with that data-center
    caption — the same change asserted five times over. Instead emit a **single** event for the
    amendment the corpus resolves as the carrier: ``document.data_center_amendment`` (Res #09-082025,
    adopted 2025-09-08 — the only zoning text amendment content-verified in the township minutes,
    inside the BOSC deal window), citing those minutes as a corroborating source. Absent that
    resolved block, emit nothing (honest null) rather than fabricate the attribution.
    """
    rel = "lacrpc/american-township-zoning.zoning.yaml"
    if not relpath_in_scope(rel, scope):
        return []
    data = _load_yaml(settings.extracted_dir / "lacrpc" / "american-township-zoning.zoning.yaml")
    doc = data.get("document", {}) if isinstance(data.get("document"), dict) else {}
    amendment = doc.get("data_center_amendment")
    if not isinstance(amendment, dict) or not amendment.get("date"):
        return []
    date = str(amendment["date"])
    resolution = str(amendment.get("resolution", "")).strip()
    minutes_rel = str(amendment.get("corroborating_source", "")).strip()
    prefix = f"{resolution} " if resolution else ""
    title = "American Township zoning text amendment — data-center provisions adopted"
    if resolution:
        title = f"{title} ({resolution})"
    detail = (
        f"{prefix}zoning text amendment — Data Center / Hyperscale Data Center definitions "
        "+ M-2 conditional use (11.2.4); the deal-window amendment carrying the data-center "
        "text [inference, corroborated by the American Township minutes]"
    )
    return [
        TimelineEvent(
            date=date,
            category="zoning_amendment",
            title=title,
            source=rel,
            ref=f"amtwp-zoning-{date}",
            detail=detail,
            also_sources=(minutes_rel,) if minutes_rel else (),
        )
    ]


def _summary_detail(meeting: dict[str, Any]) -> str:
    """Grounded one-line detail from a committed meeting summary: relevance + figures."""
    rel = re.sub(r"\s+", " ", str(meeting.get("corridor_relevance") or "")).strip()
    figs = [re.sub(r"\s+", " ", str(f)).strip() for f in meeting.get("dollar_figures", [])]
    figs = [f for f in figs if f]
    if figs:
        joined = "; ".join(figs)
        rel = f"{rel} · figures: {joined}" if rel else f"figures: {joined}"
    return rel


def _subdivision_meeting_events(
    settings: Settings,
    scope: CorpusScope | None = None,
    subjects: tuple[str, ...] | None = None,
) -> list[TimelineEvent]:
    """Subdivision meetings that name the corridor project in their minutes/agendas.

    Reads every committed ``meeting-index.yaml`` (built by ``watermark subdivisions index``) across
    both layouts — Lima's flat ``<body>/meetings/`` and a peer's nested ``<site>/<body>/meetings/``
    (:func:`~watermark.pipeline.corpus.iter_meeting_artifacts`) — and surfaces only meetings whose
    text hit one of the active site's corridor ``subjects`` — routine township business stays in the
    index as searchable corpus but off the chronology. Agenda + minutes for the same meeting collapse
    via a shared ``ref``. When a meeting has a committed summary (``meeting-summaries.yaml``), its
    grounded relevance + dollar figures become the event detail; otherwise the detail is the raw hit set.

    ``subjects`` is the per-site corridor vocabulary (#1523): the single source of truth
    is ``SiteProfile.corridor_subjects``, so ``None`` derives it from ``active_profile``
    (Lima's BOSC set by default). A peer with an **empty** set surfaces no
    ``subdivision_meeting`` events (its hits stay in the index, undropped) until it
    declares its own subjects — the safe/honest default.

    ``scope`` bounds the read to the active site's collections (#762): each index is gated on its
    real path through ``relpath_in_scope``, so a sibling site only sees its own meeting indices and
    Lima's whole-tree-minus-peers scope excludes every nested peer tree.
    """
    if subjects is None:
        subjects = active_profile(settings).corridor_subjects
    events: list[TimelineEvent] = []
    for index_path in iter_meeting_artifacts(settings.extracted_dir, "meeting-index.yaml"):
        rel = index_path.relative_to(settings.extracted_dir).as_posix()
        if not relpath_in_scope(rel, scope):
            continue
        data = _load_yaml(index_path)
        slug = str(data.get("meta", {}).get("slug", index_path.parent.parent.name))
        name = slug.replace("-", " ").title()
        summaries = _load_yaml(index_path.parent / "meeting-summaries.yaml")
        by_file = {
            str(m.get("filename")): m for m in summaries.get("meetings", []) if isinstance(m, dict)
        }
        for d in data.get("documents", []):
            if not isinstance(d, dict):
                continue
            hits = [str(h) for h in d.get("hits", [])]
            corridor = [h for h in hits if h in subjects]
            date = d.get("date_verified") or d.get("date_listing")
            if not corridor or not date:
                continue
            body = str(d.get("body") or name)
            summary = by_file.get(str(d.get("filename")))
            detail = (_summary_detail(summary) if summary else "") or ", ".join(hits)
            events.append(
                TimelineEvent(
                    date=str(date),
                    category="subdivision_meeting",
                    title=f"{body} — {d.get('kind', 'meeting')} (corridor: {', '.join(corridor)})",
                    source=rel,
                    ref=f"mtg-{slug}-{date}-{body}",
                    parties=(body,),
                    detail=detail,
                )
            )
    return events


def build_timeline(
    corpus: Corpus | None = None,
    *,
    include_curated: bool = True,
    scope: CorpusScope | None = None,
) -> list[TimelineEvent]:
    """Assemble a single sorted chronology across the whole corpus.

    The recognized-genre events come from ``corpus`` (already site-scoped by
    ``load_corpus``). When ``include_curated`` (the default for production — the CLI and
    site build), the committed unrecognized-kind extractions — the commissioners ledger,
    closed-session log, the zoning resolution, and the subdivision meeting indices — are
    folded in directly. Those read the extracted tree directly, so they are bounded by
    the active site's corpus scope (#762): when ``scope`` is omitted it's derived from the
    active site's profile (``None`` for Lima → the whole tree, byte-identical), so a
    sibling site (Fort Wayne) never inherits Lima's Allen-County civic spine. Tests pass
    ``include_curated=False`` to stay hermetic against a synthetic corpus.
    """
    corpus = corpus if corpus is not None else load_corpus()
    events = (
        _deed_events(corpus)
        + _npdes_events(corpus)
        + _epa_events(corpus)
        + _plan_events(corpus)
        + _opc_events(corpus)
    )
    if include_curated:
        settings = get_settings()
        profile = active_profile(settings)
        site_scope = scope if scope is not None else effective_corpus_scope(profile)
        events += (
            _commissioners_events(settings, site_scope)
            + _zoning_events(settings, site_scope)
            + _subdivision_meeting_events(settings, site_scope, profile.corridor_subjects)
        )
    events = _dedup(events)
    events.sort(key=lambda e: e.sort_key)
    log.info("timeline.built", events=len(events))
    return events
