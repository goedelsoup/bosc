"""Repeatable watershed-point onboarding (#326, Track 3 of #323).

`onboard_site` brings a registered site from nothing toward a "coming soon" build: it
scaffolds the per-site data dirs (with house-style READMEs), runs the portable reach
connectors for the active site's `SiteProfile` (NWIS-derived basin low-flows [shared],
NOAA Atlas-14 corridor DDF, SSURGO dominant HSG, NASA-POWER climatology), validates the
basin assimilative screen, and returns a report carrying a **blocking review checklist**.

It *proposes*; it never promotes. Flipping a site to `live`/`selectable` in
`web/packages/core/src/sites.ts` stays a separate, human, parity-gated edit.

Preconditions: the site's `SiteProfile` is already registered in `watermark.sites.SITES`
(authoring it is the first step — a code edit). Per-site point outputs (climatology, corridor
DDF) are slug-scoped via the profile so onboarding never clobbers Lima; basin-level outputs
(derived 7Q10, ECHO POTW inventory) are shared across Maumee sites by design.

The self-research first pass (Track 2, #247) is wired as the opt-in ``research`` step: the
discipline-bound agent investigates the new site and writes a proposal artifact under
``data/research/`` for human triage — see `docs/onboarding.md`.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal, NamedTuple

from pydantic import BaseModel, ConfigDict

from watermark import rsei
from watermark.config import Settings, get_settings
from watermark.connectors import OfflineError
from watermark.economics import baseline as econ_baseline
from watermark.economics import energy as econ_energy
from watermark.grid import utility as grid_utility
from watermark.hsg import normalize_hsg
from watermark.hydrology import basin, climate, drainage
from watermark.hydrology.connectors.nasa_power import fetch_climatology
from watermark.hydrology.connectors.ssurgo import dominant_hsg
from watermark.logging import get_logger
from watermark.sites import SiteProfile, active_profile, output_path_collisions

log = get_logger(__name__)

StepStatus = Literal["ok", "skipped", "dry-run", "error"]


class OnboardStep(BaseModel):
    """One step of an onboarding run + its outcome."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: StepStatus
    detail: str
    output_path: str | None = None  # data_dir-relative when a file was written


class OnboardReport(BaseModel):
    """The result of an onboarding run: what ran, what landed, and what to review."""

    model_config = ConfigDict(extra="forbid")

    slug: str
    place: str
    basin: str
    scaffolded_dirs: list[str]  # data_dir-relative
    steps: list[OnboardStep]
    review_checklist: list[str]


def _readme_body(place: str, slug: str, basin: str, purpose: str, source: str) -> str:
    """House-style README for a scaffolded per-site dir (source + gaps + regenerate).

    ``source`` names the folder's actual provenance chain — it differs per dir (the eia
    folder is EIA/RTO, the rsei folder is EPA RSEI, …), so a scaffolded README documents
    its own dataset origin per the ``data/reference/**`` source-and-gaps rule.
    """
    return (
        f"# {place} ({slug}) — {purpose}\n\n"
        f"Per-site onboarding tree for the {place} watershed point (basin: {basin}), "
        f"scaffolded by `watermark onboard {slug}` (#326). Values come from the portable onboard "
        f"connectors keyed to this site's `SiteProfile` in `watermark.sites` — nothing here is "
        f"fabricated; regenerate, don't hand-edit.\n\n"
        "## Source\n\n"
        f"`watermark onboard {slug}` over the {place} `SiteProfile` — {source}.\n\n"
        "## Known gaps & caveats\n\n"
        "- Onboarding seed — **review every value against a cited source before promotion** "
        "(`web/packages/core/src/sites.ts` `status`/`selectable`, parity-gated).\n"
        "- County/City parcel & zoning GIS is jurisdiction-specific and is **not** populated "
        "by the portable reach connectors — it needs a per-jurisdiction connector "
        "(see `docs/onboarding.md`).\n\n"
        "## Regenerate\n\n"
        f"`watermark onboard {slug}`  (or the per-connector commands: `derive-low-flows`, "
        "`nasa-power --write`, etc.)\n"
    )


def _civic_registry_stub(prof: SiteProfile) -> str:
    """An empty, load-clean subdivisions-registry stub for a newly onboarded site (#1524).

    ``meta.site`` + an empty ``subdivisions: []`` — the minimum ``civic.load_registry`` accepts,
    so ``watermark --site <slug> subdivisions discover`` runs against it immediately (an empty
    body list, not a crash). The county's meeting-holding bodies are enumerated here BY HAND from
    a committed county roster (the grounded facts); discovery only fills the ``publishing:`` block.
    """
    return (
        f"# {prof.place} ({prof.slug}) — political-subdivision public-meeting records registry.\n"
        f"# Scaffolded empty by `watermark onboard {prof.slug}` (#1524). Enumerate this site's\n"
        "# meeting-holding bodies BELOW from a committed county roster (grounded facts:\n"
        "# name/type/governing_body/meeting_schedule/office, each with `grounded_from`), then run\n"
        f"# `watermark --site {prof.slug} subdivisions discover` and fold the confirmed\n"
        "# `publishing:` platforms in BY HAND — discovery is read-only (see civic/CLAUDE.md).\n"
        "# An empty registry is honest: it does NOT make the record/story domains live.\n"
        "meta:\n"
        f"  site: {prof.slug}\n"
        f"  subject: {prof.place} political subdivisions — public-meeting records registry\n"
        "  description: >-\n"
        f"    Meeting-holding bodies for the {prof.place} watershed point, each with the verbatim\n"
        "    governing-body meeting cadence and contact carried in a committed county roster, plus\n"
        "    a `publishing:` block recording where the body posts its minutes/agendas online. The\n"
        "    grounded roster facts are immutable source; the `publishing:` block is filled by the\n"
        "    read-only discovery pass and carries its own `discovered:` provenance. Empty until\n"
        "    the bodies are enumerated by hand.\n"
        "  grounded_sources: []\n"
        "subdivisions: []\n"
    )


def _civic_readme_body(prof: SiteProfile) -> str:
    """House-style README for the scaffolded per-site subdivisions registry dir (#1524).

    Unlike the connector-output READMEs (``_readme_body``, "regenerate, don't hand-edit"), the
    civic registry is **hand-curated**: grounded facts are transcribed verbatim from committed
    county rosters and the ``publishing:`` block is folded in by hand from the read-only
    discovery pass. So this documents that curation contract, not a regenerate command.
    """
    slug, place = prof.slug, prof.place
    return (
        f"# {place} ({slug}) — subdivision meeting-records registry\n\n"
        f"Per-site registry of {place}'s meeting-holding bodies (townships, municipalities, "
        "meeting-holding special districts) and **where each publishes its minutes/agendas "
        f"online**. Scaffolded empty by `watermark onboard {slug}` (#1524); read per active site "
        "by `watermark.civic` (`registry_path`). This peer slug-scopes under "
        f"`subdivisions/{slug}/`; Lima (the reference build) keeps the flat legacy path.\n\n"
        "## Source\n\n"
        "Hand-curated, not connector-generated. **Grounded** fields "
        "(`name`/`type`/`governing_body`/`meeting_schedule`/`office`) are transcribed **verbatim** "
        f"from a committed {place}-area county-published roster named in `meta.grounded_sources` "
        "(`grounded_from` per body) — never from outside knowledge. **Discovered** fields "
        "(`publishing.*`) are a live-web finding with their own `publishing.discovered:` "
        f"provenance, folded in BY HAND from `watermark --site {slug} subdivisions discover` "
        "(read-only; it never rewrites this file).\n\n"
        "## Known gaps & caveats\n\n"
        "- **Scaffolded empty** — enumerate the county's bodies before promotion. An empty "
        'registry is honest, never a finding of "publishes nothing."\n'
        "- `publishing.platform: unknown` = *not yet looked*, never *publishes nothing*; a null "
        "`records_url` is never evidence of withholding.\n"
        "- An empty/seeded registry does **not** flip the `record`/`story` readiness domains "
        "live (#1220) — those rise only when meetings are actually ingested and summarized.\n\n"
        "## Populate\n\n"
        "Enumerate bodies by hand from a committed roster, then "
        f"`watermark --site {slug} subdivisions discover` and fold the confirmed platforms in. "
        "See `docs/onboarding.md` and `src/watermark/civic/CLAUDE.md`.\n"
    )


def scaffold_dirs(settings: Settings, *, dry_run: bool = False) -> tuple[list[str], list[str]]:
    """Create the per-site data dirs + a README in each (idempotent).

    Returns ``(dirs, readmes_to_write)`` as data_dir-relative paths; an existing README is
    left untouched. With ``dry_run`` nothing is created — it just reports what *would* land.
    """
    prof = active_profile(settings)
    slug = prof.slug
    # Each dir carries its OWN provenance chain in its README (the data/reference/** source-and-
    # gaps rule) — the eia folder is EIA/RTO, rsei is EPA RSEI, etc., not the hydrology connectors.
    targets: list[tuple[Path, str, str]] = [
        (
            settings.data_dir / "reference" / slug,
            "reference data",
            "per-site authored reference inputs + per-jurisdiction connectors (site geometry, "
            "parcels/zoning)",
        ),
        (
            settings.data_dir / "extracted" / slug,
            "extractions",
            "the ingest→extract corpus pipeline over this site's source documents",
        ),
        (
            settings.data_dir / "reference" / "hydrology" / slug,
            "hydrology connector outputs",
            "USGS NWIS (7Q10) · NOAA Atlas-14 (corridor DDF) · USDA NRCS SSURGO (dominant HSG) · "
            "NASA-POWER (climatology)",
        ),
        (
            settings.data_dir / "reference" / "economics" / slug,
            "economics baseline outputs",
            "US Census · BLS QCEW (county economic baseline)",
        ),
        (
            settings.data_dir / "reference" / "eia" / slug,
            "energy / grid outputs",
            "EIA-861 (utility retail) · EIA-930 (RTO demand/mix) · EIA v2 API (consumer energy "
            "prices)",
        ),
        (
            settings.data_dir / "reference" / "rsei" / slug,
            "RSEI toxics outputs",
            "EPA RSEI (county toxics release inventory)",
        ),
    ]
    dirs: list[str] = []
    written: list[str] = []
    for path, purpose, source in targets:
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)
        dirs.append(str(path.relative_to(settings.data_dir)))
        readme = path / "README.md"
        if not readme.is_file():
            if not dry_run:
                readme.write_text(
                    _readme_body(prof.place, slug, prof.basin, purpose, source), encoding="utf-8"
                )
            written.append(str(readme.relative_to(settings.data_dir)))
    return dirs, written


def _rel(settings: Settings, path: Path) -> str:
    """data_dir-relative string for a written output (falls back to the full path)."""
    try:
        return str(path.relative_to(settings.data_dir))
    except ValueError:
        return str(path)


def _run_step(name: str, fn: Callable[[], OnboardStep]) -> OnboardStep:
    """Run one connector step, turning the expected failure modes into a recorded status.

    A brand-new site has no committed fixtures, so an offline miss is a `dry-run` (naming the
    key to record), a missing input file is `skipped`, and anything else is a non-fatal
    `error` — onboarding always completes and reports.
    """
    try:
        return fn()
    except OfflineError as exc:  # any connector's offline miss (hydro + econ)
        return OnboardStep(name=name, status="dry-run", detail=f"offline — record fixture: {exc}")
    except FileNotFoundError as exc:
        return OnboardStep(name=name, status="skipped", detail=f"input missing: {exc}")
    except Exception as exc:  # report, never crash the run
        log.warning("onboard.step_failed", step=name, error=str(exc).splitlines()[0])
        return OnboardStep(name=name, status="error", detail=str(exc).splitlines()[0])


def _guard_output_paths(slug: str) -> None:
    """Refuse to onboard if this site's per-site outputs would overwrite another site's.

    The #326 design slug-scopes the point-specific outputs so onboarding never clobbers
    Lima; this is the guard for a profile that copied another site without re-scoping them.
    """
    clashes = output_path_collisions(slug)
    if clashes:
        detail = "; ".join(f"{field} collides with {others}" for field, others in clashes.items())
        raise ValueError(
            f"{slug}: per-site output paths are not unique ({detail}). Slug-scope "
            f"climatology_relpath/corridor_ddf_relpath (e.g. reference/hydrology/{slug}/…) in the "
            "SiteProfile so onboarding doesn't overwrite another site's committed data."
        )


def onboard_site(
    *, settings: Settings | None = None, dry_run: bool = False, research: bool = False
) -> OnboardReport:
    """Onboard the active site (``settings.site``): scaffold + reach connectors + validation.

    With ``dry_run`` nothing is written — it resolves and reports the plan (steps + target
    output paths) so the first run on a cohort site can be previewed safely. With ``research``
    the discipline-bound agent (#247) runs a self-research first pass over the new site and
    writes a proposal artifact for human triage (a paid/online call; opt-in).
    """
    settings = settings or get_settings()
    prof = active_profile(settings)
    _guard_output_paths(prof.slug)  # before any write

    dirs, readmes = scaffold_dirs(settings, dry_run=dry_run)
    verb = "would create" if dry_run else "created"
    steps: list[OnboardStep] = [
        OnboardStep(
            name="scaffold",
            status="dry-run" if dry_run else "ok",
            detail=f"{verb} {len(dirs)} dir(s); {len(readmes)} README(s)",
        )
    ]
    steps += (
        _planned_steps(settings, prof, research)
        if dry_run
        else _executed_steps(settings, prof, research)
    )

    report = OnboardReport(
        slug=prof.slug,
        place=prof.place,
        basin=prof.basin,
        scaffolded_dirs=dirs,
        steps=steps,
        review_checklist=_review_checklist(prof.slug),
    )
    # Persist the gate as a living, checkable artifact (only if absent — preserve human checks).
    if not dry_run:
        doc = settings.data_dir / "extracted" / prof.slug / "ONBOARDING.md"
        if not doc.is_file():
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(render_onboarding_doc(report), encoding="utf-8")
    return report


def _autolink_urls(cell: str) -> str:
    """Wrap bare URLs in a run-table cell as ``<...>`` autolinks (markdownlint MD034).

    An errored step's detail is the raw exception message, which for an HTTP failure embeds
    the endpoint URL — a bare URL in a table cell trips MD034 in the committed ONBOARDING.md.
    Excludes ``|`` so a URL can never split the table cell.
    """
    return re.sub(r"(?<![<(])(https?://[^\s'\"<>|]+)", r"<\1>", cell)


def render_onboarding_doc(report: OnboardReport) -> str:
    """The living onboarding record: dimension coverage + the last run + the review gate."""
    rows = "\n".join(
        f"| {s.name} | {s.status} | {_autolink_urls(s.output_path or s.detail)} |"
        for s in report.steps
    )
    gate = "\n".join(f"- [ ] {item}" for item in report.review_checklist)
    return (
        f"# Onboarding — {report.place} ({report.slug})\n\n"
        f"Living record for the {report.place} watershed point (basin: {report.basin}), "
        "scaffolded by `watermark onboard`. Check items as you complete them; the site is **not** "
        "promoted (`web/packages/core/src/sites.ts` `status`/`selectable`) until the gate is clear.\n\n"
        "## Dimension coverage\n\n"
        "- [x] **Hydrology** — onboard reach connectors (low-flows, corridor DDF, SSURGO HSG, climatology)\n"
        "- [x] **Economics** — county baseline, RSEI toxics, consumer energy, grid profile\n"
        "- [ ] **Data-center activity** — extracted permits/records + entity graph "
        "(corpus extraction; seed proposals via `watermark onboard --research`, #247)\n"
        "- [ ] **Civic records** — per-site subdivisions registry + meeting minutes/agendas "
        "(feeds record/story; scaffolded empty, evidence-gated)\n"
        "- [ ] **Per-jurisdiction GIS** — parcels/zoning connector (the known lift; see docs/onboarding.md)\n\n"
        "## Last onboard run\n\n"
        "| step | status | output |\n|---|---|---|\n" + rows + "\n\n"
        "## Review gate (blocking)\n\n" + gate + "\n"
    )


def _exec_low_flows(settings: Settings) -> OnboardStep:
    # NWIS -> basin-derived 7Q10 (basin-level, SHARED across Maumee sites).
    path = basin.write_derived_low_flows(
        basin.derive_basin_low_flows(settings=settings), settings=settings
    )
    return OnboardStep(
        name="derive-low-flows",
        status="ok",
        detail="basin-level (shared across Maumee sites)",
        output_path=_rel(settings, path),
    )


def _exec_ddf(settings: Settings) -> OnboardStep:
    # NOAA Atlas-14 -> corridor DDF (per-site).
    path = drainage.write_corridor_ddf(
        drainage.build_corridor_ddf(settings=settings), settings=settings
    )
    return OnboardStep(
        name="corridor-ddf", status="ok", detail="per-site", output_path=_rel(settings, path)
    )


def _exec_hsg(settings: Settings, prof: SiteProfile) -> OnboardStep:
    # SSURGO dominant HSG over the parcel-assemblage geometry (inline; no committed output — a
    # validation read). The geometry source is parcels_relpath (a GeoJSON), not footprint_relpath
    # (the stormwater-acreage YAML): dominant_hsg grid-samples polygon features, so it needs the
    # parcel polygons. A coming-soon site has no committed parcel geometry yet -> skipped.
    geometry = settings.data_dir / prof.parcels_relpath
    if not geometry.is_file():
        # Record the data_dir-relative path, never an absolute machine path (the report is
        # committed as ONBOARDING.md).
        return OnboardStep(
            name="ssurgo-hsg",
            status="skipped",
            detail=f"parcel geometry missing: {prof.parcels_relpath}",
        )
    survey = dominant_hsg(geometry, settings=settings)
    # Compare the survey's group to the profile VERBATIM: a profile that answered "C" to a
    # surveyed "C/D" has pre-collapsed the dual rating to its drained letter, which is exactly
    # the low-runoff choice the scenario switch exists to make visible (WS-20 / #1620).
    match = (
        "matches profile"
        if normalize_hsg(survey.dominant_hsg) == normalize_hsg(prof.dominant_hsg)
        else (f"DIFFERS from profile {prof.dominant_hsg!r} — update SiteProfile with a citation")
    )
    if survey.dominant_is_dual:
        match += (
            f" (dual group: drained {survey.letter_for('drained')} / undrained "
            f"{survey.letter_for('undrained')}; record it verbatim and let "
            "pre_drainage_condition/post_drainage_condition resolve it)"
        )
    return OnboardStep(name="ssurgo-hsg", status="ok", detail=f"HSG {survey.dominant_hsg}; {match}")


def _exec_climate(settings: Settings) -> OnboardStep:
    # NASA-POWER climatology (per-site).
    path = climate.write_climatology(fetch_climatology(settings=settings), settings=settings)
    return OnboardStep(
        name="climatology", status="ok", detail="per-site", output_path=_rel(settings, path)
    )


def _exec_screen(settings: Settings) -> OnboardStep:
    # basin-screen — validation only (read-only over the shared basin inventory).
    scr = basin.check_basin_assimilative(settings=settings)
    c = scr.coverage
    return OnboardStep(
        name="basin-screen",
        status="ok" if c.total else "skipped",
        detail=f"{c.screened}/{c.total} dischargers screened ({c.violations} violations, {c.tight} tight)",
    )


def _exec_baseline(settings: Settings) -> OnboardStep:
    # Census+QCEW county baseline (per county FIPS).
    path = econ_baseline.write_baseline(
        econ_baseline.build_baseline(settings=settings), settings=settings
    )
    return OnboardStep(
        name="econ-baseline",
        status="ok",
        detail="per-site (county FIPS)",
        output_path=_rel(settings, Path(path)),
    )


def _exec_rsei(settings: Settings) -> OnboardStep:
    # EPA RSEI county toxics inventory (per county FIPS).
    inv = rsei.build_inventory(settings)
    path = rsei.write_inventory(inv, rsei.inventory_path(settings).parent)
    return OnboardStep(
        name="rsei", status="ok", detail="per-site (county FIPS)", output_path=_rel(settings, path)
    )


def _exec_consumer_energy(settings: Settings) -> OnboardStep:
    # EIA consumer energy prices (per state).
    path = econ_energy.write_consumer_energy(
        econ_energy.build_consumer_energy(settings=settings), settings=settings
    )
    return OnboardStep(
        name="consumer-energy",
        status="ok",
        detail="per-site (state)",
        output_path=_rel(settings, Path(path)),
    )


def _exec_demand_pressure(settings: Settings, prof: SiteProfile) -> OnboardStep:
    # Facility demand→consumer-price-pressure sensitivity (#1105) — needs a derivable power basis.
    if not prof.has_facility_power_basis:
        return OnboardStep(
            name="demand-pressure",
            status="skipped",
            detail="no disclosed facility, or its IT load is entirely [open]",
        )
    pressure = econ_energy.derive_demand_pressure(settings=settings)
    path = econ_energy.write_demand_pressure(pressure, settings=settings)
    return OnboardStep(
        name="demand-pressure",
        status="ok",
        detail="per-site (facility load vs state EIA sales)",
        output_path=_rel(settings, Path(path)),
    )


def _exec_grid(settings: Settings) -> OnboardStep:
    # EIA-861 utility + grid profile (per utility; sparse without a documented facility load).
    path = grid_utility.write_grid_profile(
        grid_utility.derive_grid_profile(settings=settings), settings=settings
    )
    return OnboardStep(
        name="grid-profile",
        status="ok",
        detail="per-site (utility)",
        output_path=_rel(settings, Path(path)),
    )


def _exec_civic_scaffold(settings: Settings, prof: SiteProfile) -> OnboardStep:
    """Scaffold the per-site subdivisions registry stub + README (idempotent, #1524).

    Gives a newly onboarded site an empty, ready-to-fill civic registry
    (``data/reference/subdivisions/<slug>/subdivisions.yaml`` — ``meta.site`` + ``subdivisions:
    []``) and a house-style README, so it has a place to declare its meeting-holding bodies and
    a prompt to discover them. Resolves the path through ``civic.registry_path`` (not a hardcoded
    slug), so a peer slug-scopes and the reference build keeps its flat legacy layout. Never
    clobbers a curated registry: an existing registry (or README) is left untouched. Scaffolding
    an empty registry does NOT flip the ``record``/``story`` readiness domains live (#1220) —
    those rise only when meetings are actually ingested and summarized.
    """
    from watermark.civic.registry import registry_path

    path = registry_path(settings)
    readme = path.parent / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrote: list[str] = []
    if not path.is_file():
        path.write_text(_civic_registry_stub(prof), encoding="utf-8")
        wrote.append("registry")
    if not readme.is_file():
        readme.write_text(_civic_readme_body(prof), encoding="utf-8")
        wrote.append("README")
    if not wrote:
        return OnboardStep(
            name="civic-registry",
            status="skipped",
            detail="registry already present (curated — not clobbered)",
            output_path=_rel(settings, path),
        )
    return OnboardStep(
        name="civic-registry",
        status="ok",
        detail=f"empty stub ({', '.join(wrote)}) — enumerate bodies + discover",
        output_path=_rel(settings, path),
    )


class _StepSpec(NamedTuple):
    """One onboard reach step: the dry-run plan (detail + target path) and the real executor."""

    name: str
    planned_detail: str
    planned_path: str | None
    execute: Callable[[], OnboardStep]


def _step_specs(settings: Settings, prof: SiteProfile, research: bool) -> list[_StepSpec]:
    """The onboard reach steps in order — the single source of truth for both the dry-run plan
    and the real run, so the two can't silently drift (#604). ``planned_detail``/``planned_path``
    describe the step before it runs; ``execute`` runs the connector and reports its real outcome.
    """
    from watermark.civic.registry import registry_path

    specs = [
        _StepSpec(
            "civic-registry",
            "per-site subdivisions registry stub (empty; evidence-gated — no domain flip)",
            _rel(settings, registry_path(settings)),
            lambda: _exec_civic_scaffold(settings, prof),
        ),
        _StepSpec(
            "derive-low-flows",
            "basin-level (shared across Maumee sites)",
            "reference/hydrology/low-flow-7q10.derived.yaml",
            lambda: _exec_low_flows(settings),
        ),
        _StepSpec(
            "corridor-ddf", "per-site", prof.corridor_ddf_relpath, lambda: _exec_ddf(settings)
        ),
        _StepSpec(
            "ssurgo-hsg",
            f"would read footprint {prof.footprint_relpath}",
            None,
            lambda: _exec_hsg(settings, prof),
        ),
        _StepSpec(
            "climatology", "per-site", prof.climatology_relpath, lambda: _exec_climate(settings)
        ),
        _StepSpec("basin-screen", "validation (read-only)", None, lambda: _exec_screen(settings)),
        # economics dimension (per-site outputs)
        _StepSpec(
            "econ-baseline",
            "per-site (county FIPS)",
            prof.baseline_relpath,
            lambda: _exec_baseline(settings),
        ),
        _StepSpec(
            "rsei", "per-site (county FIPS)", prof.rsei_relpath, lambda: _exec_rsei(settings)
        ),
        _StepSpec(
            "consumer-energy",
            "per-site (state)",
            prof.consumer_energy_relpath,
            lambda: _exec_consumer_energy(settings),
        ),
        _StepSpec(
            "demand-pressure",
            "per-site (facility-gated; skipped without a derivable facility load basis)",
            prof.demand_pressure_relpath if prof.has_facility_power_basis else None,
            lambda: _exec_demand_pressure(settings, prof),
        ),
        _StepSpec(
            "grid-profile",
            "per-site (utility; sparse without a documented facility)",
            prof.grid_relpath,
            lambda: _exec_grid(settings),
        ),
    ]
    if research:
        specs.append(
            _StepSpec(
                "self-research",
                "discipline-bound agent first pass (paid/online)",
                f"research/<{prof.slug}-run>/",
                lambda: _research_step(settings, prof),
            )
        )
    return specs


def _planned_steps(settings: Settings, prof: SiteProfile, research: bool) -> list[OnboardStep]:
    """The connector steps a real run *would* take — target paths, no side effects."""
    return [
        OnboardStep(
            name=s.name, status="dry-run", detail=s.planned_detail, output_path=s.planned_path
        )
        for s in _step_specs(settings, prof, research)
    ]


def _research_step(settings: Settings, prof: SiteProfile) -> OnboardStep:
    """Run the discipline-bound self-research first pass over the new site (#247 seam).

    A paid/online LLM call — skipped cleanly when there's no key or the run is offline. The
    agent proposes (a manifest under data/research/<slug>-<date>/ for human triage); it never
    promotes or writes to the corpus.
    """
    if settings.hydro_offline or not settings.anthropic_api_key:
        why = "offline" if settings.hydro_offline else "no ANTHROPIC_API_KEY"
        return OnboardStep(name="self-research", status="skipped", detail=why)

    from datetime import UTC, datetime

    from watermark.agent.client import ResearchAgent
    from watermark.research import run_research, run_slug, write_run

    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    topic = (
        f"onboard {prof.slug} ({prof.place}): data-center activity + receiving-water screen "
        "for a new watershed-point site"
    )
    agent = ResearchAgent(settings=settings, max_turns=settings.research_max_turns)
    manifest = asyncio.run(
        run_research(
            topic,
            generated_at=generated_at,
            settings=settings,
            agent=agent,
            max_proposals=settings.research_max_proposals,
        )
    )
    out_dir = settings.research_dir / run_slug(topic, generated_at)
    write_run(manifest, out_dir, settings=settings)
    return OnboardStep(
        name="self-research",
        status="ok",
        detail=f"{len(manifest.proposals)} proposal(s) — triage",
        output_path=_rel(settings, out_dir),
    )


def _executed_steps(settings: Settings, prof: SiteProfile, research: bool) -> list[OnboardStep]:
    """Run the reach connectors for real, each resilient to an offline/missing-input miss."""
    return [_run_step(s.name, s.execute) for s in _step_specs(settings, prof, research)]


def _review_checklist(slug: str) -> list[str]:
    """The blocking, human review gate before a site can be promoted."""
    return [
        "Every written reference value is reviewed against a cited source (no fabricated values).",
        "SSURGO dominant HSG matches the profile, or the SiteProfile is updated with a citation.",
        "basin-screen coverage is sane for this site's receiving waters.",
        "A per-jurisdiction County/City GIS connector exists (the known lift — see docs/onboarding.md).",
        f"Civic registry: enumerate the county's meeting-holding bodies for {slug!r} from a "
        f"committed roster into data/reference/subdivisions/{slug}/subdivisions.yaml; run "
        f"`watermark --site {slug} subdivisions discover` and fold confirmed platforms in BY HAND "
        "(discovery is read-only). An empty registry does not make record/story live.",
        "Self-research first pass reviewed (run with --research; triage data/research/<slug>-<date>/).",
        f"PROMOTION IS A SEPARATE MANUAL EDIT: flip status->live + selectable->true for {slug!r} in "
        "web/packages/core/src/sites.ts, parity-gated. onboard never auto-promotes; only one live build "
        "(/bosc) exists today.",
    ]
