"""Anthropic Admin usage/cost connector (#1078): the reduce is faithful to the raw reports,
attribution by model + workspace is present, figures are `reference` (never metered), and an
offline miss / missing key both fail loudly rather than silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.greenops.connectors import (
    AnthropicAdminError,
    GreenopsOfflineError,
    fetch_anthropic_usage,
    load_anthropic_usage,
    write_anthropic_usage,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE = REPO_ROOT / "data" / "reference" / "greenops" / "anthropic-usage.yaml"

# The fixture window (tests/fixtures/greenops/anthropic/) — a fixed trailing-12-months.
WINDOW = ("2025-07-01T00:00:00Z", "2026-07-01T00:00:00Z")


def test_usage_report_reduces_the_raw_reports(greenops_settings: Settings) -> None:
    report = fetch_anthropic_usage(*WINDOW, settings=greenops_settings)
    assert report.period.label == "Jul 2025-Jun 2026"

    # Token totals sum every bucket's results (uncached + cache-create + cache-read for input).
    assert report.input_tokens.value == 4_250_000
    assert report.output_tokens.value == 1_330_000
    assert report.cache_read_input_tokens.value == 450_000
    assert report.cache_creation_input_tokens.value == 200_000
    # The one real request count the API exposes — web-search server-tool calls.
    assert report.web_search_requests.value == 60
    assert report.web_search_requests.unit == "requests"

    # Cost is the sum of every cost row, converted cents -> USD.
    # 5200.50 + 3100 + 300 + 2600 + 1450 cents = 12650.50c => $126.505 -> $126.5.
    assert report.total_cost.value == pytest.approx(126.5)
    assert report.total_cost.unit == "USD"


def test_attribution_by_model_and_workspace(greenops_settings: Settings) -> None:
    report = fetch_anthropic_usage(*WINDOW, settings=greenops_settings)

    by_model = {m.model: m for m in report.by_model}
    assert set(by_model) == {"claude-opus-4-8", "claude-sonnet-4-6"}
    # by_model is ranked by total token volume, descending (sonnet outweighs opus here).
    assert [m.model for m in report.by_model] == ["claude-sonnet-4-6", "claude-opus-4-8"]
    assert by_model["claude-opus-4-8"].input_tokens == 1_850_000
    assert by_model["claude-opus-4-8"].output_tokens == 380_000
    # Opus cost = 5200.50 (input) + 2600 (output) cents = $78.005 -> $78.0.
    assert by_model["claude-opus-4-8"].cost.value == pytest.approx(78.0)

    # Workspace attribution is present (what the by-task donut hangs off, #4/#1083).
    by_ws = {w.workspace_id: w for w in report.by_workspace}
    assert "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ" in by_ws
    assert "wrkspc_01XYZ789ABC123DEF456MNO0" in by_ws
    assert sum(w.input_tokens for w in report.by_workspace) == report.input_tokens.value


def test_every_figure_is_reference_never_metered(greenops_settings: Settings) -> None:
    report = fetch_anthropic_usage(*WINDOW, settings=greenops_settings)
    values = report.all_values()
    assert values
    # A usage/billing export is authoritative but not a metered fact about our consumption.
    assert all(v.source == "reference" for v in values)
    assert not any(v.verified for v in values)


def test_offline_miss_raises(greenops_settings: Settings) -> None:
    with pytest.raises(GreenopsOfflineError):
        fetch_anthropic_usage(
            "2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z", settings=greenops_settings
        )


def test_live_pull_without_admin_key_raises() -> None:
    # Not offline + no ANTHROPIC_ADMIN_KEY => a clear error, not a cryptic 401.
    settings = Settings(data_dir=REPO_ROOT / "data", anthropic_admin_key="")
    with pytest.raises(AnthropicAdminError, match="ANTHROPIC_ADMIN_KEY"):
        fetch_anthropic_usage(*WINDOW, settings=settings)


def test_committed_reference_round_trips(greenops_settings: Settings, tmp_path: Path) -> None:
    report = fetch_anthropic_usage(*WINDOW, settings=greenops_settings)
    out = write_anthropic_usage(report, settings=Settings(data_dir=tmp_path))
    assert load_anthropic_usage(out) == report
    assert (out.parent / "README.md").is_file()


def test_committed_reference_artifact_validates() -> None:
    """The committed data/reference YAML loads and stays `reference`-only."""
    report = load_anthropic_usage(REFERENCE)
    report_values = report.all_values()
    assert report_values
    assert all(v.source == "reference" for v in report_values)
