"""Derive the federal backdrop: energy policy levers + federal output/statistics (#98).

The TOP of the grid & regulatory stack (epic #93). Two halves, both read against the
campus load (the first-class ``facility_draw`` from :mod:`bosc.facility.power`, issue
#87) so the facility's demand is situated against the federal backdrop:

1. **Policy levers.** The federal clean-energy POLICY LEVERS that bear on a load /
   generation of this profile - the IRA section 45 PTC / section 48 ITC and their
   tech-neutral successors (section 45Y / 48E), section 45V clean hydrogen, section
   45X advanced manufacturing, the DOE Loan Programs Office, and DOE grid-resilience
   (section 40101) - each mapped to *what it applies to* and its *direction on cost*
   (a direction, never a quantified offset).

2. **Federal output / statistics.** US national energy OUTPUT and price series (EIA):
   total electricity net generation, the data-center share of US load (now and the
   2028 projection), and the average retail price trend. This is the macro pressure
   the consumer-cost thread (issue #91) needs as its national backdrop.

The integration is the **campus-vs-national** view: the campus annual consumption
expressed as a share of US data-center load and of US total net generation. That is
what feeds #91 - the campus sized against the national data-center demand wave.

Data discipline (epic #93). Nothing here is a facility disclosure. The federal figures
are TRANSCRIBED published values (EIA national, the LBNL/DOE data-center report, the IRA
statute / IRS guidance), each ``reference``-tagged at ``confidence="medium"`` with a
source citation and flagged for verification / regeneration via EIA. Policy levers
carry their statute and cost direction as :class:`bosc.grid.model.CitedFact`. The
campus-vs-national shares are ``derived`` from ``facility_draw``. Applicability is
direction-of-cost only - it depends on the campus's undisclosed generation / procurement
choices, so it is a backdrop, not a claim about this facility.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from bosc.config import Settings, get_settings
from bosc.economics.connectors.eia import fetch_eia_series
from bosc.facility.power import derive_power_basis
from bosc.grid.model import CitedFact
from bosc.hydrology.model import ProvenancedValue
from bosc.logging import get_logger

log = get_logger(__name__)

_HOURS_PER_YEAR = 8760.0
_LOAD_FACTOR = 0.9  # data centers run near-flat (shared convention with #91/#94/#95)
_LOAD_FACTOR_CITE = "data-center capacity utilization ~0.9 (near-flat 24x7); assumption (cf. #91)"

# --- Federal output / statistics ----------------------------------------------
# US total net generation + US avg retail price are LIVE EIA seriesid pulls (#98/#120):
#   ELEC.GEN.ALL-US-99.A (net generation, thousand MWh) and ELEC.PRICE.US-ALL.A
#   (avg retail price, cents/kWh). The data-center share below stays a report-cited
#   reference (LBNL/DOE), not on the EIA API.
_US_NET_GEN_SERIES = "ELEC.GEN.ALL-US-99.A"
_US_RETAIL_PRICE_SERIES = "ELEC.PRICE.US-ALL.A"
# US data-center electricity use ~176 TWh in 2023 (~4.4% of US total), projected to
# ~6.7-12% of US load by 2028 (LBNL/DOE 2024 data-center report).
_DC_USE_2023_TWH = 176.0
_DC_SHARE_2023_PCT = 4.4
_DC_SHARE_2028_PROJ_PCT = 9.5  # midpoint of the ~6.7-12% projected 2028 range
_DC_CITE = (
    "LBNL/DOE 2024 United States Data Center Energy Usage Report: US data-center "
    "electricity use ~176 TWh in 2023 (~4.4% of US total), projected to ~6.7-12% of "
    "US load by 2028; transcribed published figure - verify"
)

# --- Statute citations for the policy levers (IRA / DOE) -----------------------
_IRA = "Inflation Reduction Act of 2022 (Pub. L. 117-169) / IRS guidance"
_DOE_LPO = "DOE Loan Programs Office (Title 17 / 1703 / 1706)"
_DOE_GRID = "DOE Grid Resilience (IIJA section 40101)"


class PolicyLever(BaseModel):
    """One federal energy policy lever, provenance-tagged.

    ``name`` / ``statute`` / ``applies_to`` / ``cost_direction`` are each a
    :class:`bosc.grid.model.CitedFact` so the lever is *cited*, never asserted. The
    ``applies_to`` is the load / generation profile the lever bears on; the
    ``cost_direction`` is the DIRECTION on the campus's cost ("lowers clean-gen cost"
    / "tangential" / "n/a"), never a quantified offset.
    """

    model_config = ConfigDict(extra="forbid")

    name: CitedFact  # "section 45 production tax credit (PTC)"
    statute: CitedFact  # the IRA / DOE authority
    applies_to: CitedFact  # the load / generation profile it bears on
    cost_direction: CitedFact  # direction on cost: "lowers clean-gen cost" / "tangential" / "n/a"


class FederalEnergyOutput(BaseModel):
    """US national energy output / statistics (EIA + LBNL/DOE), transcribed.

    The federal output/price backdrop the consumer-cost thread (#91) reads against:
    total net generation, the data-center share of US load (now and the 2028
    projection), and the average retail price trend. Each a transcribed published
    figure (``reference``), flagged for verification - not a facility disclosure.
    """

    model_config = ConfigDict(extra="forbid")

    us_net_generation_twh: ProvenancedValue  # reference (EIA Electric Power Annual)
    datacenter_use_2023_twh: ProvenancedValue  # reference (LBNL/DOE)
    datacenter_share_pct_2023: ProvenancedValue  # reference (LBNL/DOE)
    datacenter_share_pct_2028_proj: ProvenancedValue  # reference (LBNL/DOE projection)
    us_avg_retail_price_cents_kwh: ProvenancedValue  # reference (EIA)
    source: str = (
        "EIA national output/price + LBNL/DOE 2024 data-center report (transcribed; verify)"
    )


class FederalBackdrop(BaseModel):
    """The assembled federal backdrop (#98): policy levers + output + campus integration.

    Tops the grid stack. ``policy_levers`` are the federal clean-energy levers bearing
    on a load/generation of this profile; ``output`` is the US national energy
    output/price backdrop; and the integration sizes the campus annual consumption as a
    DERIVED share of US data-center load and of US total net generation - the
    "campus vs national backdrop" that feeds #91. Nothing here is a facility disclosure.
    """

    model_config = ConfigDict(extra="forbid")

    policy_levers: list[PolicyLever]
    output: FederalEnergyOutput
    campus_load_mw: ProvenancedValue  # total facility draw, central (#87)
    load_factor: ProvenancedValue  # assumption: capacity utilization
    annual_consumption_gwh: ProvenancedValue  # derived: draw x 8760 x load factor
    share_of_us_datacenter_pct: ProvenancedValue  # derived: campus / US data-center load
    share_of_us_generation_pct: ProvenancedValue  # derived: campus / US total net generation
    note: str = ""
    caveats: list[str] = []


def _policy_levers() -> list[PolicyLever]:
    """The federal clean-energy levers bearing on a load/generation of this profile."""

    def _lever(name: str, statute: str, applies_to: str, cost_direction: str) -> PolicyLever:
        return PolicyLever(
            name=CitedFact(value=name, source="reference", citation=statute, confidence="medium"),
            statute=CitedFact(
                value=statute, source="reference", citation=statute, confidence="medium"
            ),
            applies_to=CitedFact(
                value=applies_to, source="reference", citation=statute, confidence="medium"
            ),
            cost_direction=CitedFact(
                value=cost_direction, source="reference", citation=statute, confidence="medium"
            ),
        )

    return [
        _lever(
            "section 45 production tax credit (PTC)",
            _IRA,
            "clean electricity generation (wind/solar/etc.) the campus could procure or "
            "PPA - a per-kWh credit to the generator",
            "lowers clean-gen cost",
        ),
        _lever(
            "section 48 investment tax credit (ITC)",
            _IRA,
            "clean generation / storage capital the campus could procure or co-site - an "
            "investment credit",
            "lowers clean-gen cost",
        ),
        _lever(
            "section 45Y / 48E tech-neutral credits (PTC/ITC successors)",
            _IRA,
            "zero-emission electricity placed in service post-2024 - the tech-neutral "
            "successors to section 45 / 48",
            "lowers clean-gen cost",
        ),
        _lever(
            "section 45V clean hydrogen production credit",
            _IRA,
            "clean-hydrogen production - tangential to a compute campus unless it co-sites "
            "hydrogen-fueled generation",
            "tangential",
        ),
        _lever(
            "section 45X advanced manufacturing production credit",
            _IRA,
            "advanced-manufacturing output (chips / equipment) - tangential to the campus's "
            "own energy cost, bears on its supply chain",
            "tangential",
        ),
        _lever(
            "DOE Loan Programs Office (LPO)",
            _DOE_LPO,
            "federal loan guarantees for clean-energy / grid projects the campus's power "
            "supply could draw on",
            "lowers clean-gen cost",
        ),
        _lever(
            "DOE grid resilience (section 40101)",
            _DOE_GRID,
            "grid-resilience / transmission formula grants to states & utilities serving "
            "the load - improves deliverability, not a direct campus credit",
            "tangential",
        ),
    ]


def _federal_output(settings: Settings) -> FederalEnergyOutput:
    """US output: net generation + avg retail price LIVE from EIA (#98); data-center
    share stays a report-cited reference (LBNL/DOE, not on the EIA API)."""
    gen = fetch_eia_series(_US_NET_GEN_SERIES, settings=settings)
    net_gen_twh = gen.value.value / 1000.0  # thousand MWh -> TWh (1000 thousand-MWh = 1 TWh)
    price = fetch_eia_series(_US_RETAIL_PRICE_SERIES, settings=settings)
    return FederalEnergyOutput(
        us_net_generation_twh=ProvenancedValue.from_connector(
            round(net_gen_twh, 1),
            "TWh/yr",
            citation=f"EIA {gen.series_id} ({gen.period}): {gen.value.value:,.0f} thousand MWh "
            f"= {net_gen_twh:,.0f} TWh (US total net generation, all sectors)",
        ),
        datacenter_use_2023_twh=ProvenancedValue.from_reference(
            _DC_USE_2023_TWH, "TWh/yr", citation=_DC_CITE, confidence="medium"
        ),
        datacenter_share_pct_2023=ProvenancedValue.from_reference(
            _DC_SHARE_2023_PCT, "percent", citation=_DC_CITE, confidence="medium"
        ),
        datacenter_share_pct_2028_proj=ProvenancedValue.from_reference(
            _DC_SHARE_2028_PROJ_PCT, "percent", citation=_DC_CITE, confidence="medium"
        ),
        us_avg_retail_price_cents_kwh=ProvenancedValue.from_connector(
            price.value.value,
            "cents/kWh",
            citation=f"EIA {price.series_id} ({price.period}): "
            "US average retail electricity price, all sectors",
        ),
        source=(
            "EIA national net generation + avg retail price (connector, live) + "
            "LBNL/DOE 2024 data-center report (reference)"
        ),
    )


def derive_federal_backdrop(*, settings: Settings | None = None) -> FederalBackdrop:
    """Assemble the federal backdrop and size the campus against the national figures.

    The policy levers and US output figures are transcribed reference values; the
    campus-vs-national shares are derived from the first-class ``facility_draw``
    (:func:`bosc.facility.power.derive_power_basis`, issue #87). This is the federal
    backdrop the consumer-cost thread (#91) reads against - not a facility disclosure.
    """
    settings = settings or get_settings()
    power = derive_power_basis(settings=settings)
    output = _federal_output(settings)

    draw_mw = power.facility_draw.value
    consumption_gwh = draw_mw * _HOURS_PER_YEAR * _LOAD_FACTOR / 1000.0  # MWh -> GWh

    # US national denominators in GWh (1 TWh = 1000 GWh).
    us_datacenter_gwh = output.datacenter_use_2023_twh.value * 1000.0
    us_generation_gwh = output.us_net_generation_twh.value * 1000.0

    def _share(denom: float) -> float:
        return consumption_gwh / denom * 100.0 if denom else 0.0

    backdrop = FederalBackdrop(
        policy_levers=_policy_levers(),
        output=output,
        campus_load_mw=ProvenancedValue.derived(
            round(draw_mw, 1),
            "MW",
            citation=f"PowerBasis.facility_draw central (#87): {power.facility_draw.citation or ''}",
        ),
        load_factor=ProvenancedValue.assume(_LOAD_FACTOR, "fraction", why=_LOAD_FACTOR_CITE),
        annual_consumption_gwh=ProvenancedValue.derived(
            round(consumption_gwh, 1),
            "GWh/yr",
            citation=f"{draw_mw:g} MW x {_HOURS_PER_YEAR:g} h x {_LOAD_FACTOR:g} load factor",
        ),
        share_of_us_datacenter_pct=ProvenancedValue.derived(
            round(_share(us_datacenter_gwh), 3),
            "percent",
            citation=f"campus {consumption_gwh:.0f} GWh / US data centers "
            f"{us_datacenter_gwh:,.0f} GWh ({_DC_USE_2023_TWH:g} TWh x 1000; LBNL/DOE 2023)",
            confidence="medium",
        ),
        share_of_us_generation_pct=ProvenancedValue.derived(
            round(_share(us_generation_gwh), 4),
            "percent",
            citation=f"campus {consumption_gwh:.0f} GWh / US net generation "
            f"{us_generation_gwh:,.0f} GWh ({output.us_net_generation_twh.value:g} TWh x 1000; EIA)",
            confidence="medium",
        ),
        note=(
            "Federal backdrop (#98), the top of the grid stack. The policy levers map "
            "the IRA section 45/48 (and tech-neutral 45Y/48E) clean-generation credits, "
            "section 45V/45X, and DOE LPO / grid-resilience programs to what they apply "
            "to and their direction on cost; the output figures are transcribed EIA "
            "national + LBNL/DOE data-center statistics. The campus-vs-national shares "
            "size the campus against the US data-center demand wave - the backdrop the "
            "consumer-cost thread (#91) reads against. Nothing here is a facility "
            "disclosure."
        ),
        caveats=[
            "Policy applicability depends on the campus's (undisclosed) generation / "
            "procurement choices - whether it self-generates, co-sites, or PPAs clean "
            "power. The levers are mapped to a load/generation of this profile, not "
            "asserted as claimed by this facility.",
            "Cost direction is direction-of-cost only, NOT a quantified offset: a credit "
            "lowers the cost of clean generation the campus could buy, but the dollar "
            "value depends on undisclosed contracting.",
            "National projections (the ~6.7-12% data-center share by 2028) are "
            "scenario-dependent. The US output / price figures are transcribed published "
            "values flagged for verification, regenerable via EIA.",
        ],
    )

    log.info(
        "grid.federal",
        levers=len(backdrop.policy_levers),
        consumption_gwh=round(consumption_gwh, 1),
        share_us_datacenter_pct=backdrop.share_of_us_datacenter_pct.value,
    )
    return backdrop


def _reference_path(reference_dir: Path) -> Path:
    return reference_dir / "federal" / "federal-energy.yaml"


def write_federal_backdrop(backdrop: FederalBackdrop, *, settings: Settings | None = None) -> str:
    """Persist the federal backdrop as committed reference YAML; return the path."""
    settings = settings or get_settings()
    path = _reference_path(settings.reference_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(backdrop.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("grid.federal.wrote", path=str(path))
    return str(path)


def load_federal_backdrop(reference_dir: Path) -> FederalBackdrop | None:
    """Read the committed federal-energy YAML, or ``None`` if absent."""
    path = _reference_path(reference_dir)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return FederalBackdrop.model_validate(data)
