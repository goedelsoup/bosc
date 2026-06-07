"""Build the static site staging tree under ``web/``.

Orchestrates the generator: wipe ``web/``, mirror the curated narrative markdown
and the whole ``data/extracted`` artifact tree at repo-relative paths (so the
existing cross-links resolve unchanged), then write the generated pages —
landing, per-kind record pages, timeline, entity graph, exhibits. ``web/`` is
fully regenerable; this module is the source of truth. :mod:`bosc.site.render`
turns ``web/`` into the static HTML ``site/``.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from bosc.candidates import (
    load_cloud_consumer_candidates,
    load_defense_contractors,
    load_defense_scan,
)
from bosc.config import Settings, get_settings
from bosc.gleif import load_inventory as load_lei_inventory
from bosc.logging import get_logger
from bosc.people import load_people
from bosc.pipeline.corpus import load_corpus
from bosc.pipeline.entities import build_entity_graph
from bosc.pipeline.timeline import build_timeline
from bosc.rsei import load_inventory as load_rsei_inventory
from bosc.site import candidates as candidates_mod
from bosc.site import exhibits as exhibits_mod
from bosc.site import gismap as gismap_mod
from bosc.site import gleif as gleif_mod
from bosc.site import graph as graph_mod
from bosc.site import people as people_mod
from bosc.site import records as records_mod
from bosc.site import rsei as rsei_mod

log = get_logger(__name__)

_ASSETS = Path(__file__).parent / "assets"
# Binary derived artifacts that should not be mirrored into the site source tree.
_SKIP_SUFFIXES = frozenset({".parquet"})


@dataclass
class BuildResult:
    web_dir: Path
    narrative_files: int = 0
    record_pages: list[records_mod.RecordPage] = field(default_factory=list)
    n_records: int = 0
    n_events: int = 0
    n_entities: int = 0
    n_relationships: int = 0
    exhibits: list[exhibits_mod.Exhibit] = field(default_factory=list)
    people_pages: list[people_mod.PersonPage] = field(default_factory=list)
    n_people_tracked: int = 0
    n_candidates: int = 0
    n_defense_contractors: int = 0
    n_rsei_facilities: int = 0
    n_lei_records: int = 0


def _mirror_tree(
    src: Path,
    dst: Path,
    *,
    only_suffixes: frozenset[str] | None = None,
    exclude_parts: frozenset[str] = frozenset(),
) -> int:
    """Copy ``src`` into ``dst`` preserving structure; return files copied.

    ``only_suffixes`` (if given) keeps just those extensions; ``_SKIP_SUFFIXES``
    are always dropped; any path under a directory named in ``exclude_parts`` is
    skipped. Directories are created lazily so empty ones don't appear.
    """
    count = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix in _SKIP_SUFFIXES:
            continue
        if only_suffixes is not None and path.suffix not in only_suffixes:
            continue
        rel = path.relative_to(src)
        if exclude_parts & set(rel.parts):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    return count


def _render_home(result: BuildResult) -> str:
    """The landing page — what-this-is, the disclaimer, and a live corpus snapshot."""
    return "\n".join(
        [
            "# Project BOSC — the public record",
            "",
            "A browsable, citable view of the BOSC public-records corpus: primary "
            "documents read from degraded scans into structured data, plus the "
            "cross-document analysis built on top of them.",
            "",
            '!!! warning "What this is — and is not"',
            "    This site publishes **public records** and analysis of them. "
            "Registered-agent and organizer overlaps are *common-control plumbing*, "
            "**not** statements about beneficial ownership. Claims are tagged "
            "`[verified]` (read from a cited extraction) or `[inference]` (a labelled "
            "reading of the record). Nothing here is legal advice; verify every figure "
            "against the cited source before quoting it in a filing.",
            "",
            "## The corpus at a glance",
            "",
            f"- **{result.n_records}** structured records across deeds, EPA/USACE and "
            "NPDES permits, Secretary-of-State filings, plans, and cost estimates",
            f"- **{result.n_entities}** resolved entities and "
            f"**{result.n_relationships}** relationships in the [entity graph](entities.md)",
            f"- **{result.n_events}** dated events in the [timeline](timeline.md)",
            "",
            "## Start here",
            "",
            "- **[The Dossier](docs/DOSSIER.md)** — the synthesis of everything deconstructed so far",
            "- **[Records](records/index.md)** — every extraction, browsable by kind",
            "- **[Exhibits](exhibits.md)** — key primary-source documents to download",
            "- **[Timeline](timeline.md)** · **[Entity graph](entities.md)** — the cross-document layer",
            "",
        ]
    )


def _render_records_index(pages: list[records_mod.RecordPage]) -> str:
    lines = [
        "# Records",
        "",
        "Every committed extraction, grouped by document kind. Each record links "
        "its raw YAML; dollar totals are high-confidence, quantities marked `~` are "
        "approximate transcriptions.",
        "",
        "| Kind | Records |",
        "|---|---|",
    ]
    for p in pages:
        lines.append(f"| [{p.title}]({p.slug}.md) | {p.count} |")
    lines.append("")
    return "\n".join(lines)


def build_site(settings: Settings | None = None, web_dir: Path | None = None) -> BuildResult:
    """Generate the full ``web/`` staging tree and return a build summary."""
    settings = settings or get_settings()
    repo_root = settings.data_dir.parent
    web = web_dir or (repo_root / "web")

    if web.exists():
        shutil.rmtree(web)
    web.mkdir(parents=True)

    result = BuildResult(web_dir=web)

    # 1. Mirror narrative + artifacts at repo-relative paths (keeps cross-links live).
    docs_src = repo_root / "docs"
    n = 0
    if docs_src.exists():
        # `docs/reference/` is secondary Periplus material that links to source-docs
        # we don't publish; keep it out of the site (and out of the warning stream).
        n += _mirror_tree(
            docs_src,
            web / "docs",
            only_suffixes=frozenset({".md"}),
            exclude_parts=frozenset({"reference"}),
        )
    n += _mirror_tree(settings.extracted_dir, web / "data" / "extracted")
    # Reference datasets (ECHO NPDES inventory, etc.) — README pages + their CSVs.
    # `periplus/` is secondary fork material (geojson + links to unpublished
    # source-docs); keep it out, mirroring how docs/reference/ is excluded above.
    if settings.reference_dir.exists():
        n += _mirror_tree(
            settings.reference_dir,
            web / "data" / "reference",
            exclude_parts=frozenset({"periplus"}),
        )
    result.narrative_files = n

    # 2. Static assets (extra.css, mermaid-init.js, …).
    assets_dst = web / "assets"
    assets_dst.mkdir(parents=True, exist_ok=True)
    for asset in sorted(_ASSETS.iterdir()):
        if asset.is_file():
            shutil.copy2(asset, assets_dst / asset.name)

    # 3. Cross-document layer — load the corpus once, reuse for both renders.
    corpus = load_corpus(settings)
    result.n_records = len(corpus)
    events = build_timeline(corpus)
    egraph = build_entity_graph(corpus, enrich_parcels=True, settings=settings)
    result.n_events = len(events)
    result.n_entities = len(egraph.entities)
    result.n_relationships = len(egraph.relationships)
    (web / "timeline.md").write_text(graph_mod.render_timeline(events), encoding="utf-8")

    # Curated individual profiles — the entity graph's detail store. Only the
    # expanded-research ones are published; the graph deep-links to those.
    people = load_people(settings.people_dir)
    result.n_people_tracked = len(people)
    profile_slugs = {
        p.entity_key: p.slug for p in people if p.expanded and egraph.get(p.entity_key) is not None
    }
    (web / "entities.md").write_text(
        graph_mod.render_entities(egraph, profile_slugs=profile_slugs), encoding="utf-8"
    )

    # 4. Per-kind record pages + their index.
    pages = records_mod.render_record_pages(settings.extracted_dir, web / "records")
    (web / "records" / "index.md").write_text(_render_records_index(pages), encoding="utf-8")
    result.record_pages = pages

    # 5. Curated exhibits.
    manifest = settings.data_dir / "site" / "exhibits.yaml"
    exhibits = exhibits_mod.build_exhibits(manifest, settings.documents_dir, web / "exhibits")
    (web / "exhibits.md").write_text(exhibits_mod.render_exhibits(exhibits), encoding="utf-8")
    result.exhibits = exhibits

    # 6. Individual profiles — render only the expanded-research ones, plus an index.
    people_dst = web / "people"
    people_dst.mkdir(parents=True, exist_ok=True)
    people_pages = people_mod.render_people_pages(people, people_dst, egraph=egraph)
    (people_dst / "index.md").write_text(
        people_mod.render_people_index(people_pages, tracked=result.n_people_tracked),
        encoding="utf-8",
    )
    result.people_pages = people_pages

    # 6b. Curated entity inputs (data/entities/profiles/), each if present.
    inventory = load_cloud_consumer_candidates(settings.entities_dir)
    if inventory is not None:
        (web / "candidates.md").write_text(
            candidates_mod.render_candidates(inventory, egraph=egraph), encoding="utf-8"
        )
        result.n_candidates = len(inventory.entities)

    defense = load_defense_contractors(settings.entities_dir)
    if defense is not None:
        scan = load_defense_scan(settings.reference_dir)
        (web / "defense-contractors.md").write_text(
            candidates_mod.render_defense_contractors(defense, egraph=egraph, scan=scan),
            encoding="utf-8",
        )
        result.n_defense_contractors = len(defense.defense_contractors)

    # 6b-ii. RSEI toxic-release inventory (data/reference/rsei/inventory.yaml).
    rsei_inv = load_rsei_inventory(settings.reference_dir)
    if rsei_inv is not None:
        (web / "rsei.md").write_text(
            rsei_mod.render_rsei(rsei_inv, egraph=egraph), encoding="utf-8"
        )
        result.n_rsei_facilities = len(rsei_inv.facilities)

    # 6b-iii. GLEIF LEI resolution (data/reference/gleif/lei-records.yaml).
    lei_inv = load_lei_inventory(settings.reference_dir)
    if lei_inv is not None:
        (web / "lei.md").write_text(
            gleif_mod.render_gleif(lei_inv, egraph=egraph), encoding="utf-8"
        )
        result.n_lei_records = len(lei_inv.records)

    # 6c. GIS findings map — copy the committed GeoJSON as a static asset, render the
    # Leaflet page (it fetches the asset client-side).
    findings_geojson = settings.data_dir / "site" / "gis-findings.geojson"
    if findings_geojson.is_file():
        shutil.copy2(findings_geojson, assets_dst / "gis-findings.geojson")
        (web / "gis-map.md").write_text(
            gismap_mod.render_gis_map(findings_geojson), encoding="utf-8"
        )

    # 7. Landing page, staged as home.md; bosc.site.render renders it to the root
    # index.html so the site's home URL is `/`.
    (web / "home.md").write_text(_render_home(result), encoding="utf-8")

    log.info(
        "site.built",
        web=str(web),
        narrative=result.narrative_files,
        record_pages=len(result.record_pages),
        records=result.n_records,
        events=result.n_events,
        entities=result.n_entities,
        exhibits=len(result.exhibits),
    )
    return result
