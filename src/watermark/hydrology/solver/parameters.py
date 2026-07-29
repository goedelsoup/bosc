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
from pydantic import BaseModel, ConfigDict, Field, model_validator

from watermark.config import Settings, get_settings
from watermark.sites import active_profile

# Documented defaults — the cited value hard-coded so a data_dir missing the reference file still
# runs, and the anchor a coupling test pins the committed YAML to. See tier0-parameters.yaml for
# the citations (NEH-630 Ch. 16 / TR-55 / Chow 1959).
_DEFAULT_PEAK_FACTOR = 484.0
_DEFAULT_IA_RATIO = 0.2
_DEFAULT_MANNING_N = 0.04
_DEFAULT_DILUTION_VIOLATION = 1.0
_DEFAULT_DILUTION_TIGHT = 10.0


class _Tier0Params(BaseModel):
    """Validated Tier-0 solver constants — physically constrained so a bad edit to the reference
    file (a non-finite factor, a negative ratio/roughness, reversed dilution bands) is rejected
    loudly rather than silently propagated into a screen. ``allow_inf_nan=False`` rejects inf/nan;
    the ``Field`` bounds reject non-positive (and out-of-range) values."""

    model_config = ConfigDict(allow_inf_nan=False)

    peak_factor: float = Field(gt=0)
    initial_abstraction_ratio: float = Field(gt=0, le=1)  # Ia = ratio * S; ratio in (0, 1]
    manning_n: float = Field(gt=0)
    dilution_violation: float = Field(gt=0)
    dilution_tight: float = Field(gt=0)

    @model_validator(mode="after")
    def _bands_ordered(self) -> _Tier0Params:
        if self.dilution_violation >= self.dilution_tight:
            raise ValueError(
                f"dilution violation band ({self.dilution_violation}) must sit below the tight "
                f"band ({self.dilution_tight})"
            )
        return self


@lru_cache(maxsize=4)
def _load_params(data_dir: str) -> _Tier0Params | None:
    """The validated reference constants, or ``None`` when the file is absent (defaults apply).

    A present-but-invalid file raises (``pydantic.ValidationError`` / ``KeyError``) rather than
    being silently accepted — a bad physics constant must fail loudly, not skew a screen. Only a
    *missing* file falls back to the documented defaults.
    """
    path = Path(data_dir) / "reference" / "hydrology" / "tier0-parameters.yaml"
    if not path.is_file():
        return None
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _Tier0Params(
        peak_factor=raw["runoff"]["peak_factor"]["value"],
        initial_abstraction_ratio=raw["runoff"]["initial_abstraction_ratio"]["value"],
        manning_n=raw["routing"]["manning_n"]["value"],
        dilution_violation=raw["dilution"]["violation_ratio"]["value"],
        dilution_tight=raw["dilution"]["tight_ratio"]["value"],
    )


def _resolve(settings: Settings | None) -> _Tier0Params | None:
    return _load_params(str((settings or get_settings()).data_dir))


def peak_factor(*, settings: Settings | None = None) -> float:
    """SCS dimensionless unit-hydrograph peak factor (``Qp = peak_factor * A / Tp``).

    The one exception to this module's "per-method physics constant" rule: the peak factor is
    also a *terrain* property (NEH-630 Ch. 16 — ~300 on flat/swampy ground, ~600 on steep), so a
    site whose catchment is not the standard-hydrograph shape declares it on its profile
    (``SiteProfile.uh_peak_factor``). Precedence: an explicit ``simulate_runoff(peak_factor=)``
    argument, then the site profile, then this cited reference value (484).
    """
    profile_factor = active_profile(settings or get_settings()).uh_peak_factor
    if profile_factor is not None:
        return profile_factor
    params = _resolve(settings)
    return params.peak_factor if params is not None else _DEFAULT_PEAK_FACTOR


def initial_abstraction_ratio(*, settings: Settings | None = None) -> float:
    """Initial abstraction as a fraction of maximum retention S (``Ia = ratio * S``)."""
    params = _resolve(settings)
    return params.initial_abstraction_ratio if params is not None else _DEFAULT_IA_RATIO


def default_manning_n(*, settings: Settings | None = None) -> float:
    """Default natural-channel Manning ``n`` for a reach that sets none (``reaches.yaml`` wins)."""
    params = _resolve(settings)
    return params.manning_n if params is not None else _DEFAULT_MANNING_N


def dilution_bands(*, settings: Settings | None = None) -> tuple[float, float]:
    """``(violation, tight)`` screening bands on the 7Q10/discharge dilution ratio."""
    params = _resolve(settings)
    if params is None:
        return _DEFAULT_DILUTION_VIOLATION, _DEFAULT_DILUTION_TIGHT
    return params.dilution_violation, params.dilution_tight


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
