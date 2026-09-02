"""The BOSC → yidam corpus mirror (#1561).

The projection must satisfy yidam's two hard ``graph-check`` rules — every node carries a
``class:``/``label:`` and ≥1 outgoing link whose target file exists — while preserving the
``[verified]``/``[inference]``/``[reference]``/``[open]`` claim tags and per-site scope.
:func:`validate_mirror` replicates yidam ``graph-check``, so "clean" here means the real
``yidam graph-check`` would also pass over the written mirror.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import yaml

from tests.conftest import ExportedBundle
from watermark.config import Settings
from watermark.hypotheses import HYPOTHESES, HypothesisAssessment
from watermark.site import corpus_mirror
from watermark.site.corpus_mirror import (
    CLASSES,
    ONTOLOGY,
    UNIVERSAL_PROPERTIES,
    _claim_token,
    build_mirror,
    project_mirror,
    regenerate_mirror,
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
    assert _links_all_resolve(corpus)  # the projection's own edge invariant


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
        # Under `properties:` since #2132 — yidam reads an instance's properties from that
        # mapping and nowhere else, so a bare top-level key is invisible to the ontology.
        tags[path.stem] = data["properties"].get("claim_tag")
    # Leads carry their own tag; the open hypothesis cell is [open]. The value is the
    # BRACKETED token, not the bare word — `yidam open-questions` decides a node is open by
    # scanning its raw text for the literal `[open]`, so the bare form made the real binary
    # under-report (2 against the 20 then open). Readers normalize with `.strip("[]")`, so no
    # downstream feed value changed. See corpus_mirror._claim_token.
    assert tags["lead-lead-1"] == "[open]"
    assert tags["lead-lead-2"] == "[inference]"
    assert tags["open-water"] == "[open]"


def test_provenance_survives_projection(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    # Provenance nests under `properties:` (#2132), which is the mapping yidam reads an
    # instance's properties from — the bare top-level keys this projection wrote before were
    # invisible to the whole ontology layer.
    # entity keeps its source
    ent = yaml.safe_load((corpus / "artifact" / "google.yml").read_text())
    assert ent["properties"]["sources"] == ["oepa/permit.yaml"]
    # person keeps each source's evidentiary kind ([reference] here)
    person = yaml.safe_load((corpus / "artifact" / "person-jane-doe.yml").read_text())
    assert person["properties"]["sources"][0]["source_kind"] == "reference"
    # relationship keeps its document source
    rels = [yaml.safe_load(p.read_text()) for p in (corpus / "relation").glob("*.yml")]
    assert any(r["properties"].get("source") == "oepa/permit.yaml" for r in rels)


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
    assert _links_all_resolve(corpus)
    # minimum viable graph: the site anchor + 3 hypothesis nodes + 1 concept
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
    assert _links_all_resolve(corpus)  # both distinct, both connected


# --- the projection's own invariants (BOSC's contract, not a yidam report) -----------------
def _links_all_resolve(corpus: Path) -> bool:
    """Every outgoing link resolves to a file that exists, relative to its own node's directory.

    This is the guarantee :func:`write_mirror` makes, and it is checked here rather than by
    running ``yidam graph-check``: the reports belong to the binary now
    (:mod:`watermark.site.yidam_cli`), but a projection that emits dangling edges is a bug in
    *this* module and must fail without a Rust toolchain present.
    """
    for inst in sorted(corpus.rglob("*.yml")):
        if inst.name.endswith(".ont.yml"):
            continue
        data = yaml.safe_load(inst.read_text(encoding="utf-8")) or {}
        for link in data.get("links") or []:
            target = link.get("target")
            if not target or not (inst.parent / target).resolve().exists():
                return False
    return True


def test_projection_emits_no_dangling_edges(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    assert _links_all_resolve(corpus)


def test_every_node_carries_class_and_label(tmp_path: Path) -> None:
    """`missing-class` / `missing-label` are lint checks upstream; the projection must never
    produce either, so this asserts the input to those checks is already clean."""
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    for inst in corpus.rglob("*.yml"):
        # The corpus root holds two kinds of non-instance file: a `<class>.ont.yml` per class,
        # and `universal.yml` — the corpus speaking about itself rather than about one class.
        # Neither is a node, and the real `graph-check` does not read them as one either.
        if inst.name.endswith(".ont.yml") or inst.name == "universal.yml":
            continue
        data = yaml.safe_load(inst.read_text(encoding="utf-8")) or {}
        assert data.get("class"), f"{inst} has no class:"
        assert data.get("label"), f"{inst} has no label:"


# --- the claim token: what makes BOSC and yidam agree on "open" (F3) -----------------------
def test_claim_token_brackets_bare_tags_and_is_idempotent() -> None:
    assert _claim_token("open") == "[open]"
    assert _claim_token("[open]") == "[open]"
    assert _claim_token("inference") == "[inference]"
    assert _claim_token("") is None
    assert _claim_token(None) is None


def test_open_nodes_serialize_the_literal_bracket_token(tmp_path: Path) -> None:
    """``yidam open-questions`` decides a node is open by scanning its raw text for the literal
    ``[open]`` (``cmd/mod.rs::has_open_claim``). Storing the bare word made the real binary
    report 2 open questions where the replica reported 20 over the same tree — so the
    serialized bytes must carry it."""
    corpus = tmp_path / "corpus"
    write_mirror(_project(), corpus)
    open_lead = corpus / "question" / "lead-lead-1.yml"
    assert "[open]" in open_lead.read_text(encoding="utf-8")
    # ...and an [inference] lead must NOT read as open
    inference_lead = corpus / "question" / "lead-lead-2.yml"
    text = inference_lead.read_text(encoding="utf-8")
    assert "[inference]" in text and "[open]" not in text


# --- integration: the real committed Lima corpus -------------------------------------------
def test_regenerate_mirror_writes_corpus_and_reports(tmp_path: Path) -> None:
    """The one call behind `watermark corpus-mirror` and `watermark export`: over the real Lima
    corpus it writes the node tree, populates the corpus-index README, and drops all four
    node tree, and the projection satisfies the invariants the yidam reports check."""
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    corpus = tmp_path / ".yidam" / "corpus"
    # check=False: this asserts the PROJECTION, and must pass with no Rust toolchain installed.
    regen = regenerate_mirror(settings, corpus_dir=corpus, check=False)

    assert regen.ok  # unchecked is not failure
    assert not regen.checked
    assert regen.graph_check is None
    assert regen.mirror.nodes
    assert (corpus / "artifact" / "site-lima.yml").exists()
    assert _links_all_resolve(corpus)


def test_export_skips_the_canonical_mirror_for_a_redirected_bundle(
    exported_bundle: Callable[[str], ExportedBundle],
) -> None:
    """A redirected one-off export (``--out``, and every hermetic test) must NOT touch the
    repo's canonical .yidam/ mirror — the mirror regenerates only on ``watermark export`` with
    no ``--out``. The BundleResult reflects the skip.

    Read off conftest's shared Lima export (#1773), which is itself ``out_dir``-redirected — so
    this asserts the skip on the very bundle the rest of the suite consumes, instead of paying
    for a second full export to make the same three assertions.
    """
    shared = exported_bundle("lima")
    assert shared.mirror_nodes == 0
    assert shared.mirror_graph_issues == 0
    assert shared.mirror_checked is False


def test_build_mirror_over_the_real_lima_corpus_is_clean(tmp_path: Path) -> None:
    settings = Settings(data_dir=REPO_ROOT / "data", site="lima")
    mirror = build_mirror(settings)
    corpus = tmp_path / ".yidam" / "corpus"
    write_mirror(mirror, corpus)

    assert _links_all_resolve(corpus)  # the projection's own edge invariant
    counts = mirror.counts_by_class()
    # the reference site exercises every kind
    assert counts["hypothesis"] == 3
    assert counts["concept"] > 0
    assert counts["artifact"] > 1  # the site anchor + real entities
    assert counts["relation"] > 0
    assert counts["question"] > 0


# --- the class contract (#2132) -------------------------------------------------------------
def test_every_class_declares_a_contract_and_the_two_lists_agree() -> None:
    """`CLASSES` is display order and `ONTOLOGY` is the contract; a class in one and not the
    other would write a node directory with no schema, or a schema for nothing."""
    assert set(ONTOLOGY) == set(CLASSES)
    for name, ont in ONTOLOGY.items():
        assert ont.name == name, "the class name must match its key — the filename governs"
        assert ont.properties and ont.edges, f"`{name}` declares nothing"
        # Truthful only because the mirror is GENERATED: a relationship outside the declaration
        # is a bug in this module, not a coinage somebody made deliberately.
        assert ont.edge_policy == "exhaustive"


def test_every_declared_edge_targets_a_class_that_exists() -> None:
    for name, ont in ONTOLOGY.items():
        for edge in ont.edges:
            assert edge.target in CLASSES, f"`{name}` licenses `{edge.relationship}` into nothing"
            assert edge.direction == "out", (
                "the mirror authors every edge from the node that owns it"
            )


def test_the_declaration_covers_every_property_the_projection_writes() -> None:
    """The invariant behind `undeclared-property`, checked here rather than only by the binary.

    Declaring any `properties:` makes the class contract total: every property an instance
    carries must be declared on its class or in `UNIVERSAL_PROPERTIES`. A property this
    projection starts writing and nobody declares is an ERROR-severity lint finding, so it is
    worth failing on in a suite that runs without a Rust toolchain.
    """
    universal = {p.name for p in UNIVERSAL_PROPERTIES}
    mirror = build_mirror(Settings(site="lima", data_dir=REPO_ROOT / "data"))
    undeclared: set[tuple[str, str]] = set()
    for node in mirror.nodes:
        declared = {p.name for p in ONTOLOGY[node.node_class].properties} | universal
        undeclared |= {(node.node_class, k) for k in node.meta if k not in declared}
    assert not undeclared, f"undeclared properties: {sorted(undeclared)}"


def test_a_near_universal_property_is_declared_with_its_reason() -> None:
    """The four `missing-property` warnings this corpus carries are deliberate, and the
    declaration is where that decision is recorded — not a commit message nobody will find."""
    sources = next(p for p in ONTOLOGY["artifact"].properties if p.name == "sources")
    assert "site anchor" in sources.description
    lead_kind = next(p for p in ONTOLOGY["question"].properties if p.name == "lead_kind")
    assert "open-water" in lead_kind.description


def test_an_instance_nests_its_provenance_under_properties(tmp_path: Path) -> None:
    """yidam reads an instance's properties from that mapping and from NOWHERE else.

    Written as bare top-level keys — as this projection did until #2132 — they are invisible to
    the whole ontology layer: `undeclared-property` sees an instance with no properties at all,
    and `missing-property` reports every declared one as absent. Measured before the fix: 1,129
    findings over a corpus that was carrying all of them.
    """
    mirror = _project()
    write_mirror(mirror, tmp_path)
    node = next(p for p in (tmp_path / "artifact").glob("*.yml"))
    body = yaml.safe_load(node.read_text())
    assert "properties" in body and isinstance(body["properties"], dict)
    assert body["properties"], "the provenance is inside, not beside"
    for reserved in ("class", "label", "links"):
        assert reserved in body, "the reserved keys stay at the top level"
    assert "site" not in body, "a provenance key must not also sit at the top level"


def test_the_universal_declaration_is_written_beside_the_classes(tmp_path: Path) -> None:
    mirror = _project()
    write_mirror(mirror, tmp_path)
    body = yaml.safe_load((tmp_path / "universal.yml").read_text())
    assert {p["name"] for p in body["properties"]} == {p.name for p in UNIVERSAL_PROPERTIES}
    # Re-writing clears the previous one rather than leaving a stale file behind.
    write_mirror(mirror, tmp_path)
    assert (tmp_path / "universal.yml").is_file()


def test_every_relationship_the_projection_can_author_is_licensed() -> None:
    """The guard that would have caught the two undeclared fallbacks.

    `edge_policy: exhaustive` makes an unlicensed relationship an **ERROR**, and two of this
    module's edges are written only on a fallback path: a concept that cross-references no
    sibling gets `in-corpus`, and a relation whose endpoints both fail to resolve gets
    `in-site`. Neither fires against today's corpus, so declaring the vocabulary from the
    *emitted* mirror looked complete and was not — the first isolated glossary term or
    unresolved entity key would have failed the gate.

    So this reads the relationship literals out of the **source**, which is what the projection
    can author, rather than out of the graph, which is only what it happened to author here.
    """
    src = Path(corpus_mirror.__file__).read_text(encoding="utf-8")
    authored = set(re.findall(r'anchor_link\(\s*"([a-z][a-z-]*)"', src))
    authored |= set(re.findall(r'MirrorLink\([^,]+,\s*"([a-z][a-z-]*)"', src))
    assert authored, "the scan found no relationships — the pattern has rotted, not the code"
    # And the scan must be at least as complete as reality: every relationship the projection
    # actually wrote has to be one the patterns above found. Without this the regex could rot
    # into matching a subset and the guard would keep passing while covering less and less.
    built = {
        link.relationship
        for node in build_mirror(Settings(site="lima", data_dir=REPO_ROOT / "data")).nodes
        for link in node.links
        if link.relationship
    }
    assert built <= authored, (
        f"the source scan missed {sorted(built - authored)} — a new link-writing call shape "
        "was added and these patterns no longer see it"
    )

    licensed = {edge.relationship for ont in ONTOLOGY.values() for edge in ont.edges}
    assert authored <= licensed, (
        f"unlicensed relationship(s) {sorted(authored - licensed)} — under an exhaustive policy "
        "this is an ERROR the moment the path is taken, not a warning"
    )
