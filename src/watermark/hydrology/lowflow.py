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
from watermark.sites import active_profile

# Ohio EPA regulatory SUMMER season — the fixed calendar window the summer design low flow
# (30Q10 summer) governs. This is the window that *selects* the design low flow (summer 30Q10
# in-season, annual 7Q10 otherwise), distinct from the climatic ET0 > precip growing season the
# seasonal scenario reports only as a diagnostic (finding WS-24 / issue 1624). Cited: Ohio EPA
# NPDES permit 2PH00006 (American II WWTP), Part II standard-conditions definitions — "'Summer'
# shall be considered to be the period from May 1 through October 31"; "'Winter' ... November 1
# through April 30." This is boilerplate Ohio EPA permit language, so it applies network-wide for
# Ohio sites; a non-Ohio site pins its own window on its SiteProfile.
OEPA_SUMMER_MONTHS: tuple[str, ...] = ("MAY", "JUN", "JUL", "AUG", "SEP", "OCT")


def summer_season_months(*, settings: Settings | None = None) -> tuple[str, ...]:
    """The regulatory summer-season months for the active site (Ohio EPA May-Oct by default).

    This is the fixed permit calendar window that selects the design low flow — the cited
    summer 30Q10 in-season, the annual 7Q10 otherwise — **not** the climatic ET0 > precip
    growing season, which the seasonal scenario reports separately as a diagnostic (#1624). A
    site whose permit defines a different window overrides via ``SiteProfile.summer_season_months``;
    an empty override inherits the cited Ohio EPA default (:data:`OEPA_SUMMER_MONTHS`).
    """
    settings = settings or get_settings()
    override = active_profile(settings).summer_season_months
    return tuple(str(m).upper() for m in override) if override else OEPA_SUMMER_MONTHS


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


def normalize_permit(permit: str) -> str:
    """Normalize a permit/application id for lookup (``2PD00008*UD`` -> ``2pd00008``).

    Ohio EPA appends a two-letter action suffix to the permit number for each issuance
    (``*UD`` renewal, ``*VD`` modification), so the id printed on a fact sheet is not the id
    ECHO carries. The design low flow is a property of the OUTFALL, not of which issuance is
    current, so the suffix is stripped: a permit-scoped value stays bound across renewals.
    """
    return str(permit).split("*", 1)[0].strip().lower()


def load_permit_low_flows(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Return ``{normalized permit id -> that permit's own cited 7Q10}`` (#1458).

    The **permit-scoped** index over the same committed table :func:`load_low_flows` reads by
    receiving-water name. An entry that declares ``permits:`` is binding for exactly those NPDES
    application / Ohio EPA permit ids and nothing else, because Ohio EPA computes the design low
    flow **at the outfall** — one river can carry several correct, non-interchangeable values (the
    Blanchard's 0.21 cfs at Findlay's RM 56.42 and 7.78 cfs at Ottawa's RM 22.1, 37x apart).

    Name-keying cannot express that: :func:`_normalize` strips ``at …`` on purpose, so every
    reach of one river collapses to one key. The basin screen therefore prefers this index over
    any name match for a facility it can identify by permit; the routed-network solver does not
    read it at all, because it resolves a *reach*, which is not a permit.
    """
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ProvenancedValue] = {}
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict) or entry.get("seven_q10_cfs") is None:
            continue
        permits = entry.get("permits") or []
        if not isinstance(permits, list):
            raise ValueError(f"low-flow entry {name!r}: `permits` must be a list, got {permits!r}")
        for permit in permits:
            key = normalize_permit(str(permit))
            if key in out:
                raise ValueError(
                    f"low-flow permit {permit!r} is claimed by two entries — a permit has exactly "
                    "one design low flow; fix data/reference/hydrology/low-flow-7q10.yaml"
                )
            out[key] = ProvenancedValue(
                value=float(entry["seven_q10_cfs"]),
                unit="cfs",
                source=str(entry.get("source", "document")),
                citation=entry.get("citation"),
                confidence=str(entry.get("confidence", "high")),
            )
    return out


def load_acute_low_flows(*, settings: Settings | None = None) -> dict[str, ProvenancedValue]:
    """Return ``{normalized receiving water -> cited 1Q10 ProvenancedValue}``.

    The **acute** aquatic-life design flow (the 1Q10, the lowest single-day flow expected once
    in 10 years), read from each stream's ``context`` block in the same committed table
    ``load_low_flows`` reads the 7Q10 from — the peer loader the assimilative screen uses to
    match the acute criterion to its own design flow (WS-08 / #1608), the way chronic limits are
    matched to the 7Q10. A stream whose fact sheet omits the 1Q10 is absent (never guessed), so
    the acute dilution ratio is simply not computed for it. A cited 1Q10 of exactly 0 cfs (the
    Ottawa mainstem, which stops at design low flow) is kept — it is the honest "zero acute
    assimilative capacity" signal, not a missing value.
    """
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, ProvenancedValue] = {}
    for name, entry in (data.get("streams") or {}).items():
        if not isinstance(entry, dict):
            continue
        ctx = entry.get("context")
        one = ctx.get("one_q10_cfs") if isinstance(ctx, dict) else None
        if one is None:
            continue
        cite = entry.get("citation")
        out[_normalize(str(name))] = ProvenancedValue(
            value=float(one),
            unit="cfs",
            source="document",
            citation=f"1Q10 (acute design flow) — {cite}" if cite else "cited 1Q10",
            confidence=str(entry.get("confidence", "high")),
        )
    return out


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
    """The cited summer 30Q10 and driest-day 1Q10 design low flows for a stream.

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
        one = _seasonal_value(ctx.get("one_q10_cfs"), "driest-day 1Q10", cite, note)
        return summer, one
    return None, None
