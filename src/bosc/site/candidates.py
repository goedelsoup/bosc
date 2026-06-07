"""Render the curated candidate-entity inventory as a site page.

Publishes ``data/entities/cloud-consumer-candidates.yaml`` as a browsable page that
sits alongside the corpus entity graph. The demand-fit caution is rendered up front
so the table is never misread as a customer/connection list.
"""

from __future__ import annotations

from bosc.candidates import CandidateInventory, DefenseContractorList, DefenseLandScan
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


_DEF_CAUTION = (
    '!!! warning "Pattern matches — leads, not verdicts"\n'
    "    This is a seed list of major DoD prime contractors. A match means a party "
    "name *fits a known prime's pattern* — a lead to verify, **not** a "
    "classification and **not** an accusation. It does not change an entity's "
    "graph classification, and a hit on a dual-use firm (e.g. Honeywell) may be a "
    "purely commercial holding."
)


def _corpus_names(egraph: EntityGraph) -> list[str]:
    """Every legible party name in the graph (displays + raw variants)."""
    names: set[str] = set()
    for ent in egraph.entities.values():
        names.add(ent.display)
        names.update(ent.variants)
    return sorted(names)


def _parcel_field(row: dict[str, object], key: str) -> str:
    val = row.get(key)
    return _esc("—" if val is None else str(val))


def _render_parcel_scan(scan: DefenseLandScan) -> list[str]:
    """Render the committed Allen County defense-land scan (parcels.defense.yaml)."""
    meta = scan.meta
    lines = ["## Allen County parcels", ""]
    finding = meta.get("finding")
    if finding:
        lines += [_esc(str(finding)), ""]

    lines += [f"### Prime-owned parcels ({len(scan.prime_owned)})", ""]
    if scan.prime_owned:
        lines += ["| Prime | Parcel | Owner | Situs | Acres |", "|---|---|---|---|---|"]
        for r in scan.prime_owned:
            lines.append(
                f"| {_parcel_field(r, 'matched_prime')} | {_parcel_field(r, 'parcel_no')} "
                f"| {_parcel_field(r, 'owner')} | {_parcel_field(r, 'situs_address')} "
                f"| {_parcel_field(r, 'acres')} |"
            )
    else:
        lines.append("None — no parcel is owned by a prime in its own name.")
    lines.append("")

    if scan.army_controlled:
        note = meta.get("army_controlled_note")
        lines += [f"### Army-controlled defense land ({len(scan.army_controlled)})", ""]
        if note:
            lines += [f'!!! note "Identification is an inference"\n    {_esc(str(note))}', ""]
        lines += [
            "| Parcel | Owner | Situs | Acres | Mkt total | Tax dist |",
            "|---|---|---|---|---|---|",
        ]
        for r in scan.army_controlled:
            mkt = r.get("market_total_value")
            mkt_s = f"{mkt:,}" if isinstance(mkt, int) else "—"
            lines.append(
                f"| {_parcel_field(r, 'parcel_no')} | {_parcel_field(r, 'owner')} "
                f"| {_parcel_field(r, 'situs_address')} | {_parcel_field(r, 'acres')} "
                f"| {mkt_s} | {_parcel_field(r, 'tax_district')} |"
            )
        lines += [
            "",
            '!!! tip "Independent corroboration — EPA RSEI"',
            "    EPA's RSEI Public Data Set lists **US ARMY JSMC / GENERAL DYNAMICS LAND "
            "SYSTEMS** (NAICS 336992, military armored vehicles) as a TRI reporter at "
            "this footprint — Allen County's **#3** toxic-release Score. That is an "
            "independent federal dataset naming GDLS at the JSMC; see the "
            "[RSEI inventory](rsei.md).",
            "",
        ]
    return lines


def render_defense_contractors(
    dcl: DefenseContractorList,
    *,
    egraph: EntityGraph | None = None,
    scan: DefenseLandScan | None = None,
) -> str:
    """Render the defense-contractor seed list, corpus matches, and the parcel scan."""
    primes = dcl.defense_contractors
    matches = dcl.match(_corpus_names(egraph)) if egraph is not None else {}
    n_pat = sum(len(dc.patterns) for dc in primes)

    lines = [
        "# Defense contractors",
        "",
        f"A curated seed list of **{len(primes)}** major U.S. Department of Defense "
        f"prime contractors ({n_pat} owner-name match patterns), used to flag "
        "defense-industry holdings across the corpus and Allen County parcels. It "
        "sits alongside the corpus [entity graph](entities.md) and the "
        "[cloud-consumer candidates](candidates.md); this list is curated, not "
        "corpus-derived.",
        "",
        _DEF_CAUTION,
        "",
    ]

    if scan is not None:
        lines += _render_parcel_scan(scan)

    if egraph is not None:
        lines += ["## Corpus matches", ""]
        if matches:
            lines += [
                f"{sum(len(v) for v in matches.values())} corpus party name(s) match "
                "a prime pattern. Verify each against the cited records before relying "
                "on it.",
                "",
                "| Prime | Matched corpus name |",
                "|---|---|",
            ]
            for prime in sorted(matches):
                for hit in sorted(matches[prime]):
                    lines.append(f"| {_esc(prime)} | {_esc(hit)} |")
        else:
            lines.append("No corpus party name matches a prime pattern yet.")
        lines.append("")

    lines += [
        "## Seed list",
        "",
        "| Prime | Patterns | Note |",
        "|---|---|---|",
    ]
    for dc in sorted(primes, key=lambda d: d.name):
        pats = ", ".join(f"`{_esc(p)}`" for p in dc.patterns)
        lines.append(f"| {_esc(dc.name)} | {pats} | {_esc(dc.note or '—')} |")
    lines.append("")
    return "\n".join(lines)
