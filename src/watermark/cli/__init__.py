"""``bosc`` command-line interface.

Commands:
    bosc version
    bosc ingest                 # inventory source documents
    bosc reconcile <file>       # arithmetic checks over a summary extraction
    bosc ask "<question>"       # ask the research agent
    bosc extract <doc-id> ...   # run an agentic extraction (seam for your data)
    bosc export                 # write the typed content bundle the frontend reads
"""

from __future__ import annotations

# Import the command submodules so their @app.command / @<sub>_app.command
# decorators run and register on the shared app + sub-apps in _base.
from watermark.cli import (  # noqa: F401
    catalog,
    gis,
    grid,
    hydrology,
    hypotheses,
    imagery,
    leads,
    objectstore,
    oepa,
    pipeline,
    poi,
    reference,
    research,
    retrieval,
    sites,
    subdivisions,
    sweep,
)
from watermark.cli._base import app

__all__ = ["app"]


if __name__ == "__main__":
    app()
