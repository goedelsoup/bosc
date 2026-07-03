"""Typed content-bundle export — turn the committed corpus into the frontend's JSON bundle.

:func:`watermark.site.export.export_bundle` emits the versioned, schema-validated JSON content
bundle under ``data/site/bundles/<slug>/`` (per network site; feeds + a manifest carrying a
``CONTRACT_VERSION``) that the Astro frontend reads at build time (``watermark export``). The
per-section data builders (``candidates``, ``economics``, ``gismap``, ``records``, …)
produce the typed feeds defined in :mod:`watermark.site.feeds`.
"""

from __future__ import annotations

from watermark.site.export import BundleResult, export_bundle

__all__ = [
    "BundleResult",
    "export_bundle",
]
