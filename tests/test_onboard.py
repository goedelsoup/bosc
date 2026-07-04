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
