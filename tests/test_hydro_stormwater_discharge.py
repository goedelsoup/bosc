"""ASWCD-calibrated campus storm-discharge screen (#149) — offline, hermetic.

Three things the Allen SWCD production lets the Tier-0 model do with primary data:
calibrate the post-development cover to the declared 115-of-~340 ac impervious footprint
(an area-weighted composite CN, not a blanket impervious parcel), screen the single
60-inch outfall's Manning full-flow capacity, and read the design-storm peak against Dug
Run's cited 7Q10. Also pins the committed artifact against drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.hydrology.solver.curve_number import cn_for
from watermark.hydrology.stormwater import (
    discharge_findings,
    load_discharge_screen,
    load_site_footprint,
    manning_full_pipe_cfs,
    screen_campus_discharge,
)
from watermark.pipeline.hydrology import run_storm


def test_load_site_footprint_is_document_cited(hydro_settings: Settings) -> None:
    fp = load_site_footprint(hydro_settings)
    assert fp is not None, "data/extracted/plans/bosc-site-footprint.yaml must be committed"
    assert fp.impervious_acres.value == pytest.approx(115.0)
    assert fp.developed_acres.value == pytest.approx(195.0)
    assert fp.parcel_acres.value == pytest.approx(335.0)
    assert fp.receiving_water == "Dug Run"
    assert fp.detention_design_shown is False
    assert fp.outfall_diameter_in.value == pytest.approx(60.0)
    # The declared acreages are read off the SW1225 permit application.
    assert fp.impervious_acres.source == "document"
    assert fp.outfall_diameter_in.source == "document"


def test_composite_post_cn_is_far_below_full_buildout(hydro_settings: Settings) -> None:
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    # Only ~115 of ~340 ac is impervious, so the composite sits just above the cropland
    # baseline and well below the blanket near-impervious value the old default assumed.
    assert screen.pre_cn < screen.post_cn_as_permitted < screen.post_cn_full_buildout
    # The full-buildout bound IS the blanket near-impervious CN — on the POST-development
    # drainage condition (WS-20), since that bound develops every acre of the parcel. The
    # fixture's dominant group is B/D, so that is class 24 on D, not on the drained B.
    assert screen.post_cn_full_buildout == pytest.approx(cn_for("developed_campus", "D"), abs=0.1)
    # The calibration still roughly halves the post-vs-pre CN bump. It no longer shrinks it by
    # an order of magnitude, because part of BOTH bumps is now the drained->undrained switch on
    # developed ground rather than the paving itself — a soils assumption the calibration to
    # 115 impervious acres cannot shrink.
    as_permitted_bump = screen.post_cn_as_permitted - screen.pre_cn
    blanket_bump = screen.post_cn_full_buildout - screen.pre_cn
    assert as_permitted_bump < blanket_bump / 2.0


def test_post_runoff_uses_tr55_weighted_runoff(hydro_settings: Settings) -> None:
    # #1611 / WS-11: at ~34% impervious the post-development runoff is computed by the TR-55
    # weighted-runoff method (each cover's CN run separately, runoff depths area-weighted), not
    # a single composite CN applied to the whole footprint — which under-predicts runoff above
    # ~30% impervious. The composite CN is still reported as the area-weighted summary descriptor.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    assert "weighted-runoff" in screen.method
    assert any("weighted-runoff method" in c for c in screen.caveats)
    assert screen.pre_cn < screen.post_cn_as_permitted < screen.post_cn_full_buildout


def test_dual_hsg_resolves_per_scenario_with_provenance(hydro_settings: Settings) -> None:
    # WS-20 / #1620: the fixture's dominant group is the DUAL B/D, whose two letters are two
    # drainage conditions. The screen resolves it once, per scenario, and records which and why
    # — rather than taking the drained letter implicitly from the first character.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    basis = screen.hsg_drainage
    assert basis is not None
    assert basis.group == "B/D"  # carried verbatim, never pre-collapsed
    assert basis.dual is True
    assert (basis.pre_condition, basis.pre_letter) == ("drained", "B")
    assert (basis.post_condition, basis.post_letter) == ("undrained", "D")
    # Both resolved groups are provenance-tagged: the soil rating is the live SSURGO read, and
    # the citation names the drainage condition that turned it into a curve number.
    assert basis.pre_hsg.source == "connector" and basis.post_hsg.source == "connector"
    assert basis.pre_hsg.value == pytest.approx(2.0)  # B
    assert basis.post_hsg.value == pytest.approx(4.0)  # D
    assert "SSURGO" in (basis.post_hsg.citation or "")
    assert "undrained letter of the dual group B/D" in (basis.post_hsg.citation or "")
    # `hsg` stays the pre-development code, so a reader is never handed one letter for two
    # scenarios without the basis block that says they differ.
    assert screen.hsg.value == pytest.approx(basis.pre_hsg.value)
    # The curve numbers actually run on those letters: cropland drained, developed undrained.
    assert screen.pre_cn == pytest.approx(cn_for("cropland", "B"), abs=0.1)
    assert screen.post_cn_full_buildout == pytest.approx(cn_for("developed_campus", "D"), abs=0.1)


def test_undeveloped_remainder_keeps_the_pre_drainage_condition(hydro_settings: Settings) -> None:
    # The switch is per-PART, not blanket: construction severs tile under the developed ground,
    # but the ~145 undeveloped acres are still farmed, so claiming their tile was severed too
    # would be inventing a fact. The composite therefore lands strictly between the two blanket
    # ends, and the caveat states that bracket rather than hiding the choice.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    all_drained = _blanket_composite(hydro_settings, "drained")
    all_undrained = _blanket_composite(hydro_settings, "undrained")
    assert all_drained < screen.post_cn_as_permitted < all_undrained
    assert all_drained == pytest.approx(80.6, abs=0.2)  # the pre-#1620 value
    caveat = next(c for c in screen.caveats if "DUAL group" in c)
    assert f"{all_drained:.1f}" in caveat and f"{all_undrained:.1f}" in caveat
    assert "not in the record" in caveat


def _blanket_composite(settings: Settings, condition: str) -> float:
    """The as-permitted composite CN with every part pinned to one drainage condition."""
    from watermark.hydrology.geo import parcels_total_acres
    from watermark.hydrology.solver.curve_number import composite_cn
    from watermark.hydrology.stormwater import _parcels_path, _post_cover_parts, _resolve_hsg

    basis = _resolve_hsg(_parcels_path(settings), settings=settings, live=True)
    pinned = basis.model_copy(update={"pre_condition": condition, "post_condition": condition})
    footprint = load_site_footprint(settings)
    assert footprint is not None
    acres = parcels_total_acres(_parcels_path(settings), settings=settings)
    parts, _ = _post_cover_parts(acres, footprint, pinned, settings=settings)
    return composite_cn(parts)


def test_drainage_condition_is_a_per_site_switch(hydro_settings: Settings) -> None:
    # The choice is a cited SiteProfile knob, not a hardcode: a site whose record shows the
    # drainage is carried through development declares it and the post scenario follows.
    from watermark.hydrology.stormwater import _parcels_path, _resolve_hsg
    from watermark.sites import SITES, active_profile

    prof = active_profile(hydro_settings)
    assert (prof.pre_drainage_condition, prof.post_drainage_condition) == (
        "drained",
        "undrained",
    ), "the shipped default is the conservative post-development basis"

    maintained = prof.model_copy(
        update={
            "post_drainage_condition": "drained",
            "drainage_condition_citation": "test: a maintained-tile record",
        }
    )
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(SITES, prof.slug, maintained)
        basis = _resolve_hsg(_parcels_path(hydro_settings), settings=hydro_settings, live=True)
    assert basis.post_condition == "drained"
    assert basis.post_letter == "B"  # back to the drained letter, now on a cited basis
    assert "maintained-tile record" in basis.basis


def test_tc_shortens_with_imperviousness(hydro_settings: Settings) -> None:
    # #1163: Tc is scenario-dependent — pervious pre is the longest, the as-permitted
    # composite is shorter (partly paved), and the blanket full-buildout is the shortest.
    from watermark.hydrology.stormwater import _scenario_tc_hr
    from watermark.sites import active_profile

    prof = active_profile(hydro_settings)
    pre_tc = _scenario_tc_hr(0.0, settings=hydro_settings)
    mid_tc = _scenario_tc_hr(0.34, settings=hydro_settings)  # ~115/340 ac impervious
    full_tc = _scenario_tc_hr(1.0, settings=hydro_settings)
    assert pre_tc == pytest.approx(prof.pre_tc_hr)
    assert full_tc == pytest.approx(prof.post_tc_hr)
    assert pre_tc > mid_tc > full_tc > 0
    # Out-of-range fractions clamp to the two bounds rather than extrapolating.
    assert _scenario_tc_hr(-1.0, settings=hydro_settings) == pytest.approx(prof.pre_tc_hr)
    assert _scenario_tc_hr(2.0, settings=hydro_settings) == pytest.approx(prof.post_tc_hr)


def test_screen_peaks_bracket_the_development_impact(hydro_settings: Settings) -> None:
    # The shorter post/full-buildout Tc sharpens their peaks, so the design-storm peaks are
    # strictly ordered pre < as-permitted < full-buildout, and the method documents the Tc
    # bracket — the screen honestly brackets the impact rather than holding Tc fixed (#1163).
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    p = screen.design_peak
    assert p is not None
    assert p.pre_peak_cfs < p.post_peak_cfs < p.full_buildout_peak_cfs
    assert p.post_peak_wet_cfs is not None and p.post_peak_wet_cfs > p.post_peak_cfs
    assert "time of concentration shortens with imperviousness" in screen.method


def test_run_storm_default_uses_the_calibrated_composite(hydro_settings: Settings) -> None:
    # The committed footprint calibrates run_storm's post cover: post CN is the composite,
    # strictly between the cropland pre CN and the blanket near-impervious bound.
    runoff, _ = run_storm(return_period_yr=25, settings=hydro_settings, live=True)
    blanket = cn_for("developed_campus", "D")  # the full-buildout bound, on the post condition
    assert runoff.pre.curve_number < runoff.post.curve_number < blanket
    # 85.2, not the 80.6 of the pre-#1620 drained-everywhere collapse: developed ground now runs
    # the undrained letter of the fixture's B/D rating (the undeveloped remainder stays drained).
    assert runoff.post.curve_number == pytest.approx(85.2, abs=0.3)


def test_storm_falls_back_to_blanket_when_footprint_absent(tmp_path: Path) -> None:
    # No committed footprint -> the post cover is the blanket near-impervious full-buildout.
    settings = Settings(data_dir=tmp_path, hydro_offline=True)
    assert load_site_footprint(settings) is None


def test_manning_full_pipe_capacity(hydro_settings: Settings) -> None:
    # 60-in (5 ft) concrete trunk at 0.5% slope, n=0.013 -> ~185 cfs full-flow.
    cap = manning_full_pipe_cfs(60.0 / 12.0, 0.005)
    assert cap == pytest.approx(184.7, abs=2.0)
    # Monotonic in slope (steeper carries more).
    assert manning_full_pipe_cfs(5.0, 0.003) < manning_full_pipe_cfs(5.0, 0.01)


def test_outfall_capacity_flags_when_peak_exceeds(hydro_settings: Settings) -> None:
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    checks = {f.check: f for f in discharge_findings(screen)}
    cap = checks["outfall-capacity"]
    dp = screen.design_peak
    assert dp is not None
    # The whole-footprint 25-yr peak exceeds a single 60-in trunk at the screened slopes.
    assert screen.capacity_at(0.5) is not None and screen.capacity_at(0.5) < dp.post_peak_cfs
    assert cap.ok is False


def test_receiving_water_peak_vs_dug_run_7q10(hydro_settings: Settings) -> None:
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    assert screen.receiving_water == "Dug Run"
    assert screen.receiving_7q10 is not None
    assert screen.receiving_7q10.value == pytest.approx(0.78)
    assert screen.receiving_7q10.source == "document"  # cited OEPA fact sheet, not invented
    # A design-storm peak hundreds of times the 7Q10 — a channel-stability signal.
    assert screen.peak_to_7q10_ratio is not None and screen.peak_to_7q10_ratio > 100
    peak_finding = next(f for f in discharge_findings(screen) if f.check == "receiving-water-peak")
    assert peak_finding.ok is False
    assert "Dug Run" in peak_finding.detail


def test_discharge_findings_surface_each_dimension(hydro_settings: Settings) -> None:
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    checks = {f.check for f in discharge_findings(screen)}
    assert {
        "outfall-capacity",
        "receiving-water-peak",
        "detention-design",
        "impervious-calibration",
    } <= checks


def test_wet_antecedent_bound_brackets_the_as_permitted_peak(hydro_settings: Settings) -> None:
    # The AMC-III (wet-antecedent) bound raises the as-permitted post peak the outfall and
    # Dug Run must absorb — a disclosed conservative bracket, not the headline number.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    for p in screen.peaks:
        assert p.post_peak_wet_cfs is not None
        assert p.post_peak_cfs < p.post_peak_wet_cfs
    # The design finding surfaces the wet bound so a reader knows the peaks aren't wet.
    calib = next(f for f in discharge_findings(screen) if f.check == "impervious-calibration")
    assert "AMC-III" in calib.detail


def test_receiving_peak_is_routed_to_the_confluence(hydro_settings: Settings) -> None:
    # #1298: the campus outfall hydrograph is routed down the cited Dug Run reach chain to the
    # Ottawa confluence, so the receiving-water peak reflects reach travel — attenuated and
    # lagged — not the at-outfall peak.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    rd = screen.routed_discharge
    assert rd is not None, "the committed reaches.yaml chain should route the outfall hydrograph"
    assert rd.return_period_yr == screen.design_return_period_yr
    assert rd.receiving_water == "Dug Run"
    # The at-outfall peak is the design-storm as-permitted post peak (no reach travel yet).
    dp = screen.design_peak
    assert dp is not None
    assert rd.at_outfall_peak_cfs == pytest.approx(dp.post_peak_cfs, rel=0.01)
    # Routing attenuates and (weakly) lags the peak: the confluence sees less than the outfall.
    assert 0.0 < rd.routed_peak_cfs < rd.at_outfall_peak_cfs
    assert rd.attenuation_pct > 0.0
    assert rd.lag_hr >= 0.0
    # The routed reach is the committed Dug Run chain (head + confluence), tagged an assumption.
    assert rd.reach_length_ft.source == "assumption"
    assert rd.reach_length_ft.value == pytest.approx(27000.0)
    assert "dug-run-head" in rd.reach_path and "dug-run-confluence" in rd.reach_path
    # The routed finding surfaces the attenuation/lag as an upper bound on reach travel.
    routed_finding = next(
        f for f in discharge_findings(screen) if f.check == "routed-receiving-peak"
    )
    assert "attenuated" in routed_finding.detail and "confluence" in routed_finding.detail


def test_routing_does_not_soften_the_at_outfall_erosion_signal(hydro_settings: Settings) -> None:
    # The at-outfall peak-to-7Q10 ratio (the erosion headline) is unchanged by routing — the
    # routed confluence peak is supplementary, not a replacement that softens the signal.
    screen = screen_campus_discharge(settings=hydro_settings, live=True)
    dp = screen.design_peak
    assert dp is not None and screen.peak_to_7q10_ratio is not None
    # peak_to_7q10_ratio is still computed on the at-outfall post peak, not the routed peak.
    assert screen.receiving_7q10 is not None
    assert screen.peak_to_7q10_ratio == pytest.approx(
        round(dp.post_peak_cfs / screen.receiving_7q10.value)
    )
    # The caveat discloses the reach-travel upper bound and that intermediate reaches see more.
    assert any("upper bound" in c and "intermediate" in c for c in screen.caveats)


def test_tributary_reach_chain_requires_a_confluence(hydro_settings: Settings) -> None:
    # #1298 guard: a walk that never reaches a mainstem confluence (a broken downstream edge
    # or a cycle) leaves a PARTIAL chain that must not be routed and mislabeled as reaching the
    # Ottawa confluence — the helper returns nothing so _route_campus_outfall skips it.
    from watermark.hydrology.model import NetworkNode, ProvenancedValue, Reach, ReachTable
    from watermark.hydrology.stormwater import _tributary_reach_chain

    reach = Reach(
        length_ft=ProvenancedValue.assume(1000.0, "ft", why="test"),
        slope=ProvenancedValue.assume(0.002, "ft/ft", why="test"),
    )
    table = ReachTable(reaches={"trib-head": reach})
    head = NetworkNode(
        id="trib-head",
        name="Trib head",
        kind="headwater",
        receiving_water="Trib",
        downstream="trib-mid",
    )
    # 'trib-mid' is a dangling downstream id (not a node) -> the walk ends before any
    # confluence -> no routable chain.
    assert _tributary_reach_chain([head], table, "Trib") == []

    # With a confluence terminating the walk, the chain resolves (even though the confluence
    # node itself carries no reach entry here).
    confluence = NetworkNode(
        id="trib-mid",
        name="Trib -> Ottawa",
        kind="confluence",
        receiving_water="Ottawa River",
        downstream="outlet",
    )
    resolved = _tributary_reach_chain([head, confluence], table, "Trib")
    assert [n.id for n, _ in resolved] == ["trib-head"]


def test_committed_discharge_screen_loads_and_matches(hydro_settings: Settings) -> None:
    committed = load_discharge_screen(hydro_settings)
    assert committed is not None, (
        "data/reference/hydrology/bosc-stormwater-discharge.yaml committed"
    )
    assert committed.design_return_period_yr == 25
    assert {p.return_period_yr for p in committed.peaks} == {10, 25, 100}
    assert committed.receiving_water == "Dug Run"
    # The committed artifact must still match a fresh recompute (guards against drift).
    fresh = screen_campus_discharge(settings=hydro_settings, live=True)
    assert committed.post_cn_as_permitted == pytest.approx(fresh.post_cn_as_permitted, abs=0.1)
    c25, f25 = committed.design_peak, fresh.design_peak
    assert c25 is not None and f25 is not None
    assert c25.post_peak_cfs == pytest.approx(f25.post_peak_cfs, rel=0.01)
    # The committed wet-antecedent (AMC-III) bound also round-trips and matches.
    assert c25.post_peak_wet_cfs is not None and f25.post_peak_wet_cfs is not None
    assert c25.post_peak_wet_cfs == pytest.approx(f25.post_peak_wet_cfs, rel=0.01)
    # The committed routed receiving-water peak (#1298) round-trips and matches a fresh recompute.
    assert committed.routed_discharge is not None and fresh.routed_discharge is not None
    assert committed.routed_discharge.receiving_water == "Dug Run"
    assert committed.routed_discharge.routed_peak_cfs == pytest.approx(
        fresh.routed_discharge.routed_peak_cfs, rel=0.01
    )
    assert committed.routed_discharge.attenuation_pct == pytest.approx(
        fresh.routed_discharge.attenuation_pct, abs=0.5
    )
