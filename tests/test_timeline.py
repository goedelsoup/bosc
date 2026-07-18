"""Tests for cross-document timeline assembly."""

from __future__ import annotations

from pathlib import Path

from watermark.config import Settings
from watermark.models import Deed, DeedExtraction, NpdesExtraction, NpdesPermit
from watermark.pipeline.corpus import Corpus
from watermark.pipeline.timeline import _date_key, _zoning_events, build_timeline
from watermark.sites import CorpusScope

REPO_ROOT = Path(__file__).resolve().parents[1]


def _deed(
    rel: str, *, no: str, date: str, grantor: str, grantee: str
) -> tuple[str, DeedExtraction]:
    return rel, DeedExtraction(
        doc_id=no,
        source_path=f"/x/{no}.pdf",
        kind="deed",
        dpi=200,
        deed=Deed(instrument_no=no, recording_date=date, grantors=[grantor], grantees=[grantee]),
    )


def _permit(rel: str, *, no: str, pn: str, end: str) -> tuple[str, NpdesExtraction]:
    return rel, NpdesExtraction(
        doc_id=no,
        source_path=f"/x/{rel}",
        kind="npdes",
        dpi=150,
        permit=NpdesPermit(
            permit_no=no, facility_name="WWTP", public_notice_date=pn, comment_period_end=end
        ),
    )


def test_date_key_parses_partial_dates() -> None:
    assert _date_key("2025-08-13") == (2025, 8, 13)
    assert _date_key("2024-03") == (2024, 3, 0)
    assert _date_key("2026") == (2026, 0, 0)
    assert _date_key(None) > (9000, 0, 0)  # undated sinks to the tail
    assert _date_key("n/a") > (9000, 0, 0)


def test_build_timeline_orders_and_labels() -> None:
    corpus = Corpus(
        deeds=[
            _deed(
                "recorder/late.deed.yaml",
                no="I2",
                date="2026-03-04",
                grantor="Seller",
                grantee="Acme LLC",
            ),
            _deed(
                "recorder/early.deed.yaml",
                no="I1",
                date="2025-08-13",
                grantor="Farm",
                grantee="Acme LLC",
            ),
        ],
        permits=[_permit("oepa/p.npdes.yaml", no="2PH1", pn="2025-04-28", end="2025-05-28")],
    )
    events = build_timeline(corpus, include_curated=False)
    dates = [e.date for e in events]
    assert dates == sorted(dates, key=_date_key)  # chronological
    deed_events = [e for e in events if e.category == "deed_recorded"]
    assert {e.ref for e in deed_events} == {"I1", "I2"}
    assert "Acme LLC" in deed_events[0].parties
    cats = {e.category for e in events}
    assert {"deed_recorded", "npdes_public_notice", "npdes_comment_deadline"} <= cats


def test_build_timeline_dedups_same_event_across_sources() -> None:
    # Same permit + same public-notice date reported by two different artifacts.
    corpus = Corpus(
        permits=[
            _permit("oepa/permit.npdes.yaml", no="2PH00006", pn="2025-04-28", end="2025-05-28"),
            _permit("oepa/fact-sheet.npdes.yaml", no="2PH00006", pn="2025-04-28", end="2025-05-28"),
        ]
    )
    events = build_timeline(corpus, include_curated=False)
    notices = [e for e in events if e.category == "npdes_public_notice"]
    assert len(notices) == 1  # collapsed to one event
    assert notices[0].also_sources == ("oepa/fact-sheet.npdes.yaml",)


def test_build_timeline_keeps_differing_dates_separate() -> None:
    # Same permit but two *different* public-notice dates must NOT collapse.
    corpus = Corpus(
        permits=[
            _permit("oepa/a.npdes.yaml", no="2PH00006", pn="2025-04-28", end="2025-05-28"),
            _permit("oepa/b.npdes.yaml", no="2PH00006", pn="2025-06-17", end="2025-05-28"),
        ]
    )
    notices = [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "npdes_public_notice"
    ]
    assert {e.date for e in notices} == {"2025-04-28", "2025-06-17"}


def test_zoning_events_resolve_to_the_single_data_center_amendment() -> None:
    """The American Township zoning basis must be ONE event, not one per re-adoption date.

    The resolution PDF has no change-log, so the projector must not stamp every trustee
    re-adoption with the data-center caption (the "same change five times" defect). It resolves
    to the single carrier the corpus content-verifies — Res #09-082025, adopted 2025-09-08.
    """
    events = _zoning_events(Settings(data_dir=REPO_ROOT / "data"))
    assert len(events) == 1, [e.ref for e in events]
    (event,) = events
    assert event.category == "zoning_amendment"
    assert event.date == "2025-09-08"
    assert event.ref == "amtwp-zoning-2025-09-08"
    # The pre-deal re-adoptions must no longer masquerade as the data-center change.
    assert not {"2021-02-11", "2024-01-08", "2024-08-28"} & {event.date}
    # Honest tagging: an inference corroborated by the township minutes, not a bare assertion.
    assert "inference" in event.detail.lower()
    assert "american-township/meetings/meeting-summaries.yaml" in event.also_sources


def test_zoning_events_gated_out_of_scope() -> None:
    """A sibling site whose scope excludes ``lacrpc/`` gets no Lima zoning event (#762)."""
    settings = Settings(data_dir=REPO_ROOT / "data")
    assert _zoning_events(settings, scope=CorpusScope(include=("oepa/",))) == []
