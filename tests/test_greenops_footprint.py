"""GreenOps footprint derivation (#1083): the usage → electricity → water assembly is faithful
to the committed connector exports + factor tables, every figure stays modeled (never metered),
the derived CO2e is reconciled against the AWS CCFT total, and a missing source degrades to a
stated assumption rather than fabricating or crashing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.greenops.footprint import (
    _runner_cores,
    _vcpu_for_usage_type,
    derive_footprint,
    footprint_reference_path,
    load_footprint,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "data" / "reference" / "greenops"


@pytest.fixture
def repo_settings() -> Settings:
    """Settings pointed at the committed repo data — the derivation reads the reference YAMLs."""
    return Settings(data_dir=REPO_ROOT / "data")


def _settings_with(tmp_path: Path, *relpaths: str) -> Settings:
    """A Settings whose data_dir holds only the named reference/greenops/* files (partial wiring)."""
    for rel in relpaths:
        dst = tmp_path / "reference" / "greenops" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REFERENCE / rel, dst)
    return Settings(data_dir=tmp_path)


def test_derivation_validates_and_is_never_metered(repo_settings: Settings) -> None:
    report = derive_footprint(repo_settings)
    report.assert_no_verified()  # the core discipline: our own footprint is modeled, not metered
    values = report.all_values()
    assert values
    assert all(v.source in {"reference", "derived", "assumption"} for v in values)
    assert not any(v.verified for v in values)


def test_compute_electricity_water_chain(repo_settings: Settings) -> None:
    report = derive_footprint(repo_settings)
    headline = {h.key: h.value for h in report.headline}

    # Compute: AWS EC2 t3.medium (1464 hr x 2 vCPU) + OpenSearch t3.small (1464 x 2) +
    # GitHub Actions (Linux 12000/60x2 + Windows 2400/60x2 + macOS 600/60x3) = 6366 vCPU-hrs.
    assert headline["compute"].value == pytest.approx(6366.0)
    assert headline["compute"].source == "derived"

    # Electricity: vCPU-hrs x 7 W/vCPU x PUE 1.2, Wh → MWh.
    assert headline["electricity"].value == pytest.approx(6366 * 7.0 * 1.2 / 1_000_000, rel=1e-3)

    # Monthly series sums (about) to the annual total, and the source mix splits the total.
    monthly_total = sum(m.value.value for m in report.electricity.monthly)
    assert monthly_total == pytest.approx(headline["electricity"].value, rel=0.02)
    mix_total = report.electricity.grid.value + report.electricity.renewable.value
    assert mix_total == pytest.approx(headline["electricity"].value, rel=1e-6)
    # SRVC renewables share is 9.9% — the renewable slice is the smaller one.
    assert report.electricity.renewable.value < report.electricity.grid.value

    # Water: direct (site WUE) + indirect (source WUE), reported on separate bases.
    assert report.water.total == pytest.approx(headline["water"].value, rel=1e-6)
    assert report.water.direct.source == "derived"
    assert report.water.budget_cap.source == "assumption"


def test_ai_count_is_derived_and_by_task_split_is_modeled(repo_settings: Settings) -> None:
    report = derive_footprint(repo_settings)
    ai = {h.key: h.value for h in report.headline}["ai_inferences"]
    # Total tokens (4.25M input + 1.33M output) ÷ 4000 avg tokens/call — a *derived* count.
    assert ai.value == pytest.approx(round(5_580_000 / 4000))
    assert ai.source == "derived"
    # The by-task donut is a modeled split until per-task keys are named — every slice asserted.
    assert report.ai_by_task.tasks
    assert all(t.value.source == "assumption" for t in report.ai_by_task.tasks)


def test_ccft_reconciliation_is_noted(repo_settings: Settings) -> None:
    report = derive_footprint(repo_settings)
    carbon = next(m.body for m in report.methodology if m.title == "Electricity & carbon")
    # The derivation reconciles derived CO2e against AWS's location-based estimate.
    assert "MTCO2e" in carbon
    assert "AWS" in carbon and "location-based" in carbon


def test_committed_footprint_yaml_is_in_sync(repo_settings: Settings) -> None:
    """The committed artifact equals a fresh derivation — regenerate with `greenops footprint`."""
    committed = load_footprint(footprint_reference_path(repo_settings))
    assert committed == derive_footprint(repo_settings)


def test_missing_sources_degrade_to_assumptions(tmp_path: Path) -> None:
    """An empty data dir (no exports on disk) still yields a valid, fully-modeled report."""
    report = derive_footprint(Settings(data_dir=tmp_path))
    report.assert_no_verified()
    # Nothing wired — every figure degrades to a stated assumption, none derived/metered.
    assert all(v.source == "assumption" for v in report.all_values())
    assert "not wired" in report.note


def test_compute_wired_with_only_aws(tmp_path: Path) -> None:
    """AWS present, GitHub absent: compute stays derived and the CI path is simply skipped."""
    report = derive_footprint(_settings_with(tmp_path, "aws-costs.yaml"))
    compute = {h.key: h.value for h in report.headline}["compute"]
    assert compute.source == "derived"  # a single wired source keeps compute wired, not assumption
    # EC2 t3.medium (1464 x 2) + OpenSearch t3.small (1464 x 2) = 5856 vCPU-hrs; no CI minutes.
    assert compute.value == pytest.approx(5856.0)
    assert not any(f.label == "CI/CD" for f in report.compute_by_function.functions)


def test_compute_wired_with_only_github(tmp_path: Path) -> None:
    """GitHub present, AWS absent: compute stays derived off the Actions-minutes path alone."""
    report = derive_footprint(_settings_with(tmp_path, "github-usage.yaml"))
    compute = {h.key: h.value for h in report.headline}["compute"]
    assert compute.source == "derived"
    # Linux 12000/60x2 + Windows 2400/60x2 + macOS 600/60x3 = 510 vCPU-hrs, all under CI/CD.
    assert compute.value == pytest.approx(510.0)
    assert [f.label for f in report.compute_by_function.functions] == ["CI/CD"]


def test_vcpu_and_runner_helpers() -> None:
    assert _vcpu_for_usage_type("BoxUsage:t3.medium") == 2
    assert _vcpu_for_usage_type("ESInstance:t3.small") == 2
    assert _vcpu_for_usage_type("BoxUsage:c5.xlarge") == 4
    assert _vcpu_for_usage_type("BoxUsage:m5.4xlarge") == 16
    assert _vcpu_for_usage_type("BoxUsage:weird.unknown") == 2  # default
    assert _runner_cores("Actions Linux") == 2
    assert _runner_cores("Actions macOS") == 3
    assert _runner_cores("Actions Linux 8-core") == 8


# --- H3/#1645: the scale oracle the formula tests couldn't be ---------------------------------


def test_committed_footprint_is_fixture_scale_not_platform_scale(repo_settings: Settings) -> None:
    """The committed exports are sample-sized, and the headline figures say so out loud.

    Every other test here asserts the derivation is *internally consistent* — 6366 vCPU-hrs times
    the stated W/vCPU and PUE. All of them pass on the current ~53 kWh/yr electricity total, which
    is roughly a household refrigerator for a month and cannot be a year of running this platform.
    That is not a derivation bug; it is GP-F/F3 (#1643, open): ``data/reference/greenops/*`` holds
    sample/fixture exports, so the figures downstream are fixture-scale by construction.

    This test refuses to let that read as a real footprint by accident. It fails in **both**
    directions: if the numbers stay fixture-scale after #1643 says they are real, and — more
    usefully — the moment a genuine export lands and the totals jump, forcing whoever lands it to
    come back here and to `/about/sustainability` and state which regime the page is describing.
    """
    headline = {h.key: h.value for h in derive_footprint(repo_settings).headline}
    electricity_kwh = headline["electricity"].value * 1000.0  # the headline is MWh

    # A real always-on platform is at minimum tens of MWh/yr. This is three orders below that.
    assert electricity_kwh < 1_000.0, (
        f"electricity is {electricity_kwh:.0f} kWh/yr — no longer fixture-scale. If the committed "
        "greenops exports are now real (GP-F/#1643), delete this test and give the sustainability "
        "page a plausibility band; do not simply widen the bound."
    )
    # Sanity in the other direction: fixture-scale is still a positive, finite, ordered chain.
    assert electricity_kwh > 0.0
    assert headline["compute"].value > 0.0
    assert headline["water"].value > 0.0
    assert headline["ai_inferences"].value > 0.0


def test_headline_units_are_internally_ordered(repo_settings: Settings) -> None:
    """Unit-slip oracle: the chain's magnitudes must keep their expected ordering.

    Independent of absolute scale — this survives the fixture→real cutover above. vCPU-hours are
    a much larger number than the MWh they imply (a vCPU is single-digit watts), and the modeled
    water total is larger than the MWh figure (litres per kWh is > 1). A MW↔kW or Wh↔MWh slip in
    the derivation inverts one of these long before it changes any formula test.
    """
    report = derive_footprint(repo_settings)
    headline = {h.key: h.value for h in report.headline}
    assert headline["compute"].value > headline["electricity"].value * 1000.0
    assert headline["water"].value > headline["electricity"].value
    # The two water bases are reported separately and never summed across bases.
    assert report.water.direct.unit == report.water.indirect.unit
    assert report.water.total == pytest.approx(
        report.water.direct.value + report.water.indirect.value, rel=1e-6
    )
