"""The data-center sweep methodology (single source) + the prose→candidate distillation (#1627).

Two things live here so they can't drift:

* :data:`SWEEP_METHODOLOGY` — the canonical discover-and-pin methodology block, previously
  duplicated between ``watermark.cli.sweep`` (the standalone sweep prompt) and
  ``watermark.research.run`` (the onboarding recipe's step 7). Both now embed *this* text.
* :func:`distill_candidates` — the structured read of a prose register into a validated
  :class:`~watermark.facility.candidate.SiteCandidates` via forced-tool-use (the same
  ``StructuredExtractor`` idiom the OPC extractor and the research recipes use). This closes the
  prose→structured seam: the sweep's output becomes consumable, not prose-only.

The distillation is a *reviewed* pass, like the sweep itself — its output is written
``needs-review`` for a human to check every ``[verified]`` tag against the cited instrument.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from watermark.agent.extractor import ExtractionError, StructuredExtractor
from watermark.facility.candidate import (
    CandidateStatus,
    DataCenterCandidate,
    ProvenancedFigure,
    SiteCandidates,
    build_candidate,
)
from watermark.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# The single methodology source (embedded by both the sweep prompt and the onboard recipe)
# ---------------------------------------------------------------------------

SWEEP_METHODOLOGY = """\
Follow the data-center-sweep skill methodology exactly.

STEP 1 — DISAMBIGUATION GUARDRAIL
Before recording any project, confirm it is physically located in the site's own county, not an
adjacent county. Check the street address and the resolution/deed text. Do not bridge Lima / Allen
County (OH) entities onto another county — there is no evidentiary link.

STEP 2 — CORRIDOR SWEEP
Use search_web to discover documented data-center projects along the I-75 corridor and rail freight
corridors near the site. Query patterns:
  "data center" <city> <state>
  "hyperscale" OR "cloud campus" <county>
  "data center" <city> "I-75"
  <city> "PILOT" OR "CRA" "data center"
  <city> "large load" OR "utility agreement" "data center"

STEP 3 — PRIMARY SOURCE FETCH
For every project found, call fetch_url on the city council resolution, municipal FAQ, or county
resolution that is the primary instrument for that project.

STEP 4 — REGULATORY SCAN
Search for Ohio EPA air PTI, NPDES stormwater coverage, and Ohio SOS entity registrations for any
operator found. Use the ECHO and OEPA tools if available; otherwise use search_web for the permit
reference and fetch_url on the OEPA/ECHO result page.

STEP 5 — NEGATIVE CHECKS
Call retrieve_corpus and check list_extractions for any existing data-center records. Check the
site's RSEI county inventory for NAICS 518210 entries; if inaccessible, note it as [open]. A clean
sweep is a result, not a failure — record each negative check explicitly.

Tag every claim with the BOSC evidence vocabulary: [verified] (a cited primary-source instrument),
[inference] (arithmetic from cited inputs), [reference] (secondary / trade-press / advocacy), [open]
(not yet found in any source). Never assert a figure as [verified] without the specific instrument
cited; prefer [open] over a value you cannot source. Do not fabricate figures."""


def build_sweep_prompt(*, city: str, county: str, state: str, site: str, rsei_fips: str) -> str:
    """The standalone ``watermark sweep data-centers`` prompt: site facts + shared methodology +
    the register-output instructions."""
    return f"""\
Perform a data-center activity sweep for {city} / {county}, {state} (site slug: {site}).
The RSEI county FIPS for this site = {rsei_fips}.

{SWEEP_METHODOLOGY}

STEP 6 — PRODUCE THE REGISTER
Write the full discover-and-pin register in the format defined by the data-center-sweep skill,
including:
  - Header with site name, county, and today's date
  - Disambiguation guardrail section
  - One numbered section per confirmed project (or "No activity found")
  - For each project: financial/tax instruments, water/hydrology hook, hydrology screen,
    regulatory record
  - Instruments to pull (priority order)
  - Sources section
"""


# ---------------------------------------------------------------------------
# prose register -> validated candidate records (forced tool use)
# ---------------------------------------------------------------------------

# Registers run ~10-25 KB; cap well above the largest so the whole register reaches the model.
_MAX_REGISTER_CHARS = 60_000
_DISTILL_ATTEMPTS = 3

_DISTILL_SYSTEM = (
    "You are a structured-data extractor. Always fill tool parameters with native JSON values: "
    "arrays as JSON arrays, objects as JSON objects — never as JSON-encoded strings. String fields "
    'may contain quotes; escape them properly as \\" in the JSON.'
)

_DISTILL_INSTRUCTIONS = """\
Convert this data-center activity register into structured candidate records. Use ONLY the register
text below — add no outside knowledge, invent no figures.

Emit ONE candidate per numbered project section (a "## N — Operator / Project" heading). Skip
"No activity found" / "No other activity" sections — those are negative results, not projects.

For each candidate:
- project_name: the developer's project name/codename, or null.
- operator: the developer/operator of record as a figure object (value = the entity name).
- status: one of proposed | approved | under_construction | operating | withdrawn | rejected |
  unknown, from the regulatory-record / timeline prose.
- location, county: short strings, or null.
- The disclosed figures (it_load_mw, gross_floor_area_sqft, investment_usd, acreage,
  water_draw_mgd, cooling, utility, npdes_permit, air_permit): each a figure object, or null if the
  register names no such dimension.
- register_prose: the full markdown of that project's section, verbatim.

Each FIGURE OBJECT is {value, unit, source_kind, citation, note}:
- value: the number (or short string for operator/cooling/utility/permit id). Use null when the
  register marks the item [open] / not disclosed — then leave source_kind and citation null and use
  note for the gap. NEVER invent a value to fill a gap.
- unit: "MW" | "USD" | "acres" | "sqft" | "MGD" | null.
- source_kind maps the register's evidence tag: [verified] -> "document" (a citable primary
  instrument) or "connector" (a live gauge); [reference] (trade press / advocacy / media) ->
  "reference"; [inference] (arithmetic) -> "derived". When the register tags a figure [verified] but
  cites only media, use "reference" — the tag follows the SOURCE, not the label.
- citation: the specific instrument / source named in the register (required whenever value is set).
"""

_T = TypeVar("_T")

# The figure fields a candidate carries, mapped 1:1 from the draft (keeps the two in sync).
_FIGURE_FIELDS = (
    "it_load_mw",
    "gross_floor_area_sqft",
    "investment_usd",
    "acreage",
    "water_draw_mgd",
    "cooling",
    "utility",
    "npdes_permit",
    "air_permit",
)


class _CandidateDraft(BaseModel):
    """The loose, LLM-facing shape — everything :class:`DataCenterCandidate` holds except ``key``
    (minted in code so dedupe never depends on model whim)."""

    model_config = ConfigDict(extra="forbid")

    project_name: str | None = None
    operator: ProvenancedFigure
    status: CandidateStatus = CandidateStatus.UNKNOWN
    location: str | None = None
    county: str | None = None
    it_load_mw: ProvenancedFigure | None = None
    gross_floor_area_sqft: ProvenancedFigure | None = None
    investment_usd: ProvenancedFigure | None = None
    acreage: ProvenancedFigure | None = None
    water_draw_mgd: ProvenancedFigure | None = None
    cooling: ProvenancedFigure | None = None
    utility: ProvenancedFigure | None = None
    npdes_permit: ProvenancedFigure | None = None
    air_permit: ProvenancedFigure | None = None
    register_prose: str = ""


class _CandidatesDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[_CandidateDraft] = []


def _with_retry(op: Callable[[], _T]) -> _T:
    """Re-roll a forced-tool-use distillation on a model quirk (peer of
    ``research.run._distill_with_retry`` — kept local so ``facility`` doesn't import ``research``)."""
    last_err: Exception | None = None
    for attempt in range(1, _DISTILL_ATTEMPTS + 1):
        try:
            return op()
        except (ValidationError, ExtractionError) as exc:  # model quirk; re-roll the draw
            last_err = exc
            log.warning(
                "facility.distill.retry",
                attempt=attempt,
                max=_DISTILL_ATTEMPTS,
                error=str(exc)[:160],
            )
    if last_err is None:  # unreachable: every failed attempt records last_err
        raise RuntimeError("candidate distillation failed with no recorded error")
    raise last_err


def distill_candidates(
    register_text: str,
    *,
    site: str,
    source_register: str,
    generated_at: str,
    extractor: StructuredExtractor,
) -> SiteCandidates:
    """Distill a prose data-center register into validated candidate records (forced tool use).

    The model drafts one candidate per numbered project; we mint the dedupe ``key`` in code and
    attach the run's ``generated_at`` / ``source_register``. Re-rolls on the forced-tool JSON quirk
    (same guard as the research distillers). ``extractor`` is injectable so callers/tests supply a
    fake Anthropic client — the distillation stays hermetic.
    """
    text = register_text[:_MAX_REGISTER_CHARS]

    def _draw() -> SiteCandidates:
        draft = extractor.extract_from_text(
            _CandidatesDraft,
            instructions=_DISTILL_INSTRUCTIONS,
            text=text,
            tool_name="record_data_center_candidates",
            system=_DISTILL_SYSTEM,
        )
        candidates: list[DataCenterCandidate] = [
            build_candidate(
                project_name=d.project_name,
                operator=d.operator,
                status=d.status,
                location=d.location,
                county=d.county,
                register_prose=d.register_prose,
                **{name: getattr(d, name) for name in _FIGURE_FIELDS},
            )
            for d in draft.candidates
        ]
        return SiteCandidates(
            site=site,
            generated_at=generated_at,
            source_register=source_register,
            candidates=candidates,
        )

    return _with_retry(_draw)
