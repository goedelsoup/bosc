"""The air-permit-derived facility power basis + its consistency with cooling.py."""

from __future__ import annotations

import pytest

from bosc.facility.power import _IT_LOAD_MW, derive_power_basis


def test_power_basis_traces_to_air_permit() -> None:
    b = derive_power_basis()
    assert b.it_load.value == pytest.approx(275.0)
    assert b.it_load.source == "document" and "P0138965" in (b.it_load.citation or "")
    # Backup power is the genset count x rating, derived (not asserted).
    assert b.backup_power.source == "derived"
    assert b.backup_power.value == pytest.approx(313.5, abs=0.1)  # 114 x 2.75
    # The N+1 range brackets the central figure.
    assert b.it_load_low.value < b.it_load.value < b.it_load_high.value


def test_facility_power_matches_cooling_it_load() -> None:
    """Guard against the duplicated air-permit constant silently diverging.

    bosc.facility.power deliberately re-states cooling.py's private IT-load constant
    rather than importing the private name; this test is the seam that keeps them
    equal until the FUTURE DEDUP noted in power.py lands.
    """
    from bosc.hydrology import cooling

    assert _IT_LOAD_MW == cooling._IT_LOAD_MW
    assert derive_power_basis().it_load.value == pytest.approx(cooling._IT_LOAD_MW)


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
