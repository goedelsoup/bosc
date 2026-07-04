"""EPA AERMOD dispersion engine integration (Tier-1, #1178).

The air sibling of :mod:`watermark.hydrology.swmm`: build an AERMOD control + source deck
from the site's genset stack parameters and permit-certified emission rates, run the
vendored EPA binary, and parse the modeled ground-level concentrations back into typed
models. Gated behind the Tier-0 emissions inventory (:mod:`watermark.air`).

- :mod:`watermark.air.aermod.model` — typed deck inputs (stack geometry, sources,
  receptor grid, control). Stack geometry is ``assumption``-tagged for Lima: the permit
  redacts engine specs as CBI.
- :mod:`watermark.air.aermod.inp` — the ``aermod.inp`` five-pathway deck builders.
- :mod:`watermark.air.aermod.engine` — locate + run the AERMOD Fortran binary (graceful
  degradation when absent), parse its plotfiles.

Binary provenance/pinning: ``docs/AERMOD.md``. AERMET/AERMAP met + terrain connectors are
#1179 (deferred); the minimal acceptance run uses a committed canned met pair.
"""

from __future__ import annotations
