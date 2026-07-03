from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    Settings,
    console,
    get_settings,
    imagery_app,
    repo_fixtures_dir,
)


def _gis_offline_settings() -> Settings:
    """Settings that serve committed GIS fixtures only (never touch the network)."""
    return Settings(
        gis_offline=True,
        gis_fixtures_dir=repo_fixtures_dir("gis"),
    )


@imagery_app.command("sites")
def imagery_sites() -> None:
    """List the tracking sites (the watched POIs in data/entities/poi/ that feed imagery)."""
    from watermark.gis import load_tracking_sites

    sites = load_tracking_sites()
    if not sites:
        console.print(
            "[yellow]No tracking sites[/] — no POI in data/entities/poi/ is watched "
            "(depth=watched + track.enabled with a location bbox). See `watermark poi list --tracked`."
        )
        raise typer.Exit(1)
    table = Table("id (slug)", "name", "parcels", "bbox (W,S,E,N)")
    for s in sites:
        bbox = ", ".join(f"{c:.4f}" for c in s.bbox)
        table.add_row(s.id, s.name, str(len(s.parcels)), bbox)
    console.print(table)


@imagery_app.command("search")
def imagery_search(
    site: str = typer.Argument(..., help="Tracking-site id (see `watermark imagery sites`)."),
    collection: str | None = typer.Option(
        None, "--collection", help="STAC collection (default: settings.gis_default_collection)."
    ),
    date_from: str | None = typer.Option(None, "--from", help="Start date, e.g. 2023-01-01."),
    date_to: str | None = typer.Option(None, "--to", help="End date, e.g. 2024-12-31."),
    max_cloud: float | None = typer.Option(
        None, "--max-cloud", help="Max eo:cloud_cover percent (Sentinel-2/Landsat)."
    ),
    limit: int | None = typer.Option(None, "--limit", help="Max scenes to return."),
    pad: float = typer.Option(0.0, "--pad", help="Grow the site bbox by N degrees."),
    offline: bool = typer.Option(
        False, "--offline", help="Use the committed fixture only; never touch the network."
    ),
) -> None:
    """Search a public STAC catalog for scenes covering a tracking site, newest first.

    Lists the matching scenes (acquisition date, cloud, platform, native CRS) and their
    asset count — the search step; materializing AOI-clipped GeoTIFFs is a later stage.
    """
    from watermark.gis import imagery

    dt_range = f"{date_from or '..'}/{date_to or '..'}" if (date_from or date_to) else None
    settings = _gis_offline_settings() if offline else get_settings()
    try:
        site_obj, scenes = imagery.search_site(
            site,
            collection=collection,
            datetime_range=dt_range,
            max_cloud=max_cloud,
            limit=limit,
            pad_deg=pad,
            settings=settings,
        )
    except KeyError as exc:
        console.print(f"[red]{exc}[/] — see [bold]watermark imagery sites[/].")
        raise typer.Exit(1) from exc

    coll = collection or get_settings().gis_default_collection
    span = dt_range or "all dates"
    console.print(
        f"[bold]{site_obj.name}[/] [{coll}] {span} — [bold]{len(scenes)}[/] scenes "
        f"(bbox {', '.join(f'{c:.4f}' for c in site_obj.padded_bbox(pad))})"
    )
    table = Table("acquired", "platform", "cloud %", "EPSG", "assets", "scene id")
    for sc in scenes:
        table.add_row(
            (sc.acquired or "—")[:19],
            sc.platform or "—",
            f"{sc.cloud_cover:.1f}" if sc.cloud_cover is not None else "—",
            str(sc.epsg) if sc.epsg is not None else "—",
            str(len(sc.assets)),
            sc.scene_id,
        )
    console.print(table)


@imagery_app.command("pull")
def imagery_pull(
    site: str = typer.Argument(..., help="Tracking-site id (see `watermark imagery sites`)."),
    collection: str | None = typer.Option(
        None, "--collection", help="STAC collection (default: settings.gis_default_collection)."
    ),
    asset: str | None = typer.Option(
        None, "--asset", help="Asset/band key (default per collection, e.g. sentinel-2 'visual')."
    ),
    date_from: str | None = typer.Option(None, "--from", help="Start date, e.g. 2024-06-01."),
    date_to: str | None = typer.Option(None, "--to", help="End date, e.g. 2024-09-30."),
    max_cloud: float | None = typer.Option(None, "--max-cloud", help="Max eo:cloud_cover percent."),
    limit: int = typer.Option(1, "--limit", help="How many scenes (newest first) to pull."),
    out: str | None = typer.Option(
        None, "--out", help="Output root (default: data/reference/imagery)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixtures only; never touch the network."
    ),
) -> None:
    """Clip scenes covering a tracking site to AOI GeoTIFFs (dated, with provenance sidecars).

    Searches the catalog, then for each of the newest ``--limit`` scenes reads just the
    AOI window of the chosen asset and writes
    data/reference/imagery/<site>/<collection>/<date>.<asset>.tif plus a `.yaml`
    chain-of-custody sidecar (sensing vs. retrieval date, scene id, sha256). Pixels are
    verbatim — a windowed clip in the scene's native CRS, no resampling.
    """
    from watermark.gis import imagery, raster

    dt_range = f"{date_from or '..'}/{date_to or '..'}" if (date_from or date_to) else None
    settings = _gis_offline_settings() if offline else get_settings()
    out_dir = Path(out) if out else None
    try:
        site_obj, scenes = imagery.search_site(
            site,
            collection=collection,
            datetime_range=dt_range,
            max_cloud=max_cloud,
            limit=limit,
            settings=settings,
        )
    except KeyError as exc:
        console.print(f"[red]{exc}[/] — see [bold]watermark imagery sites[/].")
        raise typer.Exit(1) from exc
    if not scenes:
        console.print("[yellow]No scenes matched[/] — widen --from/--to or raise --max-cloud.")
        raise typer.Exit(1)

    table = Table("acquired", "asset", "EPSG", "size", "sha256", "path")
    for sc in scenes[:limit]:
        try:
            cap = raster.pull_capture(sc, site_obj, asset=asset, out_dir=out_dir, settings=settings)
        except imagery.ImageryOfflineError as exc:
            console.print(f"[red]offline:[/] {exc}")
            raise typer.Exit(1) from exc
        table.add_row(
            (cap.acquired or "—")[:10],
            cap.asset,
            str(cap.epsg) if cap.epsg else "—",
            f"{cap.width}x{cap.height}",
            cap.sha256[:12],
            cap.path,
        )
    n = min(limit, len(scenes))
    console.print(f"[bold]{site_obj.name}[/] — pulled [bold]{n}[/] capture(s):")
    console.print(table)


@imagery_app.command("index")
def imagery_index(
    site: str = typer.Argument(..., help="Tracking-site id (see `watermark imagery sites`)."),
    index: str = typer.Option("ndvi", "--index", help="ndvi (vegetation) | ndwi (water)."),
    collection: str | None = typer.Option(
        None, "--collection", help="STAC collection (default: settings.gis_default_collection)."
    ),
    date_from: str | None = typer.Option(None, "--from", help="Start date, e.g. 2024-06-01."),
    date_to: str | None = typer.Option(None, "--to", help="End date, e.g. 2024-09-30."),
    max_cloud: float | None = typer.Option(None, "--max-cloud", help="Max eo:cloud_cover percent."),
    out: str | None = typer.Option(
        None, "--out", help="Output root (default: data/reference/imagery)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use committed fixtures only; never touch the network."
    ),
) -> None:
    """Compute a spectral index (NDVI/NDWI) for a site's newest scene → a derived raster.

    NDVI flags vegetation loss / land disturbance; NDWI's water fraction measures open-water
    extent (the reservoir signal). Writes a float32 GeoTIFF + a `derived`-tagged sidecar.
    """
    from typing import cast

    from watermark.gis import analysis, imagery
    from watermark.gis.imagery import ImageryOfflineError

    if index not in ("ndvi", "ndwi"):
        console.print("[red]--index must be ndvi or ndwi[/]")
        raise typer.Exit(1)
    idx = cast(analysis.Index, index)
    dt_range = f"{date_from or '..'}/{date_to or '..'}" if (date_from or date_to) else None
    settings = _gis_offline_settings() if offline else get_settings()
    out_dir = Path(out) if out else None
    try:
        site_obj, scenes = imagery.search_site(
            site,
            collection=collection,
            datetime_range=dt_range,
            max_cloud=max_cloud,
            limit=1,
            settings=settings,
        )
    except KeyError as exc:
        console.print(f"[red]{exc}[/] — see [bold]watermark imagery sites[/].")
        raise typer.Exit(1) from exc
    if not scenes:
        console.print("[yellow]No scenes matched[/] — widen --from/--to or raise --max-cloud.")
        raise typer.Exit(1)

    try:
        r = analysis.compute_index(
            scenes[0], site_obj, index=idx, out_dir=out_dir, settings=settings
        )
    except ImageryOfflineError as exc:
        console.print(f"[red]offline:[/] {exc}")
        raise typer.Exit(1) from exc

    console.print(
        f"[bold]{site_obj.name}[/] [{r.collection}] {r.index.upper()} @ {(r.acquired or '—')[:10]} "
        f"— mean=[bold]{r.mean}[/] valid={r.valid_fraction}"
        + (f" water=[bold]{r.water_fraction}[/]" if r.water_fraction is not None else "")
    )
    console.print(f"  [dim]{r.path}[/]")
