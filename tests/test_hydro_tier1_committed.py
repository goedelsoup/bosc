"""Committed Tier-1 SWMM artifact: verified engine-free (no pyswmm needed).

These pin the reviewed detention/surcharge result and prove the committed `.inp`
decks still match their recorded checksums — so the dossier shows real SWMM numbers
offline and the engine path is testable without the engine."""

from __future__ import annotations

import pytest

from bosc.config import Settings
from bosc.hydrology.tier1 import deck_checksum_mismatches, load_tier1, tier1_findings


def test_committed_tier1_loads_with_grounding(hydro_settings: Settings) -> None:
    result = load_tier1(settings=hydro_settings)
    assert result is not None, "data/reference/hydrology/tier1-swmm.yaml must be committed"
    assert result.available
    assert result.engine.startswith("pyswmm")
    assert result.storm_return_period_yr == 25
    assert len(result.decks) == 4
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
    det = result.deck("detention")
    assert det is not None and "[STORAGE]" in det.inp_text and "[ORIFICES]" in det.inp_text
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
    checks = {f.check for f in tier1_findings(result)}
    assert "detention-sizing" in checks
    assert "wet-weather-surcharge" in checks
    assert "sso-mandate" in checks  # the regulatory context
