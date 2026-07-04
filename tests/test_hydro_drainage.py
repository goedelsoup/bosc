"""Drainage scope-adequacy audit: OPC drainage estimate vs the corridor design storm."""

from __future__ import annotations

from watermark.config import Settings
from watermark.hydrology import drainage


def _settings() -> Settings:
    return Settings(hydro_offline=True)


def test_corridor_ddf_is_committed_and_consistent() -> None:
    """The committed DDF carries the design durations/return periods; 25-yr 24-hr ≈ 4.25 in."""
    ddf = drainage.load_corridor_ddf(settings=_settings())
    assert ddf is not None
    assert "24-hr" in ddf.durations
    assert 100 in ddf.return_periods
    # Depth rises with return period (a sanity invariant of any DDF table).
    d25 = ddf.depth("24-hr", 25)
    d100 = ddf.depth("24-hr", 100)
    assert d25 is not None and d100 is not None
    assert d100 > d25
    # The 25-yr 24-hr depth is the one the stormwater model already uses.
    assert abs(d25 - 4.25) < 0.05


def test_audit_decomposes_drainage_scope() -> None:
    audit = drainage.build_drainage_audit(_settings())
    assert audit.meta["sub_estimate_count"] == 6
    # Program drainage is the sum of the per-estimate subtotals.
    assert audit.meta["program_drainage_total"] == sum(
        s.drainage_subtotal or 0 for s in audit.scopes
    )
    assert audit.meta["program_drainage_total"] > 1_000_000


def test_only_diller_is_itemized_and_is_lump_sum_dominated() -> None:
    """Exactly one sub-estimate has a line-item breakdown; there 83% is lump-sum."""
    audit = drainage.build_drainage_audit(_settings())
    itemized = [s for s in audit.scopes if s.itemized]
    assert len(itemized) == 1
    diller = itemized[0]
    assert "Diller" in diller.name
    assert diller.sized_amount == 20_440  # the 6-in underdrain
    # ...transcribed ~20440 (approximate quantity ~2044 FT) — the marker survives as a flag.
    assert diller.sized_amount_approximate is True
    assert diller.lump_sum_amount == 100_000  # "Drainage improvements" LS
    assert diller.lump_sum_amount_approximate is False  # the LS is an exact round allocation
    assert diller.sized_fraction is not None and diller.sized_fraction < 0.2
    assert any("underdrain" in d.lower() for d in diller.sized_items)
    assert any("Drainage improvements" in d for d in diller.lump_sum_items)


def test_subtotal_only_estimates_carry_no_invented_breakdown() -> None:
    """Estimates without an extracted breakdown stay null — nothing fabricated."""
    audit = drainage.build_drainage_audit(_settings())
    for s in audit.scopes:
        if not s.itemized:
            assert s.sized_amount is None
            assert s.lump_sum_amount is None
            assert s.sized_fraction is None
            assert s.sized_items == [] and s.lump_sum_items == []
            assert s.drainage_subtotal is not None  # subtotal is known


def test_findings_flag_the_design_basis_gaps() -> None:
    audit = drainage.build_drainage_audit(_settings())
    checks = {f.check: f for f in audit.findings}
    # All four gap findings present and flagged not-ok.
    for key in ("line-item-breakdown", "lump-sum-dominance", "design-storm-reference"):
        assert key in checks
        assert checks[key].ok is False
    # The design-storm finding cites verified Atlas-14 depths.
    assert "Atlas-14" in checks["design-storm-reference"].detail
    # Detention cross-reference fires because the 95% plan shows none.
    assert audit.detention_in_design is False
    assert "detention-itemized" in checks


def test_ddf_roundtrip(tmp_path: object) -> None:
    from pathlib import Path

    fixtures = Path(__file__).resolve().parent / "fixtures" / "hydrology"
    s = Settings(hydro_offline=True, data_dir=Path(str(tmp_path)), hydro_fixtures_dir=fixtures)
    ddf = drainage.build_corridor_ddf(settings=s)
    path = drainage.write_corridor_ddf(ddf, settings=s)
    assert path.is_file()
    again = drainage.load_corridor_ddf(settings=s)
    assert again is not None
    assert again.depths_in == ddf.depths_in
    assert again.return_periods == ddf.return_periods
