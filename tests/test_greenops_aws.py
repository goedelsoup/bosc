"""AWS cost + carbon connector (#1079): the reduce is faithful to the raw payloads, group
values are read by name (via GroupDefinitions), the function fold never drops a service,
figures are `reference` (never metered), and an offline miss / missing credentials both
fail loudly rather than silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.greenops.connectors import (
    AwsCredentialsError,
    GreenopsOfflineError,
    fetch_aws_carbon,
    fetch_aws_costs,
    load_aws_carbon,
    load_aws_costs,
    write_aws_carbon,
    write_aws_costs,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "data" / "reference" / "greenops"

# The fixture window (tests/fixtures/greenops/aws/) — a fixed trailing-12-months.
WINDOW = ("2025-07-01T00:00:00Z", "2026-07-01T00:00:00Z")


def test_cost_report_reduces_the_raw_payload(greenops_settings: Settings) -> None:
    report = fetch_aws_costs(*WINDOW, settings=greenops_settings)
    assert report.period.label == "Jul 2025-Jun 2026"

    # Total is the sum of every (service, usage type) group across the monthly buckets.
    assert report.total_cost.value == pytest.approx(207.5)
    assert report.total_cost.unit == "USD"

    # Lines are read by name via GroupDefinitions and summed across buckets.
    lines = {(line.service, line.usage_type): line for line in report.lines}
    ec2 = lines[("Amazon Elastic Compute Cloud - Compute", "BoxUsage:t3.medium")]
    assert ec2.cost.value == pytest.approx(82.5)
    assert ec2.usage_amount == pytest.approx(1464)  # 720 + 744 across two months
    assert ec2.usage_unit == "Hrs"
    assert ec2.function == "hosting"
    # Lines are ranked by cost, descending.
    assert report.lines[0].service == "Amazon Elastic Compute Cloud - Compute"


def test_cost_fold_by_function_never_drops_a_service(greenops_settings: Settings) -> None:
    report = fetch_aws_costs(*WINDOW, settings=greenops_settings)

    by_function = {f.function: f for f in report.by_function}
    # Ranked by cost, descending.
    assert [f.function for f in report.by_function] == [
        "hosting",
        "search",
        "storage",
        "ai_inference",
        "ingestion",
        "other",
    ]
    assert by_function["hosting"].cost.value == pytest.approx(82.5)
    assert by_function["search"].services == ["Amazon OpenSearch Service"]
    # An unmapped service lands in `other` — listed, never dropped.
    assert by_function["other"].services == ["AWS Key Management Service"]
    assert by_function["other"].cost.value == pytest.approx(2.0)
    # The fold loses nothing: function costs sum back to the total.
    assert sum(f.cost.value for f in report.by_function) == pytest.approx(report.total_cost.value)


def test_carbon_report_reduces_the_raw_payload(greenops_settings: Settings) -> None:
    report = fetch_aws_carbon(*WINDOW, settings=greenops_settings)
    assert report.period.label == "Jul 2025-Jun 2026"

    # Totals sum the monthly series, both GHG-Protocol methods, in AWS's own unit.
    assert report.mbm_total.value == pytest.approx(0.018)
    assert report.lbm_total.value == pytest.approx(0.045)
    assert report.mbm_total.unit == "MTCO2e"
    assert report.model_version == "v3.0.0"

    # The emissions series lags the request window (~3 months): the fixture's twelve-month
    # window yields nine published months, ending 2026-03 — the report must not pad them.
    assert len(report.monthly) == 9
    assert report.monthly[0].month == "2025-07"
    assert report.monthly[-1].month == "2026-03"
    assert report.monthly[-1].lbm_emissions.value == pytest.approx(0.005)

    # No electricity figure exists in the payload, so none may appear here.
    assert all(v.unit == "MTCO2e" for v in report.all_values())


def test_every_figure_is_reference_never_metered(greenops_settings: Settings) -> None:
    costs = fetch_aws_costs(*WINDOW, settings=greenops_settings)
    carbon = fetch_aws_carbon(*WINDOW, settings=greenops_settings)
    values = costs.all_values() + carbon.all_values()
    assert values
    # A billing/emissions export is authoritative but not a metered fact about us.
    assert all(v.source == "reference" for v in values)
    assert not any(v.verified for v in values)


def test_offline_miss_raises(greenops_settings: Settings) -> None:
    with pytest.raises(GreenopsOfflineError):
        fetch_aws_costs("2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z", settings=greenops_settings)
    with pytest.raises(GreenopsOfflineError):
        fetch_aws_carbon("2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z", settings=greenops_settings)


def test_live_pull_without_credentials_raises(tmp_path: Path) -> None:
    # Not offline + no AWS keys => a clear error, not a cryptic HTTP failure.
    settings = Settings(data_dir=tmp_path, aws_access_key_id="", aws_secret_access_key="")
    with pytest.raises(AwsCredentialsError, match="AWS_ACCESS_KEY_ID"):
        fetch_aws_costs(*WINDOW, settings=settings)
    with pytest.raises(AwsCredentialsError, match="AWS_ACCESS_KEY_ID"):
        fetch_aws_carbon(*WINDOW, settings=settings)


def test_committed_reference_round_trips(greenops_settings: Settings, tmp_path: Path) -> None:
    costs = fetch_aws_costs(*WINDOW, settings=greenops_settings)
    carbon = fetch_aws_carbon(*WINDOW, settings=greenops_settings)
    out_settings = Settings(data_dir=tmp_path)
    costs_path = write_aws_costs(costs, settings=out_settings)
    carbon_path = write_aws_carbon(carbon, settings=out_settings)
    assert load_aws_costs(costs_path) == costs
    assert load_aws_carbon(carbon_path) == carbon
    assert (costs_path.parent / "README.md").is_file()


def test_committed_reference_artifacts_validate() -> None:
    """The committed data/reference YAMLs load and stay `reference`-only."""
    costs = load_aws_costs(REFERENCE / "aws-costs.yaml")
    carbon = load_aws_carbon(REFERENCE / "aws-carbon.yaml")
    values = costs.all_values() + carbon.all_values()
    assert values
    assert all(v.source == "reference" for v in values)
