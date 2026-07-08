"""Export the per-site contacts directory (site-level contacts).

A site's contacts are a committed, hand-curated YAML store (`data/site/contacts.yaml`, slug-scoped
via `site_scoped_path` so a sibling reads its own `site/<slug>/contacts.yaml`, never Lima's). Each
contact traces to a real committed source and carries only *public* routing (`links`) — no
fabricated people (per the data-discipline rules), and no private hand-off addresses (those stay
server-side, Phase 2). The curated spine the petition-connect + bulletin surfaces reference.

Absent store → an empty contacts feed (the frontend degrades — the section locks and asks for the
source), never Lima's contacts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from watermark.logging import get_logger
from watermark.site.feeds import ContactItem

log = get_logger(__name__)


def export_contacts(store_path: Path) -> list[ContactItem]:
    """Load a site's curated contacts store into validated :class:`ContactItem`s (empty if absent)."""
    if not store_path.exists():
        log.info("site.contacts.no_store", path=str(store_path))
        return []
    raw = yaml.safe_load(store_path.read_text(encoding="utf-8")) or {}
    entries: list[dict[str, Any]] = raw.get("contacts") or []
    items = [ContactItem.model_validate(entry) for entry in entries]
    log.info("site.contacts.built", total=len(items), path=str(store_path))
    return items
