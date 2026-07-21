"""The `watermark compute` CLI command (offline, deterministic)."""

from __future__ import annotations

from typer.testing import CliRunner

from watermark.cli import app

runner = CliRunner()


def test_compute_command_runs_and_brackets() -> None:
    result = runner.invoke(app, ["compute"])
    assert result.exit_code == 0, result.output
    out = result.output
    # The three estimators and the headline are present.
    assert "three independent estimators" in out
    assert "power basis" in out and "primary" in out
    assert "cooling-water back-solve" in out
    assert "footprint" in out
    # The equivalent-H100 cross-scenario figure and at least one TPU scenario row.
    assert "Equivalent H100-class GPUs" in out
    assert "H100-class" in out
    assert "TPU" in out
    # The no-overclaim caveat footer.
    assert "UNDISCLOSED" in out


def test_compute_command_honors_overrides() -> None:
    result = runner.invoke(
        app,
        ["compute", "--accel-fraction-low", "0.3", "--accel-fraction-high", "0.4", "--mfu", "0.3"],
    )
    assert result.exit_code == 0, result.output
    assert "MFU=0.3" in result.output
