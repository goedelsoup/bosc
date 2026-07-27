"""The air-permit-derived facility power basis + its consistency with cooling.py."""

from __future__ import annotations

import pytest

from watermark.facility.power import derive_power_basis


def test_power_basis_traces_to_air_permit() -> None:
    b = derive_power_basis()
    assert b is not None
    assert b.it_load.value == pytest.approx(275.0)
    # IT load is an [inference]: derived (N+1) from the disclosed backup, not permit-disclosed
    # (#1697) — it carries the air-permit citation as the derivation basis.
    assert b.it_load.source == "derived" and "P0138965" in (b.it_load.citation or "")
    # Backup power is the genset count x rating, derived (not asserted).
    assert b.backup_power.source == "derived"
    assert b.backup_power.value == pytest.approx(313.5, abs=0.1)  # 114 x 2.75
    # The N+1 range brackets the central figure — now a first-class range on it_load (#760).
    assert b.it_load.has_range
    assert b.it_load.low is not None and b.it_load.high is not None
    assert b.it_load.low < b.it_load.value < b.it_load.high


def test_power_and_cooling_read_one_source_for_the_it_load() -> None:
    """The power and cooling stacks read the SAME per-site figure — there is no second copy.

    The air-permit constants used to be duplicated into ``hydrology.cooling_models`` and guarded
    only by a drift test (#1634). They are gone: ``SiteProfile.facility`` is the single source,
    so the two subsystems agree by construction rather than by assertion.
    """
    from watermark.hydrology import cooling, cooling_models
    from watermark.sites import SITES

    lima_facility = SITES["lima"].facility
    assert lima_facility is not None
    basis = derive_power_basis()
    assert basis is not None
    assert basis.it_load.value == pytest.approx(lima_facility.it_load_mw)
    assert cooling.derive_cooling_basis().it_load.value == pytest.approx(lima_facility.it_load_mw)
    # No site-specific figure may reappear as a module constant in the cooling engine: the
    # archetype defaults it does carry (WUE / CoC) are generic reference values, not disclosures.
    for gone in ("_IT_LOAD_MW", "_GENSET_COUNT", "_GENSET_MW", "_BACKUP_MW", "_AIR_PERMIT_CITE"):
        assert not hasattr(cooling_models, gone), f"{gone} re-introduced a per-site constant"


def test_power_basis_is_none_without_a_facility() -> None:
    """A registered site with no documented facility has no power basis (no fabrication)."""
    from watermark.config import Settings

    # xenia is deliberately facility-less (Findlay now carries a disclosed SiteFacility, #1459).
    assert derive_power_basis(settings=Settings(site="xenia")) is None


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
        SiteFacility(
            name="Test",
            status="confirmed",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
        )
    # Both citations → ambiguous ground (derive_power_basis would silently drop it_load_citation).
    with pytest.raises(ValueError, match="exactly one basis citation"):
        SiteFacility(
            name="Test",
            status="confirmed",
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
            name="Test",
            status="confirmed",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="screening",
            it_load_source="screening",
            gross_floor_area_sqft=460_000,  # disclosed value, no citation
        )


def test_site_facility_gensets_are_paired() -> None:
    """A genset count without a rating (or vice-versa) can't form a backup figure."""
    from watermark.sites._model import SiteFacility

    with pytest.raises(ValueError, match="genset_count and genset_mw must be set together"):
        SiteFacility(
            name="Test",
            status="confirmed",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="screening",
            it_load_source="screening",
            genset_count=34,  # rating omitted
        )


def test_site_facility_blowdown_requires_a_citation() -> None:
    """A disclosed blowdown can't pass uncited: the cooling derivation would attach the
    sensitivity-override citation to it, labelling a real discharge as a sweep input."""
    from watermark.sites._model import SiteFacility

    with pytest.raises(ValueError, match="blowdown_mgd and blowdown_citation must be set together"):
        SiteFacility(
            name="Test",
            status="confirmed",
            it_load_mw=70.0,
            it_load_low_mw=35.0,
            it_load_high_mw=115.0,
            it_load_citation="screening",
            it_load_source="screening",
            blowdown_mgd=2.5,  # disclosed discharge, no citation
        )


def test_site_facility_refuses_the_default_cooling_citation_on_a_pinned_archetype() -> None:
    """The default cooling citation asserts the record discloses NO method (#1634) — a facility
    that pins an archetype, or claims a document/connector/reference source, must cite it."""
    from watermark.sites import CoolingModelType
    from watermark.sites._model import UNDISCLOSED_COOLING_CITATION, SiteFacility

    base = {
        "name": "Test",
        "status": "confirmed",
        "it_load_mw": 70.0,
        "it_load_low_mw": 35.0,
        "it_load_high_mw": 115.0,
        "it_load_citation": "screening",
        "it_load_source": "screening",
    }
    # A pinned archetype under "not disclosed in the record" is a self-contradiction.
    with pytest.raises(ValueError, match="still the default"):
        SiteFacility(**base, cooling_model=CoolingModelType.CLOSED_LOOP_DRY)
    # So is a claimed [reference] source that names no record.
    with pytest.raises(ValueError, match="still the default"):
        SiteFacility(**base, cooling_model_source="reference")
    # The honest case — undisclosed method, assumption source — still carries the default.
    fac = SiteFacility(**base)
    assert fac.cooling_model is CoolingModelType.UNKNOWN
    assert fac.cooling_model_citation == UNDISCLOSED_COOLING_CITATION


def test_compute_capacity_refuses_a_facility_less_site() -> None:
    """The compute-capacity estimate needs a facility power basis — it refuses for a
    facility-less site instead of reusing Lima's air-permit disclosure."""
    from watermark.config import Settings
    from watermark.facility.compute import derive_compute_capacity

    # xenia is deliberately facility-less (Findlay now carries a disclosed SiteFacility, #1459).
    with pytest.raises(ValueError, match="no derivable facility power basis"):
        derive_compute_capacity(settings=Settings(site="xenia"))


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

    # The IT <-> total-facility-draw relationship: central draw = IT central x PUE central,
    # and the band combines BOTH uncertainties — the IT-load band x the PUE band (#1641 D3),
    # not the central IT alone x the PUE band (which discarded the IT band and narrowed it).
    assert b.facility_draw.source == "derived" and b.facility_draw.has_range
    assert b.it_load.low is not None and b.it_load.high is not None
    assert b.facility_draw.low == pytest.approx(b.it_load.low * b.pue.low, abs=0.1)
    assert b.facility_draw.high == pytest.approx(b.it_load.high * b.pue.high, abs=0.1)
    assert b.facility_draw.value == pytest.approx(b.it_load.value * b.pue.value, abs=0.1)
    assert b.facility_draw.low < b.facility_draw.value < b.facility_draw.high
    # The combined band is strictly wider than the PUE-only band it replaced (the D3 fix).
    assert b.facility_draw.low < b.it_load.value * b.pue.low
    assert b.facility_draw.high > b.it_load.value * b.pue.high
    # Facility draw exceeds IT load by exactly the cooling/mechanical overhead.
    assert b.facility_draw.value > b.it_load.value
    assert b.cooling_overhead_mw == pytest.approx(b.facility_draw.value - b.it_load.value, abs=0.1)


def test_pue_is_cooling_model_aware() -> None:
    """Issue #1641 D5: the PUE band is resolved per cooling archetype, not a single band."""
    from watermark.config import Settings
    from watermark.facility.power import _load_pue_band
    from watermark.hydrology.cooling_models import _OT_HEAT_REJECT_MULT
    from watermark.sites import CoolingModelType

    s = Settings(site="lima")
    evap = _load_pue_band(s, CoolingModelType.EVAPORATIVE_TOWER)
    dry = _load_pue_band(s, CoolingModelType.CLOSED_LOOP_DRY)
    once = _load_pue_band(s, CoolingModelType.ONCE_THROUGH)

    # Dry/air cooling's fan penalty raises PUE above the evaporative band.
    assert (dry[0] + dry[1]) / 2.0 > (evap[0] + evap[1]) / 2.0
    # Once-through PUE is low and RECONCILES with the heat-rejection multiplier: its central
    # equals ~1.15 (the two representations of the same cooling overhead no longer disagree).
    assert (once[0] + once[1]) / 2.0 == pytest.approx(_OT_HEAT_REJECT_MULT)
    # The evaporative band is unchanged (Lima's committed figures don't move).
    assert evap == pytest.approx((1.1, 1.43))
    # An unknown archetype (no matching key would fall back) still resolves a band.
    unknown = _load_pue_band(s, CoolingModelType.UNKNOWN)
    assert unknown[0] < unknown[1]


def test_dry_site_pue_exceeds_evaporative_site() -> None:
    """A closed-loop-dry campus (Urbana) carries a higher PUE than evaporative Lima (#1641 D5)."""
    from watermark.config import Settings

    lima = derive_power_basis(settings=Settings(site="lima"))
    urbana = derive_power_basis(settings=Settings(site="urbana"))
    assert lima is not None and urbana is not None
    assert urbana.pue.value > lima.pue.value


def test_steam_water_sized_to_facility_draw_not_it_load() -> None:
    """Issue #1641 D5: combined-cycle steam condenser water scales with GENERATION (the
    facility draw the plant must supply), not the IT load alone (understated by the PUE factor)."""
    b = derive_power_basis()
    assert b is not None
    combined = b.generation_config("combined")
    assert combined is not None and combined.steam_cycle_water is not None
    # gal/kWh -> MGD: MW x 1000 kW/MW x 24 h x 0.2 gal/kWh / 1e6.
    expected_from_draw = round(b.facility_draw.value * 1_000.0 * 24.0 * 0.2 / 1_000_000.0, 2)
    expected_from_it = round(b.it_load.value * 1_000.0 * 24.0 * 0.2 / 1_000_000.0, 2)
    assert combined.steam_cycle_water.value == pytest.approx(expected_from_draw, abs=0.01)
    assert combined.steam_cycle_water.value > expected_from_it  # draw > IT (PUE > 1)


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
