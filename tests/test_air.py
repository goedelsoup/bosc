"""Air-quality Tier-0: emission factors (#1175), dispatch trigger (#1176), scenarios (#1177).

Hermetic — the grid interchange replays the committed offline fixture, no network. The
emission factors read the committed AP-42 reference dataset and the Lima permit extraction.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.air.dispatch import (
    DispatchAssumptions,
    derive_reliability_runtime,
    estimate_reliability_runtime,
)
from watermark.air.emissions import (
    load_emission_factors,
    load_nsr_caps,
    permit_factors,
    reconcile,
)
from watermark.air.model import CAPPED_POLLUTANTS, POLLUTANTS, GensetEmissionFactors
from watermark.air.scenario import (
    AirScenarioResult,
    baseline_scenario,
    cap_breach_runtime,
    diff,
    evaluate,
    reliability_dispatch_scenario,
    write_scenario,
)
from watermark.config import Settings
from watermark.grid.interchange import derive_interchange_comparison, fetch_ba_interchange

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def air_settings() -> Settings:
    """Lima, offline: grid fixture replays; AP-42 + permit read from committed data."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


# --- #1175: emission-factor model + AP-42/permit reconciliation ---------------------


def test_ap42_factors_cover_all_pollutants_and_are_reference(air_settings: Settings) -> None:
    ap = load_emission_factors(basis="ap42", settings=air_settings)
    assert ap is not None
    assert ap.basis == "ap42"
    assert set(ap.pollutants()) == set(POLLUTANTS)
    for pol in POLLUTANTS:
        ef = ap.factor(pol)
        assert ef is not None
        # AP-42 is a published prior, not a fact about this facility -> not "verified".
        assert ef.per_mwh.source == "reference"
        assert not ef.per_mwh.verified
        assert ef.per_engine_hour.value > 0


def test_permit_factors_are_document_and_partial(air_settings: Settings) -> None:
    pm = load_emission_factors(basis="permit", settings=air_settings)
    assert pm is not None
    assert pm.basis == "permit"
    # The permit isolates the capped NOx/CO plus Tier-2 PM; it does not isolate SO2/VOC.
    assert set(pm.pollutants()) == {"NOx", "CO", "PM10", "PM2.5"}
    nox = pm.factor("NOx")
    assert nox is not None
    assert nox.per_engine_hour.source == "document"
    assert nox.per_engine_hour.verified


def test_permit_load_regime_splits_rates(air_settings: Settings) -> None:
    engine_mw = load_emission_factors(basis="ap42", settings=air_settings)
    assert engine_mw is not None
    permit_path = air_settings.extracted_dir / "permits" / "4132514.epa.yaml"
    at_load = permit_factors(engine_mw.engine_mw, permit_path=permit_path, load_regime="load")
    at_idle = permit_factors(engine_mw.engine_mw, permit_path=permit_path, load_regime="idle")
    # >25%-load NOx (75.78) is far higher than the ≤25%-load rate (12.15).
    assert at_load.factor("NOx").per_engine_hour.value == 75.78  # type: ignore[union-attr]
    assert at_idle.factor("NOx").per_engine_hour.value == 12.15  # type: ignore[union-attr]
    assert at_load.factor("NOx").per_engine_hour.value > at_idle.factor("NOx").per_engine_hour.value  # type: ignore[union-attr]


def test_reconcile_ap42_overpredicts_capped_pollutants(air_settings: Settings) -> None:
    ap = load_emission_factors(basis="ap42", settings=air_settings)
    pm = load_emission_factors(basis="permit", settings=air_settings)
    assert ap is not None and pm is not None
    recs = {r.pollutant: r for r in reconcile(ap, pm)}
    # AP-42 uncontrolled runs hot vs the certified Tier-2 rate for the capped pollutants.
    for pol in CAPPED_POLLUTANTS:
        r = recs[pol]
        assert r.ratio_ap42_over_permit is not None
        assert r.ratio_ap42_over_permit > 1.0
    # SO2 / VOC are grounded only by AP-42 -> no ratio.
    assert recs["SO2"].ratio_ap42_over_permit is None
    assert recs["SO2"].permit_per_engine_hour_lb is None


def test_emission_factors_forbid_extra() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        GensetEmissionFactors.model_validate(
            {
                "basis": "ap42",
                "load_regime": "load",
                "engine_mw": {},
                "fuel": "d",
                "factors": {},
                "citation": "x",
                "bogus": 1,
            }
        )


def test_ap42_idle_regime_is_unsupported(air_settings: Settings) -> None:
    # AP-42 §3.4 has no low/idle-load factor — idle scenarios need the permit basis.
    with pytest.raises(ValueError, match="idle"):
        load_emission_factors(basis="ap42", load_regime="idle", settings=air_settings)


def test_non_reference_site_does_not_silently_load_lima_permit() -> None:
    # fort-wayne has a facility but no wired air permit; the shared extracted tree means
    # the Lima permit relpath would otherwise resolve. Permit-basis factors must fail
    # clearly, and its NSR caps must be empty — never Lima's 235.62 / 96.06.
    fw = Settings(
        site="fort-wayne",
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )
    with pytest.raises(NotImplementedError, match=r"air_permit_relpath|permit_path"):
        load_emission_factors(basis="permit", settings=fw)
    assert load_nsr_caps(settings=fw) == {}


# --- #1176: reliability dispatch-trigger model --------------------------------------


def test_dispatch_band_is_ordered_and_grid_derived(air_settings: Settings) -> None:
    est = derive_reliability_runtime(settings=air_settings)
    assert est is not None
    assert est.ba == "PJM"
    # Import-hours are derived from real EIA-930 data (net-import-hours fraction x 8760).
    assert est.import_hours_per_year.source == "derived"
    assert est.import_hours_per_year.value == pytest.approx(0.006 * 8760, abs=0.1)
    # Band ordered, and every point is an [inference] assumption.
    assert (
        est.runtime_hours_low.value
        <= est.runtime_hours_central.value
        <= est.runtime_hours_high.value
    )
    for pv in (est.runtime_hours_low, est.runtime_hours_central, est.runtime_hours_high):
        assert pv.source == "assumption"
    # C1/C2/#1638: PJM's window peak demand exceeds its mean in-BA net generation, so it is
    # import-dependent at peak. The old (circular) "comfortably covered → lower bound" caveat,
    # which rode the headroom ≡ net-interchange identity, no longer fires.
    assert est.import_dependent_at_peak is True
    assert est.peak_import_need_mw.value > 0
    assert not any("lower bound" in c for c in est.caveats)


def test_dispatch_assumptions_scale_runtime(air_settings: Settings) -> None:
    interchange = fetch_ba_interchange(settings=air_settings)
    comparison = derive_interchange_comparison(interchange=interchange, settings=air_settings)
    hi = DispatchAssumptions(
        escalation_fraction_low=0.1, escalation_fraction_central=0.5, escalation_fraction_high=1.0
    )
    est = estimate_reliability_runtime(comparison, interchange, assumptions=hi)
    raw_import_hours = 0.006 * 8760  # net-import fraction x hours/yr
    assert est.runtime_hours_high.value == pytest.approx(raw_import_hours * 1.0, abs=0.05)
    assert est.runtime_hours_central.value == pytest.approx(raw_import_hours * 0.5, abs=0.05)


# --- #1177: scenario runner + NSR cap-exceedance check ------------------------------


def test_baseline_is_compliant(air_settings: Settings) -> None:
    base = evaluate(baseline_scenario(), settings=air_settings)
    # Routine testing (idle load) must NOT breach — the permit demonstrably complies.
    assert base.any_cap_exceeded is False
    assert base.breached_pollutants == []
    nox = next(e for e in base.emissions if e.pollutant == "NOx")
    assert nox.cap_tpy == 235.62
    assert nox.pct_of_cap is not None and nox.pct_of_cap < 100


def test_cap_breach_runtime_thresholds(air_settings: Settings) -> None:
    nox_hr = cap_breach_runtime("NOx", settings=air_settings)
    co_hr = cap_breach_runtime("CO", settings=air_settings)
    assert nox_hr is not None and co_hr is not None
    # NOx is the binding cap — it breaches at fewer forced hours than CO.
    assert nox_hr < co_hr
    # A runtime just above the NOx threshold breaches; just below does not.
    over = evaluate(reliability_dispatch_scenario(nox_hr + 5, band="over"), settings=air_settings)
    under = evaluate(reliability_dispatch_scenario(nox_hr - 5, band="under"), settings=air_settings)
    assert "NOx" in over.breached_pollutants
    assert "NOx" not in under.breached_pollutants


def test_uncapped_pollutant_has_no_cap(air_settings: Settings) -> None:
    r = evaluate(reliability_dispatch_scenario(60.0), settings=air_settings)
    pm = next(e for e in r.emissions if e.pollutant == "PM10")
    assert pm.cap_tpy is None
    assert pm.exceeds_cap is False


def test_diff_reports_increase_and_new_breach(air_settings: Settings) -> None:
    base = evaluate(baseline_scenario(), settings=air_settings)
    nox_hr = cap_breach_runtime("NOx", settings=air_settings)
    assert nox_hr is not None
    disp = evaluate(
        reliability_dispatch_scenario(nox_hr + 10, band="sustained"), settings=air_settings
    )
    d = diff(base, disp)
    nox_delta = next(x for x in d.deltas if x.pollutant == "NOx")
    assert nox_delta.increase_tpy > 0
    assert nox_delta.scenario_tpy > nox_delta.baseline_tpy
    # Baseline is compliant; the dispatch newly breaches NOx.
    assert "NOx" in d.caps_newly_breached


def test_scenario_yaml_round_trips(air_settings: Settings, tmp_path: Path) -> None:
    r = evaluate(reliability_dispatch_scenario(60.0, band="roundtrip"), settings=air_settings)
    dumped = yaml.safe_dump(r.model_dump(mode="json"))
    reloaded = AirScenarioResult.model_validate(yaml.safe_load(dumped))
    assert reloaded == r


def test_write_scenario_is_slug_scoped(air_settings: Settings) -> None:
    r = evaluate(reliability_dispatch_scenario(42.0, band="writetest"), settings=air_settings)
    path = Path(write_scenario(r, settings=air_settings))
    try:
        assert path.name == "lima.air-reliability_dispatch_writetest.scenario.yaml"
        reloaded = AirScenarioResult.model_validate(yaml.safe_load(path.read_text()))
        assert reloaded.scenario.name == r.scenario.name
    finally:
        path.unlink(missing_ok=True)


def test_nsr_caps_from_permit(air_settings: Settings) -> None:
    caps = load_nsr_caps(settings=air_settings)
    assert caps["NOx"].value == 235.62
    assert caps["CO"].value == 96.06
    assert caps["NOx"].source == "document"
