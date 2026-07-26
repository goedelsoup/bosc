"""Cooling-cycling reconciliation harness (#1679, A3 of the closed-loop epic #1676).

Hermetic: the harness reads the site registry, the cited OHD000001 permit-lifecycle constant,
and the archetype math — no network, no fixture. The properties under test are the classifier's
three outcomes (discrepancy / corroborated / gap), the Intel positive control's no-false-positive
guarantee, the back-solved CoC being an [inference] bracket (never a scalar), and that the
committed artifact validates + matches the resolver.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology import cooling_reconcile as cr
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import CoolingModelType, SiteFacility


def _dry_facility(**kw: object) -> SiteFacility:
    """A closed_loop_dry facility with a resolvable IT load (the epic's low-water claim)."""
    base: dict[str, object] = {
        "name": "Test Dry Campus",
        "status": "confirmed",
        "it_load_mw": 150.0,
        "it_load_low_mw": 120.0,
        "it_load_high_mw": 180.0,
        "it_load_citation": "test screening bracket",
        "it_load_source": "screening",
        "cooling_model": CoolingModelType.CLOSED_LOOP_DRY,
        "cooling_model_source": "reference",
        "cooling_model_citation": "[reference] operator closed-loop claim",
    }
    base.update(kw)
    return SiteFacility(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------- classifier outcomes


def test_dry_claim_with_no_documents_is_a_gap() -> None:
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
    )
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.tag == "[open]"
    assert rec.confidence == "low"
    assert rec.recommended_archetype is None
    # A gap emits a C2 records-request lead payload, never "confirmed dry".
    assert rec.lead is not None
    assert rec.lead["kind"] == "records-request"
    assert rec.lead["epic_ref"] == "#1688 (C2)"
    assert "confirmed dry" not in rec.finding or "not 'confirmed dry'" in rec.finding


def test_dry_claim_with_documented_flow_is_a_discrepancy() -> None:
    # A dry claim predicts ~0 blowdown; a documented 0.5 MGD discharge contradicts it.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(0.5, "MGD", citation="test DMR"),
        seasonality_warm_ratio=1.8,  # a summer peak — the evaporative shape
    )
    assert rec.outcome is cr.ReconcileOutcome.DISCREPANCY
    # Recommends re-archetyping UP, with the source it would carry — but never mutates the facility.
    assert rec.recommended_archetype == CoolingModelType.EVAPORATIVE_TOWER.value
    assert rec.recommended_source == "document"
    assert rec.tag == "[verified]"
    assert "re-archetype" in rec.finding
    # The summer-peak seasonality is folded into the finding as corroborating evidence.
    assert "warm/cool ratio" in rec.finding


def test_dry_claim_with_documented_zero_is_corroborated_dry() -> None:
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(
            0.0, "MGD", citation="test DMR: no flow"
        ),
    )
    assert rec.outcome is cr.ReconcileOutcome.CORROBORATED
    assert rec.recommended_archetype == CoolingModelType.CLOSED_LOOP_DRY.value  # claim holds
    assert rec.recommended_source == "document"
    assert "dry claim" in rec.finding


def test_harness_never_mutates_the_pinned_cooling_model() -> None:
    fac = _dry_facility()
    cr.reconcile_facility(
        fac,
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(0.5, "MGD", citation="test DMR"),
    )
    # The recommendation is advisory only — the facility's pin is untouched (frozen model, but
    # assert the intent explicitly: A3 recommends, B-review edits).
    assert fac.cooling_model is CoolingModelType.CLOSED_LOOP_DRY


# --------------------------------------------------------------------- the Intel control


def test_intel_control_classifies_corroborated_not_a_false_discrepancy() -> None:
    # The calibration gate: an openly-evaporative facility whose documented water MATCHES its
    # evaporative prediction must be corroborated — never flagged discrepant for using a lot of
    # water. This is the property the whole harness is calibrated against.
    rec = cr.intel_control(settings=Settings())
    assert rec.is_control is True
    assert rec.account.archetype is CoolingModelType.EVAPORATIVE_TOWER
    assert rec.outcome is cr.ReconcileOutcome.CORROBORATED
    assert rec.outcome is not cr.ReconcileOutcome.DISCREPANCY  # the no-false-positive guarantee
    assert "corroborated evaporative" in rec.finding


def test_intel_control_backsolved_coc_is_a_bracket_not_a_scalar() -> None:
    rec = cr.intel_control(settings=Settings())
    coc = rec.account.backsolved_cycles
    assert coc is not None
    # The back-solved CoC is emitted as an [inference] bracket, never a headline scalar.
    assert coc.source == "derived"  # [inference]
    assert coc.has_range
    assert coc.low_or_value < coc.value < coc.high_or_value
    # Back-solves to ≈ the disclosed CoC 5 (2.2 / 0.45 ≈ 4.9).
    assert 4.5 <= coc.value <= 5.2


def test_a_wet_claim_over_the_band_is_a_discrepancy() -> None:
    # An evaporative claim whose documented blowdown is FAR above its prediction is over-cycling
    # — still a discrepancy, so the guard isn't "wet claims are never discrepant".
    fac = SiteFacility(
        name="Test Evap Campus",
        status="confirmed",
        it_load_mw=150.0,
        it_load_low_mw=120.0,
        it_load_high_mw=180.0,
        it_load_citation="test",
        it_load_source="screening",
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        cooling_model_source="reference",
        cooling_model_citation="[reference] evaporative claim",
        wue_l_per_kwh=1.8,
        wue_citation="test",
        cycles_of_concentration=5.0,
        cycles_citation="test",
    )
    rec = cr.reconcile_facility(
        fac,
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(5.0, "MGD", citation="test DMR"),
    )
    assert rec.outcome is cr.ReconcileOutcome.DISCREPANCY


# --------------------------------------------------------------------- cohort


def test_cohort_is_registry_derived_all_gap_today_plus_intel_control() -> None:
    records = cr.reconcile_cohort(settings=Settings())
    assert records
    control = [r for r in records if r.is_control]
    live = [r for r in records if not r.is_control]
    # Exactly one control (Intel), corroborated; it sorts last.
    assert len(control) == 1
    assert records[-1].is_control
    assert control[0].outcome is cr.ReconcileOutcome.CORROBORATED
    # Every live cohort facility is a closed_loop / hybrid claim (A2's cohort), and — with no
    # documented water on record while OHD000001 is draft — resolves to a gap today.
    assert live
    assert all(r.claimed_archetype in {"closed_loop_dry", "hybrid_adiabatic"} for r in live)
    assert all(r.outcome is cr.ReconcileOutcome.GAP for r in live)
    # A known closed-loop pin is in the cohort; an UNKNOWN-cooling facility is not.
    assert "urbana" in {r.site for r in live}
    assert "troy-piqua" not in {r.site for r in live}


def test_open_load_facility_cannot_be_predicted() -> None:
    # A disclosed facility whose IT load is entirely [open] can't have its archetype water
    # predicted — the harness refuses rather than leaking the Lima fallback load.
    fac = _dry_facility(
        it_load_mw=None,
        it_load_low_mw=None,
        it_load_high_mw=None,
        it_load_citation=None,
        it_load_source=None,
    )
    with pytest.raises(ValueError, match="no resolvable IT load"):
        cr.reconcile_facility(
            fac, site="x", claim_source="reference", claim_citation="x", settings=Settings()
        )


# --------------------------------------------------------------------- artifact


def test_reconciliation_document_shape_and_round_trip(tmp_path: Path) -> None:
    records = cr.reconcile_cohort(settings=Settings())
    doc = cr.reconciliation_document(records)
    assert doc["meta"]["regenerate"] == "watermark cooling-reconcile --write"
    assert doc["meta"]["outcomes"]["gap"] >= 1
    assert len(doc["candidates"]) == len(records)
    out = tmp_path / "reconciliation.yaml"
    cr.write_reconciliation(doc, out=out)
    reloaded = yaml.safe_load(out.read_text(encoding="utf-8"))
    # Each candidate round-trips back into the model (the artifact stays schema-valid).
    for row in reloaded["candidates"]:
        cr.ReconciliationRecord.model_validate(row)


def test_committed_artifact_matches_the_resolver() -> None:
    path = Path("data/reference/oepa/cooling-reconciliation.yaml")
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    live = cr.reconcile_cohort(settings=Settings())
    committed_sites = [c["site"] for c in doc["candidates"]]
    live_sites = [r.site for r in live]
    assert committed_sites == live_sites  # no hand-drift, deterministic ordering
    for row in doc["candidates"]:
        cr.ReconciliationRecord.model_validate(row)
    # The Intel control row is present and corroborated.
    control = [c for c in doc["candidates"] if c["is_control"]]
    assert len(control) == 1
    assert control[0]["outcome"] == "corroborated"
