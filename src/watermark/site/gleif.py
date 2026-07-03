"""Export the GLEIF LEI resolution as a typed feed.

Publishes ``data/reference/gleif/lei-records.yaml`` (built by ``watermark lei``) — the corridor
entity parents' "who owns whom" records — as a feed. (The legacy markdown ``render_gleif``
peer was removed at the SSG-cutover cleanup, #603.)
"""

from __future__ import annotations

from watermark.gleif import LeiInventory


def export_gleif(inv: LeiInventory) -> LeiInventory:
    """Export the GLEIF LEI inventory as a feed (it is already feed-ready).

    Like the RSEI feed, the inventory is a clean Pydantic model whose ``meta.source``
    cites GLEIF, so it already meets the #60 provenance discipline — the feed is the
    model itself; this exporter just gives the module a uniform export surface (#59).
    """
    return inv
