"""Candidate-entity store: load/validate the committed inventory."""

from __future__ import annotations

from pathlib import Path

from watermark import candidates
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTITIES = REPO_ROOT / "data" / "entities"


def test_committed_inventory_loads_and_is_marked() -> None:
    inv = candidates.load_cloud_consumer_candidates(ENTITIES)
    assert inv is not None
    assert len(inv.entities) >= 20
    # Every entity is a demand-fit candidate; tiers are 1-4.
    assert all(e.cloud_consumer_candidate for e in inv.entities)
    assert all(1 <= e.tier <= 4 for e in inv.entities)
    assert "what_this_is_not" in inv.meta  # the integrity caution is preserved


def test_inventories_live_under_profiles_subdir() -> None:
    # The curated inputs were moved under data/entities/profiles/.
    assert (ENTITIES / "profiles" / "cloud-consumer-candidates.yaml").is_file()
    assert (ENTITIES / "profiles" / "defense-contractors.yaml").is_file()


def test_defense_contractors_load_and_match() -> None:
    dcl = candidates.load_defense_contractors(ENTITIES)
    assert dcl is not None
    assert len(dcl.defense_contractors) >= 15
    assert "what_this_is_not" in dcl.meta
    names = {dc.name for dc in dcl.defense_contractors}
    assert "Boeing" in names
    # Case-insensitive substring matching against arbitrary names.
    hits = dcl.match(["The Boeing Company - Plant 4", "Jane Q. Public"])
    assert hits.get("Boeing") == ["The Boeing Company - Plant 4"]
    # The Harris false-positive guard: bare "HARRIS" must not match a person.
    assert dcl.match(["WILLIAM HARRIS"]) == {}


def test_defense_feed_carries_match_provenance_disclaimer() -> None:
    # The cross-match resolves against an entity graph whose LEI enrichment folds the JSMC
    # operator chain (General Dynamics …) into every site, so "GENERAL DYNAMICS" bleeds onto
    # peers with no local presence. The feed must ship a per-site provenance disclaimer so a
    # reader can't misread a match as a site-local finding (#1660, ME-A). It travels on every
    # bundle's feed — including a facility-less peer with no scan and no graph.
    from watermark.site.candidates import MATCH_PROVENANCE_KEY, export_defense_contractors

    dcl = candidates.load_defense_contractors(ENTITIES)
    assert dcl is not None
    feed = export_defense_contractors(dcl)  # no egraph, no scan — the leanest peer
    assert MATCH_PROVENANCE_KEY in feed.notes
    note = feed.notes[MATCH_PROVENANCE_KEY]
    assert isinstance(note, str) and "General Dynamics" in note


def test_defense_feed_joins_federal_awards() -> None:
    """A matched entity carrying a stamped UEI joins its USASpending award onto the contractor,
    rolling up the total + strongest nexus (#1662, ME-C). Unmatched contractors stay dollar-less.
    """
    from watermark.candidates import DefenseContractor, DefenseContractorList
    from watermark.pipeline.entities import Entity, EntityGraph, normalize_name
    from watermark.site.candidates import export_defense_contractors
    from watermark.usaspending import (
        AnnualObligation,
        CategoryShare,
        RecipientAward,
        UsaSpendingInventory,
    )

    key = normalize_name("GENERAL DYNAMICS CORPORATION")
    ent = Entity(key=key, kind="corporate", classification="corporate")
    ent.variants.add("GENERAL DYNAMICS CORPORATION")
    ent.uei = "VF58HFRNGEL8"  # as the federal-award enrichment stamps it
    graph = EntityGraph(entities={key: ent})

    dcl = DefenseContractorList(
        defense_contractors=[
            DefenseContractor(name="General Dynamics", patterns=["GENERAL DYNAMICS CORPORATION"]),
            DefenseContractor(name="Boeing", patterns=["BOEING"]),  # no corpus match
        ]
    )
    awards = UsaSpendingInventory(
        meta={},
        records=[
            RecipientAward(
                watchlist_name="General Dynamics Corp",
                recipient_id="gd-P",
                uei="VF58HFRNGEL8",
                recipient_name="GENERAL DYNAMICS CORPORATION",
                total_obligations=301e9,
                nexus="verified",
                defense_share=0.88,
                annual_obligations=[AnnualObligation(fiscal_year=2025, obligations=1.0)],
                by_psc=[CategoryShare(code="2350", name="TANKS", obligations=2.0)],
            )
        ],
    )

    feed = export_defense_contractors(dcl, egraph=graph, awards=awards)
    by_name = {c.name: c for c in feed.contractors}
    gd = by_name["General Dynamics"]
    assert gd.total_obligations == 301e9 and gd.nexus == "verified"
    assert len(gd.awards) == 1
    award = gd.awards[0]
    assert award.entity_key == key and award.uei == "VF58HFRNGEL8"
    assert award.defense_share == 0.88 and award.annual_obligations and award.by_psc
    # A contractor with no matched recipient carries no dollars.
    assert by_name["Boeing"].awards == [] and by_name["Boeing"].total_obligations is None
    # Without an awards inventory the join is a no-op (a peer with no watchlist).
    peer = export_defense_contractors(dcl, egraph=graph, awards=None)
    assert all(c.total_obligations is None for c in peer.contractors)


def test_defense_feed_tags_every_contractor_with_its_register() -> None:
    """The "leads, not verdicts" caveat is typed, not prose (#1663, ME-D).

    Three registers, and the classifier must never collapse them: nothing matched is ``open``
    (a standing question, not a clearance), a bare name-pattern hit is ``inference``, and only a
    UEI-pinned award whose *curated* nexus is ``verified`` upgrades the corridor-presence claim.
    """
    from watermark.candidates import DefenseContractor, DefenseContractorList
    from watermark.pipeline.entities import Entity, EntityGraph, normalize_name
    from watermark.site.candidates import export_defense_contractors
    from watermark.usaspending import RecipientAward, UsaSpendingInventory

    gd_key = normalize_name("GENERAL DYNAMICS CORPORATION")
    gd = Entity(key=gd_key, kind="corporate", classification="corporate")
    gd.variants.add("GENERAL DYNAMICS CORPORATION")
    gd.uei = "VF58HFRNGEL8"
    ctx_key = normalize_name("CONTEXTUAL HOLDINGS LLC")
    ctx = Entity(key=ctx_key, kind="corporate", classification="corporate")
    ctx.variants.add("CONTEXTUAL HOLDINGS LLC")
    ctx.uei = "CTX000000001"
    graph = EntityGraph(entities={gd_key: gd, ctx_key: ctx})

    dcl = DefenseContractorList(
        defense_contractors=[
            DefenseContractor(name="General Dynamics", patterns=["GENERAL DYNAMICS CORPORATION"]),
            DefenseContractor(name="Contextual", patterns=["CONTEXTUAL HOLDINGS"]),
            DefenseContractor(name="Boeing", patterns=["BOEING"]),  # no corpus match
        ]
    )
    awards = UsaSpendingInventory(
        meta={},
        records=[
            RecipientAward(
                watchlist_name="General Dynamics Corp",
                recipient_id="gd-P",
                uei="VF58HFRNGEL8",
                recipient_name="GENERAL DYNAMICS CORPORATION",
                total_obligations=301e9,
                nexus="verified",
            ),
            RecipientAward(
                watchlist_name="Contextual Holdings",
                recipient_id="ctx-P",
                uei="CTX000000001",
                recipient_name="CONTEXTUAL HOLDINGS LLC",
                total_obligations=5e6,
                nexus="context",  # dollars, but no verified corridor tie
            ),
        ],
    )

    by_name = {
        c.name: c for c in export_defense_contractors(dcl, egraph=graph, awards=awards).contractors
    }
    assert by_name["General Dynamics"].tag == "verified"
    # Federal dollars alone do NOT verify a corridor presence — the curated nexus governs.
    assert by_name["Contextual"].tag == "inference"
    assert by_name["Boeing"].tag == "open"
    assert all(c.tag_basis for c in by_name.values()), "every register states its basis"

    # Drop the award join and the verified upgrade evaporates: the same name-pattern hit is
    # only ever a lead on its own.
    unjoined = {c.name: c for c in export_defense_contractors(dcl, egraph=graph).contractors}
    assert unjoined["General Dynamics"].tag == "inference"


def test_defense_scan_parcels_separate_ownership_from_attribution() -> None:
    """A parcel's GIS columns and the scan's claim about it carry DIFFERENT registers (#1663).

    This is the whole point of ME-D: "UNITED STATES owns this parcel" is verbatim from the county
    service, while "this is the JSMC" is an analyst reading. One tag for both would either
    launder the inference or discard the verified ownership.
    """
    from watermark.candidates import DefenseContractorList, DefenseLandScan
    from watermark.site.candidates import export_defense_contractors

    meta = candidates.load_defense_meta(_lima_settings())
    assert meta is not None, "Lima registers a defense GIS config"
    scan = DefenseLandScan(
        meta={},
        prime_owned=[{"parcel_no": "1", "owner": "BOEING CO", "matched_prime": "Boeing"}],
        army_controlled=[{"parcel_no": "2", "owner": "UNITED STATES"}],
    )
    feed = export_defense_contractors(DefenseContractorList(), scan=scan, defense_meta=meta)

    enclave = feed.army_controlled[0]
    assert enclave.record_tag == "verified"  # the ownership row is verbatim
    assert enclave.attribution_tag == "inference"  # the JSMC identification is not
    assert enclave.attribution is not None and "Joint Systems" in enclave.attribution
    assert enclave.attribution_basis and "verify against the deed" in enclave.attribution_basis
    # The GIS columns survive the projection untouched (extra="allow").
    assert enclave.model_dump()["owner"] == "UNITED STATES"

    owned = feed.prime_owned[0]
    assert owned.record_tag == "verified" and owned.attribution_tag == "inference"
    assert owned.attribution == "Boeing"

    # A site with no defense profile inherits nothing: the enclave rows keep their verified
    # ownership and assert no attribution rather than borrowing Lima's JSMC reading.
    peerless = export_defense_contractors(DefenseContractorList(), scan=scan, defense_meta=None)
    assert peerless.army_controlled[0].attribution is None
    assert peerless.army_controlled[0].attribution_tag == "open"
    assert peerless.army_controlled[0].record_tag == "verified"


def _lima_settings() -> Settings:
    return Settings(data_dir=REPO_ROOT / "data", site="lima")
