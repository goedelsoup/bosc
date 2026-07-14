"""Hermetic CLI tests for ``watermark research run/publish`` — the publish gate + gh robustness.

No live agent, no network: ``run_research`` is monkeypatched to a fixed manifest and every
``gh`` call is stubbed at ``subprocess.run``. Covers #1367 — the ``site-onboard`` recipe must
*not* auto-open GitHub issues without an explicit ``--create-issues`` opt-in, and a missing
``gh`` / mid-batch failure must render cleanly and record what got created.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from watermark.cli import app
from watermark.config import Settings
from watermark.research import (
    IssueProposal,
    ResearchRunManifest,
    RunProvenance,
    write_run,
)

runner = CliRunner()


def _manifest(n: int = 2) -> ResearchRunManifest:
    props = [
        IssueProposal(
            title=f"Onboard proposal {i}",
            body=f"Body {i}.",
            labels=["extraction"],
            rationale="r",
            dedupe_key=f"onboard-proposal-{i}",
        )
        for i in range(n)
    ]
    prov = RunProvenance(
        topic="onboard fw",
        model="m",
        generated_at="2026-06-10T12:00:00+00:00",
        is_error=False,
    )
    return ResearchRunManifest(provenance=prov, findings="Findings.", proposals=props)


def _patch_run_research(monkeypatch: pytest.MonkeyPatch, manifest: ResearchRunManifest) -> None:
    async def _fake(*_args: object, **_kwargs: object) -> ResearchRunManifest:
        return manifest

    monkeypatch.setattr("watermark.research.run_research", _fake)


# ---------------------------------------------------------------------------
# The gate: site-onboard previews by default, never auto-opens issues (#1367)
# ---------------------------------------------------------------------------


def test_site_onboard_default_writes_plan_and_never_touches_gh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_run_research(monkeypatch, _manifest(2))

    def _boom(*args: object, **_kwargs: object) -> object:
        raise AssertionError(f"gh must not run without --create-issues: {args!r}")

    monkeypatch.setattr("watermark.cli.research.subprocess.run", _boom)

    out_dir = tmp_path / "run"
    result = runner.invoke(
        app, ["research", "run", "--recipe", "site-onboard", "--out", str(out_dir)]
    )

    assert result.exit_code == 0, result.output
    assert (out_dir / "publish-plan.json").exists()
    assert not (out_dir / "publish-result.json").exists()  # nothing opened
    assert "Preview only" in result.output
    assert "--create-issues" in result.output


def test_site_onboard_create_issues_invokes_the_publisher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_run_research(monkeypatch, _manifest(1))

    calls: list[tuple[Path, str]] = []

    def _spy(out_dir: Path, *, site: str, **_kwargs: object) -> None:
        calls.append((out_dir, site))

    monkeypatch.setattr("watermark.cli.research._publish_and_create_issues", _spy)

    out_dir = tmp_path / "run"
    result = runner.invoke(
        app,
        ["research", "run", "--recipe", "site-onboard", "--out", str(out_dir), "--create-issues"],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(out_dir, "lima")]
    assert "Preview only" not in result.output


# ---------------------------------------------------------------------------
# gh robustness — missing binary and mid-batch failures
# ---------------------------------------------------------------------------


def test_missing_gh_renders_clean_message_not_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_run_research(monkeypatch, _manifest(1))

    def _no_gh(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError(2, "No such file or directory", "gh")

    monkeypatch.setattr("watermark.cli.research.subprocess.run", _no_gh)

    result = runner.invoke(
        app,
        [
            "research",
            "run",
            "--recipe",
            "site-onboard",
            "--out",
            str(tmp_path / "run"),
            "--create-issues",
        ],
    )

    assert result.exit_code == 1
    assert "`gh`" in result.output and "not found" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def _fake_gh_factory(
    create_outcomes: list[str | Exception],
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """A ``subprocess.run`` stub that dispatches on the gh subcommand.

    ``issue list`` → no open issues; ``label list`` → ``site:lima`` already exists;
    ``issue create`` → pops the next entry from ``create_outcomes`` (a URL string to
    succeed, or an exception instance to raise).
    """
    creates = iter(create_outcomes)

    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        sub = cmd[1:3]
        if sub == ["issue", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        if sub == ["label", "list"]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps([{"name": "site:lima"}]), stderr=""
            )
        if sub == ["issue", "create"]:
            outcome = next(creates)
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(cmd, 0, stdout=outcome + "\n", stderr="")
        raise AssertionError(f"unexpected gh call: {cmd!r}")

    return _run


def test_mid_batch_failure_records_partial_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from watermark.cli.research import _publish_and_create_issues

    out_dir = tmp_path / "run"
    write_run(_manifest(2), out_dir, settings=Settings(data_dir=tmp_path / "data"))

    monkeypatch.setattr(
        "watermark.cli.research.subprocess.run",
        _fake_gh_factory(
            [
                "https://github.com/x/y/issues/1",
                subprocess.CalledProcessError(1, ["gh"], output="", stderr="rate limited"),
            ]
        ),
    )

    with pytest.raises(typer.Exit) as excinfo:
        _publish_and_create_issues(out_dir, site="lima")

    assert excinfo.value.exit_code == 1
    record = json.loads((out_dir / "publish-result.json").read_text(encoding="utf-8"))
    assert record["opened"] == ["https://github.com/x/y/issues/1"]
    assert len(record["failed"]) == 1
    assert record["failed"][0]["title"] == "Onboard proposal 1"
    assert "rate limited" in record["failed"][0]["error"]


def test_label_ensure_failure_does_not_abort_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A label list/create race must not strand the issue batch (parity with the create loop)."""
    from watermark.cli.research import _publish_and_create_issues

    out_dir = tmp_path / "run"
    write_run(_manifest(2), out_dir, settings=Settings(data_dir=tmp_path / "data"))

    creates = iter(["https://x/y/issues/1", "https://x/y/issues/2"])

    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        sub = cmd[1:3]
        if sub == ["issue", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        if sub == ["label", "list"]:  # label absent → the command will try to create it
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        if sub == ["label", "create"]:  # …and creation loses a race
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="label already exists")
        if sub == ["issue", "create"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=next(creates) + "\n", stderr="")
        raise AssertionError(f"unexpected gh call: {cmd!r}")

    monkeypatch.setattr("watermark.cli.research.subprocess.run", _run)

    # No typer.Exit — the batch completes and both issues open despite the label failure.
    _publish_and_create_issues(out_dir, site="lima")

    record = json.loads((out_dir / "publish-result.json").read_text(encoding="utf-8"))
    assert len(record["opened"]) == 2
    assert record["failed"] == []


def test_create_issues_rejected_for_non_site_onboard_recipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--create-issues` only applies to site-onboard — otherwise fail loudly, don't ignore it."""

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("run_research must not be reached — validation should stop first")

    monkeypatch.setattr("watermark.research.run_research", _boom)

    result = runner.invoke(
        app,
        ["research", "run", "--recipe", "issue-proposal", "--topic", "x", "--create-issues"],
    )

    # Exit 2 is the stable contract for a Click usage error and uniquely pins this validation:
    # had it not fired, the command would reach the run_research stub and exit 1 instead. We
    # don't assert on the rendered error text — Typer's Rich error panel wraps/ANSI-styles it
    # differently by terminal width, so a substring match is flaky across environments.
    assert result.exit_code == 2


def test_gh_json_raises_gherror_on_unparseable_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from watermark.cli.research import _gh_json, _GhError

    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="not json at all", stderr="")

    monkeypatch.setattr("watermark.cli.research.subprocess.run", _run)

    with pytest.raises(_GhError, match="unparseable JSON"):
        _gh_json(["issue", "list"])


def test_gh_timeout_becomes_gherror(monkeypatch: pytest.MonkeyPatch) -> None:
    from watermark.cli.research import _gh, _GhError

    def _run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, 60.0)

    monkeypatch.setattr("watermark.cli.research.subprocess.run", _run)

    with pytest.raises(_GhError, match="timed out"):
        _gh(["issue", "list"])
