"""Structured data-center **candidate record** — the machine-readable peer of the sweep's
freetext register (#1627, epic #1626 F1).

`watermark sweep data-centers` streams a cited prose register into
``data/extracted/<site>/data-centers.md``; **no code reads that prose** — a human re-keys
figures into a :class:`~watermark.sites.SiteFacility` by hand, dropping per-claim provenance
across the seam. This module is the structured half: a discovered project is a
:class:`DataCenterCandidate` carrying each disclosed figure as a :class:`ProvenancedFigure`
(value + the ``SourceKind`` that grounds it), the register prose as a field, and a stable
dedupe key. One site holds N candidates (:class:`SiteCandidates`), written alongside the prose
as ``data-centers.candidates.yaml``.

The record is the promotion *source*; :class:`~watermark.sites.SiteFacility` is the target. F1
lands the schema + the report that surfaces the prose→facility backlog explicitly
(:func:`promotion_report`); wiring an actual multi-facility promotion is F2 (#1628).

Evidentiary discipline is unchanged: a swept figure is ``[open]``/``[inference]``/``[reference]``
until an instrument is cited. A figure's provenance rides *with its value* — a ``value`` of
``None`` is ``[open]`` (the predicate is known, nothing is disclosed yet), never a fabricated zero.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from watermark.config import Settings, get_settings
from watermark.provenance import EvidenceTag, SourceKind, evidence_tag
from watermark.sites import SITES

# The sidecar filename that pairs the prose register 1:1 (globs together under the same prefix).
CANDIDATES_FILENAME = "data-centers.candidates.yaml"
REGISTER_FILENAME = "data-centers.md"


def _slug(text: str, *, max_len: int = 64) -> str:
    """A stable, deterministic dedupe slug (local peer of ``research.run.slug`` — kept here so
    ``watermark.facility`` doesn't depend on ``watermark.research``)."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "candidate"


class ProvenancedFigure(BaseModel):
    """One disclosed figure carried across the prose→structured seam with its provenance.

    ``value is None`` means ``[open]`` — the predicate is known (the register names the dimension)
    but nothing is disclosed yet; it carries no ``source_kind``/``citation`` (enforced below), only
    an optional ``note`` for the gap. A set ``value`` MUST name the instrument that grounds it
    (``source_kind`` + ``citation``), so a figure can never pass uncited. The evidence-discipline
    tag is *derived* from the provenance (:attr:`tag`), never re-keyed by hand.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float | int | str | None = None
    unit: str | None = None  # "MW" / "USD" / "acres" / "sqft" / "MGD" / …
    source_kind: SourceKind | None = None
    citation: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _value_carries_its_provenance(self) -> ProvenancedFigure:
        if self.value is None:
            # An [open] figure: predicate known, nothing disclosed — no source to cite.
            if self.source_kind is not None or self.citation is not None:
                raise ValueError(
                    "an open figure (value=None) carries no source_kind/citation — "
                    "set a value to ground it, or use `note` to record the gap"
                )
        elif self.source_kind is None or self.citation is None:
            raise ValueError(
                "a disclosed figure (value set) needs both source_kind and citation "
                "so its provenance travels with it across the seam"
            )
        return self

    @property
    def tag(self) -> EvidenceTag | Literal["open"]:
        """The evidence-discipline tag this figure renders as (`[open]` when no value)."""
        if self.value is None or self.source_kind is None:
            return "open"
        return evidence_tag(self.source_kind)


class CandidateStatus(StrEnum):
    """Where a discovered project sits in its lifecycle. ``withdrawn``/``rejected`` are dead ends
    (they never promote to a live facility); ``unknown`` is the honest default for a sweep hit
    whose stage is not on the record."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    UNDER_CONSTRUCTION = "under_construction"
    OPERATING = "operating"
    WITHDRAWN = "withdrawn"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


# The facility-shaping figures whose presence makes a candidate worth promoting to a SiteFacility.
_PROMOTABLE_FIELDS = ("it_load_mw", "gross_floor_area_sqft", "investment_usd")


class DataCenterCandidate(BaseModel):
    """One discovered data-center project — the structured, provenance-carrying peer of a numbered
    section in the prose register.

    ``key`` is the stable dedupe identity (project name, else operator); the figures are each a
    :class:`ProvenancedFigure`, ``None`` when the register names no such dimension at all. The
    register's prose for this project is preserved verbatim in ``register_prose`` so the structured
    record never *replaces* the reviewed narrative — it indexes it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- identity / dedup -----------------------------------------------------
    key: str
    project_name: str | None = None
    operator: ProvenancedFigure  # developer/operator of record (a string value + its provenance)
    status: CandidateStatus = CandidateStatus.UNKNOWN
    location: str | None = None
    county: str | None = None

    # --- disclosed figures (each provenance-carried; None = dimension not on the register) -----
    it_load_mw: ProvenancedFigure | None = None
    gross_floor_area_sqft: ProvenancedFigure | None = None
    investment_usd: ProvenancedFigure | None = None
    acreage: ProvenancedFigure | None = None
    water_draw_mgd: ProvenancedFigure | None = None
    cooling: ProvenancedFigure | None = None
    utility: ProvenancedFigure | None = None
    npdes_permit: ProvenancedFigure | None = None
    air_permit: ProvenancedFigure | None = None

    # --- the reviewed narrative for this project (the "prose as a field") ---------------------
    register_prose: str = ""

    @property
    def is_promotable(self) -> bool:
        """True when this candidate has ≥1 disclosed facility-shaping figure and is not a dead end.

        Promotable ≠ verified: an ``[inference]``/``[reference]`` bracket (a screening MW, a media
        investment figure) is still a promotion candidate — it lands on the target ``SiteFacility``
        as an ``[inference]``, exactly like Urbana's floor-area load. Withdrawn/rejected projects
        never promote.
        """
        if self.status in (CandidateStatus.WITHDRAWN, CandidateStatus.REJECTED):
            return False
        return any(
            (fig := getattr(self, name)) is not None and fig.value is not None
            for name in _PROMOTABLE_FIELDS
        )


class SiteCandidates(BaseModel):
    """A site's discovered data-center projects — the structured sidecar to its prose register."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: str
    generated_at: str  # ISO date the distillation ran (caller-supplied; deterministic)
    source_register: str  # relpath (from data/) of the prose register this was distilled from
    candidates: list[DataCenterCandidate] = []

    @property
    def promotable(self) -> list[DataCenterCandidate]:
        return [c for c in self.candidates if c.is_promotable]


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------


def candidates_path(settings: Settings, site: str) -> Path:
    """The sidecar path for a site's candidate record (peer of ``<site>/data-centers.md``)."""
    return settings.extracted_dir / site / CANDIDATES_FILENAME


def register_path(settings: Settings, site: str) -> Path:
    """The prose register path for a site."""
    return settings.extracted_dir / site / REGISTER_FILENAME


def load_candidates(path: Path) -> SiteCandidates | None:
    """Load a committed candidate record, or ``None`` if the site has no sidecar yet."""
    if not path.exists():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SiteCandidates.model_validate(raw)


class _BlockDumper(yaml.SafeDumper):
    """A SafeDumper that renders multi-line strings as literal ``|`` blocks — so the verbatim
    ``register_prose`` markdown stays readable in the committed artifact (PyYAML falls back to a
    quoted scalar only when a line has trailing whitespace that ``|`` cannot represent)."""


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_BlockDumper.add_representer(str, _represent_str)


def save_candidates(record: SiteCandidates, path: Path) -> None:
    """Write a candidate record as clean YAML (drops absent figures; keeps ``[open]`` ones)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # exclude_none drops fully-absent figure fields AND the inner provenance of an [open] figure,
    # leaving a present-but-empty figure (value=None) that round-trips back to [open].
    payload = record.model_dump(mode="json", exclude_none=True)
    path.write_text(
        yaml.dump(payload, Dumper=_BlockDumper, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


def build_candidate(
    *,
    project_name: str | None,
    operator: ProvenancedFigure,
    **fields: object,
) -> DataCenterCandidate:
    """Construct a candidate, minting the dedupe ``key`` in code (project name, else operator).

    The key is never left to model whim — dedupe stays deterministic across re-distillations.
    """
    basis = (
        project_name or (operator.value if isinstance(operator.value, str) else None) or "candidate"
    )
    return DataCenterCandidate(
        key=_slug(basis), project_name=project_name, operator=operator, **fields
    )


# ---------------------------------------------------------------------------
# Promotion report — surface the prose/candidate → SiteFacility backlog explicitly
# ---------------------------------------------------------------------------


class PromotionState(StrEnum):
    """A site's position on the prose → candidate → ``SiteFacility`` promotion path."""

    NONE = "none"  # no prose register at all
    NEEDS_DISTILL = "needs-distill"  # register exists, not yet distilled to a candidate record
    NEEDS_PROMOTION = "needs-promotion"  # promotable candidate(s), but SiteProfile.facility is None
    OK = "ok"  # a SiteFacility exists (or no promotable candidate is outstanding)


class PromotionRow(BaseModel):
    """One site's row in the promotion report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    site: str
    has_register: bool
    candidate_count: int
    promotable_count: int
    has_facility: bool
    state: PromotionState


# Report order: the actionable backlog first, resolved/empty sites last.
_STATE_ORDER = {
    PromotionState.NEEDS_PROMOTION: 0,
    PromotionState.NEEDS_DISTILL: 1,
    PromotionState.OK: 2,
    PromotionState.NONE: 3,
}


def promotion_status(slug: str, settings: Settings | None = None) -> PromotionRow:
    """Compute one site's promotion row from its register, candidate sidecar, and profile."""
    settings = settings or get_settings()
    profile = SITES[slug]
    has_register = register_path(settings, slug).exists()
    has_facility = profile.facility is not None
    record = load_candidates(candidates_path(settings, slug))
    candidate_count = len(record.candidates) if record else 0
    promotable_count = len(record.promotable) if record else 0

    if has_facility:
        state = PromotionState.OK
    elif record is None:
        state = PromotionState.NEEDS_DISTILL if has_register else PromotionState.NONE
    elif promotable_count:
        state = PromotionState.NEEDS_PROMOTION
    else:
        state = PromotionState.OK

    return PromotionRow(
        site=slug,
        has_register=has_register,
        candidate_count=candidate_count,
        promotable_count=promotable_count,
        has_facility=has_facility,
        state=state,
    )


def promotion_report(settings: Settings | None = None) -> list[PromotionRow]:
    """Every registered site's promotion row, backlog (needs-promotion/needs-distill) first.

    This is the explicit close of the Hamilton-Middletown / Columbus / New-Albany backlog — a site
    whose prose register or distilled candidate has no matching ``SiteFacility`` surfaces here
    rather than being tracked by memory.
    """
    settings = settings or get_settings()
    rows = [promotion_status(slug, settings) for slug in SITES]
    return sorted(rows, key=lambda r: (_STATE_ORDER[r.state], r.site))
