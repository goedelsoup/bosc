"""The air-permit-derived facility power basis.

The canonical ~275 MW IT-load figure that anchors the compute-capacity methods,
expressed as provenance-tagged :class:`ProvenancedValue`s. It traces to the same
disclosed inputs as :mod:`watermark.hydrology.cooling` — Ohio EPA Air PTI **P0138965**
(Facility 0302022054): 114 emergency generators at 2.75 ekW each ≈ 313 MW backup,
which at hyperscale N+1 ratios implies a ~250-300 MW IT load.

The genset count and IT-load constants are deliberately **duplicated** from
``cooling.py``'s private constants here rather than imported, because ``cooling``
hides them as module-private (``_GENSET_COUNT`` etc.) and importing private names
across subsystems is brittle. To keep the two from silently diverging,
``tests/facility/test_power.py`` asserts this module's IT load equals
``cooling.py``'s ``_IT_LOAD_MW``. FUTURE DEDUP: lift the air-permit constants into a
single shared module (e.g. ``watermark.facility.power`` re-exported into hydrology) once
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
pathway beyond IT cooling, cross-referenced to :mod:`watermark.hydrology.cooling`. IMPORTANT:
the disclosed units are emergency **backup** reciprocating gensets (simple-cycle by
nature); whether any *primary* on-site generation exists, and its cycle, is an **open
evidence question** (#33), so the configs are labeled scenarios, not a campus fact.

**Cooling / mechanical overhead (issue #87).** The basis also makes the IT to
total-facility-draw translation a first-class output: ``facility_draw`` = IT load x
**PUE** (total facility power / IT power), a banded assumption read from the reference
yaml. Cooling-dominated designs reach ~30% of *facility* power (PUE ≈ 1.43, per the
same call), so the band tops out there; the cooling share is ``(PUE-1)/PUE``.
``facility_draw`` is what downstream demand/economics (#91) should consume, not the
IT load alone. A cross-check against the ~313 MW N+1 genset backup (sized to IT +
mechanical) shows the backup envelope is consistent with the 275 MW IT figure only at
the efficient end of the PUE band (``implied_pue_from_backup`` ≈ 1.14).
"""

from __future__ import annotations

from typing import Any, Literal, cast

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import active_profile

# The air-permit-disclosed facility constants (genset count/rating, IT load, the permit
# citation) are now per-site: they live on ``SiteProfile.facility`` (Lima, from Air PTI
# P0138965) and ``derive_power_basis`` reads them from the active site. A site with no
# documented facility (``facility is None``) has no power basis — see ``derive_power_basis``.
# (watermark.hydrology.cooling still mirrors the Lima constants; tests/facility/test_power.py
# guards the two against drift.)

# --- Cooling / mechanical overhead (issue #87) -------------------------------
# PUE = total facility power / IT power, a banded ASSUMPTION read from the reference
# yaml (not a disclosure). The cooling share of facility power is (PUE-1)/PUE; the
# 2026-06-10 call's "~30% of power for cooling" pins the ceiling at PUE ~1.43.
_PUE_CITE = (
    "PUE = total facility power / IT power, banded assumption "
    "(data/reference/compute/rack-density.yaml pue_band); ceiling 1.43 admits "
    "cooling-dominated designs (~30% of facility power for cooling, 2026-06-10 "
    "facility-design call)"
)


def _load_pue_band(settings: Settings) -> tuple[float, float]:
    """Read the (low, high) PUE band from the committed reference data."""
    path = settings.reference_dir / "compute" / "rack-density.yaml"
    data = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))
    lo, hi = (float(x) for x in data["pue_band"])
    return lo, hi


# --- On-site generation cycle (issue #90) ------------------------------------
# Net electrical efficiency bands (fuel chemical energy -> net AC power): the
# "power-loss coefficient" per generation cycle, as stated assumptions. Heat rate
# (fuel per MWh) is the derived inverse via MMBtu/MWh = 3.412 / efficiency.
_MMBTU_PER_MWH = 3.412142  # 1 MWh = 3.412 MMBtu (thermal-energy equivalent)

_ETA_SIMPLE = 0.38  # simple-cycle / reciprocating genset; band ~0.33-0.43
_ETA_SIMPLE_CITE = (
    "simple-cycle net electrical efficiency ~0.38 (band 0.33-0.43): the prime mover "
    "drives the generator directly and exhaust heat is lost; consistent with the "
    "disclosed emergency reciprocating diesel gensets (the active site's air permit)"
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
    "(band ~0.1-0.3) applied to the IT load: an ADDITIONAL consumptive pathway "
    "beyond IT cooling. Cross-ref watermark.hydrology.cooling, whose makeup figure covers "
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
      (cross-ref :mod:`watermark.hydrology.cooling`).

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
    convention from the air permit), carrying a ``low``/``high`` range (#760) that
    brackets the 250-300 MW the genset count supports. ``pue`` and ``facility_draw``
    likewise carry their bands as a first-class range rather than as sibling
    ``*_low``/``*_high`` fields. Mirrors the shape of
    :class:`watermark.hydrology.model.CoolingBasis` so the two subsystems read alike.
    """

    model_config = ConfigDict(extra="forbid")

    # Genset / backup basis — present only for an air-permit-grounded facility. A
    # site-plan-grounded facility with no disclosed generation (Urbana) leaves these
    # ``None``: there is no fabricated fleet, so no backup or N+1 cross-check.
    genset_count: ProvenancedValue | None = None  # count (document)
    genset_rating: ProvenancedValue | None = None  # MW each (document)
    backup_power: ProvenancedValue | None = None  # MW total backup (derived)
    it_load: ProvenancedValue  # MW central (document-anchored or screening) + low/high band (#760)
    # Cooling / mechanical overhead (issue #87): PUE is a banded ASSUMPTION; the band
    # (pue.low efficient .. pue.high cooling-dominated ~1.43) drives the IT->total
    # facility_draw translation (the first-class downstream output). pue.value = band mean.
    pue: ProvenancedValue  # PUE central (band mean) + low/high band (assumption)
    cooling_share_high: ProvenancedValue  # (pue.high-1)/pue.high ~0.30, the call's cooling share
    # MW total facility draw = IT central x PUE central; facility_draw.low/high bracket the
    # efficient (x pue.low) .. cooling-dominated (x pue.high) ends (derived, #760).
    facility_draw: ProvenancedValue
    implied_pue_from_backup: ProvenancedValue | None = None  # backup / IT — N+1 cross-check vs #33
    cooling_overhead_note: str = (
        "Cooling/mechanical overhead is a banded ASSUMPTION (PUE = total/IT), not a "
        "disclosure. The N+1 genset backup is sized to IT + mechanical, so it covers "
        "the facility draw only at the efficient PUE end (see implied_pue_from_backup); "
        "a cooling-dominated PUE (~1.43) implies either a lower IT load or backup not "
        "covering full mechanical (open vs #33). facility_draw is the figure downstream "
        "demand/economics (#91) should use, not IT load alone."
    )
    # On-site generation cycle (issue #90): both simple- and combined-cycle as
    # labeled scenarios, each carrying its net-efficiency (the "power-loss
    # coefficient") and the fuel/water it implies. The band is the simple→combined
    # spread; the disclosed units are backup, so this is a scenario, not a fact.
    generation: list[GenerationConfig]
    generation_note: str = (
        "On-site generation cycle is an OPEN EVIDENCE QUESTION: the disclosed gensets "
        "(see the active site's air permit) are emergency BACKUP reciprocating gensets "
        "(simple-cycle by nature). Whether any PRIMARY on-site generation exists, and "
        "its cycle, is unproven (#33) — the configs below are scenarios labeled simple "
        "(single-phase) vs combined (double-phase)."
    )
    method: str = "air-permit genset count x rating -> N+1 backup -> IT load"

    def generation_config(self, cycle: GenerationCycle) -> GenerationConfig | None:
        """The simple- or combined-cycle generation scenario, by cycle label."""
        return next((g for g in self.generation if g.cycle == cycle), None)

    @property
    def cooling_overhead_mw(self) -> float:
        """Central cooling/mechanical overhead = facility draw - IT load (MW)."""
        return round(self.facility_draw.value - self.it_load.value, 1)


def _generation_configs(it_load_mw: float) -> list[GenerationConfig]:
    """The simple- and combined-cycle generation scenarios (issue #90).

    Each carries a provenance-tagged net electrical efficiency (the "power-loss
    coefficient") and a derived heat rate; the combined cycle additionally carries
    the steam-loop water pathway (sized to ``it_load_mw``), cross-referenced to
    :mod:`watermark.hydrology.cooling`.
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
    steam_mgd = it_load_mw * 1_000.0 * 24.0 * _STEAM_WATER_GAL_PER_KWH / 1_000_000.0
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
            "rule out (cross-ref watermark.hydrology.cooling)."
        ),
    )
    return [simple, combined]


def derive_power_basis(*, settings: Settings | None = None) -> PowerBasis | None:
    """Derive the active site's campus power basis from its disclosed air-permit facility.

    Returns ``None`` for a site with **no documented facility** (``SiteProfile.facility is
    None``) — the grid stack then emits the per-site grid backdrop without a fabricated
    campus load share. Reads the banded PUE assumption from the committed reference data for
    the IT->total ``facility_draw`` translation (issue #87); ``settings`` defaults to
    :func:`watermark.config.get_settings`.
    """
    settings = settings or get_settings()
    fac = active_profile(settings).facility
    if fac is None or fac.it_load_mw is None:
        return None
    pue_lo, pue_hi = _load_pue_band(settings)
    pue_central = (pue_lo + pue_hi) / 2.0
    cooling_share_hi = (pue_hi - 1.0) / pue_hi  # cooling as a share of facility power
    draw_central = fac.it_load_mw * pue_central

    # IT-load provenance: permit-grounded (``from_document``, Lima/Fort Wayne) vs a
    # floor-area SCREENING inference (``derived``, Urbana). Exactly one citation grounds
    # it (SiteFacility-validated); never present a screening bracket as a disclosure.
    load_cite = fac.air_permit_citation or fac.it_load_citation or ""
    if fac.air_permit_citation is not None:
        it_load_pv = ProvenancedValue.from_document(fac.it_load_mw, "MW", citation=load_cite)
    else:
        it_load_pv = ProvenancedValue.derived(fac.it_load_mw, "MW", citation=load_cite)
    it_load_pv = it_load_pv.with_range(low=fac.it_load_low_mw, high=fac.it_load_high_mw)

    # Genset backup + N+1 cross-check only when the facility discloses gensets (an air
    # permit). A site-plan-grounded facility leaves these ``None`` — no fabricated fleet.
    genset_count_pv: ProvenancedValue | None = None
    genset_rating_pv: ProvenancedValue | None = None
    backup_pv: ProvenancedValue | None = None
    implied_pue_pv: ProvenancedValue | None = None
    method = "floor-area screening IT load x PUE band -> facility draw (no disclosed gensets)"
    if fac.genset_count is not None and fac.genset_mw is not None:
        backup_mw = fac.genset_count * fac.genset_mw  # ~313 MW for Lima
        implied_pue = backup_mw / fac.it_load_mw  # if backup == IT + mechanical (N+1)
        genset_count_pv = ProvenancedValue.from_document(
            float(fac.genset_count), "count", citation=load_cite
        )
        genset_rating_pv = ProvenancedValue.from_document(fac.genset_mw, "MW", citation=load_cite)
        backup_pv = ProvenancedValue.derived(
            round(backup_mw, 1),
            "MW",
            citation=f"{fac.genset_count} gensets x {fac.genset_mw:g} MW each (the site's air permit)",
        )
        implied_pue_pv = ProvenancedValue.derived(
            round(implied_pue, 2),
            "ratio",
            citation=(
                f"{round(backup_mw, 1):g} MW N+1 backup / {fac.it_load_mw:g} MW IT: the PUE "
                "implied if the genset backup is sized to the full IT + mechanical load (#33)"
            ),
        )
        method = "air-permit genset count x rating -> N+1 backup -> IT load"

    return PowerBasis(
        generation=_generation_configs(fac.it_load_mw),
        genset_count=genset_count_pv,
        genset_rating=genset_rating_pv,
        backup_power=backup_pv,
        it_load=it_load_pv,
        method=method,
        implied_pue_from_backup=implied_pue_pv,
        pue=ProvenancedValue.assume(
            round(pue_central, 3),
            "ratio",
            why=f"{_PUE_CITE} (band mean of {pue_lo:g} efficient .. {pue_hi:g} cooling-dominated)",
            low=pue_lo,
            high=pue_hi,
        ),
        cooling_share_high=ProvenancedValue.derived(
            round(cooling_share_hi, 3),
            "fraction",
            citation=f"(PUE-1)/PUE at PUE={pue_hi:g} — cooling share of facility power",
        ),
        facility_draw=ProvenancedValue.derived(
            round(draw_central, 1),
            "MW",
            citation=f"{fac.it_load_mw:g} MW IT x PUE {pue_central:g} (band mean) — total facility draw",
            low=round(fac.it_load_mw * pue_lo, 1),
            high=round(fac.it_load_mw * pue_hi, 1),
        ),
    )
