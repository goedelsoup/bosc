"""Construction-dewatering cone-of-impact model - the documented multi-well groundwater stress.

The grounded peer of :mod:`watermark.hydrology.drawdown`. Where that module screens a *single
hypothetical* cooling-makeup well, this one models a **real, documented wellfield**: the 44
construction-dewatering wells the developer installed at the BOSC/data-center campus to lower
the water table for **site grading** (``data/reference/ohio-waterwells/lima-campus-dewatering.csv``
- ``[verified]`` ODNR well-log + sealing records). Each well is a Theis/Cooper-Jacob cone; the
field's impact is the **superposition** of all of them, evaluated at each nearby domestic census
well - the quantitative form of the residents' "area well concerns."

Provenance discipline: the wells, rates, aquifer, depths, and install/seal dates are
``[verified]`` (driller-reported). Every transmissivity, radius of influence, and drawdown
derived from them is ``[inference]`` - a Cooper-Jacob screening with **literature** hydraulic
conductivity (:mod:`watermark.hydrology.aquifer`) on an unconfined aquifer, bracketed by that
conductivity's range. ``test_rate_gpm`` is the well's yield-test *capacity*, an upper bound on
the sustained dewatering rate; installs/sealings were staged, so a simultaneous-full-rate
composite is a bound on concurrency, not a metered figure.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from math import sqrt
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import to_float, to_str
from watermark.hydrology._geo import haversine_ft
from watermark.hydrology.aquifer import load_aquifer_properties
from watermark.hydrology.connectors import ohio_waterwells as oww
from watermark.hydrology.drawdown import cooper_jacob_drawdown, radius_of_influence_ft
from watermark.hydrology.model import HydroFinding, ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

# 1 US gallon = 0.133680556 ft^3; x1440 min/day.
GPM_TO_FT3_DAY = 0.133680556 * 1440.0  # ~192.5 ft^3/day per gpm
# Composite drawdown (ft) below which a domestic well is treated as effectively unaffected.
_AFFECTED_THRESHOLD_FT = 1.0

KBand = Literal["low", "central", "high"]


def _aquifer_key(aquifer: str | None, props: dict[str, dict[str, Any]]) -> str:
    """Map a driller aquifer label onto a literature-property key (`SAND & GRAVEL`, etc.)."""
    a = (aquifer or "").upper().strip()
    if a in props:
        return a
    if "SAND" in a and "GRAVEL" in a:  # "GRAVEL & SAND" -> the same material class
        return "SAND & GRAVEL"
    if "GRAVEL" in a:
        return "GRAVEL"
    if "SAND" in a:
        return "SAND"
    return "SAND & GRAVEL"


# --- models -----------------------------------------------------------------------------


class DewateringWell(BaseModel):
    """One construction-dewatering well, verbatim from the ODNR records."""

    model_config = ConfigDict(extra="forbid")

    record_no: str
    operator: str | None
    township: str | None
    aquifer_type: str | None
    well_use: str | None
    static_water_level_ft: float | None
    test_rate_gpm: float | None
    total_depth_ft: float | None
    completion_date: str | None  # ISO
    sealed_date: str | None  # ISO; None/"" -> still active
    longitude: float | None
    latitude: float | None

    @property
    def active(self) -> bool:
        return not (self.sealed_date or "").strip()

    @property
    def saturated_thickness_ft(self) -> float | None:
        if self.total_depth_ft is None or self.static_water_level_ft is None:
            return None
        return max(self.total_depth_ft - self.static_water_level_ft, 1.0)

    def operating_days(self, asof: date) -> int:
        """Days pumped: completion -> sealing (or -> ``asof`` if still active)."""
        if not self.completion_date:
            return 0
        start = date.fromisoformat(self.completion_date)
        end = date.fromisoformat(self.sealed_date) if self.sealed_date else asof
        return max((end - start).days, 1)


class WellCone(BaseModel):
    """One dewatering well's cone of impact (all ``[inference]``)."""

    model_config = ConfigDict(extra="forbid")

    record_no: str
    aquifer_type: str | None
    q_gpm: float | None
    saturated_thickness_ft: float | None
    operating_days: int
    active: bool
    transmissivity_ft2_day: ProvenancedValue  # value = geomean-K; low/high = the K bracket
    radius_of_influence_ft: ProvenancedValue  # r0 = sqrt(2.25*T*t/S), bracketed


class ImpactedWell(BaseModel):
    """A census well inside the composite cone, with its superimposed drawdown."""

    model_config = ConfigDict(extra="forbid")

    object_id: str
    well_use: str | None
    aquifer_type: str | None
    distance_ft: float  # from the wellfield centroid
    composite_drawdown_ft: ProvenancedValue  # sum of every well's cone at this point


class DewateringImpact(BaseModel):
    """The wellfield's cone of impact: per-well cones + superimposed drawdown on neighbors."""

    model_config = ConfigDict(extra="forbid")

    county: str
    well_count: int
    active_count: int
    total_capacity_mgd: float
    operating_window: str
    centroid_lat: float
    centroid_lon: float
    cones: list[WellCone]
    impacted_wells: list[ImpactedWell]  # domestic census wells over the drawdown threshold
    tag: str = "inference"
    caveats: list[str] = []


# --- load -------------------------------------------------------------------------------


def _dewatering_path(settings: Settings) -> Path | None:
    """The active site's committed dewatering wellfield CSV, or ``None`` if it has none."""
    from watermark.sites import active_profile

    relpath = active_profile(settings).dewatering_wellfield_relpath
    return settings.data_dir / relpath if relpath else None


def load_dewatering_wells(
    path: Path | None = None, *, settings: Settings | None = None
) -> list[DewateringWell]:
    """Load the active site's committed dewatering wellfield, sorted by record number."""
    settings = settings or get_settings()
    path = path or _dewatering_path(settings)
    if path is None or not path.is_file():
        return []
    wells = [
        DewateringWell(
            record_no=str(row["record_no"]),
            operator=to_str(row.get("operator")),
            township=to_str(row.get("township")),
            aquifer_type=to_str(row.get("aquifer_type")),
            well_use=to_str(row.get("well_use")),
            static_water_level_ft=to_float(row.get("static_water_level_ft") or None),
            test_rate_gpm=to_float(row.get("test_rate_gpm") or None),
            total_depth_ft=to_float(row.get("total_depth_ft") or None),
            completion_date=to_str(row.get("completion_date")),
            sealed_date=to_str(row.get("sealed_date")),
            longitude=to_float(row.get("longitude") or None),
            latitude=to_float(row.get("latitude") or None),
        )
        for row in csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")))
    ]
    wells.sort(key=lambda w: w.record_no)
    return wells


# --- compute ----------------------------------------------------------------------------


def _k_band(
    well: DewateringWell, props: dict[str, dict[str, Any]]
) -> tuple[float, float, float, float]:
    """(K_low, K_geomean, K_high, specific_yield) in ft/day for a well's aquifer."""
    lit = props[_aquifer_key(well.aquifer_type, props)]
    k_lo, k_hi = float(lit["k_ft_day_low"]), float(lit["k_ft_day_high"])
    return k_lo, sqrt(k_lo * k_hi), k_hi, float(lit["specific_yield"])


def well_cone(
    well: DewateringWell,
    *,
    asof: date,
    props: dict[str, dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> WellCone | None:
    """One well's cone of impact: transmissivity + radius of influence, bracketed by K.

    ``props`` is the literature aquifer table; a caller looping over many wells passes it once
    (loaded via :func:`load_aquifer_properties`) rather than re-reading it per well.
    """
    settings = settings or get_settings()
    b = well.saturated_thickness_ft
    if b is None or well.test_rate_gpm is None:
        return None
    if props is None:
        props = load_aquifer_properties(settings=settings)
    k_lo, k_geo, k_hi, sy = _k_band(well, props)
    t_days = well.operating_days(asof)
    lit_cite = "literature K (Freeze & Cherry 1979) x saturated thickness, per aquifer material"
    transmissivity = ProvenancedValue.from_reference(
        round(k_geo * b, 1), "ft^2/day", lit_cite, low=round(k_lo * b, 1), high=round(k_hi * b, 1)
    )

    def r0(k: float) -> float:
        return radius_of_influence_ft(k * b, sy, t_days)

    return WellCone(
        record_no=well.record_no,
        aquifer_type=well.aquifer_type,
        q_gpm=well.test_rate_gpm,
        saturated_thickness_ft=round(b, 1),
        operating_days=t_days,
        active=well.active,
        transmissivity_ft2_day=transmissivity,
        radius_of_influence_ft=ProvenancedValue.derived(
            round(r0(k_geo), 0),
            "ft",
            f"Cooper-Jacob r0 = sqrt(2.25*T*t/S), t={t_days} d [inference].",
            low=round(r0(k_lo), 0),
            high=round(r0(k_hi), 0),
        ),
    )


def composite_drawdown_at(
    wells: list[DewateringWell],
    lat: float,
    lon: float,
    *,
    asof: date,
    band: KBand = "central",
    props: dict[str, dict[str, Any]] | None = None,
    settings: Settings | None = None,
) -> float:
    """Superimposed Cooper-Jacob drawdown (ft) at a point from every well in the field.

    ``props`` is the literature aquifer table; pass it once when calling in a loop.
    """
    settings = settings or get_settings()
    if props is None:
        props = load_aquifer_properties(settings=settings)
    total = 0.0
    for w in wells:
        b = w.saturated_thickness_ft
        if b is None or w.test_rate_gpm is None or w.latitude is None or w.longitude is None:
            continue
        k_lo, k_geo, k_hi, sy = _k_band(w, props)
        k = {"low": k_lo, "central": k_geo, "high": k_hi}[band]
        r = max(haversine_ft(lat, lon, w.latitude, w.longitude), 0.5)
        total += cooper_jacob_drawdown(
            w.test_rate_gpm * GPM_TO_FT3_DAY, k * b, sy, r, w.operating_days(asof)
        )
    return total


def compute_dewatering_impact(
    wells: list[DewateringWell],
    *,
    asof: date,
    census: list[oww.WaterWell] | None = None,
    threshold_ft: float = _AFFECTED_THRESHOLD_FT,
    settings: Settings | None = None,
) -> DewateringImpact:
    """Assemble the wellfield's cone of impact + its superimposed drawdown on census wells."""
    from watermark.sites import active_profile

    settings = settings or get_settings()
    props = load_aquifer_properties(settings=settings)  # loaded once, threaded through both helpers
    county = active_profile(settings).county_name.split(" County")[0].strip()
    located = [w for w in wells if w.latitude is not None and w.longitude is not None]
    clat = sum(w.latitude for w in located) / len(located) if located else 0.0  # type: ignore[misc]
    clon = sum(w.longitude for w in located) / len(located) if located else 0.0  # type: ignore[misc]

    cones = [
        c
        for c in (well_cone(w, asof=asof, props=props, settings=settings) for w in wells)
        if c is not None
    ]
    total_gpm = sum(w.test_rate_gpm or 0.0 for w in wells)

    dates = sorted(w.completion_date for w in wells if w.completion_date)
    seals = sorted(w.sealed_date for w in wells if w.sealed_date)
    window = f"{dates[0]} to {seals[-1]}" if dates and seals else (dates[0] if dates else "?")

    impacted: list[ImpactedWell] = []
    for c in census or []:
        if (
            (c.well_use or "").strip().upper() != "DOMESTIC"
            or c.latitude is None
            or c.longitude is None
        ):
            continue
        if haversine_ft(clat, clon, c.latitude, c.longitude) > 2 * 5280:  # screen within 2 mi
            continue
        # Composite drawdown vs K is NON-monotonic at a fixed distance (low K = deep but short
        # reach -> ~0 far away; high K = shallow but long reach), so the central value can lie
        # outside the low/high-K endpoints. Bracket with the min/max envelope over all three.
        band_keys: tuple[KBand, ...] = ("low", "central", "high")
        bands = [
            composite_drawdown_at(
                located, c.latitude, c.longitude, asof=asof, band=b, props=props, settings=settings
            )
            for b in band_keys
        ]
        # Gate on the CENTRAL best-estimate: the "impacted (>1 ft)" list stays honest. Gating on
        # max-of-bands would list wells whose central estimate is well below threshold and only
        # cross at the extreme literature-K end; the per-well bracket (low/high) carries that.
        s_mid = bands[1]
        if s_mid <= threshold_ft:
            continue
        impacted.append(
            ImpactedWell(
                object_id=str(c.object_id),
                well_use=c.well_use,
                aquifer_type=c.aquifer_type,
                distance_ft=round(haversine_ft(clat, clon, c.latitude, c.longitude), 0),
                composite_drawdown_ft=ProvenancedValue.derived(
                    round(s_mid, 1),
                    "ft",
                    "Superposition of every dewatering well's Cooper-Jacob cone [inference].",
                    low=round(min(bands), 1),
                    high=round(max(bands), 1),
                ),
            )
        )
    impacted.sort(key=lambda w: w.composite_drawdown_ft.value, reverse=True)

    return DewateringImpact(
        county=county,
        well_count=len(wells),
        active_count=sum(1 for w in wells if w.active),
        total_capacity_mgd=round(total_gpm * 1440.0 / 1e6, 2),
        operating_window=window,
        centroid_lat=round(clat, 6),
        centroid_lon=round(clon, 6),
        cones=cones,
        impacted_wells=impacted,
        caveats=[
            "Hypothetical-free but screening-grade: the wells/rates/dates are [verified] ODNR "
            "records; every drawdown is [inference] (literature K, Cooper-Jacob, unconfined).",
            "test_rate_gpm is yield-test capacity, an upper bound on the sustained dewatering rate; "
            "installs/sealings were staged, so a simultaneous-full-rate composite bounds concurrency.",
        ],
    )


def load_dewatering_impact(
    *, asof: date, settings: Settings | None = None
) -> DewateringImpact | None:
    """Load the active site's committed wellfield + its county census; compute the cone of impact."""
    from watermark.sites import active_profile

    settings = settings or get_settings()
    wells = load_dewatering_wells(settings=settings)
    if not wells:
        return None
    slug = oww.county_slug(active_profile(settings).county_name)
    census_path = settings.data_dir / "reference" / "ohio-waterwells" / f"{slug}.csv"
    census = (
        oww.read_inventory(census_path, settings=settings).wells if census_path.is_file() else []
    )
    return compute_dewatering_impact(wells, asof=asof, census=census, settings=settings)


# --- findings ---------------------------------------------------------------------------


def dewatering_findings(impact: DewateringImpact) -> list[HydroFinding]:
    """Narrate the dewatering cone of impact in the hydrology finding idiom."""
    subject = f"{impact.county} campus dewatering"
    over5 = sum(1 for w in impact.impacted_wells if w.composite_drawdown_ft.value > 5)
    worst = impact.impacted_wells[0].composite_drawdown_ft.value if impact.impacted_wells else 0.0
    return [
        HydroFinding(
            subject=subject,
            check="dewatering-wellfield",
            ok=True,
            detail=(
                f"{impact.well_count} construction-dewatering wells (~{impact.total_capacity_mgd} MGD "
                f"capacity) operated {impact.operating_window}; {impact.active_count} still active. "
                "The documented groundwater stress behind the 'area well concerns'."
            ),
        ),
        HydroFinding(
            subject=subject,
            check="dewatering-domestic-impact",
            ok=len(impact.impacted_wells) == 0,  # a surfaced impact, not an error
            detail=(
                f"{len(impact.impacted_wells)} domestic census wells fall inside the composite cone "
                f"with >1 ft of [inference] drawdown ({over5} with >5 ft; worst ~{worst:g} ft) - the "
                "population a wellfield of this size could measurably draw down."
            ),
        ),
    ]
