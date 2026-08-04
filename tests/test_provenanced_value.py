"""Range + certainty support on :class:`ProvenancedValue` (#760).

The quantitative uncertainty band is orthogonal to the qualitative ``confidence``
enum, stored as absolute ``low``/``high`` bounds however the caller spelled it.
"""

from __future__ import annotations

import pytest

from watermark.hydrology.model import ProvenancedValue
from watermark.provenance import degrade


def test_scalar_value_has_no_range() -> None:
    v = ProvenancedValue.from_document(226.0, "acre", citation="permit p1")
    assert v.has_range is False
    assert v.low is None and v.high is None


def test_explicit_low_high_bounds() -> None:
    v = ProvenancedValue.derived(
        226.0, "acre", citation="raster segmentation", low=181.0, high=271.0
    )
    assert v.has_range is True
    assert v.low == 181.0 and v.high == 271.0


def test_plus_minus_is_symmetric() -> None:
    v = ProvenancedValue.derived(250.0, "MW", citation="N+1", plus_minus=25.0)
    assert v.low == 225.0 and v.high == 275.0


def test_rel_uncertainty_is_a_fraction_of_value() -> None:
    v = ProvenancedValue.derived(226.0, "acre", citation="±20% method", rel_uncertainty=0.2)
    assert v.low == pytest.approx(180.8)
    assert v.high == pytest.approx(271.2)


def test_range_and_confidence_are_orthogonal() -> None:
    v = ProvenancedValue.derived(
        226.0, "acre", citation="est", rel_uncertainty=0.2, confidence="medium"
    )
    assert v.confidence == "medium"
    assert v.has_range is True


def test_at_most_one_range_spelling() -> None:
    with pytest.raises(ValueError, match="at most one range spelling"):
        ProvenancedValue.derived(1.0, "MW", citation="x", plus_minus=0.1, rel_uncertainty=0.1)
    with pytest.raises(ValueError, match="at most one range spelling"):
        ProvenancedValue.derived(1.0, "MW", citation="x", low=0.5, plus_minus=0.1)


def test_negative_spread_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ProvenancedValue.derived(1.0, "MW", citation="x", plus_minus=-0.1)
    with pytest.raises(ValueError, match="non-negative"):
        ProvenancedValue.assume(1.0, "MW", why="x", rel_uncertainty=-0.1)


def test_bounds_must_bracket_value() -> None:
    with pytest.raises(ValueError, match=r"range low .* exceeds value"):
        ProvenancedValue.derived(10.0, "MW", citation="x", low=12.0, high=20.0)
    with pytest.raises(ValueError, match=r"range high .* is below value"):
        ProvenancedValue.derived(10.0, "MW", citation="x", low=1.0, high=5.0)


def test_one_sided_range_is_allowed() -> None:
    lo_only = ProvenancedValue.derived(10.0, "MW", citation="x", low=8.0)
    assert lo_only.has_range and lo_only.low == 8.0 and lo_only.high is None
    hi_only = ProvenancedValue.derived(10.0, "MW", citation="x", high=12.0)
    assert hi_only.has_range and hi_only.high == 12.0 and hi_only.low is None


def test_with_range_attaches_a_band_to_a_document_central() -> None:
    central = ProvenancedValue.from_document(250.0, "MW", citation="air permit")
    banded = central.with_range(low=250.0, high=300.0)
    assert banded.source == "document"  # provenance preserved
    assert banded.low == 250.0 and banded.high == 300.0
    assert central.has_range is False  # original untouched (copy semantics)


def test_verbatim_constructors_take_no_range_kwargs() -> None:
    # from_document / from_connector deliberately omit the range params — a verbatim
    # figure gets a band only via the explicit .with_range() escape hatch.
    with pytest.raises(TypeError):
        ProvenancedValue.from_document(1.0, "MW", citation="x", low=0.5)  # type: ignore[call-arg]


def test_with_range_revalidates_the_bounds() -> None:
    # model_copy(update=...) would bypass the range validator; with_range must not — an
    # inverted band on a document central has to raise, not slip through.
    central = ProvenancedValue.from_document(250.0, "MW", citation="air permit")
    with pytest.raises(ValueError, match=r"range low .* exceeds value"):
        central.with_range(low=300.0, high=350.0)
    with pytest.raises(ValueError, match=r"range high .* is below value"):
        central.with_range(low=100.0, high=200.0)


def test_str_renders_the_band() -> None:
    v = ProvenancedValue.derived(226.0, "acre", citation="x", low=181.0, high=271.0)
    s = str(v)
    assert "181.00" in s and "271.00" in s and "[calc]" in s


def test_range_survives_round_trip() -> None:
    v = ProvenancedValue.derived(226.0, "acre", citation="x", rel_uncertainty=0.2)
    again = ProvenancedValue.model_validate(v.model_dump())
    assert again.low == v.low and again.high == v.high


def test_degrade_steps_down_once_and_floors_at_low() -> None:
    """One monotone step, so it composes with a caller's own down-weighting (WS-21, #1621).

    Never upgrades, and never wraps around — applying it to an already-``low`` figure, or
    twice, has to stay safe, because callers stack it on top of their own rules.
    """
    assert degrade("high") == "medium"
    assert degrade("medium") == "low"
    assert degrade("low") == "low"
    assert degrade(degrade(degrade("high"))) == "low"


def test_derived_takes_an_asof() -> None:
    """A derivation over dated inputs is only true as of that window (WS-21, #1621)."""
    v = ProvenancedValue.derived(4.5, "cfs", citation="NWIS min P7D", asof="2026-06-03T00:00:00Z")
    assert v.asof == "2026-06-03T00:00:00Z"
