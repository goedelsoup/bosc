"""Link the data-center's power draw to consumer energy-price pressure (issue #91).

The 2026-06-10 call: "bring in fuel costs at the consumer level due to macro pressures
and data-center demand." This assembles the committed EIA consumer energy-cost
reference (``build_consumer_energy`` / ``write_consumer_energy`` / ``load_consumer_energy``)
and derives a **sensitivity** relating the facility's first-class total ``facility_draw``
(:mod:`watermark.facility.power`, issue #87) to that consumer price.

The honest framing: the campus's annual electricity demand, expressed as a share of
EIA state retail sales and as a households-equivalent, is the robust, fully-cited
headline. The price-pressure band is a deliberately STYLIZED screening illustration
from a stated demand-to-price transmission coefficient — retail price formation is far
more complex than one coefficient, so it is reported as a sensitivity, never a forecast.
"""

from __future__ import annotations

import yaml

from watermark.config import Settings, get_settings
from watermark.economics.connectors.eia import fetch_consumer_energy
from watermark.economics.model import ConsumerEnergyCosts, FacilityDemandPressure
from watermark.facility.consumption import HOURS_PER_YEAR as _HOURS_PER_YEAR
from watermark.facility.consumption import LOAD_FACTOR as _LOAD_FACTOR
from watermark.facility.consumption import annual_consumption_gwh
from watermark.facility.power import derive_power_basis
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

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
    ``facility_draw`` from :func:`watermark.facility.power.derive_power_basis` (issue #87).
    """
    settings = settings or get_settings()
    costs = costs or build_consumer_energy(settings=settings)
    power = derive_power_basis(settings=settings)
    if power is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility (SiteProfile.facility is None) — "
            "the facility demand-pressure sensitivity needs a facility power basis"
        )

    # The state retail-sales + residential-price series, templated by the dataset's OWN state
    # (the same legacy-id template the connector pulls — watermark.economics.connectors.eia). This is
    # what un-hardcodes Ohio: a non-OH facility site resolves its own state's series, not OH's.
    state = costs.area
    sales_id = f"ELEC.SALES.{state}-ALL.A"
    price_id = f"ELEC.PRICE.{state}-RES.A"
    sales = costs.series(sales_id)
    price = costs.series(price_id)
    if sales is None or price is None:
        raise ValueError(f"consumer-energy dataset is missing {sales_id} / {price_id}")

    draw_mw = power.facility_draw.value
    consumption_gwh = annual_consumption_gwh(draw_mw)
    # The consumption figure the datum displays (1-decimal). The households-equivalent derives
    # from *this* shown value, not the raw float, so a reader can reproduce it from the two cited
    # fields (annual demand ÷ per-household use) — the reference stays internally consistent.
    consumption_shown = round(consumption_gwh, 1)
    # EIA "million kWh" is numerically GWh (1 million kWh = 1 GWh).
    sales_gwh = sales.value.value
    share_pct = consumption_gwh / sales_gwh * 100.0 if sales_gwh else 0.0
    households = consumption_shown * 1_000_000.0 / _AVG_HOUSEHOLD_KWH_YR  # GWh -> kWh per household
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
            consumption_shown,
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
            citation=f"campus {consumption_gwh:.0f} GWh / {costs.area_name} retail {sales_gwh:.0f} GWh",
        ),
        avg_household_kwh_yr=ProvenancedValue.assume(
            _AVG_HOUSEHOLD_KWH_YR, "kWh/yr", why=_HOUSEHOLD_CITE
        ),
        households_equivalent=ProvenancedValue.derived(
            round(households),
            "households",
            citation=f"campus {consumption_shown:g} GWh / {_AVG_HOUSEHOLD_KWH_YR:g} kWh per household",
        ),
        residential_price=ProvenancedValue.from_connector(
            price.value.value,
            price.value.unit,
            citation=f"EIA {price.series_id} ({price.period})",
        ),
        transmission_coefficient=ProvenancedValue.assume(
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


def write_consumer_energy(costs: ConsumerEnergyCosts, *, settings: Settings | None = None) -> str:
    """Persist the EIA consumer energy-cost dataset as committed reference YAML.

    Per-site write (#326 econ): the active site's ``consumer_energy_relpath`` (Lima = the
    legacy path). State-level data, but kept per-site for a uniform onboard tree; the reader
    (``load_consumer_energy``) resolves the same per-site path.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).consumer_energy_relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(costs.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("econ.eia.wrote", path=str(path))
    return str(path)


def load_consumer_energy(settings: Settings | None = None) -> ConsumerEnergyCosts | None:
    """Read the committed consumer energy-cost YAML for the active site, or ``None``.

    Per-site (#606): resolves ``consumer_energy_relpath`` off the active profile so a
    non-Lima read returns that site's state-level prices, not Lima's.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).consumer_energy_relpath
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return ConsumerEnergyCosts.model_validate(data)


def write_demand_pressure(
    pressure: FacilityDemandPressure, *, settings: Settings | None = None
) -> str:
    """Persist the facility demand-pressure sensitivity as committed reference YAML (issue #1105).

    Per-site: the active site's ``demand_pressure_relpath`` (Lima = the un-slugged legacy path),
    mirroring ``write_consumer_energy``. Only meaningful for a site with a documented facility —
    ``derive_demand_pressure`` raises for a facility-less site, so callers gate on the profile.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).demand_pressure_relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(pressure.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("econ.demand_pressure.wrote", path=str(path))
    return str(path)


def load_demand_pressure(settings: Settings | None = None) -> FacilityDemandPressure | None:
    """Read the committed demand-pressure YAML for the active site, or ``None``.

    Per-site: resolves ``demand_pressure_relpath`` off the active profile. Absent for a thin
    (facility-less) site — the caller (the ``economics-demand-pressure`` bundle feed) simply
    omits the feed, exactly as the derivation is gated on ``SiteProfile.facility``.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).demand_pressure_relpath
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return FacilityDemandPressure.model_validate(data)
