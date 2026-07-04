"""Derive the facility's compute / AI capacity by three independent methods.

In the :mod:`watermark.hydrology.cooling` idiom: bracket the answer from several
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

from watermark.config import Settings, get_settings
from watermark.facility.model import (
    AcceleratorScenario,
    AcceleratorSpec,
    ComputeCapacity,
    ProfileScenario,
)
from watermark.facility.power import derive_power_basis
from watermark.hydrology import geo
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.cooling_models import (
    _WUE_L_PER_KWH,
    CoolingParams,
    _resolve_heat_reject_mult,
    it_load_mw_from_once_through_withdrawal,
)
from watermark.hydrology.model import ProvenancedValue
from watermark.sites import CoolingModelType, active_profile

_L_PER_GAL = 3.785411784
_SQFT_PER_ACRE = 43560.0
_SQFT_PER_SQM = 10.763910416709722  # 1 m^2 in sqft (for the rack-profile floor area)

# In-corpus provenance for the rack-density / power-fraction figures.
_APPENDIX_CITE = (
    "in-corpus relator data appendix "
    "(data/extracted/legal/select-committee-2026/relator-testimony/"
    "bosc-data-appendix-2026-06-01.md), citing NVIDIA HGX guidance via IntuitionLabs"
)
_REF_CITE = "data/reference/compute/accelerators.yaml (vendor specs, as of 2026-06)"
_RACK_CITE = (
    "data/reference/compute/rack-density.yaml rack_profile / datacenter_profiles "
    "(assumptions from the 2026-06-10 facility-design call: 32U+ racks, 1 InfiniBand "
    "+ 1 NIC, non-standard depth for GPU/cooling layouts)"
)

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


def _rack_floor_area_sqft(density: dict[str, Any]) -> tuple[float, bool, str]:
    """Per-rack floor area (sqft) from the rack_profile geometry, with a fallback.

    Issue #88: derive floor area = depth x width x aisle_factor from the documented
    ``rack_profile`` (non-standard/extended depth raises it); fall back to the bare
    ``footprint.rack_area_sqft`` scalar if no profile is present. Returns
    (sqft, non_standard_depth, citation).
    """
    rp = density.get("rack_profile")
    if not rp:
        scalar = float(density["footprint"]["rack_area_sqft"])
        return scalar, False, f"{scalar:g} sqft/rack (fallback scalar); {_RACK_CITE}"
    depth_mm = float(rp["depth_mm"])
    width_mm = float(rp["width_mm"])
    aisle = float(rp["aisle_factor"])
    non_standard = bool(rp.get("non_standard_depth", False))
    footprint_sqm = (depth_mm / 1000.0) * (width_mm / 1000.0)
    sqft = footprint_sqm * _SQFT_PER_SQM * aisle
    std_mm = float(rp.get("standard_depth_mm", depth_mm))
    depth_note = (
        f"non-standard {depth_mm:g}mm depth vs standard {std_mm:g}mm"
        if non_standard
        else f"{depth_mm:g}mm depth"
    )
    cite = (
        f"{depth_mm:g}x{width_mm:g}mm x {aisle:g} aisle factor = {sqft:.1f} sqft/rack "
        f"({depth_note}); {_RACK_CITE}"
    )
    return round(sqft, 1), non_standard, cite


def _footprint_it_load_mw(
    settings: Settings, density: dict[str, Any]
) -> tuple[float, float, float]:
    """Method-3 IT-load envelope (MW) from campus land area + assumed fractions.

    Returns (low_mw, high_mw, land_acres). All fractions are assumptions; LAND IS
    NOT FLOOR AREA. This is the loosest, physical-upper-envelope bracket. Per-rack
    floor area comes from the rack_profile geometry (issue #88).
    """
    from watermark.hydrology.stormwater import _parcels_path

    land_acres = geo.parcels_total_acres(_parcels_path(settings), settings=settings)
    fp = density["footprint"]
    cov_lo, cov_hi = (float(x) for x in fp["building_coverage_fraction"])
    ws_lo, ws_hi = (float(x) for x in fp["whitespace_fraction"])
    rack_sqft, _non_standard, _cite = _rack_floor_area_sqft(density)
    kw_lo, kw_hi = (float(x) for x in density["ai_rack_kw_band"])

    def _it(cov: float, ws: float, kw: float) -> float:
        bldg_sqft = land_acres * _SQFT_PER_ACRE * cov
        racks = bldg_sqft * ws / rack_sqft
        return racks * kw / 1_000.0  # MW

    lo = _it(cov_lo, ws_lo, kw_lo)
    hi = _it(cov_hi, ws_hi, kw_hi)
    return lo, hi, land_acres


def _profile_scenarios(
    density: dict[str, Any], h100_tdp_w: float, accel_power_central_mw: float
) -> list[ProfileScenario]:
    """Per-data-center-profile chip-level overhead scenarios (issue #89).

    Each profile's ``host x network`` overhead sets the all-in per-accelerator power
    (vs the default global ``host_overhead_factor``); the resulting equivalent-H100
    count at the central IT load makes profiles directly comparable. Every figure is
    an assumption — no deployment is disclosed.
    """
    out: list[ProfileScenario] = []
    for p in density.get("datacenter_profiles", []):
        host = float(p["host_overhead"])
        network = float(p["network_overhead"])
        total = round(host * network, 4)
        ref_all_in = h100_tdp_w * total
        eq_h100 = accel_power_central_mw * 1_000_000.0 / ref_all_in
        pue_val = p.get("pue")
        label = str(p["label"])
        out.append(
            ProfileScenario(
                name=str(p["name"]),
                label=label,
                cooling=str(p.get("cooling", "")),
                host_overhead=ProvenancedValue.assume(
                    host, "ratio", why=f"{label} host overhead (CPU/PSU/storage); {_RACK_CITE}"
                ),
                network_overhead=ProvenancedValue.assume(
                    network,
                    "ratio",
                    why=f"{label} network overhead (1 IB + 1 Ethernet NIC + switch); {_RACK_CITE}",
                ),
                total_overhead=ProvenancedValue.derived(
                    total, "ratio", citation=f"host {host:g} x network {network:g} (TDP -> all-in)"
                ),
                pue=(
                    ProvenancedValue.assume(
                        float(pue_val), "ratio", why=f"{label} PUE (pairs cooling with #87)"
                    )
                    if pue_val is not None
                    else None
                ),
                reference_all_in_w=ProvenancedValue.derived(
                    float(round(ref_all_in)),
                    "W",
                    citation=f"H100 {h100_tdp_w:g} W TDP x {total:g} profile overhead",
                ),
                equivalent_h100_central=ProvenancedValue.derived(
                    float(round(eq_h100)),
                    "H100-equivalents",
                    citation=(
                        f"central accelerator power {accel_power_central_mw:g} MW / "
                        f"{round(ref_all_in):g} W all-in ({label} overhead)"
                    ),
                ),
            )
        )
    return out


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

    power = derive_power_basis(settings=settings)
    if power is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility (SiteProfile.facility is None) — "
            "the compute-capacity estimate needs a facility power basis"
        )
    cooling = derive_cooling_basis(settings=settings)

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
    if cooling.cooling_model is CoolingModelType.ONCE_THROUGH:
        # Once-through consumptive is only ~1-2% forced evaporation of the withdrawal, not
        # it_load x WUE — inverting it with a tower WUE badly understates the load. The
        # withdrawal is the heat-rejection basis, so recover the IT load from it instead.
        # Both consumptive bounds share one withdrawal, so the cross-check is a point. Resolve
        # the cooling-overhead multiplier with the same precedence as _derive_once_through and
        # divide it back out (#1153), so this recovers the *IT* load, not the inflated
        # rejected-heat load.
        facility = active_profile(settings).facility
        heat_reject_mult, mult_cite = _resolve_heat_reject_mult(facility, CoolingParams())
        it_water_low = it_water_high = it_load_mw_from_once_through_withdrawal(
            cooling.makeup_demand.value, heat_reject_multiplier=heat_reject_mult
        )
        water_low_cite = (
            f"once-through withdrawal {cooling.makeup_demand.value:g} MGD / heat-rejection "
            f"basis / {heat_reject_mult:g} cooling overhead ({mult_cite}) — recovers the power "
            "method; shares its dT"
        )
        water_high_cite = water_low_cite
    else:
        # Invert with the exact WUE the consumptive basis was built from (which honours a
        # per-facility SiteFacility.wue_l_per_kwh override), falling back to the archetype
        # default only when the basis carries no WUE (e.g. dry modes with ~0 consumptive).
        wue_basis = cooling.wue.value if cooling.wue is not None else _WUE_L_PER_KWH
        it_water_low = _it_load_from_consumptive_mgd(cooling.consumptive_low.value, wue_basis)
        it_water_high = _it_load_from_consumptive_mgd(cooling.consumptive_high.value, wue_basis)
        water_low_cite = (
            f"cooling consumptive {cooling.consumptive_low.value:g} MGD / "
            f"{wue_basis:g} L/kWh (recovers the power method; shares its WUE)"
        )
        water_high_cite = (
            f"FM-2 {cooling.consumptive_high.value:g} MGD upper bound / "
            f"{wue_basis:g} L/kWh — UPPER BOUND only; FM-2 is not purely cooling"
        )

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

    # Per-data-center-profile chip-level overhead scenarios (issue #89) and the
    # rack-profile-derived per-rack floor area (issue #88).
    profile_scenarios = _profile_scenarios(density, h100.tdp_w.value, accel_power_central_mw)
    rack_sqft, _rack_non_standard, rack_cite = _rack_floor_area_sqft(density)

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
            round(it_water_low, 1), "MW", citation=water_low_cite
        ),
        it_load_water_high=ProvenancedValue.derived(
            round(it_water_high, 1), "MW", citation=water_high_cite, confidence="low"
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
        profiles=profile_scenarios,
        rack_floor_area_sqft=ProvenancedValue.derived(rack_sqft, "sqft", citation=rack_cite),
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
