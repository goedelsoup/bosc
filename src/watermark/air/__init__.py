"""Air-quality & backup-generation dispatch modeling (epic #1172).

The direct sibling of :mod:`watermark.hydrology`: a **Tier-0 analytic emissions
inventory** (this package today) escalating to a **Tier-1 AERMOD dispersion** run
(``air/aermod/``, gated behind Tier-0). It connects three things already in the repo:
the grid-stress model (:mod:`watermark.grid`), the documented diesel backup fleet
(the site's air permit, e.g. OEPA PTI P0138965), and the evidence discipline.

Tier-0 pieces:

- :mod:`watermark.air.model` — the provenance-tagged emission-factor models.
- :mod:`watermark.air.emissions` — AP-42 §3.4 + permit factor loaders and their
  reconciliation.
- :mod:`watermark.air.dispatch` — the reliability dispatch-trigger model (grid stress
  signals → a genset runtime-hours band).
- :mod:`watermark.air.calibration` — anchors that band to a **captured real event**
  (the PJM §202(c) order, #1174): the event's verified authorization window dimensions
  the runtime, replacing the pure BA-wide escalation fraction.
- :mod:`watermark.air.scenario` — the scenario runner + synthetic-minor NSR
  cap-exceedance check.

Every figure carries a :class:`watermark.hydrology.model.ProvenancedValue`; nothing is
hardcoded to a single site — emission factors, engine rating, fleet, and permit caps
resolve from the active site's profile / permit extraction.
"""

from __future__ import annotations
