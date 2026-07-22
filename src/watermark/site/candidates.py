"""Export the curated candidate-entity inventory as typed feeds.

Publishes ``data/entities/cloud-consumer-candidates.yaml`` (the cloud-consumer candidates +
the defense-contractor seed list / Allen County parcel scan) as feeds alongside the corpus
entity graph. (The legacy markdown ``render_candidates`` / ``render_defense_contractors``
peers were removed at the SSG-cutover cleanup, #603.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from watermark.candidates import CandidateInventory, DefenseContractorList, DefenseLandScan
from watermark.pipeline.entities import EntityGraph, normalize_name
from watermark.site.feeds import (
    CandidateItem,
    ContractorAward,
    DefenseContractorItem,
    DefenseFeed,
    FederalAnnualFlow,
    FederalCategory,
    ScanParcel,
)

if TYPE_CHECKING:
    from watermark.pipeline.entities import Entity
    from watermark.usaspending import RecipientAward, UsaSpendingInventory

# nexus strength ordering for the rolled-up contractor nexus (strongest wins).
_NEXUS_RANK = {"verified": 3, "context": 2, "open": 1}

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


def _award_index(awards: UsaSpendingInventory | None) -> dict[str, RecipientAward]:
    """Index a USASpending inventory by every key an entity node might join on (uei / lei / name)."""
    index: dict[str, RecipientAward] = {}
    for rec in awards.records if awards is not None else []:
        index[rec.uei] = rec
        if rec.lei:
            index[rec.lei] = rec
        index[normalize_name(rec.recipient_name)] = rec
        index[normalize_name(rec.watchlist_name)] = rec
    return index


def _entity_award(ent: Entity, index: dict[str, RecipientAward]) -> RecipientAward | None:
    """The award a matched graph node joins to — by its stamped uei, else lei, else name."""
    for key in (ent.uei, ent.lei, normalize_name(ent.display)):
        if key and key in index:
            return index[key]
    return None


def _contractor_award(entity_key: str, rec: RecipientAward) -> ContractorAward:
    """Project a resolved :class:`RecipientAward` onto the feed's :class:`ContractorAward`."""
    return ContractorAward(
        entity_key=entity_key,
        recipient_name=rec.recipient_name,
        uei=rec.uei,
        total_obligations=rec.total_obligations,
        nexus=rec.nexus,
        defense_share=rec.defense_share,
        annual_obligations=[
            FederalAnnualFlow(fiscal_year=a.fiscal_year, obligations=a.obligations)
            for a in rec.annual_obligations
        ],
        by_psc=[
            FederalCategory(code=c.code, name=c.name, obligations=c.obligations) for c in rec.by_psc
        ],
        by_naics=[
            FederalCategory(code=c.code, name=c.name, obligations=c.obligations)
            for c in rec.by_naics
        ],
    )


def export_defense_contractors(
    dcl: DefenseContractorList,
    *,
    egraph: EntityGraph | None = None,
    scan: DefenseLandScan | None = None,
    awards: UsaSpendingInventory | None = None,
) -> DefenseFeed:
    """Export the defense-contractor seed list + parcel scan as a :class:`DefenseFeed`.

    Each contractor's ``matched_entities`` are the **entity keys** its name patterns hit
    in the corpus graph (resolved, so they link into the entities feed) — the data peer
    of the renderer's 'Corpus matches' table. When ``awards`` is supplied, each matched entity
    that resolves to a USASpending recipient is joined onto the contractor's ``awards`` (with a
    rolled-up ``total_obligations`` + strongest ``nexus``), so the feed finally shows the federal
    dollars that already reached the entity graph (#1662, ME-C).
    """
    matches: dict[str, list[str]] = dcl.match(_corpus_names(egraph)) if egraph is not None else {}
    index = _award_index(awards)
    contractors: list[DefenseContractorItem] = []
    for dc in dcl.defense_contractors:
        hits: list[str] = matches.get(dc.name, [])
        keys = sorted(
            {ent.key for h in hits if egraph is not None and (ent := egraph.get(h)) is not None}
        )
        seen_uei: set[str] = set()
        dc_awards: list[ContractorAward] = []
        for key in keys:
            ent = egraph.get(key) if egraph is not None else None
            rec = _entity_award(ent, index) if ent is not None else None
            if rec is None or rec.uei in seen_uei:
                continue
            seen_uei.add(rec.uei)
            dc_awards.append(_contractor_award(key, rec))
        total = sum(a.total_obligations for a in dc_awards) if dc_awards else None
        nexus = (
            max((a.nexus for a in dc_awards), key=lambda n: _NEXUS_RANK.get(n, 0))
            if dc_awards
            else None
        )
        contractors.append(
            DefenseContractorItem(
                name=dc.name,
                note=dc.note,
                patterns=list(dc.patterns),
                matched_entities=keys,
                awards=dc_awards,
                total_obligations=total,
                nexus=nexus,
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
