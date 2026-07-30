"""Typed reader for the committed data-center industry reference priors (#1665, ME-F).

``data/reference/datacenter-industry/priors.yaml`` is a hand-assembled pooled meta-analysis:
for each load-bearing unknown the Lima record leaves open, independent published estimates
are pooled into a low/central/high band, and every source that fed it is cited. It has been
committed since #269 and read by **nothing** — its numbers were hand-copied into the
frontend's ``ECON_PRIORS`` array and into the prose of ``docs/ECONOMICS.md`` §4, which is
exactly the drift this cluster exists to close.

This module gives it a typed loader so the scenario bands
(:mod:`watermark.economics.scenarios`) are computed from the cited file rather than from a
copy of it. It reads only — the file stays curated (``producer.kind: manual`` in the
catalog), regenerable by nothing, and is never written here.

**Network-global, deliberately.** These are industry ranges, not a property of any watershed
point, so the path is a module constant rather than a ``SiteProfile`` relpath (the catalog
records it ``site_scope: basin-shared``). Each prior's ``lima_status`` — surfaced as
``site_status`` — is what keeps an industry range from being read as a facility fact.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings, get_settings
from watermark.logging import get_logger

log = get_logger(__name__)

#: Relative to ``settings.data_dir``. Not per-site — see the module docstring.
PRIORS_RELPATH = "reference/datacenter-industry/priors.yaml"


class PriorSource(BaseModel):
    """One published source pooled into a prior's band."""

    model_config = ConfigDict(extra="forbid")

    name: str
    year: int | None = None
    url: str | None = None
    contributes: str = ""


class IndustryPrior(BaseModel):
    """One pooled industry prior: a band (where one is asserted) plus every source behind it.

    ``low``/``central``/``high`` are all optional because the file deliberately carries two
    kinds of entry: a **band** prior (``dist: triangular``/``bimodal``/``point``) and a
    **corroboration** prior that asserts no range of its own — ``salestax_exemption_dominance``
    and ``heat_reuse`` are qualitative findings from other jurisdictions/vendors, kept as
    cited context rather than promoted to a number. Reading one as the other is the mistake
    the optionality prevents.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    key: str
    label: str
    unit: str = ""
    # The file's own vocabulary for the prior's evidence class. Aliased because the YAML key is
    # `register`, which shadows `BaseModel.register` (ABCMeta's) as a field name.
    evidence_register: str = Field("reference", alias="register")
    lima_status: str = "open"  # open | comparative | context | verified-stated
    dist: str | None = None  # triangular | bimodal | point | None (no band asserted)
    low: float | None = None
    central: float | None = None
    high: float | None = None
    drives: list[str] = []
    note: str = ""
    sources: list[PriorSource] = []

    @property
    def has_band(self) -> bool:
        """True when the prior asserts a real (non-degenerate) low..high range."""
        return self.low is not None and self.high is not None and self.high > self.low


class IndustryPriors(BaseModel):
    """The committed priors file: its methodology block plus the pooled priors."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = {}
    priors: list[IndustryPrior] = []

    def get(self, key: str) -> IndustryPrior | None:
        """The prior with this key, or ``None`` when the file does not carry it."""
        return next((p for p in self.priors if p.key == key), None)

    def require(self, key: str) -> IndustryPrior:
        """The prior with this key, or raise naming it.

        Used where a scenario axis is *defined* by a prior: a silently-missing key would
        publish a band-less axis that looks like a deliberate corroboration entry, so the
        absent case raises instead of degrading.
        """
        prior = self.get(key)
        if prior is None:
            have = ", ".join(p.key for p in self.priors)
            raise ValueError(f"industry prior {key!r} is not in {PRIORS_RELPATH} (have: {have})")
        return prior


def load_industry_priors(settings: Settings | None = None) -> IndustryPriors | None:
    """Read the committed industry priors, or ``None`` when the file is absent.

    Absent is a legitimate state (a data_dir without the reference tree), so the caller
    degrades — the scenario axes are simply omitted — rather than crashing the export.
    """
    settings = settings or get_settings()
    path = settings.data_dir / PRIORS_RELPATH
    if not path.is_file():
        log.info("econ.priors.absent", path=str(path))
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    raw = data.get("priors") or []
    priors = [IndustryPrior(**entry) for entry in raw if isinstance(entry, dict)]
    return IndustryPriors(meta=data.get("meta") or {}, priors=priors)
