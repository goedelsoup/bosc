"""Cooling-cycling reconciliation harness (#1679, A3 of the closed-loop epic #1676).

Hermetic: the harness reads the site registry, the cited OHD000001 permit-lifecycle constant,
and the archetype math — no network, no fixture. The properties under test are the classifier's
five outcomes (discrepancy / corroborated / reservation_conflict / route_blind / gap), the
Troy-Piqua B1 reservation conflict (#1681), the Intel positive control's no-false-positive
guarantee, its B6 (#1686) counterpart — that a ~0 from an instrument which cannot REACH a
facility never corroborates a claim, while a positive signal still adjudicates — the back-solved
CoC being an [inference] bracket (never a scalar), and that the committed artifact validates +
matches the resolver.
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
    # Every live finding EXCEPT New Albany tests a closed_loop / hybrid claim (A2's cohort claims
    # + the Troy-Piqua FAQ's closed_loop_dry claim under test). New Albany (B6, #1686) is the one
    # live row whose claim is openly WET — Intel's 125 permitted cooling towers — and it is in the
    # cohort precisely because an honest evaporative disclosure still could not be reconciled.
    assert live
    claim_cohort = [r for r in live if r.site != "new-albany"]
    assert all(r.claimed_archetype in {"closed_loop_dry", "hybrid_adiabatic"} for r in claim_cohort)
    # A2's registry-derived cohort facilities resolve to a gap today: no facility-own DMR is on
    # record, and OHD000001 — which would have been the other route to one — was withdrawn rather
    # than finalized (2026-07-21), so no general-permit coverage will ever appear either. Two
    # exceptions, and they fail to be gaps for different reasons. Bowling Green (B5, #1685) has an
    # independently-sourced reservation ceiling — a quantified figure of its own — so it is a
    # reservation_conflict. Urbana (B4, #1684) has no figure at all, but its ROUTE to the City's
    # water and sewer is itself on the record, so its absence of documents is a blind instrument
    # rather than an unfinished lookup.
    cohort = [
        r for r in live if r.site not in {"troy-piqua", "new-albany", "bowling-green", "urbana"}
    ]
    assert cohort
    assert all(r.outcome is cr.ReconcileOutcome.GAP for r in cohort)
    urbana = [r for r in live if r.site == "urbana"]
    assert len(urbana) == 1
    assert urbana[0].outcome is cr.ReconcileOutcome.ROUTE_BLIND
    # Troy-Piqua (B1 #1681) pins UNKNOWN so it is NOT in A2's cohort, but its FAQ-vs-reservation
    # conflict is reconciled as an explicit live reservation_conflict — not a gap.
    troy = [r for r in live if r.site == "troy-piqua"]
    assert len(troy) == 1
    assert troy[0].outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert not troy[0].is_control  # a real site, not a constructed control
    # New Albany (B6, #1686) pins no SiteFacility at all, so it is in no cohort either; Intel's
    # real record is reconciled explicitly and lands route_blind. It is a LIVE row — the
    # constructed control is the separate is_control row above.
    new_albany = [r for r in live if r.site == "new-albany"]
    assert len(new_albany) == 1
    assert new_albany[0].outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert not new_albany[0].is_control


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


# -------------------------------------------- B3 disclosed-ceiling gap — Springfield (#1683)


def test_disclosed_permit_ceiling_does_not_fire_a_reservation_conflict() -> None:
    # The pivotal B3 call: a self-disclosed permit CEILING (the claim's own source discloses a
    # permitted-withdrawal max) is NOT a reservation_conflict — unlike B1's independently-negotiated
    # reservation, a permitted peak ceiling from the claim's own source is not a demand signal that
    # contradicts the dry claim (a dry loop sits far below it). It stays a GAP, [reference] pin KEPT.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim, 'not evaporative'",
        settings=Settings(),
        disclosed_ceiling=ProvenancedValue.from_reference(
            0.3, "MGD", citation="self-disclosed 300k gal/day permitted peak ceiling"
        ),
        water_lead_ref="#1415",
    )
    # 0.3 MGD is well above the ~0 floor and the dry claim predicts ~0 — a *reserved* figure of that
    # size WOULD be a reservation_conflict (see the B1 tests), but a *disclosed* ceiling must not.
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.outcome is not cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert rec.recommended_archetype is None  # never re-archetyped
    assert rec.recommended_source is None  # NOT upgraded to 'document'
    assert rec.kept_archetype is None  # a gap, not a reservation_conflict keep-the-pin
    assert rec.tag == "[open]"


def test_disclosed_ceiling_lands_on_its_own_slot_never_documented_or_reserved() -> None:
    # A self-disclosed ceiling never lands on documented_* (metered) or reserved_* (a negotiated
    # reservation) — the provenance categories stay distinct so it is never read as either downstream.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        disclosed_ceiling=ProvenancedValue.from_reference(0.3, "MGD", citation="permit ceiling"),
    )
    a = rec.account
    assert a.disclosed_ceiling is not None and a.disclosed_ceiling.value == 0.3
    assert a.disclosed_ceiling.source == "reference"  # a self-report, never 'document'
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_makeup is None and a.reserved_blowdown is None
    # It never seeds a back-solved CoC either (no metered/reservation pair to divide).
    assert a.backsolved_cycles is None


def test_disclosed_ceiling_gap_lead_names_the_actual_vs_ceiling_denominator() -> None:
    # The sharpened gap lead names the missing measurement — the actual metered withdrawal against the
    # disclosed ceiling — and references the site's standing water lead, not the generic gap ask.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="x",
        settings=Settings(),
        disclosed_ceiling=ProvenancedValue.from_reference(0.3, "MGD", citation="permit ceiling"),
        water_lead_ref="#1415",
    )
    assert rec.lead is not None
    joined = " | ".join(rec.lead.records_sought)
    assert "actual municipal withdrawal vs the disclosed permitted ceiling" in joined
    assert "#1415" in rec.lead.epic_ref
    # The finding is explicit that a self-disclosed ceiling is not a reservation conflict and cannot
    # corroborate the claim (circular), and keeps the pin [reference].
    assert "not a reservation conflict" in rec.finding.lower()
    assert "Keep the pin [reference]" in rec.finding


def test_reconcile_springfield_b3_disclosed_ceiling_gap() -> None:
    # The B3 case: Springfield's closed_loop_dry "not evaporative" claim vs the record. It IS in A2's
    # cohort (pins closed_loop_dry) but is reconciled explicitly so the FAQ's self-disclosed 300k
    # gal/day permitted ceiling + the ~30k gal/day realistic draw are recorded and #1415 sharpens the gap.
    rec = cr.reconcile_springfield(settings=Settings())
    assert rec.site == "springfield"
    assert rec.facility == '5C Data Centers "CMH01"'
    assert rec.is_control is False  # a real registered site, not a constructed control
    assert rec.claimed_archetype == "closed_loop_dry"
    assert rec.claim_source == "reference"
    # No A1 withdrawal (Clark County not built) + no A2 blowdown (OHD000001 draft) → an [open] gap that
    # KEEPS the [reference] pin — never silently promoted, and NOT a reservation_conflict (the B3 call).
    assert rec.outcome is cr.ReconcileOutcome.GAP
    assert rec.recommended_archetype is None
    assert rec.recommended_source is None
    assert rec.tag == "[open]"
    # Both self-reported figures are recorded — the permitted ceiling (0.3 MGD) + the realistic draw
    # (0.03 MGD) — on the disclosed_* slots, never on documented_* (metered) or reserved_* (negotiated).
    a = rec.account
    assert a.disclosed_ceiling is not None and a.disclosed_ceiling.value == 0.3
    assert a.disclosed_makeup is not None and a.disclosed_makeup.value == 0.03
    assert a.disclosed_ceiling.source == "reference" and a.disclosed_makeup.source == "reference"
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_makeup is None and a.reserved_blowdown is None
    # The gap lead is sharpened onto the actual-vs-ceiling denominator + references #1415.
    assert rec.lead is not None
    assert "#1415" in rec.lead.epic_ref
    assert "not evaporative" in rec.lead.subject
    # The finding names the ceiling as a self-report that keeps the pin [reference] and is not a conflict.
    assert "not 'confirmed dry'" in rec.finding
    assert "300,000 gal/day" in rec.finding
    assert "Keep the pin [reference]" in rec.finding
    # The profile pin is untouched (the harness recommends, it does not mutate).
    springfield_fac = next(
        f for f in cr.SITES["springfield"].facilities if f.name == '5C Data Centers "CMH01"'
    )
    assert springfield_fac.cooling_model is CoolingModelType.CLOSED_LOOP_DRY


def test_cohort_includes_springfield_b3_disclosed_ceiling_gap_exactly_once() -> None:
    # Springfield IS in A2's cohort but is reconciled explicitly (skipped in the generic loop) — so it
    # appears exactly once, as a disclosed-ceiling gap, not twice, and never as a reservation_conflict.
    records = cr.reconcile_cohort(settings=Settings())
    sp = [r for r in records if r.site == "springfield"]
    assert len(sp) == 1
    assert sp[0].outcome is cr.ReconcileOutcome.GAP
    assert sp[0].account.disclosed_ceiling is not None
    assert sp[0].is_control is False


# ------------------------------------- B6 route-blind — New Albany / Intel (#1686)


def _municipal_route() -> cr.WaterRoute:
    """Both sides outside the instruments: purchased supply, sewer discharge."""
    return cr.WaterRoute(
        supply=cr.SupplyRoute.MUNICIPAL,
        discharge=cr.DischargeRoute.SANITARY_SEWER,
        citation="test: purchased municipal makeup + POTW sanitary sewer",
        tag="[verified]",
        confidence="high",
    )


def test_a_blind_instruments_zero_never_corroborates_a_dry_claim() -> None:
    # THE B6 calibration gate, inverted from what the issue expected. Without a route, a dry
    # claim with documented ~0 corroborates and recommends the reference → document upgrade.
    # That is the false NEGATIVE the New Albany positive control found: for a municipally
    # supplied, sewer-discharging campus, A1 and A2 return ~0 by construction.
    zero = ProvenancedValue.from_reference(0.0, "MGD", citation="test: registry reports ~0")
    without_route = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        documented_makeup=zero,
    )
    assert without_route.outcome is cr.ReconcileOutcome.CORROBORATED
    assert without_route.recommended_source == "document"  # the upgrade the guard must prevent

    with_route = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        documented_makeup=zero,
        route=_municipal_route(),
    )
    assert with_route.outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert with_route.recommended_archetype is None
    assert with_route.recommended_source is None  # never upgraded on an absence of jurisdiction
    assert with_route.kept_archetype == "closed_loop_dry"


def test_a_blind_route_turns_a_bare_gap_into_route_blind() -> None:
    # A gap says "pull the water records"; for a blind route that instruction is wrong — the
    # records were pulled and answer ~0 for a reason unrelated to cooling. The lead must be
    # re-aimed at the City-held meter rather than at more of A1/A2.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        route=_municipal_route(),
    )
    assert rec.outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert rec.lead is not None
    sought = " ".join(rec.lead.records_sought).lower()
    assert "metered municipal water-service consumption" in sought
    assert "pretreatment" in sought
    assert rec.lead.tag == "[open]"


def test_blindness_never_suppresses_a_positive_signal() -> None:
    # The guard invalidates a NEGATIVE read only. A documented flow contradicting a dry claim is
    # still a discrepancy, and a reservation ceiling is still a reservation_conflict — a positive
    # signal from any instrument says something true regardless of what the blind side would have.
    discrepancy = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        documented_blowdown=ProvenancedValue.from_reference(
            0.4, "MGD", citation="test: metered blowdown DMR"
        ),
        route=_municipal_route(),
    )
    assert discrepancy.outcome is cr.ReconcileOutcome.DISCREPANCY

    conflict = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        reserved_makeup=ProvenancedValue.from_reference(
            2.0, "MGD", citation="test: negotiated reservation ceiling"
        ),
        route=_municipal_route(),
    )
    assert conflict.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT


def test_a_wet_claim_corroborated_by_real_water_survives_the_guard() -> None:
    # The Intel control's property, under a blind route: documented water that MATCHES a wet
    # claim is a positive read and must stay corroborated — the guard must not sweep it up.
    rec = cr.reconcile_facility(
        _evap_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] disclosed evaporative towers",
        settings=Settings(),
        documented_makeup=ProvenancedValue.from_reference(
            2.2, "MGD", citation="test: metered withdrawal"
        ),
        route=_municipal_route(),
    )
    assert rec.outcome is cr.ReconcileOutcome.CORROBORATED


def test_a_blind_zero_cannot_corroborate_a_wet_claim_either() -> None:
    # The subtler half of the guard. A wet claim predicts ~0.43 MGD blowdown, so a documented
    # blowdown of ~0 lands BELOW the corroboration band — and "below the band" is deliberately
    # read as corroborating (the record does not refute a lower-water reality). Under a blind
    # route that reasoning fails: the ~0 came from an instrument with no view of the facility.
    zero_blowdown = ProvenancedValue.from_reference(
        0.0, "MGD", citation="test: no DMR flow on record"
    )
    without_route = cr.reconcile_facility(
        _evap_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] disclosed evaporative towers",
        settings=Settings(),
        documented_blowdown=zero_blowdown,
    )
    assert without_route.outcome is cr.ReconcileOutcome.CORROBORATED  # the unguarded read

    with_route = cr.reconcile_facility(
        _evap_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] disclosed evaporative towers",
        settings=Settings(),
        documented_blowdown=zero_blowdown,
        route=_municipal_route(),
    )
    assert with_route.outcome is cr.ReconcileOutcome.ROUTE_BLIND


def test_a_refused_prediction_leaves_the_whole_predicted_side_unset() -> None:
    # Every archetype is IT-load-parameterized, so a facility with no IT load has no derivable
    # account. The refusal is total and cited — a partially-refused account would read as a zero.
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        prediction_refused="test: no IT load — a fab is not IT-load-parameterized",
        route=_municipal_route(),
    )
    a = rec.account
    assert a.predicted_makeup is None
    assert a.predicted_consumptive is None
    assert a.predicted_blowdown is None
    assert a.it_load is None
    assert a.prediction_refused
    assert rec.outcome is cr.ReconcileOutcome.ROUTE_BLIND


def test_a_half_refused_account_is_rejected() -> None:
    # The validator that stops a renderer reading a missing archetype figure as a real zero.
    value = ProvenancedValue.from_reference(1.0, "MGD", citation="test")
    with pytest.raises(ValueError, match="move together"):
        cr.WaterAccount(
            archetype=CoolingModelType.EVAPORATIVE_TOWER,
            predicted_makeup=value,
            predicted_consumptive=None,
            predicted_blowdown=None,
            prediction_refused="test",
        )
    with pytest.raises(ValueError, match="never a silent omission"):
        cr.WaterAccount(archetype=CoolingModelType.EVAPORATIVE_TOWER)


def test_intel_new_albany_is_route_blind_and_not_a_control() -> None:
    rec = cr.reconcile_intel_new_albany(settings=Settings())
    assert rec.site == "new-albany"
    assert not rec.is_control  # a real site's real record — the constructed vector is separate
    assert rec.outcome is cr.ReconcileOutcome.ROUTE_BLIND
    # The claim under test is openly WET — 125 permitted cooling towers — and it still cannot be
    # reconciled. That is the finding.
    assert rec.claimed_archetype == "evaporative_tower"
    assert rec.kept_archetype == "evaporative_tower"
    assert rec.recommended_source is None
    route = rec.account.route
    assert route is not None
    assert route.supply is cr.SupplyRoute.MUNICIPAL
    assert route.discharge is cr.DischargeRoute.SANITARY_SEWER
    assert route.instruments_blind
    assert len(route.blind_sides) == 2  # both sides, not one


def test_intels_construction_water_never_lands_on_documented_makeup() -> None:
    # The registry DOES report a non-zero withdrawal for Intel; recording it as documented makeup
    # would make a construction-dewatering figure the campus's cooling account.
    rec = cr.reconcile_intel_new_albany(settings=Settings())
    a = rec.account
    assert a.documented_makeup is None
    assert a.documented_blowdown is None
    assert a.nonprocess_makeup is not None
    assert a.nonprocess_makeup.value == 0.0435
    # The disclosed ~5 MGD operating projection is a self-report on its own slot, as in B2/B3.
    assert a.disclosed_makeup is not None
    assert a.disclosed_makeup.value == 5.0
    assert a.backsolved_cycles is None  # no metered pair to back-solve from


def test_intel_prediction_is_refused_because_a_fab_has_no_it_load() -> None:
    rec = cr.reconcile_intel_new_albany(settings=Settings())
    refused = rec.account.prediction_refused
    assert refused is not None
    assert "not a data center" in refused
    assert "IT load" in refused
    assert rec.account.predicted_makeup is None


# --------------------------------------------------------------------- the reference band (#1686)


def test_reference_band_is_archetype_derived_and_internally_consistent() -> None:
    band = cr.reference_band(settings=Settings())
    assert band.tag == "[inference]"
    # makeup = consumptive + blowdown, and CoC = makeup / blowdown — the archetype's own identity.
    assert band.makeup_mgd_per_mw == pytest.approx(
        band.consumptive_mgd_per_mw + band.blowdown_mgd_per_mw, rel=1e-3
    )
    assert band.makeup_mgd_per_mw / band.blowdown_mgd_per_mw == pytest.approx(
        band.cycles_of_concentration, rel=1e-2
    )


def test_reference_band_says_out_loud_it_is_not_intel_derived() -> None:
    # The issue asked for a band read off the disclosed positive control. Intel is a fab, so a
    # makeup-per-MW figure taken from it and applied to a hyperscale campus is a category error —
    # the artifact has to carry that refusal, not just omit the number quietly.
    band = cr.reference_band(settings=Settings())
    assert "NOT derived from the Intel positive control" in band.not_derived_from
    assert "semiconductor fab" in band.not_derived_from
    intel = cr.reconcile_intel_new_albany(settings=Settings())
    disclosed = intel.account.disclosed_makeup
    assert disclosed is not None
    assert band.makeup_mgd_per_mw != disclosed.value  # nothing quietly divided Intel's 5 MGD


# ------------------------------------------------- B4 the Urbana origin claim (#1684)


def test_supplier_withdrawal_requires_a_cited_municipal_route() -> None:
    # The slot only has a referent under a municipal supply: off that route a system total parked
    # next to a facility that does not buy from it is the category error the slot exists to avoid,
    # and a self-supplied facility's own withdrawal belongs on documented_makeup.
    supplier = ProvenancedValue.from_reference(1.76, "MGD", citation="test: city system total")
    with pytest.raises(ValueError, match="cited municipal supply route"):
        cr.reconcile_facility(
            _dry_facility(),
            site="test-site",
            claim_source="reference",
            claim_citation="[reference] closed-loop claim",
            settings=Settings(),
            supplier_withdrawal=supplier,
        )
    with pytest.raises(ValueError, match="cited municipal supply route"):
        cr.reconcile_facility(
            _dry_facility(),
            site="test-site",
            claim_source="reference",
            claim_citation="[reference] closed-loop claim",
            settings=Settings(),
            supplier_withdrawal=supplier,
            route=cr.WaterRoute(
                supply=cr.SupplyRoute.SELF_SUPPLIED,
                discharge=cr.DischargeRoute.SANITARY_SEWER,
                citation="test: own wells",
                tag="[verified]",
                confidence="high",
            ),
        )


def test_a_suppliers_withdrawal_never_feeds_the_classifier() -> None:
    # A system total aggregates every customer on it, so however large it is it can never make one
    # facility's dry claim a discrepancy. The row stays route_blind and no re-archetype is offered.
    huge = ProvenancedValue.from_reference(
        50.0, "MGD", citation="test: the city withdraws a great deal for everyone else"
    )
    rec = cr.reconcile_facility(
        _dry_facility(),
        site="test-site",
        claim_source="reference",
        claim_citation="[reference] closed-loop claim",
        settings=Settings(),
        supplier_withdrawal=huge,
        route=_municipal_route(),
    )
    assert rec.outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert rec.recommended_archetype is None
    assert rec.account.documented_makeup is None  # never folded into the metered register
    assert rec.account.supplier_withdrawal is not None


def test_reconcile_urbana_b4_route_blind_origin_claim() -> None:
    # The B4 case: the campus whose "water use comparable to a standard office building" is where
    # the closed-loop framing entered the network (#1327). It IS in A2's cohort (pins
    # closed_loop_dry) but is reconciled explicitly so its cited municipal route and its supplier's
    # withdrawal are carried — which is what makes it route_blind rather than a bare gap.
    rec = cr.reconcile_urbana(settings=Settings())
    assert rec.site == "urbana"
    assert rec.facility == "Urbana Technology Hub"
    assert rec.is_control is False
    assert rec.claimed_archetype == "closed_loop_dry"
    assert rec.claim_source == "reference"
    assert rec.outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert rec.recommended_archetype is None  # the instruments never reached it; nothing to say
    assert rec.kept_archetype == "closed_loop_dry"  # the pin is KEPT, never promoted
    a = rec.account
    assert a.route is not None
    assert a.route.supply is cr.SupplyRoute.MUNICIPAL
    assert a.route.discharge is cr.DischargeRoute.SANITARY_SEWER
    assert a.route.tag == "[verified]"
    # The route is established on the CITY'S OWN instruments, not on press.
    assert "4612-24" in a.route.citation and "provide water and sewer" in a.route.citation
    assert "1PD00011" in a.route.citation  # the POTW that would receive any blowdown
    # The claim is a COMPARISON, not a figure — so nothing lands on the self-report slots.
    assert a.disclosed_makeup is None
    assert a.disclosed_ceiling is None
    assert a.reserved_makeup is None and a.reserved_blowdown is None
    assert a.documented_makeup is None and a.documented_blowdown is None
    # What IS on record is the supplier's own withdrawal — its own register, its own citation.
    assert a.supplier_withdrawal is not None
    assert a.supplier_withdrawal.value == pytest.approx(1.7623)
    assert "SUPPLIER'S account, not the facility's" in a.supplier_withdrawal.citation
    # The ask is re-aimed at the holder that actually meters it — here the site's OWN city, on
    # both sides (contrast New Albany, where the meter belongs to Columbus).
    assert rec.lead is not None
    assert "City of Urbana" in rec.lead.holder
    assert "Industrial Pretreatment" in rec.lead.holder
    assert any("capacity / supply-adequacy analysis" in r for r in rec.lead.records_sought)
    # The durable pointer is the leads-board id, not just the issue that closes on merge.
    assert "URB-WATER-METER" in rec.lead.epic_ref
    # The profile pin is untouched — the harness recommends, it never mutates.
    urbana_fac = next(f for f in cr.SITES["urbana"].facilities if f.name == "Urbana Technology Hub")
    assert urbana_fac.cooling_model is CoolingModelType.CLOSED_LOOP_DRY


def test_cohort_includes_urbana_b4_route_blind_exactly_once() -> None:
    # Urbana IS in A2's cohort but is reconciled explicitly (skipped in the generic loop) — so it
    # appears exactly once, as a route_blind, not twice and never as a plain gap.
    records = cr.reconcile_cohort(settings=Settings())
    urbana = [r for r in records if r.site == "urbana"]
    assert len(urbana) == 1
    assert urbana[0].outcome is cr.ReconcileOutcome.ROUTE_BLIND
    assert urbana[0].account.supplier_withdrawal is not None
    assert urbana[0].is_control is False


def test_urbanas_denominator_reconciles_with_the_registry_and_the_band() -> None:
    """The B4 measurement is arithmetic over committed inputs — pin it so it can't drift.

    The supplier figure is the City's own WWFRP annual total annualized, and the comparison the
    citation states is that total against the evaporative reference band run at the campus's
    committed screening IT-load bracket. Both sides move if their sources move; this recomputes
    them from those sources so a stale hand-written figure fails here instead of shipping.
    """
    registry = yaml.safe_load(
        (
            Path(__file__).resolve().parent.parent
            / "data/reference/ohio-water-withdrawal/champaign.yaml"
        ).read_text(encoding="utf-8")
    )
    pws = next(f for f in registry["facilities"] if f["registration_number"] == "00837")
    total_2024 = next(y["total_mg"] for y in pws["ground_water"] if y["year"] == 2024)
    assert total_2024 == 644.99
    annualized = total_2024 / 366  # 2024 is a leap year
    rec = cr.reconcile_urbana(settings=Settings())
    supplier = rec.account.supplier_withdrawal
    assert supplier is not None
    assert supplier.value == pytest.approx(annualized, abs=5e-5)
    assert "644.99 MG" in supplier.citation

    # The campus is ABSENT from the same registry — the searched absence the route rests on.
    names = " ".join(f["name"].upper() for f in registry["facilities"])
    for token in ("THOR", "HIGHLAND", "TECHNOLOGY HUB", "DATA CENTER"):
        assert token not in names

    # The counterfactual: the evaporative band at the profile's own screening bracket.
    band = cr.reference_band(settings=Settings())
    fac = next(f for f in cr.SITES["urbana"].facilities if f.name == "Urbana Technology Hub")
    assert fac.it_load_low_mw is not None and fac.it_load_high_mw is not None
    low = fac.it_load_low_mw * band.makeup_mgd_per_mw
    high = fac.it_load_high_mw * band.makeup_mgd_per_mw
    assert round(low, 2) == 0.49 and round(high, 2) == 1.64
    assert "0.49 / 1.07 / 1.64 MGD" in supplier.citation
    assert f"{round(100 * low / annualized)}%" == "28%"
    assert f"{round(100 * high / annualized)}%" == "93%"
    assert "28% / 61% / 93%" in supplier.citation
    # And the claim's own reading is below the harness's own noise floor — the whole point.
    assert cr._MEANINGFUL_FLOW_MGD == 0.01
    assert "0.01 MGD noise floor" in supplier.citation


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
    # The live closed-loop cohort has no air permit / Tier II on file today → silent corroborators
    # (honest). New Albany is the exception and the demonstration: Intel's own air PTI lists 125
    # cooling towers, so its corroborator CORROBORATES the evaporative claim — and the outcome is
    # still route_blind, because a corroborator never changes it (the A4 discipline, #1680).
    live = [r for r in records if not r.is_control and r.site != "new-albany"]
    assert all(r.corroborators.net_stance is cr.CorroboratorStance.SILENT for r in live)
    intel = next(r for r in records if r.site == "new-albany" and not r.is_control)
    assert intel.corroborators is not None
    assert intel.corroborators.net_stance is cr.CorroboratorStance.CORROBORATES
    assert intel.outcome is cr.ReconcileOutcome.ROUTE_BLIND


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
    # B6 (#1686): the documented New Albany row rides alongside the constructed control, and the
    # meta carries the archetype-derived reference band with its not-Intel-derived refusal.
    live_new_albany = [
        c for c in doc["candidates"] if c["site"] == "new-albany" and not c["is_control"]
    ]
    assert len(live_new_albany) == 1
    assert live_new_albany[0]["outcome"] == "route_blind"
    assert live_new_albany[0]["account"]["predicted_makeup"] is None
    assert live_new_albany[0]["account"]["nonprocess_makeup"]["value"] == 0.0435
    band = doc["meta"]["reference_band"]
    assert band["tag"] == "[inference]"
    assert "NOT derived from the Intel positive control" in band["not_derived_from"]
    # Every committed row carries the A4 corroborators block (#1680); the control's are positive.
    assert all(c.get("corroborators") is not None for c in doc["candidates"])
    assert control[0]["corroborators"]["net_stance"] == "corroborates"


# ------------------------- B5 dry-cooler reservation conflict — Bowling Green (#1685)


def test_reconcile_bowling_green_b5_dry_cooler_reservation_conflict() -> None:
    # The B5 case: Meta's "closed-loop, liquid-cooled with dry coolers / no operational water" claim
    # against the record. Bowling Green IS in A2's cohort (pins closed_loop_dry) but is reconciled
    # explicitly so its two conflicting figures land on the slots their PROVENANCE earns.
    rec = cr.reconcile_bowling_green(settings=Settings())
    assert rec.site == "bowling-green"
    assert rec.facility == "Bowling Green Data Center (Project Accordion)"
    assert rec.is_control is False  # a real registered site, not a constructed control
    assert rec.claimed_archetype == "closed_loop_dry"
    assert rec.claim_source == "reference"
    # The district-linked ~600k gpd reservation is disproportionate to a ~0 dry prediction.
    assert rec.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    # A ceiling cannot license a re-archetype — the pin is KEPT, nothing recommended.
    assert rec.recommended_archetype is None
    assert rec.recommended_source is None
    assert rec.kept_archetype == "closed_loop_dry"
    assert rec.tag == "[open]"


def test_bowling_greens_two_figures_split_by_provenance_not_by_size() -> None:
    # The pivotal B5 evidentiary call. The ~600k gpd is INDEPENDENT of the claim's source (it is the
    # water district's service obligation), so it is a reservation and DOES classify. Meta's own ~50k
    # gpd is a self-report from the very source under test, so it lands on disclosed_makeup and never
    # classifies — exactly B2's rule. Neither is metered, so documented_* stays empty.
    a = cr.reconcile_bowling_green(settings=Settings()).account
    assert a.reserved_makeup is not None and a.reserved_makeup.value == 0.6
    assert a.disclosed_makeup is not None and a.disclosed_makeup.value == 0.05
    assert a.documented_makeup is None and a.documented_blowdown is None
    assert a.reserved_blowdown is None
    # Not Springfield's slot: this is not a ceiling the claim's own source self-disclosed.
    assert a.disclosed_ceiling is None
    # And no metered non-cooling withdrawal is attributed to the campus (B6's slot stays empty) —
    # the city's own PWS withdrawal is the SELLER's, three transfers upstream, never the buyer's.
    assert a.nonprocess_makeup is None


def test_bowling_green_is_reservation_conflict_not_route_blind() -> None:
    # The ordering B6 built, exercised on a real second site: the makeup route IS blind (purchased
    # municipal supply), but a negotiated ceiling is not something A1/A2 could ever have metered, so
    # blinding them cannot erase it. A blind route must not collapse a positive finding into "we
    # cannot see" — that is the whole point of the reservation_conflict pass-through.
    rec = cr.reconcile_bowling_green(settings=Settings())
    route = rec.account.route
    assert route is not None
    assert route.supply is cr.SupplyRoute.MUNICIPAL
    assert route.instruments_blind is True
    assert rec.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert rec.outcome is not cr.ReconcileOutcome.ROUTE_BLIND


def test_bowling_green_discharge_route_is_unknown_not_assumed_to_sewer() -> None:
    # Discipline: the ECHO sweep establishes there is no facility-own OUTFALL, which is not the same
    # as establishing that the flow goes to a POTW sewer. No sewer-use or pretreatment instrument is
    # in hand, so the route stays UNKNOWN. A WaterRoute is a cited determination, never an assumption.
    route = cr.reconcile_bowling_green(settings=Settings()).account.route
    assert route is not None
    assert route.discharge is cr.DischargeRoute.UNKNOWN
    assert route.discharge is not cr.DischargeRoute.SANITARY_SEWER
    # Municipal supply alone is enough to blind the account.
    assert route.instruments_blind is True


def test_bowling_green_route_cites_the_readable_negative_and_the_ky_disambiguation() -> None:
    # The A1 negative is only meaningful because the register is demonstrably live at this site: the
    # Apollo TEMP registration in the campus's own HUC-12 is what makes Meta's absence a ROUTE rather
    # than a hole in coverage. And the issue's explicit ask — record the KY/OH disambiguation.
    route = cr.reconcile_bowling_green(settings=Settings()).account.route
    assert route is not None
    cite = route.citation
    assert "Apollo Power Generation Facility - TEMP" in cite and "2026-03-26" in cite
    assert "041000100703" in cite  # the campus's own HUC-12, shared with the Apollo registration
    assert "39173" in cite  # Wood County, OH — an Ohio numeric key, not a place name
    assert "KENTUCKY" in cite
    assert route.tag == "[verified]" and route.confidence == "high"


def test_bowling_green_finding_names_the_12x_conflict_without_resolving_it() -> None:
    # B5 does not settle #1439's 50k-vs-600k conflict, and must not read as if it had. What it does
    # establish is that the architecture question does not wait on that resolution.
    rec = cr.reconcile_bowling_green(settings=Settings())
    assert "12x the operator's OWN disclosed 0.05 MGD" in rec.finding
    assert "stays unresolved here" in rec.finding
    assert "upper-bound ceiling, NOT a headline consumptive" in rec.finding
    # The generic reservation branch must not call every claim an "FAQ" claim — Troy-Piqua's came
    # from a City FAQ, Bowling Green's from a company announcement.
    assert "FAQ" not in rec.finding


def test_bowling_green_lead_names_both_holders() -> None:
    # B6's lesson generalized: the service agreement + campus meter are the DISTRICT's, the wholesale
    # contract is the CITY's, and a request to either alone answers half the question.
    rec = cr.reconcile_bowling_green(settings=Settings())
    assert rec.lead is not None
    assert "Northwestern Water & Sewer District" in rec.lead.holder
    assert "City of Bowling Green" in rec.lead.holder
    assert "#1439" in rec.lead.epic_ref  # the site's standing water lead, sharpened
    assert rec.lead.tag == "[open]"


def test_cohort_includes_bowling_green_b5_conflict_exactly_once() -> None:
    # Bowling Green IS in A2's cohort but is reconciled explicitly (skipped in the generic loop) — so
    # it appears exactly once, as the reservation conflict, not twice and not as a bare gap.
    records = cr.reconcile_cohort(settings=Settings())
    bg = [r for r in records if r.site == "bowling-green"]
    assert len(bg) == 1
    assert bg[0].outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT
    assert bg[0].is_control is False
    # Two reservation conflicts now ride in the cohort (Troy-Piqua B1 + Bowling Green B5).
    conflicts = {r.site for r in records if r.outcome is cr.ReconcileOutcome.RESERVATION_CONFLICT}
    assert conflicts == {"troy-piqua", "bowling-green"}


def test_bowling_green_profile_pin_is_untouched_by_the_harness() -> None:
    # The harness recommends; it never mutates cooling_model. Re-archetyping is a reviewed edit with
    # the instrument cited, and no instrument exists here.
    fac = next(
        f
        for f in cr.SITES["bowling-green"].facilities
        if f.name == "Bowling Green Data Center (Project Accordion)"
    )
    assert fac.cooling_model is CoolingModelType.CLOSED_LOOP_DRY
    assert fac.cooling_model_source == "reference"
