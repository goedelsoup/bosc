"""Cited Tier-0 solver + screening constants (the reference-layer seam for WS-23 / #1623).

The load-bearing per-method physics/screening constants — the SCS unit-hydrograph peak factor,
the initial-abstraction ratio, the default channel Manning ``n``, and the low-flow dilution
screening bands — live in the cited reference layer (``data/reference/hydrology/tier0-parameters.yaml``,
tagged like ``cn-lookup.yaml``), not as buried literals. This module reads that file (lazily,
cached by ``data_dir``) and exposes one accessor per constant. Each accessor:

* returns the committed, cited value from the YAML, and
* falls back to the same value hard-coded here as a documented default, so a ``data_dir`` without
  the file still runs a screen. A coupling test keeps the two in sync.

The per-call **override seam** is the solver functions themselves: they take
``peak_factor=`` / ``ia_ratio=`` / ``manning_n=`` / ``bands=`` and only consult these accessors
when the caller passes nothing. ``reaches.yaml`` overrides Manning ``n`` per reach; the
time-of-concentration endpoints are per-site on ``SiteProfile`` (not here).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from watermark.config import Settings, get_settings

# Documented defaults — the cited value hard-coded so a data_dir missing the reference file still
# runs, and the anchor a coupling test pins the committed YAML to. See tier0-parameters.yaml for
# the citations (NEH-630 Ch. 16 / TR-55 / Chow 1959).
_DEFAULT_PEAK_FACTOR = 484.0
_DEFAULT_IA_RATIO = 0.2
_DEFAULT_MANNING_N = 0.04
_DEFAULT_DILUTION_VIOLATION = 1.0
_DEFAULT_DILUTION_TIGHT = 10.0


@lru_cache(maxsize=4)
def _load_params(data_dir: str) -> dict[str, Any]:
    path = Path(data_dir) / "reference" / "hydrology" / "tier0-parameters.yaml"
    if not path.is_file():
        return {}
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def _param(section: str, key: str, default: float, *, settings: Settings | None) -> float:
    """The cited ``value`` for ``section.key`` from the reference file, else the default."""
    settings = settings or get_settings()
    table = _load_params(str(settings.data_dir))
    entry = table.get(section, {}).get(key) if isinstance(table.get(section), dict) else None
    if isinstance(entry, dict) and "value" in entry:
        return float(entry["value"])
    return default


def peak_factor(*, settings: Settings | None = None) -> float:
    """SCS dimensionless unit-hydrograph peak factor (``Qp = peak_factor * A / Tp``)."""
    return _param("runoff", "peak_factor", _DEFAULT_PEAK_FACTOR, settings=settings)


def initial_abstraction_ratio(*, settings: Settings | None = None) -> float:
    """Initial abstraction as a fraction of maximum retention S (``Ia = ratio * S``)."""
    return _param("runoff", "initial_abstraction_ratio", _DEFAULT_IA_RATIO, settings=settings)


def default_manning_n(*, settings: Settings | None = None) -> float:
    """Default natural-channel Manning ``n`` for a reach that sets none (``reaches.yaml`` wins)."""
    return _param("routing", "manning_n", _DEFAULT_MANNING_N, settings=settings)


def dilution_bands(*, settings: Settings | None = None) -> tuple[float, float]:
    """``(violation, tight)`` screening bands on the 7Q10/discharge dilution ratio."""
    violation = _param(
        "dilution", "violation_ratio", _DEFAULT_DILUTION_VIOLATION, settings=settings
    )
    tight = _param("dilution", "tight_ratio", _DEFAULT_DILUTION_TIGHT, settings=settings)
    return violation, tight


def round_sig(x: float, sig: int = 2) -> float:
    """Round ``x`` to ``sig`` significant figures (0 and non-finite pass through unchanged).

    Tier-0 screening peaks derive from ~2-significant-figure inputs (design depths, assumed CNs,
    stated Tc), so a stored 0.001-cfs precision reads as false confidence — the reported peak is
    right-sized to 2 sig figs (WS-23 / #1623). Applied to the reported scalar peak only, never to
    the physics-bearing hydrograph series.
    """
    if x == 0.0 or not math.isfinite(x):
        return x
    return round(x, -math.floor(math.log10(abs(x))) + (sig - 1))
