"""GitHub Actions/storage billing connector (#1081): the reduce is faithful to the raw
enhanced-billing usage report, Actions minutes are split by runner SKU and storage by
product, figures are `reference` (never metered), and an offline miss / missing token both
fail loudly rather than silently.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from watermark.cli import app
from watermark.config import Settings
from watermark.greenops.connectors import (
    GithubBillingError,
    GreenopsOfflineError,
    fetch_github_usage,
    load_github_usage,
    write_github_usage,
)
from watermark.greenops.connectors import github as gh

runner = CliRunner()

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "data" / "reference" / "greenops" / "github-usage.yaml"

# The fixture window (tests/fixtures/greenops/github/) — a fixed trailing-12-months.
WINDOW = ("2025-07-01T00:00:00Z", "2026-07-01T00:00:00Z")


def test_usage_report_reduces_the_raw_report(greenops_settings: Settings) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)
    assert report.period.label == "Jul 2025-Jun 2026"

    # Actions minutes sum every runner across all twelve months (Linux+Windows+macOS).
    assert report.total_minutes.value == 15_000
    assert report.total_minutes.unit == "minutes"

    # Net cost is the sum of every line's netAmount (Actions + storage + Copilot "other").
    assert report.total_cost.value == pytest.approx(871.62)
    assert report.total_cost.unit == "USD"


def test_minutes_split_by_runner_ranked_desc(greenops_settings: Settings) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)

    by_runner = {r.sku: r for r in report.by_runner}
    assert set(by_runner) == {"Actions Linux", "Actions Windows", "Actions macOS"}
    # Ranked by minutes, descending — the vCPU-hrs derivation hangs off the SKU split.
    assert [r.sku for r in report.by_runner] == [
        "Actions Linux",
        "Actions Windows",
        "Actions macOS",
    ]
    assert by_runner["Actions Linux"].minutes.value == 12_000
    assert by_runner["Actions Windows"].minutes.value == 2_400
    assert by_runner["Actions macOS"].minutes.value == 600
    # by_runner minutes reconcile with the headline total.
    assert sum(r.minutes.value for r in report.by_runner) == report.total_minutes.value


def test_storage_grouped_by_product(greenops_settings: Settings) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)

    storage = {s.product: s for s in report.storage}
    # Git LFS, Packages, and Actions artifact storage are the GB-hours lines; ranked by cost.
    assert set(storage) == {"Git LFS", "Packages", "Actions"}
    assert storage["Git LFS"].quantity.value == 600  # 50 GB-hrs/mo x 12
    assert storage["Git LFS"].unit_type == "GigabyteHours"
    assert [s.product for s in report.storage] == ["Actions", "Packages", "Git LFS"]


def test_category_taxonomy_covers_every_line(greenops_settings: Settings) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)
    by_category = {line.category for line in report.lines}
    # Copilot seats are neither compute nor storage — they land in `other`, never dropped.
    assert by_category == {"ci_compute", "storage", "other"}
    minutes_lines = [line for line in report.lines if line.category == "ci_compute"]
    assert all(line.product == "Actions" and "Minute" in line.unit_type for line in minutes_lines)


def test_every_figure_is_reference_never_metered(greenops_settings: Settings) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)
    values = report.all_values()
    assert values
    # A billing export is authoritative but not a metered fact about our own consumption.
    assert all(v.source == "reference" for v in values)
    assert not any(v.verified for v in values)


def test_offline_miss_raises(greenops_settings: Settings) -> None:
    with pytest.raises(GreenopsOfflineError):
        fetch_github_usage(
            "2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z", settings=greenops_settings
        )


def test_live_pull_without_token_raises() -> None:
    # Not offline + no GITHUB_TOKEN => a clear error, not a cryptic 401.
    settings = Settings(data_dir=REPO_ROOT / "data", github_token="")
    with pytest.raises(GithubBillingError, match="GITHUB_TOKEN"):
        fetch_github_usage(*WINDOW, settings=settings)


def test_http_error_wraps_as_billing_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A non-2xx billing response (e.g. 403 from insufficient permissions) degrades via
    # GithubBillingError, not a raw httpx.HTTPStatusError the greenops assembly won't catch.
    request = httpx.Request("GET", "https://api.github.com/organizations/x/settings/billing/usage")
    response = httpx.Response(403, json={"message": "Resource protected"}, request=request)
    monkeypatch.setattr(gh.httpx, "get", lambda *a, **k: response)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")  # alias-only field; set via env, not kwarg
    settings = Settings(data_dir=tmp_path, github_billing_org="x")
    with pytest.raises(GithubBillingError, match="403"):
        fetch_github_usage(*WINDOW, settings=settings)


def test_offline_write_is_refused() -> None:
    # --offline serves fixture-derived data; writing it would clobber the committed reference
    # artifact, so the combination is refused before any fetch/write happens.
    result = runner.invoke(app, ["greenops", "github", "--offline", "--write"])
    assert result.exit_code != 0
    assert "overwrite" in result.output.lower()


def test_committed_reference_round_trips(greenops_settings: Settings, tmp_path: Path) -> None:
    report = fetch_github_usage(*WINDOW, settings=greenops_settings)
    out = write_github_usage(report, settings=Settings(data_dir=tmp_path))
    assert load_github_usage(out) == report
    assert (out.parent / "README.md").is_file()


def test_committed_reference_artifact_validates() -> None:
    """The committed data/reference YAML loads and stays `reference`-only."""
    report = load_github_usage(REFERENCE)
    report_values = report.all_values()
    assert report_values
    assert all(v.source == "reference" for v in report_values)
