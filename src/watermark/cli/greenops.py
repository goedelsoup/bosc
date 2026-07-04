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


@greenops_app.command("aws")
def aws(
    write: bool = typer.Option(
        False, "--write", help="Write data/reference/greenops/aws-*.yaml + README."
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Replay committed fixtures only; never hit AWS."
    ),
    start: str = typer.Option(
        "", "--start", help="RFC 3339 window start (default: 12 months ago, month-aligned)."
    ),
    end: str = typer.Option(
        "", "--end", help="RFC 3339 window end, exclusive (default: start of this month)."
    ),
) -> None:
    """Pull AWS Cost Explorer (by function) + the Sustainability emissions estimate.

    Needs ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` (``ce:GetCostAndUsage`` +
    ``sustainability:GetEstimatedCarbonEmissions``) for a live pull; ``--offline`` replays
    committed fixtures. Figures are ``reference`` (a billing/emissions export), never
    metered. AWS publishes no electricity/kWh figure — that stays a derived number
    (#1082/#1083); emissions data lags ~3 months.
    """
    from watermark.greenops.connectors import (
        fetch_aws_carbon,
        fetch_aws_costs,
        write_aws_carbon,
        write_aws_costs,
    )

    settings = offline_settings("greenops", offline)
    default_start, default_end = _trailing_12_months()
    window = (start or default_start, end or default_end)
    costs = fetch_aws_costs(*window, settings=settings)
    carbon = fetch_aws_carbon(*window, settings=settings)

    console.print(
        f"[bold]AWS costs[/] [dim]({costs.period.label})[/]  "
        f"[dim]reference — a billing export, not metered[/]"
    )
    by_function = Table("function", "cost", "services")
    for f in costs.by_function:
        by_function.add_row(f.label, f"${f.cost.value:,.2f}", ", ".join(f.services))
    console.print(by_function)
    console.print(f"Total: ${costs.total_cost.value:,.2f}  [dim]{costs.total_cost.source}[/]")

    console.print(
        f"\n[bold]AWS estimated emissions[/] [dim]({carbon.period.label})[/]  "
        f"[dim]reference — AWS's own estimate; lags ~3 months[/]"
    )
    emissions = Table("figure", "value", "provenance")
    emissions.add_row(
        "Market-based (MBM)",
        f"{carbon.mbm_total.value:g} {carbon.mbm_total.unit}",
        f"[dim]{carbon.mbm_total.source}[/]",
    )
    emissions.add_row(
        "Location-based (LBM)",
        f"{carbon.lbm_total.value:g} {carbon.lbm_total.unit}",
        f"[dim]{carbon.lbm_total.source}[/]",
    )
    console.print(emissions)

    console.print(f"\n[dim]{carbon.note}[/]")
    if write:
        wrote(write_aws_costs(costs, settings=settings))
        wrote(write_aws_carbon(carbon, settings=settings))


@greenops_app.command("egrid")
def egrid(
    write: bool = typer.Option(
        False,
        "--write",
        help="Write data/reference/greenops/factors/egrid-*.yaml + wue-benchmarks.yaml + README.",
    ),
    offline: bool = typer.Option(
        False, "--offline", help="Replay committed fixtures only; never hit EPA."
    ),
) -> None:
    """Pull EPA eGRID subregion carbon-intensity + generation-mix factors; emit the WUE table.

    eGRID is a public workbook (no API key); ``--offline`` replays the committed fixture (the
    reduced subregion rows, not the ~20 MB xlsx). Both tables are ``reference`` — authoritative
    published factors, never metered. The WUE benchmark table is a hand-curated in-code
    canonical emitted alongside the eGRID factors so it stays regenerable.
    """
    from watermark.greenops.connectors import (
        build_wue_table,
        fetch_egrid_factors,
        write_egrid_factors,
        write_wue_table,
    )

    settings = offline_settings("greenops", offline)
    factors = fetch_egrid_factors(settings=settings)
    wue = build_wue_table()

    console.print(
        f"[bold]EPA {factors.vintage} subregion factors[/] "
        f"[dim]({len(factors.subregions)} subregions)[/]  "
        f"[dim]reference — an authoritative published factor, not metered[/]"
    )
    table = Table("subregion", "name", "CO2e (lb/MWh)", "renewable %")
    for sr in factors.subregions:
        table.add_row(
            sr.code, sr.name, f"{sr.co2e_rate.value:,.0f}", f"{sr.renewable_pct.value:g}%"
        )
    console.print(table)

    console.print(
        f"\n[bold]WUE benchmarks[/] [dim]({wue.vintage})[/]  "
        f"[dim]reference — published water-use benchmarks, not metered[/]"
    )
    wue_table = Table("facility type", "WUE (L/kWh)", "basis", "confidence")
    for b in wue.benchmarks:
        wue_table.add_row(b.label, f"{b.wue.value:g}", b.basis, b.wue.confidence)
    console.print(wue_table)

    console.print(f"\n[dim]{factors.note}[/]")
    if write:
        wrote(write_egrid_factors(factors, settings=settings))
        wrote(write_wue_table(wue, settings=settings))
