"""The hydrologic soil group vocabulary + dual-group drainage switch (WS-20 / #1620).

The leaf itself (`watermark.hsg`) plus the two consumers that take a single letter and must
**refuse** an unresolved dual group rather than silently slicing it to its drained one — the
TR-55 curve-number lookup and the SWMM deck's Horton infiltration.
"""

from __future__ import annotations

import pytest

from watermark.hsg import (
    DEFAULT_DRAINAGE_BASIS,
    DUAL_HSG_RULE,
    hsg_code,
    is_dual_hsg,
    normalize_hsg,
    resolve_hsg,
)


@pytest.mark.parametrize(
    ("group", "drained", "undrained"),
    [
        ("A/D", "A", "D"),
        ("B/D", "B", "D"),
        ("C/D", "C", "D"),
    ],
)
def test_dual_groups_resolve_to_either_condition(group: str, drained: str, undrained: str) -> None:
    # The first letter is the drained condition, the second the natural one — the whole point
    # of the switch, and the direction an implicit `[:1]` always picked.
    assert resolve_hsg(group, "drained") == drained
    assert resolve_hsg(group, "undrained") == undrained
    assert is_dual_hsg(group)


@pytest.mark.parametrize("group", ["A", "B", "C", "D"])
def test_single_groups_are_condition_independent(group: str) -> None:
    # Only naturally-D soils are ever dual-classed, so a single rating already IS the soil's
    # undrained behaviour — asking for either condition is the same question.
    assert resolve_hsg(group, "drained") == resolve_hsg(group, "undrained") == group
    assert not is_dual_hsg(group)


def test_verbatim_survey_values_normalize() -> None:
    # SDA values arrive with whatever whitespace/case the survey carried.
    assert normalize_hsg(" b/d ") == "B/D"
    assert resolve_hsg(" c/d ", "undrained") == "D"
    assert is_dual_hsg("b/d")


def test_an_unrecognised_group_raises_rather_than_defaulting() -> None:
    # No fallback: a soil rating that quietly became "C" would be a fabricated infiltration
    # class. The message names the vocabulary so the caller can see what drifted.
    with pytest.raises(ValueError, match="unrecognised hydrologic soil group"):
        resolve_hsg("E", "drained")
    with pytest.raises(ValueError, match="A/D, B/D, C/D"):
        resolve_hsg("", "undrained")


def test_hsg_code_needs_a_resolved_group() -> None:
    assert [hsg_code(g) for g in ("A", "B", "C", "D")] == [1.0, 2.0, 3.0, 4.0]
    # A code is a single-group ordinal; a dual group has to be resolved first, and the error
    # says so instead of coding the drained letter.
    with pytest.raises(ValueError, match="resolve the drainage condition first"):
        hsg_code("B/D")


def test_curve_number_lookup_refuses_an_unresolved_dual_group() -> None:
    # The load-bearing refusal: `cn_for("cropland", "B/D")` used to silently answer with B's
    # curve number (78) when the undrained D value is 89.
    from watermark.hydrology.solver.curve_number import cn_for

    assert cn_for("cropland", "B") == pytest.approx(78.0)
    assert cn_for("cropland", "D") == pytest.approx(89.0)
    with pytest.raises(KeyError, match=r"resolve it with watermark\.hsg\.resolve_hsg"):
        cn_for("cropland", "B/D")


def test_swmm_infiltration_refuses_an_unresolved_dual_group() -> None:
    # Same refusal on the SWMM side, where the two conditions' Horton rates differ 6-fold.
    from watermark.hydrology.swmm.inp import _horton_for

    assert _horton_for("B") != _horton_for("D")
    with pytest.raises(ValueError, match="needs a resolved hydrologic soil group"):
        _horton_for("C/D")


def test_the_published_rule_and_the_stated_basis_are_distinguishable() -> None:
    # Two different kinds of claim ride in the citations and must not blur: the NRCS dual-class
    # rule is published reference, the pre/post condition assignment is a stated assumption.
    assert "National Engineering Handbook" in DUAL_HSG_RULE
    assert "Stated Tier-0 modeling basis" in DEFAULT_DRAINAGE_BASIS
    assert "overrides both on its SiteProfile" in DEFAULT_DRAINAGE_BASIS
