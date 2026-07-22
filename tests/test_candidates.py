"""Candidate-entity store: load/validate the committed inventory."""

from __future__ import annotations

from pathlib import Path

from watermark import candidates

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
