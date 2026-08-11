"""Baseline vs buildout scenario, persistence, and the dossier report (hermetic)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from watermark.config import Settings
from watermark.hydrology import report, scenario
from watermark.hydrology.lowflow import OEPA_SUMMER_MONTHS, low_flow_for, summer_season_months
from watermark.pipeline.hydrology import run_scenarios
from watermark.sites import SITES


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


def test_provisional_live_flow_is_low_confidence(hydro_settings: Settings) -> None:
    """The live Ottawa reading is NWIS provisional, so it must not enter as high-confidence (#1602)."""
    result = scenario.evaluate(scenario.buildout_scenario(), settings=hydro_settings, live=True)
    assert result.receiving_live is not None
    assert result.receiving_live.source == "connector"
    # The committed fixture flags the current reading "P" (provisional, subject to revision).
    assert result.receiving_live.confidence == "low"


def test_diff_against_ottawa_7q10(hydro_settings: Settings) -> None:
    base, _build, delta = run_scenarios(
        cooling_demand_mgd=5.0, consumptive_fraction=0.8, settings=hydro_settings, live=True
    )
    assert base.consumptive_loss.value == 0.0
    assert delta.consumptive_increase_cfs == pytest.approx(6.188, abs=0.01)
    assert delta.receiving_7q10_cfs == pytest.approx(0.2)
    assert delta.receiving_water_name == "Ottawa River"
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
    assert data["receiving_7q10"]["source"] == "document"
    # The default cooling demand is now the sourced basis (derived), not a bare guess.
    assert data["scenario"]["cooling_demand"]["source"] == "derived"
    assert data["scenario"]["basis"]["it_load"]["source"] == "derived"  # N+1 inference (#1697)


def test_scenario_store_is_site_scoped_and_reader_writer_agree(tmp_path: Path) -> None:
    """A peer's scenario write lands in its OWN dir, where its own exporter looks (#1995).

    The bug this locks: the writer used the bare ``settings.scenarios_dir`` while the exporter's
    reader used the slug subdir. ``watermark --site <peer> scenario --write`` therefore
    overwrote **Lima's** committed ``buildout.scenario.yaml`` — the artifact Lima's cooling
    figures are regression-locked against (``tests/test_hydro_cooling.py``) — and still exported
    an empty feed for the peer, because its reader was looking somewhere else entirely.

    Asserted for every registered site, not just one: a slug added later is covered by
    construction rather than by someone remembering to extend this list.
    """
    from watermark.site.export import _load_scenarios

    lima_dir = scenario.scenarios_dir(Settings(data_dir=tmp_path, site="lima"))
    assert lima_dir == tmp_path / "scenarios"  # the reference layout keeps the flat store

    seen: dict[Path, str] = {}
    for slug in SITES:
        s = Settings(data_dir=tmp_path, site=slug)
        write_dir = scenario.scenarios_dir(s)
        # The exporter's reader must resolve the same directory the writer just chose, or the
        # feed stays empty however many scenarios were written.
        s.data_dir.joinpath("scenarios", slug).mkdir(parents=True, exist_ok=True)
        assert _load_scenarios(s) == []  # empty, not an exception, and not Lima's
        # No two sites may share a store: the scenario filename is just the scenario NAME
        # (`buildout.scenario.yaml`), so a shared directory is a silent overwrite, not a merge.
        assert write_dir not in seen, f"{slug} shares its scenario store with {seen.get(write_dir)}"
        seen[write_dir] = slug
        if slug != "lima":
            assert write_dir == tmp_path / "scenarios" / slug
            assert write_dir != lima_dir


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
    # The design low flow is selected by the cited regulatory summer window (not ET0 > precip):
    # summer-season months read against the 30Q10, the rest against the annual 7Q10 (#1624).
    summer = set(summer_season_months(settings=hydro_settings))
    for m in sw.months:
        if m.month in summer:
            assert m.low_flow_basis == "30Q10 summer" and m.low_flow_cfs == pytest.approx(1.6)
        else:
            assert m.low_flow_basis == "7Q10 annual" and m.low_flow_cfs == pytest.approx(0.2)


def test_seasonal_no_fabricated_monthly_statistic(hydro_settings: Settings) -> None:
    """Only the two cited low-flow bands appear — no invented per-month statistic."""
    sw = scenario.evaluate_seasonal(4.851, settings=hydro_settings)
    assert sw is not None
    assert {m.low_flow_basis for m in sw.months} == {"30Q10 summer", "7Q10 annual"}


def test_summer_season_is_cited_oepa_window(hydro_settings: Settings) -> None:
    """The floor switch is the cited Ohio EPA permit window (May-Oct), inherited by Lima."""
    assert OEPA_SUMMER_MONTHS == ("MAY", "JUN", "JUL", "AUG", "SEP", "OCT")
    # Lima sets no per-site override, so it inherits the cited Ohio EPA default.
    assert summer_season_months(settings=hydro_settings) == OEPA_SUMMER_MONTHS


def test_floor_keyed_on_permit_window_not_growing_season(hydro_settings: Settings) -> None:
    """A drenched July (ET0 < precip) is still a summer-30Q10 month — the switch is the
    regulatory permit window, not the ET0 > precip heuristic (finding WS-24 / #1624).

    Reads a committed synthetic fixture (`fixtures/hydrology/seasonal-wet-july/`): the real
    Lima normals with July precip perturbed above reference ET0, so the climatic growing
    season and the permit calendar diverge — no runtime mutation of reference data.
    """
    data_dir = hydro_settings.hydro_fixtures_dir / "seasonal-wet-july"
    s = Settings(
        data_dir=data_dir,
        hydro_offline=True,
        hydro_fixtures_dir=hydro_settings.hydro_fixtures_dir,
    )
    sw = scenario.evaluate_seasonal(4.851, settings=s)
    assert sw is not None
    jul = next(m for m in sw.months if m.month == "JUL")
    # Climatically no longer a growing month — the old heuristic would have picked the 7Q10.
    assert jul.growing_season is False
    assert "JUL" not in sw.growing_season_months
    # But July is inside the permit summer window, so the summer 30Q10 still governs.
    assert jul.low_flow_basis == "30Q10 summer"
    assert jul.low_flow_cfs == pytest.approx(1.6)
