"""Federal backdrop (#98): the federal energy policy levers + US output/statistics, with
the campus load sized against the national data-center demand wave. Hermetic - reads
committed reference data only, no network. The top of the grid stack (epic #93); this
backdrop feeds the consumer-cost thread (#91).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.facility.power import derive_power_basis
from watermark.grid.policy import (
    derive_federal_backdrop,
    load_federal_backdrop,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def grid_settings() -> Settings:
    """Real repo data dir (reads committed reference data + EIA fixtures); no network."""
    return Settings(
        data_dir=REPO_ROOT / "data",
        hydro_offline=True,
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
    )


def test_policy_levers_include_ira_credits_with_cost_direction(grid_settings: Settings) -> None:
    fb = derive_federal_backdrop(settings=grid_settings)
    names = {lever.name.value.lower() for lever in fb.policy_levers}
    # The IRA section 45 PTC and section 48 ITC clean-generation credits are present.
    assert any("section 45" in n and "production" in n for n in names)
    assert any("section 48" in n and "investment" in n for n in names)
    # The tech-neutral successors (45Y/48E) and the tangential 45V/45X are mapped too.
    assert any("45y" in n or "48e" in n for n in names)
    assert any("45v" in n for n in names)
    assert any("45x" in n for n in names)
    # DOE programs (Loan Programs Office, grid resilience) are levers as well.
    assert any("loan" in n for n in names)

    for lever in fb.policy_levers:
        # Each lever is cited (reference), carries its statute, and a direction on cost.
        assert lever.name.source == "reference"
        assert lever.statute.value
        assert lever.cost_direction.value in {"lowers clean-gen cost", "tangential", "n/a"}

    # The clean-generation credits lower clean-gen cost; the IRA statute is cited.
    ptc = next(lever for lever in fb.policy_levers if "section 45 " in lever.name.value)
    assert ptc.cost_direction.value == "lowers clean-gen cost"
    assert "Inflation Reduction Act" in ptc.statute.value


def test_federal_output_sources(grid_settings: Settings) -> None:
    out = derive_federal_backdrop(settings=grid_settings).output
    # US net generation + avg retail price are now LIVE EIA connector pulls (#98/#120).
    for pv in (out.us_net_generation_twh, out.us_avg_retail_price_cents_kwh):
        assert pv.source == "connector" and pv.verified
        assert "EIA" in (pv.citation or "")
    # The data-center share stays a report-cited reference (LBNL/DOE, not on the EIA API).
    for pv in (
        out.datacenter_use_2023_twh,
        out.datacenter_share_pct_2023,
        out.datacenter_share_pct_2028_proj,
    ):
        assert pv.source == "reference"
        assert pv.confidence == "medium"
        assert pv.citation
    # Realistic magnitudes.
    assert out.us_net_generation_twh.value == pytest.approx(4300.0, rel=0.2)
    assert out.datacenter_use_2023_twh.value == pytest.approx(176.0, rel=0.2)
    assert 3.0 < out.datacenter_share_pct_2023.value < 6.0
    assert out.datacenter_share_pct_2028_proj.value > out.datacenter_share_pct_2023.value
    assert 10.0 < out.us_avg_retail_price_cents_kwh.value < 16.0


def test_a_projection_is_not_dated_like_an_observation(grid_settings: Settings) -> None:
    """`asof` says when a quantity WAS true, so the two measured LBNL/DOE figures carry their
    2023 observation year — undated beside a 2025 EIA value, they read as equally current.

    The 2028 projection stays undated on purpose (#1644 review). Its target year is not a
    vintage: `asof=2028` would assert data that does not exist yet, and the report's 2024
    publication year would read as a measurement made then. A projection's currency is its
    report, which the citation already names — here, no marker is the honest answer, and a
    sweep that "fixed" every null would be the wrong fix.
    """
    out = derive_federal_backdrop(settings=grid_settings).output
    assert out.datacenter_use_2023_twh.asof == "2023"
    assert out.datacenter_share_pct_2023.asof == "2023"
    assert out.datacenter_share_pct_2028_proj.asof is None
    # The live EIA pulls carry their own, later series vintage — the whole point of dating the
    # pair above is that the reader can see the federal backdrop mixes them.
    assert out.us_net_generation_twh.asof is not None
    assert out.us_net_generation_twh.asof > out.datacenter_use_2023_twh.asof


def test_campus_vs_us_datacenter_share_links_facility_draw(grid_settings: Settings) -> None:
    fb = derive_federal_backdrop(settings=grid_settings)
    power = derive_power_basis(settings=grid_settings)

    # Campus load IS the first-class PowerBasis.facility_draw (#87).
    assert fb.campus_load_mw.value == pytest.approx(power.facility_draw.value, abs=0.1)
    expected_gwh = power.facility_draw.value * 8760.0 * fb.load_factor.value / 1000.0
    assert fb.annual_consumption_gwh.value == pytest.approx(expected_gwh, rel=0.01)

    # The campus-vs-US-datacenter share is consumption / (datacenter TWh x 1000).
    us_dc_gwh = fb.output.datacenter_use_2023_twh.value * 1000.0
    assert fb.share_of_us_datacenter_pct.value == pytest.approx(
        fb.annual_consumption_gwh.value / us_dc_gwh * 100.0, rel=0.01
    )
    # A small but non-trivial positive share of national data-center load.
    assert 0.0 < fb.share_of_us_datacenter_pct.value < 5.0
    # And a far smaller share of all US net generation; the shares are derived.
    assert 0.0 < fb.share_of_us_generation_pct.value < fb.share_of_us_datacenter_pct.value
    assert fb.share_of_us_datacenter_pct.source == "derived"
    assert fb.share_of_us_generation_pct.source == "derived"


def test_committed_federal_backdrop_round_trips() -> None:
    """The committed reference YAML round-trips into the model."""
    fb = load_federal_backdrop(Settings(data_dir=REPO_ROOT / "data"))
    assert fb is not None
    assert len(fb.policy_levers) >= 5
    assert fb.share_of_us_datacenter_pct.value > 0.0
    assert fb.output.us_net_generation_twh.value > 0.0
