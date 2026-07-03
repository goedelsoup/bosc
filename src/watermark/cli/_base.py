"""Shared core for the ``watermark`` CLI package.

Holds the root ``app`` Typer instance, the shared ``console``, every sub-app
Typer instance, the ``--site`` callback, and module-level names the command
modules reference (re-exported for use in option defaults / signatures).

The command modules live in sibling files and import from here; the package
``__init__`` imports them so their ``@app.command`` decorators register.
"""

from __future__ import annotations

import os
from typing import Any

import typer
from rich.console import Console

from watermark.config import Settings as Settings
from watermark.config import get_settings as get_settings
from watermark.config import repo_fixtures_dir as repo_fixtures_dir
from watermark.documents import DEFAULT_DPI as DEFAULT_DPI
from watermark.logging import configure_logging, configure_tracing
from watermark.models import OPCSummary as OPCSummary
from watermark.sites import SITES as SITES

app = typer.Typer(
    name="watermark",
    help="Project BOSC — agentic research platform.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def offline_settings(subsystem: str, offline: bool) -> Settings:
    """The recurring offline/online ``Settings`` switch used across the connector commands.

    When ``offline`` is set, serve committed fixtures for ``<subsystem>`` only (never touch
    the network) by flipping its ``<subsystem>_offline`` flag; otherwise return the live,
    cached config. Replaces the ``Settings(<sub>_offline=True) if offline else get_settings()``
    idiom that recurred across the command modules (#596).
    """
    if not offline:
        return get_settings()
    overrides: dict[str, Any] = {f"{subsystem}_offline": True}
    return Settings(**overrides)


def wrote(path: object) -> None:
    """Standard ``Wrote <path>`` confirmation — the repeated success line (#596)."""
    console.print(f"[green]Wrote[/] {path}")


@app.callback()
def _main(
    site: str = typer.Option(
        "lima",
        "--site",
        envvar="WATERMARK_SITE",
        help="Active site profile (registry key in watermark.sites, e.g. 'lima').",
    ),
) -> None:
    """Select the active site profile + configure logging before any command runs."""
    if site not in SITES:
        raise typer.BadParameter(
            f"unknown site {site!r}; known: {sorted(SITES)}", param_hint="--site"
        )
    # Set WATERMARK_SITE before the first get_settings() so the cached Settings resolve this
    # site; the callback runs ahead of every command, and cli has no import-time get_settings.
    os.environ["WATERMARK_SITE"] = site
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)


sites_app = typer.Typer(name="sites", help="Inspect + author the site registry (watermark.sites).")
app.add_typer(sites_app, name="sites")


hypotheses_app = typer.Typer(
    name="hypotheses",
    help="Inspect + lint the boom-origin hypotheses and their (site x hypothesis) cells.",
)
app.add_typer(hypotheses_app, name="hypotheses")


catalog_app = typer.Typer(
    name="catalog",
    help="Inspect + validate the data catalog (watermark.catalog) — one entry per data/ dataset.",
)
app.add_typer(catalog_app, name="catalog")


research_app = typer.Typer(
    name="research",
    help="Automated-research runs: investigate a topic, propose follow-up issues.",
    no_args_is_help=True,
)
app.add_typer(research_app, name="research")


objectstore_app = typer.Typer(
    name="objectstore",
    help="Source-document object store (Cloudflare R2) — epic #274. See docs/object-store.md.",
    no_args_is_help=True,
)
app.add_typer(objectstore_app, name="objectstore")


subdivisions_app = typer.Typer(
    name="subdivisions",
    help="Allen County subdivisions — meeting-records registry + publishing discovery.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(subdivisions_app, name="subdivisions")


imagery_app = typer.Typer(
    name="imagery",
    help="Satellite imagery for tracking sites (AOIs from the GIS findings).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(imagery_app, name="imagery")


poi_app = typer.Typer(
    name="poi",
    help="Points of interest (places) — the curated, depth-marked place store.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(poi_app, name="poi")


leads_app = typer.Typer(
    name="leads",
    help="Open-leads board — pull site leads from GitHub issues.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(leads_app, name="leads")


oepa_app = typer.Typer(
    name="oepa",
    help="OEPA/DAM document discovery and fetch (#847).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(oepa_app, name="oepa")


sweep_app = typer.Typer(
    name="sweep",
    help="External-discovery sweeps: data-center activity, permit searches, SOS filings (#1050).",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(sweep_app, name="sweep")


greenops_app = typer.Typer(
    name="greenops",
    help="Watermark's own compute footprint (AWS/Anthropic/GitHub/eGRID) — epic #1076.",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(greenops_app, name="greenops")
