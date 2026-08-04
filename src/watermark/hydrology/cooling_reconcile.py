"""Cooling-cycling reconciliation harness — claimed vs documented water account (#1679).

The A3 harness of the closed-loop cooling cycling epic (#1676). With the makeup side (A1
withdrawal connector, :mod:`watermark.hydrology.connectors.ohio_water_withdrawal`) and the
blowdown side (A2 discharge coverage, :mod:`watermark.hydrology.blowdown`) available, this
module assembles a **per-facility water account** and reconciles the operator's *claim*
against what records *document*:

1. Run the pinned ``SiteFacility.cooling_model`` archetype through
   :mod:`watermark.hydrology.cooling_models` to get the **predicted** makeup / consumptive /
   blowdown for the claim.
2. Read the **documented** makeup (A1) + blowdown (A2 DMR) where records exist.
3. Where both documented makeup *and* blowdown are on record, **back-solve cycles-of-
   concentration** (makeup / blowdown) — emitted as an ``[inference]`` bracket, never a
   headline scalar (the ratio of two self-reported figures is not a measurement).
4. Classify each facility into one of four outcomes (:class:`ReconcileOutcome`):

   * **discrepancy** — a low-water claim (``closed_loop_dry``) contradicted by documented
     flow ≫ the archetype's ~0 prediction (or over-cycling even vs a wet claim). Recommends
     re-archetyping up (``evaporative_tower`` / ``hybrid_adiabatic``, ``source="document"``).
   * **corroborated** — documented water is consistent with the claimed archetype. Two
     shapes: a dry claim with documented ≈ 0, and a wet claim (``evaporative_tower`` /
     ``hybrid_adiabatic``) whose documented water matches its prediction. Recommends the
     ``reference → document`` source upgrade.
   * **gap** — no documented makeup or blowdown to test against. Emits a records-request
     **lead payload** for C2 (#1688). B2 (#1682, Van Wert) SHARPENS the gap when the operator has
     *disclosed* an ongoing draw (a self-reported figure, not a metered instrument): the disclosed
     ``[reference]`` figure is recorded on ``WaterAccount.disclosed_makeup`` — never on
     ``documented_*`` — so it cannot upgrade the source or read as a measurement; it stays a gap, but
     the lead names the specific open quantity (Van Wert's **initial closed-loop fill volume**, whose
     fill-vs-annual framing is the ``#1409`` discrepancy). B3 (#1683, Springfield) sharpens a gap in a
     third way: the claim's own source (the City 5C FAQ) self-discloses a **permitted withdrawal
     CEILING** (300,000 gal/day at an >80degF extreme-heat max, "near zero" most of the year),
     recorded on ``WaterAccount.disclosed_ceiling``. A permitted PEAK ceiling self-disclosed by the
     claim's own source is **not** a ``reservation_conflict`` — unlike B1's independently-negotiated
     reservation it is not a demand signal that can contradict the claim (a dry loop sits far below
     it) — so it too never feeds ``_classify`` and never upgrades the source; the lead names the
     actual-vs-ceiling denominator (pull the metered municipal withdrawal, ``#1415``).

   * **reservation_conflict** (B1, #1681) — a low-water claim contradicted **not** by a metered
     use / DMR but by a disclosed **reservation ceiling** (a will-serve / water-service agreement
     figure): Troy-Piqua's City closed-loop FAQ vs the negotiated Water & Wastewater Agreement's
     up-to-2.0 MGD makeup + ~1.0 MGD wastewater reservation. A reservation is a *ceiling*, not a
     measurement of use, and it is **not a discharge/withdrawal instrument** — so per the epic's
     re-archetype gate it can never license a ``[verified]`` re-archetype. It **sharpens** the gap:
     the harness back-solves the implied CoC from the reserved figures (an ``[inference]`` bracket,
     explicitly labeled *ceilings, not metered use* — never collapsed into a headline consumptive),
     keeps the archetype pin as-is (Troy-Piqua stays ``unknown``), and emits a sharpened records
     request for the executed instrument + metered use. The ``reserved_makeup`` / ``reserved_blowdown``
     account fields are kept **distinct** from ``documented_makeup`` / ``documented_blowdown`` so a
     reservation is never read as a metered figure.

**The harness recommends; it does not mutate.** Re-archetyping a ``SiteFacility`` is a
reviewed B1-B6 edit landed with the instrument cited — this output is the evidence packet
for that edit, not an auto-applied change (the epic's evidentiary rule).

**A4 (#1680) independent corroborators.** Two orthogonal tells corroborate over-cycling
*independently of the makeup/blowdown accounting* (:mod:`watermark.hydrology.cooling_corroborators`):
the facility's own **air permit** listing cooling towers as PM (drift) sources, and its **Tier II /
EPCRA-312** cooling-water treatment chemistry. Each :class:`ReconciliationRecord` carries a resolved
:class:`~watermark.hydrology.cooling_corroborators.CoolingCorroborators`. They are SECONDARY: they
sharpen the finding and the gap's records-request but **never change the classified outcome** — an
air permit is not a discharge/withdrawal instrument, so a corroborator is never the sole basis for a
re-archetype.

**The Intel positive control** (:func:`intel_control`) is the calibration baseline: an
openly-evaporative facility (exemplar New Albany / Intel, ~125 cooling towers) whose
documented water *equals its evaporative-tower prediction*. The harness must classify it
``corroborated`` — **not** a false ``discrepancy`` just because it uses a lot of water. It
is a constructed calibration vector built into the harness, not a registered site; its figures
are internally consistent with an evaporative tower at CoC ≈ 5, not documented Intel data.

**B6 (#1686) tested whether the real Intel record could replace that constructed vector, and
established that it cannot** — for three cited reasons (:func:`reconcile_intel_new_albany`):
Ohio One is a semiconductor fab rather than a data center, it does not operate until 2030-31,
and its operating water is purchased City of Columbus supply discharging to the Columbus
sanitary sewer. The last of those generalizes, and is the calibration result the control was
really for: **for a municipally-supplied, sewer-discharging facility, A1 and A2 return ~0 by
construction**, and the classifier would have read that ~0 as "documented ≈ 0 → corroborated
dry". So the harness carries a cited :class:`WaterRoute` per facility and a fifth outcome:

* **route_blind** (B6, #1686) — the instruments cannot reach this facility's water at all
  (purchased municipal makeup, and/or blowdown to a POTW sanitary sewer). Their ~0 is an
  absence of jurisdiction, not a measurement, so it can never corroborate a low-water claim.
  The guard invalidates a *negative* read only: a documented flow or a reservation ceiling
  still adjudicates, so ``discrepancy``, ``reservation_conflict`` and a genuinely-corroborated
  wet claim all survive it. The pin is kept and the records request is re-aimed at the City
  meter + the industrial-pretreatment record. Two further slots serve it: ``nonprocess_makeup``
  (a documented withdrawal on record that is NOT the cooling account — Intel's
  construction-phase groundwater) and ``prediction_refused`` (the archetype account could not be
  derived at all, because every archetype is IT-load-parameterized and a fab has no IT load).
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from watermark.config import Settings, get_settings
from watermark.hydrology import blowdown, cooling_models
from watermark.hydrology.cooling_corroborators import (
    AirPermitCorroborator,
    AirPermitState,
    CoolingCorroborators,
    CorroboratorStance,
    TierIIChemistryCorroborator,
    TierIIState,
    resolve_corroborators,
)
from watermark.hydrology.model import CoolingBasis, ProvenancedValue
from watermark.logging import get_logger
from watermark.provenance import Confidence
from watermark.sites import SITES, CoolingModelType, SiteFacility

log = get_logger(__name__)

# Committed artifact relpath (under ``settings.data_dir``); regenerated by
# ``watermark cooling-reconcile --write``. Co-located with the A2 coverage artifact so the
# closed-loop epic's discharge-side references stay together.
RECONCILIATION_RELPATH = "reference/oepa/cooling-reconciliation.yaml"

# A documented flow at or below this (MGD) is read as ~0 — DMR rounding / trace non-cooling
# flow, not a cooling-water signal. It is the floor that separates a genuinely dry loop
# (documented ≈ 0) from a discrepancy (documented flow under a dry claim).
_MEANINGFUL_FLOW_MGD = 0.01

# The corroboration band: documented flow within [pred / TOL, pred x TOL] of the archetype's
# prediction corroborates it. Above the band (documented ≫ predicted) is a discrepancy even
# against a wet claim (over-cycling); below it, the claim is conservative vs the record — not
# the epic's under-reporting thesis, so it still corroborates (the record does not refute a
# lower-water reality). The band is wide because both sides are screening-grade figures.
_CORROBORATION_TOL = 2.0

# Fallback relative uncertainty on a back-solved CoC when neither documented input carries its
# own band — the ratio of two monthly-reported self-reported figures is not a point estimate.
_COC_REL_UNCERTAINTY = 0.15


class ReconcileOutcome(StrEnum):
    """The reconciliation of a facility's cooling claim against documented water."""

    DISCREPANCY = (
        "discrepancy"  # low-water claim contradicted by documented flow (a metered use / DMR)
    )
    CORROBORATED = "corroborated"  # documented water consistent with the claimed archetype
    # A low-water claim contradicted by a disclosed RESERVATION ceiling (a will-serve / water-service
    # agreement figure), NOT a metered use / DMR — a ceiling is not a discharge/withdrawal instrument,
    # so it sharpens the gap (keep the pin, records-request the instrument) without licensing a
    # re-archetype. B1 (#1681): Troy-Piqua's closed-loop FAQ vs the 2.0 MGD water-agreement reservation.
    RESERVATION_CONFLICT = "reservation_conflict"
    GAP = "gap"  # no documented makeup/blowdown to test against → a C2 records request
    # The instruments the harness reads cannot reach this facility's water at all — its makeup is
    # PURCHASED municipal supply (invisible to A1's withdrawal registry) and/or its discharge goes
    # to a POTW's sanitary sewer (invisible to A2's NPDES/DMR). A ~0 from a blind instrument is an
    # artifact of the supply route, not a measurement, so it can never corroborate a dry claim.
    # B6 (#1686), from the New Albany / Intel positive control.
    ROUTE_BLIND = "route_blind"


class SupplyRoute(StrEnum):
    """Where a facility's cooling makeup comes from — i.e. whether A1 can see it at all (B6, #1686).

    The A1 makeup source is the Ohio DNR WWFRP, a registry of withdrawals **from waters of the
    state** (R.C. 1521.16). A facility that *buys* its water from a public system withdraws
    nothing itself: it either never appears in the registry or appears with a token registration
    and a ~0 annual report, while the real consumption sits on a **City meter** the registry never
    sees. So the route decides whether an A1 ~0 is a measurement or an absence of jurisdiction.
    """

    SELF_SUPPLIED = "self_supplied"  # own wells / intake — the WWFRP registers it; A1 reaches it
    MUNICIPAL = "municipal"  # purchased from a public system — A1 cannot see the use
    UNKNOWN = "unknown"  # not established from the record


class DischargeRoute(StrEnum):
    """Where a facility's blowdown goes — i.e. whether A2 can see it at all (B6, #1686).

    The A2 blowdown source is the facility's own NPDES discharge record (ECHO/ICIS DMRs) — and
    since OHD000001's withdrawal (2026-07-21) only an INDIVIDUAL permit can ever produce one, as
    no general-permit coverage will ever exist. A facility that sends its process water to a
    **POTW's sanitary sewer** discharges to no water of the state, so it files no DMR: its flow is
    recorded only on a City industrial-pretreatment / IU permit and sewer-use agreement, which
    ECHO never carries.
    """

    SURFACE_NPDES = "surface_npdes"  # a facility-own outfall — a DMR exists; A2 reaches it
    SANITARY_SEWER = "sanitary_sewer"  # to a POTW under a sewer-use / IU permit — A2 cannot see it
    UNKNOWN = "unknown"  # not established from the record


class WaterRoute(BaseModel):
    """How a facility's water physically reaches and leaves it — the reach test on A1/A2 (B6, #1686).

    The harness's two instruments are jurisdictional, not universal: A1 sees withdrawals from
    waters of the state, A2 sees discharges to them. A facility on municipal supply and municipal
    sewer is outside **both**, and the honest consequence is that its records read ~0 for reasons
    that have nothing to do with how it cools. This is a **cited** determination about a specific
    facility — never assumed — so it is set only where the record establishes it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    supply: SupplyRoute
    discharge: DischargeRoute
    citation: str
    tag: (
        str  # evidentiary tag on the route determination ("[verified]" when instrument-established)
    )
    confidence: Confidence

    @property
    def instruments_blind(self) -> bool:
        """True when at least one side of the account is outside the instruments A1/A2 read.

        One blind side is enough to invalidate a *negative* read: the harness pairs the documented
        blowdown against predicted blowdown, else documented makeup against predicted makeup, so a
        blind side means the figure it would fall back to is not a measurement of the cooling
        account.
        """
        return (
            self.supply is SupplyRoute.MUNICIPAL or self.discharge is DischargeRoute.SANITARY_SEWER
        )

    @property
    def blind_sides(self) -> tuple[str, ...]:
        """The blind side(s), named — for the finding and the records-request lead."""
        sides: list[str] = []
        if self.supply is SupplyRoute.MUNICIPAL:
            sides.append("makeup (purchased municipal supply — outside the A1 withdrawal registry)")
        if self.discharge is DischargeRoute.SANITARY_SEWER:
            sides.append("blowdown (to a POTW sanitary sewer — outside the A2 NPDES/DMR record)")
        return tuple(sides)


class WaterAccount(BaseModel):
    """The assembled per-facility water account: predicted (claim) vs documented (record).

    ``predicted_*`` come from running the pinned archetype through
    :mod:`watermark.hydrology.cooling_models` — an ``[inference]`` from the claim. ``documented_*``
    are read from records (A1 makeup, A2 blowdown DMR) and are ``None`` until such a record
    exists. ``backsolved_cycles`` is present only when *both* documented makeup and blowdown are
    on record, and is always a bracket (never a scalar). Every figure carries its own provenance.
    """

    model_config = ConfigDict(extra="forbid")

    archetype: CoolingModelType
    # The predicted side is REFUSABLE (B6, #1686). Every archetype in
    # :mod:`watermark.hydrology.cooling_models` is IT-load-parameterized (load x WUE), so a
    # facility with no IT load has no derivable prediction — a semiconductor fab's cooling is
    # driven by process heat, not by servers, and running a data-center WUE against its
    # electrical load would emit a number with no evidentiary basis. When the prediction is
    # refused these are ``None`` and ``prediction_refused`` carries the cited reason; a renderer
    # must show the refusal, never substitute a zero.
    it_load: ProvenancedValue | None = None  # MW; None when the load is [open] / not an IT load
    predicted_makeup: ProvenancedValue | None = None  # MGD, the claim's cooling intake
    predicted_consumptive: ProvenancedValue | None = None  # MGD, the claim's evaporative loss
    predicted_blowdown: ProvenancedValue | None = None  # MGD, the claim's blowdown (makeup - evap)
    # Why the archetype's water account could not be predicted — set together with the three
    # ``predicted_*`` being ``None`` (enforced below). ``None`` = the prediction ran normally.
    prediction_refused: str | None = None
    documented_makeup: ProvenancedValue | None = None  # MGD, A1 withdrawal record (metered use)
    documented_blowdown: ProvenancedValue | None = None  # MGD, A2 discharge DMR (metered discharge)
    # A disclosed RESERVATION ceiling (a will-serve / water-service agreement figure) — kept DISTINCT
    # from documented_* so a reserved-capacity ceiling is never read as a metered use (B1, #1681).
    # A ceiling is not a discharge/withdrawal instrument, so it feeds a reservation_conflict, never a
    # re-archetype. None unless the facility has a disclosed reservation on record.
    reserved_makeup: ProvenancedValue | None = (
        None  # MGD, disclosed makeup/withdrawal reservation ceiling
    )
    reserved_blowdown: ProvenancedValue | None = (
        None  # MGD, disclosed wastewater/blowdown reservation ceiling
    )
    # An operator-DISCLOSED ongoing operational / fill draw (a self-reported figure — QTS's "about
    # what 4 households use per month" ~660k gal, B2 #1682) — kept DISTINCT from documented_* (metered
    # instrument) AND reserved_* (a negotiated ceiling). A self-report of the very claim under test is
    # neither a measurement nor a will-serve ceiling, so it NEVER feeds _classify and never upgrades the
    # source: it only SHARPENS a gap (the honest read stays [reference], not 'confirmed dry'). None
    # unless the operator has disclosed an ongoing-use figure. MGD (annualized when reported per-year).
    disclosed_makeup: ProvenancedValue | None = None
    # A self-disclosed permit / withdrawal CEILING (a permitted municipal-withdrawal maximum) — kept
    # DISTINCT from BOTH ``reserved_*`` (an independently-negotiated will-serve / water-agreement
    # reservation, B1) AND ``documented_*`` (a metered instrument). B3 (#1683, Springfield): the City
    # 5C FAQ self-discloses "up to 300,000 gal/day permitted" at an >80degF extreme-heat max ("near
    # zero" most of the year), from the SAME source that makes the "not evaporative" claim. A permitted
    # PEAK ceiling self-disclosed by the claim's own source is NOT an independent demand signal that can
    # contradict the claim (unlike B1's negotiated reservation) — a genuinely dry loop sits far below
    # it — so, like ``disclosed_makeup``, it NEVER feeds ``_classify`` and never upgrades the source: it
    # only SHARPENS a gap (name the actual-vs-ceiling denominator). None unless a self-disclosed
    # permitted ceiling is on record. MGD.
    disclosed_ceiling: ProvenancedValue | None = None
    # A documented, metered withdrawal that is on record but is NOT the cooling account under test
    # (B6, #1686) — kept distinct from ``documented_makeup`` for the same reason the self-report
    # slots are: reading it as cooling makeup would be a category error, not a conservative
    # approximation. Intel's WWFRP series is the case: 15.91 MG in 2024 across 7 wells with ~89%
    # returned, peaking May-June and troughing July-August — construction-phase groundwater at a
    # site whose 125 permitted cooling towers will not run until 2030-31, and whose monthly shape
    # is the INVERSE of a temperature-driven evaporative signature. It never feeds ``_classify``;
    # it documents what the registry actually measured, so a reader can see that the ~0 cooling
    # signal is not the registry being silent. MGD (annualized from the reported annual total).
    nonprocess_makeup: ProvenancedValue | None = None
    # The documented withdrawal of the MUNICIPAL SYSTEM that supplies a route-blind facility
    # (B4, #1684) — the only withdrawal record A1 can reach once ``route.supply`` is municipal,
    # because the registry meters the city, not its customers. It is the SUPPLIER's account, so
    # like every other non-``documented_*`` slot it never feeds ``_classify``: a system total
    # aggregates every customer on it and can neither corroborate nor contradict one facility's
    # cooling claim. What it does is give a route_blind a DENOMINATOR — the scale a future
    # disclosure lands inside — which is the difference between "we cannot see it" and "we cannot
    # see it, and here is how big the thing we cannot see would be". Urbana is the case: the City
    # reported 1.76 MGD across its two public-supply plants in 2024, while an evaporative read of
    # the same campus at its screening IT load would draw 0.49-1.64 MGD. MGD (annualized from the
    # reported annual total). Set only alongside a municipal supply route (enforced below).
    supplier_withdrawal: ProvenancedValue | None = None
    # Whether A1 / A2 can reach this facility's water at all (B6, #1686). ``None`` = not
    # established (the honest default — a route is a cited determination, never assumed).
    route: WaterRoute | None = None
    disclosed_cycles: ProvenancedValue | None = None  # the operator's disclosed CoC, if any
    # The back-solved cycles-of-concentration (makeup / blowdown) — an [inference] BRACKET, never
    # a headline scalar. Present when both makeup and blowdown are on record — as documented (metered)
    # figures, or (reservation_conflict) as reservation ceilings, in which case its citation says so.
    backsolved_cycles: ProvenancedValue | None = None
    # The A2 seasonality shape signal (warm/cool DMR-flow ratio) — a temperature-driven
    # evaporative blowdown peaks in summer (ratio ≫ 1), a dry loop is flat (~1). A shape
    # indicator, never a magnitude; None when no DMR flow series is on record.
    seasonality_warm_ratio: float | None = None

    @model_validator(mode="after")
    def _prediction_refusal_is_total(self) -> WaterAccount:
        """A refused prediction refuses ALL of it, and always says why (B6, #1686).

        The failure this forbids is a half-refused account: two archetype figures present and one
        ``None``, which a renderer would read as a real zero. Refusal is a stance about the whole
        derivation, so the three ``predicted_*`` move together with ``prediction_refused``.
        """
        predicted = (self.predicted_makeup, self.predicted_consumptive, self.predicted_blowdown)
        present = [p is not None for p in predicted]
        if any(present) != all(present):
            raise ValueError(
                "predicted_makeup / predicted_consumptive / predicted_blowdown move together — "
                "a partially-refused prediction reads as a real zero downstream"
            )
        if all(present) and self.prediction_refused is not None:
            raise ValueError(
                "prediction_refused is set but the predicted account is present — a refusal must "
                "leave predicted_makeup / predicted_consumptive / predicted_blowdown unset"
            )
        if not any(present) and not self.prediction_refused:
            raise ValueError(
                "the predicted account is absent with no prediction_refused reason — refusing to "
                "derive an archetype's water is a cited stance, never a silent omission"
            )
        return self

    @model_validator(mode="after")
    def _supplier_withdrawal_needs_a_municipal_route(self) -> WaterAccount:
        """A supplier's withdrawal only means anything under a cited municipal supply (B4, #1684).

        The slot exists because a municipally-supplied facility is invisible to A1 while its
        *supplier* is not. Off that route the figure has no referent: a self-supplied facility's
        own withdrawal belongs on ``documented_makeup``, and a system total parked next to a
        facility that does not buy from that system is the category error the slot was added to
        prevent. So the route must be set and must say ``municipal``.
        """
        if self.supplier_withdrawal is None:
            return self
        if self.route is None or self.route.supply is not SupplyRoute.MUNICIPAL:
            raise ValueError(
                "supplier_withdrawal is set without a cited municipal supply route — a supplying "
                "system's withdrawal is only the facility's denominator when the facility buys "
                "from it; a self-supplied facility's own withdrawal is documented_makeup"
            )
        return self


class RecordsRequestLead(BaseModel):
    """A C2 (#1688) records-request lead payload emitted for a gap facility.

    A validated peer of the raw dict the harness used to carry (like ``AwardLead`` /
    ``LeiLead``, a lead model lives with its producer — the reconciliation output models all
    live here, not in ``watermark.models``, which is for corpus extractions). Structured so a
    consumer (the C2 queue) reads typed fields, not free-form keys.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["records-request"] = "records-request"
    site: str
    facility: str
    subject: str
    records_sought: list[str]
    holder: str
    rationale: str
    epic_ref: str
    tag: str  # evidentiary tag on the lead ("[open]" — the gap it fills)


class ReconciliationRecord(BaseModel):
    """One facility's reconciliation: its water account, outcome, recommendation, provenance."""

    model_config = ConfigDict(extra="forbid")

    site: str
    facility: str
    # True for the Intel calibration control (a constructed positive control, not a registered
    # facility) — so consumers can filter it out of the live-cohort findings.
    is_control: bool = False
    claimed_archetype: str  # SiteFacility.cooling_model value under review
    claim_source: str  # SiteFacility.cooling_model_source (e.g. "reference" — an operator claim)
    claim_citation: str
    account: WaterAccount
    outcome: ReconcileOutcome
    # The harness RECOMMENDS (never mutates): for a discrepancy, the archetype to re-pin and the
    # source grade it would carry; for a corroboration, the source upgrade. None for a gap and for a
    # reservation_conflict (which keeps its pin — see ``kept_archetype`` — rather than re-pinning).
    recommended_archetype: str | None = None
    recommended_source: str | None = None
    # The archetype pin the harness recommends KEEPING for a reservation_conflict (the site's real
    # profile pin — "unknown" for Troy-Piqua, since a reservation ceiling is not an instrument and
    # can't re-pin it). Populated only for a reservation_conflict; None for every other outcome.
    kept_archetype: str | None = None
    # The C2 records-request lead payload (#1688) — present only for a gap outcome.
    lead: RecordsRequestLead | None = None
    # The A4 (#1680) independent corroborators — air-permit cooling-tower PM + Tier II chemistry.
    # SECONDARY by construction: they sharpen the finding / records-request but NEVER change the
    # ``outcome`` above (an air permit is not a discharge/withdrawal instrument, so it is never the
    # sole basis for a re-archetype). ``None`` when not resolved (a bare ``reconcile_facility`` call).
    corroborators: CoolingCorroborators | None = None
    tag: str  # evidentiary tag on the reconciliation ("[open]" gap / "[inference]" / "[verified]")
    confidence: Confidence
    finding: str  # one-line evidentiary read


# --------------------------------------------------------------------- predicted water


def _require(value: ProvenancedValue | None, what: str) -> ProvenancedValue:
    """Enforce a cohort invariant that survives ``python -O`` (unlike a bare ``assert``).

    ``headline_makeup``/``headline_consumptive`` return ``None`` only for a bracketed
    (``unknown``) basis, and ``documented_*`` are non-``None`` on a non-gap outcome — invariants
    the cohort upholds, but a stripped ``assert`` would let a violation surface as an opaque
    ``AttributeError``. Raise explicitly, matching :func:`_predicted_basis`.
    """
    if value is None:
        raise ValueError(
            f"{what} is unexpectedly None — the reconciliation cohort is archetype-pinned "
            "(never bracketed/unknown) and a non-gap outcome always carries a documented figure"
        )
    return value


def _predicted_basis(fac: SiteFacility, settings: Settings) -> CoolingBasis:
    """Run the facility's pinned archetype to get its predicted cooling-water basis.

    Dispatches through the archetype spec directly (not
    :func:`watermark.hydrology.cooling.derive_cooling_basis`, which reads the *active* site's
    facility) so a cross-site cohort facility is derived from its OWN disclosed inputs. The
    Lima IT-load fallback is guarded here exactly as ``derive_cooling_basis`` guards it: a
    non-``off`` archetype with no resolvable load would otherwise silently inherit Lima's
    275 MW basis.
    """
    model = fac.cooling_model
    if model is not CoolingModelType.OFF and fac.it_load_mw is None:
        raise ValueError(
            f"facility {fac.name!r} pins {model.value!r} but has no resolvable IT load — cannot "
            "predict its cooling-water account (only `off` is derivable without one)"
        )
    return cooling_models.get(model).derive(fac, cooling_models.CoolingParams(), settings)


def _predicted_blowdown(basis: CoolingBasis) -> ProvenancedValue:
    """Predicted blowdown (MGD) = makeup - evaporation for the claimed archetype.

    In a recirculating tower makeup = evaporation + blowdown, so blowdown = makeup -
    consumptive; a sealed dry loop predicts ~0 makeup → ~0 blowdown. Guards a tiny negative
    from rounding to 0. Bracketed (``unknown``) bases never reach here — the cohort is
    archetype-pinned.
    """
    makeup = _require(basis.headline_makeup(), "predicted makeup")
    consumptive = _require(basis.headline_consumptive(), "predicted consumptive")
    value = max(0.0, round(makeup.value - consumptive.value, 3))
    return ProvenancedValue.derived(
        value,
        "MGD",
        citation=(
            f"predicted blowdown = makeup {makeup.value:g} - evaporation {consumptive.value:g} "
            f"MGD for the {basis.cooling_model.value} archetype"
        ),
    )


# --------------------------------------------------------------------- back-solve


def _backsolve_cycles(
    makeup: ProvenancedValue,
    blowdown: ProvenancedValue,
    *,
    kind: Literal["documented", "reserved"] = "documented",
) -> ProvenancedValue | None:
    """Back-solve cycles-of-concentration = makeup / blowdown, as an ``[inference]`` bracket.

    Cycles-of-concentration is the makeup/blowdown ratio by definition. It is emitted as a
    bracket, never a headline scalar (the ratio of two self-reported monthly figures carries
    real uncertainty): the bracket comes from the inputs' own bands when present, else a
    ``±15%`` screening band. ``None`` when blowdown is ~0 (the ratio diverges — a non-physical
    input pair, not a cycling signal).

    ``kind`` labels what the two inputs are — ``"documented"`` (metered use / DMR figures) or
    ``"reserved"`` (reservation ceilings, a will-serve / water-agreement figure — a CoC read off
    two ceilings is doubly not a measurement, and the citation says so; B1, #1681).
    """
    bd = blowdown.value
    if bd <= _MEANINGFUL_FLOW_MGD:
        return None
    mk = makeup.value
    point = round(mk / bd, 2)
    citation = (
        (
            f"back-solved CoC = documented makeup {mk:g} MGD / documented blowdown {bd:g} MGD "
            "([inference]: the ratio of two self-reported figures, a bracket not a measurement)"
        )
        if kind == "documented"
        else (
            f"back-solved CoC = reserved makeup {mk:g} MGD / reserved wastewater {bd:g} MGD "
            "([inference]: the ratio of two RESERVATION CEILINGS, not metered use — a bracket, and "
            "an upper-bound shape only, never a headline consumptive)"
        )
    )
    # Prefer the inputs' own bands (makeup_low/blowdown_high → CoC low, and vice-versa); fall
    # back to a relative screening band. Either way the result always carries a range.
    if makeup.has_range or blowdown.has_range:
        lo = round(makeup.low_or_value / blowdown.high_or_value, 2)
        hi = round(makeup.high_or_value / blowdown.low_or_value, 2)
        return ProvenancedValue.derived(
            point, "ratio", citation=citation, low=min(lo, point), high=max(hi, point)
        )
    return ProvenancedValue.derived(
        point, "ratio", citation=citation, rel_uncertainty=_COC_REL_UNCERTAINTY
    )


# --------------------------------------------------------------------- classify


def _classify(
    archetype: CoolingModelType,
    predicted_makeup: float | None,
    predicted_blowdown: float | None,
    documented_makeup: float | None,
    documented_blowdown: float | None,
    reserved_makeup: float | None = None,
    reserved_blowdown: float | None = None,
    route: WaterRoute | None = None,
) -> ReconcileOutcome:
    """Classify the claim↔document reconciliation, applying the route guard (B6, #1686).

    Two guards sit around the base classification below.

    **The reach guard** (``route``): A1 and A2 are jurisdictional instruments — a withdrawal
    registry of waters of the state, and an NPDES discharge record. A facility on purchased
    municipal supply and/or a POTW sanitary sewer is outside them, so the ~0 they return is an
    absence of jurisdiction, not a measurement. That invalidates a **negative** read only: an
    otherwise-``gap`` or ``corroborated``-because-both-sides-are-~0 outcome becomes
    ``route_blind``. A *positive* signal from any instrument still adjudicates — a documented
    flow, or a reservation ceiling, says something true regardless of what the blind side would
    have said — so ``discrepancy``, ``reservation_conflict``, and a wet claim corroborated by real
    documented water all survive the guard untouched.

    **The refusal guard** (``predicted_* is None``): a facility whose archetype water account
    could not be derived at all (no IT load — a fab) has nothing to compare against, so it can
    never be ``corroborated`` or a ``discrepancy``. It resolves to ``route_blind`` when the route
    is blind, else ``gap``.
    """
    if predicted_makeup is None or predicted_blowdown is None:
        # No predicted account to compare against: the record cannot corroborate or contradict a
        # claim the harness declined to quantify. It is a records question either way.
        if route is not None and route.instruments_blind:
            return ReconcileOutcome.ROUTE_BLIND
        return ReconcileOutcome.GAP
    base = _classify_base(
        archetype,
        predicted_makeup,
        predicted_blowdown,
        documented_makeup,
        documented_blowdown,
        reserved_makeup,
        reserved_blowdown,
    )
    if route is None or not route.instruments_blind:
        return base
    if base is ReconcileOutcome.RESERVATION_CONFLICT:
        # A disclosed reservation ceiling is not one of the instruments the route can blind — it
        # comes from a negotiated agreement, not from a withdrawal registry or a DMR. B1's finding
        # survives a blind route untouched.
        return base
    # The adjudicating figure is the one ``_classify_base`` pairs against the prediction: the
    # cooling-specific blowdown record where one exists, else the withdrawal record.
    adjudicating = documented_blowdown if documented_blowdown is not None else documented_makeup
    if adjudicating is None or adjudicating < _MEANINGFUL_FLOW_MGD:
        # Nothing, or ~0, from an instrument that cannot reach this facility. Both are absences of
        # jurisdiction rather than measurements, and the two failure modes they would otherwise
        # produce are the ones B6 exists to catch: a `gap` that reads as a merely-unfinished lookup
        # (pulling A1/A2 harder can never close it — the ask belongs to a different holder), and a
        # `corroborated` read off a zero the blind instrument was always going to return, which
        # would silently upgrade every municipally-supplied claim in the cohort to document-grade.
        # This covers a WET claim too: a documented blowdown of ~0 against a predicted 0.43 MGD
        # sits inside the corroboration band and would otherwise pass as confirmation.
        return ReconcileOutcome.ROUTE_BLIND
    return base


def _classify_base(
    archetype: CoolingModelType,
    predicted_makeup: float,
    predicted_blowdown: float,
    documented_makeup: float | None,
    documented_blowdown: float | None,
    reserved_makeup: float | None = None,
    reserved_blowdown: float | None = None,
) -> ReconcileOutcome:
    """Classify the claim↔document reconciliation into one of the outcomes.

    The false-positive guard (the Intel control): a **discrepancy** requires the *claimed*
    archetype to predict little/no water — high documented water only contradicts a low-water
    claim. A wet claim (evaporative/hybrid) whose documents show matching high water is
    ``corroborated``, never flagged discrepant for using a lot of water.

    Instrument-grade documented flow (metered use / DMR) adjudicates first — it is stronger than a
    reservation ceiling. Only when NO documented figure is on record does a disclosed **reservation
    ceiling** get read: one disproportionate to a low-water claim is a ``reservation_conflict`` (B1,
    #1681), never a ``discrepancy`` — a ceiling is not a discharge/withdrawal instrument, so it can't
    license a re-archetype (the epic's gate). A reservation not disproportionate to the claim doesn't
    corroborate USE either (a ceiling ≠ a measurement), so it stays a ``gap``.
    """
    if documented_makeup is None and documented_blowdown is None:
        if reserved_makeup is not None or reserved_blowdown is not None:
            # Prefer the wastewater (blowdown) reservation vs predicted blowdown; else the makeup
            # reservation vs predicted makeup — the same matched pairing _classify uses below.
            if reserved_blowdown is not None:
                reserved, predicted = reserved_blowdown, predicted_blowdown
            else:
                assert reserved_makeup is not None
                reserved, predicted = reserved_makeup, predicted_makeup
            if predicted < _MEANINGFUL_FLOW_MGD and reserved >= _MEANINGFUL_FLOW_MGD:
                return ReconcileOutcome.RESERVATION_CONFLICT
        return ReconcileOutcome.GAP
    # Prefer the blowdown signal (the A2 cooling-tower/low-volume-wastewater DMR — cooling-
    # specific). Fall back to makeup (A1 withdrawal) only when no blowdown is on record: a
    # documented withdrawal is TOTAL facility water (it may bundle domestic / humidification use),
    # so the makeup-only path is a weaker discrepancy signal that B-review must confirm against the
    # cooling-specific fraction — the harness screens, it does not adjudicate.
    if documented_blowdown is not None:
        documented, predicted = documented_blowdown, predicted_blowdown
    else:
        assert documented_makeup is not None
        documented, predicted = documented_makeup, predicted_makeup
    # A low-water claim (predicted ~0) with documented flow above the noise floor is the epic's
    # discrepancy — the dry claim is contradicted by the record.
    if predicted < _MEANINGFUL_FLOW_MGD:
        if documented >= _MEANINGFUL_FLOW_MGD:
            return ReconcileOutcome.DISCREPANCY
        return ReconcileOutcome.CORROBORATED  # both ~0 → corroborated dry
    # A wet claim: documented ≫ predicted is over-cycling (still a discrepancy); within or below
    # the band the record is consistent with (or more conservative than) the claim.
    if documented / predicted > _CORROBORATION_TOL:
        return ReconcileOutcome.DISCREPANCY
    return ReconcileOutcome.CORROBORATED


_WET_ARCHETYPES = frozenset({CoolingModelType.EVAPORATIVE_TOWER, CoolingModelType.HYBRID_ADIABATIC})


def _corroborator_asks(
    corroborators: CoolingCorroborators | None,
) -> tuple[list[str], list[str]]:
    """The extra ``(records_sought, holders)`` a records-request lead adds for A4 corroborators
    that are themselves NOT on record (#1680).

    A gap or a reservation_conflict lead pulls the water records; when the facility's own air
    PTI/PTIO (its cooling-tower emission-unit list) or Tier II / EPCRA-312 chemistry inventory is
    also not on record, those become their own asks alongside. Returns ``([], [])`` when there are
    no corroborators or every one is already on record (nothing to add) — so a caller can always
    ``extend`` unconditionally.
    """
    records_sought: list[str] = []
    holders: list[str] = []
    if corroborators is None:
        return records_sought, holders
    if corroborators.air_permit.state is AirPermitState.NOT_ON_RECORD:
        records_sought.append(
            "facility air permit (PTI/PTIO) — cooling-tower emission-unit list + PM drift limits"
        )
        holders.append("Ohio EPA / regional air agency (DAPC)")
    if corroborators.tier2_chemistry.state is TierIIState.NOT_ON_RECORD:
        records_sought.append(
            "Tier II / EPCRA-312 chemical inventory — cooling-water treatment (biocide, "
            "scale / corrosion inhibitor)"
        )
        holders.append("SERC / LEPC")
    return records_sought, holders


def _records_lead(
    site: str,
    fac: SiteFacility,
    claim_source: str,
    corroborators: CoolingCorroborators | None = None,
) -> RecordsRequestLead:
    """The C2 (#1688) records-request lead payload for a gap facility.

    A closed-loop claim with no documented makeup or blowdown is not "confirmed dry" — the
    blowdown may go to sewer under a City sewer-use / pretreatment agreement ECHO never sees.
    This is the structured ask that resolves it (R.C. 149.43), consumable by the C2 queue. The A4
    corroborators that are themselves not-on-record (#1680) add their own asks — the facility air
    PTI/PTIO (its cooling-tower emission-unit list) and the Tier II / EPCRA-312 chemistry inventory.
    """
    records_sought = [
        "industrial pretreatment / indirect-discharge (IU) permit",
        "sewer-use agreement + any cooling-tower blowdown authorization",
        "metered water-service use (makeup withdrawal)",
        "cooling-tower blowdown / low-volume-wastewater DMR",
    ]
    holders = [f"City / municipal water-sewer authority serving {site}"]
    extra_records, extra_holders = _corroborator_asks(corroborators)
    records_sought.extend(extra_records)
    holders.extend(extra_holders)
    return RecordsRequestLead(
        site=site,
        facility=fac.name,
        subject="cooling-water account — makeup + blowdown records",
        records_sought=records_sought,
        holder="; ".join(holders),
        rationale=(
            f"{fac.cooling_model.value} claim (source={claim_source}) with no facility-own "
            "discharge permit and no documented makeup — resolve whether blowdown goes to sewer "
            "under a City agreement not visible in ECHO/NPDES, or the loop is genuinely dry."
        ),
        epic_ref="#1688 (C2)",
        tag="[open]",
    )


def _disclosed_gap_lead(
    site: str,
    fac: SiteFacility,
    claim_source: str,
    account: WaterAccount,
    issue_ref: str,
    corroborators: CoolingCorroborators | None = None,
) -> RecordsRequestLead:
    """The sharpened C2 (#1688) records-request lead for a gap the operator has *disclosed* into
    (B2, #1682).

    Unlike a bare gap, the operator has stated an ongoing-use figure (Van Wert: QTS's "about what 4
    households use per month" ~660k gal) — but it is a single-source self-report, not a metered
    instrument, and the closed-loop claim's "does not consume water *once operational*" wording
    structurally excludes the **initial closed-loop fill** (a real, City-approved, one-time withdrawal
    of undisclosed volume). So the ask can name the specific open quantity — the initial fill volume +
    top-off rate (whose fill-vs-annual framing is the ``issue_ref`` discrepancy, Van Wert's ``#1409``)
    — alongside the metered use that would confirm or refute the self-reported ongoing draw. The silent
    A4 corroborators (#1680) add their own not-on-record asks, as on a plain gap.
    """
    disclosed = account.disclosed_makeup
    disclosed_phrase = (
        f"{disclosed.value:g} MGD" if disclosed is not None else "the disclosed ongoing draw"
    )
    # A non-classifying screening comparison (never fed to _classify): a disclosed self-report BELOW
    # the ~0 floor is consistent-with-dry at screening scale; at/above it, the self-report does not
    # read as dry — but either way it is unverified and neither corroborates nor re-archetypes.
    below_floor = disclosed is not None and disclosed.value < _MEANINGFUL_FLOW_MGD
    screen = (
        "consistent with a dry loop at screening scale"
        if below_floor
        else "above the ~0 screening floor (it does not read as dry at screening scale)"
    )
    records_sought = [
        "initial closed-loop fill volume + top-off / make-up rate (the fill-vs-annual figure)",
        "metered water-service use (actual makeup withdrawal vs the disclosed ongoing draw)",
        "executed water & sewer service agreement (the City-approved fill authorization — the "
        "instrument, not a press summary)",
        "cooling-tower blowdown / low-volume-wastewater discharge record — a facility-own INDIVIDUAL NPDES permit + DMR on a direct-discharge path, or the industrial-user (IU) / pretreatment permit + sewer-use agreement on a sanitary-sewer route (OHD000001 was WITHDRAWN 2026-07-21; no general-permit coverage will ever exist)",
    ]
    holders = [
        f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (INDIVIDUAL NPDES — OHD000001 withdrawn 2026-07-21, no general permit to seek)",
    ]
    extra_records, extra_holders = _corroborator_asks(corroborators)
    records_sought.extend(extra_records)
    holders.extend(extra_holders)
    return RecordsRequestLead(
        site=site,
        facility=fac.name,
        subject=(
            "cooling-water account — reconcile the disclosed ongoing draw + the initial fill volume "
            "vs the closed-loop claim"
        ),
        records_sought=records_sought,
        holder="; ".join(holders),
        rationale=(
            f"A {fac.cooling_model.value} claim (source={claim_source}) that 'does not consume water "
            f"once operational', with an UNVERIFIED disclosed ongoing draw ({disclosed_phrase}) {screen} "
            "— a single-source self-report, not a metered instrument, so it neither corroborates nor "
            f"re-archetypes the claim and cannot upgrade the [reference] pin; the disclosed figure's "
            f"fill-vs-annual framing is itself unresolved ({issue_ref}). The 'once operational' wording "
            "also structurally excludes the initial closed-loop fill (a City-approved one-time "
            "withdrawal of undisclosed volume). Pull the metered use + the fill authorization to resolve "
            "whether the loop is genuinely dry or the fill / top-off is material."
        ),
        epic_ref=f"#1688 (C2); {issue_ref}",
        tag="[open]",
    )


def _disclosed_ceiling_gap_lead(
    site: str,
    fac: SiteFacility,
    claim_source: str,
    account: WaterAccount,
    issue_ref: str,
    corroborators: CoolingCorroborators | None = None,
) -> RecordsRequestLead:
    """The sharpened C2 (#1688) records-request lead for a gap the operator has bounded with a
    self-disclosed permit CEILING (B3, #1683).

    Unlike a bare gap, the claim's own source (Springfield's City 5C FAQ) has self-disclosed a
    permitted municipal-withdrawal ceiling — "up to 300,000 gal/day" at an >80degF extreme-heat max,
    with "near zero" use most of the year (~30k gal/day realistic). That ceiling is a self-report from
    the same source that makes the "not evaporative" claim, so — unlike an independently-negotiated
    reservation (B1) — it is NOT a demand signal that contradicts the claim: a genuinely dry loop sits
    far below it. The ask is therefore the missing measurement that would settle it: the **actual
    metered municipal withdrawal** (does it approach the ceiling — evaporative — or sit far below it —
    dry?), the closed-loop mechanical/plumbing permit that would confirm "not evaporative", and the
    on-site reservoir / alternate-supply study the FAQ also discloses. ``issue_ref`` is the site's own
    standing water sub-issue (Springfield's ``#1415``). The silent A4 corroborators (#1680) add their
    own not-on-record asks, as on a plain gap.
    """
    ceiling = account.disclosed_ceiling
    ceiling_phrase = (
        f"{ceiling.value:g} MGD ({round(ceiling.value * 1_000_000):,} gal/day)"
        if ceiling is not None
        else "the disclosed permitted ceiling"
    )
    records_sought = [
        "metered water-service use (actual municipal withdrawal vs the disclosed permitted ceiling "
        "— is the ceiling approached, or does a dry loop sit far below it?)",
        "the closed-loop / direct-liquid mechanical-plumbing permit (the instrument that would "
        "confirm 'not evaporative')",
        "cooling-tower / low-volume-wastewater blowdown discharge record — a facility-own INDIVIDUAL NPDES permit + DMR on a direct-discharge path (OHD000001 was WITHDRAWN 2026-07-21; no general-permit coverage will ever exist)",
        "on-site reservoir / alternate-supply plan (the disclosed municipal-tap-avoidance study)",
        "industrial pretreatment / indirect-discharge (IU) permit + sewer-use agreement",
    ]
    holders = [
        f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (INDIVIDUAL NPDES — OHD000001 withdrawn 2026-07-21, no general permit to seek; Air PTI)",
    ]
    extra_records, extra_holders = _corroborator_asks(corroborators)
    records_sought.extend(extra_records)
    holders.extend(extra_holders)
    return RecordsRequestLead(
        site=site,
        facility=fac.name,
        subject=(
            "cooling-water account — reconcile the actual municipal withdrawal vs the disclosed "
            f"{ceiling_phrase} permitted ceiling for the 'not evaporative' claim"
        ),
        records_sought=records_sought,
        holder="; ".join(holders),
        rationale=(
            f"A {fac.cooling_model.value} claim (source={claim_source}) disclosed EXPLICITLY 'not "
            f"evaporative', with a SELF-DISCLOSED permitted municipal-withdrawal ceiling of "
            f"{ceiling_phrase} (an >80degF extreme-heat peak, 'near zero' most of the year) — a "
            "permitted PEAK ceiling from the claim's own source, NOT an independently-negotiated "
            "reservation, so it is not a reservation conflict: a genuinely dry loop sits far below "
            "it. But a self-report is not a metered instrument, so it can neither confirm 'not "
            "evaporative' nor re-archetype. Pull the actual metered withdrawal to test whether use "
            f"approaches the {ceiling_phrase} ceiling or sits far below it — a screening signal only, "
            "not proof of mechanism: evaporative vs. dry is established by an ingested mechanical/"
            "plumbing permit or a facility-own blowdown/discharge record (an on-site reservoir could "
            f"also supply cooling), not the withdrawal figure alone — plus the blowdown record to "
            f"complete the account, which since OHD000001's withdrawal (2026-07-21) means an "
            f"INDIVIDUAL NPDES permit or the City IU/pretreatment file, never general-permit "
            f"coverage ({issue_ref})."
        ),
        epic_ref=f"#1688 (C2); {issue_ref}",
        tag="[open]",
    )


def _route_blind_lead(
    site: str,
    fac: SiteFacility,
    claim_source: str,
    account: WaterAccount,
    issue_ref: str,
    corroborators: CoolingCorroborators | None = None,
    water_holder: str | None = None,
) -> RecordsRequestLead:
    """The C2 (#1688) records-request lead for a facility outside A1/A2's reach (B6, #1686).

    A plain ``gap`` lead says *pull the water records*. This one exists because that instruction
    is wrong here: the water records the harness reads **have been pulled and they answer ~0 for
    a reason that has nothing to do with cooling**. So the ask is re-aimed at the holder that
    actually meters the facility — the City water utility's consumption record and its industrial
    pretreatment / IU permit and sewer-use agreement — and it names the blind sides explicitly so
    a later reader cannot mistake the harness's ~0 for a finding. The silent A4 corroborators add
    their own not-on-record asks, as on a gap.

    ``water_holder`` names that utility where the record identifies it. It is worth a parameter
    because the blind route is usually blind precisely BECAUSE the supplier is someone other than
    the site's own city (Intel buys from Columbus, two counties from the New Albany address), and a
    records request addressed to the wrong municipality is a wasted statutory clock.
    """
    route = account.route
    blind = "; ".join(route.blind_sides) if route is not None else "the instruments A1/A2 read"
    records_sought = [
        "metered municipal water-service consumption for the campus (the meter that records the "
        "makeup the withdrawal registry cannot see)",
        "industrial pretreatment / indirect-discharge (IU) permit + its reported flow",
        "sewer-use agreement / capacity reservation for the campus",
        "water-service agreement or will-serve letter (the contracted supply the campus draws on)",
    ]
    if account.supplier_withdrawal is not None:
        # B4 (#1684): where the supplying system's own withdrawal is on record, the sharper ask is
        # what that system PLANNED for. A capacity analysis sized to a campus draw is the supplier
        # writing down the number the operator would not — and it is a different document from the
        # customer's meter reading, held by the same utility.
        records_sought.append(
            "the water system's capacity / supply-adequacy analysis for the campus — what draw the "
            "supplier planned for (the figure the operator's claim never states)"
        )
    holders = [
        water_holder or f"City / municipal water-sewer utility serving {site}",
        "Ohio EPA (INDIVIDUAL NPDES — OHD000001 withdrawn 2026-07-21, no general permit to seek)",
    ]
    extra_records, extra_holders = _corroborator_asks(corroborators)
    records_sought.extend(extra_records)
    holders.extend(extra_holders)
    nonprocess = account.nonprocess_makeup
    nonprocess_clause = (
        f" The registry's non-zero series for this facility ({nonprocess.value:g} MGD) is NOT the "
        "cooling account — it is a separate, non-cooling withdrawal, recorded as such."
        if nonprocess is not None
        else ""
    )
    supplier = account.supplier_withdrawal
    supplier_clause = (
        f" The registry does reach the SUPPLIER: {supplier.value:g} MGD across the supplying "
        "system's own public-supply registrations — the system total this campus's draw will sit "
        "inside, which is the scale the request is asking the utility to resolve."
        if supplier is not None
        else ""
    )
    return RecordsRequestLead(
        site=site,
        facility=fac.name,
        subject=(
            "cooling-water account — the metered municipal record, because the withdrawal "
            "registry and the NPDES discharge record cannot reach this facility"
        ),
        records_sought=records_sought,
        holder="; ".join(holders),
        rationale=(
            f"The {fac.cooling_model.value} claim (source={claim_source}) cannot be tested against "
            "A1/A2 at all: this facility is outside their reach on the side(s) that matter — "
            f"{blind}. Their ~0 is an absence of jurisdiction, not a measurement, so it must never "
            "be read as documented ~0 water (which would corroborate a dry claim on nothing)."
            f"{nonprocess_clause}{supplier_clause} Pulling A1/A2 harder cannot resolve it; the "
            f"record that can is City-held ({issue_ref})."
        ),
        epic_ref=f"#1688 (C2); {issue_ref}",
        tag="[open]",
    )


def _reservation_conflict_lead(
    site: str,
    fac: SiteFacility,
    claim_source: str,
    account: WaterAccount,
    issue_ref: str,
    corroborators: CoolingCorroborators | None = None,
    water_holder: str | None = None,
) -> RecordsRequestLead:
    """The sharpened C2 (#1688) records-request lead for a reservation_conflict (B1, #1681).

    Unlike a bare gap, a reservation conflict already carries a quantified figure — a disclosed
    reservation ceiling that contradicts the low-water claim. The ask is therefore sharper: pull the
    **executed instrument** (the negotiated water-service agreement text, not the secondary summary of
    it) and the **metered use** that would say whether the facility draws near the ceiling
    (evaporative) or far below it (nearer dry). ``issue_ref`` is the site's own standing water lead
    (Troy-Piqua's ``#1486``) the conflict sharpens. The silent A4 corroborators (#1680) add their own
    not-on-record asks, as on a gap.

    ``water_holder`` overrides the default holder, and on a reservation conflict it is load-bearing
    for the same reason B6 (#1686) added it to the route-blind lead: the body that signed the
    reservation and the body that reads the meter need not be the site's own city. Bowling Green is
    the case — the campus is metered by a regional district that buys the water wholesale from the
    City, so a request addressed only to the City reaches the wholesale contract and not the
    service agreement, and a request addressed only to the district reaches the reverse.
    """
    reserved = account.reserved_makeup or account.reserved_blowdown
    reserved_phrase = f"{reserved.value:g} MGD" if reserved is not None else "the reserved figure"
    records_sought = [
        "executed water & wastewater service agreement (the instrument text, not a summary)",
        "metered water-service use (actual makeup withdrawal vs the reserved ceiling)",
        "cooling-tower blowdown / low-volume-wastewater discharge record — a facility-own INDIVIDUAL NPDES permit + DMR on a direct-discharge path, or the industrial-user (IU) / pretreatment permit + sewer-use agreement on a sanitary-sewer route (OHD000001 was WITHDRAWN 2026-07-21; no general-permit coverage will ever exist)",
        "industrial pretreatment / indirect-discharge (IU) permit + sewer-use agreement",
    ]
    holders = [
        water_holder or f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (INDIVIDUAL NPDES — OHD000001 withdrawn 2026-07-21, no general permit to seek)",
    ]
    extra_records, extra_holders = _corroborator_asks(corroborators)
    records_sought.extend(extra_records)
    holders.extend(extra_holders)
    return RecordsRequestLead(
        site=site,
        facility=fac.name,
        subject=(
            f"cooling-water account — reconcile the reserved {reserved_phrase} makeup vs the "
            "closed-loop claim"
        ),
        records_sought=records_sought,
        holder="; ".join(holders),
        rationale=(
            f"A disclosed reservation ceiling ({reserved_phrase}) is disproportionate to the "
            f"{fac.cooling_model.value} (source={claim_source}) low-water claim and contradicts it — "
            "but a reservation is a ceiling, not a metered use, and not a discharge/withdrawal "
            f"instrument, so it sharpens the standing water lead ({issue_ref}) without licensing a "
            "re-archetype. Pull the executed instrument + metered use to resolve which framing governs "
            "the consumptive screen."
        ),
        epic_ref=f"#1688 (C2); {issue_ref}",
        tag="[open]",
    )


def _fold_corroborators(
    finding: str, outcome: ReconcileOutcome, corroborators: CoolingCorroborators | None
) -> str:
    """Append the A4 corroborator read to the water-account finding (#1680), when it adds signal.

    The corroborators are SECONDARY: this only *annotates* the finding, never changes the outcome.
    A non-silent net stance always appends (an independent contradiction / corroboration is worth
    surfacing); a silent one appends only for an outcome whose move is a records request (a gap or a
    reservation_conflict — it names the extra records to request), since on a discrepancy /
    corroborated outcome the water account already spoke.
    """
    if corroborators is None:
        return finding
    net = corroborators.net_stance
    records_request_outcome = outcome in {
        ReconcileOutcome.GAP,
        ReconcileOutcome.RESERVATION_CONFLICT,
        ReconcileOutcome.ROUTE_BLIND,
    }
    if net is CorroboratorStance.SILENT and not records_request_outcome:
        return finding
    return f"{finding} {corroborators.summary}"


def _finding(
    outcome: ReconcileOutcome,
    fac: SiteFacility,
    account: WaterAccount,
    claim_source: str,
) -> str:
    """A one-line evidentiary read for the reconciliation record."""
    arche = account.archetype.value
    if outcome is ReconcileOutcome.ROUTE_BLIND:
        # B6 (#1686): the instruments cannot reach this facility's water. The read must say what
        # the record DOES show (so the row is not mistaken for an unfinished lookup) and why that
        # is not the cooling account — never that the account is ~0.
        route = account.route
        blind = "; ".join(route.blind_sides) if route is not None else "A1/A2"
        refused = (
            f" No archetype prediction is derivable here: {account.prediction_refused}"
            if account.prediction_refused
            else ""
        )
        nonprocess = account.nonprocess_makeup
        nonprocess_clause = (
            f" What the withdrawal registry does record — {nonprocess.value:g} MGD — is a "
            "separate, non-cooling withdrawal, carried on nonprocess_makeup so it is never read "
            "as cooling makeup."
            if nonprocess is not None
            else ""
        )
        disclosed = account.disclosed_makeup
        disclosed_clause = (
            f" The operator's own disclosed draw ({disclosed.value:g} MGD) is a self-report, "
            "unverified and not an instrument."
            if disclosed is not None
            else ""
        )
        # B4 (#1684): a supplying system's own reported withdrawal is the DENOMINATOR — it fixes
        # the scale the unmeasurable claim would land inside. It is the supplier's account, not the
        # facility's, so it stays a comparison and never a reading of this facility's water.
        supplier = account.supplier_withdrawal
        supplier_clause = (
            f" The supplying system's own withdrawal IS on record ({supplier.value:g} MGD) — that "
            "is the scale the campus's draw will sit inside, not a measurement of the campus."
            if supplier is not None
            else ""
        )
        return (
            f"The {arche} claim for {fac.name} (source={claim_source}) cannot be tested by this "
            f"harness at all — the facility is outside the reach of the instruments it reads on "
            f"{blind}. Their ~0 is an absence of jurisdiction, NOT a documented ~0, so it can "
            "neither corroborate nor contradict the claim and must never upgrade the source."
            f"{nonprocess_clause}{supplier_clause}{disclosed_clause}{refused} The record that "
            "would answer it is City-held — metered water-service consumption + the industrial "
            "pretreatment / IU permit (→ C2 records request #1688)."
        )
    if outcome is ReconcileOutcome.GAP:
        if account.disclosed_ceiling is not None:
            # B3 (#1683, Springfield): a gap bounded by a self-disclosed permit CEILING. The claim's
            # own source (the City 5C FAQ) discloses a permitted municipal-withdrawal max and an
            # explicit "not evaporative" mechanism — but a self-disclosed PEAK ceiling from the claim's
            # own source is not an independent demand signal (unlike B1's negotiated reservation), so it
            # does not contradict the dry claim (a dry loop sits far below it) and cannot corroborate it
            # (that would be circular). The actual metered withdrawal is the missing measurement.
            ceiling = account.disclosed_ceiling
            ceiling_gpd = f"{round(ceiling.value * 1_000_000):,} gal/day"
            draw = account.disclosed_makeup
            draw_phrase = (
                f", ~{draw.value:g} MGD 'realistic' and near zero most of the year"
                if draw is not None
                else ""
            )
            return (
                f"No metered makeup or blowdown for {fac.name} to test the {arche} 'not evaporative' "
                f"claim (source={claim_source}) — an [open] gap, not 'confirmed dry'. The claim's own "
                f"source self-discloses a permitted municipal-withdrawal CEILING of {ceiling.value:g} "
                f"MGD ({ceiling_gpd}, an >80degF extreme-heat max){draw_phrase}; the pinned "
                f"archetype predicts ~{_require(account.predicted_makeup, 'predicted makeup').value:g} MGD "
                "— far below the ceiling. "
                "A permitted PEAK ceiling self-disclosed by the claim's OWN source is NOT a reservation "
                "conflict (a genuinely dry loop sits far below it) and is a self-report, not a metered "
                "instrument — so it can neither corroborate 'not evaporative' (circular) nor "
                "re-archetype; the actual metered withdrawal against the ceiling is the missing "
                "measurement (→ C2 records request #1688/#1415). Keep the pin [reference]."
            )
        if account.disclosed_makeup is not None:
            # B2 (#1682): a gap the operator has DISCLOSED into. The self-reported draw is compared
            # against the ~0 screening floor for description ONLY (never fed to _classify): below it
            # is consistent-with-dry at screening scale, at/above it does not read as dry — but either
            # way it is unverified (not a metered instrument), so it cannot upgrade the [reference] pin
            # or re-archetype, and the claim's 'once operational' carve-out excludes the initial fill.
            disclosed = account.disclosed_makeup
            screen = (
                "consistent with a dry loop at screening scale"
                if disclosed.value < _MEANINGFUL_FLOW_MGD
                else "above the ~0 screening floor (it does not read as dry at screening scale)"
            )
            return (
                f"No metered makeup or blowdown for {fac.name} to test the {arche} claim "
                f"(source={claim_source}) — an [open] gap, not 'confirmed dry'. The operator DISCLOSES "
                f"an UNVERIFIED ongoing draw of {disclosed.value:g} MGD, {screen} — either way a "
                "single-source self-report (not a metered instrument), so it neither corroborates nor "
                "re-archetypes the claim and cannot upgrade the [reference] pin; the claim's 'once "
                "operational' wording also excludes the initial closed-loop fill (a City-approved "
                "one-time withdrawal of undisclosed volume) — the specific open quantity (→ C2 records "
                "request #1688). Keep the pin [reference]."
            )
        # The predicted side may itself have been refused (B6, #1686) — say so rather than
        # printing a figure the harness declined to derive.
        predicted_clause = (
            f" Predicted makeup {account.predicted_makeup.value:g} MGD."
            if account.predicted_makeup is not None
            else f" No archetype prediction is derivable: {account.prediction_refused}"
        )
        return (
            f"No documented makeup or blowdown for {fac.name}: the {arche} claim "
            f"(source={claim_source}) cannot yet be tested against records — an [open] gap, not "
            f"'confirmed dry' (→ C2 records request #1688).{predicted_clause}"
        )
    if outcome is ReconcileOutcome.RESERVATION_CONFLICT:
        reserved = account.reserved_makeup or account.reserved_blowdown
        reserved_phrase = (
            f"{reserved.value:g} MGD" if reserved is not None else "the reserved figure"
        )
        coc = (
            f" Back-solved CoC {account.backsolved_cycles.value:g} "
            f"({account.backsolved_cycles.low_or_value:g}-{account.backsolved_cycles.high_or_value:g}) "
            "off the reservation ceilings ([inference], not metered use)."
            if account.backsolved_cycles is not None
            else ""
        )
        # A competing SELF-REPORTED figure from the claim's own source (B5, #1685: Meta's ~50,000
        # gpd against the district-linked ~600,000 gpd). Naming the spread matters because it is
        # the operator's own number the reservation contradicts, not only the archetype's ~0 — and
        # because the spread is a live, unresolved conflict that this row does not settle.
        selfrep = ""
        disclosed = account.disclosed_makeup
        if reserved is not None and disclosed is not None and disclosed.value:
            selfrep = (
                f" It is also {reserved.value / disclosed.value:.0f}x the operator's OWN disclosed "
                f"{disclosed.value:g} MGD — a conflict between the two [reference] figures that "
                "stays unresolved here; the reservation classifies because it is independent of the "
                "claim's source, the self-report does not because it is not."
            )
        # A blind route does not overturn a reservation conflict (a negotiated ceiling is not
        # something A1/A2 could have metered), but it does change what the ask can ever reach.
        blind = ""
        if account.route is not None and account.route.instruments_blind:
            blind = (
                " The reservation survives as the finding precisely because the withdrawal/discharge "
                f"instruments cannot reach this facility at all ({'; '.join(account.route.blind_sides)}), "
                "so it is the only quantified figure on record that does not originate with the operator."
            )
        return (
            f"Reserved {reserved_phrase} makeup contradicts the {arche} claim's "
            f"~{_require(account.predicted_makeup, 'predicted makeup').value:g} MGD prediction — but a "
            "reservation is a ceiling, not "
            "a discharge/withdrawal instrument, so keep the archetype pin (no [verified] re-archetype) "
            f"and sharpen the water lead (→ C2 records request #1688).{coc}{selfrep}{blind} The reserved "
            "figure is an upper-bound ceiling, NOT a headline consumptive."
        )
    # A documented signal exists (DISCREPANCY / CORROBORATED) — pair it with the MATCHING
    # predicted figure exactly as _classify does: the A2 blowdown record against predicted
    # blowdown, else the A1 makeup record against predicted makeup (never cross the two).
    if account.documented_blowdown is not None:
        doc = account.documented_blowdown
        predicted = _require(account.predicted_blowdown, "predicted blowdown")
        kind = "blowdown"
    else:
        doc = _require(account.documented_makeup, "documented water")
        predicted = _require(account.predicted_makeup, "predicted makeup")
        kind = "makeup"
    if outcome is ReconcileOutcome.DISCREPANCY:
        season = (
            f" Seasonality warm/cool ratio {account.seasonality_warm_ratio:g} (a summer-peak "
            "shape corroborates temperature-driven evaporation)."
            if account.seasonality_warm_ratio is not None and account.seasonality_warm_ratio > 1.3
            else ""
        )
        return (
            f"Documented {doc.value:g} MGD {kind} contradicts the {arche} claim's "
            f"~{predicted.value:g} MGD prediction — re-archetype up with the instrument cited "
            f"(B-review).{season}"
        )
    # corroborated
    if account.archetype in _WET_ARCHETYPES:
        coc = (
            f" Back-solved CoC {account.backsolved_cycles.value:g} "
            f"({account.backsolved_cycles.low_or_value:g}-{account.backsolved_cycles.high_or_value:g})."
            if account.backsolved_cycles is not None
            else ""
        )
        return (
            f"Documented {doc.value:g} MGD {kind} matches the {arche} claim's "
            f"{predicted.value:g} MGD prediction — corroborated evaporative; "
            f"upgrade source {claim_source} → document.{coc}"
        )
    return (
        f"Documented water ≈ 0 corroborates the {arche} dry claim — upgrade source "
        f"{claim_source} → document."
    )


def reconcile_facility(
    fac: SiteFacility,
    *,
    site: str,
    claim_source: str,
    claim_citation: str,
    settings: Settings,
    documented_makeup: ProvenancedValue | None = None,
    documented_blowdown: ProvenancedValue | None = None,
    reserved_makeup: ProvenancedValue | None = None,
    reserved_blowdown: ProvenancedValue | None = None,
    disclosed_makeup: ProvenancedValue | None = None,
    disclosed_ceiling: ProvenancedValue | None = None,
    nonprocess_makeup: ProvenancedValue | None = None,
    supplier_withdrawal: ProvenancedValue | None = None,
    route: WaterRoute | None = None,
    prediction_refused: str | None = None,
    seasonality_warm_ratio: float | None = None,
    corroborators: CoolingCorroborators | None = None,
    water_lead_ref: str = "#1688 (C2)",
    water_holder: str | None = None,
    kept_archetype: CoolingModelType | None = None,
    is_control: bool = False,
) -> ReconciliationRecord:
    """Reconcile one facility's cooling claim against its documented water account.

    Pure over its inputs: the predicted account comes from the pinned archetype (under
    ``settings`` — pass the facility's OWN site settings so a hybrid assist window reads its
    climatology, not the active site's), and the documented figures are injected (the cohort
    resolver reads them from A1/A2). Emits the outcome, a recommendation, and — for a gap or a
    reservation_conflict — a C2 lead payload. Recommends only; it never mutates ``fac.cooling_model``.

    ``reserved_makeup`` / ``reserved_blowdown`` (B1, #1681) are disclosed **reservation ceilings** (a
    will-serve / water-service agreement figure), kept distinct from the metered ``documented_*`` so a
    ceiling is never read as a use. A reservation disproportionate to a low-water claim is a
    ``reservation_conflict`` — it sharpens ``water_lead_ref`` (the site's standing water lead) and the
    C2 records request, but never licenses a re-archetype (a ceiling is not a discharge/withdrawal
    instrument). ``disclosed_makeup`` (B2, #1682) is an operator-DISCLOSED ongoing-use figure (a
    self-report — Van Wert's ~660k gal), kept distinct from BOTH: it never feeds the classifier and
    never upgrades the source (a self-report of the very claim under test is not an instrument), it
    only SHARPENS a gap — the lead names the specific open quantity (the initial closed-loop fill) and
    references ``water_lead_ref`` (Van Wert's #1409). ``disclosed_ceiling`` (B3, #1683) is a
    self-disclosed permit / withdrawal CEILING (Springfield's "up to 300,000 gal/day permitted" at an
    >80degF extreme-heat max) — a permitted PEAK ceiling from the claim's OWN source, NOT an
    independently-negotiated reservation, so — unlike ``reserved_*`` — it is not a demand signal that
    contradicts the claim and does NOT fire a ``reservation_conflict``: like ``disclosed_makeup`` it
    never feeds the classifier and never upgrades the source, it only SHARPENS a gap onto the
    actual-vs-ceiling denominator (``water_lead_ref`` = Springfield's #1415). ``kept_archetype`` is the site's REAL profile pin
    recorded on a reservation_conflict
    (the recommendation keeps it): pass it when ``fac`` is a constructed claim-under-test view whose
    ``cooling_model`` differs from the profile's (Troy-Piqua's real pin is ``unknown``); it defaults
    to ``fac.cooling_model`` when the facility passed IS the profile facility.

    ``nonprocess_makeup`` (B6, #1686) is a documented, metered withdrawal that is on record but is
    NOT the cooling account under test (Intel's construction-phase groundwater at New Albany) —
    kept distinct from ``documented_*`` because reading it as cooling makeup is a category error,
    not a conservative approximation. Like the self-report slots it never feeds the classifier.

    ``supplier_withdrawal`` (B4, #1684) is the documented withdrawal of the municipal **system**
    that supplies a route-blind facility — the only withdrawal A1 can reach once the supply route
    is municipal, because the registry meters the city and not its customers. It never feeds the
    classifier either (a system total aggregates every customer on it), and it is only valid
    alongside a cited municipal supply route. Its job is to give a ``route_blind`` a denominator:
    Urbana's campus is invisible to the registry, but the City of Urbana's own 1.76 MGD is not,
    and that is the scale any later disclosure has to be read against.

    ``route`` (B6, #1686) states whether A1 / A2 can reach this facility's water at all. A facility
    on purchased municipal supply and/or a POTW sanitary sewer is outside them, so their ~0 is an
    absence of jurisdiction rather than a measurement: an otherwise-``gap`` or
    ``corroborated``-on-two-zeros outcome becomes ``route_blind``, and the lead is re-aimed at the
    City-held record that can actually answer it. A *positive* documented or reserved signal still
    adjudicates — blindness invalidates a negative read, not a positive one.

    ``water_holder`` names the utility that actually meters a ``route_blind`` facility, for its
    records-request lead. It matters because a blind route is usually blind precisely because the
    supplier is not the site's own city, and a request filed with the wrong municipality is a
    wasted statutory clock.

    ``prediction_refused`` (B6, #1686) declines the archetype prediction outright, with the reason.
    Every archetype in :mod:`watermark.hydrology.cooling_models` is IT-load-parameterized, so a
    facility with no IT load (a semiconductor fab, whose cooling is driven by process heat) has no
    derivable account; running a data-center WUE against its electrical load would emit a number
    with no evidentiary basis. When set, the three ``predicted_*`` stay ``None``.

    ``corroborators`` (A4, #1680) are the two independent tells (air-permit cooling-tower PM +
    Tier II chemistry). Injected like the documented figures (the cohort resolver reads them via
    :func:`~watermark.hydrology.cooling_corroborators.resolve_corroborators`). They are SECONDARY:
    they sharpen the finding + the gap's records-request but NEVER change the classified ``outcome``.
    """
    it_load: ProvenancedValue | None = None
    predicted_makeup: ProvenancedValue | None = None
    predicted_consumptive: ProvenancedValue | None = None
    predicted_blowdown: ProvenancedValue | None = None
    if prediction_refused is None:
        basis = _predicted_basis(fac, settings)
        it_load = basis.it_load
        predicted_makeup = _require(basis.headline_makeup(), "predicted makeup")
        predicted_consumptive = _require(basis.headline_consumptive(), "predicted consumptive")
        predicted_blowdown = _predicted_blowdown(basis)

    # A disclosed/stated CoC is reference-grade, not a self-verified measurement — `cooling_models`
    # itself carries cycles as an assumption. `from_reference` keeps it honest (and the Intel
    # control's is a constructed calibration value, never a document about a real facility).
    disclosed_cycles = (
        ProvenancedValue.from_reference(
            fac.cycles_of_concentration,
            "ratio",
            citation=fac.cycles_citation or "disclosed cycles of concentration",
        )
        if fac.cycles_of_concentration is not None
        else None
    )
    # Back-solve CoC from the metered figures when both are on record; else from the reservation
    # ceilings (labeled as such) but ONLY when there is no documented signal at all — a documented
    # use adjudicates over a ceiling, so the two are never mixed and a discrepancy never carries a
    # reservation-derived CoC.
    if documented_makeup is not None and documented_blowdown is not None:
        backsolved_cycles = _backsolve_cycles(documented_makeup, documented_blowdown)
    elif (
        documented_makeup is None
        and documented_blowdown is None
        and reserved_makeup is not None
        and reserved_blowdown is not None
    ):
        backsolved_cycles = _backsolve_cycles(reserved_makeup, reserved_blowdown, kind="reserved")
    else:
        backsolved_cycles = None

    account = WaterAccount(
        archetype=fac.cooling_model,
        it_load=it_load,
        predicted_makeup=predicted_makeup,
        predicted_consumptive=predicted_consumptive,
        predicted_blowdown=predicted_blowdown,
        prediction_refused=prediction_refused,
        documented_makeup=documented_makeup,
        documented_blowdown=documented_blowdown,
        reserved_makeup=reserved_makeup,
        reserved_blowdown=reserved_blowdown,
        disclosed_makeup=disclosed_makeup,
        disclosed_ceiling=disclosed_ceiling,
        nonprocess_makeup=nonprocess_makeup,
        supplier_withdrawal=supplier_withdrawal,
        route=route,
        disclosed_cycles=disclosed_cycles,
        backsolved_cycles=backsolved_cycles,
        seasonality_warm_ratio=seasonality_warm_ratio,
    )

    outcome = _classify(
        fac.cooling_model,
        predicted_makeup.value if predicted_makeup is not None else None,
        predicted_blowdown.value if predicted_blowdown is not None else None,
        documented_makeup.value if documented_makeup is not None else None,
        documented_blowdown.value if documented_blowdown is not None else None,
        reserved_makeup.value if reserved_makeup is not None else None,
        reserved_blowdown.value if reserved_blowdown is not None else None,
        route,
    )

    recommended_archetype: str | None = None
    recommended_source: str | None = None
    kept_archetype_value: str | None = None
    lead: RecordsRequestLead | None = None
    if outcome is ReconcileOutcome.DISCREPANCY:
        # Re-archetype up: a summer-peak seasonality points at a continuously-evaporative tower;
        # otherwise recommend the evaporative upper bound and let B-review pin tower vs hybrid
        # with the instrument cited.
        recommended_archetype = CoolingModelType.EVAPORATIVE_TOWER.value
        recommended_source = "document"
        tag = "[verified]"  # a documented discharge is a [verified] record about the facility
        confidence: Confidence = "high"
    elif outcome is ReconcileOutcome.CORROBORATED:
        recommended_archetype = fac.cooling_model.value  # unchanged; the claim holds
        recommended_source = "document"
        tag = "[verified]"
        confidence = "high"
    elif outcome is ReconcileOutcome.RESERVATION_CONFLICT:
        # A disclosed reservation ceiling contradicts the low-water claim but is NOT a discharge/
        # withdrawal instrument — keep the archetype pin (no re-archetype recommendation), and
        # sharpen the site's standing water lead + the C2 records request for the instrument. The
        # kept pin is the site's REAL profile archetype (fac.cooling_model unless the caller passes
        # the real pin — Troy-Piqua's fac is a constructed closed_loop_dry view of an UNKNOWN pin).
        recommended_archetype = None
        recommended_source = None
        kept_archetype_value = (kept_archetype or fac.cooling_model).value
        lead = _reservation_conflict_lead(
            site, fac, claim_source, account, water_lead_ref, corroborators, water_holder
        )
        tag = "[open]"  # the conflict stays open; a ceiling is not [verified] proof of use
        confidence = (
            "medium"  # sharper than an empty gap (a quantified figure), short of instrument-grade
        )
    elif outcome is ReconcileOutcome.ROUTE_BLIND:
        # B6 (#1686): the harness's instruments cannot reach this facility's water, so it makes NO
        # recommendation about the archetype — the pin is kept and the ask is re-aimed at the
        # City-held record. The tag is [verified] because the blindness itself is an established
        # fact about the record (a searched absence of jurisdiction — Intel's ECHO record carries
        # only non-major construction general permits and no DMR), not an open question; what stays
        # [open] is the cooling account, which is what the lead is for.
        recommended_archetype = None
        recommended_source = None
        kept_archetype_value = (kept_archetype or fac.cooling_model).value
        lead = _route_blind_lead(
            site, fac, claim_source, account, water_lead_ref, corroborators, water_holder
        )
        tag = "[verified]"
        confidence = "high"
    else:  # GAP
        # Sharpen the gap's records request by what the claim's own source has self-disclosed. B3
        # (#1683): a self-disclosed permit CEILING (Springfield's 300k gal/day permitted max) names the
        # actual-vs-ceiling denominator (checked FIRST — Springfield discloses BOTH a ceiling and a
        # realistic draw). B2 (#1682): a disclosed ongoing draw (a self-report, not an instrument) names
        # the initial-fill open quantity + the site's standing water lead (Van Wert's #1409). Otherwise
        # the plain gap ask. A self-report never re-archetypes or upgrades — the pin stays [reference].
        if disclosed_ceiling is not None:
            lead = _disclosed_ceiling_gap_lead(
                site, fac, claim_source, account, water_lead_ref, corroborators
            )
        elif disclosed_makeup is not None:
            lead = _disclosed_gap_lead(
                site, fac, claim_source, account, water_lead_ref, corroborators
            )
        else:
            lead = _records_lead(site, fac, claim_source, corroborators)
        tag = "[open]"
        confidence = "low"

    return ReconciliationRecord(
        site=site,
        facility=fac.name,
        is_control=is_control,
        claimed_archetype=fac.cooling_model.value,
        claim_source=claim_source,
        claim_citation=claim_citation,
        account=account,
        outcome=outcome,
        recommended_archetype=recommended_archetype,
        recommended_source=recommended_source,
        kept_archetype=kept_archetype_value,
        lead=lead,
        corroborators=corroborators,
        tag=tag,
        confidence=confidence,
        finding=_fold_corroborators(
            _finding(outcome, fac, account, claim_source), outcome, corroborators
        ),
    )


# --------------------------------------------------------------------- the Intel control

# The openly-evaporative positive control (exemplar: Intel "Ohio One" / New Albany, ~125
# cooling towers). It is a CONSTRUCTED calibration vector built into the harness, internally
# consistent with an evaporative tower at CoC ≈ 5. The harness must classify it CORROBORATED
# (documented water matches the evaporative prediction), never a false DISCREPANCY.
#
# B6 (#1686) went looking for the real Intel record to ground this control and established that
# it CANNOT be grounded on Intel — see :func:`reconcile_intel_new_albany` for the three cited
# reasons. So the control stays constructed, deliberately and with the reason recorded: it is the
# harness's self-check, not a claim about Intel.
_INTEL_CITE = (
    "constructed calibration control (exemplar: Intel 'Ohio One' / New Albany, openly "
    "evaporative, ~125 cooling towers) — figures internally consistent with an evaporative "
    "tower at CoC≈5, NOT documented Intel data. B6 (#1686) tested whether the real Intel record "
    "could ground it and established it cannot (a pre-operational semiconductor fab, on purchased "
    "Columbus municipal water and the Columbus sanitary sewer, with no IT load to parameterize an "
    "archetype) — so this stays a constructed vector and the documented Intel row is reconciled "
    "separately as route_blind. The harness must classify this row corroborated-evaporative (the "
    "no-false-discrepancy gate)."
)
INTEL_CONTROL_FACILITY = SiteFacility(
    name="Intel evaporative control (New Albany)",
    status="confirmed",  # a disclosed facility is at least confirmed
    it_load_mw=150.0,
    it_load_low_mw=120.0,
    it_load_high_mw=180.0,
    it_load_citation=_INTEL_CITE,
    it_load_source="reference",
    cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
    cooling_model_source="reference",
    cooling_model_citation=_INTEL_CITE,
    wue_l_per_kwh=1.8,
    wue_citation=_INTEL_CITE,
    cycles_of_concentration=5.0,
    cycles_citation=_INTEL_CITE,
)
# Documented water for the control: an evaporative facility at ~150 MW / WUE 1.8 / CoC 5
# predicts ~2.14 MGD makeup and ~0.43 MGD blowdown; these documented figures land just above
# that (ratio ~1.05) — inside the corroboration band, back-solving CoC ≈ 4.9 (≈ the disclosed
# 5). The harness must corroborate, not flag over-cycling.
INTEL_DOCUMENTED_MAKEUP = ProvenancedValue.from_reference(2.2, "MGD", citation=_INTEL_CITE)
INTEL_DOCUMENTED_BLOWDOWN = ProvenancedValue.from_reference(0.45, "MGD", citation=_INTEL_CITE)
INTEL_SEASONALITY_WARM_RATIO = 1.6  # a temperature-driven summer peak — the evaporative shape

# The A4 corroborators for the control (#1680): an openly-evaporative facility with ~125 cooling
# towers has BOTH tells positive — its air permit lists the towers as PM (drift) sources and its
# Tier II inventory carries cooling-water treatment chemistry. Both CORROBORATE its evaporative
# claim (the no-false-contradiction direction). Constructed calibration values, NOT documented data.
INTEL_CORROBORATORS = CoolingCorroborators(
    air_permit=AirPermitCorroborator(
        state=AirPermitState.PM_SOURCE_LISTED,
        stance=CorroboratorStance.CORROBORATES,
        tower_count=125,
        pm10_tpy=13.0,
        pm25_tpy=4.5,
        citation=_INTEL_CITE,
        tag="[verified]",
        confidence="high",
        finding=(
            "Air permit lists ~125 cooling towers as permitted PM (drift) sources — corroborates the "
            "evaporative_tower claim (constructed calibration control, not documented Intel data)."
        ),
    ),
    tier2_chemistry=TierIIChemistryCorroborator(
        state=TierIIState.TREATMENT_PRESENT,
        stance=CorroboratorStance.CORROBORATES,
        chemicals=["biocide", "scale inhibitor", "corrosion inhibitor"],
        citation=_INTEL_CITE,
        tag="[verified]",
        confidence="high",
        finding=(
            "Tier II / EPCRA-312 inventory carries cooling-water treatment chemistry (biocide, scale "
            "/ corrosion inhibitor) — the evaporative-cycling signature (constructed calibration)."
        ),
    ),
    net_stance=CorroboratorStance.CORROBORATES,
    summary=(
        "Both independent corroborators are consistent with the evaporative_tower claim — the "
        "positive-control direction (no false contradiction)."
    ),
)


def intel_control(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Intel positive control, reconciled — the harness's calibration self-check.

    Evaporative_tower needs no climatology, so any settings resolves it; a fresh
    ``Settings()`` is used when none is passed so the control is standalone-runnable. Its A4
    corroborators (:data:`INTEL_CORROBORATORS`) are constructed positive — the calibration that an
    openly-evaporative facility's air permit + Tier II chemistry CORROBORATE its wet claim.
    """
    settings = settings or Settings()
    return reconcile_facility(
        INTEL_CONTROL_FACILITY,
        site="new-albany",
        claim_source=INTEL_CONTROL_FACILITY.cooling_model_source,
        claim_citation=_INTEL_CITE,
        settings=settings,
        documented_makeup=INTEL_DOCUMENTED_MAKEUP,
        documented_blowdown=INTEL_DOCUMENTED_BLOWDOWN,
        seasonality_warm_ratio=INTEL_SEASONALITY_WARM_RATIO,
        corroborators=INTEL_CORROBORATORS,
        is_control=True,
    )


# --------------------------------------------------------------------- documented-water read


def _site_settings(slug: str, base: Settings) -> Settings:
    """Fresh per-site ``Settings`` carrying the base run's offline flags.

    A fresh ``Settings(site=...)`` re-runs the profile-knob fill (so a hybrid facility's assist
    window reads its OWN site's climatology), which ``model_copy`` would skip. The offline
    knobs are propagated so a cohort run stays hermetic in tests / ``--offline``.
    """
    overrides: dict[str, Any] = {"site": slug}
    if base.hydro_offline:
        overrides["hydro_offline"] = True
    if base.hydro_fixtures_dir is not None:
        overrides["hydro_fixtures_dir"] = base.hydro_fixtures_dir
    return Settings(**overrides)


def _documented_water(
    candidate: blowdown.Candidate, settings: Settings
) -> tuple[ProvenancedValue | None, ProvenancedValue | None, float | None]:
    """Best-effort documented makeup / blowdown / seasonality for a cohort candidate.

    Wires the A1 + A2 seams; returns ``(None, None, None)`` for every live candidate today —
    the honest current state, which is itself the gap finding:

    * **Blowdown (A2)** comes from :func:`watermark.hydrology.blowdown.resolve_coverage`. With
      OHD000001 WITHDRAWN (2026-07-21) and no facility-own DMR on record, it is ``unknown`` → no
      documented blowdown. When a DMR relpath lands, this reads it.
    * **Makeup (A1)** would come from the Ohio DNR WWFRP registry, but that connector has only
      built Allen County and none of the closed-loop candidates report withdrawal there — so
      there is no documented makeup to read. The seam is left for a peer-county registry.

    The seams auto-activate when the records land; nothing is fabricated to look complete.
    """
    coverage = blowdown.resolve_coverage(candidate)
    documented_blowdown: ProvenancedValue | None = None
    seasonality_warm_ratio: float | None = None
    if (
        coverage.facility_own_discharge is blowdown.FacilityOwnDischarge.PRESENT
        and candidate.blowdown_dmr_relpath is not None
    ):
        # A facility-own DMR is on record — the forward seam. No live candidate reaches here yet;
        # reading the DMR flow magnitude + seasonality is left to the B-review that lands it, so
        # a value is never fabricated from an absent record.
        log.info(
            "cooling_reconcile.dmr_seam",
            site=candidate.site,
            facility=candidate.facility,
            relpath=candidate.blowdown_dmr_relpath,
        )
    return None, documented_blowdown, seasonality_warm_ratio


# ---------------------------------------------------- the Troy-Piqua B1 reservation conflict (#1681)

# Troy-Piqua ("Project Klondike") is the sharpest documented conflict in the cohort, and the reason
# the profile deliberately pins ``cooling_model=UNKNOWN``: the City's public FAQ claims closed-loop
# (dry) cooling, while the negotiated Water & Wastewater Agreement reserves up to 2.0 MGD makeup +
# ~1.0 MGD wastewater. Because the facility pins UNKNOWN it is NOT in A2's registry-derived cohort
# (:func:`blowdown.closed_loop_candidates`) — so B1 reconciles it as an explicit, cited case: the
# FAQ's closed_loop_dry CLAIM (a constructed dry-claim view, to get the ~0 prediction) against the
# disclosed reservation ceilings. The reservation is a will-serve ceiling from secondary summaries,
# NOT a metered use and NOT a discharge/withdrawal instrument — so the outcome is a
# ``reservation_conflict`` that keeps the UNKNOWN pin and sharpens lead #1486; it never re-archetypes.
_TROY_PIQUA_FAQ_CITE = (
    "[reference] the City of Piqua's public FAQ describes closed-loop cooling with only an "
    "'initial fill-up' + occasional top-offs (domestic-only ongoing use) — the low-water CLAIM under "
    "test here. The profile itself deliberately pins cooling_model=UNKNOWN (the FAQ-vs-reservation "
    "conflict is unresolved, lead #1486); this reconciliation TESTS the FAQ's dry framing, it does "
    "not adopt it. See data/extracted/troy-piqua/data-centers.md 'Water / hydrology hook'."
)
# The disclosed reservation ceilings — [verified] as SUMMARIES (Miami Valley Today; civiccapacity.com),
# but the executed 2026-01-23 agreement text is not yet in-corpus (a C2 pull target, #1486/#1688). A
# reserved CAPACITY, never a metered withdrawal/discharge; kept off the documented_* slots so it is
# never read as use.
# asof = the agreement's effective date — the dated instrument the reservation ceiling is anchored to.
_TROY_PIQUA_AGREEMENT_EFFECTIVE = "2026-01-23"
_TROY_PIQUA_RESERVED_MAKEUP = ProvenancedValue.from_reference(
    2.0,
    "MGD",
    citation=(
        "[verified summary] RESERVATION CEILING, not metered use: the negotiated City of Piqua Water "
        "& Wastewater Agreement (effective 2026-01-23) reserves up to 500,000 GPD (Tier I) scaling to "
        "2.0 MGD (Tier II / full operation) — ~30% of Piqua's ~6.75 MGD permitted intake. From "
        "secondary summaries (Miami Valley Today; civiccapacity.com); the executed agreement text is a "
        "C2 pull target (#1486/#1688). A reserved capacity ceiling, NOT a withdrawal record."
    ),
    confidence="high",
    asof=_TROY_PIQUA_AGREEMENT_EFFECTIVE,
)
_TROY_PIQUA_RESERVED_WASTEWATER = ProvenancedValue.from_reference(
    1.0,
    "MGD",
    citation=(
        "[verified summary] RESERVATION CEILING, not metered discharge: ~1.0 MGD reserved wastewater "
        "under the same Water & Wastewater Agreement (Miami Valley Today; civiccapacity.com) — a "
        "reserved capacity that bundles domestic sewage (so it OVER-states cooling blowdown and the "
        "back-solved CoC is a lower bound). Executed agreement text is a C2 pull target (#1486/#1688)."
    ),
    confidence="high",
    asof=_TROY_PIQUA_AGREEMENT_EFFECTIVE,
)


def reconcile_troy_piqua(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Troy-Piqua B1 reservation conflict (#1681) — FAQ closed-loop claim vs the 2.0 MGD reserve.

    Not a control (a real registered site with a real conflict) and not in A2's cohort (it pins
    ``UNKNOWN``): reconciled explicitly. The predicted ~0 water comes from a constructed
    ``closed_loop_dry`` VIEW of the real ``Project Klondike`` facility (the FAQ's claim under test),
    while the profile's actual ``UNKNOWN`` pin is what the recommendation keeps. Closed-loop-dry
    needs no climatology, so a per-site ``Settings`` resolves it; the reservation ceilings feed the
    ``reserved_*`` slots (never ``documented_*``) so a will-serve ceiling is not read as metered use.
    """
    base = settings or get_settings()
    site_settings = _site_settings("troy-piqua", base)
    profile = SITES["troy-piqua"]
    klondike = next((f for f in profile.facilities if f.name == "Project Klondike"), None)
    if klondike is None:  # pragma: no cover - the registered profile always carries this facility
        raise ValueError(
            "troy-piqua profile has no 'Project Klondike' facility — the B1 reservation conflict "
            "reconciles that facility's FAQ claim; the profile must register it (watermark.sites)"
        )
    # The FAQ CLAIM under test is closed_loop_dry; the profile itself stays UNKNOWN. model_copy keeps
    # the real IT-load bracket (so the ~0 dry prediction is derived from the facility's own load).
    faq_claim = klondike.model_copy(
        update={
            "cooling_model": CoolingModelType.CLOSED_LOOP_DRY,
            "cooling_model_source": "reference",
            "cooling_model_citation": _TROY_PIQUA_FAQ_CITE,
        }
    )
    return reconcile_facility(
        faq_claim,
        site="troy-piqua",
        claim_source="reference",
        claim_citation=_TROY_PIQUA_FAQ_CITE,
        settings=site_settings,
        reserved_makeup=_TROY_PIQUA_RESERVED_MAKEUP,
        reserved_blowdown=_TROY_PIQUA_RESERVED_WASTEWATER,
        corroborators=resolve_corroborators(faq_claim, settings=site_settings),
        water_lead_ref="#1486",
        kept_archetype=klondike.cooling_model,  # the real profile pin (UNKNOWN), kept as-is
        is_control=False,
    )


# ---------------------------------------------------- the Van Wert B2 disclosed-fill gap (#1682)

# Van Wert (the QTS "Van Wert Mega Site") pins ``closed_loop_dry`` as a [reference] operator/developer
# claim: "does not consume water for cooling once operational" (Danfoss-patented equipment). Unlike
# Troy-Piqua it IS in A2's registry-derived cohort (it pins ``closed_loop_dry``), but a plain gap
# undersells the record: the operator has DISCLOSED an ongoing draw (~660k gal, "about what 4
# households use per month"), and the SAME ~660k gal figure is framed elsewhere as a ONE-TIME initial
# fill — the unresolved #1409 fill-vs-annual discrepancy. B2 reconciles it explicitly so the disclosed
# figure is recorded (as a self-report, never a metered instrument) and the gap's lead names the
# specific open quantity (the initial closed-loop fill). Records A1 (no Van Wert County withdrawal
# built) + A2 (OHD000001 WITHDRAWN 2026-07-21, no facility-own DMR) are absent → the honest outcome
# stays a GAP with the [reference] pin KEPT, never silently promoted (the issue's acceptance). That
# A2 absence is permanent rather than pending: no general permit will ever supply the record, so on
# the NPDES path only an individual permit is left, and a campus on the City's sanitary sewer holds
# no NPDES permit at all — its disclosing instrument is the City's IU/pretreatment file (#1688).
#
# 660,000 gal/yr / 365 ≈ 1,808 gal/day ≈ 0.0018 MGD — below the ~0 screening floor, so the disclosed
# figure is consistent with a dry loop; but a single-source self-report cannot upgrade the source.
_VAN_WERT_DISCLOSED_MAKEUP = ProvenancedValue.from_reference(
    0.0018,
    "MGD",
    citation=(
        "[reference] operator-DISCLOSED ongoing draw — NOT a metered use and NOT a discharge/"
        "withdrawal instrument: QTS characterizes the campus's ongoing water use as 'about what 4 "
        "households use per month', and local press reports ~660,000 gal (≈0.0018 MGD annualized) — a "
        "SINGLE local-press source (thevwindependent.com; vanwert.org/water-treatment). Carried here as "
        "the annualized ongoing-draw reading to test the 'does not consume water once operational' "
        "claim; the SAME ~660,000 gal figure is elsewhere framed as a ONE-TIME initial fill (the "
        "2026-06-11 City-approved closed-loop fill) — that fill-vs-annual ambiguity is the unresolved "
        "#1409 discrepancy, not settled here. Self-reported (cannot upgrade the [reference] pin); the "
        "metered water-service use + the fill authorization are C2 pull targets (#1407/#1409/#1688)."
    ),
    confidence="low",  # a single-source self-report of the very claim under test
    asof="2026-06-11",  # the City-approved closed-loop fill event the figure is anchored to
)


def reconcile_van_wert(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Van Wert B2 disclosed-fill gap (#1682) — the "no water once operational" claim vs the record.

    A real registered site (not a control) that IS in A2's registry-derived cohort (it pins
    ``closed_loop_dry``), reconciled explicitly rather than through the generic cohort loop so its
    operator-disclosed ~660k gal figure is recorded (on ``disclosed_makeup`` — never ``documented_*``,
    a self-report is not a metered instrument) and its gap lead is sharpened onto the initial-fill open
    quantity (#1409). With no A1 withdrawal (Van Wert County is not built) and no A2 blowdown
    (OHD000001 WITHDRAWN 2026-07-21, no facility-own DMR), the honest outcome is a GAP that KEEPS the
    [reference] pin — the disclosed figure is consistent with a dry loop at screening scale but
    cannot upgrade the source. The A2 absence is permanent, not pending.
    Closed-loop-dry needs no climatology, so a per-site ``Settings`` resolves it.
    """
    base = settings or get_settings()
    site_settings = _site_settings("van-wert", base)
    profile = SITES["van-wert"]
    fac = next((f for f in profile.facilities if f.name == "Van Wert Mega Site"), None)
    if fac is None:  # pragma: no cover - the registered profile always carries this facility
        raise ValueError(
            "van-wert profile has no 'Van Wert Mega Site' facility — the B2 disclosed-fill gap "
            "reconciles that facility's closed-loop claim; the profile must register it (watermark.sites)"
        )
    return reconcile_facility(
        fac,
        site="van-wert",
        claim_source=fac.cooling_model_source or "reference",
        claim_citation=fac.cooling_model_citation or "[reference] operator closed-loop claim",
        settings=site_settings,
        disclosed_makeup=_VAN_WERT_DISCLOSED_MAKEUP,
        corroborators=resolve_corroborators(fac, settings=site_settings),
        water_lead_ref="#1409",
        is_control=False,
    )


# ---------------------------------------------------- the Springfield B3 disclosed-ceiling gap (#1683)

# Springfield (5C Data Centers "CMH01", anchor tenant Vultr) pins ``closed_loop_dry`` as a [reference]
# claim disclosed EXPLICITLY "not evaporative" by the City of Springfield 5C FAQ. Like Van Wert it IS
# in A2's registry-derived cohort (pins ``closed_loop_dry``), but a plain gap undersells the record: the
# SAME FAQ self-discloses a permitted municipal-withdrawal CEILING — "up to 300,000 gal/day" at an
# >80degF extreme-heat max, "near zero" most of the year, ~30k gal/day realistic. B3 reconciles it
# explicitly so both self-reported figures are recorded (the ceiling on ``disclosed_ceiling``, the
# realistic draw on ``disclosed_makeup`` — never ``documented_*`` or ``reserved_*``) and the gap lead
# names the actual-vs-ceiling denominator. A1 (no Clark County withdrawal built) + A2 (OHD000001
# WITHDRAWN 2026-07-21, no facility-own DMR) are absent → the honest outcome stays a GAP with the
# [reference] pin KEPT. The A2 absence is now PERMANENT rather than pending — no general permit will
# ever supply the blowdown record — which sharpens the C2 ask rather than closing it: on the NPDES
# path only an individual permit is left, and a campus discharging to the City's sanitary sewer holds
# no NPDES permit at all, so its disclosing instrument is the City's IU/pretreatment record (#1688).
#
# The pivotal B3 call (vs B1 Troy-Piqua): a permitted PEAK ceiling self-disclosed by the claim's OWN
# source is NOT a reservation_conflict. Troy-Piqua's 2.0 MGD was an independently-negotiated reservation
# (a demand signal SEPARATE from the dry FAQ, so it can contradict). Springfield's 300k gal/day is
# disclosed BY the "not evaporative" FAQ, framed as rarely approached — a dry loop sits far below it —
# so it belongs to the self-report family (``disclosed_*``, never feeds ``_classify``), not the
# reservation family (``reserved_*``). "A dry loop should sit far below it" is the issue's own framing.
#
# 300,000 gal/day = 0.3 MGD exactly (the permitted extreme-heat peak). ~30,000 gal/day = 0.03 MGD (the
# "realistic" ongoing draw). Even the permitted peak is far below what evaporative cooling at ~100-150
# MW would require (~1 MGD+), so the whole disclosed range is consistent with "not evaporative" — but
# it is all self-reported (from the very FAQ under test), so it cannot upgrade the [reference] pin.
_SPRINGFIELD_DISCLOSED_CEILING = ProvenancedValue.from_reference(
    0.3,
    "MGD",
    citation=(
        "[reference] SELF-DISCLOSED permit CEILING, not metered use and not a negotiated reservation: "
        "the City of Springfield 5C FAQ (springfieldohio.gov/5c-data-center-faqs) discloses 'up to "
        "300,000 gal/day' (0.3 MGD) permitted from the municipal system at an >80degF extreme-heat "
        "MAX, with use 'near zero' most of the year. A permitted PEAK ceiling from the SAME source that "
        "makes the 'not evaporative' closed-loop claim (so it cannot corroborate the claim without "
        "circularity), and a self-report rather than an independently-negotiated will-serve reservation "
        "(so it is not a reservation_conflict — a genuinely dry loop sits far below it). The actual "
        "metered municipal withdrawal against this ceiling is the missing measurement (C2, #1415/#1688)."
    ),
    confidence="high",  # a hard, well-attested permitted-max figure — but a ceiling, not metered use
)
# The FAQ's disclosed "realistic" ongoing draw (~30k gal/day), carried on ``disclosed_makeup`` as the
# ongoing self-report distinct from the peak ceiling. A soft estimate ("~30k realistic"), so medium
# confidence; ~0.03 MGD is trivial next to the ~1 MGD+ an evaporative tower at this load would draw.
_SPRINGFIELD_DISCLOSED_MAKEUP = ProvenancedValue.from_reference(
    0.03,
    "MGD",
    citation=(
        "[reference] operator-DISCLOSED 'realistic' ongoing draw — NOT a metered use: the City of "
        "Springfield 5C FAQ characterizes ongoing municipal-system use as ~30,000 gal/day (~0.03 MGD) "
        "'realistic' with 'near zero' most of the year, under the up-to-300,000 gal/day permitted peak "
        "ceiling. A self-report from the same source as the 'not evaporative' claim (cannot upgrade the "
        "[reference] pin); ~0.03 MGD is a small fraction of the ~1 MGD+ an evaporative tower at ~100-150 "
        "MW would draw — consistent with 'not evaporative', but unverified. Metered use is a C2 target."
    ),
    confidence="medium",
)


def reconcile_springfield(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Springfield B3 disclosed-ceiling gap (#1683) — "not evaporative" vs the 300k gpd ceiling.

    A real registered site (not a control) that IS in A2's registry-derived cohort (it pins
    ``closed_loop_dry``), reconciled explicitly rather than through the generic cohort loop so both of
    the City FAQ's self-reported figures are recorded — the permitted 300,000 gal/day peak CEILING on
    ``disclosed_ceiling`` and the ~30k gal/day "realistic" ongoing draw on ``disclosed_makeup`` (never
    ``documented_*`` (metered) or ``reserved_*`` (a negotiated reservation) — both are self-reports from
    the claim's own source). With no A1 withdrawal (Clark County is not built) and no A2 blowdown
    (OHD000001 WITHDRAWN 2026-07-21, no facility-own DMR), the honest outcome is a GAP that KEEPS the
    [reference] pin: a self-disclosed permit ceiling from the claim's own source is not a
    ``reservation_conflict`` (a dry loop sits far below it) and cannot corroborate the claim (that
    would be circular). The A2 absence is permanent, not pending — no general permit will ever
    supply the blowdown record — so the lead sharpens onto the actual-vs-ceiling denominator
    (#1415) and the City's own IU/pretreatment record (#1688), the instrument that discloses a
    sewer-discharging campus. Closed-loop-dry needs no climatology, so a per-site ``Settings``
    resolves it.
    """
    base = settings or get_settings()
    site_settings = _site_settings("springfield", base)
    profile = SITES["springfield"]
    fac = next((f for f in profile.facilities if f.name == '5C Data Centers "CMH01"'), None)
    if fac is None:  # pragma: no cover - the registered profile always carries this facility
        raise ValueError(
            "springfield profile has no '5C Data Centers \"CMH01\"' facility — the B3 disclosed-ceiling "
            "gap reconciles that facility's closed-loop claim; the profile must register it (watermark.sites)"
        )
    return reconcile_facility(
        fac,
        site="springfield",
        claim_source=fac.cooling_model_source or "reference",
        claim_citation=fac.cooling_model_citation or "[reference] operator closed-loop claim",
        settings=site_settings,
        disclosed_makeup=_SPRINGFIELD_DISCLOSED_MAKEUP,
        disclosed_ceiling=_SPRINGFIELD_DISCLOSED_CEILING,
        corroborators=resolve_corroborators(fac, settings=site_settings),
        water_lead_ref="#1415",
        is_control=False,
    )


# ------------------------------------- the Bowling Green B5 dry-cooler reservation conflict (#1685)

# Bowling Green pins ``closed_loop_dry`` on a claim more specific than any other in the cohort: Meta
# describes the campus as "closed-loop, liquid-cooled with DRY COOLERS", with "no operational water"
# and domestic/cleaning/fire use only. That is an architecture claim, not a vague "closed loop" —
# dry coolers reject heat to air through a sealed coil and evaporate nothing, so the claim predicts
# a genuinely ~0 cooling account and is squarely falsifiable by a withdrawal record. B5 (#1685) went
# looking for that record. What it found:
#
# 1. THE MAKEUP SIDE IS OUT OF A1's REACH, and this time the negative is corroborated by a positive
#    next door. No registration exists in Wood County under Meta, Liames LLC, "Project Accordion",
#    the Northwestern Water & Sewer District, or any data-center name — because the campus BUYS
#    finished water from NWWSD, which buys it wholesale from the City of Bowling Green, and the
#    WWFRP registers withdrawals from waters of the state, never a purchase. But "Apollo Power
#    Generation Facility - TEMP" (03717) registered a 0.27 MGD surface intake on 2026-03-26 in the
#    campus's OWN HUC-12 (041000100703). The register is demonstrably live at this site in 2026, so
#    Meta's non-appearance is a route, not a gap in coverage. The entire supply chain reduces to one
#    registered withdrawal in the county three transfers upstream: BOWLING GREEN CITY PWS (00251, 2,103.37 MG in
#    2024 ≈ 5.75 MGD from two Maumee intakes).
# 2. THE DISCHARGE SIDE IS A SEARCHED ABSENCE. A full ECHO CWA sweep of Wood County (FIPS 39173,
#    2026-08-01) returns 241 records and 50 EFFECTIVE individual NPDES permits, and not one of them
#    is the campus. Every campus-linked record — PROJECT ACCORDION (OHGC15219), APOLLO POWER
#    GENERATION FACILITY (OHGC17963), APOLLO LAYDOWN YARD (OHGC18721), APOLLO NORTH PIPELINE
#    (OHGC19094), ACCORDION-DOWLING 138KV INTERCONNECT (OHGC15929) — sits under the CONSTRUCTION
#    stormwater general permit (master OHC000000). There is no process-water outfall and no DMR.
#    With OHD000001 now WITHDRAWN (2026-07-21), no general permit will ever supply one either.
# 3. SO THE ONLY QUANTIFIED FIGURES ARE THE TWO THAT CONFLICT, and they conflict 12-fold. Meta's own
#    announcement says ~50,000 gpd; NWWSD-linked local coverage describes a design commitment of "up
#    to" ~600,000 gpd. #1439 recorded both and preferred neither, which was right, and B5 does not
#    resolve it either. What B5 establishes is that the architecture question does not WAIT on that
#    resolution: at the ~600,000 gpd end the figure is a demand signal disproportionate to "no
#    operational water" — a reservation_conflict — and the harness reaches that verdict without ever
#    having to decide which figure governs, because the conflict is with the CLAIM, not between the
#    figures.
#
# The discipline (B1's rule, #1681): a reservation ceiling is not a withdrawal or discharge
# instrument, so it CANNOT license a re-archetype however disproportionate it is. The pin stays
# closed_loop_dry at [reference]; the ask gets sharper.
_BOWLING_GREEN_LEAD_REF = "#1439"
# The NWWSD-linked ~600,000 gpd design commitment. A demand signal INDEPENDENT of the claim's own
# source (it is the district's service obligation, not Meta's characterization of its own cooling),
# which is what separates it from Springfield's self-disclosed ceiling (B3) and puts it in B1's
# reservation family, where it DOES feed the classifier. Confidence is medium, not high as at
# Troy-Piqua: this figure has a competing figure from the operator itself, and the executed
# instrument is in nobody's hands yet.
_BOWLING_GREEN_RESERVED_MAKEUP = ProvenancedValue.from_reference(
    0.6,
    "MGD",
    citation=(
        "[reference] RESERVATION CEILING, not metered use: local reporting and Northwestern Water & "
        "Sewer District-linked coverage describe a design commitment of 'up to' roughly 600,000 gpd "
        "(0.6 MGD) for the Meta campus, with a Meta-funded 2 MG storage tank and 16-inch main built "
        "to serve it. Independent of the cooling claim's own source (it is the DISTRICT's service "
        "obligation, not Meta's characterization of its own architecture), which is why it lands on "
        "reserved_makeup and not on the disclosed_* self-report slots. It CONFLICTS 12-fold with "
        "Meta's own announced ~50,000 gpd (carried on disclosed_makeup) — a conflict "
        "data/extracted/bowling-green/water-watch.yaml recorded and deliberately left unresolved "
        "(#1439), and which B5 does not resolve either. Neither the NWWSD-Meta service agreement nor "
        "the August 2024 City-NWWSD wholesale contract (ceiling raised to 1.5 MGD against ~860,000 "
        "gpd then actually purchased) is in-corpus; both are R.C. 149.43 targets (C2, #1688). A "
        "reserved capacity ceiling, NOT a withdrawal record. ⚠️ Do NOT read the Wood County "
        "registry as corroborating this figure: BOWLING GREEN CITY PWS (00251) reports a 2024 "
        "RETURN of 220.84 MG ≈ 0.605 MGD, which resembles it numerically and is unrelated to it — "
        "that is the water treatment plant's own filter-backwash and residuals, discharged under "
        "the plant's NPDES permit OH0030848 (McDowell WTP), and every reported year sits in the "
        "same 206-235 MG band with the earliest at 2016, before the campus existed."
    ),
    confidence="medium",  # a real demand signal, but with a competing operator figure and no instrument
)
# Meta's own announced figure. A self-report from the very source that makes the dry-cooler claim,
# so by B2's rule (#1682) it never feeds the classifier and never upgrades the pin — it is here to
# be the denominator the reservation is 12x of, and to be honest about what the operator has said.
_BOWLING_GREEN_DISCLOSED_MAKEUP = ProvenancedValue.from_reference(
    0.05,
    "MGD",
    citation=(
        "[reference] operator-DISCLOSED figure — NOT a metered use: Meta's own public announcement of "
        "the Bowling Green Data Center puts the campus's water demand at ~50,000 gpd (0.05 MGD), "
        "which the company presents as consistent with its dry-cooler claim (domestic, cleaning and "
        "fire-protection use rather than cooling). A self-report from the same source as the claim "
        "under test, so it cannot corroborate that claim without circularity and cannot upgrade the "
        "[reference] pin. Recorded because it is the denominator the ~600,000 gpd NWWSD-linked "
        "reservation is 12x of — the unresolved conflict at data/extracted/bowling-green/"
        "water-watch.yaml (#1439). NB neither figure can be settled by the physical works: a 2 MG "
        "tank and a 16-inch main are also exactly what FIRE-PROTECTION storage and flow look like at "
        "a campus of this size, and Meta's claim expressly reserves fire use, so the infrastructure "
        "is consistent with BOTH figures and discriminates neither."
    ),
    confidence="low",  # a single-source self-report of the very claim under test
)
_BOWLING_GREEN_ROUTE = WaterRoute(
    supply=SupplyRoute.MUNICIPAL,
    discharge=DischargeRoute.UNKNOWN,
    citation=(
        "[verified] The MAKEUP side is outside A1 by construction and the record shows it: the campus "
        "buys finished water from the Northwestern Water & Sewer District, which buys it wholesale "
        "from the City of Bowling Green, and the Ohio DNR WWFRP registers withdrawals FROM WATERS OF "
        "THE STATE (R.C. 1521.16, >100,000 gpd) — a purchased supply is the seller's withdrawal, not "
        "the buyer's. The Wood County registry (data/reference/ohio-water-withdrawal/wood.yaml, 36 "
        "facilities) accordingly carries NO registration under Meta, Liames LLC, 'Project Accordion', "
        "NWWSD, or any data-center name, while within the county the whole supply chain reduces to one registered "
        "withdrawal three transfers upstream: BOWLING GREEN CITY PWS (00251, 2,103.37 MG in 2024 "
        "≈ 5.75 MGD, two Maumee intakes). That absence is READABLE rather than merely empty because "
        "the register is demonstrably live at this site: 'Apollo Power Generation Facility - TEMP' "
        "(03717) registered a 0.27 MGD surface intake on 2026-03-26 in the campus's own HUC-12 "
        "041000100703, with no annual report due yet. The DISCHARGE side is UNKNOWN rather than "
        "established-to-sewer: an ECHO CWA sweep of Wood County (FIPS 39173, 2026-08-01) returns 241 "
        "records including 50 effective individual NPDES permits, none of them the campus — every "
        "campus-linked record (PROJECT ACCORDION OHGC15219, APOLLO POWER GENERATION FACILITY "
        "OHGC17963, APOLLO LAYDOWN YARD OHGC18721, APOLLO NORTH PIPELINE OHGC19094, "
        "ACCORDION-DOWLING 138KV INTERCONNECT OHGC15929) sits under the CONSTRUCTION stormwater "
        "general permit, master OHC000000. So there is verifiably no facility-own outfall and no DMR, "
        "but the corpus does not establish where process/sanitary flow actually GOES — no sewer-use "
        "or pretreatment instrument is in hand — and the honest value for a route the record has not "
        "established is unknown, not sanitary_sewer. The municipal supply alone is enough to blind "
        "the account. NB every identifier above is an OHIO key (Wood County FIPS 39173; Ohio DNR "
        "registrations; Ohio EPA NPDES), and both instruments are Ohio-statutory, so neither can "
        "return a Bowling Green, KENTUCKY record; the KY collision reaches only the press-sourced "
        "~50k/~600k figures, which is precisely where it must be watched."
    ),
    tag="[verified]",
    confidence="high",
)
# B6's lesson (#1686), and Bowling Green is the case that generalizes it past a single meter: the
# request has to go to TWO bodies, because the service agreement and the wholesale contract are held
# by different ones and either alone answers half the question.
_BOWLING_GREEN_WATER_HOLDER = (
    "Northwestern Water & Sewer District (the campus's water/sewer provider — the service agreement "
    "and the campus meter) AND the City of Bowling Green (the wholesale supplier — the August 2024 "
    "wholesale contract whose ceiling was raised to 1.5 MGD, and the WWFRP registrant of record). "
    "Neither alone holds both instruments: a request filed only with the City reaches the wholesale "
    "contract but not the campus's metered use, and one filed only with the District reaches the "
    "reverse"
)


def reconcile_bowling_green(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Bowling Green B5 dry-cooler reservation conflict (#1685).

    A real registered site (not a control) that IS in A2's registry-derived cohort (it pins
    ``closed_loop_dry``), reconciled explicitly rather than through the generic cohort loop so the
    two conflicting figures land on the slots their provenance earns: the NWWSD-linked ~600,000 gpd
    design commitment on ``reserved_makeup`` (independent of the claim's source, so it feeds
    ``_classify``) and Meta's own announced ~50,000 gpd on ``disclosed_makeup`` (a self-report, so it
    never does). Outcome is ``reservation_conflict``.

    Two things make this row different from its B-series peers. First, the CLAIM is unusually
    specific — "dry coolers" is an architecture that evaporates nothing, so the ~0 prediction is a
    real falsifiable statement rather than a vague low-water gesture. Second, the route is blind on
    the makeup side (purchased municipal supply) yet the outcome is NOT ``route_blind``: a
    reservation is a negotiated ceiling, not something A1 or A2 could have metered, so B1's finding
    survives the reach guard untouched. That ordering is deliberate and is what lets a blind-route
    site still produce a positive finding instead of collapsing into "we cannot see".

    The pin is KEPT at ``closed_loop_dry``/[reference]: a ceiling cannot license a re-archetype.
    """
    base = settings or get_settings()
    site_settings = _site_settings("bowling-green", base)
    profile = SITES["bowling-green"]
    name = "Bowling Green Data Center (Project Accordion)"
    fac = next((f for f in profile.facilities if f.name == name), None)
    if fac is None:  # pragma: no cover - the registered profile always carries this facility
        raise ValueError(
            f"bowling-green profile has no {name!r} facility — the B5 dry-cooler reconciliation "
            "reconciles that facility's closed-loop claim; the profile must register it "
            "(watermark.sites)"
        )
    return reconcile_facility(
        fac,
        site="bowling-green",
        claim_source=fac.cooling_model_source or "reference",
        claim_citation=fac.cooling_model_citation or "[reference] operator closed-loop claim",
        settings=site_settings,
        reserved_makeup=_BOWLING_GREEN_RESERVED_MAKEUP,
        disclosed_makeup=_BOWLING_GREEN_DISCLOSED_MAKEUP,
        route=_BOWLING_GREEN_ROUTE,
        corroborators=resolve_corroborators(fac, settings=site_settings),
        water_lead_ref=_BOWLING_GREEN_LEAD_REF,
        water_holder=_BOWLING_GREEN_WATER_HOLDER,
        is_control=False,
    )


# -------------------------------------------- the New Albany / Intel B6 positive control (#1686)

# B6 asked the harness to calibrate itself on the honest case: Intel discloses 125 cooling towers
# in its Ohio EPA air PTI, so an openly-evaporative facility should reconcile cleanly and prove the
# discrepancy findings on the closed-loop claimants are trustworthy. Pulling the record established
# that Intel cannot play that part — for three independent, cited reasons — and that the reason it
# cannot is a more useful calibration result than the one the issue expected.
#
# 1. It is NOT A DATA CENTER. Ohio One is a semiconductor fab (NAICS 334413). Every archetype in
#    `cooling_models` is IT-load-parameterized (load x WUE), and a fab's cooling is driven by
#    process heat, not by servers — so the harness has no derivable prediction for it, and a
#    makeup-per-MW band read off a fab and applied to a hyperscale campus would be a category
#    error. `SiteFacility.kind` admits `data_center` and `federal_installation` and neither fits,
#    which is why New Albany still carries no pinned facility: pinning Intel as a data center would
#    size a chip fab as a campus, the exact failure #1664 refuses at the type level.
# 2. It is NOT OPERATING. Mod 1 construction completes 2030 with operations 2030-31 (Mod 2 in
#    2032). The 125 towers are permitted, not running; there is no operating water account to
#    reconcile yet.
# 3. Its operating water is OUT OF REACH of both instruments the harness reads. Makeup will be
#    purchased City of Columbus municipal water (the WWFRP registers withdrawals from waters of the
#    state, so it never sees a purchased supply) and process wastewater goes to the Columbus
#    sanitary sewer (so no NPDES DMR exists). This is the transferable result: for a municipally
#    supplied, sewer-discharging facility, A1 and A2 return ~0 BY CONSTRUCTION, and the classifier
#    would have read that ~0 as "documented ≈ 0 → corroborated dry". The two operating Amazon Data
#    Services campuses registered in the same county demonstrate it — 0.02 MG and 0.00 MG reported
#    for all of 2024. Hence `WaterRoute` and the `route_blind` outcome.
_INTEL_NA_PTI_CITE = (
    "[verified] Ohio EPA Air Permit-to-Install issued 2022-09-20/21 for the Intel Ohio One campus "
    "lists 125 COOLING TOWERS among its emission units (with 4 fab cleanrooms, 28 boilers, 46 "
    "emergency generators, 1 fire pump, 6 silos, 4 N2 vaporizers) — an openly-disclosed "
    "evaporative heat-rejection architecture, the opposite of a closed-loop claim (WOSU/ideastream "
    "reporting of the PTI's emission-unit list, 2022-09; data/extracted/new-albany/data-centers.md "
    "§1). The permit itself is NOT ingested into the corpus, so the cooling pin is graded "
    "`reference`, not `document` — ingesting the PTI is part of this row's records ask."
)
_INTEL_NA_WWFRP_CITE = (
    "[verified] Ohio DNR WWFRP registration 03498 'Intel Corporation - New Albany, Ohio' "
    "(registered 2022-09-15; 7 ground-water wells, 1.43 MGD registered capacity; HUC12 "
    "050400060301 Headwaters Raccoon Creek — the Muskingum side, corroborated by the same HUC12 on "
    "the campus's ECHO watershed record): reported ground-water withdrawal 15.91 MG in 2024 "
    "(1.24 MG 2022, 11.43 MG 2023), annualized here as 15.91 MG / 366 d = 0.0435 MGD. "
    "data/reference/ohio-water-withdrawal/licking.yaml"
)
# The 2024 monthly series, folded on A2's May-Oct warm window: warm mean 1.522 MG, cool mean 1.130
# MG. The bare ratio reads mildly warm-peaked, but the shape underneath it does not: the peak month
# is MAY (3.02 MG) and the two hottest months are the year's lowest (JUL 0.94, AUG 0.72). A
# temperature-driven evaporative signature peaks in July-August. This is a spring/early-summer
# construction signal — which is a real limitation of the warm/cool ratio as a lone statistic, and
# the reason the shape is described here rather than carried on `seasonality_warm_ratio` (which is
# documented as the A2 DMR blowdown shape, not a withdrawal's).
_INTEL_NA_NONPROCESS = ProvenancedValue.from_reference(
    0.0435,
    "MGD",
    citation=(
        f"{_INTEL_NA_WWFRP_CITE} This is CONSTRUCTION-PHASE water, not cooling makeup: 14.11 MG of "
        "the 15.91 MG was RETURNED in 2024 (~89%, across 2 return points), the campus holds Ohio "
        "EPA hydrostatic-test-water general-permit coverage taken out by its construction "
        "contractor, and the monthly shape peaks in MAY (3.02 MG) while July (0.94) and August "
        "(0.72) are the year's lowest — the inverse of a temperature-driven evaporative signature "
        "(warm/cool ratio 1.35 on the May-Oct window, elevated by spring, not by heat). Recorded "
        "on nonprocess_makeup so it can never be read as the cooling account."
    ),
)
_INTEL_NA_DISCLOSED_MAKEUP = ProvenancedValue.from_reference(
    5.0,
    "MGD",
    citation=(
        "[reference] Intel's disclosed OPERATING draw for Ohio One — ~5 MGD of drinking water "
        "purchased from the CITY OF COLUMBUS (which would make Intel Columbus' largest single "
        "user), with 80-90% returned and process wastewater routed to on-site treatment then the "
        "Columbus SANITARY SEWER (Jackson Pike / Southerly), i.e. NO direct surface discharge "
        "(10tv/WOSU reporting; data/extracted/new-albany/data-centers.md §1). It is a self-reported "
        "PROJECTION for a facility that will not operate until 2030-31, not a metered figure — so "
        "it lands on disclosed_makeup, never documented_*, and cannot corroborate, contradict, or "
        "upgrade anything. It is also a FAB's total process+cooling water, not a data-center "
        "cooling account: do not divide it by MW and carry the quotient to a campus."
    ),
)
_INTEL_NA_ROUTE = WaterRoute(
    supply=SupplyRoute.MUNICIPAL,
    discharge=DischargeRoute.SANITARY_SEWER,
    citation=(
        "[verified] Both sides of Intel Ohio One's operating water account are outside the "
        "instruments this harness reads. MAKEUP: the disclosed operating supply is purchased City "
        "of Columbus municipal water, and the Ohio DNR WWFRP registers withdrawals FROM WATERS OF "
        "THE STATE (R.C. 1521.16) — a purchased supply is the seller's withdrawal, not the buyer's, "
        "so A1 can never meter it (registration 03498 records only the campus's own construction "
        "wells). DISCHARGE: process wastewater goes to the Columbus sanitary sewer, so no NPDES "
        "outfall and no DMR exists — a searched absence, not an unsearched one. Intel's entire CWA "
        "record in ECHO is three NON-MAJOR GENERAL-PERMIT coverages, all construction-phase: "
        "OHGC00904 'Intel Ohio Campus Project Cardinal' and OHGC18520 'Intel Site Tree Clearing' "
        "under the construction-stormwater general permit (master OHC000000), and OHGH00789 'Intel "
        "Ohio Site' under the hydrostatic-test-water general permit (master OHH000000) — which Ohio "
        "EPA's own coverage listing shows as 4GH00052*AG, 11511 Green Chapel Rd NW, applicant "
        "BECHTEL Manufacturing & Technology, Inc. (the general contractor), effective 2024-08-01. "
        "All three carry zero DMR pollutant loads and no effluent limits; there is no individual "
        "industrial NPDES permit and no cooling-water outfall."
    ),
    tag="[verified]",
    confidence="high",
)
_INTEL_NA_PREDICTION_REFUSED = (
    "Ohio One is a semiconductor fab (NAICS 334413), not a data center: its heat rejection is "
    "driven by fab process load, and every archetype in watermark.hydrology.cooling_models is "
    "parameterized on IT load x WUE (L/kWh), a data-center metric. The campus discloses a ~100+ MW "
    "continuous ELECTRICAL load, which is not an IT load — running a data-center WUE against it "
    "would emit a cooling-makeup figure with no evidentiary basis for a fab. The prediction is "
    "refused rather than fabricated; the disclosed architecture (125 evaporative cooling towers) is "
    "carried as the claim, and the water account stays [open]."
)
_INTEL_NA_CORROBORATORS = CoolingCorroborators(
    air_permit=AirPermitCorroborator(
        state=AirPermitState.PM_SOURCE_LISTED,
        stance=CorroboratorStance.CORROBORATES,
        tower_count=125,
        citation=_INTEL_NA_PTI_CITE,
        tag="[verified]",
        # The emission-unit list is a cited public record, but it reaches us through reporting
        # rather than the ingested permit, and no PM figures are transcribed — medium, not high.
        confidence="medium",
        finding=(
            "The campus's own Ohio EPA air PTI lists 125 cooling towers as permitted emission "
            "units — an openly evaporative architecture. It CORROBORATES the evaporative claim, "
            "and it is the reason B6 expected a clean positive control. It cannot supply one: an "
            "air permit is not a discharge/withdrawal instrument, and a permitted tower at a "
            "pre-operational fab is not a water account."
        ),
    ),
    tier2_chemistry=TierIIChemistryCorroborator(
        state=TierIIState.NOT_ON_RECORD,
        stance=CorroboratorStance.SILENT,
        citation=(
            "[open] No Tier II / EPCRA-312 inventory is on record for the campus — the filings are "
            "SERC/LEPC-held and never appear on ECHO. For a facility not yet operating its towers, "
            "an absence of cooling-water treatment chemistry is expected and carries no signal."
        ),
        tag="[open]",
        confidence="low",
        finding=(
            "No Tier II / EPCRA-312 cooling-chemistry filing on record (SERC/LEPC-held) — silent, "
            "as expected for a pre-operational campus."
        ),
    ),
    net_stance=CorroboratorStance.CORROBORATES,
    summary=(
        "The air permit independently corroborates the evaporative architecture (125 permitted "
        "cooling towers); Tier II is silent. Corroborators are SECONDARY and do not change the "
        "outcome — an openly disclosed evaporative design still leaves the water account "
        "unreachable, which is precisely the point the control was supposed to test."
    ),
)
# The claim under test, as a constructed view — New Albany pins no SiteFacility (see the block
# comment above for why a fab cannot be one today), so B6 reconciles Intel as an explicit cited
# case, the pattern reconcile_troy_piqua established for a facility outside A2's registry cohort.
INTEL_NEW_ALBANY_FACILITY = SiteFacility(
    name='Intel "Ohio One" (Jersey Township)',
    status="construction",  # [verified] under construction; Mod 1 ops 2030-31, Mod 2 2032
    operator="Intel Corporation",
    operator_citation=(
        "[verified] Intel Corporation, ~1,000-acre Ohio One megasite in Jersey Township, Licking "
        "County (Johnstown / New Albany mailing address 11511 Green Chapel Rd NW); $28B (raised "
        "from $20B in March 2024), up to 8 fabs, Mod 1 + Mod 2 (Intel Newsroom; "
        "data/extracted/new-albany/data-centers.md §1)"
    ),
    cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
    cooling_model_source="reference",
    cooling_model_citation=_INTEL_NA_PTI_CITE,
)
# New Albany's own onboarding/pin issue — where the campus's primary instruments (the air PTI, the
# recorder deeds, the NPDES coverage) are tracked.
_INTEL_NA_LEAD_REF = "#485"
# The utility that actually meters the campus is two counties from its mailing address — which is
# the whole reason A1/A2 are blind here, and the reason a request filed with New Albany would miss.
_INTEL_NA_WATER_HOLDER = (
    "City of Columbus, Department of Public Utilities (Division of Water + Division of Sewerage "
    "and Drainage) — the campus's disclosed municipal supplier AND the POTW receiving its process "
    "wastewater (Jackson Pike / Southerly)"
)


def reconcile_intel_new_albany(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The DOCUMENTED New Albany / Intel row — the B6 (#1686) positive control, as the record has it.

    Peer of :func:`reconcile_troy_piqua` / :func:`reconcile_van_wert` / :func:`reconcile_springfield`
    and NOT a control row (``is_control=False``): this is a real site's real record, reconciled.
    The constructed calibration vector stays separately at :func:`intel_control`.

    Outcome is ``route_blind``. The block comment above carries the three cited reasons; the short
    form is that Intel discloses the wet architecture openly (125 permitted cooling towers) and
    still cannot be reconciled, because the campus is pre-operational, is not a data center, and
    buys its water from Columbus while discharging to Columbus' sewer — putting both sides of its
    account outside A1 and A2. The row exists to make that visible: it records what the instruments
    DO show (0.0435 MGD of construction-phase groundwater, ~89% returned, peaking in May), states
    that this is not the cooling account, and re-aims the records request at the City meter.
    """
    settings = settings or Settings()
    return reconcile_facility(
        INTEL_NEW_ALBANY_FACILITY,
        site="new-albany",
        claim_source=INTEL_NEW_ALBANY_FACILITY.cooling_model_source,
        claim_citation=INTEL_NEW_ALBANY_FACILITY.cooling_model_citation,
        settings=_site_settings("new-albany", settings),
        nonprocess_makeup=_INTEL_NA_NONPROCESS,
        disclosed_makeup=_INTEL_NA_DISCLOSED_MAKEUP,
        route=_INTEL_NA_ROUTE,
        prediction_refused=_INTEL_NA_PREDICTION_REFUSED,
        corroborators=_INTEL_NA_CORROBORATORS,
        water_lead_ref=_INTEL_NA_LEAD_REF,
        water_holder=_INTEL_NA_WATER_HOLDER,
    )


# ------------------------------------------- the Urbana B4 route-blind origin claim (#1684)

# Urbana is where this whole pattern started. In February 2026 the developer of the "Urbana
# Technology Hub" told a City of Urbana meeting the campus would use closed-loop cooling with water
# use "comparable to a standard office building" — and that sentence is what took the Mad River
# buried-valley abstraction thesis off the table for this site (#1327/#1330), then propagated as a
# framing to Van Wert, Springfield, Troy-Piqua and Bowling Green. B4 (#1684) asks what the record
# can actually say about it. The answer has three parts, and only the third is a surprise.
#
# 1. THE CLAIM CARRIES NO NUMBER. Every other B-site disclosed a quantity to argue with — Troy-
#    Piqua's 2.0 MGD reservation (B1), Van Wert's ~660k gal (B2), Springfield's 300k gal/day
#    ceiling (B3). Urbana disclosed a COMPARISON. There is nothing to put on `disclosed_makeup`,
#    because a simile is not a self-reported figure; it is a claim about which order of magnitude
#    the campus belongs to, and the two candidate readings are three orders apart.
# 2. THE INSTRUMENTS CANNOT REACH IT — the B6 (#1686) result, and here it is established on a
#    stronger instrument than New Albany's. The City's own Pre-Annexation Agreement (Ord. 4612-24
#    Exh. A) makes providing "water and sewer" a City duty and makes the FAILURE to provide it a
#    trigger for de-annexation, and the companion statement-of-services ordinance (4613-24,
#    R.C. 709.023) passed the same night. A campus on City water withdraws nothing from waters of
#    the state, so A1 never sees it; a campus on the City sewer files no DMR, so A2 never sees it.
#    The Champaign County registry confirms the consequence: 31 registrations, not one of them the
#    campus. The campus is also not built, so no meter reading exists anywhere yet.
# 3. THE SUPPLIER IS ON RECORD EVEN THOUGH THE FACILITY IS NOT — and that is what makes this row
#    something other than a shrug. The City of Urbana's public water system reported 1.76 MGD in
#    2024. An evaporative read of this same campus, at its own [inference] screening IT load,
#    would draw 0.49-1.64 MGD: between a quarter and substantially all of what the City withdrew
#    in a year. The claim's own reading is below the harness's 0.01 MGD noise floor. So the
#    untested question is not academic — it is the difference between a rounding error on the
#    City's system and a second City-sized demand on the same buried-valley aquifer, and the only
#    party holding the record that settles it is the City that is currently being sued by the
#    developer. Hence `supplier_withdrawal`: not the facility's water, but the scale of it.
_URBANA_FACILITY_NAME = "Urbana Technology Hub"
_URBANA_ROUTE = WaterRoute(
    supply=SupplyRoute.MUNICIPAL,
    discharge=DischargeRoute.SANITARY_SEWER,
    citation=(
        "[verified] Both sides of the Urbana Technology Hub's water account are outside the "
        "instruments this harness reads, on the CITY'S OWN legislative record. MAKEUP: Ordinance "
        "4612-24 (passed 5-0, 2024-12-17) authorized a Pre-Annexation Agreement with Urbana0624C, "
        "LLC — which the City's own public notice identifies as 'Highland' — under which the City "
        "must 'provide water and sewer' to the property, and whose section 3(c) makes the failure "
        "to make 'water and sewer capacity ... available to satisfy the Developer's schedule' a "
        "trigger for de-annexing the entire property on demand; the companion statement-of-services "
        "ordinance 4613-24 (R.C. 709.023) passed 5-0 the same night, and the territory was annexed "
        "by Ord. 4619-25. A campus supplied by the City withdraws nothing itself, and the Ohio DNR "
        "WWFRP registers withdrawals FROM WATERS OF THE STATE (R.C. 1521.16) — so A1 can never "
        "meter it. The registry bears that out as a SEARCHED absence: none of the 31 WWFRP "
        "registrations in Champaign County is the campus, Thor Equities, Highland55, or Urbana "
        "Owner (data/reference/ohio-water-withdrawal/champaign.yaml). DISCHARGE: the same City "
        "duty routes wastewater to the City of Urbana Water Reclamation Facility (NPDES "
        "OH0027880 / Ohio EPA 1PD00011, 4.5 MGD design, outfall 001 to the Mad River), so the "
        "campus has no outfall of its own and files no DMR — ECHO's 21-facility Champaign County "
        "CWA inventory carries no permit at the SR-55/US-68 site. What WOULD record a cooling "
        "discharge is the City's OEPA-audited industrial pretreatment program (an IU permit; the "
        "program's own 2025-09-09 Pretreatment Compliance Inspection and 2025-10-07 pretreatment "
        "SNC Notice of Violation are in corpus at data/documents/oepa/urbana/), and ECHO never "
        "carries those. NB the campus is also NOT BUILT — its Feb-2026 site plan was denied as "
        "'incomplete', a 12-month emergency moratorium (Res. 2727-26) is in force, and the zoning "
        "is in federal litigation (Thor v. City of Urbana, S.D. Ohio 3:26-cv-00196) — so what the "
        "request seeks is the service and capacity record that exists now (will-serve, capacity "
        "analysis, IU pre-application), not a historical meter. Sources: data/documents/urbana/council/"
        "2024-11-19_regular_meeting_packet.pdf (Ord. 4612-24 Exh. A); "
        "data/extracted/urbana/incentive-instruments.yaml."
    ),
    tag="[verified]",
    confidence="high",
)
# 644.99 MG (2024, WWFRP registration 00837) / 366 days = 1.7623 MGD. The City's second plant
# (03719, SR-29 W) has filed no annual report, so this is the whole reported system draw.
_URBANA_SUPPLIER_WITHDRAWAL = ProvenancedValue.from_reference(
    1.7623,
    "MGD",
    citation=(
        "[verified] The SUPPLIER'S account, not the facility's: the City of Urbana's public water "
        "system reported 644.99 MG of ground water in 2024 on Ohio DNR WWFRP registration 00837 "
        "'URBANA CITY PWS OTP' (Old Troy Pike, 6 wells, 5.76 MGD registered capacity) — 644.99 MG "
        "/ 366 d = 1.7623 MGD, the county's second-largest reported withdrawal after an "
        "agricultural irrigator. The City's second plant, registration 03719 'URBANA CITY PWS 29 "
        "WTP' (2047 State Rte 29 W, 3 wells, 3.00 MGD registered, registered 2026-03-26), has "
        "filed no annual report yet, so registered capacity totals 8.76 MGD against 1.76 MGD "
        "reported; both plants draw the same high-yield buried-valley aquifer. Do NOT read the "
        "2026 registration as capacity added for the campus — the SR-29 plant is a long-standing "
        "City facility carrying its own NPDES permit (OH0137618, effective, expiring 2027-12-31), "
        "so the registration date is a registry event whose occasion is [open]. This figure is a "
        "SYSTEM total across every customer: it can neither corroborate nor contradict the "
        "campus's cooling claim, and is carried only as the denominator the claim has to be read "
        "against. That comparison is the B4 finding. At the campus's [inference] screening IT-load "
        "bracket (34.5 / 74.8 / 115 MW, from 460,000 sq ft) the evaporative reference band in this "
        "artifact's meta (0.0143 MGD makeup per IT-MW) implies 0.49 / 1.07 / 1.64 MGD — 28% / 61% "
        "/ 93% of everything the City withdrew in 2024 — while the 'comparable to a standard "
        "office building' reading sits below this harness's 0.01 MGD noise floor. Three orders of "
        "magnitude, and no instrument on either side of the account can tell them apart. Source: "
        "data/reference/ohio-water-withdrawal/champaign.yaml (Ohio DNR WWFRP, R.C. 1521.16)."
    ),
    confidence="high",
    asof="2024-12-31",  # the reporting year the annual total closes on
)
# The holder that actually meters this campus. Unlike New Albany — where the meter belongs to
# Columbus, two counties from the site's own address (B6) — Urbana's holder IS the site's own city,
# on both sides: the Water Division for the makeup meter, the Industrial Pretreatment Program (its
# coordinator is the named OEPA-audited contact) for the IU permit that would carry blowdown. Worth
# stating, because it is also the City currently being sued by the developer over this project.
_URBANA_WATER_HOLDER = (
    "City of Urbana — Water Division (205 S Main St; the metered water-service consumption and any "
    "will-serve / capacity analysis for the campus) and the City's Industrial Pretreatment Program "
    "coordinator at the Water Reclamation Facility (the IU permit + sewer-use agreement that would "
    "carry cooling blowdown; the program is OEPA-audited annually)"
)
# Urbana's standing water lead. Named as the issue AND the leads-board id, because the issue closes
# when this lands while the ask does not: URB-WATER-METER on `data/site/urbana/leads.yaml` is the
# durable thread. (#1330, which recorded the closed-loop disclosure as having undercut the
# abstraction thesis, is already closed and is deliberately not cited as a live lead.)
_URBANA_LEAD_REF = "#1684 / lead URB-WATER-METER"


def reconcile_urbana(*, settings: Settings | None = None) -> ReconciliationRecord:
    """The Urbana B4 route-blind origin claim (#1684) — "comparable to a standard office building".

    Peer of :func:`reconcile_van_wert` / :func:`reconcile_springfield`: a real registered site (not
    a control) that IS in A2's registry-derived cohort (it pins ``closed_loop_dry``), reconciled
    explicitly rather than through the generic loop so its route and its supplier's withdrawal are
    carried. The outcome is ``route_blind``, not ``gap`` — the difference matters here more than
    anywhere else in the cohort, because a ``gap`` reads as an unfinished lookup, and no amount of
    pulling A1/A2 harder can finish this one: the City's own Pre-Annexation Agreement puts the
    campus on City water and City sewer, which is precisely where neither instrument looks.

    What keeps it from being a bare negative is ``supplier_withdrawal``. The campus is absent from
    the Champaign County registry, but its supplier is not — the City of Urbana reported 1.76 MGD
    in 2024 — and an evaporative read of the same campus at its screening load would draw
    0.49-1.64 MGD against that. The pin stays ``closed_loop_dry`` / ``[reference]`` (nothing here
    is an instrument about the facility), the claim stays untested, and the ask goes to the City.
    Closed-loop-dry needs no climatology, so a per-site ``Settings`` resolves it.
    """
    base = settings or get_settings()
    site_settings = _site_settings("urbana", base)
    profile = SITES["urbana"]
    fac = next((f for f in profile.facilities if f.name == _URBANA_FACILITY_NAME), None)
    if fac is None:  # pragma: no cover - the registered profile always carries this facility
        raise ValueError(
            f"urbana profile has no {_URBANA_FACILITY_NAME!r} facility — the B4 route-blind "
            "reconciliation tests that facility's closed-loop claim; the profile must register it "
            "(watermark.sites)"
        )
    return reconcile_facility(
        fac,
        site="urbana",
        claim_source=fac.cooling_model_source or "reference",
        claim_citation=fac.cooling_model_citation or "[reference] developer closed-loop claim",
        settings=site_settings,
        supplier_withdrawal=_URBANA_SUPPLIER_WITHDRAWAL,
        route=_URBANA_ROUTE,
        corroborators=resolve_corroborators(fac, settings=site_settings),
        water_lead_ref=_URBANA_LEAD_REF,
        water_holder=_URBANA_WATER_HOLDER,
        is_control=False,
    )


# --------------------------------------------------------------------- cohort


def reconcile_cohort(*, settings: Settings | None = None) -> list[ReconciliationRecord]:
    """Reconcile every closed-loop cohort facility + the Intel positive control.

    The cohort is A2's registry-derived closed-loop set (:func:`blowdown.closed_loop_candidates`
    — every ``SiteFacility`` pinning ``closed_loop_dry`` / ``hybrid_adiabatic``). Each facility
    is derived under its OWN site's settings so a cross-site cohort never leaks the active site's
    climatology, and its A4 corroborators (:func:`cooling_corroborators.resolve_corroborators`) are
    resolved under the same settings. The **Troy-Piqua B1 reservation conflict** (#1681,
    :func:`reconcile_troy_piqua`) is appended explicitly — it pins ``UNKNOWN`` so it is NOT in A2's
    cohort, but its FAQ-vs-2.0-MGD-reservation conflict is reconciled as a first-class live finding.
    **Van Wert** (#1682, :func:`reconcile_van_wert`), **Springfield** (#1683,
    :func:`reconcile_springfield`) and **Urbana** (#1684, :func:`reconcile_urbana`) ARE in A2's cohort
    but are reconciled explicitly (skipped in the generic loop) so what the record holds for each is
    carried — Van Wert's operator-disclosed ~660k gal draw + the #1409 initial-fill open quantity,
    Springfield's self-disclosed 300k gal/day permitted ceiling + the #1415 actual-vs-ceiling
    denominator for its "not evaporative" claim, and Urbana's municipal route (cited to the City's own
    Pre-Annexation Agreement) + its supplier's 1.76 MGD, which turns the origin claim's row from a gap
    into a quantified ``route_blind``. **Bowling Green**
    (#1685, :func:`reconcile_bowling_green`) is likewise a cohort member reconciled explicitly, but its
    figures split across two families: the NWWSD-linked ~600,000 gpd design commitment is an
    independent reservation (so it classifies) while Meta's own announced ~50,000 gpd is a self-report
    (so it does not), and the 12-fold conflict between them is #1439's, left unresolved. **New Albany /
    Intel** (#1686, :func:`reconcile_intel_new_albany`) is appended as a live (non-control) row: the
    campus pins no ``SiteFacility`` at all, so it is in no cohort, and its record is what B6
    established when it went looking for a documented positive control — ``route_blind``. The
    constructed Intel control is appended last and reconciled the same way. Ordered by (is_control,
    site, facility) so the control sorts after the live findings.
    """
    settings = settings or get_settings()
    records: list[ReconciliationRecord] = []
    for candidate in blowdown.closed_loop_candidates(settings=settings):
        # Van Wert (B2, #1682), Springfield (B3, #1683), Urbana (B4, #1684) and Bowling Green
        # (B5, #1685) are cohort members but are reconciled explicitly below so what the record
        # actually holds for each is carried — Van Wert's ~660k gal draw + #1409 initial-fill,
        # Springfield's 300k gal/day permitted ceiling + #1415, Urbana's cited municipal route +
        # its supplier's withdrawal, Bowling Green's NWWSD-linked ~600k gpd reservation against
        # Meta's own ~50k gpd + #1439 — skip the generic gap here to avoid a double row.
        if candidate.site in {"van-wert", "springfield", "urbana", "bowling-green"}:
            continue
        profile = SITES[candidate.site]
        fac = next((f for f in profile.facilities if f.name == candidate.facility), None)
        if fac is None:  # pragma: no cover - the candidate list is built from these facilities
            continue
        site_settings = _site_settings(candidate.site, settings)
        makeup, blowdown_pv, warm_ratio = _documented_water(candidate, settings)
        records.append(
            reconcile_facility(
                fac,
                site=candidate.site,
                claim_source=candidate.cooling_source,
                claim_citation=candidate.cooling_citation,
                settings=site_settings,
                documented_makeup=makeup,
                documented_blowdown=blowdown_pv,
                seasonality_warm_ratio=warm_ratio,
                corroborators=resolve_corroborators(fac, settings=site_settings),
            )
        )
    records.append(
        reconcile_van_wert(settings=settings)
    )  # B2 (#1682) — disclosed ~660k gal + #1409 initial-fill gap
    records.append(
        reconcile_springfield(settings=settings)
    )  # B3 (#1683) — disclosed 300k gal/day permitted ceiling + #1415 "not evaporative" gap
    records.append(
        reconcile_urbana(settings=settings)
    )  # B4 (#1684) — the origin claim: route_blind on the City's own instruments + its denominator
    records.append(
        reconcile_bowling_green(settings=settings)
    )  # B5 (#1685) — NWWSD-linked ~600k gpd reservation vs the "dry coolers" claim
    records.append(
        reconcile_troy_piqua(settings=settings)
    )  # B1 (#1681) — pins UNKNOWN, not in A2's cohort
    records.append(
        reconcile_intel_new_albany(settings=settings)
    )  # B6 (#1686) — the documented Intel record: route_blind, and why the control stays constructed
    records.append(intel_control(settings=settings))
    records.sort(key=lambda r: (r.is_control, r.site, r.facility))
    log.info(
        "cooling_reconcile.cohort_resolved",
        facilities=len(records),
        outcomes={o.value: sum(1 for r in records if r.outcome is o) for o in ReconcileOutcome},
    )
    return records


# ------------------------------------------------------- the cross-site reference band (B6, #1686)

# The IT load the band is normalized on. Arbitrary and cancelled out by the division — it exists
# only so the archetype's own derivation runs; the emitted figures are per-MW.
_BAND_NORMALIZING_LOAD_MW = 100.0


class ReferenceBand(BaseModel):
    """The per-IT-MW evaporative water band the cohort's claims are measured against (B6, #1686).

    B6 was asked to record "makeup, blowdown, CoC per MW for disclosed evaporative hyperscale" from
    the Intel positive control, so a closed-loop claimant could be compared against a known-honest
    evaporative site. **Intel cannot supply it.** Ohio One is a semiconductor fab whose ~5 MGD
    disclosed draw is fab process water at a facility that will not operate until 2030-31; dividing
    that by its electrical MW and carrying the quotient to a data-center campus would be a category
    error that then propagates into every comparison the band exists to support.

    So the band is emitted from the ``evaporative_tower`` **archetype spec's own defaults** —
    a screening ``[inference]``, explicitly NOT a disclosure by any facility and not Intel-derived.
    It is the same derivation the harness already runs against every pinned facility, normalized
    per IT-MW so it can be quoted cross-site.
    """

    model_config = ConfigDict(extra="forbid")

    basis: str  # what the band IS (the archetype spec), in one line
    makeup_mgd_per_mw: float
    consumptive_mgd_per_mw: float
    blowdown_mgd_per_mw: float
    cycles_of_concentration: float
    wue_l_per_kwh: float
    tag: str
    confidence: Confidence
    citation: str
    # Why the band is archetype-derived rather than read off the disclosed positive control.
    not_derived_from: str


def reference_band(*, settings: Settings | None = None) -> ReferenceBand:
    """The archetype-derived per-IT-MW evaporative band (B6, #1686) — never Intel-derived."""
    settings = settings or Settings()
    # The archetype's OWN defaults: a bare facility with no disclosed WUE / CoC override, so
    # `cooling_models` supplies its cited generic values rather than any site's disclosure.
    normalizing = SiteFacility(
        name="evaporative-tower reference band (normalizing facility)",
        status="confirmed",
        it_load_mw=_BAND_NORMALIZING_LOAD_MW,
        it_load_low_mw=_BAND_NORMALIZING_LOAD_MW,
        it_load_high_mw=_BAND_NORMALIZING_LOAD_MW,
        it_load_citation=(
            "a normalizing IT load for the per-MW reference band — not a disclosed load for any "
            "facility; it cancels out of the emitted per-MW figures"
        ),
        it_load_source="reference",
        cooling_model=CoolingModelType.EVAPORATIVE_TOWER,
        cooling_model_source="reference",
        cooling_model_citation=(
            "the evaporative_tower archetype spec itself (watermark.hydrology.cooling_models) — "
            "the band IS the archetype, not a facility's disclosure"
        ),
    )
    basis_values = _predicted_basis(normalizing, settings)
    makeup = _require(basis_values.headline_makeup(), "band makeup")
    consumptive = _require(basis_values.headline_consumptive(), "band consumptive")
    blowdown = _predicted_blowdown(basis_values)
    return ReferenceBand(
        basis=(
            "the evaporative_tower archetype spec's own defaults, run through "
            "watermark.hydrology.cooling_models and normalized per IT-MW"
        ),
        makeup_mgd_per_mw=round(makeup.value / _BAND_NORMALIZING_LOAD_MW, 5),
        consumptive_mgd_per_mw=round(consumptive.value / _BAND_NORMALIZING_LOAD_MW, 5),
        blowdown_mgd_per_mw=round(blowdown.value / _BAND_NORMALIZING_LOAD_MW, 5),
        # An evaporative basis always carries both (only the archetypes with no recirculating
        # loop leave them None), so _require states the invariant rather than defaulting one.
        cycles_of_concentration=_require(
            basis_values.cycles_of_concentration, "band cycles of concentration"
        ).value,
        wue_l_per_kwh=_require(basis_values.wue, "band WUE").value,
        tag="[inference]",
        confidence="medium",
        citation=(
            f"{makeup.citation} — normalized per IT-MW from a {_BAND_NORMALIZING_LOAD_MW:g} MW "
            "run of the archetype's own cited defaults. A screening band: it is what an "
            "evaporative tower of a given IT load WOULD draw under the archetype, not what any "
            "facility has disclosed or any instrument has measured."
        ),
        not_derived_from=(
            "NOT derived from the Intel positive control (B6, #1686). Intel Ohio One is a "
            "semiconductor fab, not a data center: its disclosed ~5 MGD is fab process water at a "
            "campus that will not operate until 2030-31, its ~100+ MW continuous is an electrical "
            "load rather than an IT load, and its cooling towers are permitted but not running. A "
            "makeup-per-MW figure read off it and applied to a hyperscale campus would be a "
            "category error, so no documented evaporative-hyperscale band exists in the network "
            "yet — that gap is itself the finding, and the archetype figures recorded here stand "
            "in as a screening reference until an operating, metered evaporative campus lands."
        ),
    )


# --------------------------------------------------------------------- artifact


def reconciliation_document(
    records: list[ReconciliationRecord], *, band: ReferenceBand | None = None
) -> dict[str, Any]:
    """A YAML-ready, deterministic document of the cohort's cooling reconciliation.

    ``band`` is the cross-site per-IT-MW evaporative reference band (B6, #1686); it is derived
    when not supplied.
    """
    counts = {o.value: sum(1 for r in records if r.outcome is o) for o in ReconcileOutcome}
    band = band if band is not None else reference_band()
    return {
        "meta": {
            "subject": (
                "Data-center cooling-cycling reconciliation — claimed cooling archetype vs the "
                "documented water account (closed-loop cooling cycling epic #1676, A3 #1679), plus "
                "the A4 (#1680) independent corroborators (air-permit PM + Tier II chemistry)"
            ),
            "source": (
                "watermark.hydrology.cooling_reconcile — the A2 closed-loop cohort x the "
                "archetype-predicted water account (cooling_models) x documented makeup (A1) / "
                "blowdown (A2) x the A4 corroborators (cooling_corroborators), plus the Troy-Piqua "
                "B1 reservation conflict (#1681) and the Intel evaporative positive control"
            ),
            "regenerate": "watermark cooling-reconcile --write",
            # As current as the A2 permit-lifecycle refresh the documented-blowdown read gates on.
            "asof": blowdown.OHD000001.asof,
            "outcomes": counts,
            "discipline": (
                "The harness RECOMMENDS; it never mutates cooling_model — re-archetyping is a "
                "reviewed B1-B6 edit with the instrument cited. A back-solved cycles-of-"
                "concentration is an [inference] bracket, never a headline scalar. A gap (no "
                "documented makeup/blowdown) is an [open] records-request lead for C2 (#1688), "
                "never read as 'confirmed dry'. A reservation_conflict (B1 Troy-Piqua, #1681) is a "
                "low-water claim contradicted by a disclosed RESERVATION CEILING (a will-serve / "
                "water-agreement figure), not a metered use — a ceiling is not a discharge/withdrawal "
                "instrument, so it keeps the archetype pin (Troy-Piqua stays UNKNOWN, Bowling Green "
                "stays closed_loop_dry) and sharpens "
                "the site's water lead (#1486, #1439) + the C2 request; the reserved figure is never "
                "collapsed into a headline consumptive. A reservation conflict SURVIVES A BLIND "
                "ROUTE (B5 Bowling Green, #1685): the reach guard below invalidates a negative read, "
                "and a negotiated ceiling is not something the withdrawal or discharge instruments "
                "could ever have metered, so blinding them cannot erase it — which is why a "
                "municipally-supplied campus with an independently-sourced reservation reads "
                "reservation_conflict and not route_blind. Where the operator's OWN figure conflicts "
                "with that reservation, the two are separated by PROVENANCE and not by size: the "
                "independently-sourced figure classifies, the self-report does not, and the conflict "
                "between them is reported rather than resolved. A gap the operator has DISCLOSED into (B2 Van "
                "Wert, #1682) records the self-reported ongoing draw on `disclosed_makeup` (never "
                "`documented_*`) — it stays a gap with the [reference] pin KEPT (a single-source "
                "self-report is not a metered instrument, so it cannot upgrade the source), and its "
                "lead names the specific open quantity: the initial closed-loop fill, whose "
                "fill-vs-annual framing is the #1409 discrepancy. The A4 corroborators (air-permit "
                "cooling-tower "
                "PM, Tier II / EPCRA-312 chemistry) are SECONDARY — recorded and reconciled against "
                "the claim, but never the sole basis for a re-archetype and never changing the "
                "outcome. The Intel control row (is_control) is a CONSTRUCTED positive control "
                "(openly evaporative) the harness must classify corroborated, not a false "
                "discrepancy — a calibration vector, not documented Intel data. A route_blind (B6 "
                "New Albany / Intel, #1686) is a facility whose water is outside the reach of BOTH "
                "instruments this harness reads — makeup purchased from a municipal system (the "
                "withdrawal registry meters withdrawals from waters of the state, not purchases) "
                "and/or blowdown to a POTW sanitary sewer (no NPDES outfall, so no DMR). Their ~0 "
                "is an absence of jurisdiction, NOT a documented ~0, so it can never corroborate a "
                "dry claim; the pin is kept and the records request is re-aimed at the City-held "
                "meter + industrial-pretreatment record. A documented withdrawal that is on record "
                "but is not the cooling account (Intel's construction-phase groundwater) rides on "
                "`nonprocess_makeup`, never `documented_*`. Where an archetype's water account "
                "cannot be derived at all — a semiconductor fab has no IT load, and every archetype "
                "is IT-load-parameterized — the prediction is REFUSED with its reason on "
                "`prediction_refused` and the three `predicted_*` are null; a reader must show the "
                "refusal, never substitute a zero. Where a route_blind facility's SUPPLIER is on "
                "record even though the facility is not (B4 Urbana, #1684), that system's reported "
                "withdrawal rides on `supplier_withdrawal` — never `documented_*`. It is the "
                "supplier's account, aggregating every customer on the system, so like the "
                "self-report slots it can neither corroborate nor contradict one facility's cooling "
                "claim; it is carried because it is the DENOMINATOR — the scale the untestable "
                "claim would land inside. Urbana is the case the epic started from: the City "
                "reported 1.76 MGD in 2024 while an evaporative read of the same campus, at its "
                "[inference] screening IT load, would draw 0.49-1.64 MGD, and the disclosed claim "
                "('water use comparable to a standard office building' — a comparison, not a "
                "figure, so nothing lands on `disclosed_makeup`) sits below the 0.01 MGD noise "
                "floor. Three orders of magnitude, and no instrument on either side can tell them "
                "apart."
            ),
            "reference_band": band.model_dump(mode="json"),
        },
        "candidates": [r.model_dump(mode="json") for r in records],
    }


def write_reconciliation(
    document: dict[str, Any], *, settings: Settings | None = None, out: Path | None = None
) -> Path:
    """Write the reconciliation document to ``reference/oepa/cooling-reconciliation.yaml``."""
    settings = settings or get_settings()
    path = out if out is not None else settings.data_dir / RECONCILIATION_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8"
    )
    return path
