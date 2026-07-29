"""The federal-enclave seam — model, registers, assembly, readiness (#1664, epic #1659 ME-E).

The properties under test are the ones that make an enclave *honest* rather than merely present:
the data-center math cannot reach it, its documented figures are projected from its record instead
of re-keyed, its land comes from a register no county parcel layer could supply, and its toxics row
is reconciled against the county scope that structurally misses it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from watermark.config import Settings
from watermark.connectors.federal import (
    fetch_discharges,
    fetch_installation_boundary,
    fetch_water_systems,
    geodesic_acres,
)
from watermark.enclave import build_enclave, installation_of, read_record_facts
from watermark.hydrology import cooling_models
from watermark.site import readiness as readiness_mod
from watermark.sites import (
    SITES,
    CoolingModelType,
    FacilityKind,
    FacilityLifecycle,
    FederalInstallation,
    SiteFacility,
    get_profile,
)

if TYPE_CHECKING:
    from pathlib import Path

WPAFB = "wpafb"


def _installation(**overrides: object) -> FederalInstallation:
    base: dict[str, object] = {
        "component": "U.S. Air Force",
        "agency": "U.S. Department of Defense",
        "record_relpath": "wpafb/cercla-ffa-1991.epa.yaml",
        "record_citation": "CERCLA §120 FFA [verified]",
    }
    base.update(overrides)
    return FederalInstallation(**base)  # type: ignore[arg-type]


def _enclave_facility(**overrides: object) -> SiteFacility:
    base: dict[str, object] = {
        "name": "Test Installation",
        "status": FacilityLifecycle.LIVE,
        "kind": FacilityKind.FEDERAL_INSTALLATION,
        "installation": _installation(),
        "cooling_model": CoolingModelType.OFF,
        "cooling_model_citation": "not a data-center facility",
    }
    base.update(overrides)
    return SiteFacility(**base)  # type: ignore[arg-type]


# --- The model refuses to model a base as a campus -----------------------------------------


def test_federal_installation_forbids_the_data_center_dimensions() -> None:
    """An IT load on an installation is the fabrication the kind exists to prevent."""
    with pytest.raises(ValidationError, match="no data-center dimensions"):
        _enclave_facility(it_load_mw=250.0, it_load_low_mw=250.0, it_load_high_mw=300.0)
    with pytest.raises(ValidationError, match="no data-center dimensions"):
        _enclave_facility(genset_count=12, genset_mw=3.0)


def test_federal_installation_must_pin_cooling_off() -> None:
    """`unknown` would publish a bracketed cooling-water range over an absence."""
    with pytest.raises(ValidationError, match="must pin cooling_model=off"):
        _enclave_facility(cooling_model=CoolingModelType.UNKNOWN, cooling_model_citation="x")


def test_kind_and_installation_must_agree() -> None:
    with pytest.raises(ValidationError, match="disagree"):
        SiteFacility(
            name="Campus",
            status=FacilityLifecycle.CONFIRMED,
            kind=FacilityKind.FEDERAL_INSTALLATION,
        )
    with pytest.raises(ValidationError, match="disagree"):
        SiteFacility(
            name="Campus",
            status=FacilityLifecycle.CONFIRMED,
            installation=_installation(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("pwsids", ("OH1234567",)), ("npdes_permits", ("OH0000001",))],
)
def test_enclave_id_lists_pair_with_their_citation(field: str, value: tuple[str, ...]) -> None:
    """An empty list is [open]; a populated one must say where it came from."""
    with pytest.raises(ValidationError, match="must be set together"):
        _installation(**{field: value})


def test_tri_identity_is_all_or_nothing() -> None:
    """A facility id without its county cannot be reduced; a county without the id screens wrong."""
    with pytest.raises(ValidationError, match="enclave TRI identity"):
        _installation(tri_facility_id="45433SDDSFDEPAR")


def test_registry_id_needs_the_tri_identity_it_belongs_to() -> None:
    with pytest.raises(ValidationError, match="epa_registry_id"):
        _installation(epa_registry_id="110001987958")


# --- The campus accessor keeps the DC math off an installation ------------------------------


def test_campus_is_none_for_an_enclave_but_facility_is_not() -> None:
    """The two accessors must diverge — that divergence is what protects the campus models."""
    profile = get_profile(WPAFB)
    assert profile.facility is not None
    assert profile.facility.kind is FacilityKind.FEDERAL_INSTALLATION
    assert profile.campus is None
    assert profile.has_facility_power_basis is False


def test_cooling_resolves_off_and_rejects_no_heat_for_an_enclave() -> None:
    fac = get_profile(WPAFB).facility
    assert fac is not None
    assert cooling_models.resolve_cooling_model(fac) is CoolingModelType.OFF
    # No resolvable IT load ⇒ no heat-rejection load, so the thermal screen skips rather than
    # inventing a discharge for an Air Force base.
    assert cooling_models.reject_heat_load(fac) is None


def test_every_other_registered_site_is_a_data_center_kind() -> None:
    """The kind is additive: WPAFB is the only non-campus facility in the registry today."""
    enclaves = {
        slug
        for slug, p in SITES.items()
        if p.facility is not None and not p.facility.is_data_center
    }
    assert enclaves == {WPAFB}


# --- Readiness: an installation is graded on its own instrument -----------------------------


def test_enclave_facility_is_instrument_grounded_by_its_record() -> None:
    fac = get_profile(WPAFB).facility
    assert fac is not None
    assert fac.is_instrument_grounded is True


def test_a_reference_grounded_enclave_only_seeds() -> None:
    """The grade is the record's provenance class — a press description does not lift the domain."""
    fac = _enclave_facility(installation=_installation(record_source="reference"))
    assert fac.is_instrument_grounded is False


def test_places_activates_on_enclave_geometry() -> None:
    """A base can never produce a county parcel, so `geo/campus` alone locked it out forever."""
    profile = get_profile(WPAFB)
    states = readiness_mod.domain_states(profile, {"geo/enclave": 1})
    assert states["places"] == "live"
    assert readiness_mod.PLACES_ENCLAVE_FEED in readiness_mod.READINESS_FEED_NAMES


def test_places_stays_absent_without_any_geometry() -> None:
    states = readiness_mod.domain_states(get_profile(WPAFB), {})
    assert states["places"] == "absent"


# --- The registers (offline, committed fixtures) --------------------------------------------


def test_mirta_boundary_replays_from_the_committed_fixture(federal_settings: Settings) -> None:
    profile = get_profile(WPAFB)
    inst = installation_of(profile)
    assert inst is not None and inst.register_name is not None
    boundary = fetch_installation_boundary(
        inst.register_name, utm_epsg=profile.hydro_utm_epsg, settings=federal_settings
    )
    assert boundary is not None
    assert boundary.component == "USAF"
    assert boundary.status_label == "Active"
    assert boundary.geometry["type"] == "MultiPolygon"
    assert boundary.parts == len(boundary.geometry["coordinates"])
    # Measured, not transcribed — and reproducible from the geometry that ships with it.
    assert boundary.acres == geodesic_acres(boundary.geometry, utm_epsg=profile.hydro_utm_epsg)


def test_water_systems_are_the_bases_own(federal_settings: Settings) -> None:
    inst = installation_of(get_profile(WPAFB))
    assert inst is not None
    systems = fetch_water_systems(inst.pwsids, settings=federal_settings)
    assert {s.pwsid for s in systems} == set(inst.pwsids)
    # Community water systems on ground water — the buried-valley aquifer of the FFA, not a
    # municipal purchase.
    assert all(s.system_type == "CWS" and s.source_type == "GW" for s in systems)


def test_discharges_report_from_the_enclaves_own_county(federal_settings: Settings) -> None:
    inst = installation_of(get_profile(WPAFB))
    assert inst is not None
    discharges = fetch_discharges(inst.npdes_permits, settings=federal_settings)
    assert {d.npdes_id for d in discharges} == set(inst.npdes_permits)
    assert all(d.federal_agency == "Defense: Air Force" for d in discharges)
    # The permits are addressed in Greene, the site's economic unit is Montgomery — the
    # disagreement the enclave model exists to surface.
    assert {d.county_fips for d in discharges} == {inst.tri_county_fips}
    assert inst.tri_county_fips != get_profile(WPAFB).rsei_fips


# --- The assembly: projection, not re-keying ------------------------------------------------


def test_documented_facts_are_projected_from_the_record(federal_settings: Settings) -> None:
    """The record is the source; the profile carries identifiers, never the record's numbers."""
    inst = installation_of(get_profile(WPAFB))
    assert inst is not None
    facts = read_record_facts(inst, settings=federal_settings)
    assert facts.supply_wells == 17
    assert facts.well_fields == 3
    assert facts.waste_disposal_sites == 58  # "~58" in the record — the approx marker coerces
    assert facts.base_area_acres == 8200  # "~8200"
    assert facts.npl_listing_date == "1989-10-04"
    # None of those numbers appear on the profile literal — that is the anti-drift property.
    dumped = inst.model_dump()
    assert 17 not in dumped.values()
    assert "supply_wells" not in dumped


def test_read_record_facts_refuses_a_missing_record(federal_settings: Settings) -> None:
    """A silent empty projection would quietly downgrade a [verified] enclave to a name."""
    with pytest.raises(FileNotFoundError, match="record_relpath"):
        read_record_facts(
            _installation(record_relpath="nope/missing.yaml"), settings=federal_settings
        )


def test_build_enclave_assembles_land_water_wastewater_power_toxics(
    federal_settings: Settings,
) -> None:
    enclave = build_enclave(federal_settings)
    assert enclave is not None
    assert enclave.name == "Wright-Patterson Air Force Base"

    assert enclave.land is not None
    assert enclave.land.record_acres == 8200
    # The register draws materially LESS land than the record describes, so the boundary must
    # ship as a partial footprint with the caveat attached — never silently as "the base".
    assert enclave.land.acreage_delta_pct is not None
    assert enclave.land.acreage_delta_pct < -5
    assert enclave.land.acreage_note is not None
    assert "COVERAGE CAVEAT" in enclave.land.acreage_note

    assert len(enclave.water.systems) == 2
    assert enclave.water.population_served == sum(
        s.population_served or 0 for s in enclave.water.systems
    )
    assert enclave.water.supply_wells == 17
    # A supply system is not a meter: the withdrawal stays [open].
    assert enclave.water.withdrawal_mgd is None

    assert len(enclave.wastewater.discharges) == 2
    assert enclave.wastewater.reported_average_flow_mgd is not None

    # The load is [open] and there is no citation pretending otherwise.
    assert enclave.power.load_mw is None
    assert enclave.power.load_citation is None

    assert enclave.toxics.scope_disagreement is True
    assert enclave.toxics.npl_site_id == "0504939"
    assert enclave.toxics.waste_disposal_sites == 58
    assert "trichloroethylene (TCE)" in enclave.toxics.contaminants


def test_scope_note_names_both_counties(federal_settings: Settings) -> None:
    """The severance must be stated in the artifact, not left to a reader to infer."""
    enclave = build_enclave(federal_settings)
    assert enclave is not None
    note = enclave.toxics.scope_note
    assert enclave.toxics.tri_county_fips in note
    assert enclave.toxics.site_rsei_fips in note
    assert "out of scope by construction" in note
    # And RSEI's own blind spot is stated where the row is published.
    assert "CERCLA mass" in enclave.toxics.cercla_gap_note


def test_partial_water_totals_are_open_not_understated() -> None:
    """A total is all-or-nothing: a partial sum would publish an understatement as a total.

    Summing 0 would assert nobody is served; summing only the reporting systems would assert a
    total that is short by exactly the part nobody can see. Both are wrong in the same direction,
    so an incomplete roster leaves the total `[open]` and the per-system rows carry the detail.
    """
    from watermark.enclave import _sum_opt

    assert _sum_opt([None, None]) is None
    assert _sum_opt([None, 5]) is None
    assert _sum_opt([]) is None
    assert _sum_opt([5, 7]) == 12


def test_build_enclave_is_none_for_a_site_without_one(tmp_path: Path) -> None:
    settings = Settings(site="lima", data_dir=tmp_path)
    assert build_enclave(settings) is None


# --- The committed artifacts stay in step with the code -------------------------------------


def test_committed_enclave_rsei_is_the_bases_own_row() -> None:
    """The reduction is one facility, in the enclave's county, and RSEI knows the id."""
    from watermark.enclave import load_enclave_rsei

    inv = load_enclave_rsei(Settings(site=WPAFB))
    assert inv is not None
    inst = installation_of(get_profile(WPAFB))
    assert inst is not None
    assert inv.county_fips == inst.tri_county_fips
    assert [f.facility_id for f in inv.facilities] == [inst.tri_facility_id]
    assert inv.facilities[0].federal_facility is True
    assert inv.meta["facility_ids_not_found"] == []


def test_committed_enclave_profile_matches_a_fresh_assembly(federal_settings: Settings) -> None:
    """The committed artifact is a build output — it must not drift from what the code produces."""
    from watermark.enclave import load_enclave

    committed = load_enclave(Settings(site=WPAFB))
    assert committed is not None
    fresh = build_enclave(federal_settings, rsei_row=committed.toxics.rsei)
    assert fresh is not None
    assert fresh.model_dump(mode="json") == committed.model_dump(mode="json")
