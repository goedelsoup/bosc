"""Tests for the cross-document corpus loader."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from watermark.config import Settings
from watermark.models import (
    BusinessFiling,
    Deed,
    DeedExtraction,
    NpdesExtraction,
    NpdesPermit,
    NpdesTranscription,
    OPCMeta,
    OPCSummary,
    OrderExtraction,
    SosExtraction,
    SubEstimate,
)
from watermark.pipeline.corpus import (
    DECLINED,
    UNPARSED,
    CorpusValidationError,
    _classify,
    load_corpus,
)
from watermark.sites import WHOLE_TREE

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_load_corpus_classifies_by_shape(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    ex = settings.extracted_dir

    deed = DeedExtraction(
        doc_id="d",
        source_path="/x/a.pdf",
        kind="deed",
        dpi=200,
        deed=Deed(instrument_no="I1", grantees=["Acme LLC"]),
    )
    _write(ex / "recorder" / "a.deed.yaml", deed.to_yaml())

    permit = NpdesExtraction(
        doc_id="n",
        source_path="/x/b.pdf",
        kind="npdes",
        dpi=150,
        permit=NpdesPermit(permit_no="2PH00006"),
    )
    _write(ex / "oepa" / "b.npdes.yaml", permit.to_yaml())

    filing = SosExtraction(
        doc_id="s",
        source_path="/x/c.pdf",
        kind="sos",
        dpi=200,
        filing=BusinessFiling(entity_name="Tilted Gate LLC", jurisdiction="Delaware"),
    )
    _write(ex / "permits" / "c.sos.yaml", filing.to_yaml())

    summary = OPCSummary(
        meta=OPCMeta(date="2025-07-11", program="Roadwork"),
        sub_estimates=[SubEstimate(name="RB1", construction_subtotal=100, total=125)],
    )
    _write(ex / "aedg" / "s.summary.opc.yaml", yaml.safe_dump(summary.model_dump()))

    # Noise that must be skipped, not crash the load.
    _write(ex / "aedg" / "junk.yaml", "just: a string\n")

    corpus = load_corpus(settings)
    assert len(corpus.deeds) == 1
    assert len(corpus.permits) == 1
    assert len(corpus.filings) == 1
    assert len(corpus.summaries) == 1
    assert corpus.filings[0][1].filing.entity_name == "Tilted Gate LLC"
    assert not corpus.is_empty()
    rel, loaded_deed = corpus.deeds[0]
    assert rel == "recorder/a.deed.yaml"
    assert loaded_deed.deed.instrument_no == "I1"


_DMR_YAML = """\
meta:
  subject: PIQUA WWTP (NPDES OH0027049) — reported effluent record (EPA ECHO DMR)
  source: EPA ECHO eff_rest_services.get_effluent_chart
  regenerate: watermark dmr OH0027049 --start 2023-01-01 --end 2023-12-31 --design-flow 8.7
  discipline: Reported DMR values are verbatim from the permittee's submissions via ECHO.
permit:
  npdes_id: OH0027049
  name: PIQUA WWTP
  permit_type: NPDES Individual Permit
  permit_status: Effective
  major_minor: M
  snc_status: null
  window: 2023-01-01..2023-12-31
discharge_summary:
  design_flow_mgd: 8.7
  design_flow_cfs: 13.46
  primary_outfall: '001'
  n_flow_months: 12
  actual_flow_mean_mgd: 3.224
  actual_flow_mean_cfs: 4.99
  actual_flow_min_mgd: 2.146
  actual_flow_max_mgd: 5.822
  flow_pct_of_design: 37.1
  overflow_outfalls: 0
  reported_exceedances: 0
flow_monthly:
- period_end: '2023-01-31'
  value_mgd: 3.46
  stat_base: MO AVG
exceedances: []
"""


_MINIMAL_DMR_PAYLOAD = {
    "meta": {
        "subject": "PIQUA WWTP (NPDES OH0027049) — reported effluent record (EPA ECHO DMR)",
        "source": "EPA ECHO eff_rest_services.get_effluent_chart",
        "regenerate": "watermark dmr OH0027049 --start 2023-01-01 --end 2023-12-31",
        "discipline": "Reported DMR values are verbatim from the permittee's submissions.",
    },
    "permit": {"npdes_id": "OH0027049", "window": "2023-01-01..2023-12-31"},
    "discharge_summary": {"n_flow_months": 12, "overflow_outfalls": 0, "reported_exceedances": 0},
    "flow_monthly": [],
    "exceedances": [],
}


def test_classify_distinguishes_npdes_doc_from_dmr_pull() -> None:
    """A real NpdesExtraction and an ECHO DMR pull both key `permit:` (#1492)."""
    assert _classify({"permit": {"permit_no": "2PH00006"}}) == "npdes"
    assert _classify(_MINIMAL_DMR_PAYLOAD) == "npdes_dmr"
    # A document-shaped payload that merely happens to carry a `discharge_summary` key
    # (no `meta:`, no `permit.npdes_id`/`window`) must not be misrouted to npdes_dmr —
    # it would then fail DmrExtraction validation and land right back in the
    # silently-dropped bug this discriminator exists to fix.
    assert (
        _classify({"permit": {"permit_no": "2PH00006"}, "discharge_summary": "not a mapping"})
        == "npdes"
    )


def test_load_corpus_loads_dmr_pull_as_its_own_kind(tmp_path: Path) -> None:
    """An ECHO DMR effluent-record pull validates and loads, distinct from corpus.permits."""
    # The pull lives under the ``troy-piqua/`` subtree, so read it as that site — Lima's scope now
    # subtracts every peer's subtree (#1505), so the default (lima) would correctly exclude it.
    settings = Settings(data_dir=tmp_path, site="troy-piqua")
    _write(settings.extracted_dir / "troy-piqua" / "wwtp-oh0027049.dmr.yaml", _DMR_YAML)

    corpus = load_corpus(settings)
    assert len(corpus.dmr_records) == 1
    assert len(corpus.permits) == 0
    rel, dmr = corpus.dmr_records[0]
    assert rel == "troy-piqua/wwtp-oh0027049.dmr.yaml"
    assert dmr.permit.npdes_id == "OH0027049"
    assert dmr.discharge_summary.n_flow_months == 12
    assert len(dmr.flow_monthly) == 1


@pytest.mark.parametrize(
    "site,rel,npdes_id",
    [
        ("troy-piqua", "troy-piqua/wwtp-oh0027049.dmr.yaml", "OH0027049"),
        ("fort-wayne", "fort-wayne/wwtp-in0032191.dmr.yaml", "IN0032191"),
        ("sidney", "sidney/wwtp-oh0027421.dmr.yaml", "OH0027421"),
    ],
)
def test_load_corpus_loads_every_committed_dmr_pull(site: str, rel: str, npdes_id: str) -> None:
    """Every committed ECHO DMR pull validates and loads into dmr_records, not permits (#1492)."""
    settings = Settings(data_dir=REPO_ROOT / "data", site=site)
    corpus = load_corpus(settings)
    dmr_by_rel = dict(corpus.dmr_records)
    assert rel in dmr_by_rel
    assert rel not in dict(corpus.permits)
    assert dmr_by_rel[rel].permit.npdes_id == npdes_id


def test_load_corpus_empty(tmp_path: Path) -> None:
    corpus = load_corpus(Settings(data_dir=tmp_path))
    assert corpus.is_empty()
    assert len(corpus) == 0


_LEGACY_DETAIL = """\
estimate_template:
  contingency_rate: 0.25
page_319_diller:
  title: "Cole/Diller Roundabout"
  pdf_page: 319
  construction_subtotal: 1228174
  contingency_and_inflation_25pct: 307044
  total: 1535218
  line_items:
    ROADWAY:
      items:
        - item_no: "203E10000"
          description: "Excavation"
          quantity: ~2490
          unit: "CY"
          total_amount: ~42315
      subtotal: ~109307
extraction_notes:
  confidence_levels: {dollar_totals: HIGH}
"""


def test_legacy_opc_detail_loads_as_estimate(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    _write(settings.extracted_dir / "aedg" / "roundabouts.detail.opc.yaml", _LEGACY_DETAIL)
    corpus = load_corpus(settings)
    # The bespoke detail is unified onto the generic Estimate shape (in memory).
    assert len(corpus.estimates) == 1
    _, pe = corpus.estimates[0]
    est = pe.estimate
    assert est.name == "Cole/Diller Roundabout"
    assert pe.pdf_page == 319
    assert est.construction_subtotal == 1228174
    assert est.total == 1535218
    assert est.section("ROADWAY") is not None
    # The ~ approximate marker is coerced to an int for computation.
    assert est.section("ROADWAY").line_items[0].quantity == 2490
    assert est.markups[0].rate == 0.25


# --- #1994: the claimed-then-dropped guard, and the classifier's positive shape tests --------

_MINIMAL_DMR_PAYLOAD = {
    "meta": {"subject": "DMR pull"},
    "permit": {"npdes_id": "OH0027421", "window": "2023-01-01..2023-12-31"},
    "discharge_summary": {},
}


def test_no_committed_extraction_is_claimed_then_dropped() -> None:
    """`_classify` claiming a file and its model then rejecting it is a DEFECT (#1994).

    The two originals — `oepa/sidney/1PD00009.npdes.yaml` and
    `regulatory/ohc000006-construction-stormwater-gp.yaml` — were found by a hand sweep months
    after they were committed, because the drop was one WARNING among eighty-one. A dropped file
    still publishes into the `records` feed, so it LOOKS PRESENT AND IS NOT.

    Whole-tree, not per-site: validity is a property of the FILE, and a per-site sweep would be
    blind to any path no registered site's scope claims (and 26x slower).
    """
    corpus = load_corpus(Settings(data_dir=REPO_ROOT / "data", site="lima"), scope=WHOLE_TREE)
    assert not corpus.rejected, (
        "the corpus loader could not take these committed artifacts in — they are silently "
        "absent from the timeline, entity graph and yidam mirror while `records.py` still "
        "publishes them. A `kind` of "
        f"`{UNPARSED}` means the file never parsed (#2084); anything else means the classifier "
        "claimed it and its model rejected it:\n"
        + "\n".join(f"  {r.kind:>18}  {r.rel}\n{' ' * 22}{r.error}" for r in corpus.rejected)
        + "\n\nFix the artifact or route the kind to a model that fits. Do NOT invent "
        "`doc_id`/`dpi`/`source_path` to make a transcription validate as a vision render."
    )


def test_classify_does_not_claim_a_bare_meta_block_as_an_opc_summary() -> None:
    """The `or "meta" in data` fallthrough claimed 72 files; ONE was an OPC summary (#1994).

    The other 71 — meeting indexes, `commissioners/minutes/filename-map.yaml`, water-watch
    reports, PRR response indexes — validated because `OPCSummary` defaults every field, and
    were inert only because `timeline._opc_events` skips a summary with no `meta.date`. The
    first artifact to key a `date` under `meta:` would have put a fabricated "OPC estimate"
    event on a water-watch report's timeline.
    """
    assert (
        _classify({"meta": {"subject": "Van Wert water watch", "checked_on": "2026-07-01"}})
        == DECLINED
    )
    assert _classify({"meta": {"kind": "idem"}, "permit_number": "WQC001454"}) == DECLINED
    # The real shape still classifies — an OPC summary is identified by what it is.
    assert _classify({"sub_estimates": [], "meta": {"date": "2025-07-11"}}) == "opc_summary"


def test_every_loaded_opc_summary_is_actually_an_opc_summary() -> None:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    summaries = load_corpus(settings).summaries
    assert summaries, "the reference build must still load its one real OPC summary"
    for rel, _ in summaries:
        raw = yaml.safe_load((settings.extracted_dir / rel).read_text(encoding="utf-8"))
        assert "sub_estimates" in raw, f"{rel} is not an OPC summary"


def test_classify_separates_a_transcription_from_a_render_from_a_framework_permit() -> None:
    render = {
        "doc_id": "n",
        "source_path": "x.pdf",
        "kind": "npdes",
        "dpi": 150,
        "permit": {"permit_no": "2PH00006"},
    }
    assert _classify(render) == "npdes"
    # A render extraction that ALSO carries a `provenance:` block stays a render — the real
    # `oepa/ottawa/2PD00028.npdes.yaml` shape; the envelope test runs first.
    assert _classify({**render, "provenance": {"extractor": "reviewed"}}) == "npdes"
    # Both committed transcription conventions.
    assert (
        _classify(
            {
                "permit": {"permit_no": "1PD00009*SD"},
                "meta": {"sources": {"permit": {"path": "data/documents/a.pdf"}}},
            }
        )
        == "npdes_transcribed"
    )
    assert (
        _classify(
            {
                "kind": "general_permit",
                "permit": {"permit_no": "OHC000006"},
                "provenance": {"sources": ["data/documents/b.pdf"]},
            }
        )
        == "general_permit"
    )
    # A DMR pull carries `meta:` too — the ordering is the guarantee, not the accident.
    assert _classify(_MINIMAL_DMR_PAYLOAD) == "npdes_dmr"
    # Neither shape: MALFORMED, not a third genre. It must fail loudly rather than be
    # reclassified into the loose envelope — that trades a silent drop for a silent mislabel.
    assert _classify({"permit": {"permit_no": "X"}}) == "npdes"


def test_transcription_envelope_requires_a_committed_source() -> None:
    with pytest.raises(ValidationError, match="data/documents/"):
        NpdesTranscription.model_validate(
            {"permit": {"permit_no": "X"}, "meta": {"sources": ["my-notes.txt"]}}
        )


def test_transcription_envelope_refuses_a_render_receipt() -> None:
    """A transcription may not assert a render it did not perform (#1994).

    `oepa/van-wert/2GC08872.approval.npdes.yaml` opens "HAND-READ, not a vision extraction …
    nothing was OCR'd" and then carries `dpi: 150`, because the type it was written against
    demanded a receipt. Removing the field is not enough — the pressure has to be unsatisfiable.
    """
    with pytest.raises(ValidationError, match="all-or-nothing"):
        NpdesTranscription.model_validate(
            {
                "permit": {"permit_no": "X"},
                "dpi": 150,
                "meta": {"sources": ["data/documents/a.pdf"]},
            }
        )


_HAND_READ_DECLARED = re.compile(
    r"hand[- ]read|nothing was OCR'?d|not a vision extraction|no page was rasterized",
    re.IGNORECASE,
)
_RENDER_RECEIPT_KEYS = ("doc_id", "dpi", "pages_read", "image_pages_read")


def _leading_comment(text: str) -> str:
    """The contiguous ``#`` header at the top of a YAML file, blank lines tolerated.

    Scanned deliberately narrowly. An earlier draft of this gate read *any* comment line in the
    first 40 and flagged seven committed render extractions, whose deeper inline comments say
    things like "transcribed from the rendered image" — a phrase about the render, not a denial
    of one. A file's leading block is where it declares what it IS; that is the only place this
    gate reads.

    A leading ``---`` document marker is stepped over rather than treated as the end of the
    header. No committed extraction opens with one today, so this changes nothing now — it is
    here because the failure mode would be silent: a hand-read declaration written *below* a
    marker would stop being scanned, and a gate whose whole job is to not miss things must not
    have a way to quietly stop looking.
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            out.append(stripped)
        elif not stripped or stripped == "---":
            continue
        else:
            break
    return "\n".join(out)


def test_no_committed_hand_read_carries_a_render_receipt() -> None:
    """A file that says it was hand-read may not also claim a render (#2001).

    :class:`~watermark.models.TranscribedExtraction` refuses the combination at the type level,
    but only for files that REACH it: a full, well-formed render envelope routes to ``npdes`` and
    validates happily, so the type system cannot retroactively detect an artifact that already
    carries one. Both van-wert ``2GC08872`` extractions did — each opened "HAND-READ, not a vision
    extraction … nothing was OCR'd" and then asserted ``dpi: 150``, because the type they were
    written against required a receipt and the alternative was being silently dropped (#1994).

    ``dpi`` is how a reader tells a figure read off a rasterized image — where the OCR digits are
    untrustworthy, which the repo's whole extract discipline turns on — from one transcribed off a
    clean text layer. A false receipt inverts that signal inside litigation evidence, so the
    corpus is swept rather than trusted.

    The render-receipt check is TOP-LEVEL ONLY, deliberately. It mirrors
    :meth:`TranscribedExtraction._carries_no_render_receipt`, which inspects the model's own
    ``__pydantic_extra__`` and nothing nested — this gate backstops that rule, so it must test the
    same thing. Recursing would also produce false positives on a different sense of the word:
    ``legal/web-vendor-audit/allen-county-web-vendor-corporate-records.yaml`` nests eight
    ``doc_id`` keys that are **Ohio Secretary of State filing numbers** (``'201414700542'``), not
    render receipts.
    """
    offenders: list[str] = []
    for path in sorted(
        p
        for pattern in ("*.yaml", "*.yml")
        for p in (REPO_ROOT / "data" / "extracted").rglob(pattern)
    ):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not _HAND_READ_DECLARED.search(_leading_comment(text)):
            continue
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            continue
        if claimed := [k for k in _RENDER_RECEIPT_KEYS if k in data]:
            rel = path.relative_to(REPO_ROOT)
            offenders.append(f"{rel} claims {', '.join(claimed)}")

    assert not offenders, (
        "these files declare a hand read in their own leading comment and then assert a vision "
        "render. Remove the receipt (a transcription carries none) — never invent a dpi to "
        "satisfy a schema:\n  " + "\n  ".join(offenders)
    )


def test_source_path_does_not_shadow_its_own_digest() -> None:
    """The block is read first, so the role + sha256 survive when source_path names the file."""
    ex = NpdesTranscription.model_validate(
        {
            "source_path": "data/documents/a.pdf",
            "meta": {"sources": {"permit": {"path": "data/documents/a.pdf", "sha256": "abc"}}},
            "permit": {},
        }
    )
    assert [(s.path, s.role, s.sha256) for s in ex.sources] == [
        ("data/documents/a.pdf", "permit", "abc")
    ]


# --- the wastewater-compliance genres (#1746/#2077/#2079) ------------------------------------

_RENDER = {"doc_id": "edoc-1", "source_path": "data/documents/oepa/lima/edoc-1.pdf", "dpi": 200}


def test_classify_routes_each_compliance_genre_by_its_own_payload_block() -> None:
    assert _classify({**_RENDER, "kind": "order", "order": {"instrument": "DFFO"}}) == "order"
    assert (
        _classify({**_RENDER, "kind": "inspection", "inspection": {"type_code": "CEI"}})
        == "inspection"
    )
    assert (
        _classify({**_RENDER, "kind": "progress-report", "progress_report": {"paragraph": "33"}})
        == "progress_report"
    )
    assert (
        _classify({**_RENDER, "kind": "engineering", "record": {"discipline": "sanitary"}})
        == "engineering"
    )


def test_classify_does_not_claim_a_generic_record_or_order_scalar() -> None:
    """`record:` is the loosest word of the four — it is tested as a MAPPING for that reason."""
    assert _classify({**_RENDER, "kind": "x", "record": "see the minutes"}) == DECLINED
    assert _classify({**_RENDER, "kind": "x", "order": ["first", "second"]}) == DECLINED


def test_a_declared_manual_read_is_declined_and_anything_else_fails_loudly() -> None:
    """The third committed convention: a human read of page images, declaring its own method.

    Nine artifacts carry `doc_id`+`source_path`+`kind`+`pages_read`+`method` and NO `dpi` — six
    Allen County DFFO/SSO-closure instruments, West Union's 1993 consent order, two awards.
    Neither `DocExtraction` (needs `dpi`) nor `TranscribedExtraction` (refuses `doc_id`/
    `pages_read`) fits them, so they stay DECLINED *deliberately*. A payload that is neither a
    render nor one of these is MALFORMED and still routes to its model, so `Corpus.rejected`
    names it (#1994) — that is the guarantee the decline must not weaken.
    """
    manual = {
        "doc_id": "dffo-2005-journalized",
        "source_path": "data/documents/legal/prr-mandamus/dffo-2005.pdf",
        "kind": "order",
        "pages_read": [0, 1],
        "method": "manual transcription from the scanned journalized instrument",
        "order": {"instrument": "DFFO"},
    }
    assert _classify(manual) == DECLINED
    # No declared method, no render receipt: malformed, and it must reach OrderExtraction.
    assert _classify({k: v for k, v in manual.items() if k != "method"}) == "order"
    # Nor is `method` alone enough. A payload that declares how it was read and then names
    # NOTHING it read asserts none of this convention; declining it would be the silent drop.
    no_pages = {k: v for k, v in manual.items() if k != "pages_read"}
    assert _classify(no_pages) == "order"
    with pytest.raises(ValidationError, match="dpi"):
        OrderExtraction.model_validate(no_pages)
    # But an EMPTY `pages_read` is a declaration, and a true one: three of the nine are
    # `textutil` reads of native .doc/.docx letters, which have no pages to read.
    assert _classify({**manual, "pages_read": []}) == DECLINED


def test_classify_leaves_the_resolution_genre_unclaimed() -> None:
    """32 hand-authored legislative transcriptions with no extractor and no envelope (#2080).

    Their shapes converged on `body`/`instrument`/`body_kind` but NOT on a date — 20 carry
    `adopted`, 7 carry `meeting_date`. Claiming them means designing the genre, not wiring it.
    """
    assert (
        _classify(
            {
                "resolution": {"body": "Sidney City Council", "adopted": "2025-10-27"},
                "source": {"file": "data/documents/sidney/council/res-80-25.pdf"},
            }
        )
        == DECLINED
    )


def test_the_committed_compliance_genres_all_load() -> None:
    """Whole-tree, like the #1994 gate: validity is a property of the FILE."""
    corpus = load_corpus(Settings(data_dir=REPO_ROOT / "data", site="lima"), scope=WHOLE_TREE)
    assert len(corpus.orders) == 32
    assert len(corpus.inspections) == 30
    assert len(corpus.progress_reports) == 9
    # 3 -> 4 (#2088): `permits/4230068.sanitary.yaml`, the Ohio EPA ePlan PTI application for the
    # BOSC-1A sanitary sewer Rev. 1. `sanitary` is the discipline ALIAS of the engineering read
    # (extract.extract_sanitary), so it lands in this bucket by design, not by misclassification.
    # Reviewed by enumerating the bucket, not by trusting the delta: oepa/lima/edoc-1840394,
    # edoc-1840396, edoc-1840397 (the three pre-existing) plus permits/4230068 (the new one).
    assert len(corpus.engineering) == 4
    # A count of 4 is satisfied by ANY four, so name the one this bucket gained.
    assert "permits/4230068.sanitary.yaml" in {rel for rel, _ in corpus.engineering}
    # Every declined file that keys one of these blocks is a declared manual read or a
    # `resolution:` — never a render extraction that quietly fell out of the loader.
    for rel in corpus.declined:
        raw = yaml.safe_load((REPO_ROOT / "data" / "extracted" / rel).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            continue
        for block in ("order", "inspection", "progress_report", "record"):
            if isinstance(raw.get(block), dict):
                assert "dpi" not in raw and isinstance(raw.get("method"), str), (
                    f"{rel} keys `{block}:` and is neither a render extraction nor a declared "
                    "manual read — it fell out of the corpus silently"
                )


def test_every_committed_extraction_parses() -> None:
    """An unparseable artifact is a silent drop from EVERY feed, and no other gate sees it.

    Since #2084 the loader records one as a `CorpusReject` under the `UNPARSED` sentinel, so
    `test_no_committed_extraction_is_claimed_then_dropped` covers it too. This stays as the
    narrower, faster backstop that names the file and its YAML error directly, and it is
    independent of the loader: it would still fail if a future refactor put the parse failure
    back behind a `continue`.

    This is not hypothetical. Editing one prose warning in
    `oepa/lima/edoc-1879637.order.yaml` put a `": "` inside an unquoted multi-line scalar, and
    the artifact vanished from `records` (160 -> 159), from the corpus, and from the timeline
    (233 -> 232) — while `catalog check`, `producer-check` and `export --check --all` all
    reported clean, because a re-export moves the committed bundle and the fresh one together.
    Whole-tree, like the #1994 gate: parseability is a property of the FILE.
    """
    unparseable: list[str] = []
    extracted = REPO_ROOT / "data" / "extracted"
    for path in sorted(extracted.rglob("*.yaml")):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            rel = path.relative_to(extracted)
            unparseable.append(f"  {rel}\n      {str(exc).splitlines()[0]}")
    assert not unparseable, (
        "these committed extractions do not parse, so they are absent from the corpus, the "
        "timeline, the entity graph and the records feed — with only a WARNING to say so:\n"
        + "\n".join(unparseable)
        + '\n\nA `": "` or a " #" inside an unquoted multi-line scalar is the usual cause.'
    )


def _broken_yaml_artifact(ex: Path) -> None:
    """One deed extraction with the #2082 defect: a `": "` inside an unquoted multi-line scalar."""
    _write(
        ex / "recorder" / "broken.deed.yaml",
        """
doc_id: broken
source_path: data/documents/recorder/broken.pdf
kind: deed
dpi: 300
deed:
  instrument_no: I2
  grantees: [Acme LLC]
warnings:
  - a wrapped note that quotes a form's own field label,
    Subsequent Stream Network: Middle Creek, and thereby
    ends the scalar where no one meant it to end
""".lstrip(),
    )


def test_an_unparseable_artifact_is_a_reject_not_a_log_line(tmp_path: Path) -> None:
    """Parsed-never must not be dropped-silently — the half of #1994 one step earlier (#2084).

    A `yaml.YAMLError` used to be a WARNING and a `continue`, so the file reached neither
    `Corpus.rejected` nor `Corpus.declined`: not counted, not reported, and invisible to
    `test_no_committed_extraction_is_claimed_then_dropped`, which asserts the reject set is empty
    but can only see files the classifier CLAIMED. It has happened twice for real (#1402, #2082),
    and on #2082 `catalog check`, `producer-check` and `export --check --all` all reported clean —
    a drift gate structurally cannot see a deletion you caused and then re-exported over.
    """
    settings = Settings(data_dir=tmp_path)
    ex = settings.extracted_dir
    good = DeedExtraction(
        doc_id="good",
        source_path="data/documents/recorder/good.pdf",
        kind="deed",
        dpi=300,
        deed=Deed(instrument_no="I1", grantees=["Acme LLC"]),
    )
    _write(ex / "recorder" / "good.deed.yaml", good.to_yaml())
    _broken_yaml_artifact(ex)

    corpus = load_corpus(settings, scope=WHOLE_TREE)

    # The valid neighbour still loads: one malformed artifact must not blind the whole layer.
    assert [rel for rel, _ in corpus.deeds] == ["recorder/good.deed.yaml"]
    # And the broken one is REPORTED — named, with its parse error, under the sentinel kind.
    assert len(corpus.rejected) == 1
    reject = corpus.rejected[0]
    assert reject.rel == "recorder/broken.deed.yaml"
    assert reject.kind == UNPARSED
    assert reject.unparsed is True
    assert reject.error
    # It is a reject, not a decline: the loader never reached a genre decision about it.
    assert "recorder/broken.deed.yaml" not in corpus.declined
    # And never a loaded artifact.
    assert "recorder/broken.deed.yaml" not in corpus.rel_paths()


def test_strict_load_raises_on_an_unparseable_artifact(tmp_path: Path) -> None:
    """`strict=True` is the gate's edge, and #2084 puts a parse failure behind it too."""
    settings = Settings(data_dir=tmp_path)
    _broken_yaml_artifact(settings.extracted_dir)

    with pytest.raises(CorpusValidationError) as excinfo:
        load_corpus(settings, scope=WHOLE_TREE, strict=True)

    message = str(excinfo.value)
    assert "recorder/broken.deed.yaml" in message
    assert UNPARSED in message
    assert "did not parse at all" in message
    assert [r.rel for r in excinfo.value.rejects] == ["recorder/broken.deed.yaml"]


def test_records_loader_and_corpus_loader_answer_a_parse_failure_the_same_way(
    tmp_path: Path,
) -> None:
    """Both read surfaces funnel through one parse (#2084).

    `load_records` has no reject bucket of its own — it yields one `_Record` per file from raw
    dicts — so the shared `read_artifact_yaml` is what keeps the two loaders from disagreeing
    about what an unparseable artifact is. On #2082 the same file left the corpus, the timeline
    and the records feed at once; the ERROR must be raised once, in one place, for all of them.
    """
    from watermark.site.records import load_records

    settings = Settings(data_dir=tmp_path)
    ex = settings.extracted_dir
    _broken_yaml_artifact(ex)

    corpus = load_corpus(settings, scope=WHOLE_TREE)
    records = load_records(ex, scope=WHOLE_TREE)

    assert [r.rel for r in corpus.rejected] == ["recorder/broken.deed.yaml"]
    assert [r.rel for r in records] == []
