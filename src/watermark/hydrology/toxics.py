"""Toxic-load x assimilative-capacity screen for the industrial water dischargers.

:mod:`watermark.hydrology.assimilative` screens the three *municipal* WWTPs against
their receiving stream's cited 7Q10. This module extends that screen to the
*industrial* side: the EPA RSEI facilities that release toxics **to water**
(:mod:`watermark.rsei`), placed on the same receiving reaches and read against the same
cited low flows (:mod:`watermark.hydrology.lowflow`).

The headline the data carries: the county's highest-RSEI-Score water dischargers —
INEOS, Lima Refining, PCS Nitrogen — cluster on the **Ottawa River at Lima**, whose
cited 7Q10 is **0.2 cfs (1Q10 = 0)**. The toxic load is largest exactly where the
stream's assimilative capacity is smallest, and that floor coincides with the
May-Oct growing-season precipitation deficit the report already frames.

Provenance discipline (the corpus is litigation evidence):

* **Receiving water** is resolved on a ladder, never invented —
  1. a coordinate/name match to an EPA **ECHO** facility that carries a cited
     receiving water (``connector``);
  2. otherwise, membership in the Ottawa River industrial corridor at Lima, a
     coordinate-cluster **inference** (``assumption``) flagged as such;
  3. otherwise left ``None`` and reported "uncharacterized".
* The **screening concentration** (annual reported water pounds carried at the
  receiving stream's 7Q10) is a coarse, order-of-magnitude ``derived`` value: it
  assumes the reported water releases enter that reach, annualized over the
  facility's reporting years, fully mixed at design low flow, with no decay or mixing zone.
  It is a *screen*, not a permit determination or a measured concentration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology import units
from watermark.hydrology.lowflow import _normalize, load_low_flows
from watermark.hydrology.model import ProvenancedValue, SourceKind
from watermark.logging import get_logger
from watermark.rsei import RseiFacility, load_inventory
from watermark.sites import active_profile

if TYPE_CHECKING:
    from pathlib import Path

log = get_logger(__name__)

# lbs/day -> mg/L at a flow Q: mg/L = (lbs/day) / (MGD * 8.34). The 8.34 lb per
# (mg/L · MG) factor is the standard regulatory mass-balance conversion; cfs->MGD
# goes through units.cfs_to_mgd (1 cfs ≈ 0.6464 MGD). Used only for the screening
# concentration below.
_LBS_PER_MGL_MGD = 8.34

# The receiving-water industrial corridor box + its inferred receiving water are per-site
# (active SiteProfile: toxic_corridor_bbox, receiving_water_name). A facility inside the box
# without an independently cited receiving water is *inferred* to discharge there
# (tagged `assumption`).

# Spatial-join tolerance (degrees ~ 0.0018 ≈ 200 m at this latitude) for matching an
# RSEI facility to an ECHO permit by coordinate.
_MATCH_DEG = 0.0018


# --- Models ----------------------------------------------------------------
class ToxicDischargeScreen(BaseModel):
    """One RSEI water-releasing facility read against its receiving stream's 7Q10."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    rsei_facility_id: str
    latitude: float | None = None
    longitude: float | None = None

    # RSEI modeled toxic magnitude (EPA's output, not a BOSC estimate).
    score: float
    cancer_score: float
    water_pounds: float  # cumulative pounds released to water over the record
    annual_water_pounds: float  # derived: water_pounds / count of reporting years
    year_span: str | None = None  # "1988-2022"
    top_water_chemical: str | None = None

    # Resolved discharge target.
    npdes_id: str | None = None  # matched ECHO permit, if any
    receiving_water: str | None = None
    receiving_water_source: SourceKind | None = None  # connector | assumption
    receiving_water_citation: str | None = None

    # Assimilative context.
    low_flow_7q10: ProvenancedValue | None = None
    screening_concentration: ProvenancedValue | None = None  # mg/L, derived, screen-only

    flag: str  # "critical" | "elevated" | "context" | "uncharacterized"
    detail: str


class ToxicDischargeInventory(BaseModel):
    """The committed screen artifact: provenance meta + ranked dischargers."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    screens: list[ToxicDischargeScreen]

    @property
    def flagged(self) -> list[ToxicDischargeScreen]:
        """Facilities on a near-undiluted reach (the `critical` band)."""
        return [s for s in self.screens if s.flag == "critical"]


# --- Resolution helpers ----------------------------------------------------
def _in_corridor(
    lat: float | None, lon: float | None, bbox: tuple[float, float, float, float]
) -> bool:
    if lat is None or lon is None:
        return False
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _match_echo(fac: RseiFacility, echo: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Closest ECHO facility within the spatial tolerance, else None."""
    if fac.latitude is None or fac.longitude is None:
        return None
    best: dict[str, Any] | None = None
    best_d = _MATCH_DEG
    for e in echo:
        elat, elon = e.get("latitude"), e.get("longitude")
        if elat is None or elon is None:
            continue
        d = ((elat - fac.latitude) ** 2 + (elon - fac.longitude) ** 2) ** 0.5
        if d <= best_d:
            best, best_d = e, d
    return best


def _resolve_receiving_water(
    fac: RseiFacility, echo: list[dict[str, Any]], *, settings: Settings
) -> tuple[str | None, SourceKind | None, str | None, str | None]:
    """Resolve (receiving_water, source, citation, npdes_id) on the provenance ladder."""
    match = _match_echo(fac, echo)
    npdes = match.get("npdes_id") if match else None

    # 1. ECHO carries a cited receiving water -> connector-grounded.
    if match and match.get("receiving_water"):
        return (
            match["receiving_water"],
            "connector",
            f"EPA ECHO {match.get('npdes_id')} — {match['receiving_water']}",
            npdes,
        )

    # 2. The site's industrial receiving-water corridor -> coordinate-cluster inference.
    prof = active_profile(settings)
    bbox = prof.toxic_corridor_bbox
    if _in_corridor(fac.latitude, fac.longitude, bbox):
        return (
            prof.receiving_water_name,
            "assumption",
            (
                f"within the {prof.receiving_water_name} industrial corridor at {prof.place} "
                f"(coordinate cluster {bbox[0]}-{bbox[1]}N, {abs(bbox[3])}-{abs(bbox[2])}W); "
                "receiving water not independently cited"
            ),
            npdes,
        )

    # 3. unresolved.
    return None, None, None, npdes


def _annual_water_pounds(fac: RseiFacility) -> float:
    """Cumulative water pounds annualized over the years the facility actually reported.

    `fac.pounds_by_media["water"]` is the cumulative total across `fac.years` only, so
    the divisor is the *count of reporting years*, never the calendar interval spanned.
    An intermittent reporter (e.g. 1988 and 2022, nothing between) has a 2-year total,
    not a 35-year one; dividing by the span would understate the annual load by the gap
    ratio and drag the screening mg/L below its band threshold. Load-bearing for the
    critical/elevated flag (`_flag`).
    """
    water_lbs = (fac.pounds_by_media or {}).get("water", 0.0)
    reporting_years = len(fac.years) or 1
    return water_lbs / reporting_years


def _screening_concentration(annual_lbs: float, q7: ProvenancedValue) -> ProvenancedValue | None:
    """mg/L if the annual reported water pounds entered the reach at its 7Q10 (screen-only)."""
    mgd = units.cfs_to_mgd(q7.value)
    if mgd <= 0 or annual_lbs <= 0:
        return None
    conc = (annual_lbs / 365.0) / (mgd * _LBS_PER_MGL_MGD)
    return ProvenancedValue.derived(
        round(conc, 3),
        "mg/L",
        citation=(
            f"{annual_lbs:,.0f} lb/yr reported to water / 365 d, fully mixed at the "
            f"{q7.value:g} cfs 7Q10 — screening order-of-magnitude only "
            "(assumes all water releases reach this reach; no decay/mixing zone)"
        ),
        confidence="low",
    )


# Screening-concentration bands (mg/L) on the aggregate water releases carried at
# design low flow. The metric integrates the water-pathway load with the stream's
# assimilative capacity, so it keys on the *water* pathway — not the total RSEI
# Score, which can be air-driven. Coarse screening bands, not water-quality limits.
_CONC_CRITICAL = 1.0  # >1 mg/L aggregate at the 7Q10: effectively undiluted toxic load
_CONC_ELEVATED = 0.01


def _flag(conc: ProvenancedValue | None, receiving: str | None) -> str:
    if receiving is None:
        return "uncharacterized"
    if conc is None:  # resolved location but no cited 7Q10 to screen against
        return "context"
    if conc.value >= _CONC_CRITICAL:
        return "critical"
    if conc.value >= _CONC_ELEVATED:
        return "elevated"
    return "context"


# --- Build -----------------------------------------------------------------
def _load_echo(settings: Settings) -> list[dict[str, Any]]:
    """Load the committed ECHO Maumee NPDES inventory rows (or [] if absent)."""
    path = settings.reference_dir / "echo" / "maumee-wwtp.all-npdes.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return list(data.get("facilities") or [])


def _low_flow_context(settings: Settings) -> dict[str, dict[str, Any]]:
    """Read the per-stream `context` blocks (1Q10, summer 30Q10) from the 7Q10 table."""
    path = settings.reference_dir / "hydrology" / "low-flow-7q10.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, Any]] = {}
    for name, entry in (data.get("streams") or {}).items():
        if isinstance(entry, dict):
            out[_normalize(str(name))] = dict(entry.get("context") or {})
    return out


def _water_releasers(facilities: list[RseiFacility]) -> list[RseiFacility]:
    return [
        f
        for f in facilities
        if f.water_releases or (f.pounds_by_media or {}).get("water", 0.0) > 0.0
    ]


def build_screen(settings: Settings | None = None) -> ToxicDischargeInventory:
    """Screen every RSEI water-releasing facility against its receiving stream's 7Q10."""
    settings = settings or get_settings()
    inv = load_inventory(settings)
    if inv is None:
        raise FileNotFoundError(
            "RSEI inventory not found — run `watermark rsei` first (data/reference/rsei/inventory.yaml)."
        )
    echo = _load_echo(settings)
    low_flows = load_low_flows(settings=settings)

    screens: list[ToxicDischargeScreen] = []
    for fac in _water_releasers(inv.facilities):
        water_lbs = (fac.pounds_by_media or {}).get("water", 0.0)
        annual_lbs = _annual_water_pounds(fac)
        top_water_chem = fac.top_chemicals[0].chemical if fac.top_chemicals else None

        water, src, cite, npdes = _resolve_receiving_water(fac, echo, settings=settings)
        q7 = low_flows.get(_normalize(water)) if water else None
        conc = _screening_concentration(annual_lbs, q7) if q7 else None
        flag = _flag(conc, water)

        if flag == "uncharacterized":
            detail = f"{fac.name}: water releaser with no cited/inferred receiving water."
        else:
            assert water is not None
            q7s = f"{q7.value:g} cfs 7Q10" if q7 else "no cited 7Q10"
            concs = f"; ~{conc.value:g} mg/L at design low flow" if conc else ""
            tag = "inferred" if src == "assumption" else "cited"
            detail = (
                f"{fac.name}: RSEI Score {fac.score:,.0f}, {water_lbs:,.0f} lb to water "
                f"→ {water} ({tag}, {q7s}{concs}) [{flag}]."
            )

        screens.append(
            ToxicDischargeScreen(
                facility=fac.name,
                rsei_facility_id=fac.facility_id,
                latitude=fac.latitude,
                longitude=fac.longitude,
                score=fac.score,
                cancer_score=fac.cancer_score,
                water_pounds=round(water_lbs, 1),
                annual_water_pounds=round(annual_lbs, 1),
                year_span=(f"{fac.first_year}-{fac.last_year}" if fac.first_year else None),
                top_water_chemical=top_water_chem,
                npdes_id=npdes,
                receiving_water=water,
                receiving_water_source=src,
                receiving_water_citation=cite,
                low_flow_7q10=q7,
                screening_concentration=conc,
                flag=flag,
                detail=detail,
            )
        )

    # Rank: critical/elevated first, then by RSEI Score.
    order = {"critical": 0, "elevated": 1, "context": 2, "uncharacterized": 3}
    screens.sort(key=lambda s: (order.get(s.flag, 9), -s.score))

    meta = {
        "subject": "Industrial toxic water dischargers vs cited receiving-stream 7Q10",
        "source": (
            "EPA RSEI (water-media releases) x EPA ECHO (receiving water) x "
            "Ohio EPA cited 7Q10 (data/reference/hydrology/low-flow-7q10.yaml)"
        ),
        "county_fips": inv.county_fips,
        "county_name": inv.county_name,
        "water_releaser_count": len(screens),
        "critical_count": sum(1 for s in screens if s.flag == "critical"),
        "caveats": [
            "Receiving water is ECHO-cited where available, else inferred from the "
            "Ottawa River industrial corridor coordinate cluster (tagged assumption).",
            "The screening concentration is a derived order-of-magnitude value: annual "
            "reported water pounds, fully mixed at the 7Q10, no decay/mixing zone. It is "
            "a screen, not a permit determination or a measured concentration.",
            "RSEI Score is EPA's modeled, population-weighted Risk-Screening Score "
            "(unitless, comparative only).",
        ],
    }
    return ToxicDischargeInventory(meta=meta, screens=screens)


# --- Persistence -----------------------------------------------------------
def write_screen(inv: ToxicDischargeInventory, out_dir: Path) -> Path:
    """Write the screen to ``<out_dir>/toxic-discharge-screen.yaml``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "toxic-discharge-screen.yaml"
    path.write_text(
        yaml.safe_dump(inv.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def load_screen(reference_dir: Path) -> ToxicDischargeInventory | None:
    """Load the committed screen, or None if it hasn't been generated."""
    path = reference_dir / "rsei" / "toxic-discharge-screen.yaml"
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ToxicDischargeInventory(**data)
