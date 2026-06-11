"""The air-permit-derived facility power basis.

The canonical ~275 MW IT-load figure that anchors the compute-capacity methods,
expressed as provenance-tagged :class:`ProvenancedValue`s. It traces to the same
disclosed inputs as :mod:`bosc.hydrology.cooling` — Ohio EPA Air PTI **P0138965**
(Facility 0302022054): 114 emergency generators at 2.75 ekW each ≈ 313 MW backup,
which at hyperscale N+1 ratios implies a ~250-300 MW IT load.

The genset count and IT-load constants are deliberately **duplicated** from
``cooling.py``'s private constants here rather than imported, because ``cooling``
hides them as module-private (``_GENSET_COUNT`` etc.) and importing private names
across subsystems is brittle. To keep the two from silently diverging,
``tests/facility/test_power.py`` asserts this module's IT load equals
``cooling.py``'s ``_IT_LOAD_MW``. FUTURE DEDUP: lift the air-permit constants into a
single shared module (e.g. ``bosc.facility.power`` re-exported into hydrology) once
``cooling.py``'s tests can be migrated without churn.

**On-site generation cycle (issue #90).** Beyond *how much* power, the basis carries
*how* power is generated: the 2026-06-10 call's "single- vs double-phase" distinction
is the **generation cycle** — ``simple`` (the prime mover drives the generator
directly; exhaust heat lost) vs ``combined`` (exhaust heat recovered to raise steam
and drive a second-stage steam turbine — cogeneration). The "power-loss coefficient"
the call asked us to verify is each config's **net electrical efficiency** (fuel
chemical energy in → net MWh delivered), carried as a banded assumption with a derived
heat rate (fuel per MWh — the lever the consumer fuel-cost thread, #91, needs). A
combined cycle's steam loop **reuses/consumes water**: an *additional* consumptive
pathway beyond IT cooling, cross-referenced to :mod:`bosc.hydrology.cooling`. IMPORTANT:
the disclosed units are emergency **backup** reciprocating gensets (simple-cycle by
nature); whether any *primary* on-site generation exists, and its cycle, is an **open
evidence question** (#33), so the configs are labeled scenarios, not a campus fact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from bosc.hydrology.model import ProvenancedValue

# --- Air-permit-disclosed constants (mirror bosc.hydrology.cooling) ----------
_GENSET_COUNT = 114
_GENSET_MW = 2.75  # ekW each, per the air permit
_BACKUP_MW = _GENSET_COUNT * _GENSET_MW  # ~313 MW
_IT_LOAD_MW = 275.0  # midpoint of the 250-300 MW estimate (IT ~= backup at N+1)
_IT_LOAD_LOW_MW = 250.0
_IT_LOAD_HIGH_MW = 300.0
_AIR_PERMIT_CITE = (
    "OEPA Air PTI P0138965 (Facility 0302022054): 114 gensets x 2.75 ekW = "
    "~313 MW backup; IT ~250-300 MW (N+1)"
)

# --- On-site generation cycle (issue #90) ------------------------------------
# Net electrical efficiency bands (fuel chemical energy -> net AC power): the
# "power-loss coefficient" per generation cycle, as stated assumptions. Heat rate
# (fuel per MWh) is the derived inverse via MMBtu/MWh = 3.412 / efficiency.
_MMBTU_PER_MWH = 3.412142  # 1 MWh = 3.412 MMBtu (thermal-energy equivalent)

_ETA_SIMPLE = 0.38  # simple-cycle / reciprocating genset; band ~0.33-0.43
_ETA_SIMPLE_CITE = (
    "simple-cycle net electrical efficiency ~0.38 (band 0.33-0.43): the prime mover "
    "drives the generator directly and exhaust heat is lost; consistent with the "
    "disclosed emergency reciprocating diesel gensets (air permit P0138965)"
)
_ETA_COMBINED = 0.55  # combined-cycle / cogeneration; band ~0.50-0.62
_ETA_COMBINED_CITE = (
    "combined-cycle net electrical efficiency ~0.55 (band 0.50-0.62): exhaust heat "
    "recovered to a steam bottoming cycle (cogeneration) — materially higher net "
    "efficiency / lower fuel per MWh than simple-cycle, at the cost of a steam/"
    "condenser water loop"
)

# Steam (bottoming) cycle condenser water — the ADDITIONAL consumptive pathway a
# combined cycle introduces beyond IT cooling. Wet recirculating CCGT cooling
# consumes ~0.2 gal/kWh of generation (NREL/USGS range ~0.13-0.30); a simple cycle
# has no steam loop, so ~0. Applied to the ~275 MW load as the conditional case
# "if primary on-site generation were combined-cycle and supplied the IT load".
_STEAM_WATER_GAL_PER_KWH = 0.2
_STEAM_WATER_CITE = (
    "combined-cycle wet-recirculating condenser water ~0.2 gal/kWh of generation "
    "(band ~0.1-0.3) applied to the ~275 MW load: an ADDITIONAL consumptive pathway "
    "beyond IT cooling. Cross-ref bosc.hydrology.cooling, whose makeup figure covers "
    "data-hall cooling only; compute.py's water back-solve assumes cooling is the "
    "dominant draw. CONDITIONAL: the disclosed gensets are backup, so on-site primary "
    "combined-cycle generation is unproven (#33) — likely ruled out, not additive today"
)

GenerationCycle = Literal["simple", "combined"]


class GenerationConfig(BaseModel):
    """One on-site generation configuration and its fuel/water implications.

    The two configurations the 2026-06-10 call distinguished as "single- vs
    double-phase" generation:

    * ``simple`` (single-phase) — the prime mover drives the generator directly;
      exhaust heat is lost. The lower net-efficiency band; no steam water loop.
    * ``combined`` (double-phase) — exhaust heat is recovered to raise steam and
      drive a second-stage steam turbine (combined-cycle / cogeneration). Higher net
      efficiency (less fuel per MWh), at the cost of a steam/condenser water loop —
      an *additional* consumptive water pathway beyond IT cooling
      (cross-ref :mod:`bosc.hydrology.cooling`).

    ``net_efficiency`` is the "power-loss coefficient" the call asked us to verify
    (fuel chemical energy in → net electrical energy delivered), a stated assumption;
    ``heat_rate_mmbtu_per_mwh`` is its derived inverse — the fuel-per-MWh lever the
    consumer fuel-cost thread (#91) needs. Nothing here is a measured campus fact —
    the disclosed units are emergency backup (see :attr:`PowerBasis.generation_note`).
    """

    model_config = ConfigDict(extra="forbid")

    cycle: GenerationCycle
    label: str
    net_efficiency: ProvenancedValue  # fraction, fuel -> net electrical (power-loss coeff)
    heat_rate_mmbtu_per_mwh: ProvenancedValue  # derived inverse: fuel energy per delivered MWh
    recovers_exhaust_heat: bool  # combined-cycle bottoming steam turbine?
    steam_cycle_water: ProvenancedValue | None = (
        None  # MGD additional condenser pathway, if combined
    )
    note: str = ""


class PowerBasis(BaseModel):
    """The disclosed-power basis for the campus, all provenance-tagged.

    ``it_load`` is the central document-anchored IT load (the N+1 backup ≈ IT
    convention from the air permit); ``it_load_low``/``it_load_high`` bracket the
    250-300 MW range the genset count supports. Mirrors the shape of
    :class:`bosc.hydrology.model.CoolingBasis` so the two subsystems read alike.
    """

    model_config = ConfigDict(extra="forbid")

    genset_count: ProvenancedValue  # count (document)
    genset_rating: ProvenancedValue  # MW each (document)
    backup_power: ProvenancedValue  # MW total backup (derived)
    it_load: ProvenancedValue  # MW central (document-anchored)
    it_load_low: ProvenancedValue  # MW low end of the N+1 range
    it_load_high: ProvenancedValue  # MW high end
    # On-site generation cycle (issue #90): both simple- and combined-cycle as
    # labeled scenarios, each carrying its net-efficiency (the "power-loss
    # coefficient") and the fuel/water it implies. The band is the simple→combined
    # spread; the disclosed units are backup, so this is a scenario, not a fact.
    generation: list[GenerationConfig]
    generation_note: str = (
        "On-site generation cycle is an OPEN EVIDENCE QUESTION: the disclosed 114 x "
        "2.75 ekW units (air permit P0138965) are emergency BACKUP reciprocating "
        "gensets (simple-cycle by nature). Whether any PRIMARY on-site generation "
        "exists, and its cycle, is unproven (#33) — the configs below are scenarios "
        "labeled simple (single-phase) vs combined (double-phase)."
    )
    method: str = "air-permit genset count x rating -> N+1 backup -> IT load (250-300 MW)"

    def generation_config(self, cycle: GenerationCycle) -> GenerationConfig | None:
        """The simple- or combined-cycle generation scenario, by cycle label."""
        return next((g for g in self.generation if g.cycle == cycle), None)


def _generation_configs() -> list[GenerationConfig]:
    """The simple- and combined-cycle generation scenarios (issue #90).

    Each carries a provenance-tagged net electrical efficiency (the "power-loss
    coefficient") and a derived heat rate; the combined cycle additionally carries
    the steam-loop water pathway, cross-referenced to :mod:`bosc.hydrology.cooling`.
    """
    simple = GenerationConfig(
        cycle="simple",
        label="simple-cycle (single-phase) — direct generation, exhaust heat lost",
        net_efficiency=ProvenancedValue.assume(_ETA_SIMPLE, "fraction", why=_ETA_SIMPLE_CITE),
        heat_rate_mmbtu_per_mwh=ProvenancedValue.derived(
            round(_MMBTU_PER_MWH / _ETA_SIMPLE, 2),
            "MMBtu/MWh",
            citation=f"3.412 MMBtu/MWh / {_ETA_SIMPLE:g} net efficiency",
        ),
        recovers_exhaust_heat=False,
        steam_cycle_water=None,
        note=(
            "Single-phase: the prime mover drives the generator directly and exhaust "
            "heat is lost. Matches the disclosed emergency reciprocating gensets; no "
            "steam loop, so no generation-side consumptive water pathway."
        ),
    )
    # If on-site primary generation were combined-cycle and supplied the IT load, its
    # steam condenser would consume water beyond data-hall cooling (conditional/flagged).
    steam_mgd = _IT_LOAD_MW * 1_000.0 * 24.0 * _STEAM_WATER_GAL_PER_KWH / 1_000_000.0
    combined = GenerationConfig(
        cycle="combined",
        label="combined-cycle (double-phase) — exhaust heat recovered to a steam turbine",
        net_efficiency=ProvenancedValue.assume(_ETA_COMBINED, "fraction", why=_ETA_COMBINED_CITE),
        heat_rate_mmbtu_per_mwh=ProvenancedValue.derived(
            round(_MMBTU_PER_MWH / _ETA_COMBINED, 2),
            "MMBtu/MWh",
            citation=f"3.412 MMBtu/MWh / {_ETA_COMBINED:g} net efficiency",
        ),
        recovers_exhaust_heat=True,
        steam_cycle_water=ProvenancedValue.assume(
            round(steam_mgd, 2), "MGD", why=_STEAM_WATER_CITE
        ),
        note=(
            "Double-phase: exhaust heat raises steam to drive a second-stage steam "
            "turbine (cogeneration). Reuses/consumes water in the steam/condenser loop "
            "— an additional pathway the water balance must account for or explicitly "
            "rule out (cross-ref bosc.hydrology.cooling)."
        ),
    )
    return [simple, combined]


def derive_power_basis() -> PowerBasis:
    """Derive the campus power basis from the cited air-permit genset count."""
    return PowerBasis(
        generation=_generation_configs(),
        genset_count=ProvenancedValue.from_document(
            float(_GENSET_COUNT), "count", citation=_AIR_PERMIT_CITE
        ),
        genset_rating=ProvenancedValue.from_document(_GENSET_MW, "MW", citation=_AIR_PERMIT_CITE),
        backup_power=ProvenancedValue.derived(
            round(_BACKUP_MW, 1),
            "MW",
            citation=f"{_GENSET_COUNT} gensets x {_GENSET_MW:g} ekW (air permit P0138965)",
        ),
        it_load=ProvenancedValue.from_document(_IT_LOAD_MW, "MW", citation=_AIR_PERMIT_CITE),
        it_load_low=ProvenancedValue.derived(
            _IT_LOAD_LOW_MW,
            "MW",
            citation="low end of the N+1 IT estimate from ~313 MW backup",
        ),
        it_load_high=ProvenancedValue.derived(
            _IT_LOAD_HIGH_MW,
            "MW",
            citation="high end of the N+1 IT estimate from ~313 MW backup",
        ),
    )
