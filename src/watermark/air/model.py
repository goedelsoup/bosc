"""Typed, provenance-tagged models for the air-quality Tier-0 emissions inventory (#1175).

The cornerstone is :class:`GensetEmissionFactors`: a backup-genset's emission intensity
on **two bases** — per unit of electrical energy (lb/MWh) and per engine-operating-hour
(lb/hr at rated load) — for each criteria pollutant, every figure a
:class:`watermark.hydrology.model.ProvenancedValue`. Two grounded sources populate it,
reconciled downstream: EPA **AP-42 §3.4** (generic prior, ``basis="ap42"``) and the
site's **air permit** certified rates (``basis="permit"``). See
:mod:`watermark.air.emissions` for the loaders and :func:`watermark.air.emissions.reconcile`.

Contractor/site-agnostic: the model holds *values*, never a hardcoded site — the engine
rating and permit rates are threaded in from the active site's profile / permit extraction.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.model import ProvenancedValue

# The criteria pollutants the Tier-0 inventory tracks. PM2.5 carries the dot in its
# label but is only ever a dict key / string, never a Python identifier.
Pollutant = Literal["NOx", "CO", "PM10", "PM2.5", "SO2", "VOC"]
POLLUTANTS: tuple[Pollutant, ...] = ("NOx", "CO", "PM10", "PM2.5", "SO2", "VOC")

# The two capped pollutants in a synthetic-minor NSR permit — the ones the caps are
# engineered around, and the focus of the reconciliation and cap-exceedance check.
CAPPED_POLLUTANTS: tuple[Pollutant, ...] = ("NOx", "CO")

FactorBasis = Literal["ap42", "permit"]

# Engine load regime. A diesel genset's per-hour emissions depend on load: readiness
# testing runs at low/no load (``idle``), a reliability dispatch carries real facility
# load (``load``). The permit isolates both points (≤25% vs >25% load) and the
# synthetic-minor cap is tracked against them — so the regime is not optional bookkeeping.
LoadRegime = Literal["idle", "load"]


class EmissionFactor(BaseModel):
    """One pollutant's genset emission intensity, on two bases.

    ``per_mwh`` is lb per MWh of engine output; ``per_engine_hour`` is lb per hour for a
    single engine at rated load. The two are consistent through the engine's rated MW
    (``per_engine_hour = per_mwh * engine_mw``). Both carry provenance so a downstream
    tonnage keeps its audit trail.
    """

    model_config = ConfigDict(extra="forbid")

    pollutant: Pollutant
    per_mwh: ProvenancedValue  # lb / MWh (engine output basis)
    per_engine_hour: ProvenancedValue  # lb / hr, one engine at rated load


class GensetEmissionFactors(BaseModel):
    """A backup-genset fleet's emission factors from one grounded source.

    ``basis="ap42"`` carries the full criteria-pollutant set from the generic AP-42 §3.4
    prior; ``basis="permit"`` carries only the pollutants the site permit isolates
    (typically the capped NOx/CO plus a Tier-2 PM factor) — a partial, higher-confidence
    cross-check. Reconciled by :func:`watermark.air.emissions.reconcile`.
    """

    model_config = ConfigDict(extra="forbid")

    basis: FactorBasis
    load_regime: LoadRegime  # the engine load point these per-hour factors represent
    engine_mw: ProvenancedValue  # rated electrical output per engine
    fuel: str  # "ULSD / renewable diesel (HVO)", "diesel", ...
    factors: dict[str, EmissionFactor]  # keyed by Pollutant label
    citation: str  # the grounding source (reference file / permit extraction)
    note: str = ""

    def factor(self, pollutant: Pollutant) -> EmissionFactor | None:
        """The factor for a pollutant, or ``None`` if this basis does not ground it."""
        return self.factors.get(pollutant)

    def pollutants(self) -> list[str]:
        return list(self.factors.keys())


class FactorReconciliation(BaseModel):
    """AP-42 vs permit for one pollutant — the generic prior against the certified rate.

    Reports both per-engine-hour rates and their ratio. AP-42 "uncontrolled" is expected
    to run *hot* versus a modern Tier-2-certified engine, so ``ratio_ap42_over_permit``
    is typically ``> 1`` — the honest signal that the permit rate, not AP-42, is the
    site's truth.
    """

    model_config = ConfigDict(extra="forbid")

    pollutant: Pollutant
    ap42_per_engine_hour_lb: float | None
    permit_per_engine_hour_lb: float | None
    ratio_ap42_over_permit: float | None  # None when either side is absent
    note: str = ""
