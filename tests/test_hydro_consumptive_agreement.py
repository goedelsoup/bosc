"""Cross-path agreement for the campus consumptive cooling loss (#1162).

Three independent code paths derive the campus's central consumptive (net-basin)
cooling loss from the same sourced :class:`CoolingBasis`:

* ``balance._campus_node`` — carries ``basis.headline_consumptive()`` onto the water
  balance's campus node as ``consumptive_use`` (cfs).
* ``scenario.evaluate`` — for the default buildout scenario, ``cooling_demand *
  consumptive_fraction`` → ``consumptive_loss`` (cfs).
* ``supply.campus_budget_from_cooling`` — ``makeup_demand * consumptive_fraction`` →
  ``campus_consumptive`` (MGD).

They agree by construction: for a disclosed wet archetype ``headline_consumptive()``
*is* ``consumptive_low`` *is* ``makeup_demand * consumptive_fraction`` (see
``CoolingBasis.headline_consumptive``). Nothing enforced that they *stay* agreed —
a review found they could silently drift. This locks the invariant so a divergence
(e.g. one path picking up the ~3x blowdown upper bound) fails CI.
"""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import scenario
from watermark.hydrology import supply as sup
from watermark.hydrology.balance import build_water_balance
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.units import mgd_to_cfs


def test_campus_consumptive_agrees_across_balance_scenario_supply(
    hydro_settings: Settings,
) -> None:
    basis = derive_cooling_basis(hydro_settings)
    assert not basis.is_bracketed, "Lima's evaporative_tower basis is disclosed, not a bracket"

    # Path 1 — the water balance's campus node (cfs).
    balance = build_water_balance(settings=hydro_settings, live=False)
    campus = balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is not None
    balance_cfs = campus.consumptive_use.value

    # Path 2 — the default buildout scenario (cfs). No knob overrides => sourced basis.
    result = scenario.evaluate(
        scenario.buildout_scenario(settings=hydro_settings), settings=hydro_settings, live=False
    )
    scenario_cfs = result.consumptive_loss.value

    # Path 3 — the supply water budget (MGD -> cfs for comparison).
    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    budget = sup.campus_budget_from_cooling(system, basis=basis)
    supply_cfs = mgd_to_cfs(budget.campus_consumptive.value)

    # All three are the same central consumptive (tolerance covers per-path MGD/cfs
    # rounding; a real divergence — wrong method, wrong fraction — is far larger).
    assert scenario_cfs == pytest.approx(balance_cfs, abs=0.05)
    assert supply_cfs == pytest.approx(balance_cfs, abs=0.05)
    # Anchored to the documented power x WUE central estimate (~4.86 cfs).
    assert balance_cfs == pytest.approx(4.86, abs=0.1)


def test_bracketed_basis_documents_why_the_paths_differ(hydro_settings: Settings) -> None:
    # The one sanctioned way the three paths *don't* produce a single agreed scalar: an
    # undisclosed cooling method is a bracket, never a headline (CLAUDE.md honesty guard).
    # Then balance carries no scalar, and scenario/supply refuse rather than publish the
    # envelope — divergence by design, asserted here so it stays deliberate.
    unknown = derive_cooling_basis(hydro_settings, cooling_model="unknown")
    assert unknown.is_bracketed and not unknown.method_disclosed
    assert unknown.headline_consumptive() is None and unknown.headline_makeup() is None

    with pytest.raises(ValueError, match="bracketed"):
        scenario.buildout_scenario(basis=unknown, settings=hydro_settings)

    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    with pytest.raises(ValueError):
        sup.campus_budget_from_cooling(system, basis=unknown)
