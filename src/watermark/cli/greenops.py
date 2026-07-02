from __future__ import annotations

from rich.table import Table

from watermark.cli._base import console, greenops_app


@greenops_app.command("report")
def report() -> None:
    """Show the current GreenOps footprint report.

    Scaffold (#1077): renders the modeled ``assumption`` placeholder — every figure is a
    stated modeling input, not a metered fact. The per-source connector ``--write``
    subcommands (AWS/Anthropic/GitHub/eGRID) land here in #1078-#1082.
    """
    from watermark.greenops.footprint import placeholder_report

    rpt = placeholder_report()
    rpt.assert_no_verified()  # discipline guard: no figure may claim to be metered

    console.print(
        f"[bold]GreenOps footprint[/] [dim]({rpt.period.label})[/]  "
        f"[yellow]modeled placeholder — every figure is an assumption pending its source[/]"
    )

    def _fmt(v: float) -> str:
        return f"{v:,.0f}" if v == int(v) else f"{v:g}"

    table = Table("figure", "value", "source", "provenance")
    for h in rpt.headline:
        table.add_row(
            h.label,
            f"{_fmt(h.value.value)} {h.value.unit}",
            h.source_label,
            f"[dim]{h.value.source}[/]",
        )
    console.print(table)
    if rpt.note:
        console.print(f"\n[dim]{rpt.note}[/]")
