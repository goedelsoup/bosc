"""Tests for the watershed-point onboarding flow (#326).

Hermetic: a synthetic second site (slug-scoped output relpaths) is monkeypatched into the
registry and onboarded against an empty ``tmp_path`` data dir, offline. A brand-new site
has no committed fixtures and no seed data, so the orchestrator must scaffold cleanly and
record each connector step as a non-crashing dry-run/skipped — never raise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from watermark.config import Settings
from watermark.onboard import onboard_site, scaffold_dirs
from watermark.sites import SITES


def _fw(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Register a synthetic Fort-Wayne-shaped site with slug-scoped output paths."""
    fw = SITES["lima"].model_copy(
        update={
            "slug": "fw",
            "place": "Fort Wayne",
            "basin": "maumee",
            "climatology_relpath": "reference/hydrology/fw/nasa-power-climatology.yaml",
            "corridor_ddf_relpath": "reference/hydrology/fw/atlas14-corridor-ddf.yaml",
            "baseline_relpath": "reference/economics/fw/baseline.yaml",
            "rsei_relpath": "reference/rsei/fw/inventory.yaml",
            "consumer_energy_relpath": "reference/eia/fw/consumer-energy.yaml",
            "demand_pressure_relpath": "reference/eia/fw/demand-pressure.yaml",
            "grid_relpath": "reference/eia/fw/grid-profile.yaml",
        }
    )
    monkeypatch.setitem(SITES, "fw", fw)


def _settings(tmp_path: Path) -> Settings:
    # Fully offline (hydro + econ + rsei) with empty fixtures dirs, so every connector misses
    # and records a dry-run — hermetic, no network.
    return Settings(
        site="fw",
        data_dir=tmp_path,
        hydro_offline=True,
        hydro_fixtures_dir=tmp_path / "no-fixtures",
        econ_offline=True,
        econ_fixtures_dir=tmp_path / "no-fixtures",
        rsei_offline=True,
    )


def test_scaffold_creates_per_site_dirs_with_readmes(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    dirs, written = scaffold_dirs(_settings(tmp_path))
    assert set(dirs) == {
        "reference/fw",
        "extracted/fw",
        "reference/hydrology/fw",
        "reference/economics/fw",
        "reference/eia/fw",
        "reference/rsei/fw",
    }
    for rel in dirs:
        readme = tmp_path / rel / "README.md"
        assert readme.is_file()
        assert "Fort Wayne" in readme.read_text(encoding="utf-8")
    assert len(written) == len(dirs)


def test_scaffold_is_idempotent(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    settings = _settings(tmp_path)
    scaffold_dirs(settings)
    # A reviewer's edits to a scaffolded README must survive a re-run.
    edited = tmp_path / "reference" / "fw" / "README.md"
    edited.write_text("EDITED BY A HUMAN\n", encoding="utf-8")
    _, written_again = scaffold_dirs(settings)
    assert written_again == []  # nothing re-written
    assert edited.read_text(encoding="utf-8") == "EDITED BY A HUMAN\n"


def test_onboard_run_is_resilient_offline(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    report = onboard_site(settings=_settings(tmp_path))

    assert report.slug == "fw"
    assert report.place == "Fort Wayne"
    # Scaffold always succeeds; the run never raises despite no fixtures / no seed data.
    names = {s.name: s.status for s in report.steps}
    assert names["scaffold"] == "ok"
    # Every connector step resolved to a recorded, non-fatal status.
    for step in report.steps:
        assert step.status in {"ok", "skipped", "dry-run", "error"}
    # The blocking review gate is always emitted, and never auto-promotes.
    assert any("PROMOTION IS A SEPARATE MANUAL EDIT" in c for c in report.review_checklist)
    assert any("--research" in c for c in report.review_checklist)  # the self-research step


def test_onboard_writes_under_slug_not_lima(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Whatever a connector step would write lands under the slug-scoped path, never Lima's.
    _fw(monkeypatch)
    onboard_site(settings=_settings(tmp_path))
    for lima_path in (
        "reference/hydrology/nasa-power-climatology.yaml",
        "reference/hydrology/atlas14-corridor-ddf.yaml",
        "reference/economics/baseline.yaml",
        "reference/rsei/inventory.yaml",
        "reference/eia/consumer-energy.yaml",
        "reference/eia/grid-profile.yaml",
        "reference/subdivisions/subdivisions.yaml",  # Lima's flat civic registry
    ):
        assert not (tmp_path / lima_path).exists(), lima_path


def test_onboard_writes_living_onboarding_doc(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    onboard_site(settings=_settings(tmp_path))
    doc = tmp_path / "extracted" / "fw" / "ONBOARDING.md"
    assert doc.is_file()
    body = doc.read_text(encoding="utf-8")
    assert "Dimension coverage" in body
    assert "[x] **Hydrology**" in body and "[x] **Economics**" in body
    assert "[ ] **Data-center activity**" in body  # not captured by onboard
    assert "Review gate (blocking)" in body
    # Idempotent: a reviewer's checks survive a re-run.
    doc.write_text(body.replace("[ ] **Data-center", "[x] **Data-center"), encoding="utf-8")
    onboard_site(settings=_settings(tmp_path))
    assert "[x] **Data-center" in doc.read_text(encoding="utf-8")


def test_dry_run_writes_no_onboarding_doc(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    onboard_site(settings=_settings(tmp_path), dry_run=True)
    assert not (tmp_path / "extracted" / "fw" / "ONBOARDING.md").exists()


def test_research_step_only_when_requested(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    # Default: no self-research step.
    report = onboard_site(settings=_settings(tmp_path))
    assert not any(s.name == "self-research" for s in report.steps)
    # --research, but offline (the test settings) -> the step runs and SKIPS cleanly (no key /
    # no network), never an LLM call or a crash.
    report = onboard_site(settings=_settings(tmp_path), research=True)
    research = next(s for s in report.steps if s.name == "self-research")
    assert research.status == "skipped"


def test_dry_run_research_plans_the_step(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    report = onboard_site(settings=_settings(tmp_path), dry_run=True, research=True)
    assert any(s.name == "self-research" and s.status == "dry-run" for s in report.steps)


def test_onboard_refuses_colliding_output_paths(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # The footgun: a profile that copied Lima but did NOT slug-scope its output relpaths would
    # overwrite Lima's committed files. onboard must refuse before writing anything.
    bad = SITES["lima"].model_copy(update={"slug": "bad", "place": "Bad"})  # keeps Lima's relpaths
    monkeypatch.setitem(SITES, "bad", bad)
    with pytest.raises(ValueError, match="not unique"):
        onboard_site(settings=Settings(site="bad", data_dir=tmp_path, hydro_offline=True))
    # Refused before any scaffold write.
    assert not (tmp_path / "reference" / "bad").exists()


def test_dry_run_writes_nothing(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    report = onboard_site(settings=_settings(tmp_path), dry_run=True)
    # Plan is reported, but the filesystem is untouched.
    assert all(s.status == "dry-run" for s in report.steps)
    assert not (tmp_path / "reference" / "fw").exists()
    assert not (tmp_path / "extracted" / "fw").exists()
    # The plan still names the slug-scoped per-site targets (hydrology + economics).
    by_name = {s.name: s for s in report.steps}
    assert (
        by_name["climatology"].output_path == "reference/hydrology/fw/nasa-power-climatology.yaml"
    )
    assert by_name["econ-baseline"].output_path == "reference/economics/fw/baseline.yaml"
    assert by_name["rsei"].output_path == "reference/rsei/fw/inventory.yaml"
    assert by_name["grid-profile"].output_path == "reference/eia/fw/grid-profile.yaml"


def test_civic_scaffold_creates_registry_stub_and_readme(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # The civic step lands an empty, load-clean per-site subdivisions registry + README (#1524).
    _fw(monkeypatch)
    settings = _settings(tmp_path)
    report = onboard_site(settings=settings)

    civic = next(s for s in report.steps if s.name == "civic-registry")
    assert civic.status == "ok"
    assert civic.output_path == "reference/subdivisions/fw/subdivisions.yaml"

    base = tmp_path / "reference" / "subdivisions" / "fw"
    assert (base / "subdivisions.yaml").is_file()
    readme = base / "README.md"
    assert readme.is_file()
    assert "Fort Wayne" in readme.read_text(encoding="utf-8")

    # The stub is load-clean for the active site and starts empty (evidence-gated — no bodies).
    from watermark.civic import load_registry

    reg = load_registry(settings)
    assert reg.meta["site"] == "fw"
    assert reg.subdivisions == []


def test_civic_scaffold_does_not_clobber_curated_registry(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # A reviewer's enumerated bodies must survive a re-run; the step then reports skipped.
    _fw(monkeypatch)
    settings = _settings(tmp_path)
    onboard_site(settings=settings)
    reg_path = tmp_path / "reference" / "subdivisions" / "fw" / "subdivisions.yaml"
    curated = (
        "meta:\n  site: fw\nsubdivisions:\n"
        "  - slug: acme-twp\n    name: Acme Township\n    type: township\n"
    )
    reg_path.write_text(curated, encoding="utf-8")

    report = onboard_site(settings=settings)
    assert reg_path.read_text(encoding="utf-8") == curated  # untouched
    civic = next(s for s in report.steps if s.name == "civic-registry")
    assert civic.status == "skipped"


def test_dry_run_plans_civic_step_without_writing(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    report = onboard_site(settings=_settings(tmp_path), dry_run=True)
    civic = next(s for s in report.steps if s.name == "civic-registry")
    assert civic.status == "dry-run"
    assert civic.output_path == "reference/subdivisions/fw/subdivisions.yaml"
    assert not (tmp_path / "reference" / "subdivisions").exists()


def test_civic_review_item_captured_onto_onboarding_doc(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _fw(monkeypatch)
    report = onboard_site(settings=_settings(tmp_path))
    assert any("subdivisions discover" in c for c in report.review_checklist)
    doc = (tmp_path / "extracted" / "fw" / "ONBOARDING.md").read_text(encoding="utf-8")
    assert "subdivisions discover" in doc  # the checklist item is persisted
    assert "[ ] **Civic records**" in doc  # the dimension-coverage line


@pytest.mark.parametrize(
    ("argv", "expected"),
    [(["onboard", "fw", "--offline"], True), (["onboard", "fw", "--dry-run"], False)],
)
def test_onboard_offline_flag_fans_out_to_every_connector(
    argv: list[str], expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`onboard <slug> --offline` must silence econ + rsei too, not just hydrology (#1367).

    Otherwise the non-hydro reach steps make live Census/BLS/EPA/EIA calls the operator
    explicitly opted out of. Captures the Settings the command hands to onboard_site.
    """
    from typer.testing import CliRunner

    import watermark.catalog.sites as catalog_sites
    import watermark.onboard as onboard_mod
    from watermark.catalog.sites import SiteReadiness
    from watermark.cli import app
    from watermark.onboard import OnboardReport

    _fw(monkeypatch)
    captured: dict[str, Settings] = {}

    def _capture(
        *, settings: Settings, dry_run: bool = False, research: bool = False
    ) -> OnboardReport:
        captured["settings"] = settings
        return OnboardReport(
            slug="fw",
            place="Fort Wayne",
            basin="maumee",
            scaffolded_dirs=[],
            steps=[],
            review_checklist=["review"],
        )

    monkeypatch.setattr(onboard_mod, "onboard_site", _capture)
    monkeypatch.setattr(
        catalog_sites, "readiness", lambda slug, **_kw: SiteReadiness(slug=slug, total=0, present=0)
    )

    result = CliRunner().invoke(app, argv)

    assert result.exit_code == 0, result.output
    s = captured["settings"]
    # All three connector families onboarding touches move together with the one flag.
    assert (s.hydro_offline, s.econ_offline, s.rsei_offline) == (expected, expected, expected)
