"""Graph exports (RDF Turtle + JSON-LD, GraphML) over the corpus mirror (#1574 · epic #1560 D1).

yidam ships ``yidam export rdf|graphml|sqlite`` — ontology-interchange serializations of the
corpus link graph. BOSC projects its committed corpus into that same yidam node graph (the
mirror, :mod:`watermark.site.corpus_mirror`, #1561), so this module is the Python peer of
yidam's ``export_rdf.rs`` / ``export_graphml.rs``: it renders the in-memory :class:`~watermark.site.corpus_mirror.Mirror`
as Turtle, JSON-LD, and GraphML downloadable research artifacts — generated at
``watermark export`` alongside the bundle and served from the wiki graph page.

**Faithful to the yidam Rust renderers** (``goedelsoup/yidam`` — the ground truth, not the
prose docs):

* the same IRI scheme — an instance is ``yidam://corpus/<class>/<name>`` (the mirror node id);
* the same vocabulary — ``owl`` classes, ``rdfs:label``, ``skos:definition``, ``prov``
  provenance, and the ``yidam:`` ontology namespace, with ``yidam:linksTo`` plus one
  ``owl:ObjectProperty`` per named relationship (``rdfs:subPropertyOf yidam:linksTo``);
* the same relationship → camelCase property sanitizer (``"relates to"`` → ``relatesTo``,
  ``"link"`` → ``linksTo``);
* the same link-target resolution (a link ``target:`` is a path relative to the *source node's
  class dir*, resolved back to a ``<class>/<name>`` id — :func:`resolve_link_target`, the peer
  of yidam's ``model::resolve_link_target``);
* unresolved link targets typed ``owl:Thing`` (RDF) / their edge skipped (GraphML), so a
  dangling link is never an export failure;
* the GraphML key set (``label``/``class``/``description``/``commit``/``outgoing_links``/
  ``incoming_links`` on nodes, ``type`` on edges), directed edges, and the 200-char
  description cap.

The BOSC mirror is always ``graph-check`` clean (every link resolves), so the unresolved path
is a belt-and-braces fidelity guarantee, not an expected state.

**That fidelity is now a test, not a claim** (#2053). ``tests/test_graph_exports.py`` runs the
real pinned binary over the same mirror and compares structurally — node/edge sets and the
GraphML key schema, subject IRIs and the ``yidam:`` predicate vocabulary. It is enforced in CI's
``corpus`` job, which asserts the binary can answer both formats before running, so the check
cannot pass by skipping.

It was written because the claim above had already stopped being true: the binary emitted
``yidam:genesisDate`` over this corpus and this module did not — :class:`ExportProvenance` had
always carried the field and :func:`resolve_provenance` never populated it. GraphML was
byte-for-byte sound the whole time. One half faithful, one half not, with no way to tell which.

**SQLite** — yidam's ``export sqlite`` is a *vector* DB (sqlite-vec ``vec0`` table of
embeddings); it needs the E4 vector index (#1564), so it is deferred to a follow-up. This
module covers the two graph-structure serializations #1574 turns on: RDF and GraphML.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.site.corpus_mirror import CLASSES, Mirror, resolve_link_target
from watermark.sites import active_profile

log = get_logger(__name__)

# --- vocabulary (identical to yidam's export_rdf.rs) ---------------------------------------
YIDAM_NS = "https://yidam.dev/ontology#"
OWL_NS = "http://www.w3.org/2002/07/owl#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS_NS = "http://www.w3.org/2004/02/skos/core#"
PROV_NS = "http://www.w3.org/ns/prov#"
XSD_NS = "http://www.w3.org/2001/XMLSchema#"

# The dataset IRI — the mirror IS the yidam corpus projection, so consumers expect this base
# (instances hang off it as ``yidam://corpus/<class>/<name>``). Kept verbatim from yidam.
DATASET_IRI = "yidam://corpus"

_GRAPHML_DESC_CAP = 200  # yidam truncates the GraphML node description to 200 chars


# --- provenance ----------------------------------------------------------------------------
@dataclass
class ExportProvenance:
    """The ontology-header provenance stamped into every graph export (yidam's ``Provenance``).

    ``domain`` becomes the ontology ``rdfs:label`` / the GraphML ``<graph id>``; ``commit`` and
    ``genesis`` land as ``yidam:commit`` / ``yidam:genesisDate``; ``generated_at`` (ISO-8601) is
    the ``prov:generatedAtTime``. Empty fields are simply omitted — nothing is fabricated.
    """

    domain: str
    commit: str = ""
    genesis: str = ""
    generated_at: str = ""


def _git_short_commit(repo_root: Path) -> str:
    """The repo's short HEAD sha, or ``""`` when git is unavailable (never raises)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return out.stdout.strip()


def _git_genesis_date(repo_root: Path) -> str:
    """The repo's first-commit date (``YYYY-MM-DD``), or ``""`` when git is unavailable.

    The peer of yidam's ``git::genesis_date``: resolve the root commit, then read its author
    date. This is what fills ``yidam:genesisDate`` in the RDF exports — a property BOSC's
    renderer has always supported and never populated, so the binary emitted 18 `yidam:`
    predicates over this corpus where BOSC emitted 17.

    Note it derives from the commit's **date**, not its message. yidam separately warns that
    BOSC's genesis message does not match its expected ``chore: genesis — <name>`` form and
    falls back to the directory name for the *domain* — a different field, and not one worth
    rewriting history to satisfy.
    """
    try:
        root = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if not root:
            return ""
        # `root[0]`, not the last: yidam takes `.lines().next()`. Identical while there is one
        # root commit, and this repo has one — but a grafted history would silently diverge.
        return subprocess.run(
            ["git", "log", "-1", "--format=%as", root[0]],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def resolve_provenance(
    settings: Settings | None = None, *, generated_at: str = ""
) -> ExportProvenance:
    """Assemble the export provenance for the active site (repo commit + site label + timestamp)."""
    settings = settings or get_settings()
    profile = active_profile(settings)
    label = profile.place or settings.site.replace("-", " ").title()
    return ExportProvenance(
        domain=f"BOSC corpus mirror — {label}",
        commit=_git_short_commit(settings.data_dir.parent),
        genesis=_git_genesis_date(settings.data_dir.parent),
        generated_at=generated_at,
    )


# --- link-target resolution (yidam model::resolve_link_target, in Python) -------------------
def property_local_name(relationship: str) -> str:
    """Relationship → RDF property local name (``"relates to"`` → ``relatesTo``); anything
    unusable, or the plain ``"link"``, falls back to ``linksTo``. Yidam's
    ``property_local_name``."""
    out: list[str] = []
    upper_next = False
    for ch in relationship:
        if ch.isascii() and ch.isalnum():
            out.append(ch.upper() if upper_next else ch)
            upper_next = False
        else:
            upper_next = bool(out)
    name = "".join(out)
    if not name or relationship == "link":
        return "linksTo"
    return name


# --- the resolved graph view (shared by all serializers) ------------------------------------
@dataclass
class _ResolvedInstance:
    """One mirror node with its links resolved to node ids — the serializer-agnostic view."""

    id: str  # <class>/<name>
    node_class: str
    label: str
    description: str
    links: list[tuple[str, str]]  # (target node id, relationship) in mirror order


@dataclass
class _GraphView:
    """The mirror mapped to the shared intermediate every serializer consumes (so they cannot
    drift), mirroring yidam's ``RdfView`` + ``corpus_nodes``."""

    instances: list[_ResolvedInstance]
    classes: list[str]  # sorted, every class an instance uses
    relationships: list[str]  # sorted property local names in use (beyond plain "link")
    unresolved: list[str]  # sorted target ids that resolve to no known instance
    incoming: dict[str, int]  # target id → resolved incoming-edge count

    @property
    def edge_count(self) -> int:
        """Resolved (non-dangling) edges — what GraphML emits."""
        return sum(self.incoming.values())


def _build_view(mirror: Mirror) -> _GraphView:
    """Resolve every mirror node's links to ids and collect the class/relationship/unresolved
    sets — the peer of yidam's ``build_view`` over ``corpus_nodes``."""
    known: set[str] = {node.id for node in mirror.nodes}
    instances: list[_ResolvedInstance] = []
    classes: set[str] = set()
    relationships: set[str] = set()
    unresolved: set[str] = set()
    incoming: dict[str, int] = {}

    for node in mirror.nodes:
        classes.add(node.node_class)
        links: list[tuple[str, str]] = []
        for link in node.links:
            target_id = resolve_link_target(node.node_class, link.target)
            if target_id not in known:
                unresolved.add(target_id)
            else:
                incoming[target_id] = incoming.get(target_id, 0) + 1
            prop = property_local_name(link.relationship)
            if prop != "linksTo":
                relationships.add(prop)
            links.append((target_id, link.relationship))
        instances.append(
            _ResolvedInstance(
                id=node.id,
                node_class=node.node_class,
                label=node.label,
                description=node.description,
                links=links,
            )
        )

    # `CLASSES` order for the present classes, then any extra (defensive) sorted after.
    ordered_classes = [c for c in CLASSES if c in classes] + sorted(classes - set(CLASSES))
    return _GraphView(
        instances=instances,
        classes=ordered_classes,
        relationships=sorted(relationships),
        unresolved=sorted(unresolved),
        incoming=incoming,
    )


# --- RDF: Turtle ----------------------------------------------------------------------------
def _ttl_literal(text: str) -> str:
    """A Turtle string literal — escape ``\\``, ``"``, and control whitespace."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def render_turtle(mirror: Mirror, prov: ExportProvenance) -> str:
    """Serialize the mirror as RDF Turtle — the peer of yidam's ``render_rdf_turtle``.

    Example SPARQL over the output — "all nodes of class concept"::

        PREFIX yidam: <https://yidam.dev/ontology#>
        SELECT ?node ?label WHERE { ?node a yidam:concept ; rdfs:label ?label . }
    """
    view = _build_view(mirror)
    lines: list[str] = [
        f"@prefix yidam: <{YIDAM_NS}> .",
        f"@prefix owl: <{OWL_NS}> .",
        f"@prefix rdfs: <{RDFS_NS}> .",
        f"@prefix rdf: <{RDF_NS}> .",
        f"@prefix skos: <{SKOS_NS}> .",
        f"@prefix prov: <{PROV_NS}> .",
        f"@prefix xsd: <{XSD_NS}> .",
        "",
    ]

    # Ontology header + provenance.
    header: list[str] = ["a owl:Ontology", f"rdfs:label {_ttl_literal(prov.domain)}"]
    if prov.generated_at:
        header.append(f"prov:generatedAtTime {_ttl_literal(prov.generated_at)}^^xsd:dateTime")
    if prov.commit:
        header.append(f"yidam:commit {_ttl_literal(prov.commit)}")
    if prov.genesis:
        header.append(f"yidam:genesisDate {_ttl_literal(prov.genesis)}")
    lines.append(f"<{DATASET_IRI}> " + " ;\n    ".join(header) + " .")
    lines.append("")

    # Classes.
    for cls in view.classes:
        lines.append(f"yidam:{cls} a owl:Class ;")
        lines.append(f"    rdfs:label {_ttl_literal(cls)} .")
        lines.append("")

    # Properties: linksTo + each named relationship as a subproperty.
    lines.append("yidam:linksTo a owl:ObjectProperty .")
    for rel in view.relationships:
        lines.append(f"yidam:{rel} a owl:ObjectProperty ;")
        lines.append("    rdfs:subPropertyOf yidam:linksTo .")
    lines.append("")

    # Instances.
    for inst in view.instances:
        preds: list[str] = [f"a yidam:{inst.node_class}"]
        if inst.label:
            preds.append(f"rdfs:label {_ttl_literal(inst.label)}")
        if inst.description:
            preds.append(f"skos:definition {_ttl_literal(inst.description)}")
        for target_id, relationship in inst.links:
            preds.append(f"yidam:{property_local_name(relationship)} <{DATASET_IRI}/{target_id}>")
        lines.append(f"<{DATASET_IRI}/{inst.id}> " + " ;\n    ".join(preds) + " .")

    # Unresolved targets exist as owl:Thing so links stay dereferenceable.
    for target_id in view.unresolved:
        lines.append("")
        lines.append(f"<{DATASET_IRI}/{target_id}> a owl:Thing ;")
        lines.append(f"    rdfs:comment {_ttl_literal('unresolved link target')} .")

    return "\n".join(lines).rstrip() + "\n"


# --- RDF: JSON-LD ---------------------------------------------------------------------------
def render_jsonld(mirror: Mirror, prov: ExportProvenance) -> str:
    """Serialize the mirror as JSON-LD (a ``@graph`` document with a ``@context`` mapping the
    same vocabulary the Turtle output uses) — the peer of yidam's ``render_rdf_jsonld``."""
    view = _build_view(mirror)
    graph: list[dict[str, object]] = []

    header: dict[str, object] = {
        "@id": DATASET_IRI,
        "@type": "owl:Ontology",
        "rdfs:label": prov.domain,
    }
    if prov.generated_at:
        header["prov:generatedAtTime"] = {"@value": prov.generated_at, "@type": "xsd:dateTime"}
    if prov.commit:
        header["yidam:commit"] = prov.commit
    if prov.genesis:
        header["yidam:genesisDate"] = prov.genesis
    graph.append(header)

    for cls in view.classes:
        graph.append({"@id": f"yidam:{cls}", "@type": "owl:Class", "rdfs:label": cls})

    graph.append({"@id": "yidam:linksTo", "@type": "owl:ObjectProperty"})
    for rel in view.relationships:
        graph.append(
            {
                "@id": f"yidam:{rel}",
                "@type": "owl:ObjectProperty",
                "rdfs:subPropertyOf": {"@id": "yidam:linksTo"},
            }
        )

    for inst in view.instances:
        obj: dict[str, object] = {
            "@id": f"{DATASET_IRI}/{inst.id}",
            "@type": f"yidam:{inst.node_class}",
        }
        if inst.label:
            obj["rdfs:label"] = inst.label
        if inst.description:
            obj["skos:definition"] = inst.description
        for target_id, relationship in inst.links:
            key = f"yidam:{property_local_name(relationship)}"
            entry = {"@id": f"{DATASET_IRI}/{target_id}"}
            existing = obj.get(key)
            if existing is None:
                obj[key] = entry
            elif isinstance(existing, list):
                existing.append(entry)
            else:
                obj[key] = [existing, entry]
        graph.append(obj)

    for target_id in view.unresolved:
        graph.append(
            {
                "@id": f"{DATASET_IRI}/{target_id}",
                "@type": "owl:Thing",
                "rdfs:comment": "unresolved link target",
            }
        )

    doc = {
        "@context": {
            "yidam": YIDAM_NS,
            "owl": OWL_NS,
            "rdfs": RDFS_NS,
            "skos": SKOS_NS,
            "prov": PROV_NS,
            "xsd": XSD_NS,
        },
        "@graph": graph,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# --- GraphML --------------------------------------------------------------------------------
def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def render_graphml(mirror: Mirror, prov: ExportProvenance) -> str:
    """Serialize the mirror's link graph as GraphML for Gephi / Cytoscape / yEd — the peer of
    yidam's ``render_graphml``.

    One ``<node>`` per mirror instance (stable id ``<class>/<name>``) carrying class, label,
    description, commit, and in/out link counts; one directed ``<edge>`` per *resolved* link
    with a ``type`` attribute for the relationship. Edges to unknown targets are skipped (a
    dangling link is a corpus lint problem, not an export failure)."""
    view = _build_view(mirror)
    known: set[str] = {inst.id for inst in view.instances}

    out: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns"',
        '         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns '
        'http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="class" for="node" attr.name="class" attr.type="string"/>',
        '  <key id="description" for="node" attr.name="description" attr.type="string"/>',
        '  <key id="commit" for="node" attr.name="commit" attr.type="string"/>',
        '  <key id="outgoing_links" for="node" attr.name="outgoing_links" attr.type="int"/>',
        '  <key id="incoming_links" for="node" attr.name="incoming_links" attr.type="int"/>',
        '  <key id="type" for="edge" attr.name="type" attr.type="string"/>',
        f'  <graph id="{_xml_escape(prov.domain)}" edgedefault="directed">',
    ]

    for inst in view.instances:
        desc = _xml_escape(inst.description[:_GRAPHML_DESC_CAP])
        out.append(f'    <node id="{_xml_escape(inst.id)}">')
        out.append(f'      <data key="label">{_xml_escape(inst.label)}</data>')
        out.append(f'      <data key="class">{_xml_escape(inst.node_class)}</data>')
        out.append(f'      <data key="description">{desc}</data>')
        out.append(f'      <data key="commit">{_xml_escape(prov.commit)}</data>')
        out.append(f'      <data key="outgoing_links">{len(inst.links)}</data>')
        out.append(f'      <data key="incoming_links">{view.incoming.get(inst.id, 0)}</data>')
        out.append("    </node>")

    edge_id = 0
    for inst in view.instances:
        for target_id, relationship in inst.links:
            if (
                target_id not in known
            ):  # dangling — skip the edge (yidam warns; the mirror never dangles)
                continue
            out.append(
                f'    <edge id="e{edge_id}" source="{_xml_escape(inst.id)}" '
                f'target="{_xml_escape(target_id)}">'
            )
            out.append(f'      <data key="type">{_xml_escape(relationship)}</data>')
            out.append("    </edge>")
            edge_id += 1

    out.append("  </graph>")
    out.append("</graphml>")
    return "\n".join(out) + "\n"


# --- write ---------------------------------------------------------------------------------
@dataclass
class GraphExport:
    """One rendered graph-export artifact — its manifest identity + payload."""

    name: str  # manifest name, e.g. "corpus-graph.ttl"
    filename: str  # file basename under the exports dir, e.g. "corpus.ttl"
    fmt: str  # "turtle" | "jsonld" | "graphml"
    media_type: str
    text: str
    node_count: int
    edge_count: int


# The three artifacts #1574 emits, in display order. yidam's default output names: corpus.ttl /
# corpus.jsonld / corpus.graphml.
_SPECS: tuple[tuple[str, str, str], ...] = (
    ("corpus.ttl", "turtle", "text/turtle"),
    ("corpus.jsonld", "jsonld", "application/ld+json"),
    ("corpus.graphml", "graphml", "application/graphml+xml"),
)


def render_exports(mirror: Mirror, prov: ExportProvenance) -> list[GraphExport]:
    """Render all graph-export formats over ``mirror`` (pure, no I/O)."""
    view = _build_view(mirror)
    node_count = len(view.instances)
    edge_count = view.edge_count
    renderers = {
        "turtle": render_turtle,
        "jsonld": render_jsonld,
        "graphml": render_graphml,
    }
    exports: list[GraphExport] = []
    for filename, fmt, media_type in _SPECS:
        exports.append(
            GraphExport(
                name=f"corpus-graph.{filename.split('.')[-1]}",
                filename=filename,
                fmt=fmt,
                media_type=media_type,
                text=renderers[fmt](mirror, prov),
                node_count=node_count,
                edge_count=edge_count,
            )
        )
    return exports


def write_exports(mirror: Mirror, out_dir: Path, prov: ExportProvenance) -> list[GraphExport]:
    """Render + write the graph exports into ``out_dir`` (created if needed); returns the set.

    ``out_dir`` is the exports subtree of the target — ``<bundle>/exports`` under ``watermark
    export``, or ``.yidam/exports`` for a standalone ``watermark corpus-mirror --exports``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    exports = render_exports(mirror, prov)
    for exp in exports:
        (out_dir / exp.filename).write_text(exp.text, encoding="utf-8")
    log.info(
        "graph_exports.written",
        dir=str(out_dir),
        formats=[e.fmt for e in exports],
        nodes=exports[0].node_count if exports else 0,
        edges=exports[0].edge_count if exports else 0,
    )
    return exports


def default_exports_dir(settings: Settings | None = None) -> Path:
    """Standalone exports location — ``<repo-root>/.yidam/exports`` (git-ignored, like the mirror)."""
    settings = settings or get_settings()
    return settings.data_dir.parent / ".yidam" / "exports"


__all__ = [
    "ExportProvenance",
    "GraphExport",
    "default_exports_dir",
    "property_local_name",
    "render_exports",
    "render_graphml",
    "render_jsonld",
    "render_turtle",
    "resolve_link_target",
    "resolve_provenance",
    "write_exports",
]
