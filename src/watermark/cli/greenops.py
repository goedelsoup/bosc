from __future__ import annotations

from datetime import UTC, datetime

import typer
from rich.table import Table

from watermark.cli._base import console, greenops_app, offline_settings, wrote


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


def _trailing_12_months() -> tuple[str, str]:
    """RFC 3339 ``[start, end)`` for the last 12 whole months, ending at the current month."""
    now = datetime.now(UTC)
    end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = end.replace(year=end.year - 1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)


@greenops_app.command("anthropic")
def anthropic(
    write: bool = typer.Option(
        False, "--write", help="Write data/reference/greenops/anthropic-usage.yaml + README."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Replay committed fixtures only; never hit the Admin API."
    ),
    start: str = typer.Option(
        "", "--start", help="RFC 3339 window start (default: 12 months ago, month-aligned)."
    ),
    end: str = typer.Option(
        "", "--end", help="RFC 3339 window end, exclusive (default: start of this month)."
    ),
) -> None:
    """Pull the Anthropic Admin usage + cost report (by model & workspace).

    Needs ``ANTHROPIC_ADMIN_KEY`` (an Admin key ``sk-ant-admin01-…``, distinct from the
    inference ``ANTHROPIC_API_KEY``) for a live pull; ``--offline`` replays committed fixtures.
    Figures are ``reference`` (a usage/billing export), never metered.
    """
    from watermark.greenops.connectors import fetch_anthropic_usage, write_anthropic_usage

    settings = offline_settings("greenops", offline)
    default_start, default_end = _trailing_12_months()
    report = fetch_anthropic_usage(start or default_start, end or default_end, settings=settings)

    console.print(
        f"[bold]Anthropic Admin usage[/] [dim]({report.period.label})[/]  "
        f"[dim]reference — a usage/billing export, not metered[/]"
    )
    table = Table("figure", "value", "provenance")
    table.add_row(
        "Total cost", f"${report.total_cost.value:,.2f}", f"[dim]{report.total_cost.source}[/]"
    )
    table.add_row(
        "Input tokens",
        f"{report.input_tokens.value:,.0f}",
        f"[dim]{report.input_tokens.source}[/]",
    )
    table.add_row(
        "Output tokens",
        f"{report.output_tokens.value:,.0f}",
        f"[dim]{report.output_tokens.source}[/]",
    )
    table.add_row(
        "Web-search requests",
        f"{report.web_search_requests.value:,.0f}",
        f"[dim]{report.web_search_requests.source}[/]",
    )
    console.print(table)

    if report.by_model:
        by_model = Table("model", "input tok", "output tok", "cost")
        for m in report.by_model:
            by_model.add_row(
                m.model, f"{m.input_tokens:,}", f"{m.output_tokens:,}", f"${m.cost.value:,.2f}"
            )
        console.print(by_model)

    console.print(f"\n[dim]{report.note}[/]")
    if write:
        wrote(write_anthropic_usage(report, settings=settings))
