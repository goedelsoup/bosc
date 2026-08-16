from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from watermark.cli._base import (
    Settings,
    app,
    console,
    get_settings,
    offline_settings,
    wrote,
)


@app.command(name="parcels")
def parcels(
    parcel: str | None = typer.Option(
        None,
        "--parcel",
        help="Look up parcels by number (comma-separate for several).",
    ),
    owner: str | None = typer.Option(None, "--owner", help="Find parcels by owner-name substring."),
    cited: bool = typer.Option(
        False, "--cited", help="Pull every parcel id cited in the corpus (deeds) -> reference YAML."
    ),
    defense: bool = typer.Option(
        False,
        "--defense",
        help="Scan parcel owners against the defense-contractor seed list -> reference YAML.",
    ),
    geojson: str | None = typer.Option(
        None,
        "--geojson",
        help="With --owner or --parcel, write the matching parcels (with WGS84 geometry) "
        "to this GeoJSON path.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for --cited/--defense (default: data/reference/allen-gis).",
    ),
) -> None:
    """Query the county GIS parcel (CAMA) layer: by number, owner, citations, or defense scan."""
    from watermark.hydrology.connectors import allen_gis
    from watermark.sites import active_profile

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    schema = active_profile(settings).gis_parcel
    if schema is None:
        console.print(
            f"[yellow]Site {settings.site!r} has no parcel GIS configured[/] (gis_parcel) — "
            "register one on its SiteProfile (see docs/onboarding.md)."
        )
        raise typer.Exit(1)
    ref_dir = settings.reference_dir / schema.reference_dir

    if parcel:
        ids = [p.strip() for p in parcel.split(",") if p.strip()]
        if not ids:
            # A value that is all separators/whitespace ("," / " ") is truthy but parses to
            # nothing. Rejected HERE, before either branch: the geojson path would otherwise
            # build `<id_field> IN ()` — malformed SQL — and the lookup path would fall through
            # its empty loop and exit 0 having silently done nothing.
            console.print(f"[yellow]No parcel ids in[/] {parcel!r} — nothing to look up.")
            raise typer.Exit(1)
        if geojson:
            # The by-NUMBER geojson path. It exists because a county layer may carry no owner
            # column at all (Adams County OH serves tax-map geometry with no CAMA join), and
            # `--owner --geojson` refuses cleanly on such a layer — leaving no way to commit an
            # assemblage the corpus has already identified by parcel id.
            norms = [allen_gis.normalize_parcel_id(i, rule=schema.id_normalize) for i in ids]
            quoted = ",".join("'" + n.replace("'", "''") + "'" for n in norms)
            fc = allen_gis.query_parcels_geojson(
                f"{schema.id_field} IN ({quoted})", settings=settings
            )
            got = {f.get("properties", {}).get("parcel_id") for f in fc.get("features", [])}
            missing = [n for n in norms if n not in got]
            if missing:
                # Refuse a partial write: a silently short assemblage is the failure mode that
                # would publish an under-stated campus footprint.
                console.print(f"[red]No parcel[/] for {', '.join(missing)} — nothing written.")
                raise typer.Exit(1)
            path = allen_gis.write_parcels_geojson(fc, Path(geojson), settings=settings)
            console.print(f"[green]Wrote[/] {len(got)} parcels (with geometry) -> {path}")
            return
        for one in ids:
            p = allen_gis.fetch_parcel(one, settings=settings)
            if p is None:
                norm = allen_gis.normalize_parcel_id(one, rule=schema.id_normalize)
                console.print(f"[yellow]No parcel[/] {one} ({norm}).")
                raise typer.Exit(1)
            console.print(p.model_dump())
        return

    if owner:
        if geojson:
            fc = allen_gis.parcels_geojson_by_owner(owner, settings=settings)
            path = allen_gis.write_parcels_geojson(fc, Path(geojson), settings=settings)
            n = len(fc.get("features", []))
            console.print(f"[green]Wrote[/] {n} parcels (with geometry) -> {path}")
            return
        results = allen_gis.parcels_by_owner(owner, settings=settings)
        table = Table("Parcel", "Owner", "Situs", "Acres", "Mkt total")
        for p in results:
            table.add_row(
                p.parcel_no or "—",
                p.owner or "—",
                p.situs_address or "—",
                f"{p.acres:.2f}" if p.acres is not None else "—",
                f"{p.market_total_value:,}" if p.market_total_value is not None else "—",
            )
        console.print(table)
        console.print(f"\n[bold]{len(results)}[/] parcels owned by ~'{owner}'.")
        return

    if cited:
        target = Path(out_dir) if out_dir else ref_dir
        ids = allen_gis.scan_parcel_ids(settings.extracted_dir, settings=settings)
        console.print(f"Found [bold]{len(ids)}[/] cited parcel ids in the corpus.")
        found: list[allen_gis.Parcel] = []
        for pid in ids:
            p = allen_gis.fetch_parcel(pid, settings=settings)
            if p is not None:
                found.append(p)
            else:
                console.print(
                    f"[dim]no GIS match for {pid} "
                    f"({allen_gis.normalize_parcel_id(pid, rule=schema.id_normalize)})[/]"
                )
        path = allen_gis.write_parcels(found, target, scope="cited", settings=settings)
        console.print(f"[green]Wrote[/] {len(found)} parcels -> {path}")
        return

    if defense:
        from watermark.candidates import load_defense_contractors

        if schema.defense is None:
            console.print(
                f"[yellow]Site {settings.site!r} has no defense-land scan configured[/] "
                "(gis_parcel.defense)."
            )
            raise typer.Exit(1)
        target = Path(out_dir) if out_dir else ref_dir
        dcl = load_defense_contractors(settings.entities_dir)
        if dcl is None:
            console.print(
                "[yellow]No defense-contractor seed list[/] under data/entities/profiles."
            )
            raise typer.Exit(1)
        primes = [(d.name, d.patterns) for d in dcl.defense_contractors]
        n_pat = sum(len(d.patterns) for d in dcl.defense_contractors)
        prime_owned = allen_gis.defense_owner_scan(primes, settings=settings)
        army = allen_gis.army_controlled_defense_land(settings=settings)
        n_owned = sum(len(v) for v in prime_owned.values())
        console.print(
            f"Scanned [bold]{n_pat}[/] prime patterns -> [bold]{n_owned}[/] prime-owned "
            f"parcels, [bold]{len(army)}[/] Army-controlled (JSMC) parcels."
        )
        for name, parcels in sorted(prime_owned.items()):
            for p in parcels:
                console.print(f"  [cyan]{name}[/]: {p.parcel_no} {p.owner}")
        path = allen_gis.write_defense_scan(
            prime_owned, army, target, patterns_searched=n_pat, settings=settings
        )
        console.print(f"[green]Wrote[/] defense scan -> {path}")
        return

    console.print("Pass one of --parcel, --owner, --cited, or --defense.")
    raise typer.Exit(1)


@app.command(name="zoning")
def zoning(
    parcel: str | None = typer.Option(None, "--parcel", help="Zoning district for one parcel."),
    districts: bool = typer.Option(
        False, "--districts", help="Pull the Lima zoning-district catalog -> reference YAML."
    ),
    cited: bool = typer.Option(
        False, "--cited", help="Look up zoning for every parcel id cited in the corpus."
    ),
    write: bool = typer.Option(
        False, "--write", help="With --cited, persist the scan to parcels.zoning.yaml."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None,
        "--out",
        help="Output directory for --districts/--cited (default: data/reference/lima-gis).",
    ),
) -> None:
    """Query the jurisdiction zoning layer (Lima = city limits only; joins by parcel number)."""
    from watermark.hydrology.connectors import allen_gis, lima_gis
    from watermark.sites import active_profile

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    schema = active_profile(settings).gis_zoning
    if schema is None:
        console.print(
            f"[yellow]Site {settings.site!r} has no zoning GIS configured[/] (gis_zoning) — "
            "register one on its SiteProfile (see docs/onboarding.md)."
        )
        raise typer.Exit(1)
    ref_dir = settings.reference_dir / schema.reference_dir

    if parcel:
        rec = lima_gis.zoning_for_parcel(parcel, settings=settings)
        if rec is None:
            norm = allen_gis.normalize_parcel_id(parcel, rule=schema.id_normalize)
            console.print(
                f"[yellow]No zoning[/] for {parcel} ({norm}) — outside the layer or unzoned."
            )
            raise typer.Exit(1)
        console.print(rec.model_dump())
        return

    if districts:
        target = Path(out_dir) if out_dir else ref_dir
        cat = lima_gis.zoning_districts(settings=settings)
        table = Table("District", "Polygons")
        for d in cat:
            table.add_row(d.code, str(d.polygon_count))
        console.print(table)
        path = lima_gis.write_zoning_districts(cat, target, settings=settings)
        console.print(f"[green]Wrote[/] {len(cat)} districts -> {path}")
        return

    if cited:
        ids = allen_gis.scan_parcel_ids(settings.extracted_dir, settings=settings)
        console.print(f"Found [bold]{len(ids)}[/] cited parcel ids; looking up zoning.")
        scan = lima_gis.scan_cited_zoning(ids, settings=settings)
        in_city = [s for s in scan if s.in_city]
        for s in in_city:
            console.print(f"  [cyan]{s.parcel_no}[/]: {s.zoning}")
        console.print(
            f"\n[bold]{len(in_city)}[/] of {len(scan)} cited parcels are within the zoning layer."
        )
        if write:
            target = Path(out_dir) if out_dir else ref_dir
            path = lima_gis.write_cited_zoning(scan, target, settings=settings)
            wrote(path)
        return

    console.print("Pass one of --parcel, --districts, or --cited.")
    raise typer.Exit(1)


@app.command(name="floodzone")
def floodzone(
    catalog: bool = typer.Option(
        False, "--catalog", help="Pull the FEMA DFIRM flood-zone catalog -> reference YAML."
    ),
    footprint: str | None = typer.Option(
        None, "--footprint", help="GeoJSON footprint to test (default: the Bistrozzi parcels)."
    ),
    buffer_m: int = typer.Option(50, "--buffer", help="Proximity buffer (metres) for the check."),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached GIS responses only; never touch the network."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory for --catalog (default: data/reference/lima-gis)."
    ),
) -> None:
    """Query the FEMA floodzone layer: zone catalog, or a footprint's flood risk."""
    from watermark.hydrology.connectors import lima_gis
    from watermark.hydrology.floodplain import write_campus_floodzone
    from watermark.sites import active_profile

    settings = get_settings()
    if offline:
        settings = Settings(hydro_offline=True)

    schema = active_profile(settings).gis_flood
    if schema is None:
        console.print(
            f"[yellow]Site {settings.site!r} has no floodzone GIS configured[/] (gis_flood) — "
            "register one on its SiteProfile (see docs/onboarding.md)."
        )
        raise typer.Exit(1)
    ref_dir = settings.reference_dir / schema.reference_dir

    if catalog:
        target = Path(out_dir) if out_dir else ref_dir
        classes = lima_gis.floodzone_catalog(settings=settings)
        table = Table("Zone", "Subtype", "SFHA", "Polygons")
        for c in classes:
            table.add_row(
                c.fld_zone, c.zone_subtype or "—", "✓" if c.sfha else "—", str(c.polygon_count)
            )
        console.print(table)
        path = lima_gis.write_floodzone_catalog(classes, target, settings=settings)
        console.print(f"[green]Wrote[/] {len(classes)} flood-zone classes -> {path}")
        return

    fp = (
        Path(footprint)
        if footprint
        else settings.reference_dir / "periplus" / "bosc-parcels.geojson"
    )
    if not fp.is_file():
        console.print(f"[yellow]No footprint GeoJSON[/] at {fp}.")
        raise typer.Exit(1)
    in_parcels = lima_gis.footprint_floodzones(fp, distance_m=0, settings=settings)
    nearby = lima_gis.footprint_floodzones(fp, distance_m=buffer_m, settings=settings)
    in_zones = sorted({f.fld_zone or "?" for f in in_parcels})
    near_zones = sorted(
        {f"{f.fld_zone}{' (' + f.zone_subtype + ')' if f.zone_subtype else ''}" for f in nearby}
    )
    if in_parcels:
        console.print(f"[red]In floodplain[/]: parcels intersect {', '.join(in_zones)}.")
    else:
        console.print(
            f"[green]Not in floodplain[/]: parcels intersect no SFHA; "
            f"within {buffer_m} m: {', '.join(near_zones) or 'none'}."
        )
    path = write_campus_floodzone(
        in_parcels, nearby, buffer_m=buffer_m, footprint=fp.name, settings=settings
    )
    console.print(f"[green]Wrote[/] campus floodzone finding -> {path}")


@app.command(name="wbd")
def wbd(
    site: str = typer.Option(
        "data-center-campus", "--site", help="Tracking-site POI whose AOI to frame (centroid)."
    ),
    point: str | None = typer.Option(
        None, "--point", help="Override AOI with an explicit 'lon,lat' WGS84 point."
    ),
    levels: str = typer.Option(
        "12,10", "--levels", help="HU digit-levels to pull, finest first (e.g. 12,10 or 12,10,8)."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Use cached/fixture WBD responses only; never touch the network."
    ),
    write: bool = typer.Option(
        False, "--write", help="Write each boundary to data/reference/hydrology/wbd/."
    ),
    out_dir: str | None = typer.Option(
        None, "--out", help="Output directory (default: data/reference/hydrology/wbd)."
    ),
) -> None:
    """Pull the USGS WBD watershed boundaries framing a tracked AOI (#61, for the #72 map).

    Resolves the AOI centroid (a tracking-site POI's bbox, or --point) and fetches the
    containing Hydrologic Unit at each --levels rung, finest first — by default the
    campus's Subwatershed (HU12 Pike Run) and Watershed (HU10 Middle Ottawa River),
    which nest into the Auglaize/Maumee basin. With --write, lands them as committed
    reference GeoJSON the `watershed` feed reads.
    """
    from watermark.gis.sites import get_site
    from watermark.hydrology.connectors import wbd as wbd_mod

    settings = offline_settings("hydro", offline)

    if point is not None:
        try:
            lon_s, lat_s = point.split(",")
            lon, lat = float(lon_s), float(lat_s)
        except ValueError:
            console.print(f"[red]Bad --point[/] {point!r}; expected 'lon,lat'.")
            raise typer.Exit(1) from None
        aoi = f"point {lon},{lat}"
    else:
        ts = get_site(site, settings=settings)
        if ts is None:
            console.print(f"[red]No tracking site[/] {site!r} (see `watermark imagery sites`).")
            raise typer.Exit(1)
        minx, miny, maxx, maxy = ts.bbox
        lon, lat = (minx + maxx) / 2.0, (miny + maxy) / 2.0
        aoi = f"{ts.name} ({site})"

    try:
        level_seq = tuple(int(x) for x in levels.split(","))
    except ValueError:
        console.print(f"[red]Bad --levels[/] {levels!r}; expected e.g. '12,10,8'.")
        raise typer.Exit(1) from None

    boundaries = wbd_mod.watershed_chain(lon, lat, levels=level_seq, settings=settings)
    if not boundaries:
        console.print(f"[yellow]No HU found[/] at {aoi}.")
        raise typer.Exit(1)

    table = Table("HU", "Code", "Name", "km²", "→ drains to")
    for hu in boundaries:
        table.add_row(
            f"HU{hu.level} ({hu.hu_label})",
            hu.huc,
            hu.name,
            f"{hu.area_sqkm:,.0f}" if hu.area_sqkm is not None else "—",
            hu.to_huc or "—",
        )
    console.print(f"Watershed boundaries framing [bold]{aoi}[/]:")
    console.print(table)

    if write:
        target = Path(out_dir) if out_dir else settings.reference_dir / "hydrology" / "wbd"
        paths = wbd_mod.write_watershed_boundaries(boundaries, target, queried_point=(lon, lat))
        for p in paths:
            console.print(f"[green]Wrote[/] {p}")
