"""``watermark`` command-line interface.

Commands:
    watermark version
    watermark ingest                 # inventory source documents
    watermark reconcile <file>       # arithmetic checks over a summary extraction
    watermark ask "<question>"       # ask the research agent
    watermark extract <doc-id> ...   # run an agentic extraction (seam for your data)
    watermark export                 # write the typed content bundle the frontend reads
"""

from __future__ import annotations

# Import the command submodules so their @app.command / @<sub>_app.command
# decorators run and register on the shared app + sub-apps in _base.
from watermark.cli import (  # noqa: F401
    air,
    catalog,
    gis,
    greenops,
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
    wiki,
)
from watermark.cli._base import app

__all__ = ["app"]


if __name__ == "__main__":
    app()
