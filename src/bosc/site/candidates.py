"""Render the curated candidate-entity inventory as a site page.

Publishes ``data/entities/cloud-consumer-candidates.yaml`` as a browsable page that
sits alongside the corpus entity graph. The demand-fit caution is rendered up front
so the table is never misread as a customer/connection list.
"""

from __future__ import annotations

from bosc.candidates import CandidateInventory
from bosc.pipeline.entities import EntityGraph, normalize_name

_CAUTION = (
    '!!! warning "Demand-fit candidates — not customers or connections"\n'
    "    Each entity is listed for *what the business does* (it has a workload class "
    "hyperscale/edge infrastructure serves), from public descriptions. Nothing here "
    "asserts any entity uses, plans to use, or was approached about data-center "
    "capacity, or is connected to Project BOSC. `confirmed_cloud_relationship` notes a "
    "publicly documented cloud tie where one exists (usually corporate-level)."
)
_TIER_NAMES = {
    1: "Allen County industrial base",
    2: "Logistics & distribution (I-75 spine)",
    3: "Regulated-data / defense-adjacent",
    4: "Healthcare, institutional & research",
}


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_candidates(inv: CandidateInventory, *, egraph: EntityGraph | None = None) -> str:
    """Render the cloud-consumer candidate inventory to a markdown page."""
    ents = inv.entities
    n_conf = sum(1 for e in ents if e.confirmed_cloud_relationship)
    classes: dict[str, str] = inv.meta.get("workload_classes", {})

    lines = [
        "# Cloud-consumer candidates",
        "",
        f"{len(ents)} corridor operations marked **cloud-consumer candidates** on "
        f"demand-fit only — each has at least one workload class that hyperscale / edge "
        f"infrastructure exists to serve. {n_conf} carry a publicly documented cloud "
        "relationship. This inventory sits alongside the corpus "
        "[entity graph](entities.md); these entities are curated, not corpus-derived.",
        "",
        _CAUTION,
        "",
    ]
    if classes:
        lines += ["## Workload classes", ""]
        lines += [f"- **{k}** — {_esc(v)}" for k, v in classes.items()]
        lines.append("")

    for tier in sorted({e.tier for e in ents}):
        rows = [e for e in ents if e.tier == tier]
        lines += [f"## Tier {tier} — {_TIER_NAMES.get(tier, '')}".rstrip(" —"), ""]
        lines += [
            "| Entity | Sector | Location | Workload classes | Confirmed cloud | In graph |",
            "|---|---|---|---|---|---|",
        ]
        for e in sorted(rows, key=lambda e: e.name):
            in_graph = "✓" if egraph is not None and egraph.get(normalize_name(e.name)) else "—"
            conf = _esc(e.confirmed_cloud_relationship or "—")
            spec = " *(speculative)*" if e.speculative else ""
            lines.append(
                f"| {_esc(e.name)}{spec} | {_esc(e.sector or '—')} | {_esc(e.location or '—')} "
                f"| {_esc(', '.join(e.workload_classes))} | {conf} | {in_graph} |"
            )
        lines.append("")
    return "\n".join(lines)
