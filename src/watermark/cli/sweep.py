"""``bosc sweep`` — external-discovery sweeps for a watershed-point site.

Currently exposes one sub-command:
    bosc sweep data-centers   # I-75/rail-corridor data-center activity sweep (#1050)
"""

from __future__ import annotations

import asyncio

import typer

from watermark.cli._base import (
    console,
    get_settings,
    sweep_app,
    wrote,
)

# ---------------------------------------------------------------------------
# Catalog entry template (needs-review; human promotes to reviewed after QA)
# ---------------------------------------------------------------------------

_CATALOG_TEMPLATE = """\
id: data-centers-{site}
title: {city} / {county} — Data-Center Activity Register
scope: extracted
status: needs-review
producer:
  kind: manual
  source: >-
    bosc sweep data-centers ({site}); search_web + fetch_url sweep via
    watermark.research.connectors — verify every figure against cited primary sources
    before promoting status to reviewed.
license: Curated from cited public sources
access_tier: public
site_scope: site:{site}
storage:
- relpath: extracted/{site}/data-centers.md
  media_type: text/markdown
  lfs: false
refresh:
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
# Sweep prompt
# ---------------------------------------------------------------------------

_SWEEP_PROMPT = """\
Perform a data-center activity sweep for {city} / {county}, {state} (site slug: {site}).

Follow the data-center-sweep skill methodology exactly:

STEP 1 — DISAMBIGUATION GUARDRAIL
Before recording any project, confirm it is physically located in {county}, not an
adjacent county. Check the street address and the resolution/deed text.

STEP 2 — CORRIDOR SWEEP
Use search_web to discover documented data-center projects along the I-75 corridor
and rail freight corridors near {city}. Suggested queries:
  "data center" "{city}" "{state}"
  "hyperscale" OR "cloud campus" "{county}"
  "data center" "{city}" "I-75"
  "{city}" "PILOT" OR "CRA" "data center"
  "{city}" "large load" OR "utility agreement" "data center"

STEP 3 — PRIMARY SOURCE FETCH
For every project found, call fetch_url on the city council resolution, municipal FAQ,
or county resolution that is the primary instrument for that project.

STEP 4 — REGULATORY SCAN
Search for Ohio EPA air PTI, NPDES stormwater coverage, and Ohio SOS entity registrations
for any operator found. Use the ECHO and OEPA tools if available; otherwise use search_web
for the permit reference and fetch_url on the OEPA/ECHO result page.

STEP 5 — NEGATIVE CHECKS
Call retrieve_corpus (site="{site}") and check list_extractions for any existing
data-center records. Note the RSEI county FIPS = {rsei_fips}; if the rsei corpus is
accessible, check for NAICS 518210 entries. Otherwise note it as [open].

STEP 6 — PRODUCE THE REGISTER
Write the full discover-and-pin register in the format defined by the data-center-sweep
skill, including:
  - Header with site name, county, and today's date
  - Disambiguation guardrail section
  - One numbered section per confirmed project (or "No activity found")
  - For each project: financial/tax instruments, water/hydrology hook, hydrology screen,
    regulatory record
  - Instruments to pull (priority order)
  - Sources section

Tag every claim: [verified] [inference] [open] [reference]
Do not fabricate figures. Use [open] for any value not found in a cited source.
Do not bridge Lima / Allen County (OH) entities onto {county} — no evidentiary link.
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
) -> None:
    """Sweep the I-75/rail corridor for data-center activity for the active site and write
    data/extracted/<site>/data-centers.md + the catalog entry.  Uses search_web and
    fetch_url to gather publicly documented projects; follow the data-center-sweep skill
    methodology (disambiguation → primary sources → regulatory scan → register).

    The output is a discover-and-pin register tagged with the BOSC evidence vocabulary.
    Status is written as needs-review — a human pass is required before promoting to
    reviewed in the catalog entry."""
    from datetime import UTC, datetime

    from watermark.agent.client import RESEARCH_SKILLS as _SKILLS
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
    prompt = _SWEEP_PROMPT.format(
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

    agent = ResearchAgent(
        settings=settings,
        max_turns=turns,
        skills=_SKILLS,
    )
    result = asyncio.run(agent.converse(prompt, on_text=emit))
    console.print()  # newline after streamed output

    register_text = result.text or "".join(streamed)

    register_path.parent.mkdir(parents=True, exist_ok=True)
    register_path.write_text(register_text, encoding="utf-8")
    wrote(register_path)

    catalog_text = _CATALOG_TEMPLATE.format(
        site=site,
        city=city,
        county=county,
        county_tag=county_tag,
        date=date,
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

    if result.is_error:
        raise typer.Exit(code=1)
