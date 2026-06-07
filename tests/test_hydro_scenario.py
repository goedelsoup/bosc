"""Baseline vs buildout scenario, persistence, and the dossier report (hermetic)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from bosc.config import Settings
from bosc.hydrology import report, scenario
from bosc.hydrology.lowflow import low_flow_for
from bosc.pipeline.hydrology import run_scenarios


def test_ottawa_7q10_now_cited(hydro_settings: Settings) -> None:
    pv = low_flow_for("Ottawa River at River Mile 32.5", settings=hydro_settings)
    assert pv is not None and pv.value == pytest.approx(0.2)
    assert pv.source == "document" and "2IG00001" in (pv.citation or "")


def test_consumptive_loss_from_knobs(hydro_settings: Settings) -> None:
    result = scenario.evaluate(
        scenario.buildout_scenario(cooling_demand_mgd=5.0, consumptive_fraction=0.8),
        settings=hydro_settings,
        live=True,
    )
    # 5 MGD * 0.8 = 4 MGD evaporated = 6.188 cfs net basin loss.
    assert result.consumptive_loss.value == pytest.approx(6.188, abs=0.01)
    assert result.consumptive_loss.source == "derived"
    # The campus node's consumptive seam is now filled (no longer the inert zero).
    campus = result.balance.node("bosc-campus")
    assert campus is not None and campus.consumptive_use is not None
    assert campus.consumptive_use.value == pytest.approx(6.188, abs=0.01)


def test_diff_against_ottawa_7q10(hydro_settings: Settings) -> None:
    base, _build, delta = run_scenarios(
        cooling_demand_mgd=5.0, consumptive_fraction=0.8, settings=hydro_settings, live=True
    )
    assert base.consumptive_loss.value == 0.0
    assert delta.consumptive_increase_cfs == pytest.approx(6.188, abs=0.01)
    assert delta.ottawa_7q10_cfs == pytest.approx(0.2)
    assert delta.multiple_of_7q10 == pytest.approx(30.9, abs=0.2)  # the headline


def test_buildout_ottawa_now_screened(hydro_settings: Settings) -> None:
    # With the Ottawa 7Q10 cited, Shawnee II -> Ottawa is no longer skipped.
    _base, build, _delta = run_scenarios(settings=hydro_settings, live=True)
    waters = {c.receiving_water for c in build.assimilative}
    assert "Ottawa River" in waters
    assert all(c.flag == "violation" for c in build.assimilative)


def test_write_scenario_is_self_auditing(hydro_settings: Settings, tmp_path: Path) -> None:
    result = scenario.evaluate(scenario.buildout_scenario(), settings=hydro_settings, live=True)
    out_settings = Settings(data_dir=tmp_path)
    path = scenario.write_scenario(result, settings=out_settings)
    data = yaml.safe_load(Path(path).read_text())
    # Every persisted figure keeps its provenance tag.
    assert data["consumptive_loss"]["source"] == "derived"
    assert data["ottawa_7q10"]["source"] == "document"
    # The default cooling demand is now the sourced basis (derived), not a bare guess.
    assert data["scenario"]["cooling_demand"]["source"] == "derived"
    assert data["scenario"]["basis"]["it_load"]["source"] == "document"


def test_report_renders_all_sections(hydro_settings: Settings) -> None:
    md = report.render_report(settings=hydro_settings, live=False)
    assert "municipal loop" in md
    assert "Low-flow assimilative screen" in md
    assert "Stormwater" in md
    assert "data-center cooling" in md
    assert "24.3" in md  # the sourced-basis headline multiple (power x WUE central)
    assert "sourced" in md  # the cooling basis derivation is shown
    assert "[verified" in md and "[inference" in md  # provenance legend in use
    assert "draw lands when the river is lowest" in md  # the seasonal screen


def test_seasonal_growing_season_is_may_oct(hydro_settings: Settings) -> None:
    sw = scenario.evaluate_seasonal(4.851, settings=hydro_settings)
    assert sw is not None
    # The growing season is exactly the months reference ET exceeds precipitation.
    assert sw.growing_season_months == ["MAY", "JUN", "JUL", "AUG", "SEP", "OCT"]
    for m in sw.months:
        assert m.growing_season == (m.net_atmospheric_mm_day > 0)


def test_seasonal_multiples_use_cited_floors(hydro_settings: Settings) -> None:
    """The seasonal multiple uses the cited summer 30Q10; annual uses the 7Q10."""
    sw = scenario.evaluate_seasonal(4.851, settings=hydro_settings)
    assert sw is not None
    assert sw.annual_7q10_cfs == pytest.approx(0.2)
    assert sw.summer_30q10_cfs == pytest.approx(1.6)
    assert sw.one_q10_cfs == pytest.approx(0.0)
    assert sw.annual_multiple == pytest.approx(24.3, abs=0.1)
    assert sw.summer_multiple == pytest.approx(3.0, abs=0.1)
    # Growing-season months read against the 30Q10; off-season against the 7Q10.
    for m in sw.months:
        if m.growing_season:
            assert m.low_flow_basis == "30Q10 summer" and m.low_flow_cfs == pytest.approx(1.6)
        else:
            assert m.low_flow_basis == "7Q10 annual" and m.low_flow_cfs == pytest.approx(0.2)


def test_seasonal_no_fabricated_monthly_statistic(hydro_settings: Settings) -> None:
    """Only the two cited low-flow bands appear — no invented per-month statistic."""
    sw = scenario.evaluate_seasonal(4.851, settings=hydro_settings)
    assert sw is not None
    assert {m.low_flow_basis for m in sw.months} == {"30Q10 summer", "7Q10 annual"}
