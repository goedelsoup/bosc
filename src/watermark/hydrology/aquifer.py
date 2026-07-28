"""Aquifer-parameter derivation from the ODNR well-log census - the ``[inference]`` basis.

The groundwater peer of :mod:`watermark.hydrology.supply`. The census
(:mod:`watermark.hydrology.connectors.ohio_waterwells`) carries the driller-reported
**static water level**, **total depth**, **test yield**, and **aquifer material** for every
logged well - ``[verified]`` for what the log states. This module reduces that population,
by aquifer material, to the hydraulic parameters a drawdown screen needs.

**The method decision (Phase 2), recorded here.** The census has **no pumping-water-level /
drawdown-during-test column**, so a true *specific capacity* (yield / drawdown) - and thus a
per-well transmissivity - is **not** derivable from it. A specific-capacity or Cooper-Jacob
route is therefore off the table. Instead:

* the **static-water-level surface** and **yield distribution** are summarized straight from
  the census (``derived`` → ``[inference]``);
* **saturated thickness** ``b`` is the census's own ``total_depth - static_level`` per well;
* **hydraulic conductivity** ``K``, **specific yield**, and **storativity** come from
  published literature ranges by material (``data/reference/hydrology/aquifer-properties.yaml``,
  Freeze & Cherry 1979 - ``from_reference`` → ``[reference]``);
* **transmissivity** ``T = K*b`` is emitted as an ``[inference]`` **bracket**, never a scalar
  - ``K`` spans orders of magnitude by material, so ``T`` does too, and that width is the
  honest screening result (a site-specific pumping test is the ``[open]`` record that would
  tighten it).

Nothing here is presented as measured. :func:`compute_aquifer_parameters` returns the
per-material parameter set; :func:`aquifer_findings` narrates it in the hydrology finding idiom.
"""

from __future__ import annotations

from math import sqrt
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.hydrology.connectors import ohio_waterwells as oww
from watermark.hydrology.model import HydroFinding, ProvenancedValue
from watermark.logging import get_logger

log = get_logger(__name__)

# Fallback literature properties, mirroring data/reference/hydrology/aquifer-properties.yaml so a
# data_dir without that file still runs. A coupling test pins the two together. Keys are the
# ODNR census's own AQUIFER_TYPE labels (uppercase). K in ft/day; Sy/S dimensionless.
_DEFAULT_PROPERTIES: dict[str, dict[str, Any]] = {
    "LIMESTONE": {
        "confinement": "confined",
        "k_ft_day_low": 0.03,
        "k_ft_day_high": 300.0,
        "specific_yield": 0.01,
        "storativity": 5.0e-4,
        "citation": "Freeze & Cherry (1979) Table 2.2 (limestone/dolomite) + Table 2.4.",
    },
    "DOLOMITE": {
        "confinement": "confined",
        "k_ft_day_low": 0.03,
        "k_ft_day_high": 300.0,
        "specific_yield": 0.01,
        "storativity": 5.0e-4,
        "citation": "Freeze & Cherry (1979) Table 2.2 (dolomite).",
    },
    "SHALE": {
        "confinement": "confined",
        "k_ft_day_low": 3.0e-7,
        "k_ft_day_high": 0.03,
        "specific_yield": 0.02,
        "storativity": 1.0e-4,
        "citation": "Freeze & Cherry (1979) Table 2.2 (shale) - an aquitard.",
    },
    "SAND & GRAVEL": {
        "confinement": "unconfined",
        "k_ft_day_low": 3.0,
        "k_ft_day_high": 3000.0,
        "specific_yield": 0.20,
        "storativity": 0.20,
        "citation": "Freeze & Cherry (1979) Table 2.2 (glacial outwash) + Table 2.4.",
    },
    "GRAVEL": {
        "confinement": "unconfined",
        "k_ft_day_low": 300.0,
        "k_ft_day_high": 30000.0,
        "specific_yield": 0.23,
        "storativity": 0.23,
        "citation": "Freeze & Cherry (1979) Table 2.2 (gravel) + Table 2.4.",
    },
    "SAND": {
        "confinement": "unconfined",
        "k_ft_day_low": 3.0,
        "k_ft_day_high": 300.0,
        "specific_yield": 0.25,
        "storativity": 0.25,
        "citation": "Freeze & Cherry (1979) Table 2.2 (sand) + Table 2.4.",
    },
}

_LITERATURE_CITATION = "Freeze & Cherry (1979) Groundwater, Tables 2.2/2.4 (by material)"


def _properties_path(settings: Settings) -> Path:
    return settings.data_dir / "reference" / "hydrology" / "aquifer-properties.yaml"


def load_aquifer_properties(*, settings: Settings | None = None) -> dict[str, dict[str, Any]]:
    """Literature hydraulic properties by material; the committed YAML or the fallback dict."""
    settings = settings or get_settings()
    path = _properties_path(settings)
    if not path.is_file():
        return _DEFAULT_PROPERTIES
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    materials = data.get("materials") or {}
    return {str(k).upper(): dict(v) for k, v in materials.items()} or _DEFAULT_PROPERTIES


# --- models -----------------------------------------------------------------------------


class AquiferProperty(BaseModel):
    """One aquifer material's census-derived stats + literature hydraulics + derived T bracket."""

    model_config = ConfigDict(extra="forbid")

    material: str
    confinement: str  # confined | unconfined
    well_count: int
    # census-derived [inference] (None when the material's wells report none of that field)
    static_water_level_ft: ProvenancedValue | None
    test_yield_gpm: ProvenancedValue | None
    saturated_thickness_ft: ProvenancedValue | None
    # literature [reference]
    hydraulic_conductivity_ft_day: ProvenancedValue  # value = geomean; low/high = the K range
    specific_yield: ProvenancedValue
    storativity: ProvenancedValue
    # derived [inference] bracket
    transmissivity_ft2_day: ProvenancedValue | None  # T = K*b; None without a thickness


class AquiferParameters(BaseModel):
    """A county's aquifer characterization for the drawdown screen (per-material + totals)."""

    model_config = ConfigDict(extra="forbid")

    county: str
    well_count: int
    domestic_well_count: int
    materials: list[AquiferProperty]
    method: str
    caveats: list[str] = []

    def material(self, name: str) -> AquiferProperty | None:
        key = name.strip().upper()
        return next((m for m in self.materials if m.material == key), None)

    def dominant(self) -> AquiferProperty | None:
        """The material the most wells tap (the drawdown screen's default aquifer)."""
        return max(self.materials, key=lambda m: m.well_count, default=None)


# --- compute ----------------------------------------------------------------------------


def _pctl(values: list[float], p: float) -> float:
    """Linear-interpolated percentile of a non-empty list (p in [0, 1])."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _derived_stat(values: list[float], unit: str, label: str) -> ProvenancedValue | None:
    """A census-derived median with a p25-p75 band, or ``None`` for an empty sample."""
    if not values:
        return None
    return ProvenancedValue.derived(
        round(_pctl(values, 0.5), 2),
        unit,
        f"ODNR well-log census {label}, median (n={len(values)})",
        low=round(_pctl(values, 0.25), 2),
        high=round(_pctl(values, 0.75), 2),
    )


def compute_aquifer_parameters(
    inventory: oww.WaterWellInventory, *, settings: Settings | None = None
) -> AquiferParameters:
    """Reduce a well-log census to per-material aquifer parameters (see the module docstring)."""
    settings = settings or get_settings()
    props = load_aquifer_properties(settings=settings)

    materials: list[AquiferProperty] = []
    for name, lit in props.items():
        wells = [w for w in inventory.wells if (w.aquifer_type or "").strip().upper() == name]
        if not wells:
            continue

        swl = [w.static_water_level_ft for w in wells if w.static_water_level_ft is not None]
        yields = [w.test_rate_gpm for w in wells if w.test_rate_gpm is not None]
        # Saturated thickness per well: total_depth - static_level (both present, positive).
        thickness = [
            w.total_depth_ft - w.static_water_level_ft
            for w in wells
            if w.total_depth_ft is not None
            and w.static_water_level_ft is not None
            and w.total_depth_ft > w.static_water_level_ft
        ]

        k_low = float(lit["k_ft_day_low"])
        k_high = float(lit["k_ft_day_high"])
        k_geomean = sqrt(k_low * k_high)
        k_value = ProvenancedValue.from_reference(
            round(k_geomean, 4),
            "ft/day",
            str(lit.get("citation", _LITERATURE_CITATION)),
            low=k_low,
            high=k_high,
        )

        thickness_pv = _derived_stat(
            thickness, "ft", f"{name} saturated thickness (depth - static)"
        )
        transmissivity: ProvenancedValue | None = None
        if thickness_pv is not None:
            b_lo = thickness_pv.low_or_value
            b_hi = thickness_pv.high_or_value
            transmissivity = ProvenancedValue.derived(
                round(k_geomean * thickness_pv.value, 1),
                "ft^2/day",
                f"T = K x b: literature K ({_LITERATURE_CITATION}) x census saturated thickness "
                f"for {name}. An [inference] BRACKET - K spans orders of magnitude.",
                low=round(k_low * b_lo, 1),
                high=round(k_high * b_hi, 1),
            )

        materials.append(
            AquiferProperty(
                material=name,
                confinement=str(lit.get("confinement", "unknown")),
                well_count=len(wells),
                static_water_level_ft=_derived_stat(swl, "ft", f"{name} static water level"),
                test_yield_gpm=_derived_stat(yields, "gpm", f"{name} reported test yield"),
                saturated_thickness_ft=thickness_pv,
                hydraulic_conductivity_ft_day=k_value,
                specific_yield=ProvenancedValue.from_reference(
                    float(lit["specific_yield"]),
                    "fraction",
                    str(lit.get("citation", _LITERATURE_CITATION)),
                ),
                storativity=ProvenancedValue.from_reference(
                    float(lit["storativity"]),
                    "fraction",
                    str(lit.get("citation", _LITERATURE_CITATION)),
                ),
                transmissivity_ft2_day=transmissivity,
            )
        )

    materials.sort(key=lambda m: m.well_count, reverse=True)
    method = (
        "The census carries no pumping-water-level column, so specific capacity (and a per-well "
        "transmissivity) is not derivable. Static-water-level and yield are summarized from the "
        "census [inference]; K/Sy/storativity are literature [reference] by material; T = K x "
        "census saturated thickness is an [inference] bracket. A site-specific aquifer test is "
        "the [open] record that would replace the literature K."
    )
    return AquiferParameters(
        county=inventory.county,
        well_count=len(inventory.wells),
        domestic_well_count=inventory.use_counts().get("DOMESTIC", 0),
        materials=materials,
        method=method,
        caveats=[
            "No specific capacity: the well-log service reports a static level and a test yield "
            "but not the pumping level during the test.",
            "Transmissivity is a literature-K x census-thickness bracket, not a measured value.",
        ],
    )


def load_aquifer_parameters(*, settings: Settings | None = None) -> AquiferParameters | None:
    """Compute the active site's aquifer parameters from its committed census CSV, or ``None``.

    Reads ``data/reference/ohio-waterwells/<county>.csv`` (the county of the active site).
    """
    settings = settings or get_settings()
    from watermark.sites import active_profile

    profile = active_profile(settings)
    slug = oww.county_slug(profile.county_name)
    path = settings.data_dir / "reference" / "ohio-waterwells" / f"{slug}.csv"
    if not path.is_file():
        return None
    inventory = oww.read_inventory(path, settings=settings)
    return compute_aquifer_parameters(inventory, settings=settings)


# --- findings ---------------------------------------------------------------------------


def aquifer_findings(params: AquiferParameters) -> list[HydroFinding]:
    """Narrate the aquifer characterization in the hydrology finding idiom."""
    subject = f"{params.county} aquifer"
    out: list[HydroFinding] = [
        HydroFinding(
            subject=subject,
            check="aquifer-well-census",
            ok=params.domestic_well_count > 0,
            detail=(
                f"{params.well_count} logged wells; {params.domestic_well_count} domestic - the "
                "private-well population the drawdown screen intersects."
            ),
        ),
        HydroFinding(
            subject=subject,
            check="aquifer-specific-capacity",
            ok=False,  # a standing gap, surfaced (not an error)
            detail=(
                "No pumping-water-level column in the well-log census, so specific capacity / a "
                "measured transmissivity is not derivable. T is a literature-K bracket [inference]; "
                "a site-specific aquifer test is the [open] record that would tighten it."
            ),
        ),
    ]
    dominant = params.dominant()
    if dominant is not None:
        swl = dominant.static_water_level_ft
        swl_txt = f"{swl.value:g} ft (p25-p75 {swl.low:g}-{swl.high:g})" if swl else "unrecorded"
        t = dominant.transmissivity_ft2_day
        t_txt = f"{t.low_or_value:g}-{t.high_or_value:g} ft^2/day" if t else "n/a"
        out.append(
            HydroFinding(
                subject=subject,
                check="aquifer-dominant-material",
                ok=True,
                detail=(
                    f"Dominant material {dominant.material} ({dominant.well_count} wells, "
                    f"{dominant.confinement}); median static level {swl_txt}; transmissivity "
                    f"bracket {t_txt}."
                ),
            )
        )
    return out
