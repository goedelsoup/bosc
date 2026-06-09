"""Cited sanitary design basis for the municipal loop's WWTPs.

Loads ``data/reference/hydrology/sanitary-basis.yaml`` into a :class:`SanitaryBasis`:
per-plant permitted average design flow + peak hydraulic capacity (both
``source=document``), with the derived peaking factor and the system's I/I + SSO
regulatory context. This grounds the Tier-1 sanitary surcharge — the campus's
wet-weather contribution is judged against each plant's *documented* wet-weather
headroom (peak - average), on a system already under an SSO-elimination mandate,
rather than against an invented capacity.

Mirrors :mod:`bosc.hydrology.lowflow`: a committed, cited reference table is the
grounded source; we never invent a design flow.
"""

from __future__ import annotations

from typing import Any

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology.model import ProvenancedValue, SanitaryBasis, SanitaryPlant


def _reference_path(settings: Settings) -> Any:
    return settings.data_dir / "reference" / "hydrology" / "sanitary-basis.yaml"


def _plant_from_entry(name: str, entry: dict[str, Any]) -> SanitaryPlant:
    cite = entry.get("citation")
    src = str(entry.get("source", "document"))
    conf = str(entry.get("confidence", "high"))
    avg = ProvenancedValue(
        value=float(entry["avg_design_flow_mgd"]),
        unit="MGD",
        source=src,
        citation=cite,
        confidence=conf,
    )
    peak: ProvenancedValue | None = None
    peaking: ProvenancedValue | None = None
    if entry.get("peak_capacity_mgd") is not None:
        peak = ProvenancedValue(
            value=float(entry["peak_capacity_mgd"]),
            unit="MGD",
            source=src,
            citation=cite,
            confidence=conf,
        )
        peaking = ProvenancedValue.derived(
            round(peak.value / avg.value, 2),
            "ratio",
            citation=f"peak {peak.value:g} / avg {avg.value:g} MGD ({name}, document-cited)",
        )
    return SanitaryPlant(
        plant=name,
        npdes=entry.get("npdes"),
        routing_id=entry.get("routing_id"),
        receiving_water=entry.get("receiving_water"),
        avg_design_flow=avg,
        peak_capacity=peak,
        peaking_factor=peaking,
        pretreatment=bool(entry.get("pretreatment", False)),
        note=entry.get("note"),
    )


def load_sanitary_basis(*, settings: Settings | None = None) -> SanitaryBasis | None:
    """Load the cited sanitary basis, or ``None`` if the reference table is absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    plants = [
        _plant_from_entry(str(name), entry)
        for name, entry in (data.get("plants") or {}).items()
        if isinstance(entry, dict) and entry.get("avg_design_flow_mgd") is not None
    ]
    return SanitaryBasis(
        plants=plants,
        campus_industrial=ProvenancedValue.from_document(
            float(data.get("campus_industrial_mgd", 0.0)),
            "MGD",
            citation=str(data.get("campus_industrial_citation", "")),
        ),
        ii_remediation_musd=ProvenancedValue.from_document(
            float(data.get("ii_remediation_musd", 0.0)),
            "$M",
            citation=str(data.get("ii_remediation_citation", "")),
        ),
        decree_note=str(data.get("decree_note", "")).strip(),
        source_note=str(data.get("source_note", "")).strip(),
    )
