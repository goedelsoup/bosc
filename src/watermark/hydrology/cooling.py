"""A sourced cooling-water design basis for the data-center campus.

Since #1055 this module is a thin **dispatcher** over the cooling-model taxonomy
(:mod:`watermark.hydrology.cooling_models`): the archetype comes from the active site's
``SiteFacility.cooling_model`` (never hardcoded — #1054), and each archetype's spec owns
its own consumptive/withdrawal math. The historical two-method evaporative bracket —

* **Top-down (power x WUE).** The Ohio EPA air permit P0138965 lists 114 emergency
  generators at 2,750 ekW = ~313 MW backup; at hyperscale N+1 ratios that implies a
  ~250-300 MW IT load. Evaporative consumptive water = IT energy x a water-use
  effectiveness (WUE). This is the central estimate.
* **Bottom-up (blowdown x cycles).** The documented 2.5 MGD FM-2 industrial
  discharge (CMAR RFQ §A.6), if taken as cooling-tower blowdown at typical cycles of
  concentration, implies the evaporation upper bound (makeup = blowdown x CoC).

— is now the ``evaporative_tower`` archetype (Lima's, made explicit), regression-locked
so the reference build's committed figures do not move.
"""

from __future__ import annotations

from watermark.config import Settings, get_settings
from watermark.hydrology import cooling_models
from watermark.hydrology.cooling_models import (
    _AIR_PERMIT_CITE,
    _BACKUP_MW,
    _CYCLES,
    _CYCLES_CITE,
    _FM2_BLOWDOWN_MGD,
    _FM2_CITE,
    _GENSET_COUNT,
    _GENSET_MW,
    _IT_LOAD_MW,
    _WUE_CITE,
    _WUE_L_PER_KWH,
    CoolingParams,
)
from watermark.hydrology.model import CoolingBasis
from watermark.sites import CoolingModelType, active_profile

# The evaporative_tower defaults are re-exported for legacy consumers (#1055).
__all__ = [
    "_AIR_PERMIT_CITE",
    "_BACKUP_MW",
    "_CYCLES",
    "_CYCLES_CITE",
    "_FM2_BLOWDOWN_MGD",
    "_FM2_CITE",
    "_GENSET_COUNT",
    "_GENSET_MW",
    "_IT_LOAD_MW",
    "_WUE_CITE",
    "_WUE_L_PER_KWH",
    "derive_cooling_basis",
]


def derive_cooling_basis(
    settings: Settings | None = None,
    *,
    cooling_model: CoolingModelType | str | None = None,
    it_load_mw: float | None = None,
    blowdown_mgd: float | None = None,
    wue_l_per_kwh: float | None = None,
    cycles: float | None = None,
) -> CoolingBasis:
    """Derive the cooling design basis for the active site's cooling archetype.

    Dispatch (#1055): the archetype is ``cooling_model`` when given (sensitivity runs),
    else the active site's ``SiteProfile.facility.cooling_model``; a site with no
    facility is ``off``. The spec registered in
    :data:`~watermark.hydrology.cooling_models.COOLING_MODELS` does the math — the
    evaporative two-method bracket is one archetype, not the universal path.

    Per-site (#607): IT load, the blowdown cross-check, WUE/CoC overrides, and their
    citations come from the active site's ``SiteProfile.facility``; the keyword
    overrides still win, for sensitivity sweeps. A facility that discloses no blowdown
    uses the site's own power-derived consumptive as the high bound — so no Lima FM-2
    figure leaks into another site's estimate.
    """
    settings = settings or get_settings()
    facility = active_profile(settings).facility
    model = cooling_models.resolve_cooling_model(facility, override=cooling_model)
    spec = cooling_models.get(model)
    params = CoolingParams(
        it_load_mw=it_load_mw,
        blowdown_mgd=blowdown_mgd,
        wue_l_per_kwh=wue_l_per_kwh,
        cycles_of_concentration=cycles,
    )
    return spec.derive(facility, params, settings)
