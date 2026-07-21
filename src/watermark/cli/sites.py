from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    SITES,
    console,
    sites_app,
)

# The frontend registry lives in @watermark/core now (Epic #1549, Phase 1 #1551) — it moved
# out of web/src/lib when the shared domain logic was extracted into a workspace package.
_REGISTRY_REL = "web/packages/core/src/sites-registry.json"
_REGISTRY_PATH = Path(__file__).parents[3] / _REGISTRY_REL


def _build_registry_json() -> str:
    """The content that sites-registry.json should contain — deterministic, YAML-order."""
    from watermark.sites._model import _get_identity

    entries = []
    for entry in _get_identity().values():
        entries.append(
            {
                "slug": entry.slug,
                "place": entry.place,
                "basin": entry.basin_label,
                "state": entry.state,
                "codename": entry.codename,
                "mono": entry.mono,
                "status": entry.status,
                "selectable": entry.selectable,
                "issue": entry.issue,
                "map_lat": entry.map_lat,
                "map_lon": entry.map_lon,
                "map_zoom": entry.map_zoom,
            }
        )
    return json.dumps({"sites": entries}, indent=2) + "\n"


@sites_app.command("list")
def sites_list() -> None:
    """List the registered site profiles (watermark.sites.SITES)."""
    table = Table("slug", "place", "basin")
    for slug, prof in SITES.items():
        table.add_row(slug, prof.place, prof.basin)
    console.print(table)


@sites_app.command("show")
def sites_show(
    slug: str = typer.Argument(..., help="Site slug to display."),
) -> None:
    """Print a site's resolved SiteProfile."""
    if slug not in SITES:
        raise typer.BadParameter(
            f"unknown site {slug!r}; known: {sorted(SITES)}", param_hint="slug"
        )
    prof = SITES[slug]
    table = Table("field", "value")
    for name in type(prof).model_fields:
        table.add_row(name, str(getattr(prof, name)))
    console.print(table)

    from watermark.catalog.sites import readiness

    r = readiness(slug)
    ready = "[green]ready[/]" if r.ready else f"[yellow]{len(r.missing)} missing[/]"
    console.print(
        f"\n[bold]Catalog readiness[/] — {r.present}/{r.total} datasets present · {ready}"
    )
    if r.missing:
        console.print(f"  [dim]missing:[/] {', '.join(r.missing)}")
    if r.stale:
        console.print(f"  [dim]stale:[/] {', '.join(r.stale)}")
    console.print(
        "  [dim](datasets derived from the catalog's per-site axis — `watermark catalog "
        f"list --site {slug}`)[/]"
    )


@sites_app.command("new")
def sites_new(
    slug: str = typer.Argument(..., help="New site slug (kebab-case)."),
    basin: str = typer.Option("maumee", "--basin", help="Basin slug (default: maumee)."),
) -> None:
    """Print a paste-ready SiteProfile stub for a new site (output relpaths pre-slug-scoped)."""
    from watermark.sites import scaffold_profile_src

    if slug in SITES:
        raise typer.BadParameter(f"site {slug!r} is already registered", param_hint="slug")
    # soft_wrap so the paste-ready stub isn't re-wrapped to the terminal width.
    console.print(
        scaffold_profile_src(slug, basin=basin), markup=False, highlight=False, soft_wrap=True
    )


@sites_app.command("sync")
def sites_sync() -> None:
    """Write the frontend registry from data/sites.yaml (the identity SSOT, #1027).

    Target: web/packages/core/src/sites-registry.json (the @watermark/core copy).
    """
    content = _build_registry_json()
    _REGISTRY_PATH.write_text(content, encoding="utf-8")
    console.print(f"[green]Wrote[/] {_REGISTRY_PATH.relative_to(Path.cwd())}")


@sites_app.command("check")
def sites_check() -> None:
    """Validate that both registries are in sync with data/sites.yaml (#1027).

    Checks:
    - Every Python SITES slug has an entry in data/sites.yaml.
    - The @watermark/core registry byte-matches what `watermark sites sync` would write.
    - No registered profile carries a raw 'TODO' grid-identity citation (B3/#1639).
    """
    from watermark.sites import grid_identity_todo_violations
    from watermark.sites._model import _get_identity

    errors: list[str] = []

    identity = _get_identity()
    for slug in SITES:
        if slug not in identity:
            errors.append(
                f"Python profile {slug!r} is missing from data/sites.yaml — "
                "add it there and run `watermark sites sync`"
            )

    for violation in grid_identity_todo_violations():
        errors.append(
            f"{violation} — replace with an honest citation or an '[open] …' pending note (B3/#1639)"
        )

    expected = _build_registry_json()
    if _REGISTRY_PATH.exists():
        actual = _REGISTRY_PATH.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(f"{_REGISTRY_REL} is out of sync — run `watermark sites sync`")
    else:
        errors.append(f"{_REGISTRY_REL} does not exist — run `watermark sites sync`")

    if errors:
        for e in errors:
            console.print(f"[red]✗[/] {e}")
        raise typer.Exit(1)

    console.print("[green]✓[/] sites registry is in sync")
