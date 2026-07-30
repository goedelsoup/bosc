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
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from watermark.connectors.gis_schema import GisFloodSchema, GisParcelSchema, GisZoningSchema

_YAML_PATH = Path(__file__).parents[3] / "data" / "sites.yaml"

# Canonical three-letter month abbreviations (English, uppercase) — hardcoded rather than derived
# from `calendar` (which is locale-dependent) or `watermark.hydrology.et` (hydrology cannot be
# imported here). Used to validate `SiteProfile.summer_season_months` (#1624).
_MONTH_ABBRS: frozenset[str] = frozenset(
    {"JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"}
)


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


class FacilityKind(StrEnum):
    """What KIND of thing a :class:`SiteFacility` describes (#1664, epic #1659 ME-E).

    The model grew up around the **data center** — an IT load, a genset fleet, a cooling
    archetype — because that is the network's subject. But a watershed point can be dominated by
    a facility that has none of those and still drives the water / power / discharge story: a
    **federal installation** (Wright-Patterson AFB) runs its own wells, its own wastewater
    outfalls, and its own load, and is invisible to every instrument the data-center model reads
    (no air-permit genset bank, no site plan, no county CAMA parcel).

    ``federal_installation`` carries a :class:`FederalInstallation` block instead of the IT-load /
    genset / cooling dimensions, and the data-center math refuses it by construction rather than
    modeling a base as if it were a campus: the IT-load triple must be ``[open]``, the cooling
    archetype must be ``off`` (there is no IT-load-driven cooling-water demand to derive), and the
    per-archetype overrides must be unset. See :meth:`SiteFacility._installation_kind_consistent`.

    This is a **kind**, not a grade: an installation is graded on the same documentary-depth
    rule as a campus (:attr:`SiteFacility.is_instrument_grounded`) — a filed federal instrument
    (a CERCLA §120 Federal Facility Agreement) grounds it the way an air permit grounds Lima.
    """

    DATA_CENTER = "data_center"  # the network's default subject (every campus)
    FEDERAL_INSTALLATION = "federal_installation"  # a federal enclave (WPAFB)


class ItLoadGrounding(StrEnum):
    """The evidentiary grounding of a facility's disclosed IT load — the grade #1630 keys facility
    readiness (``watermark.site.readiness``) on, so a permit-grounded and a screening-only facility
    produce distinguishable readiness instead of collapsing to one ``live`` label.

    ``permit``/``disclosure`` are **instrument-grounded** ([verified]): an air permit disclosing the
    backup (Lima/Fort Wayne → N+1 IT) or a filed primary-instrument load disclosure (Findlay's SEC
    Form S-1: "30 MW operating / 150 MW take-or-pay"). ``screening`` is an [inference] bracket
    (floor-area / investment; Urbana, Sidney, Troy-Piqua, Wilmington); ``reference`` is a
    [reference] announced "up to" ceiling / press peak (Van Wert, Bowling Green, Springfield). The
    last two are on the record but **not instrument-documented** — they SEED the facility domain
    rather than lifting it to ``live``. A screening bracket is [inference] by construction (epic
    #1626); never collapse it with a [verified] disclosure.
    """

    PERMIT = "permit"  # air-permit-grounded backup → derived IT (Lima, Fort Wayne)
    DISCLOSURE = "disclosure"  # a filed primary-instrument load disclosure (Findlay's SEC S-1)
    SCREENING = "screening"  # an [inference] floor-area / investment bracket
    REFERENCE = "reference"  # a [reference] announced "up to" ceiling / press peak


def _facility_slug(text: str, *, max_len: int = 64) -> str:
    """A stable dedupe slug for a facility ``key`` (local peer of ``facility.candidate._slug`` —
    kept here so ``watermark.sites`` doesn't depend on ``watermark.facility``)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "facility"


# The citation carried by a facility whose cooling method is **not on the record**. It is a
# literal statement of ABSENCE, so it may only stand where that is true — the ``SiteFacility``
# validator refuses it on a facility that pins an archetype or claims a non-``assumption``
# source (either would ship a disclosed method under "not disclosed in the record").
UNDISCLOSED_COOLING_CITATION = "cooling method not disclosed in the record"


def _require_together(*fields: tuple[str, object], label: str = "", note: str = "") -> None:
    """All-or-nothing pairing: every named field is set, or every one is left ``None``.

    The single home for the :class:`SiteFacility` pairing discipline — a disclosed value and
    its citation (or a value and its inseparable partner, e.g. genset count x rating) travel
    together, so a disclosed value can never pass uncited and a half-set group can never
    silently mix a disclosed dimension with an assumed one under one citation. ``label`` names
    a multi-field group ("genset stack geometry") ahead of the field list; ``note`` appends the
    field-specific gloss ("or both left None", the ``[open]`` reading, …).
    """
    if any(v is not None for _, v in fields) and any(v is None for _, v in fields):
        names = [n for n, _ in fields]
        joined = " and ".join(names) if len(names) == 2 else " / ".join(names)
        subject = f"{label} ({joined})" if label else joined
        raise ValueError(f"{subject} must be set together{f' {note}' if note else ''}")


class FederalInstallation(BaseModel):
    """A federal enclave's own land / water / wastewater / power / toxics **identity** (#1664).

    The block a :class:`SiteFacility` of kind ``federal_installation`` carries in place of the
    data-center dimensions. It answers the three questions the generic models structurally cannot
    for an enclave, and it answers them by **pointing at instruments**, never by re-keying them:

    * **Land** — a federal enclave is off the county tax rolls, so no county CAMA parcel layer will
      ever carry it (``SiteProfile.gis_parcel`` is honestly ``None`` for WPAFB and always will be).
      ``register_name`` is the enclave's key in the **DoD MIRTA** register — the federal peer of a
      parcel id — which :mod:`watermark.connectors.federal_land` resolves to committed boundary
      geometry so the ``places`` domain can activate off non-CAMA land.
    * **Water / wastewater / power** — the base runs its own supply wells, its own outfalls, and
      its own load. The **documented** figures are read out of ``record_relpath`` (the committed
      extraction), so this block never restates them; what it adds is what that record does not
      carry — the NPDES permits (EPA ECHO) and the load, which stays ``[open]`` until an
      instrument discloses it.
    * **Toxics** — ``tri_facility_id`` / ``tri_county_fips`` locate the enclave's OWN row in
      EPA TRI/RSEI. These are load-bearing precisely because they usually **disagree** with the
      site's ``rsei_fips``: an installation straddling two counties reports from the one the
      profile did not pick as its economic unit, so the county backdrop misses the enclave by
      construction. Recording the enclave's own county here is what lets
      :mod:`watermark.enclave` reconcile the two instead of leaving the base severed from the
      toxics layer.

    Every figure here is either a [verified] identifier from a named federal source or ``None``
    (``[open]``). Nothing is estimated; a value and its citation travel together.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- Identity in the federal register -------------------------------------
    # The reporting component + owning department, as the federal registers name them (MIRTA
    # ``SITEREPORTINGCOMPONENT``; EPA TRI ``asgn_agency``). Free text, not an enum: the register
    # vocabulary spans services, Guard components and defence agencies, and inventing a closed
    # set here would force a mis-fit on the first non-Air-Force enclave.
    component: str
    agency: str
    # The enclave's key in the **DoD MIRTA** site register (``FEATURENAME``) — the federal peer of
    # a parcel id, and the join `watermark.connectors.federal_land` queries on. ``None`` = the
    # enclave is not in MIRTA (or has not been located in it yet): the land seam then stays
    # ``[open]`` and no boundary is fabricated from a bounding box.
    register_name: str | None = None
    register_citation: str | None = None

    # --- The grounding instrument ---------------------------------------------
    # The committed extraction the enclave's documented water / contaminant facts are READ from
    # (relative to ``settings.extracted_dir``) — e.g. the CERCLA §120 Federal Facility Agreement,
    # which states the acreage, the supply wells, the well fields, the treatment units, the waste
    # sites and the contaminants. Those figures are deliberately NOT restated as fields here:
    # re-keying a primary record into a profile is exactly the drift this repo refuses, so
    # :mod:`watermark.enclave` projects them from the record instead. This is also the facility's
    # instrument grounding (:attr:`SiteFacility.is_instrument_grounded`) — a filed federal
    # instrument grounds an installation the way an air permit grounds a campus.
    record_relpath: str
    record_citation: str
    record_source: Literal["document", "connector", "reference", "assumption"] = "document"

    # --- Water supply (EPA SDWIS — not in the CERCLA record) ------------------
    # The enclave's own **public water systems**, by PWSID. A base does not buy from the city: it
    # runs its own community water systems off its own wells, and SDWIS is where their source,
    # their population served and their connection count are on the record — the closest thing to
    # a metered water footprint the enclave publishes. Empty = ``[open]``.
    pwsids: tuple[str, ...] = ()
    pws_citation: str | None = None

    # --- Wastewater (EPA ECHO / the state permit — not in the CERCLA record) ---
    # The enclave's own NPDES permits. Empty = ``[open]``, never "no discharge".
    npdes_permits: tuple[str, ...] = ()
    npdes_citation: str | None = None

    # --- Power / withdrawal (both ``[open]`` for WPAFB) -----------------------
    # An installation-wide electrical load and a raw-water withdrawal, each present ONLY when an
    # instrument discloses it. ``None`` is the honest default: a base is unmistakably a large
    # power and water user, and that is precisely why no figure may be invented for it — the
    # grid stack emits the county/utility backdrop with ``load_share=None`` instead.
    load_mw: float | None = None
    load_citation: str | None = None
    withdrawal_mgd: float | None = None
    withdrawal_citation: str | None = None

    # --- Toxics identity (EPA TRI / FRS / NPL) --------------------------------
    # The enclave's own TRI facility id and the county it REPORTS FROM — which for a straddling
    # installation is not the site's ``rsei_fips``. ``tri_county_fips`` is the scope
    # :func:`watermark.enclave.build_enclave_inventory` reduces RSEI against.
    tri_facility_id: str | None = None
    tri_county_fips: str | None = None
    tri_county_name: str | None = None
    epa_registry_id: str | None = None  # EPA FRS registry id (optional; not every enclave has one)
    tri_citation: str | None = None

    @model_validator(mode="after")
    def _identity_citations_paired(self) -> FederalInstallation:
        _require_together(
            ("register_name", self.register_name),
            ("register_citation", self.register_citation),
            note="(or both left None — the enclave is not located in the federal land register)",
        )
        # An empty id tuple is [open], so it carries no citation; a disclosed list must.
        if bool(self.pwsids) != (self.pws_citation is not None):
            raise ValueError(
                "pwsids and pws_citation must be set together (or both left empty/None — the "
                "enclave's water systems are [open], not 'served by the municipality')"
            )
        if bool(self.npdes_permits) != (self.npdes_citation is not None):
            raise ValueError(
                "npdes_permits and npdes_citation must be set together (or both left empty/None "
                "— the enclave's outfalls are [open], which is not the same as 'no discharge')"
            )
        _require_together(("load_mw", self.load_mw), ("load_citation", self.load_citation))
        _require_together(
            ("withdrawal_mgd", self.withdrawal_mgd),
            ("withdrawal_citation", self.withdrawal_citation),
        )
        # The TRI identity is all-or-nothing: a facility id without the county it reports from
        # cannot be reduced against RSEI, and a county without the id cannot be narrowed to the
        # enclave — a half-set group would silently screen the wrong rows.
        _require_together(
            ("tri_facility_id", self.tri_facility_id),
            ("tri_county_fips", self.tri_county_fips),
            ("tri_county_name", self.tri_county_name),
            ("tri_citation", self.tri_citation),
            label="the enclave TRI identity",
            note="or all left None (the enclave's TRI row is [open])",
        )
        if self.epa_registry_id is not None and self.tri_facility_id is None:
            raise ValueError(
                "epa_registry_id identifies the enclave's EPA-registered facility — set it only "
                "alongside the TRI identity it belongs to"
            )
        return self


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

    A third mode is not a data center at all:

    * **Federal enclave** (Wright-Patterson AFB, #1664): ``kind = federal_installation`` and an
      :class:`FederalInstallation` block in place of the IT-load / genset / cooling dimensions.
      The base's water, wastewater and land are documented by federal instruments the campus
      models never read (a CERCLA §120 agreement, the DoD MIRTA land register, EPA TRI), and its
      load is ``[open]``. The data-center math refuses it by construction rather than sizing a
      base as a campus — see :meth:`_installation_kind_consistent`.

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
    # What kind of facility this is (#1664). Defaults to ``data_center`` — every campus in the
    # network — so no existing profile changes. ``federal_installation`` swaps the data-center
    # dimensions for the ``installation`` block below.
    kind: FacilityKind = FacilityKind.DATA_CENTER
    installation: FederalInstallation | None = None
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
    # The evidentiary GRADE of a non-permit disclosed load (#1630): a ``disclosure`` (a filed
    # primary instrument — Findlay's SEC S-1), a ``screening`` [inference] bracket (Urbana/Sidney/
    # …), or a ``reference`` announced ceiling (Van Wert/Bowling Green/Springfield). Paired with
    # ``it_load_citation`` (enforced below): a **permit**-grounded load derives ``permit`` grounding
    # from the air permit (leave this None), and an [open] load has no grade. Read via the
    # ``it_load_grounding`` property, which folds in the permit case, so facility readiness grades
    # ``live`` (instrument-grounded) vs ``seeded`` (screening/announcement) without parsing prose.
    it_load_source: ItLoadGrounding | None = None
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
    # The default is the ``unknown``-archetype citation and nothing else: it asserts that the
    # record discloses no method, so the validator below refuses it on a facility that pins an
    # archetype or claims a non-``assumption`` source (#1634).
    cooling_model_citation: str = UNDISCLOSED_COOLING_CITATION
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
    def _installation_kind_consistent(self) -> SiteFacility:
        """A ``federal_installation`` carries its enclave block and **none** of the data-center
        dimensions; a ``data_center`` carries no enclave block (#1664).

        This is the structural half of the refusal. A base is a large power and water user, so
        the tempting failure is to let it inherit the campus math and emit a plausible number:
        an IT load standing in for the installation's load, the ``unknown`` cooling archetype
        bracketing a nonexistent cooling-water demand, a genset fleet dispatched through AERMOD.
        Every one of those would be fabricated. Forbidding the fields makes the enclave's load
        ``[open]`` at the type level, which is what the record actually says, and pins the
        cooling archetype to ``off`` so :func:`watermark.hydrology.cooling.derive_cooling_basis`
        reports an explicit zero data-center cooling load rather than a bracket over silence.
        """
        if (self.kind is FacilityKind.FEDERAL_INSTALLATION) != (self.installation is not None):
            raise ValueError(
                f"kind={self.kind.value} and installation="
                f"{'set' if self.installation is not None else 'None'} disagree — a "
                f"`federal_installation` carries a FederalInstallation block and a `data_center` "
                f"carries none"
            )
        if self.kind is not FacilityKind.FEDERAL_INSTALLATION:
            return self
        # The data-center dimensions, by the name a profile would set them under.
        dc_only: tuple[tuple[str, object], ...] = (
            ("it_load_mw", self.it_load_mw),
            ("it_load_low_mw", self.it_load_low_mw),
            ("it_load_high_mw", self.it_load_high_mw),
            ("it_load_citation", self.it_load_citation),
            ("it_load_source", self.it_load_source),
            ("air_permit_citation", self.air_permit_citation),
            ("air_permit_relpath", self.air_permit_relpath),
            ("genset_count", self.genset_count),
            ("genset_mw", self.genset_mw),
            ("genset_stack_citation", self.genset_stack_citation),
            ("end_use", self.end_use),
            ("gross_floor_area_sqft", self.gross_floor_area_sqft),
            ("disclosed_investment_usd", self.disclosed_investment_usd),
            ("blowdown_mgd", self.blowdown_mgd),
            ("wue_l_per_kwh", self.wue_l_per_kwh),
            ("cycles_of_concentration", self.cycles_of_concentration),
            ("heat_reject_multiplier", self.heat_reject_multiplier),
        )
        set_fields = [n for n, v in dc_only if v is not None]
        if set_fields:
            raise ValueError(
                f"a federal_installation facility carries no data-center dimensions; got "
                f"{set_fields} — an installation's load lives in installation.load_mw (or stays "
                f"[open]), and its water in the record at installation.record_relpath"
            )
        if self.cooling_model is not CoolingModelType.OFF:
            raise ValueError(
                f"a federal_installation facility must pin cooling_model=off (got "
                f"{self.cooling_model.value}) — there is no IT load to derive a cooling-water "
                f"demand from, and `unknown` would publish a bracketed range over an absence"
            )
        return self

    @model_validator(mode="after")
    def _override_citations_paired(self) -> SiteFacility:
        # The IT-load triple moves together: all three set (a bracketed load) or all None (the
        # load is entirely [open] — a disclosed facility, e.g. a rezoning-only second campus,
        # whose MW/instruments are all undisclosed).
        _require_together(
            ("it_load_mw", self.it_load_mw),
            ("it_load_low_mw", self.it_load_low_mw),
            ("it_load_high_mw", self.it_load_high_mw),
            label="the IT-load triple",
            note="(a bracketed load) or all left None (the load is entirely [open])",
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
        # The IT-load grounding GRADE (#1630) pairs with the non-permit basis: a load grounded by
        # ``it_load_citation`` declares which grade via ``it_load_source`` (disclosure / screening /
        # reference). A permit-grounded load derives ``permit`` grounding from the air permit, and an
        # [open] load has no grade — both leave ``it_load_source`` None. ``permit`` is never set by
        # hand (it would double-declare, and disagree silently if the permit citation were dropped).
        if self.it_load_citation is None:
            if self.it_load_source is not None:
                raise ValueError(
                    "it_load_source grades a non-permit disclosed load — set it only alongside "
                    "it_load_citation; a permit-grounded or [open] load leaves it None (permit "
                    "grounding is derived from air_permit_citation)"
                )
        elif self.it_load_source is None or self.it_load_source is ItLoadGrounding.PERMIT:
            raise ValueError(
                "a non-permit disclosed IT load (it_load_citation set) must declare it_load_source "
                "as disclosure / screening / reference — 'permit' is derived from a wired air permit"
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
        _require_together(
            ("operator", self.operator), ("operator_citation", self.operator_citation)
        )
        _require_together(("end_use", self.end_use), ("end_use_citation", self.end_use_citation))
        # Gensets are paired: a count without a rating (or vice-versa) can't form a backup
        # figure. A site-plan-grounded facility with no disclosed generation leaves both None.
        _require_together(
            ("genset_count", self.genset_count),
            ("genset_mw", self.genset_mw),
            note="(or both left None)",
        )
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
        # A disclosed blowdown carries the SAME pairing duty as the overrides below: uncited, it
        # would reach `_derive_evaporative_tower` and pick up the override citation ("not a
        # disclosed discharge for this facility"), mislabelling a real disclosure as a sweep input.
        _require_together(
            ("blowdown_mgd", self.blowdown_mgd), ("blowdown_citation", self.blowdown_citation)
        )
        _require_together(
            ("wue_l_per_kwh", self.wue_l_per_kwh), ("wue_citation", self.wue_citation)
        )
        _require_together(
            ("cycles_of_concentration", self.cycles_of_concentration),
            ("cycles_citation", self.cycles_citation),
        )
        _require_together(
            ("heat_reject_multiplier", self.heat_reject_multiplier),
            ("heat_reject_multiplier_citation", self.heat_reject_multiplier_citation),
        )
        # Genset stack geometry is all-or-nothing: a partial set would silently mix a
        # disclosed dimension with an assumed one under one citation. Either the site
        # discloses the full geometry (+ its citation) or it leaves all five None.
        _require_together(
            ("genset_stack_height_m", self.genset_stack_height_m),
            ("genset_stack_diameter_m", self.genset_stack_diameter_m),
            ("genset_stack_exit_velocity_ms", self.genset_stack_exit_velocity_ms),
            ("genset_stack_exit_temp_k", self.genset_stack_exit_temp_k),
            ("genset_stack_citation", self.genset_stack_citation),
            label="genset stack geometry",
            note="or all left None (assumed screening geometry)",
        )
        # The default cooling citation asserts an ABSENCE ("not disclosed in the record"), so it
        # may only stand where that is literally true. A facility that PINS an archetype
        # (anything but `unknown`) or claims a document/connector/reference source while leaving
        # the citation defaulted would publish a disclosed method under a statement that the
        # record discloses none — the inverse of the pairing discipline enforced just above.
        if self.cooling_model_citation == UNDISCLOSED_COOLING_CITATION and (
            self.cooling_model is not CoolingModelType.UNKNOWN
            or self.cooling_model_source != "assumption"
        ):
            raise ValueError(
                f"cooling_model_citation is still the default {UNDISCLOSED_COOLING_CITATION!r}, "
                f"which only holds for cooling_model=unknown + cooling_model_source=assumption "
                f"(this facility declares {self.cooling_model.value}/{self.cooling_model_source}) "
                "— cite the record that discloses the method"
            )
        return self

    @property
    def is_data_center(self) -> bool:
        """True for a data-center campus — the subject the power / cooling / air models size."""
        return self.kind is FacilityKind.DATA_CENTER

    @property
    def has_disclosed_stack(self) -> bool:
        """True if the site discloses a documented genset stack geometry (not the CBI case)."""
        return self.genset_stack_citation is not None

    @property
    def it_load_grounding(self) -> ItLoadGrounding | None:
        """The evidentiary grade of the IT load, or ``None`` when the load is [open] (#1630).

        Permit grounding is DERIVED from a wired air permit (so it can never silently disagree with
        ``air_permit_citation``); a non-permit disclosed load reports the grade its profile declared
        in ``it_load_source``. ``None`` = the load is entirely [open] (``it_load_mw is None``) — a
        disclosed facility with no gradeable load (a rezoning-only campus).
        """
        if self.it_load_mw is None:
            return None
        if self.air_permit_citation is not None:
            return ItLoadGrounding.PERMIT
        return self.it_load_source

    @property
    def is_instrument_grounded(self) -> bool:
        """True when the facility carries instrument-grade documentary evidence — the #1630 signal
        that grades facility readiness ``live`` rather than ``seeded``.

        Instrument-grounded = an IT load grounded in a primary instrument (a wired air permit or a
        filed disclosure — ``it_load_grounding`` in {permit, disclosure}) **or** a cooling mechanism
        disclosed by a [verified] document/connector. A site-plan / FAQ / floor-area SCREENING
        ([inference]) or a [reference] announced ceiling is on the record but not instrument-
        documented — it SEEDS the facility domain rather than lifting it. Never collapse a screening
        bracket with a permit/disclosure figure (epic #1626).

        A **federal installation** (#1664) is graded on the same rule through its own instrument:
        the enclave's ``record_relpath`` — a filed federal agreement (WPAFB's CERCLA §120 FFA)
        documenting the base's extent, supply wells and contaminant mass — grounds it exactly as an
        air permit grounds a campus. The grade is the *record's* provenance class, so an enclave
        seeded from a press description (``record_source="reference"``) still only SEEDS.
        """
        inst = self.installation
        if inst is not None:
            return inst.record_source in ("document", "connector")
        return self.it_load_grounding in (
            ItLoadGrounding.PERMIT,
            ItLoadGrounding.DISCLOSURE,
        ) or self.cooling_model_source in ("document", "connector")


class DischargeReach(BaseModel):
    """A river reach bracketed by two USGS gages, for the dewatering discharge-signal screen.

    The construction-dewatering wellfield (:mod:`watermark.hydrology.dewatering`) pumps groundwater
    that, if discharged to surface water, enters the reach between an ``upstream`` and a
    ``downstream`` gage; the reach gain (downstream - upstream) carries any point input. Drainage
    areas are ``[reference]`` (USGS NWIS site service, cited) — a gaining reach whose incremental
    drainage dwarfs a small point source cannot resolve it, which the screen reports honestly rather
    than manufacturing a signal. Present only for a site with a committed dewatering wellfield.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    upstream_gage: str
    upstream_name: str
    upstream_da_sqmi: float
    downstream_gage: str
    downstream_name: str
    downstream_da_sqmi: float
    citation: str = "USGS NWIS site service (published drainage areas)"

    @model_validator(mode="after")
    def _drainage_areas_are_ordered(self) -> DischargeReach:
        # The DA-ratio residual (downstream - downstream/upstream * upstream) is only meaningful for a
        # gaining reach with a positive upstream area — guard both before compute_discharge_screen
        # can divide by / rank them.
        if self.upstream_da_sqmi <= 0:
            raise ValueError(f"upstream_da_sqmi must be positive, got {self.upstream_da_sqmi}")
        if self.downstream_da_sqmi <= self.upstream_da_sqmi:
            raise ValueError(
                "downstream_da_sqmi must exceed upstream_da_sqmi (the reach gains drainage "
                f"downstream): {self.downstream_da_sqmi} <= {self.upstream_da_sqmi}"
            )
        return self


class SiteProfile(BaseModel):
    """Everything specific to one watershed-point site. Frozen — a fixed reference value.

    **"Corridor" names four unrelated things here (#1634).** The word is load-bearing in this
    repo's vocabulary but not in one sense, so every field below states which one it means, and
    no code should assume two of them refer to the same geography:

    1. **Design-storm corridor** — a *rainfall* label, not a place: ``corridor_name`` (the
       NOAA Atlas-14 subject) + ``corridor_ddf_relpath`` (its depth-duration-frequency
       artifact). Anchored to ``design_lat``/``design_lon``, the stormwater design point.
    2. **Corroboration geometry** — ``corridor_geo_relpath``, the frozen Periplus-era
       ``corridor.geojson`` + centerline folded into the GIS findings. An actual line/polygon.
    3. **Toxics screening window** — ``toxic_corridor_bbox``, a lat/lon bounding box for the
       RSEI/toxics inference. A screening extent, deliberately coarser than (2).
    4. **Civic subject vocabulary** — ``corridor_subjects``, the meeting *keywords* that put a
       subdivision meeting on the project chronology. Not a geography at all.

    A fifth, purely editorial sense ("the corridor" as the story's subject area) appears in
    prose and report slugs; it is never a modeled value.
    """

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
        # entitled to that feed must carry a non-None ``demand_pressure_relpath`` — else the feed
        # could never be written (#1660). The reverse (a site without one must be None) is
        # intentionally NOT enforced here: 15 registered peers still carry a dangling path pending
        # the network-wide cleanup this ME-A fix deferred.
        #
        # Entitlement is ``has_facility_power_basis``, not "has a facility" (#1664): the writer
        # sizes the sensitivity against a **derivable campus load**, so a facility whose load is
        # entirely ``[open]`` — a rezoning-only campus, or a federal installation, which has no IT
        # load at all — is no more entitled to the feed than a facility-less site. Keying on the
        # power basis is the same gate ``onboard`` and the grid CLI already use.
        if self.has_facility_power_basis and self.demand_pressure_relpath is None:
            raise ValueError(
                f"site {self.slug!r} has a facility with a derivable power basis but "
                "demand_pressure_relpath is None — it needs a destination for its "
                "demand-pressure feed"
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
    # The NOAA-Atlas-14 design-storm point — distinct from the nasa_power loop centroid above.
    design_lat: float
    design_lon: float
    # "Corridor" sense 1 (DESIGN-STORM): a rainfall subject label, not a place — unrelated to
    # the corroboration geometry, the toxics bbox, or the civic vocabulary. See the class docstring.
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
    # Stated Tier-0 screening ``assumption``s (`source: assumption`) — a single-slope proxy for the
    # NRCS velocity method, which needs flow lengths not in the record. These ARE the per-site
    # override seam (a reference site sets both from its catchment); the defaults hold for
    # pre-parity sites. Distinct from the per-method physics constants, which are cited in
    # ``data/reference/hydrology/tier0-parameters.yaml``. ``roundabout_tc_hr`` is the small
    # Cole/Beery roundabout catchment (``roundabout.py``) — a distinct single fully-impervious
    # scenario, not a pre/post pair.
    pre_tc_hr: float = 1.0
    post_tc_hr: float = 0.35
    roundabout_tc_hr: float = 0.2
    # SCS unit-hydrograph peak factor for this site's catchments (WS-10 / #1610). ``None`` uses
    # the cited standard-hydrograph 484 in ``tier0-parameters.yaml``; a site whose terrain is not
    # that shape overrides here with a CITED value — NEH-630 Ch. 16 puts flat/swampy ground near
    # 300 (as low as ~100 in true wetland storage) and steep ground near 600. It sets the
    # dimensionless UH's shape, not just its height, so volume is conserved either way
    # (`solver.runoff`). Read via `solver.parameters.peak_factor`, NOT baked into Settings.
    uh_peak_factor: float | None = None
    noaa_fallback_24h_depth_in: dict[int, float]
    parcels_relpath: str  # relative to settings.data_dir
    footprint_relpath: str  # relative to settings.data_dir
    # The FEDERAL-LAND boundary (#1664), relative to settings.data_dir — committed GeoJSON pulled
    # from the DoD MIRTA site register by `watermark federal-land`. This is a THIRD land path,
    # deliberately not folded into `parcels_relpath`: a parcel assemblage is a county CAMA record
    # (owner, situs, transfer date, valuation) and a federal enclave has none of those — it is off
    # the tax rolls, so no county parcel layer will ever carry it. Keeping the two apart is what
    # lets the `places` domain activate off non-CAMA geometry without a phantom owner column.
    # ``None`` for every site with no federal enclave.
    federal_land_relpath: str | None = None
    # "Corridor" sense 2 (CORROBORATION GEOMETRY): the frozen external-corroboration geometry
    # dir (corridor.geojson + corridor-centerline.geojson), relative to settings.data_dir —
    # folded into the GIS findings by site/gismap.merge_corridor_layer. Real line/polygon
    # geometry, NOT the design-storm label above nor the toxics bbox below. ``None`` = no such
    # layer for this site (the merge emits nothing rather than reading another site's geometry).
    corridor_geo_relpath: str | None = None
    # Construction-dewatering wellfield CSV (relative to settings.data_dir), for the
    # `watermark.hydrology.dewatering` cone-of-impact model. Present ONLY for a site with a
    # committed wellfield (Lima today); a site without one carries no dewatering cone.
    dewatering_wellfield_relpath: str | None = None
    # The upstream/downstream USGS gage reach the dewatering discharge (if to surface water) would
    # register in, for `watermark.hydrology.dewatering_discharge`. Present ONLY where a wellfield is
    # committed AND a bracketing gage pair exists; a site without one carries no discharge screen.
    dewatering_discharge_reach: DischargeReach | None = None
    # The committed discharge-report YAML (relative to settings.data_dir) — the precomputed reach
    # screen + reservoir-recharge read the bundle reads offline, regenerated by
    # `watermark dewatering-discharge --write`. Present ONLY for a site with a committed report.
    dewatering_discharge_relpath: str | None = None

    # --- Per-site onboard reach outputs (point-specific writes; relative to data_dir) ----
    # The point-specific connector outputs `watermark onboard` writes. Lima keeps its legacy
    # (un-slugged) filenames; a new site slug-scopes them so onboarding never clobbers Lima.
    # Basin/state/PJM/national outputs (derived 7Q10, ECHO POTW, consumer-energy is state-
    # but kept per-site for uniformity, ba-interchange, federal) — the shared ones are NOT here.
    # Hydrology (#326):
    climatology_relpath: str  # NASA-POWER climatology (hydrology/climate.py)
    # "Corridor" sense 1 again (DESIGN-STORM): the DDF artifact for ``corridor_name``'s point.
    corridor_ddf_relpath: str  # NOAA Atlas-14 design-storm DDF (hydrology/drainage.py)
    # Economics (per-site by county FIPS / state / utility):
    baseline_relpath: str  # Census+QCEW county baseline (economics/baseline.py)
    rsei_relpath: str  # EPA RSEI county toxics inventory (rsei.py)
    # The federal ENCLAVE's own RSEI row (#1664) — a second, one-facility reduction scoped to the
    # installation's own reporting county (``installation.tri_county_fips``), which for a
    # straddling enclave is NOT ``rsei_fips``. Enclave-GATED, like ``demand_pressure_relpath`` is
    # facility-gated: ``None`` for every site without a ``federal_installation`` facility, so no
    # peer declares a destination for a file that can never be written. It never replaces
    # ``rsei_relpath`` — the county backdrop stays the readiness floor signal; this reconciles the
    # enclave the county scope structurally misses (:mod:`watermark.enclave`).
    enclave_rsei_relpath: str | None = None
    consumer_energy_relpath: str  # EIA consumer energy prices (economics/energy.py)
    # Facility demand→price-pressure sensitivity (economics/energy.py). Facility-GATED: the feed
    # only exists for a site with a documented ``facility`` (``derive_demand_pressure`` raises
    # otherwise), so a facility-less site declares ``None`` — no destination — rather than a path
    # to a file that can never be written. Mirrors onboard's ``… if facility is not None else None``.
    demand_pressure_relpath: str | None = None
    # The local tax mechanics + what-if scenario knobs the economic scenario bands run on
    # (#1665, epic #1659 ME-F) — relative to settings.data_dir. INSTRUMENT-GATED: the
    # assessment ratio, effective millage, sales-and-use rate and the discrete
    # building-share x jobs profiles are one county's abatement agreement, not a model of
    # an abatement, so a site with no such instrument on the record declares ``None`` and
    # the `economics-scenarios` feed is simply absent. Never default it: pricing a peer's
    # build off Allen County's mills is exactly the failure the gate exists to prevent
    # (the Python peer of `econLedger.ts`'s `ledgerProfiles(site) -> null`).
    abatement_parameters_relpath: str | None = None
    grid_relpath: str  # EIA-861 utility + grid profile (grid/utility.py)

    # --- Toxics screening inference (hydrology/toxics.py) --------------------------------
    # "Corridor" sense 3 (TOXICS SCREENING WINDOW): a coarse lat/lon bounding box for the RSEI
    # toxics inference — a screening extent, not the corroboration geometry (sense 2) and not
    # co-extensive with it. Never substitute one for the other.
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

    # Regulatory SUMMER-season months — the fixed permit calendar window the summer design low
    # flow (30Q10 summer) governs, which SELECTS the design low flow in the seasonal screen
    # (`hydrology.scenario.evaluate_seasonal`, #1624). Distinct from the climatic ET0 > precip
    # growing season (a diagnostic, never the switch). Empty = inherit the cited Ohio EPA default
    # (May-Oct, `hydrology.lowflow.OEPA_SUMMER_MONTHS`, from NPDES permit 2PH00006 Part II); a
    # non-Ohio site (e.g. an Indiana/IDEM permit) pins its own window here.
    summer_season_months: tuple[str, ...] = ()

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

    # --- Civic subject vocabulary (civic.keywords / pipeline.timeline, #1523) -------------
    # "Corridor" sense 4 (CIVIC VOCABULARY): meeting KEYWORDS, not a geography — nothing here
    # is spatial, and it never constrains or is constrained by senses 1-3.
    # The project-specific meeting subjects that put a subdivision meeting on the project
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

    @field_validator("summer_season_months", mode="before")
    @classmethod
    def _validate_summer_months(cls, v: object) -> tuple[str, ...]:
        """Uppercase-normalize + validate the regulatory summer-season months (#1624).

        The empty tuple stays empty — the signal to inherit the Ohio EPA default. Any token must
        be a recognized three-letter month abbreviation (``JAN``..``DEC``); an unknown token
        (``"JLY"``) or a duplicate is a profile error, not silently ignored — a typo would
        otherwise never match the canonical month keys and vanish from the seasonal screen.
        Normalization happens here so the stored value is already canonical for comparison.
        """
        if v is None:
            return ()
        if isinstance(v, str) or not isinstance(v, (list, tuple)):
            raise ValueError("summer_season_months must be a sequence of month abbreviations")
        months = [str(m).strip().upper() for m in v]
        unknown = sorted({m for m in months if m not in _MONTH_ABBRS})
        if unknown:
            raise ValueError(f"summer_season_months has unrecognized month(s): {unknown}")
        if len(set(months)) != len(months):
            raise ValueError(f"summer_season_months has duplicate month(s): {months}")
        return tuple(months)

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
    def campus(self) -> SiteFacility | None:
        """The primary facility **if it is a data-center campus**, else ``None`` (#1664).

        The narrower peer of :attr:`facility`, and the accessor the data-center models should
        read. Before the enclave seam the two were the same thing, so ``facility is not None``
        was a safe stand-in for "there is a campus to size". A ``federal_installation`` breaks
        that equivalence: WPAFB now HAS a facility, but sizing a genset fleet or an AERMOD
        dispatch deck against it would be fabricating a data center on an Air Force base.

        Everything that models a *campus* (air dispatch, the compute/power basis, the
        demand→price sensitivity, the basin activity summary) reads this; everything that asks
        "does this site have a documented facility at all" (readiness, the facility feed) keeps
        reading :attr:`facility`.
        """
        fac = self.facility
        return fac if fac is not None and fac.is_data_center else None

    @property
    def has_facility_power_basis(self) -> bool:
        """True when the primary facility has a **derivable** IT-load power basis (#1628): a
        facility exists AND its load is not entirely ``[open]``.

        The honest gate for the grid / compute / demand-pressure commands, which derive a campus
        power basis (:func:`watermark.facility.power.derive_power_basis` returns ``None`` in both the
        no-facility and the open-load cases). A rezoning-only campus (load all ``[open]``) is treated
        like no facility for that purpose — never a fabricated Lima-scale load — so those commands
        skip cleanly instead of crashing. A ``federal_installation`` never has one: its IT load is
        forbidden at the type level (#1664), so it falls out here without a special case.
        """
        fac = self.campus
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
