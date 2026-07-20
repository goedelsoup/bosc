"""Ohio numeric water-quality criteria (OAC 3745-1) — the per-chemical thresholds the
industrial toxic screen (:mod:`watermark.hydrology.toxics`) reads each pollutant's derived
receiving-water concentration against, replacing the old flat 1.0 mg/L aggregate band
(epic #1600, finding WS-07 / #1607).

The committed table is ``data/reference/wqs/ohio-water-quality-criteria.yaml`` — published
state standards (Ohio Administrative Code 3745-1), tagged ``reference`` when surfaced, never
``verified``. This module is the loader/index, the water-domain peer of
:func:`watermark.air.aermod.dispersion.load_naaqs`.

Each criterion carries three types, each paired to a regulatory design flow (wired in
``toxics``): **acute** (CMC / Ohio "maximum outside the mixing zone", OMZM) → 1Q10, **chronic**
(CCC / Ohio "outside mixing zone 30-day average", OMZA) → 7Q10, and **human health** (public
water supply) → harmonic mean. Any type may be ``None`` — the screen omits it, never guesses.

Metals criteria are hardness-dependent (OAC 3745-1-35 Table 35-9): the committed mg/L values are
at the stated reference hardness (100 mg/L CaCO₃), and each metal carries its
``criterion(µg/L) = exp(m·ln(hardness) + b)`` equation so the value re-derives at a cited
receiving-water hardness (:meth:`WaterQualityCriterion.acute_at` / :meth:`chronic_at`).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, PrivateAttr

from watermark.config import get_settings
from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

# The committed WQS reference dataset, relative to ``settings.reference_dir``.
_CRITERIA_RELPATH = "wqs/ohio-water-quality-criteria.yaml"


def _norm(token: str) -> str:
    """Normalize an RSEI chemical token (CAS or ``Nxxx`` category code) for indexing."""
    return token.strip().upper()


class HardnessEquation(BaseModel):
    """A Table 35-9 hardness-dependent metals equation: ``criterion(µg/L) = exp(m·ln(H) + b)``."""

    model_config = ConfigDict(extra="forbid")

    m: float
    b: float

    def at(self, hardness_mg_l: float) -> float:
        """The criterion in **µg/L** at a given hardness (mg/L as CaCO₃).

        Hardness must be positive (the equation is ``exp(m·ln(H) + b)``); a non-positive
        hardness is physically meaningless and raises rather than emit a ``math domain error``.
        """
        if hardness_mg_l <= 0:
            raise ValueError(f"hardness must be > 0 mg/L, got {hardness_mg_l}")
        return math.exp(self.m * math.log(hardness_mg_l) + self.b)


class WaterQualityCriterion(BaseModel):
    """One chemical's Ohio criteria (mg/L), keyed by its RSEI token(s)."""

    model_config = ConfigDict(extra="forbid")

    cas: str  # the RSEI token: a real CAS ("7664-41-7") or a category code ("N511")
    name: str
    aka_cas: list[str] = []  # other RSEI tokens resolving to the same criterion

    acute_cmc_mg_l: float | None = None  # CMC / OMZM, screened at 1Q10
    chronic_ccc_mg_l: float | None = None  # CCC / OMZA, screened at 7Q10
    human_health_mg_l: float | None = None  # public water supply, screened at harmonic mean

    hardness_dependent: bool = False
    hardness_mg_l: float | None = None  # the reference hardness the mg/L values are stated at
    hardness_acute: HardnessEquation | None = None
    hardness_chronic: HardnessEquation | None = None

    basis_acute: str | None = None
    basis_chronic: str | None = None
    basis_human_health: str | None = None
    notes: str | None = None

    @property
    def tokens(self) -> list[str]:
        """Every RSEI token that resolves to this criterion (primary + aliases)."""
        return [self.cas, *self.aka_cas]

    def acute_at(self, hardness_mg_l: float | None = None) -> float | None:
        """Acute criterion (mg/L), re-derived at ``hardness_mg_l`` for a hardness metal.

        Falls back to the stored (reference-hardness) value when no positive hardness is given
        or the chemical is not hardness-dependent.
        """
        if hardness_mg_l and hardness_mg_l > 0 and self.hardness_dependent and self.hardness_acute:
            return self.hardness_acute.at(hardness_mg_l) / 1000.0
        return self.acute_cmc_mg_l

    def chronic_at(self, hardness_mg_l: float | None = None) -> float | None:
        """Chronic criterion (mg/L), re-derived at ``hardness_mg_l`` for a hardness metal.

        Falls back to the stored (reference-hardness) value when no positive hardness is given
        or the chemical is not hardness-dependent.
        """
        if (
            hardness_mg_l
            and hardness_mg_l > 0
            and self.hardness_dependent
            and self.hardness_chronic
        ):
            return self.hardness_chronic.at(hardness_mg_l) / 1000.0
        return self.chronic_ccc_mg_l


class CriteriaTable(BaseModel):
    """The committed WQS table: provenance/assumptions meta + criteria, indexed by token."""

    model_config = ConfigDict(extra="forbid")

    source: dict[str, Any] = {}
    assumptions: dict[str, Any] = {}
    criteria: list[WaterQualityCriterion] = []

    # Token -> criterion index, built lazily on first `match` (NOT in model_post_init): pydantic
    # skips post-init on model_copy(), which would leave a copied table with an empty index and
    # silently match nothing. Lazy build survives copies — an empty index just rebuilds.
    _index: dict[str, WaterQualityCriterion] = PrivateAttr(default_factory=dict)

    def match(self, token: str | None) -> WaterQualityCriterion | None:
        """The criterion for an RSEI chemical token (CAS or ``Nxxx``), or ``None``."""
        if not token:
            return None
        if not self._index:
            self._index = {_norm(t): c for c in self.criteria for t in c.tokens}
        return self._index.get(_norm(token))


def load_criteria(*, settings: Settings | None = None) -> CriteriaTable:
    """The committed Ohio WQS criteria table, or an empty table if the dataset is absent.

    Degrades (empty table + a warning) rather than raising, mirroring the screen's other inputs
    (``_load_echo`` / ``load_low_flows`` return empty when their file is missing) so a partial
    checkout doesn't crash ``build_screen``. With an empty table every chemical resolves to
    ``no_criterion`` — a visible "we have no criteria to screen against" signal, not a silent
    "nothing exceeds".
    """
    settings = settings or get_settings()
    path = settings.reference_dir / _CRITERIA_RELPATH
    if not path.is_file():
        log.warning("wqs.criteria_missing", path=str(path))
        return CriteriaTable()
    data = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return CriteriaTable.model_validate(data)


def criterion_for(
    token: str | None, *, settings: Settings | None = None
) -> WaterQualityCriterion | None:
    """The Ohio criterion for one RSEI chemical token, or ``None`` if none is committed."""
    return load_criteria(settings=settings).match(token)
