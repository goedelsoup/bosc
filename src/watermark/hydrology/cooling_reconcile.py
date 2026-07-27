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

**The Intel positive control** (:data:`INTEL_CONTROL`) is the calibration baseline: an
openly-evaporative facility (exemplar New Albany / Intel, ~125 cooling towers) whose
documented water *equals its evaporative-tower prediction*. The harness must classify it
``corroborated`` — **not** a false ``discrepancy** just because it uses a lot of water. It
is a constructed calibration vector built into the harness, not a registered site (New
Albany carries no pinned ``SiteFacility`` — that is B6 #1686's work); its figures are
internally consistent with an evaporative tower at CoC ≈ 5, not documented Intel data.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

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
    it_load: ProvenancedValue  # MW
    predicted_makeup: ProvenancedValue  # MGD, the claim's cooling intake
    predicted_consumptive: ProvenancedValue  # MGD, the claim's evaporative loss
    predicted_blowdown: ProvenancedValue  # MGD, the claim's blowdown (makeup - evaporation)
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
    disclosed_cycles: ProvenancedValue | None = None  # the operator's disclosed CoC, if any
    # The back-solved cycles-of-concentration (makeup / blowdown) — an [inference] BRACKET, never
    # a headline scalar. Present when both makeup and blowdown are on record — as documented (metered)
    # figures, or (reservation_conflict) as reservation ceilings, in which case its citation says so.
    backsolved_cycles: ProvenancedValue | None = None
    # The A2 seasonality shape signal (warm/cool DMR-flow ratio) — a temperature-driven
    # evaporative blowdown peaks in summer (ratio ≫ 1), a dry loop is flat (~1). A shape
    # indicator, never a magnitude; None when no DMR flow series is on record.
    seasonality_warm_ratio: float | None = None


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
        "cooling-tower blowdown / low-volume-wastewater DMR (facility-own or OHD000001 coverage)",
    ]
    holders = [
        f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (NPDES / OHD000001)",
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
        "cooling-tower / low-volume-wastewater blowdown DMR (facility-own or OHD000001 coverage)",
        "on-site reservoir / alternate-supply plan (the disclosed municipal-tap-avoidance study)",
        "industrial pretreatment / indirect-discharge (IU) permit + sewer-use agreement",
    ]
    holders = [
        f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (NPDES / OHD000001; Air PTI)",
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
            f"approaches the {ceiling_phrase} ceiling (which would contradict 'not evaporative') or "
            f"sits far below it (dry), plus the blowdown / OHD000001 to complete the account ({issue_ref})."
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
) -> RecordsRequestLead:
    """The sharpened C2 (#1688) records-request lead for a reservation_conflict (B1, #1681).

    Unlike a bare gap, a reservation conflict already carries a quantified figure — a disclosed
    reservation ceiling that contradicts the low-water claim. The ask is therefore sharper: pull the
    **executed instrument** (the negotiated water-service agreement text, not the secondary summary of
    it) and the **metered use** that would say whether the facility draws near the ceiling
    (evaporative) or far below it (nearer dry). ``issue_ref`` is the site's own standing water lead
    (Troy-Piqua's ``#1486``) the conflict sharpens. The silent A4 corroborators (#1680) add their own
    not-on-record asks, as on a gap.
    """
    reserved = account.reserved_makeup or account.reserved_blowdown
    reserved_phrase = f"{reserved.value:g} MGD" if reserved is not None else "the reserved figure"
    records_sought = [
        "executed water & wastewater service agreement (the instrument text, not a summary)",
        "metered water-service use (actual makeup withdrawal vs the reserved ceiling)",
        "cooling-tower blowdown / low-volume-wastewater DMR (facility-own or OHD000001 coverage)",
        "industrial pretreatment / indirect-discharge (IU) permit + sewer-use agreement",
    ]
    holders = [
        f"City / municipal water-sewer authority serving {site}",
        "Ohio EPA (NPDES / OHD000001)",
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
                f"archetype predicts ~{account.predicted_makeup.value:g} MGD — far below the ceiling. "
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
        return (
            f"No documented makeup or blowdown for {fac.name}: the {arche} claim "
            f"(source={claim_source}) cannot yet be tested against records — an [open] gap, not "
            "'confirmed dry' (→ C2 records request #1688). Predicted makeup "
            f"{account.predicted_makeup.value:g} MGD."
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
        return (
            f"Reserved {reserved_phrase} makeup contradicts the {arche} FAQ claim's "
            f"~{account.predicted_makeup.value:g} MGD prediction — but a reservation is a ceiling, not "
            "a discharge/withdrawal instrument, so keep the archetype pin (no [verified] re-archetype) "
            f"and sharpen the water lead (→ C2 records request #1688).{coc} The reserved figure is an "
            "upper-bound ceiling, NOT a headline consumptive."
        )
    # A documented signal exists (DISCREPANCY / CORROBORATED) — pair it with the MATCHING
    # predicted figure exactly as _classify does: the A2 blowdown record against predicted
    # blowdown, else the A1 makeup record against predicted makeup (never cross the two).
    if account.documented_blowdown is not None:
        doc, predicted, kind = account.documented_blowdown, account.predicted_blowdown, "blowdown"
    else:
        doc = _require(account.documented_makeup, "documented water")
        predicted, kind = account.predicted_makeup, "makeup"
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
    seasonality_warm_ratio: float | None = None,
    corroborators: CoolingCorroborators | None = None,
    water_lead_ref: str = "#1688 (C2)",
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

    ``corroborators`` (A4, #1680) are the two independent tells (air-permit cooling-tower PM +
    Tier II chemistry). Injected like the documented figures (the cohort resolver reads them via
    :func:`~watermark.hydrology.cooling_corroborators.resolve_corroborators`). They are SECONDARY:
    they sharpen the finding + the gap's records-request but NEVER change the classified ``outcome``.
    """
    basis = _predicted_basis(fac, settings)
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
        it_load=basis.it_load,
        predicted_makeup=predicted_makeup,
        predicted_consumptive=predicted_consumptive,
        predicted_blowdown=predicted_blowdown,
        documented_makeup=documented_makeup,
        documented_blowdown=documented_blowdown,
        reserved_makeup=reserved_makeup,
        reserved_blowdown=reserved_blowdown,
        disclosed_makeup=disclosed_makeup,
        disclosed_ceiling=disclosed_ceiling,
        disclosed_cycles=disclosed_cycles,
        backsolved_cycles=backsolved_cycles,
        seasonality_warm_ratio=seasonality_warm_ratio,
    )

    outcome = _classify(
        fac.cooling_model,
        predicted_makeup.value,
        predicted_blowdown.value,
        documented_makeup.value if documented_makeup is not None else None,
        documented_blowdown.value if documented_blowdown is not None else None,
        reserved_makeup.value if reserved_makeup is not None else None,
        reserved_blowdown.value if reserved_blowdown is not None else None,
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
            site, fac, claim_source, account, water_lead_ref, corroborators
        )
        tag = "[open]"  # the conflict stays open; a ceiling is not [verified] proof of use
        confidence = (
            "medium"  # sharper than an empty gap (a quantified figure), short of instrument-grade
        )
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
# cooling towers). NOT a registered site — New Albany carries no pinned SiteFacility (that is
# B6 #1686's work); this is a constructed calibration vector built into the harness, internally
# consistent with an evaporative tower at CoC ≈ 5. The harness must classify it CORROBORATED
# (documented water matches the evaporative prediction), never a false DISCREPANCY. Its
# documented figures are a calibration vector, NOT documented Intel data.
_INTEL_CITE = (
    "constructed calibration control (exemplar: Intel 'Ohio One' / New Albany, openly "
    "evaporative, ~125 cooling towers) — figures internally consistent with an evaporative "
    "tower at CoC≈5, NOT documented Intel data; New Albany carries no pinned SiteFacility "
    "(B6 #1686). The harness must classify it corroborated-evaporative (no false discrepancy)."
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

    * **Blowdown (A2)** comes from :func:`watermark.hydrology.blowdown.resolve_coverage`. While
      OHD000001 is a draft permit and no facility-own DMR is on record, it is ``unknown`` → no
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
# built) + A2 (OHD000001 draft, no facility-own DMR) are absent → the honest outcome stays a GAP with
# the [reference] pin KEPT, never silently promoted (the issue's acceptance).
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
    quantity (#1409). With no A1 withdrawal (Van Wert County is not built) and no A2 blowdown (OHD000001
    is draft, no facility-own DMR), the honest outcome is a GAP that KEEPS the [reference] pin — the
    disclosed figure is consistent with a dry loop at screening scale but cannot upgrade the source.
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
# names the actual-vs-ceiling denominator. A1 (no Clark County withdrawal built) + A2 (OHD000001 draft,
# no facility-own DMR) are absent → the honest outcome stays a GAP with the [reference] pin KEPT.
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
    (OHD000001 is draft, no facility-own DMR), the honest outcome is a GAP that KEEPS the [reference]
    pin: a self-disclosed permit ceiling from the claim's own source is not a ``reservation_conflict``
    (a dry loop sits far below it) and cannot corroborate the claim (that would be circular). The lead
    sharpens onto the actual-vs-ceiling denominator (#1415). Closed-loop-dry needs no climatology, so a
    per-site ``Settings`` resolves it.
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
    **Van Wert** (#1682, :func:`reconcile_van_wert`) and **Springfield** (#1683,
    :func:`reconcile_springfield`) ARE in A2's cohort but are reconciled explicitly (skipped in the
    generic loop) so their self-disclosed figures sharpen the gap — Van Wert's operator-disclosed ~660k
    gal draw + the #1409 initial-fill open quantity, Springfield's self-disclosed 300k gal/day permitted
    ceiling + the #1415 actual-vs-ceiling denominator for its "not evaporative" claim. The Intel control
    is appended and reconciled the same way. Ordered by (is_control, site, facility) so the control
    sorts last after the live findings.
    """
    settings = settings or get_settings()
    records: list[ReconciliationRecord] = []
    for candidate in blowdown.closed_loop_candidates(settings=settings):
        # Van Wert (B2, #1682) + Springfield (B3, #1683) are cohort members but are reconciled
        # explicitly below so their self-disclosed figures are carried — Van Wert's ~660k gal draw +
        # #1409 initial-fill, Springfield's 300k gal/day permitted ceiling + #1415 — skip the generic
        # gap here to avoid a double row.
        if candidate.site in {"van-wert", "springfield"}:
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
        reconcile_troy_piqua(settings=settings)
    )  # B1 (#1681) — pins UNKNOWN, not in A2's cohort
    records.append(intel_control(settings=settings))
    records.sort(key=lambda r: (r.is_control, r.site, r.facility))
    log.info(
        "cooling_reconcile.cohort_resolved",
        facilities=len(records),
        outcomes={o.value: sum(1 for r in records if r.outcome is o) for o in ReconcileOutcome},
    )
    return records


# --------------------------------------------------------------------- artifact


def reconciliation_document(records: list[ReconciliationRecord]) -> dict[str, Any]:
    """A YAML-ready, deterministic document of the cohort's cooling reconciliation."""
    counts = {o.value: sum(1 for r in records if r.outcome is o) for o in ReconcileOutcome}
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
                "instrument, so it keeps the archetype pin (Troy-Piqua stays UNKNOWN) and sharpens "
                "the site's water lead (#1486) + the C2 request; the reserved figure is never "
                "collapsed into a headline consumptive. A gap the operator has DISCLOSED into (B2 Van "
                "Wert, #1682) records the self-reported ongoing draw on `disclosed_makeup` (never "
                "`documented_*`) — it stays a gap with the [reference] pin KEPT (a single-source "
                "self-report is not a metered instrument, so it cannot upgrade the source), and its "
                "lead names the specific open quantity: the initial closed-loop fill, whose "
                "fill-vs-annual framing is the #1409 discrepancy. The A4 corroborators (air-permit "
                "cooling-tower "
                "PM, Tier II / EPCRA-312 chemistry) are SECONDARY — recorded and reconciled against "
                "the claim, but never the sole basis for a re-archetype and never changing the "
                "outcome. The Intel row is a constructed positive control (openly evaporative) the "
                "harness must classify corroborated, not a false discrepancy — it is a calibration "
                "vector, not documented Intel data."
            ),
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
