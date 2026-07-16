"""Project the BOSC corpus into yidam node format (Epic #1560, E1 · #1561).

``yidam overlay`` bootstraps an **empty** ``.yidam/corpus/``; every yidam report
(``corpus-index``, ``graph-check``, ``open-questions``), MCP resource, and the vector
index read *node files* from there. yidam does **not** read BOSC's Pydantic/YAML/markdown
corpus. This module is the bridge: ``watermark corpus-mirror`` projects the committed
corpus — entities, relationships, the wiki concepts, profiled people, the per-site leads
board, the boom-origin hypotheses, and the ``[open]`` claims — into yidam corpus nodes.

**The yidam node format** (from the `goedelsoup/yidam` CLI — `walk.rs`/`parse.rs`/`corpus.rs`,
which are the ground truth, not the prose docs). A corpus lives under ``.yidam/corpus/``:

* ``<class>.ont.yml`` — one class-schema file per node *kind*, at the corpus root.
* ``<class>/<name>.yml`` — one instance node per file, inside its class dir. Each parses as
  ``{class, label, description?, links: [{target, relationship?}]}``; **unknown keys are
  ignored** by yidam's parser, so a node also carries the BOSC provenance it was projected
  from (``site``, ``scope``, ``claim_tag``, ``source``, …) as extra fields — lossless for
  the downstream index and #1562+ tooling.

The node **kind is the class (directory)**. This mirror uses the five the issue names:

===========  ==================================================================
kind         projected from
===========  ==================================================================
``concept``  the wiki glossary (:class:`~watermark.site.feeds.ConceptItem`)
``relation`` the entity-graph edges (:class:`~watermark.site.feeds.RelationshipEdge`)
``artifact`` the site anchor + resolved entities + profiled people
``question`` the per-site leads board + the ``[open]``-tagged hypothesis claims
``hypothesis`` the network's boom-origin lenses (:data:`watermark.hypotheses.HYPOTHESES`)
===========  ==================================================================

**Two hard yidam rules this module must satisfy** (its ``graph-check`` gate, replicated in
:func:`validate_mirror`): every instance has a ``class:`` matching a ``<class>.ont.yml`` and a
``label:``, and **every node emits ≥1 outgoing link whose target file exists**. The projection
guarantees the second by giving every node at least one edge to a node that is always present:
the **site anchor** (``artifact/site-<slug>``, which links out to the three hypothesis nodes).
So the graph is always connected and never orphaned, even for a thin peer site.

**Per-site & regenerable.** The mirror is projected for the active site (``settings.site``);
every node is ``site:``-tagged, and the network-shared kinds (concepts, hypotheses) carry
``scope: network``. The mirror is a git-ignored, regenerated artifact — never a source of
truth (the committed corpus is). Claim tags (``[verified]``/``[inference]``/``[reference]``/
``[open]``) are preserved: leads and open hypothesis claims carry ``claim_tag``; entities and
people carry their sources' :class:`~watermark.provenance.SourceKind` verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings
from watermark.hypotheses import HYPOTHESES, Hypothesis, HypothesisAssessment, load_assessments
from watermark.logging import get_logger
from watermark.people import load_people
from watermark.pipeline.corpus import load_corpus
from watermark.pipeline.entities import build_entity_graph
from watermark.site import concepts as concepts_mod
from watermark.site import graph as graph_mod
from watermark.site import leads as leads_mod
from watermark.site import people as people_mod
from watermark.site.feeds import (
    ConceptItem,
    EntityNode,
    LeadItem,
    PersonItem,
    RelationshipEdge,
)
from watermark.sites import active_profile, site_scoped_path

log = get_logger(__name__)

# The five yidam node kinds this mirror emits (the issue's taxonomy). Each becomes a class
# directory + a `<class>.ont.yml` schema. Order is display order.
CLASSES: tuple[str, ...] = ("concept", "relation", "artifact", "question", "hypothesis")

_CLASS_DESC: dict[str, str] = {
    "concept": "A domain concept, term, or method from the BOSC wiki glossary.",
    "relation": "A directed, document-traceable relationship between two entities.",
    "artifact": "A resolved entity, party, profiled person, or the site anchor.",
    "question": "An open lead or an [open]-tagged claim under investigation.",
    "hypothesis": "A network-wide reading of the data-center boom (a directory lens).",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_MAX_NAME_PART = 48  # keep filenames stable + readable; long keys are truncated then deduped


def _slug(text: str, *, fallback: str = "node") -> str:
    """Kebab-case a string into a stable, filesystem-safe node name part."""
    s = _SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    return s[:_MAX_NAME_PART].strip("-") or fallback


def _oneline(text: str, *, limit: int = 600) -> str:
    """Collapse whitespace and cap length — keep a node small and focused."""
    s = " ".join((text or "").split())
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


# --- node model ----------------------------------------------------------------------------
@dataclass
class MirrorLink:
    """One outgoing edge: ``target`` is a path relative to the *source node's class dir*."""

    target: str
    relationship: str = "link"


@dataclass
class MirrorNode:
    """One yidam corpus instance — serialized to ``.yidam/corpus/<node_class>/<name>.yml``."""

    node_class: str
    name: str  # the filename stem (kebab, unique within the class)
    label: str
    description: str = ""
    links: list[MirrorLink] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)  # extra BOSC provenance (kept, not lost)

    @property
    def id(self) -> str:
        """The yidam node id — ``<class>/<name>``."""
        return f"{self.node_class}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """The instance's YAML mapping — class/label/description first, meta, then links last."""
        out: dict[str, Any] = {"class": self.node_class, "label": self.label}
        if self.description:
            out["description"] = self.description
        for key, value in self.meta.items():
            if value is None or value == [] or value == {} or value == "":
                continue
            out[key] = value
        out["links"] = [
            {"target": link.target, "relationship": link.relationship} for link in self.links
        ]
        return out


@dataclass
class Mirror:
    """A projected, in-memory corpus mirror for one site — write it with :func:`write_mirror`."""

    site: str
    nodes: list[MirrorNode] = field(default_factory=list)

    @property
    def classes(self) -> list[str]:
        """The node classes actually present (only these get a ``.ont.yml``)."""
        return sorted({n.node_class for n in self.nodes})

    def counts_by_class(self) -> dict[str, int]:
        """``{class: node count}`` in :data:`CLASSES` order (present classes only)."""
        counts: dict[str, int] = {}
        for node in self.nodes:
            counts[node.node_class] = counts.get(node.node_class, 0) + 1
        return {c: counts[c] for c in CLASSES if c in counts}


class _Names:
    """Hands out unique, stable node names *within a class* (deduping slug collisions)."""

    def __init__(self) -> None:
        self._used: dict[str, set[str]] = {}

    def take(self, node_class: str, desired: str) -> str:
        used = self._used.setdefault(node_class, set())
        name = desired
        n = 2
        while name in used:
            name = f"{desired}-{n}"
            n += 1
        used.add(name)
        return name


# --- projection ----------------------------------------------------------------------------
def project_mirror(
    *,
    site: str,
    site_label: str,
    site_detail: str = "",
    entities: list[EntityNode],
    relationships: list[RelationshipEdge],
    concepts: list[ConceptItem],
    people: list[PersonItem],
    leads: list[LeadItem],
    hypotheses: dict[str, Hypothesis],
    open_claims: list[HypothesisAssessment],
) -> Mirror:
    """Project the loaded feeds into a connected yidam :class:`Mirror` (pure, no I/O).

    Every node is guaranteed ≥1 outgoing link to a node that exists in the mirror, so the
    result passes yidam ``graph-check``. The **site anchor** (``artifact/site-<slug>``) is
    the universal fallback hub; it links out to the three hypothesis nodes, which are always
    present, so the graph is connected end to end.
    """
    names = _Names()
    nodes: list[MirrorNode] = []

    # -- phase 1: assign every node its (class, name) up front, so links can resolve to real
    #    files regardless of projection order. The site anchor is registered FIRST, so any
    #    entity/person that slugs into "site-<slug>" is deduped around it (never collides).
    anchor_name = names.take("artifact", f"site-{_slug(site)}")

    hyp_name: dict[str, str] = {hid: names.take("hypothesis", _slug(hid)) for hid in hypotheses}
    concept_name: dict[str, str] = {c.slug: names.take("concept", _slug(c.slug)) for c in concepts}
    entity_name: dict[str, str] = {e.key: names.take("artifact", _slug(e.key)) for e in entities}
    person_name: dict[str, str] = {
        p.slug: names.take("artifact", f"person-{_slug(p.slug)}") for p in people
    }
    lead_name: dict[str, str] = {
        lead.id: names.take("question", f"lead-{_slug(lead.id)}") for lead in leads
    }
    # One [open]-claim question per open hypothesis cell (keyed by hypothesis id for the site).
    open_name: dict[str, str] = {
        cell.hypothesis: names.take("question", f"open-{_slug(cell.hypothesis)}")
        for cell in open_claims
    }

    def anchor_link(relationship: str, *, cross: bool) -> MirrorLink:
        """A guaranteed-valid link to the site anchor (``cross`` from a non-artifact class)."""
        prefix = "../artifact/" if cross else ""
        return MirrorLink(f"{prefix}{anchor_name}.yml", relationship)

    # -- phase 2: build nodes with links pointing at the names assigned above.

    # site anchor (artifact) — the hub. Links to every hypothesis lens.
    nodes.append(
        MirrorNode(
            "artifact",
            anchor_name,
            label=site_label,
            description=_oneline(site_detail) or f"The {site_label} watershed-point site.",
            meta={"kind": "site", "scope": "site", "site": site},
            links=[
                MirrorLink(f"../hypothesis/{hyp_name[hid]}.yml", "assessed-under")
                for hid in hypotheses
            ],
        )
    )

    # hypothesis lenses (network-shared). Link back to the site + out to any open thread.
    for hid, hyp in hypotheses.items():
        open_links = (
            [MirrorLink(f"../question/{open_name[hid]}.yml", "open-thread")]
            if hid in open_name
            else []
        )
        nodes.append(
            MirrorNode(
                "hypothesis",
                hyp_name[hid],
                label=f"{hyp.number} · {hyp.name}",
                description=_oneline(hyp.claim),
                meta={
                    "scope": "network",
                    "number": hyp.number,
                    "status": hyp.status,
                    "site": site,
                },
                links=[anchor_link("assessed-at", cross=True), *open_links],
            )
        )

    # concepts (network glossary). Link to emitted siblings, else fall back to the anchor.
    for concept in concepts:
        related = [
            MirrorLink(f"{concept_name[r]}.yml", "related")
            for r in concept.related
            if r in concept_name and concept_name[r] != concept_name[concept.slug]
        ]
        nodes.append(
            MirrorNode(
                "concept",
                concept_name[concept.slug],
                label=concept.title,
                description=_oneline(concept.summary),
                meta={
                    "scope": "network",
                    "kind": concept.kind,
                    "aliases": list(concept.aliases),
                    "tags": list(concept.tags),
                    "site": site,
                },
                links=related or [anchor_link("in-corpus", cross=True)],
            )
        )

    # entities (per-site). Every entity belongs to the site anchor.
    for ent in entities:
        detail = f"{ent.kind} · {ent.classification}"
        if ent.roles:
            detail += "; roles: " + ", ".join(sorted(ent.roles))
        nodes.append(
            MirrorNode(
                "artifact",
                entity_name[ent.key],
                label=ent.display,
                description=_oneline(detail),
                meta={
                    "scope": "site",
                    "entity_kind": ent.kind,
                    "classification": ent.classification,
                    "relation_class": ent.relation_class,
                    "relation_basis": ent.relation_basis,
                    "lei": ent.lei,
                    "uei": ent.uei,
                    "sources": list(ent.sources),
                    "site": site,
                },
                # Same class (artifact) → the anchor target needs no `../`.
                links=[MirrorLink(f"{anchor_name}.yml", "in-site")],
            )
        )

    # profiled people (per-site). Link to the resolved entity when it exists, else the anchor.
    for person in people:
        if person.entity_key and person.entity_key in entity_name:
            link = MirrorLink(f"{entity_name[person.entity_key]}.yml", "is-entity")
        else:
            link = MirrorLink(f"{anchor_name}.yml", "in-site")
        nodes.append(
            MirrorNode(
                "artifact",
                person_name[person.slug],
                label=person.name,
                description=_oneline(person.summary or ""),
                meta={
                    "scope": "site",
                    "kind": "person",
                    "entity_key": person.entity_key,
                    "roles": list(person.roles),
                    "affiliations": list(person.affiliations),
                    "tags": list(person.tags),
                    # Preserve each source's evidentiary kind ([verified]/[reference]/…).
                    "sources": [
                        {"source": s.source, "source_kind": s.source_kind} for s in person.sources
                    ],
                    "site": site,
                },
                links=[link],
            )
        )

    # relationships (per-site). Edge nodes fan out to their subject + object entities.
    for edge in relationships:
        edge_links: list[MirrorLink] = []
        if edge.src in entity_name:
            edge_links.append(MirrorLink(f"../artifact/{entity_name[edge.src]}.yml", "from"))
        if edge.dst in entity_name:
            edge_links.append(MirrorLink(f"../artifact/{entity_name[edge.dst]}.yml", "to"))
        if not edge_links:  # neither endpoint resolved → keep the node connected to the site
            edge_links.append(anchor_link("in-site", cross=True))
        detail_bits = [b for b in (edge.date, edge.ref, edge.source) if b]
        name = names.take("relation", f"{_slug(edge.src)}--{_slug(edge.rel)}--{_slug(edge.dst)}")
        nodes.append(
            MirrorNode(
                "relation",
                name,
                label=_oneline(f"{edge.src} {edge.rel} {edge.dst}"),
                description=_oneline(" · ".join(detail_bits)),
                meta={
                    "scope": "site",
                    "rel": edge.rel,
                    "src": edge.src,
                    "dst": edge.dst,
                    "date": edge.date,
                    "ref": edge.ref,
                    "source": edge.source,
                    "relation_class": edge.relation_class,
                    "relation_basis": edge.relation_basis,
                    "site": site,
                },
                links=edge_links,
            )
        )

    # leads (per-site open board) — questions. Preserve the lead's claim tag.
    for lead in leads:
        nodes.append(
            MirrorNode(
                "question",
                lead_name[lead.id],
                label=lead.title,
                description=_oneline(lead.detail),
                meta={
                    "scope": "site",
                    "lead_kind": lead.kind,
                    "status": lead.status,
                    "claim_tag": lead.tag,  # [open] | [inference] — preserved
                    "source": lead.source,
                    "issue": lead.issue,
                    "note": lead.note,
                    "site": site,
                },
                links=[anchor_link("on-site", cross=True)],
            )
        )

    # [open] claims — the open-tagged hypothesis cells. Link to the lens they hang under.
    for cell in open_claims:
        lens_hyp = hypotheses.get(cell.hypothesis)
        lens = f"{lens_hyp.number} {lens_hyp.name}" if lens_hyp else cell.hypothesis
        if cell.hypothesis in hyp_name:
            links = [MirrorLink(f"../hypothesis/{hyp_name[cell.hypothesis]}.yml", "open-under")]
        else:
            links = [anchor_link("on-site", cross=True)]
        nodes.append(
            MirrorNode(
                "question",
                open_name[cell.hypothesis],
                label=f"Open thread — {lens} @ {site}",
                description=_oneline(
                    f"No documented nexus yet for {site} under {lens}."
                    + (f" Fields: {cell.fields}." if cell.fields else "")
                ),
                meta={
                    "scope": "site",
                    "claim_tag": "open",  # [open] — preserved
                    "hypothesis": cell.hypothesis,
                    "signal": cell.signal,
                    "sub_thesis": cell.sub_thesis,
                    "group": cell.group,
                    "fields": dict(cell.fields),
                    "site": site,
                },
                links=links,
            )
        )

    return Mirror(site=site, nodes=nodes)


def build_mirror(settings: Settings | None = None) -> Mirror:
    """Load the committed corpus for the active site and project it into a :class:`Mirror`.

    Offline by construction: the entity graph is built with no live enrichments (all
    ``enrich_*`` default off), so the mirror is a pure read of the committed corpus.
    """
    settings = settings or get_settings()
    profile = active_profile(settings)

    corpus = load_corpus(settings)
    egraph = build_entity_graph(corpus, settings=settings)

    entities = graph_mod.export_entities(egraph)
    relationships = graph_mod.export_relationships(egraph)
    concepts = concepts_mod.load_concepts(settings.concepts_dir, site=settings.site)
    people = people_mod.export_people(
        load_people(site_scoped_path(settings.people_dir, settings.site, is_dir=True)),
        egraph=egraph,
    )
    leads = leads_mod.export_leads(
        site_scoped_path(settings.data_dir / "site" / "leads.yaml", settings.site, is_dir=False),
    )
    # The [open] claims: the open-tagged hypothesis cells committed for *this* site.
    open_claims = [
        cell
        for cell in load_assessments(settings=settings)
        if cell.site == settings.site and cell.tag == "open"
    ]

    mirror = project_mirror(
        site=settings.site,
        site_label=profile.place or settings.site.replace("-", " ").title(),
        site_detail=(
            f"{profile.place or settings.site} — {profile.basin} basin." if profile.basin else ""
        ),
        entities=entities,
        relationships=relationships,
        concepts=concepts,
        people=people,
        leads=leads,
        hypotheses=HYPOTHESES,
        open_claims=open_claims,
    )
    log.info(
        "corpus_mirror.built",
        site=settings.site,
        nodes=len(mirror.nodes),
        by_class=mirror.counts_by_class(),
    )
    return mirror


# --- writing -------------------------------------------------------------------------------
def default_corpus_dir(settings: Settings | None = None) -> Path:
    """The mirror's default location — ``<repo-root>/.yidam/corpus`` (what the yidam CLI reads)."""
    settings = settings or get_settings()
    return settings.data_dir.parent / ".yidam" / "corpus"


def _ont_yaml(node_class: str) -> str:
    """The ``<class>.ont.yml`` class schema (yidam reads the class name from the filename)."""
    return yaml.safe_dump(
        {"class": node_class, "description": _CLASS_DESC.get(node_class, node_class)},
        sort_keys=False,
        allow_unicode=True,
    )


_README = """# corpus

The **BOSC corpus mirror** — the committed corpus (entities, relationships, wiki concepts,
people, leads, hypotheses, and `[open]` claims) projected into yidam node format by
`watermark corpus-mirror`. Regenerated, git-ignored, never a source of truth.

Each file is one node; every node has at least one outgoing link.

## Node index

<!-- REGEN: yidam corpus-index -->
_Run `yidam corpus-index` (or `watermark corpus-mirror`) to populate._
<!-- /REGEN -->
"""


def _clear_corpus(corpus_dir: Path) -> None:
    """Remove only the yidam-owned artifacts under ``corpus_dir`` (safe if it's a shared dir)."""
    import shutil

    for node_class in CLASSES:
        class_dir = corpus_dir / node_class
        if class_dir.is_dir():
            shutil.rmtree(class_dir)
        ont = corpus_dir / f"{node_class}.ont.yml"
        if ont.exists():
            ont.unlink()
    readme = corpus_dir / "README.md"
    if readme.exists():
        readme.unlink()


def write_mirror(mirror: Mirror, corpus_dir: Path) -> None:
    """Write ``mirror`` to ``corpus_dir`` as yidam node files (clearing a prior mirror first)."""
    corpus_dir.mkdir(parents=True, exist_ok=True)
    _clear_corpus(corpus_dir)

    for node_class in mirror.classes:  # only classes that actually have instances
        (corpus_dir / f"{node_class}.ont.yml").write_text(_ont_yaml(node_class), encoding="utf-8")
        (corpus_dir / node_class).mkdir(exist_ok=True)

    for node in mirror.nodes:
        path = corpus_dir / node.node_class / f"{node.name}.yml"
        path.write_text(
            yaml.safe_dump(node.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8"
        )

    (corpus_dir / "README.md").write_text(_README, encoding="utf-8")
    log.info("corpus_mirror.written", dir=str(corpus_dir), nodes=len(mirror.nodes))


# --- validation (the yidam graph-check rules, in Python) -----------------------------------
@dataclass
class MirrorIssue:
    """One node with graph-check problems — the Python peer of yidam's ``graph-check`` output."""

    node: str  # path relative to the corpus dir
    problems: list[str]


def validate_mirror(corpus_dir: Path) -> list[MirrorIssue]:
    """Replicate yidam ``graph-check`` over a written mirror (empty list ⇒ the graph is clean).

    Faithful to `yidam/cli/src/cmd/corpus.rs::render_graph_check`: an instance must carry a
    ``class:`` that matches a ``<class>.ont.yml`` (when any schema exists), a ``label:``, and
    ≥1 outgoing link whose ``target:`` resolves to a file that exists. Instance files are the
    ``.yml`` files at depth ≥2 that don't end in ``.ont.yml``.
    """
    defined = {p.name[: -len(".ont.yml")] for p in corpus_dir.glob("*.ont.yml")}
    issues: list[MirrorIssue] = []
    for inst in sorted(corpus_dir.rglob("*.yml")):
        rel = inst.relative_to(corpus_dir)
        if len(rel.parts) < 2 or inst.name.endswith(".ont.yml"):
            continue
        data = yaml.safe_load(inst.read_text(encoding="utf-8")) or {}
        problems: list[str] = []

        node_class = data.get("class")
        if node_class is None:
            problems.append("missing 'class:' field")
        elif defined and node_class not in defined:
            problems.append(f"unknown class '{node_class}': no matching {node_class}.ont.yml")
        if data.get("label") is None:
            problems.append("missing 'label:' field")

        links = data.get("links") or []
        if not links:
            problems.append("orphan node: no outgoing links")
        else:
            for link in links:
                target = (link or {}).get("target") if isinstance(link, dict) else None
                if target is None:
                    problems.append("link entry missing 'target:' field")
                elif not (inst.parent / target).exists():
                    problems.append(f"broken link: {target}")

        if problems:
            issues.append(MirrorIssue(node=str(rel), problems=problems))
    return issues


def render_corpus_index(corpus_dir: Path) -> str:
    """Render the ``yidam corpus-index`` markdown table over a written mirror.

    Faithful to `render_corpus_index` in yidam: one row per instance, sorted by path, with
    class, label, outgoing-link count, and line count.
    """
    rows: list[str] = ["| Instance | Class | Label | Links out | Lines |", "|---|---|---|---|---|"]
    found = False
    for inst in sorted(corpus_dir.rglob("*.yml")):
        rel = inst.relative_to(corpus_dir)
        if len(rel.parts) < 2 or inst.name.endswith(".ont.yml"):
            continue
        found = True
        text = inst.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        node_class = data.get("class", "—")
        label = data.get("label", "—")
        links = len(data.get("links") or [])
        lines = len(text.splitlines())
        rows.append(f"| [{inst.name}]({rel}) | {node_class} | {label} | {links} | {lines} |")
    if not found:
        return "_No corpus instances yet._"
    return "\n".join(rows)
