"""GreenOps — Watermark's own compute footprint, published to its own standard (#1076).

The sibling of :mod:`watermark.economics`: where economics measures what a *place* is,
this measures what *we* consume to run the platform — compute, AI inference, electricity,
water — assembled into a :class:`~watermark.greenops.model.GreenopsReport` the
``/about/sustainability`` page reads as a global bundle feed.

Per-source billing/usage connectors (AWS Cost Explorer + Customer Carbon Footprint Tool,
Anthropic Admin usage, GitHub Actions, EPA eGRID) live under ``connectors/`` and reach
external services through the shared ``watermark.connectors.cached_get`` cache/offline/
fixture machinery. This issue (#1077) is the scaffold — package, config surface, model
contract, CLI group; the connectors and the usage→electricity→water derivation land in
#1078-#1083.

**Discipline:** the platform's own footprint is *modeled, not metered*. Every figure is
``reference`` / ``derived`` / ``assumption``, never ``connector``-``verified``
(:meth:`GreenopsReport.assert_no_verified`).
"""

from __future__ import annotations

from watermark.greenops.footprint import (
    FootprintInputs,
    derive_footprint,
    footprint_reference_path,
    load_footprint,
    load_footprint_inputs,
    placeholder_report,
    write_footprint,
)
from watermark.greenops.model import (
    AiByTask,
    ComputeByFunction,
    ElectricitySeries,
    GreenopsPeriod,
    GreenopsReport,
    HeadlineFigure,
    MethodologyItem,
    NamedQuantity,
    WaterDraw,
)

__all__ = [
    "AiByTask",
    "ComputeByFunction",
    "ElectricitySeries",
    "FootprintInputs",
    "GreenopsPeriod",
    "GreenopsReport",
    "HeadlineFigure",
    "MethodologyItem",
    "NamedQuantity",
    "WaterDraw",
    "derive_footprint",
    "footprint_reference_path",
    "load_footprint",
    "load_footprint_inputs",
    "placeholder_report",
    "write_footprint",
]
