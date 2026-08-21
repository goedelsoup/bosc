"""The report-envelope contract (:mod:`watermark.site.yidam_cli`).

Two halves. The parsing tests are pure — they build envelopes by hand and never shell out, so
they run on a checkout with no Rust toolchain. The conformance tests run the real binary and
skip without it; CI installs it, so they are a live gate there.

The thing these guard is the reason the Python replica was retired: a consumer that reads a
verdict it does not actually understand is worse than one that has no verdict at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from watermark.config import Settings
from watermark.site import yidam_cli
from watermark.site.corpus_mirror import build_mirror, write_mirror

REPO_ROOT = Path(__file__).resolve().parents[1]


def _envelope(**body: Any) -> dict[str, Any]:
    """A well-formed envelope with the command-specific fields spliced in."""
    return {
        "format_version": "1",
        "yidam": {"version": "0.1.0", "commit": "2930415", "features": ["reports"]},
        "root": "/repo",
        **body,
    }


def _parse(monkeypatch: pytest.MonkeyPatch, command: str, payload: dict[str, Any]) -> Any:
    """Run ``run_report`` against a canned stdout instead of a real process."""

    class _Proc:
        stdout = json.dumps(payload)
        stderr = ""
        returncode = 0

    monkeypatch.setattr(yidam_cli, "yidam_path", lambda: Path("/fake/yidam"))
    monkeypatch.setattr(yidam_cli.subprocess, "run", lambda *a, **k: _Proc())
    return yidam_cli.run_report(command)


# --- the version handshake -----------------------------------------------------------------
def test_unknown_contract_version_degrades_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """The schema's own instruction: an unknown major version MUST NOT be parsed.

    A consumer versions independently of the binary a repo pins, so skew is expected. Reading
    the body anyway is how a changed field silently becomes a wrong verdict.
    """
    bad = _envelope(gate={"passed": True})
    bad["format_version"] = "2"
    with pytest.raises(yidam_cli.YidamContractError, match="contract v2"):
        _parse(monkeypatch, "lint", bad)


def test_missing_json_is_an_error_not_a_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Empty:
        stdout = ""
        stderr = "error: unexpected argument"
        returncode = 2

    monkeypatch.setattr(yidam_cli, "yidam_path", lambda: Path("/fake/yidam"))
    monkeypatch.setattr(yidam_cli.subprocess, "run", lambda *a, **k: _Empty())
    with pytest.raises(yidam_cli.YidamContractError, match="no JSON"):
        yidam_cli.run_report("lint")


def test_absent_binary_raises_with_the_remedy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yidam_cli, "yidam_path", lambda: None)
    with pytest.raises(yidam_cli.YidamUnavailableError, match="mise run yidam-build"):
        yidam_cli.run_report("graph-check")


def test_build_block_reports_the_feature_set(monkeypatch: pytest.MonkeyPatch) -> None:
    report = _parse(monkeypatch, "graph-check", _envelope(passed=True))
    assert report.build.commit == "2930415"
    assert report.build.is_light  # the `reports` build CI pins — no index/serve


# --- usability is provenance, not flag support ----------------------------------------------
def _usable_with(monkeypatch: pytest.MonkeyPatch, stdout: str) -> bool:
    class _Proc:
        returncode = 0

    _Proc.stdout = stdout  # type: ignore[attr-defined]
    monkeypatch.setattr(yidam_cli, "yidam_path", lambda root=None: Path("/fake/yidam"))
    monkeypatch.setattr(yidam_cli.subprocess, "run", lambda *a, **k: _Proc())
    monkeypatch.setattr(yidam_cli, "pinned_commit", lambda root=None: "f05b62042e2228f0091")
    yidam_cli.usable.cache_clear()
    try:
        return yidam_cli.usable()
    finally:
        yidam_cli.usable.cache_clear()


def test_a_binary_at_the_pin_is_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _usable_with(
        monkeypatch, json.dumps(_envelope(passed=True)).replace('"2930415"', '"f05b620"')
    )


def test_a_binary_off_the_pin_is_not_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case a flag probe cannot see.

    A binary from another commit answers `--format json` perfectly and then answers questions
    about the *corpus* with whatever it knew at its own commit — upstream's "perfect envelope
    and a wrong payload". It surfaces downstream as a confusing assertion about someone else's
    build, so it counts as unusable and skippable tests skip.
    """
    off_pin = _envelope(passed=True)
    off_pin["yidam"]["commit"] = "7be9ce8"
    assert not _usable_with(monkeypatch, json.dumps(off_pin))


def test_an_unreadable_answer_is_not_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not _usable_with(monkeypatch, "error: unexpected argument '--format' found")


def test_an_unknown_contract_version_is_not_usable(monkeypatch: pytest.MonkeyPatch) -> None:
    future = _envelope(passed=True)
    future["format_version"] = "2"
    assert not _usable_with(monkeypatch, json.dumps(future))


# --- the baseline ratchet ------------------------------------------------------------------
def test_in_baseline_is_per_violation_not_per_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inherited debt and a regression can sit under the *same* check.

    Collapsing them to a per-check flag renders both as errors, which reproduces one layer up
    the exact failure the ratchet exists to prevent — and trains people to switch the gate off.
    """
    report = _parse(
        monkeypatch,
        "lint",
        _envelope(
            gate={"passed": False, "new_violations": 1, "baselined_violations": 1},
            checks=[
                {
                    "id": "dangling-edge",
                    "title": "Broken edge",
                    "severity": "error",
                    "rationale": "…",
                    "violations": [
                        {"node": "a.yml", "detail": "old", "in_baseline": True},
                        {"node": "b.yml", "detail": "new", "in_baseline": False},
                    ],
                }
            ],
        ),
    )
    assert not report.passed
    assert [v.node for v in report.regressions] == ["b.yml"]


def test_info_severity_never_counts_as_a_regression(monkeypatch: pytest.MonkeyPatch) -> None:
    """``orphan-in`` is Info upstream — a node authored this morning legitimately has no inbound
    edges yet. It is reported and must never gate, which is what makes this repo's 37 of them
    survivable without blessing anything."""
    report = _parse(
        monkeypatch,
        "lint",
        _envelope(
            gate={"passed": True, "new_violations": 0, "baselined_violations": 0},
            checks=[
                {
                    "id": "orphan-in",
                    "title": "Node nothing points to",
                    "severity": "info",
                    "rationale": "…",
                    "violations": [{"node": "c.yml", "detail": "…", "in_baseline": False}],
                }
            ],
        ),
    )
    assert report.passed
    assert report.regressions == ()


def test_unknown_fields_are_ignored_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a field is explicitly not a breaking change in this contract."""
    report = _parse(monkeypatch, "graph-check", _envelope(passed=True, some_future_field={"x": 1}))
    assert report.passed
    assert report.payload["some_future_field"] == {"x": 1}


# --- conformance against the real binary ---------------------------------------------------
@pytest.mark.skipif(not yidam_cli.usable(), reason="no yidam binary that speaks --format json")
def test_the_pinned_binary_speaks_the_contract_this_repo_understands() -> None:
    """The handshake, run for real. If upstream bumps ``format_version``, this fails here — at
    the seam — rather than somewhere downstream that mis-read a verdict."""
    report = yidam_cli.run_report("graph-check")
    assert report.build.features  # a build always names what it compiled in
    assert report.command == "graph-check"


@pytest.mark.skipif(not yidam_cli.usable(), reason="no yidam binary that speaks --format json")
def test_the_projection_passes_the_real_graph_check(tmp_path: Path) -> None:
    """The projection's contract, verified by the tool that defines it rather than by a replica.

    ``graph-check`` is the hard gate: every node carries a class and a label, and every edge
    resolves. A projection that breaks it is a bug in :mod:`watermark.site.corpus_mirror`.
    """
    settings = Settings(site="lima", data_dir=REPO_ROOT / "data")
    corpus = tmp_path / ".yidam" / "corpus"
    write_mirror(build_mirror(settings), corpus)

    report = yidam_cli.run_report("graph-check", root=tmp_path)
    assert report.passed, report.payload.get("nodes_with_issues")
    assert report.payload["total_instances"] == report.payload["clean_instances"]
