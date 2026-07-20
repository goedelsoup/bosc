"""``watermark facility`` — data-center facility modeling (epic #1626).

Thin wrappers over :mod:`watermark.facility.candidate` (the structured candidate record + the
promotion report) and :mod:`watermark.facility.sweep` (the prose→candidate distillation): parse
args → ``get_settings()`` → call the library → render. Consistent with ``cli/air.py`` /
``cli/sweep.py``.

Two verbs today:

* ``distill`` — (re)structure the active site's committed ``data-centers.md`` into
  ``data-centers.candidates.yaml`` without re-running the web sweep (the backfill path for the
  existing registers).
* ``promotion-report`` — surface, across every registered site, the prose/candidate facilities not
  yet represented in a :class:`~watermark.sites.SiteFacility` (the explicit backlog board).
"""

from __future__ import annotations

import typer
from rich.table import Table

from watermark.cli._base import (
    console,
    facility_app,
    get_settings,
    wrote,
)
from watermark.facility.candidate import (
    PromotionState,
    candidates_path,
    promotion_report,
    register_path,
    save_candidates,
)

# Rich style per promotion state — the actionable backlog reads loud, resolved/empty rows dim.
_STATE_STYLE = {
    PromotionState.NEEDS_PROMOTION: "bold yellow",
    PromotionState.NEEDS_DISTILL: "cyan",
    PromotionState.OK: "green",
    PromotionState.NONE: "dim",
}


@facility_app.command("distill")
def facility_distill(
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing data-centers.candidates.yaml."
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the register + planned output path without calling the model.",
    ),
) -> None:
    """Distill the active site's committed data-centers.md register into a validated candidate
    record (data-centers.candidates.yaml). Reuses the reviewed prose; runs a forced-tool-use
    extraction (needs API keys) — the output is needs-review, like the sweep itself."""
    from datetime import UTC, datetime

    from watermark.agent.extractor import StructuredExtractor
    from watermark.facility.sweep import distill_candidates

    settings = get_settings()
    site = settings.site
    register = register_path(settings, site)
    out = candidates_path(settings, site)

    if not register.exists():
        console.print(
            f"[yellow]No register for '{site}':[/] {register}\n"
            "Run `watermark sweep data-centers` first, or pick a site that has one."
        )
        raise typer.Exit(code=1)
    if not force and out.exists():
        console.print(
            f"[yellow]Candidate record already exists:[/] {out}\nUse --force to overwrite."
        )
        raise typer.Exit(code=1)

    source_register = str(register.relative_to(settings.data_dir))
    if dry_run:
        console.print(f"[bold]Site:[/] {site}")
        console.print(f"[bold]Register  →[/] {register}")
        console.print(f"[bold]Candidate →[/] {out}")
        return

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d")
    extractor = StructuredExtractor(settings=settings)
    record = distill_candidates(
        register.read_text(encoding="utf-8"),
        site=site,
        source_register=source_register,
        generated_at=generated_at,
        extractor=extractor,
    )
    save_candidates(record, out)
    wrote(out)

    promotable = len(record.promotable)
    console.print(
        f"\n[green]Distilled {len(record.candidates)} candidate(s)[/] "
        f"({promotable} promotable).\n"
        "[yellow]Status: needs-review[/] — verify every figure's provenance against the cited "
        "instrument before committing. Then run:\n  watermark catalog reconcile"
    )


@facility_app.command("promotion-report")
def facility_promotion_report() -> None:
    """List every site whose prose register or distilled candidate has no matching SiteFacility.

    The explicit close of the prose→SiteFacility backlog: needs-promotion (a promotable candidate
    with facility=None) and needs-distill (a register not yet structured) read first."""
    settings = get_settings()
    rows = promotion_report(settings)

    table = Table(title="Data-center facility promotion backlog", title_justify="left")
    table.add_column("site")
    table.add_column("register", justify="center")
    table.add_column("cand.", justify="right")
    table.add_column("promotable", justify="right")
    table.add_column("facility", justify="center")
    table.add_column("state")

    counts: dict[PromotionState, int] = dict.fromkeys(PromotionState, 0)
    for r in rows:
        counts[r.state] += 1
        table.add_row(
            r.site,
            "✓" if r.has_register else "-",
            str(r.candidate_count),
            str(r.promotable_count),
            "✓" if r.has_facility else "-",
            f"[{_STATE_STYLE[r.state]}]{r.state.value}[/]",
        )

    console.print(table)
    console.print(
        f"[dim]{counts[PromotionState.NEEDS_PROMOTION]} needs-promotion · "
        f"{counts[PromotionState.NEEDS_DISTILL]} needs-distill · "
        f"{counts[PromotionState.OK]} ok · {counts[PromotionState.NONE]} no register[/]"
    )
