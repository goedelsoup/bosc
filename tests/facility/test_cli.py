"""The `watermark compute` CLI command (offline, deterministic)."""

from __future__ import annotations

import os

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


def test_compute_command_renders_all_three_water_bound_cases() -> None:
    """#1641 D4: the cooling-water back-solve renders in three shapes by archetype, and the
    "the loop closes" agreement line appears ONLY when a low water bound exists (full range).

    * Lima (evaporative) — both bounds present: full range + loop-closes.
    * Fort Wayne (unknown) — low None, high present: upper-bound-only, no loop-closes.
    * Urbana (closed_loop_dry) — both None: not-applicable, no loop-closes.

    Each site is asserted for its complete method-2 message and the presence/absence of the
    loop-closes line, not just the labels.
    """
    from watermark.config import get_settings

    def run(slug: str) -> str:
        # get_settings is lru_cache(maxsize=1) — clear it so `--site` re-resolves per invoke,
        # and normalize rich's line-wrapping so wrapped phrases match as substrings.
        get_settings.cache_clear()
        result = runner.invoke(app, ["--site", slug, "compute"])
        assert result.exit_code == 0, result.output
        return " ".join(result.output.split())

    saved_site = os.environ.get("WATERMARK_SITE")
    try:
        # Full range (Lima): both water bounds -> low "recovers #1" .. high upper bound, and the
        # power/water-low agreement footer ("the loop closes") is present.
        lima = run("lima")
        assert "cooling-water back-solve:" in lima
        assert "(low, recovers #1)" in lima
        assert "(upper bound; shares the WUE assumption)" in lima
        assert "the loop closes" in lima
        assert "power, not floor space, is the binding constraint" in lima

        # Upper-only (Fort Wayne, unknown): the dry lower bound is None, so only the evaporative
        # upper bound prints, and the loop-closes line is REPLACED by the "does not bound" footer.
        fw = run("fort-wayne")
        assert "cooling-water back-solve: upper bound only" in fw
        assert "does not bound the low; #1641 D4" in fw
        assert "the loop closes" not in fw
        assert "the cooling-water back-solve does not bound a dry/undisclosed-method campus" in fw

        # Not applicable (Urbana, closed_loop_dry): both bounds are None -> the method is N/A and
        # the loop-closes line is absent.
        urbana = run("urbana")
        assert "cooling-water back-solve: not applicable" in urbana
        assert "consumes ~0 cooling water" in urbana
        assert "the loop closes" not in urbana
        assert (
            "the cooling-water back-solve does not bound a dry/undisclosed-method campus" in urbana
        )
    finally:
        get_settings.cache_clear()
        if saved_site is None:
            os.environ.pop("WATERMARK_SITE", None)
        else:
            os.environ["WATERMARK_SITE"] = saved_site
