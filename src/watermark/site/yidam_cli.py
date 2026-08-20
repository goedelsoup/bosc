"""The real ``yidam`` binary as BOSC's corpus-report engine (epic #1560).

BOSC projects its committed corpus into yidam node format itself — that projection knows about
sites, leads, hypotheses and the ``[verified]``/``[inference]``/``[open]`` claim vocabulary, and
nothing upstream can own it (:mod:`watermark.site.corpus_mirror`). But the four **reports** over
that mirror — ``graph-check`` · ``lint`` · ``corpus-index`` · ``open-questions`` — are upstream's,
and this module is how BOSC asks for them.

**Why this replaced a Python replica.** BOSC re-implemented all four in Python when the only way
to obtain the binary was to build the whole native ML stack. Two upstream changes retired that:

* RFC-0003 feature-partitioned the crate. ``reports`` is the default build and pulls no protoc,
  no lancedb and no ONNX runtime — it compiles in seconds (see ``mise run yidam-build``).
* RFC-0016 Phase 0 added ``--format json`` with a committed schema, so there is a machine-readable
  *verdict* to consume rather than prose to scrape.

The replica's own docstrings claimed faithfulness to Rust symbols it had already drifted from, and
nothing could detect it. The divergence was real and measured: over one and the same mirror, the
binary reported **2** open questions where the replica reported **20** — BOSC stored a bare
``open`` where ``has_open_claim`` scans the raw text for the literal ``[open]``. After the fix
(:func:`watermark.site.corpus_mirror._claim_token`) the two return an identical set; on the
current mirror that set is 26 nodes, but the number that matters is the 18 the tool could not
see. Deleting the replica removes the drift surface rather than instrumenting it.

**The binary is optional at runtime, required in CI.** ``watermark export`` must keep working
offline with no Rust toolchain — the content bundle's feeds are post-passes over the in-memory
:class:`~watermark.site.corpus_mirror.Mirror`, never over a rendered report, so the export path
does not need this module. When the binary *is* present, ``regenerate_mirror`` uses it to check
the projection it just wrote; when it is absent, it says so and continues. CI installs it and
gates (``.github/workflows/ci.yml``, the ``corpus`` job).

The pin lives in ``.yidam.toml`` (upstream's schema: ``origin``/``commit``/``template``/
``committed``). ``mise run yidam-vendor-status`` reports how far it has drifted — a report, never
a gate.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from watermark.logging import get_logger

log = get_logger(__name__)

#: The report-envelope contract major version this module understands.
#:
#: The schema's own instruction: *"A consumer reading an unknown value MUST degrade loudly —
#: disable verdict features and say why — and MUST NOT attempt to parse the rest."* A consumer
#: versions independently of the binary a repo pins, so skew is expected and must be detectable.
CONTRACT_VERSION = "1"


class YidamUnavailableError(RuntimeError):
    """The ``yidam`` binary is not on PATH."""


class YidamContractError(RuntimeError):
    """The binary emitted an envelope this module cannot safely read."""


@dataclass(frozen=True)
class YidamBuild:
    """Which yidam produced a report — the handshake half of the envelope."""

    version: str
    commit: str
    features: tuple[str, ...]

    @property
    def is_light(self) -> bool:
        """True for the ``reports``-only build — the one BOSC pins and CI installs."""
        return "index" not in self.features


@dataclass(frozen=True)
class Violation:
    """One finding, under the check that produced it."""

    node: str
    detail: str
    in_baseline: bool = False

    @property
    def is_regression(self) -> bool:
        """True when this violation is *new* — not inherited debt the baseline already lists."""
        return not self.in_baseline


@dataclass(frozen=True)
class Check:
    """One lint rule and everything it found.

    ``severity`` is upstream's: ``error`` gates, ``warn`` and ``info`` report. The distinction is
    what keeps the gate from being switched off wholesale — a node with no inbound edges may
    simply have been authored this morning, and reporting that as an error trains people to
    disable every check at once.
    """

    id: str
    title: str
    severity: str
    rationale: str
    violations: tuple[Violation, ...] = ()

    @property
    def gates(self) -> bool:
        return self.severity == "error"


@dataclass(frozen=True)
class Report:
    """A parsed ``yidam <command> --format json`` envelope.

    ``payload`` keeps the command-specific fields verbatim. Per the schema, *unknown fields must
    be ignored* — adding one is not a breaking change — so this deliberately does not model each
    report's body as typed attributes it would then have to chase upstream.
    """

    command: str
    build: YidamBuild
    root: Path
    payload: dict[str, Any] = field(default_factory=dict)

    # -- verdict -----------------------------------------------------------------
    @property
    def passed(self) -> bool:
        """Whether a gating report passed. Non-gating reports are always ``True``."""
        if self.command == "graph-check":
            return bool(self.payload.get("passed", True))
        if self.command == "lint":
            return bool(self.payload.get("gate", {}).get("passed", True))
        return True

    @property
    def checks(self) -> tuple[Check, ...]:
        """The lint checks, in the order the binary emitted them. Empty for other reports."""
        out: list[Check] = []
        for raw in self.payload.get("checks", []):
            out.append(
                Check(
                    id=str(raw.get("id", "")),
                    title=str(raw.get("title", "")),
                    severity=str(raw.get("severity", "")),
                    rationale=str(raw.get("rationale", "")),
                    violations=tuple(
                        Violation(
                            node=str(v.get("node", "")),
                            detail=str(v.get("detail", "")),
                            # Per violation, never per check: it is what separates inherited debt
                            # from a regression, and a consumer that loses it renders both as
                            # errors — reproducing one layer up the failure the ratchet prevents.
                            in_baseline=bool(v.get("in_baseline", False)),
                        )
                        for v in raw.get("violations", [])
                    ),
                )
            )
        return tuple(out)

    @property
    def regressions(self) -> tuple[Violation, ...]:
        """Error-severity violations that are *not* in the baseline — what actually fails a build."""
        return tuple(v for c in self.checks if c.gates for v in c.violations if v.is_regression)

    # -- graph-check body -------------------------------------------------------
    # Typed here rather than read as `report.payload["..."]` at each call site. The payload is
    # deliberately kept verbatim (unknown fields must survive), but that makes it untyped, and
    # a consumer indexing it directly has quietly taken on the contract this module exists to
    # own — an upstream rename would then surface as a silent default rather than a failure.
    @property
    def total_instances(self) -> int:
        """Instances walked by ``graph-check``. 0 for any other report."""
        return int(self.payload.get("total_instances", 0))

    @property
    def clean_instances(self) -> int:
        """Instances ``graph-check`` found no issue with."""
        return int(self.payload.get("clean_instances", 0))

    @property
    def instances_with_issues(self) -> int:
        """How many instances ``graph-check`` faulted — the count, not the nodes."""
        return max(0, self.total_instances - self.clean_instances)

    @property
    def nodes_with_issues(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """``(node, problems)`` for each faulted instance, in the order reported."""
        return tuple(
            (str(n.get("node", "?")), tuple(str(p) for p in n.get("problems", [])))
            for n in self.payload.get("nodes_with_issues", [])
        )

    @property
    def open_questions(self) -> tuple[str, ...]:
        """Node paths ``open-questions`` flagged as still open."""
        return tuple(str(q.get("node", "")) for q in self.payload.get("open_questions", []))

    def summary(self) -> str:
        """One line fit for a log or a CI annotation."""
        if self.command == "graph-check":
            return f"graph-check: {self.clean_instances}/{self.total_instances} instances clean"
        if self.command == "lint":
            gate = self.payload.get("gate", {})
            return (
                f"lint: {gate.get('new_violations', 0)} introduced, "
                f"{gate.get('baselined_violations', 0)} baselined"
            )
        if self.command == "open-questions":
            return f"open-questions: {len(self.open_questions)} open"
        if self.command == "corpus-index":
            return f"corpus-index: {len(self.payload.get('nodes', []))} nodes"
        return self.command


def yidam_path() -> Path | None:
    """The ``yidam`` binary, or ``None`` when it is not installed.

    ``cargo install`` puts it in ``~/.cargo/bin``, which is not always on a non-login shell's
    PATH, so that location is checked explicitly rather than relying on the caller's environment.
    """
    found = shutil.which("yidam")
    if found:
        return Path(found)
    fallback = Path.home() / ".cargo" / "bin" / "yidam"
    return fallback if fallback.is_file() else None


def available() -> bool:
    """Whether a ``yidam`` binary is installed. Says nothing about whether it *works*."""
    return yidam_path() is not None


@lru_cache(maxsize=1)
def usable() -> bool:
    """Whether the installed binary can be *asked* for a machine-readable verdict.

    Presence is not usability. Every `cargo install` of yidam on a machine writes the same
    ``~/.cargo/bin/yidam`` whatever ref it was built from, so an unrelated checkout can leave
    a binary here that predates ``--format json`` — it happened twice while this module was
    being written. Gate skippable conformance tests on this rather than on :func:`available`,
    so a stale binary skips them exactly as an absent one does instead of turning the suite
    red for a reason that has nothing to do with the change under test.

    Probes ``--help`` rather than running a report: it needs no corpus, no cwd, and cannot be
    confused by a repository that legitimately has findings.
    """
    binary = yidam_path()
    if binary is None:
        return False
    try:
        proc = subprocess.run(
            [str(binary), "graph-check", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and "--format" in proc.stdout


def pinned_commit(root: Path | None = None) -> str | None:
    """The commit `.yidam.toml` pins, or ``None`` when there is no readable pin.

    Deliberately a regex over the raw text rather than a TOML parse: this is the same field,
    read the same way, as `mise run yidam-build` and the CI gate read it (`sed`), and a reader
    that disagreed with them about what the pin says would be worse than no reader.
    """
    root = root or Path.cwd()
    pin = root / ".yidam.toml"
    if not pin.is_file():
        return None
    match = re.search(r'^\s*commit\s*=\s*"([^"]+)"', pin.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def pin_mismatch(build: YidamBuild, root: Path | None = None) -> str | None:
    """A message when the running binary is not the pinned one, else ``None``.

    Worth checking because **every** `cargo install` of yidam on a machine writes the same
    `~/.cargo/bin/yidam`, whatever ref it was built from. Nothing about the binary records
    which repo asked for it, so an unrelated checkout elsewhere silently re-points this one —
    it happened on the machine this was written on, to a build predating `--format json`.
    A verdict from the wrong version is worse than no verdict, so say so.
    """
    pinned = pinned_commit(root)
    if not pinned or build.commit in {"", "?", "unknown"}:
        return None
    # The envelope carries a short commit; the pin is full-length.
    if pinned.startswith(build.commit):
        return None
    return (
        f"the `yidam` on PATH is {build.commit}, but .yidam.toml pins {pinned[:7]} — "
        "re-run `mise run yidam-build` (another checkout's `cargo install` overwrites the "
        "same ~/.cargo/bin/yidam)"
    )


def run_report(command: str, *args: str, root: Path | None = None) -> Report:
    """Run one ``yidam`` report and return its parsed envelope.

    Raises :class:`YidamUnavailableError` when the binary is missing and
    :class:`YidamContractError` when the envelope is unreadable or announces a contract major
    version this module was not written against.

    A nonzero exit is *not* an error here: ``graph-check`` and ``lint`` exit nonzero precisely
    when they have findings, which is a verdict to report, not a failure to run.
    """
    binary = yidam_path()
    if binary is None:
        raise YidamUnavailableError(
            "the `yidam` binary is not installed — run `mise run yidam-build` "
            "(it installs the commit pinned in .yidam.toml; the light build takes ~20s)"
        )
    proc = subprocess.run(
        [str(binary), command, *args, "--format", "json"],
        capture_output=True,
        text=True,
        cwd=str(root) if root else None,
    )
    if not proc.stdout.strip():
        raise YidamContractError(
            f"`yidam {command}` produced no JSON (exit {proc.returncode}): "
            f"{proc.stderr.strip()[:400]}"
        )
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise YidamContractError(f"`yidam {command}` emitted unparseable JSON: {exc}") from exc

    got = str(raw.get("format_version", ""))
    if got != CONTRACT_VERSION:
        # Degrade loudly, and do not attempt to read the body. The envelope is versioned so that
        # skew is a detectable condition rather than a silent misreading.
        raise YidamContractError(
            f"`yidam {command}` speaks report contract v{got or '?'}, "
            f"this repo understands v{CONTRACT_VERSION}. Re-pin .yidam.toml and rebuild "
            f"(`mise run yidam-build`), or update watermark.site.yidam_cli."
        )

    block = raw.get("yidam", {})
    build = YidamBuild(
        version=str(block.get("version", "?")),
        commit=str(block.get("commit", "?")),
        features=tuple(str(f) for f in block.get("features", [])),
    )
    payload = {k: v for k, v in raw.items() if k not in {"format_version", "yidam", "root"}}
    return Report(
        command=command,
        build=build,
        root=Path(str(raw.get("root", root or Path.cwd()))),
        payload=payload,
    )


def check_mirror(root: Path | None = None) -> tuple[Report, Report] | None:
    """Run the two gating reports over the mirror. ``None`` when the binary is unavailable.

    Returns ``(graph_check, lint)``. Callers decide what to do with a failing verdict: the export
    tail only logs it, while CI gates on it.
    """
    if not available():
        return None
    try:
        graph_check = run_report("graph-check", root=root)
        lint = run_report("lint", root=root)
    except YidamContractError as exc:
        # An *unusable* binary degrades exactly like an absent one. It must not abort the
        # caller: `watermark corpus-mirror` has already written a valid mirror by this point,
        # and failing the whole command because a stale binary cannot be asked for a verdict
        # would make an unrelated `cargo install` elsewhere on the machine break the
        # projection. Loud, because a silently unchecked mirror is the thing to avoid.
        log.warning(
            "yidam_cli.unusable",
            error=next(iter(str(exc).splitlines()), repr(exc)),
            hint="`mise run yidam-build` reinstalls the commit pinned in .yidam.toml",
        )
        return None
    mismatch = pin_mismatch(graph_check.build, root)
    if mismatch:
        log.warning("yidam_cli.pin_mismatch", detail=mismatch)
    return graph_check, lint
