"""AERMOD engine integration (Tier-1, #1178): deck generation + output parsing.

Hermetic. The deck builders read the committed Lima permit extraction (per-engine certified
rates) via the emissions loader; the plotfile parser reads a committed sample. The end-to-end
run test skips unless a real AERMOD binary is located — the engine degrades gracefully when
it isn't (mirroring the SWMM tests).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from watermark.air.aermod import engine, inp
from watermark.air.aermod.model import (
    AermodControl,
    AermodSource,
    ReceptorGrid,
    lb_per_hr_to_g_per_s,
)
from watermark.air.aermod.screening import build_screening_deck
from watermark.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]
_PLT = REPO_ROOT / "tests" / "fixtures" / "air" / "aermod" / "sample.annual.plt"


@pytest.fixture
def air_settings() -> Settings:
    """Lima, offline: permit + AP-42 read from committed data; no AERMOD binary configured."""
    return Settings(data_dir=REPO_ROOT / "data", aermod_bin="")


# --- stack geometry provenance discipline -------------------------------------------


def test_assumed_stack_params_are_all_assumption() -> None:
    """The permit redacts engine specs — screening geometry must never claim to be documented."""
    stack = inp.assumed_stack_params()
    assert stack.all_assumption
    for v in (stack.height_m, stack.diameter_m, stack.exit_velocity_ms, stack.exit_temp_k):
        assert v.source == "assumption"
        assert "CBI" in (v.citation or "") or "redact" in (v.citation or "")


# --- emission-rate conversion + point source ----------------------------------------


def test_lb_per_hr_to_g_per_s_conversion() -> None:
    # 1 lb/hr = 453.59237 g / 3600 s ≈ 0.125998 g/s
    assert lb_per_hr_to_g_per_s(1.0) == pytest.approx(0.125998, rel=1e-4)
    assert lb_per_hr_to_g_per_s(75.78) == pytest.approx(9.5481, rel=1e-4)


def test_genset_point_source_grounds_rate_assumes_geometry() -> None:
    src = inp.genset_point_source(
        src_id="GEN1",
        pollutant="NOx",
        per_engine_lb_per_hr=75.78,
        rate_citation="permit per-engine NOx at load",
    )
    assert src.emission_g_s.source == "derived"
    assert src.emission_g_s.value == pytest.approx(9.5481, rel=1e-4)
    assert src.stack.all_assumption  # geometry stays assumption even with a grounded rate


# --- deck generation ----------------------------------------------------------------


def _source() -> AermodSource:
    return inp.genset_point_source(
        src_id="GEN1", pollutant="NOx", per_engine_lb_per_hr=75.78, rate_citation="permit"
    )


def test_control_pathway_structure() -> None:
    text = inp.control_pathway(AermodControl(pollutant="NOx", averaging_periods=("1", "ANNUAL")))
    assert text.startswith("CO STARTING")
    assert text.endswith("CO FINISHED")
    assert "CO MODELOPT  DFAULT CONC FLAT" in text
    assert "CO AVERTIME  1 ANNUAL" in text
    assert "CO POLLUTID  NOX" in text
    assert "CO RUNORNOT  RUN" in text


def test_source_pathway_srcparam_order_and_values() -> None:
    text = inp.source_pathway([_source()])
    assert "SO LOCATION  GEN1  POINT  0 0 0" in text
    # SRCPARAM order: rate(g/s) height(m) temp(K) velocity(m/s) diameter(m)
    srcparam = next(ln for ln in text.splitlines() if ln.startswith("SO SRCPARAM"))
    assert srcparam.startswith("SO SRCPARAM  GEN1  9.5481")  # ~9.548 g/s
    assert srcparam.endswith(" 10 720 40 0.6")  # assumed geometry tail
    assert "SO SRCGROUP  ALL" in text


def test_receptor_pathway_gridcart() -> None:
    grid = ReceptorGrid.centered(half_extent_m=500.0, spacing_m=250.0)
    assert grid.nx == 5 and grid.ny == 5  # -500..500 step 250 -> 5 points
    text = inp.receptor_pathway(grid)
    assert "RE GRIDCART GRID1 STA" in text
    assert "RE GRIDCART GRID1 XYINC -500 5 250 -500 5 250" in text
    assert "RE GRIDCART GRID1 END" in text


def test_build_aermod_inp_has_all_five_pathways() -> None:
    text = inp.build_aermod_inp(
        control=AermodControl(),
        sources=[_source()],
        grid=ReceptorGrid.centered(half_extent_m=500.0, spacing_m=250.0),
        surface_file="canned.sfc",
        profile_file="canned.pfl",
    )
    for pathway in ("CO STARTING", "SO STARTING", "RE STARTING", "ME STARTING", "OU STARTING"):
        assert pathway in text
    assert "ME SURFFILE  canned.sfc" in text
    assert "OU PLOTFILE  1 ALL FIRST  1.plt" in text


def test_unsupported_averaging_period_rejected() -> None:
    # The AveragePeriod literal guards the model boundary — an unknown token can't be built.
    with pytest.raises(ValueError, match="24"):
        AermodControl(averaging_periods=("2",))  # type: ignore[arg-type]


def test_empty_source_pathway_rejected() -> None:
    with pytest.raises(ValueError, match="at least one source"):
        inp.source_pathway([])


# --- screening deck: emissions inventory -> dispersion deck --------------------------


def test_build_screening_deck_uses_permit_nox_rate(air_settings: Settings) -> None:
    result = build_screening_deck(pollutant="NOx", settings=air_settings)
    assert result is not None
    text, plotfiles = result
    # Permit NOx at >25% load = 75.78 lb/hr -> ~9.548 g/s in the SRCPARAM line.
    srcparam = next(ln for ln in text.splitlines() if ln.startswith("SO SRCPARAM"))
    assert srcparam.startswith("SO SRCPARAM  GEN1  9.5481")
    assert set(plotfiles) == {"1", "ANNUAL"}
    assert "CO POLLUTID  NOX" in text


# --- plotfile parsing ---------------------------------------------------------------


def test_parse_plotfile_reads_all_receptors() -> None:
    recs = engine.parse_plotfile(_PLT.read_text(), ave_period="ANNUAL")
    assert len(recs) == 8  # 8 data rows, comment/header lines skipped
    peak = max(recs, key=lambda r: r.conc)
    assert peak.conc == pytest.approx(2.3187)
    assert (peak.x_m, peak.y_m) == (500.0, 0.0)
    assert all(r.ave_period == "ANNUAL" and r.group == "ALL" for r in recs)


# --- graceful degradation (no binary) -----------------------------------------------


def test_engine_unavailable_without_binary(air_settings: Settings) -> None:
    assert engine.aermod_bin(air_settings) is None
    assert engine.aermod_available(air_settings) is False
    assert engine.engine_version(air_settings) == ""


def test_run_degrades_when_binary_absent(air_settings: Settings) -> None:
    res = engine.run(
        "CO STARTING\nCO FINISHED\n",
        met_files={},
        plotfiles={"ANNUAL": "annual.plt"},
        settings=air_settings,
    )
    assert res.available is False
    assert res.max_conc == {}
    assert "unavailable" in res.note


@pytest.mark.parametrize("bad", ["../escape.sfc", "/etc/passwd", "sub/../../x.sfc"])
def test_scratch_path_rejects_escaping_met_file_names(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="escapes the scratch dir"):
        engine._scratch_path(tmp_path, bad)


def test_scratch_path_allows_safe_relative_names(tmp_path: Path) -> None:
    assert engine._scratch_path(tmp_path, "canned.sfc").parent == tmp_path.resolve()


def test_run_degrades_on_timeout(monkeypatch: pytest.MonkeyPatch, air_settings: Settings) -> None:
    # A fake located binary + a subprocess that times out: run() must return a structured
    # AermodResult, not let TimeoutExpired escape the graceful-degradation path.
    monkeypatch.setattr(engine, "aermod_bin", lambda *_a, **_k: Path("/usr/bin/true"))

    def _raise(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="aermod", timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise)
    res = engine.run(
        "CO STARTING\nCO FINISHED\n",
        met_files={},
        plotfiles={"ANNUAL": "annual.plt"},
        pollutant="NOx",
        timeout_s=1,
        settings=air_settings,
    )
    assert res.available is True
    assert res.pollutant == "NOx"
    assert "timed out" in res.note


# --- end-to-end (skipped unless a real AERMOD binary is present) ---------------------


@pytest.mark.skipif(
    not engine.aermod_available(), reason="AERMOD binary not located (vendored Fortran build)"
)
def test_end_to_end_screening_run() -> None:  # pragma: no cover - needs the vendored binary
    settings = Settings(data_dir=REPO_ROOT / "data")
    built = build_screening_deck(pollutant="NOx", settings=settings)
    assert built is not None
    inp_text, plotfiles = built
    met_dir = REPO_ROOT / "tests" / "fixtures" / "air" / "aermod"
    sfc, pfl = met_dir / "canned.sfc", met_dir / "canned.pfl"
    if not (sfc.is_file() and pfl.is_file()):
        # AERMET-processed met is #1179; without a validated canned pair there's nothing
        # to feed a real run. Don't fabricate a met file we can't validate.
        pytest.skip("canned AERMET met fixture not present (#1179)")
    met_files = {"canned.sfc": sfc.read_text(), "canned.pfl": pfl.read_text()}
    res = engine.run(inp_text, met_files=met_files, plotfiles=plotfiles, pollutant="NOx")
    assert res.available
    assert res.max_conc  # produced at least one averaging-period peak
