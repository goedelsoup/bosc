"""Cited receiving-stream 7Q10 low flows.

Loads ``data/reference/hydrology/low-flow-7q10.yaml`` into a lookup of
``receiving_water -> ProvenancedValue`` (the 7Q10 in cfs, ``source=document``).
NWIS does not expose the regulatory 7Q10, so this committed, cited table is the
grounded source; :func:`watermark.hydrology.connectors.nwis.observed_min_discharge`
only cross-checks it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.model import ProvenancedValue


def _normalize(water: str) -> str:
    """Normalize a receiving-water name for lookup.

    ``"Dug Run at River Mile 3.1"`` and ``"Dug Run"`` resolve to the same key.
    """
    base = re.split(r"\s+(?:at|near|@)\s+", water, maxsplit=1, flags=re.IGNORECASE)[0]
    return base.strip().lower()


def _reference_path(settings: Settings) -> Path:
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


def _seasonal_value(
    raw: Any, label: str, stream_citation: str | None, note: str | None
) -> ProvenancedValue | None:
    """Wrap one cited seasonal design low flow as a provenanced value (``None`` if absent)."""
    if raw is None:
        return None
    cite = f"{label} — {stream_citation}" if stream_citation else label
    if note:
        cite = f"{cite} ({note})"
    return ProvenancedValue.from_document(float(raw), "cfs", citation=cite, confidence="high")


def seasonal_low_flows(
    receiving_water: str, *, settings: Settings | None = None
) -> tuple[ProvenancedValue | None, ProvenancedValue | None]:
    """The cited summer 30Q10 and driest-week 1Q10 design low flows for a stream.

    Both come from the same committed low-flow table's ``context`` block and carry the stream's
    fact-sheet citation; either is ``None`` when the table omits it — never guessed. This is the
    grounded source the ``hydrology-scenarios`` feed surfaces so the frontend reads seasonal
    floors per-site instead of hardcoding Lima's (#1633). Returns ``(summer_30q10, one_q10)``.
    """
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None, None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    target = _normalize(receiving_water)
    for name, entry in (data.get("streams") or {}).items():
        if _normalize(str(name)) != target or not isinstance(entry, dict):
            continue
        ctx = entry.get("context")
        if not isinstance(ctx, dict):
            return None, None
        cite = entry.get("citation")
        note = ctx.get("note")
        summer = _seasonal_value(ctx.get("thirty_q10_summer_cfs"), "summer 30Q10", cite, note)
        one = _seasonal_value(ctx.get("one_q10_cfs"), "driest-week 1Q10", cite, note)
        return summer, one
    return None, None
