"""Site-profile data models for the BOSC network registry.

Split out of the former monolithic ``sites.py`` (#597). Re-exported by the package
:mod:`watermark.sites` ``__init__`` so ``watermark.sites.SiteProfile`` / ``SiteFacility`` /
``PROFILE_SETTINGS_FIELDS`` are unchanged for callers.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from watermark.connectors.gis_schema import GisFloodSchema, GisParcelSchema, GisZoningSchema

_YAML_PATH = Path(__file__).parents[3] / "data" / "sites.yaml"


class SiteEntry(BaseModel):
    """One entry in ``data/sites.yaml`` — the canonical identity for a watershed-point site."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    place: str
    basin_label: str
    receiving_water: str | None = None
    state: str
    codename: str | None = None
    mono: str
    status: str
    selectable: bool
    issue: str | None = None
    map_lat: float | None = None
    map_lon: float | None = None
    map_zoom: int | None = None


_IDENTITY: dict[str, SiteEntry] | None = None


def _get_identity() -> dict[str, SiteEntry]:
    global _IDENTITY
    if _IDENTITY is None:
        raw = yaml.safe_load(_YAML_PATH.read_text(encoding="utf-8"))
        _IDENTITY = {e["slug"]: SiteEntry(**e) for e in raw.get("sites", [])}
    return _IDENTITY


class CoolingModelType(StrEnum):
    """The cooling-water archetype of a data-center facility, keyed on physical mechanism.

    Each member selects one spec in :data:`watermark.hydrology.cooling_models.COOLING_MODELS` —
    its own consumptive/withdrawal math and parameter set. The enum lives here (not in
    ``watermark.hydrology``) because the archetype is a **per-site facility attribute**
    (:class:`SiteFacility.cooling_model`) and ``watermark.config`` imports this package,
    so hydrology modules cannot be imported from here.

    Naming ([reference]): the enum is keyed on mechanism because the data-center industry's
    "open loop / closed loop" labels are ambiguous — EPA WaterSense at Work (§6, Cooling
    Towers) calls a recirculating wet tower an *open recirculating* system, which trade
    usage shortens to "open loop", while "closed loop" is used both for sealed dry/air-
    cooled circuits and (confusingly) for tower condenser-water loops. The open/closed
    labels are display-only **aliases**, documented per spec in
    :mod:`watermark.hydrology.cooling_models`; the engine never dispatches on them.

    ``unknown`` means "facility disclosed, cooling method not on record" — never "no
    cooling". It yields a bracketed range, not a single figure. ``off`` is the explicit
    no-cooling-water-load case; ``SiteProfile.facility is None`` also resolves to it.
    """

    OFF = "off"  # no cooling-water load
    EVAPORATIVE_TOWER = "evaporative_tower"  # recirculating wet tower (alias: "open loop")
    ONCE_THROUGH = "once_through"  # surface-water pass-through (alias: "open once-through")
    CLOSED_LOOP_DRY = "closed_loop_dry"  # sealed fluid + dry/air rejection (alias: "closed loop")
    HYBRID_ADIABATIC = "hybrid_adiabatic"  # dry with seasonal evaporative assist
    UNKNOWN = "unknown"  # disclosed facility, undisclosed method -> bracketed range


class FacilityLifecycle(StrEnum):
    """A disclosed facility's real-world lifecycle stage (#1628) — the four-stage clock the
    frontend's facility-status rail walks (``investigation → confirmed → construction → live``).

    The 1:1 Python peer of the TS ``FacilityStatus`` in ``web/packages/core/src/sites.ts``; the
    frontend now reads this off the bundle instead of a hand-maintained per-slug dict. Distinct
    from the SITE-BUILD status (how far along OUR website is) and from
    :class:`watermark.facility.candidate.CandidateStatus` (the richer discovery-stage vocabulary a
    swept candidate carries — mapped to this at promotion). ``investigation`` is the honest floor
    for a site with **no** disclosed facility; a site that *has* a :class:`SiteFacility` is at least
    ``confirmed`` (a project is on the record).
    """

    INVESTIGATION = "investigation"  # no disclosed project yet — the inferential floor
    CONFIRMED = "confirmed"  # a project is on the record (announced / approved / disclosed)
    CONSTRUCTION = "construction"  # under construction (grading/build permit, groundbreaking)
    LIVE = "live"  # operational / energized


class DcEndUse(StrEnum):
    """The disclosed data-center **end-use** archetype (#1628) — the controlled vocabulary shared
    with the frontend's end-use explorer (``DcKey`` in ``web/packages/core/src/endUse.ts``).

    Set only where the record discloses the type (with ``end_use_citation``); left ``None`` = the
    end use is ``[open]`` — the sharp unanswered question for Lima itself, which must NOT be
    asserted (``endUse.ts`` exists precisely because Lima's type is open). ``bitcoin`` is its own
    customer (behind-the-meter mining); ``hyperscale`` = the operator runs its own workloads;
    ``colocation`` = a landlord with unnamed tenants; ``enclave`` = an authorized-only federal
    environment.
    """

    BITCOIN = "bitcoin"
    HYPERSCALE = "hyperscale"
    COLOCATION = "colocation"
    ENCLAVE = "enclave"


def _facility_slug(text: str, *, max_len: int = 64) -> str:
    """A stable dedupe slug for a facility ``key`` (local peer of ``facility.candidate._slug`` —
    kept here so ``watermark.sites`` doesn't depend on ``watermark.facility``)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "facility"


class SiteFacility(BaseModel):
    """A site's disclosed data-center facility power basis.

    Present only for a site with an identified, documented facility. Two grounding modes:

    * **Air-permit-grounded** (Lima, from Ohio EPA Air PTI P0138965; Fort Wayne, IDEM Title V):
      the permit discloses the **backup** capacity (gensets x rating) — that is the ``[verified]``
      figure. The **IT load is an ``[inference]``**, derived from the backup by the N+1 relation
      (IT ~= backup net of mechanical overhead), never a permit disclosure (#1697). Full power +
      air-dispatch basis.
    * **Site-plan-grounded** (Urbana Technology Hub, from the disclosed data-center site plan):
      the facility is on the public record (type / floor area / investment / cooling) but the
      MW load is **not** disclosed. Gensets and the air permit are ``None``; the IT load is a
      floor-area SCREENING bracket carried as ``[inference]`` (``it_load_citation``), never a
      disclosure — the interconnection/air-permit MW stays ``[open]``.

    A site with no identified facility leaves ``SiteProfile.facility = None`` — the grid stack
    then emits the per-site grid backdrop (utility / BA / state denominators) **without**
    fabricating a campus load share. Drives :func:`watermark.facility.power.derive_power_basis`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- Identity / structured facts (#1628) ----------------------------------
    # A site now holds N facilities (``SiteProfile.facilities``); ``name`` is the display
    # identity (e.g. "Shawnee Energy Campus") and ``key`` its stable dedupe slug (filled from
    # ``name`` when left blank — unique within a site). ``status`` is the real-world lifecycle
    # stage the frontend rail reads off the bundle (retiring the hand-maintained TS
    # ``FACILITY_STATUS`` dict): a disclosed facility is at least ``confirmed``. ``operator`` and
    # ``end_use`` are the structured peers of the old freetext ``facility_type`` — each paired
    # with its own citation (enforced below) so a disclosed value never passes uncited; ``end_use``
    # left ``None`` = the end use is ``[open]`` (Lima's unanswered question — never asserted).
    name: str
    key: str = ""
    status: FacilityLifecycle
    operator: str | None = None
    operator_citation: str | None = None
    end_use: DcEndUse | None = None
    end_use_citation: str | None = None
    # Facility-level geometry link (#1628): the campus's own parcels/footprint artifacts, relative
    # to ``settings.data_dir``. ``None`` = inherit the site-level ``SiteProfile.parcels_relpath`` /
    # ``footprint_relpath`` (the single-facility default), resolved via ``geometry_relpaths``.
    footprint_relpath: str | None = None
    parcels_relpath: str | None = None

    # --- IT-load power basis --------------------------------------------------
    # The central IT load and its low/high range. It is an [inference] in EVERY mode, never
    # a disclosure (#1697): for an air-permit-grounded site (Lima, Fort Wayne) it is DERIVED
    # from the disclosed backup by the N+1 relation (the permit discloses the backup, not the
    # load); for a site-plan-grounded facility whose load is NOT disclosed (Urbana Technology
    # Hub) it is a floor-area SCREENING bracket, its basis in ``it_load_citation``. The
    # disclosed interconnection/air-permit MW stays ``[open]`` until an instrument discloses it.
    # ``None`` = the load is entirely ``[open]`` — a disclosed facility (e.g. a rezoning-only
    # second campus) whose MW/instruments are all undisclosed; the three move together (enforced
    # below) and no load-basis citation is carried.
    it_load_mw: float | None = None  # central IT load (N+1 backup ~= IT, or floor-area screening)
    it_load_low_mw: float | None = None  # low end of the range
    it_load_high_mw: float | None = None  # high end
    # The disclosing air permit + committed extraction, when the load is permit-grounded;
    # also the citation the genset/backup figures carry. ``None`` for a site whose load is
    # not permit-disclosed — then ``it_load_citation`` carries the derivation basis instead.
    air_permit_citation: str | None = None
    # The load-basis citation when it is NOT an air permit (e.g. a floor-area screening
    # inference). Exactly one of ``air_permit_citation`` / ``it_load_citation`` grounds the
    # IT load (enforced below).
    it_load_citation: str | None = None
    # Emergency gensets disclosed in the air permit. ``None`` for a facility with no
    # disclosed on-site generation (a site-plan-grounded facility): the power basis then
    # carries no backup / implied-PUE cross-check and the air-dispatch fleet model
    # (:mod:`watermark.air.scenario`) refuses cleanly rather than modeling a fabricated fleet.
    genset_count: int | None = None  # emergency gensets disclosed in the air permit
    genset_mw: float | None = None  # MW each (ekW)
    # --- Site-plan disclosure (non-power facility attributes) -----------------
    # Populated for a facility disclosed by a site-plan / public record rather than an air
    # permit (Urbana Technology Hub): the facility type, gross floor area, and disclosed
    # capital investment — each [reference]/[verified] from the disclosing record, carried
    # so the profile records what IS on the record without inflating it into a power figure.
    facility_type: str | None = None
    gross_floor_area_sqft: int | None = None
    disclosed_investment_usd: float | None = None
    disclosure_citation: str | None = None
    # Disclosed cooling/industrial blowdown discharge — the independent cross-check for the
    # cooling back-solve (:func:`watermark.hydrology.cooling.derive_cooling_basis`, method 2). Per-site
    # (#607): a site that doesn't disclose one leaves these None and the back-solve uses the
    # site's own power-derived consumptive as the high bound (no Lima FM-2 leak).
    blowdown_mgd: float | None = None
    blowdown_citation: str | None = None
    # Cooling archetype (#1054): selected per site, never hardcoded. The default is
    # ``unknown`` — a disclosed facility whose cooling method is not on record must NOT
    # silently inherit the water-intensive evaporative model (it gets a bracketed range
    # instead). ``SiteProfile.facility is None`` resolves to ``off`` in
    # :func:`watermark.hydrology.cooling_models.resolve_cooling_model`.
    cooling_model: CoolingModelType = CoolingModelType.UNKNOWN
    cooling_model_citation: str = "cooling method not disclosed in the record"
    cooling_model_source: Literal["document", "connector", "reference", "assumption"] = "assumption"
    # Per-archetype parameter overrides — a site cites disclosed values here instead of
    # inheriting the archetype defaults. ``None`` = use the spec default (with its cite).
    # A value and its citation travel together (enforced below): an uncited override would
    # silently pick up the generic archetype citation and misattribute the number.
    wue_l_per_kwh: float | None = None
    wue_citation: str | None = None
    cycles_of_concentration: float | None = None
    cycles_citation: str | None = None
    # Condenser heat-rejection overhead for the once_through withdrawal (#1153): heat
    # rejected = IT load x this multiplier (server load + cooling-system work). None = use
    # the archetype default (~1.15). Only the once_through math reads it; the tower/hybrid
    # fold cooling overhead into their empirical WUE instead.
    heat_reject_multiplier: float | None = None
    heat_reject_multiplier_citation: str | None = None

    # --- Air-quality / backup-generation dispatch modeling (watermark.air, epic #1172) ----
    # The committed air-permit extraction that grounds the fleet's emission rates + the
    # synthetic-minor NSR caps, relative to ``settings.extracted_dir`` (the #1180 seam that
    # retires the Lima-default in ``air.emissions``). ``None`` = no wired air permit for this
    # facility yet: permit-basis factors refuse cleanly and the NSR caps come back empty
    # (``air.emissions.load_nsr_caps``) rather than silently inheriting another site's permit.
    air_permit_relpath: str | None = None
    # Per-unit genset exhaust-stack geometry for the AERMOD dispersion deck (Tier-1, #1178).
    # Present ONLY for a site whose permit / manufacturer data discloses the engine specs —
    # for Lima the permit redacts make/model/size as CBI, so these stay ``None`` and
    # ``air.aermod.inp`` falls back to the ``assumption``-tagged screening geometry (never
    # presented as the permit's). Set together with a citation (paired below); when set they
    # travel as ``document`` provenance.
    genset_stack_height_m: float | None = None
    genset_stack_diameter_m: float | None = None
    genset_stack_exit_velocity_ms: float | None = None
    genset_stack_exit_temp_k: float | None = None
    genset_stack_citation: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _fill_key(cls, data: object) -> object:
        """Mint the stable dedupe ``key`` from ``name`` when a profile leaves it blank (#1628)."""
        if isinstance(data, dict) and not data.get("key"):
            name = data.get("name")
            if isinstance(name, str) and name:
                data["key"] = _facility_slug(name)
        return data

    @model_validator(mode="after")
    def _override_citations_paired(self) -> SiteFacility:
        # The IT-load triple moves together: all three set (a bracketed load) or all None (the
        # load is entirely [open] — a disclosed facility, e.g. a rezoning-only second campus,
        # whose MW/instruments are all undisclosed).
        load_parts = (self.it_load_mw, self.it_load_low_mw, self.it_load_high_mw)
        if any(v is not None for v in load_parts) and any(v is None for v in load_parts):
            raise ValueError(
                "it_load_mw / it_load_low_mw / it_load_high_mw must be set together (a bracketed "
                "load) or all left None (the load is entirely [open])"
            )
        # A disclosed load must be grounded by EXACTLY ONE basis: an air permit (Lima/Fort Wayne)
        # or a non-permit derivation cite (Urbana's floor-area screening). Neither ⇒ an uncited
        # load figure; both ⇒ an ambiguous ground (``derive_power_basis`` would silently drop
        # ``it_load_citation`` and treat the load as permit-grounded). An [open] load (None)
        # carries no basis citation at all.
        if self.it_load_mw is None:
            # An [open] load carries no load-DERIVATION basis — a screening/derivation cite is
            # meaningless with no load to ground.
            if self.it_load_citation is not None:
                raise ValueError(
                    "an open IT load (it_load_mw=None) carries no it_load_citation — set a load to "
                    "ground it, or leave it_load_citation None"
                )
            # An air permit MAY still be cited on an open-load facility, but only in its documented
            # secondary role — grounding disclosed gensets (#1628 review; e.g. a permit disclosing a
            # genset fleet before any IT load is derived). With no gensets it would ground nothing.
            if self.air_permit_citation is not None and self.genset_count is None:
                raise ValueError(
                    "air_permit_citation on an open-load facility (it_load_mw=None) must ground "
                    "disclosed gensets — set genset_count/genset_mw, or leave air_permit_citation None"
                )
        elif (self.air_permit_citation is None) == (self.it_load_citation is None):
            raise ValueError(
                "the IT load needs exactly one basis citation — set air_permit_citation "
                "(permit-grounded) or it_load_citation (a non-permit derivation basis), not both/neither"
            )
        # A disclosed facility is at least `confirmed` (#1628): `investigation` is the honest floor
        # for a site with NO SiteFacility — the frontend equates it with facility-absence, so a
        # facility carrying it would ship the self-contradiction "disclosed facility (investigation)".
        if self.status is FacilityLifecycle.INVESTIGATION:
            raise ValueError(
                "a disclosed SiteFacility is at least `confirmed` — `investigation` is the "
                "facility-absent floor (there is no SiteFacility to attach it to)"
            )
        # Operator / end-use each travel with their own citation (#1628): a disclosed value can
        # never pass uncited, and end_use=None keeps the end use honestly [open].
        if (self.operator is None) != (self.operator_citation is None):
            raise ValueError("operator and operator_citation must be set together")
        if (self.end_use is None) != (self.end_use_citation is None):
            raise ValueError("end_use and end_use_citation must be set together")
        # Gensets are paired: a count without a rating (or vice-versa) can't form a backup
        # figure. A site-plan-grounded facility with no disclosed generation leaves both None.
        if (self.genset_count is None) != (self.genset_mw is None):
            raise ValueError("genset_count and genset_mw must be set together (or both left None)")
        # Site-plan disclosure attributes (type / floor area / investment) carry
        # [reference]/[verified] claims — they travel with disclosure_citation (both or
        # neither), so a disclosed value can never pass uncited.
        has_disclosure = any(
            v is not None
            for v in (self.facility_type, self.gross_floor_area_sqft, self.disclosed_investment_usd)
        )
        if has_disclosure != (self.disclosure_citation is not None):
            raise ValueError(
                "site-plan disclosure fields (facility_type / gross_floor_area_sqft / "
                "disclosed_investment_usd) and disclosure_citation must be set together"
            )
        if (self.wue_l_per_kwh is None) != (self.wue_citation is None):
            raise ValueError("wue_l_per_kwh and wue_citation must be set together")
        if (self.cycles_of_concentration is None) != (self.cycles_citation is None):
            raise ValueError("cycles_of_concentration and cycles_citation must be set together")
        if (self.heat_reject_multiplier is None) != (self.heat_reject_multiplier_citation is None):
            raise ValueError(
                "heat_reject_multiplier and heat_reject_multiplier_citation must be set together"
            )
        # Genset stack geometry is all-or-nothing: a partial set would silently mix a
        # disclosed dimension with an assumed one under one citation. Either the site
        # discloses the full geometry (+ its citation) or it leaves all five None.
        stack = (
            self.genset_stack_height_m,
            self.genset_stack_diameter_m,
            self.genset_stack_exit_velocity_ms,
            self.genset_stack_exit_temp_k,
            self.genset_stack_citation,
        )
        if any(v is not None for v in stack) and any(v is None for v in stack):
            raise ValueError(
                "genset stack geometry (height/diameter/exit_velocity/exit_temp) and its "
                "citation must all be set together, or all left None (assumed screening geometry)"
            )
        return self

    @property
    def has_disclosed_stack(self) -> bool:
        """True if the site discloses a documented genset stack geometry (not the CBI case)."""
        return self.genset_stack_citation is not None


class SiteProfile(BaseModel):
    """Everything specific to one watershed-point site. Frozen — a fixed reference value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _fill_from_yaml(cls, data: object) -> object:
        """Back-fill identity fields from data/sites.yaml (the SSOT for #1027).

        Every SiteProfile must have a matching entry in the YAML registry. The fields
        ``place``, ``receiving_water_name``, and ``map_view_lat/lon/zoom`` are authoritative
        in the YAML; profiles that omit them get them filled here. Profiles that still carry
        them explicitly (e.g. during a migration) take precedence via ``setdefault``.
        """
        if not isinstance(data, dict):
            return data
        slug = data.get("slug")
        if not slug:
            return data
        identity = _get_identity()
        entry = identity.get(str(slug))
        if entry is None:
            # Unregistered slug (e.g. a test stub) — skip filling; `watermark sites check` is the gate.
            return data
        data.setdefault("place", entry.place)
        if entry.receiving_water is not None:
            data.setdefault("receiving_water_name", entry.receiving_water)
        if entry.map_lat is not None:
            data.setdefault("map_view_lat", entry.map_lat)
        if entry.map_lon is not None:
            data.setdefault("map_view_lon", entry.map_lon)
        if entry.map_zoom is not None:
            data.setdefault("map_view_zoom", entry.map_zoom)
        return data

    @model_validator(mode="after")
    def _facility_has_demand_pressure_destination(self) -> SiteProfile:
        # The demand-pressure sensitivity is facility-gated (``derive_demand_pressure`` raises for
        # a facility-less site), and ``write_demand_pressure`` needs a destination. So a profile
        # WITH a documented facility must carry a non-None ``demand_pressure_relpath`` — else the
        # feed it is entitled to could never be written (#1660). The reverse (a facility-less site
        # must be None) is intentionally NOT enforced here: 15 registered peers still carry a
        # dangling path pending the network-wide cleanup this ME-A fix deferred — WPAFB is the
        # first facility-less profile set to None.
        if self.facility is not None and self.demand_pressure_relpath is None:
            raise ValueError(
                f"site {self.slug!r} has a documented facility but demand_pressure_relpath is None "
                "— a facility site needs a destination for its demand-pressure feed"
            )
        return self

    # A raw "TODO" in a grid-identity citation would render verbatim on the grid backdrop, so
    # it is gated at the REGISTRY level (`grid_identity_todo_violations` → `watermark sites
    # check`, B3/#1639) rather than at construction — a scaffolded DRAFT profile legitimately
    # carries TODO placeholders while it is being authored (see `scaffold_profile_src`).

    # --- Identity (mirrors sites.ts; ``basin`` is the shared-across-Maumee axis) ---------
    slug: str
    # place, receiving_water_name, map_view_* are authoritative in data/sites.yaml and filled
    # by _fill_from_yaml at construction time (#1027). Defaults satisfy mypy; the validator
    # ensures they're set for all registered slugs. `watermark sites check` is the enforcement gate.
    place: str = ""
    basin: str

    # --- Config knobs resolved into Settings (see PROFILE_SETTINGS_FIELDS) ---------------
    nwis_sites: list[str]
    nasa_power_lat: float
    nasa_power_lon: float
    rsei_fips: str
    econ_fips: str
    eia861_utility_number: int
    eia_state: str = "OH"  # the network is Ohio-dominant; only non-OH sites (Fort Wayne) override
    # County/City GIS layer endpoints — per-site. The connector code that reads them is now
    # jurisdiction-agnostic: the field names + encodings live in the gis_* schemas below (#237).
    parcels_url: str
    zoning_url: str
    floodzone_url: str
    gnis_default_state: str = "OH"  # only non-OH sites (Fort Wayne) override
    hydro_utm_epsg: int
    # Ohio LSC General Assembly (statusreport.lsc.ohio.gov is Ohio-only); "" disables the
    # connector for an out-of-state site (Fort Wayne). Ohio sites share the 136th GA.
    lsc_default_ga: str = "136"

    # --- GIS layer field-maps (jurisdiction schemas; #237) ------------------------------
    # The ArcGIS field names + value encodings the GIS connectors read, lifted off Lima/Allen
    # so a new jurisdiction is config, not a copied connector (mirrors the OPC Profile idiom).
    # Optional: ``None`` means "no connector for this layer here yet" — the connector/CLI then
    # refuses cleanly rather than querying another jurisdiction's fields. Read via
    # ``active_profile`` (NOT in PROFILE_SETTINGS_FIELDS — never bled into Settings).
    gis_parcel: GisParcelSchema | None = None
    gis_zoning: GisZoningSchema | None = None
    gis_flood: GisFloodSchema | None = None

    # --- Stormwater design point + cited assumptions (hydrology/stormwater.py) -----------
    # The NOAA-Atlas-14 corridor point — distinct from the nasa_power loop centroid above.
    design_lat: float
    design_lon: float
    corridor_name: str  # the Atlas-14 design-storm corridor label (drainage.py meta.subject)
    dominant_hsg: str
    hsg_citation: str
    pre_cover: str
    post_cover: str
    developed_pervious_cover: str
    # Time of concentration (hr) for the design-storm peak. Impervious paving shortens travel
    # time and sharpens the peak, so pre- and post-development cannot share one Tc: ``pre_tc_hr``
    # is the pervious (prior-cover) catchment and ``post_tc_hr`` the fully-impervious bound. Each
    # scenario's Tc is interpolated on its impervious fraction between the two
    # (``stormwater._scenario_tc_hr``); the full-buildout peak uses the shorter ``post_tc_hr``.
    # Screening-grade assumptions — the defaults hold for pre-parity sites; a reference site sets
    # both from its catchment. ``roundabout_tc_hr`` is the small Cole/Beery roundabout catchment
    # (``roundabout.py``) — a distinct single fully-impervious scenario, not a pre/post pair.
    pre_tc_hr: float = 1.0
    post_tc_hr: float = 0.35
    roundabout_tc_hr: float = 0.2
    noaa_fallback_24h_depth_in: dict[int, float]
    parcels_relpath: str  # relative to settings.data_dir
    footprint_relpath: str  # relative to settings.data_dir
    # The frozen external-corroboration corridor geometry dir (corridor.geojson +
    # corridor-centerline.geojson), relative to settings.data_dir — folded into the GIS
    # findings by site/gismap.merge_corridor_layer. ``None`` = no corridor layer for this
    # site (the merge then emits nothing rather than reading another site's geometry).
    corridor_geo_relpath: str | None = None

    # --- Per-site onboard reach outputs (point-specific writes; relative to data_dir) ----
    # The point-specific connector outputs `watermark onboard` writes. Lima keeps its legacy
    # (un-slugged) filenames; a new site slug-scopes them so onboarding never clobbers Lima.
    # Basin/state/PJM/national outputs (derived 7Q10, ECHO POTW, consumer-energy is state-
    # but kept per-site for uniformity, ba-interchange, federal) — the shared ones are NOT here.
    # Hydrology (#326):
    climatology_relpath: str  # NASA-POWER climatology (hydrology/climate.py)
    corridor_ddf_relpath: str  # NOAA Atlas-14 corridor DDF (hydrology/drainage.py)
    # Economics (per-site by county FIPS / state / utility):
    baseline_relpath: str  # Census+QCEW county baseline (economics/baseline.py)
    rsei_relpath: str  # EPA RSEI county toxics inventory (rsei.py)
    consumer_energy_relpath: str  # EIA consumer energy prices (economics/energy.py)
    # Facility demand→price-pressure sensitivity (economics/energy.py). Facility-GATED: the feed
    # only exists for a site with a documented ``facility`` (``derive_demand_pressure`` raises
    # otherwise), so a facility-less site declares ``None`` — no destination — rather than a path
    # to a file that can never be written. Mirrors onboard's ``… if facility is not None else None``.
    demand_pressure_relpath: str | None = None
    grid_relpath: str  # EIA-861 utility + grid profile (grid/utility.py)

    # --- Toxics corridor inference (hydrology/toxics.py) ---------------------------------
    toxic_corridor_bbox: tuple[float, float, float, float]  # lat_min, lat_max, lon_min, lon_max
    receiving_water_name: str = ""  # authoritative in data/sites.yaml; filled by _fill_from_yaml

    # --- Water-balance routing fallback (hydrology/balance.py) ---------------------------
    plant_receiving: dict[str, tuple[str, str]]  # fid -> (receiving water, citation)
    abstraction_gage: str
    # The municipal WTP intake reach, grounded with the abstraction gage's live streamflow.
    # Per-site (#1159): an empty ``abstraction_node_id`` means this site has no modeled
    # intake node, so ``build_water_balance`` omits it rather than labeling another site's
    # gage as Lima's WTP. ``abstraction_river`` fills the node's ``receiving_water``.
    abstraction_node_id: str = ""
    abstraction_node_name: str = ""
    abstraction_river: str = ""

    # --- Refill supply rivers (hydrology/refill.py) -------------------------------------
    # The site's two refill supply rivers (the model sums both, each passby-adjusted). Named
    # by role, not river: for Lima, primary = Auglaize (Fort Jennings), secondary = Ottawa.
    supply_gage_primary: str
    supply_gage_secondary: str
    passby_primary_cfs: float
    passby_secondary_cfs: float
    # The supply rivers' display names + per-gauge caveats (#1159). Per-site so no Lima river
    # name or Fort-Jennings caveat leaks into another site's refill screen. Empty = unset.
    supply_river_primary: str = ""
    supply_river_secondary: str = ""
    supply_note_primary: str = ""
    supply_note_secondary: str = ""
    # Drainage-area-ratio transfer of the primary gage's daily flow to the intake reach (#1613).
    # The primary gage sits DOWNSTREAM of the intake with more drainage area, so its record
    # overstates the flow available at the intake — and when it also sits below a confluence
    # whose tributary is routed separately (the secondary river), it double-counts that tributary.
    # This ratio scales the primary series to the intake reach before the sequent-peak; default
    # 1.0 = the gage is the intake (no transfer). Lima's 0.614 = (332-128)/332 nets the Ottawa's
    # drainage out of the Fort-Jennings Auglaize record — the SAME committed transfer already
    # applied to that gage's 7Q10 at the network outlet (low-flow-7q10.derived.yaml).
    intake_da_ratio_primary: float = 1.0

    # --- Tier-1 SWMM sanitary campus routing (hydrology/tier1.py, #1159) -----------------
    # The campus forcemain display labels (routing ``via`` id -> label, e.g. bosc-fm2 -> FM-2)
    # and the receiving-plant node-id -> name map used to render the sanitary surcharge, plus
    # the dry-weather industrial base and capacity fallback consulted ONLY when the cited
    # sanitary basis is absent. All empty/zero for a site with no modeled campus sanitary
    # routing — the surcharge then degrades to the cited basis rather than Lima's plants.
    forcemain_labels: dict[str, str] = {}
    sanitary_receiver_names: dict[str, str] = {}
    # Fallback peak hydraulic capacity: (plant, peak_capacity_mgd, forcemain_label, citation).
    sanitary_capacity_fallback: list[tuple[str, float, str, str]] = []
    # Campus dry-weather industrial base (MGD) used only when no cited sanitary basis loads.
    campus_dry_weather_mgd: float = 0.0

    # --- Grid / facility (grid/*.py, facility/power.py) ---------------------------------
    # The disclosed DC facilities (#1628): a site holds N campuses (empty = no identified facility
    # yet → grid backdrop only, no fabricated campus load share). The FIRST is the primary/modeled
    # campus (``facility`` property) that drives the water/power/air math; later entries are
    # structured but not each run through hydrology. The serving-utility *identity* (name) is
    # connector-sourced (EIA-861); only its provenance is per-site: a corpus document for Lima, the
    # EIA-861/PUCO service-territory record for a site without corpus coverage.
    facilities: tuple[SiteFacility, ...] = ()
    serving_utility_citation: str
    # Default "reference" (EIA-861/PUCO service-territory record); only a corpus-grounded site
    # (Lima, from its air permit) overrides to "document".
    serving_utility_source: Literal["document", "connector", "reference", "assumption"] = (
        "reference"
    )

    # --- Air-quality met stations (watermark.air.connectors, #1179 → #1180 seam) ----------
    # The AERMET surface + upper-air observing stations a Tier-1 AERMOD run for this site draws
    # its meteorology from. These are the per-site knobs the #1179 met connectors (`isd.py` /
    # `igra.py`) read off ``Settings`` — this is the ``SiteProfile`` half they name as the
    # "#1180 seam": both feed ``Settings.air_surface_station`` / ``air_upperair_station`` via
    # ``PROFILE_SETTINGS_FIELDS`` (env/kwarg still wins). Empty = not pinned; the connector then
    # refuses cleanly rather than fabricating a station, and the minimal AERMOD run stays
    # flat-terrain + operator-supplied canned met. The AERMAP terrain domain needs no separate
    # knob — it centres on the profile's ``nasa_power_lat``/``lon`` + ``air_terrain_halfwidth_deg``.
    air_surface_station: str = ""  # NOAA ISD 'USAF-WBAN' surface station id
    air_upperair_station: str = ""  # NOAA IGRA v2 upper-air sounding station id

    # --- Grid market (grid/market.py) ---------------------------------------------------
    lmp_usd_mwh: float  # zonal day-ahead LMP fallback (connector-sourced when lmp_pnode_id is set)
    lmp_citation: str
    # The site's PJM pricing zone for the live LMP connector (grid/lmp.py, #121). When pinned,
    # the connector's zonal day-ahead mean overrides lmp_usd_mwh; 0/"" leaves the placeholder
    # (e.g. Bryan/AMP #411, Fort Wayne/I&M #361 — zones not yet pinned). AEP=8445784, ATSI=116013753.
    lmp_pnode_id: int = 0
    lmp_pnode_name: str = ""
    # Balancing authority / RTO (B2/#1639). The EIA-930 respondent code (``ba_code``, e.g.
    # "PJM", "MISO") + its RTO display name. Empty = unconfirmed: the grid layer then resolves
    # PJM only for a serving utility in the confirmed per-utility map, and otherwise reports the
    # BA as "unknown/unconfirmed" rather than ASSUMING PJM (much of Indiana + any future MISO/SPP
    # site is not PJM). A site whose confirmed utility is off that map pins this explicitly.
    ba_code: str = ""
    rto_name: str = ""

    # --- Per-site committed reference outputs for the regulatory-stack writers (#1639/B1) ----
    # `watermark ferc` / `pjm` / `federal` write PER-SITE content — the FERC↔state-PUC
    # jurisdiction (OH→IN), the LMP pricing zone (AEP→ATSI→DAY), and the campus load shares all
    # vary by site — but historically wrote a single basin-shared path, so a non-Lima run
    # clobbered Lima's committed file (and a non-Lima read returned Lima's data). These relpaths
    # make the write+read per-site (relative to data_dir, like `grid_relpath`). Optional: `None`
    # resolves to a slug-scoped default (`reference/<dir>/<slug>/<file>` — the #762/#780
    # safe-default idiom, `_grid_ref_relpath`); Lima pins the un-slugged legacy paths.
    # (`ba-interchange` is legitimately BA-wide, not per-site — deliberately NOT here.)
    ferc_relpath: str | None = None  # FERC seam (grid/ferc.py)
    pjm_relpath: str | None = None  # PJM market reference (grid/market.py)
    federal_relpath: str | None = None  # federal backdrop (grid/policy.py)

    # --- OEPA permit registry (#844) -----------------------------------------------------
    # Known NPDES permit IDs for this site's facilities. Used by ``watermark oepa discover``
    # to annotate results as "known" vs. "new". Not a Settings knob — per-site constant.
    npdes_permits: list[str] = []

    # --- Civil plan artifacts (hydrology/stormplan.py, #901) -----------------------------
    # Relative path (from settings.data_dir) to the committed storm-plan inventory artifact
    # generated by ``watermark storm-plan --refresh``.  ``None`` = this site has not yet extracted
    # a storm/grading plan — ``load_inventory()`` returns ``None`` rather than reading Lima's
    # artifact. A new site sets this once it commits its own extracted inventory.
    storm_inventory_relpath: str | None = None

    # --- Corpus scope — the content bundle's extracted-tree feeds (#762) -----------------
    # The ``data/extracted/**`` collection prefixes that hold THIS site's records. The bundle's
    # corpus-derived feeds (records/timeline/entities/relationships, via ``load_corpus`` +
    # ``load_records``) read only artifacts whose rel-path is under one of these prefixes, so a
    # non-Lima site never inherits Lima's deeds/permits/filings/meetings. A prefix is a path
    # segment, so it spans both a slug-named collection (``"fort-wayne"``) and a jurisdiction+site
    # hybrid (``"idem/fort-wayne"``). ``None`` = the whole extracted tree — Lima, the reference
    # build that owns the un-slugged Allen-County-OH collections (keeps its bundle byte-identical).
    corpus_relpaths: tuple[str, ...] | None = None

    # --- Civic corridor vocabulary (civic.keywords / pipeline.timeline, #1523) ------------
    # The project-specific meeting subjects that put a subdivision meeting on the corridor
    # timeline (``category: subdivision_meeting``) and select it for summarization: a meeting
    # whose index ``hits`` name one of these is corridor-relevant. Generic township topics
    # (rezoning/easement/annexation/solar/...) and ambiguous names (``hume``/``amazon``) stay
    # searchable in the meeting index ``hits`` but don't by themselves pull routine business onto
    # the chronology. Per-site (#1523) — Lima carries its BOSC corridor set (``bosc``/``bistrozzi``/
    # ``datacenter``/``google``); every other site defaults **empty**, so a peer floods no
    # ``subdivision_meeting`` events until it declares its own subjects (the safe/honest default
    # per the readiness model — a corridor term is never invented). Read directly off
    # ``active_profile(settings)`` (NOT a Settings knob, never bled into ``Settings``).
    corridor_subjects: tuple[str, ...] = ()

    # --- RSEI county (rsei.py) ----------------------------------------------------------
    county_name: str
    # Optional per-site economic-unit caveat, appended to the ``EconomicBaseline.note`` by
    # ``economics.baseline.build_baseline``. For a site whose single-county econ unit does not
    # capture the signature the site's thesis rests on (e.g. WPAFB straddles Greene+Montgomery
    # and its defense-supplier concentration lives in the *other* county), this states that
    # plainly and points the reader at the county/sibling that carries it. Default "" = no note.
    econ_unit_note: str = ""

    # --- Legacy SSG map default view (site/gismap.py) -----------------------------------
    map_view_lat: float = 0.0  # authoritative in data/sites.yaml; filled by _fill_from_yaml
    map_view_lon: float = 0.0
    map_view_zoom: int = 0

    @model_validator(mode="after")
    def _facility_keys_unique(self) -> SiteProfile:
        keys = [f.key for f in self.facilities]
        if len(keys) != len(set(keys)):
            raise ValueError(f"facility keys must be unique within a site; got {keys}")
        return self

    @property
    def facility(self) -> SiteFacility | None:
        """The primary (modeled) campus — the first facility, or ``None`` when the site has none.

        Backward-compatible accessor (#1628): every subsystem that reads a single disclosed
        facility (hydrology cooling, :func:`watermark.facility.power.derive_power_basis`, air,
        readiness, the basin network) operates on this primary campus. Additional
        :attr:`facilities` are structured but not each run through the water/power/air math.
        """
        return self.facilities[0] if self.facilities else None

    @property
    def has_facility_power_basis(self) -> bool:
        """True when the primary facility has a **derivable** IT-load power basis (#1628): a
        facility exists AND its load is not entirely ``[open]``.

        The honest gate for the grid / compute / demand-pressure commands, which derive a campus
        power basis (:func:`watermark.facility.power.derive_power_basis` returns ``None`` in both the
        no-facility and the open-load cases). A rezoning-only campus (load all ``[open]``) is treated
        like no facility for that purpose — never a fabricated Lima-scale load — so those commands
        skip cleanly instead of crashing.
        """
        fac = self.facility
        return fac is not None and fac.it_load_mw is not None

    def facility_geometry(self, fac: SiteFacility) -> tuple[str, str]:
        """Resolve a facility's ``(parcels_relpath, footprint_relpath)`` (#1628) — inheriting the
        site-level paths when the facility carries none of its own (the single-facility default)."""
        return (
            fac.parcels_relpath or self.parcels_relpath,
            fac.footprint_relpath or self.footprint_relpath,
        )


# Fields whose authoritative values live in data/sites.yaml and are filled at construction time
# by _fill_from_yaml (the model_validator). They have empty/zero defaults to satisfy mypy; at
# runtime every registered profile has them set from YAML. `watermark sites check` is the gate.
YAML_BACKED_PROFILE_FIELDS: frozenset[str] = frozenset(
    {"place", "receiving_water_name", "map_view_lat", "map_view_lon", "map_view_zoom"}
)

# The config-knob fields a profile shares 1:1 with Settings; Settings fills any of these the
# caller did not set explicitly (env/dotenv/kwarg) from the active profile.
PROFILE_SETTINGS_FIELDS: tuple[str, ...] = (
    "nwis_sites",
    "nasa_power_lat",
    "nasa_power_lon",
    "rsei_fips",
    "econ_fips",
    "eia861_utility_number",
    "eia_state",
    "parcels_url",
    "zoning_url",
    "floodzone_url",
    "gnis_default_state",
    "hydro_utm_epsg",
    "lsc_default_ga",
    "air_surface_station",
    "air_upperair_station",
)
