"""Tests for cross-document timeline assembly."""

from __future__ import annotations

from pathlib import Path

from watermark.config import Settings
from watermark.models import (
    ComplianceInspection,
    ComplianceProgressReport,
    Deed,
    DeedExtraction,
    EnforcementOrder,
    InspectionExtraction,
    NpdesExtraction,
    NpdesPermit,
    OrderExtraction,
    ProgressReportExtraction,
)
from watermark.pipeline.corpus import Corpus
from watermark.pipeline.timeline import _date_key, _zoning_events, build_timeline
from watermark.sites import CorpusScope, effective_corpus_scope, get_profile

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


def test_curated_corridor_vocabulary_follows_the_injected_settings() -> None:
    """The curated half must read the corridor subjects of the site it is *told* to build (#2025).

    ``build_timeline`` used to take the vocabulary from ``get_settings()``, which is
    ``lru_cache``d on the process-global active site. ``export.py`` threads ``scope`` but
    exports with an injected ``Settings``, so a peer export read the right *files* and then
    filtered them through the default site's vocabulary — Findlay's three One Power meetings
    fell out of a 14-event chronology, silently, in every programmatic export (the whole test
    suite's shared bundle fixtures included). The CLI was unaffected, so the committed bundle
    and the suite's export of it disagreed with no test in a position to notice.

    Both calls below read the SAME files — ``scope`` is pinned to Findlay's — so the only
    variable is which profile supplies ``corridor_subjects``.
    """
    corpus = Corpus()
    scope = effective_corpus_scope(get_profile("findlay"))

    def corridors(site: str) -> set[str]:
        events = build_timeline(
            corpus, scope=scope, settings=Settings(data_dir=REPO_ROOT / "data", site=site)
        )
        return {
            subject
            for e in events
            if e.category == "subdivision_meeting"
            for subject in e.title.rsplit("(corridor: ", 1)[-1].rstrip(")").split(", ")
        }

    # Findlay declares one_power; Lima does not. Read with Findlay's own vocabulary, its One
    # Power meetings are on the chronology.
    assert "one_power" in corridors("findlay")
    # Read with Lima's vocabulary over the very same files, they are not — which is exactly
    # what a peer export produced before the settings were threaded.
    assert "one_power" not in corridors("lima")
    # `datacenter` is in both vocabularies, so it survives either way: proof the difference is
    # the vocabulary and not the scope silently emptying.
    assert "datacenter" in corridors("findlay") & corridors("lima")


# --- the wastewater-compliance genres (#1746/#2077/#2079) ------------------------------------


def _inspection(rel: str, **kw: object) -> tuple[str, InspectionExtraction]:
    return rel, InspectionExtraction(
        doc_id=rel,
        source_path=f"/x/{rel}",
        kind="inspection",
        dpi=200,
        inspection=ComplianceInspection(permit_no="2PE00000", facility="Lima WWTP", **kw),
    )


def _order(rel: str, **kw: object) -> tuple[str, OrderExtraction]:
    return rel, OrderExtraction(
        doc_id=rel,
        source_path=f"/x/{rel}",
        kind="order",
        dpi=200,
        order=EnforcementOrder(permit_no="2PE00000", respondent="City of Lima", **kw),
    )


def test_inspection_events_date_on_the_visit_not_the_letter() -> None:
    """An inspection is a thing that happened at the plant, weeks before the letter reporting it."""
    corpus = Corpus(
        inspections=[
            _inspection(
                "oepa/lima/a.inspection.yaml",
                inspection_date="2026-07-07",
                report_date="2026-07-16",
                type_code="CEI",
            )
        ]
    )
    (event,) = [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "agency_inspection"
    ]
    assert event.date == "2026-07-07"
    assert "reported 2026-07-16" in event.detail


def test_inspection_with_only_a_report_date_contributes_nothing() -> None:
    """No fabricated visit: `oepa/lima/edoc-3170414.inspection.yaml` is in exactly this state."""
    corpus = Corpus(
        inspections=[_inspection("oepa/lima/b.inspection.yaml", report_date="2016-07-20")]
    )
    assert not [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "agency_inspection"
    ]


def test_twin_portal_captures_of_one_inspection_collapse_to_one_event() -> None:
    """12 `v2` clusters in `document-versions.yaml` are one letter served at two docids.

    The key is the VISIT (permit + date + type), which is what two readings of one letter agree
    about — not the cluster manifest, which `watermark.pipeline` cannot import.
    """
    corpus = Corpus(
        inspections=[
            _inspection(
                "oepa/lima/edoc-1914739.inspection.yaml",
                inspection_date="2016-07-13",
                type_code="RI",
            ),
            _inspection(
                "oepa/lima/edoc-467350.inspection.yaml",
                inspection_date="2016-07-13",
                type_code="RI",
            ),
        ]
    )
    (event,) = [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "agency_inspection"
    ]
    assert event.also_sources == ("oepa/lima/edoc-467350.inspection.yaml",)


def test_two_inspections_of_one_plant_on_one_day_stay_separate() -> None:
    """2017-12-05 and 2019-04-04 each carry a CEI *and* a biosolids inspection — hence the type."""
    corpus = Corpus(
        inspections=[
            _inspection(
                "oepa/lima/cei.inspection.yaml", inspection_date="2017-12-05", type_code="CEI"
            ),
            _inspection(
                "oepa/lima/biosolids.inspection.yaml",
                inspection_date="2017-12-05",
                inspection_type="Biosolids Generator Inspection",
            ),
        ]
    )
    events = [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "agency_inspection"
    ]
    assert len(events) == 2
    assert not any(e.also_sources for e in events)


def test_order_events_ignore_a_disputed_case_no_when_deduping() -> None:
    """One 2016-07-11 letter at two docids; one capture invented a case_no from the permit number.

    Keying on the identifier the two readings DISPUTE would publish the letter twice.
    """
    corpus = Corpus(
        orders=[
            _order(
                "oepa/lima/edoc-1914761.order.yaml",
                instrument="correspondence",
                issued_date="2016-07-11",
            ),
            _order(
                "oepa/lima/edoc-463755.order.yaml",
                instrument="correspondence",
                issued_date="2016-07-11",
                case_no="2PE00000",
            ),
        ]
    )
    (event,) = [
        e
        for e in build_timeline(corpus, include_curated=False)
        if e.category == "enforcement_order"
    ]
    assert event.also_sources == ("oepa/lima/edoc-463755.order.yaml",)


def test_undated_order_contributes_nothing() -> None:
    corpus = Corpus(orders=[_order("oepa/lima/x.order.yaml", instrument="DFFO")])
    assert not build_timeline(corpus, include_curated=False)


def test_progress_report_dates_on_the_filing_and_joins_on_the_docket() -> None:
    """Every committed Lima progress report leaves `permit_no` null and names the decree docket."""
    corpus = Corpus(
        progress_reports=[
            (
                "oepa/lima/p.progress-report.yaml",
                ProgressReportExtraction(
                    doc_id="p",
                    source_path="/x/p",
                    kind="progress-report",
                    dpi=200,
                    progress_report=ComplianceProgressReport(
                        instrument="Consent Decree",
                        case_no="3:14-CV-02551-JZ",
                        paragraph="33",
                        respondent="City of Lima, Ohio",
                        report_date="2017-07-31",
                        period_start="2017-01-01",
                        period_end="2017-06-30",
                    ),
                ),
            )
        ]
    )
    (event,) = build_timeline(corpus, include_curated=False)
    assert event.date == "2017-07-31"  # the filing, not the period it covers
    assert event.ref == "progress-3:14-CV-02551-JZ-2017-01-01"
    assert "period 2017-01-01 \u2192 2017-06-30" in event.detail


def test_the_committed_lima_enforcement_arc_reaches_the_timeline() -> None:
    """The four spot-checks of the 1994 -> 2043 arc, against the real committed corpus."""
    events = build_timeline(settings=Settings(data_dir=REPO_ROOT / "data", site="lima"))
    orders = {e.date: e for e in events if e.category == "enforcement_order"}
    assert "consent decree" in orders["2015-01-13"].title
    assert "3:14-CV-02551-JZ" in orders["2015-01-13"].title
    assert "DFFO" in orders["1994-02-25"].title
    assert "V-W-05-AO-08" in orders["2005-02-07"].title
    assert "NOV" in orders["2026-07-16"].title


def test_a_flagged_artifact_warning_reaches_the_row_it_dates() -> None:
    """`oepa/lima/edoc-3063821` is a MANSFIELD letter shelved under Lima's permit (custody, not
    attribution). The catalog raises the attribution as a follow-up rather than moving a source
    byte, so the chronology carries the artifact's own flag instead of asserting Lima context.
    """
    corpus = Corpus(
        orders=[
            _order(
                "oepa/lima/edoc-3063821.order.yaml",
                instrument="correspondence",
                issued_date="2020-03-04",
                warnings=[
                    "Permit number may be a placeholder; verify against permit records.",
                    "\u26a0\ufe0f MISFILED AT THE AGENCY — this document's subject is the "
                    "MANSFIELD WWTP in RICHLAND County, not Lima.",
                ],
            )
        ]
    )
    (event,) = build_timeline(corpus, include_curated=False)
    assert "MISFILED AT THE AGENCY" in event.detail
    # Only the FLAGGED warning; the routine OCR caveat stays on the artifact.
    assert "placeholder" not in event.detail
