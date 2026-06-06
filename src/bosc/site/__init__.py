"""Static-site generation — turn the committed corpus into a MkDocs source tree.

The :func:`bosc.site.build.build_site` orchestrator stages ``web/`` from
``data/extracted`` + ``docs/`` and the cross-document layer; MkDocs builds it.
Driven by the ``bosc site`` CLI command group.
"""

from __future__ import annotations

from bosc.site.build import BuildResult, build_site

__all__ = ["BuildResult", "build_site"]
