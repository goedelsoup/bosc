"""The relation-class overlay is additive-only: it classifies existing corpus
parties/edges, never adds a node, and drops any key/edge it can't resolve.
"""

from __future__ import annotations

from pathlib import Path

from bosc.config import Settings
from bosc.pipeline.corpus import load_corpus
from bosc.pipeline.entities import (
    Entity,
    EntityGraph,
    Relationship,
    build_entity_graph,
    enrich_with_relation_classes,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

_ENRICH = {
    "enrich_parcels": True,
    "enrich_lei": True,
    "enrich_rsei": True,
    "enrich_federal": True,
    "enrich_subdivisions": True,
}


def test_pure_graph_unclassified() -> None:
    """Without the overlay flag every relation_class is None (proves additivity)."""
    graph = build_entity_graph(load_corpus(), **_ENRICH)
    assert graph.entities, "graph should be non-empty"
    assert all(e.relation_class is None for e in graph.entities.values())
    assert all(r.relation_class == "" for r in graph.relationships)


def test_overlay_classifies_without_adding_nodes() -> None:
    """The committed overlay classifies parties/edges and adds no nodes/edges."""
    corpus = load_corpus()
    pure = build_entity_graph(corpus, **_ENRICH)
    overlaid = build_entity_graph(corpus, **_ENRICH, enrich_relation_classes=True)

    # No node or edge was added — purely additive annotation.
    assert len(overlaid.entities) == len(pure.entities)
    assert len(overlaid.relationships) == len(pure.relationships)

    classes = {e.key: e.relation_class for e in overlaid.entities.values() if e.relation_class}
    assert classes.get("BISTROZZI") == "bosc_relation"
    assert classes.get("ALLEN COUNTY BOARD OF COMMISSIONERS") == "direct_approval"
    assert classes.get("GOOGLE") == "possible_end_user"  # held as annotation, prose = confirmed
    assert classes.get("OTTAWA RIVER") == "environmental_beneficiary"
    # An edge was classified too.
    assert any(
        r.relation_class == "environmental_beneficiary" and r.rel == "discharges_to"
        for r in overlaid.relationships
    )


def test_overlay_drops_unknown_keys_and_classes(tmp_path: Path) -> None:
    """A key/edge absent from the graph (or an unknown class) is dropped, not added."""
    graph = EntityGraph()
    graph.entities["BISTROZZI"] = Entity(
        key="BISTROZZI", kind="corporate", classification="corporate_out_of_state"
    )
    graph.relationships.append(Relationship("BISTROZZI", "operates", "GHOST"))

    profiles = tmp_path / "entities" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "relation-classes.yaml").write_text(
        "entities:\n"
        "  - {key: BISTROZZI, relation_class: bosc_relation, basis: ok}\n"
        "  - {key: NOPE LLC, relation_class: direct_manage, basis: missing}\n"
        "  - {key: BISTROZZI, relation_class: not_a_class, basis: bad}\n",
        encoding="utf-8",
    )
    settings = Settings(data_dir=tmp_path)
    enrich_with_relation_classes(graph, settings=settings)

    # The valid one applied; the missing key and unknown class were dropped silently.
    assert graph.entities["BISTROZZI"].relation_class == "bosc_relation"
    assert len(graph.entities) == 1  # NOPE LLC was never added
