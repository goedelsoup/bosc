"""Facility compute / AI-capacity derivation.

The semantic companion to :mod:`bosc.hydrology` (water) and the economics
baseline (demand): "what compute capacity does the facility provide?" Derives the
data-center campus's accelerator count and aggregate FLOPS from disclosed power,
water, and footprint figures by three independent methods that bracket the answer,
in the :mod:`bosc.hydrology.cooling` idiom — every input tagged
document/connector/assumption/derived, the range reported honestly, nothing
presented as a measured fact about the facility.
"""

from __future__ import annotations

from bosc.facility.compute import derive_compute_capacity
from bosc.facility.model import AcceleratorScenario, ComputeCapacity
from bosc.facility.power import GenerationConfig, PowerBasis, derive_power_basis

__all__ = [
    "AcceleratorScenario",
    "ComputeCapacity",
    "GenerationConfig",
    "PowerBasis",
    "derive_compute_capacity",
    "derive_power_basis",
]
