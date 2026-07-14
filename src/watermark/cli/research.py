from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.table import Table

from watermark.cli._base import (
    console,
    get_settings,
    research_app,
)

if TYPE_CHECKING:
    from watermark.research import PublishPlan


class _GhError(RuntimeError):
    """A ``gh`` invocation failed (missing binary or non-zero exit).

    Carries a rendered, human-readable message so the CLI shows a clean line
    instead of a raw ``FileNotFoundError``/``CalledProcessError`` traceback.
    """


def _gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run ``gh <args>`` capturing output; raise :class:`_GhError` on any failure.

    Normalizes the two ways ``gh`` can blow up — not installed (``FileNotFoundError``)
    and non-zero exit (``CalledProcessError``) — into one rendered message. The error
    names only the subcommand (``args[:2]``), never the full body payload.
    """
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise _GhError(
            "GitHub CLI (`gh`) not found — install it (https://cli.github.com) to publish issues."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip() or f"exit {exc.returncode}"
        raise _GhError(f"`gh {' '.join(args[:2])}` failed: {detail}") from exc


def _write_publish_plan(
    out_dir: Path,
    *,
    existing: list[dict[str, Any]],
    plan_out: Path | None = None,
) -> PublishPlan:
    """Load the run manifest, build the publish plan (deduping against ``existing``),
    write it to JSON, and print the summary. No GitHub mutations — safe to run offline."""
    from watermark.research import build_plan, load_manifest

    manifest = load_manifest(out_dir)
    plan = build_plan(manifest, existing=existing, run_ref=out_dir.as_posix())
    out_path = plan_out or out_dir / "publish-plan.json"
    out_path.write_text(json.dumps(plan.model_dump(), indent=2) + "\n", encoding="utf-8")
    console.print(
        f"[bold]Publish plan →[/] {out_path}  "
        f"({len(plan.issues)} to open, {len(plan.duplicates)} skipped)"
    )
    return plan


def _publish_and_create_issues(
    out_dir: Path,
    site: str,
    *,
    existing: list[dict[str, Any]] | None = None,
    plan_out: Path | None = None,
) -> None:
    """Fetch open issues, build a publish plan, write it, and open net-new issues on GitHub.

    If ``existing`` is None, open issues are fetched automatically via ``gh``.
    ``plan_out`` defaults to ``<out_dir>/publish-plan.json``. Every ``gh`` call is routed
    through :func:`_gh`: a missing binary or a mid-loop failure renders a clean line and
    (for per-issue failures) is recorded to ``publish-result.json`` rather than aborting
    with a traceback after some issues were already opened.
    """
    try:
        _do_publish_and_create_issues(out_dir, site, existing=existing, plan_out=plan_out)
    except _GhError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc


def _do_publish_and_create_issues(
    out_dir: Path,
    site: str,
    *,
    existing: list[dict[str, Any]] | None,
    plan_out: Path | None,
) -> None:
    issues: list[dict[str, Any]]
    if existing is not None:
        issues = existing
    else:
        console.print("[dim]Fetching open issues for dedupe…[/]")
        loaded = json.loads(
            _gh(["issue", "list", "--json", "number,title,body", "--limit", "500"]).stdout
        )
        issues = loaded if isinstance(loaded, list) else []
        console.print(f"[dim]  {len(issues)} open issues fetched.[/]")

    plan = _write_publish_plan(out_dir, existing=issues, plan_out=plan_out)

    if not plan.issues:
        console.print("[yellow]No issues to open (all deduped or none proposed).[/]")
        return

    # Ensure the site label exists before trying to apply it.
    site_label = f"site:{site}"
    existing_label_names = {
        lbl["name"]
        for lbl in json.loads(_gh(["label", "list", "--json", "name", "--limit", "1000"]).stdout)
    }
    if site_label not in existing_label_names:
        _gh(["label", "create", site_label, "--color", "c5def5", "--description", f"Site: {site}"])
        console.print(f"[dim]Created label [bold]{site_label}[/].[/]")

    console.print()
    opened: list[str] = []
    failed: list[dict[str, str]] = []
    for iss in plan.issues:
        cmd = ["issue", "create", "--title", iss.title, "--body", iss.body]
        for label in [*iss.labels, f"site:{site}"]:
            cmd += ["--label", label]
        try:
            url = _gh(cmd).stdout.strip()
        except _GhError as exc:
            # Don't abort the batch — record and keep going so a rate limit / transient
            # 500 on one issue doesn't strand the rest with no record of what was created.
            failed.append({"title": iss.title, "error": str(exc)})
            console.print(f"  [red]failed[/] {iss.title} — {exc}")
            continue
        opened.append(url)
        console.print(f"  [green]opened[/] {url}")

    result_path = out_dir / "publish-result.json"
    result_path.write_text(
        json.dumps({"opened": opened, "failed": failed}, indent=2) + "\n", encoding="utf-8"
    )
    console.print(f"\n[bold]{len(opened)} opened[/], {len(failed)} failed — record → {result_path}")
    if failed:
        raise typer.Exit(1)


@research_app.command("run")
def research_run_cmd(
    topic: str = typer.Option("", "--topic", "-t", help="The investigation topic / question."),
    recipe: str = typer.Option(
        "issue-proposal",
        "--recipe",
        help="Research-agent recipe: issue-proposal | hypothesis-assessment | site-onboard.",
    ),
    hypothesis: str = typer.Option(
        "", "--hypothesis", help="Hypothesis id (required for the hypothesis-assessment recipe)."
    ),
    out: str = typer.Option("", "--out", help="Output dir (default: data/research/<slug>)."),
    max_turns: int = typer.Option(0, "--max-turns", help="Agent turn cap (0 = settings default)."),
    max_proposals: int = typer.Option(
        -1, "--max-proposals", help="Issue proposals to distill (-1 = settings default)."
    ),
    no_tools: bool = typer.Option(False, "--no-tools", help="Disable the BOSC data tools."),
    create_issues: bool = typer.Option(
        False,
        "--create-issues",
        "--publish",
        help="For --recipe site-onboard: open the proposed issues on GitHub via gh "
        "(default off — otherwise just writes the publish plan for review).",
    ),
) -> None:
    """Investigate over the corpus (read-only) and write findings + the recipe's output under
    data/research/. The default recipe distills issue proposals; --recipe hypothesis-assessment
    --hypothesis <id> assesses the active --site against a boom-origin hypothesis (candidate
    cells, for review). The site-onboard recipe writes a publish plan for its proposals; add
    --create-issues to also open them on GitHub (an irreversible external action, off by
    default). Never mutates source bytes."""
    from datetime import UTC, datetime

    from watermark.hypotheses import HYPOTHESES
    from watermark.research import RECIPES, run_research, run_slug, write_run

    settings = get_settings()
    if recipe not in RECIPES:
        raise typer.BadParameter(
            f"unknown recipe {recipe!r}; known: {sorted(RECIPES)}", param_hint="--recipe"
        )
    context: dict[str, str] = {}
    if recipe == "hypothesis-assessment":
        if hypothesis not in HYPOTHESES:
            raise typer.BadParameter(
                f"--hypothesis must be one of {sorted(HYPOTHESES)}", param_hint="--hypothesis"
            )
        context = {"hypothesis": hypothesis, "site": settings.site}
        if not topic:
            topic = f"assess {settings.site} x {hypothesis}"
    elif recipe == "site-onboard":
        context = {"site": settings.site}
        if not topic:
            topic = f"onboard {settings.site}"
    elif not topic:
        raise typer.BadParameter("the issue-proposal recipe needs --topic", param_hint="--topic")

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    turns = max_turns or settings.research_max_turns
    n = max_proposals if max_proposals >= 0 else settings.research_max_proposals

    def emit(chunk: str) -> None:
        console.print(chunk, end="", markup=False, highlight=False)

    manifest = asyncio.run(
        run_research(
            topic,
            generated_at=generated_at,
            settings=settings,
            max_turns=turns,
            max_proposals=n,
            enable_tools=not no_tools,
            on_text=emit,
            recipe=RECIPES[recipe],
            context=context,
        )
    )
    console.print()  # newline after the streamed findings

    out_dir = Path(out) if out else settings.research_dir / run_slug(topic, generated_at)
    write_run(manifest, out_dir, settings=settings)

    console.print(f"\n[bold]Research run →[/] {out_dir}")
    prov = manifest.provenance
    footer: list[str] = []
    if prov.tools_used:
        footer.append("tools: " + ", ".join(prov.tools_used))
    if prov.num_turns:
        footer.append(f"{prov.num_turns} turns")
    if prov.cost_usd is not None:
        footer.append(f"${prov.cost_usd:.4f}")
    if footer:
        console.print(f"[dim]({' · '.join(footer)})[/]")

    if manifest.assessments:
        table = Table("site x hypothesis", "signal", "tag", "group", "cites")
        for a in manifest.assessments:
            table.add_row(
                f"{a.site} x {a.hypothesis}",
                a.signal or "—",
                a.tag,
                a.group or "—",
                str(len(a.citations)),
            )
        console.print(table)
        console.print(
            f"[dim]candidate cells under {out_dir}/assessments/ — review, then promote into "
            "data/hypotheses/ by hand (watermark hypotheses check before committing).[/]"
        )
    elif manifest.proposals:
        table = Table("proposed issue", "labels", "dedupe key")
        for pr in manifest.proposals:
            table.add_row(pr.title, ", ".join(pr.labels), pr.dedupe_key)
        console.print(table)
    else:
        console.print("[yellow]No issue proposals or assessment cells produced.[/]")

    if prov.is_error:
        raise typer.Exit(code=1)

    if recipe == "site-onboard" and manifest.proposals:
        console.print()
        if create_issues:
            _publish_and_create_issues(out_dir, site=settings.site)
        else:
            _write_publish_plan(out_dir, existing=[])
            console.print(
                "[dim]Preview only — no issues opened. Re-run with [bold]--create-issues[/] "
                f"(or [bold]watermark research publish --run {out_dir} --create-issues[/]) "
                "to open them.[/]"
            )


@research_app.command("publish")
def research_publish_cmd(
    run: str = typer.Option(..., "--run", help="Run directory (contains manifest.yaml)."),
    existing: str = typer.Option(
        "",
        "--existing",
        help="JSON file of existing issues (gh issue list --json number,title,body). "
        "Optional: --create-issues fetches open issues automatically if this is omitted.",
    ),
    out: str = typer.Option(
        "", "--out", help="Write the publish plan JSON here (default: <run>/publish-plan.json)."
    ),
    create_issues: bool = typer.Option(
        False,
        "--create-issues",
        help="Open each planned issue on GitHub via gh, deduping against open issues first.",
    ),
) -> None:
    """Build a publish plan from a research run: dedupe its proposals against existing
    issues and render the PR body. Add --create-issues to also open them on GitHub."""
    settings = get_settings()
    run_dir = Path(run)

    if create_issues:
        existing_issues: list[dict[str, Any]] | None = None
        if existing:
            loaded = json.loads(Path(existing).read_text(encoding="utf-8"))
            existing_issues = loaded if isinstance(loaded, list) else []
        _publish_and_create_issues(
            run_dir,
            site=settings.site,
            existing=existing_issues,
            plan_out=Path(out) if out else None,
        )
    else:
        issues: list[dict[str, Any]] = []
        if existing:
            loaded = json.loads(Path(existing).read_text(encoding="utf-8"))
            issues = loaded if isinstance(loaded, list) else []
        _write_publish_plan(run_dir, existing=issues, plan_out=Path(out) if out else None)
