"""Cited receiving-stream 7Q10 low flows.

Loads ``data/reference/hydrology/low-flow-7q10.yaml`` into a lookup of
``receiving_water -> ProvenancedValue`` (the 7Q10 in cfs, ``source=document``).
NWIS does not expose the regulatory 7Q10, so this committed, cited table is the
grounded source; :func:`bosc.hydrology.connectors.nwis.observed_min_discharge`
only cross-checks it.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from bosc.config import Settings, get_settings
from bosc.hydrology.model import ProvenancedValue


def _normalize(water: str) -> str:
    """Normalize a receiving-water name for lookup.

    ``"Dug Run at River Mile 3.1"`` and ``"Dug Run"`` resolve to the same key.
    """
    base = re.split(r"\s+(?:at|near|@)\s+", water, maxsplit=1, flags=re.IGNORECASE)[0]
    return base.strip().lower()


def _reference_path(settings: Settings) -> Any:
    return settings.data_dir / "reference" / "hydrology" / "low-flow-7q10.yaml"


def load_low_flows(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Return ``{normalized receiving water -> 7Q10 ProvenancedValue}``."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ProvenancedValue] = {}
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict) or entry.get("seven_q10_cfs") is None:
            continue
        out[_normalize(str(name))] = ProvenancedValue(
            value=float(entry["seven_q10_cfs"]),
            unit="cfs",
            source=str(entry.get("source", "document")),
            citation=entry.get("citation"),
            confidence=str(entry.get("confidence", "high")),
        )
    return out


def low_flow_for(
    receiving_water: str, *, settings: Settings | None = None
) -> ProvenancedValue | None:
    """Look up the cited 7Q10 for one receiving water, or ``None`` if uncited."""
    return load_low_flows(settings=settings).get(_normalize(receiving_water))


def low_flow_context(receiving_water: str, *, settings: Settings | None = None) -> dict[str, Any]:
    """Return the cited ``context`` block (1Q10, summer 30Q10, ...) for a stream, or ``{}``."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    target = _normalize(receiving_water)
    for name, entry in (data.get("streams") or {}).items():
        if _normalize(str(name)) == target and isinstance(entry, dict):
            ctx = entry.get("context")
            return dict(ctx) if isinstance(ctx, dict) else {}
    return {}
