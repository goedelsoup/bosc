"""Render the Allen County RSEI toxic-release inventory as a site page.

Publishes ``data/reference/rsei/inventory.yaml`` (built by ``bosc rsei`` from the
EPA RSEI Public Data Set) as a browsable, ranked page. The Score's comparative-only
caveat is rendered up front so the ranking is never misread as a risk estimate.
"""

from __future__ import annotations

from collections import defaultdict

from bosc.pipeline.entities import EntityGraph, normalize_name
from bosc.rsei import RseiInventory

_CAUTION = (
    '!!! warning "RSEI Score is comparative — not a risk estimate"\n'
    "    The **RSEI Score** is EPA's modeled, population-weighted, *unitless* "
    "screening number. It ranks/triages facilities; it is **not** a risk, a dose, or "
    "a concentration, and says nothing about any single person's exposure. **Pounds** "
    "are reported TRI releases; **Hazard** is pounds x toxicity weight (no population "
    "term). Every figure is summed from EPA RSEI rows — nothing is estimated by BOSC."
)
_MEDIA_LABELS = {
    "air": "Air",
    "water": "Direct water",
    "potw": "POTW transfer",
    "underground": "Underground injection",
    "land": "Land",
    "offsite": "Off-site",
}


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _num(x: float) -> str:
    return f"{x:,.0f}"


def _in_graph(egraph: EntityGraph | None, *names: str | None) -> bool:
    if egraph is None:
        return False
    return any(n and egraph.get(normalize_name(n)) is not None for n in names)


def render_rsei(inv: RseiInventory, *, egraph: EntityGraph | None = None) -> str:
    """Render the per-county RSEI inventory to a markdown page."""
    facs = inv.facilities
    scored = [f for f in facs if f.score > 0]
    with_npdes = [f for f in facs if f.npdes_permit]
    federal = [f for f in facs if f.federal_facility]

    lines = [
        f"# RSEI toxic-release inventory — {inv.county_name}",
        "",
        f"**{len(facs)}** TRI/RSEI facilities in {inv.county_name} (FIPS "
        f"{inv.county_fips}), ranked by EPA's **Risk-Screening Score**. {len(scored)} "
        "carry a modeled Score; the rest reported pounds of only non-modeled "
        "media/chemicals. Built from the EPA RSEI Public Data Set "
        f"(`{inv.meta.get('version', '')}`) — see the "
        "[reference README](data/reference/rsei/README.md). This inventory sits "
        "alongside the corpus [entity graph](entities.md), the "
        "[NPDES inventory](data/reference/echo/README.md), and the "
        "[defense contractors](defense-contractors.md) page.",
        "",
        _CAUTION,
        "",
    ]

    # Corridor highlight: the JSMC / GDLS defense footprint, if present.
    gdls = next((f for f in facs if "GENERAL DYNAMICS" in f.name.upper()), None)
    if gdls is not None:
        rank = facs.index(gdls) + 1
        top = gdls.top_chemicals[0].chemical if gdls.top_chemicals else "—"
        lines += [
            '!!! note "Corridor: the JSMC / General Dynamics defense footprint"',
            f"    **{_esc(gdls.name)}** (parent *{_esc(gdls.parent_name or '—')}*) is "
            f"Allen County's **#{rank}** RSEI Score (~{_num(gdls.score)}, "
            f"{100 * gdls.cancer_score / gdls.score:.0f}% cancer-driven, chiefly "
            f"{_esc(top.lower())}), reported {gdls.first_year}-{gdls.last_year}. This "
            "independently corroborates the GDLS-at-JSMC reading in the "
            "[defense-contractor scan](defense-contractors.md).",
            "",
        ]

    # Ranked facility table.
    lines += [
        "## Facilities by RSEI Score",
        "",
        "| # | Facility | Parent | RSEI Score | Cancer % | Pounds | Years | NPDES | Fed | In graph |",
        "|---|---|---|--:|--:|--:|---|---|:-:|:-:|",
    ]
    for i, f in enumerate(facs, 1):
        cpct = f"{100 * f.cancer_score / f.score:.0f}%" if f.score else "—"
        yrs = f"{f.first_year}-{f.last_year}" if f.first_year else "—"
        npdes = f"`{_esc(f.npdes_permit)}`" if f.npdes_permit else "—"
        fed = "✓" if f.federal_facility else ""
        ig = "✓" if _in_graph(egraph, f.name, f.parent_name) else "—"
        lines.append(
            f"| {i} | {_esc(f.name)} | {_esc(f.parent_name or '—')} | {_num(f.score)} "
            f"| {cpct} | {_num(f.pounds)} | {yrs} | {npdes} | {fed} | {ig} |"
        )
    lines.append("")

    # County totals by media — ties the 'water' bucket to the hydrology thread.
    media_tot: dict[str, float] = defaultdict(float)
    for f in facs:
        for bucket, lbs in f.pounds_by_media.items():
            media_tot[bucket] += lbs
    if media_tot:
        total = sum(media_tot.values())
        lines += [
            "## Reported pounds by medium (county total)",
            "",
            "| Medium | Pounds | Share |",
            "|---|--:|--:|",
        ]
        for bucket, lbs in sorted(media_tot.items(), key=lambda kv: -kv[1]):
            share = f"{100 * lbs / total:.1f}%" if total else "—"
            lines.append(f"| {_MEDIA_LABELS.get(bucket, bucket.title())} | {_num(lbs)} | {share} |")
        lines.append("")

    # Top chemicals across the county, by modeled Score.
    chem_score: dict[str, float] = defaultdict(float)
    chem_cat: dict[str, str | None] = {}
    for f in facs:
        for c in f.top_chemicals:
            chem_score[c.chemical] += c.score
            chem_cat.setdefault(c.chemical, c.toxicity_category)
    ranked_chems = sorted(chem_score.items(), key=lambda kv: -kv[1])[:10]
    if any(s > 0 for _, s in ranked_chems):
        lines += [
            "## Top chemicals by RSEI Score (county)",
            "",
            "| Chemical | Toxicity class | Score |",
            "|---|---|--:|",
        ]
        for name, sc in ranked_chems:
            if sc <= 0:
                continue
            lines.append(f"| {_esc(name)} | {_esc(chem_cat.get(name) or '—')} | {_num(sc)} |")
        lines.append("")

    lines += [
        "## Notes",
        "",
        f"- **{len(with_npdes)}** facilities carry an NPDES permit that joins to the "
        "[Maumee NPDES inventory](data/reference/echo/README.md).",
        f"- **{len(federal)}** federal facility(ies) by RSEI's `FederalFacilityFlag`.",
        "- Score reflects the modeling vintage of this RSEI version; values are "
        "comparable within it, not across versions.",
        "",
    ]
    return "\n".join(lines)
