"""Typed models for the grid & regulatory stack (epic #93).

The layer **above** the facility power model (:mod:`watermark.facility.power`): the campus
load's serving electric utility, its balancing authority / RTO, and the load expressed
as a share of each. Like the other computed subsystems these use ``extra="forbid"`` and
carry provenance — numeric figures as :class:`watermark.hydrology.model.ProvenancedValue`,
string identifications as :class:`CitedFact` (the non-numeric analogue), so a serving
utility is *cited*, never asserted.

Issue #94 is the foundation layer (serving utility + BA profile + load share); #95-#98
(interchange, PJM market, FERC, federal policy) build on top.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from watermark.hydrology.model import ProvenancedValue, SourceKind


class CitedFact(BaseModel):
    """A non-numeric identification carrying provenance — the string analogue of
    :class:`ProvenancedValue`. ``source`` maps onto the same evidence discipline
    (``document``/``connector`` → verified; ``reference``/``assumption`` → asserted).
    """

    model_config = ConfigDict(extra="forbid")

    value: str  # "AEP Ohio (Ohio Power Company)"
    source: SourceKind
    citation: str
    confidence: Literal["high", "medium", "low"] = "medium"

    @property
    def verified(self) -> bool:
        return self.source in ("document", "connector")


class ServingUtility(BaseModel):
    """The cited identification of the campus's electric-service chain.

    Bottom of the regulatory stack: who delivers retail power (the utility, PUCO-
    regulated), within which balancing authority / RTO (PJM, FERC-jurisdictional), and
    its holding company. Each field is a :class:`CitedFact` — the working identification
    is corpus- or authoritative-source-grounded, with the EIA-861 service territory /
    PUCO map named as the formal confirmation source.
    """

    model_config = ConfigDict(extra="forbid")

    utility: CitedFact  # the retail electric utility serving the parcels
    holding_company: CitedFact  # its parent (e.g. American Electric Power)
    balancing_authority: CitedFact  # the BA / RTO that balances the load
    rto: CitedFact  # the wholesale-market RTO/ISO (FERC-jurisdictional)
    retail_regulator: CitedFact  # the state retail regulator (PUCO)
    note: str = ""


class UtilityProfile(BaseModel):
    """EIA-861 annual profile for the serving utility (retail sales / customers / price).

    **Connector-sourced**, not transcribed: :func:`watermark.grid.eia861.fetch_utility_retail`
    reduces the EIA-861 annual bulk zip's Sales-to-Ultimate-Customers sheet (or the 861S short
    form for a utility that files it) to this one utility's rows, so every value below is a
    ``connector`` :class:`ProvenancedValue` carrying the data year as its ``asof`` (G1/#1644).
    Not a facility disclosure — a published federal figure about the utility.

    ``avg_price_cents_kwh`` is a **cohort** price, not the utility's all-sector average (G3/#1644):
    on the full form it is bundled (standard-service-offer) revenue over bundled sales, i.e. the
    customers who never shopped, which in a restructured state skews residential and runs well
    above the all-sector rate. It is emphatically **not** what a large industrial / data-center
    customer pays — the value's own citation says so, and any surface that renders it must carry
    that qualification with it. (The short-form case has no such skew: a full-service
    municipal/cooperative's single line IS its whole retail cohort.)
    """

    model_config = ConfigDict(extra="forbid")

    utility: str  # "AEP Ohio (Ohio Power Company)"
    ownership: str = (
        ""  # EIA-861 ownership ("Investor Owned" / "Municipal" / "Cooperative"); "" if unread
    )
    # Overwritten by the connector with the form + total actually read; this default only
    # survives on a hand-authored profile.
    eia_source: str = "EIA-861 utility annual electric sales (connector)"
    retail_sales_gwh: ProvenancedValue  # connector (EIA-861)
    customers: ProvenancedValue | None = None  # connector (EIA-861)
    avg_price_cents_kwh: ProvenancedValue | None = None  # connector; bundled-SSO COHORT, see above


class BalancingAuthorityProfile(BaseModel):
    """EIA-930 annual profile for the balancing authority / RTO (PJM).

    Connector-sourced (:func:`watermark.grid.interchange.fetch_ba_annual_load` sums the EIA-930
    daily demand route over the configured ``eia930_year``); the load carries that year as its
    ``asof``.
    """

    model_config = ConfigDict(extra="forbid")

    ba: str  # "PJM Interconnection"
    eia_source: str = "EIA-930 hourly grid monitor, annual demand (connector)"
    annual_load_gwh: ProvenancedValue  # connector (EIA-930)


class GridLoadShare(BaseModel):
    """The campus load expressed as a share of utility / BA / state load.

    Sizes the campus annual electricity demand (from the first-class ``facility_draw``,
    :mod:`watermark.facility.power`, issue #87) against three cited denominators. All three are
    connector pulls (A1/#1638 replaced the last transcribed ones and made a missing denominator
    raise rather than zero-fill), so the confidence ordering that once separated them is gone.

    **They are not the same vintage** (G2/#1644). The EIA state seriesid route publishes ahead of
    the EIA-861 bulk file and the EIA-930 annual sum, so the three percentages here are struck
    against three different years' grids. That is a real property of the upstream data, not a
    defect — but it has to be visible: each denominator carries its year as ``asof``, each share's
    citation names the vintage it divided by, and :class:`GridProfile.note` states the spread.
    :func:`watermark.grid.utility._load_share_vintages` refuses to derive the block at all once
    the spread passes ``Settings.grid_vintage_max_spread_years``.
    """

    model_config = ConfigDict(extra="forbid")

    campus_load_mw: ProvenancedValue  # total facility draw, central (#87)
    load_factor: ProvenancedValue  # assumption: capacity utilization
    annual_consumption_gwh: ProvenancedValue  # derived: draw x 8760 x load factor
    utility_retail_gwh: ProvenancedValue  # serving-utility retail sales (connector, EIA-861)
    ba_load_gwh: ProvenancedValue  # BA annual load (connector, EIA-930)
    state_retail_gwh: ProvenancedValue  # state retail sales (connector, shared with #91)
    share_of_utility_pct: ProvenancedValue  # derived
    share_of_ba_pct: ProvenancedValue  # derived
    share_of_state_pct: ProvenancedValue  # derived


class GridProfile(BaseModel):
    """The assembled grid foundation layer (issue #94): identity + profiles + load share.

    ``load_share`` is ``None`` for a site with no documented data-center facility
    (``SiteProfile.facility is None``): the grid backdrop (serving utility + EIA utility/BA
    profiles) is real per-site data, but there is no campus load to express as a share of it
    until that site's facility is disclosed (the data-center dimension).
    """

    model_config = ConfigDict(extra="forbid")

    serving_utility: ServingUtility
    utility_profile: UtilityProfile
    ba_profile: BalancingAuthorityProfile
    load_share: GridLoadShare | None = None
    note: str = ""

    @property
    def has_real_denominators(self) -> bool:
        """True when the profile carries the nonzero load denominators it exists to establish.

        The grid backdrop's job is to say *whose* grid a site sits on and *how big* it is —
        the serving utility's retail sales and the balancing authority's annual load. A
        profile carrying zeros for both establishes neither: it is a shell.

        ``derive_grid_profile`` cannot produce one (A1/#1638 made the denominators live
        connector pulls that raise rather than zero-fill), but a stale or hand-authored
        ``grid-profile.yaml`` round-tripped through :func:`~watermark.grid.utility.load_grid_profile`
        can. Since the ``grid`` object feed is a **backdrop floor** signal (#1642, GP-E E1),
        such a shell must be dropped rather than shipped as a ``count == 1`` row that floats
        the backdrop domain to ``live`` — the #1364 present-but-empty rule, applied on the
        grid axis exactly as :attr:`FacilityDemandPressure.has_material_load` applies it on
        the facility axis (#1631).
        """
        return (
            self.utility_profile.retail_sales_gwh.value > 0
            and self.ba_profile.annual_load_gwh.value > 0
        )


class BAInterchange(BaseModel):
    """Reduced EIA-930 hourly interchange profile for one balancing authority (#95).

    The "interchange layer": the BA's hourly **demand**, **net generation**, and
    **total net interchange** (``TI``; sign convention + = net exports, - = net
    imports) summarized over a representative window from the EIA-930 Hourly Electric
    Grid Monitor. The point is to situate the campus load against where the BA's
    marginal electrons come from — in-BA generation vs net imports. Connector-sourced.
    """

    model_config = ConfigDict(extra="forbid")

    ba: str  # "PJM"
    period_start: str  # ISO date of the window start
    period_end: str
    hours: int  # hourly samples in the window
    demand_mean_mw: ProvenancedValue  # connector
    demand_peak_mw: ProvenancedValue
    net_generation_mean_mw: ProvenancedValue
    total_interchange_mean_mw: ProvenancedValue  # + = net exports, - = net imports
    interchange_min_mw: ProvenancedValue  # most-importing hour (most negative TI)
    interchange_max_mw: ProvenancedValue  # most-exporting hour
    net_import_hours_fraction: ProvenancedValue  # share of hours with TI < 0 (importing)
    source: str = "EIA-930 Hourly Electric Grid Monitor (region-data: D / NG / TI)"
    note: str = ""


class CampusInterchangeComparison(BaseModel):
    """Campus load situated against the BA's interchange & coincident-peak adequacy (#95, derived).

    Answers the call's question — how does the added ~275 MW sit against the BA's balance?
    The comparison sizes the campus against the BA's **mean demand**, its **coincident
    peak** (the binding case for a flat 24x7 data-center load), and the magnitude of its
    **net interchange** (the import/export swing).

    Evidentiary note (C1/C2/#1638): an earlier version headlined an "in-BA generation
    headroom" = mean net generation - mean demand. By the EIA-930 balance identity
    D = NG - TI, that quantity is **algebraically net interchange** (NG - D ≡ TI), so it
    duplicated ``ba_interchange_mean_mw`` and made the "fits within in-BA headroom → no
    imports needed" conclusion circular. It is dropped. Adequacy is now judged at the
    **coincident peak** — where the window peak demand exceeds mean in-BA net generation
    (``import_dependent_at_peak``), the BA already leans on imports/peaking and the campus
    adds on top — using the peak that was previously collected and discarded. A screening
    comparison over window aggregates, not an hourly dispatch or reserve-margin model
    (installed capacity is not in the EIA-930 region-data feed).
    """

    model_config = ConfigDict(extra="forbid")

    ba: str
    campus_load_mw: ProvenancedValue  # total facility draw, central (#87)
    ba_demand_mean_mw: ProvenancedValue  # connector (EIA-930)
    ba_demand_peak_mw: ProvenancedValue  # connector: the window coincident peak (C2)
    ba_net_generation_mean_mw: ProvenancedValue
    ba_interchange_mean_mw: ProvenancedValue  # + = net exports, - = net imports
    campus_share_of_demand_pct: ProvenancedValue  # derived: campus / BA mean demand
    campus_share_of_peak_demand_pct: ProvenancedValue  # derived: campus / BA peak demand (C2)
    campus_vs_interchange_pct: ProvenancedValue  # derived: campus / |BA mean interchange|
    peak_import_need_mw: ProvenancedValue  # derived: peak demand - mean in-BA net generation (C2)
    import_dependent_at_peak: bool  # peak demand exceeds mean in-BA net generation (C2)
    interpretation: str = ""
    caveats: list[str] = []
