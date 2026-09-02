"""The typed-path query engine over the corpus mirror — `query` / `pack` / `estimate` (#2132).

`neighbors` chains edges in both directions and filters on neither relationship nor direction:
it carries both out as labels on the result and reads neither as an input. A server offering
only that has typed its graph and left no way to walk by the types. **This is the walk.**

Three things this module holds that the MCP handlers in :mod:`watermark.agent.yidam_tools`
deliberately do not, because each is a distinction a caller branches on and a shape-passing
implementation would collapse:

* **A rejection is an answer, not an error.** ``rejected`` carries a frozen code and never
  travels as MCP's ``isError``. An empty ``results`` with ``rejected: None`` means the query was
  well formed and the corpus is quiet — and the two MUST be distinguishable, which is the whole
  reason this is not ``retrieve`` with a filter.
* **An absence is not a rejection.** ``rejected`` says the query is wrong; ``absence`` says the
  query is right and the corpus has nothing. Reporting a typo as ``class-unpopulated`` would
  tell a caller its mistake was a true negative.
* **A diagnostic is neither.** A query that *ran* can still report a near miss. Promoting those
  to rejections refuses legal queries.

The grammar is small and whitespace-delimited — ``-rel->`` and ``<-rel-`` are single tokens, so
a path is ``STEP HOP STEP HOP STEP``. A step is a class name or ``*``, optionally narrowed by a
property predicate ``[name=value]``, optionally opened by a similarity anchor ``~"text"`` which
only the entry step may carry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from watermark.site.corpus_mirror import (
    CLASSES,
    ONTOLOGY,
    UNIVERSAL_PROPERTIES,
    Mirror,
    MirrorNode,
    node_text,
    resolve_link_target,
)

#: Every projectable field name. ``properties.<name>`` is handled separately.
SELECTABLE = ("node", "class", "label", "description", "body")

#: The default projection — enough to identify a node and no prose.
DEFAULT_SELECT = "node,class,label"

#: Rejection codes, frozen by the contract. A client branches on these.
REJECTION_CODES = (
    "parse",
    "unknown-class",
    "unknown-property",
    "unlicensed-edge",
    "edge-target-class",
    "unknown-field",
    "anchor-not-entry",
    "anchor-unavailable",
    "anchor-unresolvable",
)

#: Absence codes, frozen by the contract. Three about the entry step, four about a hop, one
#: fallback. ``relationship-unauthored`` is the one worth the most — a relationship a class
#: licenses and no instance uses is invisible from every other angle, and comes back from a
#: traversal exactly as a mistyped name would.
ABSENCE_CODES = (
    "class-unpopulated",
    "predicate-unsatisfied",
    "anchor-empty",
    "relationship-unauthored",
    "relationship-unknown",
    "no-edge-from-here",
    "edge-lands-elsewhere",
    "no-match",
)

_STEP_RE = re.compile(
    r"""^
    (?P<cls>\*|[A-Za-z][A-Za-z0-9_-]*)          # a class name, or the wildcard
    (?:\[(?P<pred>[^\]]*)\])?                   # optional property predicate
    (?:~"(?P<anchor>[^"]*)")?                   # optional similarity anchor
    $""",
    re.X,
)
_FORWARD_RE = re.compile(r"^-(?P<rel>[^>\s]+)->$")
_BACKWARD_RE = re.compile(r"^<-(?P<rel>[^>\s]+)-$")


@dataclass(frozen=True)
class Step:
    """One step of a path: where to stand, and (after the first) how we got here."""

    node_class: str  # a class name, or "*"
    predicate: tuple[str, str] | None = None
    anchor: str | None = None
    relationship: str | None = None  # None on the entry step
    direction: str = "out"  # "out" follows an authored edge, "in" follows it backwards


@dataclass(frozen=True)
class Rejection:
    """The query is wrong. Never an ``isError`` — the caller branches on ``code``."""

    step: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"step": self.step, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class Diagnostic:
    """The query RAN and something about it is worth saying."""

    level: str
    step: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "step": self.step,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class Absence:
    """The query is right and the corpus is quiet — with the reason, derived not inferred.

    ``instances`` is the denominator the message is about: instances of the step's class at an
    entry step, nodes that reached the previous step at a hop. *None of three* and *none of nine
    hundred* are different facts about a corpus.
    """

    step: int
    code: str
    message: str
    instances: int
    elsewhere: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "code": self.code,
            "message": self.message,
            "instances": self.instances,
            # Always present, empty when there is nothing to name, so a client never has to
            # distinguish "no dependency holds this" from "the server did not look".
            "elsewhere": list(self.elsewhere),
        }


@dataclass
class Cost:
    """What the CALLER pays, not what the server did.

    ``nodes_read`` counts nodes whose content was evaluated by a predicate, tested for a hop's
    class, or projected — never the corpus load, which happens either way. Class narrowing is a
    directory listing and is not charged; a degraded keyword anchor **is** charged for every
    candidate it scored, because it read them. Counted as distinct nodes: a node evaluated twice
    costs a caller its content once.
    """

    steps: int = 0
    edges_walked: int = 0
    corpus_nodes: int = 0
    chars: int = 0
    _read: set[str] = field(default_factory=set)

    def read(self, node_ids: Any) -> None:
        self._read.update(node_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": self.steps,
            "edges_walked": self.edges_walked,
            "nodes_read": len(self._read),
            "chars": self.chars,
            # `chars / 4`, an approximation by construction and not a tokenizer. There is
            # deliberately no range: a caller holding a real tokenizer needs the exact `chars`
            # rather than a wider guess laid over it.
            "tokens": self.chars // 4,
            "corpus_nodes": self.corpus_nodes,
        }


@dataclass
class Execution:
    """A parsed, typechecked, executed path — everything the three tools render from."""

    query: str
    steps: tuple[Step, ...] = ()
    #: What each step's class resolved to — a `*` narrowed by a predicate reports the classes
    #: that declare it, which is the difference between "every class" and "the one that does".
    step_classes: tuple[tuple[str, ...], ...] = ()
    rejected: Rejection | None = None
    absence: Absence | None = None
    anchor: dict[str, Any] | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    matched: list[MirrorNode] = field(default_factory=list)
    at: int = 0
    cost: Cost = field(default_factory=Cost)


# --- the ontology, read as data ---------------------------------------------------------------
# From `ONTOLOGY` directly, never by parsing the emitted `.ont.yml` back. A second reader would
# be a second ontology, and the two would drift the way the report replica did (#2051).
def declared_properties(node_class: str) -> dict[str, str]:
    """``{name: type}`` a class declares, plus the corpus-wide universal ones."""
    out = {p.name: p.type for p in UNIVERSAL_PROPERTIES}
    if (ont := ONTOLOGY.get(node_class)) is not None:
        out.update({p.name: p.type for p in ont.properties})
    return out


def licensed_edges(node_class: str) -> list[dict[str, str]]:
    """Every edge ``node_class`` is party to, **from both ends**.

    An edge is documented from both sides: the class that authors it declares `direction: out`,
    and the class it lands on is party to the same relationship inbound. The licensing check
    ignores direction, so filtering to `out` here would answer a question the gate does not ask.
    """
    out: list[dict[str, str]] = []
    for owner, ont in ONTOLOGY.items():
        for edge in ont.edges:
            if owner == node_class:
                out.append(
                    {
                        "relationship": edge.relationship,
                        "target": edge.target,
                        "direction": "out",
                        "description": edge.description,
                    }
                )
            elif edge.target == node_class:
                out.append(
                    {
                        "relationship": edge.relationship,
                        "target": owner,
                        "direction": "in",
                        "description": edge.description,
                    }
                )
    return out


def _edge_spec(source_class: str, relationship: str, direction: str) -> tuple[str, str] | None:
    """``(owner, target)`` for a licensed hop, or ``None`` when no class licenses it that way."""
    for owner, ont in ONTOLOGY.items():
        for edge in ont.edges:
            if edge.relationship != relationship:
                continue
            if direction == "out" and owner == source_class:
                return owner, edge.target
            if direction == "in" and edge.target == source_class:
                return owner, owner
    return None


def _near_miss(name: str, candidates: Any) -> str | None:
    """The closest candidate within one edit — what makes a rejection actionable."""
    import difflib

    hit = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.6)
    return hit[0] if hit else None


# --- parsing ----------------------------------------------------------------------------------
#: Whitespace splits a path — except inside an anchor's quotes. `concept~"water quality"` is one
#: token and two words, and splitting it on the space rejected a legal query as malformed.
_TOKEN_RE = re.compile(r'[^\s"]*"[^"]*"[^\s"]*|\S+')


def tokenize(query: str) -> list[str]:
    """Split a path on whitespace, keeping a quoted anchor whole."""
    return _TOKEN_RE.findall(query or "")


def parse(query: str) -> tuple[tuple[Step, ...], Rejection | None]:
    """Split a path into steps, or reject it with ``parse``."""
    tokens = tokenize(query)
    if not tokens:
        return (), Rejection(0, "parse", "empty query — name a class, or `*`, to enter at")

    steps: list[Step] = []
    relationship: str | None = None
    direction = "out"
    for index, token in enumerate(tokens):
        if index % 2 == 0:
            match = _STEP_RE.match(token)
            if match is None:
                return (), Rejection(
                    len(steps),
                    "parse",
                    f"`{token}` is not a step — write a class name, `*`, "
                    '`class[property=value]`, or `class~"text"`',
                )
            predicate: tuple[str, str] | None = None
            if (raw := match.group("pred")) is not None:
                if "=" not in raw:
                    return (), Rejection(
                        len(steps),
                        "parse",
                        f"`[{raw}]` is not a predicate — write `[property=value]`",
                    )
                key, _, value = raw.partition("=")
                predicate = (key.strip(), value.strip())
            steps.append(
                Step(
                    node_class=match.group("cls"),
                    predicate=predicate,
                    anchor=match.group("anchor"),
                    relationship=relationship,
                    direction=direction,
                )
            )
        else:
            if (forward := _FORWARD_RE.match(token)) is not None:
                relationship, direction = forward.group("rel"), "out"
            elif (backward := _BACKWARD_RE.match(token)) is not None:
                relationship, direction = backward.group("rel"), "in"
            else:
                return (), Rejection(
                    len(steps),
                    "parse",
                    f"`{token}` is not a hop — write `-relationship->` or `<-relationship-`, "
                    "with whitespace around it",
                )
    if len(tokens) % 2 == 0:
        return (), Rejection(
            len(steps), "parse", "the path ends on a hop — name the class it lands on"
        )
    return tuple(steps), None


# --- typechecking -----------------------------------------------------------------------------
def step_classes(steps: tuple[Step, ...]) -> tuple[tuple[str, ...], ...]:
    """The classes each step actually stands on, after a `*` is narrowed by its predicate."""
    out: list[tuple[str, ...]] = []
    for step in steps:
        if step.node_class != "*":
            out.append((step.node_class,))
            continue
        if step.predicate is None:
            out.append(tuple(CLASSES))
            continue
        out.append(tuple(c for c in CLASSES if step.predicate[0] in declared_properties(c)))
    return tuple(out)


def typecheck(steps: tuple[Step, ...]) -> tuple[Rejection | None, list[Diagnostic]]:
    """Reject a path the ontology cannot license, and report what it can only warn about.

    Without an ontology every class name and every relationship is accepted, so a misspelling
    comes back as zero results — the one failure this tool exists to prevent.
    """
    diagnostics: list[Diagnostic] = []
    for index, step in enumerate(steps):
        if step.anchor is not None and index > 0:
            return (
                Rejection(
                    index,
                    "anchor-not-entry",
                    "only the entry step may open on a similarity anchor; a later `~` is not a "
                    "filter and is refused rather than reinterpreted as one",
                ),
                diagnostics,
            )
        if step.node_class != "*" and step.node_class not in CLASSES:
            near = _near_miss(step.node_class, CLASSES)
            return (
                Rejection(
                    index,
                    "unknown-class",
                    f"no class `{step.node_class}`"
                    + (f" — did you mean `{near}`?" if near else "")
                    + f" (declared: {', '.join(CLASSES)})",
                ),
                diagnostics,
            )
        if step.predicate is not None:
            classes = CLASSES if step.node_class == "*" else (step.node_class,)
            declaring = [c for c in classes if step.predicate[0] in declared_properties(c)]
            if not declaring:
                # Over EVERY candidate, not `classes[0]`: the rejection was decided across all
                # of them, so drawing the hint from one arbitrary class hides the near miss a
                # later class would have supplied.
                near = _near_miss(
                    step.predicate[0], {p for c in classes for p in declared_properties(c)}
                )
                return (
                    Rejection(
                        index,
                        "unknown-property",
                        f"no class declares `{step.predicate[0]}`"
                        + (f" — did you mean `{near}`?" if near else ""),
                    ),
                    diagnostics,
                )
            if step.node_class == "*" and len(declaring) < len(CLASSES):
                diagnostics.append(
                    Diagnostic(
                        "info",
                        index,
                        "star-narrowed",
                        f"`*` narrowed to the classes declaring `{step.predicate[0]}`: "
                        + ", ".join(declaring),
                    )
                )
        if step.relationship is None:
            continue
        source = steps[index - 1].node_class
        sources = CLASSES if source == "*" else (source,)
        licensed = [c for c in sources if _edge_spec(c, step.relationship, step.direction)]
        if not licensed:
            every = {e.relationship for ont in ONTOLOGY.values() for e in ont.edges}
            near = _near_miss(step.relationship, every)
            hint = f" — did you mean `{near}`?" if near else ""
            direction = "outbound" if step.direction == "out" else "inbound"
            # **A non-empty `edges:` says these relationships exist, not "and no others may."**
            # Only `exhaustive` closes the vocabulary; under any other policy an undeclared
            # relationship is a DIAGNOSTIC on a query that runs. Reading every declaration as
            # exhaustive put 210 errors on a compliant corpus upstream, and a server that
            # rejects here refuses legal queries against every corpus written before the field
            # existed. BOSC declares `exhaustive` on all five classes — truthfully, because its
            # mirror is generated — so it takes the rejecting arm; the other is the contract's
            # and is exercised in the tests.
            closed = all(ONTOLOGY[c].edge_policy == "exhaustive" for c in sources if c in ONTOLOGY)
            if closed:
                return (
                    Rejection(
                        index,
                        "unlicensed-edge",
                        f"`{source}` does not license `{step.relationship}` {direction}{hint}",
                    ),
                    diagnostics,
                )
            diagnostics.append(
                Diagnostic(
                    "warn",
                    index,
                    "undeclared-relationship",
                    f"`{source}` does not declare `{step.relationship}` {direction}{hint}; its "
                    "edge policy is not exhaustive, so the query runs",
                )
            )
            continue
        if step.node_class != "*":
            targets = {
                spec[1]
                for c in licensed
                if (spec := _edge_spec(c, step.relationship, step.direction))
            }
            if step.node_class not in targets:
                return (
                    Rejection(
                        index,
                        "edge-target-class",
                        f"`{step.relationship}` lands on {', '.join(sorted(targets))}, "
                        f"not on `{step.node_class}`",
                    ),
                    diagnostics,
                )
    return None, diagnostics


# --- execution --------------------------------------------------------------------------------
def _property_of(node: MirrorNode, name: str) -> Any:
    return node.meta.get(name)


def _satisfies(node: MirrorNode, predicate: tuple[str, str]) -> bool:
    """Whether a node's property matches, comparing on the tag rather than the spelling.

    A `type: claim` property is written `[open]` here and `open` upstream, and both are the same
    standing — so `[claim_tag=open]` must match either. Stripping the brackets on both sides is
    what makes the predicate answer the same question the claim counter does.
    """
    name, wanted = predicate
    value = _property_of(node, name)
    if value is None:
        return False
    if isinstance(value, list):
        return any(str(v).strip().strip("[]") == wanted.strip("[]") for v in value)
    return str(value).strip().strip("[]") == wanted.strip("[]")


def _keyword_entries(
    mirror: Mirror, node_classes: tuple[str, ...], text: str, k: int
) -> list[MirrorNode]:
    """The degraded anchor: term-overlap over the entry step's instances, best first.

    Takes the step's RESOLVED classes, not its written one. `*[rel=owns]~"water"` narrows to the
    classes that declare `rel` before the anchor runs, so the anchor scores that pool and no
    other — otherwise it both leaks out-of-class nodes into `anchor.entries` and scores far more
    candidates than `cost` is charged for.
    """
    terms = [t for t in re.split(r"\s+", text.lower().strip()) if t]
    if not terms:
        return []
    pool = [n for n in mirror.nodes if n.node_class in node_classes]
    scored = []
    for node in pool:
        haystack = node_text(node).lower()
        hits = sum(1 for t in terms if t in haystack)
        if hits:
            scored.append((hits / len(terms), node))
    scored.sort(key=lambda s: (-s[0], s[1].id))
    return [node for _, node in scored[:k]]


def _edges(mirror: Mirror) -> list[tuple[str, str, str]]:
    """Every ``(from_id, to_id, relationship)``, targets resolved to node ids."""
    return [
        (node.id, resolve_link_target(node.node_class, link.target), link.relationship)
        for node in mirror.nodes
        for link in node.links
    ]


def _authored(mirror: Mirror, relationship: str) -> bool:
    return any(link.relationship == relationship for node in mirror.nodes for link in node.links)


def execute(
    mirror: Mirror,
    query: str,
    *,
    anchor_k: int = 1,
    vector_ready: bool = False,
) -> Execution:
    """Parse, typecheck and walk. Never raises for a bad query — it returns a rejection."""
    run = Execution(query=query)
    run.cost.corpus_nodes = len(mirror.nodes)

    steps, rejection = parse(query)
    if rejection is not None:
        run.rejected = rejection
        return run
    run.steps = steps
    run.step_classes = step_classes(steps)
    run.cost.steps = len(steps)

    rejection, diagnostics = typecheck(steps)
    run.diagnostics = diagnostics
    if rejection is not None:
        run.rejected = rejection
        return run

    by_id = {n.id: n for n in mirror.nodes}
    edges = _edges(mirror)

    # --- the entry step ---------------------------------------------------------------------
    entry = steps[0]
    entry_classes = run.step_classes[0]
    pool = [n for n in mirror.nodes if n.node_class in entry_classes]
    if entry.anchor is not None:
        # `degraded` lives on the anchor, never at the top level: a query with no anchor
        # performed no retrieval, and a `false` up there would read as retrieval succeeding.
        entries = _keyword_entries(mirror, entry_classes, entry.anchor, max(1, anchor_k))
        # `pool` IS what the anchor scored — same classes, same nodes. The charge is honest only
        # because those two are built from `entry_classes`; feeding the anchor a wider set would
        # silently under-bill the most expensive step there is.
        run.cost.read(n.id for n in pool)
        run.anchor = {
            "step": 0,
            "text": entry.anchor,
            "k": max(1, anchor_k),
            "degraded": not vector_ready,
            "degraded_reason": None if vector_ready else "no_index",
            "repair": None
            if vector_ready
            else "build the corpus vector index — `mise run corpus-vector-index`",
            "entries": [{"node": n.id, "class": n.node_class, "label": n.label} for n in entries],
        }
        current = entries
        if not current:
            run.absence = Absence(
                0,
                "anchor-empty",
                f"the similarity anchor {entry.anchor!r} resolved to no entry node",
                len(pool),
            )
            return run
    else:
        current = pool
        if not current:
            run.absence = Absence(
                0,
                "class-unpopulated",
                f"the ontology declares `{entry.node_class}` and it holds no instances",
                0,
            )
            return run

    if entry.predicate is not None:
        run.cost.read(n.id for n in current)
        before = len(current)
        current = [n for n in current if _satisfies(n, entry.predicate)]
        if not current:
            run.absence = Absence(
                0,
                "predicate-unsatisfied",
                f"`{entry.node_class}` holds instances and none satisfies "
                f"`{entry.predicate[0]}={entry.predicate[1]}`",
                before,
            )
            return run

    # --- the hops ---------------------------------------------------------------------------
    for index, step in enumerate(steps[1:], start=1):
        run.at = index
        assert step.relationship is not None
        reached = len(current)
        here = {n.id for n in current}
        if step.direction == "out":
            landed = [to for (frm, to, rel) in edges if rel == step.relationship and frm in here]
        else:
            landed = [frm for (frm, to, rel) in edges if rel == step.relationship and to in here]
        run.cost.edges_walked += len(landed)

        if not landed:
            # Declared-and-unused and never-heard-of come back from a traversal identically and
            # their repairs are opposite, so they are split. The first is a corpus that has not
            # written what its ontology promises; the second is almost always a typo.
            if not _authored(mirror, step.relationship):
                code, message = (
                    "relationship-unauthored",
                    f"a class declares `{step.relationship}` and no instance authors it",
                )
            else:
                code, message = (
                    "no-edge-from-here",
                    f"`{step.relationship}` is authored elsewhere, by nothing that reached "
                    "the previous step",
                )
            run.absence = Absence(index, code, message, reached)
            return run

        candidates = [by_id[i] for i in dict.fromkeys(landed) if i in by_id]
        run.cost.read(n.id for n in candidates)
        current = [n for n in candidates if n.node_class in run.step_classes[index]]
        if not current:
            run.absence = Absence(
                index,
                "edge-lands-elsewhere",
                f"edges were followed and nothing they landed on is a `{step.node_class}`",
                reached,
            )
            return run
        if step.predicate is not None:
            before = len(current)
            current = [n for n in current if _satisfies(n, step.predicate)]
            if not current:
                run.absence = Absence(
                    index,
                    "predicate-unsatisfied",
                    f"nothing reached satisfies `{step.predicate[0]}={step.predicate[1]}`",
                    before,
                )
                return run

    # By id, not by identity: `MirrorNode` is a mutable dataclass and so unhashable, and a
    # node reached by two edges must be one result rather than two.
    unique = {n.id: n for n in current}
    run.matched = [unique[i] for i in sorted(unique)]
    if not run.matched:
        run.absence = Absence(run.at, "no-match", "the path matched nothing", len(mirror.nodes))
    return run


# --- projection -------------------------------------------------------------------------------
def project(node: MirrorNode, select: list[str]) -> dict[str, Any]:
    """One matched node, rendered to the requested fields — plus its ``origin``.

    ``origin`` is null for a node from this corpus and names the package a node came from when
    a query spans. It is present whether or not the query spanned, so a client never has to
    distinguish "local" from "a server that does not attribute".
    """
    row: dict[str, Any] = {"origin": None}
    for name in select:
        if name == "node":
            row["node"] = node.id
        elif name == "class":
            row["class"] = node.node_class
        elif name == "label":
            row["label"] = node.label
        elif name == "description":
            row["description"] = node.description
        elif name == "body":
            row["body"] = node_text(node)
        elif name.startswith("properties."):
            row[name] = _property_of(node, name.split(".", 1)[1])
    return row


def parse_select(raw: str | None) -> tuple[list[str], Rejection | None]:
    """Split and validate a ``select``, rejecting a field nothing can project."""
    fields = [f.strip() for f in (raw or DEFAULT_SELECT).split(",") if f.strip()]
    if not fields:
        return list(DEFAULT_SELECT.split(",")), None
    for name in fields:
        if name in SELECTABLE or name.startswith("properties."):
            continue
        near = _near_miss(name, SELECTABLE)
        return (
            [],
            Rejection(
                0,
                "unknown-field",
                f"`{name}` is not projectable"
                + (f" — did you mean `{near}`?" if near else "")
                + f" (available: {', '.join(SELECTABLE)}, properties.<name>)",
            ),
        )
    return fields, None
