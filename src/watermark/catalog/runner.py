"""``bosc catalog run <entry-id>`` — the DAG-aware producer runner (epic #1019, issue #1021).

The executable half of the process DAG: resolve the dependency subgraph rooted at one
catalog entry (:func:`watermark.catalog.dag.subgraph_order`, upstream-first), decide per node
whether it needs regenerating (missing or past ``refresh.ttl_days`` — the observed staleness
:mod:`watermark.catalog.reconcile` computes), and invoke each ``producer.command`` as a
``watermark`` subprocess in order, aborting on the first failure.

Planning and execution are split so ``--dry-run`` is the plan verbatim and tests never touch
a subprocess: :func:`plan` is pure observation, :func:`execute_plan` takes an injectable
``execute`` callable (defaulting to ``python -m watermark …``).
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.catalog import load_entries
from watermark.catalog.dag import subgraph_order
from watermark.catalog.reconcile import reconcile
from watermark.config import Settings, get_settings

# Why a node is in (or out of) the run: ``run`` = stale/missing/forced, ``skip-fresh`` =
# within TTL, ``virtual`` = no producer.command (an aggregate node like `onboard-bundle`).
PlanAction = Literal["run", "skip-fresh", "virtual"]
# What happened to a planned node: terminal states after execute_plan.
StepStatus = Literal["ran", "failed", "fresh", "virtual", "aborted"]


class PlanStep(BaseModel):
    """One node of the resolved run plan, in execution order."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str
    command: (
        str | None
    )  # the {site}-expanded producer command ("npdes --basin maumee"); None = virtual
    action: PlanAction
    reason: str  # human-readable why ("stale — last 2026-03-01", "fresh — last …", …)


class StepResult(BaseModel):
    """The outcome of one planned node after execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: PlanStep
    status: StepStatus
    exit_code: int | None = None  # the subprocess exit code, for ran/failed nodes


class RunReport(BaseModel):
    """The full run summary — what ran, what was fresh, what failed."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    results: list[StepResult]

    @property
    def failed(self) -> StepResult | None:
        return next((r for r in self.results if r.status == "failed"), None)

    def count(self, status: StepStatus) -> int:
        return sum(1 for r in self.results if r.status == status)


def plan(
    entry_id: str,
    *,
    site: str | None = None,
    force: bool = False,
    settings: Settings | None = None,
) -> list[PlanStep]:
    """Resolve the upstream-first run plan for ``entry_id`` (pure observation, no execution).

    A node is planned ``run`` when its observed storage is missing or past its
    ``refresh.ttl_days`` (or ``force`` is set); ``skip-fresh`` otherwise. A node without a
    ``producer.command`` is ``virtual`` — it orders the graph but executes nothing.
    Raises ``KeyError`` for an unknown entry/dependency id and ``ValueError`` on a cycle
    (both are `bosc catalog check` failures — fix the graph first).
    """
    settings = settings or get_settings()
    site = site or settings.site
    entries = load_entries(settings=settings)
    order = subgraph_order(entries, entry_id)
    observed = reconcile(settings=settings).entries

    steps: list[PlanStep] = []
    for entry in order:
        command = entry.producer.command
        if command is None:
            steps.append(
                PlanStep(
                    entry_id=entry.id,
                    command=None,
                    action="virtual",
                    reason="no producer command — nothing to execute",
                )
            )
            continue
        command = command.replace("{site}", site)
        obs = observed.get(entry.id)
        last = (obs.asof if obs else None) or entry.refresh.last_refreshed or "unknown"
        if force:
            steps.append(
                PlanStep(entry_id=entry.id, command=command, action="run", reason="forced")
            )
        elif obs is None or not obs.exists:
            steps.append(
                PlanStep(
                    entry_id=entry.id,
                    command=command,
                    action="run",
                    reason="missing — never produced",
                )
            )
        elif obs.stale:
            steps.append(
                PlanStep(
                    entry_id=entry.id,
                    command=command,
                    action="run",
                    reason=f"stale — last {last}",
                )
            )
        else:
            steps.append(
                PlanStep(
                    entry_id=entry.id,
                    command=command,
                    action="skip-fresh",
                    reason=f"fresh — last {last}",
                )
            )
    return steps


def _argv(command: str, site: str) -> list[str]:
    """The subprocess argv for one producer command — ``python -m watermark --site <slug> …``.

    Runs the same interpreter/venv as the parent so `uv run watermark catalog run` and the
    installed console script behave identically. The global ``--site`` flag goes first (it's
    an app-level callback option), then the entry's own command string.
    """
    return [sys.executable, "-m", "watermark", "--site", site, *shlex.split(command)]


# A generous per-producer backstop against a wedged subprocess (a hung network pull). Real
# connector pulls can run for minutes; this only trips a runaway, not legitimate work.
_PRODUCER_TIMEOUT_S = 3600


def _subprocess_execute(argv: list[str]) -> int:
    return subprocess.run(argv, check=False, timeout=_PRODUCER_TIMEOUT_S).returncode


def execute_plan(
    steps: list[PlanStep],
    *,
    site: str,
    execute: Callable[[list[str]], int] | None = None,
) -> RunReport:
    """Run the planned nodes in order, aborting the remainder on the first non-zero exit.

    ``execute`` is injectable (tests pass a recorder; the default spawns the real
    ``watermark`` subprocess). Fresh/virtual nodes are carried through as-is so the report
    accounts for every planned node.
    """
    execute = execute or _subprocess_execute
    results: list[StepResult] = []
    failed = False
    for step in steps:
        if failed:
            results.append(StepResult(step=step, status="aborted"))
            continue
        if step.action == "virtual":
            results.append(StepResult(step=step, status="virtual"))
            continue
        if step.action == "skip-fresh":
            results.append(StepResult(step=step, status="fresh"))
            continue
        assert step.command is not None  # action == "run" implies a concrete command
        try:
            code = execute(_argv(step.command, site))
        except (subprocess.SubprocessError, OSError):
            # a timeout, a missing interpreter, a fork failure — treat as a failed step (not a
            # crash) so the abort-on-first-failure path reports it cleanly like a non-zero exit.
            results.append(StepResult(step=step, status="failed", exit_code=None))
            failed = True
            continue
        if code == 0:
            results.append(StepResult(step=step, status="ran", exit_code=0))
        else:
            results.append(StepResult(step=step, status="failed", exit_code=code))
            failed = True
    return RunReport(results=results)
