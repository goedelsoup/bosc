"""Curated receiving-water overlay for the ECHO basin NPDES inventories (#1698).

**Not a connector** — no network, no ``cached_get``. This is a committed, cited *overlay*
read off disk and merged into the regenerated inventory by
:mod:`watermark.hydrology.connectors.echo`, so ``watermark npdes --basin <slug>`` can
re-pull live ECHO **without clobbering reviewed data**.

The problem it solves: ECHO's ``CWPStateWaterBodyName`` is null for ~70% of the Ohio rows,
including load-bearing plants whose receiving water a *primary document* names outright
(Lima WWTP -> Ottawa River, permit 2PE00000; Van Wert WWTP -> Town Creek, fact sheet
2PD00006). Those corrections used to live as hand edits inside the connector's own output,
so a re-pull silently reverted them and regressed every downstream screen. Now they live
here — declared, cited, and re-applied on every pull.

Discipline (the point of the overlay, not decoration):

* A correction **never invents** a receiving water. It carries the ``citation`` of the
  document that names it, and the ``echo_value`` ECHO itself returned when the correction
  was reviewed (normally ``null``).
* A correction **never silently overrides live ECHO**. If ECHO now asserts something else,
  that's a ``conflict`` and the pull **refuses to write** until a human reconciles. If ECHO
  merely caught up and now says the same thing, that's ``superseded``: not a disagreement,
  so the write proceeds on ECHO's own value and the run reports the entry as retirable.
* A correction whose facility is **gone** from a pull that covered its subbasin is
  ``stale`` and also refuses — a terminated or re-keyed permit is a reviewable event, not
  a silent drop. (A pull of *other* subbasins simply leaves it ``out_of_scope``.)
* ``mode: caveat`` records the correction **without** touching the field, preserving the
  reviewed decision that a given row's ``receiving_water`` should keep mirroring ECHO
  verbatim (OH0135569, #379). Flipping it to ``mode: field`` is a one-word reviewed edit.

The emitted record keeps both values, so nothing is lost either way: ``receiving_water``
carries the curated value, ``receiving_water_echo`` the verbatim ECHO one.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from watermark.config import Settings, get_settings
from watermark.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only, keeps this module import-cycle free
    from watermark.hydrology.connectors.echo import Basin, Facility

log = get_logger(__name__)

__all__ = [
    "AppliedCorrection",
    "Curation",
    "CurationError",
    "CurationOverlay",
    "ReceivingWaterCorrection",
    "curate",
    "load_overlay",
    "overlay_path",
    "overlay_relpath",
]

# Overlays live in their own subdirectory so the catalog's fileset grouping never mistakes
# a hand-authored overlay for connector output (`<stem>.*` in data/reference/echo/).
_CURATION_SUBDIR = "curation"

# How a correction reaches the emitted inventory.
#   field  — write the curated value into `receiving_water` (ECHO's own value is preserved
#            alongside as `receiving_water_echo`), so downstream screens can use it.
#   caveat — leave the field mirroring ECHO verbatim; record the correction in the row's
#            `receiving_water_documented` + the file's meta caveats only.
CurationMode = Literal["field", "caveat"]

# What reconciling one correction against the live pull produced.
#   applied     — mode:field, ECHO unchanged; the curated value is in `receiving_water`.
#   documented  — mode:caveat, ECHO unchanged; recorded beside the untouched field.
#   out_of_scope— this pull didn't cover the correction's subbasin (a partial pull); skipped.
#   superseded  — ECHO now supplies the same water itself; the entry can be retired.
#   conflict    — ECHO now supplies a DIFFERENT water; a human must reconcile.
#   stale       — the facility is absent from a pull that did cover its subbasin.
CorrectionOutcome = Literal[
    "applied", "documented", "out_of_scope", "superseded", "conflict", "stale"
]

# Outcomes that mean the overlay no longer matches reality and a human must look.
_BLOCKING_OUTCOMES: frozenset[str] = frozenset({"conflict", "stale"})


class CurationError(RuntimeError):
    """The overlay no longer reconciles against live ECHO (conflict or stale entry)."""


def _norm(value: str | None) -> str | None:
    """Case/whitespace-insensitive surface form for comparing two ECHO water-body strings."""
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed.casefold() or None


class ReceivingWaterCorrection(BaseModel):
    """One cited receiving-water correction to an ECHO row.

    ``frs_registry_id`` is the hard identity assertion (it is the inventory's dedup key and
    is stable); ``facility`` is ECHO's ``CWPName`` at review time, recorded for readability
    and only *logged* on a mismatch — ECHO renames facilities routinely
    ("SHAWNEE NO 2 WWTP" -> "SHAWNEE II WWTP") and a name gate would fail on churn alone.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    npdes_id: str
    frs_registry_id: str
    facility: str
    huc8: str  # the subbasin the facility is pulled under — scopes the stale check
    receiving_water: str  # the corrected value, as the cited document names it
    echo_value: str | None = None  # CWPStateWaterBodyName observed when this was reviewed
    mode: CurationMode = "field"
    citation: str  # the document that names the receiving water
    issue: int | None = None  # the GitHub issue the correction was reviewed under
    caveat: str = Field(min_length=1)  # reviewed prose emitted into the file's meta.caveats


class OverlayMeta(BaseModel):
    """Provenance header of an overlay file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject: str
    basin: str  # the Basin slug this overlay belongs to; cross-checked on load
    rationale: str


class CurationOverlay(BaseModel):
    """A basin's committed receiving-water overlay."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: OverlayMeta
    corrections: list[ReceivingWaterCorrection] = Field(default_factory=list)


class AppliedCorrection(BaseModel):
    """One correction reconciled against the live pull."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correction: ReceivingWaterCorrection
    outcome: CorrectionOutcome
    echo_now: str | None = None  # CWPStateWaterBodyName in *this* pull

    @property
    def in_field(self) -> bool:
        """True iff this correction's value was written into ``receiving_water``."""
        return self.outcome == "applied"


class Curation(BaseModel):
    """The overlay as merged into one pull: what was applied, and where it came from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relpath: str | None = None  # overlay path relative to settings.data_dir (None = no overlay)
    applied: list[AppliedCorrection] = Field(default_factory=list)

    def by_frs(self) -> dict[str, AppliedCorrection]:
        """``{FRS Registry ID -> correction}`` for the corrections that reach a record.

        A ``superseded`` correction is redundant (ECHO now says it itself) and an
        ``out_of_scope`` one has no row in this pull, so neither annotates a record.
        """
        return {
            a.correction.frs_registry_id: a
            for a in self.applied
            if a.outcome in ("applied", "documented")
        }


def overlay_path(basin: Basin, *, settings: Settings | None = None) -> Path:
    """Where a basin's overlay lives (present or not)."""
    settings = settings or get_settings()
    return (
        settings.reference_dir
        / "echo"
        / _CURATION_SUBDIR
        / f"{basin.file_stem}.receiving-water.yaml"
    )


def overlay_relpath(basin: Basin) -> str:
    """The overlay's path relative to ``settings.data_dir`` (the catalog's addressing)."""
    return f"reference/echo/{_CURATION_SUBDIR}/{basin.file_stem}.receiving-water.yaml"


def load_overlay(basin: Basin, *, settings: Settings | None = None) -> CurationOverlay | None:
    """A basin's overlay, or ``None`` when it has no curated corrections.

    An absent file is the normal case (most basins need no correction) — never an error.
    A *present* file that names another basin is an error: an overlay merged into the wrong
    inventory would attach a citation to the wrong facility.
    """
    path = overlay_path(basin, settings=settings)
    if not path.is_file():
        return None
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overlay = CurationOverlay.model_validate(raw)
    if overlay.meta.basin != basin.slug:
        raise CurationError(
            f"{path} declares basin {overlay.meta.basin!r} but was loaded for {basin.slug!r}"
        )
    # Two entries for one facility would race: both reconcile against the same row, the last
    # `field` write silently wins, and only one survives the FRS-keyed record lookup. Refuse
    # at load rather than emit an inventory that reflects an arbitrary one of them.
    seen: set[str] = set()
    for correction in overlay.corrections:
        if correction.frs_registry_id in seen:
            raise CurationError(
                f"{path} has duplicate corrections for FRS {correction.frs_registry_id} "
                f"(at {correction.npdes_id}); one facility takes at most one correction"
            )
        seen.add(correction.frs_registry_id)
    return overlay


def _reconcile_one(
    correction: ReceivingWaterCorrection,
    fac: Facility | None,
    queried_huc8s: frozenset[str],
) -> AppliedCorrection:
    """Classify one correction against the facility the live pull returned for it.

    ``queried_huc8s`` are the subbasins this pull actually covered: a correction the pull
    never looked for is ``out_of_scope``, not ``stale``, so a single-HUC pull isn't blocked
    by corrections belonging to the rest of the basin. On a full-basin pull (the refresh
    path) every subbasin is in scope, so a missing facility is always ``stale``.
    """
    if fac is None:
        missing: CorrectionOutcome = "stale" if correction.huc8 in queried_huc8s else "out_of_scope"
        return AppliedCorrection(correction=correction, outcome=missing)

    if fac.queried_huc8 != correction.huc8:
        # The FRS match is authoritative (ECHO re-derives HUCs); the declared huc8 only
        # scopes the stale check above, so a drift here is recorded, not fatal.
        log.info(
            "echo.curation.rehucked",
            npdes_id=correction.npdes_id,
            was=correction.huc8,
            now=fac.queried_huc8,
        )

    if fac.name and _norm(fac.name) != _norm(correction.facility):
        # Recorded, not fatal: ECHO renames facilities and the FRS ID already pinned identity.
        log.info(
            "echo.curation.renamed",
            npdes_id=correction.npdes_id,
            was=correction.facility,
            now=fac.name,
        )

    now = fac.receiving_water
    if _norm(now) != _norm(correction.echo_value):
        # ECHO moved off the value this correction was reviewed against.
        outcome: CorrectionOutcome = (
            "superseded" if _norm(now) == _norm(correction.receiving_water) else "conflict"
        )
        return AppliedCorrection(correction=correction, outcome=outcome, echo_now=now)

    return AppliedCorrection(
        correction=correction,
        outcome="applied" if correction.mode == "field" else "documented",
        echo_now=now,
    )


def _blocking_message(blocked: list[AppliedCorrection], relpath: str) -> str:
    lines = [
        f"{len(blocked)} curated receiving-water correction(s) in {relpath} no longer "
        "reconcile against live ECHO; review them before rewriting the inventory:"
    ]
    for a in blocked:
        c = a.correction
        if a.outcome == "stale":
            lines.append(
                f"  - {c.npdes_id} ({c.facility}, FRS {c.frs_registry_id}): stale — no such "
                "facility in this pull. The permit may have been terminated or re-keyed; "
                "confirm and retire or re-point the entry."
            )
        else:
            lines.append(
                f"  - {c.npdes_id} ({c.facility}): conflict — ECHO now returns "
                f"{a.echo_now!r}, but the entry was reviewed against {c.echo_value!r} and "
                f"corrects to {c.receiving_water!r} per {c.citation}. Reconcile the "
                "document against ECHO, then update or retire the entry."
            )
    return "\n".join(lines)


def curate(
    facilities: list[Facility],
    basin: Basin,
    *,
    queried_huc8s: frozenset[str],
    settings: Settings | None = None,
) -> Curation:
    """Merge a basin's overlay into a freshly pulled facility list, in place.

    ``mode: field`` corrections have their curated value written into
    ``Facility.receiving_water`` (so the connector's derived flags — ``ottawa_discharge`` —
    and every downstream screen see it); ECHO's verbatim value is handed back on the
    returned :class:`Curation` for the record's ``receiving_water_echo``.

    ``queried_huc8s`` is the set of subbasins this pull actually *asked* ECHO for — required,
    and deliberately not inferred from ``facilities``: a HUC that returned zero rows leaves no
    trace on them, so inferring scope would quietly downgrade a genuine ``stale`` (the
    facility vanished) to ``out_of_scope`` (we never looked) and let the write proceed —
    exactly the silent drop this overlay exists to prevent.

    Raises :class:`CurationError` if any correction is ``conflict`` or ``stale`` — refusing
    to write a half-reviewed inventory is the whole point (#1698).
    """
    overlay = load_overlay(basin, settings=settings)
    if overlay is None:
        return Curation()

    by_frs = {f.frs_registry_id: f for f in facilities if f.frs_registry_id}
    applied = [
        _reconcile_one(c, by_frs.get(c.frs_registry_id), queried_huc8s) for c in overlay.corrections
    ]

    blocked = [a for a in applied if a.outcome in _BLOCKING_OUTCOMES]
    if blocked:
        raise CurationError(_blocking_message(blocked, overlay_relpath(basin)))

    for entry in applied:
        if entry.outcome == "out_of_scope":
            continue
        if entry.outcome == "superseded":
            log.warning(
                "echo.curation.superseded",
                npdes_id=entry.correction.npdes_id,
                value=entry.echo_now,
                hint="ECHO now supplies this receiving water; retire the overlay entry",
            )
            continue
        if entry.in_field:
            fac = by_frs[entry.correction.frs_registry_id]
            fac.receiving_water = entry.correction.receiving_water

    return Curation(relpath=overlay_relpath(basin), applied=applied)


def record_fields(entry: AppliedCorrection) -> dict[str, Any]:
    """The provenance keys a curated facility record carries beside ``receiving_water``.

    ``applied`` rows advertise that the field is curated and keep ECHO's verbatim value;
    ``documented`` rows keep the ECHO-verbatim field and carry the correction alongside.

    ``receiving_water_echo`` is what ECHO returned in **this** pull, not the reviewed
    ``echo_value`` it was matched against: the two agree only after normalization, so using
    the overlay's copy would report a stale surface form as if it were the live one.
    """
    c = entry.correction
    if entry.outcome == "applied":
        return {
            "receiving_water_source": "curated",
            "receiving_water_echo": entry.echo_now,
            "receiving_water_citation": c.citation,
        }
    if entry.outcome == "documented":
        return {
            "receiving_water_documented": c.receiving_water,
            "receiving_water_citation": c.citation,
        }
    return {}


def meta_block(curation: Curation, present_frs: set[str]) -> dict[str, Any] | None:
    """The machine-readable ``meta.receiving_water_curation`` block for one emitted file.

    Scoped to the corrections whose facility is actually *in* this file, so the POTW-only
    inventory never advertises a correction to a non-POTW row it doesn't contain.
    """
    entries = [a for a in curation.applied if a.correction.frs_registry_id in present_frs]
    if not entries or curation.relpath is None:
        return None
    return {
        "overlay": curation.relpath,
        "corrections": [
            {
                "npdes_id": a.correction.npdes_id,
                "frs_registry_id": a.correction.frs_registry_id,
                "mode": a.correction.mode,
                "outcome": a.outcome,
                "receiving_water": a.correction.receiving_water,
                "echo_value": a.correction.echo_value,
                "citation": a.correction.citation,
                "issue": a.correction.issue,
            }
            for a in entries
        ],
    }


def caveats(curation: Curation, present_frs: set[str]) -> list[str]:
    """The reviewed caveat prose for the corrections present in one emitted file."""
    return [
        a.correction.caveat
        for a in curation.applied
        if a.correction.frs_registry_id in present_frs and a.outcome != "superseded"
    ]
