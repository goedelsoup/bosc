"""Export the localized economic baseline + consumer energy costs as typed feeds.

Generated from the committed ``data/reference/economics/baseline.yaml`` (BLS QCEW) and
``data/reference/eia/consumer-energy.yaml`` (EIA), not a live pull — so the static build
needs no network. (The legacy markdown ``render_economics`` peer was removed at the
SSG-cutover cleanup, #603.)
"""

from __future__ import annotations

from watermark.economics.model import ConsumerEnergyCosts, EconomicBaseline


def export_economics(baseline: EconomicBaseline) -> EconomicBaseline:
    """Export the localized economic baseline as a feed (it is already feed-ready).

    Every number on the baseline is a :class:`~watermark.economics.model.ProvenancedValue`
    (BLS QCEW / Census ACS), so the model already carries structured provenance per #60 —
    the feed is the model itself; this exporter gives the module a uniform surface (#59).
    """
    return baseline


def export_consumer_energy(costs: ConsumerEnergyCosts) -> ConsumerEnergyCosts:
    """Export the state consumer energy-cost dataset as a feed (already feed-ready).

    Each series carries its full annual history (``points``) plus the latest cited value
    (issue #1111), so the frontend can chart electricity/gas price trends. Like
    :func:`export_economics`, the feed is the provenanced model itself (#60/#59).
    """
    return costs
