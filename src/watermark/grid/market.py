"""PJM wholesale-market context for the campus load (#96, epic #93).

The "RTO / wholesale market" layer of the grid & regulatory stack: above the
serving-utility / BA identification (#94) and the EIA-930 interchange layer (#95),
this situates the campus load against the three price signals a large new load in
PJM actually sees -

  - zonal **LMP** (locational marginal price - the energy price signal),
  - the **capacity market** (RPM - the Base Residual Auction clearing price, which
    drives the capacity obligation a large new load implies), and
  - the **large-load interconnection queue** (the data-center / large-load interest
    PJM has reported, against which the campus is sized).

Data discipline (epic #93): NO live PJM connector is provided here - PJM Data Miner 2
needs no key but is not reachable from this environment, so the published figures are
**transcribed** into a committed reference YAML (``data/reference/pjm/pjm-market.yaml``)
as :class:`watermark.hydrology.model.ProvenancedValue` at ``confidence="medium"``, each
citation naming its source (PJM Data Miner 2, PJM Base Residual Auction reports, PJM
interconnection-queue reporting) and flagged *verify / regenerate via PJM Data Miner 2*.
The derived scenario is a **screening** view in the "bracket, don't overclaim" idiom -
LMP varies by node and hour, the RPM clearing price is not the campus's contracted
rate, and the queue figure is order-of-magnitude. **Nothing here is a facility
disclosure**: the campus draw is the first-class ``facility_draw`` from
:mod:`watermark.facility.power` (#87); everything else is published market data.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from watermark.config import Settings, get_settings
from watermark.connectors import OfflineError
from watermark.facility.consumption import HOURS_PER_YEAR as _HOURS_PER_YEAR
from watermark.facility.consumption import LOAD_FACTOR as _LOAD_FACTOR
from watermark.facility.consumption import annual_consumption_gwh, load_factor_cite
from watermark.facility.power import derive_power_basis
from watermark.grid.lmp import PjmLmpError, fetch_zonal_lmp
from watermark.grid.model import CitedFact
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import SiteProfile, active_profile, site_reference_path

log = get_logger(__name__)

_LOAD_FACTOR_CITE = load_factor_cite(refs="#91/#94/#95")
_DAYS_PER_YEAR = 365.0

# --- Transcribed PJM published figures (verify / regenerate via PJM Data Miner 2) ----
# Zonal LMP: the site's pricing-zone average annual locational marginal price + its cite are
# per-site (active SiteProfile: lmp_usd_mwh / lmp_citation; Lima = AEP zone).
# Capacity (RPM): 2025/2026 Base Residual Auction RTO-wide clearing price, a major
# spike from the prior 2024/2025 delivery year.
_RPM_CLEARING_USD_MW_DAY = 269.92
_RPM_PRIOR_USD_MW_DAY = 28.92
_RPM_CLEARING_CITE = (
    "PJM 2025/2026 Base Residual Auction, RTO-wide clearing price ($/MW-day); "
    "transcribed published figure - verify (PJM RPM BRA report)"
)
_RPM_PRIOR_CITE = (
    "PJM 2024/2025 Base Residual Auction, RTO-wide clearing price ($/MW-day) - "
    "the prior-year level, for context; transcribed - verify (PJM RPM BRA report)"
)
# Large-load / interconnection queue: PJM-reported large-load / data-center interest.
# Order-of-magnitude only - do not overstate precision.
_LARGE_LOAD_QUEUE_GW = 50.0
_LARGE_LOAD_QUEUE_CITE = (
    "PJM large-load / data-center interconnection interest, order-of-magnitude "
    "(tens of GW) ~2024; transcribed - verify (PJM interconnection-queue reporting)"
)


class PjmMarketReference(BaseModel):
    """The transcribed PJM published market figures (the reference inputs, #96).

    Each numeric figure is a :class:`ProvenancedValue` tagged ``reference`` at
    ``confidence="medium"`` whose citation names its PJM source and is flagged for
    verification - none is asserted as ground truth. The non-numeric BA/zone/RTO
    identifications are :class:`CitedFact`. Regenerate by re-reading PJM Data Miner 2 /
    the RPM Base Residual Auction reports / the interconnection-queue reporting.
    """

    model_config = ConfigDict(extra="forbid")

    rto: CitedFact  # "PJM Interconnection (RTO/ISO)"
    lmp_zone: CitedFact  # the LMP pricing zone the campus sits in (AEP)
    zonal_lmp_usd_mwh: ProvenancedValue  # reference: AEP-zone annual average LMP
    rpm_clearing_usd_mw_day: ProvenancedValue  # reference: RTO-wide BRA clearing price
    rpm_prior_year_usd_mw_day: ProvenancedValue  # reference: prior-year clearing, for context
    large_load_queue_gw: (
        ProvenancedValue  # reference: large-load / data-center queue (order-of-mag)
    )
    source: str = (
        "PJM Data Miner 2 / PJM RPM Base Residual Auction reports / PJM queue (transcribed; verify)"
    )
    note: str = ""


class PjmMarketScenario(BaseModel):
    """The campus load's marginal-price / capacity footprint in PJM (#96, derived).

    A provenance-tagged screening scenario: the campus annual energy cost at the zonal
    LMP, its annual capacity-market (RPM) obligation at the clearing price, and the
    campus sized against the large-load interconnection queue. The campus draw is the
    first-class ``facility_draw`` (#87); the prices are transcribed PJM reference
    figures. **Not** a settlement, dispatch, or RPM-bidding model - a bracketed view.
    """

    model_config = ConfigDict(extra="forbid")

    rto: str  # "PJM Interconnection (RTO/ISO)"
    lmp_zone: str  # "AEP zone"
    campus_load_mw: ProvenancedValue  # total facility draw, central (#87)
    load_factor: ProvenancedValue  # assumption: capacity utilization
    annual_consumption_gwh: ProvenancedValue  # derived: draw x 8760 x load factor
    zonal_lmp_usd_mwh: ProvenancedValue  # reference: AEP-zone annual average LMP
    rpm_clearing_usd_mw_day: ProvenancedValue  # reference: RTO-wide BRA clearing price
    annual_energy_cost_musd: ProvenancedValue  # derived: consumption x LMP -> $M/yr
    annual_capacity_cost_musd: ProvenancedValue  # derived: draw x clearing x 365 -> $M/yr
    large_load_queue_gw: ProvenancedValue  # reference: large-load queue (order-of-magnitude)
    campus_share_of_queue_pct: ProvenancedValue  # derived: campus MW / queue GW
    interpretation: str = ""
    caveats: list[str] = []


def _zonal_lmp(prof: SiteProfile, settings: Settings) -> tuple[CitedFact, ProvenancedValue]:
    """The site's pricing zone + its day-ahead LMP, connector-sourced when the zone is pinned (#121).

    When the profile pins a PJM pricing zone (``lmp_pnode_id``), prefer the live PJM Data Miner 2
    zonal day-ahead mean (or its committed fixture offline); fall back to the committed
    ``lmp_usd_mwh`` reference if the connector is unreachable / unkeyed. A site whose zone is not
    yet pinned (Bryan/AMP #411, Fort Wayne/I&M #361) uses the transcribed reference placeholder.
    """
    if prof.lmp_pnode_id:
        zone = CitedFact(
            value=f"{prof.lmp_pnode_name} zone",
            source="connector",
            citation=f"PJM pricing zone {prof.lmp_pnode_name} (pnode {prof.lmp_pnode_id}); "
            "the campus's LMP zone via PJM Data Miner 2 (#121)",
            confidence="high",
        )
        try:
            z = fetch_zonal_lmp(
                pnode_id=prof.lmp_pnode_id, zone=prof.lmp_pnode_name, settings=settings
            )
            lmp = ProvenancedValue.from_connector(
                z.mean_da_lmp_usd_mwh,
                "USD/MWh",
                citation=f"PJM Data Miner 2 da_hrl_lmps, {z.zone} zone (pnode {z.pnode_id}), "
                f"{z.period_start[:4]} day-ahead annual mean ({z.n_hours} h)",
                confidence="medium",
            )
            return zone, lmp
        except (OfflineError, PjmLmpError) as exc:
            log.warning("grid.pjm_lmp.fallback", zone=prof.lmp_pnode_name, error=str(exc))
    else:
        zone = CitedFact(
            value=f"{prof.lmp_pnode_name} zone" if prof.lmp_pnode_name else "PJM zone (unpinned)",
            source="reference",
            citation="PJM pricing zone not yet pinned (transcribed placeholder; verify)",
            confidence="medium",
        )
    return zone, ProvenancedValue.from_reference(
        prof.lmp_usd_mwh, "USD/MWh", citation=prof.lmp_citation, confidence="medium"
    )


def _market_reference(settings: Settings) -> PjmMarketReference:
    """Assemble the PJM market figures: zonal LMP connector-sourced (#121), the rest transcribed."""
    prof = active_profile(settings)
    lmp_zone, zonal_lmp = _zonal_lmp(prof, settings)
    return PjmMarketReference(
        rto=CitedFact(
            value="PJM Interconnection (RTO/ISO)",
            source="reference",
            citation="PJM is the FERC-jurisdictional wholesale-market RTO for AEP Ohio (#94)",
            confidence="high",
        ),
        lmp_zone=lmp_zone,
        zonal_lmp_usd_mwh=zonal_lmp,
        rpm_clearing_usd_mw_day=ProvenancedValue.from_reference(
            _RPM_CLEARING_USD_MW_DAY,
            "USD/MW-day",
            citation=_RPM_CLEARING_CITE,
            confidence="medium",
        ),
        rpm_prior_year_usd_mw_day=ProvenancedValue.from_reference(
            _RPM_PRIOR_USD_MW_DAY, "USD/MW-day", citation=_RPM_PRIOR_CITE, confidence="medium"
        ),
        large_load_queue_gw=ProvenancedValue.from_reference(
            _LARGE_LOAD_QUEUE_GW, "GW", citation=_LARGE_LOAD_QUEUE_CITE, confidence="medium"
        ),
        note=(
            "Zonal LMP is connector-sourced from PJM Data Miner 2 da_hrl_lmps (#121) when the "
            "site's pricing zone is pinned (the energy price signal - LMP = energy + congestion + "
            "losses); the RPM clearing price and large-load queue remain transcribed published "
            "figures (verify / regenerate via the RPM Base Residual Auction reports + PJM "
            "interconnection-queue reporting). Not a facility disclosure."
        ),
    )


def derive_pjm_market_scenario(*, settings: Settings | None = None) -> PjmMarketScenario:
    """Derive the campus load's PJM marginal-price / capacity footprint (#96).

    Links the first-class ``facility_draw`` (#87) to the transcribed PJM LMP / RPM /
    queue reference figures: annual energy cost at the zonal LMP, the annual RPM
    capacity obligation at the clearing price, and the campus sized against the
    large-load interconnection queue. A bracketed screening view, not a settlement model.
    """
    settings = settings or get_settings()
    power = derive_power_basis(settings=settings)
    if power is None:
        raise ValueError(
            f"site {settings.site!r} has no documented facility (SiteProfile.facility is None) — "
            "the PJM market scenario needs a facility load"
        )
    ref = _market_reference(settings)

    draw_mw = power.facility_draw.value
    consumption_mwh = draw_mw * _HOURS_PER_YEAR * _LOAD_FACTOR
    consumption_gwh = annual_consumption_gwh(draw_mw)  # == consumption_mwh / 1000.0

    lmp = ref.zonal_lmp_usd_mwh.value
    clearing = ref.rpm_clearing_usd_mw_day.value
    queue_gw = ref.large_load_queue_gw.value

    # Energy cost: consumption (MWh/yr) x LMP ($/MWh) -> $/yr -> $M/yr.
    annual_energy_cost_musd = consumption_mwh * lmp / 1_000_000.0
    # Capacity cost: draw (MW) x clearing ($/MW-day) x 365 days -> $/yr -> $M/yr.
    annual_capacity_cost_musd = draw_mw * clearing * _DAYS_PER_YEAR / 1_000_000.0
    # Campus MW as a fraction of the large-load queue (GW -> MW).
    share_of_queue_pct = draw_mw / (queue_gw * 1000.0) * 100.0 if queue_gw else 0.0

    interp = (
        f"At the {ref.lmp_zone.value} average LMP (~${lmp:g}/MWh) the campus's ~{consumption_gwh:,.0f} "
        f"GWh/yr of energy costs on the order of ${annual_energy_cost_musd:,.0f}M/yr; its "
        f"RPM capacity footprint at the 2025/2026 BRA clearing price (${clearing:g}/MW-day) "
        f"is on the order of ${annual_capacity_cost_musd:,.0f}M/yr for {draw_mw:g} MW of "
        f"unforced capacity. That capacity figure tracks an ~{clearing / ref.rpm_prior_year_usd_mw_day.value:.0f}x "
        f"clearing-price spike over the prior year. The campus ({draw_mw:g} MW) is "
        f"~{share_of_queue_pct:.1f}% of the reported large-load interconnection queue "
        f"(~{queue_gw:g} GW, order-of-magnitude) - one campus, a small slice of a very "
        "large pipeline. Bracketing figures, not the campus's contracted costs."
    )

    log.info(
        "grid.pjm_market",
        lmp_usd_mwh=lmp,
        rpm_usd_mw_day=clearing,
        energy_cost_musd=round(annual_energy_cost_musd, 1),
        capacity_cost_musd=round(annual_capacity_cost_musd, 1),
        share_of_queue_pct=round(share_of_queue_pct, 2),
    )
    return PjmMarketScenario(
        rto=ref.rto.value,
        lmp_zone=ref.lmp_zone.value,
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
        zonal_lmp_usd_mwh=ref.zonal_lmp_usd_mwh,
        rpm_clearing_usd_mw_day=ref.rpm_clearing_usd_mw_day,
        annual_energy_cost_musd=ProvenancedValue.derived(
            round(annual_energy_cost_musd, 1),
            "USD_million/yr",
            citation=f"{consumption_gwh:,.0f} GWh x ${lmp:g}/MWh ({ref.lmp_zone.value} LMP, "
            f"{ref.zonal_lmp_usd_mwh.source})",
            confidence="medium",
        ),
        annual_capacity_cost_musd=ProvenancedValue.derived(
            round(annual_capacity_cost_musd, 1),
            "USD_million/yr",
            citation=f"{draw_mw:g} MW x ${clearing:g}/MW-day x {_DAYS_PER_YEAR:g} d "
            "(2025/2026 BRA clearing, transcribed; verify)",
            confidence="medium",
        ),
        large_load_queue_gw=ref.large_load_queue_gw,
        campus_share_of_queue_pct=ProvenancedValue.derived(
            round(share_of_queue_pct, 2),
            "percent",
            citation=f"campus {draw_mw:g} MW / large-load queue {queue_gw:g} GW "
            "(order-of-magnitude, transcribed; verify)",
            confidence="medium",
        ),
        interpretation=interp,
        caveats=[
            "A SCREENING price/capacity footprint, not a settlement or dispatch model - "
            "energy and capacity are settled hourly/by delivery year against the campus's "
            "actual contracts, not these annualized averages.",
            "LMP varies by NODE and HOUR (LMP = energy + congestion + losses); the zonal "
            "annual average is a single point, not the campus's bus-specific or peak-hour price.",
            "The RPM clearing price is an RTO-wide CLEARING price, not the campus's contracted "
            "capacity rate; the 2025/2026 spike may not persist, and obligations depend on the "
            "campus's coincident-peak contribution, not nameplate MW.",
            "The large-load / interconnection-queue figure is ORDER-OF-MAGNITUDE (tens of GW) "
            "and not all queued load is built; the campus share is illustrative.",
            "Zonal LMP is connector-sourced (PJM Data Miner 2 da_hrl_lmps) when the zone is "
            "pinned; the RPM clearing price + large-load queue remain TRANSCRIBED published "
            "values at medium confidence (verify via the RPM BRA reports). None is a facility "
            "disclosure.",
        ],
    )


def _reference_path(settings: Settings) -> Path:
    """The active site's PJM-market path (#1639/B1). Per-site because the reference embeds the
    site's LMP pricing zone (AEP→ATSI→DAY) — a slug-scoped default unless the profile pins one
    (Lima keeps the un-slugged legacy path)."""
    return site_reference_path(
        settings, active_profile(settings).pjm_relpath, subdir="pjm", filename="pjm-market.yaml"
    )


def write_pjm_market(reference: PjmMarketReference, *, settings: Settings | None = None) -> str:
    """Persist the PJM market reference as committed YAML for the active site; return the path."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(reference.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("grid.pjm_market.wrote", path=str(path))
    return str(path)


def load_pjm_market(settings: Settings | None = None) -> PjmMarketReference | None:
    """Read the committed PJM market reference YAML for the active site, or ``None`` if absent."""
    settings = settings or get_settings()
    path = _reference_path(settings)
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return PjmMarketReference.model_validate(data)
