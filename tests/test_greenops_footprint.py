"""GreenOps footprint derivation (#1083 / #1643): the usage → electricity → CO2e → water
assembly is faithful to the committed connector exports + factor tables, every figure stays
modeled (never metered), and a missing source degrades to a stated assumption rather than
fabricating or crashing.

The #1643 (GP-F) tests are grouped at the bottom and each name the finding it pins: carbon as a
first-class dual-method figure (F1), inference energy in the chain (F2), the illustrative /
measured basis and its plausibility bounds (F3), the water boundary and basis composition (F4),
and the coefficient bands + per-fleet grid attribution (F5).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.connectors import cached_get_traced
from watermark.greenops.footprint import (
    FootprintInputs,
    _Band,
    _inference_energy,
    _runner_cores,
    _vcpu_for_usage_type,
    _water,
    derive_footprint,
    footprint_reference_path,
    load_footprint,
    load_footprint_inputs,
)
from watermark.greenops.model import basis_for_origin

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

    # Electricity is infrastructure + inference (#1643/F2), so it EXCEEDS the vCPU chain alone.
    infra_mwh = 6366 * 7.0 * 1.2 / 1_000_000
    assert report.energy is not None
    assert report.energy.infrastructure.value == pytest.approx(infra_mwh, rel=1e-3)
    assert report.energy.inference.value > 0.0
    assert headline["electricity"].value == pytest.approx(
        report.energy.infrastructure.value + report.energy.inference.value, rel=1e-3
    )

    # Monthly series sums (about) to the annual total, and the source mix splits the total.
    monthly_total = sum(m.value.value for m in report.electricity.monthly)
    assert monthly_total == pytest.approx(headline["electricity"].value, rel=0.02)
    mix_total = report.electricity.grid.value + report.electricity.renewable.value
    assert mix_total == pytest.approx(headline["electricity"].value, rel=1e-6)
    # SRVC renewables share is 9.9% — the renewable slice is the smaller one.
    assert report.electricity.renewable.value < report.electricity.grid.value

    # Water: provider facility cooling (site WUE x IT-kWh) + the upstream generation increment
    # (x facility kWh) — composable bases, so the total is well-formed source-basis (#1643/F4).
    assert report.water.total == pytest.approx(headline["water"].value, rel=1e-6)
    assert report.water.direct.source == "derived"
    assert report.water.budget_cap.source == "assumption"


def test_water_divides_out_pue_and_uses_the_provider_wue(repo_settings: Settings) -> None:
    """F4: a per-IT-kWh benchmark applied to a PUE-inclusive total overstates cooling by the PUE.

    The old chain multiplied the industry-average *site* WUE (1.8 L/kWh, defined per kWh of IT
    load) by the facility total (IT x PUE) and called the result our "direct on-site cooling" —
    on a platform that operates no data center. Both halves are fixed here, and the arithmetic
    is asserted against the two loads explicitly so a future refactor can't quietly re-multiply.
    """
    report = derive_footprint(repo_settings)
    facility_kwh = {h.key: h.value for h in report.headline}["electricity"].value * 1000.0
    it_kwh = facility_kwh / 1.2  # PUE

    # Cooling: our PROVIDER's published site WUE (0.12 L/kWh), applied to IT load only.
    # Absolute tolerances throughout: both the electricity this reads back and the gallons it
    # checks are published rounded, so a relative bound would be measuring the rounding.
    assert report.water.direct.value == pytest.approx(it_kwh * 0.12 / 3.785411784, abs=0.1)
    assert "site WUE" in (report.water.direct.citation or "")
    assert "we operate no data center" in (report.water.direct.citation or "")

    # Upstream: the generation increment (1.9 L/kWh), applied to the WHOLE facility draw — the
    # grid delivered every kWh the facility took, overhead included.
    assert report.water.indirect.value == pytest.approx(facility_kwh * 1.9 / 3.785411784, abs=0.1)


def test_water_refuses_a_wue_row_on_the_wrong_basis(repo_settings: Settings) -> None:
    """F4: summing a site-basis and a source-basis WUE double-counts cooling — so it raises.

    The table's own docstring already said the bases must never be summed; nothing enforced it.
    Re-typing the upstream increment as an already-complete `source` figure is exactly the drift
    that would resurrect the bug, so the derivation refuses rather than silently composing.
    """
    inputs = load_footprint_inputs(repo_settings)
    assert inputs.wue is not None
    for b in inputs.wue.benchmarks:
        if b.facility_type == "grid_upstream":
            b.basis = "source"
    with pytest.raises(ValueError, match="double-counts cooling"):
        _water(_Band(1.0, 1.0, 1.0), inputs, wired=True)


def test_inference_energy_is_priced_on_output_tokens_by_model_class(
    repo_settings: Settings,
) -> None:
    """F2: the dominant scope was missing entirely; this is the arithmetic that adds it.

    Priced per 1,000 **output** tokens (decode dominates; prefill is far cheaper per token), by
    model class, times PUE — the published anchors are accelerator+host, so facility overhead is
    ours to add. The fixture's split is opus 380k output + sonnet 950k output.
    """
    report = derive_footprint(repo_settings)
    assert report.energy is not None
    expected_wh = (380_000 / 1000 * 2.0) + (950_000 / 1000 * 0.6)  # frontier + mid_tier
    # `abs=5e-5` because the published MWh figure is rounded to four decimals.
    assert report.energy.inference.value == pytest.approx(expected_wh * 1.2 / 1_000_000, abs=5e-5)
    # It is an estimate over published third-party figures, and says so both ways.
    assert report.energy.inference.source == "derived"
    assert report.energy.inference.confidence == "low"
    assert "output token" in (report.energy.inference.citation or "")
    # The band is not decoration — it must actually straddle the central value.
    assert report.energy.inference.low is not None
    assert report.energy.inference.low < report.energy.inference.value
    assert (report.energy.inference.high or 0) > report.energy.inference.value


def test_carbon_is_a_first_class_figure_with_dual_method_reporting(
    repo_settings: Settings,
) -> None:
    """F1: eGRID exists to produce this number, and the page reported everything but it."""
    report = derive_footprint(repo_settings)
    assert report.carbon is not None
    carbon = report.carbon

    # Our own model, priced at the configured subregion's output rate.
    assert carbon.subregion == "SRVC"
    assert carbon.derived_location_based.source == "derived"
    assert carbon.derived_location_based.unit == "MTCO2e"
    assert carbon.derived_location_based.value > 0

    # The provider's own totals — read from aws-carbon.yaml and, until now, never surfaced.
    assert carbon.provider_location_based is not None
    assert carbon.provider_location_based.value == pytest.approx(0.045)
    assert carbon.market_based is not None
    assert carbon.market_based.value == pytest.approx(0.018)
    # Market-based is the procurement figure; it must never be the one standing alone.
    assert carbon.market_based.value < carbon.provider_location_based.value
    assert "market-based" in carbon.reconciliation and "location-based" in carbon.reconciliation

    # And it reaches the page as a headline, not only as prose.
    headline = {h.key: h.value for h in report.headline}
    assert headline["carbon"].value == pytest.approx(carbon.derived_location_based.value)


def test_ci_is_priced_on_its_own_grid_not_the_cloud_one(repo_settings: Settings) -> None:
    """F5: GitHub-hosted runners are Azure VMs; folding them in attributed CI to AWS's grid.

    Both subregions resolve to SRVC today (Azure East US 2 and AWS us-east-1 are both in
    Virginia), so this asserts the *mechanism* — that a re-pointed CI region actually moves the
    CI share onto a different emission rate — rather than a number that happens to coincide.
    """
    baseline = derive_footprint(repo_settings)
    assert baseline.carbon is not None

    # RFCW (RFC West) is a dirtier grid than SRVC, so moving CI onto it must raise the total.
    moved = derive_footprint(
        Settings(data_dir=repo_settings.data_dir, greenops_ci_grid_subregion="RFCW")
    )
    assert moved.carbon is not None
    assert moved.carbon.derived_location_based.value > baseline.carbon.derived_location_based.value
    assert "RFCW" in (moved.carbon.derived_location_based.citation or "")


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


def test_inference_only_wiring_still_produces_a_footprint(tmp_path: Path) -> None:
    """F2: the two energy scopes degrade independently — inference alone is a real footprint.

    Folding inference into the chain would be a regression if it could only exist alongside a
    billing export: the Anthropic export plus the coefficient table is a complete, if partial,
    story, and it must reach electricity / carbon / water on its own. The infrastructure half
    stays a stated assumption rather than a `derived` zero, which would read as a measurement.
    """
    settings = _settings_with(tmp_path, "anthropic-usage.yaml")
    for rel in (
        "factors/egrid-2023.yaml",
        "factors/wue-benchmarks.yaml",
        "factors/inference-energy.yaml",
    ):
        dst = tmp_path / "reference" / "greenops" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REFERENCE / rel, dst)

    report = derive_footprint(settings)
    report.assert_no_verified()
    assert report.energy is not None
    assert report.energy.inference.source == "derived"
    assert report.energy.inference.value > 0
    assert report.energy.infrastructure.source == "assumption"  # not a derived zero
    headline = {h.key: h.value for h in report.headline}
    assert headline["electricity"].value == pytest.approx(report.energy.inference.value)
    assert headline["water"].value > 0
    assert report.carbon is not None and report.carbon.derived_location_based.value > 0


def test_output_tokens_outside_the_by_model_split_are_priced_not_dropped(
    repo_settings: Settings,
) -> None:
    """F2: silently omitting unattributed tokens would understate the very scope this adds.

    A provider export can report a total that its by-model breakdown doesn't fully account for
    (a model missing from the split, or no split at all). Those tokens are priced at the table's
    conservative default class and named in the citation, rather than falling out of the chain.
    """
    inputs = load_footprint_inputs(repo_settings)
    assert inputs.anthropic is not None
    baseline, _, _ = _inference_energy(inputs)

    inputs.anthropic.by_model = []  # the whole total is now unattributed
    widened, _, notes = _inference_energy(inputs)
    assert widened.value > baseline.value  # frontier default > the fixture's sonnet-heavy mix
    assert any("not in the by-model split" in n for n in notes)


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


def test_committed_report_declares_itself_illustrative(repo_settings: Settings) -> None:
    """F3: the committed exports are samples, and the artifact says so in a machine-readable way.

    The predecessor of this test asserted electricity stayed under 1,000 kWh/yr — a scale oracle
    standing in for a marker that didn't exist. The marker exists now, so the scale bound is not
    the guard: ``basis`` is, and it is composed from the exports rather than asserted here.
    """
    report = derive_footprint(repo_settings)
    assert report.basis == "illustrative"
    assert "ILLUSTRATIVE" in report.note
    # Every usage export votes, and none of them is a live pull today.
    inputs = load_footprint_inputs(repo_settings)
    assert inputs.aws_costs is not None and inputs.aws_costs.basis == "illustrative"
    assert inputs.github is not None and inputs.github.basis == "illustrative"
    assert inputs.anthropic is not None and inputs.anthropic.basis == "illustrative"


def test_basis_is_composed_not_asserted(repo_settings: Settings) -> None:
    """F3: one sample export keeps the whole report illustrative — `measured` needs unanimity.

    The failure this prevents is a partial cutover: three real pulls and one stale fixture would
    otherwise publish a `measured` banner over a number a sample is still feeding.
    """
    inputs = load_footprint_inputs(repo_settings)
    for src in (inputs.aws_costs, inputs.aws_carbon, inputs.github, inputs.anthropic):
        assert src is not None
        src.basis = "measured"
    assert inputs.usage_basis() == "measured"

    assert inputs.github is not None
    inputs.github.basis = "illustrative"
    assert inputs.usage_basis() == "illustrative"

    # And a report with nothing wired is illustrative, not vacuously measured.
    assert FootprintInputs().usage_basis() == "illustrative"


def test_basis_is_stamped_from_the_fetch_path(tmp_path: Path) -> None:
    """F3: `illustrative` comes from the connector's own resolution rung, not a hand-set field.

    A fixture replay is a sample; a live fetch and the cache entry it writes are real usage. This
    is the whole mechanism behind the banner, so it is asserted at the cache layer directly.
    """
    calls: list[str] = []

    def fetch() -> dict[str, str]:
        calls.append("live")
        return {"ok": "yes"}

    params = {"connector": "demo", "report": "x"}
    # First call has no cache and is not offline → a live fetch, which is `measured`.
    payload, origin = cached_get_traced("demo", params, fetch, cache_dir=tmp_path)
    assert payload == {"ok": "yes"}
    assert basis_for_origin(origin) == "measured"
    # Second call is served by the entry that write left behind — still real usage.
    _, origin = cached_get_traced("demo", params, fetch, cache_dir=tmp_path)
    assert origin == "cache"
    assert basis_for_origin(origin) == "measured"
    assert calls == ["live"]  # the fetch really only ran once

    # A committed fixture, replayed offline, is a sample.
    fixtures = tmp_path / "fixtures"
    key = next(p for p in (tmp_path / "demo").glob("*.json"))
    (fixtures / "demo").mkdir(parents=True)
    (fixtures / "demo" / key.name).write_text(key.read_text(encoding="utf-8"), encoding="utf-8")
    _, origin = cached_get_traced(
        "demo",
        params,
        fetch,
        cache_dir=tmp_path / "empty",
        offline=True,
        fixtures_dir=fixtures,
    )
    assert origin == "fixture"
    assert basis_for_origin(origin) == "illustrative"


def test_headline_figures_are_within_their_declared_basis_bounds(repo_settings: Settings) -> None:
    """F3: plausibility bounds keyed to what the report CLAIMS to be, not to a frozen magnitude.

    An `illustrative` report may be any size — it is a sample. A `measured` one may not be
    absurd: a real always-on platform draws at least tens of kWh a year, and if it ever claimed
    to draw more than a small data center something upstream is mis-scaled. Bounding by the
    declared basis is what makes this survive the fixture→real cutover instead of being deleted
    at it.
    """
    report = derive_footprint(repo_settings)
    headline = {h.key: h.value for h in report.headline}
    electricity_kwh = headline["electricity"].value * 1000.0

    if report.basis == "measured":
        assert 10.0 < electricity_kwh < 10_000_000.0, (
            f"a MEASURED footprint of {electricity_kwh:.0f} kWh/yr is not plausible for this "
            "platform — check the exports before publishing it"
        )

    # In either regime the chain must stay positive and ordered; a zero is a wiring failure.
    assert electricity_kwh > 0.0
    assert headline["compute"].value > 0.0
    assert headline["water"].value > 0.0
    assert headline["ai_inferences"].value > 0.0
    assert headline["carbon"].value > 0.0


def test_derived_headlines_carry_their_coefficient_bands(repo_settings: Settings) -> None:
    """F5: the bands are published data, not prose — a consumer must be able to read the spread.

    Every coefficient in the chain (W/vCPU, PUE, the WUE rows, the per-token ones) is banded with
    a dated citation, and the band propagates. A central value shipped alone reads more precise
    than the underlying literature supports, which is the false confidence F5 names.
    """
    report = derive_footprint(repo_settings)
    headline = {h.key: h.value for h in report.headline}
    for key in ("electricity", "water", "carbon"):
        pv = headline[key]
        assert pv.low is not None and pv.high is not None, f"{key} lost its band"
        assert pv.low < pv.value < pv.high, f"{key} band does not straddle its central value"


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
