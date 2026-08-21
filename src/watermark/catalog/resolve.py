"""Per-site resolution of a catalog entry's storage (#2066) — one rule, four consumers.

A ``slug-scoped`` dataset has a *different file per site*: its storage carries a ``{site}``
template that resolves against the active slug. Answering "what does this dataset look like
**for one site**" was previously done twice and differently — :mod:`watermark.catalog.reconcile`
never did it at all (it folded every site's copy into one entry-level record, which
``watermark export`` then published into every site's bundle as that site's own fact), while
:mod:`watermark.catalog.sites` did it with a stricter predicate than reconcile's own. This
module is the single answer both now read.

Two rules, and they are deliberately the same ones :func:`watermark.catalog.reconcile._observe`
applies at the entry level:

* **What belongs to a site.** The ``{site}`` expansions for that slug, plus — for the reference
  build alone — the entry's *un-slugged peers*, which are that build's committed layout (a
  sibling's bundle must never borrow ``reference/economics/baseline.yaml``). The peers are a
  **union** with the expansions, not an alternative to them: ``hydrology-reaches`` gives Lima
  both an un-slugged ``reach-nav.yaml`` and a slugged ``reaches/lima.geojson``.
* **What counts as present.** No *declared concrete* member absent, and at least one member
  found. A ``{site}`` template's per-site absence is expected and never a gap — which is what
  ``rsei-inventory`` turned on: it declares a second templated member (``{site}/enclave.yaml``)
  that only the one federal-enclave site has, and an all-members rule read 21 sites that hold
  their inventory as missing it.

Pure and offline: path arithmetic plus ``Path.exists``. It imports no other catalog module, so
``reconcile`` and ``sites`` can both depend on it without a cycle.
"""

from __future__ import annotations

from pathlib import Path

from watermark.catalog import CatalogEntry
from watermark.config import Settings

# The reference build keeps its reference/extracted files un-slugged, so an entry's un-templated
# storage IS that site's copy; every other site's lives under its `{site}` expansion. A storage
# convention, not a site-axis exception — see `watermark.sites.is_reference_site`.
REFERENCE_LAYOUT_SITE = "lima"


def _resolved(entry: CatalogEntry, slug: str) -> list[tuple[str, bool]]:
    """``(relpath, templated)`` for every storage member that belongs to ``slug``.

    ``templated`` marks a ``{site}`` expansion, whose absence for one site is expected; an
    un-templated member is *declared concrete* and its absence is a real gap.
    """
    if entry.site_scope != "slug-scoped":
        # Shared / single-owner datasets are owned wholesale — their storage is concrete.
        return [(s.relpath, False) for s in entry.storage if "{site}" not in s.relpath]
    out: list[tuple[str, bool]] = []
    if slug == REFERENCE_LAYOUT_SITE:
        out += [(s.relpath, False) for s in entry.storage if "{site}" not in s.relpath]
    out += [
        (s.relpath.replace("{site}", slug), True) for s in entry.storage if "{site}" in s.relpath
    ]
    return out


def resolved_for_site(entry: CatalogEntry, slug: str) -> list[str]:
    """The storage relpaths that belong to ``slug`` for this entry (declared, not disk-checked)."""
    return [rel for rel, _ in _resolved(entry, slug)]


def site_members(
    entry: CatalogEntry, slug: str, settings: Settings
) -> tuple[list[tuple[str, Path]], list[str]]:
    """Resolve ``slug``'s members to ``(relpath, path)`` pairs that exist, plus absent concretes.

    The per-site peer of :func:`watermark.catalog.reconcile._members`, which does the same walk
    across *every* registered slug at once.
    """
    found: list[tuple[str, Path]] = []
    missing: list[str] = []
    for rel, templated in _resolved(entry, slug):
        path = settings.data_dir / rel
        if path.exists():
            found.append((rel, path))
        elif not templated:
            missing.append(rel)
    return found, missing


def member_exists(found: list[tuple[str, Path]], missing: list[str], *, has_storage: bool) -> bool:
    """The presence predicate: no concrete member absent, and something found.

    An entry with **no** declared storage is a *virtual* node (a pure aggregate in the producer
    DAG, or a git-ignored regenerable output). There is nothing on disk to observe, so it counts
    as present rather than as every site's standing gap.
    """
    return (not missing and len(found) >= 1) or not has_storage


def present_for_site(entry: CatalogEntry, slug: str, settings: Settings) -> bool:
    """Whether this dataset is present *for* ``slug`` — :func:`site_members` reduced."""
    found, missing = site_members(entry, slug, settings)
    return member_exists(found, missing, has_storage=bool(entry.storage))
