"""Per-chemical toxic screen vs Ohio WQS criteria over the committed RSEI/ECHO/7Q10 data (WS-07)."""

from __future__ import annotations

from watermark.config import Settings
from watermark.hydrology import toxics, units
from watermark.hydrology.model import ProvenancedValue


def _by_name(inv: toxics.ToxicDischargeInventory, needle: str) -> toxics.ToxicDischargeScreen:
    return next(s for s in inv.screens if needle in s.facility)


def _chem(s: toxics.ToxicDischargeScreen, needle: str) -> toxics.ChemicalScreen:
    return next(c for c in s.chemical_screens if needle in c.chemical)


def _crit(cs: toxics.ChemicalScreen, ctype: str) -> toxics.CriterionScreen:
    return next(c for c in cs.criteria if c.criterion_type == ctype)


# --- resolution / provenance (unchanged behaviour) -----------------------------------------
def test_screen_builds_and_the_refinery_majors_are_critical() -> None:
    inv = toxics.build_screen(Settings())
    assert inv.meta["water_releaser_count"] == len(inv.screens)
    # The three refinery-complex majors: heavy per-chemical loads exceeding an Ohio aquatic-life
    # criterion on a near-undiluted reach.
    for name in ("INEOS", "LIMA REFINING", "PCS NITROGEN"):
        assert _by_name(inv, name).flag == "critical"
    assert inv.meta["critical_count"] == len(inv.flagged) >= 3
    assert inv.meta["exceeding_chemical_count"] > 0


def test_lima_refining_receiving_water_is_echo_cited() -> None:
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    assert s.receiving_water_source == "connector"
    assert s.npdes_id == "OH0002623"
    assert s.receiving_water is not None and "OTTAWA" in s.receiving_water.upper()


def test_corridor_inference_is_tagged_and_cited() -> None:
    for name in ("INEOS", "PCS NITROGEN"):
        s = _by_name(toxics.build_screen(Settings()), name)
        assert s.receiving_water_source == "assumption"
        assert s.receiving_water == "Ottawa River"
        assert s.receiving_water_citation is not None
        assert "corridor" in s.receiving_water_citation.lower()
        assert "not independently cited" in s.receiving_water_citation.lower()


def test_low_flow_is_the_cited_7q10() -> None:
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    assert s.low_flow_7q10 is not None
    assert s.low_flow_7q10.source == "document"
    assert s.low_flow_7q10.value == 0.2


def test_uncharacterized_when_no_receiving_water() -> None:
    inv = toxics.build_screen(Settings())
    unchar = [s for s in inv.screens if s.flag == "uncharacterized"]
    assert unchar, "expected some facilities we cannot place on a cited reach"
    for s in unchar:
        assert s.receiving_water is None
        assert s.receiving_water_source is None
        assert s.low_flow_7q10 is None
        assert s.chemical_screens == []


# --- per-chemical screening (WS-07) ---------------------------------------------------------
def test_ammonia_is_ineos_top_water_chemical_and_screens_all_three_flows() -> None:
    """The screen keys on the *water* chemical (ammonia), not the all-media top-by-score."""
    s = _by_name(toxics.build_screen(Settings()), "INEOS")
    assert s.top_water_chemical is not None and "Ammonia" in s.top_water_chemical
    ammonia = _chem(s, "Ammonia")
    # Ammonia carries an acute + chronic Ohio criterion (no human-health value).
    types = {c.criterion_type for c in ammonia.criteria}
    assert {"acute", "chronic"} <= types and "human_health" not in types


def test_design_flow_matches_criterion_type() -> None:
    """acute -> 1Q10 (0 for the Ottawa), chronic -> 7Q10 (0.2), human health -> harmonic mean (4.8)."""
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    ammonia = _chem(s, "Ammonia")
    assert _crit(ammonia, "acute").design_flow.value == 0.0  # Ottawa 1Q10
    assert _crit(ammonia, "chronic").design_flow.value == 0.2  # cited 7Q10
    benzene = _chem(s, "Benzene")  # human-health only
    assert _crit(benzene, "human_health").design_flow.value == 4.8  # harmonic mean


def test_1q10_zero_acute_is_a_degenerate_exceedance_not_infinity() -> None:
    """At 1Q10 = 0 there is no acute assimilative capacity: flagged, but no Inf concentration."""
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    acute = _crit(_chem(s, "Ammonia"), "acute")
    assert acute.flag == "exceedance"
    assert acute.derived_concentration is None
    assert acute.exceedance_factor is None
    assert acute.loading_capacity_lb_day == 0.0
    assert acute.note is not None and "no assimilative capacity" in acute.note


def test_loading_capacity_and_exceedance_factor_math() -> None:
    """Chronic screen: loading capacity = criterion x Q x 8.34; factor = derived / criterion."""
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    chronic = _crit(_chem(s, "Ammonia"), "chronic")
    assert chronic.derived_concentration is not None and chronic.exceedance_factor is not None
    mgd = units.cfs_to_mgd(chronic.design_flow.value)
    expected_lc = chronic.criterion.value * mgd * 8.34
    assert chronic.loading_capacity_lb_day is not None
    assert abs(chronic.loading_capacity_lb_day - expected_lc) < 1e-2
    expected_factor = chronic.derived_concentration.value / chronic.criterion.value
    assert abs(chronic.exceedance_factor - expected_factor) < 5e-3
    # The criterion is a `reference` value citing the OAC rule; the concentration is derived.
    assert chronic.criterion.source == "reference" and "3745-1" in (
        chronic.criterion.citation or ""
    )
    assert chronic.derived_concentration.source == "derived"


def test_nitrate_screens_human_health_only() -> None:
    """Nitrate has no aquatic-life criterion — only the human-health (harmonic-mean) screen."""
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    nitrate = _chem(s, "Nitrate")
    assert {c.criterion_type for c in nitrate.criteria} == {"human_health"}


def test_no_criterion_chemical_is_reported_not_guessed() -> None:
    """A water chemical with no committed Ohio criterion is flagged no_criterion, empty criteria."""
    s = _by_name(toxics.build_screen(Settings()), "INEOS")
    glycol = _chem(s, "Ethylene glycol")
    assert glycol.flag == "no_criterion"
    assert glycol.criteria == []


def test_trace_discharger_with_only_zero_flow_acute_is_elevated_not_critical() -> None:
    """Teledyne's 5 lb of chromium: a degenerate 1Q10=0 acute 'exceedance' alone -> elevated.

    Critical is reserved for a *computed* chronic/nonzero-flow acute exceedance, so a trace
    discharger is never alarmistly flagged critical.
    """
    inv = toxics.build_screen(Settings())
    teledyne = _by_name(inv, "TELEDYNE")
    assert teledyne.water_pounds < 10
    assert teledyne.flag == "elevated"
    # It DOES carry the honest zero-capacity acute note (surfaced, not hidden).
    chrome = _chem(teledyne, "Chromium")
    acute = _crit(chrome, "acute")
    assert acute.flag == "exceedance" and acute.exceedance_factor is None
    # ...but no chemical has a computed aquatic-life exceedance.
    assert not any(
        c.criterion_type in ("acute", "chronic")
        and c.flag == "exceedance"
        and c.exceedance_factor is not None
        for cs in teledyne.chemical_screens
        for c in cs.criteria
    )


def test_every_critical_facility_has_a_computed_aquatic_exceedance() -> None:
    inv = toxics.build_screen(Settings())
    for s in inv.flagged:
        assert any(
            c.criterion_type in ("acute", "chronic")
            and c.flag == "exceedance"
            and c.exceedance_factor is not None
            for cs in s.chemical_screens
            for c in cs.criteria
        ), f"{s.facility} is critical without a computed exceedance"


def test_chemical_flag_is_the_worst_of_its_criteria() -> None:
    s = _by_name(toxics.build_screen(Settings()), "LIMA REFINING")
    ammonia = _chem(s, "Ammonia")
    assert ammonia.flag == "exceedance"  # chronic exceeds


# --- format helper --------------------------------------------------------------------------
def test_format_factor() -> None:
    assert toxics.format_factor(float("inf")) == "∞"
    assert toxics.format_factor(1.101) == "1.1x"
    assert toxics.format_factor(13007.2) == "13,007x"


# --- aggregate context helper (unchanged) ---------------------------------------------------
def test_screening_concentration_conversion() -> None:
    """1 lb/day into 1 cfs is the textbook ~0.186 mg/L; confirm the mass balance."""
    q7 = ProvenancedValue.from_document(1.0, "cfs", "test")
    conc = toxics._screening_concentration(365.0, q7)  # 365 lb/yr == 1 lb/day
    assert conc is not None
    assert abs(conc.value - 0.186) < 0.002
    assert conc.source == "derived" and conc.confidence == "low"


def test_zero_flow_or_zero_load_yields_no_aggregate_concentration() -> None:
    assert (
        toxics._screening_concentration(1000.0, ProvenancedValue.from_document(0.0, "cfs", "t"))
        is None
    )
    assert (
        toxics._screening_concentration(0.0, ProvenancedValue.from_document(0.2, "cfs", "t"))
        is None
    )


# --- annualization helper (unchanged) -------------------------------------------------------
def _fac_with_years(water_lbs: float, years: list[int]) -> object:
    from watermark.rsei import RseiFacility, RseiYearScore

    return RseiFacility(
        facility_id="TEST",
        facility_number="0",
        name="TEST",
        fips="39003",
        pounds_by_media={"water": water_lbs},
        first_year=years[0] if years else None,
        last_year=years[-1] if years else None,
        years=[
            RseiYearScore(year=y, score=0, cancer_score=0, noncancer_score=0, hazard=0, pounds=0)
            for y in years
        ],
    )


def test_annualizes_over_reporting_years_not_span() -> None:
    fac = _fac_with_years(1000.0, [1988, 2022])  # 2 reporting years, 35 calendar
    assert toxics._annual_water_pounds(fac) == 500.0


def test_annualize_guards_empty_year_record() -> None:
    assert toxics._annual_water_pounds(_fac_with_years(50.0, [])) == 50.0


# --- persistence ----------------------------------------------------------------------------
def test_write_load_roundtrip_preserves_chemical_screens(tmp_path: object) -> None:
    from pathlib import Path

    ref = Path(str(tmp_path))
    inv = toxics.build_screen(Settings())
    path = toxics.write_screen(inv, ref / "rsei")
    assert path.is_file()
    reloaded = toxics.load_screen(ref)
    assert reloaded is not None
    assert len(reloaded.screens) == len(inv.screens)
    assert reloaded.meta["critical_count"] == inv.meta["critical_count"]
    # The nested per-chemical screens survive the YAML round-trip.
    ineos = _by_name(reloaded, "INEOS")
    assert ineos.chemical_screens and any(cs.criteria for cs in ineos.chemical_screens)
    assert toxics.load_screen(ref / "nonexistent") is None
