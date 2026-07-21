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
from watermark.economics.model import ConsumerEnergyCosts, EnergyBurden, FacilityDemandPressure
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
# EIA: US average residential natural-gas consumption ~70 Mcf/customer/yr (thousand cu ft).
_AVG_HOUSEHOLD_MCF_YR = 70.0
_HOUSEHOLD_GAS_CITE = (
    "US avg residential natural-gas use ~70 Mcf/household/yr (EIA consumption per "
    "customer); assumption — applies to gas-heated homes"
)
# Stylized demand-to-price transmission: % price pressure per % demand increase, under
# tight short-run supply. A SCREENING band, not an estimated elasticity.
_KAPPA_LOW, _KAPPA_HIGH = 0.5, 1.0
_KAPPA_CITE = (
    "stylized demand-to-price transmission (%price per %demand) under tight short-run "
    "supply — the low/high band is a SCREENING sensitivity, not an estimated elasticity "
    "or forecast"
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
        # No power basis: either no disclosed facility, or a facility whose IT load is entirely
        # `[open]` (a rezoning-only campus, #1628) — don't claim `facility is None` when it isn't.
        raise ValueError(
            f"site {settings.site!r} has no derivable facility power basis (no disclosed facility, "
            "or its IT load is entirely [open]) — the demand-pressure sensitivity needs one"
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
    if not sales_gwh:
        # A zero/missing denominator means the retail-sales series is broken (upstream gap,
        # fixture drift), not that the campus is a negligible share. Refuse to synthesize a
        # "0% demand share" from absent data — matching the missing-series guard above.
        raise ValueError(
            f"consumer-energy dataset has zero/missing retail sales for {sales_id} "
            f"({sales_gwh!r}) — cannot derive a demand share from an absent denominator"
        )
    share_pct = consumption_gwh / sales_gwh * 100.0
    households = consumption_shown * 1_000_000.0 / _AVG_HOUSEHOLD_KWH_YR  # GWh -> kWh per household
    kappa_central = (_KAPPA_LOW + _KAPPA_HIGH) / 2.0

    return FacilityDemandPressure(
        area=costs.area,
        facility_draw_mw=ProvenancedValue.derived(
            round(draw_mw, 1),
            "MW",
            citation=f"PowerBasis.facility_draw central (#87): {power.facility_draw.citation or ''}",
            # Carry through the PUE band from PowerBasis.facility_draw (#760) rather than
            # dropping the upstream uncertainty at the feed boundary.
            low=power.facility_draw.low,
            high=power.facility_draw.high,
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
            # Cite the same shown (1-decimal-rounded) consumption figure as
            # ``annual_consumption_gwh``/``households_equivalent`` — not the raw unrounded
            # value — so the three citations agree on one reproducible number.
            citation=f"campus {consumption_shown:g} GWh / {costs.area_name} retail {sales_gwh:.0f} GWh",
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
            # The central is the band mean; carry the 0.5-1.0 spread as data (#760) instead
            # of only in the citation prose.
            round(kappa_central, 2),
            "ratio",
            why=_KAPPA_CITE,
            low=_KAPPA_LOW,
            high=_KAPPA_HIGH,
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


def derive_energy_burden(
    *,
    costs: ConsumerEnergyCosts | None = None,
    income: ProvenancedValue | None = None,
    settings: Settings | None = None,
) -> EnergyBurden:
    """Household energy burden = annual home-energy spend / median household income (#1110).

    ``costs`` defaults to the EIA pull/fixture; ``income`` is the Census B19013 median
    household income (:func:`watermark.economics.connectors.census.fetch_median_household_income`),
    defaulting to a fresh pull for the active site's latest ACS5 vintage. A fully **[derived]**
    consumer-impact metric — unlike the stylized demand→price band, every input is cited. This
    also gives the fetched-but-unused residential natural-gas price a job.
    """
    settings = settings or get_settings()
    costs = costs or build_consumer_energy(settings=settings)
    if income is None:
        # Deferred import: the income pull lives with the population pull on the baseline's
        # Census connector, and the baseline year constant is that module's business.
        from watermark.economics.baseline import _INCOME_YEAR
        from watermark.economics.connectors.census import fetch_median_household_income

        income = fetch_median_household_income(year=_INCOME_YEAR, settings=settings)

    elec = costs.by_metric("electricity", "price")
    gas = costs.by_metric("natural_gas", "price")
    if elec is None or gas is None:
        raise ValueError(
            f"energy burden needs residential electricity + natural-gas prices; the "
            f"{costs.area} consumer-energy dataset is missing one"
        )
    income_usd = income.value
    if income_usd <= 0:
        raise ValueError(f"median household income must be positive, got {income_usd}")

    # Electricity: kWh/yr x cents/kWh / 100 -> $/yr. Gas: Mcf/yr x $/Mcf -> $/yr.
    elec_price = elec.value.value  # cents/kWh
    elec_cost = _AVG_HOUSEHOLD_KWH_YR * elec_price / 100.0
    gas_price = gas.value.value  # $/Mcf
    gas_cost = _AVG_HOUSEHOLD_MCF_YR * gas_price
    combined_cost = elec_cost + gas_cost

    return EnergyBurden(
        area=costs.area,
        area_name=costs.area_name,
        median_household_income=income,
        avg_household_kwh_yr=ProvenancedValue.assume(
            _AVG_HOUSEHOLD_KWH_YR, "kWh/yr", why=_HOUSEHOLD_CITE
        ),
        residential_electricity_price=ProvenancedValue.from_connector(
            elec_price, elec.value.unit, citation=f"EIA {elec.series_id} ({elec.period})"
        ),
        electricity_annual_cost=ProvenancedValue.derived(
            round(elec_cost, 2),
            "USD/yr",
            citation=f"{_AVG_HOUSEHOLD_KWH_YR:g} kWh/yr x {elec_price:g} cents/kWh",
        ),
        electricity_burden_pct=ProvenancedValue.derived(
            round(elec_cost / income_usd * 100.0, 2),
            "percent",
            citation=f"${elec_cost:,.0f}/yr electricity / ${income_usd:,.0f} median household income",
        ),
        avg_household_mcf_yr=ProvenancedValue.assume(
            _AVG_HOUSEHOLD_MCF_YR, "Mcf/yr", why=_HOUSEHOLD_GAS_CITE
        ),
        residential_gas_price=ProvenancedValue.from_connector(
            gas_price, gas.value.unit, citation=f"EIA {gas.series_id} ({gas.period})"
        ),
        gas_annual_cost=ProvenancedValue.derived(
            round(gas_cost, 2),
            "USD/yr",
            citation=f"{_AVG_HOUSEHOLD_MCF_YR:g} Mcf/yr x {gas_price:g} $/Mcf",
        ),
        gas_burden_pct=ProvenancedValue.derived(
            round(gas_cost / income_usd * 100.0, 2),
            "percent",
            citation=f"${gas_cost:,.0f}/yr gas / ${income_usd:,.0f} median household income",
        ),
        combined_annual_cost=ProvenancedValue.derived(
            round(combined_cost, 2),
            "USD/yr",
            citation=f"${elec_cost:,.0f}/yr electricity + ${gas_cost:,.0f}/yr gas",
        ),
        combined_burden_pct=ProvenancedValue.derived(
            round(combined_cost / income_usd * 100.0, 2),
            "percent",
            citation=f"${combined_cost:,.0f}/yr electricity+gas / ${income_usd:,.0f} income",
        ),
        caveats=[
            "Median household income is county-level (Census B19013); residential energy "
            "prices are state averages (EIA) — the burden mixes a county denominator with "
            "state prices.",
            "The gas and combined burdens assume a gas-heated home at average use; a home "
            "heating with electricity or another fuel carries no gas burden.",
            "Household electricity/gas use are national-average assumptions — actual use "
            "varies with climate, home size, and efficiency.",
        ],
    )


def build_energy_burden(settings: Settings | None = None) -> EnergyBurden | None:
    """Assemble the household energy burden from committed reference data, or ``None``.

    Reads the committed EIA consumer-energy prices (:func:`load_consumer_energy`) and the
    committed baseline's median household income (Census B19013) — both offline artifacts,
    so the site build needs no live pull. Returns ``None`` when either is absent (a site that
    hasn't onboarded income yet), so the feed is skipped and the section degrades (#781).
    """
    settings = settings or get_settings()
    from watermark.economics.baseline import load_baseline

    costs = load_consumer_energy(settings)
    baseline = load_baseline(settings)
    if costs is None or baseline is None or baseline.median_household_income is None:
        return None
    return derive_energy_burden(
        costs=costs, income=baseline.median_household_income, settings=settings
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
    relpath = active_profile(settings).demand_pressure_relpath
    if relpath is None:
        raise ValueError(
            "the active site declares no demand_pressure_relpath (facility-less site) — "
            "a demand-pressure sensitivity has no destination without a documented facility"
        )
    path = settings.data_dir / relpath
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
    relpath = active_profile(settings).demand_pressure_relpath
    if relpath is None:
        return None  # facility-less site: no destination, so nothing to load
    path = settings.data_dir / relpath
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return FacilityDemandPressure.model_validate(data)
