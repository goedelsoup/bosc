"""Sanitary / TMDL / SWMM (Tier-1) models for the Tier-0 hydrology subsystem."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from watermark.hydrology.models._core import ProvenancedValue


class StormPlanInventory(BaseModel):
    """Document-grounded drainage facts read off the campus grading & storm plan.

    Transcribed from the civil sheet (not computed hydrology), so it belongs in
    ``data/extracted/``. It captures what the drawing *states* — the storm-structure
    rim-elevation population, the conveyance inventory, and crucially whether any
    on-site **detention/retention storage** is shown. The connectivity and inverts
    that a routable SWMM network needs are drawn as vector geometry with no schedule
    table, so we deliberately do **not** fabricate a pipe network here; we ground the
    facts the sheet actually carries and flag the absence of storage.
    """

    model_config = ConfigDict(extra="forbid")

    sheet_id: str  # e.g. "1A-C-3104"
    discipline: str  # "Grading & Storm Plan"
    phase: str  # "95% SPS Design"
    status: str  # "Not For Construction"
    source_path: str  # rel path to the source drawing
    engineer: str | None = None

    # Graded surface, from the storm-structure rim labels.
    rim_labels: int  # count of RIM=… labels read
    rim_distinct: int
    rim_min: ProvenancedValue  # ft (document)
    rim_max: ProvenancedValue  # ft (document)
    relief: ProvenancedValue  # ft (derived: max - min)

    # Conveyance inventory (what the legend/labels name).
    structure_types: list[str] = []
    pipe_sizes_in: list[float] = []  # nominal callout sizes
    conveyance_features: list[str] = []  # swale, headwall, check dam, flood routing, …

    # The determination that reframes the Tier-1 detention result.
    detention_shown: bool  # any on-site storage labeled?
    storage_terms_searched: list[str] = []  # the negative is auditable
    note: str = ""


class DetentionDesign(BaseModel):
    """Tier-1 (SWMM) detention sizing: the basin that holds post-dev peak to pre-dev.

    The **as-permitted** case is the primary one — its imperviousness is driven by the
    committed :class:`SiteFootprint`'s declared permanently-impervious acreage, so the basin
    reported here is the one the permitted footprint needs (WS-14 / #1614). The blanket
    near-impervious deck survives alongside it as the explicitly-labeled **full-buildout
    bound** — the peer of the Tier-0 screen's ``full_buildout_peak_cfs``, not a second reading
    of the same project. The bound fields are optional so pre-#1614 committed artifacts load.
    """

    model_config = ConfigDict(extra="forbid")

    pre_peak_cfs: float
    post_peak_cfs: float  # undetained post-development, as-permitted footprint
    controlled_peak_cfs: float  # released through the sized orifice
    orifice_diam_ft: float
    required_storage_acft: float
    basin_area_acres: float
    # The as-permitted subcatchment imperviousness actually modeled, and where it came from.
    post_imperv_pct: float | None = None
    post_imperv_basis: str = ""
    # The blanket near-impervious upper bound (whole parcel paved), sized against the same
    # pre-development peak — what the corridor would need if the parcel were built out.
    full_buildout_imperv_pct: float | None = None
    full_buildout_peak_cfs: float | None = None
    full_buildout_controlled_peak_cfs: float | None = None
    full_buildout_orifice_diam_ft: float | None = None
    full_buildout_storage_acft: float | None = None
    tier: Literal["tier1-swmm"] = "tier1-swmm"

    @property
    def has_full_buildout(self) -> bool:
        """Whether the full-buildout bound is reportable — *every* field of it, or none.

        ``run_tier1`` writes the block atomically, but a pre-#1614 artifact carries none of
        it and a hand-edited one could carry part. Renderers gate on this rather than on the
        two headline fields, so a half-populated block can't reach a format string.
        """
        return all(
            v is not None
            for v in (
                self.full_buildout_imperv_pct,
                self.full_buildout_peak_cfs,
                self.full_buildout_controlled_peak_cfs,
                self.full_buildout_orifice_diam_ft,
                self.full_buildout_storage_acft,
            )
        )


class SanitaryPlant(BaseModel):
    """A WWTP's document-cited sanitary design flows (the grounded sanitary basis)."""

    model_config = ConfigDict(extra="forbid")

    plant: str
    npdes: str | None = None
    routing_id: str | None = None  # the watch-items node id used by the routing table
    receiving_water: str | None = None
    avg_design_flow: ProvenancedValue  # MGD, document-cited permitted average
    peak_capacity: ProvenancedValue | None = None  # MGD, document-cited peak hydraulic
    peaking_factor: ProvenancedValue | None = None  # derived: peak / avg
    pretreatment: bool = False
    note: str | None = None

    @property
    def headroom_mgd(self) -> float | None:
        """Wet-weather headroom above the permitted average (peak - avg), if both cited."""
        if self.peak_capacity is None:
            return None
        return round(self.peak_capacity.value - self.avg_design_flow.value, 2)


class TmdlWla(BaseModel):
    """One facility's total-phosphorus wasteload allocation under the Maumee TMDL."""

    model_config = ConfigDict(extra="forbid")

    facility: str
    npdes: str | None = None
    spring_tp: ProvenancedValue  # metric tons TP, spring season (Mar-Jul)
    daily_tp: ProvenancedValue  # kg TP/day (spring load / 153 days)
    note: str | None = None


class MaumeeTmdl(BaseModel):
    """The Maumee Watershed Nutrient TMDL phosphorus WLAs for the Lima loop.

    A vendored, document-cited reference (transcribed verbatim from Appendix 4 of
    the final TMDL), like the 7Q10 and sanitary tables — not computed hydrology — so
    it lives under ``data/reference/hydrology``. Ties the local low-flow assimilative
    failure to the basin-scale, Lake-Erie-driven nutrient cap on the same permits.
    """

    model_config = ConfigDict(extra="forbid")

    facilities: list[TmdlWla]
    grouped_spring_tp: ProvenancedValue | None = None  # category total, metric tons
    grouped_daily_tp: ProvenancedValue | None = None  # category total, kg/day

    def facility(self, name: str) -> TmdlWla | None:
        return next((f for f in self.facilities if f.facility == name), None)


class SanitaryBasis(BaseModel):
    """Document-grounded sanitary design basis for the municipal loop's WWTPs.

    Aggregates cited per-plant design flows (OEPA NPDES permits / watch-items) with the
    system's I/I + SSO regulatory context (the 1996 federal consent decree and the 2005
    OEPA agreement to eliminate bypassing by 2015). Like the 7Q10 table, it is a vendored,
    cited reference — not computed hydrology — so it lives under ``data/reference``.
    """

    model_config = ConfigDict(extra="forbid")

    plants: list[SanitaryPlant]
    campus_industrial: ProvenancedValue  # MGD, the BOSC FM-2 industrial discharge
    ii_remediation_musd: ProvenancedValue  # $M of documented I/I remediation
    decree_note: str = ""
    source_note: str = ""

    def plant(self, name: str) -> SanitaryPlant | None:
        return next((p for p in self.plants if p.plant == name), None)


class SanitarySurcharge(BaseModel):
    """Campus wet-weather sanitary contribution vs a plant's documented headroom.

    ``wet_weather_peak`` is the campus's SWMM-derived storm contribution (dry-weather
    base + RDII). ``headroom_mgd`` is the receiving plant's documented wet-weather
    headroom (peak hydraulic capacity - permitted average). ``exceeds`` compares the two:
    a campus contribution larger than the headroom is screening-grade SSO risk.
    """

    model_config = ConfigDict(extra="forbid")

    plant: str
    forcemain: str | None = None  # the campus forcemain that reaches this plant (FM-1 / FM-2)
    capacity: ProvenancedValue  # MGD, document-cited peak hydraulic capacity
    avg_design_flow: ProvenancedValue | None = None  # MGD, document-cited permitted average
    peaking_factor: ProvenancedValue | None = None  # derived, peak / avg (context)
    headroom_mgd: float | None = None  # peak - avg, the wet-weather margin
    wet_weather_peak: ProvenancedValue  # MGD, SWMM-derived campus contribution (base + RDII)
    exceeds: bool
    margin_mgd: float


class SwmmDeck(BaseModel):
    """A committed EPA-SWMM input deck — the model itself, kept for chain-of-custody.

    The ``.inp`` text is written to ``filename`` (under ``data/reference/hydrology/swmm/``)
    and its ``sha256`` recorded here, so the committed result is reproducible: anyone
    can re-run the exact deck in EPA SWMM. ``inp_text`` is the runtime-only carrier
    (``Field(exclude=True)``) — it never lands in the committed YAML, only in the file.
    """

    model_config = ConfigDict(extra="forbid")

    name: str  # "pre" | "post" | "detention" | "sanitary"
    filename: str  # relative path under data/reference/hydrology/swmm/
    reports_node: str  # the element whose peak the result reads
    sha256: str = ""
    peak_cfs: float | None = None
    continuity_error_pct: float = 0.0  # SWMM flow-routing mass-balance error (quality signal)
    note: str = ""
    inp_text: str = Field(default="", exclude=True)  # runtime only; lives in the .inp file


class Tier1Result(BaseModel):
    """The Tier-1 SWMM escalation: detention sizing + sanitary surcharge."""

    model_config = ConfigDict(extra="forbid")

    available: bool
    detention: DetentionDesign | None = None
    surcharge: list[SanitarySurcharge] = []
    surcharge_note: str = ""  # auditable routing of the campus flow + who is/isn't judged
    decks: list[SwmmDeck] = []  # the committed model inputs behind the numbers
    engine: str = ""  # the SWMM/pyswmm version that produced the result
    storm_return_period_yr: int | None = None
    design_depth_in: float | None = None  # the design-storm depth driving the decks
    inventory: StormPlanInventory | None = None  # grounds the detention finding in the real sheet
    sanitary_basis: SanitaryBasis | None = None  # grounds the surcharge in cited design flows
    note: str = ""

    def deck(self, name: str) -> SwmmDeck | None:
        return next((d for d in self.decks if d.name == name), None)
