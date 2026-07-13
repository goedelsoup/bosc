"""Tests for the cross-document corpus loader."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.models import (
    BusinessFiling,
    Deed,
    DeedExtraction,
    NpdesExtraction,
    NpdesPermit,
    OPCMeta,
    OPCSummary,
    SosExtraction,
    SubEstimate,
)
from watermark.pipeline.corpus import _classify, load_corpus

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
  cso_outfalls: 0
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
    "discharge_summary": {"n_flow_months": 12, "cso_outfalls": 0, "reported_exceedances": 0},
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
