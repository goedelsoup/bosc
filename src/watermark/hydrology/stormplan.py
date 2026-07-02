"""Ground the Tier-1 stormwater network in the real campus grading & storm plan.

The civil sheet (LMA-1A-C-3104, *Grading & Stormwater Plan*, 95% SPS) is the
authoritative drainage design for campus sub-area 1A. Its pipe connectivity and
inverts are drawn as vector geometry with **no schedule table**, so a routable SWMM
network cannot be reconstructed without invention — and BOSC discipline prefers
omission over invention. What the drawing *does* state, we transcribe:

* the storm-structure **rim-elevation population** (the graded surface), and
* whether any on-site **detention/retention storage** is shown.

The headline grounded fact: the 95% design conveys runoff off-site via catch basins
-> inlets -> storm sewer -> headwall outfalls (with rock check dams and overland
flood routing for erosion/overflow), and shows **no detention, retention, or
infiltration storage**. That is what makes the Tier-1 SWMM-sized basin meaningful:
it is the *absent* control, not a redesign of an existing one.

:func:`refresh_inventory` re-parses the source drawing and rewrites the committed
artifact; :func:`load_inventory` reads that reviewed artifact (the hot path, like the
rest of the extract stage). The 70 MB drawing is parsed once, offline, by the refresh
tool — never on a CLI/agent call.
"""

from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path

import yaml

from watermark.config import Settings, get_settings
from watermark.hydrology.model import HydroFinding, ProvenancedValue, StormPlanInventory
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

# Source drawing (ODG, an OpenDocument export of the civil DWG set) and the committed
# inventory artifact, both relative to ``data/``.
_SOURCE_REL = "documents/plans/bistrozzi-plans/LMA1A-95-SPS-2025-10-28.odg"
_PLAN_YAML_REL = "extracted/plans/LMA1A-95-SPS-2025-10-28.plan.yaml"
_INVENTORY_REL = "extracted/plans/lma1a.storm-inventory.yaml"

# Conveyance/structure labels we report when the legend names them (presence, not count;
# per-instance counting needs reliable geometry parsing we deliberately avoid).
_STRUCTURE_LABELS = [
    "CATCH BASIN",
    "CURB & GUTTER INLET",
    "INLET MANHOLE",
    "MANHOLE",
    "STORM SEWER",
    "UNDERDRAIN",
    "ROOF DRAIN",
    "TRENCH DRAIN",
]
_CONVEYANCE_LABELS = [
    "SWALE",
    "HEADWALL",
    "CHANNEL PROTECTION",
    "CHECK DAM",
    "FLOOD ROUTING",
    "CONTAINMENT",
]
# On-site storage we explicitly look for so the *negative* is auditable.
_STORAGE_TERMS = [
    "DETENTION",
    "RETENTION",
    "FOREBAY",
    "POND",
    "BIORETENTION",
    "INFILTRATION BASIN",
    "OUTLET CONTROL",
]
_PIPE_SIZE_RE = re.compile(
    r'(\d+)"\s+(?:DIA\.?\s+)?'
    r"(?:HDPE|INLINE DRAIN|TRENCH DRAIN|PERFORATED UNDERDRAIN|FIBER TRENCH|PIPE UNDERDRAIN)"
)
_RIM_RE = re.compile(r"RIM\s*=\s*(\d+\.\d+)")


def _odg_text(odg_path: Path) -> str:
    """Decode the ODG drawing's text payload (entities unescaped).

    The drawing's stored CRC-32 for ``content.xml`` is off (the data inflates fine;
    ``unzip`` ignores it), so we disable CRC validation for that one member.
    """
    with zipfile.ZipFile(odg_path) as zf, zf.open("content.xml") as fp:
        fp._expected_crc = None  # type: ignore[attr-defined]  # skip the bad stored CRC
        raw = fp.read().decode("utf-8", errors="replace")
    return html.unescape(raw)


def _plan_meta(plan_yaml: Path) -> dict[str, str]:
    """Pull sheet metadata from the reviewed vision extraction (single source of truth)."""
    data = yaml.safe_load(plan_yaml.read_text(encoding="utf-8")) or {}
    plan = data.get("plan", {}) if isinstance(data, dict) else {}
    engineer = None
    for party in plan.get("prepared_by") or []:
        if isinstance(party, dict) and "civil" in str(party.get("discipline", "")).lower():
            engineer = party.get("name")
            break
    return {
        "sheet_id": str(plan.get("sheet_id", "1A-C-3104")),
        "discipline": str(plan.get("discipline", "Grading & Storm Plan")),
        "phase": str(plan.get("phase", "95% SPS Design")),
        "status": str(plan.get("status", "Not For Construction")),
        "engineer": engineer or "",
    }


def refresh_inventory(
    *, settings: Settings | None = None, write: bool = True
) -> StormPlanInventory:
    """Parse the source drawing into a :class:`StormPlanInventory` and (optionally) commit it."""
    settings = settings or get_settings()
    odg_path = settings.data_dir / _SOURCE_REL
    text = _odg_text(odg_path)
    meta = _plan_meta(settings.data_dir / _PLAN_YAML_REL)

    rims = [float(x) for x in _RIM_RE.findall(text)]
    if not rims:
        raise ValueError(f"no RIM= elevations found in {odg_path}")
    rim_min, rim_max = min(rims), max(rims)
    cite = f"{_SOURCE_REL} (sheet {meta['sheet_id']}, {meta['phase']})"

    structures = [s.title() for s in _STRUCTURE_LABELS if s in text]
    conveyance = [c.title() for c in _CONVEYANCE_LABELS if c in text]
    # Keep plausible nominal sizes only; garbled CAD path digits glue onto callouts.
    sizes = sorted({int(m) for m in _PIPE_SIZE_RE.findall(text) if 2 <= int(m) <= 48}, reverse=True)
    storage_present = [t for t in _STORAGE_TERMS if t in text]

    inv = StormPlanInventory(
        sheet_id=meta["sheet_id"],
        discipline=meta["discipline"],
        phase=meta["phase"],
        status=meta["status"],
        source_path=_SOURCE_REL,
        engineer=meta["engineer"] or None,
        rim_labels=len(rims),
        rim_distinct=len(set(rims)),
        rim_min=ProvenancedValue.from_document(rim_min, "ft", cite),
        rim_max=ProvenancedValue.from_document(rim_max, "ft", cite),
        relief=ProvenancedValue.derived(
            round(rim_max - rim_min, 2), "ft", f"max - min storm-structure rim, {cite}"
        ),
        structure_types=structures,
        pipe_sizes_in=[float(s) for s in sizes],
        conveyance_features=conveyance,
        detention_shown=bool(storage_present),
        storage_terms_searched=[t.title() for t in _STORAGE_TERMS],
        note=(
            "Pipe connectivity/inverts are drawn as vector geometry with no schedule "
            "table; a routable network is not transcribed (omission over invention)."
        ),
    )
    if write:
        relpath = active_profile(settings).storm_inventory_relpath
        if relpath is None:
            raise ValueError(
                f"Site '{settings.site}' has no storm_inventory_relpath — "
                "set it in the site profile before running refresh."
            )
        out = settings.data_dir / relpath
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
        )
        log.info("stormplan.refresh", sheet=inv.sheet_id, rims=inv.rim_labels, out=str(out))
    return inv


def load_inventory(*, settings: Settings | None = None) -> StormPlanInventory | None:
    """Load the committed inventory artifact, or ``None`` if unavailable for this site."""
    settings = settings or get_settings()
    relpath = active_profile(settings).storm_inventory_relpath
    if relpath is None:
        return None
    path = settings.data_dir / relpath
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return StormPlanInventory.model_validate(data)


def storm_plan_findings(inv: StormPlanInventory) -> list[HydroFinding]:
    """Render the grounded drainage facts as findings."""
    subject = f"BOSC campus sub-area {inv.sheet_id}"
    conveyance = ", ".join(f.lower() for f in inv.conveyance_features) or "piped conveyance"
    return [
        HydroFinding(
            subject,
            "on-site-detention",
            inv.detention_shown,
            (
                f"{inv.phase} grading & storm plan ({inv.sheet_id}) routes runoff via "
                f"{', '.join(s.lower() for s in inv.structure_types[:4])} to storm sewer "
                f"({conveyance}) but shows "
                f"{'on-site storage' if inv.detention_shown else 'no detention/retention/infiltration storage'}"
                "; post-development peak is conveyed off-site without on-site attenuation"
            ),
        ),
        HydroFinding(
            "BOSC campus grading",
            "graded-relief",
            True,
            (
                f"storm-structure rims span {inv.rim_min.value:.1f}-{inv.rim_max.value:.1f} ft "
                f"({inv.relief.value:.1f} ft relief) across {inv.rim_labels} labels "
                f"({inv.rim_distinct} distinct) [doc: {inv.sheet_id}]"
            ),
        ),
    ]
