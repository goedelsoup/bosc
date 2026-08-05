"""Committed Tier-1 SWMM artifact: verified engine-free (no pyswmm needed).

These pin the reviewed detention/surcharge result and prove the committed `.inp`
decks still match their recorded checksums — so the dossier shows real SWMM numbers
offline and the engine path is testable without the engine."""

from __future__ import annotations

import pytest

from watermark.config import Settings
from watermark.hydrology.tier1 import deck_checksum_mismatches, load_tier1, tier1_findings


def test_committed_tier1_loads_with_grounding(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None, "data/reference/hydrology/tier1-swmm.yaml must be committed"
    assert result.available
    assert result.engine.startswith("pyswmm")
    assert result.storm_return_period_yr == 25
    assert len(result.decks) == 6
    # The cited grounding is re-attached from its own reference files, not duplicated.
    assert result.inventory is not None and result.inventory.sheet_id
    assert result.sanitary_basis is not None


def test_committed_detention_holds_post_peak_to_pre(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None and result.detention is not None
    d = result.detention
    assert d.post_peak_cfs > d.pre_peak_cfs  # paving raises the peak
    # The sized basin holds the controlled release near the pre-development rate.
    assert d.controlled_peak_cfs == pytest.approx(d.pre_peak_cfs, rel=0.15)
    assert d.required_storage_acft > 0
    assert d.orifice_diam_ft > 0


def test_committed_detention_is_sized_against_the_as_permitted_footprint(
    hydro_settings: Settings,
) -> None:
    """WS-14 (#1614): the committed basin is the permitted project's, not the blanket 90%'s.

    The committed post deck used to run the blanket near-impervious value over the whole
    parcel — 90% against the Tier-0 screen's ~34% ASWCD-declared composite, two different
    projects — and the reported basin was sized against the one the permit does not describe.
    """
    from watermark.hydrology.stormwater import load_site_footprint

    result = load_tier1(settings=hydro_settings)
    assert result is not None and result.detention is not None
    d = result.detention

    footprint = load_site_footprint(hydro_settings)
    assert footprint is not None
    # The modeled %Imperv reconciles with the declaration it claims to come from.
    assert d.post_imperv_pct is not None
    declared = 100.0 * footprint.impervious_acres.value / 339.59
    assert d.post_imperv_pct == pytest.approx(declared, abs=0.5)
    assert "declared permanently impervious" in d.post_imperv_basis

    # The deck actually carries that value, and the sized deck carries it too.
    post = result.deck("post")
    detention = result.deck("detention")
    assert post is not None and detention is not None
    subcatchment = next(ln for ln in post.inp_text.splitlines() if ln.startswith("S1 RG1"))
    assert float(subcatchment.split()[4]) == pytest.approx(d.post_imperv_pct, abs=0.05)
    assert f" {d.post_imperv_pct:.1f} " in detention.inp_text

    # The blanket case survives as an explicitly-labeled bound, sized against the same
    # pre-development peak — larger peak, larger basin, separate deck.
    full = result.deck("full-buildout")
    full_det = result.deck("detention-full-buildout")
    assert full is not None and full_det is not None
    assert d.full_buildout_imperv_pct == 90.0 and " 90.0 " in full.inp_text
    assert d.full_buildout_peak_cfs is not None and d.full_buildout_peak_cfs > d.post_peak_cfs
    assert d.full_buildout_storage_acft is not None
    assert d.full_buildout_storage_acft > d.required_storage_acft
    assert d.full_buildout_controlled_peak_cfs == pytest.approx(d.pre_peak_cfs, rel=0.15)


def test_committed_surcharge_exceeds_headroom_with_provenance(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    assert result.surcharge, "expected per-plant surcharge rows"
    assert all(s.exceeds for s in result.surcharge)  # campus overruns documented headroom
    am2 = next(s for s in result.surcharge if "American II" in s.plant)
    # The cited capacity/avg are document; the SWMM wet peak and peaking factor are derived.
    assert am2.capacity.source == "document"
    assert am2.wet_weather_peak.source == "derived"
    assert am2.avg_design_flow is not None and am2.avg_design_flow.source == "document"
    assert am2.peaking_factor is not None and am2.peaking_factor.source == "derived"
    assert am2.headroom_mgd == pytest.approx(
        am2.capacity.value - am2.avg_design_flow.value, abs=0.01
    )


def test_committed_surcharge_respects_campus_routing(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    judged = {s.plant for s in result.surcharge}
    # Shawnee II receives no campus flow (FM-3 theorized) -> it must not be judged.
    assert "Shawnee II" not in judged
    # The judged plant is an FM-1 receiver.
    am2 = next(s for s in result.surcharge if "American II" in s.plant)
    assert am2.forcemain == "FM-1"
    # The routing decisions are recorded for audit: the FM split + the exclusion.
    note = result.surcharge_note
    assert "FM-1" in note and "FM-2" in note
    assert "Shawnee II" in note and "Excluded" in note


def test_committed_deck_checksums_match(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    # load_tier1 reads each committed .inp back into inp_text; the sha256 must still match.
    assert all(d.inp_text for d in result.decks)
    assert deck_checksum_mismatches(result) == []


def test_committed_decks_are_wellformed_inp(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    common = ("[OPTIONS]", "[RAINGAGES]", "[TIMESERIES]")
    for deck in result.decks:
        for section in common:
            assert section in deck.inp_text, f"{deck.name} missing {section}"
    for name in ("detention", "detention-full-buildout"):
        det = result.deck(name)
        assert det is not None and "[STORAGE]" in det.inp_text and "[ORIFICES]" in det.inp_text
    for name in ("pre", "post", "full-buildout"):
        undetained = result.deck(name)
        assert undetained is not None and "[STORAGE]" not in undetained.inp_text
    san = result.deck("sanitary")
    assert san is not None and "[DWF]" in san.inp_text and "[RDII]" in san.inp_text


def test_committed_continuity_is_sane(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    # A SWMM run with a large mass-balance error is not trustworthy.
    assert all(abs(d.continuity_error_pct) < 5.0 for d in result.decks)


def test_committed_yaml_excludes_deck_text(hydro_settings: Settings) -> None:
    # The committed YAML records checksums + filenames, not the (large) .inp text.
    path = hydro_settings.data_dir / "reference" / "hydrology" / "tier1-swmm.yaml"
    raw = path.read_text(encoding="utf-8")
    assert "[SUBCATCHMENTS]" not in raw and "[OPTIONS]" not in raw
    assert "sha256:" in raw


def test_committed_findings_surface_the_case(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None
    findings = tier1_findings(result)
    checks = {f.check for f in findings}
    assert "detention-sizing" in checks
    assert "wet-weather-surcharge" in checks
    assert "sso-mandate" in checks  # the regulatory context
    # The two post-development readings are separate findings, each naming its own case.
    sizing = next(f for f in findings if f.check == "detention-sizing")
    assert "as permitted" in sizing.detail
    bound = next(f for f in findings if f.check == "detention-full-buildout")
    assert "full-buildout bound" in bound.detail and "assumption" in bound.detail
