"""In-process tools exposed to the research agent via an SDK MCP server.

Each tool is a thin, deterministic adapter over the pipeline so the agent can
inspect real data instead of guessing. Tools return the standard MCP content
shape (``{"content": [{"type": "text", "text": ...}]}``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from claude_agent_sdk import create_sdk_mcp_server, tool

from bosc.config import get_settings
from bosc.models import Estimate, OPCSummary
from bosc.pipeline import analyze, ingest

SERVER_NAME = "bosc"


def _text(payload: str) -> dict[str, Any]:
    """Wrap a string in the MCP tool-result content shape."""
    return {"content": [{"type": "text", "text": payload}]}


def _resolve(filename: str | None, pattern: str = "*.yaml") -> Path | None:
    """Resolve an extraction within data/extracted (now a collection tree).

    A ``filename`` may be a path relative to ``extracted`` (``recorder/foo.yaml``)
    or a bare basename matched anywhere in the tree. With no filename, the first
    ``pattern`` match (recursive) is returned.
    """
    extracted = get_settings().extracted_dir
    if not extracted.exists():
        return None
    if filename:
        direct = extracted / filename
        if direct.is_file():
            return direct
        name = Path(filename).name
        matches = sorted(p for p in extracted.rglob(name) if p.is_file())
        return matches[0] if matches else None
    matches = sorted(extracted.rglob(pattern))
    return matches[0] if matches else None


@tool("list_documents", "List ingested source documents and their collections.", {})
async def list_documents(_args: dict[str, Any]) -> dict[str, Any]:
    docs = ingest.discover()
    if not docs:
        return _text("No source documents found under data/documents.")
    lines = [
        f"- {d.doc_id}  [{d.collection or 'root'}]  {d.path.name}  ({d.size_bytes / 1e6:.1f} MB)"
        for d in docs
    ]
    return _text("\n".join(lines))


@tool("list_extractions", "List available structured extraction files.", {})
async def list_extractions(_args: dict[str, Any]) -> dict[str, Any]:
    extracted = get_settings().extracted_dir
    files = sorted(extracted.rglob("*.yaml")) if extracted.exists() else []
    if not files:
        return _text("No extractions found under data/extracted.")
    # Show the collection-relative path so the agent sees provenance (recorder/...).
    return _text("\n".join(f"- {f.relative_to(extracted)}" for f in files))


@tool(
    "read_extraction",
    "Read the raw text of an extraction file under data/extracted by name or "
    "collection-relative path (e.g. 'recorder/202511180011830-amazon-deed.deed.yaml').",
    {"filename": str},
)
async def read_extraction(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(args["filename"])
    if path is None:
        return _text(f"Not found: {args['filename']}")
    return _text(path.read_text(encoding="utf-8"))


@tool(
    "reconcile_summary",
    "Run deterministic arithmetic reconciliation over a *.summary.opc.yaml file.",
    {"filename": str},
)
async def reconcile_summary(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(args["filename"])
    if path is None:
        return _text(f"Not found: {args['filename']}")
    summary = OPCSummary.from_yaml(path)
    findings = analyze.reconcile(summary)
    return _text("\n".join(str(f) for f in findings))


@tool(
    "program_overview",
    "Structured overview of the OPC program: per-estimate totals, section subtotals, "
    "and reconciliation status (reads the summary extraction).",
    {},
)
async def program_overview(_args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(None, "*.summary.opc.yaml")
    if path is None:
        return _text("No *.summary.opc.yaml extraction found under data/extracted.")
    summary = OPCSummary.from_yaml(path)
    findings = analyze.reconcile(summary)
    passed = sum(1 for f in findings if f.ok)
    lines = [
        f"Source: {path.name}",
        f"Program construction total: {summary.construction_total():,}",
        f"Program grand total: {summary.grand_total():,}",
        f"Reconciliation: {passed}/{len(findings)} checks pass.",
        "",
    ]
    for se in summary.sub_estimates:
        secs = {k: v for k, v in se.section_subtotals.model_dump().items() if v is not None}
        lines.append(f"## {se.name} (pdf_page {se.pdf_page})")
        lines.append(f"   construction_subtotal={se.construction_subtotal:,} total={se.total:,}")
        lines.append("   sections: " + ", ".join(f"{k}={v:,}" for k, v in secs.items()))
    return _text("\n".join(lines))


@tool(
    "timeline",
    "Cross-document chronology: dated events (deed recordings, NPDES public "
    "notices/comment deadlines, OPC estimates) from every extraction, in order.",
    {},
)
async def timeline(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.pipeline import timeline as timeline_stage

    events = timeline_stage.build_timeline()
    if not events:
        return _text("No dated events found under data/extracted.")
    lines = []
    for e in events:
        date = e.date or "(undated)"
        corrob = f" (+{len(e.also_sources)} corroborating)" if e.also_sources else ""
        lines.append(f"{date}  [{e.category}]  {e.title}  <{e.source}>{corrob}")
        if e.detail:
            lines.append(f"            {e.detail}")
    return _text("\n".join(lines))


@tool(
    "entities",
    "Cross-document entity graph: parties resolved across deeds/NPDES (with kind, "
    "classification, roles, parcels) and the relationships between them.",
    {},
)
async def entities(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.pipeline import entities as entities_stage

    graph = entities_stage.build_entity_graph(
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        enrich_subdivisions=True,
    )
    if not graph.entities:
        return _text("No entities found under data/extracted.")
    lines = ["ENTITIES:"]
    for ent in sorted(graph.entities.values(), key=lambda e: (e.kind, e.key)):
        roles = ", ".join(f"{r} x{n}" for r, n in ent.roles.most_common())
        sig = f" signals={sorted(ent.signals)}" if ent.signals else ""
        parcels = f" parcels={len(ent.parcels)}" if ent.parcels else ""
        lines.append(f"- {ent.display} [{ent.kind}/{ent.classification}] {roles}{parcels}{sig}")
    lines.append("\nRELATIONSHIPS:")
    for r in graph.relationships:
        src = graph.entities[r.src].display if r.src in graph.entities else r.src
        dst = graph.entities[r.dst].display if r.dst in graph.entities else r.dst
        when = f" ({r.date})" if r.date else ""
        ref = f" [{r.ref}]" if r.ref else ""
        lines.append(f"- {src} --{r.rel}--> {dst}{when}{ref}")
    return _text("\n".join(lines))


@tool(
    "hydrology_balance",
    "Tier-0 municipal water balance + low-flow assimilative screen: the WWTP "
    "discharges (cited design flows) routed to their receiving waters, each checked "
    "against the stream's cited 7Q10 low flow. Flags effluent-dominated streams.",
    {},
)
async def hydrology_balance(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.pipeline import hydrology as hydro_stage

    balance, _checks, findings = hydro_stage.run_baseline()
    lines = ["WATER BALANCE (cfs; source in brackets):"]
    for n in balance.nodes:
        v = n.return_flow or n.inflow
        flow = str(v) if v else "—"
        recv = f" -> {n.node.receiving_water}" if n.node.receiving_water else ""
        lines.append(f"- [{n.node.role}] {n.node.name}{recv}: {flow}")
    lines.append("\nLOW-FLOW ASSIMILATIVE SCREEN (7Q10 dilution):")
    lines.extend(str(f) for f in findings)
    if not findings:
        lines.append("(no WWTP discharge had a cited receiving-water 7Q10)")
    if balance.warnings:
        lines.append("\nCaveats:")
        lines.extend(f"! {w}" for w in balance.warnings)
    return _text("\n".join(lines))


@tool(
    "stormwater_runoff",
    "Tier-0 pre- vs post-development design-storm runoff for the data-center campus: "
    "SCS curve-number method with live NOAA Atlas-14 rainfall. Reports the peak-flow "
    "and runoff-volume increase from paving the footprint (the detention deficit).",
    {},
)
async def stormwater_runoff(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.pipeline import hydrology as hydro_stage

    runoff, findings = hydro_stage.run_storm()
    lines = [
        f"{runoff.name}: {runoff.area.value:,.0f} ac footprint [{runoff.area.source}]",
        f"Design storm: {runoff.storm.return_period_yr}-yr 24-hr, "
        f"{runoff.storm.depth.value:.2f} in [{runoff.storm.depth.source}]",
        f"  pre-development  CN {runoff.pre.curve_number:.0f}: "
        f"peak {runoff.pre.peak_cfs:,.0f} cfs, {runoff.pre.volume_acft:,.0f} ac-ft",
        f"  post-development CN {runoff.post.curve_number:.0f}: "
        f"peak {runoff.post.peak_cfs:,.0f} cfs, {runoff.post.volume_acft:,.0f} ac-ft",
        "",
    ]
    lines.extend(str(f) for f in findings)
    lines.append("\n(Tier-0 SCS; HSG + land cover are cited assumptions, rainfall is live NOAA.)")
    return _text("\n".join(lines))


@tool(
    "hydrology_scenario",
    "Baseline vs data-center-buildout scenario: the campus cooling consumptive draw "
    "(an assumption knob) compared against the cited Ottawa River 7Q10 low flow. Shows "
    "how a data center stresses an already low-flow river.",
    {},
)
async def hydrology_scenario(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.pipeline import hydrology as hydro_stage

    base, build, delta = hydro_stage.run_scenarios()
    lines = [
        f"baseline: consumptive draw {base.consumptive_loss.value:.2f} cfs",
        f"buildout: cooling {build.scenario.cooling_demand.value:g} MGD x "
        f"{build.scenario.consumptive_fraction.value:g} consumptive "
        f"-> {build.consumptive_loss.value:.2f} cfs net basin loss",
        f"net new consumptive draw: {delta.consumptive_increase_cfs:.2f} cfs",
    ]
    if delta.multiple_of_7q10 is not None:
        lines.append(
            f"= {delta.multiple_of_7q10:g}x the Ottawa River 7Q10 ({delta.ottawa_7q10_cfs:g} cfs, cited)"
        )
    if build.ottawa_live is not None:
        lines.append(f"Ottawa live flow: {build.ottawa_live.value:.0f} cfs")
    lines.append(
        "\n(Cooling knobs are assumptions; Ottawa 7Q10 is document-cited. Tier-0 screening.)"
    )
    return _text("\n".join(lines))


@tool(
    "storm_plan_inventory",
    "Document-grounded drainage facts from the campus grading & storm plan (sheet "
    "1A-C-3104, 95% SPS): storm-structure rim-elevation relief, the conveyance "
    "inventory, and whether any on-site detention/retention storage is shown. Grounds "
    "the Tier-1 detention result in the real civil design.",
    {},
)
async def storm_plan_inventory(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.hydrology import stormplan

    inv = stormplan.load_inventory()
    if inv is None:
        return _text("No storm-plan inventory yet (run `bosc storm-plan --refresh`).")
    lines = [
        f"{inv.sheet_id} {inv.discipline} ({inv.phase}, {inv.status})",
        f"graded relief {inv.rim_min.value:.1f}-{inv.rim_max.value:.1f} ft "
        f"over {inv.rim_labels} storm-structure rims",
        f"conveyance: {', '.join(inv.structure_types)}",
        f"features: {', '.join(inv.conveyance_features)}",
    ]
    lines += [str(f) for f in stormplan.storm_plan_findings(inv)]
    lines.append(
        "\n(Transcribed from the civil sheet; pipe connectivity/inverts are vector geometry "
        "with no schedule table, so a routable network is not fabricated.)"
    )
    return _text("\n".join(lines))


@tool(
    "sanitary_basis",
    "Document-cited sanitary design basis for the WWTPs: per-plant permitted average "
    "design flow and peak hydraulic capacity (so the wet-weather headroom = peak - avg), "
    "plus the I/I + SSO regulatory context (1996 federal consent decree; 2005 OEPA mandate "
    "to eliminate bypassing by 2015). Grounds the Tier-1 sanitary surcharge.",
    {},
)
async def sanitary_basis(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.hydrology.sanitary import load_sanitary_basis

    basis = load_sanitary_basis()
    if basis is None:
        return _text(
            "No sanitary basis table found (data/reference/hydrology/sanitary-basis.yaml)."
        )
    lines = []
    for p in basis.plants:
        peak = f"{p.peak_capacity.value:g} MGD peak" if p.peak_capacity else "peak uncited"
        pf = f", {p.peaking_factor.value:g}x" if p.peaking_factor else ""
        head = f", headroom {p.headroom_mgd:g} MGD" if p.headroom_mgd is not None else ""
        lines.append(
            f"{p.plant} ({p.npdes or 'NPDES n/a'} -> {p.receiving_water}): "
            f"{p.avg_design_flow.value:g} MGD avg / {peak}{pf}{head}"
        )
    lines.append(f"Campus FM-2 industrial: {basis.campus_industrial.value:g} MGD (document)")
    lines.append(f"I/I remediation: ${basis.ii_remediation_musd.value:g}M; {basis.decree_note}")
    return _text("\n".join(lines))


@tool(
    "tier1_swmm",
    "Tier-1 EPA SWMM run: detention-basin sizing (the storage that holds the "
    "post-development peak to the pre-development rate) and sanitary wet-weather "
    "surcharge (storm-driven peak vs documented WWTP peak capacities). Needs the "
    "SWMM engine; reports clearly if unavailable.",
    {},
)
async def tier1_swmm(_args: dict[str, Any]) -> dict[str, Any]:
    from bosc.hydrology.tier1 import run_tier1, tier1_findings

    result = run_tier1()
    if not result.available:
        return _text(result.note)
    lines = [str(f) for f in tier1_findings(result)]
    lines.append(
        "\n(Tier-1 EPA SWMM; footprint + plant capacities document-sourced, storm from NOAA; "
        "network/hydraulic params are assumptions.)"
    )
    return _text("\n".join(lines))


@tool(
    "reconcile_estimate",
    "Reconcile a generated estimate extraction (*.opc.yaml): line items -> section "
    "subtotals -> construction subtotal + markups -> total.",
    {"filename": str},
)
async def reconcile_estimate(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(args["filename"], "*.opc.yaml")
    if path is None:
        return _text(f"Not found: {args['filename']}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return _text(f"{path.name} is not valid YAML: {str(exc).splitlines()[0]}")
    if not isinstance(data, dict) or "estimate" not in data:
        return _text(f"{path.name} is not a generated estimate extraction (no 'estimate' block).")
    estimate = Estimate.model_validate(data["estimate"])
    findings = analyze.reconcile_estimate(estimate)
    if not findings:
        return _text(f"{path.name}: nothing to reconcile (no subtotals/total present).")
    return _text("\n".join(str(f) for f in findings))


# All tools, and the in-process MCP server that hosts them.
ALL_TOOLS = [
    list_documents,
    list_extractions,
    read_extraction,
    reconcile_summary,
    program_overview,
    reconcile_estimate,
    timeline,
    entities,
    hydrology_balance,
    stormwater_runoff,
    hydrology_scenario,
    storm_plan_inventory,
    sanitary_basis,
    tier1_swmm,
]
ALLOWED_TOOL_NAMES = [f"mcp__{SERVER_NAME}__{t.name}" for t in ALL_TOOLS]


def build_server() -> Any:
    """Create the in-process SDK MCP server hosting BOSC's tools."""
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)
