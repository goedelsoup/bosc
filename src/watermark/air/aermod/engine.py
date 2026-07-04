"""Run the EPA AERMOD dispersion engine, with graceful degradation.

Unlike SWMM (:mod:`watermark.hydrology.swmm.engine`), AERMOD is **not** a Python wheel:
EPA distributes it through SCRAM as a Fortran build (or source), so we locate the
executable on disk rather than ``import`` it. :func:`aermod_bin` resolves it
(``WATERMARK_AERMOD_BIN`` → ``aermod`` on ``PATH`` → a vendored build), :func:`aermod_available`
probes it, and :func:`run` executes it in a scratch dir. If the binary is absent the run
degrades to ``AermodResult(available=False)`` — exactly like ``SwmmResult(available=False)``
— so deck generation and output parsing stay testable without the vendored engine.

AERMOD is control-file driven: it reads ``aermod.inp`` from its working directory and
writes ``aermod.out`` plus any ``OU PLOTFILE`` outputs there. We parse the plotfiles (a
stable, columnar format) rather than the human-oriented ``aermod.out``. Provenance/pinning
of the binary itself is documented in ``docs/AERMOD.md``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

# AERMOD's fixed control-file name (it reads ./aermod.inp from its working directory).
_CONTROL_NAME = "aermod.inp"
_OUTPUT_NAME = "aermod.out"


@dataclass(frozen=True)
class ReceptorConc:
    """One receptor's modeled concentration for one averaging period / source group."""

    x_m: float
    y_m: float
    conc: float  # µg/m³
    ave_period: str  # the AERMOD AVE token: "1", "24", "ANNUAL", ...
    group: str  # source group id (usually "ALL")


@dataclass(frozen=True)
class AermodResult:
    """Parsed concentrations from one AERMOD run.

    Empty + ``available=False`` when the engine is missing (or the run produced no
    plotfile). ``max_conc`` maps each averaging period to its peak receptor value (µg/m³).
    """

    available: bool
    pollutant: str = ""
    unit: str = "ug/m3"
    receptors: tuple[ReceptorConc, ...] = ()
    max_conc: dict[str, float] = field(default_factory=dict)
    engine_version: str = ""
    note: str = ""


def aermod_bin(settings: Settings | None = None) -> Path | None:
    """Resolve the AERMOD executable, or ``None`` if it can't be found.

    Order: the ``WATERMARK_AERMOD_BIN`` setting (an explicit path) → ``aermod`` on ``PATH``
    → nothing. A configured path that doesn't exist resolves to ``None`` (and is logged),
    never a broken command handed to ``subprocess``.
    """
    settings = settings or get_settings()
    configured = settings.aermod_bin.strip()
    if configured:
        p = Path(configured)
        if p.is_file():
            return p
        log.info("aermod.bin_missing", configured=configured)
        return None
    found = shutil.which("aermod")
    return Path(found) if found else None


def aermod_available(settings: Settings | None = None) -> bool:
    """True if an AERMOD executable can be located (and looks runnable)."""
    p = aermod_bin(settings)
    if p is None:
        return False
    return os.access(p, os.X_OK)


def engine_version(settings: Settings | None = None) -> str:
    """A provenance string for the located binary (its path), or ``""`` if absent.

    AERMOD has no ``--version`` flag; the version banner only appears in run output. The
    binary path is the stable provenance we can record without a run — :func:`run` upgrades
    this to the banner line when it parses ``aermod.out``.
    """
    p = aermod_bin(settings)
    return f"aermod ({p})" if p else ""


def _parse_out_banner(out_text: str) -> str:
    """Pull the AERMOD version banner (e.g. ``VERSION 23132``) from ``aermod.out``."""
    for line in out_text.splitlines():
        s = line.strip()
        if "VERSION" in s and "AERMOD" in s.upper():
            return " ".join(s.split())
    return ""


def parse_plotfile(text: str, *, ave_period: str, group: str = "ALL") -> list[ReceptorConc]:
    """Parse an AERMOD ``PLOTFILE`` into per-receptor concentrations.

    The plotfile is a fixed columnar text format: comment lines start with ``*``; each data
    row is ``X  Y  CONC  ZELEV  ZHILL  ZFLAG  AVE  GRP  NUM_HRS  NET_ID``. We read X, Y and
    the concentration (µg/m³) and tag them with the caller's averaging period / group (the
    AVE/GRP columns echo these but the filename is what selected the period).
    """
    out: list[ReceptorConc] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            x, y, conc = float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            continue  # a header row that slipped the '*' convention — skip it
        out.append(ReceptorConc(x_m=x, y_m=y, conc=conc, ave_period=ave_period, group=group))
    return out


def run(
    inp_text: str,
    *,
    met_files: dict[str, str],
    plotfiles: dict[str, str],
    pollutant: str = "",
    group: str = "ALL",
    timeout_s: int = 600,
    settings: Settings | None = None,
) -> AermodResult:
    """Run an AERMOD deck in a scratch dir and parse its plotfiles.

    ``met_files`` maps a filename (as named in the deck's ``ME`` pathway) to its text
    contents (the canned AERMET surface/profile files); ``plotfiles`` maps each averaging-
    period token to the ``OU PLOTFILE`` filename the deck declared. Returns
    ``AermodResult(available=False)`` if the engine can't be located.
    """
    settings = settings or get_settings()
    binary = aermod_bin(settings)
    if binary is None:
        return AermodResult(available=False, note="AERMOD engine unavailable (binary not located)")

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / _CONTROL_NAME).write_text(inp_text, encoding="utf-8")
        for name, content in met_files.items():
            (work / name).write_text(content, encoding="utf-8")

        proc = subprocess.run(
            [str(binary)],
            cwd=work,
            capture_output=True,
            timeout=timeout_s,
            text=True,
        )
        out_text = (
            (work / _OUTPUT_NAME).read_text(encoding="utf-8")
            if (work / _OUTPUT_NAME).is_file()
            else proc.stdout
        )
        version = _parse_out_banner(out_text) or engine_version(settings)

        if proc.returncode != 0:
            log.info("aermod.run_failed", returncode=proc.returncode)
            return AermodResult(
                available=True,
                pollutant=pollutant,
                engine_version=version,
                note=f"AERMOD exited {proc.returncode}: {proc.stderr.strip()[:200]}",
            )

        receptors: list[ReceptorConc] = []
        max_conc: dict[str, float] = {}
        for ave, fname in plotfiles.items():
            fpath = work / fname
            if not fpath.is_file():
                continue
            recs = parse_plotfile(fpath.read_text(encoding="utf-8"), ave_period=ave, group=group)
            receptors.extend(recs)
            if recs:
                max_conc[ave] = max(r.conc for r in recs)

    return AermodResult(
        available=True,
        pollutant=pollutant,
        receptors=tuple(receptors),
        max_conc=max_conc,
        engine_version=version,
        note="" if receptors else "run completed but produced no plotfile receptors",
    )
