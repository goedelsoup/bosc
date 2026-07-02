"""``watermark catalog check`` — the validation + drift gate (epic #631, issue #626).

The capstone of Phase 1: turns the manual ``corpus-completeness-audit.md`` pass into a
CI-enforced invariant. Wired into ``mise run check`` and the CI ``check`` job, it fails
(non-zero) when the catalog and the data tree have drifted apart:

* **schema** — a ``data/catalog/**.yaml`` that doesn't validate, or a duplicate ``id``
  (delegated to :func:`watermark.catalog.validate_entries`).
* **missing-files** — an entry whose declared concrete storage doesn't exist on disk. A
  Git-LFS *pointer* counts as present-but-unmaterialized (reported distinctly, not missing).
* **orphan-file** — a file under a catalogued scope (``reference``/``extracted``) with **no**
  catalog entry: the "we added data but never catalogued it" leak this gate exists to catch.
* **stale** — an entry past ``refresh.ttl_days`` (warn by default; ``--strict`` makes it fail).
* **checksum-drift** — a pinned single-file entry whose observed sha256 ≠ its pin.

Offline and hermetic (it observes the filesystem via :func:`watermark.catalog.reconcile.reconcile`;
no network). It is **LFS-aware**: CI checks out without LFS bytes, so unmaterialized pointers
are never treated as missing or drift — only as an informational ``unmaterialized`` note.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.catalog import CatalogEntry, load_entries, validate_entries
from watermark.catalog.backfill import BACKFILL_SCOPES, _is_data_file
from watermark.catalog.reconcile import ObservedEntry, load_observed, reconcile
from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.sites import SITES

log = get_logger(__name__)

Severity = Literal["error", "warn"]
CheckKind = Literal[
    "schema",
    "duplicate-id",
    "missing-files",
    "orphan-file",
    "stale",
    "checksum-drift",
    "render-drift",
    "audit-drift",
    "unmaterialized",
    "no-snapshot",
    "unknown-dependency",
    "dependency-cycle",
    "downstream-stale",
]


class CheckFinding(BaseModel):
    """One gate finding. ``severity='error'`` fails the gate; ``'warn'`` is informational."""

    model_config = ConfigDict(extra="forbid")

    kind: CheckKind
    severity: Severity
    subject: str  # the entry id or the orphan file's relpath
    detail: str = ""


def _covered_relpaths(entries: list[CatalogEntry], settings: Settings) -> set[str]:
    """Every data-tree relpath claimed by some entry's storage (``{site}`` templates expanded)."""
    covered: set[str] = set()
    for entry in entries:
        for item in entry.storage:
            rel = item.relpath
            if "{site}" in rel:
                for slug in sorted(SITES):
                    actual = rel.replace("{site}", slug)
                    if (settings.data_dir / actual).exists():
                        covered.add(actual)
            else:
                covered.add(rel)
    return covered


def _all_data_files(settings: Settings) -> set[str]:
    """Every catalogue-eligible file under the catalogued scopes (same skip rules as backfill)."""
    found: set[str] = set()
    for scope in BACKFILL_SCOPES:
        root = settings.data_dir / scope
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if _is_data_file(path):
                found.add(str(path.relative_to(settings.data_dir)))
    return found


def check(
    *,
    settings: Settings | None = None,
    strict: bool = False,
    now: datetime | None = None,
) -> list[CheckFinding]:
    """Run every catalog invariant and return the findings (errors fail the gate).

    ``strict`` promotes staleness from a warning to a failure. ``now`` drives the freshness
    check (defaults to the current time, injectable for deterministic tests).
    """
    settings = settings or get_settings()
    findings: list[CheckFinding] = []

    # 1. schema + duplicate id — if the catalog can't even load, stop here (nothing else is safe).
    schema_findings = validate_entries(settings=settings)
    for f in schema_findings:
        kind: CheckKind = "duplicate-id" if f.kind == "duplicate-id" else "schema"
        findings.append(
            CheckFinding(kind=kind, severity="error", subject=f.entry_id, detail=f.detail)
        )
    if any(f.kind == "load-error" for f in schema_findings):
        return findings  # the tree is unparseable; missing/orphan/drift can't be trusted

    entries = load_entries(settings=settings)

    # 1b. the dependency graph (#1020) — every depends_on id resolves, and the graph is
    # acyclic. Pure graph operations over the loaded catalog; both are hard failures (a
    # broken graph would strand `bosc catalog run` and the downstream-staleness gate).
    from watermark.catalog.dag import find_cycle, unknown_dependencies

    for entry_id, dep in unknown_dependencies(entries):
        findings.append(
            CheckFinding(
                kind="unknown-dependency",
                severity="error",
                subject=entry_id,
                detail=f"depends_on names unknown entry {dep!r}",
            )
        )
    cycle = find_cycle(entries)
    if cycle is not None:
        findings.append(
            CheckFinding(
                kind="dependency-cycle",
                severity="error",
                subject=cycle[0],
                detail=f"dependency cycle: {' -> '.join(cycle)}",
            )
        )

    # 2 + 3. missing files / unmaterialized LFS / staleness — from a live observation.
    snapshot = reconcile(settings=settings, now=now)
    for eid, obs in snapshot.entries.items():
        if not obs.exists:
            findings.append(
                CheckFinding(
                    kind="missing-files",
                    severity="error",
                    subject=eid,
                    detail=f"declared file(s) absent on disk: {', '.join(obs.missing) or '(no storage)'}",
                )
            )
        elif not obs.lfs_materialized:
            findings.append(
                CheckFinding(
                    kind="unmaterialized",
                    severity="warn",
                    subject=eid,
                    detail="present but Git-LFS bytes not materialized (expected in a no-LFS checkout)",
                )
            )
        if obs.stale:
            findings.append(
                CheckFinding(
                    kind="stale",
                    severity="error" if strict else "warn",
                    subject=eid,
                    detail=f"past refresh.ttl_days (asof {obs.asof})",
                )
            )

    # 3b. downstream staleness (#1022) — a dependent whose upstream was refreshed after it.
    # Warn by default (expected during incremental onboarding); --strict promotes to error.
    for finding in downstream_stale_findings(entries, snapshot.entries):
        findings.append(finding.model_copy(update={"severity": "error"}) if strict else finding)

    # 4. orphan files — committed data under a catalogued scope with no entry.
    orphans = _all_data_files(settings) - _covered_relpaths(entries, settings)
    for rel in sorted(orphans):
        findings.append(
            CheckFinding(
                kind="orphan-file",
                severity="error",
                subject=rel,
                detail="no catalog entry — run `watermark catalog backfill --apply`",
            )
        )

    # 5. checksum drift — a pinned single-file entry whose observed sha ≠ its pin.
    findings.extend(_checksum_findings(entries, settings))

    # 6. render drift — a README that opted into `watermark catalog render` but fell out of sync.
    from watermark.catalog.render import render_drift

    for collection, relpath in render_drift(settings=settings):
        findings.append(
            CheckFinding(
                kind="render-drift",
                severity="error",
                subject=relpath,
                detail=f"{collection} README out of sync — run `watermark catalog render --apply`",
            )
        )

    # 7. audit drift — the generated COMPLETENESS.md no longer matches the snapshot.
    from watermark.catalog.audit import audit_drift

    drifted_audit = audit_drift(settings=settings)
    if drifted_audit is not None:
        findings.append(
            CheckFinding(
                kind="audit-drift",
                severity="error",
                subject=drifted_audit,
                detail="completeness audit out of sync — run `watermark catalog audit --apply`",
            )
        )

    return findings


def downstream_stale_findings(
    entries: list[CatalogEntry],
    observed: dict[str, ObservedEntry],
    *,
    root: str | None = None,
) -> list[CheckFinding]:
    """Per-edge downstream staleness (#1022): B depends on A, and A refreshed after B.

    B's data may not reflect A's latest output — the fix is ``watermark catalog run <B>``.
    Each entry's reference date is what reconcile observed (the data's own ``meta.asof``)
    falling back to the declared ``refresh.last_refreshed``; an edge with either date
    unknown, or an unresolved dependency id (its own gate finding), is skipped. ``root``
    restricts the scan to the dependency closure of one entry — the ``watermark export``
    pre-flight (#1024) checks only the bundle's own upstream chain that way. Always emitted
    as warnings; the caller promotes under ``--strict``.
    """
    from watermark.catalog.dag import by_id, subgraph_order
    from watermark.catalog.reconcile import _parse_date

    if root is not None:
        try:
            scoped = subgraph_order(entries, root)
        except (KeyError, ValueError):  # unknown root / broken graph — check() reports those
            return []
    else:
        scoped = entries
    index = by_id(entries)

    def ref_date(entry_id: str) -> date | None:
        entry = index[entry_id]
        obs = observed.get(entry_id)
        ref = (obs.asof if obs else None) or entry.refresh.last_refreshed
        return _parse_date(ref) if ref else None

    out: list[CheckFinding] = []
    for entry in scoped:
        b_date = ref_date(entry.id)
        if b_date is None:
            continue
        for dep in entry.depends_on:
            if dep not in index:
                continue
            a_date = ref_date(dep)
            if a_date is not None and a_date > b_date:
                out.append(
                    CheckFinding(
                        kind="downstream-stale",
                        severity="warn",
                        subject=entry.id,
                        detail=(
                            f"depends on {dep} (refreshed {a_date.isoformat()}) but was last "
                            f"refreshed {b_date.isoformat()} — re-run: "
                            f"watermark catalog run {entry.id}"
                        ),
                    )
                )
    return out


def upstream_preflight(
    root: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> list[CheckFinding]:
    """The pre-flight for one entry's dependency closure — ``watermark export`` calls this (#1024).

    Scoped to the DAG rooted at ``root``, it surfaces (as warnings, never gate failures) every
    upstream that is TTL-stale plus every downstream-stale edge, so a consumer command can
    print them before running with current data. Returns ``[]`` when the root entry doesn't
    exist or the graph is broken — those are ``bosc catalog check``'s findings, not ours.

    **Fails open:** this is an advisory pre-flight for a "never abort" caller (``watermark
    export``, #1024), so any unexpected failure loading/reconciling the catalog is swallowed
    (logged) and returns ``[]`` rather than propagating and aborting the consumer.
    """
    from watermark.catalog.dag import subgraph_order

    settings = settings or get_settings()
    try:
        entries = load_entries(settings=settings)
        closure = subgraph_order(entries, root)
        observed = reconcile(settings=settings, now=now).entries
    except (KeyError, ValueError):
        return []  # unknown root / broken graph — bosc catalog check owns those findings
    except Exception:  # advisory pre-flight must never abort the caller — fail open, log
        log.warning("catalog.upstream_preflight.skipped", root=root, exc_info=True)
        return []
    out: list[CheckFinding] = []
    for entry in closure:
        if entry.id == root:  # the export target itself is not one of its own upstreams
            continue
        obs = observed.get(entry.id)
        if obs is not None and obs.stale:
            out.append(
                CheckFinding(
                    kind="stale",
                    severity="warn",
                    subject=entry.id,
                    detail=(
                        f"past refresh.ttl_days (last {obs.asof or entry.refresh.last_refreshed})"
                        f" — re-run: watermark catalog run {root}"
                    ),
                )
            )
    out.extend(downstream_stale_findings(entries, observed, root=root))
    return out


def _checksum_findings(entries: list[CatalogEntry], settings: Settings) -> list[CheckFinding]:
    """Compare each pinned single-file entry's committed-observed sha against its pin."""
    observed = load_observed(settings=settings)
    out: list[CheckFinding] = []
    pinned = [e for e in entries if len(e.storage) == 1 and e.storage[0].sha256]
    if pinned and observed is None:
        out.append(
            CheckFinding(
                kind="no-snapshot",
                severity="warn",
                subject="_observed.yaml",
                detail="pinned entries exist but no snapshot — run `watermark catalog reconcile`",
            )
        )
        return out
    if observed is None:
        return out
    for entry in pinned:
        pin = entry.storage[0].sha256
        if pin is None:  # narrowed for the type checker (the `pinned` filter guarantees it)
            continue
        obs = observed.entries.get(entry.id)
        if obs is None or obs.sha256 is None:
            continue  # unreconciled or an unmaterialized LFS pointer — can't verify
        if obs.sha256 != pin:
            out.append(
                CheckFinding(
                    kind="checksum-drift",
                    severity="error",
                    subject=entry.id,
                    detail=f"observed sha256 {obs.sha256[:12]}… ≠ pinned {pin[:12]}…",
                )
            )
    return out


def errors(findings: list[CheckFinding]) -> list[CheckFinding]:
    """The gate-failing subset."""
    return [f for f in findings if f.severity == "error"]
