"""Derive the facility's compute / AI capacity by three independent methods.

In the :mod:`bosc.hydrology.cooling` idiom: bracket the answer from several
independent estimators, tag every input by provenance, report the range honestly,
and never overclaim. This extends the chain ``cooling.py`` already builds (air-permit
gensets -> ~275 MW IT load -> cooling water) one step further:
power/water/footprint -> accelerator count -> aggregate FLOPS -> "AI capacity".

Three estimators of the campus IT load, then a shared accelerator chain:

* **Power / gensets (PRIMARY, best-grounded).** Air permit P0138965: 114 gensets
  x 2.75 ekW ≈ 313 MW backup -> ~275 MW IT (N+1, document). Usable accelerator power
  = IT load x an accelerator-power fraction (~0.5-0.7: the share of IT power that
  reaches accelerators vs CPU host / storage / network). Accelerator count =
  accelerator power / per-accelerator all-in power; aggregate FLOPS = count x
  per-accelerator peak FLOPS. This is the central estimate.

* **Cooling-water back-solve (independent cross-check).** The disclosed cooling
  consumptive figures from ``CoolingBasis`` (power x WUE low ≈ 3.1 MGD; FM-2
  blowdown x cycles high ≈ 10 MGD) divided back by WUE recover an IT energy ->
  IT load. The low recovers ~275 MW (the buildout scenario derived 3.1-10 MGD *from*
  275 MW, so the loop closes); the high, if the whole 10 MGD were evaporative cooling,
  implies a much larger load — an UPPER bound only, because FM-2 is not purely
  cooling blowdown. NOTE: this method shares method 1's WUE assumption, so it is a
  consistency check, **not** a fully independent line of evidence — said plainly.

* **Building footprint / floorspace (plans-based, WEAKEST — flagged heavily).**
  Campus LAND area (~340 acres, recorded Bistrozzi parcels) x an assumed building-
  coverage fraction -> building floor area x a data-hall white-space fraction ->
  rack count at an AI rack density (40-140 kW/rack) -> IT power. LAND IS NOT FLOOR
  AREA, and no building footprint is documented in the 95% SPS plans (sheet
  1A-C-3104 is grading & storm only). This method shows the physical UPPER ENVELOPE
  the land could hold; it lands far above the power method precisely because POWER,
  not floor space, is the binding constraint — which corroborates that the
  power-based figure is the operative one. Every input is an assumption.

The methods are reported as a bracket. The conclusion is robust to their
disagreement: even the conservative power method puts the facility at a
hyperscale-AI scale (hundreds of thousands of H100-equivalent accelerators,
hundreds of EFLOP/s peak). Accelerator type/count/utilization are UNDISCLOSED, so
per-chip results are labeled SCENARIOS, and peak (nameplate) FLOPS are kept distinct
from delivered throughput (derated by a labeled MFU).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from bosc.config import Settings, get_settings
from bosc.facility.model import (
    AcceleratorScenario,
    AcceleratorSpec,
    ComputeCapacity,
)
from bosc.facility.power import derive_power_basis
from bosc.hydrology import geo
from bosc.hydrology.cooling import derive_cooling_basis
from bosc.hydrology.model import ProvenancedValue

_L_PER_GAL = 3.785411784
_SQFT_PER_ACRE = 43560.0

# In-corpus provenance for the rack-density / power-fraction figures.
_APPENDIX_CITE = (
    "in-corpus relator data appendix "
    "(data/extracted/legal/select-committee-2026/relator-testimony/"
    "bosc-data-appendix-2026-06-01.md), citing NVIDIA HGX guidance via IntuitionLabs"
)
_REF_CITE = "data/reference/compute/accelerators.yaml (vendor specs, as of 2026-06)"
_WUE_L_PER_KWH = 1.8  # shared with cooling.py — the method-2 dependency we flag

# A defensible cap on the water method's high IT load: the FM-2 10 MGD upper bound,
# if taken as pure evaporative cooling at WUE 1.8, implies ~876 MW — but FM-2 is not
# purely cooling, so we report it as an upper bound and note its weakness rather than
# treating it as a real second load.


def _ref_dir(settings: Settings) -> Path:
    return settings.reference_dir / "compute"


def _load_yaml(path: Path) -> dict[str, Any]:
    return cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _it_load_from_consumptive_mgd(consumptive_mgd: float, wue_l_per_kwh: float) -> float:
    """Invert cooling.py: consumptive water (MGD) / WUE -> IT load (MW)."""
    liters_per_day = consumptive_mgd * 1_000_000.0 * _L_PER_GAL
    # consumptive_mgd = it_mw * 1000 kW/MW * 24 h/day * WUE / L_PER_GAL / 1e6
    return liters_per_day / (1_000.0 * 24.0 * wue_l_per_kwh)


def _flops_value(
    row: dict[str, Any], key: str, *, unit: str = "TFLOP/s"
) -> ProvenancedValue | None:
    """A peak-FLOPS spec field from one accelerator row, or None if absent."""
    val = row.get(key)
    if val is None:
        return None
    return ProvenancedValue.from_reference(float(val), unit, citation=_REF_CITE)


def _spec_from_row(row: dict[str, Any], overhead: float) -> AcceleratorSpec:
    """Build one provenanced :class:`AcceleratorSpec` from a reference-data row."""
    tdp = float(row["tdp_w"])
    all_in = round(tdp * overhead)
    return AcceleratorSpec(
        name=str(row["name"]),
        label=str(row["label"]),
        vendor=str(row["vendor"]),
        generation=str(row["generation"]),
        tdp_w=ProvenancedValue.from_reference(tdp, "W", citation=_REF_CITE, confidence="high"),
        all_in_w=ProvenancedValue.derived(
            float(all_in),
            "W",
            citation=f"chip TDP {tdp:g} W x {overhead:g} host overhead (assumption)",
        ),
        bf16_dense_tflops=ProvenancedValue.from_reference(
            float(row["bf16_dense_tflops"]), "TFLOP/s", citation=_REF_CITE
        ),
        bf16_sparse_tflops=_flops_value(row, "bf16_sparse_tflops"),
        fp8_dense_tflops=_flops_value(row, "fp8_dense_tflops"),
        fp8_sparse_tflops=_flops_value(row, "fp8_sparse_tflops"),
        fp4_dense_tflops=_flops_value(row, "fp4_dense_tflops"),
        fp4_sparse_tflops=_flops_value(row, "fp4_sparse_tflops"),
        int8_tops=_flops_value(row, "int8_tops", unit="TOP/s"),
        gpus_per_server=int(row["gpus_per_server"]),
        cooling=str(row.get("cooling", "")),
    )


def _load_accelerator_specs(settings: Settings) -> tuple[list[AcceleratorSpec], float]:
    """Read the committed accelerator reference data into provenanced specs."""
    data = _load_yaml(_ref_dir(settings) / "accelerators.yaml")
    overhead = float(data["host_overhead_factor"])
    specs = [_spec_from_row(row, overhead) for row in data["accelerators"]]
    return specs, overhead


def _footprint_it_load_mw(
    settings: Settings, density: dict[str, Any]
) -> tuple[float, float, float]:
    """Method-3 IT-load envelope (MW) from campus land area + assumed fractions.

    Returns (low_mw, high_mw, land_acres). All fractions are assumptions; LAND IS
    NOT FLOOR AREA. This is the loosest, physical-upper-envelope bracket.
    """
    from bosc.hydrology.stormwater import _parcels_path

    land_acres = geo.parcels_total_acres(_parcels_path(settings), settings=settings)
    fp = density["footprint"]
    cov_lo, cov_hi = (float(x) for x in fp["building_coverage_fraction"])
    ws_lo, ws_hi = (float(x) for x in fp["whitespace_fraction"])
    rack_sqft = float(fp["rack_area_sqft"])
    kw_lo, kw_hi = (float(x) for x in density["ai_rack_kw_band"])

    def _it(cov: float, ws: float, kw: float) -> float:
        bldg_sqft = land_acres * _SQFT_PER_ACRE * cov
        racks = bldg_sqft * ws / rack_sqft
        return racks * kw / 1_000.0  # MW

    lo = _it(cov_lo, ws_lo, kw_lo)
    hi = _it(cov_hi, ws_hi, kw_hi)
    return lo, hi, land_acres


def derive_compute_capacity(
    *,
    settings: Settings | None = None,
    accelerator_power_fraction: tuple[float, float] | None = None,
    mfu: float | None = None,
) -> ComputeCapacity:
    """Derive the bracketed compute / AI capacity from disclosed campus data.

    All three IT-load estimators run; the accelerator chain runs against the central
    (power-method) IT load for every candidate chip as a labeled scenario.
    """
    settings = settings or get_settings()
    specs, _overhead = _load_accelerator_specs(settings)
    density = _load_yaml(_ref_dir(settings) / "rack-density.yaml")

    power = derive_power_basis()
    cooling = derive_cooling_basis()

    # --- Method 1: power / gensets (PRIMARY) ---------------------------------
    it_power = power.it_load.value
    it_power_low = power.it_load_low.value
    it_power_high = power.it_load_high.value

    # --- Method 2: cooling-water back-solve (cross-check, shares WUE) --------
    # NB: this inversion treats the disclosed consumptive water as data-hall cooling
    # only. If primary on-site generation were combined-cycle, its steam condenser
    # would be an additional consumptive pathway (see power.py GenerationConfig /
    # issue #90), biasing this back-solve high — but that is unproven (the disclosed
    # gensets are backup), so we do not add it here.
    it_water_low = _it_load_from_consumptive_mgd(cooling.consumptive_low.value, _WUE_L_PER_KWH)
    it_water_high = _it_load_from_consumptive_mgd(cooling.consumptive_high.value, _WUE_L_PER_KWH)

    # --- Method 3: footprint (WEAKEST, physical upper envelope) --------------
    it_fp_low, it_fp_high, land_acres = _footprint_it_load_mw(settings, density)

    # --- Shared levers -------------------------------------------------------
    if accelerator_power_fraction is None:
        frac_lo, frac_hi = (float(x) for x in density["accelerator_power_fraction"])
        frac_source = "ref"
    else:
        frac_lo, frac_hi = accelerator_power_fraction
        frac_source = "override"
    frac_central = (frac_lo + frac_hi) / 2.0
    mfu_val = mfu if mfu is not None else 0.40  # 40% MFU: typical large-scale training

    frac_cite = (
        "share of IT power reaching accelerators (vs CPU host/storage/network); "
        f"{_APPENDIX_CITE}" + (" [override]" if frac_source == "override" else "")
    )

    # Accelerator power available at each IT-load / fraction corner (method 1).
    accel_power_low_mw = it_power_low * frac_lo
    accel_power_central_mw = it_power * frac_central
    accel_power_high_mw = it_power_high * frac_hi

    # --- Per-chip scenarios over the power-method IT load --------------------
    scenarios: list[AcceleratorScenario] = []
    h100 = next(s for s in specs if s.name == "H100-SXM5")
    h100_all_in_w = h100.all_in_w.value

    def _count(accel_power_mw: float, all_in_w: float) -> float:
        return accel_power_mw * 1_000_000.0 / all_in_w  # MW->W / per-chip W

    for spec in specs:
        all_in_w = spec.all_in_w.value
        c_low = _count(accel_power_low_mw, all_in_w)
        c_high = _count(accel_power_high_mw, all_in_w)
        c_central = _count(accel_power_central_mw, all_in_w)

        def _eflops(count: float, per_chip_tflops: float) -> float:
            return count * per_chip_tflops / 1_000_000.0  # TFLOP/s -> EFLOP/s

        bf16_dense = spec.bf16_dense_tflops.value
        dense_lo = _eflops(c_low, bf16_dense)
        dense_hi = _eflops(c_high, bf16_dense)
        count_cite = (
            f"{spec.label}: accelerator power (IT load x {frac_lo:g}-{frac_hi:g}) "
            f"/ {all_in_w:g} W all-in (chip TDP x host overhead)"
        )

        scenarios.append(
            AcceleratorScenario(
                spec=spec,
                count_low=ProvenancedValue.derived(
                    round(c_low), "accelerators", citation=count_cite
                ),
                count_high=ProvenancedValue.derived(
                    round(c_high), "accelerators", citation=count_cite
                ),
                count_central=ProvenancedValue.derived(
                    round(c_central), "accelerators", citation=count_cite
                ),
                bf16_dense_eflops_low=ProvenancedValue.derived(
                    round(dense_lo, 1),
                    "EFLOP/s",
                    citation=f"count x {bf16_dense:g} TFLOP/s peak dense BF16 (nameplate)",
                ),
                bf16_dense_eflops_high=ProvenancedValue.derived(
                    round(dense_hi, 1),
                    "EFLOP/s",
                    citation=f"count x {bf16_dense:g} TFLOP/s peak dense BF16 (nameplate)",
                ),
                bf16_sparse_eflops_high=(
                    ProvenancedValue.derived(
                        round(_eflops(c_high, spec.bf16_sparse_tflops.value), 1),
                        "EFLOP/s",
                        citation="count x peak sparse BF16 (2:4) (nameplate)",
                    )
                    if spec.bf16_sparse_tflops is not None
                    else None
                ),
                fp8_dense_eflops_high=(
                    ProvenancedValue.derived(
                        round(_eflops(c_high, spec.fp8_dense_tflops.value), 1),
                        "EFLOP/s",
                        citation="count x peak dense FP8 (nameplate)",
                    )
                    if spec.fp8_dense_tflops is not None
                    else None
                ),
                fp8_sparse_eflops_high=(
                    ProvenancedValue.derived(
                        round(_eflops(c_high, spec.fp8_sparse_tflops.value), 1),
                        "EFLOP/s",
                        citation="count x peak sparse FP8 (nameplate)",
                    )
                    if spec.fp8_sparse_tflops is not None
                    else None
                ),
                bf16_delivered_eflops_central=ProvenancedValue.derived(
                    round(_eflops(c_central, bf16_dense) * mfu_val, 1),
                    "EFLOP/s",
                    citation=f"central peak dense BF16 x {mfu_val:g} MFU (delivered, not nameplate)",
                ),
            )
        )

    # Equivalent H100-class GPUs at the central IT load (cross-scenario unit).
    eq_h100_low = _count(accel_power_low_mw, h100_all_in_w)
    eq_h100_high = _count(accel_power_high_mw, h100_all_in_w)

    # Cross-method IT-load bracket (the headline). The footprint high is a physical
    # envelope; we include it but flag it. The robust *operative* range is
    # method 1 (power) corroborated by the method-2 low.
    bracket_lo = min(it_power_low, it_water_low, it_fp_low)
    bracket_hi = max(it_power_high, it_water_high, it_fp_high)

    return ComputeCapacity(
        it_load_power=ProvenancedValue.from_document(
            round(it_power, 1), "MW", citation=power.it_load.citation or ""
        ),
        it_load_water_low=ProvenancedValue.derived(
            round(it_water_low, 1),
            "MW",
            citation=f"cooling consumptive {cooling.consumptive_low.value:g} MGD / "
            f"{_WUE_L_PER_KWH:g} L/kWh (recovers the power method; shares its WUE)",
        ),
        it_load_water_high=ProvenancedValue.derived(
            round(it_water_high, 1),
            "MW",
            citation=f"FM-2 {cooling.consumptive_high.value:g} MGD upper bound / "
            f"{_WUE_L_PER_KWH:g} L/kWh — UPPER BOUND only; FM-2 is not purely cooling",
            confidence="low",
        ),
        it_load_footprint_low=ProvenancedValue.assume(
            round(it_fp_low, 0),
            "MW",
            why=f"footprint envelope: {land_acres:.0f} land-acres x assumed coverage/"
            f"white-space/density (LAND != FLOOR AREA; weakest method)",
        ),
        it_load_footprint_high=ProvenancedValue.assume(
            round(it_fp_high, 0),
            "MW",
            why=f"footprint envelope (high corner) from {land_acres:.0f} land-acres "
            f"— physical UPPER ENVELOPE, not a likely load (power is the constraint)",
        ),
        it_load_bracket_low=ProvenancedValue.derived(
            round(bracket_lo, 1), "MW", citation="min IT load across the three methods"
        ),
        it_load_bracket_high=ProvenancedValue.derived(
            round(bracket_hi, 0),
            "MW",
            citation="max IT load across methods (footprint high = physical envelope, flagged)",
            confidence="low",
        ),
        accelerator_power_fraction_low=ProvenancedValue.assume(frac_lo, "fraction", why=frac_cite),
        accelerator_power_fraction_high=ProvenancedValue.assume(frac_hi, "fraction", why=frac_cite),
        mfu=ProvenancedValue.assume(
            mfu_val,
            "fraction",
            why="model-FLOPS-utilization for delivered training throughput "
            "(typical large-scale ~30-50%); applied only to the delivered figure",
        ),
        scenarios=scenarios,
        equivalent_h100_low=ProvenancedValue.derived(
            round(eq_h100_low),
            "H100-equivalents",
            citation="central IT load -> accelerator power / H100 all-in W (cross-scenario unit)",
        ),
        equivalent_h100_high=ProvenancedValue.derived(
            round(eq_h100_high),
            "H100-equivalents",
            citation="central IT load -> accelerator power / H100 all-in W (cross-scenario unit)",
        ),
    )
