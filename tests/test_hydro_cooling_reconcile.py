"""Cooling-cycling reconciliation harness (#1679, A3 of the closed-loop epic #1676).

Hermetic: the harness reads the site registry, the cited OHD000001 permit-lifecycle constant,
and the archetype math — no network, no fixture. The properties under test are the classifier's
four outcomes (discrepancy / corroborated / reservation_conflict / gap), the Troy-Piqua B1
reservation conflict (#1681), the Intel positive control's no-false-positive guarantee, the
back-solved CoC being an [inference] bracket (never a scalar), and that the committed artifact
validates + matches the resolver.
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
    # A gap emits a C2 records-request lead payload (a typed model), never "confirmed dry".
    assert rec.lead is not None
    assert isinstance(rec.lead, cr.RecordsRequestLead)
    assert rec.lead.kind == "records-request"
    assert rec.lead.epic_ref == "#1688 (C2)"
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


def _evap_facility(**kw: object) -> SiteFacility:
    """An evaporative_tower facility (150 MW / WUE 1.8 / CoC 5 → ~2.14 MGD makeup, ~0.43 bd)."""
    base: dict[str, object] = {
        "name": "Test Evap Campus",
        "status": "confirmed",
        "it_load_mw": 150.0,
        "it_load_low_mw": 120.0,
        "it_load_high_mw": 180.0,
        "it_load_citation": "test",
        "it_load_source": "screening",
        "cooling_model": CoolingModelType.EVAPORATIVE_TOWER,
        "cooling_model_source": "reference",
        "cooling_model_citation": "[reference] evaporative claim",
        "wue_l_per_kwh": 1.8,
        "wue_citation": "test",
        "cycles_of_concentration": 5.0,
        "cycles_citation": "test",
    }
    base.update(kw)
    return SiteFacility(**base)  # type: ignore[arg-type]


def test_a_wet_claim_over_the_band_is_a_discrepancy() -> None:
    # An evaporative claim whose documented blowdown is FAR above its prediction is over-cycling
    # — still a discrepancy, so the guard isn't "wet claims are never discrepant".
    rec = cr.reconcile_facility(
        _evap_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(5.0, "MGD", citation="test DMR"),
    )
    assert rec.outcome is cr.ReconcileOutcome.DISCREPANCY


def test_wet_claim_makeup_only_compares_against_predicted_makeup() -> None:
    # A wet claim with a documented WITHDRAWAL (A1 makeup) but no blowdown (A2) must reconcile
    # the makeup against PREDICTED MAKEUP, never predicted blowdown — the finding would otherwise
    # compare mismatched quantities (makeup vs blowdown).
    rec = cr.reconcile_facility(
        _evap_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        documented_makeup=ProvenancedValue.from_document(2.2, "MGD", citation="test withdrawal"),
    )
    assert rec.outcome is cr.ReconcileOutcome.CORROBORATED
    # No blowdown on record → nothing to back-solve CoC from.
    assert rec.account.backsolved_cycles is None
    # The finding cites the predicted MAKEUP (~2.14), not the predicted blowdown (~0.43), and
    # labels the documented signal as makeup.
    pred_makeup = rec.account.predicted_makeup.value
    pred_blowdown = rec.account.predicted_blowdown.value
    assert pred_makeup != pred_blowdown  # the two are distinct, so the check is meaningful
    assert f"{pred_makeup:g} MGD prediction" in rec.finding
    assert f"{pred_blowdown:g} MGD prediction" not in rec.finding
    assert "MGD makeup matches" in rec.finding


# --------------------------------------------------------------------- cohort


def test_cohort_is_registry_derived_gaps_plus_troy_piqua_and_intel_control() -> None:
    records = cr.reconcile_cohort(settings=Settings())
    assert records
    control = [r for r in records if r.is_control]
    live = [r for r in records if not r.is_control]
    # Exactly one control (Intel), corroborated; it sorts last.
    assert len(control) == 1
    assert records[-1].is_control
    assert control[0].outcome is cr.ReconcileOutcome.CORROBORATED
    # Every live finding tests a closed_loop / hybrid claim (A2's cohort claims + the Troy-Piqua
    # FAQ's closed_loop_dry claim under test).
    assert live
    assert all(r.claimed_archetype in {"closed_loop_dry", "hybrid_adiabatic"} for r in live)
    # A2's registry-derived cohort facilities resolve to a gap today (no documented water while
    # OHD000001 is draft and no facility-own DMR is on record).
    cohort = [r for r in live if r.site != "troy-piqua"]
    assert cohort
    assert all(r.outcome is cr.ReconcileOutcome.GAP for r in cohort)
    assert "urbana" in {r.site for r in cohort}
    # Troy-Piqua (B1 #1681) pins UNKNOWN so it is NOT in A2's cohort, but its FAQ-vs-reservation
    # conflict is reconciled as an explicit live reservation_conflict — not a gap.
    troy = [r for r in live if r.site == "troy-piqua"]
    assert len(troy) == 1
    assert troy[0].outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert not troy[0].is_control  # a real site, not a constructed control


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


# -------------------------------------------- B1 reservation conflict — Troy-Piqua (#1681)


def test_reservation_ceiling_contradicts_a_dry_claim_without_a_re_archetype() -> None:
    # A disclosed RESERVATION ceiling (a will-serve figure), not a metered use, contradicts the dry
    # claim's ~0 prediction — but a ceiling is not a discharge/withdrawal instrument, so the outcome
    # is a reservation_conflict that KEEPS the pin (no re-archetype), never a discrepancy.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop FAQ claim",
        settings=Settings(),
        reserved_makeup=ProvenancedValue.from_reference(2.0, "MGD", citation="reserved ceiling"),
        reserved_blowdown=ProvenancedValue.from_reference(
            1.0, "MGD", citation="reserved wastewater"
        ),
        water_lead_ref="#1486",
    )
    assert rec.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert rec.outcome is not cr.ReconcileOutcome.DISCREPANCY  # a ceiling is not an instrument
    # Keeps the pin: no re-archetype recommendation, and the conflict stays [open]. With no explicit
    # kept_archetype, it defaults to the facility's own pin (this facility IS closed_loop_dry).
    assert rec.recommended_archetype is None
    assert rec.recommended_source is None
    assert rec.kept_archetype == CoolingModelType.CLOSED_LOOP_DRY.value
    assert rec.tag == "[open]"
    assert rec.confidence == "medium"  # sharper than an empty gap, short of instrument-grade
    # Emits a sharpened C2 lead that references the site's standing water lead (#1486) + the instrument.
    assert rec.lead is not None
    assert "#1486" in rec.lead.epic_ref
    joined = " | ".join(rec.lead.records_sought)
    assert "executed water & wastewater service agreement" in joined
    assert "metered water-service use" in joined
    # The finding is explicit that the reserved figure is a ceiling, not a headline consumptive.
    assert "ceiling" in rec.finding
    assert "NOT a headline consumptive" in rec.finding


def test_reservation_backsolved_coc_is_a_labeled_inference_bracket() -> None:
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        reserved_makeup=ProvenancedValue.from_reference(2.0, "MGD", citation="reserved ceiling"),
        reserved_blowdown=ProvenancedValue.from_reference(
            1.0, "MGD", citation="reserved wastewater"
        ),
    )
    coc = rec.account.backsolved_cycles
    assert coc is not None
    assert coc.source == "derived"  # [inference]
    assert coc.has_range  # a bracket, never a scalar
    assert coc.value == 2.0  # 2.0 / 1.0
    # The citation names the inputs as reservation ceilings, not metered use.
    assert "RESERVATION CEILINGS" in (coc.citation or "")
    assert "not metered use" in (coc.citation or "")


def test_reservation_is_kept_distinct_from_documented_slots() -> None:
    # The reservation ceiling never lands on the documented_* slots — so a will-serve ceiling is
    # never read downstream as a metered withdrawal/discharge.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        reserved_makeup=ProvenancedValue.from_reference(2.0, "MGD", citation="reserved ceiling"),
        reserved_blowdown=ProvenancedValue.from_reference(
            1.0, "MGD", citation="reserved wastewater"
        ),
    )
    a = rec.account
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_makeup is not None and a.reserved_makeup.value == 2.0
    assert a.reserved_blowdown is not None and a.reserved_blowdown.value == 1.0


def test_documented_metered_flow_outranks_a_reservation_ceiling() -> None:
    # A metered documented discharge (an instrument) adjudicates over a reservation ceiling: the
    # outcome is a discrepancy (re-archetype up), NOT a reservation_conflict.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_document(0.5, "MGD", citation="test DMR"),
        reserved_makeup=ProvenancedValue.from_reference(2.0, "MGD", citation="reserved ceiling"),
        reserved_blowdown=ProvenancedValue.from_reference(
            1.0, "MGD", citation="reserved wastewater"
        ),
    )
    assert rec.outcome is cr.ReconcileOutcome.DISCREPANCY
    assert rec.recommended_archetype == CoolingModelType.EVAPORATIVE_TOWER.value
    # A documented signal is present (blowdown, but no documented makeup) — so there is no metered
    # pair to back-solve from, and the harness does NOT fall back to the reservation ceilings on a
    # discrepancy (a discrepancy never carries a reservation-derived CoC).
    assert rec.account.backsolved_cycles is None


def test_zero_reservation_is_a_gap_not_a_conflict() -> None:
    # A reservation that is NOT disproportionate to the dry claim (here ~0) does not corroborate USE
    # (a ceiling is not a measurement) — it falls back to a gap, not a reservation_conflict.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        reserved_makeup=ProvenancedValue.from_reference(0.0, "MGD", citation="reserved ceiling"),
        reserved_blowdown=ProvenancedValue.from_reference(
            0.0, "MGD", citation="reserved wastewater"
        ),
    )
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.confidence == "low"
    assert rec.account.backsolved_cycles is None  # ~0 blowdown → no CoC to back-solve


def test_troy_piqua_b1_reservation_conflict() -> None:
    # The B1 case: the City closed-loop FAQ (a closed_loop_dry CLAIM under test) vs the negotiated
    # Water & Wastewater Agreement's 2.0 MGD makeup + ~1.0 MGD wastewater reservation.
    rec = cr.reconcile_troy_piqua(settings=Settings())
    assert rec.site == "troy-piqua"
    assert rec.facility == "Project Klondike"
    assert rec.is_control is False  # a real registered site, not a constructed control
    # The claim under test is the FAQ's dry framing; the profile itself stays UNKNOWN.
    assert rec.claimed_archetype == "closed_loop_dry"
    assert cr.SITES["troy-piqua"].facilities[0].cooling_model is CoolingModelType.UNKNOWN
    assert rec.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    # Keeps the UNKNOWN pin — no re-archetype — and sharpens lead #1486. The kept pin is the site's
    # REAL profile archetype (UNKNOWN), carried on the record — not the closed_loop_dry claim view.
    assert rec.recommended_archetype is None
    assert rec.kept_archetype == CoolingModelType.UNKNOWN.value
    assert "#1486" in (rec.lead.epic_ref if rec.lead else "")
    # The reserved figures are the ceilings; nothing is collapsed into a documented/consumptive.
    a = rec.account
    assert a.reserved_makeup is not None and a.reserved_makeup.value == 2.0
    assert a.reserved_blowdown is not None and a.reserved_blowdown.value == 1.0
    assert a.documented_makeup is None
    # Back-solved CoC ≈ 2.0 off the ceilings, an [inference] bracket.
    assert a.backsolved_cycles is not None
    assert a.backsolved_cycles.value == 2.0
    assert a.backsolved_cycles.has_range
    # No air permit on file (confirmed-negative PTI) → corroborators are silent (honest).
    assert rec.corroborators is not None
    assert rec.corroborators.net_stance is cr.CorroboratorStance.SILENT


# -------------------------------------------- B2 disclosed-fill gap — Van Wert (#1682)


def test_disclosed_ongoing_draw_sharpens_a_gap_without_upgrading() -> None:
    # A dry claim with an operator-DISCLOSED ongoing draw (a self-report, not a metered instrument)
    # stays a GAP that KEEPS the [reference] pin — the disclosed figure sharpens the lead onto the
    # specific open quantity (the initial fill) but never upgrades the source.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        disclosed_makeup=ProvenancedValue.from_reference(
            0.0018, "MGD", citation="operator self-report ~660k gal/yr"
        ),
        water_lead_ref="#1409",
    )
    assert rec.outcome is cr.ReconcileOutcome.GAP  # a self-report is not a metered instrument
    assert rec.recommended_archetype is None  # kept [reference], no re-archetype
    assert rec.recommended_source is None  # NOT upgraded to 'document'
    assert rec.tag == "[open]"
    assert rec.confidence == "low"
    # The disclosed figure lands on disclosed_makeup, NEVER on documented_* (would read as metered).
    assert rec.account.disclosed_makeup is not None and rec.account.disclosed_makeup.value == 0.0018
    assert rec.account.documented_makeup is None and rec.account.documented_blowdown is None
    # The lead names the specific open quantity (the initial fill) + the site's standing water lead.
    assert rec.lead is not None
    joined = " | ".join(rec.lead.records_sought)
    assert "initial closed-loop fill volume" in joined
    assert "#1409" in rec.lead.epic_ref
    # The finding is explicit: consistent-with-dry but self-reported, pin stays [reference].
    assert "self-report" in rec.finding
    assert "cannot upgrade the [reference] pin" in rec.finding


def test_disclosed_near_zero_draw_does_not_corroborate_the_dry_claim() -> None:
    # The circularity guard: a self-reported ~0 ongoing draw must NOT be read as "corroborated dry"
    # (which would upgrade source reference→document) — corroborating the operator's claim with the
    # operator's own self-report is circular. It stays a GAP; the [reference] pin is kept.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        disclosed_makeup=ProvenancedValue.from_reference(0.0018, "MGD", citation="self-report ~0"),
    )
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.outcome is not cr.ReconcileOutcome.CORROBORATED  # never a self-corroboration
    assert rec.recommended_source is None  # NOT upgraded to 'document'
    # No blowdown pair to back-solve from; the disclosed figure never seeds a CoC either.
    assert rec.account.backsolved_cycles is None


def test_high_disclosed_draw_stays_unclassified_without_a_dry_loop_conclusion() -> None:
    # A LARGE disclosed self-report (well above the ~0 screening floor) must NOT produce a
    # "consistent with a dry loop" conclusion — the consistency wording is conditioned on a
    # non-classifying screening comparison. It stays an unclassified GAP either way (a self-report is
    # not a metered instrument, so it never corroborates or re-archetypes), pin kept [reference].
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        disclosed_makeup=ProvenancedValue.from_reference(
            5.0, "MGD", citation="large operator self-report"
        ),
        water_lead_ref="#1409",
    )
    assert (
        rec.outcome is cr.ReconcileOutcome.GAP
    )  # unclassified — never classified off a self-report
    assert rec.recommended_archetype is None  # not re-archetyped
    assert rec.recommended_source is None  # not upgraded to 'document'
    # The finding does NOT claim the loop is dry, and flags the draw as above the screening floor.
    assert "consistent with a dry loop" not in rec.finding
    assert "above the ~0 screening floor" in rec.finding
    assert "UNVERIFIED" in rec.finding
    # The same neutral wording flows into the sharpened gap lead's rationale.
    assert rec.lead is not None
    assert "consistent with a dry loop" not in rec.lead.rationale
    assert "above the ~0 screening floor" in rec.lead.rationale
    # The disclosed figure is still recorded (on disclosed_makeup, not documented_*).
    assert rec.account.disclosed_makeup is not None and rec.account.disclosed_makeup.value == 5.0
    assert rec.account.documented_makeup is None


def test_disclosed_makeup_is_kept_distinct_from_documented_and_reserved_slots() -> None:
    # A disclosed self-report never lands on documented_* (metered) or reserved_* (ceiling) — the
    # three provenance categories stay distinct so a self-report is never read as either downstream.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        disclosed_makeup=ProvenancedValue.from_reference(0.0018, "MGD", citation="self-report"),
    )
    a = rec.account
    assert a.disclosed_makeup is not None and a.disclosed_makeup.value == 0.0018
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_makeup is None and a.reserved_blowdown is None


def test_van_wert_b2_disclosed_fill_gap() -> None:
    # The B2 case: QTS's closed_loop_dry "does not consume water once operational" claim vs the record.
    # It IS in A2's cohort (pins closed_loop_dry) but is reconciled explicitly so its disclosed ~660k
    # gal figure is recorded and the #1409 initial-fill open quantity sharpens the gap.
    rec = cr.reconcile_van_wert(settings=Settings())
    assert rec.site == "van-wert"
    assert rec.facility == "Van Wert Mega Site"
    assert rec.is_control is False  # a real registered site, not a constructed control
    assert rec.claimed_archetype == "closed_loop_dry"
    assert rec.claim_source == "reference"
    # No A1 withdrawal (Van Wert County not built) + no A2 blowdown (OHD000001 draft) → an [open] gap
    # that KEEPS the [reference] pin — never silently promoted (the issue's acceptance).
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.recommended_archetype is None
    assert rec.recommended_source is None
    assert rec.tag == "[open]"
    # The disclosed ~660k gal ongoing draw (≈0.0018 MGD) is recorded as a self-report, not metered.
    a = rec.account
    assert a.disclosed_makeup is not None and a.disclosed_makeup.value == 0.0018
    assert a.disclosed_makeup.source == "reference"  # a self-report, never 'document'
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_makeup is None and a.reserved_blowdown is None
    assert a.backsolved_cycles is None  # no blowdown pair to back-solve a CoC from
    # The gap lead is sharpened onto the initial-fill open quantity + references #1409.
    assert rec.lead is not None
    assert "#1409" in rec.lead.epic_ref
    assert rec.lead.records_sought[0].startswith("initial closed-loop fill volume")
    # The finding keeps the pin [reference] and names the fill as the open quantity.
    assert "not 'confirmed dry'" in rec.finding
    assert "initial closed-loop fill" in rec.finding
    assert "cannot upgrade the [reference] pin" in rec.finding
    # No air permit / Tier II on file → corroborators silent (honest), and the pin is untouched.
    assert rec.corroborators is not None
    assert rec.corroborators.net_stance is cr.CorroboratorStance.SILENT
    assert cr.SITES["van-wert"].facilities[0].cooling_model is CoolingModelType.CLOSED_LOOP_DRY


def test_cohort_includes_van_wert_b2_disclosed_gap_exactly_once() -> None:
    # Van Wert IS in A2's cohort but is reconciled explicitly (skipped in the generic loop) — so it
    # appears exactly once, as a disclosed gap, not twice.
    records = cr.reconcile_cohort(settings=Settings())
    vw = [r for r in records if r.site == "van-wert"]
    assert len(vw) == 1
    assert vw[0].outcome is cr.ReconcileOutcome.GAP
    assert vw[0].account.disclosed_makeup is not None
    assert vw[0].is_control is False


# --------------------------------------------------------------------- A4 corroborators (#1680)


def _contradicting_corroborators() -> cr.CoolingCorroborators:
    """A constructed corroborator set whose air-permit signal CONTRADICTS a dry claim."""
    return cr.CoolingCorroborators(
        air_permit=cr.AirPermitCorroborator(
            state=cr.AirPermitState.PM_SOURCE_LISTED,
            stance=cr.CorroboratorStance.CONTRADICTS,
            tower_count=36,
            citation="test permit lists cooling towers as PM sources",
            tag="[verified]",
            confidence="high",
            finding="Air permit lists 36 cooling towers as PM sources — contradicts the dry claim.",
        ),
        tier2_chemistry=cr.TierIIChemistryCorroborator(
            state=cr.TierIIState.NOT_ON_RECORD,
            stance=cr.CorroboratorStance.SILENT,
            citation="not on record",
            tag="[open]",
            confidence="low",
            finding="Tier II not on record.",
        ),
        net_stance=cr.CorroboratorStance.CONTRADICTS,
        summary="Independent corroborators contradict the closed_loop_dry claim.",
    )


def test_corroborators_never_change_the_primary_outcome() -> None:
    # A gap (no documented water) with a CONTRADICTING air-permit corroborator stays a GAP — the
    # corroborators are secondary and never the sole basis for a re-archetype (the epic's rule).
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        corroborators=_contradicting_corroborators(),
    )
    assert rec.outcome is cr.ReconcileOutcome.GAP  # unchanged by the contradicting corroborator
    assert rec.recommended_archetype is None  # still a records request, not a re-archetype
    # But the contradiction is surfaced in the finding (its evidentiary value is not discarded).
    assert rec.corroborators is not None
    assert rec.corroborators.net_stance is cr.CorroboratorStance.CONTRADICTS
    assert "contradict" in rec.finding


def test_gap_lead_absorbs_not_on_record_corroborator_asks() -> None:
    # When the corroborators are themselves not-on-record, the gap's C2 records request gains the
    # air-permit (PTI/PTIO) and Tier II asks so C2 pulls them alongside the water records.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        corroborators=cr.resolve_corroborators(_dry_facility(), settings=Settings()),
    )
    assert rec.lead is not None
    joined = " | ".join(rec.lead.records_sought)
    assert "air permit (PTI/PTIO)" in joined
    assert "Tier II / EPCRA-312" in joined
    assert "LEPC" in rec.lead.holder


def test_intel_control_corroborators_are_both_positive() -> None:
    rec = cr.intel_control(settings=Settings())
    assert rec.corroborators is not None
    assert rec.corroborators.air_permit.stance is cr.CorroboratorStance.CORROBORATES
    assert rec.corroborators.tier2_chemistry.stance is cr.CorroboratorStance.CORROBORATES
    assert rec.corroborators.net_stance is cr.CorroboratorStance.CORROBORATES


def test_cohort_every_record_carries_resolved_corroborators() -> None:
    records = cr.reconcile_cohort(settings=Settings())
    assert all(r.corroborators is not None for r in records)
    # The live cohort has no air permit / Tier II on file today → silent corroborators (honest).
    live = [r for r in records if not r.is_control]
    assert all(r.corroborators.net_stance is cr.CorroboratorStance.SILENT for r in live)


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
    # Every committed row carries the A4 corroborators block (#1680); the control's are positive.
    assert all(c.get("corroborators") is not None for c in doc["candidates"])
    assert control[0]["corroborators"]["net_stance"] == "corroborates"
