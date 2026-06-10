"""Economics connectors — pure-sync ``fn(..., settings) -> pydantic`` pulls.

Reuse the neutral ``bosc.connectors`` cache/offline/fixture machinery (``cached_get``)
pointed at the economics cache root, so tests stay hermetic and offline misses raise an
actionable ``OfflineError`` naming the key to record.
"""

from __future__ import annotations

from bosc.economics.connectors.census import fetch_population_series
from bosc.economics.connectors.qcew import fetch_county_industries

__all__ = ["fetch_county_industries", "fetch_population_series"]
