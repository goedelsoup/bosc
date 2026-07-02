"""``bosc catalog reconcile`` — the observed half of the declared-vs-observed split.

Phase 1 of the data-catalog epic (#631, issue #625). Where :class:`watermark.catalog.CatalogEntry`
is what a dataset *declares*, this walks each entry's ``storage`` on disk and records what is
*observed* — existence, an entry-level sha256, on-disk size, whether Git-LFS bytes are
materialized (vs an unresolved pointer), the data's own ``asof``/``last_refreshed`` timestamp,
and freshness against ``refresh.ttl_days`` — into a committed, deterministic, sorted snapshot at
``data/catalog/_observed.yaml``.

Reconcile **observes**; it does not decide acceptability — that's ``bosc catalog check`` (#626),
which gates on this snapshot. It is offline and hermetic (stat + sha256 of committed files, no
network, no parquet/Arrow fingerprint — the data is YAML/CSV/PDF/GeoJSON). Slug-scoped
``{site}`` templates are expanded across the registered sites and resolved to the files that
actually exist, so per-site absence (not every site has every dataset) is never a false miss.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.catalog import CatalogEntry, load_entries
from watermark.config import Settings, get_settings
from watermark.sites import SITES

# The committed observed snapshot, at the catalog root (``load_entries`` skips root-level files).
OBSERVED_RELNAME = "_observed.yaml"


def _is_lfs_pointer(path: Path) -> bool:
    """True if ``path`` is an unresolved Git-LFS pointer rather than the real bytes.

    Mirrors ``watermark.site.documents._is_lfs_pointer`` — replicated (it's a 6-line constant) to
    keep this core data path off the heavy ``watermark.site`` presentation package.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(64)
    except OSError:
        return True
    return head.startswith(b"version https://git-lfs.github.com/spec/v1")


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_date(text: str) -> date | None:
    """Lenient date parse: ISO ``YYYY-MM-DD``, or a bare ``YYYY`` year (→ Jan 1)."""
    text = text.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        if len(text) == 4 and text.isdigit():
            return date(int(text), 1, 1)
    return None


def _read_asof(path: Path) -> str | None:
    """The data's own timestamp — ``meta.asof`` or ``meta.last_refreshed`` — if it carries one."""
    if path.suffix.lower() not in (".yaml", ".yml"):
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # a malformed/huge member is not worth crashing reconcile over
        return None
    if isinstance(data, dict):
        meta = data.get("meta")
        if isinstance(meta, dict):
            for key in ("asof", "last_refreshed"):
                val = meta.get(key)
                if isinstance(val, str):
                    return val
    return None


class ObservedEntry(BaseModel):
    """What reconcile saw on disk for one catalog entry (the observed half)."""

    model_config = ConfigDict(extra="forbid")

    exists: bool  # all concrete members present (templated entries: ≥1 site materialized)
    sha256: (
        str | None
    )  # the materialized file's hash (single-file) or a stable aggregate; None if incomplete
    size_bytes: int  # summed on-disk size of the materialized members
    lfs_materialized: bool  # no present member is an unresolved Git-LFS pointer
    file_count: int  # materialized member count (a {site} template fans out)
    missing: list[str] = Field(default_factory=list)  # declared concrete relpaths absent on disk
    asof: str | None = None  # the data's own meta.asof/last_refreshed
    stale: bool = False  # past refresh.ttl_days vs asof/last_refreshed (False when unknowable)


class ObservedSnapshot(BaseModel):
    """The full ``_observed.yaml`` artifact — ``reconciled_at`` plus one record per entry."""

    model_config = ConfigDict(extra="forbid")

    reconciled_at: str
    entries: dict[str, ObservedEntry] = Field(default_factory=dict)


def _members(entry: CatalogEntry, settings: Settings) -> tuple[list[tuple[str, Path]], list[str]]:
    """Resolve an entry's storage to (relpath, path) pairs that exist, plus absent concrete relpaths.

    A ``{site}`` template expands across the registered sites and keeps only the files that
    actually exist — per-site absence is expected, so it never contributes to ``missing``.
    """
    found: list[tuple[str, Path]] = []
    missing: list[str] = []
    for item in entry.storage:
        rel = item.relpath
        if "{site}" in rel:
            for slug in sorted(SITES):
                actual = rel.replace("{site}", slug)
                path = settings.data_dir / actual
                if path.exists():
                    found.append((actual, path))
        else:
            path = settings.data_dir / rel
            if path.exists():
                found.append((rel, path))
            else:
                missing.append(rel)
    return found, missing


def _observe(entry: CatalogEntry, settings: Settings, now: date) -> ObservedEntry:
    found, missing = _members(entry, settings)
    pointers = [p for _, p in found if _is_lfs_pointer(p)]
    lfs_materialized = not pointers
    # An entry with no declared storage is a *virtual* node (#1020/#1024) — a pure aggregate
    # in the dependency DAG (e.g. `onboard-bundle`) or a feed whose output is regenerable and
    # git-ignored (the bundle). Nothing on disk to observe, so it counts as present.
    exists = (not missing and len(found) >= 1) or not entry.storage
    size_bytes = sum(p.stat().st_size for _, p in found)

    # sha256: the file's own hash for a single materialized file (so a pinned, file-level
    # checksum compares directly); a stable aggregate for multi-file; None when incomplete.
    sha256: str | None
    if missing or pointers or not found:
        sha256 = None
    elif len(found) == 1:
        sha256 = _file_sha256(found[0][1])
    else:
        lines = sorted(f"{rel}  {_file_sha256(p)}" for rel, p in found)
        sha256 = hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()

    asof = next((a for a in (_read_asof(p) for _, p in found) if a), None)
    ref = asof or entry.refresh.last_refreshed
    ttl = entry.refresh.ttl_days
    stale = False
    if ttl is not None and ref is not None:
        ref_date = _parse_date(ref)
        if ref_date is not None:
            stale = (now - ref_date).days > ttl

    return ObservedEntry(
        exists=exists,
        sha256=sha256,
        size_bytes=size_bytes,
        lfs_materialized=lfs_materialized,
        file_count=len(found),
        missing=sorted(missing),
        asof=asof,
        stale=stale,
    )


def reconcile(
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    reconciled_at: str | None = None,
) -> ObservedSnapshot:
    """Observe every committed catalog entry's storage on disk (offline, hermetic).

    ``now`` drives the freshness check and defaults to the current UTC time; ``reconciled_at``
    overrides the recorded timestamp (both injectable so tests are deterministic).
    """
    settings = settings or get_settings()
    moment = now or datetime.now(UTC)
    entries = {
        entry.id: _observe(entry, settings, moment.date())
        for entry in load_entries(settings=settings)
    }
    return ObservedSnapshot(
        reconciled_at=reconciled_at or moment.isoformat(),
        entries=dict(sorted(entries.items())),
    )


def observed_path(*, settings: Settings | None = None) -> Path:
    settings = settings or get_settings()
    return settings.catalog_dir / OBSERVED_RELNAME


def _dump(snapshot: ObservedSnapshot) -> str:
    """Deterministic YAML: stable field order, entries sorted by id."""
    payload = {
        "reconciled_at": snapshot.reconciled_at,
        "entries": {eid: snapshot.entries[eid].model_dump() for eid in sorted(snapshot.entries)},
    }
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)


def write_observed(snapshot: ObservedSnapshot, *, settings: Settings | None = None) -> Path:
    """Write the snapshot to ``data/catalog/_observed.yaml`` and return its path."""
    settings = settings or get_settings()
    path = observed_path(settings=settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(snapshot), encoding="utf-8")
    return path


def load_observed(*, settings: Settings | None = None) -> ObservedSnapshot | None:
    """Load the committed snapshot, or ``None`` if reconcile has never run."""
    path = observed_path(settings=settings)
    if not path.exists():
        return None
    return ObservedSnapshot.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
