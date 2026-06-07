"""Candidate-entity store: load/validate the committed inventory + site rendering."""

from __future__ import annotations

from pathlib import Path

from bosc import candidates
from bosc.pipeline.entities import EntityGraph
from bosc.site import candidates as site_candidates

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


def test_render_includes_caution_and_tiers() -> None:
    inv = candidates.load_cloud_consumer_candidates(ENTITIES)
    assert inv is not None
    page = site_candidates.render_candidates(inv, egraph=EntityGraph())
    assert "# Cloud-consumer candidates" in page
    assert "not customers or connections" in page.lower()
    assert "## Tier 1" in page
    # a known entity from the inventory renders
    assert "Ford Lima Engine Plant" in page
