"""Independent cooling corroborators — air-permit cooling-tower PM + Tier II chemistry (#1680).

The A4 (stretch) half of the closed-loop cooling cycling epic (#1676). A1-A3 build the primary
**water account** — makeup (A1) vs blowdown (A2) reconciled against the pinned archetype (A3). This
module adds two *orthogonal* tells that corroborate over-cycling **independently of that
makeup/blowdown accounting**, and are hard for an operator to reconcile with a "dry, sealed"
claim:

1. **Air permit** (:func:`air_permit_corroborator`) — an evaporative cooling tower emits PM (drift)
   and is a permitted air source fitted with drift eliminators; a sealed/dry system is not. So a
   facility whose **own air permit lists cooling towers as PM emission units** contradicts a
   ``closed_loop_dry`` claim, and corroborates an ``evaporative_tower`` / ``hybrid_adiabatic`` one.
   Read from the committed air-permit extraction at :attr:`SiteFacility.air_permit_relpath` (the same
   seam :mod:`watermark.air.emissions` grounds its rates on) — real today for any facility whose air
   PTI/PTIO is on file (Lima's lists 36), ``not_on_record`` where none is wired.
2. **Tier II chemistry** (:func:`tier2_chemistry_corroborator`) — cooling-water treatment purchases
   (biocide, scale / corrosion inhibitor) scale with makeup and blowdown volume. A truly dry closed
   loop needs little chemistry; a heavy treatment inventory implies an evaporative tower cycling.
   Source: **Tier II / EPCRA-312** chemical inventory + LEPC filings — held by the SERC/LEPC, not on
   ECHO, so for the live cohort this is a **forward seam** (``not_on_record`` → a C2 records-request
   item) until a filing lands.

**Both are corroborators, never the sole basis for a re-archetype** (the epic's rule): a re-
archetype is ``[verified]`` only with the discharge/withdrawal *instrument* cited (A3's water
account), and an air permit is not a discharge/withdrawal instrument. So these signals attach to the
A3 :class:`~watermark.hydrology.cooling_reconcile.ReconciliationRecord` and sharpen its finding /
records-request, but they **never change its primary outcome**. Each corroborator carries its OWN
tag: an on-record signal (a permit that lists — or verifiably omits — a cooling tower) is
``[verified]``; a not-on-record one is ``[open]``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.provenance import Confidence
from watermark.sites import CoolingModelType, SiteFacility

log = get_logger(__name__)

# The archetypes that run a wet **cooling tower** (a permitted PM drift source): the evaporative
# tower and the hybrid's evaporative-assist section. A ``closed_loop_dry`` (or ``off`` / ``once_
# through``) claim predicts NO cooling-tower PM — so a listed tower CONTRADICTS it. Keyed on
# mechanism, mirroring ``cooling_reconcile._WET_ARCHETYPES``.
_TOWER_ARCHETYPES: frozenset[CoolingModelType] = frozenset(
    {CoolingModelType.EVAPORATIVE_TOWER, CoolingModelType.HYBRID_ADIABATIC}
)


class CorroboratorStance(StrEnum):
    """How a corroborating signal bears on the *claimed* archetype — never on the primary outcome.

    A stance is read relative to whether the claim runs an evaporative cooling tower
    (:data:`_TOWER_ARCHETYPES`): a cooling-tower PM listing / treatment-chemistry inventory
    ``corroborates`` a wet claim and ``contradicts`` a dry (``closed_loop_dry``) one; ``silent``
    when the signal is not on record and cannot speak either way.
    """

    CORROBORATES = "corroborates"  # the signal is consistent with the claimed archetype
    CONTRADICTS = (
        "contradicts"  # the signal is inconsistent with the claim (points to over-cycling)
    )
    SILENT = "silent"  # not on record — cannot speak to the claim (→ a records-request item)


class AirPermitState(StrEnum):
    """Whether the facility's own air permit lists a cooling tower as a PM emission source."""

    PM_SOURCE_LISTED = "pm_source_listed"  # cooling tower(s) permitted as PM (drift) sources
    NO_PM_SOURCE = "no_pm_source"  # air permit on file, no cooling-tower PM unit — a cited absence
    NOT_ON_RECORD = "not_on_record"  # no air permit wired for this facility yet — an [open] seam


class TierIIState(StrEnum):
    """Whether a Tier II / EPCRA-312 cooling-water treatment inventory is on record."""

    TREATMENT_PRESENT = (
        "treatment_present"  # biocide / scale / corrosion-inhibitor inventory on file
    )
    ABSENT = "absent"  # Tier II filed, no cooling-treatment chemistry — a cited absence
    NOT_ON_RECORD = (
        "not_on_record"  # no Tier II / LEPC filing wired — an [open] records-request seam
    )


class AirPermitCorroborator(BaseModel):
    """The air-permit cooling-tower-PM corroborator, reconciled against the claimed archetype.

    ``pm10_tpy`` / ``pm25_tpy`` / ``tower_count`` are populated only when a permit is on file and
    lists cooling towers as PM units; the PM figures are best-effort (the ``~`` approx marker is
    tolerated). The ``stance`` is the reconciliation against ``cooling_model`` — never the primary
    outcome.
    """

    model_config = ConfigDict(extra="forbid")

    state: AirPermitState
    stance: CorroboratorStance
    tower_count: int | None = None  # cooling-tower emission units listed, when on record
    pm10_tpy: float | None = None  # combined cooling-tower PM10 (tpy) from the permit, when listed
    pm25_tpy: float | None = None  # combined cooling-tower PM2.5 (tpy), when listed
    citation: str
    tag: str  # [verified] for an on-record listing/absence, [open] for not-on-record
    confidence: Confidence
    finding: str


class TierIIChemistryCorroborator(BaseModel):
    """The Tier II / EPCRA-312 cooling-chemistry corroborator, reconciled against the claim.

    ``chemicals`` lists the cooling-water treatment substances on file (biocide, scale / corrosion
    inhibitor) when a Tier II inventory is on record; empty otherwise. A forward seam for the live
    cohort (LEPC/SERC-held, not on ECHO) until a filing lands.
    """

    model_config = ConfigDict(extra="forbid")

    state: TierIIState
    stance: CorroboratorStance
    chemicals: list[str] = []  # cooling-treatment chemicals on file, when present
    citation: str
    tag: str
    confidence: Confidence
    finding: str


class CoolingCorroborators(BaseModel):
    """The two independent corroborators for one facility, plus their combined read.

    ``net_stance`` is the strongest non-silent direction across the two signals (a single
    contradiction dominates): it lets a consumer see at a glance whether the corroborators point the
    same way as the primary water account, *without* ever having changed that account's outcome.
    """

    model_config = ConfigDict(extra="forbid")

    air_permit: AirPermitCorroborator
    tier2_chemistry: TierIIChemistryCorroborator
    net_stance: CorroboratorStance
    summary: str


# --------------------------------------------------------------------- helpers


def _approx_float(value: Any) -> float | None:
    """Best-effort float from a permit figure, tolerating the ``~`` approx marker (YAML string).

    ``combined_pm10_tpy: ~4.0`` parses as the string ``"~4.0"`` (``~`` is the corpus approx marker,
    :mod:`watermark.models`); a plain number parses as a float. Anything else → ``None`` (the PM
    magnitude is a nice-to-have display field, never the presence signal).
    """
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().lstrip("~").replace(",", ""))
        except ValueError:
            return None
    return None


def _claim_runs_tower(model: CoolingModelType) -> bool:
    """True when the claimed archetype runs a wet cooling tower (a permitted PM drift source)."""
    return model in _TOWER_ARCHETYPES


def _stance_for_positive(claim_runs_tower: bool) -> CorroboratorStance:
    """A *present* signal (PM listed / chemistry on file) corroborates a wet claim, contradicts dry."""
    return CorroboratorStance.CORROBORATES if claim_runs_tower else CorroboratorStance.CONTRADICTS


def _stance_for_absence(claim_runs_tower: bool) -> CorroboratorStance:
    """A verified *absence* corroborates a dry claim, contradicts a wet one (the mirror of positive)."""
    return CorroboratorStance.CONTRADICTS if claim_runs_tower else CorroboratorStance.CORROBORATES


# --------------------------------------------------------------------- air permit


def _cooling_tower_block(
    action: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The permit's cooling-tower emission-unit group + limit block, if either is present.

    The extraction's air-specific capture (``EpaPermitAction`` is ``extra=allow``) puts the
    cooling-tower emission units under ``emission_unit_groups.cooling_towers`` and their PM limits
    under ``cooling_tower_limits`` (see ``data/extracted/permits/4132514.epa.yaml``). Either one
    present ⇒ the permit lists cooling towers as PM (drift) sources.
    """
    groups = action.get("emission_unit_groups")
    towers = groups.get("cooling_towers") if isinstance(groups, dict) else None
    limits = action.get("cooling_tower_limits")
    return (
        towers if isinstance(towers, dict) else None,
        limits if isinstance(limits, dict) else None,
    )


def air_permit_corroborator(
    fac: SiteFacility, *, settings: Settings | None = None
) -> AirPermitCorroborator:
    """Reconcile the facility's air-permit cooling-tower PM listing against its claimed archetype.

    Reads the committed extraction at ``SiteFacility.air_permit_relpath`` (relative to
    ``settings.extracted_dir`` — the #1180 per-site seam ``watermark.air.emissions`` grounds rates
    on). Three states, each with its stance relative to the claim:

    * **pm_source_listed** — cooling towers are permitted PM (drift) units. A ``[verified]`` air-
      permit fact: it CONTRADICTS a ``closed_loop_dry`` claim (a dry loop is not a PM source) and
      CORROBORATES an evaporative / hybrid one.
    * **no_pm_source** — a permit is on file but lists no cooling-tower PM unit; a ``[verified]``
      cited absence (mirror stance).
    * **not_on_record** — no air permit wired for this facility; ``[open]``, ``silent`` — the C2
      records-request item, never read as "no cooling tower".

    Corroborating only: this never re-archetypes on its own (an air permit is not a discharge/
    withdrawal instrument — the epic's re-archetype gate).
    """
    settings = settings or get_settings()
    runs_tower = _claim_runs_tower(fac.cooling_model)
    claim = fac.cooling_model.value

    if fac.air_permit_relpath is None:
        return AirPermitCorroborator(
            state=AirPermitState.NOT_ON_RECORD,
            stance=CorroboratorStance.SILENT,
            citation=f"no air permit wired for {fac.name} (SiteFacility.air_permit_relpath is None)",
            tag="[open]",
            confidence="low",
            finding=(
                f"No air permit on file for {fac.name}: whether its cooling towers are permitted PM "
                f"(drift) sources cannot be checked against the {claim} claim — a records-request "
                "item (facility air PTI/PTIO), never read as 'no cooling tower'."
            ),
        )

    path = settings.extracted_dir / fac.air_permit_relpath
    if not path.exists():  # pragma: no cover - a wired relpath should resolve; guard the seam
        log.warning("cooling_corroborators.air_permit_missing", facility=fac.name, path=str(path))
        return AirPermitCorroborator(
            state=AirPermitState.NOT_ON_RECORD,
            stance=CorroboratorStance.SILENT,
            citation=f"air permit relpath {fac.air_permit_relpath} does not resolve under extracted_dir",
            tag="[open]",
            confidence="low",
            finding=f"Air permit for {fac.name} not found at {fac.air_permit_relpath} — unresolved seam.",
        )

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    action = data.get("action", {}) if isinstance(data, dict) else {}
    permit_no = action.get("permit_no") or action.get("permit_number") or fac.air_permit_relpath
    towers, limits = _cooling_tower_block(action)

    if towers is None and limits is None:
        return AirPermitCorroborator(
            state=AirPermitState.NO_PM_SOURCE,
            stance=_stance_for_absence(runs_tower),
            citation=f"{fac.air_permit_relpath}: air permit lists no cooling-tower PM emission unit",
            tag="[verified]",
            confidence="high",
            finding=(
                f"Air permit {permit_no} on file for {fac.name} lists no cooling-tower PM source — "
                f"{'consistent with' if not runs_tower else 'in tension with'} the {claim} claim "
                "(a corroborator, not a re-archetype basis)."
            ),
        )

    count = towers.get("count") if towers is not None else None
    tower_count = int(count) if isinstance(count, (int, float)) else None
    pm10 = _approx_float(limits.get("combined_pm10_tpy")) if limits is not None else None
    pm25 = _approx_float(limits.get("combined_pm25_tpy")) if limits is not None else None
    stance = _stance_for_positive(runs_tower)
    towers_phrase = (
        f"{tower_count} cooling tower(s)" if tower_count is not None else "cooling tower(s)"
    )
    pm_phrase = f", ~{pm10:g} tpy PM10" if pm10 is not None else ""
    return AirPermitCorroborator(
        state=AirPermitState.PM_SOURCE_LISTED,
        stance=stance,
        tower_count=tower_count,
        pm10_tpy=pm10,
        pm25_tpy=pm25,
        citation=(
            f"{fac.air_permit_relpath}: air permit {permit_no} lists {towers_phrase} as PM (drift) "
            f"emission units w/ drift eliminators{pm_phrase}"
        ),
        tag="[verified]",
        confidence="high",
        finding=(
            f"Air permit {permit_no} lists {towers_phrase} as permitted PM (drift) sources — "
            + (
                f"a documentary contradiction of the {claim} dry claim (an evaporative tower is a "
                "permitted air source; a sealed dry loop is not). Independent of the water account; "
                "corroborates re-archetyping up but is not itself the [verified] instrument."
                if stance is CorroboratorStance.CONTRADICTS
                else f"corroborates the {claim} claim's evaporative cooling."
            )
        ),
    )


# --------------------------------------------------------------------- Tier II chemistry


def tier2_chemistry_corroborator(
    fac: SiteFacility, *, settings: Settings | None = None
) -> TierIIChemistryCorroborator:
    """Reconcile a Tier II / EPCRA-312 cooling-chemistry inventory against the claim.

    Forward seam: cooling-water treatment inventories (biocide, scale / corrosion inhibitor) are
    filed with the SERC/LEPC under EPCRA §312 and are **not on ECHO**, so no live cohort facility
    has one wired today — the honest state is ``not_on_record`` / ``silent``, which is itself the
    finding (a C2 records-request item). The seam activates when a committed Tier II filing lands;
    the Intel positive control constructs a ``treatment_present`` reading directly (a calibration
    vector, not a real filing).
    """
    settings = settings or get_settings()
    claim = fac.cooling_model.value
    return TierIIChemistryCorroborator(
        state=TierIIState.NOT_ON_RECORD,
        stance=CorroboratorStance.SILENT,
        citation=(
            "Tier II / EPCRA-312 cooling-water treatment inventory not on record (SERC/LEPC-held, "
            "not published to ECHO)"
        ),
        tag="[open]",
        confidence="low",
        finding=(
            f"No Tier II / EPCRA-312 cooling-chemistry inventory on file for {fac.name}: heavy "
            "biocide / scale-inhibitor treatment scales with evaporative cycling and would corroborate "
            f"over-cycling against the {claim} claim — a records-request item (LEPC/SERC filing), not "
            "yet obtainable."
        ),
    )


# --------------------------------------------------------------------- combined


def _net_stance(*stances: CorroboratorStance) -> CorroboratorStance:
    """The strongest non-silent direction across signals — a single contradiction dominates."""
    if CorroboratorStance.CONTRADICTS in stances:
        return CorroboratorStance.CONTRADICTS
    if CorroboratorStance.CORROBORATES in stances:
        return CorroboratorStance.CORROBORATES
    return CorroboratorStance.SILENT


def _summary(
    fac: SiteFacility, air: AirPermitCorroborator, tier2: TierIIChemistryCorroborator
) -> str:
    """A one-line combined read of the two corroborators against the claim."""
    net = _net_stance(air.stance, tier2.stance)
    claim = fac.cooling_model.value
    if net is CorroboratorStance.CONTRADICTS:
        who = []
        if air.stance is CorroboratorStance.CONTRADICTS:
            who.append("the air permit's cooling-tower PM listing")
        if tier2.stance is CorroboratorStance.CONTRADICTS:
            who.append("the Tier II cooling-chemistry inventory")
        return (
            f"Independent corroborators contradict the {claim} claim ({', '.join(who)}) — secondary "
            "to the water account, never the sole basis for a re-archetype."
        )
    if net is CorroboratorStance.CORROBORATES:
        return f"Independent corroborators are consistent with the {claim} claim."
    return (
        f"Neither corroborator is on record for {fac.name} (air permit + Tier II) — both are "
        "C2 records-request items, not read as confirming the claim."
    )


def resolve_corroborators(
    fac: SiteFacility, *, settings: Settings | None = None
) -> CoolingCorroborators:
    """Resolve both independent corroborators for a facility and combine them.

    Facility-intrinsic (reads the pinned ``cooling_model`` + the wired ``air_permit_relpath``), so
    a cohort caller resolves each candidate under its own site settings. Corroborating only —
    :mod:`watermark.hydrology.cooling_reconcile` attaches the result to its record but never lets it
    change the primary outcome.
    """
    settings = settings or get_settings()
    air = air_permit_corroborator(fac, settings=settings)
    tier2 = tier2_chemistry_corroborator(fac, settings=settings)
    return CoolingCorroborators(
        air_permit=air,
        tier2_chemistry=tier2,
        net_stance=_net_stance(air.stance, tier2.stance),
        summary=_summary(fac, air, tier2),
    )
