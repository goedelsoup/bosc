"""Typed models for the facility compute-capacity derivation.

Like :mod:`watermark.hydrology.model`, these are computed by our own code, so they use
``extra="forbid"``. Every numeric field is a :class:`ProvenancedValue` (reused from
hydrology) so a derived capacity is self-auditing. The cornerstone is
:class:`ComputeCapacity`, mirroring :class:`watermark.hydrology.model.CoolingBasis`: it
captures the per-method IT-load estimates that bracket the answer, the modeling
levers (accelerator-power fraction, MFU), and a list of accelerator **scenarios** —
because the facility's actual accelerator type, count, and utilization are
undisclosed.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.model import ProvenancedValue


class AcceleratorSpec(BaseModel):
    """A published per-accelerator vendor spec (from data/reference/compute).

    ``reference``-tagged figures (chip TDP, peak FLOPS) with ``assumption``-tagged
    all-in power. NOT a fact about the facility — one of several candidate chips.
    """

    model_config = ConfigDict(extra="forbid")

    name: str  # "H100-SXM5"
    label: str  # "H100-class (Hopper)"
    vendor: str  # NVIDIA | Google
    generation: str  # Hopper | Blackwell | v5p | ...
    tdp_w: ProvenancedValue  # chip thermal design power (reference)
    all_in_w: ProvenancedValue  # per-accelerator rack power incl. host share (derived)
    bf16_dense_tflops: ProvenancedValue  # peak dense BF16/FP16 (the training rate)
    bf16_sparse_tflops: ProvenancedValue | None = None  # 2:4 structured sparsity
    fp8_dense_tflops: ProvenancedValue | None = None
    fp8_sparse_tflops: ProvenancedValue | None = None
    fp4_dense_tflops: ProvenancedValue | None = None
    fp4_sparse_tflops: ProvenancedValue | None = None
    int8_tops: ProvenancedValue | None = None
    gpus_per_server: int = 8
    cooling: str = ""


class AcceleratorScenario(BaseModel):
    """One labeled "if the chip is X" scenario over the bracketed IT load.

    The count and aggregate FLOPS are ``derived`` ranges (low/high) from the IT-load
    bracket and the accelerator-power fraction — *conditional* on this chip. Never
    "the facility has N of these"; always "if X-class, then ~N1-N2".
    """

    model_config = ConfigDict(extra="forbid")

    spec: AcceleratorSpec
    count_low: ProvenancedValue  # accelerators if IT-load low / fraction low
    count_high: ProvenancedValue  # accelerators if IT-load high / fraction high
    count_central: ProvenancedValue  # central estimate
    # Aggregate PEAK throughput (nameplate, not delivered) across the count range.
    bf16_dense_eflops_low: ProvenancedValue  # EFLOP/s = count x per-chip / 1e6
    bf16_dense_eflops_high: ProvenancedValue
    bf16_sparse_eflops_high: ProvenancedValue | None = None
    fp8_dense_eflops_high: ProvenancedValue | None = None
    fp8_sparse_eflops_high: ProvenancedValue | None = None
    # Delivered training throughput at the labeled MFU (derated; clearly separate).
    bf16_delivered_eflops_central: ProvenancedValue | None = None


class ProfileScenario(BaseModel):
    """One data-center profile's chip-level overhead and its effect on the count.

    Issue #89: the host CPU / NIC / PSU / in-rack-conversion overhead between chip TDP
    and all-in per-accelerator power differs by deployment (air-cooled HGX vs liquid
    GB200 NVL72), so collapsing it to one global ``host_overhead_factor`` hides a real
    lever. Each profile is a labeled SCENARIO with the overhead split into a ``host``
    and a ``network`` share — the network share reflecting the 1 InfiniBand + 1 Ethernet
    NIC complement (issue #88) — and the cooling / PUE it pairs with (issue #87). The
    count is expressed in equivalent-H100 units at the central power-method IT load, so
    profiles are directly comparable. Nothing here is a disclosed deployment.
    """

    model_config = ConfigDict(extra="forbid")

    name: str  # "air-hgx" | "liquid-gb200-nvl72" | ...
    label: str
    cooling: str
    host_overhead: ProvenancedValue  # assumption, multiplier on chip TDP (host share)
    network_overhead: ProvenancedValue  # assumption, multiplier (1 IB + 1 NIC fabric share)
    total_overhead: ProvenancedValue  # derived, host x network (chip TDP -> all-in)
    pue: ProvenancedValue | None = None  # assumption, the PUE this profile pairs with (#87)
    reference_all_in_w: ProvenancedValue  # derived, H100 TDP x total_overhead (per-accelerator)
    equivalent_h100_central: ProvenancedValue  # derived, H100-equiv accelerators at central IT load


class ComputeCapacity(BaseModel):
    """The bracketed facility compute / AI capacity, derived by three methods.

    Mirrors :class:`watermark.hydrology.model.CoolingBasis`: a self-auditing bundle of
    provenance-tagged inputs and derived ranges. The three IT-load estimates
    (``it_load_power`` / ``it_load_water`` / ``it_load_footprint``) should bracket a
    similar value; the accelerator scenarios then turn the central IT load into
    per-chip count and FLOPS ranges. Nothing here is a measured fact about the
    facility — accelerator type/count/utilization are undisclosed.
    """

    model_config = ConfigDict(extra="forbid")

    # --- The three independent IT-load estimates (MW) ------------------------
    it_load_power: ProvenancedValue  # method 1: air-permit gensets (PRIMARY)
    # Method 2 (cooling-water back-solve) is ``None`` when the archetype consumes ~0 water
    # (closed_loop_dry / off, or the dry lower bound of unknown): dividing a 0 MGD consumptive
    # by the WUE recovers a meaningless 0 MW, which then collapsed the whole bracket floor to
    # 0 (#1641 D4). A None here means "the water method does not constrain this bound", and it
    # is excluded from the cross-method bracket rather than dragging it to 0.
    it_load_water_low: ProvenancedValue | None = None  # method 2: cooling-water back-solve (low)
    it_load_water_high: ProvenancedValue | None = None  # method 2: cooling-water back-solve (high)
    it_load_footprint_low: ProvenancedValue  # method 3: footprint (WEAKEST)
    it_load_footprint_high: ProvenancedValue  # method 3 (high)

    # The cross-method bracket on IT load (the headline robustness statement).
    it_load_bracket_low: ProvenancedValue  # min across methods (derived)
    it_load_bracket_high: ProvenancedValue  # max across methods (derived)

    # --- The shared modeling levers ------------------------------------------
    accelerator_power_fraction_low: ProvenancedValue  # share of IT power to accelerators
    accelerator_power_fraction_high: ProvenancedValue
    mfu: ProvenancedValue  # model-FLOPS-utilization for delivered throughput

    # --- The conditional accelerator scenarios -------------------------------
    scenarios: list[AcceleratorScenario]

    # Per-data-center-profile chip-level overhead scenarios (issue #89). The per-chip
    # `scenarios` above use the default global host_overhead_factor; these vary the
    # host/network overhead by deployment profile, in equivalent-H100 units.
    profiles: list[ProfileScenario] = []

    # Derived per-rack floor area used by the footprint method (issue #88), from the
    # rack_profile geometry (depth x width x aisle factor). None if no rack_profile.
    rack_floor_area_sqft: ProvenancedValue | None = None

    # An apples-to-apples cross-scenario figure: equivalent H100-class GPUs at the
    # central IT load (so a TPU/B200 deployment is comparable to a familiar unit).
    equivalent_h100_low: ProvenancedValue
    equivalent_h100_high: ProvenancedValue

    method: str = (
        "power (air-permit gensets, primary); cooling-water back-solve (cross-check); "
        "footprint (weakest) -> accelerator count -> aggregate peak FLOPS by scenario"
    )

    def scenario(self, name: str) -> AcceleratorScenario | None:
        return next((s for s in self.scenarios if s.spec.name == name), None)

    def profile(self, name: str) -> ProfileScenario | None:
        return next((p for p in self.profiles if p.name == name), None)
