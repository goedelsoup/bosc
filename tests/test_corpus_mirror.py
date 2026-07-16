"""The BOSC → yidam corpus mirror (#1561).

The projection must satisfy yidam's two hard ``graph-check`` rules — every node carries a
``class:``/``label:`` and ≥1 outgoing link whose target file exists — while preserving the
``[verified]``/``[inference]``/``[reference]``/``[open]`` claim tags and per-site scope.
:func:`validate_mirror` replicates yidam ``graph-check``, so "clean" here means the real
``yidam graph-check`` would also pass over the written mirror.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from watermark.config import Settings
from watermark.hypotheses import HYPOTHESES, HypothesisAssessment
from watermark.site.corpus_mirror import (
    build_mirror,
    project_mirror,
    render_corpus_index,
    validate_mirror,
    write_mirror,
)
from watermark.site.feeds import (
    Citation,
    ConceptItem,
    EntityNode,
    LeadItem,
    PersonItem,
    RelationshipEdge,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- fixtures: a small, connected synthetic corpus -----------------------------------------
def _entities() -> list[EntityNode]:
    return [
        EntityNode(
            key="GOOGLE",
            display="Google LLC",
            kind="corporate",
            classification="operator",
            relation_class="operator",
            sources=["oepa/permit.yaml"],
        ),
        EntityNode(
            key="npdes:1AB00001",
            display="NPDES 1AB00001",
            kind="permit",
            classification="permit",
        ),
    ]


def _relationships() -> list[RelationshipEdge]:
    return [
        RelationshipEdge(
            src="GOOGLE",
            rel="operates",
            dst="npdes:1AB00001",
            ref="1AB00001*ED",
            source="oepa/permit.yaml",
        ),
        # An edge whose endpoints are NOT in the entity set — must still stay connected.
        RelationshipEdge(src="GHOST-A", rel="linked-to", dst="GHOST-B", source="x.yaml"),
    ]


def _concepts() -> list[ConceptItem]:
    return [
        ConceptItem(
            slug="7q10",
            title="7Q10",
            kind="term",
            summary="A design low flow.",
            related=["assimilative-capacity"],
            tags=["hydrology"],
        ),
        ConceptItem(
            slug="assimilative-capacity",
            title="Assimilative Capacity",
            summary="How much load a stream can take.",
            related=["7q10"],
        ),
        # `related` points at a concept that is NOT emitted → falls back to the anchor.
        ConceptItem(slug="orphan-concept", title="Orphan Concept", related=["does-not-exist"]),
    ]


def _people() -> list[PersonItem]:
    return [
        PersonItem(
            slug="jane-doe",
            name="Jane Doe",
            entity_key="GOOGLE",  # resolves into the entity set
            summary="An operator principal.",
            expanded=True,
            sources=[Citation(source="history/allen-oh/book.yaml", source_kind="reference")],
        ),
        PersonItem(slug="john-roe", name="John Roe", summary="No entity link.", expanded=True),
    ]


def _leads() -> list[LeadItem]:
    return [
        LeadItem(
            id="lead-1",
            kind="question",
            status="unanswered",
            tag="open",
            title="An open question",
            detail="Still chasing.",
            source="audit.md",
        ),
        LeadItem(
            id="lead-2",
            kind="claim",
            status="review",
            tag="inference",
            title="An inferred claim",
            detail="Not yet corroborated.",
            source="deed.yaml",
        ),
    ]


def _open_claims() -> list[HypothesisAssessment]:
    return [
        HypothesisAssessment(
            site="lima",
            hypothesis="water",
            signal="watch",
            tag="open",
            sub_thesis="coercion",
            group="coercion",
            fields={"wwtp": "City of Lima"},
        ),
    ]


def _project(**overrides: object):
    kwargs: dict[str, object] = {
        "site": "lima",
        "site_label": "Lima, Ohio",
        "entities": _entities(),
        "relationships": _relationships(),
        "concepts": _concepts(),
        "people": _people(),
        "leads": _leads(),
        "hypotheses": HYPOTHESES,
        "open_claims": _open_claims(),
    }
    kwargs.update(overrides)
    return project_mirror(**kwargs)  # type: ignore[arg-type]


# --- the core guarantees -------------------------------------------------------------------
def test_projection_writes_a_graph_check_clean_mirror(tmp_path: Path) -> None:
    corpus = tmp_path / ".yidam" / "corpus"
    write_mirror(_project(), corpus)
    assert validate_mirror(corpus) == []  # the yidam graph-check rules pass


def test_every_node_has_at_least_one_outgoing_link(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    mirror = _project()
    write_mirror(mirror, corpus)
    for node in mirror.nodes:
        assert node.links, f"{node.id} is an orphan (no outgoing links)"
    # and every emitted class has a schema file (no unknown-class graph-check error)
    for node_class in mirror.classes:
        assert (corpus / f"{node_class}.ont.yml").exists()


def test_all_five_yidam_kinds_are_projected(tmp_path: Path) -> None:
    mirror = _project()
    assert set(mirror.counts_by_class()) == {
        "concept",
        "relation",
        "artifact",
        "question",
        "hypothesis",
    }
    # the site anchor + entities + people all land in `artifact`
    names = {n.name for n in mirror.nodes if n.node_class == "artifact"}
    assert "site-lima" in names
    assert "person-jane-doe" in names


def test_claim_tags_are_preserved(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    tags = {}
    for path in (corpus / "question").glob("*.yml"):
        data = yaml.safe_load(path.read_text())
        tags[path.stem] = data.get("claim_tag")
    # leads carry their own tag (open|inference); the open hypothesis cell is [open]
    assert tags["lead-lead-1"] == "open"
    assert tags["lead-lead-2"] == "inference"
    assert tags["open-water"] == "open"


def test_provenance_survives_projection(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    # entity keeps its source
    ent = yaml.safe_load((corpus / "artifact" / "google.yml").read_text())
    assert ent["sources"] == ["oepa/permit.yaml"]
    # person keeps each source's evidentiary kind ([reference] here)
    person = yaml.safe_load((corpus / "artifact" / "person-jane-doe.yml").read_text())
    assert person["sources"][0]["source_kind"] == "reference"
    # relationship keeps its document source
    rels = [yaml.safe_load(p.read_text()) for p in (corpus / "relation").glob("*.yml")]
    assert any(r.get("source") == "oepa/permit.yaml" for r in rels)


def test_relationship_edges_point_at_their_entities(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    # the resolved edge links to both entity artifacts...
    edge = yaml.safe_load(
        (corpus / "relation" / "google--operates--npdes-1ab00001.yml").read_text()
    )
    targets = {link["target"] for link in edge["links"]}
    assert "../artifact/google.yml" in targets
    assert "../artifact/npdes-1ab00001.yml" in targets
    # ...and the unresolved (ghost) edge falls back to the site anchor, never orphaning
    ghost = yaml.safe_load((corpus / "relation" / "ghost-a--linked-to--ghost-b.yml").read_text())
    assert ghost["links"] == [{"target": "../artifact/site-lima.yml", "relationship": "in-site"}]


def test_concept_related_links_resolve_or_fall_back(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    # a concept whose `related` is emitted links to the sibling
    c = yaml.safe_load((corpus / "concept" / "7q10.yml").read_text())
    assert {"target": "assimilative-capacity.yml", "relationship": "related"} in c["links"]
    # a concept whose `related` is absent falls back to the anchor (still ≥1 valid link)
    o = yaml.safe_load((corpus / "concept" / "orphan-concept.yml").read_text())
    assert o["links"] == [{"target": "../artifact/site-lima.yml", "relationship": "in-corpus"}]


def test_thin_site_is_still_connected(tmp_path: Path) -> None:
    """A peer with no entities/relationships/leads still yields a clean, connected graph."""
    corpus = tmp_path / "corpus"
    mirror = _project(
        entities=[],
        relationships=[],
        people=[],
        leads=[],
        open_claims=[],
        concepts=[ConceptItem(slug="only", title="Only Concept")],
    )
    write_mirror(mirror, corpus)
    assert validate_mirror(corpus) == []
    # minimum viable graph: the site anchor + 3 hypothesis lenses + 1 concept
    assert mirror.counts_by_class() == {"concept": 1, "artifact": 1, "hypothesis": 3}


def test_slug_collisions_are_deduped(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    mirror = _project(
        entities=[
            EntityNode(key="Acme, LLC", display="Acme A", kind="corporate", classification="x"),
            EntityNode(key="Acme LLC", display="Acme B", kind="corporate", classification="x"),
        ],
        relationships=[],
        people=[],
        leads=[],
        open_claims=[],
    )
    write_mirror(mirror, corpus)
    files = {p.name for p in (corpus / "artifact").glob("*.yml")}
    assert "acme-llc.yml" in files and "acme-llc-2.yml" in files
    assert validate_mirror(corpus) == []  # both distinct, both connected


# --- the validator itself (it must actually catch bad graphs) ------------------------------
def test_validate_mirror_flags_orphan_class_and_broken_link(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    (corpus / "concept").mkdir(parents=True)
    (corpus / "concept.ont.yml").write_text("class: concept\n")
    # orphan: no links; also missing label
    (corpus / "concept" / "orphan.yml").write_text("class: concept\n")
    # broken link + unknown class
    (corpus / "concept" / "bad.yml").write_text(
        "class: nonesuch\nlabel: Bad\nlinks:\n  - target: nowhere.yml\n"
    )
    issues = {i.node: i.problems for i in validate_mirror(corpus)}
    assert any("orphan node" in p for p in issues["concept/orphan.yml"])
    assert any("missing 'label:'" in p for p in issues["concept/orphan.yml"])
    assert any("broken link" in p for p in issues["concept/bad.yml"])
    assert any("unknown class" in p for p in issues["concept/bad.yml"])


def test_render_corpus_index_lists_instances(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    index = render_corpus_index(corpus)
    assert "| Instance | Class | Label | Links out | Lines |" in index
    assert "site-lima.yml" in index


# --- integration: the real committed Lima corpus -------------------------------------------
def test_build_mirror_over_the_real_lima_corpus_is_clean(tmp_path: Path) -> None:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    mirror = build_mirror(settings)
    corpus = tmp_path / ".yidam" / "corpus"
    write_mirror(mirror, corpus)

    assert validate_mirror(corpus) == []  # yidam graph-check would pass
    counts = mirror.counts_by_class()
    # the reference site exercises every kind
    assert counts["hypothesis"] == 3
    assert counts["concept"] > 0
    assert counts["artifact"] > 1  # the site anchor + real entities
    assert counts["relation"] > 0
    assert counts["question"] > 0
