"""Typed inputs for an EPA AERMOD dispersion deck (Tier-1, #1178).

AERMOD models the ground-level concentration of a pollutant downwind of one or more
point sources (here, the site's emergency diesel gensets). A run needs three physical
inputs, modeled below as provenance-tagged Pydantic values so the deck keeps its audit
trail:

- :class:`GensetStackParams` — the per-unit **stack geometry** (release height, inside
  diameter, exit velocity, exit temperature). **Critical provenance boundary:** the Lima
  air permit (P0138965) does *not* state these — engine make/model/size is redacted as
  Confidential Business Information (Comments 16/19, Response 16). So the defaults here are
  ``assumption``-tagged screening values for a large (~2.75 MW) stationary diesel genset,
  **never** presented as the permit's. A site that later obtains the manufacturer stack
  data passes them in as ``document`` values — the model holds the seam, not a fabricated
  fact.
- :class:`AermodSource` — one point source: a location + its stack params + the per-source
  emission rate (g/s). The rate *is* grounded (permit-certified lb/hr, converted).
- :class:`ReceptorGrid` — the Cartesian receptor grid the concentrations are computed on.
- :class:`AermodControl` — the modeled pollutant, averaging periods, and terrain flag.

Contractor/site-agnostic, exactly like the rest of :mod:`watermark.air`: the model holds
*values* threaded in from the active site's profile/permit, never a hardcoded site.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from watermark.air.model import Pollutant
from watermark.hydrology.model import ProvenancedValue

# g per lb and s per hr — the lb/hr (permit rate) -> g/s (AERMOD SRCPARAM) conversion.
_G_PER_LB = 453.59237
_S_PER_HR = 3600.0
LB_PER_HR_TO_G_PER_S = _G_PER_LB / _S_PER_HR  # ~0.125998


def lb_per_hr_to_g_per_s(lb_per_hr: float) -> float:
    """Convert a permit emission rate (lb/hr) to the AERMOD source rate (g/s)."""
    return lb_per_hr * LB_PER_HR_TO_G_PER_S


class GensetStackParams(BaseModel):
    """Per-unit exhaust-stack geometry for one genset — the AERMOD ``SRCPARAM`` physicals.

    Every field is a :class:`ProvenancedValue`. For Lima these are ``assumption``-tagged
    screening values (the permit redacts engine specs as CBI); a site with disclosed
    manufacturer data supplies ``document`` values instead. See
    :func:`watermark.air.aermod.inp.assumed_stack_params`.
    """

    model_config = ConfigDict(extra="forbid")

    height_m: ProvenancedValue  # release height above ground (m)
    diameter_m: ProvenancedValue  # inside stack diameter at exit (m)
    exit_velocity_ms: ProvenancedValue  # exhaust exit velocity (m/s)
    exit_temp_k: ProvenancedValue  # exhaust exit temperature (K)

    @property
    def all_assumption(self) -> bool:
        """True if every geometry field is an asserted modeling input (not documented)."""
        return all(
            v.source == "assumption"
            for v in (self.height_m, self.diameter_m, self.exit_velocity_ms, self.exit_temp_k)
        )


class AermodSource(BaseModel):
    """One AERMOD ``POINT`` source: a location, stack geometry, and emission rate.

    ``emission_g_s`` is ``derived`` — the permit-certified per-engine rate (lb/hr) converted
    to g/s. ``x_m``/``y_m`` are model-grid metres (a local origin is fine for a single-site
    screening run); ``base_elev_m`` is the stack-base ground elevation.
    """

    model_config = ConfigDict(extra="forbid")

    src_id: str = Field(min_length=1, max_length=8)  # AERMOD source id (<=8 chars)
    pollutant: Pollutant
    x_m: float
    y_m: float
    base_elev_m: float
    emission_g_s: ProvenancedValue
    stack: GensetStackParams


class ReceptorGrid(BaseModel):
    """A uniform Cartesian receptor grid (AERMOD ``GRIDCART`` / ``XYINC``).

    ``x0``/``y0`` are the SW corner (m), ``nx``/``ny`` the counts, ``dx``/``dy`` the spacing
    (m). A modest grid centered on the source is enough for a screening single-source run.
    """

    model_config = ConfigDict(extra="forbid")

    net_id: str = Field(default="GRID1", min_length=1, max_length=8)
    x0_m: float
    y0_m: float
    nx: int = Field(ge=1)
    ny: int = Field(ge=1)
    dx_m: float = Field(gt=0)
    dy_m: float = Field(gt=0)

    @classmethod
    def centered(
        cls, *, half_extent_m: float, spacing_m: float, net_id: str = "GRID1"
    ) -> ReceptorGrid:
        """A square grid centered on the origin, spanning ±``half_extent_m`` at ``spacing_m``."""
        n = round(2 * half_extent_m / spacing_m) + 1
        return cls(
            net_id=net_id,
            x0_m=-half_extent_m,
            y0_m=-half_extent_m,
            nx=n,
            ny=n,
            dx_m=spacing_m,
            dy_m=spacing_m,
        )


# AERMOD averaging periods: short-term hour counts, plus the special ANNUAL/PERIOD tokens.
AveragePeriod = Literal["1", "3", "8", "24", "MONTH", "PERIOD", "ANNUAL"]


class AermodControl(BaseModel):
    """The AERMOD control pathway: pollutant, averaging periods, terrain, title.

    ``terrain="FLAT"`` is the minimal screening assumption (the acceptance case); ``"ELEV"``
    needs AERMAP-processed receptor elevations (#1179, deferred). ``regulatory_default``
    emits ``MODELOPT DFAULT`` (the EPA regulatory option set).
    """

    model_config = ConfigDict(extra="forbid")

    title: str = "Watermark AERMOD screening run"
    pollutant: Pollutant = "NOx"
    averaging_periods: tuple[AveragePeriod, ...] = ("1", "ANNUAL")
    terrain: Literal["FLAT", "ELEV"] = "FLAT"
    regulatory_default: bool = True
    flagpole_height_m: float | None = None  # receptor height above ground; None = ground level
