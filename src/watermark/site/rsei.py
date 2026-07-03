"""Export the Allen County RSEI toxic-release inventory as a typed feed.

Publishes ``data/reference/rsei/inventory.yaml`` (built by ``watermark rsei`` from the EPA RSEI
Public Data Set) as a feed. (The legacy markdown ``render_rsei`` peer was removed at the
SSG-cutover cleanup, #603.)
"""

from __future__ import annotations

from watermark.rsei import RseiInventory


def export_rsei(inv: RseiInventory) -> RseiInventory:
    """Export the RSEI inventory as a feed (it is already feed-ready).

    The inventory is a clean Pydantic model whose ``meta.source`` cites the EPA RSEI
    Public Data Set, so it already satisfies the #60 provenance discipline — the feed is
    the model itself. The exporter exists so every ``watermark.site.*`` module has one (#59).
    """
    return inv
