"""Grid foundation layer (#94): the serving utility is cited (AEP Ohio / PJM), the
EIA profile assembles, and the campus load is expressed as a provenance-tagged share
of utility / BA / state load. Hermetic — reads committed reference data only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from watermark.config import Settings
from watermark.connectors import OfflineError
from watermark.facility.power import derive_power_basis
from watermark.grid.interchange import fetch_ba_annual_load
from watermark.grid.utility import (
    GridVintageDriftError,
    _load_share_vintages,
    _retail_regulator,
    _serving_utility,
    derive_grid_profile,
    load_grid_profile,
)
from watermark.hydrology.model import ProvenancedValue
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
    from watermark.grid._registry import utility_identity
    from watermark.grid.utility import _balancing_authority
    from watermark.sites import get_profile

    prof = get_profile("lima")  # #14006 is in the shared registry
    ba = _balancing_authority(prof, utility_identity(prof.eia861_utility_number, "AEP Ohio"))
    assert ba.confirmed is True and ba.ba_code == "PJM" and ba.confidence == "high"


def test_ba_unlisted_utility_is_unconfirmed_not_pjm() -> None:
    """B2/#1639: an off-map serving utility with no ba_code pin reports the RTO as unconfirmed,
    NOT PJM at high confidence — Portsmouth (#0, unpinned) is the stub case."""
    from watermark.grid._registry import utility_identity
    from watermark.grid.utility import _balancing_authority
    from watermark.sites import get_profile

    prof = get_profile("portsmouth")
    ba = _balancing_authority(prof, utility_identity(prof.eia861_utility_number, "serving utility"))
    assert ba.confirmed is False
    assert ba.ba_code == "" and "PJM" not in ba.rto_name
    assert ba.confidence == "low"


def test_ba_off_map_pinned_site_uses_pin() -> None:
    """B2/#1639: an off-map but ba_code-pinned site (Hamilton/Duke) resolves its pinned BA."""
    from watermark.grid._registry import utility_identity
    from watermark.grid.utility import _balancing_authority
    from watermark.sites import get_profile

    prof = get_profile("hamilton-middletown")
    ba = _balancing_authority(
        prof, utility_identity(prof.eia861_utility_number, "Duke Energy Ohio")
    )
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


# --- the committed-artifact staleness guard (#1769) -----------------------------------------
# The committed grid profiles are CLI-produced artifacts, so they freeze whatever the code said
# on the day they were written while the code keeps moving: `watermark grid` needs two live EIA
# pulls, so nobody re-runs it when a facility lands or a citation is unified. Four classes of
# drift had accumulated silently by #1769 — a facility registered after the profile (`load_share`
# stuck at null on a site that HAS a campus), a pre-#1641 `campus_load_mw`, a pre-#1639
# BA/RTO citation, and a pre-`ownership` utility block. The first is the one that reached the
# site: `/network/urbana/economy/grid` rendered "no data-center facility is disclosed here" over
# a disclosed campus. These two tests hold the committed artifacts to what the code derives today.

_GRID_PROFILE_SITES = sorted(
    slug for slug, prof in SITES.items() if (REPO_ROOT / "data" / prof.grid_relpath).is_file()
)


def _committed_grid_settings(slug: str) -> Settings:
    return Settings(site=slug, data_dir=REPO_ROOT / "data", hydro_offline=True, econ_offline=True)


def test_committed_load_share_tracks_the_facility_power_basis() -> None:
    """A committed profile carries a campus ``load_share`` exactly when the site has a load basis.

    ``derive_grid_profile`` omits ``load_share`` for a site whose ``derive_power_basis`` is
    ``None`` — the honest degrade for a facility-less peer. But the profile is a *snapshot* and
    ``has_facility_power_basis`` is a *standing* property of the registry, so a facility that
    lands after the profile was written leaves a null share on a site that has a campus. The
    page then reports the absence as a fact about the place ("no data-center facility is
    disclosed here") rather than as the stale artifact it is. Both directions matter: a share
    committed for a site that has since lost its load basis is equally wrong.
    """
    for slug in _GRID_PROFILE_SITES:
        gp = load_grid_profile(_committed_grid_settings(slug))
        assert gp is not None
        expected = SITES[slug].has_facility_power_basis
        assert (gp.load_share is not None) == expected, (
            f"{slug}: committed grid profile has load_share="
            f"{'set' if gp.load_share else 'null'} but has_facility_power_basis={expected} — "
            f"re-run `watermark --site {slug} grid --write`"
        )
    assert len(_GRID_PROFILE_SITES) >= 20


@pytest.mark.parametrize("slug", _GRID_PROFILE_SITES)
def test_committed_grid_profile_matches_a_current_code_derivation(
    slug: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every committed grid profile equals what ``derive_grid_profile`` produces today.

    The two connector pulls are substituted with the figures **the committed profile itself
    carries** (its ``utility_profile`` block and its ``ba_profile.annual_load_gwh``), so this
    stays hermetic and compares only what the code derives — the service chain, the campus load,
    and the shares — against the committed bytes. The denominators are held fixed rather than
    re-fetched on purpose: a change in the EIA vintage is a data decision that belongs in a
    reviewed re-pull, not a test failure. Everything else is code, and code drift is exactly the
    staleness this catches.
    """
    from watermark.grid import utility as grid_utility
    from watermark.grid.model import UtilityProfile

    settings = _committed_grid_settings(slug)
    committed = load_grid_profile(settings)
    assert committed is not None

    monkeypatch.setattr(grid_utility, "fetch_utility_retail", lambda **_: committed.utility_profile)
    monkeypatch.setattr(
        grid_utility, "fetch_ba_annual_load", lambda **_: committed.ba_profile.annual_load_gwh
    )
    derived = derive_grid_profile(settings=settings)

    assert isinstance(committed.utility_profile, UtilityProfile)
    assert derived.model_dump() == committed.model_dump(), (
        f"{slug}: the committed grid profile has fallen behind the code that produces it — "
        f"re-run `watermark --site {slug} grid --write` (and refresh its bundle feed)"
    )


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


# --- G1/#1644: vintage markers on connector values --------------------------------------------


def _connector_values(model: object, prefix: str = "") -> list[tuple[str, ProvenancedValue]]:
    """Every ``source == "connector"`` :class:`ProvenancedValue` reachable on ``model``."""
    found: list[tuple[str, ProvenancedValue]] = []
    for name, value in getattr(model, "__dict__", {}).items():
        path = f"{prefix}{name}"
        if isinstance(value, ProvenancedValue):
            if value.source == "connector":
                found.append((path, value))
        elif isinstance(value, BaseModel):
            found.extend(_connector_values(value, f"{path}."))
    return found


def test_grid_profile_actually_pulls_its_denominators_from_connectors(
    grid_settings: Settings,
) -> None:
    """The premise of the vintage assertion below: these values are live pulls, not literals.

    If a future refactor turned a denominator back into a transcribed constant, the ``asof`` gap
    would "close" by the value ceasing to be connector-sourced at all — the wrong way to pass.
    """
    gp = derive_grid_profile(settings=grid_settings)
    paths = {p for p, _ in _connector_values(gp)}
    assert {
        "utility_profile.retail_sales_gwh",
        "ba_profile.annual_load_gwh",
        "load_share.state_retail_gwh",
    } <= paths, f"the grid denominators are no longer connector-sourced; got {sorted(paths)}"


def test_connector_values_carry_a_vintage_marker(grid_settings: Settings) -> None:
    """H3/#1645, closed by G1/#1644: ``asof`` makes a stale live pull visible (#1107 discipline).

    ``ProvenancedValue.asof`` is documented as "ISO datetime, for connector (live) values". A
    connector value without one cannot be aged by the catalog's staleness check, so a profile
    regenerated from a year-old cache reads exactly like a fresh one.
    """
    gp = derive_grid_profile(settings=grid_settings)
    undated = [path for path, v in _connector_values(gp) if not getattr(v, "asof", None)]
    assert not undated, f"connector values missing an asof vintage marker: {undated}"


def test_vintage_markers_are_the_data_year_not_the_run_date(grid_settings: Settings) -> None:
    """The marker has to be the DATA's vintage, not "when we fetched it" — otherwise a re-pull
    of a five-year-old bulk file would stamp itself fresh and the staleness check would be worse
    than useless. Each ``asof`` must be the year its own citation names.
    """
    gp = derive_grid_profile(settings=grid_settings)
    for path, value in _connector_values(gp):
        assert value.asof is not None
        year = value.asof[:4]
        assert year.isdigit(), f"{path}: asof {value.asof!r} is not a data year"
        assert year in (value.citation or ""), (
            f"{path}: asof {value.asof!r} is not the vintage its citation names "
            f"({value.citation!r}) — the marker must date the DATA, not the run"
        )


# --- G2/#1644: mixed denominator vintages, surfaced and gated ----------------------------------


def test_each_load_share_denominator_names_its_own_vintage(grid_settings: Settings) -> None:
    """The load-share table divides one campus figure by three denominators of DIFFERENT years.

    Before G2 only the utility share named a vintage; the BA share said "EIA-930 annual demand"
    with no year and the state share named none at all. A reader comparing 5.64% / 0.337% / 1.69%
    could not tell they were struck against 2024 / 2024 / 2025 grids. Each citation now carries
    the year of the denominator it actually divided by — asserted against that denominator's own
    ``asof`` rather than a literal, so this cannot pass by naming the wrong year confidently.
    """
    ls = derive_grid_profile(settings=grid_settings).load_share
    assert ls is not None
    for share, denom in (
        (ls.share_of_utility_pct, ls.utility_retail_gwh),
        (ls.share_of_ba_pct, ls.ba_load_gwh),
        (ls.share_of_state_pct, ls.state_retail_gwh),
    ):
        assert denom.asof is not None
        assert denom.asof[:4] in (share.citation or ""), (
            f"share citation {share.citation!r} does not name its denominator's "
            f"{denom.asof!r} vintage"
        )
    # The mixed vintage is stated once, in prose, where a reader meets the table — not left to
    # be reassembled from three citations.
    note = derive_grid_profile(settings=grid_settings).note
    assert "vintages differ" in note.lower()
    assert ls.state_retail_gwh.asof is not None and ls.state_retail_gwh.asof[:4] in note


def test_the_committed_denominators_really_are_mixed_vintage(grid_settings: Settings) -> None:
    """The premise of the test above: if all three ever landed on one year, that assertion would
    pass trivially and stop testing anything. Pin the condition it exists to describe."""
    ls = derive_grid_profile(settings=grid_settings).load_share
    assert ls is not None
    years = {
        v.asof[:4]
        for v in (ls.utility_retail_gwh, ls.ba_load_gwh, ls.state_retail_gwh)
        if v.asof is not None
    }
    assert len(years) > 1, (
        f"all three denominators are now vintage {years} — the mixed-vintage reconciliation is "
        "no longer describing a real condition; revisit G2/#1644 rather than deleting it"
    )


def test_vintage_drift_past_the_tolerance_refuses_to_derive_a_share() -> None:
    """A forgotten vintage bump must fail loudly, not ship a share against a stale grid.

    The whole point of G2: ``eia861_year`` / ``eia930_year`` are knobs someone has to remember,
    and a forgotten one shows up only as a slowly widening gap that three printed percentages
    hide completely. Drive the guard directly with denominators three years apart — past the
    default 2-year tolerance — and it must raise rather than divide.
    """
    settings = _committed_grid_settings("lima")
    fresh = ProvenancedValue.from_connector(100.0, "GWh/yr", citation="state", asof="2025")
    stale = ProvenancedValue.from_connector(100.0, "GWh/yr", citation="utility", asof="2022")
    with pytest.raises(GridVintageDriftError) as exc:
        _load_share_vintages(settings, utility_retail=stale, ba_load=fresh, state_retail=fresh)
    assert "3 years" in str(exc.value)
    # It names the knobs to bump — a guard that only says "no" costs more than it saves.
    assert "EIA861_YEAR" in str(exc.value) and "EIA930_YEAR" in str(exc.value)

    # Inside the tolerance the same call reconciles rather than raising: a one-year spread is
    # the normal upstream publication lag, and refusing it would break every re-pull.
    ok = _load_share_vintages(
        settings,
        utility_retail=ProvenancedValue.from_connector(1.0, "GWh/yr", citation="u", asof="2024"),
        ba_load=ProvenancedValue.from_connector(1.0, "GWh/yr", citation="b", asof="2024"),
        state_retail=fresh,
    )
    assert ok.spread_years == 1 and ok.state == "2025" and ok.utility == "2024"


def test_undated_denominators_fall_back_to_config_not_to_year_zero() -> None:
    """A pre-G1 committed profile round-trips with ``asof: null``. Reading that as "year 0" would
    make the guard raise on every legacy artifact, so an undated value reads the configured
    vintage instead — undated is unknown, not ancient."""
    settings = _committed_grid_settings("lima")
    undated = ProvenancedValue.from_connector(1.0, "GWh/yr", citation="legacy")
    v = _load_share_vintages(
        settings, utility_retail=undated, ba_load=undated, state_retail=undated
    )
    assert v.utility == str(settings.eia861_year) and v.ba == str(settings.eia930_year)
    assert v.spread_years == 0


def test_the_eia930_vintage_is_a_config_knob_not_a_call_site_literal() -> None:
    """G2: the BA denominator's year lived only as a default in ``fetch_ba_annual_load``'s
    signature, beside an ``eia861_year`` that WAS config — so half the vintage set was
    invisible to anyone bumping the other half. Changing the setting must change the pull."""
    settings = Settings(
        data_dir=REPO_ROOT / "data",
        econ_offline=True,
        econ_fixtures_dir=REPO_ROOT / "tests" / "fixtures" / "economics",
        eia930_year=1999,
    )
    with pytest.raises(OfflineError) as exc:  # no fixture for 1999 — the key names the year
        fetch_ba_annual_load(ba="PJM", settings=settings)
    assert "1999" in str(exc.value)
