"""In-process tools exposed to the research agent via an SDK MCP server.

Each tool is a thin, deterministic adapter over the pipeline so the agent can
inspect real data instead of guessing. Tools return the standard MCP content
shape (``{"content": [{"type": "text", "text": ...}]}``).
"""

from __future__ import annotations

import asyncio
import ipaddress
import urllib.parse as _urlparse
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import yaml
from claude_agent_sdk import create_sdk_mcp_server, tool

from watermark.agent.tracing import traced_tool
from watermark.config import get_settings
from watermark.github import (
    AdminChecker,
    GitHubAppClient,
)
from watermark.github import (
    add_label as _gh_add_label,
)
from watermark.github import (
    comment_on_pr as _gh_comment_on_pr,
)
from watermark.github import (
    remove_label as _gh_remove_label,
)
from watermark.github import (
    set_issue_state as _gh_set_issue_state,
)
from watermark.models import Estimate, OPCSummary
from watermark.pipeline import analyze, ingest

if TYPE_CHECKING:
    from watermark.sites import CorpusScope

SERVER_NAME = "watermark"


def _text(payload: str) -> dict[str, Any]:
    """Wrap a string in the MCP tool-result content shape."""
    return {"content": [{"type": "text", "text": payload}]}


# Read-side per-site resolution (#424). The extraction-reading tools resolve against the ACTIVE
# site's own committed corpus: the whole data/extracted/ tree for the corpus home (Lima), else the
# site's own subtree (data/extracted/<slug>/) — so a per-site run reads its own record, never
# another site's. `entities` and `timeline` resolve per active site via load_corpus(settings).
# `list_documents` filters data/documents/ by site slug (#899). `hydrology_balance` runs
# per-site for any site with a committed watch-items.geojson (else the reference-only notice,
# #829). The rest of the hydrology suite (stormwater_runoff, hydrology_scenario, tier1_swmm,
# storm_plan_inventory, sanitary_basis) remains Lima-specific off-home (#900/#901).
_CORPUS_HOME = "lima"


def _is_corpus_home(settings: Any) -> bool:
    return bool(settings.site == _CORPUS_HOME)


def _site_extracted_scope(settings: Any) -> CorpusScope:
    """The active site's corpus scope (#1504): the extracted-tree region it owns — the *same*
    scope `load_corpus` / retrieval read (via `effective_corpus_scope`).

    Lima (the corpus home) is the whole tree minus every peer's subtree (#1505); a peer reads only
    the prefixes its profile names (its own ``<slug>/`` plus any jurisdiction prefix like
    ``idem/fort-wayne``).
    """
    from watermark.sites import active_profile, effective_corpus_scope

    return effective_corpus_scope(active_profile(settings))


def _site_extracted_files(settings: Any, pattern: str = "*.yaml") -> list[Path]:
    """Every extracted file matching *pattern* in the active site's corpus scope, sorted (#1504).

    Membership uses the same `relpath_in_scope` predicate as the export path, so the read tools
    (`list_extractions` / `read_extraction` / `reconcile_*` / `program_overview`) see exactly the
    corpus the bundle and retrieval do — including collection-prefixed records (`idem/fort-wayne`,
    `oepa/urbana`), not just the bare ``<slug>/`` subdir.
    """
    from watermark.pipeline.corpus import relpath_in_scope

    extracted: Path = settings.extracted_dir
    if not extracted.exists():
        return []
    scope = _site_extracted_scope(settings)
    return [
        p
        for p in sorted(extracted.rglob(pattern))
        if p.is_file() and relpath_in_scope(p.relative_to(extracted).as_posix(), scope)
    ]


def _site_scope_note(settings: Any) -> str:
    """A scope banner naming whose corpus a payload is (empty for the corpus home → zero drift)."""
    if _is_corpus_home(settings):
        return ""
    prefixes = _site_extracted_scope(settings).include or (str(settings.site),)
    where = ", ".join(f"data/extracted/{p}/" for p in prefixes)
    return f"[scope] Reading site {settings.site!r}'s own committed corpus ({where}).\n\n"


def _scoped(payload: str) -> dict[str, Any]:
    """Wrap a data payload with the active-site scope note (empty for the corpus home, Lima)."""
    return _text(_site_scope_note(get_settings()) + payload)


def _reference_only(tool: str) -> dict[str, Any] | None:
    """Guard for the Lima-reference tools (entities/timeline/hydrology): off the corpus home they
    have no per-site equivalent yet, so return an honest notice instead of silently serving Lima's
    record (#424). Returns ``None`` on the corpus home (the caller proceeds normally)."""
    settings = get_settings()
    if _is_corpus_home(settings):
        return None
    return _text(
        f"[scope] No committed {tool} for site {settings.site!r} yet. This tool serves the "
        f"{_CORPUS_HOME!r} reference build, which is not substituted for another site (#424); "
        f"onboard {settings.site}'s corpus/scenario to populate it."
    )


def _load_all_permits(
    settings: Any,
) -> list[tuple[str, Any]]:
    """Return ``(relpath, NpdesExtraction)`` pairs for every *.npdes.yaml in the corpus.

    Used to annotate ``discharges_to`` edges with ``stream_network`` so the agent can
    verify basin attribution without a separate ``read_extraction`` call per permit.
    """
    from watermark.models import NpdesExtraction

    results = []
    for path in sorted(settings.extracted_dir.rglob("*.npdes.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            ex = NpdesExtraction.model_validate(data)
            rel = path.relative_to(settings.extracted_dir).as_posix()
            results.append((rel, ex))
        except Exception:
            pass
    return results


def _resolve(filename: str | None, pattern: str = "*.yaml") -> Path | None:
    """Resolve an extraction within the ACTIVE SITE's corpus scope (#424/#1504).

    Candidates are the extracted files in the active site's `effective_corpus_scope` (the whole
    tree for the corpus home, else the site's scoped prefixes). A ``filename`` may be a path
    relative to ``data/extracted`` (``idem/fort-wayne/foo.yaml``, as `list_extractions` prints it)
    or a bare basename matched anywhere in scope; with no filename, the first ``pattern`` match is
    returned.
    """
    settings = get_settings()
    files = _site_extracted_files(settings, pattern)
    if not files:
        return None
    if filename:
        extracted: Path = settings.extracted_dir
        rel_want = filename.replace("\\", "/")
        for f in files:
            if f.relative_to(extracted).as_posix() == rel_want:
                return f
        name = Path(filename).name
        for f in files:
            if f.name == name:
                return f
        return None
    return files[0]


@tool("list_documents", "List ingested source documents and their collections.", {})
@traced_tool
async def list_documents(_args: dict[str, Any]) -> dict[str, Any]:
    # Per-site scoping (#899): for the corpus home, return all docs; for other sites, filter
    # to documents whose path contains the site slug (e.g. data/documents/idem/fort-wayne/).
    settings = get_settings()
    site_filter = None if _is_corpus_home(settings) else str(settings.site)
    docs = ingest.discover(settings, site=site_filter)
    if not docs:
        if site_filter:
            return _text(
                f"No source documents found for site {settings.site!r} yet. "
                f"Commit documents under data/documents/<collection>/{settings.site}/ to populate."
            )
        return _text("No source documents found under data/documents.")
    lines = [
        f"- {d.doc_id}  [{d.collection or 'root'}]  {d.path.name}  ({d.size_bytes / 1e6:.1f} MB)"
        for d in docs
    ]
    return _scoped("\n".join(lines))


@tool("list_extractions", "List available structured extraction files.", {})
@traced_tool
async def list_extractions(_args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    files = _site_extracted_files(settings)
    if not files:
        if _is_corpus_home(settings):
            loc = "data/extracted"
        else:
            prefixes = _site_extracted_scope(settings).include or (str(settings.site),)
            loc = ", ".join(f"data/extracted/{p}" for p in prefixes)
        return _text(f"No extractions found under {loc}.")
    # Show the path relative to data/extracted so the agent sees full provenance
    # (recorder/…, idem/fort-wayne/…) — the same key read_extraction accepts.
    extracted = settings.extracted_dir
    return _scoped("\n".join(f"- {f.relative_to(extracted).as_posix()}" for f in files))


@tool(
    "read_extraction",
    "Read the raw text of an extraction file under data/extracted by name or "
    "collection-relative path (e.g. 'recorder/202511180011830-amazon-deed.deed.yaml').",
    {"filename": str},
)
@traced_tool
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
@traced_tool
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
@traced_tool
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
    return _scoped("\n".join(lines))


@tool(
    "timeline",
    "Cross-document chronology: dated events (deed recordings, NPDES public "
    "notices/comment deadlines, OPC estimates) from every extraction, in order.",
    {},
)
@traced_tool
async def timeline(_args: dict[str, Any]) -> dict[str, Any]:
    # build_timeline() delegates to load_corpus(), which is per-site scoped (#762/#780).
    # A non-Lima site gets its own corpus events (or "No dated events" if none yet) —
    # not Lima's Allen-County record. No _reference_only guard needed here (#424).
    # We pre-load the corpus from the active settings so the per-site scope is honoured
    # even when get_settings() is monkeypatched in tests.
    from watermark.pipeline import timeline as timeline_stage
    from watermark.pipeline.corpus import load_corpus
    from watermark.sites import active_profile, effective_corpus_scope

    settings = get_settings()
    corpus = load_corpus(settings)
    scope = effective_corpus_scope(active_profile(settings))
    events = timeline_stage.build_timeline(corpus=corpus, scope=scope)
    if not events:
        return _text("No dated events found under data/extracted.")
    lines = []
    for e in events:
        date = e.date or "(undated)"
        corrob = f" (+{len(e.also_sources)} corroborating)" if e.also_sources else ""
        lines.append(f"{date}  [{e.category}]  {e.title}  <{e.source}>{corrob}")
        if e.detail:
            lines.append(f"            {e.detail}")
    return _scoped("\n".join(lines))


@tool(
    "entities",
    "Cross-document entity graph: parties resolved across deeds/NPDES (with kind, "
    "classification, roles, parcels) and the relationships between them.",
    {},
)
@traced_tool
async def entities(_args: dict[str, Any]) -> dict[str, Any]:
    # build_entity_graph() delegates to load_corpus(), which is per-site scoped (#762/#780).
    # A non-Lima site gets its own corpus entities only — not Lima's cross-site reference
    # graph. No _reference_only guard needed here (#424).
    from watermark.pipeline import entities as entities_stage

    settings = get_settings()
    # Pre-load the corpus from the active settings so the per-site scope is honoured
    # even when get_settings() is monkeypatched in tests.
    from watermark.pipeline.corpus import load_corpus

    corpus = load_corpus(settings)
    graph = entities_stage.build_entity_graph(
        corpus=corpus,
        enrich_parcels=True,
        enrich_lei=True,
        enrich_rsei=True,
        enrich_federal=True,
        enrich_subdivisions=True,
        settings=settings,
    )
    if not graph.entities:
        return _scoped("No entities found under data/extracted.")

    # Pre-load stream_network from every NPDES extraction so discharges_to edges can
    # be annotated with the basin chain. This prevents the agent from attributing a
    # permit from a different basin (e.g. Great Miami) to the active site's receiving
    # waters (e.g. Little Miami / Lytle Creek). LAMP permits have receiving_water=null
    # and will not have a discharges_to edge at all — they are excluded by construction.
    _stream_network_by_source: dict[str, str] = {}
    try:
        for rel_path, pex in _load_all_permits(settings):
            sn = pex.permit.stream_network
            if sn:
                _stream_network_by_source[rel_path] = sn
    except Exception:
        pass  # annotation is best-effort; never block the main output

    # The Lima reference graph is whole-corpus (all sites' permits); for any other site
    # load_corpus() scopes to that site's own extractions so the cross-basin attribution
    # issue cannot arise from the data layer. Tailor the scope note accordingly.
    if _is_corpus_home(settings):
        lines = [
            "SCOPE NOTE: This is the Lima reference entity graph — it includes NPDES permits",
            "from ALL sites in the corpus (not just the active site). Before attributing a",
            "discharges_to edge to the active site's basin, verify the permit source_path",
            "matches this site and that the stream_network annotation is consistent with",
            "the active basin. LAMP/non-discharge permits (receiving_water=null) are excluded",
            "from discharges_to edges by construction and must not appear in load screens.",
            "",
            "ENTITIES:",
        ]
    else:
        lines = [
            f"SCOPE NOTE: Per-site entity graph for {settings.site!r} — "
            "only this site's committed corpus extractions are included.",
            "",
            "ENTITIES:",
        ]
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
        basin = (
            f" [stream_network: {_stream_network_by_source[r.source]}]"
            if r.rel == "discharges_to" and r.source in _stream_network_by_source
            else ""
        )
        lines.append(f"- {src} --{r.rel}--> {dst}{when}{ref}{basin}")
    return _scoped("\n".join(lines))


@tool(
    "hydrology_balance",
    "Tier-0 municipal water balance + low-flow assimilative screen: the WWTP "
    "discharges (cited design flows) routed to their receiving waters, each checked "
    "against the stream's cited 7Q10 low flow. Flags effluent-dominated streams.",
    {},
)
@traced_tool
async def hydrology_balance(_args: dict[str, Any]) -> dict[str, Any]:
    from watermark.hydrology.balance import has_site_watch_items
    from watermark.pipeline import hydrology as hydro_stage

    settings = get_settings()
    # Per-site (#829): the balance runs for the corpus home (Lima) and for any site that
    # has committed its own WWTP graph (data/reference/<slug>/watch-items.geojson). Off the
    # corpus home with no such graph it would silently fall back to Lima's periplus
    # watch-items, so keep the honest reference-only notice instead.
    if not _is_corpus_home(settings) and not has_site_watch_items(settings):
        note = _reference_only("hydrology_balance")
        if note is not None:
            return note

    balance, _checks, findings = hydro_stage.run_baseline(settings=settings)
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
    return _scoped("\n".join(lines))


@tool(
    "stormwater_runoff",
    "Tier-0 pre- vs post-development design-storm runoff for the data-center campus: "
    "SCS curve-number method with live NOAA Atlas-14 rainfall. Reports the peak-flow "
    "and runoff-volume increase from paving the footprint (the detention deficit).",
    {},
)
@traced_tool
async def stormwater_runoff(_args: dict[str, Any]) -> dict[str, Any]:
    if (note := _reference_only("stormwater_runoff")) is not None:
        return note
    from watermark.pipeline import hydrology as hydro_stage

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
    return _scoped("\n".join(lines))


@tool(
    "hydrology_scenario",
    "Baseline vs data-center-buildout scenario: the campus cooling consumptive draw "
    "(an assumption knob) compared against the cited Ottawa River 7Q10 low flow. Shows "
    "how a data center stresses an already low-flow river.",
    {},
)
@traced_tool
async def hydrology_scenario(_args: dict[str, Any]) -> dict[str, Any]:
    if (note := _reference_only("hydrology_scenario")) is not None:
        return note
    from watermark.pipeline import hydrology as hydro_stage

    base, build, delta = hydro_stage.run_scenarios()
    lines = [
        f"baseline: consumptive draw {base.consumptive_loss.value:.2f} cfs",
        f"buildout: cooling {build.scenario.cooling_demand.value:g} MGD x "
        f"{build.scenario.consumptive_fraction.value:g} consumptive "
        f"-> {build.consumptive_loss.value:.2f} cfs net basin loss",
        f"net new consumptive draw: {delta.consumptive_increase_cfs:.2f} cfs",
    ]
    rw = delta.receiving_water_name or "receiving water"
    if delta.multiple_of_7q10 is not None:
        lines.append(
            f"= {delta.multiple_of_7q10:g}x the {rw} 7Q10 ({delta.receiving_7q10_cfs:g} cfs, cited)"
        )
    if build.receiving_live is not None:
        lines.append(f"{rw} live flow: {build.receiving_live.value:.0f} cfs")
    lines.append(
        f"\n(Cooling knobs are assumptions; {rw} 7Q10 is document-cited. Tier-0 screening.)"
    )
    return _scoped("\n".join(lines))


@tool(
    "storm_plan_inventory",
    "Document-grounded drainage facts from the campus grading & storm plan (sheet "
    "1A-C-3104, 95% SPS): storm-structure rim-elevation relief, the conveyance "
    "inventory, and whether any on-site detention/retention storage is shown. Grounds "
    "the Tier-1 detention result in the real civil design.",
    {},
)
@traced_tool
async def storm_plan_inventory(_args: dict[str, Any]) -> dict[str, Any]:
    from watermark.hydrology import stormplan

    inv = stormplan.load_inventory(settings=get_settings())
    if inv is None:
        return _text("No storm-plan inventory yet (run `watermark storm-plan --refresh`).")
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
    return _scoped("\n".join(lines))


@tool(
    "sanitary_basis",
    "Document-cited sanitary design basis for the WWTPs: per-plant permitted average "
    "design flow and peak hydraulic capacity (so the wet-weather headroom = peak - avg), "
    "plus the I/I + SSO regulatory context (1996 federal consent decree; 2005 OEPA mandate "
    "to eliminate bypassing by 2015). Grounds the Tier-1 sanitary surcharge.",
    {},
)
@traced_tool
async def sanitary_basis(_args: dict[str, Any]) -> dict[str, Any]:
    from watermark.hydrology.sanitary import load_sanitary_basis

    settings = get_settings()
    basis = load_sanitary_basis(settings=settings)
    if basis is None:
        return _text(
            f"No sanitary basis table found for site {settings.site!r} "
            f"(data/reference/hydrology/{settings.site}/sanitary-basis.yaml)."
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
    return _scoped("\n".join(lines))


@tool(
    "tier1_swmm",
    "Tier-1 EPA SWMM run: detention-basin sizing (the storage that holds the "
    "post-development peak to the pre-development rate) and sanitary wet-weather "
    "surcharge (storm-driven peak vs documented WWTP peak capacities). Needs the "
    "SWMM engine; reports clearly if unavailable.",
    {},
)
@traced_tool
async def tier1_swmm(_args: dict[str, Any]) -> dict[str, Any]:
    if (note := _reference_only("tier1_swmm")) is not None:
        return note
    from watermark.hydrology.tier1 import run_tier1, tier1_findings

    result = run_tier1()
    if not result.available:
        return _text(result.note)
    lines = [str(f) for f in tier1_findings(result)]
    lines.append(
        "\n(Tier-1 EPA SWMM; footprint + plant capacities document-sourced, storm from NOAA; "
        "network/hydraulic params are assumptions.)"
    )
    return _scoped("\n".join(lines))


@tool(
    "retrieve_corpus",
    "Semantic search over the indexed source corpus (documents, reference data, extracted "
    "artifacts). Returns ranked chunks with text and provenance citations. Use to find "
    "relevant precedents from reference sites, or to discover source context that has not "
    "yet been extracted. Requires the index to be built first (watermark index).",
    {
        "query": str,
        "site": str,
        "collection": str,
        "doc_kind": str,
        "limit": int,
    },
)
@traced_tool
async def retrieve_corpus(args: dict[str, Any]) -> dict[str, Any]:
    from watermark.retrieval.embeddings import get_provider
    from watermark.retrieval.store import CorpusStore

    settings = get_settings()
    store = CorpusStore(settings.lancedb_dir, get_provider(settings))

    if not store.exists:
        return _text(
            "[retrieval] Index not built. Run `watermark index` to build the corpus store "
            "before using retrieve_corpus."
        )

    query: str = args.get("query", "")
    if not query:
        return _text("[retrieval] query is required.")

    results = store.query(
        query,
        site=args.get("site") or None,
        collection=args.get("collection") or None,
        doc_kind=args.get("doc_kind") or None,
        limit=int(args.get("limit", 10)),
    )

    if not results:
        return _text("[retrieval] No results found for that query / filter combination.")

    lines = [f"[retrieval] {len(results)} result(s) for: {query!r}\n"]
    for i, r in enumerate(results, start=1):
        page_note = f" p.{r.page + 1}" if r.page >= 0 else ""
        site_note = f" [{r.site}]" if r.site else ""
        lines.append(
            f"--- {i}. {r.doc_kind}/{r.collection}/{r.source_path}{page_note}{site_note} "
            f"(score {r.score:.3f}) ---"
        )
        lines.append(r.text[:600])
        lines.append("")
    return _text("\n".join(lines))


@tool(
    "discover_oepa_permits",
    "Search the Ohio EPA DAM and ECHO for NPDES permit PDFs for the active site. "
    "Returns each result annotated 'new' (not yet downloaded), 'committed' (already on disk), "
    "or 'known' (in the site profile). Use before fetch_oepa_permit to identify what to pull.",
    {"extra_terms": str},
)
@traced_tool
async def discover_oepa_permits(args: dict[str, Any]) -> dict[str, Any]:
    from pathlib import Path as _Path

    from watermark.oepa.discovery import discover_dam_documents
    from watermark.sites import SITES

    settings = get_settings()
    slug = str(settings.site)

    if slug not in SITES:
        return _text(f"[discover_oepa_permits] Unknown site {slug!r}.")

    prof = SITES[slug]
    county = prof.county_name.split(",")[0].strip()
    extra = [args["extra_terms"]] if args.get("extra_terms") else None

    docs = discover_dam_documents(
        prof.place, county, basin=prof.basin, extra_terms=extra, settings=settings
    )

    known_ids = set(prof.npdes_permits)
    doc_dir = settings.documents_dir / "oepa" / slug
    committed_files = {p.name for p in doc_dir.glob("*.pdf")} if doc_dir.exists() else set()

    results = []
    for d in docs:
        committed = _Path(d.url).name in committed_files
        status = "committed" if committed else ("known" if d.permit_id in known_ids else "new")
        results.append({**d.model_dump(), "status": status})

    if not results:
        return _text(f"[discover_oepa_permits] No DAM documents found for {slug!r}.")

    lines = [f"[discover_oepa_permits] {len(results)} result(s) for {slug!r}:\n"]
    for r in results:
        lines.append(f"- {r['permit_id']:<15s}  {r['doc_type']:<20s}  [{r['status']}]  {r['url']}")
    new_count = sum(1 for r in results if r["status"] == "new")
    lines.append(
        f"\n{new_count} new · "
        f"{sum(1 for r in results if r['status'] == 'known')} known · "
        f"{sum(1 for r in results if r['status'] == 'committed')} committed"
    )
    return _text("\n".join(lines))


@tool(
    "fetch_oepa_permit",
    "Download an OEPA/DAM permit PDF by its DAM permit ID (e.g. '1PD00008') for the "
    "active site. Saves to data/documents/oepa/<site>/ and updates filename-map.yaml. "
    "After fetching, run `watermark ingest` and `watermark extract` to process the file.",
    {"permit_id": str},
)
@traced_tool
async def fetch_oepa_permit(args: dict[str, Any]) -> dict[str, Any]:
    from watermark.oepa.fetch import dam_url, fetch_one, update_filename_map

    settings = get_settings()
    slug = str(settings.site)
    permit_id: str = args.get("permit_id", "").strip()

    if not permit_id:
        return _text("[fetch_oepa_permit] permit_id is required (e.g. '1PD00008').")

    url = dam_url(permit_id)
    dest = settings.documents_dir / "oepa" / slug
    dest.mkdir(parents=True, exist_ok=True)
    map_path = dest / "filename-map.yaml"

    result = fetch_one(url, dest, permit_id=permit_id, settings=settings)
    update_filename_map([result], map_path)

    if result.status == "downloaded":
        return _text(
            f"[fetch_oepa_permit] Downloaded {result.filename} ({result.bytes:,} bytes) "
            f"→ data/documents/oepa/{slug}/{result.filename}\n"
            f"SHA256: {result.sha256}\n"
            f"Next: `watermark ingest` then "
            f"`watermark --site {slug} extract <doc_id> --kind npdes --write`."
        )
    if result.status == "skipped_existing":
        return _text(f"[fetch_oepa_permit] {result.filename} already on disk — not re-downloaded.")
    return _text(f"[fetch_oepa_permit] {result.status}: {result.filename or permit_id}")


_GH_REPO = "watermark-directory/the-watermark-directory"


@tool(
    "list_site_issues",
    "List GitHub issues for the active site (all states: open + closed). "
    "Call this before proposing new issues to avoid duplicating tracked findings.",
    {
        "state": {
            "type": "string",
            "enum": ["open", "closed", "all"],
            "description": "Issue state filter (default: 'all').",
        }
    },
)
@traced_tool
async def list_site_issues(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    state: str = args.get("state", "all")
    if state not in ("open", "closed", "all"):
        state = "all"

    if not settings.github_token:
        return _text(
            "[list_site_issues] No GITHUB_TOKEN configured — cannot read the issue backlog. "
            "Set GITHUB_TOKEN to enable backlog deduplication."
        )

    site_label = f"site:{settings.site}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    issues: list[dict[str, Any]] = []
    url: str | None = (
        f"{settings.github_base_url}/repos/{_GH_REPO}/issues"
        f"?labels={site_label}&state={state}&per_page=100"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    return _text(
                        f"[list_site_issues] GitHub API returned {resp.status_code}: "
                        f"{resp.text[:200]}"
                    )
                page = resp.json()
                for item in page:
                    issues.append(
                        {
                            "number": item["number"],
                            "title": item["title"],
                            "state": item["state"],
                            "url": item["html_url"],
                            "labels": [lb["name"] for lb in item.get("labels", [])],
                        }
                    )
                # Follow Link rel="next" pagination
                link_header = resp.headers.get("link", "")
                url = None
                for part in link_header.split(","):
                    part = part.strip()
                    if 'rel="next"' in part:
                        url = part.split(";")[0].strip().lstrip("<").rstrip(">")
                        break
    except Exception as exc:
        return _text(f"[list_site_issues] Request failed: {exc}")

    if not issues:
        return _text(
            f"[list_site_issues] No issues found for site:{settings.site} (state={state})."
        )

    lines = [
        f"[list_site_issues] {len(issues)} issue(s) for site:{settings.site} (state={state}):\n"
    ]
    for iss in issues:
        label_str = ", ".join(iss["labels"])
        lines.append(
            f"- #{iss['number']} [{iss['state']}] {iss['title']}\n"
            f"  {iss['url']}\n"
            f"  labels: {label_str}"
        )
    return _text("\n".join(lines))


@tool(
    "report_novel_finding",
    "File a GitHub issue for context found in the source corpus that has no corresponding "
    "extraction. Use when retrieve_corpus surfaces something significant that is not yet in "
    "data/extracted/. Files the issue and returns immediately — do not pursue the finding "
    "inline.",
    {
        "title": str,
        "description": str,
        "source_citation": str,
        "site": str,
        "collection": str,
    },
)
@traced_tool
async def report_novel_finding(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    title: str = args.get("title", "").strip()
    description: str = args.get("description", "").strip()
    source_citation: str = args.get("source_citation", "").strip()
    finding_site: str = args.get("site", "").strip()
    collection: str = args.get("collection", "").strip()

    if not title or not description:
        return _text("[report_novel_finding] title and description are required.")

    labels = ["type:gap", "area:evidence", "status:agent-proposed"]
    if finding_site:
        labels.append(f"site:{finding_site}")

    body_parts = [description]
    if source_citation:
        body_parts.append(f"\n**Source citation:** {source_citation}")
    if collection:
        body_parts.append(f"**Collection:** {collection}")
    body_parts.append(
        "\n_Filed automatically by the research agent (status:agent-proposed). "
        "Requires triage before any extraction work is scheduled._"
    )
    body = "\n".join(body_parts)

    gh_client = GitHubAppClient(settings)
    if not GitHubAppClient.is_configured(settings) and not settings.github_token:
        summary = (
            f"[report_novel_finding] No GitHub credentials — issue not filed.\n"
            f"Title: {title}\n"
            f"Labels: {', '.join(labels)}\n"
            f"Body:\n{body}"
        )
        return _text(summary)

    payload = {"title": title, "body": body, "labels": labels}

    try:
        headers = await gh_client.get_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.github_base_url}/repos/{_GH_REPO}/issues",
                json=payload,
                headers=headers,
            )
        if resp.status_code == 201:
            data = resp.json()
            return _text(f"[report_novel_finding] Filed as #{data['number']}: {data['html_url']}")
        return _text(
            f"[report_novel_finding] GitHub API returned {resp.status_code}: {resp.text[:200]}"
        )
    except Exception as exc:
        return _text(f"[report_novel_finding] Request failed: {exc}")


@tool(
    "reconcile_estimate",
    "Reconcile a generated estimate extraction (*.opc.yaml): line items -> section "
    "subtotals -> construction subtotal + markups -> total.",
    {"filename": str},
)
@traced_tool
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


_FETCH_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _ssrf_check(url: str) -> str | None:
    """Return an error string if the URL targets a private/loopback/reserved host."""
    try:
        parsed = _urlparse.urlparse(url)
    except Exception:
        return "Invalid URL."
    if parsed.scheme not in _FETCH_ALLOWED_SCHEMES:
        return f"Scheme {parsed.scheme!r} is not allowed; use http or https."
    host = (parsed.hostname or "").rstrip(".")
    if not host:
        return "URL has no hostname."
    if host.lower() == "localhost":
        return "Host 'localhost' is blocked."
    try:
        addr = ipaddress.ip_address(host)
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            return f"IP {host!r} is in a restricted range."
    except ValueError:
        pass  # hostname — can't validate without DNS resolution
    return None


@tool(
    "search_web",
    "Search the web via Google (Serper) and return ranked snippets + URLs. "
    "Use for data-center activity, permit searches, SOS filings, and local news. "
    "Requires WATERMARK_SERPER_API_KEY; returns empty if the key is absent and no "
    "cached result exists.",
    {"query": str, "n": int},
)
@traced_tool
async def search_web(args: dict[str, Any]) -> dict[str, Any]:
    from watermark.research.connectors.serper import search_web as _search_web

    settings = get_settings()
    query: str = args.get("query", "").strip()
    if not query:
        return _text("[search_web] query is required.")
    try:
        n = int(args.get("n", 10))
    except (TypeError, ValueError):
        n = 10
    results = await asyncio.to_thread(_search_web, query, n=n, settings=settings)
    if not results:
        return _text(
            f"[search_web] No results for {query!r}. "
            "Check WATERMARK_SERPER_API_KEY or try a broader query."
        )
    lines = [f"[search_web] {len(results)} result(s) for: {query!r}\n"]
    for i, r in enumerate(results, start=1):
        date_note = f" ({r.date})" if r.date else ""
        lines.append(f"--- {i}.{date_note} ---")
        lines.append(f"Title: {r.title}")
        lines.append(f"URL:   {r.url}")
        lines.append(f"       {r.snippet}")
        lines.append("")
    return _text("\n".join(lines))


@tool(
    "fetch_url",
    "Fetch the text content of a URL (HTML stripped to readable text; PDF pages "
    "extracted up to 50 pages). Response capped at ~20 k characters. Cached — "
    "repeated fetches are free.",
    {"url": str},
)
@traced_tool
async def fetch_url(args: dict[str, Any]) -> dict[str, Any]:
    from watermark.research.connectors.fetch import fetch_url as _fetch_url

    url: str = args.get("url", "").strip()
    if not url:
        return _text("[fetch_url] url is required.")
    err = _ssrf_check(url)
    if err:
        return _text(f"[fetch_url] {err}")
    settings = get_settings()
    content = await asyncio.to_thread(_fetch_url, url, settings=settings)
    if not content:
        return _text(f"[fetch_url] No content fetched from {url!r}.")
    return _text(f"[fetch_url] {url}\n\n{content}")


def _gh_app_required(tool_name: str) -> dict[str, Any]:
    """Standard dry-run response when App credentials are not configured."""
    return _text(
        f"[{tool_name}] GitHub App credentials not configured — operation skipped. "
        "Set WATERMARK_GITHUB_APP_ID, WATERMARK_GITHUB_APP_PRIVATE_KEY, and "
        "WATERMARK_GITHUB_APP_INSTALLATION_ID to enable write operations."
    )


def _gh_permission_denied(tool_name: str, exc: PermissionError) -> dict[str, Any]:
    return _text(f"[{tool_name}] Permission denied: {exc}")


@tool(
    "comment_on_pr",
    "Post a comment on a GitHub PR or issue for the active site's repo. "
    "Requires GitHub App credentials (WATERMARK_GITHUB_APP_*) and admin or site-admin access. "
    "Use for research-run summaries, triage notes, or evidence annotations.",
    {
        "pr_number": {
            "type": "integer",
            "description": "PR or issue number to comment on.",
        },
        "body": {
            "type": "string",
            "description": "Markdown body of the comment (max 65536 chars).",
        },
    },
)
@traced_tool
async def comment_on_pr(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not GitHubAppClient.is_configured(settings):
        return _gh_app_required("comment_on_pr")

    checker = AdminChecker(settings)
    caller = checker.resolve_caller()
    try:
        checker.require_site_admin(caller, settings.site)
    except PermissionError as exc:
        return _gh_permission_denied("comment_on_pr", exc)

    pr_number: int = int(args["pr_number"])
    body: str = str(args.get("body", "")).strip()
    if not body:
        return _text("[comment_on_pr] body is required.")

    result = await _gh_comment_on_pr(settings, pr_number, body)
    if result.ok:
        return _text(f"[comment_on_pr] Comment posted: {result.url}")
    return _text(f"[comment_on_pr] Failed: {result.error}")


@tool(
    "add_label",
    "Add a label to a GitHub issue or PR for the active site's repo. "
    "Requires GitHub App credentials and admin or site-admin access.",
    {
        "issue_number": {
            "type": "integer",
            "description": "Issue or PR number.",
        },
        "label": {
            "type": "string",
            "description": "Label name to add (must already exist in the repo).",
        },
    },
)
@traced_tool
async def add_label(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not GitHubAppClient.is_configured(settings):
        return _gh_app_required("add_label")

    checker = AdminChecker(settings)
    caller = checker.resolve_caller()
    try:
        checker.require_site_admin(caller, settings.site)
    except PermissionError as exc:
        return _gh_permission_denied("add_label", exc)

    issue_number: int = int(args["issue_number"])
    label: str = str(args.get("label", "")).strip()
    if not label:
        return _text("[add_label] label is required.")

    result = await _gh_add_label(settings, issue_number, label)
    if result.ok:
        return _text(f"[add_label] Label {label!r} added to #{issue_number}.")
    return _text(f"[add_label] Failed: {result.error}")


@tool(
    "remove_label",
    "Remove a label from a GitHub issue or PR for the active site's repo. "
    "Requires GitHub App credentials and admin or site-admin access.",
    {
        "issue_number": {
            "type": "integer",
            "description": "Issue or PR number.",
        },
        "label": {
            "type": "string",
            "description": "Label name to remove.",
        },
    },
)
@traced_tool
async def remove_label(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not GitHubAppClient.is_configured(settings):
        return _gh_app_required("remove_label")

    checker = AdminChecker(settings)
    caller = checker.resolve_caller()
    try:
        checker.require_site_admin(caller, settings.site)
    except PermissionError as exc:
        return _gh_permission_denied("remove_label", exc)

    issue_number: int = int(args["issue_number"])
    label: str = str(args.get("label", "")).strip()
    if not label:
        return _text("[remove_label] label is required.")

    result = await _gh_remove_label(settings, issue_number, label)
    if result.ok:
        return _text(f"[remove_label] Label {label!r} removed from #{issue_number}.")
    return _text(f"[remove_label] Failed: {result.error}")


@tool(
    "set_issue_state",
    "Open or close a GitHub issue for the active site's repo. "
    "Requires GitHub App credentials and admin or site-admin access.",
    {
        "issue_number": {
            "type": "integer",
            "description": "Issue number to update.",
        },
        "state": {
            "type": "string",
            "enum": ["open", "closed"],
            "description": "Target state: 'open' or 'closed'.",
        },
    },
)
@traced_tool
async def set_issue_state(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not GitHubAppClient.is_configured(settings):
        return _gh_app_required("set_issue_state")

    checker = AdminChecker(settings)
    caller = checker.resolve_caller()
    try:
        checker.require_site_admin(caller, settings.site)
    except PermissionError as exc:
        return _gh_permission_denied("set_issue_state", exc)

    issue_number: int = int(args["issue_number"])
    state: str = str(args.get("state", "")).strip()
    if state not in ("open", "closed"):
        return _text("[set_issue_state] state must be 'open' or 'closed'.")

    result = await _gh_set_issue_state(settings, issue_number, state)
    if result.ok:
        return _text(f"[set_issue_state] #{issue_number} is now {state}: {result.url}")
    return _text(f"[set_issue_state] Failed: {result.error}")


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
    retrieve_corpus,
    search_web,
    fetch_url,
    discover_oepa_permits,
    fetch_oepa_permit,
    list_site_issues,
    report_novel_finding,
    comment_on_pr,
    add_label,
    remove_label,
    set_issue_state,
]
ALLOWED_TOOL_NAMES = [f"mcp__{SERVER_NAME}__{t.name}" for t in ALL_TOOLS]


def build_server() -> Any:
    """Create the in-process SDK MCP server hosting BOSC's tools."""
    return create_sdk_mcp_server(name=SERVER_NAME, version="0.1.0", tools=ALL_TOOLS)
