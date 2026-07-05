"""AERMET/AERMAP preprocessing connectors (epic #1172, #1179).

Live public-data pulls for the AERMOD preprocessors, each under the offline/committed-fixture
connector discipline (:mod:`._cache`):

- :mod:`.isd` — NOAA ISD hourly surface met (AERMET SURFACE / ISHD input)
- :mod:`.igra` — NOAA IGRA v2 upper-air soundings (AERMET UPPERAIR input)
- :mod:`.ned` — USGS 3DEP/NED DEM raster (AERMAP terrain input)

and the file emitters that stage the preprocessor runs from those pulls:

- :mod:`.aermet` — surface + upper-air → AERMET-ready files + runstream
- :mod:`.aermap` — DEM → receptor/source elevations + AERMAP control file
"""

from __future__ import annotations

from watermark.air.connectors._cache import AirOfflineError

__all__ = ["AirOfflineError"]
