"""Drainage scope-adequacy audit: the OPC drainage estimate vs the design storm.

The Tetra Tech roundabout OPCs (``data/extracted/aedg/roundabouts.*.opc.yaml``)
each carry a DRAINAGE section, but the engineering sizing is thin: the only
quantified conveyance element is a 6-in subsurface underdrain; the rest of the
drainage cost is a lump-sum "Drainage improvements" line. This module audits that
scope against the **regulatory design rainfall** — the committed NOAA Atlas-14
depth-duration-frequency table for the corridor (:mod:`...connectors.noaa_atlas14`)
— and against the 95% SPS grading & storm plan, which itself shows **no detention**
(:class:`...model.StormPlanInventory`).

It does **not** size the roundabouts' hydraulics: the corpus carries no per-
roundabout footprint area, so a runoff/detention volume would be fabrication. The
audit is a *design-basis / scope-completeness* finding — what the estimate does and
does not quantify — anchored by the verified design-storm depths, mirroring the
zoning-jurisdiction "documented null" elsewhere in the corpus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.models import OPCSummary
from watermark.sites import active_profile

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

# The design-relevant slice of the Atlas-14 grid committed as the corridor reference:
# a short duration (storm-sewer scale) through 24-hr (culvert / detention scale).
_DDF_DURATIONS = ("60-min", "6-hr", "12-hr", "24-hr")
_DDF_RETURN_PERIODS = (2, 10, 25, 50, 100)

_SUMMARY_REL = ("aedg", "roundabouts.summary.opc.yaml")
_DETAIL_REL = ("aedg", "roundabouts.detail.opc.yaml")


# --- Models ----------------------------------------------------------------
class CorridorDdf(BaseModel):
    """The committed NOAA Atlas-14 depth-duration-frequency table for the corridor."""

    model_config = ConfigDict(extra="forbid")

    latitude: float
    longitude: float
    durations: list[str]
    return_periods: list[int]
    depths_in: dict[str, dict[str, float]]  # duration -> {str(return_period): depth in}
    source: str = "NOAA Atlas-14 PDS, English depths (HDSC point query)"

    def depth(self, duration: str, return_period: int) -> float | None:
        return self.depths_in.get(duration, {}).get(str(return_period))


class EstimateDrainageScope(BaseModel):
    """One OPC sub-estimate's drainage section decomposed into sized vs lump-sum."""

    model_config = ConfigDict(extra="forbid")

    name: str
    total: int | None = None
    drainage_subtotal: int | None = None
    itemized: bool = False  # was a line-item breakdown extracted at all?
    sized_amount: int | None = None  # sum of quantified conveyance items (non-LS)
    sized_amount_approximate: bool = False  # any summed sized item was a ``~`` approximate read
    lump_sum_amount: int | None = None  # sum of lump-sum (LS) allocations
    lump_sum_amount_approximate: bool = False  # any summed lump-sum item was a ``~`` read
    sized_fraction: float | None = None  # sized / drainage_subtotal
    sized_items: list[str] = []
    lump_sum_items: list[str] = []


class DrainageFinding(BaseModel):
    """One audit observation (``ok=False`` marks a scope/design-basis gap)."""

    model_config = ConfigDict(extra="forbid")

    subject: str
    check: str
    ok: bool
    detail: str


class DrainageAudit(BaseModel):
    """The assembled drainage scope-adequacy audit."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    scopes: list[EstimateDrainageScope]
    ddf: CorridorDdf | None = None
    detention_in_design: bool | None = None  # StormPlanInventory.detention_shown
    findings: list[DrainageFinding]


# --- Helpers ---------------------------------------------------------------
def _num(x: Any) -> int | None:
    """Coerce a transcribed figure (possibly the ``~12345`` approximate marker) to int.

    Rounds rather than truncates: these are dollar figures rolled up into subtotals, so
    ``int(float(...))`` would bias every subtotal downward by up to a dollar per item. The
    ``~`` marker is stripped here (an int can't carry it); callers that sum ``~`` reads flag
    the aggregate via :func:`_is_approx` so the uncertainty stays visible (data-discipline).
    """
    if x is None:
        return None
    if isinstance(x, int | float):
        return round(x)
    s = str(x).strip().lstrip("~").replace(",", "")
    try:
        return round(float(s))
    except ValueError:
        return None


def _is_approx(x: Any) -> bool:
    """True iff a raw transcribed figure carries the ``~`` approximate marker."""
    return isinstance(x, str) and x.strip().startswith("~")


def _is_lump_sum(item: dict[str, Any]) -> bool:
    return str(item.get("unit", "")).strip().upper() == "LS"


# --- DDF reference persistence ---------------------------------------------
def _ddf_path(settings: Settings) -> Path:
    # Per-site (#326): Lima keeps the legacy un-slugged path; a new site slug-scopes it.
    return settings.data_dir / active_profile(settings).corridor_ddf_relpath


def write_corridor_ddf(ddf: CorridorDdf, *, settings: Settings | None = None) -> Path:
    """Persist the corridor DDF table to the committed reference YAML."""
    settings = settings or get_settings()
    path = _ddf_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {
            "subject": (
                f"NOAA Atlas-14 design-storm depths — {active_profile(settings).corridor_name}"
            ),
            "source": ddf.source,
            "point": {"latitude": ddf.latitude, "longitude": ddf.longitude},
            "units": "inches (point precipitation depth)",
        },
        "ddf": ddf.model_dump(mode="json"),
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_corridor_ddf(*, settings: Settings | None = None) -> CorridorDdf | None:
    """Load the committed corridor DDF table, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _ddf_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = data.get("ddf")
    return CorridorDdf.model_validate(block) if block else None


def build_corridor_ddf(*, settings: Settings | None = None) -> CorridorDdf:
    """Pull the design-relevant Atlas-14 slice for the corridor from the connector."""
    from watermark.hydrology.connectors.noaa_atlas14 import precip_frequency_grid

    settings = settings or get_settings()
    prof = active_profile(settings)
    grid = precip_frequency_grid(lat=prof.design_lat, lon=prof.design_lon, settings=settings)
    depths = {
        dur: {str(rp): round(grid[dur][rp], 2) for rp in _DDF_RETURN_PERIODS}
        for dur in _DDF_DURATIONS
    }
    return CorridorDdf(
        latitude=prof.design_lat,
        longitude=prof.design_lon,
        durations=list(_DDF_DURATIONS),
        return_periods=list(_DDF_RETURN_PERIODS),
        depths_in=depths,
    )


# --- Audit -----------------------------------------------------------------
def _detail_drainage_sections(settings: Settings) -> dict[str, list[dict[str, Any]]]:
    """Map each itemized sub-estimate's printed title -> its DRAINAGE line items."""
    path = settings.extracted_dir.joinpath(*_DETAIL_REL)
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for block in data.values():
        if not isinstance(block, dict):
            continue
        items = (block.get("line_items") or {}) if isinstance(block.get("line_items"), dict) else {}
        drainage = items.get("DRAINAGE")
        title = block.get("title")
        if isinstance(drainage, dict) and isinstance(title, str):
            out[title] = list(drainage.get("items") or [])
    return out


def _scope_for(
    name: str, total: int | None, sub: int | None, items: list[dict[str, Any]]
) -> EstimateDrainageScope:
    if not items:
        return EstimateDrainageScope(name=name, total=total, drainage_subtotal=sub, itemized=False)
    sized = [it for it in items if not _is_lump_sum(it)]
    lump = [it for it in items if _is_lump_sum(it)]
    sized_amt = sum(_num(it.get("total_amount")) or 0 for it in sized)
    lump_amt = sum(_num(it.get("total_amount")) or 0 for it in lump)
    sized_approx = any(_is_approx(it.get("total_amount")) for it in sized)
    lump_approx = any(_is_approx(it.get("total_amount")) for it in lump)
    frac = round(sized_amt / sub, 3) if sub else None
    return EstimateDrainageScope(
        name=name,
        total=total,
        drainage_subtotal=sub,
        itemized=True,
        sized_amount=sized_amt,
        sized_amount_approximate=sized_approx,
        lump_sum_amount=lump_amt,
        lump_sum_amount_approximate=lump_approx,
        sized_fraction=frac,
        sized_items=[str(it.get("description", "")) for it in sized],
        lump_sum_items=[str(it.get("description", "")) for it in lump],
    )


def build_drainage_audit(settings: Settings | None = None) -> DrainageAudit:
    """Audit the OPC drainage scope against the corridor design storm + the 95% plan."""
    settings = settings or get_settings()
    summary = OPCSummary.from_yaml(settings.extracted_dir.joinpath(*_SUMMARY_REL))
    detail = _detail_drainage_sections(settings)

    scopes: list[EstimateDrainageScope] = []
    for se in summary.sub_estimates:
        sub = _num(se.section_subtotals.drainage)
        scopes.append(_scope_for(se.name, _num(se.total), sub, detail.get(se.name, [])))

    program_drainage = sum(s.drainage_subtotal or 0 for s in scopes)
    program_total = sum(s.total or 0 for s in scopes)
    itemized = [s for s in scopes if s.itemized]

    ddf = load_corridor_ddf(settings=settings)
    from watermark.hydrology import stormplan

    plan = stormplan.load_inventory(settings=settings)
    detention = plan.detention_shown if plan is not None else None

    findings = _findings(scopes, program_drainage, program_total, itemized, ddf, detention)
    meta = {
        "subject": "Drainage scope-adequacy: OPC drainage estimate vs the design storm",
        "source": (
            "Tetra Tech roundabout OPC (data/extracted/aedg/roundabouts.*.opc.yaml) vs "
            "NOAA Atlas-14 corridor DDF + the 95% SPS grading & storm plan"
        ),
        "sub_estimate_count": len(scopes),
        "itemized_count": len(itemized),
        "program_drainage_total": program_drainage,
        "program_total": program_total,
        "caveats": [
            "No per-roundabout footprint area exists in the corpus, so the audit does NOT "
            "size runoff/detention volumes — it reports estimate scope vs the verified "
            "design-storm depths only.",
            "Most drainage cost is a lump-sum 'Drainage improvements' line; only one of the "
            "six sub-estimates carries an extracted line-item breakdown.",
        ],
    }
    return DrainageAudit(
        meta=meta, scopes=scopes, ddf=ddf, detention_in_design=detention, findings=findings
    )


def _findings(
    scopes: list[EstimateDrainageScope],
    program_drainage: int,
    program_total: int,
    itemized: list[EstimateDrainageScope],
    ddf: CorridorDdf | None,
    detention: bool | None,
) -> list[DrainageFinding]:
    findings: list[DrainageFinding] = []

    pct = f"{program_drainage / program_total:.1%}" if program_total else "—"
    findings.append(
        DrainageFinding(
            subject="program drainage scope",
            check="line-item-breakdown",
            ok=False,
            detail=(
                f"${program_drainage:,} of drainage across {len(scopes)} sub-estimates "
                f"({pct} of the ${program_total:,} program), but only {len(itemized)} of "
                f"{len(scopes)} carry an extracted line-item breakdown — the rest is a bare "
                "section subtotal."
            ),
        )
    )

    for s in itemized:
        if s.lump_sum_amount and s.drainage_subtotal:
            lump_pct = s.lump_sum_amount / s.drainage_subtotal
            sized = ", ".join(s.sized_items) or "none"
            findings.append(
                DrainageFinding(
                    subject=s.name,
                    check="lump-sum-dominance",
                    ok=lump_pct < 0.5,
                    detail=(
                        f"${s.lump_sum_amount:,} of ${s.drainage_subtotal:,} "
                        f"({lump_pct:.0%}) is lump-sum '{'; '.join(s.lump_sum_items)}'. "
                        f"The only sized conveyance is: {sized}."
                    ),
                )
            )

    if ddf is not None:
        d25 = ddf.depth("24-hr", 25)
        d100 = ddf.depth("24-hr", 100)
        if d25 is not None and d100 is not None:
            findings.append(
                DrainageFinding(
                    subject="design-storm basis",
                    check="design-storm-reference",
                    ok=False,
                    detail=(
                        "No estimate cites a design storm or return period. The corridor "
                        f"design rainfall (NOAA Atlas-14): 25-yr 24-hr {d25:.2f} in, 100-yr "
                        f"24-hr {d100:.2f} in [verified: connector] — the basis the unsized "
                        "storm-sewer / detention scope must meet."
                    ),
                )
            )

    if detention is False:
        findings.append(
            DrainageFinding(
                subject="detention storage",
                check="detention-itemized",
                ok=False,
                detail=(
                    "Neither the OPC drainage scope nor the 95% SPS grading & storm plan "
                    "itemizes detention/retention storage (detention_shown=false), echoing "
                    "the corpus's own open question on the lump-sum DRAINAGE items."
                ),
            )
        )
    return findings
