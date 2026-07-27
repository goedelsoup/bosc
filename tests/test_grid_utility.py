"""Grid foundation layer (#94): the serving utility is cited (AEP Ohio / PJM), the
EIA profile assembles, and the campus load is expressed as a provenance-tagged share
of utility / BA / state load. Hermetic — reads committed reference data only.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.facility.power import derive_power_basis
from watermark.grid.utility import (
    _retail_regulator,
    _serving_utility,
    derive_grid_profile,
    load_grid_profile,
)
from watermark.sites import SITES

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


def test_serving_utility_is_cited_not_asserted(grid_settings: Settings) -> None:
    gp = derive_grid_profile(settings=grid_settings)
    su = gp.serving_utility
    # The serving utility is AEP Ohio, document-grounded in the corpus (not asserted).
    assert "AEP Ohio" in su.utility.value
    assert su.utility.source == "document" and su.utility.verified
    assert "tariff" in su.utility.citation.lower()
    # The RTO / balancing authority is PJM (authoritative).
    assert "PJM" in su.rto.value and "PJM" in su.balancing_authority.value
    # The retail regulator is PUCO.
    assert "PUCO" in su.retail_regulator.value


def test_campus_load_share_links_facility_draw(grid_settings: Settings) -> None:
    gp = derive_grid_profile(settings=grid_settings)
    ls = gp.load_share
    power = derive_power_basis(settings=grid_settings)

    # Campus load IS the first-class PowerBasis.facility_draw (#87).
    assert ls.campus_load_mw.value == pytest.approx(power.facility_draw.value, abs=0.1)
    expected_gwh = power.facility_draw.value * 8760.0 * ls.load_factor.value / 1000.0
    assert ls.annual_consumption_gwh.value == pytest.approx(expected_gwh, rel=0.01)

    # The shares order correctly: a campus is a larger fraction of its utility than of
    # the whole RTO, and the utility is smaller than the state.
    assert ls.share_of_utility_pct.value > ls.share_of_state_pct.value
    assert ls.share_of_state_pct.value > ls.share_of_ba_pct.value
    # The campus is a MATERIAL fraction of its serving utility's retail load (a few %).
    assert 3.0 < ls.share_of_utility_pct.value < 10.0
    # Each share is the consumption over the corresponding denominator.
    assert ls.share_of_utility_pct.value == pytest.approx(
        ls.annual_consumption_gwh.value / ls.utility_retail_gwh.value * 100.0, rel=0.01
    )


def test_load_denominators_are_connector_sourced(grid_settings: Settings) -> None:
    gp = derive_grid_profile(settings=grid_settings)
    ls = gp.load_share
    # All three denominators are now connector-sourced (#94/#120): Ohio retail (EIA,
    # shared #91), AEP-Ohio per-utility (EIA-861), PJM annual demand (EIA-930).
    assert ls.state_retail_gwh.source == "connector"
    assert ls.utility_retail_gwh.source == "connector" and ls.utility_retail_gwh.verified
    assert ls.ba_load_gwh.source == "connector" and ls.ba_load_gwh.verified
    assert "EIA-861" in ls.utility_retail_gwh.citation
    assert "EIA-930" in ls.ba_load_gwh.citation
    # The utility profile carries EIA-861 customers + price, connector-sourced.
    up = gp.utility_profile
    assert up.customers is not None and up.customers.source == "connector"
    assert up.avg_price_cents_kwh is not None and up.avg_price_cents_kwh.source == "connector"


def test_retail_regulator_is_ownership_aware() -> None:
    """An IOU is PUC-regulated; a municipal is home rule; a cooperative is member-regulated."""
    iou_value, _ = _retail_regulator("OH", "Investor Owned")
    assert "PUCO" in iou_value
    muni_value, muni_cite = _retail_regulator("OH", "Municipal")
    assert "municipal" in muni_value.lower() and "home rule" in muni_value.lower()
    assert "not state-PUC" in muni_cite
    coop_value, _ = _retail_regulator("OH", "Cooperative")
    assert "cooperative" in coop_value.lower()


def test_serving_utility_municipal_is_home_rule_not_puco() -> None:
    """Bryan's municipal system: home-rule regulator, AMP/PJM, no IOU holding company."""
    settings = Settings(site="bryan", data_dir=REPO_ROOT / "data")
    su = _serving_utility(settings, "City of Bryan - (OH)", ownership="Municipal")
    assert "home rule" in su.retail_regulator.value.lower()
    assert "PUCO" not in su.retail_regulator.value
    assert "PJM" in su.rto.value and "PJM" in su.balancing_authority.value
    assert "American Municipal Power" in su.holding_company.value
    assert "PUC-certified IOU territory" in su.note


def test_ba_confirmed_map_site_is_pjm_high() -> None:
    """B2/#1639: a serving utility in the confirmed per-utility map resolves PJM at high conf."""
    from watermark.grid.utility import _balancing_authority, _utility_grid
    from watermark.sites import get_profile

    prof = get_profile("lima")  # #14006 is in _UTILITY_GRID
    ba = _balancing_authority(prof, _utility_grid(prof.eia861_utility_number, "AEP Ohio"))
    assert ba.confirmed is True and ba.ba_code == "PJM" and ba.confidence == "high"


def test_ba_unlisted_utility_is_unconfirmed_not_pjm() -> None:
    """B2/#1639: an off-map serving utility with no ba_code pin reports the RTO as unconfirmed,
    NOT PJM at high confidence — Portsmouth (#0, unpinned) is the stub case."""
    from watermark.grid.utility import _balancing_authority, _utility_grid
    from watermark.sites import get_profile

    prof = get_profile("portsmouth")
    ba = _balancing_authority(prof, _utility_grid(prof.eia861_utility_number, "serving utility"))
    assert ba.confirmed is False
    assert ba.ba_code == "" and "PJM" not in ba.rto_name
    assert ba.confidence == "low"


def test_ba_off_map_pinned_site_uses_pin() -> None:
    """B2/#1639: an off-map but ba_code-pinned site (Hamilton/Duke) resolves its pinned BA."""
    from watermark.grid.utility import _balancing_authority, _utility_grid
    from watermark.sites import get_profile

    prof = get_profile("hamilton-middletown")
    ba = _balancing_authority(prof, _utility_grid(prof.eia861_utility_number, "Duke Energy Ohio"))
    assert ba.confirmed is True and ba.ba_code == "PJM"


def test_committed_grid_profile_loads() -> None:
    """The committed reference YAML round-trips into the model."""
    gp = load_grid_profile(Settings(data_dir=REPO_ROOT / "data"))
    assert gp is not None
    assert "AEP Ohio" in gp.serving_utility.utility.value
    assert gp.load_share.share_of_utility_pct.value > 0.0


# --- the bundle-feed guard (E1 / #1642) -----------------------------------------------------
def test_committed_grid_profiles_carry_real_denominators() -> None:
    """Every committed grid profile establishes the denominators the backdrop floor rests on.

    ``has_real_denominators`` is the #1364 present-but-empty gate the ``grid`` object feed is
    dropped by. If a real committed profile ever fails it, that site silently loses a floor
    feed and its backdrop domain drops to ``seeded`` — so pin the committed corpus here rather
    than discover it as a readiness regression.
    """
    checked = 0
    for slug in SITES:
        gp = load_grid_profile(Settings(site=slug, data_dir=REPO_ROOT / "data"))
        if gp is None:  # a site that hasn't run `watermark grid` yet
            continue
        checked += 1
        assert gp.has_real_denominators, (
            f"{slug}: committed grid profile has a zeroed utility/BA denominator — the grid feed "
            "would be dropped and its backdrop domain would fall to seeded"
        )
    assert checked >= 20, f"expected the committed grid profiles to be found, saw {checked}"


def test_zeroed_denominators_are_a_shell_not_a_backdrop() -> None:
    """A stale/hand-authored profile with zeroed utility + BA figures establishes nothing.

    ``derive_grid_profile`` cannot emit one (A1/#1638 raises instead of zero-filling), but a
    round-tripped YAML can — and the ``grid`` feed must drop it rather than ship a ``count == 1``
    shell that floats the backdrop domain to ``live`` on a profile with no denominators.
    """
    gp = load_grid_profile(Settings(data_dir=REPO_ROOT / "data"))
    assert gp is not None and gp.has_real_denominators

    zeroed = gp.model_copy(deep=True)
    zeroed.utility_profile.retail_sales_gwh.value = 0.0
    assert not zeroed.has_real_denominators
    # One live denominator is not enough — the feed asserts *whose* grid and *how big*, both.
    half = gp.model_copy(deep=True)
    half.ba_profile.annual_load_gwh.value = 0.0
    assert not half.has_real_denominators
