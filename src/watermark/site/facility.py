"""Project the active site's disclosed data-center facilities into the `facility` bundle feed.

Generated from ``SiteProfile.facilities`` (the multi-facility model, #1628 / epic #1626 F2) — a
machine-readable projection, not a new extraction: each figure's provenance rides on the validated
model and is carried through verbatim, so nothing is re-keyed by hand across the seam. Peer of
:mod:`watermark.site.economics` (the feed IS the projected model). Facility-gated — ``None`` (feed
skipped) / summary absent for a site with no disclosed facility, exactly like the readiness
``facility`` domain gate.
"""

from __future__ import annotations

from watermark.config import Settings, get_settings
from watermark.site.feeds import FacilityItem, FacilitySummary
from watermark.sites import SiteFacility, SiteProfile, active_profile


def _committed_geometry(
    profile: SiteProfile, fac: SiteFacility, *, is_primary: bool, settings: Settings
) -> tuple[str | None, str | None]:
    """Resolve a facility's ``(parcels_relpath, footprint_relpath)`` for the feed (#1628 review).

    Only the PRIMARY (modeled) campus inherits the site-level geometry; a secondary campus carries
    ONLY its own (``None`` when it hasn't committed any) — inheriting the primary's would
    misattribute one campus's parcels to another. And a link is emitted only when the artifact
    actually exists under ``settings.data_dir`` — an ``[open]``/placeholder path that was never
    committed ships as ``null``, not a phantom link.
    """
    parcels: str | None
    footprint: str | None
    if is_primary:
        parcels, footprint = profile.facility_geometry(fac)
    else:
        parcels, footprint = fac.parcels_relpath, fac.footprint_relpath

    def _existing(relpath: str | None) -> str | None:
        return relpath if relpath and (settings.data_dir / relpath).is_file() else None

    return _existing(parcels), _existing(footprint)


def build_facility_feed(settings: Settings | None = None) -> list[FacilityItem] | None:
    """Project the active site's ``facilities`` into a list of :class:`FacilityItem` rows.

    Returns ``None`` (feed skipped) for a facility-less site. The first facility is the primary
    (modeled) campus; its geometry inherits the site default, secondaries carry only their own.
    """
    settings = settings or get_settings()
    profile = active_profile(settings)
    if not profile.facilities:
        return None
    items: list[FacilityItem] = []
    for i, fac in enumerate(profile.facilities):
        parcels, footprint = _committed_geometry(
            profile, fac, is_primary=(i == 0), settings=settings
        )
        items.append(
            FacilityItem(
                key=fac.key,
                name=fac.name,
                is_primary=(i == 0),
                status=fac.status,
                operator=fac.operator,
                operator_citation=fac.operator_citation,
                end_use=fac.end_use,
                end_use_citation=fac.end_use_citation,
                facility_type=fac.facility_type,
                it_load_mw=fac.it_load_mw,
                it_load_low_mw=fac.it_load_low_mw,
                it_load_high_mw=fac.it_load_high_mw,
                # Keep the two groundings distinct so the permit-vs-screening discriminant survives
                # (#1697 / #1628 review) — exactly one is set on a disclosed load, both None on [open].
                air_permit_citation=fac.air_permit_citation,
                air_permit_relpath=fac.air_permit_relpath,
                it_load_citation=fac.it_load_citation,
                gross_floor_area_sqft=fac.gross_floor_area_sqft,
                disclosed_investment_usd=fac.disclosed_investment_usd,
                disclosure_citation=fac.disclosure_citation,
                cooling_model=fac.cooling_model,
                cooling_model_source=fac.cooling_model_source,
                cooling_model_citation=fac.cooling_model_citation,
                parcels_relpath=parcels,
                footprint_relpath=footprint,
            )
        )
    return items


def build_facility_summary(settings: Settings | None = None) -> FacilitySummary | None:
    """The manifest's compact facility block: the PRIMARY campus's status + the facility count.

    ``None`` for a facility-less site, so the frontend badge reader defaults to ``investigation``.
    """
    settings = settings or get_settings()
    profile = active_profile(settings)
    primary = profile.facility
    if primary is None:
        return None
    return FacilitySummary(
        status=primary.status,
        count=len(profile.facilities),
        primary_name=primary.name,
        primary_operator=primary.operator,
        primary_end_use=primary.end_use,
    )
