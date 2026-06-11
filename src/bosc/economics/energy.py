"""Link the data-center's power draw to consumer energy-price pressure (issue #91).

The 2026-06-10 call: "bring in fuel costs at the consumer level due to macro pressures
and data-center demand." This assembles the committed EIA consumer energy-cost
reference (``build_consumer_energy`` / ``write_consumer_energy`` / ``load_consumer_energy``)
and derives a **sensitivity** relating the facility's first-class total ``facility_draw``
(:mod:`bosc.facility.power`, issue #87) to that consumer price.

The honest framing: the campus's annual electricity demand, expressed as a share of
EIA state retail sales and as a households-equivalent, is the robust, fully-cited
headline. The price-pressure band is a deliberately STYLIZED screening illustration
from a stated demand-to-price transmission coefficient — retail price formation is far
more complex than one coefficient, so it is reported as a sensitivity, never a forecast.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from bosc.config import Settings, get_settings
from bosc.economics.connectors.eia import fetch_consumer_energy
from bosc.economics.model import ConsumerEnergyCosts, FacilityDemandPressure
from bosc.facility.power import derive_power_basis
from bosc.hydrology.model import ProvenancedValue
from bosc.logging import get_logger

log = get_logger(__name__)

_HOURS_PER_YEAR = 8760.0
_LOAD_FACTOR = 0.9  # data centers run near-flat; capacity utilization (assumption)
_LOAD_FACTOR_CITE = "data-center capacity utilization ~0.9 (near-flat 24x7 load); assumption"
# EIA: US average annual residential electricity consumption ~10,500 kWh/household.
_AVG_HOUSEHOLD_KWH_YR = 10500.0
_HOUSEHOLD_CITE = "US avg residential use ~10,500 kWh/household/yr (EIA FAQ); assumption"
# Stylized demand-to-price transmission: % price pressure per % demand increase, under
# tight short-run supply. A SCREENING band, not an estimated elasticity.
_KAPPA_LOW, _KAPPA_HIGH = 0.5, 1.0
_KAPPA_CITE = (
    "stylized demand-to-price transmission ~0.5-1.0 %price per %demand under tight "
    "short-run supply; a SCREENING sensitivity, not an estimated elasticity or forecast"
)

_ELEC_SALES_ID = "ELEC.SALES.OH-ALL.A"
_ELEC_PRICE_ID = "ELEC.PRICE.OH-RES.A"


def build_consumer_energy(*, settings: Settings | None = None) -> ConsumerEnergyCosts:
    """Pull the state's EIA consumer energy-cost dataset (live or offline-from-fixture)."""
    settings = settings or get_settings()
    costs = fetch_consumer_energy(settings=settings)
    log.info("econ.eia.consumer_energy", area=costs.area, series=len(costs.prices))
    return costs


def derive_demand_pressure(
    *,
    costs: ConsumerEnergyCosts | None = None,
    settings: Settings | None = None,
) -> FacilityDemandPressure:
    """Size the facility's electricity demand vs consumer prices (a sensitivity).

    ``costs`` defaults to the EIA pull/fixture; the facility draw is the central
    ``facility_draw`` from :func:`bosc.facility.power.derive_power_basis` (issue #87).
    """
    settings = settings or get_settings()
    costs = costs or build_consumer_energy(settings=settings)
    power = derive_power_basis(settings=settings)

    sales = costs.series(_ELEC_SALES_ID)
    price = costs.series(_ELEC_PRICE_ID)
    if sales is None or price is None:
        raise ValueError(f"consumer-energy dataset is missing {_ELEC_SALES_ID} / {_ELEC_PRICE_ID}")

    draw_mw = power.facility_draw.value
    consumption_gwh = draw_mw * _HOURS_PER_YEAR * _LOAD_FACTOR / 1000.0  # MWh -> GWh
    # EIA "million kWh" is numerically GWh (1 million kWh = 1 GWh).
    sales_gwh = sales.value.value
    share_pct = consumption_gwh / sales_gwh * 100.0 if sales_gwh else 0.0
    households = consumption_gwh * 1_000_000.0 / _AVG_HOUSEHOLD_KWH_YR  # GWh -> kWh / per-household
    kappa_central = (_KAPPA_LOW + _KAPPA_HIGH) / 2.0

    return FacilityDemandPressure(
        area=costs.area,
        facility_draw_mw=ProvenancedValue.derived(
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
        state_retail_sales_gwh=ProvenancedValue.from_connector(
            round(sales_gwh, 1),
            "GWh/yr",
            citation=f"EIA {sales.series_id} ({sales.period}); {sales.value.value:g} million kWh",
        ),
        demand_share_pct=ProvenancedValue.derived(
            round(share_pct, 2),
            "percent",
            citation=f"campus {consumption_gwh:.0f} GWh / Ohio retail {sales_gwh:.0f} GWh",
        ),
        avg_household_kwh_yr=ProvenancedValue.assume(
            _AVG_HOUSEHOLD_KWH_YR, "kWh/yr", why=_HOUSEHOLD_CITE
        ),
        households_equivalent=ProvenancedValue.derived(
            round(households),
            "households",
            citation=f"campus {consumption_gwh:.0f} GWh / {_AVG_HOUSEHOLD_KWH_YR:g} kWh per household",
        ),
        residential_price=ProvenancedValue.from_connector(
            price.value.value,
            price.value.unit,
            citation=f"EIA {price.series_id} ({price.period})",
        ),
        supply_elasticity=ProvenancedValue.assume(
            round(kappa_central, 2), "ratio", why=_KAPPA_CITE
        ),
        price_pressure_pct_low=ProvenancedValue.derived(
            round(share_pct * _KAPPA_LOW, 2),
            "percent",
            citation=f"{share_pct:.2f}% demand x {_KAPPA_LOW:g} transmission (STYLIZED lower bound)",
            confidence="low",
        ),
        price_pressure_pct_high=ProvenancedValue.derived(
            round(share_pct * _KAPPA_HIGH, 2),
            "percent",
            citation=f"{share_pct:.2f}% demand x {_KAPPA_HIGH:g} transmission (STYLIZED upper bound)",
            confidence="low",
        ),
        caveats=[
            "The demand share and households-equivalent are the robust, EIA-cited "
            "headline; the price-pressure band is a STYLIZED screening sensitivity, not "
            "a forecast of retail bills.",
            "The campus buys at wholesale/industrial rates, not the residential price "
            "shown — residential price is the consumer-impact reference, not the campus bill.",
            "Facility draw is itself an assumption-laden estimate (air-permit IT load x "
            "PUE band, #87); the load factor and transmission coefficient are assumptions.",
        ],
    )


def _reference_path(reference_dir: Path) -> Path:
    return reference_dir / "eia" / "consumer-energy.yaml"


def write_consumer_energy(costs: ConsumerEnergyCosts, *, settings: Settings | None = None) -> str:
    """Persist the EIA consumer energy-cost dataset as committed reference YAML."""
    settings = settings or get_settings()
    path = _reference_path(settings.reference_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(costs.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("econ.eia.wrote", path=str(path))
    return str(path)


def load_consumer_energy(reference_dir: Path) -> ConsumerEnergyCosts | None:
    """Read the committed consumer energy-cost YAML, or ``None`` if absent."""
    path = _reference_path(reference_dir)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return ConsumerEnergyCosts.model_validate(data)
