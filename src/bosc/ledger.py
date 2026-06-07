"""Public-subsidy vs. public-benefit ledger for the data-center CRA abatement.

Assembles, in one place, what the public *gives* (the 15-year / 75% real-property tax
abatement in the committed CRA extraction) against what it *gets* (the developer's own
~50-jobs / ~$4M-payroll estimate) and what it *bears* (the resource/environmental
burdens already quantified by the other threads — toxics dilution, the cooling draw,
the drainage-scope gap, the federal entanglement, the genset air permit).

Discipline:

* The CRA terms, jobs, and payroll are read from the committed CRA extraction
  (``data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml``) — document-grounded.
* **No property-tax rate exists in the corpus** and the CRA states none, so the
  foregone tax is a **screening range** from a clearly-tagged effective-rate
  *assumption* (Ohio commercial band), never presented as a cited figure. An
  open-followup tracks sourcing the Allen County Auditor's actual American-Township /
  Elida millage to replace it.
* The net public cost is deliberately left as a *range with an unknown clawback*: the
  schools recover at least 25% of their foregone share via a **non-public** School
  District Compensation Agreement, and the County's own **cost-benefit analysis is
  withheld** (PRR item 4) — so the deciding figures are, by the County's own choices,
  outside public view. That withholding is the point, not a gap to paper over.
"""

from __future__ import annotations

from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.logging import get_logger

log = get_logger(__name__)

_CRA_REL = ("legal", "prr-mandamus", "cra-agreement.cra.yaml")

# Ohio real-property tax mechanics: assessed value = 35% of market value (R.C. 5715.01).
# Effective commercial/industrial rates (gross millage on the assessed value, net of
# H.B.920 reduction factors) typically fall in this band as a fraction of MARKET value.
# This is a STATED ASSUMPTION, not a cited Allen County rate — see the open-followup.
_EFFECTIVE_RATE_LOW = 0.015
_EFFECTIVE_RATE_HIGH = 0.023
_ASSESSMENT_RATIO = 0.35  # Ohio statutory (cited)
_SCHOOL_FLOOR_PCT = 0.25  # R.C. 3735.671(A)(2): schools floored at 25% of their foregone share


# --- Models ----------------------------------------------------------------
class ForegoneTax(BaseModel):
    """The abated property tax, as a screening range (effective rate is an assumption)."""

    model_config = ConfigDict(extra="forbid")

    capital_usd: int  # the improvement value abated (≈ the CRA capital estimate)
    abatement_pct: float
    term_years: int
    assessment_ratio: float
    effective_rate_low: float  # fraction of market value
    effective_rate_high: float
    annual_full_tax_low: int  # full property tax if NOT abated
    annual_full_tax_high: int
    annual_abated_low: int  # the 75% exempted each year
    annual_abated_high: int
    term_abated_low: int  # abated x term (full-occupancy simplification)
    term_abated_high: int
    school_floor_pct: float
    basis: str  # the assumption + caveat string


class PublicBenefit(BaseModel):
    """What the public is promised, and per-subsidy-dollar framing."""

    model_config = ConfigDict(extra="forbid")

    jobs: int
    annual_payroll_usd: int
    abatement_per_job_low: int  # term_abated / jobs
    abatement_per_job_high: int
    comparables: list[str]  # cited external comparisons (relator testimony)


class BurdenItem(BaseModel):
    """One quantified public burden carried alongside the abatement (cross-thread)."""

    model_config = ConfigDict(extra="forbid")

    thread: str
    headline: str
    source: str


class WithheldItem(BaseModel):
    """A deciding figure the public cannot see — by the County's own choices."""

    model_config = ConfigDict(extra="forbid")

    what: str
    why_withheld: str
    source: str


class PublicLedger(BaseModel):
    """The assembled public cost / benefit / burden / withheld ledger."""

    model_config = ConfigDict(extra="forbid")

    meta: dict[str, Any]
    foregone_tax: ForegoneTax
    benefit: PublicBenefit
    burdens: list[BurdenItem]
    withheld: list[WithheldItem]
    findings: list[str]


# --- Helpers ---------------------------------------------------------------
def _num(x: Any) -> int:
    """Coerce a transcribed figure (possibly the ``~12345`` marker) to int."""
    if isinstance(x, int | float):
        return int(x)
    return int(float(str(x).strip().lstrip("~").replace(",", "")))


def _load_cra(settings: Settings) -> dict[str, Any]:
    path = settings.extracted_dir.joinpath(*_CRA_REL)
    if not path.is_file():
        raise FileNotFoundError(f"CRA extraction not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _foregone(cra: dict[str, Any]) -> ForegoneTax:
    ab = cra["abatement"]
    est = cra["company_estimates"]
    capital = _num(est["capital_investment_usd"])
    pct = float(ab["percent"]) / 100.0
    term = int(ab["term_years"])

    full_low = round(capital * _EFFECTIVE_RATE_LOW)
    full_high = round(capital * _EFFECTIVE_RATE_HIGH)
    return ForegoneTax(
        capital_usd=capital,
        abatement_pct=float(ab["percent"]),
        term_years=term,
        assessment_ratio=_ASSESSMENT_RATIO,
        effective_rate_low=_EFFECTIVE_RATE_LOW,
        effective_rate_high=_EFFECTIVE_RATE_HIGH,
        annual_full_tax_low=full_low,
        annual_full_tax_high=full_high,
        annual_abated_low=round(full_low * pct),
        annual_abated_high=round(full_high * pct),
        term_abated_low=round(full_low * pct * term),
        term_abated_high=round(full_high * pct * term),
        school_floor_pct=_SCHOOL_FLOOR_PCT,
        basis=(
            f"market value ≈ the ${capital:,} CRA capital estimate; assessed = 35% of market "
            f"(R.C. 5715.01, cited); effective rate {_EFFECTIVE_RATE_LOW:.1%}-"
            f"{_EFFECTIVE_RATE_HIGH:.1%} of market is a STATED ASSUMPTION (Ohio commercial band, "
            "[inference: assumption]) — replace with the Allen County Auditor's American-Township/"
            "Elida millage. Term total assumes full occupancy across the 15-yr window (phasing "
            "spreads it over the 2040-2054 lien-date window)."
        ),
    )


def _burdens(settings: Settings) -> list[BurdenItem]:
    """Pull the headline burden from each committed cross-thread artifact (best-effort)."""
    out: list[BurdenItem] = []

    try:
        from bosc.hydrology import toxics

        tx = toxics.build_screen(settings)
        out.append(
            BurdenItem(
                thread="toxics x dilution",
                headline=(
                    f"{tx.meta['critical_count']} of {tx.meta['water_releaser_count']} county "
                    "toxic water dischargers sit on the Ottawa at Lima (7Q10 0.2 cfs, 1Q10 0)"
                ),
                source="data/reference/rsei/toxic-discharge-screen.yaml",
            )
        )
    except (FileNotFoundError, KeyError):
        pass

    try:
        from bosc.hydrology import scenario

        sw = scenario.evaluate_seasonal(4.851, settings=settings)
        if sw is not None and sw.summer_multiple is not None:
            out.append(
                BurdenItem(
                    thread="cooling withdrawal",
                    headline=(
                        f"~{sw.consumptive_cfs:g} cfs consumptive cooling draw — {sw.summer_multiple:g}x "
                        f"the Ottawa summer 30Q10, {sw.annual_multiple:g}x the annual 7Q10"
                    ),
                    source="data/scenarios/buildout.scenario.yaml + low-flow-7q10.yaml",
                )
            )
    except (FileNotFoundError, KeyError):
        pass

    try:
        from bosc.hydrology import drainage

        da = drainage.build_drainage_audit(settings)
        out.append(
            BurdenItem(
                thread="drainage scope",
                headline=(
                    f"${da.meta['program_drainage_total']:,} of roundabout drainage budgeted with "
                    f"only {da.meta['itemized_count']}/{da.meta['sub_estimate_count']} estimates "
                    "itemized and no detention sized"
                ),
                source="data/extracted/aedg/roundabouts.*.opc.yaml + atlas14-corridor-ddf.yaml",
            )
        )
    except (FileNotFoundError, KeyError):
        pass

    try:
        from bosc.usaspending import load_inventory as load_awards

        inv = load_awards(settings.reference_dir)
        if inv is not None:
            by = {r.watchlist_name: r for r in inv.records}
            gdls = by.get("General Dynamics Land Systems Inc.")
            if gdls is not None:
                out.append(
                    BurdenItem(
                        thread="federal nexus",
                        headline=(
                            f"corridor's federal defense anchor (JSMC operator GDLS, "
                            f"${gdls.total_obligations / 1e9:.0f}B all-time federal awards)"
                        ),
                        source="data/reference/usaspending/awards.yaml",
                    )
                )
    except (FileNotFoundError, KeyError):
        pass

    # Air permit — a document-cited static fact (the extraction structure is permit-specific).
    air = settings.extracted_dir / "permits" / "3987144.epa.yaml"
    if air.is_file():
        out.append(
            BurdenItem(
                thread="air permit",
                headline=(
                    "114 diesel emergency gensets (~313 MW backup), permitted synthetic-minor "
                    "to stay just under major-source NSR review"
                ),
                source="data/extracted/permits/3987144.epa.yaml (OEPA PTI P0138965)",
            )
        )
    return out


# --- Build -----------------------------------------------------------------
def build_ledger(settings: Settings | None = None) -> PublicLedger:
    """Assemble the public cost / benefit / burden / withheld ledger from committed data."""
    settings = settings or get_settings()
    cra = _load_cra(settings)
    ft = _foregone(cra)

    est = cra["company_estimates"]
    jobs = _num(est["jobs"])
    payroll = _num(est["annual_payroll_usd"])
    benefit = PublicBenefit(
        jobs=jobs,
        annual_payroll_usd=payroll,
        abatement_per_job_low=round(ft.term_abated_low / jobs) if jobs else 0,
        abatement_per_job_high=round(ft.term_abated_high / jobs) if jobs else 0,
        comparables=[
            "Ohio: 13 data-center deals through Sep 2024 (~$5.1B) -> 356 jobs, $31.6M payroll "
            "vs ~$281.9M revenue loss (~$1M/job) [relator testimony 2026-06-01, citing PwC/state data]",
            "Loudoun County VA (taxes data-center equipment as business personal property): "
            "~38% of the general fund from data centers, residential rate cut for a decade "
            "[relator testimony 2026-06-01] — the abatement-vs-BPP contrast",
        ],
    )

    withheld = [
        WithheldItem(
            what="The County's cost-benefit analysis of the project (PRR request item 4)",
            why_withheld="withheld under R.C. 149.43 / 9.66 as 'being reviewed by legal counsel' (2025-dated records)",
            source="data/extracted/legal/prr-mandamus/bosc-prr-production-2026-06-05.response-index.yaml",
        ),
        WithheldItem(
            what="The School District Compensation Agreement dollar amounts (Elida + JVSD)",
            why_withheld="referenced by the CRA but in a separate, non-public agreement; only the 25% statutory floor is disclosed",
            source="data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml (school_compensation.amounts_public: false)",
        ),
    ]

    findings = [
        f"The public grants a {ft.abatement_pct:g}% / {ft.term_years}-yr real-property abatement on a "
        f"${ft.capital_usd:,} data center for ~{jobs} permanent jobs — a screening "
        f"${ft.term_abated_low / 1e6:.0f}-{ft.term_abated_high / 1e6:.0f}M in abated property tax "
        f"[inference: assumption], i.e. ~${benefit.abatement_per_job_low / 1e6:.1f}-"
        f"{benefit.abatement_per_job_high / 1e6:.1f}M of abatement per promised job.",
        "Both deciding figures are outside public view by the County's own choices: the cost-benefit "
        "analysis is withheld (PRR item 4) and the school compensation amounts are non-public — and the "
        "CRA §22 indemnifies the County's attorney fees for defending exactly such withholding.",
        "The developer's §13(A) assurance is that its parent is a publicly-traded Fortune 100 company — "
        "a major beneficiary the abatement subsidizes, while the named developer (Bistrozzi LLC) is a "
        "Delaware shell c/o Vorys (Scott Ziance).",
    ]

    meta = {
        "subject": "Public subsidy vs. public benefit — Allen County CRA No. 1 / Bistrozzi data center",
        "cra_source": "data/extracted/legal/prr-mandamus/cra-agreement.cra.yaml",
        "caveats": [
            "Foregone tax is a screening RANGE from a stated effective-rate assumption (Ohio "
            "commercial band) — not a cited Allen County rate. See open_followup.",
            "Net public cost is unquantifiable from public records: schools recover >=25% of their "
            "share via a non-public compensation agreement, and the cost-benefit analysis is withheld.",
        ],
        "open_followups": [
            "Source the Allen County Auditor's actual American-Township / Elida-district effective "
            "millage to replace the assumed rate band.",
            "Obtain the School District Compensation Agreement dollar terms (currently non-public).",
            "Compel/obtain PRR item 4 (the County's cost-benefit analysis).",
        ],
    }
    return PublicLedger(
        meta=meta,
        foregone_tax=ft,
        benefit=benefit,
        burdens=_burdens(settings),
        withheld=withheld,
        findings=findings,
    )
