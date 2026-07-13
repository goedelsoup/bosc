"""Models for reading a continuous water-quality monitor against an event timeline.

Built for #1498: the Maumee-at-Waterville gage (USGS 04193500) read against the
Napoleon / Huston Creek fertilizer-spill timeline. The gage carries no ammonia or
nitrate probe, so its water-quality channels (turbidity, phycocyanin, specific
conductance, DO) are **optical/ionic surrogates** — never a nitrogen measurement.
The whole point of the read is to separate what the storm did from what the release
did, so every attributed number stays ``[inference]`` until the travel time lines up.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from watermark.hydrology.models._core import ProvenancedValue

# Field-level provenance contract: the observational fields are gauge readings
# ([verified] connector), the interpretive fields are computed ([inference] derived).
_OBSERVED_FIELDS = (
    "discharge_min",
    "discharge_storm_peak",
    "turbidity_baseline",
    "do_min",
    "water_temp_max",
    "conductance_storm_min",
    "conductance_low_flow_max",
    "phycocyanin_month_max",
    "phycocyanin_at_turbidity_spike",
)
_DERIVED_FIELDS = ("reach_river_km", "plume_travel")


class MonitorSpike(BaseModel):
    """One isolated transient in a continuous channel (a turbidity/optical spike)."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str  # ISO datetime with the gage's UTC offset, verbatim from NWIS
    value: float
    unit: str


class ContinuousMonitorRead(BaseModel):
    """A structured read of one gage's continuous record across an event window.

    The observational fields (spikes, trough, sag, surrogate extrema) are computed
    directly from the instantaneous-value record and are ``connector``-sourced
    ``[verified]`` observations. The interpretive fields (``reach_river_km``,
    ``plume_travel``, ``attribution``) are ``derived`` ``[inference]`` — a
    travel-time argument laid over the observations, not a measurement.
    """

    model_config = ConfigDict(extra="forbid")

    site_no: str
    site_name: str
    window_start: str
    window_end: str

    # --- discharge & the assimilative denominator ---
    discharge_min: ProvenancedValue  # cfs, the low-flow trough (asof = its timestamp)
    discharge_storm_peak: ProvenancedValue  # cfs, the rain-driven rise
    seven_q10_cfs: ProvenancedValue  # derived Maumee 7Q10 at this gage (screening denom)
    low_flow_dilution_ratio: float  # trough / 7Q10 — how tight the initial-week denominator was

    # --- turbidity: the loud, storm-timed signal ---
    turbidity_baseline: ProvenancedValue  # FNU, median of the record
    turbidity_spikes: list[MonitorSpike]

    # --- dissolved oxygen + its thermal driver (context, NOT attributed to the spill) ---
    do_min: ProvenancedValue  # mg/L, the sag
    water_temp_max: ProvenancedValue  # deg C, the heat that drove the sag

    # --- ionic surrogate: specific conductance (the closest thing to a dissolved-plume trace) ---
    conductance_storm_min: ProvenancedValue  # uS/cm — storm dilution, NOT an ionic plume bump
    conductance_low_flow_max: ProvenancedValue  # uS/cm — low-flow ion concentration

    # --- cyanobacteria surrogate: phycocyanin (fPC) — sub-bloom all month ---
    phycocyanin_month_max: ProvenancedValue  # ug/L, the true monthly high (a diel peak)
    phycocyanin_at_turbidity_spike: ProvenancedValue  # ug/L, co-timed w/ the turbidity spike

    # --- travel-time argument & attribution ---
    reach_river_km: ProvenancedValue  # Huston Creek mouth -> Waterville, along the mainstem
    plume_travel: ProvenancedValue  # hours (low/high band from the velocity bracket)
    release_start: str  # the dam-failure hour the plume clock starts from ([verified], #1497)
    spikes_precede_release: bool  # do the observed spikes pre-date the release?
    attribution: str  # the one-line [inference] verdict
    caveats: list[str]

    @model_validator(mode="after")
    def _check_field_provenance(self) -> ContinuousMonitorRead:
        """A gauge reading may not masquerade as an inference, nor an inference as a reading.

        Rejects a mislabeled build/round-trip: observational fields must be ``connector``
        ([verified]) and the travel-time argument must be ``derived`` ([inference]).
        """
        for name in _OBSERVED_FIELDS:
            source = getattr(self, name).source
            if source != "connector":
                raise ValueError(
                    f"{name} is an observed gauge reading; expected source 'connector', got {source!r}"
                )
        for name in _DERIVED_FIELDS:
            source = getattr(self, name).source
            if source != "derived":
                raise ValueError(
                    f"{name} is an interpretive value; expected source 'derived', got {source!r}"
                )
        return self
