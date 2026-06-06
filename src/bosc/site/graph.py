"""Render the cross-document layer (timeline + entity graph) as site pages.

Reuses the structured returns of :func:`bosc.pipeline.timeline.build_timeline`
and :func:`bosc.pipeline.entities.build_entity_graph` — not the Rich console
tables — and emits markdown: a chronology table, an entity/relationship pair of
tables, and a Mermaid diagram of the graph so the shared-agent shell cluster is
visible at a glance.
"""

from __future__ import annotations

import re

from bosc.pipeline.entities import EntityGraph
from bosc.pipeline.timeline import TimelineEvent

# Evidence-discipline note reused verbatim from the dossier's framing.
_SIGNALS_NOTE = (
    '!!! note "Signals are evidence, not verdicts"\n'
    "    A shared registered agent or an out-of-state (`delaware`) formation is "
    "*common-control plumbing* read from public records — **not** a statement "
    "about beneficial ownership. Treat flagged signals as leads to verify, not "
    "conclusions."
)


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
    """A Mermaid ``graph LR`` of the entity graph, signal-flagged nodes styled."""
    ids: dict[str, str] = {}
    lines = ["```mermaid", "graph LR"]
    flagged: list[str] = []
    for key, ent in sorted(graph.entities.items()):
        nid = _node_id(key, ids)
        label = ent.display.replace('"', "'")
        lines.append(f'  {nid}["{label}"]')
        if ent.signals:
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
        _SIGNALS_NOTE,
        "",
        "## Graph",
        "",
        *_mermaid(graph),
        "",
        "## Entities",
        "",
        "| Entity | Kind | Classification | Roles | Signals |",
        "|---|---|---|---|---|",
    ]
    for ent in sorted(graph.entities.values(), key=lambda e: (e.kind, e.key)):
        roles = ", ".join(f"{r} x{n}" for r, n in ent.roles.most_common())
        signals = ", ".join(sorted(ent.signals)) or "—"
        slug = profile_slugs.get(ent.key)
        name = f"[{_esc(ent.display)}](people/{slug}.md)" if slug else _esc(ent.display)
        lines.append(
            f"| {name} | {_esc(ent.kind)} | {_esc(ent.classification)} "
            f"| {_esc(roles)} | {_esc(signals)} |"
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
        lines.append(
            f"| {_esc(src)} | {_esc(r.rel)} | {_esc(dst)} | {_esc(r.date or '—')} "
            f"| {_esc(r.ref or '—')} |"
        )
    lines.append("")
    return "\n".join(lines)
