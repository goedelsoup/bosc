"""The economic argument as disciplined scenario bands (#1665, epic #1659 ME-F).

The magnitudes that decide whether this deal was a good one — the abated base, the
sales-tax exemption, the subsidy per job, the load per job, the authorized-region (GovCloud)
premium that explains the *incentive* to build here — lived only in prose
(``docs/ECONOMICS.md`` §3/§4, ``docs/the-economic-ledger.md``) and in a hardcoded frontend
array. Prose drifts from its sources; a typed feed does not. This module computes them once,
from three committed inputs, and publishes them as the ``economics-scenarios`` bundle feed:

1. the site's **abatement instrument** — the CRA extraction (percent, term, capex, jobs);
2. its **cited local parameters** — ``SiteProfile.abatement_parameters_relpath``
   (assessment ratio, effective millage, sales-and-use rate, the withheld knobs, the
   discrete what-if profiles), each carrying its citation and register;
3. the network-global **industry priors** — ``reference/datacenter-industry/priors.yaml``,
   read through :mod:`watermark.economics.priors`.

plus the facility power basis (:mod:`watermark.facility.power`) for the load-per-job ratio.

**The discipline is the point.** This is the one cluster in tension with the anti-modeling
method of ``docs/defense-nexus.md``, so the guarantees are structural rather than editorial —
:class:`~watermark.economics.model.ScenarioBand` refuses a collapsed band, and every axis,
line and withheld input refuses the ``verified`` tag and any confidence above ``low``. A
scenario here *cannot* be serialized as an assertion. It mirrors the stylized-band discipline
of ``derive_demand_pressure`` (:mod:`watermark.economics.energy`), one rung stricter.

Instrument-gated: :func:`derive_economic_scenarios` returns ``None`` for a site with no
abatement agreement on the record, so no peer is ever priced off another county's mills —
the Python peer of ``econLedger.ts``'s ``ledgerProfiles(site) -> null``.
"""

from __future__ import annotations

import math
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.economics.model import (
    EconomicScenarios,
    ScenarioAxis,
    ScenarioBand,
    ScenarioConstant,
    ScenarioLine,
    ScenarioProfile,
    ScenarioSource,
    WithheldInput,
)
from watermark.economics.priors import IndustryPriors, load_industry_priors
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.provenance import SourceKind, as_confidence
from watermark.sites import active_profile

log = get_logger(__name__)

_CRA_REL = ("legal", "prr-mandamus", "cra-agreement.cra.yaml")

METHOD = (
    "15-yr forgone real-property tax = capex x building_share x assessment_ratio x "
    "effective_commercial_mills x abatement_percent x term_years; forgone sales tax (the "
    "DCTE, if taken) = (1 - building_share) x capex x sales_and_use_rate x equipment_refresh; "
    "net subsidy = the two, before the withheld school-compensation offset. Each is priced at "
    "every scenario corner and published as the envelope of those corners."
)


def _band_shape(dist: str | None) -> Literal["triangular", "uniform", "profiles"]:
    """Narrow a free-text ``dist`` from a committed YAML to the band's shape vocabulary.

    ``bimodal`` and ``point`` appear in the industry priors for entries this cluster does not
    publish as axes; anything unrecognized falls back to ``triangular`` (a central with a
    spread), which is what every banded entry in both files actually is. The fallback is
    deliberate: an unknown shape must not silently become ``profiles``, which would claim the
    band is the envelope of discrete corners when it is a distribution.
    """
    if dist == "uniform":
        return "uniform"
    if dist == "profiles":
        return "profiles"
    return "triangular"


# --- the committed parameters file --------------------------------------------
class ParameterEntry(BaseModel):
    """One cited parameter from ``abatement-parameters.yaml`` (the tier0-parameters shape)."""

    model_config = ConfigDict(extra="forbid")

    value: float
    low: float | None = None
    high: float | None = None
    dist: str | None = None
    source: SourceKind = "assumption"
    citation: str = ""
    confidence: str = "low"
    note: str = ""
    resolving_record: str = ""

    def provenanced(self, unit: str) -> ProvenancedValue:
        """As a :class:`ProvenancedValue`, carrying the band and the citation together."""
        citation = (
            f"{self.citation.strip()} {self.note.strip()}".strip()
            if self.note
            else (self.citation.strip())
        )
        return ProvenancedValue(
            value=self.value,
            unit=unit,
            source=self.source,
            citation=citation or None,
            confidence=as_confidence(self.confidence),
            low=self.low,
            high=self.high,
        )

    def band(self, unit: str) -> ScenarioBand | None:
        """As a :class:`ScenarioBand`, or ``None`` when the entry states no range."""
        if self.low is None or self.high is None or self.high <= self.low:
            return None
        return ScenarioBand(
            low=self.low,
            central=self.value,
            high=self.high,
            unit=unit,
            dist=_band_shape(self.dist),
        )


class ScenarioKnobs(BaseModel):
    """One what-if corner as declared in the parameters file (before it is priced)."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    building_share: float
    jobs: int
    note: str = ""
    basis: str = ""


class AbatementParameters(BaseModel):
    """The committed, cited local tax mechanics + what-if knobs for one site's instrument."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any] = {}
    tax: dict[str, ParameterEntry] = {}
    knobs: dict[str, ParameterEntry] = {}
    scenarios: list[ScenarioKnobs] = []

    def tax_param(self, key: str) -> ParameterEntry:
        entry = self.tax.get(key)
        if entry is None:
            raise ValueError(f"abatement parameters are missing the tax entry {key!r}")
        return entry

    def knob(self, key: str) -> ParameterEntry:
        entry = self.knobs.get(key)
        if entry is None:
            raise ValueError(f"abatement parameters are missing the knob {key!r}")
        return entry


def load_abatement_parameters(settings: Settings | None = None) -> AbatementParameters | None:
    """Read the active site's committed abatement parameters, or ``None``.

    Instrument-gated on ``SiteProfile.abatement_parameters_relpath``: a site with no abatement
    agreement on the record declares no path, so there is nothing to read and nothing to
    price. ``None`` is also returned when a declared file is missing (a data_dir without the
    reference tree) — the caller degrades rather than crashing the export.
    """
    settings = settings or get_settings()
    relpath = active_profile(settings).abatement_parameters_relpath
    if relpath is None:
        return None
    path = settings.data_dir / relpath
    if not path.is_file():
        log.info("econ.scenarios.parameters_absent", path=str(path))
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return AbatementParameters.model_validate(data)


# --- the instrument -----------------------------------------------------------
class AbatementInstrument(BaseModel):
    """The abatement terms read straight off the committed CRA extraction.

    Deliberately a *read*, never a re-key: the percent, term, capex and job estimate all come
    from ``cra-agreement.cra.yaml``, so a correction to the extraction moves the scenario
    bands with it. ``ApproxInt``-style ``~`` markers in the source YAML are tolerated.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str
    record: str
    abatement_pct: float  # 0..1
    term_years: int
    capex_usd: float
    stated_jobs: int
    real_property_only: bool
    school_terms_public: bool
    tax_base: str = ""


def _approx_number(raw: object) -> float:
    """Coerce a possibly ``~``-marked transcription (``~500000000``) to a float."""
    if isinstance(raw, int | float):
        return float(raw)
    text = str(raw).strip().lstrip("~").replace(",", "")
    return float(text)


def load_abatement_instrument(settings: Settings | None = None) -> AbatementInstrument | None:
    """Read the committed CRA extraction for the active site, or ``None`` when absent.

    Gated the same way as :func:`load_abatement_parameters` — ``data/extracted`` is one tree
    for the whole network, so the profile's declared parameters path (not the file's mere
    existence) is what says this instrument belongs to this site.
    """
    settings = settings or get_settings()
    if active_profile(settings).abatement_parameters_relpath is None:
        return None
    path = settings.extracted_dir.joinpath(*_CRA_REL)
    if not path.is_file():
        log.info("econ.scenarios.instrument_absent", path=str(path))
        return None
    cra = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    abatement = cra.get("abatement") or {}
    estimates = cra.get("company_estimates") or {}
    school = cra.get("school_compensation") or {}
    approval = (cra.get("authorization") or {}).get("approval_resolution") or {}
    resolution = approval.get("number")
    subject = str(cra.get("subject") or "abatement agreement")
    return AbatementInstrument(
        subject=f"{subject} (Res #{resolution})" if resolution else subject,
        record="/".join(("data", "extracted", *_CRA_REL)),
        abatement_pct=float(abatement.get("percent", 0)) / 100.0,
        term_years=int(abatement.get("term_years", 0)),
        capex_usd=_approx_number(estimates.get("capital_investment_usd", 0)),
        stated_jobs=int(_approx_number(estimates.get("jobs", 0))),
        real_property_only=bool(abatement.get("real_property_only", False)),
        school_terms_public=bool(school.get("amounts_public", False)),
        tax_base=str(school.get("school_district") or ""),
    )


# --- the arithmetic (pure) ----------------------------------------------------
def abatement_usd(
    *, capex: float, building_share: float, effective_rate: float, pct: float, years: int
) -> float:
    """15-year forgone real-property tax at one building share."""
    return capex * building_share * effective_rate * pct * years


def kept_usd(
    *, capex: float, building_share: float, effective_rate: float, pct: float, years: int
) -> float:
    """The un-abated share the public still collects over the term."""
    return capex * building_share * effective_rate * (1.0 - pct) * years


def exemption_usd(
    *, capex: float, building_share: float, sales_rate: float, refresh: float
) -> float:
    """Forgone sales tax on the equipment (the inverse of the building share), refreshed."""
    return (1.0 - building_share) * capex * sales_rate * refresh


def _round_half_up(value: float) -> int:
    """Round to the nearest integer, halves UP — matching JavaScript's ``Math.round``.

    Python's built-in ``round`` is half-to-even, so a figure landing exactly on ``.5`` (the
    un-abated 25% line does) would publish one dollar below what the frontend's live recompute
    produces for the same corner. The two tiers price the same instrument and must agree
    exactly, so the published figures use JS's convention rather than asking the test that pins
    them to tolerate an off-by-one. Amounts here are positive, so ``floor(x + 0.5)`` is it.
    """
    return math.floor(value + 0.5)


def _envelope(values: list[float], central: float, unit: str) -> ScenarioBand:
    """The band across the scenario corners, with a named corner as the central."""
    return ScenarioBand(
        low=min(values), central=central, high=max(values), unit=unit, dist="profiles"
    )


# --- the axes (the cited industry drivers) ------------------------------------
def _sources(prior_sources: list[Any]) -> list[ScenarioSource]:
    return [
        ScenarioSource(name=s.name, year=s.year, url=s.url, contributes=s.contributes)
        for s in prior_sources
    ]


#: The industry priors this cluster publishes as axes, with the ``[open]`` question each
#: bears on. The question text is the discipline: an axis exists to *sharpen a question*, not
#: to answer it, and the feed says so in the row rather than in a page-level caveat.
_AXIS_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "govcloud_premium",
        "Does the authorized-region premium explain why this load is sited here?",
        "The recurring price premium government/sovereign cloud commands over commercial "
        "(isolation, U.S.-persons staffing, compliance) is what would reward building "
        "dedicated hardened capacity in a low-cost jurisdiction. That the premium exists is "
        "documented; that it applies to this campus is not — the facility's authorization "
        "posture is undisclosed (docs/defense-nexus.md).",
    ),
    (
        "ai_rack_refresh",
        "Does AI-class hardware break the equipment forecast the DCTE was scored against?",
        "Ohio's data-center sales-tax exemption is scored against a single equipment-purchase "
        "forecast. AI-class hardware refreshes on a 3-5 year cycle at ~30-40% of hardware cost "
        "annually, and rack density is rising, so the exempted base recurs across the "
        "abatement window rather than being spent once. Whether this campus takes the "
        "exemption, and on how much hardware, is not in the record.",
    ),
    (
        "building_real_property_share",
        "How much of the build is abated real property rather than exempt equipment?",
        "The CRA abates real property only; the DCTE covers equipment and construction "
        "materials. The split is jurisdiction-specific and genuinely fuzzy, and it is the "
        "single knob that moves the most money between the two subsidies.",
    ),
    (
        "jobs_per_mw",
        "How many permanent jobs does a load this size actually carry?",
        "Automated hyperscale campuses run roughly 20-40 operators per 100 MW. Applied to a "
        "load of this scale the range independently brackets the agreement's own non-binding "
        "estimate, which is why the job count is turned across a band rather than taken at "
        "its stated value.",
    ),
    (
        "subsidy_per_job_benchmark",
        "Is the modeled subsidy per job typical of a data-center deal, or an outlier?",
        "A comparative benchmark the modeled per-job figures are read against — a "
        "corroboration of the output, never an input to it.",
    ),
    (
        "salestax_exemption_dominance",
        "Which subsidy is actually the larger one?",
        "Every jurisdiction that has measured it reports the sales-tax exemption, not the "
        "property abatement, as the dominant cost. A qualitative corroboration from other "
        "states — it asserts no magnitude here, which is why it carries no band.",
    ),
)


def _build_axes(priors: IndustryPriors) -> list[ScenarioAxis]:
    axes: list[ScenarioAxis] = []
    for key, question, basis in _AXIS_SPECS:
        prior = priors.get(key)
        if prior is None:
            continue
        band: ScenarioBand | None = None
        if prior.has_band and prior.low is not None and prior.high is not None:
            central = prior.central if prior.central is not None else (prior.low + prior.high) / 2
            band = ScenarioBand(
                low=prior.low,
                central=central,
                high=prior.high,
                unit=prior.unit or "fraction",
                dist=_band_shape(prior.dist),
            )
        axes.append(
            ScenarioAxis(
                key=prior.key,
                label=prior.label,
                question=question,
                band=band,
                # `reference` — a published outside range. Never `verified`: the band is real
                # and cited, but it is a fact about the industry, not about this facility.
                tag="reference",
                confidence="low",
                site_status=prior.lima_status,
                drives=list(prior.drives),
                basis=f"{basis} {prior.note.strip()}".strip(),
                sources=_sources(prior.sources),
                resolving_record=None,
            )
        )
    return axes


# --- the assembly -------------------------------------------------------------
def derive_economic_scenarios(
    settings: Settings | None = None,
) -> EconomicScenarios | None:
    """Assemble the site's economic argument as scenario bands, or ``None``.

    ``None`` for a site with no abatement instrument on the record (no
    ``abatement_parameters_relpath``, or the parameters/CRA file absent) — the feed is then
    simply omitted and the report locks and asks for that site's agreement, exactly as the
    frontend already did for a peer.
    """
    settings = settings or get_settings()
    params = load_abatement_parameters(settings)
    instrument = load_abatement_instrument(settings)
    if params is None or instrument is None:
        return None

    profile = active_profile(settings)
    assess = params.tax_param("assessment_ratio")
    mills = params.tax_param("effective_commercial_mills")
    sales_rate = params.tax_param("sales_and_use_rate")
    refresh = params.knob("equipment_refresh")
    school = params.knob("school_compensation")
    share_knob = params.knob("building_share")
    jobs_knob = params.knob("jobs")

    effective_rate = assess.value * mills.value  # tax as a share of market value, per year

    # --- the priced corners ---------------------------------------------------
    priced: list[ScenarioProfile] = []
    for knobs in params.scenarios:
        ab = abatement_usd(
            capex=instrument.capex_usd,
            building_share=knobs.building_share,
            effective_rate=effective_rate,
            pct=instrument.abatement_pct,
            years=instrument.term_years,
        )
        kept = kept_usd(
            capex=instrument.capex_usd,
            building_share=knobs.building_share,
            effective_rate=effective_rate,
            pct=instrument.abatement_pct,
            years=instrument.term_years,
        )
        ex = exemption_usd(
            capex=instrument.capex_usd,
            building_share=knobs.building_share,
            sales_rate=sales_rate.value,
            refresh=refresh.value,
        )
        priced.append(
            ScenarioProfile(
                key=knobs.key,
                label=knobs.label,
                note=knobs.note,
                basis=knobs.basis,
                building_share=knobs.building_share,
                jobs=knobs.jobs,
                abatement_usd=_round_half_up(ab),
                kept_usd=_round_half_up(kept),
                exemption_usd=_round_half_up(ex),
                net_subsidy_usd=_round_half_up(ab + ex),
                abatement_per_job_usd=_round_half_up(ab / knobs.jobs),
                net_subsidy_per_job_usd=_round_half_up((ab + ex) / knobs.jobs),
            )
        )
    if len(priced) < 2:
        raise ValueError(
            f"{settings.site}: the abatement parameters declare {len(priced)} scenario(s) — a "
            "band needs at least two corners, or it is a point estimate in disguise"
        )

    # The reference corner: the profile that takes the agreement at its word, else the first.
    reference = next((p for p in priced if p.key == "stated"), priced[0])

    lines = [
        ScenarioLine(
            key="abatement",
            label="Property-tax abatement (forgone)",
            band=_envelope([p.abatement_usd for p in priced], reference.abatement_usd, "usd"),
            tag="inference",
            note=(
                f"{instrument.abatement_pct:.0%} / {instrument.term_years}-yr on the "
                "real-property share of the stated capital investment"
            ),
            resolving_record=share_knob.resolving_record or None,
        ),
        ScenarioLine(
            key="exemption",
            label="Sales-tax exemption (if taken)",
            band=_envelope([p.exemption_usd for p in priced], reference.exemption_usd, "usd"),
            # `open`, not `inference`: the magnitude is computed, but whether the campus holds
            # a DCTE agreement at all is a question the record does not answer.
            tag="open",
            note="DCTE on equipment + construction materials (R.C. 122.175); application [open]",
            resolving_record=refresh.resolving_record or None,
        ),
        ScenarioLine(
            key="kept",
            label="Un-abated property tax (the public keeps)",
            band=_envelope([p.kept_usd for p in priced], reference.kept_usd, "usd"),
            tag="inference",
            note=f"the {1 - instrument.abatement_pct:.0%} the abatement does not touch",
            resolving_record=share_knob.resolving_record or None,
        ),
        ScenarioLine(
            key="net",
            label="Net public subsidy (gives)",
            band=_envelope([p.net_subsidy_usd for p in priced], reference.net_subsidy_usd, "usd"),
            tag="inference",
            note=(
                "abatement + exemption, before the withheld school-compensation offset and "
                "before water / grid burdens, which are not monetized here"
            ),
            resolving_record=school.resolving_record or None,
        ),
        ScenarioLine(
            key="net_per_job",
            label="Net public subsidy per job",
            band=_envelope(
                [p.net_subsidy_per_job_usd for p in priced],
                reference.net_subsidy_per_job_usd,
                "usd_per_job",
            ),
            tag="inference",
            note=(
                "the deciding number the withheld figures all move; read against the "
                "subsidy_per_job_benchmark axis, not on its own"
            ),
            resolving_record="the School District Compensation Agreement + an actual headcount",
        ),
    ]

    # --- load per job (the §3 "subsidizes load, not employment" figure) --------
    load_line = _load_per_job_line(settings, [p.jobs for p in priced])

    priors = load_industry_priors(settings)
    axes = _build_axes(priors) if priors is not None else []

    constants = [
        ScenarioConstant(
            key="capital_investment",
            label="Stated capital investment",
            value=ProvenancedValue.from_document(
                instrument.capex_usd,
                "usd",
                citation=(
                    f"{instrument.record} — company good-faith estimate per R.C. "
                    "3735.671(B)(8); explicitly NOT a cap"
                ),
                confidence="medium",
            ),
        ),
        ScenarioConstant(
            key="abatement_percent",
            label="Abatement percent",
            value=ProvenancedValue.from_document(
                instrument.abatement_pct, "fraction", citation=instrument.record
            ),
        ),
        ScenarioConstant(
            key="term_years",
            label="Abatement term",
            value=ProvenancedValue.from_document(
                float(instrument.term_years),
                "years",
                citation=f"{instrument.record} — per Building",
            ),
        ),
        ScenarioConstant(
            key="stated_jobs",
            label="Stated permanent jobs",
            value=ProvenancedValue.from_document(
                float(instrument.stated_jobs),
                "jobs",
                citation=(
                    f"{instrument.record} — company estimate; the agreement records that "
                    "actuals may differ significantly"
                ),
                confidence="low",
            ),
        ),
        ScenarioConstant(
            key="assessment_ratio",
            label="Assessment ratio (market -> assessed)",
            value=assess.provenanced("fraction"),
        ),
        ScenarioConstant(
            key="effective_commercial_mills",
            label="Effective commercial millage (of assessed value)",
            value=mills.provenanced("fraction"),
        ),
        ScenarioConstant(
            key="effective_rate",
            label="Effective tax rate (of market value, per year)",
            value=ProvenancedValue.derived(
                round(effective_rate, 6),
                "fraction",
                citation=(
                    f"{assess.value:g} assessment ratio x {mills.value:g} effective mills — "
                    "the product the whole ledger scales on"
                ),
                confidence="low",
                low=assess.value * (mills.low if mills.low is not None else mills.value),
                high=assess.value * (mills.high if mills.high is not None else mills.value),
            ),
        ),
        ScenarioConstant(
            key="sales_and_use_rate",
            label="Combined sales-and-use rate",
            value=sales_rate.provenanced("fraction"),
        ),
        ScenarioConstant(
            key="equipment_refresh",
            label="Equipment refresh over the term",
            value=refresh.provenanced("x"),
        ),
    ]

    withheld = [
        WithheldInput(
            key="building_share",
            label="Building (abated real-property) share of the build",
            band=share_knob.band("fraction")
            or ScenarioBand(low=0.2, central=0.3, high=0.45, unit="fraction"),
            why=share_knob.citation.strip(),
            resolving_record=share_knob.resolving_record,
        ),
        WithheldInput(
            key="jobs",
            label="Steady-state permanent jobs",
            band=jobs_knob.band("jobs") or ScenarioBand(low=30, central=50, high=50, unit="jobs"),
            why=jobs_knob.citation.strip(),
            resolving_record=jobs_knob.resolving_record,
        ),
        WithheldInput(
            key="equipment_refresh",
            label="Equipment spend + refresh across the term",
            band=refresh.band("x") or ScenarioBand(low=1.0, central=1.5, high=2.0, unit="x"),
            why=refresh.citation.strip(),
            resolving_record=refresh.resolving_record,
        ),
        WithheldInput(
            key="school_compensation",
            label="School District Compensation (offset)",
            band=school.band("usd")
            or ScenarioBand(low=0, central=15_000_000, high=30_000_000, unit="usd"),
            why=school.citation.strip(),
            resolving_record=school.resolving_record,
        ),
    ]

    caveats = [
        "Every figure here is a band across labeled scenarios, not an estimate of what will "
        "happen. The constants are all published above; turn any of them and the band moves.",
        f"The effective commercial millage is a STATED ASSUMPTION, not a cited "
        f"{profile.county_name} rate — it scales every dollar figure linearly and is the "
        "largest unforced uncertainty in the model.",
        "The abatement is on real property only, so the building/equipment split moves money "
        "between the two subsidies rather than shrinking the total.",
        "The sales-tax exemption line is conditional: whether this campus holds a DCTE "
        "agreement is not in the record.",
        "The school-compensation offset is a wide screening range because the agreement's "
        "dollar terms are non-public — the net-subsidy line is stated before it, not net of it.",
    ]
    if not instrument.school_terms_public:
        caveats.append(
            "The single figure that would most narrow this band — the School District "
            "Compensation Agreement — is withheld by the county, which is why the band is wide."
        )

    scenarios = EconomicScenarios(
        site=settings.site,
        site_name=profile.place or settings.site,
        instrument=instrument.subject,
        instrument_record=instrument.record,
        constants=constants,
        withheld=withheld,
        axes=axes,
        profiles=priced,
        lines=lines,
        load_per_job=load_line,
        method=METHOD,
        caveats=caveats,
    )
    log.info(
        "econ.scenarios.derived",
        site=settings.site,
        profiles=len(priced),
        axes=len(axes),
        net_low=lines[3].band.low,
        net_high=lines[3].band.high,
    )
    return scenarios


def _load_per_job_line(settings: Settings, job_counts: list[int]) -> ScenarioLine | None:
    """The campus's IT load per modeled job, as a band — or ``None`` with no power basis.

    The typed home of ``docs/ECONOMICS.md`` §3's "~5-6 MW per job". The numerator is the
    disclosed IT-load bracket (:func:`watermark.facility.power.derive_power_basis`), the
    denominator the scenario job counts — so the band is wider than the prose figure, which
    used the stated headcount alone. That is the honest reading: the prose number is the
    band's reference corner, not its extent.

    Returns ``None`` when the site has no derivable power basis. A ratio is never synthesized
    from a missing numerator (the same refusal ``derive_demand_pressure`` makes).
    """
    from watermark.facility.power import derive_power_basis

    try:
        power = derive_power_basis(settings=settings)
    except ValueError:
        return None
    if power is None or not power.it_load.value:
        return None
    it = power.it_load
    load_low = it.low_or_value
    load_high = it.high_or_value
    jobs_low, jobs_high = min(job_counts), max(job_counts)
    if jobs_low <= 0:
        return None
    # Widest honest span: the smallest load over the most jobs .. the largest over the fewest.
    ratios = [load_low / jobs_high, load_high / jobs_low]
    central = it.value / jobs_high  # the reference corner — the stated headcount
    band = ScenarioBand(
        low=round(min(ratios), 2),
        central=round(central, 2),
        high=round(max(ratios), 2),
        unit="MW_per_job",
        dist="profiles",
    )
    return ScenarioLine(
        key="load_per_job",
        label="Disclosed IT load per modeled job",
        band=band,
        tag="inference",
        note=(
            f"IT load {load_low:g}-{load_high:g} MW ({it.citation or 'power basis'}) over "
            f"{jobs_low}-{jobs_high} modeled jobs. The central is the reference corner — the "
            "load at the agreement's own stated headcount. This is the magnitude behind the "
            "structural reading that the public instrument is scaled to load and consumption "
            "rather than to employment; it is a ratio of two modeled quantities, not a finding "
            "about intent."
        ),
        resolving_record="an actual steady-state headcount + a disclosed IT load",
    )


def build_economic_scenarios(settings: Settings | None = None) -> EconomicScenarios | None:
    """Public entry point for the site export — :func:`derive_economic_scenarios`, guarded.

    Everything it reads is committed (the CRA extraction, the parameters file, the priors,
    the facility profile), so the static build needs no network. A site whose parameters are
    absent or degenerate yields ``None`` and the feed is skipped.
    """
    try:
        return derive_economic_scenarios(settings)
    except (ValueError, FileNotFoundError) as exc:
        log.warning("econ.scenarios.skipped", error=str(exc))
        return None
