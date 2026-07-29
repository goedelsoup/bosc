"""Cole/Beery roundabout directed-flow derivation: the grounding for the waterfall theory.

The point these tests lock in: the roundabout's runoff REFUTES the sustained-augmentation
premise — a negligible mean-annual flow, zero at design low flow — and the theory's committed
inject matches the derivation."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology import network as net
from watermark.hydrology import roundabout as rb


def test_impervious_area_derived_from_opc_quantities() -> None:
    area = rb._derive_impervious_acres()
    # Cole/Diller subgrade 6200 SY (= 1.28 ac) x the Beery:Diller pavement ratio (~2.25).
    assert area.value == pytest.approx(2.88, abs=0.05)
    assert area.source == "derived"
    assert "204E11" in area.citation or "204E10001" in area.citation or "subgrade" in area.citation


def test_mean_annual_is_negligible_and_drought_is_zero(hydro_settings: Settings) -> None:
    rf = rb.derive_roundabout_flow(settings=hydro_settings)
    # A single roundabout's catchment yields a tiny continuous-equivalent flow...
    assert rf.mean_annual_cfs.value == pytest.approx(0.012, abs=0.004)
    assert rf.mean_annual_cfs.source == "derived"
    # ...and ZERO at design low flow (it does not rain at the 7Q10).
    assert rf.drought_flow_cfs == 0.0
    # The annual precip traces to the committed NASA POWER reference (connector-sourced).
    assert rf.annual_precip_in.value == pytest.approx(39.2, abs=1.0)


def test_storm_peaks_increase_with_return_period(hydro_settings: Settings) -> None:
    rf = rb.derive_roundabout_flow(settings=hydro_settings)
    peaks = [p.peak_cfs for p in rf.storm_peaks]
    assert peaks == sorted(peaks)  # monotonic in return period
    p2, p100 = rf.peak(2), rf.peak(100)
    assert p2 is not None and p100 is not None
    # Transient surges of several cfs — far larger than the sustained flow, but episodic. Pinned
    # to the calibrated values rather than a wide band: this catchment (Tc 0.2 hr) is the network's
    # most peak-sensitive, so it is where a hyetograph/unit-duration/peak-factor regression would
    # show first (#1610 moved these ~2.5x). rel=0.02 is the storage tolerance — peak_cfs is
    # round_sig'd to 2 significant figures — so anything materially different fails.
    assert p2.peak_cfs == pytest.approx(7.6, rel=0.02)
    assert p100.peak_cfs == pytest.approx(17.0, rel=0.02)
    assert p100.peak_cfs > 100 * rf.mean_annual_cfs.value  # storm >> sustained


def test_findings_refute_sustained_augmentation(hydro_settings: Settings) -> None:
    rf = rb.derive_roundabout_flow(settings=hydro_settings)
    findings = rb.roundabout_findings(rf)
    by_check = {f.check: f for f in findings}
    assert by_check["roundabout-sustained-flow"].ok is False  # the premise fails
    assert "ZERO at design low flow" in by_check["roundabout-sustained-flow"].detail
    assert by_check["roundabout-storm-surge"].ok is True  # episodic flushing is real


def test_committed_theory_inject_matches_the_derivation(hydro_settings: Settings) -> None:
    theories = net.load_theories(settings=hydro_settings)
    waterfall = next(t for t in theories if t.id == "waterfall-roundabout-pike-run")
    node = next(n for n in waterfall.add_nodes if n.inject_cfs is not None)
    inject = node.inject_cfs
    assert inject is not None
    # The theory now carries the DERIVED value, not the old 0.5 assumption placeholder.
    assert inject.source == "derived"
    assert inject.value == pytest.approx(0.012, abs=0.001)
    # Drift guard: the committed value tracks the module's derivation.
    rf = rb.derive_roundabout_flow(settings=hydro_settings)
    assert inject.value == pytest.approx(rf.mean_annual_cfs.value, abs=0.005)


def test_pipeline_run_roundabout(hydro_settings: Settings) -> None:
    from watermark.pipeline import hydrology as hydro_stage

    rf, findings = hydro_stage.run_roundabout(settings=hydro_settings)
    assert rf.impervious_acres.value > 0
    assert len(rf.storm_peaks) == 5
    assert findings


def test_storm_depths_fallback_reads_the_active_profile(
    hydro_settings: Settings, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    # With no committed corridor DDF, the 24-hr storm depths fall back to the ACTIVE SITE's
    # Atlas-14 table (SiteProfile.noaa_fallback_24h_depth_in), not a hardcoded Lima dict (#426).
    monkeypatch.setattr(rb, "load_corridor_ddf", lambda **_: None)
    assert rb._storm_depths(hydro_settings, (2, 10, 100)) == {2: 2.52, 10: 3.58, 100: 5.39}  # Lima
    findlay = hydro_settings.model_copy(update={"site": "findlay"})
    assert rb._storm_depths(findlay, (2, 10, 100)) == {2: 2.44, 10: 3.48, 100: 5.26}  # distinct


def test_storm_depths_raises_when_site_lacks_depth(hydro_settings: Settings, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # #1604: with no committed corridor DDF and an empty profile fallback table, a site's
    # roundabout storm depths must fail loudly (naming the site + return period), never
    # substitute Lima's 4.25 for a different site/frequency.
    from watermark.hydrology.connectors._cache import HydroOfflineError

    monkeypatch.setattr(rb, "load_corridor_ddf", lambda **_: None)
    urbana = hydro_settings.model_copy(update={"site": "urbana"})  # empty fallback map
    with pytest.raises(HydroOfflineError) as exc:
        rb._storm_depths(urbana, (2, 100))
    assert "urbana" in str(exc.value)
