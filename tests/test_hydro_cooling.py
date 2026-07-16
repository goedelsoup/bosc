"""The cooling-model taxonomy (#1053-#1058): per-archetype specs, dispatch, regression lock.

The reference build's evaporative figures are golden-locked against the committed
``data/scenarios/buildout.scenario.yaml`` so the taxonomy can evolve without moving
Lima's published numbers (#1055).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology import scenario
from watermark.hydrology.cooling import derive_cooling_basis
from watermark.hydrology.cooling_models import (
    COOLING_MODELS,
    CoolingParams,
    resolve_cooling_model,
)
from watermark.hydrology.model import ScenarioResult
from watermark.hydrology.units import mgd_to_cfs
from watermark.sites import SITES, CoolingModelType, SiteFacility

# ---------------------------------------------------------------------------------------
# evaporative_tower — the pre-taxonomy math, regression-locked (#1053/#1055)
# ---------------------------------------------------------------------------------------


def test_basis_is_derived_from_cited_power() -> None:
    b = derive_cooling_basis()
    assert b.cooling_model == CoolingModelType.EVAPORATIVE_TOWER
    # IT load traces to the air permit genset count (document-sourced).
    assert b.it_load.value == pytest.approx(275.0)
    assert b.it_load.source == "document" and "P0138965" in (b.it_load.citation or "")
    # WUE and cycles are explicit assumptions, not silent constants.
    assert b.wue is not None and b.wue.source == "assumption"
    assert b.cycles_of_concentration is not None
    assert b.cycles_of_concentration.source == "assumption"


def test_basis_two_methods_bracket_demand() -> None:
    b = derive_cooling_basis()
    # Power x WUE central vs blowdown x cycles upper bound — both derived.
    assert b.consumptive_low.value == pytest.approx(3.14, abs=0.05)
    assert b.consumptive_high.value == pytest.approx(10.0, abs=0.1)
    assert b.consumptive_low.value < b.consumptive_high.value
    assert b.makeup_demand.source == "derived"
    # Evaporation/makeup fraction follows cycles of concentration: (CoC-1)/CoC.
    assert b.consumptive_fraction.value == pytest.approx(0.8)
    assert b.method_disclosed and not b.is_bracketed


def test_basis_scales_with_inputs() -> None:
    base = derive_cooling_basis()
    hotter = derive_cooling_basis(it_load_mw=350.0, wue_l_per_kwh=2.2)
    assert hotter.consumptive_low.value > base.consumptive_low.value


def test_lima_committed_buildout_figures_are_regression_locked(hydro_settings: Settings) -> None:
    """The dispatch refactor must not move the reference build's committed figures (#1055)."""
    committed = yaml.safe_load(
        (Path("data") / "scenarios" / "buildout.scenario.yaml").read_text(encoding="utf-8")
    )
    b = derive_cooling_basis(hydro_settings)
    assert committed["scenario"]["cooling_demand"]["value"] == b.makeup_demand.value
    assert committed["scenario"]["consumptive_fraction"]["value"] == b.consumptive_fraction.value
    assert committed["scenario"]["basis"]["consumptive_low"]["value"] == b.consumptive_low.value
    assert committed["scenario"]["basis"]["consumptive_high"]["value"] == b.consumptive_high.value
    assert committed["consumptive_loss"]["value"] == pytest.approx(
        mgd_to_cfs(b.makeup_demand.value * b.consumptive_fraction.value)
    )


# ---------------------------------------------------------------------------------------
# the other constant-draw archetypes (#1053)
# ---------------------------------------------------------------------------------------


def test_off_archetype_is_explicit_zero() -> None:
    b = derive_cooling_basis(cooling_model="off")
    assert b.cooling_model == CoolingModelType.OFF
    assert b.makeup_demand.value == 0.0
    assert b.consumptive_low.value == 0.0 and b.consumptive_high.value == 0.0
    assert b.consumptive_fraction.value == 0.0
    # Zero is a derived, cited statement — not an absence.
    assert b.makeup_demand.source == "derived"


def test_closed_loop_dry_is_near_zero_without_faked_params() -> None:
    b = derive_cooling_basis(cooling_model="closed_loop_dry")
    assert b.cooling_model == CoolingModelType.CLOSED_LOOP_DRY
    assert b.consumptive_low.value == 0.0 and b.consumptive_high.value == 0.0
    # WUE / cycles-of-concentration do not apply to a sealed dry loop: None, never faked.
    assert b.wue is None and b.cycles_of_concentration is None
    assert "energy penalty" in b.method


def test_once_through_low_consumptive_fraction() -> None:
    b = derive_cooling_basis(cooling_model="once_through")
    assert b.cooling_model == CoolingModelType.ONCE_THROUGH
    # Big pass-through withdrawal, small (~1-2%) forced-evaporation loss.
    assert b.consumptive_fraction.value == pytest.approx(0.015)
    assert 0 < b.consumptive_low.value < b.consumptive_high.value
    assert b.consumptive_high.value < 0.05 * b.makeup_demand.value
    assert b.wue is None and b.cycles_of_concentration is None


def test_once_through_withdrawal_reflects_total_rejected_heat() -> None:
    # Heat rejected at the condenser is IT + cooling-system work, so the withdrawal must be
    # driven by IT x the overhead multiplier (~1.15), not bare IT (#1153). A bare-IT basis
    # is understated ~13%.
    from watermark.hydrology.cooling_models import _OT_HEAT_REJECT_MULT

    base = derive_cooling_basis(cooling_model="once_through")
    unity = derive_cooling_basis(cooling_model="once_through", heat_reject_multiplier=1.0)
    assert base.makeup_demand.value == pytest.approx(
        unity.makeup_demand.value * _OT_HEAT_REJECT_MULT, rel=0.01
    )
    assert base.makeup_demand.value > unity.makeup_demand.value


def test_once_through_headline_is_central_not_range_low() -> None:
    # The once_through range is a *fraction* bracket (1% low, 2% high) around a *central*
    # fraction (1.5%). headline_consumptive() must return the central (makeup x 1.5%), not
    # consumptive_low (makeup x 1%), so balance/scenario agree (#1153).
    b = derive_cooling_basis(cooling_model="once_through")
    headline = b.headline_consumptive()
    assert headline is not None
    assert headline.value == pytest.approx(b.makeup_demand.value * b.consumptive_fraction.value)
    assert headline.value > b.consumptive_low.value  # central sits above the range low
    assert headline.value < b.consumptive_high.value
    # The intake does not grow with the consumptive fraction: the high-bound makeup is the
    # same withdrawal, so refill must not inflate it by dividing consumptive_high / fraction.
    makeup_high = b.headline_makeup_high()
    assert makeup_high is not None and makeup_high.value == pytest.approx(b.makeup_demand.value)


# ---------------------------------------------------------------------------------------
# unknown — bracketed range, honesty flags (#1057)
# ---------------------------------------------------------------------------------------


def test_unknown_yields_bracket_not_estimate() -> None:
    b = derive_cooling_basis(cooling_model="unknown")
    assert b.cooling_model == CoolingModelType.UNKNOWN
    assert b.is_bracketed and not b.method_disclosed
    assert b.consumptive_low.value < b.consumptive_high.value
    # Lower bound is the closed_loop_dry candidate; upper is the evaporative tower.
    assert b.consumptive_low.value == 0.0
    tower = derive_cooling_basis(cooling_model="evaporative_tower")
    assert b.consumptive_high.value == tower.consumptive_high.value
    # The envelope knobs are assumptions, never presented as sourced estimates.
    assert b.makeup_demand.source == "assumption"
    assert "undisclosed" in (b.makeup_demand.citation or "")


def test_bracketed_basis_has_no_headline_and_guards_data_tier(hydro_settings: Settings) -> None:
    # The `is_bracketed` honesty guard must live in the data tier, not only the
    # presentation tier: an undisclosed-method basis exposes no single headline, and the
    # data-tier consumers (supply budget, scenario knob) refuse to publish the envelope.
    from watermark.hydrology import supply as sup

    b = derive_cooling_basis(cooling_model="unknown")
    assert b.is_bracketed
    assert b.headline_consumptive() is None
    assert b.headline_makeup() is None
    # A disclosed archetype does expose a headline: the central consumptive, which is
    # makeup x fraction (== the power x WUE central for the tower), not consumptive_low
    # doubling as headline (#1153).
    tower = derive_cooling_basis(cooling_model="evaporative_tower")
    headline = tower.headline_consumptive()
    assert headline is not None
    assert headline.value == pytest.approx(
        tower.makeup_demand.value * tower.consumptive_fraction.value
    )
    assert tower.headline_makeup() is tower.makeup_demand

    system = sup.load_supply(settings=hydro_settings)
    assert system is not None
    with pytest.raises(ValueError, match="bracketed"):
        sup.campus_budget_from_cooling(system, basis=b)
    with pytest.raises(ValueError, match="bracketed"):
        scenario.buildout_scenario(basis=b)


def test_fort_wayne_is_unknown_and_leaks_no_lima_figure() -> None:
    # hydro_settings is lima-pinned, so the site override needs its own Settings;
    # hydro_offline keeps it hermetic like the fixture (tests/conftest.py).
    fw = Settings(data_dir=Path("data"), site="fort-wayne", hydro_offline=True)
    b = derive_cooling_basis(fw)
    assert b.cooling_model == CoolingModelType.UNKNOWN
    assert b.is_bracketed and not b.method_disclosed
    # Upper bound comes from Fort Wayne's own 90 MW power basis (no disclosed blowdown),
    # not Lima's FM-2 discharge.
    assert b.consumptive_high.value < 2.0


# ---------------------------------------------------------------------------------------
# resolution rules (#1054)
# ---------------------------------------------------------------------------------------


def _stub_facility(**overrides: object) -> SiteFacility:
    base: dict[str, object] = {
        "genset_count": 10,
        "genset_mw": 2.0,
        "it_load_mw": 20.0,
        "it_load_low_mw": 15.0,
        "it_load_high_mw": 25.0,
        "air_permit_citation": "stub permit",
    }
    base.update(overrides)
    return SiteFacility(**base)  # type: ignore[arg-type]


def test_no_facility_resolves_off() -> None:
    assert resolve_cooling_model(None) == CoolingModelType.OFF
    # xenia is deliberately facility-less (Findlay now carries a disclosed SiteFacility, #1459).
    xenia = Settings(data_dir=Path("data"), site="xenia", hydro_offline=True)
    assert derive_cooling_basis(xenia).cooling_model == CoolingModelType.OFF


def test_undisclosed_method_defaults_unknown_never_evaporative() -> None:
    # A facility that never set cooling_model carries `unknown` — the water-intensive
    # evaporative model must never be silently inherited (#1054).
    assert resolve_cooling_model(_stub_facility()) == CoolingModelType.UNKNOWN


def test_explicit_override_wins() -> None:
    fac = _stub_facility(cooling_model=CoolingModelType.EVAPORATIVE_TOWER)
    assert resolve_cooling_model(fac, override="closed_loop_dry") == (
        CoolingModelType.CLOSED_LOOP_DRY
    )


def test_lima_profile_is_explicit_evaporative() -> None:
    lima = SITES["lima"].facility
    assert lima is not None
    assert lima.cooling_model == CoolingModelType.EVAPORATIVE_TOWER
    assert lima.cooling_model_source == "assumption"  # asserted, not disclosed (CBI-withheld)
    fw = SITES["fort-wayne"].facility
    assert fw is not None and fw.cooling_model == CoolingModelType.UNKNOWN
    # Findlay's disclosed One Power / MARA facility (#1459) carries UNKNOWN cooling (MARA's Findlay
    # cooling design is not on the record — a bracketed range, never the evaporative default).
    fnd = SITES["findlay"].facility
    assert fnd is not None and fnd.cooling_model == CoolingModelType.UNKNOWN
    assert SITES["xenia"].facility is None  # a facility-less site ⇒ off


def test_registry_covers_every_enum_member() -> None:
    assert set(COOLING_MODELS) == set(CoolingModelType)


def test_explicit_model_without_facility_is_refused() -> None:
    # A facility-less site (xenia) must never derive a non-off basis from the Lima
    # module fallbacks — that would leak Lima's air-permit provenance into its figures.
    xenia = Settings(data_dir=Path("data"), site="xenia", hydro_offline=True)
    with pytest.raises(ValueError, match=r"requires a SiteProfile\.facility"):
        derive_cooling_basis(xenia, cooling_model="evaporative_tower")


def test_override_without_citation_is_rejected() -> None:
    # Provenance travels with the value: an uncited WUE/CoC override must not construct.
    with pytest.raises(ValueError, match="wue_citation"):
        _stub_facility(wue_l_per_kwh=2.0)
    with pytest.raises(ValueError, match="cycles_citation"):
        _stub_facility(cycles_of_concentration=4.0)


def test_cycles_at_or_below_one_is_rejected() -> None:
    # CoC is the makeup/blowdown ratio — always > 1. A `cycles <= 1` override makes the
    # evaporative fraction (CoC-1)/CoC zero or negative (and CoC=0 divides by zero), so the
    # basis is non-physical; reject it at the source for both tower and hybrid (#1170).
    for model in ("evaporative_tower", "hybrid_adiabatic"):
        with pytest.raises(ValueError, match="cycles of concentration must be > 1"):
            derive_cooling_basis(cooling_model=model, cycles=1.0)
        with pytest.raises(ValueError, match="cycles of concentration must be > 1"):
            derive_cooling_basis(cooling_model=model, cycles=0.0)


def test_consumptive_high_pairs_with_makeup_high_not_makeup_demand() -> None:
    # The trap #1170 guards: consumptive_high is the blowdown-method evaporation, whose
    # implied intake is the larger makeup_high — not makeup_demand (the power-method
    # central). Dividing consumptive_high by the matching intake stays a valid fraction.
    b = derive_cooling_basis(cooling_model="evaporative_tower")
    assert b.consumptive_high.value > b.makeup_demand.value  # non-physical if paired as a stream
    makeup_high = b.headline_makeup_high()
    assert makeup_high is not None and makeup_high.value > b.makeup_demand.value
    assert 0.0 < b.consumptive_high.value / makeup_high.value <= 1.0


def test_consumptive_range_label_collapses_point_estimates() -> None:
    from watermark.hydrology.cooling_models import consumptive_range_label

    dry = derive_cooling_basis(cooling_model="closed_loop_dry")
    assert consumptive_range_label(dry) == "0 MGD"
    tower = derive_cooling_basis(cooling_model="evaporative_tower")
    assert consumptive_range_label(tower) == "3.14-10 MGD"


# ---------------------------------------------------------------------------------------
# hybrid_adiabatic — seasonal integration (#1058)
# ---------------------------------------------------------------------------------------


def test_hybrid_basis_is_seasonal_and_between_dry_and_tower(hydro_settings: Settings) -> None:
    hybrid = derive_cooling_basis(hydro_settings, cooling_model="hybrid_adiabatic")
    tower = derive_cooling_basis(hydro_settings, cooling_model="evaporative_tower")
    assert hybrid.cooling_model == CoolingModelType.HYBRID_ADIABATIC
    assert hybrid.seasonal_months  # the assist window is recorded
    # Annual average sits strictly between closed_loop_dry (0) and the full-year tower.
    assert 0.0 < hybrid.consumptive_low.value < tower.consumptive_low.value
    # The warm-season rate is the tower-like power x WUE draw.
    assert hybrid.consumptive_high.value == tower.consumptive_low.value
    frac = len(hybrid.seasonal_months) / 12.0
    assert hybrid.consumptive_low.value == pytest.approx(
        hybrid.consumptive_high.value * frac, abs=0.01
    )


def test_hybrid_seasonal_screen_zeroes_winter(hydro_settings: Settings) -> None:
    basis = derive_cooling_basis(hydro_settings, cooling_model="hybrid_adiabatic")
    annual_cfs = mgd_to_cfs(basis.makeup_demand.value * basis.consumptive_fraction.value)
    sw = scenario.evaluate_seasonal(annual_cfs, settings=hydro_settings, basis=basis)
    assert sw is not None
    assert sw.cooling_model == CoolingModelType.HYBRID_ADIABATIC
    warm = [m for m in sw.months if m.growing_season]
    cold = [m for m in sw.months if not m.growing_season]
    assert warm and cold
    assert all(m.consumptive_cfs > 0 for m in warm)
    assert all(m.consumptive_cfs == 0.0 for m in cold)
    # The seasonal headline reflects the concentrated warm-season rate, not the smear;
    # the summer multiple reads that rate against the cited summer 30Q10.
    warm_rate_cfs = mgd_to_cfs(basis.consumptive_high.value)
    assert sw.consumptive_cfs == pytest.approx(warm_rate_cfs, abs=0.01)
    if sw.summer_multiple is not None and sw.summer_30q10_cfs:
        assert sw.summer_multiple == pytest.approx(warm_rate_cfs / sw.summer_30q10_cfs, abs=0.1)


def test_assist_window_matches_seasonal_growing_months(hydro_settings: Settings) -> None:
    # The assist window recorded on the basis (_assist_months) and the growing-season
    # months from scenario.evaluate_seasonal must agree — both round net (ET0 - precip)
    # to 3 dp before the > 0 test, so no boundary month is assist in one path but not the
    # other (#1170).
    basis = derive_cooling_basis(hydro_settings, cooling_model="hybrid_adiabatic")
    warm_cfs = mgd_to_cfs(basis.consumptive_high.value)
    sw = scenario.evaluate_seasonal(warm_cfs, settings=hydro_settings, basis=basis)
    assert sw is not None
    assert basis.seasonal_months == sw.growing_season_months


def test_constant_archetype_seasonal_screen_unchanged(hydro_settings: Settings) -> None:
    basis = derive_cooling_basis(hydro_settings)
    cfs = mgd_to_cfs(basis.makeup_demand.value * basis.consumptive_fraction.value)
    sw = scenario.evaluate_seasonal(cfs, settings=hydro_settings, basis=basis)
    assert sw is not None
    assert all(m.consumptive_cfs == pytest.approx(cfs, abs=0.001) for m in sw.months)


# ---------------------------------------------------------------------------------------
# scenario / pipeline threading (#1056)
# ---------------------------------------------------------------------------------------


def test_baseline_is_explicitly_off() -> None:
    s = scenario.baseline_scenario()
    assert s.cooling_model == CoolingModelType.OFF


def test_buildout_defaults_to_sourced_basis() -> None:
    s = scenario.buildout_scenario()
    # Default knobs come from the basis (derived), not a bare assumption.
    assert s.cooling_demand.source == "derived"
    assert s.consumptive_fraction.source == "derived"
    assert s.basis is not None and s.basis.it_load.source == "document"
    assert s.cooling_model == CoolingModelType.EVAPORATIVE_TOWER


def test_override_tags_as_assumption() -> None:
    s = scenario.buildout_scenario(cooling_demand_mgd=8.0, consumptive_fraction=0.75)
    assert s.cooling_demand.value == 8.0 and s.cooling_demand.source == "assumption"
    assert s.consumptive_fraction.value == 0.75 and s.consumptive_fraction.source == "assumption"


def test_scenario_cooling_model_override(hydro_settings: Settings) -> None:
    # --cooling-model closed_loop_dry on an evaporative_tower facility uses the
    # closed-loop basis, not the profile default.
    s = scenario.buildout_scenario(cooling_model="closed_loop_dry", settings=hydro_settings)
    assert s.cooling_model == CoolingModelType.CLOSED_LOOP_DRY
    assert s.basis is not None and s.basis.cooling_model == CoolingModelType.CLOSED_LOOP_DRY
    assert s.cooling_demand.value == 0.0


def test_run_scenarios_records_cooling_model(hydro_settings: Settings) -> None:
    from watermark.pipeline.hydrology import run_scenarios

    base, build, _delta = run_scenarios(settings=hydro_settings, live=False)
    assert base.cooling_model == CoolingModelType.OFF
    assert build.cooling_model == CoolingModelType.EVAPORATIVE_TOWER
    _dry_base, dry_build, dry_delta = run_scenarios(
        settings=hydro_settings, live=False, cooling_model="closed_loop_dry"
    )
    assert dry_build.cooling_model == CoolingModelType.CLOSED_LOOP_DRY
    assert dry_delta.consumptive_increase_cfs == 0.0


def test_persisted_yaml_roundtrips_cooling_model(hydro_settings: Settings, tmp_path: Path) -> None:
    result = scenario.evaluate(
        scenario.buildout_scenario(settings=hydro_settings), settings=hydro_settings, live=False
    )
    out_settings = Settings(data_dir=tmp_path, hydro_offline=True)
    path = scenario.write_scenario(result, settings=out_settings)
    parsed = ScenarioResult.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    assert parsed.cooling_model == CoolingModelType.EVAPORATIVE_TOWER
    assert parsed.scenario.cooling_model == CoolingModelType.EVAPORATIVE_TOWER
    assert parsed.scenario.basis is not None
    assert parsed.scenario.basis.cooling_model == CoolingModelType.EVAPORATIVE_TOWER


def test_sourced_buildout_still_dwarfs_7q10(hydro_settings: Settings) -> None:
    from watermark.pipeline.hydrology import run_scenarios

    _base, _build, delta = run_scenarios(settings=hydro_settings, live=True)
    # Even the conservative power-based central estimate is ~24x the Ottawa 7Q10.
    assert delta.multiple_of_7q10 is not None and delta.multiple_of_7q10 > 15


def test_params_dataclass_is_pure_overrides() -> None:
    # A CoolingParams with nothing set resolves everything from facility/spec defaults.
    p = CoolingParams()
    assert p.it_load_mw is None and p.blowdown_mgd is None
    assert p.wue_l_per_kwh is None and p.cycles_of_concentration is None
