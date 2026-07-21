"""Export the curated candidate-entity inventory as typed feeds.

Publishes ``data/entities/cloud-consumer-candidates.yaml`` (the cloud-consumer candidates +
the defense-contractor seed list / Allen County parcel scan) as feeds alongside the corpus
entity graph. (The legacy markdown ``render_candidates`` / ``render_defense_contractors``
peers were removed at the SSG-cutover cleanup, #603.)
"""

from __future__ import annotations

from watermark.candidates import CandidateInventory, DefenseContractorList, DefenseLandScan
from watermark.pipeline.entities import EntityGraph, normalize_name
from watermark.site.feeds import (
    CandidateItem,
    DefenseContractorItem,
    DefenseFeed,
    ScanParcel,
)

# The defense cross-match runs against the whole entity graph, and the graph's LEI enrichment
# folds a defense-operator overlay (the reference build's JSMC / General Dynamics operator chain +
# its GLEIF ultimate parent) into *every* site's graph, network-global. So "GENERAL DYNAMICS" lands
# in ``matched_entities`` on sites with no General Dynamics presence in their own records. The feed
# already routes around this for readiness (``watermark.site.readiness`` excludes
# ``defense-contractors`` from the record-domain signal), but the feed itself carried no disclaimer
# — a reader of a peer bundle could misread a match as a local finding. This note travels on every
# site's feed to say so (#1660, ME-A). It is deliberately a module constant, not threaded per-site:
# the overlay it describes is network-global and identical on every bundle, so a "dynamic per-site"
# note would misrepresent a shared reference-build overlay as this site's own value.
MATCH_PROVENANCE_KEY = "matched_entities_provenance"
_MATCH_PROVENANCE_NOTE = (
    "matched_entities are resolved against this site's entity graph, whose LEI enrichment folds a "
    "network-global defense-operator overlay — the reference build's JSMC / General Dynamics "
    "operator chain and its GLEIF ultimate parent — into every site's graph. A match here may "
    "reflect that shared overlay rather than any presence of the contractor in this site's own "
    "records; treat it as a cross-reference to follow up, not a site-local finding."
)


def _corpus_names(egraph: EntityGraph) -> list[str]:
    """Every legible party name in the graph (displays + raw variants)."""
    names: set[str] = set()
    for ent in egraph.entities.values():
        names.add(ent.display)
        names.update(ent.variants)
    return sorted(names)


def export_candidates(
    inv: CandidateInventory, *, egraph: EntityGraph | None = None
) -> list[CandidateItem]:
    """Export the cloud-consumer candidate inventory as :class:`CandidateItem` items.

    ``entity_key`` is set to the resolved graph key when the candidate name matches an
    entity (the same demand-fit lookup the renderer's 'In graph' column uses).
    """
    items: list[CandidateItem] = []
    for e in inv.entities:
        resolved = egraph.get(normalize_name(e.name)) if egraph is not None else None
        items.append(
            CandidateItem(
                name=e.name,
                tier=e.tier,
                kind=e.kind,
                sector=e.sector,
                location=e.location,
                workload_classes=list(e.workload_classes),
                confirmed_cloud_relationship=e.confirmed_cloud_relationship,
                speculative=e.speculative,
                basis=e.basis,
                entity_key=resolved.key if resolved is not None else None,
            )
        )
    return items


def export_defense_contractors(
    dcl: DefenseContractorList,
    *,
    egraph: EntityGraph | None = None,
    scan: DefenseLandScan | None = None,
) -> DefenseFeed:
    """Export the defense-contractor seed list + parcel scan as a :class:`DefenseFeed`.

    Each contractor's ``matched_entities`` are the **entity keys** its name patterns hit
    in the corpus graph (resolved, so they link into the entities feed) — the data peer
    of the renderer's 'Corpus matches' table.
    """
    matches: dict[str, list[str]] = dcl.match(_corpus_names(egraph)) if egraph is not None else {}
    contractors: list[DefenseContractorItem] = []
    for dc in dcl.defense_contractors:
        hits: list[str] = matches.get(dc.name, [])
        keys = sorted(
            {ent.key for h in hits if egraph is not None and (ent := egraph.get(h)) is not None}
        )
        contractors.append(
            DefenseContractorItem(
                name=dc.name,
                note=dc.note,
                patterns=list(dc.patterns),
                matched_entities=keys,
            )
        )
    notes: dict[str, object] = dict(scan.meta) if scan is not None else {}
    notes[MATCH_PROVENANCE_KEY] = _MATCH_PROVENANCE_NOTE
    return DefenseFeed(
        contractors=contractors,
        prime_owned=[ScanParcel.model_validate(r) for r in (scan.prime_owned if scan else [])],
        army_controlled=[
            ScanParcel.model_validate(r) for r in (scan.army_controlled if scan else [])
        ],
        notes=notes,
    )
