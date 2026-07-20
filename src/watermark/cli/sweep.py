"""``watermark sweep`` — external-discovery sweeps for a watershed-point site.

Currently exposes one sub-command:
    watermark sweep data-centers   # I-75/rail-corridor data-center activity sweep (#1050)
"""

from __future__ import annotations

import asyncio

import typer
import yaml

from watermark.cli._base import (
    console,
    get_settings,
    sweep_app,
    wrote,
)
from watermark.facility.candidate import candidates_path, save_candidates
from watermark.facility.sweep import build_sweep_prompt, distill_candidates

# ---------------------------------------------------------------------------
# Catalog entry template (needs-review; human promotes to reviewed after QA)
# ---------------------------------------------------------------------------

_CATALOG_TEMPLATE = """\
id: data-centers-{site}
title: {city} / {county} — Data-Center Activity Register
scope: extracted
status: {status}
producer:
  kind: manual
  source: >-
    watermark sweep data-centers ({site}); search_web + fetch_url sweep via
    watermark.research.connectors — verify every figure against cited primary sources
    before promoting status to reviewed.
license: Curated from cited public sources
access_tier: public
site_scope: site:{site}
storage:
- relpath: extracted/{site}/data-centers.md
  media_type: text/markdown
  lfs: false
{candidates_storage}refresh:
  cadence: on-demand
provenance: reference
tags:
- data-center
- i75-corridor
- {county_tag}
- {site}
- sweep
notes: >-
  #1050 data-center sweep ({date}). Status needs-review — human QA required
  before promoting to reviewed. Run `watermark catalog reconcile` after commit.
"""

# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


@sweep_app.command("data-centers")
def sweep_data_centers(
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Use cached/fixture results only — no live web requests.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the sweep prompt and planned output paths without running the agent.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing data-centers.md register.",
    ),
    max_turns: int = typer.Option(
        0,
        "--max-turns",
        help="Agent turn cap (0 = settings default).",
    ),
    no_distill: bool = typer.Option(
        False,
        "--no-distill",
        help="Skip the prose→structured candidate-record distillation (write the register only).",
    ),
) -> None:
    """Sweep the I-75/rail corridor for data-center activity for the active site and write
    data/extracted/<site>/data-centers.md + the catalog entry.  Uses search_web and
    fetch_url to gather publicly documented projects; follow the data-center-sweep skill
    methodology (disambiguation → primary sources → regulatory scan → register).

    The output is a discover-and-pin register tagged with the BOSC evidence vocabulary.
    Status is written as needs-review — a human pass is required before promoting to
    reviewed in the catalog entry."""
    from datetime import UTC, datetime

    from watermark.agent.client import ResearchAgent
    from watermark.sites import active_profile

    settings = get_settings()
    if offline:
        settings = settings.model_copy(update={"research_offline": True})

    site = settings.site
    profile = active_profile(settings)

    # Derive city name from slug (title-case, hyphen → space for multi-word slugs).
    city = site.replace("-", " ").title()
    county = profile.county_name
    # county_tag: "shelby-county-oh" style slug for catalog tags
    county_tag = county.lower().replace(", ", "-").replace(" ", "-")
    state = profile.eia_state  # "OH" for all Ohio sites; "IN" for Fort Wayne
    rsei_fips = profile.rsei_fips

    register_path = settings.extracted_dir / site / "data-centers.md"
    catalog_path = settings.data_dir / "catalog" / "extracted" / f"data-centers-{site}.yaml"

    if not force and register_path.exists():
        console.print(
            f"[yellow]Register already exists:[/] {register_path}\nUse --force to overwrite."
        )
        raise typer.Exit(code=1)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    prompt = build_sweep_prompt(
        city=city,
        county=county,
        state=state,
        site=site,
        rsei_fips=rsei_fips,
    )

    if dry_run:
        console.print(f"[bold]Site:[/] {site}  county: {county}  state: {state}")
        console.print(f"[bold]Register →[/] {register_path}")
        console.print(f"[bold]Catalog →[/] {catalog_path}")
        console.print(f"\n[bold dim]Sweep prompt:[/]\n{prompt}")
        return

    turns = max_turns or settings.research_max_turns

    streamed: list[str] = []

    def emit(chunk: str) -> None:
        console.print(chunk, end="", markup=False, highlight=False)
        streamed.append(chunk)

    console.print(
        f"[bold]sweep data-centers[/] → {site} / {county} (max_turns={turns}, offline={offline})\n"
    )

    agent = ResearchAgent(settings=settings, max_turns=turns)
    result = asyncio.run(agent.converse(prompt, on_text=emit))
    console.print()  # newline after streamed output

    if result.is_error:
        raise typer.Exit(code=1)

    register_text = result.text or "".join(streamed)

    register_path.parent.mkdir(parents=True, exist_ok=True)
    register_path.write_text(register_text, encoding="utf-8")
    wrote(register_path)

    # Distill the prose register into a structured, provenance-carrying candidate record so the
    # sweep output is consumable (not prose-only) — the #1627 seam. Reviewed like the register.
    candidates_storage = ""
    if not no_distill:
        from watermark.agent.extractor import StructuredExtractor

        cand_path = candidates_path(settings, site)
        record = distill_candidates(
            register_text,
            site=site,
            source_register=str(register_path.relative_to(settings.data_dir)),
            generated_at=date,
            extractor=StructuredExtractor(settings=settings),
        )
        save_candidates(record, cand_path)
        wrote(cand_path)
        console.print(
            f"[dim]distilled {len(record.candidates)} candidate(s), "
            f"{len(record.promotable)} promotable[/]"
        )
        candidates_storage = (
            f"- relpath: extracted/{site}/data-centers.candidates.yaml\n"
            "  media_type: application/yaml\n"
            "  lfs: false\n"
        )

    # Preserve an existing "reviewed" status rather than resetting it to needs-review.
    catalog_status = "needs-review"
    if catalog_path.exists():
        try:
            existing = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
            if existing.get("status") == "reviewed":
                catalog_status = "reviewed"
        except Exception:
            pass

    catalog_text = _CATALOG_TEMPLATE.format(
        site=site,
        city=city,
        county=county,
        county_tag=county_tag,
        date=date,
        status=catalog_status,
        candidates_storage=candidates_storage,
    )
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.write_text(catalog_text, encoding="utf-8")
    wrote(catalog_path)

    prov_parts: list[str] = []
    if result.num_turns:
        prov_parts.append(f"{result.num_turns} turns")
    if result.cost_usd is not None:
        prov_parts.append(f"${result.cost_usd:.4f}")
    if result.tools_used:
        prov_parts.append("tools: " + ", ".join(result.tools_used))
    if prov_parts:
        console.print(f"[dim]({' · '.join(prov_parts)})[/]")

    console.print()
    console.print(
        "[yellow]Status: needs-review[/] — verify every [verified] tag against the "
        "cited instrument before committing. Then run:\n"
        "  watermark catalog reconcile"
    )
