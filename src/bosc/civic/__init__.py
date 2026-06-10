"""Civic-records subsystem: Allen County political-subdivision meeting minutes/agendas.

Parallel to ``bosc.hydrology`` but for governance records. A canonical registry of
the county's meeting-holding bodies (``data/reference/subdivisions/``) drives a
discovery pass that classifies where each body publishes, and (downstream) a small
set of per-platform fetchers that pull minutes/agendas into ``data/documents/``.

Reuses the shared connector cache/offline/fixture machinery in ``bosc.connectors``
(against the hydrology cache root + fixtures it shares), so it gets the same
offline/fixture discipline as every other subsystem's connectors.
"""

from __future__ import annotations

from bosc.civic.models import (
    DiscoveryResult,
    MeetingDoc,
    Platform,
    Registry,
    Subdivision,
)
from bosc.civic.registry import load_registry

__all__ = [
    "DiscoveryResult",
    "MeetingDoc",
    "Platform",
    "Registry",
    "Subdivision",
    "load_registry",
]
