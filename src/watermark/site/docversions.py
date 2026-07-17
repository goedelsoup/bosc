"""Project curated document version / duplicate-cluster metadata onto the documents feed (#1590).

Search returns a filing's final permit, its draft public notice, and its fact sheet as three
separate hits with no signal they are one filing's versions. This reads a committed, curated
manifest (`data/site/document-versions.yaml`, slug-scoped like leads/contacts) that declares each
duplicate cluster — its canonical (authoritative) member and the versions it supersedes — sourced
from the custody manifests + the entity graph's ``_base_permit`` collapsing, and stamps the four
version fields onto the matching :class:`~watermark.site.feeds.DocumentItem`s. Retrieval then
collapses a cluster to its canonical member while retaining a superseded version's distinct
evidence (the ``deduplicate`` / ``version_policy`` args on search_corpus/search_passages, epic
#1579 Phase 3) — so a naive `latest`-only collapse never drops, e.g., a draft's CBI-unredacted
figure that the final redacts.

Chain of custody: the manifest is a *reading* of already-committed evidence — it invents no
documents. A member whose rel isn't in the catalog is skipped (never a dangling ref); a cluster
left with fewer than two present members is dropped (nothing to collapse).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from watermark.logging import get_logger
from watermark.site.feeds import DocumentCollectionItem, DocumentItem

log = get_logger(__name__)


@dataclass(frozen=True)
class VersionMember:
    """One member of a duplicate cluster: its corpus rel + version label + optional evidence note."""

    rel: str
    version: str | None
    evidence_note: str | None = None


@dataclass(frozen=True)
class VersionCluster:
    """A declared duplicate cluster — a canonical member and every version of the same filing."""

    id: str
    canonical: str  # rel of the authoritative member
    members: tuple[VersionMember, ...]


@dataclass(frozen=True)
class DocumentVersions:
    """The loaded manifest: the curated clusters (empty ⇒ a no-op projection)."""

    clusters: tuple[VersionCluster, ...]

    def __bool__(self) -> bool:
        return bool(self.clusters)


def load_document_versions(path: Path) -> DocumentVersions:
    """Load the curated version manifest; empty (a no-op) when absent or malformed.

    Never raises — a bad manifest degrades to no dedup metadata, exactly as an absent one does.
    """
    if not path.exists():
        log.info("site.docversions.no_store", path=str(path))
        return DocumentVersions(clusters=())
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        log.warning("site.docversions.bad_yaml", path=str(path), error=str(exc).splitlines()[0])
        return DocumentVersions(clusters=())
    if not isinstance(raw, dict):
        return DocumentVersions(clusters=())
    clusters: list[VersionCluster] = []
    for entry in raw.get("clusters") or []:
        cluster = _parse_cluster(entry)
        if cluster is not None:
            clusters.append(cluster)
    log.info("site.docversions.loaded", clusters=len(clusters), path=str(path))
    return DocumentVersions(clusters=tuple(clusters))


def _parse_cluster(entry: Any) -> VersionCluster | None:
    """Parse one cluster entry, or ``None`` (with a warning) when it's malformed."""
    if not isinstance(entry, dict):
        return None
    cid = str(entry.get("id") or "").strip()
    canonical = str(entry.get("canonical") or "").strip()
    raw_members = entry.get("members")
    if not cid or not canonical or not isinstance(raw_members, list):
        log.warning("site.docversions.bad_cluster", id=cid or "<none>")
        return None
    members: list[VersionMember] = []
    for m in raw_members:
        if not isinstance(m, dict):
            continue
        rel = str(m.get("rel") or "").strip()
        if not rel:
            continue
        version = str(m["version"]).strip() if m.get("version") else None
        note = str(m["evidence_note"]).strip() if m.get("evidence_note") else None
        members.append(VersionMember(rel=rel, version=version, evidence_note=note))
    if not any(m.rel == canonical for m in members):
        log.warning("site.docversions.canonical_not_a_member", id=cid, canonical=canonical)
        return None
    return VersionCluster(id=cid, canonical=canonical, members=tuple(members))


def apply_document_versions(
    collections: list[DocumentCollectionItem], versions: DocumentVersions
) -> None:
    """Stamp cluster/version metadata onto the matching catalogued entries, in place.

    Stale-safe (like :func:`~watermark.site.documents.build_doc_index`'s join): a member rel absent
    from the catalog is skipped, and a cluster left with fewer than two present members is dropped
    (nothing to collapse). When the declared canonical member itself isn't present, the first
    present member becomes the representative so the surviving versions still cluster.
    """
    if not versions:
        return
    by_rel: dict[str, DocumentItem] = {
        item.rel: item for coll in collections for item in coll.entries
    }
    stamped = 0
    for cluster in versions.clusters:
        present = [m for m in cluster.members if m.rel in by_rel]
        if len(present) < 2:
            if present:
                log.info("site.docversions.cluster_thin", id=cluster.id, present=len(present))
            continue
        present_rels = [m.rel for m in present]
        if cluster.canonical in by_rel:
            canonical = cluster.canonical
        else:
            canonical = present_rels[0]
            log.warning(
                "site.docversions.canonical_absent",
                id=cluster.id,
                canonical=cluster.canonical,
                promoted=canonical,
            )
        superseded = [r for r in present_rels if r != canonical]
        for m in present:
            item = by_rel[m.rel]
            item.duplicate_cluster = cluster.id
            item.canonical_document_id = canonical
            item.version = m.version
            item.supersedes = list(superseded) if m.rel == canonical else []
            stamped += 1
    if stamped:
        log.info("site.docversions.applied", entries=stamped, clusters=len(versions.clusters))
