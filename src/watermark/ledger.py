"""Public-subsidy vs. public-benefit ledger for the data-center CRA abatement.

Assembles, in one place, what the public *gives* (the 15-year / 75% real-property tax
abatement in the committed CRA extraction) against what it *gets* (the developer's own
~50-jobs / ~$4M-payroll estimate) and what it *bears* (the resource/environmental
burdens already quantified by the other threads — toxics dilution, the cooling draw,
the drainage-scope gap, the federal entanglement, the genset air permit, the $14.5M
roadwork channel with perpetual County maintenance, the TMDL wastewater-upgrade load,
and the CAUV farmland conversion).

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

from collections.abc import Callable
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

_CRA_REL = ("legal", "prr-mandamus", "cra-agreement.cra.yaml")


def _buildout_consumptive_cfs(settings: Settings) -> float | None:
    """The buildout scenario's net consumptive cooling draw (cfs), from the committed artifact.

    Reads ``consumptive_loss.value`` off ``data/scenarios/buildout.scenario.yaml`` rather than
    carrying a per-site literal — a non-Lima site supplies its own reviewed scenario.
    """
    path = settings.scenarios_dir / "buildout.scenario.yaml"
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return float(data["consumptive_loss"]["value"])
    except (KeyError, TypeError, ValueError):
        return None


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


def _burden_toxics(settings: Settings) -> BurdenItem | None:
    from watermark.hydrology import toxics

    tx = toxics.build_screen(settings)
    return BurdenItem(
        thread="toxics x dilution",
        headline=(
            f"{tx.meta['critical_count']} of {tx.meta['water_releaser_count']} county toxic "
            "water dischargers exceed an Ohio aquatic-life criterion on the Ottawa at Lima "
            "(1Q10 0 cfs — no acute assimilative capacity)"
        ),
        source="data/reference/rsei/toxic-discharge-screen.yaml",
    )


def _burden_cooling(settings: Settings) -> BurdenItem | None:
    from watermark.hydrology import scenario

    draw_cfs = _buildout_consumptive_cfs(settings)
    sw = (
        scenario.evaluate_seasonal(
            draw_cfs,
            receiving_water=active_profile(settings).receiving_water_name,
            settings=settings,
        )
        if draw_cfs is not None
        else None
    )
    if sw is None or sw.summer_multiple is None:
        return None
    return BurdenItem(
        thread="cooling withdrawal",
        headline=(
            f"~{sw.consumptive_cfs:g} cfs consumptive cooling draw — {sw.summer_multiple:g}x "
            f"the Ottawa summer 30Q10, {sw.annual_multiple:g}x the annual 7Q10"
        ),
        source="data/scenarios/buildout.scenario.yaml + low-flow-7q10.yaml",
    )


def _burden_drainage(settings: Settings) -> BurdenItem | None:
    from watermark.hydrology import drainage

    da = drainage.build_drainage_audit(settings)
    return BurdenItem(
        thread="drainage scope",
        headline=(
            f"${da.meta['program_drainage_total']:,} of roundabout drainage budgeted with "
            f"only {da.meta['itemized_count']}/{da.meta['sub_estimate_count']} estimates "
            "itemized and no detention sized"
        ),
        source="data/extracted/aedg/roundabouts.*.opc.yaml + atlas14-corridor-ddf.yaml",
    )


def _burden_federal(settings: Settings) -> BurdenItem | None:
    from watermark.usaspending import load_inventory as load_awards

    inv = load_awards(settings.reference_dir, settings.site)
    if inv is None:
        return None
    gdls = {r.watchlist_name: r for r in inv.records}.get("General Dynamics Land Systems Inc.")
    if gdls is None:
        return None
    return BurdenItem(
        thread="federal nexus",
        headline=(
            f"corridor's federal defense anchor (JSMC operator GDLS, "
            f"${gdls.total_obligations / 1e9:.0f}B all-time federal awards)"
        ),
        source="data/reference/usaspending/awards.yaml",
    )


def _air_cap_breach_headline(settings: Settings) -> tuple[str, str] | None:
    """The modeled cap-exceedance headline + source from the committed event-anchored scenario.

    Reads the Tier-0 air scenario runner's committed output (``<site>.air-reliability_dispatch_
    event_high.scenario.yaml``, epic #1172) rather than a static string: at the captured event's
    verified authorized-window ceiling, does forced dispatch breach the synthetic-minor NSR cap?
    Returns ``None`` when no committed air scenario exists (caller falls back to the static
    permit fact) — a peer site without the modeling degrades, it doesn't break.
    """
    path = (
        settings.scenarios_dir
        / f"{settings.site}.air-reliability_dispatch_event_high.scenario.yaml"
    )
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        fleet = int(data["fleet_size"])
        runtime = round(float(data["scenario"]["runtime_hours"]["value"]), 1)
        by_pol = {e["pollutant"]: e for e in data["emissions"]}
        nox = by_pol.get("NOx")
        if nox is None or nox.get("cap_tpy") is None:
            return None
        # Float, not _num: the cap is a federally-enforceable limit (235.62 tpy) — its decimals
        # must survive; the tonnage is rounded for the headline but the cap is quoted exactly.
        tpy = round(float(nox["tpy"]["value"]), 1)
        cap = float(nox["cap_tpy"])
        pct = nox.get("pct_of_cap")
        breached = bool(data.get("any_cap_exceeded"))
    except (KeyError, TypeError, ValueError):
        return None
    verb = (
        f"would breach the {cap:g} tpy synthetic-minor NOx NSR cap ({tpy:g} tpy, {pct:g}% of cap)"
        if breached
        else f"reaches {tpy:g} tpy NOx ({pct:g}% of the {cap:g} tpy cap)"
    )
    headline = (
        f"{fleet} diesel emergency gensets (~313 MW backup) permitted synthetic-minor to stay "
        f"under major-source NSR — but a reliability-forced dispatch at the captured event's "
        f"verified {runtime:g}-hour authorized-window ceiling {verb}"
    )
    source = (
        f"data/scenarios/{path.name} (Tier-0 air emissions inventory, epic #1172; permit "
        "P0138965 caps x AP-42/permit factors x the PJM §202(c) event window, #1177/#1182)"
    )
    return headline, source


def _burden_air(settings: Settings) -> BurdenItem | None:
    # Prefer the modeled cap-exceedance headline (the committed air scenario, epic #1172); fall
    # back to the static permit fact when the modeling hasn't been run for this site.
    modeled = _air_cap_breach_headline(settings)
    if modeled is not None:
        headline, source = modeled
        return BurdenItem(thread="air permit", headline=headline, source=source)
    if not (settings.extracted_dir / "permits" / "4132514.epa.yaml").is_file():
        return None
    return BurdenItem(
        thread="air permit",
        headline=(
            "115 diesel emergency gensets (114 data-hall + 1 HUBGEN, ~313 MW backup), "
            "permitted synthetic-minor to stay just under major-source NSR review"
        ),
        # Count + synthetic-minor caps from the final PTI; the ~313 MW per-engine ekW
        # is from the draft public notice (engine size is CBI-redacted in the final).
        source=(
            "data/extracted/permits/4132514.epa.yaml (OEPA Final Air PTI P0138965, "
            "issued 2026-05-28; ekW basis: draft notice 3987141/3987144)"
        ),
    )


def _burden_roadwork(settings: Settings) -> BurdenItem | None:
    # The PAAC/Bistrozzi Roadwork Development Agreement (the public-road channel).
    rda = settings.extracted_dir / "aedg" / "roadwork-development-agreement.rda.yaml"
    if not rda.is_file():
        return None
    data = yaml.safe_load(rda.read_text(encoding="utf-8")) or {}
    contrib = _num(data["financial_terms"]["company_contribution_usd"])
    return BurdenItem(
        thread="roadwork (PAAC)",
        headline=(
            f"${contrib:,} developer 'contribution' builds 4 roundabouts + 2 road rehabs "
            "dedicated to the County for PERPETUAL maintenance; RDA §5.5 lets State 629 / "
            "ODOD grants refund the contribution to the company (so the public may fund the "
            "'private' share)"
        ),
        source="data/extracted/aedg/roadwork-development-agreement.rda.yaml",
    )


def _burden_tmdl(settings: Settings) -> BurdenItem | None:
    # A new sanitary load against a fully-allocated, reduction-bound watershed.
    tmdl = settings.reference_dir / "hydrology" / "maumee-tmdl-budget.yaml"
    if not tmdl.is_file():
        return None
    data = yaml.safe_load(tmdl.read_text(encoding="utf-8")) or {}
    afg = data["future_growth_headroom"]["point_source_group_afg_spring_tp_metric_tons"]
    return BurdenItem(
        thread="wastewater x TMDL",
        headline=(
            f"a new data-center sanitary load enters a fully-allocated watershed (point-source "
            f"future-growth reserve only ~{afg:g} mt P/spring for the whole basin) and, as a new/"
            "expanding discharger, must add secondary+tertiary treatment to hit a 0.5 mg/L TP "
            "limit — a ratepayer cost the incentive package omits"
        ),
        source="data/reference/hydrology/maumee-tmdl-budget.yaml + maumee-tmdl-responsiveness.yaml",
    )


def _burden_sanitary(settings: Settings) -> BurdenItem | None:
    # The BOSC pump-station/forcemain + the Cridersville reroute (ratepayer).
    san = settings.extracted_dir / "commissioners" / "sanitary-economics.yaml"
    if not san.is_file():
        return None
    data = yaml.safe_load(san.read_text(encoding="utf-8")) or {}
    fig = data["figures"]
    return BurdenItem(
        thread="sanitary capital (BOSC)",
        headline=(
            f"the BOSC sanitary load (0.13 MGD @ 83 F interim) is served by a "
            f"~${_num(fig['developer_pump_station_usd']):,} developer pump station + a "
            f"~${_num(fig['bosc_capital_permit_fee_usd']):,} capital permit fee, while the County "
            f"reroutes Cridersville/Shawnee Oaks to its own plant "
            f"(${_num(fig['reroute_loan_usd']):,} 0% loan) and moves to raise capital-permit/tap "
            "fees — onto a system already strained (Elm St 45->250 homes)"
        ),
        source="data/extracted/commissioners/sanitary-economics.yaml",
    )


def _burden_land(settings: Settings) -> BurdenItem | None:
    # CAUV farmland taken out of agricultural use for the campus.
    if not (settings.extracted_dir / "aedg" / "seller-land-packets.land.yaml").is_file():
        return None
    return BurdenItem(
        thread="land conversion (CAUV)",
        headline=(
            "the assembled campus parcels (Neff/Brenneman/Miller-Pike Run/Neighbors) were CAUV "
            "farmland; conversion triggers a one-time CAUV recoupment and removes productive ag "
            "land from the Elida LSD tax base — onto which the 75% abatement is then layered"
        ),
        source="data/extracted/aedg/seller-land-packets.land.yaml",
    )


# In bundle order. Each builder pulls one thread's headline or returns None when its artifact
# is absent/unbuildable; the shared loop normalizes the formerly-inconsistent catch sets (#604).
_BURDEN_BUILDERS: tuple[Callable[[Settings], BurdenItem | None], ...] = (
    _burden_toxics,
    _burden_cooling,
    _burden_drainage,
    _burden_federal,
    _burden_air,
    _burden_roadwork,
    _burden_tmdl,
    _burden_sanitary,
    _burden_land,
)


def _burdens(settings: Settings) -> list[BurdenItem]:
    """Pull the headline burden from each committed cross-thread artifact (best-effort).

    A missing file / key / value skips that thread uniformly (one normalized catch set,
    #604) rather than the prior mix of ``(FileNotFoundError, KeyError)`` /
    ``(KeyError, ValueError)`` — never a partial crash, never a silent type-level surprise.
    """
    out: list[BurdenItem] = []
    for build in _BURDEN_BUILDERS:
        try:
            item = build(settings)
        except (FileNotFoundError, KeyError, ValueError):
            continue
        if item is not None:
            out.append(item)
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
            why_withheld=(
                "the executed agreement is non-public (only the 25% statutory floor is disclosed) — though "
                "the PAAC board minutes surface a PROPOSED $200,000->$250,000/yr PILOT to Elida, the binding "
                "terms remain out of view"
            ),
            source="cra-agreement.cra.yaml (amounts_public: false) + paac-board-minutes.minutes.yaml (proposed PILOT)",
        ),
        WithheldItem(
            what="The land-assembly purchase prices for the ~350-acre campus",
            why_withheld=(
                "the recorded deeds state only 'valuable consideration' and the DTE-100 transfer-tax forms "
                "were produced with the price/consideration fields BLANK; only the Neighbors parcel "
                "($600,000 / 5.0 ac) is disclosed — so what was paid to assemble the land is opaque"
            ),
            source="data/extracted/aedg/seller-land-packets.land.yaml",
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
        "Delaware shell c/o Vorys (Scott Ziance). The PAAC minutes confirm the end user is Google.",
        "The abatement is not the only public channel: a parallel $14.5M Roadwork Development Agreement "
        "(PAAC/Bistrozzi) builds public roads the County then maintains forever, and RDA §5.5 lets State "
        "629/ODOD grants refund the developer's 'contribution' — so public money may fund the private share "
        "while the early actual award (Eagle Bridge ~$3.52M) runs far under the $14.5M collected.",
        "The school compensation the CRA keeps non-public surfaces in the Port Authority's own minutes as a "
        "proposed $200,000->$250,000/yr PILOT to Elida — evidence the deciding figure exists and is known, "
        "even as the executed agreement is withheld.",
        "The abatement is not bespoke to the data center: the same AEDG Enterprise-Zone/CRA machinery is a "
        "standing County product (renewed annually by resolution — #42/#43-23 -> #45-24 -> #62-25) and was "
        "applied to e.g. a Nutrien 50%/10-yr abatement (Russ Decker, 2024-12-19) on the same Leis/Niemeyer/"
        "Woods rails — so the BOSC subsidy sits inside a routine abatement pipeline, not a one-off.",
        "The Board first invoked the economic-development executive-session exemption ORC 121.22(G)(8) on "
        "2025-05-27 for the BOSC CRA — expressly citing the Bistrozzi NDA — and never before in the covered "
        "record (2023-2024): the closed-meeting shield mirrors the records shield.",
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
            "Obtain the School District Compensation Agreement dollar terms (currently non-public; PAAC "
            "minutes show a proposed $200-250K/yr PILOT to Elida).",
            "Compel/obtain PRR item 4 (the County's cost-benefit analysis).",
            "Obtain the land-assembly purchase prices (DTE-100 transfer-tax forms produced with blank "
            "consideration fields; only Neighbors $600K/5ac disclosed).",
            "Track the Roadwork Development Agreement grant awards (629/ODOD) and the §5.5 refund — the "
            "actual public/private split of the $14.5M turns on grants not in the corpus.",
            "Obtain any Ohio Data Center Tax Exemption (DCTE) agreement for Bistrozzi/Google — a SECOND "
            "subsidy layer (sales/use tax on the EQUIPMENT, which the CRA's real-property abatement does "
            "not touch). ODOD testified it holds 18 such agreements (witness-submissions.digest.yaml).",
            "Source the BOSC sanitary capital: the ~$32M developer pump station + ~$3.125M capital permit "
            "fee, and the Cridersville-reroute $1M 0% loan economics (sanitary-economics.yaml) — including "
            "whether the capital-permit/tap-fee increases land on existing ratepayers.",
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
