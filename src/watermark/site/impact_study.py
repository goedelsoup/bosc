"""The ``impact-study`` bundle feed (#1804, epic #1803 P1) — the study's data spine, exported.

The missing-impact-study epic (PRs #1795-#1802) built each site's primary artifact — the
environmental + economic impact study communities never receive — as a frontend derivation:
``web/packages/core/src/study.ts`` composes a per-chapter verdict + model from the bundle's
feeds at the Astro build. This module is that derivation's **Python realization**: a pure
post-pass PROJECTION over the feeds ``export_bundle`` has already assembled (the
``open_questions`` pattern — no corpus re-load, no new claims), emitting one
:class:`~watermark.site.feeds.ImpactStudyItem` per study chapter so the study ships as a
committed, citable, catalogued artifact.

**Parity is the contract.** The frontend prefers a shipped row WHOLESALE (exact
``(chapter, facility_key)`` match) over its TS composers, so a divergence here silently
changes a published verdict. Every derivation below — the chapter registry, the status
rules (row counts + content probes, never presence alone), the probe copy, the composer
output down to the JS number formatting — mirrors ``study.ts`` line-for-line, and the
frontend's ``study.parity.test.ts`` pins the two derivations equal over every committed
bundle. Change the two files together or not at all.

Three disciplines carry over verbatim (see the ``study.ts`` module header):

- **The study never locks.** An absent feed is content (a ``gap`` finding or an ``na``
  watch state), never a lock; ``hasEnough`` semantics are deliberately not consulted.
- **Verdicts measure the record, not the lifecycle.** A facility's
  ``investigation → live`` clock changes framing copy only.
- **Multi-project forward-compat, no compute change.** Rows are keyed
  ``(chapter, facility_key)`` and emit the resolved PRIMARY campus only; a second campus
  later gets its own rows without rearchitecting.

The curated gap → lead joins (``STUDY_GAP_LEADS``) live here now — ONE owner (the TS copy
retired with the feed cutover). Strictly curated, never a fuzzy keyword match; an id that
stops reconciling against the site's own ``leads`` feed **fails the export loudly** rather
than shipping a dangling join (the drift-test discipline, moved to the producer).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from watermark.site.feeds import (
    ImpactStudyItem,
    StudyBasis,
    StudyChapterModel,
    StudyChapterStatus,
    StudyEvidence,
    StudyGap,
    StudyStat,
)
from watermark.site.readiness import State

# --- JS-parity primitives ---------------------------------------------------------------
# The frontend formats every display string with JS semantics (`format.ts`, template
# literals, `toFixed`). The shipped strings must be byte-identical, so these mirror the JS
# operations rather than reaching for Python's own rounding/str conventions.

# Escaped (not literal) so RUF001's confusable check doesn't trip on chars the frontend
# genuinely prints: EN DASH (the `fmtRanged` range separator) and MULTIPLICATION SIGN.
_EN_DASH = "\u2013"
_MULT_SIGN = "\u00d7"


def _js_round(n: float, decimals: int = 0) -> float:
    """JS ``Math.round(n * 10**d) / 10**d`` — half-up toward +∞, not banker's rounding."""
    f = 10.0**decimals
    return math.floor(n * f + 0.5) / f


def _js_num(v: float) -> str:
    """A JS ``${number}`` — integral values print bare, the rest shortest-roundtrip."""
    if math.isfinite(v) and v == int(v):
        return str(int(v))
    return repr(v)


def _js_to_fixed(x: float, digits: int) -> str:
    """JS ``Number.prototype.toFixed`` — decimal rounding of the exact binary value."""
    q = Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return f"{q:.{digits}f}"


def _fmt_ranged(
    value: float | None,
    low: float | None,
    high: float | None,
    decimals: int,
    unit: str | None = None,
) -> str:
    """``format.ts`` ``fmtRanged`` — the #760 uncertainty-band presentation, ported."""
    if value is None:
        return "—"
    u = f" {unit}" if unit else ""
    v = _js_round(value, decimals)
    if low is None and high is None:
        return f"{_js_num(v)}{u}"
    d_lo = value - low if low is not None else None
    d_hi = high - value if high is not None else None
    # Symmetric two-sided band (bounds equidistant within 5% of the spread) → the ± form.
    if d_lo is not None and d_hi is not None:
        spread = max(d_lo, d_hi)
        if abs(d_lo - d_hi) <= 0.05 * max(spread, 1e-9):
            return f"{_js_num(v)} ± ~{_js_num(_js_round((d_lo + d_hi) / 2, decimals))}{u}"
    lo = _js_round(low if low is not None else value, decimals)
    hi = _js_round(high if high is not None else value, decimals)
    return f"{_js_num(v)} ({_js_num(lo)}{_EN_DASH}{_js_num(hi)}{u})"


def _fmt_mult(m: float) -> str:
    """``format.ts`` ``fmtMult`` — a ratio multiple: integer at ≥10, else one decimal."""
    if not math.isfinite(m):
        return f"∞{_MULT_SIGN}"
    return (
        f"{_js_num(_js_round(m))}{_MULT_SIGN}" if m >= 10 else f"{_js_to_fixed(m, 1)}{_MULT_SIGN}"
    )


# --- the chapter registry (the `study.ts` mirror) -----------------------------------------


@dataclass(frozen=True)
class _ChapterDef:
    """One study chapter's derivation inputs — the Python `StudyChapterDef`."""

    id: str
    required_feeds: tuple[str, ...] = ()
    # When True, the required feeds are alternatives — any ONE lifts the chapter out of gap.
    any_required: bool = False
    optional_feeds: tuple[str, ...] = ()
    gap: StudyGap = field(default_factory=lambda: StudyGap(would_screen="—", missing_record="—"))
    # Project-dependent chapters read `na` (watch state) for a facility-less site.
    project_dependent: bool = False
    # `probe` / `derive` names dispatch into _PROBES / _DERIVES (a frozen dataclass can't
    # carry the closures directly without upsetting hashability/mypy).
    probe: str | None = None
    derive: str | None = None


_NA_REASON = "No disclosed project — this chapter is computed the day one is on the record."

# The chapters whose screens the balance chapter aggregates (feed-shaped verdicts only).
# The record groups the two corpus-keyed chapters screen on (`study.ts` `ASSEMBLY_GROUPS` /
# `GOVERNANCE_GROUPS`).
_ASSEMBLY_GROUPS = ("land-assembly", "deeds")
_GOVERNANCE_GROUPS = ("local-legislation", "litigation")

_SCREEN_CHAPTER_IDS = (
    "water-supply",
    "discharge",
    "heat",
    "groundwater",
    "stormwater",
    "air",
    "labor",
    "power",
)

_CHAPTERS: tuple[_ChapterDef, ...] = (
    # --- Part I · The project (front matter) ---
    _ChapterDef(id="method", derive="data"),
    _ChapterDef(
        id="project",
        required_feeds=("facility",),
        gap=StudyGap(
            would_screen="the project this study screens — its operator, scale, load, and cooling design.",
            missing_record=(
                "a disclosed project — none is on the record at this site yet; "
                "the day one is, this chapter names it."
            ),
            producer=(
                "the operator's own filings — a permit application, a rezoning, "
                "an interconnection request"
            ),
        ),
        probe="project",
    ),
    _ChapterDef(
        id="assembly",
        # Corpus-keyed, not facility-keyed (#1969), and deliberately NOT project_dependent:
        # speculative assembly PRECEDES the announcement, which is the shape of the Lima story.
        required_feeds=("records",),
        gap=StudyGap(
            would_screen=(
                "how the project's land was assembled — the conveyance chain, "
                "the buyers of record, and the dates."
            ),
            missing_record=(
                "the recorded deeds and the option or purchase instruments for the campus "
                "parcels — none produced into this record."
            ),
            producer="the county recorder and auditor — recorded instruments are public records",
        ),
        probe="assembly",
    ),
    # --- Part II · The environment ---
    _ChapterDef(
        id="water-supply",
        required_feeds=("hydrology-scenarios",),
        optional_feeds=("water-seasonal-field",),
        gap=StudyGap(
            would_screen=(
                "how much water this project consumes at buildout — monthly, against the "
                "receiving water's cited design low flows."
            ),
            missing_record=(
                "a disclosed cooling method and a metered or contracted water quantity; "
                "neither is on the record here."
            ),
            producer=(
                "the water utility's contract, a wastewater permit application, "
                "or the operator's cooling-plant spec"
            ),
        ),
        probe="water-supply",
        project_dependent=True,
    ),
    _ChapterDef(
        id="discharge",
        required_feeds=("hydrology-scenarios",),
        optional_feeds=("rsei",),
        gap=StudyGap(
            would_screen=(
                "the discharge screened against the receiving stream's assimilative capacity "
                "at its cited design low flows."
            ),
            missing_record="a discharge characterization for this project — none has been filed.",
            producer="an NPDES permit application and its fact sheet",
        ),
    ),
    _ChapterDef(
        id="heat",
        required_feeds=("thermal",),
        gap=StudyGap(
            would_screen=(
                "how much heat the discharge adds to a reach screened against Ohio's numeric "
                "temperature criterion at its design low flows."
            ),
            missing_record="a thermal characterization for this project — none exists on the record.",
            producer="the NPDES application's thermal load sheet, or the permit's §316(a) demonstration",
        ),
        project_dependent=True,
    ),
    _ChapterDef(
        id="groundwater",
        required_feeds=("drawdown", "dewatering"),
        any_required=True,
        gap=StudyGap(
            would_screen=(
                "the wells within the drawdown radius, and whether construction dewatering "
                "was permitted and where the water went."
            ),
            missing_record="a well survey and any dewatering record — neither has been produced.",
            producer="state well logs, a dewatering permit, and the contractor's discharge records",
        ),
        project_dependent=True,
    ),
    _ChapterDef(
        id="stormwater",
        required_feeds=("reach-network",),
        optional_feeds=("routed-hydrograph",),
        gap=StudyGap(
            would_screen=(
                "the runoff a campus-scale impervious surface adds to the design storm, "
                "routed down the reach."
            ),
            missing_record="the site grading and drainage plan — requested, not produced.",
            producer="the site plan's grading/drainage sheets and the construction stormwater permit (NOI)",
        ),
        project_dependent=True,
    ),
    _ChapterDef(
        id="air",
        required_feeds=("air-dispersion",),
        optional_feeds=("air-dispersion-field", "air-scenarios"),
        gap=StudyGap(
            would_screen="the dispersion footprint of the campus's permitted backup-generator fleet.",
            missing_record="an air-permit application for this project — none is on the record.",
            producer="the state air permit application (PTI/Title V) and its emissions tables",
        ),
        project_dependent=True,
    ),
    # --- Part III · The economy ---
    _ChapterDef(
        id="labor",
        required_feeds=("economics-baseline",),
        gap=StudyGap(
            would_screen="the local labor baseline every jobs claim should be read against.",
            missing_record="the county employment baseline — not yet assembled for this site.",
            producer="BLS QCEW and Census ACS — public series; this gap closes on the next export",
        ),
    ),
    _ChapterDef(
        id="power",
        required_feeds=("grid",),
        optional_feeds=("economics-demand-pressure", "energy-burden", "consumer-energy"),
        gap=StudyGap(
            would_screen=(
                "the campus's load against the serving utility's, balancing authority's, "
                "and state's annual load."
            ),
            missing_record="the site's grid backdrop — not yet assembled.",
            producer="EIA-861/930 — public series; this gap closes on the next export",
        ),
        probe="power",
    ),
    _ChapterDef(
        id="fiscal",
        gap=StudyGap(
            would_screen=(
                "what tax revenue is being traded away and for how long, "
                "before the trade is approved."
            ),
            missing_record=(
                "the abatement agreement, the school-board resolution, and the county auditor's "
                "abatement report — all public records, none produced into this record."
            ),
            producer=(
                "the county auditor, the school board, and the enterprise-zone/CRA agreement itself"
            ),
        ),
        project_dependent=True,
        # Curated-only, gap-first by design: no fiscal feed exists, and none is fabricated.
        derive="fiscal",
    ),
    _ChapterDef(
        id="governance",
        # Corpus-keyed and deliberately NOT project_dependent (#1969): Mansfield carries a
        # governance record and no facility at all, and a project gate would read the corpus's
        # first documented REFUSAL as "nothing to say here".
        required_feeds=("records",),
        optional_feeds=("meetings",),
        gap=StudyGap(
            would_screen=(
                "the public decisions that approved or refused the project — the ordinances, "
                "resolutions, roll-call votes, and the minutes that carry them."
            ),
            missing_record=(
                "the legislative instruments and meeting minutes of the deciding bodies — "
                "none produced into this record."
            ),
            producer=(
                "the municipal clerk, the township trustees, and the county commissioners — "
                "R.C. 149.43 records"
            ),
        ),
        probe="governance",
    ),
    _ChapterDef(
        id="balance",
        gap=StudyGap(
            would_screen="the whole trade on one sheet — headroom given against benefits documented.",
            missing_record=(
                "no record of its own — it synthesizes the other chapters, and none of them "
                "has a record to draw on yet."
            ),
        ),
        project_dependent=True,
        derive="balance",
    ),
    # --- Part IV · What's missing (annex) ---
    _ChapterDef(id="missing", derive="data"),
)

_CHAPTER_IDS = frozenset(c.id for c in _CHAPTERS)

# Curated gap → lead joins, per site — the ONE owner (the `study.ts` copy retired at the
# feed cutover). Each entry says "this chapter's asks are ALREADY TRACKED as these leads";
# the study's gap panels and the annex inventory deep-link the board's own anchors, so the
# study and the leads board present ONE set of asks. Strictly curated, never a fuzzy
# keyword match (misattributing a gap is an evidentiary-discipline violation) — which is
# why a site whose leads don't correspond to a study ask (urbana today) is simply absent.
STUDY_GAP_LEADS: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "lima": {
        "water-supply": ("FORCEMAIN-MGD", "LIMA-WWTP-SHARE", "H1-DRAW"),
        "discharge": ("WWTP-PARAM-ASSIM", "OEPA-2DP00130"),
        "heat": ("THERMAL-NO-LIMIT",),
        "groundwater": ("DEWATERING-DRYWELL-NW",),
        "stormwater": ("ASWCD-PLANS", "ASWCD-04"),
        "air": ("PTI-313MW", "GH-160"),
        "power": ("PTI-313MW", "AEP-LYKA-OPSB"),
        "fiscal": ("PRR-04", "GH-35"),
    },
}

# The shared probe-level asks (`study.ts` `COOLING_GAP` / `LOAD_INSTRUMENT_GAP`).
_COOLING_GAP = StudyGap(
    would_screen="a single consumptive-draw figure against the receiving water's low-flow floor.",
    missing_record=(
        "any record of how the facility rejects heat — a water contract, a wastewater permit, "
        "or a cooling-plant spec; until one surfaces, the water figures stay a bracketed range "
        "across candidate archetypes."
    ),
    producer=(
        "the water utility, the wastewater permit file, or the operator's own "
        "engineering disclosure"
    ),
)

_LOAD_INSTRUMENT_GAP = StudyGap(
    would_screen=(
        "the campus's share of the serving utility's, balancing authority's, and state's "
        "annual load, from a grounded load figure."
    ),
    missing_record=(
        "an instrument that grounds the IT load — an air permit or an interconnection filing; "
        "the load on the record is a screening bracket."
    ),
    producer="the state air-permit file or the RTO interconnection queue",
)


# --- derivation context -------------------------------------------------------------------


@dataclass(frozen=True)
class _Ctx:
    """The projector's read surface: the assembled payloads + counts + the facility domain."""

    site: str
    payloads: Mapping[str, Any]
    counts: Mapping[str, int]
    facility_domain: State


@dataclass(frozen=True)
class _Composition:
    stats: tuple[StudyStat, ...] = ()
    gaps: tuple[StudyGap, ...] = ()
    caveats: tuple[str, ...] = ()


_EMPTY = _Composition()


def _rows(ctx: _Ctx, name: str) -> list[dict[str, Any]]:
    v = ctx.payloads.get(name)
    return v if isinstance(v, list) else []


def _obj(ctx: _Ctx, name: str) -> dict[str, Any] | None:
    v = ctx.payloads.get(name)
    return v if isinstance(v, dict) else None


def _feed_rows(ctx: _Ctx, name: str) -> int:
    """A feed's row count (0 when absent) — never presence alone (`study.ts` `feedRows`):
    a present-but-empty collection (fort-wayne's zero-row scenarios) is NOT on the record."""
    return ctx.counts.get(name, 0)


def _record_group_rows(ctx: _Ctx, groups: tuple[str, ...]) -> int:
    """Rows in the site's OWN records feed carrying any of ``groups`` (`study.ts`
    ``recordGroupRows``) — the corpus-keyed primitive `assembly` / `governance` screen on.

    A raw read, matching the TS side: the frontend's readiness-gated ``citeGroups`` is the
    tempting reuse there, but a verdict that ran through a gate this projector cannot see would
    break parity the first time a site's record facet locked with rows on disk.
    """
    return sum(1 for r in _rows(ctx, "records") if r.get("group") in groups)


def _resolve_facility(ctx: _Ctx) -> dict[str, Any] | None:
    """The primary campus row (`resolveStudyFacility` with no key — the v1 emission)."""
    rows = _rows(ctx, "facility")
    return next((r for r in rows if r.get("is_primary")), rows[0] if rows else None)


def _chapter_gap(d: _ChapterDef, ctx: _Ctx, facility: dict[str, Any] | None) -> StudyGap:
    """A chapter's gap framing, narrowed to what is ACTUALLY missing for this site (#1983).

    ``_ChapterDef.gap`` is written for the common case, which for ``water-supply`` is a facility
    that discloses neither its cooling method nor a water quantity. A facility that DOES disclose
    the method (West Union / Buck Canyon: hybrid/adiabatic, ~97% air, from Amazon's own brochure)
    would otherwise be told the method is missing — asserting an absence the record contradicts.
    The gap is narrowed to the quantity, which is the half genuinely `[open]`.

    ``off`` is deliberately NOT a disclosed method here: it means there is no cooling-water load
    to quantify at all (a federal enclave — WPAFB), so narrowing the gap to "no quantity" would
    assert a missing figure that the archetype says cannot exist.
    """
    if (
        d.id == "water-supply"
        and facility is not None
        and facility.get("cooling_model") not in (None, "off")
        and not _cooling_undisclosed(ctx, facility)
    ):
        return d.gap.model_copy(
            update={
                "missing_record": (
                    "a metered, contracted or permit-grounded water quantity — the cooling "
                    "method is disclosed here, but no quantity is."
                )
            }
        )
    return d.gap


def _cooling_undisclosed(ctx: _Ctx, facility: dict[str, Any] | None) -> bool:
    """`study.ts` `coolingUndisclosed`: the scenario rows' probe (#1057) OR the facility row."""
    if facility is not None and facility.get("cooling_model") == "unknown":
        return True
    for r in _rows(ctx, "hydrology-scenarios"):
        scenario = r.get("scenario") or {}
        cm = r.get("cooling_model")
        if cm is None:
            cm = scenario.get("cooling_model")
        if cm == "unknown" or (scenario.get("basis") or {}).get("method_disclosed") is False:
            return True
    return False


def _facility_load_available(ctx: _Ctx) -> bool:
    """`readiness.ts` `facilityLoadAvailable` — the facility domain is instrument-grounded."""
    return ctx.facility_domain == "live"


# --- status derivation (`chapterAvailability`) ----------------------------------------------


def _probes(d: _ChapterDef, ctx: _Ctx, facility: dict[str, Any] | None) -> list[str]:
    if d.probe == "project":
        if ctx.facility_domain == "live":
            return []
        # A facility whose load is entirely `[open]` has no bracket to describe (#1983): saying
        # "a screening bracket" would assert a figure the record does not carry. West Union /
        # Buck Canyon is the first — the campus is disclosed, but the only MW on the record is
        # filed for an unnamed customer, so `SiteFacility.it_load_mw` is None.
        if facility is not None and facility.get("it_load_mw") is None:
            return [
                "the facility is disclosed but its IT load is not instrument-grounded — no "
                "instrument on the record states it"
            ]
        return [
            "the IT load on the record is a screening bracket, not an instrument-grounded figure"
        ]
    if d.probe == "water-supply":
        if _cooling_undisclosed(ctx, facility):
            return [
                "cooling method undisclosed — the water figures are a bracketed range across "
                "candidate archetypes, not an estimate"
            ]
        return []
    if d.probe == "assembly":
        if _record_group_rows(ctx, _ASSEMBLY_GROUPS) > 0:
            return []
        return [
            "the record carries no conveyance instrument — the land history has not been "
            "produced for this site"
        ]
    if d.probe == "governance":
        if _record_group_rows(ctx, _GOVERNANCE_GROUPS) > 0 or _feed_rows(ctx, "meetings") > 0:
            return []
        return [
            "the record carries no legislative instrument and no minutes — the decision path "
            "has not been produced for this site"
        ]
    if d.probe == "power":
        if facility is None:
            return [
                "no disclosed campus load to size against the grid — the backdrop stands on its own"
            ]
        if _facility_load_available(ctx):
            return []
        return [
            "the campus load is a screening bracket — the demand-pressure read is withheld "
            "until an instrument grounds it"
        ]
    return []


def _probe_or_data(
    d: _ChapterDef, ctx: _Ctx, facility: dict[str, Any] | None
) -> tuple[StudyChapterStatus, list[str]]:
    flags = _probes(d, ctx, facility)
    return ("partial", flags) if flags else ("data", [])


def _derive(
    d: _ChapterDef, ctx: _Ctx, facility: dict[str, Any] | None
) -> tuple[StudyChapterStatus, list[str]]:
    if d.derive == "data":
        return ("data", [])
    if d.derive == "fiscal":
        return ("gap", ["no fiscal instrument is on the record"])
    # balance: an aggregate verdict over the screened chapters (never fiscal's designed gap,
    # never itself): all data ⇒ data; anything on the record ⇒ partial; nothing ⇒ gap.
    statuses = [
        s
        for s in (_availability(_chapter(cid), ctx)[0] for cid in _SCREEN_CHAPTER_IDS)
        if s != "na"
    ]
    data = sum(1 for s in statuses if s == "data")
    partial = sum(1 for s in statuses if s == "partial")
    if statuses and data == len(statuses):
        return ("data", [])
    if data + partial > 0:
        return (
            "partial",
            [
                f"synthesizes the screened chapters — {data} on the record, {partial} partial, "
                f"{len(statuses) - data - partial} gap"
            ],
        )
    return ("gap", ["none of the screened chapters has a record to balance yet"])


def _chapter(chapter_id: str) -> _ChapterDef:
    for c in _CHAPTERS:
        if c.id == chapter_id:
            return c
    raise KeyError(f"Unknown study chapter {chapter_id!r}")


def _availability(d: _ChapterDef, ctx: _Ctx) -> tuple[StudyChapterStatus, list[str]]:
    """A chapter's verdict — feed presence + row counts + content probes (`chapterAvailability`)."""
    facility = _resolve_facility(ctx)
    if d.project_dependent and facility is None:
        return ("na", [_NA_REASON])
    if d.derive is not None:
        return _derive(d, ctx, facility)

    present = [f for f in d.required_feeds if _feed_rows(ctx, f) > 0]
    optional_present = [f for f in d.optional_feeds if _feed_rows(ctx, f) > 0]
    if not present and not optional_present:
        return ("gap", [_chapter_gap(d, ctx, facility).missing_record])
    if len(present) < len(d.required_feeds):
        # `any_required` feeds are alternatives (either groundwater screen suffices).
        if d.any_required and present:
            return _probe_or_data(d, ctx, facility)
        missing = [f for f in d.required_feeds if f not in present]
        return (
            "partial",
            ["baseline context only — the project-side record has not been produced"]
            if not present
            else [f"no {f} on the record for this site" for f in missing],
        )
    return _probe_or_data(d, ctx, facility)


# --- composers ------------------------------------------------------------------------------


def _pv_stat(
    label: str,
    pv: Mapping[str, Any] | None,
    evidence: StudyEvidence,
    *,
    basis: StudyBasis | None = None,
    sub: str | None = None,
    source: str | None = None,
) -> StudyStat | None:
    """`study.ts` `pvStat` — a ProvenancedValue as a headline stat, or None when empty.

    ``source`` overrides the value's own ``source`` kind when given (the TS `extra` spread).
    """
    if pv is None or pv.get("value") is None:
        return None
    return StudyStat(
        label=label,
        value=_fmt_ranged(pv.get("value"), pv.get("low"), pv.get("high"), 1),
        unit=pv.get("unit"),
        evidence=evidence,
        basis=basis,
        sub=sub,
        source=source if source is not None else pv.get("source"),
    )


def _compose_project(ctx: _Ctx, facility: dict[str, Any] | None) -> _Composition:
    if facility is None:
        return _EMPTY
    stats: list[StudyStat] = []
    it_load = facility.get("it_load_mw")
    low = facility.get("it_load_low_mw")
    high = facility.get("it_load_high_mw")
    if low is not None or it_load is not None:
        grounded = ctx.facility_domain == "live"
        value = (
            f"{_js_num(_js_round(low))}{_EN_DASH}{_js_num(_js_round(high))}"
            if low is not None and high is not None
            else _js_num(_js_round(it_load if it_load is not None else (low or 0)))
        )
        stats.append(
            StudyStat(
                label="IT load",
                value=value,
                unit="MW",
                evidence="inference",
                basis="modeled",
                sub=(
                    "bracket grounded by an instrument on the record"
                    if grounded
                    else "screening bracket — no instrument grounds it yet"
                ),
                source=(
                    "air permit (committed)"
                    if facility.get("air_permit_citation")
                    else "screening estimate"
                ),
            )
        )
    cooling_model = facility.get("cooling_model")
    cooling_source = facility.get("cooling_model_source")
    stats.append(
        StudyStat(
            label="Cooling",
            value=(
                "not disclosed"
                if cooling_model == "unknown"
                else str(cooling_model).replace("_", " ")
            ),
            evidence=(
                "open"
                if cooling_model == "unknown"
                else ("verified" if cooling_source in ("document", "connector") else "inference")
            ),
            sub=(
                "an operator claim — a claim is not an instrument"
                if cooling_source == "reference"
                else None
            ),
        )
    )
    caveats: list[str] = []
    if facility.get("status") == "investigation":
        caveats.append(
            "Reported, not confirmed: every project-dependent figure in this study is "
            "conditional on the project proceeding."
        )
    return _Composition(stats=tuple(stats), caveats=tuple(caveats))


def _compose_water_supply(ctx: _Ctx, facility: dict[str, Any] | None) -> _Composition:
    if _feed_rows(ctx, "hydrology-scenarios") == 0:
        return _EMPTY
    rows = _rows(ctx, "hydrology-scenarios")
    stats: list[StudyStat] = []
    worst: dict[str, Any] | None = None
    for r in rows:
        if worst is None or ((r.get("consumptive_loss") or {}).get("value") or 0) > (
            (worst.get("consumptive_loss") or {}).get("value") or 0
        ):
            worst = r
    if worst is not None:
        s = _pv_stat(
            "Worst-case consumptive draw",
            worst.get("consumptive_loss"),
            "inference",
            basis="modeled",
            sub=f"scenario: {(worst.get('scenario') or {}).get('name')}",
        )
        if s is not None:
            stats.append(s)
        floor = _pv_stat(
            "Receiving low flow (7Q10)",
            worst.get("receiving_7q10"),
            "verified",
            basis="grounded",
            sub=worst.get("receiving_water_name"),
        )
        if floor is not None:
            stats.append(floor)
    gaps = (_COOLING_GAP,) if _cooling_undisclosed(ctx, facility) else ()
    return _Composition(
        stats=tuple(stats),
        gaps=gaps,
        caveats=(
            "The draw is set against the receiving water's cited design low flow as a "
            "worst-case, basin-scale bound — a screening comparison, not a withdrawal claim.",
        ),
    )


def _compose_discharge(ctx: _Ctx, _facility: dict[str, Any] | None) -> _Composition:
    if _feed_rows(ctx, "hydrology-scenarios") == 0:
        return _Composition(
            caveats=(
                "Only the receiving water's existing burden is on the record here — the "
                "project-side discharge screen renders the day a characterization is filed.",
            )
        )
    checks = [c for r in _rows(ctx, "hydrology-scenarios") for c in r.get("assimilative") or []]
    if not checks:
        return _EMPTY
    worst = checks[0]
    for c in checks[1:]:
        if c["dilution_ratio"] < worst["dilution_ratio"]:
            worst = c
    return _Composition(
        stats=(
            StudyStat(
                label="Tightest chronic dilution",
                value=_fmt_mult(worst["dilution_ratio"]),
                evidence="verified",
                basis="grounded",
                sub=f"{worst['discharger']} → {worst['receiving_water']}",
                warn=worst.get("flag") == "violation",
            ),
        )
    )


def _thermal_chronic(screens: list[dict[str, Any]]) -> dict[str, Any] | None:
    """`thermal.ts` `buildThermal`'s chronic-screen read — the reach's 7Q10 row, consistency-
    checked across every screen (they screen the same water; disagreement is a defect)."""

    def flow_at(row: Mapping[str, Any]) -> dict[str, Any] | None:
        for f in row.get("flow_screens") or []:
            if f.get("flow_label") == "7Q10":
                return dict(f)
        return None

    chronics = [f for f in (flow_at(s) for s in screens) if f is not None]
    chronic = chronics[0] if chronics else None
    if chronic is not None:
        for f in chronics:
            if f.get("thermal_capacity_mw") != chronic.get("thermal_capacity_mw") or (
                f.get("design_flow") or {}
            ).get("value") != (chronic.get("design_flow") or {}).get("value"):
                raise ValueError(
                    "impact-study: thermal rows disagree on the reach's 7Q10 screen — "
                    "a defect in the screen, not a display choice (see thermal.ts)"
                )
    return chronic


def _compose_heat(ctx: _Ctx, _facility: dict[str, Any] | None) -> _Composition:
    report = _obj(ctx, "thermal")
    if report is None:
        return _EMPTY
    meta = report.get("meta") or {}
    screens = list(report.get("screens") or [])
    criterion = meta.get("daily_max_c")
    ambient = meta.get("ambient_c")
    headroom = (
        _js_round(criterion - ambient, 1) if criterion is not None and ambient is not None else None
    )
    river = meta.get("receiving_water") or "the receiving water"
    chronic = _thermal_chronic(screens)
    capacity = chronic.get("thermal_capacity_mw") if chronic is not None else None
    stats: list[StudyStat] = []
    if headroom is not None:
        stats.append(
            StudyStat(
                label="Thermal headroom at design low flow",
                value=_js_num(headroom),
                unit="°C",
                evidence="inference",
                basis="modeled",
                sub=river,
                warn=headroom <= 0,
            )
        )
    if capacity is not None:
        stats.append(
            StudyStat(
                label="Reach thermal capacity",
                value=_js_num(_js_round(capacity, 1)),
                unit="MW",
                evidence="inference",
                basis="modeled",
            )
        )
    ambient_grounded = meta.get("ambient_source") in ("connector", "document")
    return _Composition(
        stats=tuple(stats),
        caveats=()
        if ambient_grounded
        else (
            "The design ambient is the zone's seasonal criterion standing in, not a measured "
            "in-stream temperature — the capacity moves with that choice.",
        ),
    )


def _compose_labor(ctx: _Ctx, _facility: dict[str, Any] | None) -> _Composition:
    if _feed_rows(ctx, "economics-baseline") == 0:
        return _EMPTY
    eb = _obj(ctx, "economics-baseline") or {}
    latest = eb.get("latest") or {}
    stats: list[StudyStat] = []
    emp = _pv_stat(
        "County employment",
        latest.get("total_employment"),
        "verified",
        basis="grounded",
        sub=f"{eb.get('area_name')} · {latest.get('year')}",
        source="BLS QCEW",
    )
    if emp is not None:
        stats.append(emp)
    return _Composition(
        stats=tuple(stats),
        caveats=(
            "Any jobs claim reads against this baseline as claim vs. denominator — the study "
            "never computes a jobs multiplier.",
        ),
    )


def _compose_power(ctx: _Ctx, facility: dict[str, Any] | None) -> _Composition:
    gp = _obj(ctx, "grid")
    if gp is None:
        return _EMPTY
    utility_profile = gp.get("utility_profile") or {}
    ba_profile = gp.get("ba_profile") or {}
    share = gp.get("load_share")
    # `gridBackdrop.ts`: the utility denominator (and so its share) exists only when the
    # cited retail-sales figure is a real positive number — never a zero baseline.
    retail = (utility_profile.get("retail_sales_gwh") or {}).get("value")
    utility_share = None
    if retail is not None and retail > 0 and share is not None:
        utility_share = (share.get("share_of_utility_pct") or {}).get("value")
    campus_load = None
    if (
        share is not None
        and (share.get("campus_load_mw") or {}).get("value") is not None
        and (share.get("annual_consumption_gwh") or {}).get("value") is not None
    ):
        campus_load = share["campus_load_mw"]["value"]
    stats: list[StudyStat] = [
        StudyStat(
            label="Serving utility",
            value=str(utility_profile.get("utility")),
            evidence="verified",
            basis="grounded",
            sub=str(ba_profile.get("ba")),
        )
    ]
    if campus_load is not None and utility_share is not None:
        stats.append(
            StudyStat(
                label="Campus share of utility load",
                value=f"{_js_to_fixed(utility_share, 2)}%",
                evidence="inference",
                basis="modeled",
                sub=f"~{_js_num(_js_round(campus_load))} MW disclosed campus draw",
            )
        )
    gaps = (
        (_LOAD_INSTRUMENT_GAP,)
        if facility is not None and not _facility_load_available(ctx)
        else ()
    )
    caveats: list[str] = []
    if _facility_load_available(ctx):
        pressure = _obj(ctx, "economics-demand-pressure")
        if pressure is not None and pressure.get("caveats"):
            caveats.extend(pressure["caveats"])
    note = gp.get("note") or ""
    if note:
        caveats.append(note)
    return _Composition(stats=tuple(stats), gaps=gaps, caveats=tuple(caveats))


def _compose_fiscal(_ctx: _Ctx, facility: dict[str, Any] | None) -> _Composition:
    caveats: list[str] = []
    investment = facility.get("disclosed_investment_usd") if facility is not None else None
    if investment is not None:
        caveats.append(
            f"Disclosed investment: ${_js_to_fixed(investment / 1e9, 1)}B — the operator's own "
            "announcement, not an instrument; the abatement agreement that would price the "
            "trade is not on the record."
        )
    return _Composition(caveats=tuple(caveats))


def _compose_assembly(ctx: _Ctx, _facility: dict[str, Any] | None) -> _Composition:
    """The conveyance count (`study.ts` `COMPOSERS.assembly`).

    Counts ONLY rows in the groups the chapter declares, so a ``verified`` stat exists exactly
    where the frontend's ``citeGroups`` can resolve a destination for it — the citation
    invariant holds by construction rather than by a listed exemption.
    """
    rows = _record_group_rows(ctx, _ASSEMBLY_GROUPS)
    if rows == 0:
        return _EMPTY
    return _Composition(
        stats=(
            StudyStat(
                label="Conveyance instruments",
                value=str(rows),
                evidence="verified",
                basis="grounded",
                sub="recorded deeds and assembly instruments on this site's record",
            ),
        ),
        caveats=(
            "A conveyance chain on the record is what was produced, not what exists — an "
            "assembly can run through options, nominees, and unrecorded agreements that no "
            "recorder's index will show.",
        ),
    )


def _compose_governance(ctx: _Ctx, _facility: dict[str, Any] | None) -> _Composition:
    """The legislative-instrument count (`study.ts` `COMPOSERS.governance`).

    ``meetings`` is a STATUS signal for this chapter, never a stat: a minutes count has no
    destination in the evidence annex's three bands, so asserting one as ``verified`` would be
    a provenance claim the page cannot honour.
    """
    instruments = _record_group_rows(ctx, _GOVERNANCE_GROUPS)
    if instruments == 0:
        return _EMPTY
    return _Composition(
        stats=(
            StudyStat(
                label="Legislative instruments",
                value=str(instruments),
                evidence="verified",
                basis="grounded",
                sub="resolutions, ordinances, and filed court instruments on this site's record",
            ),
        ),
        caveats=(
            "An instrument on the record says what was enacted, not what was decided — the "
            "deliberation that produced it lives in minutes and audio that are separate records.",
        ),
    )


_COMPOSERS: Mapping[str, Callable[[_Ctx, dict[str, Any] | None], _Composition]] = {
    "project": _compose_project,
    "assembly": _compose_assembly,
    "governance": _compose_governance,
    "water-supply": _compose_water_supply,
    "discharge": _compose_discharge,
    "heat": _compose_heat,
    "labor": _compose_labor,
    "power": _compose_power,
    "fiscal": _compose_fiscal,
}


# --- the projection entry point --------------------------------------------------------------


def _validate_curation(site: str, payloads_by_feed: Mapping[str, Any]) -> None:
    """Refuse to ship a dangling gap → lead join (the drift test, moved to the producer)."""
    curated = STUDY_GAP_LEADS.get(site)
    if not curated:
        return
    leads = payloads_by_feed.get("leads")
    known = {r.get("id") for r in leads} if isinstance(leads, list) else set()
    for chapter_id, ids in curated.items():
        if chapter_id not in _CHAPTER_IDS:
            raise ValueError(
                f"impact-study: STUDY_GAP_LEADS[{site!r}] names unknown chapter {chapter_id!r}"
            )
        for lead_id in ids:
            if lead_id not in known:
                raise ValueError(
                    f"impact-study: curated lead {lead_id!r} ({site}/{chapter_id}) is not on "
                    "the site's leads board — reconcile STUDY_GAP_LEADS against data/site/"
                    "leads.yaml instead of shipping a dangling join"
                )


def build_impact_study(
    payloads_by_feed: Mapping[str, Any],
    *,
    site: str,
    feed_counts: Mapping[str, int],
    facility_domain: State,
) -> list[ImpactStudyItem]:
    """Project the assembled feeds into the ``impact-study`` rows — 15 chapters, always.

    ``payloads_by_feed`` maps feed name → serialized rows (collections) / object payload;
    ``feed_counts`` maps feed name → manifest row count (the status derivation reads counts,
    never presence); ``facility_domain`` is the readiness facility state
    (:func:`watermark.site.readiness.domain_states` — profile-graded, so it equals what the
    manifest will carry and what the frontend probe reads back out of it).
    """
    _validate_curation(site, payloads_by_feed)
    ctx = _Ctx(
        site=site, payloads=payloads_by_feed, counts=feed_counts, facility_domain=facility_domain
    )
    facility = _resolve_facility(ctx)
    key = facility.get("key") if facility is not None else None

    items: list[ImpactStudyItem] = []
    for d in _CHAPTERS:
        status, reasons = _availability(d, ctx)
        composer = _COMPOSERS.get(d.id)
        composed = _EMPTY if status == "na" or composer is None else composer(ctx, facility)
        lead_ids = list(STUDY_GAP_LEADS.get(site, {}).get(d.id, ()))
        # The chapter-level gap framing renders whenever the chapter IS the finding; the
        # curated joins ride every gap that carries none of its own (one board, one ask).
        gaps = (
            [_chapter_gap(d, ctx, facility), *composed.gaps]
            if status == "gap"
            else list(composed.gaps)
        )
        gaps = [
            g.model_copy(update={"lead_ids": list(lead_ids)}) if lead_ids and not g.lead_ids else g
            for g in gaps
        ]
        items.append(
            ImpactStudyItem(
                chapter=d.id,
                facility_key=key,
                lead_ids=lead_ids,
                model=StudyChapterModel(
                    id=d.id,
                    facility_key=key,
                    status=status,
                    status_reasons=reasons,
                    stats=list(composed.stats),
                    gaps=gaps,
                    caveats=list(composed.caveats),
                ),
            )
        )
    return items


__all__ = ["STUDY_GAP_LEADS", "build_impact_study"]
