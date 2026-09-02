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
``hypothesis`` the network's boom-origin readings (:data:`watermark.hypotheses.HYPOTHESES`)
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
from watermark.site import corpus_catalog, corpus_records, yidam_cli
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
from watermark.site.yidam_cli import Report
from watermark.sites import active_profile, site_scoped_path

log = get_logger(__name__)

# The five yidam node kinds this mirror emits (the issue's taxonomy). Each becomes a class
# directory + a `<class>.ont.yml` schema. Order is display order.
CLASSES: tuple[str, ...] = (
    "concept",
    "relation",
    "artifact",
    "question",
    "hypothesis",
    "record",
)

# --- the class contract ----------------------------------------------------------------------
# What each class declares about its own instances: the properties they carry and the
# relationships they may author. Declared as DATA here and rendered to `<class>.ont.yml` by
# `_ont_yaml`, so `watermark.agent`'s `licensed_edges` can read the same object the binary
# reads a rendering of. A second reader that parsed the emitted YAML back would be a second
# ontology, and the two would drift the way the report replica did (#2051).
#
# Until #2132 this said `class:` and `description:` and nothing else, and the cost was
# invisible: upstream's eight error-severity ontology checks all reported zero because a check
# that grades instances against their class declaration has nothing to grade. That is a green
# meaning "no rule", not one meaning "no violation".


@dataclass(frozen=True)
class OntologyProperty:
    """One property a class declares its instances may carry.

    ``type`` is upstream's vocabulary and only some of it is *tested*: `claim`, `date` and
    `string`/`text`/`ref` are checked by `property-type`, and anything else is left alone
    (`checks.rs`, `property_type_violation`). So `list`, `mapping` and `integer` below are
    declarative — they say what the field is without asking for a test yidam cannot run.

    **Getting a type wrong is worse than leaving it broad.** Declaring `sources` a `string`
    would fault all 63 artifacts that carry it, because it is a list.
    """

    name: str
    type: str
    description: str


@dataclass(frozen=True)
class OntologyEdge:
    """One relationship a class licenses, and the class it lands on.

    ``direction`` is always ``out`` here: the mirror authors every edge from the node that owns
    it, so a class's declaration describes what its own instances write. Upstream documents an
    edge from both ends, and `licensed_edges` reconstructs the inbound view rather than the
    projection carrying it twice.
    """

    relationship: str
    target: str
    description: str
    direction: str = "out"
    #: Declared for a path the projection **can** take and has not taken yet — a fallback link
    #: no instance authors against the current corpus. It must still be licensed, because
    #: `edge_policy: exhaustive` makes the first traversal of an undeclared relationship an
    #: ERROR, and it must be marked, because "declared and unauthored" is otherwise
    #: indistinguishable from an ontology that has reached past its corpus. Not rendered into
    #: `<class>.ont.yml`: it is a fact about this projection, not part of yidam's schema.
    fallback: bool = False


@dataclass(frozen=True)
class ClassOntology:
    """One ``<class>.ont.yml`` — the contract for a node class.

    ``edge_policy`` is ``exhaustive`` for every class, and that is a claim worth defending: the
    mirror is **generated**, so its relationship vocabulary is closed by construction. A
    relationship outside `edges` is not a coinage somebody made deliberately — it is a bug in
    this module, most likely in :func:`resolve_link_target`. `exhaustive` is what turns that
    into an error instead of a shrug. A hand-authored corpus would say `characteristic`.
    """

    name: str
    label: str
    description: str
    properties: tuple[OntologyProperty, ...] = ()
    edges: tuple[OntologyEdge, ...] = ()
    edge_policy: str = "exhaustive"


#: Properties every instance of the class carries, plus a few it *should*.
#:
#: `undeclared-property` is all-or-nothing per class: declare any `properties:` and every
#: instance property must be declared here or covered by `UNIVERSAL_PROPERTIES`. But
#: `missing-property` reports every declared property an instance omits, and the schema has no
#: `required` field — so declaring an optional one asserts a contract the ontology cannot
#: express. Declaring all 40 of this corpus's properties on their classes emits **593** such
#: warnings for fields that are legitimately optional.
#:
#: So a class declares its INVARIANTS, and `UNIVERSAL_PROPERTIES` takes the rest. The four
#: exceptions are marked in their own `description` — they are near-universal, they each cost
#: one standing warning today, and the reason to accept that is written where it will be read.
ONTOLOGY: dict[str, ClassOntology] = {
    "concept": ClassOntology(
        name="concept",
        label="Concept",
        description="A domain concept, term, or method from the BOSC wiki glossary.",
        properties=(
            OntologyProperty(
                "scope", "string", "Whether the concept is site-local or network-wide."
            ),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty(
                "kind", "string", "The glossary entry's kind — `term`, `method`, `actor`, …"
            ),
            OntologyProperty("aliases", "list", "Other names the corpus uses for this concept."),
            OntologyProperty(
                "tags", "list", "Glossary facets, used by the wiki's cross-link audit."
            ),
        ),
        edges=(
            OntologyEdge(
                "related",
                "concept",
                "A cross-reference authored in the glossary as a `[[wiki link]]`.",
            ),
            # Unexercised by the current corpus and NOT dead: `project_mirror` falls back to
            # this when a concept resolves no `related` sibling, so an isolated glossary term
            # stays reachable from the site anchor. Under an `exhaustive` policy the first such
            # term would be an ERROR-severity `unlicensed-edge` — the failure is in the
            # declaration, not the projection, so the licence is written before it can fire.
            OntologyEdge(
                "in-corpus",
                "artifact",
                "The site anchor, when a concept cross-references no other concept.",
                fallback=True,
            ),
        ),
    ),
    "relation": ClassOntology(
        name="relation",
        label="Relation",
        description="A directed, document-traceable relationship between two entities.",
        properties=(
            OntologyProperty(
                "scope", "string", "Whether the relationship is site-local or network-wide."
            ),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty(
                "rel", "string", "The relationship verb as the source document states it."
            ),
            OntologyProperty(
                "src", "string", "The source entity's key, as resolved by the entity graph."
            ),
            OntologyProperty(
                "dst", "string", "The target entity's key, as resolved by the entity graph."
            ),
            OntologyProperty(
                "source", "ref", "The committed extraction this relationship was read from."
            ),
        ),
        edges=(
            OntologyEdge("from", "artifact", "The entity this relationship is authored from."),
            OntologyEdge("to", "artifact", "The entity this relationship lands on."),
            # The same fallback on the other side: an edge node whose endpoints BOTH failed to
            # resolve against the entity graph keeps its tie to the site rather than floating
            # free. Unreachable today because every relationship resolves — which is exactly
            # what makes it an undeclared ERROR waiting on the first entity-key miss.
            OntologyEdge(
                "in-site",
                "artifact",
                "The site anchor, when neither endpoint resolves to an entity.",
                fallback=True,
            ),
        ),
    ),
    "artifact": ClassOntology(
        name="artifact",
        label="Artifact",
        description="A resolved entity, party, profiled person, or the site anchor.",
        properties=(
            OntologyProperty(
                "scope", "string", "Whether the artifact is site-local or network-wide."
            ),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty(
                "sources",
                "list",
                "The committed extractions this entity was resolved from. Declared here although "
                "one instance lacks it — `artifact/site-lima` is the synthetic site anchor and has "
                "no source document — because an entity arriving with no citation is a real gap "
                "and this is the only thing that would report it. The anchor's standing "
                "`missing-property` warning is the price, and it is deliberate.",
            ),
        ),
        edges=(
            OntologyEdge("in-site", "artifact", "The site anchor this entity was found under."),
            OntologyEdge("is-entity", "artifact", "The resolved entity a profiled person is."),
            OntologyEdge(
                "assessed-under", "hypothesis", "A network hypothesis this entity is evidence for."
            ),
        ),
    ),
    "record": ClassOntology(
        name="record",
        label="Record",
        description="One committed extraction — a reviewed artifact of the public record.",
        properties=(
            OntologyProperty(
                "scope", "string", "Always site-local: a record belongs to the site that holds it."
            ),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty(
                "relpath",
                "string",
                "The extraction's path under `data/extracted/`. This is the record's identity — "
                "the catalog registers it by exactly this path, so a citation resolves through "
                "it and a typo here is an uncited record rather than a wrong one.",
            ),
            OntologyProperty(
                "collection",
                "string",
                "The first path segment — `oepa`, `legal`, `permits`. The extracted tree mirrors "
                "`data/documents/` by collection, so this is the source shelf.",
            ),
        ),
        edges=(
            OntologyEdge(
                "in-site",
                "artifact",
                "The site anchor this record was filed under. Every record carries it, so a "
                "record is connected whether or not the catalog registers its file.",
            ),
        ),
    ),
    "question": ClassOntology(
        name="question",
        label="Question",
        description="An open lead or an [open]-tagged claim under investigation.",
        properties=(
            OntologyProperty(
                "scope", "string", "Whether the question is site-local or network-wide."
            ),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty(
                "claim_tag",
                "claim",
                "The evidence standing this question is asserted at. `type: claim` is what makes "
                "the third arm of the frozen `open_questions` predicate literal here rather than "
                "incidental — see `_claim_token`, and goedelsoup/yidam#127, which was filed from "
                "this corpus and settled by widening that predicate.",
            ),
            OntologyProperty(
                "lead_kind",
                "string",
                "The lead's kind — `signal`, `question`, `redaction`, `claim`. Declared although "
                "`question/open-water` lacks it: that node is a hypothesis thread rather than a "
                "lead. One standing warning, accepted so a lead arriving unkinded is reported.",
            ),
            OntologyProperty(
                "status",
                "string",
                "The lead's review status. Same exception as `lead_kind`, same reason.",
            ),
            OntologyProperty(
                "source",
                "ref",
                "The committed lead or extraction this question was read from. Same exception as "
                "`lead_kind`, same reason.",
            ),
        ),
        edges=(
            OntologyEdge("on-site", "artifact", "The site anchor this question is open against."),
            OntologyEdge(
                "open-under", "hypothesis", "The hypothesis this question is a thread of."
            ),
        ),
    ),
    "hypothesis": ClassOntology(
        name="hypothesis",
        label="Hypothesis",
        description="A network-wide reading of the data-center boom (a directory hypothesis).",
        properties=(
            OntologyProperty("scope", "string", "Hypotheses are network-wide by construction."),
            OntologyProperty(
                "site", "string", "The watershed-point slug this projection was built for."
            ),
            OntologyProperty("number", "string", "The hypothesis's stable id — `H1`, `H2`, `H3`."),
            OntologyProperty("status", "string", "Where the hypothesis stands against the record."),
        ),
        edges=(
            OntologyEdge(
                "assessed-at", "artifact", "A site anchor this hypothesis is assessed at."
            ),
            OntologyEdge("open-thread", "question", "An open question pursuing this hypothesis."),
        ),
    ),
}


#: Properties any class may carry, whatever its own ontology declares.
#:
#: Rendered to `.yidam/corpus/universal.yml`, which is the corpus speaking about itself rather
#: than about one of its classes. Everything here is genuinely optional — present on some
#: instances of a class and legitimately absent from others — so declaring it per class would
#: assert a contract the corpus does not hold and emit a `missing-property` warning for every
#: instance that correctly does without it.
#:
#: This is **not** a way to stop declaring things. Upstream is explicit that a blanket opt-out
#: would throw away the gate that catches the next real typo; each entry below names a property
#: this projection actually writes, and a name that is not here is a finding.
UNIVERSAL_PROPERTIES: tuple[OntologyProperty, ...] = (
    # --- the record's claim profile (#2134) ----------------------------------------------
    # Optional because most records assert nothing: 39 of Lima's 250 carry a claim marker at
    # all. Declaring these on `record` would emit a `missing-property` warning for the other
    # 211, which would say "this extraction has no evidence tags" — true, unremarkable, and
    # not a gap anybody should be asked to close.
    OntologyProperty(
        "claim_standings",
        "claim",
        "The distinct evidence standings this record carries, bracketed so yidam counts them. "
        "One token per standing, NOT per assertion — the question `verified-unsourced` asks is "
        "whether this record rests on a registered source, which is a fact about the record.",
    ),
    OntologyProperty(
        "claim_counts",
        "mapping",
        "The true per-tag totals, including `[reference]`, which yidam has no counter for. "
        "Carried so the summary above loses nothing a reader might want back.",
    ),
    # --- the assessed cell (#2134) ------------------------------------------------------
    # A hypothesis node carries the active site's committed reading when there is one, and a
    # site may legitimately have none for a given hypothesis — Lima's H1 cell is `open`, so it
    # lands on a `question` node and leaves the hypothesis node without a cell at all. They are
    # therefore genuinely optional, which is what `universal.yml` is for: declaring them on the
    # class would assert a contract the projection does not keep and emit a `missing-property`
    # warning for every (site, hypothesis) pair with nothing committed.
    OntologyProperty(
        "cell_tag",
        "claim",
        "The evidentiary standing this site's reading of the hypothesis is asserted at, "
        "written bracketed so the text scan counts it. This is the property that gives "
        "`verified-unsourced` something to check: a `[verified]` cell whose citations reach "
        "no catalog entry is a standing the corpus cannot demonstrate.",
    ),
    OntologyProperty("cell_signal", "string", "How loud the nexus is — orthogonal to the tag."),
    OntologyProperty("cell_group", "string", "The hypothesis's own taxonomy group for the cell."),
    OntologyProperty("cell_sub_thesis", "string", "Which kind of claim the cell makes."),
    OntologyProperty("cell_fields", "mapping", "The per-hypothesis fields the cell records."),
    OntologyProperty(
        "cell_sources",
        "list",
        "Every source the cell cites, verbatim — INCLUDING the ones no catalog entry "
        "registers. The `rests-on` links carry only the registered ones, so the difference "
        "between these two is exactly what `verified-unsourced` reports on.",
    ),
    OntologyProperty("kind", "string", "A class-specific kind discriminator."),
    OntologyProperty("tags", "list", "Facets, carried by concepts and by some entities."),
    OntologyProperty(
        "entity_kind",
        "string",
        "The resolved entity's kind — absent on people and on the site anchor.",
    ),
    OntologyProperty(
        "classification", "string", "The entity's registry classification, where one was resolved."
    ),
    OntologyProperty("entity_key", "string", "The entity-graph key a profiled person resolves to."),
    OntologyProperty("roles", "list", "A profiled person's roles, where the record states them."),
    OntologyProperty(
        "affiliations", "list", "A profiled person's affiliations, where the record states them."
    ),
    OntologyProperty("issue", "integer", "The GitHub issue tracking this lead."),
    OntologyProperty("note", "string", "A short editorial note carried from the lead."),
    OntologyProperty("hypothesis", "string", "The hypothesis slug a question threads under."),
    OntologyProperty("sub_thesis", "string", "The sub-thesis a question threads under."),
    OntologyProperty("signal", "string", "The lead's signal state, where the lead declares one."),
    OntologyProperty("group", "string", "The lead's grouping key, where the lead declares one."),
    OntologyProperty(
        "fields", "mapping", "A question's structured answer fields, where it carries any."
    ),
    OntologyProperty("ref", "string", "A permit or instrument reference the relationship names."),
    OntologyProperty("date", "date", "The date the source document states for this relationship."),
    # Latent, and declared for exactly that reason. `to_dict` drops an empty value, so none of
    # these four reaches a node file on the current corpus — but the projection writes them
    # whenever the entity graph resolves one, and an undeclared property is an ERROR. Declaring
    # them now costs nothing and stops the first LEI this corpus resolves from failing the gate.
    OntologyProperty("lei", "string", "The entity's Legal Entity Identifier, where GLEIF has one."),
    OntologyProperty(
        "uei", "string", "The entity's federal Unique Entity Identifier, where one is known."
    ),
    OntologyProperty(
        "relation_class", "string", "How the entity graph classified this relationship."
    ),
    OntologyProperty(
        "relation_basis", "string", "The evidence the relationship classification rests on."
    ),
)

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
    # Hints at the committed corpus file(s) this node derives from, used by the `corpus-index` feed
    # (#1573) to date each node's freshness. Deliberately **not** serialized by :meth:`to_dict` — it
    # never enters the yidam node YAML, so the mirror stays byte-identical (and its line counts too).
    # A `concept:<slug>` sentinel (resolved against ``concepts_dir``) or a raw corpus source path/
    # citation (resolved best-effort); non-path citations resolve to nothing → null freshness.
    source_refs: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        """The yidam node id — ``<class>/<name>``."""
        return f"{self.node_class}/{self.name}"

    def to_dict(self) -> dict[str, Any]:
        """The instance's YAML mapping — class/label/description, then ``properties``, then links.

        **The provenance nests under ``properties:``, and that is not cosmetic.** yidam reads an
        instance's properties from that mapping (`Node::inst.properties`) and from nowhere else,
        so the bare top-level keys this projection wrote until #2132 were invisible to the whole
        ontology layer: `undeclared-property` saw an instance with no properties at all, and
        `missing-property` reported every declared one as absent — 1,129 findings over a corpus
        that was carrying all of them. A class contract cannot grade what the instances are not
        saying in the shape it reads.

        ``claim_tag`` stays **bracketed** here. A property the class declares `type: claim`
        accepts the bare token, so `open` would satisfy the ontology arm — but BOSC's own
        `open_question_nodes` scans the serialized text for the bracketed form, and the prose
        arm of the frozen predicate reads only that. The bracket satisfies every arm of both
        surfaces; the bare word satisfies one. See :func:`_claim_token`.
        """
        out: dict[str, Any] = {"class": self.node_class, "label": self.label}
        if self.description:
            out["description"] = self.description
        properties = {
            key: value
            for key, value in self.meta.items()
            if value is not None and value != [] and value != {} and value != ""
        }
        if properties:
            out["properties"] = properties
        out["links"] = [
            {"target": link.target, "relationship": link.relationship} for link in self.links
        ]
        return out


def _citation_links(
    cell: HypothesisAssessment, catalog: list[corpus_catalog.CatalogSource]
) -> list[MirrorLink]:
    """The cell's citations, as links to the catalog entries that register them.

    **A citation is a link that resolves to the catalog file** — `checks.rs::linked_paths`
    reads `links:` targets and prose links and nothing else, so naming a source in a property
    is not citing it. That is the whole mechanism by which `verified-unsourced` can tell a
    grounded claim from an ungrounded one, and it is why this returns links rather than text.

    A citation the catalog does not register produces **no link**, deliberately. Lima's
    defense cell rests on `data/reference/economics/baseline.yaml`, which is registered, and
    resolves; four cells across the network rest only on `docs/defense-nexus.md`, which is
    internally-authored prose no catalog entry covers — and `source_is_verified` already says
    a `reference` kind is "authoritative but not a record about the subject". Manufacturing a
    link for those would be the flattering error the check exists to catch.
    """
    seen: set[str] = set()
    links: list[MirrorLink] = []
    for citation in cell.citations:
        if not citation.source:
            continue
        slug = corpus_catalog.entry_for_path(catalog, citation.source)
        if slug is None or slug in seen:
            continue
        seen.add(slug)
        links.append(MirrorLink(corpus_catalog.catalog_link_target(slug), corpus_catalog.CITES))
    return links


def _claim_token(tag: str | None) -> str | None:
    """The canonical bracketed claim token for a bare evidence tag — ``open`` → ``[open]``.

    The mirror stores the token, never the bare word. Two reasons, and the second is
    load-bearing:

    * ``[verified]`` / ``[inference]`` / ``[reference]`` / ``[open]`` **is** the claim
      vocabulary the rest of the corpus is written in, so the bare word was the lossy form.
    * ``yidam open-questions`` decides a node is open by scanning its raw serialized text for
      the literal ``[open]`` (``yidam/cli/src/cmd/mod.rs::has_open_claim``). With the bare
      word the real binary saw 2 open questions in this mirror against the 20 the replica
      reported over the same tree — it matched only the handful of nodes carrying ``[open]``
      somewhere in their prose.

    Readers normalize with ``.strip("[]")`` (:func:`watermark.site.corpus_nodes._evidence`),
    so the bracketing changes no downstream feed value. Idempotent.

    **The inconsistency this used to work around is settled, and the bracketing stays anyway.**
    The two surfaces once disagreed: upstream added a structural route — a class may declare, in
    its ``.ont.yml``, which properties carry an evidence tag (``yidam/cli/src/claims.rs``,
    `goedelsoup/yidam` `6aaf18e`) — so ``yidam open-questions`` would find a bare ``open``,
    while the frozen MCP ``open_questions`` predicate was two arms and forbade that extension by
    name. Filed from here as goedelsoup/yidam#127; upstream resolved it by **widening the
    contract rather than narrowing the CLI**, and at contract 0.12.0 the predicate is three arms
    reading both spellings. Its note names this corpus by measurement: *"the corpus that
    measured 26 open questions against this tool's 2, and reshaped its data to `[open]` to be
    seen at all."*

    So the bracketed token is no longer the *only* form that satisfies both surfaces — but it
    still satisfies every arm of both, and reverting is a data-shape change with nothing to buy
    it. The third arm reads a property a class **declares**, and ``_ont_yaml`` declares none, so
    a bare word here would be invisible to the declaration-reading arm and to the text scan
    alike. The bare form becomes available when the ontology declares the property (#2132) — and
    that is where the decision belongs, with the declaration in front of it.
    """
    raw = (tag or "").strip()
    if not raw:
        return None
    return raw if raw.startswith("[") else f"[{raw.strip('[]')}]"


def resolve_link_target(source_class: str, target: str) -> str:
    """Resolve a link ``target`` to the node id (``<class>/<name>``) it points at.

    A link serializes **relative to its own node's class dir** — :meth:`MirrorLink` writes
    ``other.yml`` for a same-class edge and ``../<class>/<name>.yml`` for a cross-class one — so
    inverting it needs the source class. That is why this lives here, beside the writer whose
    convention it inverts, rather than beside either of its callers.

    A full path-component walk, not a prefix strip: ``./`` is skipped, each ``..`` pops one
    component, and a target that escapes the corpus root is returned **verbatim** — faithful to
    yidam's ``model::resolve_link_target``, which every consumer of this graph agrees with.
    """
    parts: list[str] = [source_class]
    for comp in target.split("/"):
        if comp in (".", ""):
            continue
        if comp == "..":
            if not parts:  # escaped the corpus root — yidam returns the target verbatim
                return target
            parts.pop()
        else:
            parts.append(comp)
    joined = "/".join(parts)
    return joined[: -len(".yml")] if joined.endswith(".yml") else joined


def _meta_bits(node: MirrorNode) -> list[str]:
    """Salient, human-meaningful ``meta`` values for a node, flattened to search text.

    Structural provenance (``site``/``scope``) and machine ids (``lei``/``uei``/``issue``) add
    noise, not meaning, to a semantic vector, so they are skipped; the fields that carry what a
    node *is about* (its kind, roles, relationship, tags, aliases, the hypothesis it hangs
    under) are kept.
    """
    keep = (
        "kind",
        "entity_kind",
        "classification",
        "rel",
        "src",
        "dst",
        "lead_kind",
        "hypothesis",
        "sub_thesis",
        "signal",
        "roles",
        "affiliations",
        "tags",
        "aliases",
        "relation_class",
    )
    bits: list[str] = []
    for key in keep:
        value = node.meta.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            scalars = [str(x) for x in value if x]
            if scalars:
                bits.append(" ".join(scalars))
        else:
            bits.append(str(value))
    return bits


def node_text(node: MirrorNode) -> str:
    """The text unit for a mirror node — label, description, class, and salient meta.

    Deterministic and self-contained (no I/O), so the same node always yields the same text.
    The one canonical node-text derivation, shared by the semantic vector index
    (:func:`watermark.site.yidam_index.YidamVectorIndex.build`) and the lexical ``corpus-nodes``
    retrieval feed (:mod:`watermark.site.corpus_nodes`) so both surfaces tokenize the same content.
    """
    parts = [node.label, node.description, node.node_class, *_meta_bits(node)]
    return " · ".join(p for p in (s.strip() for s in parts if s) if p)


@dataclass
class Mirror:
    """A projected, in-memory corpus mirror for one site — write it with :func:`write_mirror`.

    Carries its **catalog** as well as its nodes, because the two are one artifact: a node
    cites a source by linking to `.yidam/catalog/<slug>.md`, so a corpus written without its
    registry has dangling citations and breaks the projection's own edge invariant. Coupling
    them here means anywhere a mirror can be written, it can be written whole.
    """

    site: str
    nodes: list[MirrorNode] = field(default_factory=list)
    catalog: list[corpus_catalog.CatalogSource] = field(default_factory=list)

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
    assessed_claims: list[HypothesisAssessment] = (),  # type: ignore[assignment]
    catalog: list[corpus_catalog.CatalogSource] = (),  # type: ignore[assignment]
    records: list[corpus_records.CorpusRecord] = (),  # type: ignore[assignment]
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
    record_name: dict[str, str] = {
        r.relpath: names.take("record", _slug(r.relpath.rsplit(".", 1)[0])) for r in records
    }

    def anchor_link(relationship: str, *, cross: bool) -> MirrorLink:
        """A guaranteed-valid link to the site anchor (``cross`` from a non-artifact class)."""
        prefix = "../artifact/" if cross else ""
        return MirrorLink(f"{prefix}{anchor_name}.yml", relationship)

    # -- phase 2: build nodes with links pointing at the names assigned above.

    # site anchor (artifact) — the hub. Links to every hypothesis.
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

    # hypotheses (network-shared). Link back to the site, out to any open thread, and — where
    # this site has committed a reading — out to the catalog entries that reading rests on.
    assessed_by_hyp = {cell.hypothesis: cell for cell in assessed_claims}
    for hid, hyp in hypotheses.items():
        open_links = (
            [MirrorLink(f"../question/{open_name[hid]}.yml", "open-thread")]
            if hid in open_name
            else []
        )
        meta: dict[str, Any] = {
            "scope": "network",
            "number": hyp.number,
            "status": hyp.status,
            "site": site,
        }
        cite_links: list[MirrorLink] = []
        if (cell := assessed_by_hyp.get(hid)) is not None:
            # **The claim this corpus makes about this site, at the standing it asserts.**
            # The projection carried only `open` cells until #2134, so the mirror held no
            # `[verified]` claim at all and `verified-unsourced` returned early at zero — a
            # green meaning "nothing asserted", not "nothing unsupported".
            meta["cell_tag"] = _claim_token(cell.tag)
            meta["cell_signal"] = cell.signal
            meta["cell_group"] = cell.group
            meta["cell_sub_thesis"] = cell.sub_thesis
            if cell.fields:
                meta["cell_fields"] = dict(cell.fields)
            cite_links = _citation_links(cell, catalog)
            meta["cell_sources"] = [c.source for c in cell.citations if c.source]
        nodes.append(
            MirrorNode(
                "hypothesis",
                hyp_name[hid],
                label=f"{hyp.number} · {hyp.name}",
                description=_oneline(hyp.claim),
                meta=meta,
                links=[anchor_link("assessed-at", cross=True), *open_links, *cite_links],
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
                source_refs=[f"concept:{concept.slug}"],  # → `concepts_dir/<slug>.md`
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
                source_refs=list(ent.sources),  # committed corpus source paths → freshness
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
                source_refs=[s.source for s in person.sources if s.source],
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
                source_refs=[edge.source] if edge.source else [],
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
                    "claim_tag": _claim_token(
                        lead.tag
                    ),  # [open] | [inference] — the token, not the bare word
                    "source": lead.source,
                    "issue": lead.issue,
                    "note": lead.note,
                    "site": site,
                },
                source_refs=[lead.source] if lead.source else [],
                links=[anchor_link("on-site", cross=True)],
            )
        )

    # [open] claims — the open-tagged hypothesis cells. Link to the hypothesis they hang under.
    for cell in open_claims:
        cell_hyp = hypotheses.get(cell.hypothesis)
        label = f"{cell_hyp.number} {cell_hyp.name}" if cell_hyp else cell.hypothesis
        if cell.hypothesis in hyp_name:
            links = [MirrorLink(f"../hypothesis/{hyp_name[cell.hypothesis]}.yml", "open-under")]
        else:
            links = [anchor_link("on-site", cross=True)]
        nodes.append(
            MirrorNode(
                "question",
                open_name[cell.hypothesis],
                label=f"Open thread — {label} @ {site}",
                description=_oneline(
                    f"No documented nexus yet for {site} under {label}."
                    + (f" Fields: {cell.fields}." if cell.fields else "")
                ),
                meta={
                    "scope": "site",
                    "claim_tag": "[open]",  # the token yidam open-questions scans for
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

    # records (per-site) — the committed extractions themselves, each tied to the site anchor
    # and, where the catalog registers its file, to the source it rests on. The `rests-on`
    # link is what makes `verified-unsourced` answerable: a record asserting `[verified]` with
    # no such link is a standing the corpus cannot demonstrate.
    for record in records:
        record_meta: dict[str, Any] = {
            "scope": "site",
            "relpath": record.relpath,
            "collection": record.collection,
            "site": site,
        }
        if record.standings:
            record_meta["claim_standings"] = record.standings
        if record.counts:
            record_meta["claim_counts"] = dict(record.counts)
        links = [MirrorLink(f"../artifact/{anchor_name}.yml", "in-site")]
        if (slug := corpus_catalog.entry_for_path(catalog, record.data_relpath)) is not None:
            links.append(MirrorLink(corpus_catalog.catalog_link_target(slug), corpus_catalog.CITES))
        nodes.append(
            MirrorNode(
                "record",
                record_name[record.relpath],
                label=record.title,
                description=_oneline(f"{record.collection or 'corpus'} · {record.relpath}"),
                source_refs=[record.relpath],
                meta=record_meta,
                links=links,
            )
        )

    return Mirror(site=site, nodes=nodes, catalog=list(catalog))


@dataclass
class MirrorFeeds:
    """The committed corpus for one site, loaded into the feeds the mirror projects from.

    The shared read behind :func:`build_mirror` and the wiki-link audit
    (:mod:`watermark.site.wiki_lint`, #1571) — both need the same site-scoped entities,
    concepts, and people, and loading the entity graph is the expensive half, so it happens
    once here. Offline by construction (no live enrichments).
    """

    site: str
    site_label: str
    site_detail: str
    entities: list[EntityNode]
    relationships: list[RelationshipEdge]
    concepts: list[ConceptItem]
    people: list[PersonItem]
    leads: list[LeadItem]
    open_claims: list[HypothesisAssessment]
    #: The site's NON-open cells — the readings this corpus asserts rather than the ones it is
    #: still asking. Split from `open_claims` because they land on different nodes and mean
    #: opposite things: an open cell is a question, an assessed one is a claim.
    #: Defaulted, like the two below, because a mirror without them is thin rather than
    #: invalid — a peer with no committed reading, no catalog and no extraction still projects
    #: its always-present spine, and the wiki-lint callers build feeds for exactly that shape.
    assessed_claims: list[HypothesisAssessment] = field(default_factory=list)
    #: The projected source registry, so a cell's citation can resolve to a catalog slug.
    catalog: list[corpus_catalog.CatalogSource] = field(default_factory=list)
    #: The committed extractions themselves — the corpus the other feeds are derived FROM.
    records: list[corpus_records.CorpusRecord] = field(default_factory=list)


def load_mirror_feeds(settings: Settings | None = None) -> MirrorFeeds:
    """Load the committed corpus for the active site into the feeds the mirror projects from.

    Offline by construction: the entity graph is built with no live enrichments (all
    ``enrich_*`` default off), so this is a pure read of the committed corpus.
    """
    settings = settings or get_settings()
    profile = active_profile(settings)

    corpus = load_corpus(settings)
    egraph = build_entity_graph(corpus, settings=settings)

    # The [open] claims: the open-tagged hypothesis cells committed for *this* site.
    cells = [cell for cell in load_assessments(settings=settings) if cell.site == settings.site]
    open_claims = [cell for cell in cells if cell.tag == "open"]
    # Everything the site actually asserts. Dropping these is what left the mirror with zero
    # `[verified]` claims while the committed corpus held thousands (#2134).
    assessed_claims = [cell for cell in cells if cell.tag != "open"]
    return MirrorFeeds(
        site=settings.site,
        site_label=profile.place or settings.site.replace("-", " ").title(),
        site_detail=(
            f"{profile.place or settings.site} — {profile.basin} basin." if profile.basin else ""
        ),
        entities=graph_mod.export_entities(egraph),
        relationships=graph_mod.export_relationships(egraph),
        concepts=concepts_mod.load_concepts(settings.concepts_dir, site=settings.site),
        people=people_mod.export_people(
            load_people(site_scoped_path(settings.people_dir, settings.site, is_dir=True)),
            egraph=egraph,
        ),
        leads=leads_mod.export_leads(
            site_scoped_path(
                settings.data_dir / "site" / "leads.yaml", settings.site, is_dir=False
            ),
        ),
        open_claims=open_claims,
        assessed_claims=assessed_claims,
        catalog=corpus_catalog.build_catalog(settings),
        records=corpus_records.load_records(settings),
    )


def build_mirror(settings: Settings | None = None) -> Mirror:
    """Load the committed corpus for the active site and project it into a :class:`Mirror`.

    Offline by construction: the entity graph is built with no live enrichments (all
    ``enrich_*`` default off), so the mirror is a pure read of the committed corpus.
    """
    settings = settings or get_settings()
    feeds = load_mirror_feeds(settings)

    mirror = project_mirror(
        site=feeds.site,
        site_label=feeds.site_label,
        site_detail=feeds.site_detail,
        entities=feeds.entities,
        relationships=feeds.relationships,
        concepts=feeds.concepts,
        people=feeds.people,
        leads=feeds.leads,
        hypotheses=HYPOTHESES,
        open_claims=feeds.open_claims,
        assessed_claims=feeds.assessed_claims,
        catalog=feeds.catalog,
        records=feeds.records,
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
    """Render one class's :class:`ClassOntology` to its ``<class>.ont.yml``.

    yidam reads the class name from the *filename*, not the `class:` field — where the two
    disagree the stem governs — so this writes both and they are the same by construction.
    """
    ont = ONTOLOGY[node_class]
    body: dict[str, Any] = {
        "class": ont.name,
        "label": ont.label,
        "description": ont.description,
    }
    if ont.properties:
        body["properties"] = [
            {"name": p.name, "type": p.type, "description": p.description} for p in ont.properties
        ]
    if ont.edges:
        body["edge_policy"] = ont.edge_policy
        body["edges"] = [
            {
                "relationship": e.relationship,
                "target": e.target,
                "direction": e.direction,
                "description": e.description,
            }
            for e in ont.edges
        ]
    return yaml.safe_dump(body, sort_keys=False, allow_unicode=True)


def _universal_yaml() -> str:
    """Render :data:`UNIVERSAL_PROPERTIES` to ``.yidam/corpus/universal.yml``."""
    return yaml.safe_dump(
        {
            "properties": [
                {"name": p.name, "type": p.type, "description": p.description}
                for p in UNIVERSAL_PROPERTIES
            ]
        },
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
    for owned in ("README.md", "universal.yml"):
        stale = corpus_dir / owned
        if stale.exists():
            stale.unlink()


def write_mirror(mirror: Mirror, corpus_dir: Path) -> None:
    """Write ``mirror`` to ``corpus_dir`` as yidam node files (clearing a prior mirror first).

    Writes the **catalog** beside it, at `<corpus_dir>/../catalog/`. Not optional: the nodes
    cite it by relative link, so a corpus written alone fails its own "every link resolves"
    invariant on the first cited record.
    """
    corpus_dir.mkdir(parents=True, exist_ok=True)
    _clear_corpus(corpus_dir)
    corpus_catalog.write_catalog(mirror.catalog, corpus_dir.parent)

    # Written whatever classes are present: `undeclared-property` consults it for every class,
    # so a corpus that projected only `concept` still needs the artifact-side names covered.
    (corpus_dir / "universal.yml").write_text(_universal_yaml(), encoding="utf-8")

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


# --- walking a written mirror (yidam's walk.rs, in Python) ----------------------------------
@dataclass
class MirrorRegen:
    """The outcome of one mirror regeneration — what was projected, and the binary's verdict on it.

    ``graph_check``/``lint`` are ``None`` when the ``yidam`` binary is not installed. That is a
    normal state, not a failure: ``watermark export`` must run offline with no Rust toolchain, so
    the projection always happens and the *reports* are best-effort locally and mandatory in CI.
    """

    site: str
    corpus_dir: Path
    mirror: Mirror
    graph_check: Report | None = None
    lint: Report | None = None

    @property
    def checked(self) -> bool:
        """Whether the binary was available to report on this projection."""
        return self.graph_check is not None

    @property
    def ok(self) -> bool:
        """True when the mirror is valid — or was not checked.

        Unchecked is deliberately not failure. Treating "no binary installed" as a broken corpus
        would make every offline export red, which is how a gate gets switched off.
        """
        return self.graph_check is None or self.graph_check.passed


def regenerate_mirror(
    settings: Settings | None = None,
    *,
    corpus_dir: Path | None = None,
    mirror: Mirror | None = None,
    check: bool = True,
) -> MirrorRegen:
    """Project the active site's corpus into ``.yidam/corpus/`` — the call behind
    ``watermark corpus-mirror`` and the tail of ``watermark export`` (#1562).

    The **projection** is BOSC's and stays here. The **reports** over it belong to the real
    ``yidam`` binary (:mod:`watermark.site.yidam_cli`): BOSC used to re-implement all four in
    Python, and the replica had already drifted from the Rust symbols its docstrings cited. When
    the binary is installed this runs ``graph-check`` and ``lint`` over what was just written and
    hands back their verdicts; when it is not, it says so and returns an unchecked result.

    Pass a pre-projected ``mirror`` to reuse it (``watermark export`` builds one for the graph
    exports, #1574, and hands it back so the corpus is projected once, not twice). Pass
    ``check=False`` to skip the reports even when the binary is present.
    """
    settings = settings or get_settings()
    corpus_dir = corpus_dir or default_corpus_dir(settings)

    mirror = mirror if mirror is not None else build_mirror(settings)
    write_mirror(mirror, corpus_dir)

    graph_check: Report | None = None
    lint: Report | None = None
    if check:
        root = corpus_dir.parent.parent
        reports = yidam_cli.check_mirror(root=root)
        if reports is None:
            log.info(
                "corpus_mirror.unchecked",
                site=settings.site,
                hint="`mise run yidam-build` installs the pinned yidam; reports are gated in CI",
            )
        else:
            graph_check, lint = reports

    log.info(
        "corpus_mirror.regenerated",
        site=settings.site,
        nodes=len(mirror.nodes),
        checked=graph_check is not None,
        graph_ok=graph_check.passed if graph_check else None,
        lint_regressions=len(lint.regressions) if lint else None,
    )
    return MirrorRegen(
        site=settings.site,
        corpus_dir=corpus_dir,
        mirror=mirror,
        graph_check=graph_check,
        lint=lint,
    )
