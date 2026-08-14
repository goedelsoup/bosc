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
    SosExtraction,
    SubEstimate,
)
from watermark.pipeline.corpus import DECLINED, _classify, load_corpus
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
        "the corpus classifier claimed these committed artifacts and their models rejected "
        "them — they are silently absent from the timeline, entity graph and yidam mirror "
        "while `records.py` still publishes them:\n"
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
