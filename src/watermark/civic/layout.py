"""Where a body's meeting artifacts live under the active site's layout (#1520/#1522).

A meeting-holding body's raw binaries and extracted artifacts are keyed by the body slug.
Lima — the reference build — keeps the flat legacy layout ``<body>/meetings/`` so the committed
litigation corpus is never relocated (chain of custody). Every peer nests one level deeper under
its **site** slug, ``<site>/<body>/meetings/``, so the peer's default corpus scope ``(slug,)``
owns the whole subtree for free via segment-prefix match, and Lima's whole-tree-minus-peers scope
excludes it (the leading ``<site>`` segment is a registered peer prefix). Which site owns the flat
layout is :func:`watermark.sites.is_reference_site`, not a hardcoded slug — the same rule the
subdivisions registry follows (#1521).
"""

from __future__ import annotations

from pathlib import Path

from watermark.config import Settings, get_settings
from watermark.pipeline.corpus import assert_meeting_layout_depth
from watermark.sites import is_reference_site


def meetings_dir(root: Path, body_slug: str, settings: Settings | None = None) -> Path:
    """A body's meeting subtree under ``root`` (``data/documents`` or ``data/extracted``).

    Reference build (Lima): ``root/<body>/meetings``. Every peer: ``root/<site>/<body>/meetings``.
    Pass the same ``root`` for both the raw binaries (``settings.documents_dir``) and the extracted
    manifest/index/summaries (``settings.extracted_dir``) so the two trees stay parallel.
    """
    settings = settings or get_settings()
    out = (
        root / body_slug / "meetings"
        if is_reference_site(settings.site)
        else root / settings.site / body_slug / "meetings"
    )
    # The read path (pipeline.corpus.iter_meeting_artifacts) globs exactly one- and two-segment
    # prefixes. Nothing but this function decides the depth, so assert it here rather than
    # letting a future layout write a tree the reader silently can't see (#1839).
    assert_meeting_layout_depth(str(out.relative_to(root) / "download-manifest.yaml"))
    return out
