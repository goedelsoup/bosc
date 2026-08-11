"""Baseline vs buildout scenario, persistence, and the dossier report (hermetic)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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


def test_scenario_store_is_site_scoped_and_reader_writer_agree(
    hydro_settings: Settings, tmp_path: Path
) -> None:
    """A peer's scenario write lands in its OWN dir, where its own exporter looks (#1995).

    The bug this locks: the writer used the bare ``settings.scenarios_dir`` while the exporter's
    reader used the slug subdir. ``watermark --site <peer> scenario --write`` therefore
    overwrote **Lima's** committed ``buildout.scenario.yaml`` — the artifact Lima's cooling
    figures are regression-locked against (``tests/test_hydro_cooling.py``) — and still exported
    an empty feed for the peer, because its reader was looking somewhere else entirely.

    The assertion is a **round trip**, not an empty read. Checking that a fresh per-site
    directory reads back empty proves only that the reader is not returning Lima's; it would
    stay green if the reader and the writer drifted apart again, because two different empty
    directories both read empty. Writing a real result and reading *that* back is what actually
    pins the two to the same path.

    Asserted for every registered site, not just one: a slug added later is covered by
    construction rather than by someone remembering to extend this list.
    """
    from watermark.site.export import _load_scenarios

    # Evaluated once, offline, against the committed fixtures — the per-site loop is about
    # WHERE a result is stored, so it needs one real `ScenarioResult`, not one per site.
    result = scenario.evaluate(scenario.buildout_scenario(), settings=hydro_settings, live=True)

    def site_settings(slug: str) -> Settings:
        # Constructed, never `hydro_settings.model_copy(update={"site": …})`: the profile fill
        # (`PROFILE_SETTINGS_FIELDS`) runs at construction only, so a copied Settings keeps the
        # ORIGINAL site's knobs under the new slug — verified, and silent. `data_dir` is the
        # tmp tree so this test can never write into the repo's own `data/scenarios/`, which is
        # the very clobber it exists to prevent.
        return Settings(
            data_dir=tmp_path,
            site=slug,
            hydro_offline=hydro_settings.hydro_offline,
            hydro_fixtures_dir=hydro_settings.hydro_fixtures_dir,
        )

    lima_dir = scenario.scenarios_dir(site_settings("lima"))
    assert lima_dir == tmp_path / "scenarios"  # the reference layout keeps the flat store

    seen: dict[Path, str] = {}
    for slug in SITES:
        s = site_settings(slug)
        write_dir = scenario.scenarios_dir(s)
        # No two sites may share a store: the scenario filename is just the scenario NAME
        # (`buildout.scenario.yaml`), so a shared directory is a silent overwrite, not a merge.
        assert write_dir not in seen, f"{slug} shares its scenario store with {seen.get(write_dir)}"
        seen[write_dir] = slug

        written = Path(scenario.write_scenario(result, settings=s))
        assert written.parent == write_dir
        # The round trip: the exporter's reader must resolve the directory the writer just used.
        loaded = _load_scenarios(s)
        assert [r.scenario.name for r in loaded] == [result.scenario.name], (
            f"{slug}: wrote {written} but the exporter's reader returned {loaded!r} — the "
            "reader and the writer have drifted apart again (#1995)"
        )

        if slug != "lima":
            assert write_dir == tmp_path / "scenarios" / slug
            assert write_dir != lima_dir

    # The bug, stated directly: every registered site wrote the SAME scenario name, and the
    # reference store still holds exactly one file. Under the old writer all of them landed
    # here, each overwriting the last, and Lima's committed artifact was whichever peer ran most
    # recently. (Lima is in `SITES`, so the one file is its own legitimate write.)
    assert [p.name for p in sorted(lima_dir.glob("*.scenario.yaml"))] == [
        f"{result.scenario.name}.scenario.yaml"
    ]


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


# --- the stated (contracted) cooling account, #1995 -------------------------------------------


def _sidney(hydro_settings: Settings) -> Settings:
    # Constructed, never `model_copy` — the profile fill (`PROFILE_SETTINGS_FIELDS`) runs at
    # construction only, so a copied Settings keeps Lima's knobs under the new slug.
    return Settings(
        data_dir=hydro_settings.data_dir,
        site="sidney",
        hydro_offline=True,
        hydro_fixtures_dir=hydro_settings.hydro_fixtures_dir,
    )


def test_stated_makeup_beats_the_derived_basis(hydro_settings: Settings) -> None:
    """A cooling withdrawal the record STATES drives the scenario, and says so (#1995).

    Sidney inverts the network's usual shape — no MW and no floor area disclosed, but an
    executed municipal service agreement that states the gallons — so its water chapter is
    driven by the instrument rather than by the investment-scaled IT-load screen, which would
    stack an inference on an inference. The tag is the assertion: `document`, carrying the
    agreement's own citation, is what makes the committed artifact traceable to Res. 26-26
    instead of reading as a knob someone typed on the command line.
    """
    s = _sidney(hydro_settings)
    sc = scenario.buildout_scenario(settings=s)

    assert sc.cooling_demand.source == "document"
    assert sc.cooling_demand.value == pytest.approx(0.0126)
    assert "26-26" in (sc.cooling_demand.citation or "")
    # Consumption is the DIFFERENCE — makeup less the stated return to the sewer — not an
    # archetype efficiency. 4.6M gal/yr withdrawn, 1.16M returned.
    assert sc.consumptive_fraction.source == "derived"
    assert sc.consumptive_fraction.value == pytest.approx((0.0126 - 0.00318) / 0.0126)


def test_a_stated_account_does_not_close_the_cooling_method(hydro_settings: Settings) -> None:
    """Volumes are not a design: the archetype stays UNKNOWN and bracketed (#1679/A3).

    The temptation the guard exists against is real — Sidney's makeup:blowdown ratio back-solves
    to ~4 cycles of concentration, the signature of an evaporative tower. A ratio BRACKETS a
    design and does not close it, so the basis must still refuse to name a single headline even
    though the scenario now has a grounded intake.
    """
    from watermark.hydrology.cooling import derive_cooling_basis

    s = _sidney(hydro_settings)
    basis = derive_cooling_basis(s)
    assert basis.is_bracketed and not basis.method_disclosed
    assert basis.headline_makeup() is None
    # And the derived bracket still rides along as the cross-check rather than being discarded.
    assert scenario.buildout_scenario(settings=s).basis is not None


def test_an_explicit_override_still_wins_and_is_an_assumption(hydro_settings: Settings) -> None:
    """A sensitivity sweep outranks the record — and is tagged as the assumption it is."""
    sc = scenario.buildout_scenario(cooling_demand_mgd=2.5, settings=_sidney(hydro_settings))
    assert sc.cooling_demand.value == pytest.approx(2.5)
    assert sc.cooling_demand.source == "assumption"


def test_a_stated_makeup_with_no_stated_return_leaves_the_fraction_alone(
    hydro_settings: Settings,
) -> None:
    """Half an account is not a consumption figure — don't invent the return (#1995).

    With a makeup on the record and no blowdown, the consumed share is genuinely unknown, so
    the archetype's fraction stands and the pair reads `document` intake x `assumption`
    fraction. Legible from the tags, and better than deriving a return the record never states.
    """
    from watermark.hydrology.scenario import _stated_cooling_account
    from watermark.sites import SITES

    profile = SITES["sidney"]
    facility = profile.facility
    assert facility is not None
    # `facility` is a read-only accessor over `facilities[0]` (#1628) — copying it directly
    # constructs a field the model does not have and silently leaves the original in place.
    no_return = profile.model_copy(
        update={
            "facilities": (
                facility.model_copy(update={"blowdown_mgd": None, "blowdown_citation": None}),
                *profile.facilities[1:],
            )
        }
    )
    assert no_return.facility is not None and no_return.facility.blowdown_mgd is None
    with patch.dict(SITES, {"sidney": no_return}):
        stated = _stated_cooling_account(_sidney(hydro_settings))
    assert stated is not None
    makeup, frac = stated
    assert makeup.source == "document"
    assert frac is None


def test_makeup_without_a_citation_is_refused() -> None:
    """The one figure that can override a derivation may never pass uncited (#1995)."""
    from watermark.sites import SiteFacility

    with pytest.raises(ValueError, match="makeup_citation"):
        SiteFacility(name="Stub", status="confirmed", makeup_mgd=0.01)


def test_sidney_screens_against_its_cited_reach_not_the_basin_proxy(
    hydro_settings: Settings,
) -> None:
    """The reach key and the display name are different strings, deliberately (#1995/#829).

    The bare river name belongs to the basin screen's DERIVED Hamilton mainstem proxy; this
    outfall's cited reach is the permit-scoped entry #1992 added. Reading the display name as a
    lookup key credits the discharge with ~17x the dilution it has — the same defect #1992 fixed
    on the basin side. Both halves are asserted here: the scenario resolves the cited 24.0, and
    the bare key still resolves to the proxy, so nothing was fixed by overriding it.
    """
    from watermark.hydrology.basin import build_low_flow_lookup
    from watermark.hydrology.lowflow import _normalize
    from watermark.sites import SITES

    s = _sidney(hydro_settings)
    profile = SITES["sidney"]
    assert profile.receiving_water_name == "Great Miami River"
    assert profile.receiving_low_flow_key is not None

    cited = low_flow_for(profile.receiving_low_flow_key, settings=s)
    assert cited is not None and cited.value == pytest.approx(24.0)
    assert cited.source == "document"

    proxy = build_low_flow_lookup(settings=s)[_normalize(profile.receiving_water_name)]
    assert proxy.source == "derived" and proxy.value > 400.0

    result = scenario.evaluate(scenario.buildout_scenario(settings=s), settings=s, live=False)
    assert result.receiving_7q10 is not None
    assert result.receiving_7q10.value == pytest.approx(24.0)
    # Reported under the readable name, screened against the exact reach.
    assert result.receiving_water_name == "Great Miami River"


def test_a_real_ratio_never_publishes_as_zero(hydro_settings: Settings) -> None:
    """A draw three orders below its denominator is small, not absent (#1995).

    One decimal is right for the multiples this network was built on (Lima's draw is 24x the
    Ottawa's 7Q10) and rounds Sidney's contracted 0.0146 cfs against 24.0 cfs to `0.0` — which
    reads as no draw at all. That is a different claim, and the wrong one.
    """
    assert scenario._ratio(24.25) == 24.2 or scenario._ratio(24.25) == 24.3  # unchanged scale
    assert scenario._ratio(3.0) == 3.0
    assert scenario._ratio(0.014575 / 24.0) == pytest.approx(0.00061, rel=0.02)

    s = _sidney(hydro_settings)
    _, _build, delta = run_scenarios(settings=s, live=False)
    assert delta.multiple_of_7q10 is not None and delta.multiple_of_7q10 > 0
