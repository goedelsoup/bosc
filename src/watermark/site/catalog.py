"""Build the published ``catalog`` feed (epic #631 Phase 3 / #659).

Projects the data catalog (:mod:`watermark.catalog`) into the content bundle: each
:class:`watermark.catalog.CatalogEntry` becomes a :class:`watermark.site.feeds.CatalogItem`, joined to
the reconcile observed snapshot (``data/catalog/_observed.yaml``) where one is committed. This
is what lets the Astro ``/about/data`` page read the catalog at build time — the data tier's
view of *what datasets exist, where each came from, its license/access tier, and whether it's
fresh*, the legible successor to the manual corpus-completeness audit.

The observation a site publishes is **its own** (#2066). A ``slug-scoped`` dataset has a
different file per site, and the snapshot's entry-level record is the network-wide aggregate of
all of them; copying that into every bundle made each site assert its siblings' bytes as its own,
including ``exists: true`` for sites holding no such file. The reference build alone additionally
carries the network membership figure, for the network-global ``/about/catalog`` page.
"""

from __future__ import annotations

from watermark.catalog import CatalogEntry, ProducerKind, load_entries
from watermark.catalog.reconcile import ObservedEntry, load_observed
from watermark.catalog.sites import owner_matches, site_title
from watermark.config import Settings, get_settings
from watermark.site.feeds import (
    CatalogItem,
    CatalogNetworkObserved,
    CatalogObserved,
    CatalogStorageFile,
    Citation,
    SourceKind,
)
from watermark.sites import SITES, is_reference_site

# Producer kind → the bundle's shared provenance vocabulary (mirrors catalog_backfill).
_SOURCE_KIND: dict[ProducerKind, SourceKind] = {
    "connector": "connector",
    "extracted": "document",
    "derived": "derived",
    "vendored": "reference",
    "manual": "reference",
}


def _collection(entry: CatalogEntry) -> str:
    """The dataset's collection — the first dir under its scope, ``{site}`` dropped."""
    if not entry.storage:
        return entry.scope
    parts = [p for p in entry.storage[0].relpath.split("/")[1:-1] if p != "{site}"]
    return parts[0] if parts else entry.scope


def _in_site_scope(entry: CatalogEntry, slug: str) -> bool:
    """Whether a catalog entry belongs in ``slug``'s per-site bundle (#762/#778).

    A sibling site's bundle is strictly its own: a row is included iff its owner matches the site
    (:func:`watermark.catalog.sites.owner_matches` — ``site:``/``basin:``/``state:`` against the site's
    slug/basin/state, plus the shared/template kinds). The reference build (Lima, the network host
    the root ``/about/data`` page reads) keeps the whole catalog, byte-identical.
    """
    return is_reference_site(slug) or owner_matches(entry.site_scope, slug)


def _has_site_axis(entry: CatalogEntry) -> bool:
    """Whether this entry's observation is per-site rather than one record for everyone (#2066).

    A ``slug-scoped`` entry resolves a ``{site}`` template, so its file differs per site. The
    condition is structural — ``site_scope`` plus declared storage — and not "does the snapshot
    happen to carry site records", so an entry no site has a copy of still resolves to
    ``exists: false`` per site instead of silently falling back to the aggregate. A slug-scoped
    entry with NO storage is a virtual DAG node: nothing on disk, so its record is already the
    right answer for every site.
    """
    return entry.site_scope == "slug-scoped" and bool(entry.storage)


def _observed_for_site(
    entry: CatalogEntry, obs: ObservedEntry | None, slug: str
) -> CatalogObserved | None:
    """The observation this site publishes — its own record, never a sibling's.

    Absence is the point: a slug with no copy of a slug-scoped dataset is left out of the
    snapshot's ``sites`` map, and resolves here to a zeroed ``exists: false``. It used to inherit
    the network aggregate and assert an artifact the site does not have (#2066).
    """
    if obs is None:
        return None
    if not _has_site_axis(entry):
        return CatalogObserved(
            exists=obs.exists,
            sha256=obs.sha256,
            size_bytes=obs.size_bytes,
            lfs_materialized=obs.lfs_materialized,
            file_count=obs.file_count,
            stale=obs.stale,
            asof=obs.asof,
        )
    record = obs.sites.get(slug)
    if record is None:
        return CatalogObserved(exists=False, sha256=None, size_bytes=0, file_count=0)
    return CatalogObserved(
        exists=record.exists,
        sha256=record.sha256,
        size_bytes=record.size_bytes,
        lfs_materialized=record.lfs_materialized,
        file_count=record.file_count,
        stale=record.stale,
        asof=record.asof,
    )


def _observed_network(
    entry: CatalogEntry, obs: ObservedEntry | None, slug: str
) -> CatalogNetworkObserved | None:
    """The network membership figure — reference build only, slug-scoped only (#2066).

    ``/about/catalog`` is network-global but reads the reference build's bundle, so without this
    a per-site dataset would render there as whatever Lima happens to hold: ``parcel-assemblage``
    would read "missing" on a page about the whole data tree, for a dataset eleven sites have.
    A sibling's bundle carries only its own slice and has no business asserting a network figure.
    """
    if obs is None or not _has_site_axis(entry) or not is_reference_site(slug):
        return None
    return CatalogNetworkObserved(
        sites_present=sum(1 for r in obs.sites.values() if r.exists),
        sites_total=len(SITES),
    )


def export_catalog(settings: Settings | None = None) -> list[CatalogItem]:
    """Project every catalog entry to a :class:`CatalogItem`, joined to the observed snapshot.

    Per-site (#762): a sibling site's bundle carries only the entries in its own scope; the
    reference build (Lima, the network host the root ``/about/data`` page reads) keeps the whole
    inventory. See :func:`_in_site_scope`.
    """
    settings = settings or get_settings()
    snapshot = load_observed(settings=settings)
    items: list[CatalogItem] = []
    for entry in load_entries(settings=settings):
        if not _in_site_scope(entry, settings.site):
            continue
        obs = snapshot.entries.get(entry.id) if snapshot else None
        items.append(
            CatalogItem(
                id=entry.id,
                # Slug-scoped titles are materialized for the active site (#1250) so a sibling
                # bundle names its own county, not Lima's; fixed titles pass through unchanged.
                title=site_title(entry, settings.site),
                scope=entry.scope,
                collection=_collection(entry),
                status=entry.status,
                producer_kind=entry.producer.kind,
                command=entry.producer.command,
                connector_ref=entry.producer.connector_ref,
                source=entry.producer.source,
                external_url=entry.producer.external_url,
                license=entry.license,
                access_tier=entry.access_tier,
                site_scope=entry.site_scope,
                cadence=entry.refresh.cadence,
                ttl_days=entry.refresh.ttl_days,
                last_refreshed=entry.refresh.last_refreshed,
                tags=list(entry.tags),
                storage=[
                    CatalogStorageFile(relpath=s.relpath, media_type=s.media_type, lfs=s.lfs)
                    for s in entry.storage
                ],
                observed=_observed_for_site(entry, obs, settings.site),
                observed_network=_observed_network(entry, obs, settings.site),
                citation=Citation(
                    source=entry.producer.source,
                    source_kind=_SOURCE_KIND[entry.producer.kind],
                    note=f"watermark {entry.producer.command}" if entry.producer.command else None,
                ),
            )
        )
    return sorted(items, key=lambda i: (i.scope, i.id))
