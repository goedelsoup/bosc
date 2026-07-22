"""Ohio numeric temperature criteria (OAC 3745-1) + Great Lakes RIS thermal tolerances — the
receiving-water thermal thresholds the thermal-discharge screen (:mod:`watermark.hydrology.thermal`,
Phase 2 of epic #1715) reads a cooling discharge's fully-mixed in-stream temperature against.

The heat-side peer of :mod:`watermark.hydrology.criteria` (the per-chemical toxic criteria loader,
WS-07 / #1607). Two committed reference datasets, both ``reference`` when surfaced, never ``verified``:

* ``data/reference/wqs/ohio-temperature-criteria.yaml`` — published state standards (Ohio
  Administrative Code chapter 3745-1). Ohio sets temperature criteria GEOGRAPHICALLY (by water body
  / basin), not per aquatic-life use: each :class:`TemperatureZone` gives an average and a daily
  maximum temperature for each of 18 half-month :class:`TemperaturePeriod` s. Values are stored as
  the primary published °F integers; °C is derived here as ``round((°F - 32) * 5/9, 1)`` (which
  reproduces the rule's own rounded (Celsius) parenthetical). Plus the OAC 3745-1-06 (O) thermal
  mixing-zone rule (ambient → max daily-average-temperature ceiling, and the closed-cycle-blowdown
  ``< 5% of 7Q10`` exemption).
* ``data/reference/thermal/great-lakes-ris-thermal-tolerances.yaml`` — EPA-833-F-23-007 Table 3-5
  Representative Important Species thermal tolerances (Great Lakes region: Lima → Maumee → Lake
  Erie). Federal guidance ("does not have the force and effect of law"): the biological limits for
  a CWA §316(a) balanced-indigenous-community read. Temperature values are the verbatim strings the
  table prints (ranges kept, e.g. ``"32-35.6"``); :meth:`ThermalMetric.upper_span` parses a span.

Both loaders degrade to an empty table (a warning, no crash) when their file is absent, mirroring
:func:`watermark.hydrology.criteria.load_criteria`.
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING, Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, PrivateAttr, model_validator

from watermark.config import get_settings
from watermark.logging import get_logger

if TYPE_CHECKING:
    from watermark.config import Settings

log = get_logger(__name__)

# The committed reference datasets, relative to ``settings.reference_dir``.
_TEMP_CRITERIA_RELPATH = "wqs/ohio-temperature-criteria.yaml"
_RIS_TOLERANCES_RELPATH = "thermal/great-lakes-ris-thermal-tolerances.yaml"


def fahrenheit_to_celsius(f: float) -> float:
    """Convert °F to °C, rounded to 0.1 — reproduces Ohio's published (Celsius) parenthetical."""
    return round((f - 32.0) * 5.0 / 9.0, 1)


def _parse_span(value: str | None) -> tuple[float, float] | None:
    """Parse a verbatim temperature cell into a ``(low, high)`` °C span.

    Table 3-5 prints single values (``"34.4"``) and ranges (``"32-35.6"``, ``"20.6-28.5"``,
    ``"3-4.9"``). A single value yields ``(v, v)``; a hyphenated range yields ``(low, high)``.
    Returns ``None`` for a blank/unparseable cell (omit, don't guess). A leading-minus value is
    not expected (all tolerances are above freezing), so ``-`` is always a range separator.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    parts = text.split("-")
    try:
        nums = [float(p) for p in parts if p.strip()]
    except ValueError:
        return None
    if not nums:
        return None
    return (min(nums), max(nums))


# ---------------------------------------------------------------------------------------------
# Ohio temperature criteria (OAC 3745-1-35 / 31-1 / 06)
# ---------------------------------------------------------------------------------------------


class TemperaturePeriod(BaseModel):
    """One of the 18 half-month reporting periods the zone tables are indexed by."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    month: int
    day_start: int
    day_end: int

    def contains(self, month: int, day: int) -> bool:
        """Whether ``(month, day)`` falls in this period (each period is within one month)."""
        return month == self.month and self.day_start <= day <= self.day_end


class TemperatureZone(BaseModel):
    """One geographic zone's average + daily-maximum temperature criteria (stored °F, exposed °C).

    ``average_f`` / ``daily_max_f`` are aligned to the table's ``periods`` order; an entry is
    ``None`` where the rule prints no criterion for that period (omit, never guess).
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    rule: str
    name: str
    basin: str | None = None
    description: str | None = None
    note: str | None = None
    average_f: list[float | None] = []
    daily_max_f: list[float | None] = []

    @staticmethod
    def _c(values: list[float | None], index: int) -> float | None:
        if index < 0 or index >= len(values):
            return None
        f = values[index]
        return None if f is None else fahrenheit_to_celsius(f)

    def average_c(self, period_index: int) -> float | None:
        """Average temperature criterion (°C) for a period index, or ``None`` if not printed."""
        return self._c(self.average_f, period_index)

    def daily_max_c(self, period_index: int) -> float | None:
        """Daily-maximum temperature criterion (°C) for a period index, or ``None``."""
        return self._c(self.daily_max_f, period_index)


class ThermalMixingZoneCurve(BaseModel):
    """OAC 3745-1-06 Table 1 — max daily-average temperature inside a thermal mixing zone vs. ambient.

    Only the regulatorily-operative rows (ambient below :attr:`applies_below_ambient_c`, i.e. < 15 °C
    / 59 °F) are committed; at/above that the rule makes the limit case-by-case.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    applies_to: str
    source: str
    applies_below_ambient_c: float
    limits: list[dict[str, float]] = []

    def limit_c(self, ambient_c: float) -> float | None:
        """Max mixing-zone daily-average temperature (°C) at ``ambient_c``, or ``None``.

        ``None`` means the rule does not tabulate a limit at this ambient: at/above
        :attr:`applies_below_ambient_c` the limit is case-by-case, and below the tabulated range the
        lookup does not extrapolate. Interpolates linearly between the tabulated ambient rows.
        """
        if ambient_c >= self.applies_below_ambient_c or not self.limits:
            return None
        pts = sorted(
            (
                (fahrenheit_to_celsius(row["ambient_f"]), fahrenheit_to_celsius(row["limit_f"]))
                for row in self.limits
            ),
            key=lambda p: p[0],
        )
        if ambient_c < pts[0][0] or ambient_c > pts[-1][0]:
            return None
        for (a0, l0), (a1, l1) in pairwise(pts):
            if a0 <= ambient_c <= a1:
                if a1 == a0:
                    return l0
                frac = (ambient_c - a0) / (a1 - a0)
                return round(l0 + frac * (l1 - l0), 1)
        return pts[-1][1]


class ThermalMixingZone(BaseModel):
    """OAC 3745-1-06 (O) thermal-mixing-zone rule: the Table 1 curves + the operative narrative rules."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    case_by_case_ambient_c: float | None = None
    closed_cycle_blowdown_exempt_fraction_of_7q10: float | None = None
    elevated_review_waters: list[str] = []
    curves: list[ThermalMixingZoneCurve] = []

    def curve(self, curve_id: str) -> ThermalMixingZoneCurve | None:
        """The mixing-zone curve by id (``non_lake_erie`` / ``lake_erie``), or ``None``."""
        return next((c for c in self.curves if c.id == curve_id), None)


class TemperatureCriteriaTable(BaseModel):
    """The committed Ohio temperature-criteria table: periods + geographic zones + mixing-zone rule."""

    model_config = ConfigDict(extra="forbid")

    source: dict[str, Any] = {}
    default_zone_hint: str | None = None
    periods: list[TemperaturePeriod] = []
    zones: list[TemperatureZone] = []
    thermal_mixing_zone: ThermalMixingZone | None = None
    transcription_notes: list[str] = []

    # id -> zone, built lazily on first `zone()` (see criteria.CriteriaTable for the model_copy rationale).
    _index: dict[str, TemperatureZone] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _check_zone_lengths(self) -> TemperatureCriteriaTable:
        """Every zone's arrays must align to the shared period axis (a transcription-error guard)."""
        n = len(self.periods)
        if not n:
            return self
        for z in self.zones:
            for label, arr in (("average_f", z.average_f), ("daily_max_f", z.daily_max_f)):
                if len(arr) != n:
                    raise ValueError(
                        f"zone {z.id!r} {label} has {len(arr)} entries, expected {n} (period count)"
                    )
        return self

    def zone(self, zone_id: str | None) -> TemperatureZone | None:
        """The temperature zone by id, or ``None``."""
        if not zone_id:
            return None
        if not self._index:
            self._index = {z.id: z for z in self.zones}
        return self._index.get(zone_id)

    def period_index_for(self, month: int, day: int) -> int | None:
        """The index into the period axis for a calendar ``(month, day)``, or ``None``."""
        for i, p in enumerate(self.periods):
            if p.contains(month, day):
                return i
        return None

    def period_for(self, month: int, day: int) -> TemperaturePeriod | None:
        """The reporting period covering a calendar ``(month, day)``, or ``None``."""
        i = self.period_index_for(month, day)
        return None if i is None else self.periods[i]


def load_temperature_criteria(*, settings: Settings | None = None) -> TemperatureCriteriaTable:
    """The committed Ohio temperature-criteria table, or an empty table if the dataset is absent.

    Degrades (empty table + a warning) rather than raising, mirroring
    :func:`watermark.hydrology.criteria.load_criteria` — a partial checkout must not crash the screen.
    """
    settings = settings or get_settings()
    path = settings.reference_dir / _TEMP_CRITERIA_RELPATH
    if not path.is_file():
        log.warning("thermal.temperature_criteria_missing", path=str(path))
        return TemperatureCriteriaTable()
    data = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return TemperatureCriteriaTable.model_validate(data)


# ---------------------------------------------------------------------------------------------
# Great Lakes RIS thermal tolerances (EPA-833-F-23-007 Table 3-5)
# ---------------------------------------------------------------------------------------------


class ThermalMetric(BaseModel):
    """One acute / chronic / optimal thermal-limit cell: verbatim °C strings + reference numbers."""

    model_config = ConfigDict(extra="forbid")

    upper_c: str | None = None
    lower_c: str | None = None
    refs: list[int] = []

    def upper_span(self) -> tuple[float, float] | None:
        """The upper limit parsed to a ``(low, high)`` °C span, or ``None`` if blank."""
        return _parse_span(self.upper_c)

    def lower_span(self) -> tuple[float, float] | None:
        """The lower limit parsed to a ``(low, high)`` °C span, or ``None`` if blank."""
        return _parse_span(self.lower_c)


class LifeStageTolerance(BaseModel):
    """A species life stage's acute / chronic / optimal thermal tolerances."""

    model_config = ConfigDict(extra="forbid")

    life_stage: str
    acute: ThermalMetric | None = None
    chronic: ThermalMetric | None = None
    optimal: ThermalMetric | None = None


class RisSpecies(BaseModel):
    """One Representative Important Species: Table 3-4 context + Table 3-5 tolerances."""

    model_config = ConfigDict(extra="forbid")

    scientific_name: str
    common_name: str
    category: str  # fish | invertebrate | plant_algae | planktonic
    trophic: str | None = None
    ris_status: str | None = None
    note: str | None = None
    tolerances: list[LifeStageTolerance] = []

    def stage(self, life_stage: str) -> LifeStageTolerance | None:
        """The tolerances for a named life stage (case-insensitive), or ``None``."""
        want = life_stage.strip().lower()
        return next((t for t in self.tolerances if t.life_stage.lower() == want), None)


class ThermalToleranceTable(BaseModel):
    """The committed Great Lakes RIS thermal-tolerance table, indexed by species name."""

    model_config = ConfigDict(extra="forbid")

    source: dict[str, Any] = {}
    region: str | None = None
    species: list[RisSpecies] = []
    references: dict[int, str] = {}

    # normalized name -> species, built lazily (survives model_copy; see criteria.CriteriaTable).
    _index: dict[str, RisSpecies] = PrivateAttr(default_factory=dict)

    def match(self, name: str | None) -> RisSpecies | None:
        """A species by common OR scientific name (case-insensitive), or ``None``."""
        if not name:
            return None
        if not self._index:
            idx: dict[str, RisSpecies] = {}
            for s in self.species:
                idx[s.common_name.strip().lower()] = s
                idx[s.scientific_name.strip().lower()] = s
            self._index = idx
        return self._index.get(name.strip().lower())


def load_thermal_tolerances(*, settings: Settings | None = None) -> ThermalToleranceTable:
    """The committed Great Lakes RIS thermal-tolerance table, or empty if the dataset is absent."""
    settings = settings or get_settings()
    path = settings.reference_dir / _RIS_TOLERANCES_RELPATH
    if not path.is_file():
        log.warning("thermal.ris_tolerances_missing", path=str(path))
        return ThermalToleranceTable()
    data = cast("dict[str, Any]", yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return ThermalToleranceTable.model_validate(data)
