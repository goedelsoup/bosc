"""The wiki cross-link audit — ``watermark wiki-lint`` (corpus-hygiene, #1571, epic #1560 · C).

BOSC's ``[[wiki links]]`` are the reader-facing cross-links of the glossary: a ``[[Target]]`` in
a concept or person **body** resolves — by normalized title, key, slug, or alias — to the concept,
entity, or person page for that term (:mod:`web/packages/core/src/wiki.ts`, the Astro frontend).
An unresolved one ships to the site as a dotted ``wikilink-missing`` span — a visible dead link.

``yidam graph-check`` / ``yidam lint`` (ported over the yidam **node** graph in
:mod:`watermark.site.corpus_mirror`) audit the *projected* mirror's structured ``links:`` — but
that projection carries only the concepts' ``related`` slugs, never the inline ``[[…]]`` prose
links, so the node graph is blind to exactly the cross-links a reader navigates. This module is
the missing content-level pass: it rebuilds the **wiki cross-reference graph** (resolved body
``[[…]]`` + ``related`` slugs, over the same site-scoped concepts / entities / people the frontend
indexes) and flags the three gaps the issue names —

* **unresolved ``[[wiki links]]``** — an inline link (or a ``related:`` slug) that resolves to no
  node; the hard gate (``--check``), because it ships as a broken cross-link.
* **orphan concepts** — a glossary concept no other concept or profile links to (undiscoverable).
* **under-linked concepts** — a concept with fewer than ``min_degree`` total cross-links.

with optional ``--suggest`` hints: other wiki nodes a concept *names in prose* but never links.
The resolution index and the ``norm``/whole-phrase matching mirror ``wiki.ts`` exactly, so a clean
``wiki-lint`` means the frontend renders no missing spans over the same feeds. Offline, per-site,
read-only (the committed corpus stays the source of truth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.site.corpus_mirror import MirrorFeeds, load_mirror_feeds
from watermark.site.feeds import ConceptItem, EntityNode, PersonItem

log = get_logger(__name__)

_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
_NORM_RE = re.compile(r"[^a-z0-9]+")


def norm(text: str) -> str:
    """Normalize a label/key/slug to a comparable token — the peer of ``wiki.ts``'s ``norm``."""
    return _NORM_RE.sub(" ", (text or "").lower()).strip()


def _backlinkable(name: str) -> bool:
    """Whether a normalized name is specific enough to match as a plain-text mention.

    The peer of ``wiki.ts``'s ``backlinkable``: a very short single token (``pH``, a 3-letter
    initialism) matches noise, so only multi-word names or single tokens of ≥4 chars qualify.
    """
    n = norm(name)
    return bool(n) and (" " in n or len(n) >= 4)


# --- the resolution index (the Python peer of wiki.ts `wikiIndex`) --------------------------
@dataclass(frozen=True)
class WikiTarget:
    """One resolvable wiki node — a concept, entity, or profiled person."""

    id: str  # stable node id: `concept:<slug>` | `entity:<key>` | `person:<slug>`
    label: str
    kind: str  # "concept" | "entity" | "person"


def build_wiki_index(
    concepts: list[ConceptItem],
    entities: list[EntityNode],
    people: list[PersonItem],
) -> dict[str, WikiTarget]:
    """Build ``normalized name → node`` over concepts, entities, and people (first writer wins).

    Faithful to ``wiki.ts``'s ``wikiIndex``: a concept is keyed by its slug, title, and aliases;
    an entity by its key, display, and variants; a person by their slug, name, and aliases. The
    insertion order (concepts, then entities, then people) and first-writer-wins tie-break match
    the frontend, so a ``[[Target]]`` resolves here iff it resolves there.
    """
    index: dict[str, WikiTarget] = {}

    def add(names: list[str], target: WikiTarget) -> None:
        for n in names:
            key = norm(n)
            if key and key not in index:
                index[key] = target

    for c in concepts:
        add([c.slug, c.title, *c.aliases], WikiTarget(f"concept:{c.slug}", c.title, "concept"))
    for e in entities:
        add([e.key, e.display, *e.variants], WikiTarget(f"entity:{e.key}", e.display, "entity"))
    for p in people:
        add([p.slug, p.name, *p.aliases], WikiTarget(f"person:{p.slug}", p.name, "person"))
    return index


# --- findings -------------------------------------------------------------------------------
@dataclass
class UnresolvedLink:
    """One ``[[wiki link]]`` (or ``related:`` slug) that resolves to no node — a broken cross-link."""

    source_id: str  # the concept/person node the link lives in
    source_label: str
    target: str  # the raw bracket text / related slug as written
    via: str  # "body" | "related"
    line: int | None = None  # 1-based line within the body ("related" links have none)


@dataclass
class OrphanConcept:
    """A glossary concept no other concept or profile links to — undiscoverable in the wiki."""

    id: str
    label: str
    out_degree: int  # it may link out; nothing links *in*


@dataclass
class UnderlinkedConcept:
    """A concept with fewer than ``min_degree`` total cross-links (in + out)."""

    id: str
    label: str
    in_degree: int
    out_degree: int

    @property
    def degree(self) -> int:
        return self.in_degree + self.out_degree


@dataclass
class LinkSuggestion:
    """A proposed ``[[link]]`` a concept could add — it *names* ``target`` in prose but never
    links it — that would strengthen a weak node on one end (a ``--suggest`` hint)."""

    source_id: str  # the concept whose body mentions the target
    source_label: str
    target: WikiTarget  # the node it names but doesn't link
    helps: str  # which weak node this edge would strengthen: "orphan-target" | "under-linked"


@dataclass
class WikiLintReport:
    """The outcome of one wiki cross-link audit for a site."""

    site: str
    concepts: int
    links_scanned: int
    unresolved: list[UnresolvedLink] = field(default_factory=list)
    orphans: list[OrphanConcept] = field(default_factory=list)
    underlinked: list[UnderlinkedConcept] = field(default_factory=list)
    suggestions: list[LinkSuggestion] = field(default_factory=list)
    min_degree: int = 2

    @property
    def ok(self) -> bool:
        """True when the hard gate is clean — no unresolved ``[[wiki links]]``.

        Orphan / under-linked findings are advisory (like ``yidam lint``): a concept can be
        legitimately terminal, so they never fail the gate — only broken cross-links do.
        """
        return not self.unresolved


# --- the audit ------------------------------------------------------------------------------
def _iter_body_links(body: str) -> list[tuple[str, int]]:
    """Every ``[[inner]]`` in ``body`` as ``(inner, 1-based line)``."""
    out: list[tuple[str, int]] = []
    for m in _WIKILINK_RE.finditer(body or ""):
        line = (body.count("\n", 0, m.start())) + 1
        out.append((m.group(1), line))
    return out


def audit_wiki(
    feeds: MirrorFeeds,
    *,
    min_degree: int = 2,
    suggest: bool = False,
) -> WikiLintReport:
    """Audit the wiki cross-reference graph over already-loaded ``feeds`` (pure, no I/O).

    Builds the resolution index, resolves every concept/person body ``[[…]]`` and every concept
    ``related:`` slug, and derives the per-concept in/out degree of the resulting graph. Concepts
    are the audited node set (the glossary backbone); entities and people are resolution targets
    and link *sources*, not orphan-audited (both are reached through their own hosts).
    """
    index = build_wiki_index(feeds.concepts, feeds.entities, feeds.people)

    unresolved: list[UnresolvedLink] = []
    # Distinct directed edges `source_id -> target_id`, and the reverse, over the audited graph.
    out_targets: dict[str, set[str]] = {}
    in_sources: dict[str, set[str]] = {}
    links_scanned = 0

    def resolve(source_id: str, raw: str) -> WikiTarget | None:
        target = index.get(norm(raw))
        if target is not None and target.id != source_id:
            out_targets.setdefault(source_id, set()).add(target.id)
            in_sources.setdefault(target.id, set()).add(source_id)
        return target

    def scan_body(source_id: str, source_label: str, body: str) -> None:
        nonlocal links_scanned
        for inner, line in _iter_body_links(body):
            links_scanned += 1
            if resolve(source_id, inner) is None:
                unresolved.append(UnresolvedLink(source_id, source_label, inner, "body", line))

    for c in feeds.concepts:
        cid = f"concept:{c.slug}"
        scan_body(cid, c.title, c.body)
        for slug in c.related:  # `related:` slugs are cross-links too — resolve + audit them
            links_scanned += 1
            if resolve(cid, slug) is None:
                unresolved.append(UnresolvedLink(cid, c.title, slug, "related", None))
    for p in feeds.people:
        scan_body(f"person:{p.slug}", p.name, p.body)

    # Orphan / under-linked over the *concept* node set only.
    orphans: list[OrphanConcept] = []
    underlinked: list[UnderlinkedConcept] = []
    for c in feeds.concepts:
        cid = f"concept:{c.slug}"
        out_deg = len(out_targets.get(cid, ()))
        in_deg = len(in_sources.get(cid, ()))
        if in_deg == 0:
            orphans.append(OrphanConcept(cid, c.title, out_deg))
        if in_deg + out_deg < min_degree:
            underlinked.append(UnderlinkedConcept(cid, c.title, in_deg, out_deg))

    suggestions = _suggest_links(feeds, index, out_targets, orphans, underlinked) if suggest else []

    report = WikiLintReport(
        site=feeds.site,
        concepts=len(feeds.concepts),
        links_scanned=links_scanned,
        unresolved=unresolved,
        orphans=orphans,
        underlinked=underlinked,
        suggestions=suggestions,
        min_degree=min_degree,
    )
    log.info(
        "wiki_lint.audited",
        site=feeds.site,
        concepts=report.concepts,
        links=links_scanned,
        unresolved=len(unresolved),
        orphans=len(orphans),
        underlinked=len(underlinked),
    )
    return report


_SUGGEST_CAP = 24  # max total suggestions — keep the hint list actionable


def _suggest_links(
    feeds: MirrorFeeds,
    index: dict[str, WikiTarget],
    out_targets: dict[str, set[str]],
    orphans: list[OrphanConcept],
    underlinked: list[UnderlinkedConcept],
) -> list[LinkSuggestion]:
    """Propose ``[[link]]``s that would strengthen the weak concepts (peer of ``yidam lint
    --suggest``).

    A candidate edge is a concept that *names* another wiki node in plain prose (a whole
    normalized phrase, outside any existing ``[[…]]``) but doesn't link it. We keep the edges
    that would help a weak node on either end: one whose **target** is an orphan concept (adds
    the incoming link it lacks) or whose **source** is under-linked (grows its out-degree).
    Advisory only — the author decides which are apt.
    """
    orphan_ids = {o.id for o in orphans}
    underlinked_ids = {u.id for u in underlinked}
    suggestions: list[LinkSuggestion] = []
    for c in feeds.concepts:
        cid = f"concept:{c.slug}"
        # The prose with existing wiki links stripped, normalized + space-padded for whole-phrase
        # matching (` name ` never matches a substring).
        prose = f" {norm(_WIKILINK_RE.sub(' ', c.body))} "
        linked = out_targets.get(cid, set())
        seen: set[str] = set()
        for name, target in index.items():
            if target.id == cid or target.id in linked or target.id in seen:
                continue
            if not (_backlinkable(name) and f" {name} " in prose):
                continue
            seen.add(target.id)
            if target.id in orphan_ids:  # this edge gives an orphan the incoming link it lacks
                suggestions.append(LinkSuggestion(cid, c.title, target, "orphan-target"))
            elif cid in underlinked_ids:  # this edge grows an under-linked concept's out-degree
                suggestions.append(LinkSuggestion(cid, c.title, target, "under-linked"))
    # Orphan-repairing edges first (the higher-value fix), then by node — capped.
    suggestions.sort(key=lambda s: (s.helps != "orphan-target", s.source_id, s.target.label))
    return suggestions[:_SUGGEST_CAP]


def lint_wiki(
    settings: Settings | None = None,
    *,
    min_degree: int = 2,
    suggest: bool = False,
) -> WikiLintReport:
    """Load the active site's corpus and audit its wiki cross-links (the ``watermark wiki-lint``
    engine). Offline, read-only; the committed corpus stays the source of truth."""
    settings = settings or get_settings()
    feeds = load_mirror_feeds(settings)
    return audit_wiki(feeds, min_degree=min_degree, suggest=suggest)


# --- rendering ------------------------------------------------------------------------------
def render_report(report: WikiLintReport, *, suggest: bool = False) -> str:
    """A plain-text ``wiki-lint`` report (the ``--out`` artifact; also the report file body)."""
    out: list[str] = [
        f"wiki-lint · {report.site} — {report.concepts} concept(s), "
        f"{report.links_scanned} cross-link(s) scanned"
    ]
    if report.unresolved:
        out.append(f"\nunresolved [[wiki links]] ({len(report.unresolved)}):")
        for u in report.unresolved:
            where = f"{u.source_id}" + (f":{u.line}" if u.line else " (related)")
            out.append(f"  [{u.via}] {where} → [[{u.target}]]")
    if report.orphans:
        out.append(f"\norphan concepts ({len(report.orphans)}) — nothing links to them:")
        out.extend(f"  {o.id} (out {o.out_degree})" for o in report.orphans)
    if report.underlinked:
        out.append(
            f"\nunder-linked concepts ({len(report.underlinked)}) — degree < {report.min_degree}:"
        )
        out.extend(f"  {u.id} (in {u.in_degree}, out {u.out_degree})" for u in report.underlinked)
    if suggest and report.suggestions:
        out.append(
            f"\nsuggested links ({len(report.suggestions)}) — mentioned in prose, not linked:"
        )
        for s in report.suggestions:
            why = "→ orphan" if s.helps == "orphan-target" else "(under-linked)"
            out.append(f"  {s.source_id} could link [[{s.target.label}]] {why}")
    if report.ok and not report.orphans and not report.underlinked:
        out.append("\nall clean — every cross-link resolves, no orphan or under-linked concepts.")
    elif report.ok:
        out.append("\ngate: clean (no unresolved links; orphan/under-linked are advisory).")
    else:
        out.append(f"\ngate: FAIL — {len(report.unresolved)} unresolved [[wiki link(s)]].")
    return "\n".join(out)
