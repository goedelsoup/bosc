"""Facility compute / AI-capacity derivation.

The semantic companion to :mod:`watermark.hydrology` (water) and the economics
baseline (demand): "what compute capacity does the facility provide?" Derives the
data-center campus's accelerator count and aggregate FLOPS from disclosed power,
water, and footprint figures by three independent methods that bracket the answer,
in the :mod:`watermark.hydrology.cooling` idiom — every input tagged
document/connector/assumption/derived, the range reported honestly, nothing
presented as a measured fact about the facility.

Re-exports are **lazy** (PEP 562): importing this package no longer eagerly pulls in
``compute``/``power`` (which reach ``watermark.config`` -> ``watermark.sites``). That
matters because ``watermark.sites._profiles`` imports :mod:`watermark.facility.screening`
to build its IT-load brackets — an eager re-export would make that a circular import.
The dependency-free ``screening`` submodule imports fine on its own; the heavier names
below resolve on first attribute access.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from watermark.facility.compute import derive_compute_capacity
    from watermark.facility.model import AcceleratorScenario, ComputeCapacity, ProfileScenario
    from watermark.facility.power import GenerationConfig, PowerBasis, derive_power_basis

__all__ = [
    "AcceleratorScenario",
    "ComputeCapacity",
    "GenerationConfig",
    "PowerBasis",
    "ProfileScenario",
    "derive_compute_capacity",
    "derive_power_basis",
]

# name -> submodule holding it; resolved on first access so package import stays light.
_LAZY: dict[str, str] = {
    "derive_compute_capacity": "watermark.facility.compute",
    "AcceleratorScenario": "watermark.facility.model",
    "ComputeCapacity": "watermark.facility.model",
    "ProfileScenario": "watermark.facility.model",
    "GenerationConfig": "watermark.facility.power",
    "PowerBasis": "watermark.facility.power",
    "derive_power_basis": "watermark.facility.power",
}


def __getattr__(name: str) -> object:
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
