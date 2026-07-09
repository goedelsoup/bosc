"""The air-permit-derived facility power basis + its consistency with cooling.py."""

from __future__ import annotations

import pytest

from watermark.facility.power import derive_power_basis


def test_power_basis_traces_to_air_permit() -> None:
    b = derive_power_basis()
    assert b is not None
    assert b.it_load.value == pytest.approx(275.0)
    assert b.it_load.source == "document" and "P0138965" in (b.it_load.citation or "")
    # Backup power is the genset count x rating, derived (not asserted).
    assert b.backup_power.source == "derived"
    assert b.backup_power.value == pytest.approx(313.5, abs=0.1)  # 114 x 2.75
    # The N+1 range brackets the central figure — now a first-class range on it_load (#760).
    assert b.it_load.has_range
    assert b.it_load.low is not None and b.it_load.high is not None
    assert b.it_load.low < b.it_load.value < b.it_load.high


def test_facility_power_matches_cooling_it_load() -> None:
    """Guard against the duplicated air-permit constant silently diverging.

    The Lima ``SiteProfile.facility`` now carries the air-permit IT load; cooling.py still
    mirrors it as a private constant. This test is the seam that keeps them equal.
    """
    from watermark.hydrology import cooling
    from watermark.sites import SITES

    lima_facility = SITES["lima"].facility
    assert lima_facility is not None
    assert lima_facility.it_load_mw == cooling._IT_LOAD_MW
    basis = derive_power_basis()
    assert basis is not None
    assert basis.it_load.value == pytest.approx(cooling._IT_LOAD_MW)


def test_power_basis_is_none_without_a_facility() -> None:
    """A registered site with no documented facility has no power basis (no fabrication)."""
    from watermark.config import Settings

    assert derive_power_basis(settings=Settings(site="findlay")) is None


def test_site_plan_grounded_facility_has_no_genset_basis() -> None:
    """A site-plan-grounded facility (Urbana, #1327): the IT load is a floor-area SCREENING
    inference (``derived``), and there is NO fabricated genset fleet — backup / implied-PUE
    stay ``None`` — but the facility_draw (→ demand-pressure) is still derived."""
    from watermark.config import Settings

    b = derive_power_basis(settings=Settings(site="urbana"))
    assert b is not None
    # IT load is a screening inference, not a permit disclosure.
    assert b.it_load.source == "derived"
    assert "SCREENING" in (b.it_load.citation or "")
    assert b.it_load.has_range and b.it_load.low is not None and b.it_load.high is not None
    # No disclosed gensets → no backup / N+1 cross-check (never fabricated).
    assert b.genset_count is None
    assert b.genset_rating is None
    assert b.backup_power is None
    assert b.implied_pue_from_backup is None
    assert "no disclosed gensets" in b.method
    # The demand-pressure basis (facility_draw = IT x PUE) is still derived.
    assert b.facility_draw.source == "derived"
    assert b.facility_draw.value > b.it_load.value  # PUE > 1


def test_site_facility_requires_exactly_one_load_basis_citation() -> None:
    """SiteFacility forbids an uncited IT load AND an ambiguous double-cited one — the load
    is grounded by exactly one basis (air permit XOR non-permit derivation)."""
    from watermark.sites._model import SiteFacility

    # Neither citation → uncited load.
    with pytest.raises(ValueError, match="exactly one basis citation"):
        SiteFacility(it_load_mw=70.0, it_load_low_mw=35.0, it_load_high_mw=115.0)
    # Both citations → ambiguous ground (derive_power_basis would silently drop it_load_citation).
    with pytest.raises(ValueError, match="exactly one basis citation"):
        SiteFacility(
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            air_permit_citation="permit",
            it_load_citation="screening",
        )


def test_site_facility_disclosure_fields_require_a_citation() -> None:
    """A site-plan disclosure value (floor area / investment / type) can't pass uncited."""
    from watermark.sites._model import SiteFacility

    with pytest.raises(ValueError, match="disclosure_citation must be set together"):
        SiteFacility(
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="screening",
            gross_floor_area_sqft=460_000,  # disclosed value, no citation
        )


def test_site_facility_gensets_are_paired() -> None:
    """A genset count without a rating (or vice-versa) can't form a backup figure."""
    from watermark.sites._model import SiteFacility

    with pytest.raises(ValueError, match="genset_count and genset_mw must be set together"):
        SiteFacility(
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="screening",
            genset_count=34,  # rating omitted
        )


def test_compute_capacity_refuses_a_facility_less_site() -> None:
    """The compute-capacity estimate needs a facility power basis — it refuses for a
    facility-less site instead of reusing Lima's air-permit disclosure."""
    from watermark.config import Settings
    from watermark.facility.compute import derive_compute_capacity

    with pytest.raises(ValueError, match="no documented facility"):
        derive_compute_capacity(settings=Settings(site="findlay"))


def test_generation_cycle_efficiency_coefficient() -> None:
    """Issue #90: simple- vs combined-cycle net efficiency (the power-loss coefficient)."""
    b = derive_power_basis()
    simple = b.generation_config("simple")
    combined = b.generation_config("combined")
    assert simple is not None and combined is not None

    # The net-efficiency coefficient is a banded assumption, and the combined cycle
    # (heat-recovery) is materially more efficient than the simple cycle.
    for g in (simple, combined):
        assert g.net_efficiency.source == "assumption"
        assert 0.0 < g.net_efficiency.value < 1.0
    assert combined.net_efficiency.value > simple.net_efficiency.value

    # Heat rate is the derived inverse (fuel per MWh) — lower for the efficient cycle.
    assert simple.heat_rate_mmbtu_per_mwh.source == "derived"
    assert combined.heat_rate_mmbtu_per_mwh.value < simple.heat_rate_mmbtu_per_mwh.value
    assert simple.heat_rate_mmbtu_per_mwh.value == pytest.approx(
        3.412142 / simple.net_efficiency.value, abs=0.01
    )


def test_combined_cycle_steam_water_cross_refs_cooling() -> None:
    """Issue #90: the steam loop is an additional water pathway, cross-ref to cooling."""
    b = derive_power_basis()
    simple = b.generation_config("simple")
    combined = b.generation_config("combined")
    assert simple is not None and combined is not None

    # Only the combined cycle recovers exhaust heat and carries a steam-water pathway.
    assert simple.recovers_exhaust_heat is False
    assert simple.steam_cycle_water is None
    assert combined.recovers_exhaust_heat is True
    assert combined.steam_cycle_water is not None
    assert combined.steam_cycle_water.unit == "MGD"
    assert combined.steam_cycle_water.value > 0.0
    # The water implication is an assumption that cross-references the cooling subsystem.
    assert combined.steam_cycle_water.source == "assumption"
    assert "cooling" in (combined.steam_cycle_water.citation or "").lower()

    # The cycle is honestly framed as an open evidence question (disclosed = backup).
    assert "OPEN EVIDENCE QUESTION" in b.generation_note


def test_cooling_pue_overhead_and_facility_draw() -> None:
    """Issue #87: PUE is a banded assumption and facility_draw = IT load x PUE."""
    b = derive_power_basis()

    # PUE is a banded assumption (#760: low/high on a single value); the ceiling admits
    # cooling-dominated designs (~1.43), and the central value is the band mean.
    assert b.pue.source == "assumption" and b.pue.has_range
    assert b.pue.low is not None and b.pue.high is not None
    assert b.pue.low < b.pue.value < b.pue.high
    assert b.pue.high == pytest.approx(1.43, abs=0.01)
    assert b.pue.value == pytest.approx((b.pue.low + b.pue.high) / 2.0, abs=1e-3)
    # Cooling share at the high PUE is ~30% of facility power (the call's figure).
    assert b.cooling_share_high.value == pytest.approx((b.pue.high - 1.0) / b.pue.high, abs=1e-3)
    assert b.cooling_share_high.value == pytest.approx(0.30, abs=0.01)

    # The IT <-> total-facility-draw relationship: draw = IT central x PUE, banded (#760).
    assert b.facility_draw.source == "derived" and b.facility_draw.has_range
    assert b.facility_draw.low == pytest.approx(b.it_load.value * b.pue.low, abs=0.1)
    assert b.facility_draw.high == pytest.approx(b.it_load.value * b.pue.high, abs=0.1)
    assert b.facility_draw.low < b.facility_draw.value < b.facility_draw.high
    # Facility draw exceeds IT load by exactly the cooling/mechanical overhead.
    assert b.facility_draw.value > b.it_load.value
    assert b.cooling_overhead_mw == pytest.approx(b.facility_draw.value - b.it_load.value, abs=0.1)


def test_facility_draw_vs_backup_n_plus_one_crosscheck() -> None:
    """Issue #87/#33: the N+1 backup covers the facility draw only at the efficient PUE."""
    b = derive_power_basis()

    # The PUE implied if the genset backup is sized to the full IT + mechanical load.
    implied = b.implied_pue_from_backup
    assert implied.source == "derived"
    assert implied.value == pytest.approx(b.backup_power.value / b.it_load.value, abs=0.01)
    assert implied.value == pytest.approx(1.14, abs=0.02)

    # That implied PUE sits at the efficient end of the band: the backup envelope
    # covers the low-PUE draw but is exceeded by the cooling-dominated draw.
    assert b.facility_draw.low_or_value <= b.backup_power.value < b.facility_draw.high_or_value
    assert "#33" in b.cooling_overhead_note
