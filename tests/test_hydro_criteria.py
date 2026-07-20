"""Tests for the committed Ohio WQS criteria table + loader (WS-07 / #1607)."""

from __future__ import annotations

import math

from watermark.config import Settings
from watermark.hydrology import criteria


def test_committed_table_loads_and_indexes() -> None:
    table = criteria.load_criteria(settings=Settings())
    assert table.criteria, "no criteria committed"
    # The two stated screening assumptions are recorded (re-derivable).
    assert table.assumptions["hardness_mg_l_caco3"] == 100
    assert table.assumptions["ammonia_ph"] == 8.0


def test_resolves_by_cas_and_rsei_category_code() -> None:
    """A chemical resolves by its real CAS *and* by the RSEI Nxxx category alias."""
    table = criteria.load_criteria(settings=Settings())
    # Ammonia — the dominant water load, an aquatic-life criterion with no human-health value.
    ammonia = table.match("7664-41-7")
    assert ammonia is not None
    assert ammonia.acute_cmc_mg_l == 5.9 and ammonia.chronic_ccc_mg_l == 0.6
    assert ammonia.human_health_mg_l is None
    # Cyanide resolves by both hydrogen-cyanide CAS and the RSEI cyanide-compounds code.
    assert table.match("74-90-8") is table.match("N106") is not None
    # Copper resolves by elemental CAS and its "compounds" category alias.
    assert table.match("7440-50-8") is table.match("N100")


def test_missing_chemical_omitted_not_guessed() -> None:
    """A chemical with no committed Ohio criterion resolves to None (omit, don't guess)."""
    table = criteria.load_criteria(settings=Settings())
    assert table.match("67-56-1") is None  # methanol — no numeric aquatic-life criterion
    assert table.match(None) is None
    assert table.match("not-a-cas") is None


def test_nitrate_is_human_health_only_expressed_as_no3() -> None:
    table = criteria.load_criteria(settings=Settings())
    nitrate = table.match("N511")
    assert nitrate is not None
    assert nitrate.acute_cmc_mg_l is None and nitrate.chronic_ccc_mg_l is None
    assert nitrate.human_health_mg_l == 44.0  # 10 mg/L as N, expressed as NO3


def test_hardness_metal_re_derives_from_equation() -> None:
    """A hardness metal's stored mg/L is at 100 mg/L; the equation re-derives at other hardness."""
    table = criteria.load_criteria(settings=Settings())
    copper = table.match("7440-50-8")
    assert copper is not None and copper.hardness_dependent
    # The committed mg/L equals the equation evaluated at the reference hardness (100).
    at_100 = copper.hardness_chronic.at(100.0) / 1000.0
    assert copper.chronic_ccc_mg_l is not None
    assert math.isclose(copper.chronic_at(100.0), copper.chronic_ccc_mg_l, rel_tol=1e-3)
    assert math.isclose(copper.chronic_at(100.0), at_100, rel_tol=1e-9)
    # Softer water -> a more protective (lower) criterion; harder water -> higher.
    assert copper.chronic_at(50.0) < copper.chronic_ccc_mg_l < copper.chronic_at(200.0)


def test_hardness_equations_reproduce_epa_100mgl_values() -> None:
    """Cross-check: the Table 35-9 equations reproduce EPA's tabulated criteria at 100 mg/L."""
    table = criteria.load_criteria(settings=Settings())
    # (token, EPA acute ug/L, EPA chronic ug/L) at 100 mg/L hardness.
    for token, acute_ug, chronic_ug in [("7440-02-0", 470.0, 52.0), ("N982", 120.0, 120.0)]:
        crit = table.match(token)
        assert crit is not None and crit.hardness_acute is not None
        # Ohio's equation vs EPA's rounded tabulated value diverge by a few percent (e.g. zinc
        # 117 vs 120) — a sanity cross-check, not an exact-equality assertion.
        assert abs(crit.hardness_acute.at(100.0) - acute_ug) / acute_ug < 0.03
        assert crit.hardness_chronic is not None
        assert abs(crit.hardness_chronic.at(100.0) - chronic_ug) / chronic_ug < 0.03
