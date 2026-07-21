"""Derive the grid foundation layer: serving utility + BA profile + campus load share.

Issue #94 (foundation of epic #93). Identifies the campus's electric-service chain
(cited, not asserted), assembles the EIA utility/BA profile, and expresses the campus
load — the first-class ``facility_draw`` from :mod:`watermark.facility.power` (issue #87) —
as a provenance-tagged share of the serving utility's, the balancing authority's, and
the state's retail load.

Data discipline (epic #93): the serving-utility identification is grounded in the
committed corpus (the relator data appendix references the AEP Ohio tariff for this
campus; the Allen County commissioners' minutes reference local AEP service), with the
EIA-861 service territory / PUCO map named as the formal confirmation source. All three
load denominators are connector-sourced: the Ohio state-retail figure from EIA (shared
with #91), the AEP-Ohio per-utility retail from the EIA-861 bulk "Sales to Ultimate
Customers" file (:mod:`watermark.grid.eia861`), and the PJM annual demand from EIA-930
(:func:`watermark.grid.interchange.fetch_ba_annual_load`). See ``data/reference/eia/README.md``.
"""

from __future__ import annotations

from typing import NamedTuple

import yaml

from watermark.config import Settings, get_settings
from watermark.economics.energy import load_consumer_energy
from watermark.facility.consumption import HOURS_PER_YEAR as _HOURS_PER_YEAR
from watermark.facility.consumption import LOAD_FACTOR as _LOAD_FACTOR
from watermark.facility.consumption import annual_consumption_gwh
from watermark.facility.power import derive_power_basis
from watermark.grid.eia861 import fetch_utility_retail
from watermark.grid.interchange import fetch_ba_annual_load
from watermark.grid.model import (
    BalancingAuthorityProfile,
    CitedFact,
    GridLoadShare,
    GridProfile,
    ServingUtility,
)
from watermark.hydrology.model import ProvenancedValue
from watermark.logging import get_logger
from watermark.sites import active_profile

log = get_logger(__name__)

_LOAD_FACTOR_CITE = "data-center capacity utilization ~0.9 (near-flat 24x7); assumption (cf. #91)"

# All three load denominators are now LIVE connector pulls — fetch_utility_retail
# (watermark.grid.eia861), fetch_ba_annual_load (watermark.grid.interchange), and the state
# retail from the committed #91 EIA consumer-energy dataset. There is deliberately NO
# hardcoded state fallback: a missing state denominator RAISES (A1/#1638), never silently
# substitutes Ohio's figure for another state's — the economics demand-pressure layer (#1103)
# raises on the identical condition.


# Full state name for prose/citation labels (keyed by EIA state). Keeps the readable form
# in per-site citations (Lima "Ohio", Fort Wayne "Indiana") rather than the bare abbreviation;
# an unlisted state falls back to its abbreviation.
_STATE_NAME: dict[str, str] = {"OH": "Ohio", "IN": "Indiana"}


# Per-state retail electric regulator (the serving-utility chain). OH + IN cover the sites
# registered today; an unlisted state falls back to a generic state-regulator label.
_RETAIL_REGULATOR: dict[str, tuple[str, str]] = {
    "OH": (
        "Public Utilities Commission of Ohio (PUCO)",
        "Ohio retail electric service is PUCO-regulated (intrastate)",
    ),
    "IN": (
        "Indiana Utility Regulatory Commission (IURC)",
        "Indiana retail electric service is IURC-regulated (intrastate)",
    ),
}


def _retail_regulator(state: str, ownership: str) -> tuple[str, str]:
    """The retail rate regulator for a utility's ownership in ``state`` (value, citation).

    Investor-owned utilities are state-PUC rate-regulated (:data:`_RETAIL_REGULATOR`); a
    municipal electric system sets its own retail rates under **home rule** (not PUC-
    regulated), and a cooperative's rates are member/board-regulated — so the regulator is a
    function of ownership, not just the state. ``ownership`` is the EIA-861 ownership string.
    """
    own = ownership.lower()
    if "municipal" in own:
        return (
            f"municipal (home rule, {state})",
            f"{state} municipal electric systems set their own retail rates under home rule "
            "(not state-PUC rate-regulated)",
        )
    if "cooperative" in own or "co-op" in own:
        return (
            f"member-regulated electric cooperative ({state})",
            f"{state} electric cooperatives set retail rates by member/board governance "
            "(not state-PUC rate-regulated)",
        )
    return _RETAIL_REGULATOR.get(
        state,
        (
            f"{state} state utility regulator",
            f"{state} retail electric service is state-regulated (intrastate)",
        ),
    )


class _UtilityGrid(NamedTuple):
    """A serving utility's parent + PJM market-zone provenance (the non-connector chain)."""

    holding_company: str
    holding_citation: str
    ba_citation: str
    rto_citation: str


# Per-utility holding company + PJM transmission-zone provenance, keyed by EIA-861 utility
# number. The AEP-family utilities (Ohio Power #14006 for Lima/Findlay/Van Wert, Indiana
# Michigan Power #9324 for Fort Wayne) share the AEP parent; The Toledo Edison Co #18997 is
# FirstEnergy (the PJM **ATSI** zone, not AEP) — the first registered non-AEP utility; Dayton
# Power & Light / AES Ohio #4922 (WPAFB/Xenia) is the AES-parent, PJM **DAY** zone IOU. An
# unlisted utility falls back to a zone-agnostic PJM phrasing keyed off the EIA-861 name.
_UTILITY_GRID: dict[int, _UtilityGrid] = {
    14006: _UtilityGrid(
        holding_company="American Electric Power (AEP)",
        holding_citation="AEP Ohio is the Ohio operating company of American Electric Power",
        ba_citation="AEP's Ohio (AEP/APS) transmission zone is within the PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for AEP Ohio",
    ),
    9324: _UtilityGrid(
        holding_company="American Electric Power (AEP)",
        holding_citation="Indiana Michigan Power (I&M) is an AEP operating company",
        ba_citation="Indiana Michigan Power's transmission zone is within the PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Indiana Michigan Power",
    ),
    18997: _UtilityGrid(
        holding_company="FirstEnergy Corp",
        holding_citation="Toledo Edison is an Ohio operating company of FirstEnergy Corp",
        ba_citation="Toledo Edison's ATSI (FirstEnergy) transmission zone is within the PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Toledo Edison (ATSI zone)",
    ),
    2439: _UtilityGrid(
        # The network's first MUNICIPAL utility (Bryan, OH) — no IOU holding company; its
        # wholesale power + PJM scheduling are through American Municipal Power (AMP).
        holding_company="City of Bryan (municipal; American Municipal Power member)",
        holding_citation="Bryan Municipal Utilities is a municipally-owned electric system "
        "with no IOU holding company; its wholesale power and PJM scheduling are through "
        "American Municipal Power (AMP), the Ohio municipal joint-action agency",
        ba_citation="Bryan's municipal load is scheduled into the PJM RTO footprint via "
        "American Municipal Power (EIA-861S BA Code PJM)",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Bryan (AMP/PJM)",
    ),
    4922: _UtilityGrid(
        # The Miami-basin serving IOU (WPAFB #442, Xenia #444) — Dayton Power & Light,
        # d/b/a AES Ohio, the AES Corporation operating company; its transmission zone is
        # PJM's **DAY** zone, the network's first non-AEP/non-ATSI IOU zone.
        holding_company="The AES Corporation (AES Ohio)",
        holding_citation="Dayton Power & Light Co does business as AES Ohio, the Ohio "
        "operating company of The AES Corporation",
        ba_citation="Dayton Power & Light's (AES Ohio) DAY transmission zone is within the "
        "PJM RTO footprint",
        rto_citation="PJM is the FERC-jurisdictional wholesale-market RTO for Dayton Power "
        "& Light (AES Ohio)",
    ),
}


def _utility_grid(utility_number: int, utility_name: str) -> _UtilityGrid:
    """Parent/zone provenance for a utility; a generic PJM fallback for an unlisted one."""
    known = _UTILITY_GRID.get(utility_number)
    if known is not None:
        return known
    return _UtilityGrid(
        holding_company=utility_name,
        holding_citation=f"{utility_name} parent/holding company — identified from the EIA-861 record",
        ba_citation=f"{utility_name}'s transmission zone is within the PJM RTO footprint",
        rto_citation=f"PJM is the FERC-jurisdictional wholesale-market RTO for {utility_name}",
    )


def _serving_utility(
    settings: Settings, utility_name: str, *, ownership: str = ""
) -> ServingUtility:
    """The cited serving-utility chain. The utility *name* is connector-sourced (EIA-861);
    its *provenance* (source + citation) is per-site — a corpus document for Lima, the
    EIA-861 service-territory record for a site without corpus coverage. The retail regulator
    is ownership-aware (:func:`_retail_regulator`): a state PUC for an IOU, home rule for a
    municipal, member-regulated for a cooperative. The holding company / market zone are
    per-utility (:data:`_UTILITY_GRID`): AEP for Lima/Findlay/Van Wert (#14006) and Fort
    Wayne's I&M (#9324), FirstEnergy/ATSI for Toledo's Toledo Edison (#18997), AMP/PJM for
    Bryan's municipal system (#2439). RTO is PJM for every registered site; an unlisted
    utility gets a generic PJM fallback.
    """
    prof = active_profile(settings)
    reg_value, reg_citation = _retail_regulator(prof.eia_state, ownership)
    is_public = any(k in ownership.lower() for k in ("municipal", "cooperative", "co-op"))
    reg_short = (
        reg_value[reg_value.find("(") + 1 : reg_value.rfind(")")] if "(" in reg_value else reg_value
    )
    grid = _utility_grid(prof.eia861_utility_number, utility_name)
    # Provenance grounding follows the per-site serving_utility source: Lima's is a corpus
    # document (the AEP-Ohio tariff in the relator appendix); a site without corpus coverage is
    # grounded in the EIA-861 service-territory record instead.
    grounding = (
        "corpus-grounded (AEP Ohio tariff referenced for this campus)"
        if prof.serving_utility_source == "document"
        else "identified from the EIA-861 service-territory file"
    )
    return ServingUtility(
        utility=CitedFact(
            value=utility_name,
            source=prof.serving_utility_source,
            citation=prof.serving_utility_citation,
            confidence="high",
        ),
        holding_company=CitedFact(
            value=grid.holding_company,
            source="reference",
            citation=grid.holding_citation,
            confidence="high",
        ),
        balancing_authority=CitedFact(
            value="PJM Interconnection",
            source="reference",
            citation=grid.ba_citation,
            confidence="high",
        ),
        rto=CitedFact(
            value="PJM Interconnection (RTO/ISO)",
            source="reference",
            citation=grid.rto_citation,
            confidence="high",
        ),
        retail_regulator=CitedFact(
            value=reg_value,
            source="reference",
            citation=reg_citation,
            confidence="high",
        ),
        note=(
            (
                f"Serving utility is {grounding}; RTO=PJM is authoritative. The retail "
                f"service area is the utility's own ({reg_short}), not a PUC-certified IOU "
                f"territory; it is confirmed against the EIA-861 service-territory file (#94)."
            )
            if is_public
            else (
                f"Serving utility is {grounding}; RTO=PJM is authoritative. The retail "
                f"service-territory boundary is formally confirmed against the EIA-861 territory "
                f"file / {reg_short} map (#94)."
            )
        ),
    )


def _state_retail_gwh(settings: Settings) -> ProvenancedValue:
    """State total retail sales from the committed #91 EIA dataset (connector). GWh.

    EIA 'million kWh' is numerically GWh. The state denominator is connector-sourced,
    state-aware, and never a hardcoded fallback (A1/#1638): a missing dataset or a
    zero/absent retail-sales series RAISES (mirroring the economics demand-pressure guard,
    #1103) rather than silently substituting one state's figure for another's — so a
    non-Ohio site can never inherit Ohio's 149,003 GWh denominator.
    """
    prof = active_profile(settings)
    state = prof.eia_state
    costs = load_consumer_energy(settings)
    if costs is None:
        raise ValueError(
            f"site {settings.site!r} ({state}): no committed consumer-energy dataset at "
            f"{prof.consumer_energy_relpath} — cannot source the state retail denominator; "
            "run `watermark eia` for this site first (refusing to fall back to Ohio's figure)"
        )
    sales = costs.by_metric("electricity", "sales")
    if sales is None or not sales.value.value:
        raise ValueError(
            f"consumer-energy dataset for {state} has a missing/zero electricity retail-sales "
            f"series ({sales.value.value if sales else None!r}) — cannot derive a state load "
            "share from an absent denominator"
        )
    return ProvenancedValue.from_connector(
        round(sales.value.value, 1),
        "GWh/yr",
        citation=f"EIA {sales.series_id} ({sales.period}); shared with #91",
    )


def derive_grid_profile(*, settings: Settings | None = None) -> GridProfile:
    """Assemble the serving utility, the EIA utility/BA profile, and the campus load share.

    For a site with no documented facility (``derive_power_basis`` returns ``None``) the
    campus ``load_share`` is omitted: the grid backdrop (serving utility + connector-sourced
    utility/BA/state denominators) is real per-site data, but there is no campus load to
    fabricate against it (the data-center dimension onboarding does not capture).
    """
    settings = settings or get_settings()
    power = derive_power_basis(settings=settings)

    # Live connector pulls (#94/#120): per-utility EIA-861 + PJM annual EIA-930.
    utility_profile = fetch_utility_retail(settings=settings)
    ba_load = fetch_ba_annual_load(settings=settings)

    load_share: GridLoadShare | None = None
    if power is not None:
        draw_mw = power.facility_draw.value
        consumption_gwh = annual_consumption_gwh(draw_mw)
        utility_retail = utility_profile.retail_sales_gwh
        # The state denominator is only needed for the campus share, so resolve it here (a
        # facility-less site skips it and never trips the A1 raise for an absent dataset).
        state_retail = _state_retail_gwh(settings)
        eia_state = active_profile(settings).eia_state
        state_name = _STATE_NAME.get(eia_state, eia_state)

        def _share(denom: float, *, of: str) -> float:
            # A zero/absent denominator means a broken upstream (empty connector, fixture
            # drift), not that the campus is a negligible share. Refuse to synthesize a "0%
            # load share" from an absent denominator (A3/#1638; the #1103 raise-on-zero guard).
            if not denom:
                raise ValueError(
                    f"grid load-share denominator {of!r} is zero/absent for site "
                    f"{settings.site!r} — cannot derive a load share from a broken denominator"
                )
            return consumption_gwh / denom * 100.0

        load_share = GridLoadShare(
            campus_load_mw=ProvenancedValue.derived(
                round(draw_mw, 1),
                "MW",
                citation=(
                    f"PowerBasis.facility_draw central (#87): {power.facility_draw.citation or ''}"
                ),
            ),
            load_factor=ProvenancedValue.assume(_LOAD_FACTOR, "fraction", why=_LOAD_FACTOR_CITE),
            annual_consumption_gwh=ProvenancedValue.derived(
                round(consumption_gwh, 1),
                "GWh/yr",
                citation=f"{draw_mw:g} MW x {_HOURS_PER_YEAR:g} h x {_LOAD_FACTOR:g} load factor",
            ),
            utility_retail_gwh=utility_retail,
            ba_load_gwh=ba_load,
            state_retail_gwh=state_retail,
            share_of_utility_pct=ProvenancedValue.derived(
                round(_share(utility_retail.value, of="utility retail (EIA-861)"), 2),
                "percent",
                citation=f"campus {consumption_gwh:.0f} GWh / {utility_profile.utility} "
                f"{utility_retail.value:,.0f} GWh (EIA-861 {settings.eia861_year} per-utility)",
            ),
            share_of_ba_pct=ProvenancedValue.derived(
                round(_share(ba_load.value, of="BA annual load (EIA-930)"), 3),
                "percent",
                citation=f"campus {consumption_gwh:.0f} GWh / PJM {ba_load.value:,.0f} GWh "
                "(EIA-930 annual demand)",
            ),
            share_of_state_pct=ProvenancedValue.derived(
                round(_share(state_retail.value, of="state retail (EIA)"), 2),
                "percent",
                citation=f"campus {consumption_gwh:.0f} GWh / "
                f"{state_name} {state_retail.value:.0f} GWh",
            ),
        )

    log.info(
        "grid.profile",
        utility=utility_profile.utility,
        ba="PJM",
        consumption_gwh=(load_share.annual_consumption_gwh.value if load_share else None),
        share_utility_pct=(load_share.share_of_utility_pct.value if load_share else None),
    )
    state_label = _STATE_NAME.get(
        active_profile(settings).eia_state, active_profile(settings).eia_state
    )
    note = (
        f"Grid foundation layer (#94). The state, {utility_profile.utility}, and PJM denominators "
        f"are now all connector-sourced — {state_label} retail from EIA (shared with #91), "
        "per-utility retail from the EIA-861 file, and PJM annual demand from EIA-930. The campus "
        "is a single load equal to a material fraction of its serving utility's entire retail sales."
        if load_share is not None
        else (
            "Grid foundation layer (#94): per-site grid backdrop only. This site has no "
            "documented data-center facility, so there is no campus load to express as a "
            "share — the utility/BA/state denominators are real connector-sourced data, but "
            "the campus load share awaits the site's facility disclosure (the data-center "
            "dimension onboarding does not capture)."
        )
    )
    return GridProfile(
        serving_utility=_serving_utility(
            settings, utility_profile.utility, ownership=utility_profile.ownership
        ),
        utility_profile=utility_profile,
        ba_profile=BalancingAuthorityProfile(
            ba="PJM Interconnection",
            eia_source="EIA-930 daily demand sum, annual (connector)",
            annual_load_gwh=ba_load,
        ),
        load_share=load_share,
        note=note,
    )


def write_grid_profile(profile: GridProfile, *, settings: Settings | None = None) -> str:
    """Persist the grid profile as committed reference YAML; return the path.

    Per-site write (#326 econ): the active site's ``grid_relpath`` (Lima = the legacy path).
    The profile aggregates the per-site utility (EIA-861) + shared state/PJM data; the reader
    (``load_grid_profile``) resolves the same per-site path.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).grid_relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(profile.model_dump(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    log.info("grid.profile.wrote", path=str(path))
    return str(path)


def load_grid_profile(settings: Settings | None = None) -> GridProfile | None:
    """Read the committed grid-profile YAML for the active site, or ``None`` if absent.

    Per-site (#606): resolves ``grid_relpath`` off the active profile so a non-Lima read
    returns that site's grid profile, not Lima's.
    """
    settings = settings or get_settings()
    path = settings.data_dir / active_profile(settings).grid_relpath
    if not path.is_file():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return GridProfile.model_validate(data)
