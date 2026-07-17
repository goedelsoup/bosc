"""Graph exports — RDF (Turtle + JSON-LD) + GraphML over the corpus mirror (#1574, epic #1560 D1).

These serializers are the Python peer of yidam's ``export_rdf.rs`` / ``export_graphml.rs``: same
IRI scheme (``yidam://corpus/<class>/<name>``), same vocabulary (owl/rdfs/skos/prov + ``yidam:``),
same relationship→camelCase sanitizer, same link-target resolution, same GraphML key set. The
tests assert that fidelity structurally (parse the XML/JSON back; check the Turtle triples), so a
drift from the yidam renderers is caught here rather than by a downstream consumer.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from watermark.hypotheses import HYPOTHESES, HypothesisAssessment
from watermark.site.corpus_mirror import Mirror, MirrorLink, MirrorNode, project_mirror
from watermark.site.feeds import ConceptItem, EntityNode, LeadItem, PersonItem, RelationshipEdge
from watermark.site.graph_exports import (
    DATASET_IRI,
    ExportProvenance,
    property_local_name,
    render_exports,
    render_graphml,
    render_jsonld,
    render_turtle,
    resolve_link_target,
    write_exports,
)

GRAPHML_NS = "{http://graphml.graphdrawing.org/xmlns}"

PROV = ExportProvenance(
    domain="BOSC corpus mirror — Lima, Ohio",
    commit="abc1234",
    genesis="2026-01-01",
    generated_at="2026-01-01T00:00:00+00:00",
)


# --- a small, connected synthetic mirror (the corpus_mirror projection over toy feeds) -------
def _mirror() -> Mirror:
    entities = [
        EntityNode(key="GOOGLE", display="Google LLC", kind="corporate", classification="operator"),
        EntityNode(
            key="npdes:1AB00001", display="NPDES 1AB00001", kind="permit", classification="permit"
        ),
    ]
    relationships = [
        RelationshipEdge(src="GOOGLE", rel="operates", dst="npdes:1AB00001", source="permit.yaml"),
    ]
    concepts = [
        ConceptItem(slug="7q10", title="7Q10", summary='A design low flow, with "quotes".'),
    ]
    people = [PersonItem(slug="jane-doe", name="Jane Doe", entity_key="GOOGLE", expanded=True)]
    leads = [
        LeadItem(
            id="lead-1",
            kind="question",
            status="unanswered",
            tag="open",
            title="An open question",
            detail="Still chasing.",
            source="audit.md",
        )
    ]
    open_claims = [
        HypothesisAssessment(site="lima", hypothesis="water", signal="watch", tag="open"),
    ]
    return project_mirror(
        site="lima",
        site_label="Lima, Ohio",
        entities=entities,
        relationships=relationships,
        concepts=concepts,
        people=people,
        leads=leads,
        hypotheses=HYPOTHESES,
        open_claims=open_claims,
    )


# --- link-target resolution (yidam model::resolve_link_target) ------------------------------
def test_resolve_link_target_matches_yidam() -> None:
    assert resolve_link_target("reach", "alpha.yml") == "reach/alpha"
    assert resolve_link_target("reach", "../concept/formation.yml") == "concept/formation"
    assert resolve_link_target("reach", "./beta.yml") == "reach/beta"
    # escapes the corpus dir → returned verbatim
    assert resolve_link_target("reach", "../../skills/x.md") == "../../skills/x.md"


def test_property_local_name_sanitizes() -> None:
    assert property_local_name("causes") == "causes"
    assert property_local_name("relates to") == "relatesTo"
    assert property_local_name("assessed-under") == "assessedUnder"
    assert property_local_name("link") == "linksTo"
    assert property_local_name("???") == "linksTo"


# --- RDF: Turtle ----------------------------------------------------------------------------
def test_turtle_has_prefixes_ontology_header_and_provenance() -> None:
    ttl = render_turtle(_mirror(), PROV)
    assert "@prefix yidam: <https://yidam.dev/ontology#> ." in ttl
    assert "a owl:Ontology" in ttl
    assert "BOSC corpus mirror — Lima, Ohio" in ttl
    assert 'yidam:commit "abc1234"' in ttl
    assert 'yidam:genesisDate "2026-01-01"' in ttl
    assert "^^xsd:dateTime" in ttl


def test_turtle_types_instances_and_carries_named_relationships() -> None:
    mirror = _mirror()
    ttl = render_turtle(mirror, PROV)
    # every instance is typed by its class and reachable by its full IRI
    for node in mirror.nodes:
        assert f"<{DATASET_IRI}/{node.id}>" in ttl
    assert "a yidam:concept" in ttl
    assert "a yidam:relation" in ttl
    # a named relationship becomes a yidam: object property + subproperty declaration
    assert "yidam:linksTo a owl:ObjectProperty ." in ttl
    assert "rdfs:subPropertyOf yidam:linksTo" in ttl
    # the concept's quoted definition is escaped
    assert 'skos:definition "A design low flow, with \\"quotes\\"."' in ttl


def test_turtle_is_deterministic() -> None:
    mirror = _mirror()
    assert render_turtle(mirror, PROV) == render_turtle(mirror, PROV)


# --- RDF: JSON-LD ---------------------------------------------------------------------------
def test_jsonld_is_valid_with_context_and_graph() -> None:
    mirror = _mirror()
    doc = json.loads(render_jsonld(mirror, PROV))
    assert doc["@context"]["yidam"] == "https://yidam.dev/ontology#"
    graph = doc["@graph"]
    by_id = {o["@id"]: o for o in graph}

    ontology = by_id[DATASET_IRI]
    assert ontology["@type"] == "owl:Ontology"
    assert ontology["prov:generatedAtTime"] == {
        "@value": "2026-01-01T00:00:00+00:00",
        "@type": "xsd:dateTime",
    }

    # the resolved entity relationship edge points from GOOGLE to the permit
    google = next(n for n in mirror.nodes if n.name and n.label == "Google LLC")
    google_obj = by_id[f"{DATASET_IRI}/{google.id}"]
    assert google_obj["@type"] == "yidam:artifact"
    # every yidam:* relationship value dereferences to an @id
    for key, value in google_obj.items():
        if key.startswith("yidam:"):
            entries = value if isinstance(value, list) else [value]
            for entry in entries:
                assert entry["@id"].startswith(f"{DATASET_IRI}/")


def test_jsonld_classes_and_properties_declared() -> None:
    doc = json.loads(render_jsonld(_mirror(), PROV))
    ids = {o["@id"] for o in doc["@graph"]}
    assert "yidam:concept" in ids
    assert "yidam:linksTo" in ids
    types = {o["@id"]: o["@type"] for o in doc["@graph"]}
    assert types["yidam:concept"] == "owl:Class"
    assert types["yidam:linksTo"] == "owl:ObjectProperty"


# --- GraphML --------------------------------------------------------------------------------
def test_graphml_round_trips_through_xml_parser() -> None:
    mirror = _mirror()
    xml = render_graphml(mirror, PROV)
    root = ET.fromstring(xml)
    graph = root.find(f"{GRAPHML_NS}graph")
    assert graph is not None
    nodes = graph.findall(f"{GRAPHML_NS}node")
    edges = graph.findall(f"{GRAPHML_NS}edge")
    # one node per mirror instance; edges = resolved (non-dangling) links
    assert len(nodes) == len(mirror.nodes)
    resolved_edges = render_exports(mirror, PROV)[0].edge_count
    assert len(edges) == resolved_edges

    node_ids = {n.get("id") for n in nodes}
    assert node_ids == {node.id for node in mirror.nodes}
    # every edge endpoint is a real node (no dangling edge emitted)
    for edge in edges:
        assert edge.get("source") in node_ids
        assert edge.get("target") in node_ids


def test_graphml_nodes_carry_attributes_and_escape() -> None:
    xml = render_graphml(_mirror(), PROV)
    assert '<data key="commit">abc1234</data>' in xml
    assert 'key="outgoing_links"' in xml
    assert 'key="incoming_links"' in xml
    # edge `type` carries the mirror's raw relationship (the relation node fans out from→to its
    # subject/object entities); GraphML keeps it verbatim (unlike the RDF camelCase property).
    assert 'key="type">from</data>' in xml
    assert 'key="type">to</data>' in xml


def test_graphml_description_truncates_to_200_chars() -> None:
    long = "x" * 400
    node = MirrorNode(
        "concept", "long", label="Long", description=long, links=[MirrorLink("long.yml", "self")]
    )
    xml = render_graphml(Mirror(site="lima", nodes=[node]), PROV)
    assert "x" * 200 in xml
    assert "x" * 201 not in xml


# --- unresolved link targets (belt-and-braces: the real mirror never dangles) ---------------
def test_unresolved_target_becomes_owl_thing_and_skips_graphml_edge() -> None:
    node = MirrorNode(
        "concept",
        "alpha",
        label="Alpha",
        links=[MirrorLink("missing.yml", "link")],  # resolves to concept/missing, not present
    )
    mirror = Mirror(site="lima", nodes=[node])

    ttl = render_turtle(mirror, PROV)
    assert f"<{DATASET_IRI}/concept/missing> a owl:Thing" in ttl
    assert "unresolved link target" in ttl

    doc = json.loads(render_jsonld(mirror, PROV))
    thing = next(o for o in doc["@graph"] if o["@id"] == f"{DATASET_IRI}/concept/missing")
    assert thing["@type"] == "owl:Thing"

    xml = render_graphml(mirror, PROV)
    root = ET.fromstring(xml)
    graph = root.find(f"{GRAPHML_NS}graph")
    assert graph is not None
    assert graph.findall(f"{GRAPHML_NS}edge") == []  # dangling edge skipped


# --- writing --------------------------------------------------------------------------------
def test_write_exports_emits_three_named_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "exports"
    exports = write_exports(_mirror(), out, PROV)
    assert {e.filename for e in exports} == {"corpus.ttl", "corpus.jsonld", "corpus.graphml"}
    assert {e.name for e in exports} == {
        "corpus-graph.ttl",
        "corpus-graph.jsonld",
        "corpus-graph.graphml",
    }
    for exp in exports:
        assert (out / exp.filename).is_file()
        assert (out / exp.filename).read_text(encoding="utf-8") == exp.text
        assert exp.node_count == len(_mirror().nodes)
    # media types line up with the formats
    by_fmt = {e.fmt: e.media_type for e in exports}
    assert by_fmt == {
        "turtle": "text/turtle",
        "jsonld": "application/ld+json",
        "graphml": "application/graphml+xml",
    }
