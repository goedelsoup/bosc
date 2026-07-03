"""``watermark catalog diff`` — the committed snapshot ↔ live disk delta (epic #631, issue #1134).

The ``git diff`` analogue to ``reconcile``'s ``git add``: after running a producer/connector you
can see exactly which entries' content, membership, or freshness moved **before** committing the
new ``data/catalog/_observed.yaml``. Deliberately **non-gating** and distinct from
:mod:`watermark.catalog.check` (the CI gate that compares *declared catalog ↔ disk*) — ``diff``
compares *committed snapshot ↔ live disk*, a comparison no existing command performs.

* **Before** = :func:`watermark.catalog.reconcile.load_observed` → the committed
  ``ObservedSnapshot | None``.
* **After** = :func:`watermark.catalog.reconcile.reconcile` → a live ``ObservedSnapshot``.

Two axes of delta, keyed by entry id: an **entry-set** delta (``added``/``removed`` — a catalog
YAML landed or was deleted since the last reconcile) and a **per-entry field** delta (``changed``
— one :class:`FieldChange` per moved observed field). Pure and offline: no I/O beyond
``load_observed`` + ``reconcile``. If the snapshot is missing (reconcile never run), every live
entry reports as ``added`` and the CLI prints the ``watermark catalog reconcile`` hint.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.catalog import load_entries
from watermark.catalog.reconcile import ObservedEntry, load_observed, reconcile
from watermark.catalog.sites import is_relevant
from watermark.config import Settings, get_settings

# The observed fields a per-entry delta reports, in display order. ``reconciled_at`` is
# snapshot-level (and intentionally non-deterministic), so it never appears; ``missing`` and
# ``lfs_materialized`` are diagnostics owned by ``check``, not part of the moved-field delta.
COMPARED_FIELDS: tuple[str, ...] = (
    "exists",
    "sha256",
    "file_count",
    "size_bytes",
    "asof",
    "stale",
)


class FieldChange(BaseModel):
    """One observed field that moved between the committed snapshot and live disk."""

    model_config = ConfigDict(extra="forbid")

    field: str
    before: str | int | bool | None
    after: str | int | bool | None


class DiffEntry(BaseModel):
    """One entry's standing in the snapshot↔disk delta.

    ``added``/``removed`` carry no ``changes`` (there is no counterpart to diff against);
    ``changed`` carries one :class:`FieldChange` per moved field.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["added", "removed", "changed"]
    changes: list[FieldChange] = []


def _field_changes(before: ObservedEntry, after: ObservedEntry) -> list[FieldChange]:
    """The moved observed fields between two records for the same entry id."""
    changes: list[FieldChange] = []
    for field in COMPARED_FIELDS:
        b = getattr(before, field)
        a = getattr(after, field)
        if b != a:
            changes.append(FieldChange(field=field, before=b, after=a))
    return changes


def diff(
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    site: str | None = None,
) -> list[DiffEntry]:
    """Compare the committed observed snapshot against a fresh live reconcile.

    Returns one :class:`DiffEntry` per entry whose membership or observed fields moved, sorted by
    id. ``now`` drives the live reconcile's freshness check (injectable for deterministic tests).
    ``site`` scopes the report to entries relevant to that slug (slug-scoped + basin-shared + the
    owner kinds), via :func:`watermark.catalog.sites.is_relevant`. When the snapshot is missing,
    every live entry reports as ``added``.
    """
    settings = settings or get_settings()
    before = load_observed(settings=settings)
    after = reconcile(settings=settings, now=now)

    relevant: set[str] | None = None
    if site is not None:
        relevant = {e.id for e in load_entries(settings=settings) if is_relevant(e, site)}

    before_entries = before.entries if before is not None else {}
    after_entries = after.entries

    out: list[DiffEntry] = []
    for eid in sorted(set(before_entries) | set(after_entries)):
        if relevant is not None and eid not in relevant:
            continue
        b = before_entries.get(eid)
        a = after_entries.get(eid)
        if a is not None and b is None:
            out.append(DiffEntry(id=eid, status="added"))
        elif a is None and b is not None:
            out.append(DiffEntry(id=eid, status="removed"))
        elif a is not None and b is not None:
            changes = _field_changes(b, a)
            if changes:
                out.append(DiffEntry(id=eid, status="changed", changes=changes))
    return out
