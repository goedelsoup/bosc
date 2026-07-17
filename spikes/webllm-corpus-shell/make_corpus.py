"""Snapshot the yidam corpus mirror into the spike's compact ``corpus.json``.

Spike #1576 (Epic #1560 D3). Projects the active site's corpus mirror
(:func:`watermark.site.corpus_mirror.build_mirror`) into the tiny node shape the demo
retrieves over — ``{id, cls, label, desc, tag, scope}`` per node. Regenerable, offline:

    uv run watermark --site lima corpus-mirror
    uv run python spikes/webllm-corpus-shell/make_corpus.py
"""

from __future__ import annotations

import json
from pathlib import Path

from watermark.config import get_settings
from watermark.site.corpus_mirror import build_mirror


def main() -> None:
    settings = get_settings()
    mirror = build_mirror(settings)
    nodes = [
        {
            "id": n.id,
            "cls": n.node_class,
            "label": n.label,
            "desc": n.description,
            "tag": n.meta.get("claim_tag") or n.meta.get("source_kind") or "",
            "scope": n.meta.get("scope") or "",
        }
        for n in mirror.nodes
    ]
    out = {
        "site": mirror.site,
        "generated_by": "watermark corpus-mirror (Epic #1560 E1/#1561) — snapshot for spike #1576",
        "counts": mirror.counts_by_class(),
        "nodes": nodes,
    }
    path = Path(__file__).parent / "corpus.json"
    path.write_text(
        json.dumps(out, ensure_ascii=False, indent=0, separators=(",", ":")), encoding="utf-8"
    )
    print(f"wrote {path} — {len(nodes)} nodes ({path.stat().st_size} bytes), site={mirror.site}")


if __name__ == "__main__":
    main()
