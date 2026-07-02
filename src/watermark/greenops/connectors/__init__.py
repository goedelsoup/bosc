"""GreenOps connectors — per-source billing/usage pulls (#1078-#1082).

Pure-sync ``fn(..., settings) -> pydantic`` pulls (AWS Cost Explorer + Customer Carbon
Footprint Tool, Anthropic Admin usage, GitHub Actions, EPA eGRID) that reuse the neutral
``watermark.connectors`` cache/offline/fixture machinery (``cached_get``) pointed at
``settings.greenops_cache_dir`` — so tests stay hermetic and an offline miss raises an
actionable ``OfflineError`` naming the key to record. Credentials come from ``settings``
(AWS SDK names, ``anthropic_admin_key``), excluded from the cache key and added only in
the live fetch, mirroring the EIA connector template.

Empty this issue (#1077 scaffolds the package only); the connectors land next.
"""

from __future__ import annotations

__all__: list[str] = []
