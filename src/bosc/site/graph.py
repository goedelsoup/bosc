"""Render the cross-document layer (timeline + entity graph) as site pages.

Reuses the structured returns of :func:`bosc.pipeline.timeline.build_timeline`
and :func:`bosc.pipeline.entities.build_entity_graph` — not the Rich console
tables — and emits markdown: a chronology table, an entity/relationship pair of
tables, and a Mermaid diagram of the graph so the shared-agent shell cluster is
visible at a glance.
"""

from __future__ import annotations

import re

from bosc.pipeline.entities import RELATION_CLASS_ORDER, EntityGraph
from bosc.pipeline.timeline import TimelineEvent

# Evidence-discipline note reused verbatim from the dossier's framing.
_SIGNALS_NOTE = (
    '!!! note "Signals are evidence, not verdicts"\n'
    "    A shared registered agent or an out-of-state (`delaware`) formation is "
    "*common-control plumbing* read from public records — **not** a statement "
    "about beneficial ownership. Treat flagged signals as leads to verify, not "
    "conclusions. A **relation class** (below) is likewise an editorial reading of "
    "an already-verified party — never a new claim, and never a new node."
)

# Relation-class display labels + one-line definitions, in proximity order. Kept in
# sync with the controlled vocabulary in bosc.pipeline.entities (RELATION_CLASS_ORDER)
# and the self-documenting overlay (data/entities/profiles/relation-classes.yaml).
_RELATION_CLASS_LABELS: dict[str, str] = {
    "bosc_relation": "Project BOSC",
    "direct_approval": "Direct approval",
    "direct_manage": "Direct management",
    "direct_beneficiary": "Direct beneficiary",
    "possible_end_user": "End user",
    "environmental_beneficiary": "Environmental beneficiary",
    "govt_relation": "Government relation",
}
_RELATION_CLASS_DEFS: dict[str, str] = {
    "bosc_relation": "Project BOSC itself — its developer + campus entities.",
    "direct_approval": "A body that voted for / permitted the project.",
    "direct_manage": "Builds, operates, or finances the campus, its utilities, or the deal vehicle.",
    "direct_beneficiary": "Named recipient of the public benefit (abatement, captured revenue).",
    "possible_end_user": "The data-center customer the campus serves (confidence stated in the basis).",
    "environmental_beneficiary": "A receiving water / body bearing the project's externality.",
    "govt_relation": "A known tie to another government entity.",
}
# Muted fills for the Mermaid diagram, one per relation class.
_RELATION_CLASS_FILL: dict[str, str] = {
    "bosc_relation": "#cde4ff",
    "direct_approval": "#d7f0d0",
    "direct_manage": "#fff2c9",
    "direct_beneficiary": "#ffe0c2",
    "possible_end_user": "#e6d6ff",
    "environmental_beneficiary": "#c9eee7",
    "govt_relation": "#eaeaea",
}


def _relation_label(cls: str | None) -> str:
    """Short display label for a relation class, or an em dash."""
    return _RELATION_CLASS_LABELS.get(cls or "", "—")


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _src_link(rel: str) -> str:
    """Link a ``data/extracted``-relative source to its mirrored raw artifact."""
    return f"[`{_esc(rel)}`](data/extracted/{rel})"


def render_timeline(events: list[TimelineEvent]) -> str:
    """Render the assembled chronology as a dated markdown table."""
    lines = [
        "# Timeline",
        "",
        f"A single chronology assembled across the corpus — {len(events)} dated "
        "events, each citing the extraction it came from. Dates are transcribed "
        "from degraded scans; undated events sort to the end.",
        "",
        "| Date | Category | Event | Source |",
        "|---|---|---|---|",
    ]
    for e in events:
        date = e.date or "—"
        extra = f" (+{len(e.also_sources)})" if e.also_sources else ""
        lines.append(
            f"| {_esc(date)} | {_esc(e.category)} | {_esc(e.title)} | {_src_link(e.source)}{extra} |"
        )
    lines.append("")
    return "\n".join(lines)


def _node_id(key: str, seen: dict[str, str]) -> str:
    """A stable, Mermaid-safe node id for an entity key."""
    if key not in seen:
        seen[key] = "n" + re.sub(r"[^A-Za-z0-9]", "_", key) + str(len(seen))
    return seen[key]


def _mermaid(graph: EntityGraph) -> list[str]:
    """A Mermaid ``graph LR`` of the entity graph.

    Nodes are filled by **relation class** when classified; otherwise a shell-adjacent
    **signal** keeps the pink flag. (Relation class takes precedence so the proximity
    grouping reads at a glance; the Entities table still carries every signal.)
    """
    ids: dict[str, str] = {}
    lines = ["```mermaid", "graph LR"]
    flagged: list[str] = []
    by_class: dict[str, list[str]] = {}
    for key, ent in sorted(graph.entities.items()):
        nid = _node_id(key, ids)
        label = ent.display.replace('"', "'")
        lines.append(f'  {nid}["{label}"]')
        if ent.relation_class in _RELATION_CLASS_FILL:
            by_class.setdefault(ent.relation_class or "", []).append(nid)
        elif ent.signals:
            flagged.append(nid)
    for r in graph.relationships:
        if r.src not in graph.entities or r.dst not in graph.entities:
            continue
        src = _node_id(r.src, ids)
        dst = _node_id(r.dst, ids)
        rel = r.rel.replace("_", " ")
        lines.append(f"  {src} -->|{rel}| {dst}")
    if flagged:
        lines.append("  classDef flagged fill:#fde,stroke:#c39;")
        lines.append("  class " + ",".join(flagged) + " flagged;")
    for cls in RELATION_CLASS_ORDER:
        nids = by_class.get(cls)
        if not nids:
            continue
        lines.append(f"  classDef {cls} fill:{_RELATION_CLASS_FILL[cls]},stroke:#667;")
        lines.append(f"  class {','.join(nids)} {cls};")
    lines.append("```")
    return lines


def render_entities(graph: EntityGraph, *, profile_slugs: dict[str, str] | None = None) -> str:
    """Render the entity graph: Mermaid diagram + entity & relationship tables.

    ``profile_slugs`` maps an entity key to a published person-profile slug; matching
    entities link their name to ``people/<slug>.md`` (the curated detail store).
    """
    profile_slugs = profile_slugs or {}
    lines = [
        "# Entity graph",
        "",
        f"{len(graph.entities)} resolved parties and {len(graph.relationships)} "
        "relationships, merged across deeds, permits, and Secretary-of-State "
        "filings. Nodes carrying a shell-adjacent **signal** (shared agent, "
        "out-of-state formation) are highlighted.",
        "",
        "See also the curated [cloud-consumer candidates](candidates.md) — corridor "
        "operations marked on demand-fit only (not corpus-derived, not customers).",
        "",
    ]
    if any("army_controlled" in e.signals for e in graph.entities.values()):
        lines += [
            "One node is folded in from county parcel records (`data/reference/allen-gis`), "
            "not a deed: the federally-held **United States / JSMC (Lima Army Tank Plant)** "
            "land — Allen County's documented defense-industry footprint (see "
            "[defense contractors](defense-contractors.md)).",
            "",
        ]
    if any(e.lei for e in graph.entities.values()):
        lines += [
            "Nodes carrying a **GLEIF Legal Entity Identifier** are folded in from "
            "`data/reference/gleif`: **General Dynamics Land Systems** (the JSMC "
            "operator and Allen County's [RSEI](rsei.md) #3 facility) and its "
            "GLEIF-reported ultimate parent, **General Dynamics Corporation**. The "
            "`owned_by` edge is verified from GLEIF; `tenant_of` the Army-owned JSMC "
            "is an *operator inference* from RSEI + county CAMA, not a deed.",
            "",
        ]
    if any(e.classification == "industrial_facility" for e in graph.entities.values()):
        lines += [
            "An **industrial-ownership layer** is folded in from [RSEI](rsei.md) + GLEIF: "
            "the Allen County toxic-release facilities (incl. the Ottawa-corridor "
            "[toxic water dischargers](rsei.md)) linked `owned_by` their GLEIF-resolved "
            "corporate parents (INEOS, Cenovus, Shell, Ford, Marathon, Dana, Textron, "
            "P&G) — who owns the dischargers.",
            "",
        ]
    if any(e.federal_obligations for e in graph.entities.values()):
        lines += [
            "Nodes with a **federal-award footprint** carry their USASpending UEI + "
            "all-time prime-award obligations (`data/reference/usaspending`): the "
            "corridor's federal defense nexus — **General Dynamics Land Systems** "
            "(~$33.6 B) and parent **General Dynamics Corp** (~$299 B) — and the "
            "corridor land recipient **Amazon.com Services LLC** (~$0.7 M; a "
            "*warehouse*, not the data center). The data-center end user is **Google** "
            "(PAAC/LACRPC minutes; see the Dossier) — kept off the graph as a fabricated "
            "edge, so its federal figures never read as a Lima-campus obligation.",
            "",
        ]
    lines += [
        _SIGNALS_NOTE,
        "",
        "## Graph",
        "",
        *_mermaid(graph),
        "",
        *_relation_section(graph, profile_slugs),
        "## Entities",
        "",
        "| Entity | Kind | Classification | Relation to BOSC | Roles | Signals | Federal $ |",
        "|---|---|---|---|---|---|---|",
    ]
    for ent in sorted(graph.entities.values(), key=lambda e: (e.kind, e.key)):
        roles = ", ".join(f"{r} x{n}" for r, n in ent.roles.most_common())
        signals = ", ".join(sorted(ent.signals)) or "—"
        slug = profile_slugs.get(ent.key)
        name = f"[{_esc(ent.display)}](people/{slug}.md)" if slug else _esc(ent.display)
        if ent.lei:
            name += f" `LEI {ent.lei}`"
        if ent.uei:
            name += f" `UEI {ent.uei}`"
        fed = f"${ent.federal_obligations:,.0f}" if ent.federal_obligations is not None else "—"
        lines.append(
            f"| {name} | {_esc(ent.kind)} | {_esc(ent.classification)} "
            f"| {_relation_label(ent.relation_class)} | {_esc(roles)} | {_esc(signals)} | {fed} |"
        )
    lines += [
        "",
        "## Relationships",
        "",
        "| Source | Relationship | Target | When | Ref |",
        "|---|---|---|---|---|",
    ]
    for r in graph.relationships:
        src = graph.entities[r.src].display if r.src in graph.entities else r.src
        dst = graph.entities[r.dst].display if r.dst in graph.entities else r.dst
        rel = r.rel
        if r.relation_class:
            rel += f" · {_RELATION_CLASS_LABELS.get(r.relation_class, r.relation_class)}"
        lines.append(
            f"| {_esc(src)} | {_esc(rel)} | {_esc(dst)} | {_esc(r.date or '—')} "
            f"| {_esc(r.ref or '—')} |"
        )
    lines.append("")
    return "\n".join(lines)


def _relation_section(graph: EntityGraph, profile_slugs: dict[str, str]) -> list[str]:
    """The 'By relation to Project BOSC' grouped section + legend.

    Empty (returns ``[]``) when no entity is classified — so the pure corpus graph
    renders exactly as before. A trailing 'Not yet classified' group keeps the gap
    auditable (negative-evidence discipline).
    """
    classified = [e for e in graph.entities.values() if e.relation_class]
    if not classified:
        return []
    legend = ['!!! note "Relation classes"']
    for cls in RELATION_CLASS_ORDER:
        legend.append(f"    - **{_RELATION_CLASS_LABELS[cls]}** — {_RELATION_CLASS_DEFS[cls]}")
    out = ["## By relation to Project BOSC", "", *legend, ""]
    for cls in RELATION_CLASS_ORDER:
        members = sorted(
            (e for e in graph.entities.values() if e.relation_class == cls),
            key=lambda e: e.key,
        )
        if not members:
            continue
        out += [f"### {_RELATION_CLASS_LABELS[cls]}", ""]
        for ent in members:
            slug = profile_slugs.get(ent.key)
            name = (
                f"[{_esc(ent.display)}](people/{slug}.md)" if slug else f"**{_esc(ent.display)}**"
            )
            basis = f" — {_esc(ent.relation_basis)}" if ent.relation_basis else ""
            out.append(f"- {name}{basis}")
        out.append("")
    unclassified = sorted(
        (e for e in graph.entities.values() if not e.relation_class), key=lambda e: e.key
    )
    if unclassified:
        names = ", ".join(_esc(e.display) for e in unclassified)
        out += [
            "### Not yet classified",
            "",
            f"{len(unclassified)} parties carry no relation class yet "
            f"(the overlay is grown deliberately, not auto-assigned): {names}.",
            "",
        ]
    return out
