"""Static-site generation — turn the committed corpus into a static HTML site.

The :func:`bosc.site.build.build_site` orchestrator stages the markdown source
tree under ``web/`` from ``data/extracted`` + ``docs/`` and the cross-document
layer; :func:`bosc.site.render.render_site` renders that into a plain multipage
HTML site under ``site/`` (no MkDocs, no theme). Driven by the ``bosc site`` CLI
command group.
"""

from __future__ import annotations

from bosc.site.build import BuildResult, build_site
from bosc.site.render import RenderResult, render_site

__all__ = ["BuildResult", "RenderResult", "build_site", "render_site"]
