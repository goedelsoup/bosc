"""Maumee Watershed Nutrient TMDL phosphorus wasteload allocations (WLAs).

Loads ``data/reference/hydrology/maumee-tmdl-wla.yaml`` into a :class:`MaumeeTmdl`:
the individual total-phosphorus WLAs the final TMDL assigns each Lima-loop NPDES
facility, transcribed verbatim from Appendix 4. The Lima WWTPs discharge (via the
Ottawa → Auglaize) into the Maumee, Lake Erie's largest tributary, so each carries
a binding spring-season phosphorus cap on top of the local low-flow dilution
failure the assimilative screen already flags.

Mirrors :mod:`watermark.hydrology.lowflow` and :mod:`watermark.hydrology.sanitary`: a
committed, cited reference table is the grounded source; we never invent a WLA.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.model import MaumeeTmdl, ProvenancedValue, TmdlWla
from watermark.provenance import as_confidence


def _reference_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "maumee-tmdl-wla.yaml"


def load_maumee_tmdl(*, settings: Settings | None = None) -> MaumeeTmdl | None:
    """Load the cited Maumee TMDL WLAs, or ``None`` if the reference table is absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    citation = str(data.get("citation", "")).strip()
    facilities = [
        TmdlWla(
            facility=str(name),
            npdes=entry.get("npdes"),
            spring_tp=ProvenancedValue.from_document(
                float(entry["spring_tp_metric_tons"]),
                "metric tons",
                citation,
                confidence=as_confidence(entry.get("confidence", "high")),
            ),
            daily_tp=ProvenancedValue.from_document(
                float(entry["daily_tp_kg"]),
                "kg/day",
                citation,
                confidence=as_confidence(entry.get("confidence", "high")),
            ),
            note=entry.get("note"),
        )
        for name, entry in (data.get("facilities") or {}).items()
        if isinstance(entry, dict) and entry.get("spring_tp_metric_tons") is not None
    ]
    total = data.get("grouped_load_total") or {}
    grouped_spring = grouped_daily = None
    if total.get("spring_tp_metric_tons") is not None:
        grouped_spring = ProvenancedValue.from_document(
            float(total["spring_tp_metric_tons"]), "metric tons", citation
        )
        grouped_daily = ProvenancedValue.from_document(
            float(total["daily_tp_kg"]), "kg/day", citation
        )
    return MaumeeTmdl(
        facilities=facilities,
        grouped_spring_tp=grouped_spring,
        grouped_daily_tp=grouped_daily,
    )
